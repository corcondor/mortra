"""Deterministic natural-language/TeX to AlphaGeometry2 formalization.

This is intentionally a finite mathematical grammar, not a general prose
translator.  It produces a typed predicate IR, constructs a numerical witness
by constrained optimization, and emits an AG2 statement only when every
mathematical relation in the supported input has been consumed.
"""

from __future__ import annotations

import hashlib
import itertools
import re
from dataclasses import asdict, dataclass
from fractions import Fraction
from typing import Any, Iterable

import numpy as np
from scipy.optimize import least_squares


RELATION_SYMBOLS = (
    "perp", "para", "cong", "coll", "cyclic", "eqangle",
    "rconst", "eqratio", "s_angle", "distseq",
)
QUERY_MARKERS_JA = ("を示せ", "を証明せよ", "を証明しなさい", "ことを示せ", "ことを証明せよ")
QUERY_MARKERS_EN = ("prove that", "show that", "prove", "show")


@dataclass(frozen=True)
class TypedPredicate:
    name: str
    points: tuple[str, ...]
    source: str
    constants: tuple[str, ...] = ()

    def render(self) -> str:
        return " ".join((self.name, *self.points, *self.constants))


@dataclass
class GeometryFormalization:
    status: str
    normalized_text: str
    points: list[str]
    predicates: list[TypedPredicate]
    goal: TypedPredicate | None
    triangles: list[tuple[str, str, str]]
    unresolved_relations: list[str]
    coordinates: dict[str, tuple[float, float]]
    diagram_residual: float | None
    restarts: int
    formal_problem: str | None
    discourse_objects: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["predicates"] = [asdict(item) for item in self.predicates]
        value["goal"] = asdict(self.goal) if self.goal else None
        return value


def formalize_geometry_text(text: str, *, max_restarts: int = 20) -> GeometryFormalization:
    normalized = normalize_text(text)
    premise_text, goal_text = split_goal(normalized)
    from geometry_discourse import elaborate_circle_discourse

    discourse = elaborate_circle_discourse(premise_text, goal_text)
    premise_text, goal_text = discourse.premise_text, discourse.goal_text
    triangles = extract_triangles(normalized)
    predicates, premise_spans = extract_predicates(premise_text)
    goals, goal_spans = extract_predicates(goal_text)
    predicates.extend(
        TypedPredicate(item.name, item.points, item.source)
        for item in discourse.premise_relations
    )
    goals.extend(
        TypedPredicate(item.name, item.points, item.source)
        for item in discourse.goal_relations
    )
    predicates = expand_derived_predicates(predicates, triangles)
    goal = goals[0] if len(goals) == 1 else None
    unresolved = unresolved_relation_fragments(premise_text, premise_spans)
    unresolved.extend(unresolved_relation_fragments(goal_text, goal_spans))
    unresolved.extend(discourse.unresolved)
    unsupported = sorted({item.name for item in [*predicates, *goals] if item.name not in RELATION_SYMBOLS})
    unresolved.extend(f"unsupported typed predicate: {name}" for name in unsupported)
    for item in [*predicates, *goals]:
        issue = predicate_type_issue(item)
        if issue:
            unresolved.append(f"ill-typed predicate {item.render()}: {issue}")
    if len(goals) != 1:
        unresolved.append(f"expected exactly one goal predicate, found {len(goals)}")

    points = sorted({point for item in [*predicates, *goals] for point in item.points} | {
        point for triangle in triangles for point in triangle
    })
    if len(points) < 2:
        unresolved.append("fewer than two geometric points were identified")

    result = GeometryFormalization(
        status="unresolved" if unresolved else "parsed",
        normalized_text=normalized,
        points=points,
        predicates=deduplicate_predicates(predicates),
        goal=goal,
        triangles=triangles,
        unresolved_relations=unresolved,
        coordinates={},
        diagram_residual=None,
        restarts=0,
        formal_problem=None,
        discourse_objects=[item.to_dict() for item in discourse.circles],
    )
    if unresolved or goal is None:
        return result

    coordinates, residual, restarts = construct_diagram(
        points,
        [*result.predicates, goal],
        triangles,
        seed_text=normalized,
        max_restarts=max_restarts,
    )
    result.coordinates = coordinates
    result.diagram_residual = residual
    result.restarts = restarts
    if not coordinates:
        result.status = "diagram_failed"
        result.unresolved_relations.append("typed constraints did not yield a nondegenerate numerical diagram")
        return result
    result.formal_problem = render_formal_problem(points, coordinates, result.predicates, goal)
    result.status = "formalized"
    return result


