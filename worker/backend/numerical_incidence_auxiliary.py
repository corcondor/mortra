"""Numerical incidence heuristics for symbolic auxiliary constructions.

The numeric plane is a proposal oracle only.  It never accepts a theorem;
every selected construction must still be replayed by the native prover.
"""

from __future__ import annotations

from dataclasses import dataclass
from itertools import combinations
import math
from typing import Mapping, Sequence


Point = tuple[float, float]
LocusKey = tuple[float, ...]


def _canonical_sign(values: tuple[float, ...]) -> tuple[float, ...]:
    for value in values:
        if abs(value) <= 1e-14:
            continue
        if value < 0:
            return tuple(-item for item in values)
        break
    return values


def _line_coefficients(left: Point, right: Point) -> tuple[float, float, float] | None:
    a = left[1] - right[1]
    b = right[0] - left[0]
    norm = math.hypot(a, b)
    if norm <= 1e-12:
        return None
    c = left[0] * right[1] - right[0] * left[1]
    return _canonical_sign((a / norm, b / norm, c / norm))


def _circle_coefficients(
    first: Point,
    second: Point,
    third: Point,
) -> tuple[float, float, float] | None:
    x1, y1 = first
    x2, y2 = second
    x3, y3 = third
    determinant = 2.0 * (
        x1 * (y2 - y3) + x2 * (y3 - y1) + x3 * (y1 - y2)
    )
    if abs(determinant) <= 1e-12:
        return None
    x1s = x1 * x1 + y1 * y1
    x2s = x2 * x2 + y2 * y2
    x3s = x3 * x3 + y3 * y3
    center_x = (
        x1s * (y2 - y3) + x2s * (y3 - y1) + x3s * (y1 - y2)
    ) / determinant
    center_y = (
        x1s * (x3 - x2) + x2s * (x1 - x3) + x3s * (x2 - x1)
    ) / determinant
    d = -2.0 * center_x
    e = -2.0 * center_y
    f = center_x * center_x + center_y * center_y - x1s
    return d, e, f


def _center_point_circle(center: Point, point: Point) -> tuple[float, float, float] | None:
    radius2 = (point[0] - center[0]) ** 2 + (point[1] - center[1]) ** 2
    if radius2 <= 1e-18:
        return None
    d = -2.0 * center[0]
    e = -2.0 * center[1]
    f = center[0] * center[0] + center[1] * center[1] - radius2
    return d, e, f


def _key(values: Sequence[float], digits: int) -> LocusKey:
    return tuple(round(float(value), digits) for value in values)


def _line_residual(coefficients: Sequence[float], point: Point) -> float:
    a, b, c = coefficients
    return abs(a * point[0] + b * point[1] + c)


def _circle_residual(coefficients: Sequence[float], point: Point) -> float:
    d, e, f = coefficients
    value = point[0] ** 2 + point[1] ** 2 + d * point[0] + e * point[1] + f
    scale = max(
        1.0,
        point[0] ** 2 + point[1] ** 2,
        abs(d * point[0]),
        abs(e * point[1]),
        abs(f),
    )
    return abs(value) / scale


@dataclass(frozen=True)
class NumericalLocus:
    coefficients: LocusKey
    support: tuple[str, ...]


@dataclass(frozen=True)
class NumericalIncidenceProfile:
    family: str
    coincident_points: tuple[str, ...]
    incident_lines: tuple[NumericalLocus, ...]
    incident_circles: tuple[NumericalLocus, ...]
    nontrivial_lines: tuple[NumericalLocus, ...]
    nontrivial_circles: tuple[NumericalLocus, ...]
    heuristic_categories: tuple[str, ...]

    @property
    def is_heuristic_candidate(self) -> bool:
        return bool(self.heuristic_categories)

    @property
    def rank(self) -> tuple[int, ...]:
        return (
            0 if self.is_heuristic_candidate else 1,
            -len(self.heuristic_categories),
            -(len(self.nontrivial_lines) + len(self.nontrivial_circles)),
            -len(self.nontrivial_lines),
            -len(self.nontrivial_circles),
            -len(self.coincident_points),
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "family": self.family,
            "coincident_points": list(self.coincident_points),
            "incident_line_count": len(self.incident_lines),
            "incident_circle_count": len(self.incident_circles),
            "nontrivial_line_count": len(self.nontrivial_lines),
            "nontrivial_circle_count": len(self.nontrivial_circles),
            "heuristic_categories": list(self.heuristic_categories),
            "is_heuristic_candidate": self.is_heuristic_candidate,
            "rank": list(self.rank),
        }


