"""Exact representation charts for typed Euclidean relations.

The atlas changes coordinates, not truth.  Metric relations are represented
as linear forms in squared distances and affine incidence relations as linear
forms in homogeneous three-point brackets.  Every lift and every cross-chart
equivalence is replayed in an independent Cartesian realization before it can
be used by search.

The module contains no problem identifiers, expected answers, or text
patterns.  Point names are opaque typed entities and may include proof holes.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
import hashlib
from itertools import combinations
from typing import Iterable, Mapping, Sequence

import sympy as sp

from worker.backend.geometry_proof_hypergraph import Atom


METRIC_CHART = "metric_squared_distance"
AFFINE_CHART = "affine_determinant"


def _render(atom: Atom) -> str:
    atom = atom.canonical()
    return f"{atom.predicate}({','.join(atom.arguments)})"


def _rational_text(value: sp.Rational) -> str:
    value = sp.Rational(value)
    return f"{value.p}/{value.q}"


def _clean(values: Mapping[str, sp.Rational]) -> dict[str, sp.Rational]:
    return {
        str(key): sp.Rational(value)
        for key, value in values.items()
        if sp.Rational(value) != 0
    }


def _serialized(values: Mapping[str, sp.Rational]) -> tuple[tuple[str, str], ...]:
    return tuple(
        (key, _rational_text(value))
        for key, value in sorted(_clean(values).items())
    )


def _canonical_key(values: Mapping[str, sp.Rational]) -> tuple[tuple[str, str], ...]:
    cleaned = _clean(values)
    if not cleaned:
        return ()
    first = cleaned[min(cleaned)]
    return _serialized({key: value / first for key, value in cleaned.items()})


def _add(
    output: dict[str, sp.Rational],
    feature: str,
    coefficient: sp.Rational,
) -> None:
    output[feature] = output.get(feature, sp.Rational(0)) + sp.Rational(coefficient)
    if output[feature] == 0:
        del output[feature]


def _distance_feature(left: str, right: str) -> str | None:
    if left == right:
        return None
    left, right = sorted((str(left), str(right)))
    return f"d2({left},{right})"


def _permutation_sign(values: Sequence[str]) -> int:
    inversions = sum(
        values[left] > values[right]
        for left in range(len(values))
        for right in range(left + 1, len(values))
    )
    return -1 if inversions % 2 else 1


def _bracket_feature(first: str, second: str, third: str) -> tuple[str, int] | None:
    values = (str(first), str(second), str(third))
    if len(set(values)) < 3:
        return None
    ordered = tuple(sorted(values))
    return f"br({','.join(ordered)})", _permutation_sign(values)


def _metric_length_equation(
    tokens: Sequence[str],
) -> dict[str, sp.Rational] | None:
    """Parse the linear squared-distance fragment of Newclid lequation."""

    if len(tokens) < 4:
        return None
    try:
        constant = sp.Rational(tokens[-1])
    except (TypeError, ValueError):
        return None
    output: dict[str, sp.Rational] = {}
    if constant:
        _add(output, "1", -constant)
    index = 0
    end = len(tokens) - 1
    while index < end:
        try:
            coefficient = sp.Rational(tokens[index])
        except (TypeError, ValueError):
            return None
        index += 1
        segments: list[tuple[str, str]] = []
        if index + 1 >= end:
            return None
        segments.append(tuple(sorted((tokens[index], tokens[index + 1]))))
        index += 2
        while index < end and tokens[index] == "*":
            index += 1
            if index + 1 >= end:
                return None
            segments.append(tuple(sorted((tokens[index], tokens[index + 1]))))
            index += 2
        multiplicities: dict[tuple[str, str], int] = {}
        for left, right in segments:
            if left == right:
                return None
            key = (left, right)
            multiplicities[key] = multiplicities.get(key, 0) + 1
        if any(value % 2 for value in multiplicities.values()):
            return None
        powers = {
            key: multiplicity // 2
            for key, multiplicity in multiplicities.items()
            if multiplicity
        }
        # This chart is deliberately linear. Products of squared lengths stay
        # in the polynomial chart and are not silently approximated here.
        if sum(powers.values()) != 1:
            return None
        (left, right), _power = next(iter(powers.items()))
        feature = _distance_feature(left, right)
        if feature is None:
            return None
        _add(output, feature, coefficient)
    return _clean(output)


def _metric_vector(atom: Atom) -> dict[str, sp.Rational] | None:
    atom = atom.canonical()
    args = atom.arguments
    output: dict[str, sp.Rational] = {}
    if atom.predicate == "cong" and len(args) == 4:
        left = _distance_feature(args[0], args[1])
        right = _distance_feature(args[2], args[3])
        if left is None or right is None:
            return None
        _add(output, left, 1)
        _add(output, right, -1)
        return _clean(output)
    if atom.predicate == "perp" and len(args) == 4:
        a, b, c, d = args
        # 2 (B-A).(D-C) = BC^2 + AD^2 - BD^2 - AC^2.
        for coefficient, pair in (
            (1, (b, c)),
            (1, (a, d)),
            (-1, (b, d)),
            (-1, (a, c)),
        ):
            feature = _distance_feature(*pair)
            if feature is not None:
                _add(output, feature, sp.Rational(coefficient, 2))
        return _clean(output)
    if atom.predicate == "lequation":
        return _metric_length_equation(args)
    return None


def _affine_vector(atom: Atom) -> dict[str, sp.Rational] | None:
    atom = atom.canonical()
    args = atom.arguments
    output: dict[str, sp.Rational] = {}
    if atom.predicate == "coll" and len(args) == 3:
        feature = _bracket_feature(*args)
        if feature is None:
            return None
        name, sign = feature
        _add(output, name, sign)
        return output
    if atom.predicate == "para" and len(args) == 4:
        a, b, c, d = args
        # cross(B-A, D-C) = [A,B,D] - [A,B,C].
        for coefficient, triple in ((1, (a, b, d)), (-1, (a, b, c))):
            feature = _bracket_feature(*triple)
            if feature is None:
                continue
            name, sign = feature
            _add(output, name, coefficient * sign)
        return _clean(output) or None
    return None


def _point_names(atom: Atom) -> tuple[str, ...]:
    atom = atom.canonical()
    if atom.predicate != "lequation":
        return tuple(dict.fromkeys(atom.arguments))
    points: list[str] = []
    index = 0
    end = len(atom.arguments) - 1
    while index < end:
        try:
            sp.Rational(atom.arguments[index])
        except (TypeError, ValueError):
            return ()
        index += 1
        if index + 1 >= end:
            return ()
        points.extend((atom.arguments[index], atom.arguments[index + 1]))
        index += 2
        while index < end and atom.arguments[index] == "*":
            index += 1
            if index + 1 >= end:
                return ()
            points.extend((atom.arguments[index], atom.arguments[index + 1]))
            index += 2
    return tuple(dict.fromkeys(points))


def _coordinates(points: Iterable[str]) -> dict[str, tuple[sp.Symbol, sp.Symbol]]:
    return {
        point: (sp.Symbol(f"x_{index}"), sp.Symbol(f"y_{index}"))
        for index, point in enumerate(sorted(set(points)))
    }


def _sub(
    left: tuple[sp.Expr, sp.Expr], right: tuple[sp.Expr, sp.Expr]
) -> tuple[sp.Expr, sp.Expr]:
    return left[0] - right[0], left[1] - right[1]


def _dot(
    left: tuple[sp.Expr, sp.Expr], right: tuple[sp.Expr, sp.Expr]
) -> sp.Expr:
    return sp.expand(left[0] * right[0] + left[1] * right[1])


def _cross(
    left: tuple[sp.Expr, sp.Expr], right: tuple[sp.Expr, sp.Expr]
) -> sp.Expr:
    return sp.expand(left[0] * right[1] - left[1] * right[0])


def _distance_squared(
    coordinates: Mapping[str, tuple[sp.Symbol, sp.Symbol]],
    left: str,
    right: str,
) -> sp.Expr:
    delta = _sub(coordinates[left], coordinates[right])
    return _dot(delta, delta)


def _bracket(
    coordinates: Mapping[str, tuple[sp.Symbol, sp.Symbol]],
    first: str,
    second: str,
    third: str,
) -> sp.Expr:
    return _cross(
        _sub(coordinates[second], coordinates[first]),
        _sub(coordinates[third], coordinates[first]),
    )


def _feature_polynomial(
    feature: str,
    coordinates: Mapping[str, tuple[sp.Symbol, sp.Symbol]],
) -> sp.Expr:
    if feature == "1":
        return sp.Integer(1)
    if feature.startswith("d2("):
        left, right = feature[3:-1].split(",")
        return _distance_squared(coordinates, left, right)
    if feature.startswith("br("):
        first, second, third = feature[3:-1].split(",")
        return _bracket(coordinates, first, second, third)
    raise ValueError(f"unknown chart feature: {feature}")


def _direct_polynomial(
    atom: Atom,
    coordinates: Mapping[str, tuple[sp.Symbol, sp.Symbol]],
) -> sp.Expr | None:
    atom = atom.canonical()
    args = atom.arguments
    if atom.predicate == "cong" and len(args) == 4:
        return sp.expand(
            _distance_squared(coordinates, args[0], args[1])
            - _distance_squared(coordinates, args[2], args[3])
        )
    if atom.predicate == "perp" and len(args) == 4:
        return _dot(
            _sub(coordinates[args[1]], coordinates[args[0]]),
            _sub(coordinates[args[3]], coordinates[args[2]]),
        )
    if atom.predicate == "coll" and len(args) == 3:
        return _bracket(coordinates, *args)
    if atom.predicate == "para" and len(args) == 4:
        return _cross(
            _sub(coordinates[args[1]], coordinates[args[0]]),
            _sub(coordinates[args[3]], coordinates[args[2]]),
        )
    if atom.predicate == "lequation":
        index = 0
        end = len(args) - 1
        try:
            expression = -sp.Rational(args[-1])
        except (TypeError, ValueError):
            return None
        while index < end:
            try:
                term = sp.Rational(args[index])
            except (TypeError, ValueError):
                return None
            index += 1
            if index + 1 >= end:
                return None
            segments = [(args[index], args[index + 1])]
            index += 2
            while index < end and args[index] == "*":
                index += 1
                if index + 1 >= end:
                    return None
                segments.append((args[index], args[index + 1]))
                index += 2
            multiplicities: dict[tuple[str, str], int] = {}
            for left, right in segments:
                key = tuple(sorted((left, right)))
                multiplicities[key] = multiplicities.get(key, 0) + 1
            if any(value % 2 for value in multiplicities.values()):
                return None
            for (left, right), multiplicity in multiplicities.items():
                term *= _distance_squared(coordinates, left, right) ** (
                    multiplicity // 2
                )
            expression += term
        return sp.expand(expression)
    return None


@dataclass(frozen=True)
class RelationChartLift:
    atom: Atom
    chart: str
    coefficients: tuple[tuple[str, str], ...]
    canonical_key: tuple[tuple[str, str], ...]
    coordinate_polynomial: str
    replay_residual: str
    replayed: bool


@dataclass(frozen=True)
class RelationChartEquivalence:
    source: Atom
    target: Atom
    chart: str
    source_key: tuple[tuple[str, str], ...]
    target_key: tuple[tuple[str, str], ...]
    coordinate_scale: str
    replay_residual: str
    replayed: bool
    certificate_sha256: str


@lru_cache(maxsize=65536)
def _chart_vector_signature(
    atom: Atom,
) -> tuple[
    str,
    tuple[tuple[str, str], ...],
    tuple[tuple[str, str], ...],
] | None:
    """Return the cheap algebraic signature before Cartesian replay."""

    atom = atom.canonical()
    vector = _metric_vector(atom)
    chart = METRIC_CHART
    if vector is None:
        vector = _affine_vector(atom)
        chart = AFFINE_CHART
    if vector is None or not vector:
        return None
    return chart, _serialized(vector), _canonical_key(vector)


@lru_cache(maxsize=65536)
def lift_relation(atom: Atom) -> RelationChartLift | None:
    atom = atom.canonical()
    signature = _chart_vector_signature(atom)
    if signature is None:
        return None
    chart, coefficients, canonical_key = signature
    vector = {
        feature: sp.Rational(value) for feature, value in coefficients
    }
    points = _point_names(atom)
    if not points:
        return None
    coordinates = _coordinates(points)
    chart_polynomial = sp.expand(
        sum(
            (
                coefficient * _feature_polynomial(feature, coordinates)
                for feature, coefficient in vector.items()
            ),
            sp.Integer(0),
        )
    )
    direct = _direct_polynomial(atom, coordinates)
    if direct is None:
        return None
    residual = sp.expand(direct - chart_polynomial)
    return RelationChartLift(
        atom=atom,
        chart=chart,
        coefficients=coefficients,
        canonical_key=canonical_key,
        coordinate_polynomial=sp.sstr(chart_polynomial),
        replay_residual=sp.sstr(residual),
        replayed=residual == 0,
    )


def _vector(lift: RelationChartLift) -> dict[str, sp.Rational]:
    return {feature: sp.Rational(value) for feature, value in lift.coefficients}


@lru_cache(maxsize=65536)
def certify_relation_equivalence(
    source: Atom,
    target: Atom,
) -> RelationChartEquivalence | None:
    source = source.canonical()
    target = target.canonical()
    source_signature = _chart_vector_signature(source)
    target_signature = _chart_vector_signature(target)
    if (
        source_signature is None
        or target_signature is None
        or source_signature[0] != target_signature[0]
        or source_signature[2] != target_signature[2]
    ):
        return None
    source_lift = lift_relation(source)
    target_lift = lift_relation(target)
    if (
        source_lift is None
        or target_lift is None
        or not source_lift.replayed
        or not target_lift.replayed
        or source_lift.chart != target_lift.chart
        or source_lift.canonical_key != target_lift.canonical_key
    ):
        return None
    source_vector = _vector(source_lift)
    target_vector = _vector(target_lift)
    pivot = min(source_vector)
    scale = sp.Rational(source_vector[pivot], target_vector[pivot])
    points = tuple(dict.fromkeys((*_point_names(source), *_point_names(target))))
    coordinates = _coordinates(points)
    source_polynomial = _direct_polynomial(source, coordinates)
    target_polynomial = _direct_polynomial(target, coordinates)
    if source_polynomial is None or target_polynomial is None:
        return None
    residual = sp.expand(source_polynomial - scale * target_polynomial)
    replayed = residual == 0
    material = "|".join(
        (
            _render(source),
            _render(target),
            source_lift.chart,
            _rational_text(scale),
            sp.sstr(residual),
        )
    )
    return RelationChartEquivalence(
        source=source.canonical(),
        target=target.canonical(),
        chart=source_lift.chart,
        source_key=source_lift.canonical_key,
        target_key=target_lift.canonical_key,
        coordinate_scale=_rational_text(scale),
        replay_residual=sp.sstr(residual),
        replayed=replayed,
        certificate_sha256=hashlib.sha256(material.encode("utf-8")).hexdigest(),
    )


def _squared_segment_tokens(coefficient: int, left: str, right: str) -> tuple[str, ...]:
    return (f"{coefficient}/1", left, right, "*", left, right)


def _identity_length_equation(atom: Atom) -> Atom | None:
    atom = atom.canonical()
    args = atom.arguments
    tokens: tuple[str, ...]
    if atom.predicate == "perp" and len(args) == 4:
        a, b, c, d = args
        tokens = (
            *_squared_segment_tokens(1, b, c),
            *_squared_segment_tokens(1, a, d),
            *_squared_segment_tokens(-1, b, d),
            *_squared_segment_tokens(-1, a, c),
            "0",
        )
    elif atom.predicate == "cong" and len(args) == 4:
        tokens = (
            *_squared_segment_tokens(1, args[0], args[1]),
            *_squared_segment_tokens(-1, args[2], args[3]),
            "0",
        )
    else:
        return None
    return Atom("lequation", tokens)


@lru_cache(maxsize=32768)
def certified_equivalent_relations(
    atom: Atom,
    *,
    max_candidates: int = 128,
) -> tuple[RelationChartEquivalence, ...]:
    """Enumerate a finite named chart fibre and certify every returned edge."""

    source = atom.canonical()
    lift = lift_relation(source)
    if lift is None or not lift.replayed:
        return ()
    points = tuple(sorted(set(_point_names(source))))
    candidates: list[Atom] = []
    if lift.chart == METRIC_CHART:
        # A named perp/cong relation contains at most four points.  More than
        # four support points cannot be proportional to either relation, so no
        # finite candidate scan is required in that case.
        if len(points) <= 4:
            segments = tuple(combinations(points, 2))
            for left, right in combinations(segments, 2):
                candidates.append(Atom("perp", (*left, *right)).canonical())
                candidates.append(Atom("cong", (*left, *right)).canonical())
        identity = _identity_length_equation(source)
        if identity is not None:
            candidates.append(identity)
    elif lift.chart == AFFINE_CHART:
        candidates.extend(
            Atom("coll", triple).canonical() for triple in combinations(points, 3)
        )
        segments = tuple(combinations(points, 2))
        candidates.extend(
            Atom("para", (*left, *right)).canonical()
            for left, right in combinations(segments, 2)
        )
    output: dict[Atom, RelationChartEquivalence] = {}
    for candidate in candidates:
        if candidate == source:
            continue
        certificate = certify_relation_equivalence(source, candidate)
        if certificate is not None and certificate.replayed:
            output.setdefault(candidate, certificate)
            if len(output) >= max_candidates:
                break
    return tuple(output.values())


@lru_cache(maxsize=32768)
def equivalent_atoms(atom: Atom, *, max_candidates: int = 128) -> tuple[Atom, ...]:
    return tuple(
        certificate.target
        for certificate in certified_equivalent_relations(
            atom, max_candidates=max_candidates
        )
    )


@dataclass(frozen=True)
class ChartAtomResidual:
    atom: Atom
    chart: str | None
    remainder: tuple[tuple[str, str], ...]
    proved: bool
    replayed: bool


@dataclass(frozen=True)
class ChartBranchResidual:
    branch_index: int
    atoms: tuple[ChartAtomResidual, ...]
    rank: tuple[int, int, int]


@dataclass(frozen=True)
class RelationChartResidual:
    branches: tuple[ChartBranchResidual, ...]
    selected_branch_index: int | None
    selected_rank: tuple[int, int, int]


def _rref_rows(
    rows: Sequence[Sequence[sp.Rational]],
) -> tuple[tuple[tuple[sp.Rational, ...], tuple[sp.Rational, ...], int], ...]:
    if not rows:
        return ()
    width = len(rows[0])
    count = len(rows)
    values = [list(map(sp.Rational, row)) for row in rows]
    transforms = [
        [sp.Rational(1 if left == right else 0) for right in range(count)]
        for left in range(count)
    ]
    pivot_row = 0
    records: list[tuple[tuple[sp.Rational, ...], tuple[sp.Rational, ...], int]] = []
    for column in range(width):
        selected = next(
            (index for index in range(pivot_row, count) if values[index][column]),
            None,
        )
        if selected is None:
            continue
        values[pivot_row], values[selected] = values[selected], values[pivot_row]
        transforms[pivot_row], transforms[selected] = (
            transforms[selected],
            transforms[pivot_row],
        )
        scale = values[pivot_row][column]
        values[pivot_row] = [value / scale for value in values[pivot_row]]
        transforms[pivot_row] = [value / scale for value in transforms[pivot_row]]
        for row in range(count):
            if row == pivot_row or not values[row][column]:
                continue
            factor = values[row][column]
            values[row] = [
                value - factor * pivot
                for value, pivot in zip(values[row], values[pivot_row], strict=True)
            ]
            transforms[row] = [
                value - factor * pivot
                for value, pivot in zip(
                    transforms[row], transforms[pivot_row], strict=True
                )
            ]
        records.append(
            (tuple(values[pivot_row]), tuple(transforms[pivot_row]), column)
        )
        pivot_row += 1
        if pivot_row == count:
            break
    return tuple(records)


def relation_chart_residual(
    facts: Iterable[Atom],
    obligation_branches: Iterable[Iterable[Atom]],
) -> RelationChartResidual:
    """Reduce coherent typed branches in each exact representation chart."""

    fact_lifts = tuple(
        lift
        for atom in facts
        if (lift := lift_relation(atom)) is not None and lift.replayed
    )
    raw_branches = tuple(tuple(branch) for branch in obligation_branches)
    branch_records: list[ChartBranchResidual] = []
    for branch_index, branch in enumerate(raw_branches):
        atom_records: list[ChartAtomResidual] = []
        for atom in branch:
            target = lift_relation(atom)
            if target is None or not target.replayed:
                atom_records.append(
                    ChartAtomResidual(atom.canonical(), None, (), False, False)
                )
                continue
            generators = tuple(
                lift for lift in fact_lifts if lift.chart == target.chart
            )
            features = tuple(
                sorted(
                    {
                        feature
                        for lift in (*generators, target)
                        for feature, _value in lift.coefficients
                    }
                )
            )
            generator_rows = tuple(
                tuple(_vector(lift).get(feature, sp.Rational(0)) for feature in features)
                for lift in generators
            )
            residual = [
                _vector(target).get(feature, sp.Rational(0)) for feature in features
            ]
            combination = [sp.Rational(0) for _ in generators]
            for row, transform, pivot in _rref_rows(generator_rows):
                factor = residual[pivot]
                if not factor:
                    continue
                residual = [
                    value - factor * basis
                    for value, basis in zip(residual, row, strict=True)
                ]
                combination = [
                    value + factor * coefficient
                    for value, coefficient in zip(
                        combination, transform, strict=True
                    )
                ]
            replay = [
                _vector(target).get(feature, sp.Rational(0))
                - sum(
                    (
                        coefficient * _vector(generator).get(feature, sp.Rational(0))
                        for coefficient, generator in zip(
                            combination, generators, strict=True
                        )
                    ),
                    sp.Rational(0),
                )
                - residual[index]
                for index, feature in enumerate(features)
            ]
            remainder = _serialized(
                {
                    feature: residual[index]
                    for index, feature in enumerate(features)
                    if residual[index]
                }
            )
            atom_records.append(
                ChartAtomResidual(
                    atom=atom.canonical(),
                    chart=target.chart,
                    remainder=remainder,
                    proved=not remainder,
                    replayed=all(value == 0 for value in replay),
                )
            )
        atoms = tuple(atom_records)
        rank = (
            sum(not (item.proved and item.replayed) for item in atoms),
            sum(item.chart is None for item in atoms),
            sum(len(item.remainder) for item in atoms),
        )
        branch_records.append(ChartBranchResidual(branch_index, atoms, rank))
    branches = tuple(branch_records)
    if not branches:
        return RelationChartResidual((), None, (0, 0, 0))
    selected = min(branches, key=lambda item: (item.rank, item.branch_index))
    return RelationChartResidual(branches, selected.branch_index, selected.rank)


__all__ = [
    "AFFINE_CHART",
    "METRIC_CHART",
    "ChartAtomResidual",
    "ChartBranchResidual",
    "RelationChartEquivalence",
    "RelationChartLift",
    "RelationChartResidual",
    "certified_equivalent_relations",
    "certify_relation_equivalence",
    "equivalent_atoms",
    "lift_relation",
    "relation_chart_residual",
]
