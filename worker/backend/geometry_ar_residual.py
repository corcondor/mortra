"""Exact affine residuals for Yuclid angle and length reasoning.

The module does not prove a geometric goal.  It maps typed relations to the
same additive angle/length coordinates used by algebraic reasoning and
measures which part of a goal is still outside the span of known equations.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from typing import Any, Iterable, Mapping


SparseVector = dict[str, Fraction]


@dataclass(frozen=True)
class ARGoalResidual:
    relation: str
    channel: str
    known_equation_count: int
    known_rank: int
    closed: bool
    support_size: int
    l1_weight: float
    residual_terms: tuple[tuple[str, str], ...]


@dataclass(frozen=True)
class ARResidualSummary:
    supported_goal_count: int
    closed_goal_count: int
    residual_support_size: int
    residual_l1_weight: float
    known_rank: int
    goals: tuple[ARGoalResidual, ...]


def _add(vector: SparseVector, term: str, coefficient: int | Fraction) -> None:
    value = vector.get(term, Fraction()) + Fraction(coefficient)
    if value:
        vector[term] = value
    else:
        vector.pop(term, None)


def _line(a: str, b: str) -> str:
    first, second = sorted((a, b))
    return f"angle:{first}-{second}"


def _length(a: str, b: str) -> str:
    first, second = sorted((a, b))
    return f"length:{first}-{second}"


def relation_equation(name: str, points: Iterable[str]) -> tuple[str, SparseVector] | None:
    """Translate a typed Euclidean relation to an additive AR equation."""

    values = tuple(str(point) for point in points)
    vector: SparseVector = {}
    if name == "cong" and len(values) == 4:
        _add(vector, _length(values[0], values[1]), 1)
        _add(vector, _length(values[2], values[3]), -1)
        return "length", vector
    if name == "coll" and len(values) == 3:
        _add(vector, _line(values[0], values[1]), 1)
        _add(vector, _line(values[0], values[2]), -1)
        return "angle", vector
    if name in {"para", "perp"} and len(values) == 4:
        _add(vector, _line(values[0], values[1]), 1)
        _add(vector, _line(values[2], values[3]), -1)
        if name == "perp":
            _add(vector, "angle:#quarter_turn", -1)
        return "angle", vector
    if name == "eqangle" and len(values) == 8:
        _add(vector, _line(values[0], values[1]), 1)
        _add(vector, _line(values[2], values[3]), -1)
        _add(vector, _line(values[4], values[5]), -1)
        _add(vector, _line(values[6], values[7]), 1)
        return "angle", vector
    if name == "cyclic" and len(values) == 4:
        a, b, c, d = values
        _add(vector, _line(b, a), -1)
        _add(vector, _line(d, a), 1)
        _add(vector, _line(b, c), 1)
        _add(vector, _line(d, c), -1)
        return "angle", vector
    return None


def _normalized(vector: Mapping[str, Fraction]) -> SparseVector:
    result = {term: Fraction(value) for term, value in vector.items() if value}
    if not result:
        return {}
    pivot = min(result)
    scale = result[pivot]
    return {term: value / scale for term, value in result.items()}


def _reduce(vector: Mapping[str, Fraction], basis: Mapping[str, SparseVector]) -> SparseVector:
    result = {term: Fraction(value) for term, value in vector.items() if value}
    for pivot in sorted(basis):
        coefficient = result.get(pivot, Fraction())
        if not coefficient:
            continue
        for term, value in basis[pivot].items():
            _add(result, term, -coefficient * value)
    return result


def _row_basis(vectors: Iterable[Mapping[str, Fraction]]) -> dict[str, SparseVector]:
    basis: dict[str, SparseVector] = {}
    for raw in vectors:
        row = _reduce(raw, basis)
        if not row:
            continue
        row = _normalized(row)
        pivot = min(row)
        for other_pivot, other in tuple(basis.items()):
            coefficient = other.get(pivot, Fraction())
            if not coefficient:
                continue
            updated = dict(other)
            for term, value in row.items():
                _add(updated, term, -coefficient * value)
            basis[other_pivot] = _normalized(updated)
        basis[pivot] = row
    return dict(sorted(basis.items()))


def _assertions(payload: Mapping[str, Any]) -> tuple[tuple[str, tuple[str, ...]], ...]:
    assertions: dict[tuple[str, tuple[str, ...]], None] = {}
    for deduction in payload.get("all_deductions", ()):
        if not isinstance(deduction, Mapping):
            continue
        for assertion in deduction.get("assertions", ()):
            if not isinstance(assertion, Mapping):
                continue
            name = str(assertion.get("name", ""))
            points = tuple(str(point) for point in assertion.get("points", ()))
            assertions.setdefault((name, points), None)
    return tuple(assertions)


def yuclid_ar_residual(
    payload: Mapping[str, Any],
    goals: Iterable[tuple[str, Iterable[str]]],
) -> ARResidualSummary:
    """Measure exact row-space residuals for all supported typed goals."""

    equations: dict[str, list[SparseVector]] = {"angle": [], "length": []}
    seen: dict[str, set[tuple[tuple[str, Fraction], ...]]] = {
        "angle": set(),
        "length": set(),
    }
    for name, points in _assertions(payload):
        translated = relation_equation(name, points)
        if translated is None:
            continue
        channel, vector = translated
        key = tuple(sorted(_normalized(vector).items()))
        if key and key not in seen[channel]:
            seen[channel].add(key)
            equations[channel].append(vector)

    bases = {channel: _row_basis(rows) for channel, rows in equations.items()}
    residuals: list[ARGoalResidual] = []
    for name, points in goals:
        translated = relation_equation(str(name), points)
        if translated is None:
            continue
        channel, target = translated
        residual = _reduce(target, bases[channel])
        residuals.append(
            ARGoalResidual(
                relation=str(name),
                channel=channel,
                known_equation_count=len(equations[channel]),
                known_rank=len(bases[channel]),
                closed=not residual,
                support_size=len(residual),
                l1_weight=float(sum(abs(value) for value in residual.values())),
                residual_terms=tuple(
                    (term, str(value)) for term, value in sorted(residual.items())
                ),
            )
        )
    return ARResidualSummary(
        supported_goal_count=len(residuals),
        closed_goal_count=sum(item.closed for item in residuals),
        residual_support_size=sum(item.support_size for item in residuals),
        residual_l1_weight=sum(item.l1_weight for item in residuals),
        known_rank=sum(len(basis) for basis in bases.values()),
        goals=tuple(residuals),
    )