def normalize_text(text: str) -> str:
    value = text.replace("\r", " ").replace("\n", " ")
    value = re.sub(r"\\text\s*\{([^{}]*)\}", r"\1", value)
    value = re.sub(r"\\frac\s*\{\s*(-?\d+)\s*\}\s*\{\s*(\d+)\s*\}", r"\1/\2", value)
    replacements = {
        "\\perp": "⊥",
        "\\parallel": "∥",
        "\\angle": "∠",
        "^\\circ": "°",
        "\\circ": "°",
        "\\Gamma": "Γ",
        "\\Omega": "Ω",
        "\\gamma": "γ",
        "\\omega": "ω",
        "$": "",
        "（": "(",
        "）": ")",
        "，": ",",
        "；": ";",
        "：": ":",
        "＝": "=",
        "−": "-",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    value = re.sub(r"\s+", " ", value).strip()
    return value


def split_goal(text: str) -> tuple[str, str]:
    if "?" in text:
        return tuple(part.strip() for part in text.rsplit("?", 1))  # type: ignore[return-value]
    lowered = text.lower()
    for marker in QUERY_MARKERS_EN:
        index = lowered.rfind(marker)
        if index >= 0:
            return text[:index].strip(" ,.;。"), text[index + len(marker):].strip(" ,.;。")
    for marker in QUERY_MARKERS_JA:
        index = text.rfind(marker)
        if index < 0:
            continue
        before = text[:index].rstrip()
        boundary = max(before.rfind("。"), before.rfind(";"), before.rfind("."))
        if boundary >= 0:
            return before[:boundary].strip(), before[boundary + 1:].strip(" ,、")
        comma = max(before.rfind("、"), before.rfind(","))
        if comma >= 0:
            return before[:comma].strip(), before[comma + 1:].strip()
        return "", before.strip()
    return text, ""


def extract_triangles(text: str) -> list[tuple[str, str, str]]:
    patterns = (
        r"(?:三角形|△)\s*([A-Z])([A-Z])([A-Z])",
        r"triangle\s+([A-Z])([A-Z])([A-Z])",
    )
    found: list[tuple[str, str, str]] = []
    for pattern in patterns:
        found.extend(tuple(match.groups()) for match in re.finditer(pattern, text, re.IGNORECASE))
    return list(dict.fromkeys(tuple(point.lower() for point in triangle) for triangle in found))


def extract_predicates(text: str) -> tuple[list[TypedPredicate], list[tuple[int, int]]]:
    predicates: list[TypedPredicate] = []
    spans: list[tuple[int, int]] = []

    def collect(pattern: str, builder) -> None:
        for match in re.finditer(pattern, text):
            if any(match.start() < end and start < match.end() for start, end in spans):
                continue
            value = builder(match)
            if isinstance(value, list):
                predicates.extend(value)
            else:
                predicates.append(value)
            spans.append(match.span())

    segment = r"([A-Z])\s*([A-Z])"
    scalar = r"(-?\d+(?:/\d+|\.\d+)?)"
    collect(
        segment + r"\s*:\s*" + segment + r"\s*=\s*" + segment + r"\s*:\s*" + segment,
        lambda m: TypedPredicate("eqratio", tuple(value.lower() for value in m.groups()), m.group(0)),
    )
    collect(
        segment + r"\s*/\s*" + segment + r"\s*=\s*" + scalar,
        lambda m: TypedPredicate(
            "rconst",
            tuple(value.lower() for value in m.groups()[:4]),
            m.group(0),
            (normalize_constant(m.group(5)),),
        ),
    )
    collect(
        r"∠\s*([A-Z])([A-Z])([A-Z])\s*=\s*" + scalar + r"\s*°?",
        lambda m: constant_angle_predicate(m.groups(), m.group(0)),
    )
    collect(r"∠\s*([A-Z])([A-Z])([A-Z])\s*=\s*∠\s*([A-Z])([A-Z])([A-Z])",
            lambda m: angle_predicate(m.groups(), m.group(0)))
    collect(segment + r"\s*(?:⊥|is\s+perpendicular\s+to)\s*" + segment,
            lambda m: predicate("perp", m.groups(), m.group(0)))
    collect(segment + r"\s*(?:∥|//|is\s+parallel\s+to)\s*" + segment,
            lambda m: predicate("para", m.groups(), m.group(0)))
    collect(segment + r"\s*=\s*" + segment,
            lambda m: predicate("cong", m.groups(), m.group(0)))

    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:直線|line)\s*([A-Z])([A-Z])(?:\s*(?:上にある|上|on))",
        lambda m: TypedPredicate("coll", (m.group(2).lower(), m.group(1).lower(), m.group(3).lower()), m.group(0)),
    )
    collect(
        r"([A-Z])\s+(?:lies|is)\s+on\s+(?:the\s+)?line\s+([A-Z])([A-Z])",
        lambda m: TypedPredicate("coll", (m.group(2).lower(), m.group(1).lower(), m.group(3).lower()), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:線分|segment)\s*([A-Z])([A-Z])(?:\s*(?:上|上にある|on))",
        lambda m: TypedPredicate("coll", (m.group(2).lower(), m.group(1).lower(), m.group(3).lower()), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:円|circle)\s*([A-Z])([A-Z])([A-Z])(?:\s*(?:上にある|上|on))",
        lambda m: TypedPredicate(
            "cyclic",
            (m.group(2).lower(), m.group(3).lower(), m.group(4).lower(), m.group(1).lower()),
            m.group(0),
        ),
    )
    collect(
        r"([A-Z])\s+(?:lies|is)\s+on\s+(?:the\s+)?circle\s+through\s+([A-Z])\s*[, ]\s*([A-Z])\s*(?:and|[, ])\s*([A-Z])",
        lambda m: TypedPredicate(
            "cyclic",
            (m.group(2).lower(), m.group(3).lower(), m.group(4).lower(), m.group(1).lower()),
            m.group(0),
        ),
    )
    collect(
        r"([A-Z])\s*(?:は)?\s*([A-Z])\s*[,、]\s*([A-Z])\s*[,、]\s*([A-Z])\s*(?:を通る円|の定める円)(?:周)?上にある",
        lambda m: TypedPredicate(
            "cyclic",
            (m.group(2).lower(), m.group(3).lower(), m.group(4).lower(), m.group(1).lower()),
            m.group(0),
        ),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:直線\s*)?([A-Z])([A-Z])\s*(?:と|and)\s*(?:直線\s*)?([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:交点|intersection)",
        lambda m: intersection_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+intersection\s+of\s+(?:lines?\s+)?([A-Z])([A-Z])\s+and\s+([A-Z])([A-Z])",
        lambda m: intersection_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"(?:直線|line)\s*([A-Z])([A-Z])\s*(?:は|is)?\s*(?:点\s*)?([A-Z])(?:\s*で|\s+at)\s*(?:中心\s*)?([A-Z])(?:\s*の|[- ]centered)?\s*(?:円|circle)(?:\s*に|\s+is)?\s*(?:接する|tangent)",
        lambda m: tangent_predicate(m.groups(), m.group(0)),
    )

    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:線分\s*)?([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:中点|midpoint)",
        lambda m: midpoint_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+midpoint\s+of\s+([A-Z])([A-Z])",
        lambda m: midpoint_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:三角形\s*)?([A-Z])([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:外心|circumcenter)",
        lambda m: circumcenter_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+circumcenter\s+of\s+(?:triangle\s+)?([A-Z])([A-Z])([A-Z])",
        lambda m: circumcenter_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:三角形\s*)?([A-Z])([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:重心|centroid)",
        lambda m: centroid_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+centroid\s+of\s+(?:triangle\s+)?([A-Z])([A-Z])([A-Z])",
        lambda m: centroid_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:三角形\s*)?([A-Z])([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:垂心|orthocenter)",
        lambda m: orthocenter_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+orthocenter\s+of\s+(?:triangle\s+)?([A-Z])([A-Z])([A-Z])",
        lambda m: orthocenter_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s*(?:は|is)\s*(?:三角形\s*)?([A-Z])([A-Z])([A-Z])(?:\s*(?:の|the))?\s*(?:内心|incenter)",
        lambda m: incenter_predicates(m.groups(), m.group(0)),
    )
    collect(
        r"([A-Z])\s+is\s+the\s+incenter\s+of\s+(?:triangle\s+)?([A-Z])([A-Z])([A-Z])",
        lambda m: incenter_predicates(m.groups(), m.group(0)),
    )

    for match in re.finditer(r"([A-Z](?:\s*[,、]\s*[A-Z]){2,})\s*(?:は|are)?\s*(?:一直線上|collinear)", text):
        names = tuple(point.lower() for point in re.findall(r"[A-Z]", match.group(1)))
        for triple in itertools.combinations(names, 3):
            predicates.append(TypedPredicate("coll", triple, match.group(0)))
        spans.append(match.span())
    for match in re.finditer(r"([A-Z](?:\s*[,、]\s*[A-Z]){3,})\s*(?:は|are)?\s*(?:同一円周上|concyclic|cyclic)", text):
        names = tuple(point.lower() for point in re.findall(r"[A-Z]", match.group(1)))
        for quadruple in itertools.combinations(names, 4):
            predicates.append(TypedPredicate("cyclic", quadruple, match.group(0)))
        spans.append(match.span())
    return predicates, merge_spans(spans)


