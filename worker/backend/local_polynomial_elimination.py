"""Certificate-carrying variable elimination on a polynomial factor graph."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from itertools import combinations, permutations
from typing import Iterable

import sympy as sp


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


@dataclass(frozen=True)
class LocalEliminationResult:
    initial_polynomials: tuple[str, ...]
    remaining_polynomials: tuple[str, ...]
    remaining_variables: tuple[str, ...]
    steps: tuple[LocalEliminationStep, ...]
    eliminated_variables: tuple[str, ...]
    stopped_reason: str | None
    exact_replay: bool


def _deduplicate(polynomials: Iterable[sp.Expr]) -> tuple[sp.Expr, ...]:
    unique: dict[str, sp.Expr] = {}
    for polynomial in polynomials:
        exact = sp.factor(sp.expand(polynomial))
        if exact == 0:
            continue
        unique.setdefault(sp.sstr(exact), exact)
    return tuple(unique[key] for key in sorted(unique))


def _term_count(polynomial: sp.Expr) -> int:
    return len(sp.Add.make_args(sp.expand(polynomial)))


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


def _resultant_term_upper_bound(
    left: sp.Expr,
    right: sp.Expr,
    variable: sp.Symbol,
) -> int:
    """Bound determinant expansion using coefficient term counts only."""

    left_coefficients = sp.Poly(left, variable).all_coeffs()
    right_coefficients = sp.Poly(right, variable).all_coeffs()
    left_degree = len(left_coefficients) - 1
    right_degree = len(right_coefficients) - 1
    size = left_degree + right_degree
    rows: list[list[sp.Expr | int]] = []
    for offset in range(right_degree):
        rows.append(
            [0] * offset + left_coefficients + [0] * (right_degree - 1 - offset)
        )
    for offset in range(left_degree):
        rows.append(
            [0] * offset + right_coefficients + [0] * (left_degree - 1 - offset)
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


def _linear_eliminate(
    variable: sp.Symbol,
    bucket: tuple[sp.Expr, ...],
) -> tuple[tuple[sp.Expr, ...], LocalEliminationStep]:
    decomposed: list[tuple[sp.Expr, sp.Expr, sp.Expr]] = []
    for polynomial in bucket:
        poly = sp.Poly(polynomial, variable)
        coefficient = sp.factor(poly.coeff_monomial(variable))
        constant = sp.factor(poly.coeff_monomial(1))
        decomposed.append((polynomial, coefficient, constant))
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
        output = sp.factor(pivot_coefficient * constant - coefficient * pivot_constant)
        residual = sp.expand(
            output - (pivot_coefficient * polynomial - coefficient * pivot)
        )
        if variable in output.free_symbols:
            raise AssertionError("linear local elimination retained its variable")
        output = sp.factor(sp.expand(output))
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
    material = "|".join(
        (
            str(variable),
            "linear_localization",
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
        method="linear_localization",
        input_polynomials=tuple(sp.sstr(item) for item in bucket),
        output_polynomials=tuple(sp.sstr(item) for item in outputs),
        replay_residuals=tuple(sp.sstr(item) for item in residuals),
        ideal_membership_witnesses=witnesses,
        nonzero_conditions=(f"{sp.sstr(pivot_coefficient)} != 0",),
        replayed=replayed,
        certificate_sha256=hashlib.sha256(material.encode()).hexdigest(),
    )


def _resultant_eliminate(
    variable: sp.Symbol,
    bucket: tuple[sp.Expr, ...],
) -> tuple[tuple[sp.Expr, ...], LocalEliminationStep]:
    pivot = min(
        bucket,
        key=lambda item: (
            sp.Poly(item, variable).degree(),
            _term_count(item),
            int(sp.count_ops(item)),
        ),
    )
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
) -> LocalEliminationResult:
    """Eliminate local variables without constructing a global basis.

    Each step is exact in the localization where the selected pivot coefficient
    is nonzero. Low-degree nonlinear buckets use exact resultants. Higher-degree
    variables are left untouched; no heuristic consequence is accepted as proof.
    """

    initial_factors = _deduplicate(polynomials)
    if ordering_strategy not in {"local_degree", "min_fill"}:
        raise ValueError(f"unknown ordering strategy: {ordering_strategy}")
    factors = initial_factors
    remaining = set(variables)
    protected = set(protected_variables)
    steps: list[LocalEliminationStep] = []
    eliminated: list[str] = []
    stopped_reason: str | None = None
    separator_blocked = False

    while True:
        if max_steps is not None and len(steps) >= max_steps:
            stopped_reason = "max_steps"
            break
        adjacency = _primal_adjacency(factors)
        candidates: list[
            tuple[
                tuple[int, int, int, int, int, str],
                sp.Symbol,
                tuple[sp.Expr, ...],
                int,
            ]
        ] = []
        for variable in remaining - protected:
            bucket = tuple(item for item in factors if variable in item.free_symbols)
            if not bucket:
                candidates.append(((0, 0, 0, 0, 0, str(variable)), variable, bucket, 0))
                continue
            degrees: list[int] = []
            valid = True
            for polynomial in bucket:
                try:
                    degree = sp.Poly(polynomial, variable).degree()
                except sp.PolynomialError:
                    valid = False
                    break
                if degree > max_resultant_degree:
                    valid = False
                    break
                degrees.append(degree)
            if not valid:
                continue
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
                if ordering_strategy == "min_fill"
                else len(bucket)
            )
            rank = (
                max(degrees, default=0),
                fill_edges,
                len(neighbors),
                len(bucket),
                sum(_term_count(item) for item in bucket),
                str(variable),
            )
            candidates.append((rank, variable, bucket, max(degrees, default=0)))
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
        for _, variable, bucket, maximum_degree in sorted(
            candidates, key=lambda item: item[0]
        ):
            if not bucket:
                selected = (variable, bucket, (), None)
                break
            if maximum_degree <= 1:
                outputs, certificate = _linear_eliminate(variable, bucket)
            else:
                pivot = min(
                    bucket,
                    key=lambda item: (
                        sp.Poly(item, variable).degree(),
                        _term_count(item),
                        int(sp.count_ops(item)),
                    ),
                )
                if any(
                    _resultant_term_upper_bound(pivot, polynomial, variable)
                    > max_output_terms
                    for polynomial in bucket
                    if polynomial != pivot
                ):
                    continue
                outputs, certificate = _resultant_eliminate(variable, bucket)
            if not certificate.replayed:
                continue
            if all(_term_count(item) <= max_output_terms for item in outputs):
                selected = (variable, bucket, outputs, certificate)
                break
        if selected is None:
            stopped_reason = "term_budget"
            break
        variable, bucket, outputs, certificate = selected
        factors = (
            _deduplicate(item for item in factors if variable not in item.free_symbols)
            + outputs
        )
        factors = _deduplicate(factors)
        remaining.remove(variable)
        eliminated.append(str(variable))
        if certificate is not None:
            steps.append(certificate)

    return LocalEliminationResult(
        initial_polynomials=tuple(sp.sstr(item) for item in initial_factors),
        remaining_polynomials=tuple(sp.sstr(item) for item in factors),
        remaining_variables=tuple(sorted(str(item) for item in remaining)),
        steps=tuple(steps),
        eliminated_variables=tuple(eliminated),
        stopped_reason=stopped_reason,
        exact_replay=all(item.replayed for item in steps),
    )
