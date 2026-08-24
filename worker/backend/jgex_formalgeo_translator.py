"""Translate a Newclid/JGEX construction DAG into executable FormalGeo GCL.

This is a structural translation of construction primitives.  It does not use
the expected proof, theorem sequence, problem identifier, or answer.  The
official FormalGeo runtime still checks every generated construction and its
numeric goal gate before backward decomposition starts.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from worker.backend.formalgeo_runtime_bridge import (
    FormalGeoElaboration,
    FormalGeoElaborationError,
    _LINE_SYMBOLS,
    _POINT_SYMBOLS,
    _formal_relation,
    _segment,
)
from worker.backend.geometry_proof_hypergraph import Atom


_CIRCLE_SYMBOLS = tuple("ΩΦΓΔΘΛΞΠΣΨ") + tuple("ωφγδθλξπσψ")


@dataclass(frozen=True)
class JGEXFormalGeoTranslation:
    elaboration: FormalGeoElaboration
    translated_clauses: int
    construction_kinds: tuple[str, ...]
    circle_to_object: tuple[tuple[str, str], ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "elaboration": self.elaboration.to_dict(),
            "translated_clauses": self.translated_clauses,
            "construction_kinds": list(self.construction_kinds),
            "circle_to_object": dict(self.circle_to_object),
        }


class _JGEXGCLBuilder:
    def __init__(self, point_names: Iterable[str]):
        points = tuple(sorted(set(point_names)))
        if len(points) > len(_POINT_SYMBOLS):
            raise FormalGeoElaborationError("too many JGEX points for FormalGeo GDL")
        self.point_map = {
            point: _POINT_SYMBOLS[index] for index, point in enumerate(points)
        }
        self.line_map: dict[tuple[str, str], str] = {}
        self.circle_map: dict[str, str] = {}
        self.circumcircle_map: dict[tuple[str, str, str], str] = {}
        self.constructed_points: set[str] = set()
        self.constructed_lines: set[tuple[str, str]] = set()
        self.constructions: list[str] = []
        self.kinds: list[str] = []

    def point(self, name: str) -> str:
        return self.point_map[name]

    def _allocate_line(self, segment: tuple[str, str]) -> str:
        if segment not in self.line_map:
            if len(self.line_map) >= len(_LINE_SYMBOLS):
                raise FormalGeoElaborationError("too many JGEX lines for FormalGeo GDL")
            self.line_map[segment] = _LINE_SYMBOLS[len(self.line_map)]
        return self.line_map[segment]

    def line_name(self, left: str, right: str) -> str:
        return self._allocate_line(_segment(left, right))

    def _allocate_circle(self, key: str) -> str:
        if key not in self.circle_map:
            if len(self.circle_map) >= len(_CIRCLE_SYMBOLS):
                raise FormalGeoElaborationError("too many circles for FormalGeo GDL")
            self.circle_map[key] = _CIRCLE_SYMBOLS[len(self.circle_map)]
        return self.circle_map[key]

    def add(self, kind: str, statement: str) -> None:
        self.kinds.append(kind)
        self.constructions.append(statement)

    def free_point(self, point: str, *, left_of: tuple[str, str] | None = None) -> None:
        if point in self.constructed_points:
            return
        obj = self.point(point)
        if left_of is None:
            constraint = f"FreePoint({obj})"
        else:
            constraint = (
                f"PointLeftSegment({obj},{self.point(left_of[0])},{self.point(left_of[1])})"
            )
        self.add("free_point", f"Point({obj}):{constraint}")
        self.constructed_points.add(point)

    def point_with_constraints(self, point: str, constraints: Iterable[str], kind: str) -> None:
        if point in self.constructed_points:
            raise FormalGeoElaborationError(f"JGEX point {point!r} was constructed twice")
        constraints = tuple(dict.fromkeys(constraints))
        if not constraints:
            self.free_point(point)
            return
        obj = self.point(point)
        self.add(kind, f"Point({obj}):" + "&".join(constraints))
        self.constructed_points.add(point)

    def ensure_line(self, left: str, right: str, *, extra: Iterable[str] = ()) -> str:
        segment = _segment(left, right)
        line = self._allocate_line(segment)
        extras = tuple(extra)
        if segment in self.constructed_lines:
            if extras:
                raise FormalGeoElaborationError(
                    f"cannot attach constraints after line {segment!r} exists"
                )
            return line
        if left not in self.constructed_points or right not in self.constructed_points:
            raise FormalGeoElaborationError(
                f"line {segment!r} depends on points that are not constructed"
            )
        constraints = (
            f"PointOnLine({self.point(left)},{line})",
            f"PointOnLine({self.point(right)},{line})",
            *extras,
        )
        self.add("secant_line", f"Line({line}):" + "&".join(constraints))
        self.constructed_lines.add(segment)
        return line

    def constrained_line(
        self,
        anchor: str,
        target: str,
        relation: str,
        *,
        kind: str,
    ) -> str:
        segment = _segment(anchor, target)
        line = self._allocate_line(segment)
        if segment in self.constructed_lines:
            raise FormalGeoElaborationError(f"constrained line {segment!r} already exists")
        if anchor not in self.constructed_points:
            raise FormalGeoElaborationError(f"line anchor {anchor!r} is not constructed")
        self.add(
            kind,
            f"Line({line}):PointOnLine({self.point(anchor)},{line})&{relation}",
        )
        self.constructed_lines.add(segment)
        return line

    def triangle(self, a: str, b: str, c: str) -> None:
        self.free_point(a)
        self.free_point(b)
        self.free_point(c, left_of=(a, b))
        ab = self.ensure_line(a, b)
        bc = self.ensure_line(b, c)
        ac_segment = _segment(a, c)
        ac = self._allocate_line(ac_segment)
        if ac_segment in self.constructed_lines:
            raise FormalGeoElaborationError("triangle closing line already exists")
        relation = (
            f"Triangle({self.point(a)},{ab},{self.point(b)},{bc},{self.point(c)},{ac})"
        )
        constraints = (
            f"PointOnLine({self.point(a)},{ac})",
            f"PointOnLine({self.point(c)},{ac})",
            relation,
        )
        self.add("triangle", f"Line({ac}):" + "&".join(constraints))
        self.constructed_lines.add(ac_segment)

    def triangle_signature(self, a: str, b: str, c: str) -> str:
        return ",".join(
            (
                self.point(a),
                self.line_name(a, b),
                self.point(b),
                self.line_name(b, c),
                self.point(c),
                self.line_name(a, c),
            )
        )

    def circumcircle(self, center: str, a: str, b: str, c: str) -> str:
        circle = self._allocate_circle(center)
        signature = self.triangle_signature(a, b, c)
        self.add(
            "circumcircle",
            f"Circle({circle}):CircumcircleOfTriangle({circle},{signature})",
        )
        self.point_with_constraints(
            center,
            (f"CenterOfCircle({self.point(center)},{circle})",),
            "circle_center",
        )
        self.circumcircle_map[tuple(sorted((a, b, c)))] = circle
        return circle

    def anonymous_circumcircle(self, a: str, b: str, c: str) -> str:
        key = tuple(sorted((a, b, c)))
        if key in self.circumcircle_map:
            return self.circumcircle_map[key]
        circle_key = "circum:" + ":".join(key)
        circle = self._allocate_circle(circle_key)
        signature = self.triangle_signature(a, b, c)
        self.add(
            "circumcircle",
            f"Circle({circle}):CircumcircleOfTriangle({circle},{signature})",
        )
        self.circumcircle_map[key] = circle
        return circle

    def incenter(self, center: str, a: str, b: str, c: str) -> None:
        signature = self.triangle_signature(a, b, c)
        self.point_with_constraints(
            center,
            (f"IncenterOfTriangle({self.point(center)},{signature})",),
            "incenter",
        )

    def _midpoint_constraints(self, x: str, a: str, b: str) -> tuple[str, str]:
        return (
            f"Eq(Sub(Mul(2,{self.point(x)}.x),Add({self.point(a)}.x,{self.point(b)}.x)))",
            f"Eq(Sub(Mul(2,{self.point(x)}.y),Add({self.point(a)}.y,{self.point(b)}.y)))",
        )

    def _mirror_constraints(self, x: str, a: str, b: str) -> tuple[str, str]:
        return (
            f"Eq(Sub({self.point(x)}.x,Sub(Mul(2,{self.point(b)}.x),{self.point(a)}.x)))",
            f"Eq(Sub({self.point(x)}.y,Sub(Mul(2,{self.point(b)}.y),{self.point(a)}.y)))",
        )

    def point_clause(self, target: str, construction_strings: Iterable[str]) -> None:
        constraints: list[str] = []
        kinds: list[str] = []
        for raw in construction_strings:
            tokens = raw.split()
            name, args = tokens[0], tokens[1:]
            kinds.append(name)
            if name == "free":
                continue
            if name == "on_line":
                _, a, b = args
                line = self.ensure_line(a, b)
                constraints.append(f"PointOnLine({self.point(target)},{line})")
            elif name == "on_circle":
                _, center, reference = args
                circle = self.circle_map.get(center)
                if circle is None:
                    raise FormalGeoElaborationError(f"unknown JGEX circle center {center!r}")
                constraints.extend(
                    (
                        f"PointOnCircle({self.point(target)},{circle})",
                        f"~SamePoint({self.point(target)},{self.point(reference)})",
                    )
                )
            elif name == "on_circum":
                _, a, b, c = args
                circle = self.anonymous_circumcircle(a, b, c)
                constraints.append(f"PointOnCircle({self.point(target)},{circle})")
            elif name == "circumcenter":
                _, a, b, c = args
                circle = self.anonymous_circumcircle(a, b, c)
                constraints.append(
                    f"CenterOfCircle({self.point(target)},{circle})"
                )
            elif name == "midpoint":
                _, a, b = args
                constraints.extend(self._midpoint_constraints(target, a, b))
            elif name == "mirror":
                _, a, b = args
                constraints.extend(self._mirror_constraints(target, a, b))
            elif name == "intersection_ll":
                _, a, b, c, d = args
                for left, right in ((a, b), (c, d)):
                    line = self.ensure_line(left, right)
                    constraints.append(f"PointOnLine({self.point(target)},{line})")
            elif name == "on_pline":
                _, anchor, b, c = args
                base = self.ensure_line(b, c)
                target_line = self.constrained_line(
                    anchor,
                    target,
                    f"ParallelBetweenLine({base},{self.line_name(anchor,target)})",
                    kind="parallel_line",
                )
                constraints.append(f"PointOnLine({self.point(target)},{target_line})")
            elif name == "on_tline":
                _, anchor, b, c = args
                base = self.ensure_line(b, c)
                target_line = self.constrained_line(
                    anchor,
                    target,
                    f"PerpendicularBetweenLine({base},{self.line_name(anchor,target)})",
                    kind="perpendicular_line",
                )
                constraints.append(f"PointOnLine({self.point(target)},{target_line})")
            elif name == "angle_bisector":
                _, left, vertex, right = args
                left_ray = self.ensure_line(vertex, left)
                right_ray = self.ensure_line(vertex, right)
                bisector_name = self.line_name(vertex, target)
                bisector = self.constrained_line(
                    vertex,
                    target,
                    "AngleBisector("
                    f"{self.point(vertex)},{bisector_name},{left_ray},{right_ray})",
                    kind="angle_bisector",
                )
                constraints.append(
                    f"PointOnLine({self.point(target)},{bisector})"
                )
            elif name == "on_aline":
                _, a, b, c, d, e = args
                ab = self.ensure_line(a, b)
                dc = self.ensure_line(d, c)
                de = self.ensure_line(d, e)
                target_line_name = self.line_name(a, target)
                target_line = self.constrained_line(
                    a,
                    target,
                    f"EqualAngle({target_line_name},{ab},{dc},{de})",
                    kind="equal_angle_line",
                )
                constraints.append(f"PointOnLine({self.point(target)},{target_line})")
            elif name == "on_aline0":
                _, a, b, c, d, e, f, g = args
                ab = self.ensure_line(a, b)
                cd = self.ensure_line(c, d)
                ef = self.ensure_line(e, f)
                target_line_name = self.line_name(g, target)
                target_line = self.constrained_line(
                    g,
                    target,
                    f"EqualAngle({ab},{cd},{ef},{target_line_name})",
                    kind="equal_angle_line",
                )
                constraints.append(f"PointOnLine({self.point(target)},{target_line})")
            elif name == "eqdistance":
                _, a, b, c = args
                constraints.append(
                    "EqualDistancePointToPoint("
                    f"{self.point(target)},{self.point(a)},{self.point(b)},{self.point(c)})"
                )
            elif name == "foot":
                _, a, b, c = args
                base = self.ensure_line(b, c)
                altitude_name = self.line_name(a, target)
                altitude = self.constrained_line(
                    a,
                    target,
                    f"PerpendicularBetweenLine({base},{altitude_name})",
                    kind="altitude",
                )
                constraints.extend(
                    (
                        f"PointOnLine({self.point(target)},{base})",
                        f"PointOnLine({self.point(target)},{altitude})",
                    )
                )
            else:
                raise FormalGeoElaborationError(f"unsupported JGEX construction: {raw}")
        self.point_with_constraints(target, constraints, "+".join(kinds) or "free")

    def clause(self, clause: Any) -> None:
        strings = tuple(item.string for item in clause.constructions)
        if not strings:
            raise FormalGeoElaborationError("empty JGEX clause")
        head = strings[0].split()
        if head[0] == "triangle":
            _, a, b, c = head
            self.triangle(a, b, c)
            return
        if head[0] == "segment":
            _, a, b = head
            self.free_point(a)
            self.free_point(b)
            self.ensure_line(a, b)
            return
        if head[0] == "circle":
            _, center, a, b, c = head
            self.circumcircle(center, a, b, c)
            return
        if head[0] == "incenter":
            _, center, a, b, c = head
            self.incenter(center, a, b, c)
            return
        if len(clause.points) != 1:
            raise FormalGeoElaborationError(
                f"unsupported multi-output JGEX clause: {clause}"
            )
        self.point_clause(clause.points[0], strings)


def translate_jgex_to_formalgeo(
    formulation: Any,
    goal: Atom,
    *,
    include_auxiliary_clauses: bool = False,
) -> JGEXFormalGeoTranslation:
    clauses = tuple(formulation.setup_clauses)
    if include_auxiliary_clauses:
        clauses = (*clauses, *tuple(formulation.auxiliary_clauses))
    point_names = set(goal.arguments)
    for clause in clauses:
        point_names.update(clause.points)
        for construction in clause.constructions:
            point_names.update(construction.string.split()[1:])
    builder = _JGEXGCLBuilder(point_names)
    for clause in clauses:
        builder.clause(clause)

    normalized_goal = goal.canonical()
    for point in normalized_goal.arguments:
        if point not in builder.constructed_points:
            raise FormalGeoElaborationError(
                f"goal point {point!r} is absent from the JGEX construction DAG"
            )
    for index in range(0, len(normalized_goal.arguments), 2):
        if normalized_goal.predicate in {"para", "perp"}:
            builder.ensure_line(
                normalized_goal.arguments[index], normalized_goal.arguments[index + 1]
            )
        elif normalized_goal.predicate == "eqangle":
            builder.ensure_line(
                normalized_goal.arguments[index], normalized_goal.arguments[index + 1]
            )
    formal_goal = _formal_relation(
        normalized_goal, builder.point_map, builder.line_map
    )
    elaboration = FormalGeoElaboration(
        facts=(),
        goal=normalized_goal,
        constructions=tuple(builder.constructions),
        formal_goal=formal_goal,
        point_to_object=tuple(sorted(builder.point_map.items())),
        segment_to_object=tuple(sorted(builder.line_map.items())),
    )
    return JGEXFormalGeoTranslation(
        elaboration=elaboration,
        translated_clauses=len(clauses),
        construction_kinds=tuple(builder.kinds),
        circle_to_object=tuple(sorted(builder.circle_map.items())),
    )


__all__ = ["JGEXFormalGeoTranslation", "translate_jgex_to_formalgeo"]