def predicate(name: str, groups: Iterable[str], source: str) -> TypedPredicate:
    return TypedPredicate(name, tuple(value.lower() for value in groups), source)


def angle_predicate(groups: Iterable[str], source: str) -> TypedPredicate:
    a, b, c, d, e, f = (value.lower() for value in groups)
    return TypedPredicate("eqangle", (b, a, b, c, e, d, e, f), source)


def constant_angle_predicate(groups: Iterable[str], source: str) -> TypedPredicate:
    a, b, c, value = groups
    return TypedPredicate(
        "s_angle",
        (b.lower(), a.lower(), b.lower(), c.lower()),
        source,
        (normalize_constant(value),),
    )


def midpoint_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    midpoint, a, b = (value.lower() for value in groups)
    return [
        TypedPredicate("coll", (a, midpoint, b), source),
        TypedPredicate("cong", (a, midpoint, midpoint, b), source),
    ]


def circumcenter_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    center, a, b, c = (value.lower() for value in groups)
    return [
        TypedPredicate("cong", (center, a, center, b), source),
        TypedPredicate("cong", (center, b, center, c), source),
    ]


def centroid_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    center, a, b, c = (value.lower() for value in groups)
    # Affine centroid is encoded as two additive vector equations during diagram
    # construction. AG2 has no primitive centroid predicate, so do not emit an
    # unsound DDAR premise here.
    return [TypedPredicate("centroid", (center, a, b, c), source)]


