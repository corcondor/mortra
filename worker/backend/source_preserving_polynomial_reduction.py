"""Source-certificate-preserving reduction by simple triangular relations."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable

import sympy as sp


@dataclass(frozen=True)
class ReducedPolynomial:
    input_index: int
    expression: sp.Expr
    reducer_quotients: tuple[sp.Expr, ...]


@dataclass(frozen=True)
class SourcePreservingReduction:
    input_polynomials: tuple[sp.Expr, ...]
    variables: tuple[sp.Symbol, ...]
    reduced_variables: tuple[sp.Symbol, ...]
    goal: sp.Expr
    reducer_input_indices: tuple[int, ...]
    eliminated_reducer_input_indices: tuple[int, ...]
    reduced_polynomials: tuple[ReducedPolynomial, ...]
    reduced_goal: sp.Expr
    goal_reducer_quotients: tuple[sp.Expr, ...]


def _reduce_expression(
    expression: sp.Expr,
    reducers: tuple[tuple[int, sp.Symbol, sp.Expr], ...],
) -> tuple[sp.Expr, tuple[sp.Expr, ...]]:
    if not reducers:
        return expression, ()
    remainder = sp.expand(expression)
    quotients: list[sp.Expr] = []
    for _, variable, reducer in reducers:
        dividend = sp.Poly(remainder, variable, domain="EX")
        divisor = sp.Poly(reducer, variable, domain="EX")
        if divisor.LC() != 1:
            raise ValueError("triangular reducer must be monic")

        divisor_degree = divisor.degree()
        divisor_coefficients = {
            power[0]: coefficient for power, coefficient in divisor.terms()
        }
        work = {power[0]: coefficient for power, coefficient in dividend.terms()}
        quotient_coefficients: dict[int, sp.Expr] = {}
        while work and max(work) >= divisor_degree:
            degree = max(work)
            leading = work.pop(degree)
            offset = degree - divisor_degree
            quotient_coefficients[offset] = (
                quotient_coefficients.get(offset, sp.Integer(0)) + leading
            )
            for power, coefficient in divisor_coefficients.items():
                if power == divisor_degree:
                    continue
                target = power + offset
                work[target] = (
                    work.get(target, sp.Integer(0)) - leading * coefficient
                )

        quotient = sp.expand(
            sum(
                coefficient * variable**power
                for power, coefficient in quotient_coefficients.items()
            )
        )
        remainder = sp.expand(
            sum(coefficient * variable**power for power, coefficient in work.items())
        )
        quotients.append(sp.expand(quotient))
    return remainder, tuple(quotients)


def reduce_by_monic_univariate_relations(
    polynomials: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal: sp.Expr,
    *,
    max_degree: int = 2,
) -> SourcePreservingReduction:
    """Reduce by monic equations involving one proof variable each."""

    inputs = tuple(sp.sympify(item) for item in polynomials)
    ordered_variables = tuple(variables)
    if max_degree < 1:
        return SourcePreservingReduction(
            input_polynomials=inputs,
            variables=ordered_variables,
            reduced_variables=ordered_variables,
            goal=sp.sympify(goal),
            reducer_input_indices=(),
            eliminated_reducer_input_indices=(),
            reduced_polynomials=tuple(
                ReducedPolynomial(
                    input_index=input_index,
                    expression=expression,
                    reducer_quotients=(),
                )
                for input_index, expression in enumerate(inputs)
            ),
            reduced_goal=sp.sympify(goal),
            goal_reducer_quotients=(),
        )
    reducers: list[tuple[int, sp.Symbol, sp.Expr]] = []
    used_variables: set[sp.Symbol] = set()
    for input_index, expression in enumerate(inputs):
        proof_symbols = expression.free_symbols & set(ordered_variables)
        if len(proof_symbols) != 1:
            continue
        variable = next(iter(proof_symbols))
        if variable in used_variables:
            continue
        polynomial = sp.Poly(expression, variable, domain="EX")
        if not 1 <= polynomial.degree() <= max_degree:
            continue
        if sp.expand(polynomial.LC()) not in {sp.Integer(1), sp.Integer(-1)}:
            continue
        normalized = expression if polynomial.LC() == 1 else -expression
        reducers.append((input_index, variable, normalized))
        used_variables.add(variable)

    reducer_tuple = tuple(reducers)
    if not reducer_tuple:
        return SourcePreservingReduction(
            input_polynomials=inputs,
            variables=ordered_variables,
            reduced_variables=ordered_variables,
            goal=sp.sympify(goal),
            reducer_input_indices=(),
            eliminated_reducer_input_indices=(),
            reduced_polynomials=tuple(
                ReducedPolynomial(
                    input_index=input_index,
                    expression=expression,
                    reducer_quotients=(),
                )
                for input_index, expression in enumerate(inputs)
            ),
            reduced_goal=sp.sympify(goal),
            goal_reducer_quotients=(),
        )
    eliminated_reducer_indices = {
        input_index
        for input_index, variable, reducer in reducer_tuple
        if sp.Poly(reducer, variable, domain="EX").degree() == 1
    }
    reduced: list[ReducedPolynomial] = []
    for input_index, expression in enumerate(inputs):
        if input_index in eliminated_reducer_indices:
            continue
        if input_index in {item[0] for item in reducer_tuple}:
            reduced.append(
                ReducedPolynomial(
                    input_index=input_index,
                    expression=expression,
                    reducer_quotients=tuple(sp.Integer(0) for _ in reducer_tuple),
                )
            )
            continue
        remainder, quotients = _reduce_expression(expression, reducer_tuple)
        reduced.append(
            ReducedPolynomial(
                input_index=input_index,
                expression=remainder,
                reducer_quotients=quotients,
            )
        )
    reduced_goal, goal_quotients = _reduce_expression(goal, reducer_tuple)
    return SourcePreservingReduction(
        input_polynomials=inputs,
        variables=ordered_variables,
        reduced_variables=tuple(
            variable
            for variable in ordered_variables
            if variable
            not in {
                reducer_variable
                for input_index, reducer_variable, _ in reducer_tuple
                if input_index in eliminated_reducer_indices
            }
        ),
        goal=sp.sympify(goal),
        reducer_input_indices=tuple(item[0] for item in reducer_tuple),
        eliminated_reducer_input_indices=tuple(sorted(eliminated_reducer_indices)),
        reduced_polynomials=tuple(reduced),
        reduced_goal=reduced_goal,
        goal_reducer_quotients=goal_quotients,
    )


def retarget_source_preserving_reduction(
    reduction: SourcePreservingReduction,
    goal: sp.Expr,
) -> SourcePreservingReduction:
    """Reuse an exact source reduction while reducing a different goal."""

    reducers: list[tuple[int, sp.Symbol, sp.Expr]] = []
    for input_index in reduction.reducer_input_indices:
        expression = reduction.input_polynomials[input_index]
        proof_symbols = expression.free_symbols & set(reduction.variables)
        if len(proof_symbols) != 1:
            raise ValueError("stored triangular reducer is no longer univariate")
        variable = next(iter(proof_symbols))
        polynomial = sp.Poly(expression, variable, domain="EX")
        if sp.expand(polynomial.LC()) not in {sp.Integer(1), sp.Integer(-1)}:
            raise ValueError("stored triangular reducer is no longer monic")
        normalized = expression if polynomial.LC() == 1 else -expression
        reducers.append((input_index, variable, normalized))

    parsed_goal = sp.sympify(goal)
    reduced_goal, goal_quotients = _reduce_expression(
        parsed_goal,
        tuple(reducers),
    )
    return replace(
        reduction,
        goal=parsed_goal,
        reduced_goal=reduced_goal,
        goal_reducer_quotients=goal_quotients,
    )


def lift_reduced_multipliers(
    reduction: SourcePreservingReduction,
    reduced_multipliers: Iterable[sp.Expr],
    *,
    goal_multiplier: sp.Expr = sp.Integer(1),
) -> tuple[sp.Expr, ...]:
    """Lift reduced-polynomial multipliers to the input polynomial list."""

    reduced_multiplier_tuple = tuple(sp.sympify(item) for item in reduced_multipliers)
    goal_multiplier = sp.sympify(goal_multiplier)
    if len(reduced_multiplier_tuple) != len(reduction.reduced_polynomials):
        raise ValueError("one multiplier is required for every reduced polynomial")
    multipliers = [sp.Integer(0) for _ in reduction.input_polynomials]
    for multiplier, item in zip(
        reduced_multiplier_tuple,
        reduction.reduced_polynomials,
        strict=True,
    ):
        multipliers[item.input_index] = multiplier
    for reducer_offset, reducer_input_index in enumerate(
        reduction.reducer_input_indices
    ):
        correction = (
            goal_multiplier * reduction.goal_reducer_quotients[reducer_offset]
            - sum(
                multiplier * item.reducer_quotients[reducer_offset]
                for multiplier, item in zip(
                    reduced_multiplier_tuple,
                    reduction.reduced_polynomials,
                    strict=True,
                )
            )
        )
        multipliers[reducer_input_index] = (
            multipliers[reducer_input_index] + correction
        )

    coefficient_parameters = tuple(
        sorted(
            set().union(
                goal_multiplier.free_symbols,
                reduction.goal.free_symbols,
                *(item.free_symbols for item in multipliers),
                *(item.free_symbols for item in reduction.input_polynomials),
            )
            - set(reduction.variables),
            key=str,
        )
    )
    domain = (
        sp.QQ.frac_field(*coefficient_parameters)
        if coefficient_parameters
        else sp.QQ
    )
    if reduction.variables:
        residual = sp.Poly(
            goal_multiplier * reduction.goal,
            *reduction.variables,
            domain=domain,
        )
        for multiplier, polynomial in zip(
            multipliers,
            reduction.input_polynomials,
            strict=True,
        ):
            residual -= sp.Poly(
                multiplier * polynomial,
                *reduction.variables,
                domain=domain,
            )
        replayed = residual.is_zero
    else:
        replayed = sp.cancel(
            goal_multiplier * reduction.goal
            - sum(
                multiplier * polynomial
                for multiplier, polynomial in zip(
                    multipliers,
                    reduction.input_polynomials,
                    strict=True,
                )
            )
        ) == 0
    if not replayed:
        raise AssertionError("source-preserving polynomial reduction did not replay")
    return tuple(multipliers)


def lift_reduced_power_multipliers(
    reduction: SourcePreservingReduction,
    reduced_multipliers: Iterable[sp.Expr],
    *,
    exponent: int,
) -> tuple[sp.Expr, ...]:
    """Lift ``reduced_goal**exponent`` to ``goal**exponent`` exactly."""

    if exponent < 1:
        raise ValueError("power-lift exponent must be positive")
    reduced_multiplier_tuple = tuple(sp.sympify(item) for item in reduced_multipliers)
    if len(reduced_multiplier_tuple) != len(reduction.reduced_polynomials):
        raise ValueError("one multiplier is required for every reduced polynomial")

    goal = reduction.goal
    reduced_goal = reduction.reduced_goal
    difference_quotient = sum(
        goal ** (exponent - 1 - offset) * reduced_goal**offset
        for offset in range(exponent)
    )
    multipliers = [sp.Integer(0) for _ in reduction.input_polynomials]
    for multiplier, item in zip(
        reduced_multiplier_tuple,
        reduction.reduced_polynomials,
        strict=True,
    ):
        multipliers[item.input_index] = multiplier
    for reducer_offset, reducer_input_index in enumerate(
        reduction.reducer_input_indices
    ):
        correction = (
            difference_quotient * reduction.goal_reducer_quotients[reducer_offset]
            - sum(
                multiplier * item.reducer_quotients[reducer_offset]
                for multiplier, item in zip(
                    reduced_multiplier_tuple,
                    reduction.reduced_polynomials,
                    strict=True,
                )
            )
        )
        multipliers[reducer_input_index] += correction

    coefficient_parameters = tuple(
        sorted(
            set().union(
                goal.free_symbols,
                reduced_goal.free_symbols,
                *(item.free_symbols for item in multipliers),
                *(item.free_symbols for item in reduction.input_polynomials),
            )
            - set(reduction.variables),
            key=str,
        )
    )
    domain = (
        sp.QQ.frac_field(*coefficient_parameters)
        if coefficient_parameters
        else sp.QQ
    )
    if reduction.variables:
        residual = sp.Poly(goal**exponent, *reduction.variables, domain=domain)
        for multiplier, polynomial in zip(
            multipliers,
            reduction.input_polynomials,
            strict=True,
        ):
            residual -= sp.Poly(
                multiplier * polynomial,
                *reduction.variables,
                domain=domain,
            )
        replayed = residual.is_zero
    else:
        replayed = sp.cancel(
            goal**exponent
            - sum(
                multiplier * polynomial
                for multiplier, polynomial in zip(
                    multipliers,
                    reduction.input_polynomials,
                    strict=True,
                )
            )
        ) == 0
    if not replayed:
        raise AssertionError("source-preserving power lift did not replay")
    return tuple(multipliers)


__all__ = [
    "ReducedPolynomial",
    "SourcePreservingReduction",
    "lift_reduced_power_multipliers",
    "lift_reduced_multipliers",
    "reduce_by_monic_univariate_relations",
    "retarget_source_preserving_reduction",
]
