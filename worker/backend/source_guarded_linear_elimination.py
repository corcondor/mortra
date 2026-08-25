"""Exact linear elimination guarded by source-proved nonzero conditions."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Iterable

import sympy as sp

from worker.backend.jgex_exact_constraint_bridge import (
    _canonical_nonconstant_factor_keys,
)


@dataclass(frozen=True)
class PolynomialTransform:
    source_index: int
    degree: int
    transformed: sp.Expr
    pivot_quotient: sp.Expr


@dataclass(frozen=True)
class GuardedLinearStep:
    pivot_source_index: int
    pivot_variable: sp.Symbol
    pivot_polynomial: sp.Expr
    coefficient: sp.Expr
    constant: sp.Expr
    coefficient_factor_keys: tuple[str, ...]
    coefficient_source_proved_nonzero: bool
    transforms: tuple[PolynomialTransform, ...]
    goal_degree: int
    transformed_goal: sp.Expr
    goal_pivot_quotient: sp.Expr


@dataclass(frozen=True)
class GuardedLinearSystem:
    source_polynomials: tuple[sp.Expr, ...]
    source_variables: tuple[sp.Symbol, ...]
    source_goal: sp.Expr
    reduced_polynomials: tuple[sp.Expr, ...]
    reduced_source_indices: tuple[int, ...]
    reduced_variables: tuple[sp.Symbol, ...]
    reduced_goal: sp.Expr
    reduced_nonzero_expressions: tuple[sp.Expr, ...]
    steps: tuple[GuardedLinearStep, ...]
    operation_counts_by_stage: tuple[tuple[int, ...], ...] = ()
    stopped_reason: str | None = None


@dataclass(frozen=True)
class LiftedSaturationCertificate:
    goal_multiplier: sp.Expr
    reduced_goal_multiplier: sp.Expr
    source_multipliers: tuple[sp.Expr, ...]
    replay_residual: sp.Expr
    replayed: bool
    reduced_goal_multiplier_factor_keys: tuple[str, ...]
    reduced_goal_multiplier_source_proved_nonzero: bool
    nonzero_multiplier_factor_keys: tuple[str, ...]
    multiplier_source_proved_nonzero: bool


@dataclass(frozen=True)
class GoalFactorCandidate:
    factor: sp.Expr
    complementary_multiplier: sp.Expr
    replay_residual: sp.Expr
    replayed: bool


def _fraction_free_substitute(
    expression: sp.Expr,
    variable: sp.Symbol,
    coefficient: sp.Expr,
    constant: sp.Expr,
    pivot: sp.Expr,
) -> tuple[int, sp.Expr, sp.Expr]:
    polynomial = sp.Poly(expression, variable, domain="EX")
    degree, transformed = _fraction_free_value(
        expression,
        variable,
        coefficient,
        constant,
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
    return degree, transformed, quotient


def _coefficients_by_power(
    polynomial: sp.Poly,
    variable_index: int,
) -> tuple[sp.Expr, ...]:
    degree = polynomial.degree(polynomial.gens[variable_index])
    if degree < 0:
        return (sp.S.Zero,)
    coefficients: list[sp.Expr] = [sp.S.Zero] * (degree + 1)
    for powers, coefficient in polynomial.terms():
        selected_power = powers[variable_index]
        term = sp.sympify(coefficient)
        for index, (variable, power) in enumerate(
            zip(polynomial.gens, powers, strict=True)
        ):
            if index != variable_index and power:
                term *= variable**power
        coefficients[selected_power] += term
    return tuple(coefficients)


def _univariate_coefficients(
    expression: sp.Expr,
    variable: sp.Symbol,
) -> tuple[sp.Expr, ...]:
    if variable not in expression.free_symbols:
        return (expression,)
    polynomial = sp.Poly(expression, variable, domain="EX")
    degree = polynomial.degree()
    if degree < 0:
        return (sp.S.Zero,)
    return tuple(polynomial.nth(power) for power in range(degree + 1))


def _linear_coefficients_structural(
    expression: sp.Expr,
    variable: sp.Symbol,
) -> tuple[sp.Expr, sp.Expr] | None:
    """Return constant and linear coefficients without expanding the DAG."""

    cache: dict[sp.Expr, tuple[sp.Expr, sp.Expr] | None] = {}

    def visit(current: sp.Expr) -> tuple[sp.Expr, sp.Expr] | None:
        if current in cache:
            return cache[current]
        if variable not in current.free_symbols:
            result: tuple[sp.Expr, sp.Expr] | None = (current, sp.S.Zero)
        elif current == variable:
            result = (sp.S.Zero, sp.S.One)
        elif current.is_Add:
            children = tuple(visit(item) for item in current.args)
            if any(item is None for item in children):
                result = None
            else:
                affine_children = tuple(item for item in children if item is not None)
                result = (
                    sum((item[0] for item in affine_children), sp.S.Zero),
                    sum((item[1] for item in affine_children), sp.S.Zero),
                )
        elif current.is_Mul:
            constant = sp.S.One
            coefficient = sp.S.Zero
            result = (constant, coefficient)
            for item in current.args:
                child = visit(item)
                if child is None:
                    result = None
                    break
                child_constant, child_coefficient = child
                if coefficient != 0 and child_coefficient != 0:
                    result = None
                    break
                coefficient = (
                    constant * child_coefficient
                    + coefficient * child_constant
                )
                constant *= child_constant
                result = (constant, coefficient)
        elif (
            current.is_Pow
            and current.exp.is_Integer
            and int(current.exp) >= 0
        ):
            exponent = int(current.exp)
            child = visit(current.base)
            if child is None:
                result = None
            else:
                child_constant, child_coefficient = child
                if child_coefficient == 0:
                    result = (child_constant**exponent, sp.S.Zero)
                elif exponent == 1:
                    result = child
                else:
                    result = None
        else:
            polynomial = sp.Poly(current, variable, domain="EX")
            if polynomial.degree() > 1:
                result = None
            else:
                result = (
                    polynomial.coeff_monomial(1),
                    polynomial.coeff_monomial(variable),
                )
        cache[current] = result
        return result

    return visit(expression)


def _fraction_free_from_coefficients(
    coefficients: tuple[sp.Expr, ...],
    variable: sp.Symbol,
    pivot_coefficient: sp.Expr,
    pivot_constant: sp.Expr,
) -> tuple[int, sp.Expr, sp.Expr]:
    degree = len(coefficients) - 1
    transformed = sum(
        (
            coefficients[power]
            * (-pivot_constant) ** power
            * pivot_coefficient ** (degree - power)
            for power in range(degree + 1)
        ),
        sp.S.Zero,
    )
    quotient = sum(
        (
            coefficients[power]
            * pivot_coefficient ** (degree - power)
            * sum(
                (pivot_coefficient * variable) ** (power - 1 - offset)
                * (-pivot_constant) ** offset
                for offset in range(power)
            )
            for power in range(1, degree + 1)
        ),
        sp.S.Zero,
    )
    return degree, transformed, quotient


def _fraction_free_structural(
    expression: sp.Expr,
    variable: sp.Symbol,
    pivot_coefficient: sp.Expr,
    pivot_constant: sp.Expr,
    pivot: sp.Expr,
) -> tuple[int, sp.Expr, sp.Expr]:
    """Substitute a linear pivot while preserving the expression DAG."""

    cache: dict[sp.Expr, tuple[int, sp.Expr, sp.Expr]] = {}

    def multiply(
        left: tuple[int, sp.Expr, sp.Expr],
        right: tuple[int, sp.Expr, sp.Expr],
    ) -> tuple[int, sp.Expr, sp.Expr]:
        left_degree, left_value, left_quotient = left
        right_degree, right_value, right_quotient = right
        return (
            left_degree + right_degree,
            left_value * right_value,
            left_value * right_quotient
            + right_value * left_quotient
            + left_quotient * right_quotient * pivot,
        )

    def visit(current: sp.Expr) -> tuple[int, sp.Expr, sp.Expr]:
        if current in cache:
            return cache[current]
        if variable not in current.free_symbols:
            result = (0, current, sp.S.Zero)
        elif current == variable:
            result = (1, -pivot_constant, sp.S.One)
        elif current.is_Add:
            children = tuple(visit(item) for item in current.args)
            degree = max(item[0] for item in children)
            result = (
                degree,
                sum(
                    (
                        pivot_coefficient ** (degree - child_degree)
                        * child_value
                        for child_degree, child_value, _ in children
                    ),
                    sp.S.Zero,
                ),
                sum(
                    (
                        pivot_coefficient ** (degree - child_degree)
                        * child_quotient
                        for child_degree, _, child_quotient in children
                    ),
                    sp.S.Zero,
                ),
            )
        elif current.is_Mul:
            result = (0, sp.S.One, sp.S.Zero)
            for item in current.args:
                result = multiply(result, visit(item))
        elif (
            current.is_Pow
            and current.exp.is_Integer
            and int(current.exp) >= 0
        ):
            exponent = int(current.exp)
            result = (0, sp.S.One, sp.S.Zero)
            factor = visit(current.base)
            while exponent:
                if exponent & 1:
                    result = multiply(result, factor)
                exponent >>= 1
                if exponent:
                    factor = multiply(factor, factor)
        else:
            result = _fraction_free_substitute(
                current,
                variable,
                pivot_coefficient,
                pivot_constant,
                pivot,
            )
        cache[current] = result
        return result

    return visit(expression)


def _fraction_free_value(
    expression: sp.Expr,
    variable: sp.Symbol,
    coefficient: sp.Expr,
    constant: sp.Expr,
) -> tuple[int, sp.Expr]:
    polynomial = sp.Poly(expression, variable, domain="EX")
    degree = polynomial.degree()
    if degree < 0:
        degree = 0
    transformed = sp.expand(
        sum(
            polynomial.nth(power)
            * (-constant) ** power
            * coefficient ** (degree - power)
            for power in range(degree + 1)
        )
    )
    return degree, transformed


def _known_nonzero_keys(expressions: Iterable[sp.Expr]) -> frozenset[str]:
    return frozenset().union(
        *(_canonical_nonconstant_factor_keys(item) for item in expressions)
    )


def source_proved_nondegeneracy_factors(
    system: GuardedLinearSystem,
    *,
    allowed_symbols: Iterable[sp.Symbol],
    proof_variables: Iterable[sp.Symbol],
) -> tuple[sp.Expr, ...]:
    """Return canonical source-proved factors usable in the proof ring.

    Coefficient-only factors are already units in the fraction-field domain and
    cannot change ideal membership. Factors containing an omitted coordinate
    are excluded because Singular cannot represent them in the selected ring.
    """

    allowed = frozenset(allowed_symbols)
    variables = frozenset(proof_variables)
    local_symbols = {str(symbol): symbol for symbol in allowed}
    factors: list[sp.Expr] = []
    for key in sorted(_known_nonzero_keys(system.reduced_nonzero_expressions)):
        factor = sp.sympify(key, locals=local_symbols)
        if not factor.free_symbols <= allowed:
            continue
        if not factor.free_symbols & variables:
            continue
        factors.append(sp.expand(factor))
    return tuple(
        sorted(
            dict.fromkeys(factors),
            key=lambda item: (
                int(sp.count_ops(item)),
                len(item.free_symbols),
                sp.sstr(item),
            ),
        )
    )


def source_preserving_goal_factor_candidates(
    goal: sp.Expr,
    *,
    proof_variables: Iterable[sp.Symbol],
) -> tuple[GoalFactorCandidate, ...]:
    """Return exact target factors whose proofs lift to the original target."""

    goal = sp.sympify(goal)
    variables = frozenset(proof_variables)
    factored = sp.factor_terms(goal)
    factors = factored.args if factored.is_Mul else (factored,)
    candidates: list[GoalFactorCandidate] = []
    for index, raw_factor in enumerate(factors):
        if raw_factor.is_Number:
            continue
        if (
            raw_factor.is_Pow
            and raw_factor.exp.is_Integer
            and int(raw_factor.exp) > 0
        ):
            factor = raw_factor.base
            remaining_power = int(raw_factor.exp) - 1
            selected_remainder = (
                factor**remaining_power if remaining_power else sp.S.One
            )
        else:
            factor = raw_factor
            selected_remainder = sp.S.One
        if not factor.free_symbols & variables:
            continue
        complementary_multiplier = sp.Mul(
            selected_remainder,
            *(
                item
                for item_index, item in enumerate(factors)
                if item_index != index
            ),
        )
        reconstructed = factor * complementary_multiplier
        if reconstructed != factored:
            continue
        candidate = GoalFactorCandidate(
            factor=factor,
            complementary_multiplier=complementary_multiplier,
            replay_residual=sp.S.Zero,
            replayed=True,
        )
        if all(candidate.factor != item.factor for item in candidates):
            candidates.append(candidate)
    return tuple(
        sorted(
            candidates,
            key=lambda item: (
                int(sp.count_ops(item.factor)),
                len(item.factor.free_symbols & variables),
                sp.sstr(item.factor),
            ),
        )
    )


def _candidate_score(
    expression: sp.Expr,
    variable: sp.Symbol,
    source_index: int,
) -> tuple[int, int, int, str]:
    polynomial = sp.Poly(expression, variable, domain="EX")
    coefficient = polynomial.coeff_monomial(variable)
    constant = polynomial.coeff_monomial(1)
    return (
        int(sp.count_ops(coefficient) + sp.count_ops(constant)),
        len(expression.free_symbols),
        source_index,
        str(variable),
    )


def eliminate_source_guarded_linear_variables(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal: sp.Expr,
    nonzero_expressions: Iterable[sp.Expr],
    *,
    max_steps: int | None = None,
    max_expression_operation_count: int | None = None,
    max_total_operation_count: int | None = None,
    progress_callback: Callable[[str, dict[str, int | str]], None] | None = None,
) -> GuardedLinearSystem:
    """Eliminate only variables whose linear coefficient is proved nonzero."""

    def report(stage: str, **details: int | str) -> None:
        if progress_callback is not None:
            progress_callback(stage, details)

    report("initialization_started")
    source_polynomials = tuple(sp.sympify(item) for item in polynomials)
    source_variables = tuple(variables)
    current = tuple(enumerate(source_polynomials))
    current_variables = source_variables
    current_goal = sp.sympify(goal)
    current_nonzero = tuple(sp.sympify(item) for item in nonzero_expressions)
    steps: list[GuardedLinearStep] = []
    operation_counts_by_stage: list[tuple[int, ...]] = []
    stopped_reason: str | None = None
    report("initialization_complete")

    while max_steps is None or len(steps) < max_steps:
        operation_counts = tuple(
            int(sp.count_ops(item)) for _, item in current
        ) + (int(sp.count_ops(current_goal)),)
        operation_counts_by_stage.append(operation_counts)
        if (
            max_expression_operation_count is not None
            and operation_counts
            and max(operation_counts) > max_expression_operation_count
        ):
            stopped_reason = "max_expression_operation_count"
            break
        if (
            max_total_operation_count is not None
            and sum(operation_counts) > max_total_operation_count
        ):
            stopped_reason = "max_total_operation_count"
            break
        known_nonzero = _known_nonzero_keys(current_nonzero)
        if not current_variables:
            break
        report(
            "candidate_scan_started",
            step=len(steps),
            equation_count=len(current),
            variable_count=len(current_variables),
        )
        candidates: list[
            tuple[tuple[int, int, int, int, str], int, int, sp.Symbol]
        ] = []
        for source_index, expression in current:
            for variable_index, variable in enumerate(current_variables):
                coefficients = _linear_coefficients_structural(expression, variable)
                if coefficients is None:
                    continue
                constant, coefficient = coefficients
                if coefficient == 0:
                    continue
                coefficient_keys = _canonical_nonconstant_factor_keys(coefficient)
                if not coefficient_keys or not coefficient_keys <= known_nonzero:
                    continue
                goal_occurrences = (
                    int(current_goal.count(variable))
                    if variable in current_goal.free_symbols
                    else 0
                )
                local_operation_count = int(
                    sp.count_ops(coefficient) + sp.count_ops(constant)
                )
                report(
                    "candidate_identified",
                    step=len(steps),
                    source_index=source_index,
                    variable=str(variable),
                    goal_occurrences=goal_occurrences,
                    local_operation_count=local_operation_count,
                )
                candidates.append(
                    (
                        (
                            goal_occurrences,
                            local_operation_count,
                            len(expression.free_symbols),
                            source_index,
                            str(variable),
                        ),
                        source_index,
                        variable_index,
                        variable,
                    )
                )
        if not candidates:
            break

        _, pivot_source_index, pivot_variable_index, pivot_variable = min(candidates)
        report(
            "pivot_selected",
            step=len(steps),
            source_index=pivot_source_index,
            variable=str(pivot_variable),
            candidate_count=len(candidates),
        )
        pivot = next(
            expression
            for source_index, expression in current
            if source_index == pivot_source_index
        )
        pivot_coefficients = _linear_coefficients_structural(
            pivot,
            pivot_variable,
        )
        if pivot_coefficients is None:
            raise AssertionError("selected structural linear pivot became nonlinear")
        constant, coefficient = pivot_coefficients
        transforms: list[PolynomialTransform] = []
        next_current: list[tuple[int, sp.Expr]] = []
        for completed_count, (source_index, expression) in enumerate(current, 1):
            if source_index == pivot_source_index:
                continue
            degree, transformed, quotient = _fraction_free_structural(
                expression,
                pivot_variable,
                coefficient,
                constant,
                pivot,
            )
            transforms.append(
                PolynomialTransform(
                    source_index=source_index,
                    degree=degree,
                    transformed=transformed,
                    pivot_quotient=quotient,
                )
            )
            next_current.append((source_index, transformed))
            report(
                "source_transform_complete",
                step=len(steps),
                source_index=source_index,
                completed_count=completed_count,
                equation_count=len(current),
            )

        goal_degree, next_goal, goal_quotient = _fraction_free_structural(
            current_goal,
            pivot_variable,
            coefficient,
            constant,
            pivot,
        )
        report("goal_transform_complete", step=len(steps))
        next_nonzero: list[sp.Expr] = [coefficient]
        for expression in current_nonzero:
            _, transformed, _ = _fraction_free_structural(
                expression,
                pivot_variable,
                coefficient,
                constant,
                pivot,
            )
            if transformed != 0:
                next_nonzero.append(transformed)
        steps.append(
            GuardedLinearStep(
                pivot_source_index=pivot_source_index,
                pivot_variable=pivot_variable,
                pivot_polynomial=pivot,
                coefficient=coefficient,
                constant=constant,
                coefficient_factor_keys=tuple(
                    sorted(_canonical_nonconstant_factor_keys(coefficient))
                ),
                coefficient_source_proved_nonzero=True,
                transforms=tuple(transforms),
                goal_degree=goal_degree,
                transformed_goal=next_goal,
                goal_pivot_quotient=goal_quotient,
            )
        )
        current = tuple(next_current)
        current_variables = tuple(
            item for item in current_variables if item != pivot_variable
        )
        current_goal = next_goal
        current_nonzero = tuple(next_nonzero)

    if not operation_counts_by_stage or len(operation_counts_by_stage) == len(steps):
        operation_counts_by_stage.append(
            tuple(int(sp.count_ops(item)) for _, item in current)
            + (int(sp.count_ops(current_goal)),)
        )

    return GuardedLinearSystem(
        source_polynomials=source_polynomials,
        source_variables=source_variables,
        source_goal=sp.sympify(goal),
        reduced_polynomials=tuple(expression for _, expression in current),
        reduced_source_indices=tuple(source_index for source_index, _ in current),
        reduced_variables=current_variables,
        reduced_goal=current_goal,
        reduced_nonzero_expressions=current_nonzero,
        steps=tuple(steps),
        operation_counts_by_stage=tuple(operation_counts_by_stage),
        stopped_reason=stopped_reason,
    )


def lift_guarded_linear_certificate(
    system: GuardedLinearSystem,
    reduced_multipliers: Iterable[sp.Expr],
    *,
    reduced_goal_multiplier: sp.Expr = sp.Integer(1),
) -> LiftedSaturationCertificate:
    """Lift a reduced ideal certificate back to the source polynomial system."""

    reduced_goal_multiplier = sp.expand(reduced_goal_multiplier)
    reduced_multiplier_keys = tuple(
        sorted(_canonical_nonconstant_factor_keys(reduced_goal_multiplier))
    )
    reduced_multiplier_source_proved_nonzero = set(reduced_multiplier_keys) <= set(
        _known_nonzero_keys(system.reduced_nonzero_expressions)
    )
    multiplier_by_source = dict(
        zip(system.reduced_source_indices, reduced_multipliers, strict=True)
    )
    goal_multiplier = reduced_goal_multiplier
    for step in reversed(system.steps):
        pivot_multiplier = (
            goal_multiplier * step.goal_pivot_quotient
            - sum(
                multiplier_by_source[transform.source_index]
                * transform.pivot_quotient
                for transform in step.transforms
            )
        )
        multiplier_by_source = {
            transform.source_index: (
                multiplier_by_source[transform.source_index]
                * step.coefficient**transform.degree
            )
            for transform in step.transforms
        }
        multiplier_by_source[step.pivot_source_index] = pivot_multiplier
        goal_multiplier = (
            goal_multiplier * step.coefficient**step.goal_degree
        )

    source_multipliers = tuple(
        multiplier_by_source[index]
        for index in range(len(system.source_polynomials))
    )
    coefficient_parameters = tuple(
        sorted(
            set().union(
                goal_multiplier.free_symbols,
                system.source_goal.free_symbols,
                *(item.free_symbols for item in source_multipliers),
                *(item.free_symbols for item in system.source_polynomials),
            )
            - set(system.source_variables),
            key=str,
        )
    )
    domain = (
        sp.QQ.frac_field(*coefficient_parameters)
        if coefficient_parameters
        else sp.QQ
    )
    if system.source_variables:
        residual_poly = sp.Poly(
            goal_multiplier,
            *system.source_variables,
            domain=domain,
        ) * sp.Poly(
            system.source_goal,
            *system.source_variables,
            domain=domain,
        )
        for multiplier, polynomial in zip(
            source_multipliers,
            system.source_polynomials,
            strict=True,
        ):
            residual_poly -= sp.Poly(
                multiplier,
                *system.source_variables,
                domain=domain,
            ) * sp.Poly(
                polynomial,
                *system.source_variables,
                domain=domain,
            )
        replayed = residual_poly.is_zero
        residual = sp.Integer(0) if replayed else residual_poly.as_expr()
    else:
        residual = sp.cancel(
            goal_multiplier * system.source_goal
            - sum(
                multiplier * polynomial
                for multiplier, polynomial in zip(
                    source_multipliers,
                    system.source_polynomials,
                    strict=True,
                )
            )
        )
        replayed = residual == 0
    multiplier_keys = tuple(
        sorted(_canonical_nonconstant_factor_keys(goal_multiplier))
    )
    return LiftedSaturationCertificate(
        goal_multiplier=goal_multiplier,
        reduced_goal_multiplier=reduced_goal_multiplier,
        source_multipliers=source_multipliers,
        replay_residual=residual,
        replayed=replayed,
        reduced_goal_multiplier_factor_keys=reduced_multiplier_keys,
        reduced_goal_multiplier_source_proved_nonzero=(
            reduced_multiplier_source_proved_nonzero
        ),
        nonzero_multiplier_factor_keys=multiplier_keys,
        multiplier_source_proved_nonzero=all(
            step.coefficient_source_proved_nonzero for step in system.steps
        )
        and reduced_multiplier_source_proved_nonzero,
    )


__all__ = [
    "GoalFactorCandidate",
    "GuardedLinearStep",
    "GuardedLinearSystem",
    "LiftedSaturationCertificate",
    "PolynomialTransform",
    "eliminate_source_guarded_linear_variables",
    "lift_guarded_linear_certificate",
    "source_proved_nondegeneracy_factors",
    "source_preserving_goal_factor_candidates",
]