def intersection_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    point, a, b, c, d = (value.lower() for value in groups)
    return [
        TypedPredicate("coll", (a, point, b), source),
        TypedPredicate("coll", (c, point, d), source),
    ]


def tangent_predicate(groups: Iterable[str], source: str) -> TypedPredicate:
    a, b, contact, center = (value.lower() for value in groups)
    return TypedPredicate("perp", (a, b, center, contact), source)


def orthocenter_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    center, a, b, c = (value.lower() for value in groups)
    return [
        TypedPredicate("perp", (a, center, b, c), source),
        TypedPredicate("perp", (b, center, a, c), source),
    ]


def incenter_predicates(groups: Iterable[str], source: str) -> list[TypedPredicate]:
    center, a, b, c = (value.lower() for value in groups)
    return [
        TypedPredicate("eqangle", (a, b, a, center, a, center, a, c), source),
        TypedPredicate("eqangle", (b, c, b, center, b, center, b, a), source),
    ]


def expand_derived_predicates(
    predicates: list[TypedPredicate],
    triangles: list[tuple[str, str, str]],
) -> list[TypedPredicate]:
    existing = {point for predicate_item in predicates for point in predicate_item.points}
    existing.update(point for triangle in triangles for point in triangle)
    expanded: list[TypedPredicate] = []
    for item in predicates:
        if item.name != "centroid":
            expanded.append(item)
            continue
        center, a, b, c = item.points
        midpoint = unused_point_name(existing, f"{center}_mid_{b}{c}")
        existing.add(midpoint)
        expanded.extend((
            TypedPredicate("coll", (b, midpoint, c), item.source),
            TypedPredicate("cong", (b, midpoint, midpoint, c), item.source),
            TypedPredicate("coll", (a, center, midpoint), item.source),
            TypedPredicate("rconst", (a, center, center, midpoint), item.source, ("2",)),
            TypedPredicate("distseq", (a, center, center, midpoint, a, midpoint), item.source, ("1", "1", "-1")),
        ))
    return expanded


