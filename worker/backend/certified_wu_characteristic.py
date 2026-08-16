"""Certificate-carrying Wu-style triangularization for polynomial systems.

The implementation follows the control structure used by GCLC's Wu prover:
choose the highest dependent variable, select a minimum-degree pivot, and use
pseudo-division until one pivot remains for that variable.  Every reduction is
stored as an exact identity, so a result can be replayed without trusting this
module or an external CAS.
"""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from itertools import combinations
from typing import Callable, Iterable

import sympy as sp
from sympy.polys.domains import QQ
from sympy.polys.rings import PolyElement, ring


@dataclass(frozen=True)
class StructuralVariableMatching:
    equation_to_variable: tuple[tuple[int, str], ...]
    dependent_variables: tuple[str, ...]
    parameter_variables: tuple[str, ...]
    unmatched_equations: tuple[int, ...]
    complete: bool


@dataclass(frozen=True)
class StructuralGoalCone:
    equation_indices: tuple[int, ...]
    variable_names: tuple[str, ...]
    dropped_equation_indices: tuple[int, ...]
    matching_complete: bool


@dataclass(frozen=True)
class CertifiedPseudoDivision:
    phase: str
    variable: str
    dividend: str
    divisor: str
    multiplier: str
    quotient: str
    remainder_multiplier: str
    remainder: str
    dividend_degree: int
    divisor_degree: int
    replay_residual: str
    nonzero_obligation: str | None
    normalization_nonzero_obligation: str | None
    replayed: bool
    certificate_sha256: str


@dataclass(frozen=True)
class WuTriangularPivot:
    variable: str
    polynomial: str
    degree: int


@dataclass(frozen=True)
class CertifiedWuResult:
    initial_polynomials: tuple[str, ...]
    variables: tuple[str, ...]
    elimination_order: tuple[str, ...]
    vanished_variables: tuple[str, ...]
    matching: StructuralVariableMatching
    pivots: tuple[WuTriangularPivot, ...]
    parameter_conditions: tuple[str, ...]
    triangulation_steps: tuple[CertifiedPseudoDivision, ...]
    goal_steps: tuple[CertifiedPseudoDivision, ...]
    goal_polynomial: str
    final_remainder: str
    nonzero_obligations: tuple[str, ...]
    stopped_reason: str | None
    triangularization_complete: bool
    all_identities_replayed: bool
    conditional_goal_proved: bool
    unconditional_goal_proved: bool
    maximum_term_count: int
    elapsed_seconds: float


def _text(expression: sp.Expr) -> str:
    return sp.sstr(sp.expand(expression))


def _term_count(expression: sp.Expr) -> int:
    return len(sp.Add.make_args(sp.expand(expression)))


def _degree(expression: sp.Expr, variable: sp.Symbol) -> int:
    value = sp.degree(expression, variable)
    return -1 if value is sp.S.NegativeInfinity else int(value)


def _deduplicate(polynomials: Iterable[sp.Expr]) -> tuple[sp.Expr, ...]:
    unique: dict[str, sp.Expr] = {}
    for polynomial in polynomials:
        expanded = sp.expand(polynomial)
        if expanded == 0:
            continue
        unique.setdefault(sp.sstr(expanded), expanded)
    return tuple(unique.values())


def structural_variable_matching(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
) -> StructuralVariableMatching:
    """Match equations to dependent variables using only the incidence graph.

    Later variables are tried first.  For construction-generated systems this
    leaves early gauge/free variables unmatched without relying on their names.
    """

    equations = tuple(sp.expand(item) for item in polynomials)
    ordered_variables = tuple(variables)
    variable_rank = {variable: index for index, variable in enumerate(ordered_variables)}
    variable_to_equation: dict[sp.Symbol, int] = {}

    def augment(equation_index: int, seen: set[sp.Symbol]) -> bool:
        candidates = sorted(
            equations[equation_index].free_symbols & set(ordered_variables),
            key=lambda variable: variable_rank[variable],
            reverse=True,
        )
        for variable in candidates:
            if variable in seen:
                continue
            seen.add(variable)
            owner = variable_to_equation.get(variable)
            if owner is None or augment(owner, seen):
                variable_to_equation[variable] = equation_index
                return True
        return False

    for equation_index in reversed(range(len(equations))):
        augment(equation_index, set())

    equation_to_variable = {
        equation: variable for variable, equation in variable_to_equation.items()
    }
    unmatched = tuple(
        index for index in range(len(equations)) if index not in equation_to_variable
    )
    dependent = tuple(
        variable
        for variable in ordered_variables
        if variable in variable_to_equation
    )
    parameters = tuple(
        variable
        for variable in ordered_variables
        if variable not in variable_to_equation
    )
    return StructuralVariableMatching(
        equation_to_variable=tuple(
            (index, str(equation_to_variable[index]))
            for index in sorted(equation_to_variable)
        ),
        dependent_variables=tuple(str(item) for item in dependent),
        parameter_variables=tuple(str(item) for item in parameters),
        unmatched_equations=unmatched,
        complete=not unmatched,
    )


