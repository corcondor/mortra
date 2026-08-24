"""Bounded-degree exact ideal membership through a Macaulay linear system."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
from itertools import combinations_with_replacement
from typing import Any, Iterable, Mapping

import sympy as sp


@dataclass(frozen=True)
class BoundedMacaulayCertificate:
    status: str
    generator_polynomials: tuple[str, ...]
    variables: tuple[str, ...]
    goal_polynomial: str
    multiplier_degree: int | None
    multipliers: tuple[str, ...]
    matrix_rows: int
    matrix_columns: int
    replay_residual: str
    proved: bool
    replayed: bool
    certificate_sha256: str


def _monomials(
    variables: tuple[sp.Symbol, ...],
    max_degree: int,
) -> tuple[sp.Expr, ...]:
    output: list[sp.Expr] = [sp.Integer(1)]
    for degree in range(1, max_degree + 1):
        for indices in combinations_with_replacement(range(len(variables)), degree):
            monomial = sp.Integer(1)
            for index in indices:
                monomial *= variables[index]
            output.append(monomial)
    return tuple(output)


def _coefficient_map(
    expression: sp.Expr,
    variables: tuple[sp.Symbol, ...],
) -> dict[tuple[int, ...], sp.Rational]:
    polynomial = sp.Poly(sp.expand(expression), *variables, domain=sp.QQ)
    return {
        powers: sp.Rational(coefficient)
        for powers, coefficient in polynomial.terms()
    }


def _certificate_hash(
    generators: tuple[sp.Expr, ...],
    variables: tuple[sp.Symbol, ...],
    goal: sp.Expr,
    degree: int | None,
    multipliers: tuple[sp.Expr, ...],
    residual: sp.Expr,
) -> str:
    material = "|".join(
        (
            *(sp.sstr(item) for item in generators),
            *(str(item) for item in variables),
            sp.sstr(goal),
            str(degree),
            *(sp.sstr(item) for item in multipliers),
            sp.sstr(residual),
        )
    )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def certify_bounded_macaulay_membership(
    generators: Iterable[sp.Expr],
    variables: Iterable[sp.Symbol],
    goal: sp.Expr,
    *,
    max_multiplier_degree: int = 1,
    max_matrix_columns: int = 512,
    max_matrix_rows: int = 2_048,
) -> BoundedMacaulayCertificate:
    """Seek an exact low-degree identity ``goal = sum(h_i * generator_i)``.

    This is sound but incomplete.  It never interprets a failed bounded search
    as a mathematical disproof.
    """

    initial = tuple(sp.expand(item) for item in generators if sp.expand(item) != 0)
    ordered_variables = tuple(variables)
    expanded_goal = sp.expand(goal)
    unknown = set().union(
        expanded_goal.free_symbols,
        *(item.free_symbols for item in initial),
    ) - set(ordered_variables)
    if unknown:
        raise ValueError(f"variables omitted from ring: {sorted(map(str, unknown))}")
    if not initial:
        return BoundedMacaulayCertificate(
            status="no_generators",
            generator_polynomials=(),
            variables=tuple(map(str, ordered_variables)),
            goal_polynomial=sp.sstr(expanded_goal),
            multiplier_degree=None,
            multipliers=(),
            matrix_rows=0,
            matrix_columns=0,
            replay_residual=sp.sstr(expanded_goal),
            proved=False,
            replayed=False,
            certificate_sha256=_certificate_hash(
                (), ordered_variables, expanded_goal, None, (), expanded_goal
            ),
        )

    last_rows = 0
    last_columns = 0
    for degree in range(max_multiplier_degree + 1):
        monomials = _monomials(ordered_variables, degree)
        columns = tuple(
            (generator_index, monomial, sp.expand(monomial * generator))
            for generator_index, generator in enumerate(initial)
            for monomial in monomials
        )
        if len(columns) > max_matrix_columns:
            break
        column_maps = tuple(
            _coefficient_map(expression, ordered_variables)
            for _, _, expression in columns
        )
        goal_map = _coefficient_map(expanded_goal, ordered_variables)
        powers = tuple(
            sorted(
                set(goal_map).union(*(set(item) for item in column_maps)),
                reverse=True,
            )
        )
        last_rows = len(powers)
        last_columns = len(columns)
        if last_rows > max_matrix_rows:
            break
        matrix = sp.MutableSparseMatrix(
            last_rows,
            last_columns,
            {
                (row, column): coefficients[power]
                for column, coefficients in enumerate(column_maps)
                for row, power in enumerate(powers)
                if power in coefficients
            },
        )
        target = sp.Matrix([goal_map.get(power, 0) for power in powers])
        solution_set = sp.linsolve((matrix, target))
        if solution_set is sp.EmptySet or not solution_set:
            continue
        solution = tuple(next(iter(solution_set)))
        parameters = set().union(*(item.free_symbols for item in solution))
        substitutions = {parameter: sp.Integer(0) for parameter in parameters}
        coefficients = tuple(sp.expand(item.subs(substitutions)) for item in solution)
        multipliers = [sp.Integer(0) for _ in initial]
        for coefficient, (generator_index, monomial, _) in zip(
            coefficients,
            columns,
            strict=True,
        ):
            multipliers[generator_index] += coefficient * monomial
        multiplier_tuple = tuple(sp.expand(item) for item in multipliers)
        residual = sp.expand(
            expanded_goal
            - sum(
                (
                    multiplier * generator
                    for multiplier, generator in zip(
                        multiplier_tuple,
                        initial,
                        strict=True,
                    )
                ),
                sp.Integer(0),
            )
        )
        replayed = residual == 0
        if replayed:
            return BoundedMacaulayCertificate(
                status="proved",
                generator_polynomials=tuple(sp.sstr(item) for item in initial),
                variables=tuple(map(str, ordered_variables)),
                goal_polynomial=sp.sstr(expanded_goal),
                multiplier_degree=degree,
                multipliers=tuple(sp.sstr(item) for item in multiplier_tuple),
                matrix_rows=last_rows,
                matrix_columns=last_columns,
                replay_residual="0",
                proved=True,
                replayed=True,
                certificate_sha256=_certificate_hash(
                    initial,
                    ordered_variables,
                    expanded_goal,
                    degree,
                    multiplier_tuple,
                    residual,
                ),
            )

    residual = expanded_goal
    return BoundedMacaulayCertificate(
        status="open_within_degree_bound",
        generator_polynomials=tuple(sp.sstr(item) for item in initial),
        variables=tuple(map(str, ordered_variables)),
        goal_polynomial=sp.sstr(expanded_goal),
        multiplier_degree=None,
        multipliers=(),
        matrix_rows=last_rows,
        matrix_columns=last_columns,
        replay_residual=sp.sstr(residual),
        proved=False,
        replayed=False,
        certificate_sha256=_certificate_hash(
            initial,
            ordered_variables,
            expanded_goal,
            None,
            (),
            residual,
        ),
    )


def verify_bounded_macaulay_certificate(
    raw_certificate: Mapping[str, Any] | BoundedMacaulayCertificate,
) -> bool:
    """Replay a serialized exact ideal-membership identity."""

    payload = (
        asdict(raw_certificate)
        if isinstance(raw_certificate, BoundedMacaulayCertificate)
        else dict(raw_certificate)
    )
    try:
        generators = tuple(
            sp.expand(sp.sympify(item))
            for item in payload["generator_polynomials"]
        )
        variables = tuple(sp.Symbol(str(item)) for item in payload["variables"])
        goal = sp.expand(sp.sympify(payload["goal_polynomial"]))
        multipliers = tuple(
            sp.expand(sp.sympify(item)) for item in payload["multipliers"]
        )
        degree = payload.get("multiplier_degree")
        if len(generators) != len(multipliers):
            return False
        residual = sp.expand(
            goal
            - sum(
                (
                    multiplier * generator
                    for multiplier, generator in zip(
                        multipliers,
                        generators,
                        strict=True,
                    )
                ),
                sp.Integer(0),
            )
        )
        expected_hash = _certificate_hash(
            generators,
            variables,
            goal,
            int(degree) if degree is not None else None,
            multipliers,
            residual,
        )
    except (KeyError, TypeError, ValueError, sp.SympifyError):
        return False
    return bool(
        payload.get("proved") is True
        and payload.get("replayed") is True
        and residual == 0
        and str(payload.get("replay_residual")) == "0"
        and payload.get("certificate_sha256") == expected_hash
    )