def unused_point_name(existing: set[str], seed: str) -> str:
    if seed not in existing:
        return seed
    ordinal = 2
    while f"{seed}_{ordinal}" in existing:
        ordinal += 1
    return f"{seed}_{ordinal}"


def normalize_constant(value: str) -> str:
    fraction = Fraction(value)
    return str(fraction.numerator) if fraction.denominator == 1 else f"{fraction.numerator}/{fraction.denominator}"


def predicate_type_issue(item: TypedPredicate) -> str | None:
    arities = {
        "coll": (3, 0), "cyclic": (4, 0), "perp": (4, 0), "para": (4, 0),
        "cong": (4, 0), "eqangle": (8, 0), "rconst": (4, 1),
        "eqratio": (8, 0), "s_angle": (4, 1), "distseq": (6, 3),
    }
    expected = arities.get(item.name)
    if expected is None:
        return None
    if (len(item.points), len(item.constants)) != expected:
        return f"expected {expected[0]} points and {expected[1]} constants"
    if item.name == "coll" and len(set(item.points)) < 3:
        return "collinearity requires three distinct points"
    if item.name == "cyclic" and len(set(item.points)) < 4:
        return "cyclicity requires four distinct points"
    if item.name in {"perp", "para", "cong", "eqangle", "rconst", "eqratio", "s_angle", "distseq"}:
        for index in range(0, len(item.points), 2):
            if item.points[index] == item.points[index + 1]:
                return "a directed segment has identical endpoints"
    return None


def unresolved_relation_fragments(text: str, consumed: list[tuple[int, int]]) -> list[str]:
    remainder = list(text)
    for start, end in consumed:
        remainder[start:end] = " " * (end - start)
    value = "".join(remainder)
    markers = (
        "⊥", "∥", "//", "∠", "=", "比", "円", "中点", "外心", "重心", "垂心", "内心", "傍心",
        "一直線", "同一円周", "交点", "接する", "上にある", "perpendicular", "parallel",
        "midpoint", "circumcenter", "centroid", "orthocenter", "incenter", "excenter", "intersection",
        "tangent", "collinear", "cyclic",
    )
    return [marker for marker in markers if marker.lower() in value.lower()]


def deduplicate_predicates(predicates: list[TypedPredicate]) -> list[TypedPredicate]:
    result: list[TypedPredicate] = []
    seen: set[tuple[str, tuple[str, ...], tuple[str, ...]]] = set()
    for item in predicates:
        key = (item.name, item.points, item.constants)
        if key not in seen:
            seen.add(key)
            result.append(item)
    return result