def structural_goal_cone(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal_polynomial: sp.Expr,
) -> StructuralGoalCone:
    """Trace the construction equations needed by goal variables.

    The relation is induced only by the equation-to-variable matching.  The
    returned equations form a subset of the hypotheses, so a certificate built
    from the cone remains valid for the full system.  No omitted equation is
    ever inferred or treated as proved.
    """

    equations = tuple(sp.expand(item) for item in polynomials)
    ordered_variables = tuple(variables)
    matching = structural_variable_matching(equations, ordered_variables)
    defining_equation = {
        variable_name: equation_index
        for equation_index, variable_name in matching.equation_to_variable
    }
    pending = [
        str(item)
        for item in sorted(
            sp.expand(goal_polynomial).free_symbols & set(ordered_variables),
            key=lambda item: ordered_variables.index(item),
        )
    ]
    seen_variables = set(pending)
    selected_equations: set[int] = set()
    while pending:
        variable_name = pending.pop()
        equation_index = defining_equation.get(variable_name)
        if equation_index is None or equation_index in selected_equations:
            continue
        selected_equations.add(equation_index)
        for dependency in equations[equation_index].free_symbols:
            name = str(dependency)
            if dependency in ordered_variables and name not in seen_variables:
                seen_variables.add(name)
                pending.append(name)
    selected = tuple(sorted(selected_equations))
    return StructuralGoalCone(
        equation_indices=selected,
        variable_names=tuple(
            str(item) for item in ordered_variables if str(item) in seen_variables
        ),
        dropped_equation_indices=tuple(
            index for index in range(len(equations)) if index not in selected_equations
        ),
        matching_complete=matching.complete,
    )


def structural_min_fill_elimination_order(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    *,
    protected_variables: Iterable[sp.Symbol] = (),
) -> tuple[sp.Symbol, ...]:
    """Choose a deterministic sparse elimination order from the primal graph.

    Variables occurring in the goal are protected until unprotected variables
    with the same structural cost have been removed.  No variable name,
    construction type, or benchmark identifier participates in the ranking.
    """

    ordered_variables = tuple(variables)
    variable_set = set(ordered_variables)
    protected = set(protected_variables) & variable_set
    adjacency = {variable: set() for variable in ordered_variables}
    incidence = {variable: 0 for variable in ordered_variables}
    for polynomial in polynomials:
        scope = set(sp.expand(polynomial).free_symbols) & variable_set
        for variable in scope:
            incidence[variable] += 1
            adjacency[variable].update(scope - {variable})

    remaining = set(ordered_variables)
    result: list[sp.Symbol] = []
    rank = {variable: index for index, variable in enumerate(ordered_variables)}
    while remaining:
        def fill_count(variable: sp.Symbol) -> int:
            neighbors = adjacency[variable] & remaining
            return sum(
                right not in adjacency[left]
                for left, right in combinations(neighbors, 2)
            )

        selected = min(
            remaining,
            key=lambda variable: (
                variable in protected,
                fill_count(variable),
                len(adjacency[variable] & remaining),
                incidence[variable],
                rank[variable],
            ),
        )
        neighbors = adjacency[selected] & remaining
        for left, right in combinations(neighbors, 2):
            adjacency[left].add(right)
            adjacency[right].add(left)
        remaining.remove(selected)
        result.append(selected)
    return tuple(result)