@dataclass(frozen=True)
class NumericalIncidenceAtlas:
    coordinates: Mapping[str, Point]
    normalized_coordinates: Mapping[str, Point]
    center: Point
    scale: float
    lines: tuple[NumericalLocus, ...]
    circles: tuple[NumericalLocus, ...]
    tolerance: float = 1e-7
    digits: int = 8

    @classmethod
    def build(
        cls,
        coordinates: Mapping[str, Point],
        *,
        tolerance: float = 1e-7,
        digits: int = 8,
    ) -> "NumericalIncidenceAtlas":
        finite = {
            str(name): (float(point[0]), float(point[1]))
            for name, point in coordinates.items()
            if math.isfinite(float(point[0])) and math.isfinite(float(point[1]))
        }
        if not finite:
            return cls({}, {}, (0.0, 0.0), 1.0, (), (), tolerance, digits)
        center = (
            sum(point[0] for point in finite.values()) / len(finite),
            sum(point[1] for point in finite.values()) / len(finite),
        )
        scale = max(
            (
                math.hypot(point[0] - center[0], point[1] - center[1])
                for point in finite.values()
            ),
            default=1.0,
        )
        scale = max(scale, 1e-12)
        normalized = {
            name: (
                (point[0] - center[0]) / scale,
                (point[1] - center[1]) / scale,
            )
            for name, point in finite.items()
        }

        line_support: dict[LocusKey, set[str]] = {}
        names = tuple(sorted(normalized))
        for left_name, right_name in combinations(names, 2):
            coefficients = _line_coefficients(
                normalized[left_name], normalized[right_name]
            )
            if coefficients is None:
                continue
            line_support.setdefault(_key(coefficients, digits), set()).update(
                (left_name, right_name)
            )

        circle_support: dict[LocusKey, set[str]] = {}
        for first_name, second_name, third_name in combinations(names, 3):
            coefficients = _circle_coefficients(
                normalized[first_name],
                normalized[second_name],
                normalized[third_name],
            )
            if coefficients is None:
                continue
            circle_support.setdefault(_key(coefficients, digits), set()).update(
                (first_name, second_name, third_name)
            )

        lines = tuple(
            NumericalLocus(coefficients, tuple(sorted(support)))
            for coefficients, support in sorted(line_support.items())
        )
        circles = tuple(
            NumericalLocus(coefficients, tuple(sorted(support)))
            for coefficients, support in sorted(circle_support.items())
        )
        return cls(
            finite,
            normalized,
            center,
            scale,
            lines,
            circles,
            tolerance,
            digits,
        )

    def normalize(self, point: Point) -> Point:
        return (
            (float(point[0]) - self.center[0]) / self.scale,
            (float(point[1]) - self.center[1]) / self.scale,
        )

    def line_key(self, left: str, right: str) -> LocusKey | None:
        if left not in self.normalized_coordinates or right not in self.normalized_coordinates:
            return None
        coefficients = _line_coefficients(
            self.normalized_coordinates[left], self.normalized_coordinates[right]
        )
        return None if coefficients is None else _key(coefficients, self.digits)

    def center_point_circle_key(self, center: str, point: str) -> LocusKey | None:
        if center not in self.normalized_coordinates or point not in self.normalized_coordinates:
            return None
        coefficients = _center_point_circle(
            self.normalized_coordinates[center], self.normalized_coordinates[point]
        )
        return None if coefficients is None else _key(coefficients, self.digits)

    def circumcircle_key(self, points: Sequence[str]) -> LocusKey | None:
        if len(points) < 3 or any(
            point not in self.normalized_coordinates for point in points[:3]
        ):
            return None
        coefficients = _circle_coefficients(
            *(self.normalized_coordinates[point] for point in points[:3])
        )
        return None if coefficients is None else _key(coefficients, self.digits)

    def profile(
        self,
        point: Point,
        *,
        family: str,
        inputs: Sequence[str],
    ) -> NumericalIncidenceProfile:
        normalized_point = self.normalize(point)
        coincident = tuple(
            sorted(
                name
                for name, existing in self.normalized_coordinates.items()
                if math.dist(existing, normalized_point) <= self.tolerance
            )
        )
        incident_lines = tuple(
            locus
            for locus in self.lines
            if _line_residual(locus.coefficients, normalized_point) <= self.tolerance
        )
        incident_circles = tuple(
            locus
            for locus in self.circles
            if _circle_residual(locus.coefficients, normalized_point) <= self.tolerance
        )

        trivial_lines: set[LocusKey] = set()
        trivial_circles: set[LocusKey] = set()

        def add_line(left: int, right: int) -> None:
            if max(left, right) >= len(inputs):
                return
            key = self.line_key(inputs[left], inputs[right])
            if key is not None:
                trivial_lines.add(key)

        if family in {"midpoint", "mirror", "on_line"}:
            add_line(0, 1)
        elif family == "foot":
            add_line(1, 2)
        elif family == "intersection_ll":
            add_line(0, 1)
            add_line(2, 3)
        elif family == "intersection_lc":
            add_line(0, 2)

        if family == "on_circle" and len(inputs) >= 2:
            key = self.center_point_circle_key(inputs[0], inputs[1])
            if key is not None:
                trivial_circles.add(key)
        elif family == "intersection_lc" and len(inputs) >= 3:
            key = self.center_point_circle_key(inputs[1], inputs[2])
            if key is not None:
                trivial_circles.add(key)
        elif family == "intersection_cc" and len(inputs) >= 3:
            for center_index in (0, 1):
                key = self.center_point_circle_key(
                    inputs[center_index], inputs[2]
                )
                if key is not None:
                    trivial_circles.add(key)
        elif family == "on_circum":
            key = self.circumcircle_key(inputs)
            if key is not None:
                trivial_circles.add(key)

        nontrivial_lines = tuple(
            locus for locus in incident_lines if locus.coefficients not in trivial_lines
        )
        nontrivial_circles = tuple(
            locus
            for locus in incident_circles
            if locus.coefficients not in trivial_circles
        )

        categories: list[str] = []
        if len(incident_lines) >= 3:
            categories.append("multiple_lines")
        if (
            len(incident_lines) >= 1
            and len(incident_circles) >= 1
            and len(incident_lines) + len(incident_circles) >= 3
        ):
            categories.append("mixed_lines_circles")
        if family == "midpoint" and (nontrivial_lines or nontrivial_circles):
            categories.append("midpoint_extra_locus")
        if family == "mirror" and (nontrivial_lines or nontrivial_circles):
            categories.append("mirror_extra_locus")
        if family == "foot" and nontrivial_lines:
            source = self.normalized_coordinates.get(inputs[0]) if inputs else None
            if source is not None and any(
                _line_residual(locus.coefficients, source) > self.tolerance
                for locus in nontrivial_lines
            ):
                categories.append("foot_extra_line")
        if coincident and len(incident_lines) + len(incident_circles) >= 2:
            categories.append("identical_point_multiple_loci")

        return NumericalIncidenceProfile(
            family=family,
            coincident_points=coincident,
            incident_lines=incident_lines,
            incident_circles=incident_circles,
            nontrivial_lines=nontrivial_lines,
            nontrivial_circles=nontrivial_circles,
            heuristic_categories=tuple(categories),
        )