def merge_spans(spans: list[tuple[int, int]]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for start, end in sorted(spans):
        if result and start <= result[-1][1]:
            result[-1] = (result[-1][0], max(result[-1][1], end))
        else:
            result.append((start, end))
    return result


def construct_diagram(
    points: list[str],
    constraints: list[TypedPredicate],
    triangles: list[tuple[str, str, str]],
    *,
    seed_text: str,
    max_restarts: int,
) -> tuple[dict[str, tuple[float, float]], float | None, int]:
    if len(points) < 2:
        return {}, None, 0
    seed = int(hashlib.sha256(seed_text.encode("utf-8")).hexdigest()[:16], 16)
    rng = np.random.default_rng(seed)
    best: tuple[float, np.ndarray] | None = None

    def unpack(vector: np.ndarray) -> dict[str, np.ndarray]:
        coordinates = {points[0]: np.asarray([0.0, 0.0]), points[1]: np.asarray([4.0, 0.0])}
        for offset, name in enumerate(points[2:]):
            coordinates[name] = vector[2 * offset:2 * offset + 2]
        return coordinates

    def residuals(vector: np.ndarray) -> np.ndarray:
        coordinates = unpack(vector)
        values = [predicate_residual(item, coordinates) for item in constraints]
        for a, b, c in triangles:
            if all(name in coordinates for name in (a, b, c)):
                area = abs(cross2d(coordinates[b] - coordinates[a], coordinates[c] - coordinates[a]))
                values.append(max(0.0, 0.8 - area))
        for left, right in itertools.combinations(points, 2):
            if any(item.name == "overlap" and {left, right} == set(item.points) for item in constraints):
                continue
            distance = float(np.linalg.norm(coordinates[left] - coordinates[right]))
            values.append(max(0.0, 0.12 - distance))
        return np.asarray(values, dtype=float)

    variable_count = max(0, 2 * (len(points) - 2))
    for restart in range(1, max_restarts + 1):
        initial = rng.normal(0.0, 2.5, size=variable_count)
        solved = least_squares(residuals, initial, max_nfev=3000, ftol=1e-13, xtol=1e-13, gtol=1e-13)
        if residuals(solved.x).size >= variable_count and variable_count:
            solved = least_squares(
                residuals,
                solved.x,
                method="lm",
                max_nfev=10000,
                ftol=1e-15,
                xtol=1e-15,
                gtol=1e-15,
            )
        error = float(np.max(np.abs(residuals(solved.x)))) if residuals(solved.x).size else 0.0
        if best is None or error < best[0]:
            best = (error, solved.x.copy())
        if error <= 1e-14:
            coordinates = unpack(solved.x)
            return {name: (float(value[0]), float(value[1])) for name, value in coordinates.items()}, error, restart
    if best is None or best[0] > 5e-14:
        return {}, best[0] if best else None, max_restarts
    coordinates = unpack(best[1])
    return {name: (float(value[0]), float(value[1])) for name, value in coordinates.items()}, best[0], max_restarts


def predicate_residual(item: TypedPredicate, coordinates: dict[str, np.ndarray]) -> float:
    p = [coordinates[name] for name in item.points]
    if item.name == "coll":
        return cross2d(p[1] - p[0], p[2] - p[0]) / 16.0
    if item.name == "para":
        return cross2d(p[1] - p[0], p[3] - p[2]) / 16.0
    if item.name == "perp":
        return float((p[1] - p[0]) @ (p[3] - p[2])) / 16.0
    if item.name == "cong":
        return (squared_distance(p[0], p[1]) - squared_distance(p[2], p[3])) / 16.0
    if item.name == "eqangle":
        u, v = p[1] - p[0], p[3] - p[2]
        w, z = p[5] - p[4], p[7] - p[6]
        return (cross2d(u, v) * float(w @ z) - float(u @ v) * cross2d(w, z)) / 256.0
    if item.name == "cyclic":
        matrix = np.asarray([[point[0], point[1], point @ point, 1.0] for point in p])
        return float(np.linalg.det(matrix)) / 256.0
    if item.name == "rconst":
        ratio = float(Fraction(item.constants[0]))
        return (squared_distance(p[0], p[1]) - ratio * ratio * squared_distance(p[2], p[3])) / 16.0
    if item.name == "eqratio":
        left_num = squared_distance(p[0], p[1])
        left_den = squared_distance(p[2], p[3])
        right_num = squared_distance(p[4], p[5])
        right_den = squared_distance(p[6], p[7])
        return (left_num * right_den - right_num * left_den) / 256.0
    if item.name == "s_angle":
        angle = np.deg2rad(float(Fraction(item.constants[0])))
        u, v = p[1] - p[0], p[3] - p[2]
        # DDAR encodes dir(u) - dir(v) = angle, modulo 180 degrees.
        return (cross2d(u, v) * np.cos(angle) + float(u @ v) * np.sin(angle)) / 16.0
    if item.name == "distseq":
        return sum(
            float(Fraction(coef)) * float(np.linalg.norm(p[2 * index] - p[2 * index + 1]))
            for index, coef in enumerate(item.constants)
        ) / 4.0
    if item.name == "centroid":
        center, a, b, c = p
        delta = center - (a + b + c) / 3
        return float(np.linalg.norm(delta))
    raise ValueError(f"unsupported numerical predicate: {item.name}")


def squared_distance(a: np.ndarray, b: np.ndarray) -> float:
    delta = a - b
    return float(delta @ delta)


def cross2d(a: np.ndarray, b: np.ndarray) -> float:
    return float(a[0] * b[1] - a[1] * b[0])


def render_formal_problem(
    points: list[str],
    coordinates: dict[str, tuple[float, float]],
    predicates: list[TypedPredicate],
    goal: TypedPredicate,
) -> str:
    declarations = []
    executable = [item for item in predicates if item.name in RELATION_SYMBOLS]
    for index, name in enumerate(points):
        x, y = coordinates[name]
        suffix = ", ".join(item.render() for item in executable) if index == len(points) - 1 else ""
        declarations.append(f"{name}@{format_number(x)}_{format_number(y)} = {suffix}")
    return "; ".join(declarations) + " ? " + goal.render()


def format_number(value: float) -> str:
    if abs(value) < 1e-12:
        value = 0.0
    return f"{value:.17g}"