def certified_pseudo_division(
    dividend: sp.Expr,
    divisor: sp.Expr,
    variable: sp.Symbol,
    *,
    phase: str,
) -> CertifiedPseudoDivision:
    """Compute and replay ``m*dividend = quotient*divisor + remainder``."""

    left = sp.expand(dividend)
    right = sp.expand(divisor)
    if right == 0:
        raise ZeroDivisionError("pseudo-divisor must be nonzero")
    left_degree = _degree(left, variable)
    right_degree = _degree(right, variable)
    if left_degree < right_degree or left_degree < 0:
        quotient = sp.Integer(0)
        remainder = left
        multiplier = sp.Integer(1)
    else:
        quotient, remainder = sp.pdiv(left, right, variable)
        quotient = sp.expand(quotient)
        remainder = sp.expand(remainder)
        leading = sp.expand(sp.Poly(right, variable).LC())
        multiplier = sp.expand(leading ** (left_degree - right_degree + 1))
    residual = sp.expand(multiplier * left - quotient * right - remainder)
    obligation = None
    if multiplier.free_symbols:
        obligation = f"Ne({sp.sstr(multiplier)}, 0)"
    material = "|".join(
        (
            phase,
            str(variable),
            _text(left),
            _text(right),
            _text(multiplier),
            _text(quotient),
            _text(sp.Integer(1)),
            _text(remainder),
            _text(residual),
        )
    )
    return CertifiedPseudoDivision(
        phase=phase,
        variable=str(variable),
        dividend=_text(left),
        divisor=_text(right),
        multiplier=_text(multiplier),
        quotient=_text(quotient),
        remainder_multiplier="1",
        remainder=_text(remainder),
        dividend_degree=left_degree,
        divisor_degree=right_degree,
        replay_residual=_text(residual),
        nonzero_obligation=obligation,
        normalization_nonzero_obligation=None,
        replayed=residual == 0,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )


def _constant_multiple(left: sp.Expr, right: sp.Expr) -> sp.Expr | None:
    """Return a nonzero rational ``c`` when ``left = c*right``."""

    if left == 0 or right == 0:
        return None
    ratio = sp.cancel(left / right)
    if ratio.free_symbols or not ratio.is_Rational or ratio == 0:
        return None
    return ratio if sp.expand(left - ratio * right) == 0 else None


