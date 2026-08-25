"""Certificate-carrying variable elimination on a polynomial factor graph."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from functools import lru_cache
from itertools import combinations, permutations
from typing import Callable, Iterable

import sympy as sp

from worker.backend.polynomial_obligation_alignment import (
    polynomial_obligation_alignment_rank,
)
from worker.backend.polynomial_proof_residual import (
    bounded_normal_form_residual,
)


@dataclass(frozen=True)
class PolynomialCombinationWitness:
    output_polynomial: str
    left_input: str
    right_input: str
    left_multiplier: str
    right_multiplier: str
    replay_residual: str


@dataclass(frozen=True)
class LocalEliminationStep:
    variable: str
    separator_variables: tuple[str, ...]
    method: str
    input_polynomials: tuple[str, ...]
    output_polynomials: tuple[str, ...]
    replay_residuals: tuple[str, ...]
    ideal_membership_witnesses: tuple[PolynomialCombinationWitness, ...]
    nonzero_conditions: tuple[str, ...]
    replayed: bool
    certificate_sha256: str
    pivot_coefficient: str = ""
    pivot_constant: str = ""


@dataclass(frozen=True)
class NonzeroConditionTransportCertificate:
    source_polynomial: str
    target_polynomial: str
    variable: str
    pivot_coefficient: str
    pivot_constant: str
    degree: int
    replay_residual: str
    replayed: bool
    certificate_sha256: str


@dataclass(frozen=True)
class LocalEliminationResult:
    initial_polynomials: tuple[str, ...]
    remaining_polynomials: tuple[str, ...]
    remaining_variables: tuple[str, ...]
    steps: tuple[LocalEliminationStep, ...]
    eliminated_variables: tuple[str, ...]
    stopped_reason: str | None
    exact_replay: bool


def _expand_polynomial_in_generators(
    expression: sp.Expr,
    generators: frozenset[sp.Symbol],
) -> sp.Expr:
    if not generators:
        return expression
    protected: dict[sp.Expr, sp.Dummy] = {}

    def protect_coefficients(node: sp.Expr) -> None:
        if node.is_Atom:
            return
        if node.free_symbols.isdisjoint(generators):
            protected.setdefault(node, sp.Dummy("coefficient_chart"))
            return
        for argument in node.args:
            protect_coefficients(argument)

    protect_coefficients(expression)
    guarded = expression.xreplace(protected)
    expanded = sp.expand(guarded)
    return expanded.xreplace({value: key for key, value in protected.items()})


def _deduplicate(
    polynomials: Iterable[sp.Expr],
    *,
    generators: Iterable[sp.Symbol] = (),
) -> tuple[sp.Expr, ...]:
    generator_set = frozenset(generators)
    unique: dict[sp.Expr, sp.Expr] = {}
    for polynomial in polynomials:
        exact = (
            _expand_polynomial_in_generators(polynomial, generator_set)
            if generator_set
            else sp.factor(sp.expand(polynomial))
        )
        if exact == 0:
            continue
        unique.setdefault(exact, exact)
    return tuple(sorted(unique.values(), key=sp.default_sort_key))


def _term_count(polynomial: sp.Expr) -> int:
    # Inputs are normalized in the active proof generators by ``_deduplicate``.
    # Re-expanding here would expand exact coefficient charts as well, once for
    # every candidate-ranking query, although those coefficients are atomic in
    # the elimination ring.
    return len(sp.Add.make_args(polynomial))


@lru_cache(maxsize=16_384)
def _active_polynomial_term_upper_bound(
    expression: sp.Expr,
    generators: frozenset[sp.Symbol],
    cap: int,
) -> int:
    """Bound expanded terms in the active polynomial generators.

    ``_term_count`` deliberately treats a factored separator message as one
    top-level term.  That is useful for cheap ranking, but it is not a valid
    expansion budget: ``(x + 1)**20`` would otherwise cost one term.  This
    structural bound expands only the active-generator shape and treats every
    coefficient-only chart as one atom.  Returning ``cap + 1`` is sufficient
    for rejection and avoids materializing an expression that already exceeds
    the configured budget.
    """

    if expression == 0:
        return 0
    if expression.free_symbols.isdisjoint(generators):
        return 1
    if expression.is_Atom:
        return 1
    if expression.is_Add:
        total = 0
        for argument in expression.args:
            total += _active_polynomial_term_upper_bound(argument, generators, cap)
            if total > cap:
                return cap + 1
        return total
    if expression.is_Mul:
        total = 1
        for argument in expression.args:
            factor_terms = _active_polynomial_term_upper_bound(
                argument, generators, cap
            )
            if factor_terms == 0:
                return 0
            total *= factor_terms
            if total > cap:
                return cap + 1
        return total
    if expression.is_Pow:
        base, exponent = expression.args
        if exponent.is_Integer and int(exponent) >= 0:
            exponent_value = int(exponent)
            if exponent_value == 0:
                return 1
            base_terms = _active_polynomial_term_upper_bound(base, generators, cap)
            total = 1
            for _ in range(exponent_value):
                total *= base_terms
                if total > cap:
                    return cap + 1
            return total
    # Derived messages are polynomial.  An unfamiliar active-generator node is
    # conservatively over budget rather than silently admitting an explosion.
    return cap + 1


def _factor_bounded(expression: sp.Expr, *, max_operations: int = 128) -> sp.Expr:
    """Factor small expressions without re-expanding large separator charts."""

    if int(sp.count_ops(expression)) > max_operations:
        return expression
    return sp.factor(expression)


@lru_cache(maxsize=4096)
def _coefficients_in_generator(
    expression: sp.Expr,
    variable: sp.Symbol,
) -> tuple[sp.Expr, ...]:
    """Return exact coefficients without expanding the parameter chart."""

    protected: dict[sp.Expr, sp.Dummy] = {}

    def protect_coefficients(node: sp.Expr) -> None:
        if node.is_Atom:
            return
        if variable not in node.free_symbols:
            protected.setdefault(node, sp.Dummy("coefficient_chart"))
            return
        for argument in node.args:
            protect_coefficients(argument)

    protect_coefficients(expression)
    guarded = expression.xreplace(protected)
    try:
        polynomial = sp.Poly(guarded, variable, domain=sp.EX, expand=False)
    except sp.PolynomialError:
        polynomial = sp.Poly(guarded, variable, domain=sp.EX)
    restore = {value: key for key, value in protected.items()}
    return tuple(item.xreplace(restore) for item in polynomial.all_coeffs())


def _degree_in_generator(expression: sp.Expr, variable: sp.Symbol) -> int:
    return len(_coefficients_in_generator(expression, variable)) - 1


@lru_cache(maxsize=8192)
def _polynomial_degree_upper_bound(
    expression: sp.Expr,
    variable: sp.Symbol,
) -> int:
    """Compute a structural degree bound without coefficient expansion."""

    if expression.is_Atom:
        return int(expression == variable)
    if expression.is_Add:
        return max(
            _polynomial_degree_upper_bound(item, variable)
            for item in expression.args
        )
    if expression.is_Mul:
        return sum(
            _polynomial_degree_upper_bound(item, variable)
            for item in expression.args
        )
    if expression.is_Pow:
        base, exponent = expression.args
        if exponent.is_Integer and int(exponent) >= 0:
            return int(exponent) * _polynomial_degree_upper_bound(base, variable)
    if not expression.has(variable):
        return 0
    raise sp.PolynomialError(
        f"cannot derive a polynomial degree bound for {expression} in {variable}"
    )


@lru_cache(maxsize=8192)
def _polynomial_degree_capped(
    expression: sp.Expr,
    variable: sp.Symbol,
    cap: int,
) -> int:
    """Return the exact degree up to ``cap``, stopping once it is exceeded."""

    if not expression.has(variable):
        return 0
    if expression.is_Atom:
        return int(expression == variable)
    if expression.is_Add:
        degree = 0
        for item in expression.args:
            degree = max(degree, _polynomial_degree_capped(item, variable, cap))
            if degree > cap:
                return cap + 1
        return degree
    if expression.is_Mul:
        degree = 0
        for item in expression.args:
            degree += _polynomial_degree_capped(item, variable, cap - degree)
            if degree > cap:
                return cap + 1
        return degree
    if expression.is_Pow:
        base, exponent = expression.args
        if exponent.is_Integer and int(exponent) >= 0:
            exponent_value = int(exponent)
            if exponent_value == 0:
                return 0
            base_degree = _polynomial_degree_capped(
                base,
                variable,
                cap // exponent_value,
            )
            degree = exponent_value * base_degree
            return degree if degree <= cap else cap + 1
    raise sp.PolynomialError(
        f"cannot derive a capped polynomial degree for {expression} in {variable}"
    )


def _expanded_polynomial_degree(
    expression: sp.Expr,
    variable: sp.Symbol,
) -> int:
    """Read a degree from an expression already expanded in ``variable``."""

    degree = 0
    for term in sp.Add.make_args(expression):
        term_degree = 0
        for factor in sp.Mul.make_args(term):
            if factor == variable:
                term_degree += 1
                continue
            if factor.is_Pow and factor.base == variable:
                exponent = factor.exp
                if not exponent.is_Integer or int(exponent) < 0:
                    raise sp.PolynomialError(
                        f"non-polynomial exponent {exponent} for {variable}"
                    )
                term_degree += int(exponent)
                continue
            if variable in factor.free_symbols:
                # The initial equations may be expanded, but exact elimination
                # deliberately factors every derived separator message. Fall
                # back to structural degree analysis once the generator is
                # nested inside such a factor instead of misreading it as a
                # coefficient of degree zero.
                return _polynomial_degree_upper_bound(expression, variable)
        degree = max(degree, term_degree)
    return degree


def _primal_adjacency(
    polynomials: Iterable[sp.Expr],
) -> dict[sp.Symbol, set[sp.Symbol]]:
    adjacency: dict[sp.Symbol, set[sp.Symbol]] = {}
    for polynomial in polynomials:
        scope = tuple(polynomial.free_symbols)
        for variable in scope:
            adjacency.setdefault(variable, set()).update(set(scope) - {variable})
    return adjacency


def _fill_edge_count(
    variable: sp.Symbol,
    adjacency: dict[sp.Symbol, set[sp.Symbol]],
) -> int:
    neighbors = adjacency.get(variable, set())
    return sum(
        right not in adjacency.get(left, set())
        for left, right in combinations(neighbors, 2)
    )


def _scope_distance_to_targets(
    scope: frozenset[sp.Symbol],
    targets: tuple[frozenset[sp.Symbol], ...],
    adjacency: dict[sp.Symbol, set[sp.Symbol]],
) -> int:
    """Return the shortest primal-graph distance to a typed obligation image."""

    if not targets:
        return 0
    target_union = frozenset().union(*targets)
    if scope & target_union:
        return 0
    frontier = set(scope)
    visited = set(scope)
    distance = 0
    while frontier:
        distance += 1
        frontier = {
            neighbor
            for variable in frontier
            for neighbor in adjacency.get(variable, set())
            if neighbor not in visited
        }
        if frontier & target_union:
            return distance
        visited.update(frontier)
    return len(adjacency) + 1


def _obligation_alignment_rank(
    scope: frozenset[sp.Symbol],
    targets: tuple[frozenset[sp.Symbol], ...],
    adjacency: dict[sp.Symbol, set[sp.Symbol]],
) -> tuple[int, int, int]:
    if not targets:
        return (0, 0, 0)
    overlap = max(len(scope & target) for target in targets)
    symmetric_difference = min(len(scope ^ target) for target in targets)
    return (
        _scope_distance_to_targets(scope, targets, adjacency),
        -overlap,
        symmetric_difference,
    )


def _resultant_term_upper_bound(
    left: sp.Expr,
    right: sp.Expr,
    variable: sp.Symbol,
) -> int:
    """Bound determinant expansion using coefficient term counts only."""

    left_coefficients = _coefficients_in_generator(left, variable)
    right_coefficients = _coefficients_in_generator(right, variable)
    left_degree = len(left_coefficients) - 1
    right_degree = len(right_coefficients) - 1
    size = left_degree + right_degree
    rows: list[list[sp.Expr | int]] = []
    for offset in range(right_degree):
        rows.append(
            [0] * offset
            + list(left_coefficients)
            + [0] * (right_degree - 1 - offset)
        )
    for offset in range(left_degree):
        rows.append(
            [0] * offset
            + list(right_coefficients)
            + [0] * (left_degree - 1 - offset)
        )
    bound = 0
    for permutation in permutations(range(size)):
        product = 1
        for row, column in enumerate(permutation):
            coefficient = rows[row][column]
            if coefficient == 0:
                product = 0
                break
            product *= _term_count(sp.sympify(coefficient))
        bound += product
    return bound


def _select_resultant_pivot(
    bucket: tuple[sp.Expr, ...], variable: sp.Symbol
) -> sp.Expr:
    """Choose the pivot minimizing predicted total resultant expansion."""

    def rank(candidate: sp.Expr) -> tuple[int, int, int, int, int, str]:
        bounds = tuple(
            _resultant_term_upper_bound(candidate, other, variable)
            for other in bucket
            if other != candidate
        )
        return (
            max(bounds, default=0),
            sum(bounds),
            _degree_in_generator(candidate, variable),
            _term_count(candidate),
            int(sp.count_ops(candidate)),
            sp.sstr(candidate),
        )

    return min(bucket, key=rank)


def _linear_eliminate(
    variable: sp.Symbol,
    bucket: tuple[sp.Expr, ...],
    *,
    pivot_index: int | None = None,
    require_pivot_nonzero: bool = True,
) -> tuple[tuple[sp.Expr, ...], LocalEliminationStep]:
    decomposed: list[tuple[sp.Expr, sp.Expr, sp.Expr]] = []
    for polynomial in bucket:
        coefficients = _coefficients_in_generator(polynomial, variable)
        if len(coefficients) > 2:
            raise sp.PolynomialError("linear elimination received nonlinear input")
        coefficient = (
            _factor_bounded(coefficients[-2])
            if len(coefficients) == 2
            else sp.Integer(0)
        )
        constant = _factor_bounded(coefficients[-1])
        decomposed.append((polynomial, coefficient, constant))
    if pivot_index is None:
        pivot_index = min(
            range(len(decomposed)),
            key=lambda index: (
                int(sp.count_ops(decomposed[index][1])),
                _term_count(decomposed[index][0]),
            ),
        )
    pivot, pivot_coefficient, pivot_constant = decomposed[pivot_index]
    separator_variables = tuple(
        sorted(
            str(item)
            for item in set().union(*(item.free_symbols for item in bucket))
            - {variable}
        )
    )
    derived: dict[str, tuple[sp.Expr, sp.Expr, PolynomialCombinationWitness]] = {}
    for index, (polynomial, coefficient, constant) in enumerate(decomposed):
        if index == pivot_index:
            continue
        determinant = (
            pivot_coefficient * constant - coefficient * pivot_constant
        )
        output = _factor_bounded(determinant)
        if variable in output.free_symbols:
            raise AssertionError("linear local elimination retained its variable")
        # ``_coefficients_in_generator`` is an exact Poly decomposition.  In
        # those coefficient coordinates the replay is the two-by-two
        # determinant identity
        #   pc*(c*x+k) - c*(pc*x+pk) = pc*k - c*pk.
        # Constructing and fully expanding the original chart again can be
        # exponentially larger while proving the same identity.
        # The coefficient lists came from an exact Poly decomposition.  When
        # bounded factoring leaves the determinant unchanged, the replay is
        # the defining 2x2 determinant identity and does not require expanding
        # a potentially enormous coefficient chart.  Small factorizations are
        # still checked explicitly.
        residual = (
            sp.Integer(0)
            if output == determinant
            else sp.expand(output - determinant)
        )
        if residual != 0:
            raise AssertionError("linear coefficient replay did not close")
        key = sp.sstr(output)
        derived.setdefault(
            key,
            (
                output,
                residual,
                PolynomialCombinationWitness(
                    output_polynomial=key,
                    left_input=sp.sstr(polynomial),
                    right_input=sp.sstr(pivot),
                    left_multiplier=sp.sstr(pivot_coefficient),
                    right_multiplier=sp.sstr(-coefficient),
                    replay_residual=sp.sstr(residual),
                ),
            ),
        )
    ordered = tuple(derived[key] for key in sorted(derived))
    outputs = tuple(item[0] for item in ordered)
    residuals = tuple(item[1] for item in ordered)
    witnesses = tuple(item[2] for item in ordered)
    method = "linear_localization" if require_pivot_nonzero else "resultant_projection"
    material = "|".join(
        (
            str(variable),
            method,
            *(sp.sstr(item) for item in bucket),
            *(sp.sstr(item) for item in outputs),
            *(sp.sstr(item) for item in residuals),
            *(
                "::".join(
                    (
                        item.output_polynomial,
                        item.left_input,
                        item.right_input,
                        item.left_multiplier,
                        item.right_multiplier,
                    )
                )
                for item in witnesses
            ),
            sp.sstr(pivot_coefficient),
        )
    )
    replayed = all(item == 0 for item in residuals)
    return tuple(outputs), LocalEliminationStep(
        variable=str(variable),
        separator_variables=separator_variables,
        method=method,
        input_polynomials=tuple(sp.sstr(item) for item in bucket),
        output_polynomials=tuple(sp.sstr(item) for item in outputs),
        replay_residuals=tuple(sp.sstr(item) for item in residuals),
        ideal_membership_witnesses=witnesses,
        nonzero_conditions=(
            (f"{sp.sstr(pivot_coefficient)} != 0",)
            if require_pivot_nonzero
            else ()
        ),
        replayed=replayed,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
        pivot_coefficient=(
            sp.sstr(pivot_coefficient) if require_pivot_nonzero else ""
        ),
        pivot_constant=sp.sstr(pivot_constant) if require_pivot_nonzero else "",
    )


def _mixed_degree_linear_eliminate(
    variable: sp.Symbol,
    bucket: tuple[sp.Expr, ...],
    *,
    pivot_index: int,
) -> tuple[tuple[sp.Expr, ...], LocalEliminationStep]:
    """Eliminate through one source-proved linear pivot without division."""

    pivot = bucket[pivot_index]
    pivot_coefficients = _coefficients_in_generator(pivot, variable)
    if len(pivot_coefficients) != 2:
        raise sp.PolynomialError("mixed-degree pivot must be linear")
    pivot_coefficient = _factor_bounded(pivot_coefficients[-2])
    pivot_constant = _factor_bounded(pivot_coefficients[-1])
    separator_variables = tuple(
        sorted(
            str(item)
            for item in set().union(*(item.free_symbols for item in bucket))
            - {variable}
        )
    )
    derived: dict[str, tuple[sp.Expr, sp.Expr, PolynomialCombinationWitness]] = {}
    for index, polynomial in enumerate(bucket):
        if index == pivot_index:
            continue
        univariate = sp.Poly(polynomial, variable, domain="EX")
        degree = max(int(univariate.degree()), 0)
        transformed = sp.expand(
            sum(
                univariate.nth(power)
                * (-pivot_constant) ** power
                * pivot_coefficient ** (degree - power)
                for power in range(degree + 1)
            )
        )
        quotient = sp.expand(
            sum(
                univariate.nth(power)
                * pivot_coefficient ** (degree - power)
                * sum(
                    (pivot_coefficient * variable) ** (power - 1 - offset)
                    * (-pivot_constant) ** offset
                    for offset in range(power)
                )
                for power in range(1, degree + 1)
            )
        )
        output = _factor_bounded(transformed)
        if variable in output.free_symbols:
            raise AssertionError("mixed-degree localization retained its variable")
        residual = sp.expand(output - transformed)
        if residual != 0:
            raise AssertionError("mixed-degree localization did not replay")
        key = sp.sstr(output)
        derived.setdefault(
            key,
            (
                output,
                residual,
                PolynomialCombinationWitness(
                    output_polynomial=key,
                    left_input=sp.sstr(polynomial),
                    right_input=sp.sstr(pivot),
                    left_multiplier=sp.sstr(pivot_coefficient**degree),
                    right_multiplier=sp.sstr(-quotient),
                    replay_residual=sp.sstr(residual),
                ),
            ),
        )
    ordered = tuple(derived[key] for key in sorted(derived))
    outputs = tuple(item[0] for item in ordered)
    residuals = tuple(item[1] for item in ordered)
    witnesses = tuple(item[2] for item in ordered)
    material = "|".join(
        (
            str(variable),
            "mixed_degree_linear_localization",
            *(sp.sstr(item) for item in bucket),
            *(sp.sstr(item) for item in outputs),
            *(
                "::".join(
                    (
                        item.output_polynomial,
                        item.left_input,
                        item.right_input,
                        item.left_multiplier,
                        item.right_multiplier,
                    )
                )
                for item in witnesses
            ),
            sp.sstr(pivot_coefficient),
        )
    )
    return outputs, LocalEliminationStep(
        variable=str(variable),
        separator_variables=separator_variables,
        method="mixed_degree_linear_localization",
        input_polynomials=tuple(sp.sstr(item) for item in bucket),
        output_polynomials=tuple(sp.sstr(item) for item in outputs),
        replay_residuals=tuple(sp.sstr(item) for item in residuals),
        ideal_membership_witnesses=witnesses,
        nonzero_conditions=(f"{sp.sstr(pivot_coefficient)} != 0",),
        replayed=all(item == 0 for item in residuals),
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
        pivot_coefficient=sp.sstr(pivot_coefficient),
        pivot_constant=sp.sstr(pivot_constant),
    )


def transport_nonzero_conditions_through_local_elimination(
    expressions: Iterable[sp.Expr],
    steps: Iterable[LocalEliminationStep],
) -> tuple[
    tuple[sp.Expr, ...],
    tuple[NonzeroConditionTransportCertificate, ...],
    tuple[str, ...],
]:
    """Transport source nonzero assumptions through certified localizations.

    For a pivot ``c*x+k=0`` with source-proved ``c != 0``, a condition
    ``h(x) != 0`` is equivalent to ``c**deg(h) h(-k/c) != 0``.  Resultant
    projections do not select a branch and therefore cannot transport a
    condition involving the eliminated variable; such conditions are
    reported rather than silently reused in the smaller polynomial ring.
    """

    active = [sp.factor(item) for item in expressions if item != 0]
    certificates: list[NonzeroConditionTransportCertificate] = []
    unresolved: list[str] = []
    for step in steps:
        variable = sp.Symbol(step.variable)
        if not any(variable in item.free_symbols for item in active):
            continue
        if not step.pivot_coefficient:
            retained: list[sp.Expr] = []
            for item in active:
                if variable in item.free_symbols:
                    unresolved.append(sp.sstr(item))
                else:
                    retained.append(item)
            active = retained
            continue
        coefficient = sp.sympify(step.pivot_coefficient)
        constant = sp.sympify(step.pivot_constant)
        pivot = sp.expand(coefficient * variable + constant)
        transported: list[sp.Expr] = []
        for source in active:
            if variable not in source.free_symbols:
                transported.append(source)
                continue
            try:
                polynomial = sp.Poly(source, variable, domain="EX")
            except sp.PolynomialError:
                unresolved.append(sp.sstr(source))
                continue
            degree = max(int(polynomial.degree()), 0)
            target = sp.factor(
                sum(
                    polynomial.nth(power)
                    * (-constant) ** power
                    * coefficient ** (degree - power)
                    for power in range(degree + 1)
                )
            )
            quotient = sp.expand(
                sum(
                    polynomial.nth(power)
                    * coefficient ** (degree - power)
                    * sum(
                        (coefficient * variable) ** (power - 1 - offset)
                        * (-constant) ** offset
                        for offset in range(power)
                    )
                    for power in range(1, degree + 1)
                )
            )
            residual = sp.expand(
                target - coefficient**degree * source + pivot * quotient
            )
            if residual != 0 or target == 0:
                unresolved.append(sp.sstr(source))
                continue
            material = "|".join(
                (
                    sp.sstr(source),
                    sp.sstr(target),
                    str(variable),
                    sp.sstr(coefficient),
                    sp.sstr(constant),
                    str(degree),
                )
            )
            certificates.append(
                NonzeroConditionTransportCertificate(
                    source_polynomial=sp.sstr(source),
                    target_polynomial=sp.sstr(target),
                    variable=str(variable),
                    pivot_coefficient=sp.sstr(coefficient),
                    pivot_constant=sp.sstr(constant),
                    degree=degree,
                    replay_residual=sp.sstr(residual),
                    replayed=True,
                    certificate_sha256=hashlib.sha256(
                        material.encode()
                    ).hexdigest(),
                )
            )
            transported.append(target)
        active = transported
    deduplicated = _deduplicate(active)
    return deduplicated, tuple(certificates), tuple(sorted(set(unresolved)))


def _resultant_eliminate(
    variable: sp.Symbol,
    bucket: tuple[sp.Expr, ...],
) -> tuple[tuple[sp.Expr, ...], LocalEliminationStep]:
    pivot = _select_resultant_pivot(bucket, variable)
    separator_variables = tuple(
        sorted(
            str(item)
            for item in set().union(*(item.free_symbols for item in bucket))
            - {variable}
        )
    )
    derived: dict[str, tuple[sp.Expr, sp.Expr, PolynomialCombinationWitness]] = {}
    for polynomial in bucket:
        if polynomial == pivot:
            continue
        raw_resultant = sp.resultant(pivot, polynomial, variable)
        output = sp.factor(raw_resultant)
        if variable in output.free_symbols:
            raise AssertionError("resultant retained its eliminated variable")
        try:
            left, right, gcd = sp.gcdex(pivot, polynomial, variable)
            quotient = sp.cancel(output / gcd)
            left_multiplier = sp.cancel(left * quotient)
            right_multiplier = sp.cancel(right * quotient)
            polynomial_witness = (
                sp.denom(left_multiplier) == 1 and sp.denom(right_multiplier) == 1
            )
            residual = sp.cancel(
                output - left_multiplier * pivot - right_multiplier * polynomial
            )
        except (sp.PolynomialError, ValueError, ZeroDivisionError):
            left_multiplier = sp.nan
            right_multiplier = sp.nan
            polynomial_witness = False
            residual = sp.nan
        output = sp.factor(sp.expand(output))
        key = sp.sstr(output)
        derived.setdefault(
            key,
            (
                output,
                residual,
                PolynomialCombinationWitness(
                    output_polynomial=key,
                    left_input=sp.sstr(pivot),
                    right_input=sp.sstr(polynomial),
                    left_multiplier=sp.sstr(left_multiplier),
                    right_multiplier=sp.sstr(right_multiplier),
                    replay_residual=sp.sstr(residual),
                ),
            ),
        )
        if not polynomial_witness:
            break
    ordered = tuple(derived[key] for key in sorted(derived))
    outputs = tuple(item[0] for item in ordered)
    residuals = tuple(item[1] for item in ordered)
    witnesses = tuple(item[2] for item in ordered)
    material = "|".join(
        (
            str(variable),
            "resultant_projection",
            *(sp.sstr(item) for item in bucket),
            *(sp.sstr(item) for item in outputs),
            *(sp.sstr(item) for item in residuals),
            *(
                "::".join(
                    (
                        item.output_polynomial,
                        item.left_input,
                        item.right_input,
                        item.left_multiplier,
                        item.right_multiplier,
                    )
                )
                for item in witnesses
            ),
        )
    )
    replayed = len(witnesses) == len(outputs) and all(item == 0 for item in residuals)
    return tuple(outputs), LocalEliminationStep(
        variable=str(variable),
        separator_variables=separator_variables,
        method="resultant_projection",
        input_polynomials=tuple(sp.sstr(item) for item in bucket),
        output_polynomials=tuple(sp.sstr(item) for item in outputs),
        replay_residuals=tuple(sp.sstr(item) for item in residuals),
        ideal_membership_witnesses=witnesses,
        nonzero_conditions=(),
        replayed=replayed,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )


def eliminate_local_linear_variables(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    *,
    protected_variables: Iterable[sp.Symbol] = (),
    max_steps: int | None = None,
    max_output_terms: int = 20_000,
    max_resultant_degree: int = 2,
    max_separator_variables: int | None = None,
    ordering_strategy: str = "local_degree",
    guidance_polynomials: Iterable[sp.Expr] = (),
    guidance_branches: Iterable[Iterable[sp.Expr]] = (),
    obligation_cost_slack: int = 1,
    residual_candidate_limit: int = 2,
    residual_max_pairs: int = 1,
    residual_max_basis_size: int = 32,
    nonzero_condition_acceptor: Callable[[str], bool] | None = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
    pre_normalized: bool = False,
) -> LocalEliminationResult:
    """Eliminate local variables without constructing a global basis.

    Each step is exact in the localization where the selected pivot coefficient
    is nonzero. Low-degree nonlinear buckets use exact resultants. Higher-degree
    variables are left untouched; no heuristic consequence is accepted as proof.
    """

    raw_factors = tuple(sp.sympify(item) for item in polynomials)
    remaining = set(variables)
    protected = set(protected_variables)
    if not remaining - protected:
        serialized = tuple(
            sp.sstr(item) for item in raw_factors if sp.sympify(item) != 0
        )
        return LocalEliminationResult(
            initial_polynomials=serialized,
            remaining_polynomials=serialized,
            remaining_variables=tuple(sorted(map(str, remaining))),
            steps=(),
            eliminated_variables=(),
            stopped_reason="no_unprotected_variables",
            exact_replay=True,
        )

    if progress_callback is not None:
        progress_callback(
            {
                "stage": "normalization_started",
                "polynomial_count": len(raw_factors),
                "variable_count": len(remaining),
                "pre_normalized": pre_normalized,
            }
        )
    if pre_normalized:
        initial_factors = tuple(
            sorted(
                {item for item in raw_factors if item != 0},
                key=sp.default_sort_key,
            )
        )
    else:
        initial_factors = _deduplicate(raw_factors, generators=remaining)
    if progress_callback is not None:
        progress_callback(
            {
                "stage": "normalization_completed",
                "polynomial_count": len(initial_factors),
            }
        )
    if ordering_strategy not in {
        "local_degree",
        "min_fill",
        "obligation_conditioned",
        "residual_conditioned",
    }:
        raise ValueError(f"unknown ordering strategy: {ordering_strategy}")
    if obligation_cost_slack < 0:
        raise ValueError("obligation_cost_slack must be nonnegative")
    if residual_candidate_limit < 1:
        raise ValueError("residual_candidate_limit must be positive")
    target_polynomials = tuple(
        sp.expand(sp.sympify(item)) for item in guidance_polynomials
    )
    raw_target_branches = tuple(tuple(branch) for branch in guidance_branches)
    target_branches = tuple(
        tuple(sp.expand(sp.sympify(item)) for item in branch)
        for branch in raw_target_branches
        if branch
    )
    target_scopes = tuple(
        frozenset(item.free_symbols)
        for item in target_polynomials
        if item.free_symbols
    )
    factors = initial_factors
    steps: list[LocalEliminationStep] = []
    eliminated: list[str] = []
    stopped_reason: str | None = None
    separator_blocked = False
    residual_messages: tuple[sp.Expr, ...] = ()

    while True:
        if max_steps is not None and len(steps) >= max_steps:
            stopped_reason = "max_steps"
            break
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "candidate_scan_started",
                    "remaining_variable_count": len(remaining),
                    "polynomial_count": len(factors),
                }
            )
        adjacency = _primal_adjacency(factors)
        candidates: list[
            tuple[
                tuple[int, int, int, int, int],
                tuple[int, ...],
                sp.Symbol,
                tuple[sp.Expr, ...],
                int,
                tuple[sp.Expr, ...],
            ]
        ] = []
        for variable in remaining - protected:
            bucket = tuple(item for item in factors if variable in item.free_symbols)
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "candidate_degree_scan_started",
                        "variable": str(variable),
                        "bucket_size": len(bucket),
                    }
                )
            if not bucket:
                candidates.append(
                    (
                        (0, 0, 0, 0, 0),
                        (0, 0, 0, 0, 0),
                        variable,
                        bucket,
                        0,
                        (),
                    )
                )
                continue
            degrees: list[int] = []
            valid = True
            for polynomial in bucket:
                try:
                    degree = (
                        _expanded_polynomial_degree(polynomial, variable)
                        if pre_normalized
                        else _polynomial_degree_capped(
                            polynomial,
                            variable,
                            max_resultant_degree,
                        )
                    )
                except sp.PolynomialError:
                    valid = False
                    break
                if degree > max_resultant_degree:
                    valid = False
                    break
                degrees.append(degree)
            if not valid:
                continue
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "candidate_degree_scan_completed",
                        "variable": str(variable),
                        "maximum_degree": max(degrees, default=0),
                    }
                )
            neighbors = set().union(*(item.free_symbols for item in bucket)) - {
                variable
            }
            if (
                max_separator_variables is not None
                and len(neighbors) > max_separator_variables
            ):
                separator_blocked = True
                continue
            fill_edges = (
                _fill_edge_count(variable, adjacency)
                if ordering_strategy in {
                    "min_fill",
                    "obligation_conditioned",
                    "residual_conditioned",
                }
                else len(bucket)
            )
            base_rank = (
                max(degrees, default=0),
                fill_edges,
                len(neighbors),
                len(bucket),
                sum(_term_count(item) for item in bucket),
            )
            projected_messages: tuple[sp.Expr, ...] = ()
            if (
                ordering_strategy in {
                    "obligation_conditioned",
                    "residual_conditioned",
                }
                and target_polynomials
                and max(degrees, default=0) <= 1
                and len(bucket) >= 2
            ):
                try:
                    preview_pivot_index = None
                    if nonzero_condition_acceptor is not None:
                        accepted_previews: list[
                            tuple[tuple[int, int, str], int]
                        ] = []
                        for index, polynomial in enumerate(bucket):
                            coefficients = _coefficients_in_generator(
                                polynomial, variable
                            )
                            coefficient = sp.factor(
                                coefficients[-2]
                                if len(coefficients) >= 2
                                else sp.Integer(0)
                            )
                            if nonzero_condition_acceptor(
                                f"{sp.sstr(coefficient)} != 0"
                            ):
                                accepted_previews.append(
                                    (
                                        (
                                            int(sp.count_ops(coefficient)),
                                            _term_count(polynomial),
                                            sp.sstr(polynomial),
                                        ),
                                        index,
                                    )
                                )
                        if not accepted_previews:
                            continue
                        preview_pivot_index = min(accepted_previews)[1]
                    projected_messages, _ = _linear_eliminate(
                        variable,
                        bucket,
                        pivot_index=preview_pivot_index,
                    )
                except (AssertionError, sp.PolynomialError, ValueError):
                    projected_messages = ()
            support_rank = (
                *polynomial_obligation_alignment_rank(
                    projected_messages, target_polynomials
                ),
                *_obligation_alignment_rank(
                    frozenset(neighbors), target_scopes, adjacency
                ),
            )
            if (
                ordering_strategy == "residual_conditioned"
                and target_branches
                and not projected_messages
                and max(degrees, default=0) == 2
                and len(bucket) >= 2
            ):
                pivot = _select_resultant_pivot(bucket, variable)
                if all(
                    _resultant_term_upper_bound(pivot, polynomial, variable)
                    <= max_output_terms
                    for polynomial in bucket
                    if polynomial != pivot
                ):
                    try:
                        projected_messages, _ = _resultant_eliminate(
                            variable, bucket
                        )
                    except (AssertionError, sp.PolynomialError, ValueError):
                        projected_messages = ()
            candidates.append(
                (
                    base_rank,
                    support_rank,
                    variable,
                    bucket,
                    max(degrees, default=0),
                    projected_messages,
                )
            )
        if not candidates:
            stopped_reason = (
                "separator_budget"
                if separator_blocked
                else "no_locally_linear_variable"
            )
            break
        selected: (
            tuple[
                sp.Symbol,
                tuple[sp.Expr, ...],
                tuple[sp.Expr, ...],
                LocalEliminationStep | None,
            ]
            | None
        ) = None
        if ordering_strategy in {
            "obligation_conditioned",
            "residual_conditioned",
        }:
            minimum_degree = min(item[0][0] for item in candidates)
            degree_pool = [
                item for item in candidates if item[0][0] == minimum_degree
            ]
            minimum_fill = min(item[0][1] for item in degree_pool)
            fill_pool = [
                item
                for item in degree_pool
                if item[0][1] <= minimum_fill + obligation_cost_slack
            ]
            minimum_width = min(item[0][2] for item in fill_pool)
            bounded = [
                item
                for item in fill_pool
                if item[0][2] <= minimum_width + obligation_cost_slack
            ]
            if ordering_strategy == "residual_conditioned" and target_branches:
                residual_candidates: list[
                    tuple[
                        tuple[int, int, int, int, int],
                        tuple[int, ...],
                        sp.Symbol,
                        tuple[sp.Expr, ...],
                        int,
                        tuple[sp.Expr, ...],
                    ]
                ] = []
                shortlist = sorted(
                    bounded,
                    key=lambda item: (item[1], item[0], str(item[2])),
                )[:residual_candidate_limit]
                for item in shortlist:
                    projected_messages = item[5]
                    # Rank exact separator messages, not the complete
                    # construction ideal. This measures what the action makes
                    # available to the next proof agent and keeps evaluation
                    # incremental.
                    simulated = _deduplicate(
                        (*residual_messages, *projected_messages)
                    )
                    try:
                        residual = bounded_normal_form_residual(
                            simulated,
                            target_branches,
                            max_pairs=residual_max_pairs,
                            max_basis_size=residual_max_basis_size,
                            max_polynomial_terms=max_output_terms,
                            max_certificate_terms=max(
                                4_096, max_output_terms * 4
                            ),
                            linear_span_reduction=True,
                        )
                        residual_rank = residual.selected_rank
                    except (ValueError, sp.PolynomialError) as exc:
                        residual_rank = (10**9, 10**9, 10**9, 10**9)
                        if progress_callback is not None:
                            progress_callback(
                                {
                                    "stage": "residual_evaluation_failed",
                                    "variable": str(item[2]),
                                    "reason": f"{type(exc).__name__}: {exc}",
                                    "message_count": len(simulated),
                                    "branch_count": len(target_branches),
                                }
                            )
                    residual_candidates.append(
                        (
                            item[0],
                            (*residual_rank, *item[1]),
                            item[2],
                            item[3],
                            item[4],
                            item[5],
                        )
                    )
                bounded = residual_candidates
            selected_variables = {item[2] for item in bounded}
            fallback_candidates = [
                (
                    item[0],
                    (
                        *((10**9,) * 4),
                        *item[1],
                    )
                    if ordering_strategy == "residual_conditioned"
                    and target_branches
                    else item[1],
                    item[2],
                    item[3],
                    item[4],
                    item[5],
                )
                for item in candidates
                if item[2] not in selected_variables
            ]
            ordered_candidates = sorted(
                bounded,
                key=lambda item: (item[1], item[0], str(item[2])),
            ) + sorted(
                fallback_candidates,
                key=lambda item: (item[0], str(item[2])),
            )
            eligible_candidate_count = len(bounded)
        else:
            ordered_candidates = sorted(
                candidates, key=lambda item: (item[0], str(item[2]))
            )
            eligible_candidate_count = len(candidates)
        for (
            cost_rank,
            alignment_rank,
            variable,
            bucket,
            maximum_degree,
            _,
        ) in ordered_candidates:
            if not bucket:
                selected = (variable, bucket, (), None)
                break
            if maximum_degree <= 1:
                pivot_index = None
                use_division_free_resultant = False
                if nonzero_condition_acceptor is not None:
                    accepted_pivots: list[tuple[tuple[int, int, str], int]] = []
                    for index, polynomial in enumerate(bucket):
                        coefficients = _coefficients_in_generator(
                            polynomial, variable
                        )
                        coefficient = sp.factor(
                            coefficients[-2]
                            if len(coefficients) >= 2
                            else sp.Integer(0)
                        )
                        condition = f"{sp.sstr(coefficient)} != 0"
                        if nonzero_condition_acceptor(condition):
                            accepted_pivots.append(
                                (
                                    (
                                        int(sp.count_ops(coefficient)),
                                        _term_count(polynomial),
                                        sp.sstr(polynomial),
                                    ),
                                    index,
                                )
                            )
                    if not accepted_pivots:
                        pivot = _select_resultant_pivot(bucket, variable)
                        if len(bucket) < 2 or any(
                            _resultant_term_upper_bound(
                                pivot, polynomial, variable
                            )
                            > max_output_terms
                            for polynomial in bucket
                            if polynomial != pivot
                        ):
                            continue
                        use_division_free_resultant = True
                    else:
                        pivot_index = min(accepted_pivots)[1]
                if progress_callback is not None:
                    progress_callback(
                        {
                            "stage": "candidate_started",
                            "variable": str(variable),
                            "method": (
                                "linear_resultant_projection"
                                if use_division_free_resultant
                                else "linear_localization"
                            ),
                            "bucket_size": len(bucket),
                            "ordering_strategy": ordering_strategy,
                            "candidate_count": len(candidates),
                            "eligible_candidate_count": eligible_candidate_count,
                            "cost_rank": list(cost_rank),
                            "obligation_alignment_rank": list(alignment_rank),
                            "proof_residual_rank": (
                                list(alignment_rank[:4])
                                if ordering_strategy == "residual_conditioned"
                                else None
                            ),
                            "separator_width": len(
                                set().union(*(item.free_symbols for item in bucket))
                                - {variable}
                            ),
                        }
                    )
                if use_division_free_resultant:
                    # For linear equations the resultant is the exact 2x2
                    # coefficient determinant.  Building a Sylvester matrix
                    # and running gcdex can dominate the whole proof even
                    # though the direct ideal witness is simply
                    #   a*(c*x+d) - c*(a*x+b) = a*d-c*b.
                    outputs, certificate = _linear_eliminate(
                        variable,
                        bucket,
                        require_pivot_nonzero=False,
                    )
                else:
                    outputs, certificate = _linear_eliminate(
                        variable,
                        bucket,
                        pivot_index=pivot_index,
                    )
            else:
                mixed_linear_pivots: list[tuple[tuple[int, int, str], int]] = []
                if nonzero_condition_acceptor is not None:
                    for index, polynomial in enumerate(bucket):
                        coefficients = _coefficients_in_generator(
                            polynomial, variable
                        )
                        if len(coefficients) != 2:
                            continue
                        coefficient = sp.factor(coefficients[-2])
                        if nonzero_condition_acceptor(
                            f"{sp.sstr(coefficient)} != 0"
                        ):
                            mixed_linear_pivots.append(
                                (
                                    (
                                        int(sp.count_ops(coefficient)),
                                        _term_count(polynomial),
                                        sp.sstr(polynomial),
                                    ),
                                    index,
                                )
                            )
                if mixed_linear_pivots:
                    pivot_index = min(mixed_linear_pivots)[1]
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "stage": "candidate_started",
                                "variable": str(variable),
                                "method": "mixed_degree_linear_localization",
                                "bucket_size": len(bucket),
                                "ordering_strategy": ordering_strategy,
                                "candidate_count": len(candidates),
                                "eligible_candidate_count": eligible_candidate_count,
                                "cost_rank": list(cost_rank),
                                "obligation_alignment_rank": list(alignment_rank),
                                "proof_residual_rank": None,
                                "separator_width": len(
                                    set().union(
                                        *(item.free_symbols for item in bucket)
                                    )
                                    - {variable}
                                ),
                            }
                        )
                    outputs, certificate = _mixed_degree_linear_eliminate(
                        variable,
                        bucket,
                        pivot_index=pivot_index,
                    )
                else:
                    pivot = _select_resultant_pivot(bucket, variable)
                    if any(
                        _resultant_term_upper_bound(pivot, polynomial, variable)
                        > max_output_terms
                        for polynomial in bucket
                        if polynomial != pivot
                    ):
                        continue
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "stage": "candidate_started",
                                "variable": str(variable),
                                "method": "resultant_projection",
                                "bucket_size": len(bucket),
                                "ordering_strategy": ordering_strategy,
                                "candidate_count": len(candidates),
                                "eligible_candidate_count": eligible_candidate_count,
                                "cost_rank": list(cost_rank),
                                "obligation_alignment_rank": list(alignment_rank),
                                "proof_residual_rank": (
                                    list(alignment_rank[:4])
                                    if ordering_strategy == "residual_conditioned"
                                    else None
                                ),
                                "separator_width": len(
                                    set().union(
                                        *(item.free_symbols for item in bucket)
                                    )
                                    - {variable}
                                ),
                                "predicted_max_output_terms": max(
                                    (
                                        _resultant_term_upper_bound(
                                            pivot,
                                            polynomial,
                                            variable,
                                        )
                                        for polynomial in bucket
                                        if polynomial != pivot
                                    ),
                                    default=0,
                                ),
                            }
                        )
                    outputs, certificate = _resultant_eliminate(variable, bucket)
            if not certificate.replayed:
                continue
            if (
                certificate.method == "resultant_projection"
                and outputs
                and all(sp.expand(item) == 0 for item in outputs)
            ):
                # A zero resultant only says that the bucket shares an
                # unmodelled component.  Removing the variable here discards
                # the very branch information that a later localization can
                # use, while adding no polynomial consequence at all.
                continue
            if nonzero_condition_acceptor is not None and any(
                not nonzero_condition_acceptor(condition)
                for condition in certificate.nonzero_conditions
            ):
                continue
            output_generators = frozenset(remaining - {variable})
            output_term_bounds = tuple(
                _active_polynomial_term_upper_bound(
                    item,
                    output_generators,
                    max_output_terms,
                )
                for item in outputs
            )
            if all(item <= max_output_terms for item in output_term_bounds):
                selected = (variable, bucket, outputs, certificate)
                break
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "candidate_rejected",
                        "variable": str(variable),
                        "reason": "active_term_budget",
                        "output_term_upper_bounds": list(output_term_bounds),
                        "max_output_terms": max_output_terms,
                    }
                )
        if selected is None:
            stopped_reason = "term_budget"
            break
        variable, bucket, outputs, certificate = selected
        next_remaining = remaining - {variable}
        factors = (
            _deduplicate(
                (item for item in factors if variable not in item.free_symbols),
                generators=next_remaining,
            )
            + outputs
        )
        # Normalize only in the variables that remain in the local polynomial
        # ring.  Re-expanding coefficient-only geometry charts here repeats a
        # large exact computation after every elimination step without changing
        # the ideal or the certificate.
        factors = _deduplicate(factors, generators=next_remaining)
        remaining.remove(variable)
        eliminated.append(str(variable))
        if certificate is not None:
            steps.append(certificate)
            if ordering_strategy == "residual_conditioned":
                residual_messages = _deduplicate(
                    (*residual_messages, *outputs),
                    generators=next_remaining,
                )
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "step_completed",
                    "variable": str(variable),
                    "method": certificate.method if certificate is not None else "unused",
                    "remaining_variable_count": len(remaining),
                    "remaining_polynomial_count": len(factors),
                    "output_polynomial_count": len(outputs),
                    "exact_replay": bool(certificate is None or certificate.replayed),
                    "checkpoint_node": (
                        asdict(certificate) if certificate is not None else None
                    ),
                }
            )

    return LocalEliminationResult(
        initial_polynomials=tuple(sp.sstr(item) for item in initial_factors),
        remaining_polynomials=tuple(sp.sstr(item) for item in factors),
        remaining_variables=tuple(sorted(str(item) for item in remaining)),
        steps=tuple(steps),
        eliminated_variables=tuple(eliminated),
        stopped_reason=stopped_reason,
        exact_replay=all(item.replayed for item in steps),
    )