def certified_wu_characteristic_proof(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal_polynomial: sp.Expr,
    *,
    max_reductions: int = 10_000,
    max_terms: int = 20_000,
    timeout_seconds: float = 300.0,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> CertifiedWuResult:
    """Triangularize a square dependent subsystem and pseudo-reduce a goal.

    ``conditional_goal_proved`` means the final pseudo-remainder is zero.  It is
    promoted to ``unconditional_goal_proved`` only when every multiplier used
    while reducing the goal is a nonzero constant.
    """

    started = time.perf_counter()
    initial = _deduplicate(polynomials)
    ordered_variables = tuple(variables)
    matching = structural_variable_matching(initial, ordered_variables)
    variable_by_name = {str(item): item for item in ordered_variables}
    dependent = tuple(
        variable_by_name[name] for name in matching.dependent_variables
    )
    active = list(initial)
    pivots: list[tuple[sp.Symbol, sp.Expr]] = []
    vanished_variables: list[str] = []
    triangulation_steps: list[CertifiedPseudoDivision] = []
    goal_steps: list[CertifiedPseudoDivision] = []
    maximum_terms = max((_term_count(item) for item in initial), default=0)
    stopped_reason: str | None = None

    def over_budget() -> str | None:
        if timeout_seconds > 0 and time.perf_counter() - started >= timeout_seconds:
            return "timeout"
        if len(triangulation_steps) + len(goal_steps) >= max_reductions:
            return "reduction_budget"
        return None

    if not matching.complete:
        stopped_reason = "structural_matching_incomplete"

    for variable in reversed(dependent):
        if stopped_reason is not None:
            break
        while True:
            stopped_reason = over_budget()
            if stopped_reason is not None:
                break
            containing = [
                index for index, polynomial in enumerate(active)
                if variable in polynomial.free_symbols
            ]
            if not containing:
                vanished_variables.append(str(variable))
                break
            ranked = sorted(
                containing,
                key=lambda index: (
                    _degree(active[index], variable),
                    _term_count(active[index]),
                    int(sp.count_ops(active[index])),
                    _text(active[index]),
                ),
            )
            pivot_index = ranked[0]
            pivot = active[pivot_index]
            pivot_degree = _degree(pivot, variable)
            if len(ranked) == 1:
                active.pop(pivot_index)
                pivots.append((variable, pivot))
                break

            targets = ranked[1:] if pivot_degree == 1 else ranked[1:2]
            replacements: dict[int, sp.Expr] = {}
            for target_index in targets:
                certificate = certified_pseudo_division(
                    active[target_index],
                    pivot,
                    variable,
                    phase="triangulation",
                )
                triangulation_steps.append(certificate)
                if not certificate.replayed:
                    stopped_reason = "certificate_replay_failed"
                    break
                remainder = sp.sympify(certificate.remainder)
                maximum_terms = max(maximum_terms, _term_count(remainder))
                if maximum_terms > max_terms:
                    stopped_reason = "term_budget"
                    break
                replacements[target_index] = remainder
                if progress_callback is not None:
                    progress_callback(
                        {
                            "stage": "triangulation_reduction",
                            "variable": str(variable),
                            "pivot_degree": pivot_degree,
                            "remaining_polynomials": len(active),
                            "reduction_count": len(triangulation_steps),
                            "remainder_terms": _term_count(remainder),
                            "maximum_term_count": maximum_terms,
                        }
                    )
            if stopped_reason is not None:
                break
            for index in sorted(replacements, reverse=True):
                remainder = replacements[index]
                if remainder == 0:
                    active.pop(index)
                else:
                    active[index] = remainder
            if pivot_degree == 1:
                # The pivot itself was not replaced; remove it after all targets.
                pivot_position = next(
                    index for index, polynomial in enumerate(active)
                    if polynomial == pivot
                )
                active.pop(pivot_position)
                pivots.append((variable, pivot))
                break

    triangular_complete = stopped_reason is None
    parameter_conditions = _deduplicate(active)
    current = sp.expand(goal_polynomial)
    nonzero: list[str] = []
    if triangular_complete:
        for variable, pivot in pivots:
            if current == 0 or variable not in current.free_symbols:
                continue
            constant = _constant_multiple(current, pivot)
            if constant is not None:
                current = sp.Integer(0)
                continue
            stopped_reason = over_budget()
            if stopped_reason is not None:
                break
            certificate = certified_pseudo_division(
                current,
                pivot,
                variable,
                phase="goal_reduction",
            )
            goal_steps.append(certificate)
            if not certificate.replayed:
                stopped_reason = "certificate_replay_failed"
                break
            current = sp.sympify(certificate.remainder)
            maximum_terms = max(maximum_terms, _term_count(current))
            if certificate.nonzero_obligation is not None:
                nonzero.append(certificate.nonzero_obligation)
            if maximum_terms > max_terms:
                stopped_reason = "term_budget"
                break
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "goal_reduction",
                        "variable": str(variable),
                        "reduction_count": len(goal_steps),
                        "remainder_terms": _term_count(current),
                        "maximum_term_count": maximum_terms,
                    }
                )

    replayed = all(
        item.replayed for item in (*triangulation_steps, *goal_steps)
    )
    conditional = (
        triangular_complete
        and stopped_reason is None
        and replayed
        and sp.expand(current) == 0
    )
    obligations = tuple(dict.fromkeys(nonzero))
    return CertifiedWuResult(
        initial_polynomials=tuple(_text(item) for item in initial),
        variables=tuple(str(item) for item in ordered_variables),
        elimination_order=tuple(str(item) for item in reversed(dependent)),
        vanished_variables=tuple(vanished_variables),
        matching=matching,
        pivots=tuple(
            WuTriangularPivot(
                variable=str(variable),
                polynomial=_text(polynomial),
                degree=_degree(polynomial, variable),
            )
            for variable, polynomial in pivots
        ),
        parameter_conditions=tuple(_text(item) for item in parameter_conditions),
        triangulation_steps=tuple(triangulation_steps),
        goal_steps=tuple(goal_steps),
        goal_polynomial=_text(goal_polynomial),
        final_remainder=_text(current),
        nonzero_obligations=obligations,
        stopped_reason=stopped_reason,
        triangularization_complete=triangular_complete,
        all_identities_replayed=replayed,
        conditional_goal_proved=conditional,
        unconditional_goal_proved=conditional and not obligations,
        maximum_term_count=maximum_terms,
        elapsed_seconds=time.perf_counter() - started,
    )


def _ring_main_coefficient(
    polynomial: PolyElement,
    variable_index: int,
) -> PolyElement:
    degree = polynomial.degree(variable_index)
    coefficients: dict[tuple[int, ...], object] = {}
    for monomial, coefficient in polynomial.items():
        if monomial[variable_index] != degree:
            continue
        projected = list(monomial)
        projected[variable_index] = 0
        key = tuple(projected)
        coefficients[key] = coefficients.get(key, QQ.zero) + coefficient
    return polynomial.ring.from_dict(coefficients)


def _ring_constant_multiple(
    left: PolyElement,
    right: PolyElement,
) -> object | None:
    if not left or not right or set(left) != set(right):
        return None
    first = next(iter(left))
    ratio = left[first] / right[first]
    if ratio == 0:
        return None
    return ratio if all(left[key] == ratio * right[key] for key in left) else None


def _ring_pseudo_division(
    dividend: PolyElement,
    divisor: PolyElement,
    variable_index: int,
    *,
    max_intermediate_terms: int | None = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> tuple[PolyElement, PolyElement]:
    """Pseudo-divide in one selected variable with a zero-initialized quotient."""

    dividend_degree = dividend.degree(variable_index)
    divisor_degree = divisor.degree(variable_index)
    if divisor_degree < 0:
        raise ZeroDivisionError("pseudo-divisor must be nonzero")
    if dividend_degree < divisor_degree:
        return dividend.ring.zero, dividend
    leading = divisor.coeff_wrt(variable_index, divisor_degree)
    generator = dividend.ring.gens[variable_index]
    quotient = dividend.ring.zero
    remainder = dividend
    remainder_degree = dividend_degree
    remaining_scale = dividend_degree - divisor_degree + 1
    iteration = 0
    while remainder_degree >= divisor_degree:
        remainder_leading = remainder.coeff_wrt(
            variable_index,
            remainder_degree,
        )
        power = remainder_degree - divisor_degree
        remaining_scale -= 1
        quotient = quotient * leading + remainder_leading * generator**power
        remainder = (
            remainder * leading
            - divisor * remainder_leading * generator**power
        )
        iteration += 1
        if progress_callback is not None:
            progress_callback(
                {
                    "stage": "pseudo_division_micro_step",
                    "iteration": iteration,
                    "remainder_terms": len(remainder),
                }
            )
        if (
            max_intermediate_terms is not None
            and len(remainder) > max_intermediate_terms
        ):
            raise SparsePseudoDivisionBudgetExceeded(
                len(remainder),
                iteration,
            )
        remainder_degree = remainder.degree(variable_index)
    trailing_scale = leading**remaining_scale
    quotient *= trailing_scale
    remainder *= trailing_scale
    if (
        max_intermediate_terms is not None
        and len(remainder) > max_intermediate_terms
    ):
        raise SparsePseudoDivisionBudgetExceeded(len(remainder), iteration)
    return quotient, remainder


class SparsePseudoDivisionBudgetExceeded(RuntimeError):
    def __init__(self, observed_terms: int, iteration: int) -> None:
        super().__init__(
            f"pseudo-division exceeded term budget at micro-step {iteration}: "
            f"{observed_terms} terms"
        )
        self.observed_terms = observed_terms
        self.iteration = iteration


def _ring_selected_variable_content(
    polynomial: PolyElement,
    variable_index: int,
    *,
    max_terms: int,
) -> tuple[PolyElement, PolyElement]:
    """Remove coefficient content while preserving its exact multiplier.

    The content is the gcd of the coefficients when the polynomial is viewed
    as univariate in ``variable_index``.  A nonconstant content is not silently
    cancelled: callers retain it in the pseudo-division identity and expose a
    nonzero obligation before using the primitive part as a new equation.
    """

    ring_object = polynomial.ring
    if not polynomial or len(polynomial) > max_terms:
        return ring_object.one, polynomial
    support_indices = [
        index
        for index in range(polynomial.ring.ngens)
        if polynomial.degree(index) > 0
    ]
    if not support_indices:
        return ring_object.one, polynomial
    # A linear elimination leaves a remainder independent of the eliminated
    # variable.  In that case primitive-part reduction must continue at the
    # highest variable that actually survives; treating a constant-in-x
    # remainder as its own content would incorrectly replace it by 1.
    content_variable_index = (
        variable_index
        if polynomial.degree(variable_index) > 0
        else support_indices[-1]
    )
    degrees = sorted(
        {monomial[content_variable_index] for monomial in polynomial}
    )
    coefficients = [
        polynomial.coeff_wrt(content_variable_index, degree)
        for degree in degrees
    ]
    content = coefficients[0]
    for coefficient in coefficients[1:]:
        content = content.gcd(coefficient)
        if len(content) == 1 and not next(iter(content)):
            break
    if not content:
        return ring_object.one, polynomial
    if all(not any(monomial) for monomial in content):
        return ring_object.one, polynomial
    primitive = polynomial.exquo(content)
    return content, primitive


def _sparse_pseudo_division(
    dividend: PolyElement,
    divisor: PolyElement,
    variable_index: int,
    variable_name: str,
    *,
    phase: str,
    normalize_remainder: bool = True,
    max_content_terms: int = 5_000,
    max_intermediate_terms: int | None = None,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> tuple[CertifiedPseudoDivision, PolyElement]:
    if not divisor:
        raise ZeroDivisionError("pseudo-divisor must be nonzero")
    left_degree = dividend.degree(variable_index)
    right_degree = divisor.degree(variable_index)
    if left_degree < right_degree or left_degree < 0:
        quotient = dividend.ring.zero
        remainder = dividend
        multiplier = dividend.ring.one
    else:
        quotient, remainder = _ring_pseudo_division(
            dividend,
            divisor,
            variable_index,
            max_intermediate_terms=max_intermediate_terms,
            progress_callback=progress_callback,
        )
        leading = _ring_main_coefficient(divisor, variable_index)
        multiplier = leading ** (left_degree - right_degree + 1)
    remainder_multiplier = dividend.ring.one
    if normalize_remainder and remainder:
        remainder_multiplier, remainder = _ring_selected_variable_content(
            remainder,
            variable_index,
            max_terms=max_content_terms,
        )
    residual = (
        multiplier * dividend
        - quotient * divisor
        - remainder_multiplier * remainder
    )
    obligation = None
    if any(any(power for power in monomial) for monomial in multiplier):
        obligation = f"Ne({multiplier}, 0)"
    normalization_obligation = None
    if any(
        any(power for power in monomial)
        for monomial in remainder_multiplier
    ):
        normalization_obligation = f"Ne({remainder_multiplier}, 0)"
    material = "|".join(
        (
            phase,
            variable_name,
            str(dividend),
            str(divisor),
            str(multiplier),
            str(quotient),
            str(remainder_multiplier),
            str(remainder),
            str(residual),
        )
    )
    return (
        CertifiedPseudoDivision(
            phase=phase,
            variable=variable_name,
            dividend=str(dividend),
            divisor=str(divisor),
            multiplier=str(multiplier),
            quotient=str(quotient),
            remainder_multiplier=str(remainder_multiplier),
            remainder=str(remainder),
            dividend_degree=left_degree,
            divisor_degree=right_degree,
            replay_residual=str(residual),
            nonzero_obligation=obligation,
            normalization_nonzero_obligation=normalization_obligation,
            replayed=not residual,
            certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
        ),
        remainder,
    )


def certified_sparse_wu_characteristic_proof(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal_polynomial: sp.Expr,
    *,
    max_reductions: int = 10_000,
    max_terms: int = 20_000,
    timeout_seconds: float = 300.0,
    normalize_remainders: bool = True,
    max_content_terms: int = 5_000,
    elimination_order: Iterable[sp.Symbol] | None = None,
    require_complete_matching: bool = True,
    progress_callback: Callable[[dict[str, object]], None] | None = None,
) -> CertifiedWuResult:
    """Sparse-ring implementation of the same certified Wu experiment.

    Construction elaboration normally requires every source equation to have a
    distinct dependent variable. Zero decomposition intentionally adds
    degeneracy equations and can therefore create overdetermined systems;
    callers may disable only that structural guard while retaining every exact
    pseudo-division and certificate check.
    """

    started = time.perf_counter()
    initial_expressions = _deduplicate(polynomials)
    ordered_variables = tuple(variables)
    if not ordered_variables:
        raise ValueError("at least one variable is required")
    polynomial_ring, *ring_variables = ring(
        ",".join(str(item) for item in ordered_variables),
        QQ,
    )
    variable_index = {
        str(variable): index for index, variable in enumerate(ordered_variables)
    }
    initial = tuple(
        polynomial_ring.from_expr(expression) for expression in initial_expressions
    )
    goal = polynomial_ring.from_expr(sp.expand(goal_polynomial))
    matching = structural_variable_matching(initial_expressions, ordered_variables)
    dependent = matching.dependent_variables
    if elimination_order is None:
        selected_elimination_order = tuple(reversed(dependent))
    else:
        proposed = tuple(str(item) for item in elimination_order)
        if len(proposed) != len(set(proposed)) or set(proposed) != set(dependent):
            raise ValueError(
                "elimination_order must contain each structurally dependent variable once"
            )
        selected_elimination_order = proposed
    active = list(initial)
    pivots: list[tuple[str, PolyElement]] = []
    vanished_variables: list[str] = []
    triangulation_steps: list[CertifiedPseudoDivision] = []
    goal_steps: list[CertifiedPseudoDivision] = []
    nonzero: list[str] = []
    maximum_terms = max((len(item) for item in initial), default=0)
    stopped_reason: str | None = None

    def over_budget() -> str | None:
        if timeout_seconds > 0 and time.perf_counter() - started >= timeout_seconds:
            return "timeout"
        if len(triangulation_steps) + len(goal_steps) >= max_reductions:
            return "reduction_budget"
        return None

    if require_complete_matching and not matching.complete:
        stopped_reason = "structural_matching_incomplete"

    for variable_name in selected_elimination_order:
        if stopped_reason is not None:
            break
        index = variable_index[variable_name]
        while True:
            stopped_reason = over_budget()
            if stopped_reason is not None:
                break
            containing = [
                position for position, polynomial in enumerate(active)
                if polynomial.degree(index) > 0
            ]
            if not containing:
                vanished_variables.append(variable_name)
                break
            ranked = sorted(
                containing,
                key=lambda position: (
                    active[position].degree(index),
                    len(active[position]),
                    str(active[position]),
                ),
            )
            pivot_position = ranked[0]
            pivot = active[pivot_position]
            pivot_degree = pivot.degree(index)
            if len(ranked) == 1:
                active.pop(pivot_position)
                pivots.append((variable_name, pivot))
                break
            targets = ranked[1:] if pivot_degree == 1 else ranked[1:2]
            replacements: dict[int, PolyElement] = {}
            for target_position in targets:
                try:
                    certificate, remainder = _sparse_pseudo_division(
                        active[target_position],
                        pivot,
                        index,
                        variable_name,
                        phase="triangulation",
                        normalize_remainder=normalize_remainders,
                        max_content_terms=max_content_terms,
                        max_intermediate_terms=max_terms,
                        progress_callback=(
                            (
                                lambda event: progress_callback(
                                    {**event, "variable": variable_name}
                                )
                            )
                            if progress_callback is not None
                            else None
                        ),
                    )
                except SparsePseudoDivisionBudgetExceeded as error:
                    maximum_terms = max(maximum_terms, error.observed_terms)
                    stopped_reason = "term_budget"
                    if progress_callback is not None:
                        progress_callback(
                            {
                                "stage": "pseudo_division_budget_exceeded",
                                "variable": variable_name,
                                "iteration": error.iteration,
                                "maximum_term_count": maximum_terms,
                            }
                        )
                    break
                triangulation_steps.append(certificate)
                if not certificate.replayed:
                    stopped_reason = "certificate_replay_failed"
                    break
                if certificate.normalization_nonzero_obligation is not None:
                    nonzero.append(certificate.normalization_nonzero_obligation)
                maximum_terms = max(maximum_terms, len(remainder))
                if maximum_terms > max_terms:
                    stopped_reason = "term_budget"
                    break
                replacements[target_position] = remainder
                if progress_callback is not None:
                    progress_callback(
                        {
                            "stage": "triangulation_reduction",
                            "backend": "sparse_ring",
                            "variable": variable_name,
                            "pivot_degree": pivot_degree,
                            "remaining_polynomials": len(active),
                            "reduction_count": len(triangulation_steps),
                            "remainder_terms": len(remainder),
                            "maximum_term_count": maximum_terms,
                        }
                    )
            if stopped_reason is not None:
                break
            for position in sorted(replacements, reverse=True):
                remainder = replacements[position]
                if not remainder:
                    active.pop(position)
                else:
                    active[position] = remainder
            if pivot_degree == 1:
                pivot_position = next(
                    position for position, polynomial in enumerate(active)
                    if polynomial == pivot
                )
                active.pop(pivot_position)
                pivots.append((variable_name, pivot))
                break

    triangular_complete = stopped_reason is None
    current = goal
    if triangular_complete:
        for variable_name, pivot in pivots:
            index = variable_index[variable_name]
            if not current or current.degree(index) <= 0:
                continue
            if _ring_constant_multiple(current, pivot) is not None:
                current = polynomial_ring.zero
                continue
            stopped_reason = over_budget()
            if stopped_reason is not None:
                break
            try:
                certificate, current = _sparse_pseudo_division(
                    current,
                    pivot,
                    index,
                    variable_name,
                    phase="goal_reduction",
                    normalize_remainder=normalize_remainders,
                    max_content_terms=max_content_terms,
                    max_intermediate_terms=max_terms,
                    progress_callback=(
                        (
                            lambda event: progress_callback(
                                {**event, "variable": variable_name}
                            )
                        )
                        if progress_callback is not None
                        else None
                    ),
                )
            except SparsePseudoDivisionBudgetExceeded as error:
                maximum_terms = max(maximum_terms, error.observed_terms)
                stopped_reason = "term_budget"
                if progress_callback is not None:
                    progress_callback(
                        {
                            "stage": "pseudo_division_budget_exceeded",
                            "variable": variable_name,
                            "iteration": error.iteration,
                            "maximum_term_count": maximum_terms,
                        }
                    )
                break
            goal_steps.append(certificate)
            if not certificate.replayed:
                stopped_reason = "certificate_replay_failed"
                break
            maximum_terms = max(maximum_terms, len(current))
            if certificate.nonzero_obligation is not None:
                nonzero.append(certificate.nonzero_obligation)
            if maximum_terms > max_terms:
                stopped_reason = "term_budget"
                break
            if progress_callback is not None:
                progress_callback(
                    {
                        "stage": "goal_reduction",
                        "backend": "sparse_ring",
                        "variable": variable_name,
                        "reduction_count": len(goal_steps),
                        "remainder_terms": len(current),
                        "maximum_term_count": maximum_terms,
                    }
                )

    replayed = all(
        item.replayed for item in (*triangulation_steps, *goal_steps)
    )
    conditional = (
        triangular_complete
        and stopped_reason is None
        and replayed
        and not current
    )
    obligations = tuple(dict.fromkeys(nonzero))
    return CertifiedWuResult(
        initial_polynomials=tuple(str(item) for item in initial),
        variables=tuple(str(item) for item in ordered_variables),
        elimination_order=selected_elimination_order,
        vanished_variables=tuple(vanished_variables),
        matching=matching,
        pivots=tuple(
            WuTriangularPivot(
                variable=variable_name,
                polynomial=str(polynomial),
                degree=polynomial.degree(variable_index[variable_name]),
            )
            for variable_name, polynomial in pivots
        ),
        parameter_conditions=tuple(str(item) for item in active if item),
        triangulation_steps=tuple(triangulation_steps),
        goal_steps=tuple(goal_steps),
        goal_polynomial=str(goal),
        final_remainder=str(current),
        nonzero_obligations=obligations,
        stopped_reason=stopped_reason,
        triangularization_complete=triangular_complete,
        all_identities_replayed=replayed,
        conditional_goal_proved=conditional,
        unconditional_goal_proved=conditional and not obligations,
        maximum_term_count=maximum_terms,
        elapsed_seconds=time.perf_counter() - started,
    )
