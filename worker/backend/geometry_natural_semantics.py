"""Small, auditable natural-language semantics for geometry benchmarks.

JGEX records construction syntax but drops some theorem-domain qualifiers such
as ``acute`` and ``on segment``.  Exact charts must not silently recover those
conditions from a problem name.  This module extracts a deliberately small
typed subset from the frozen natural-language statement so the conditions can
participate in the certificate hash chain.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import re


_SYMBOL = r"[A-Z][0-9]*"


def _plain_text(statement: str) -> str:
    text = re.sub(r"\\overline\s*\{([^{}]+)\}", r"\1", statement)
    text = re.sub(r"\\overarc\s*\{([^{}]+)\}", r"\1", text)
    text = re.sub(r"\b([A-Za-z])['’](?=[A-Za-z])", r"\g<1>1", text)
    text = re.sub(r"\\triangle\b", " triangle ", text)
    text = text.replace("$", " ").replace("\\(", " ").replace("\\)", " ")
    text = text.replace("{", "").replace("}", "").replace("_", "")
    return re.sub(r"\s+", " ", text).strip().upper()


@dataclass(frozen=True)
class NaturalGeometrySemantics:
    parser_version: str
    statement_sha256: str
    normalized_text: str
    acute_triangles: tuple[tuple[str, str, str], ...]
    segment_memberships: tuple[tuple[str, str, str], ...]
    arc_midpoints_through: tuple[tuple[str, str, str, str], ...]
    circle_intersection_pairs: tuple[
        tuple[str, str, tuple[str, str, str], tuple[str, str, str]], ...
    ]
    existential_circle_pair_labellings: tuple[
        tuple[str, str, tuple[str, str, str], tuple[str, str, str]], ...
    ]
    second_circle_intersections: tuple[
        tuple[str, str, tuple[str, str, str], tuple[str, str, str]], ...
    ]
    existential_midpoints_on_circumcircles: tuple[
        tuple[str, str, str, tuple[str, str, str]], ...
    ]
    miquel_points: tuple[tuple[str, str, str, str], ...]
    typed_atoms: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def has_acute_triangle(self, vertices: tuple[str, str, str]) -> bool:
        wanted = tuple(point.upper() for point in vertices)
        return any(
            triangle == wanted or triangle == (wanted[0], wanted[2], wanted[1])
            for triangle in self.acute_triangles
        )

    def point_on_segment(self, point: str, endpoints: tuple[str, str]) -> bool:
        wanted_point = point.upper()
        wanted_endpoints = frozenset(endpoint.upper() for endpoint in endpoints)
        return any(
            candidate == wanted_point
            and frozenset((left, right)) == wanted_endpoints
            for candidate, left, right in self.segment_memberships
        )

    def has_arc_midpoint_through(
        self,
        point: str,
        endpoints: tuple[str, str],
        through: str,
    ) -> bool:
        """Return whether ``point`` bisects the endpoint arc containing ``through``."""

        wanted_point = point.upper()
        wanted_endpoints = frozenset(endpoint.upper() for endpoint in endpoints)
        wanted_through = through.upper()
        return any(
            candidate == wanted_point
            and frozenset((left, right)) == wanted_endpoints
            and arc_through == wanted_through
            for candidate, left, arc_through, right in self.arc_midpoints_through
        )

    def has_second_circle_intersection(
        self,
        point: str,
        known_point: str,
        circles: tuple[tuple[str, str, str], tuple[str, str, str]],
    ) -> bool:
        wanted_circles = {
            frozenset(vertex.upper() for vertex in circle) for circle in circles
        }
        return any(
            candidate == point.upper()
            and known == known_point.upper()
            and {
                frozenset(first_circle),
                frozenset(second_circle),
            }
            == wanted_circles
            for candidate, known, first_circle, second_circle
            in self.second_circle_intersections
        )

    def has_existential_midpoint_on_circumcircle(
        self,
        midpoint_base: str,
        roots: tuple[str, str],
        parent_triangle: tuple[str, str, str],
    ) -> bool:
        wanted_roots = frozenset(root.upper() for root in roots)
        wanted_triangle = frozenset(vertex.upper() for vertex in parent_triangle)
        return any(
            base == midpoint_base.upper()
            and frozenset((first_root, second_root)) == wanted_roots
            and frozenset(triangle) == wanted_triangle
            for base, first_root, second_root, triangle
            in self.existential_midpoints_on_circumcircles
        )

    def has_circle_intersection_pair(
        self,
        roots: tuple[str, str],
        circles: tuple[tuple[str, str, str], tuple[str, str, str]],
    ) -> bool:
        wanted_roots = frozenset(root.upper() for root in roots)
        wanted_circles = {
            frozenset(vertex.upper() for vertex in circle) for circle in circles
        }
        return any(
            frozenset((first_root, second_root)) == wanted_roots
            and {
                frozenset(first_circle),
                frozenset(second_circle),
            }
            == wanted_circles
            for first_root, second_root, first_circle, second_circle
            in self.circle_intersection_pairs
        )

    def has_existential_circle_pair_labelling(
        self,
        roots: tuple[str, str],
        circles: tuple[tuple[str, str, str], tuple[str, str, str]],
    ) -> bool:
        """Return whether a common pair may be labelled in either order."""

        wanted_roots = frozenset(root.upper() for root in roots)
        wanted_circles = {
            frozenset(vertex.upper() for vertex in circle) for circle in circles
        }
        return any(
            frozenset((first_root, second_root)) == wanted_roots
            and {
                frozenset(first_circle),
                frozenset(second_circle),
            }
            == wanted_circles
            for first_root, second_root, first_circle, second_circle
            in self.existential_circle_pair_labellings
        )

    def has_miquel_point(
        self,
        point: str,
        cevian_triangle: tuple[str, str, str],
    ) -> bool:
        wanted_point = point.upper()
        wanted_triangle = frozenset(vertex.upper() for vertex in cevian_triangle)
        return any(
            candidate == wanted_point
            and frozenset((first, second, third)) == wanted_triangle
            for candidate, first, second, third in self.miquel_points
        )


def extract_geometry_natural_semantics(statement: str) -> NaturalGeometrySemantics:
    """Extract the certified finite grammar currently used by exact charts."""

    normalized = statement.strip()
    plain = _plain_text(normalized)

    acute_triangles = {
        (match.group(1), match.group(2), match.group(3))
        for match in re.finditer(
            r"\b([A-Z])([A-Z])([A-Z])\s+BE\s+AN?\s+"
            r"ACUTE(?:[\s-]+ANGLED)?\s+TRIANGLE\b",
            plain,
        )
    }

    segment_memberships: set[tuple[str, str, str]] = set()
    plural_pattern = re.compile(
        rf"\b((?:{_SYMBOL}\s*,\s*)*{_SYMBOL})\s+BE\s+POINTS?\s+ON\s+"
        r"(?:THE\s+)?SEGMENT\s+([A-Z])([A-Z])\b"
    )
    for match in plural_pattern.finditer(plain):
        points = tuple(part.strip() for part in match.group(1).split(","))
        for point in points:
            segment_memberships.add((point, match.group(2), match.group(3)))

    singular_pattern = re.compile(
        rf"\bPOINT\s+({_SYMBOL})\s+(?:LIES|IS)\s+ON\s+"
        r"(?:THE\s+)?SEGMENT\s+([A-Z])([A-Z])\b"
    )
    for match in singular_pattern.finditer(plain):
        segment_memberships.add((match.group(1), match.group(2), match.group(3)))

    arc_midpoints_through: set[tuple[str, str, str, str]] = set()
    arc_midpoint_patterns = (
        re.compile(
            rf"\b({_SYMBOL})\s+(?:IS|BE)\s+(?:THE\s+)?MIDPOINT\s+OF\s+"
            r"(?:THE\s+)?(?:MAJOR\s+|MINOR\s+)?ARC\s+"
            r"([A-Z])([A-Z])([A-Z])\b"
        ),
        re.compile(
            rf"\bDENOTE\s+BY\s+({_SYMBOL})\s+(?:THE\s+)?MIDPOINT\s+OF\s+"
            r"(?:THE\s+)?(?:MAJOR\s+|MINOR\s+)?ARC\s+"
            r"([A-Z])([A-Z])([A-Z])\b"
        ),
    )
    for pattern in arc_midpoint_patterns:
        for match in pattern.finditer(plain):
            arc_midpoints_through.add(
                (match.group(1), match.group(2), match.group(3), match.group(4))
            )

    circle_intersection_pairs: set[
        tuple[str, str, tuple[str, str, str], tuple[str, str, str]]
    ] = set()
    circle_pair_pattern = re.compile(
        rf"\bCIRCUMCIRCLES?\s+OF\s+(?:TRIANGLES?\s+)?"
        rf"([A-Z])([A-Z])([A-Z])\s+AND\s+(?:TRIANGLES?\s+)?"
        rf"([A-Z])([A-Z])([A-Z])\s+INTERSECT\s+AT\s+POINTS?\s+"
        rf"({_SYMBOL})\s+AND\s+({_SYMBOL})\b"
    )
    for match in circle_pair_pattern.finditer(plain):
        circle_intersection_pairs.add(
            (
                match.group(7),
                match.group(8),
                (match.group(1), match.group(2), match.group(3)),
                (match.group(4), match.group(5), match.group(6)),
            )
        )

    existential_circle_pair_labellings: set[
        tuple[str, str, tuple[str, str, str], tuple[str, str, str]]
    ] = set()
    existential_pair_pattern = re.compile(
        rf"\b(?:THE\s+)?CIRCLES?\s+\(?"
        rf"({_SYMBOL})({_SYMBOL})({_SYMBOL})\)?\s+AND\s+\(?"
        rf"({_SYMBOL})({_SYMBOL})({_SYMBOL})\)?"
        rf".{{0,220}}?\b(?:THESE\s+)?(?:TWO\s+)?INTERSECTION\s+POINTS?\s+"
        rf"(?:CAN|MAY)\s+BE\s+(?:NAMED|DENOTED|LABELLED|LABELED)\s+"
        rf"(?:BY\s+)?({_SYMBOL})\s+(?:AND|,)\s+({_SYMBOL})\b"
    )
    for match in existential_pair_pattern.finditer(plain):
        existential_circle_pair_labellings.add(
            (
                match.group(7),
                match.group(8),
                (match.group(1), match.group(2), match.group(3)),
                (match.group(4), match.group(5), match.group(6)),
            )
        )

    second_circle_intersections: set[
        tuple[str, str, tuple[str, str, str], tuple[str, str, str]]
    ] = set()
    second_intersection_pattern = re.compile(
        rf"\b({_SYMBOL})\s+(?:IS\s+|BE\s+)?(?:THE\s+)?SECOND\s+INTERSECTION\s+OF\s+"
        rf"(?:THE\s+)?CIRCUMCIRCLES?\s+OF\s+TRIANGLES?\s+"
        rf"([A-Z])([A-Z])([A-Z])\s*,?\s+(?:AND\s+)?"
        rf"([A-Z])([A-Z])([A-Z])\b"
    )
    for match in second_intersection_pattern.finditer(plain):
        first_circle = (match.group(2), match.group(3), match.group(4))
        second_circle = (match.group(5), match.group(6), match.group(7))
        shared = sorted(set(first_circle) & set(second_circle))
        if len(shared) == 1:
            second_circle_intersections.add(
                (match.group(1), shared[0], first_circle, second_circle)
            )

    named_circumcircles: dict[str, tuple[str, str, str]] = {}
    named_circle_pattern = re.compile(
        r"\b([A-Z])([A-Z])([A-Z])\s+BE\s+(?:AN?\s+)?"
        r"(?:SCALENE\s+|ACUTE(?:[\s-]+ANGLED)?\s+)?TRIANGLE\s+WITH\s+"
        r"CIRCUMCIRCLE\s+(\\?[A-Z]+)\b"
    )
    for match in named_circle_pattern.finditer(plain):
        named_circumcircles[match.group(4)] = (
            match.group(1),
            match.group(2),
            match.group(3),
        )

    existential_midpoints_on_circumcircles: set[
        tuple[str, str, str, tuple[str, str, str]]
    ] = set()
    for first_root, second_root, _, _ in circle_intersection_pairs:
        for circle_name, triangle in named_circumcircles.items():
            alternatives = (
                (first_root, second_root),
                (second_root, first_root),
            )
            for left_root, right_root in alternatives:
                pattern = re.compile(
                    rf"{re.escape(circle_name)}\s+PASSES\s+THROUGH\s+THE\s+MIDPOINT\s+"
                    rf"OF\s+EITHER\s+({_SYMBOL}){re.escape(left_root)}\s+OR\s+"
                    rf"({_SYMBOL}){re.escape(right_root)}\b"
                )
                match = pattern.search(plain)
                if match and match.group(1) == match.group(2):
                    existential_midpoints_on_circumcircles.add(
                        (match.group(1), first_root, second_root, triangle)
                    )

    miquel_points = {
        (match.group(1), match.group(2), match.group(3), match.group(4))
        for match in re.finditer(
            rf"\bMIQUEL\s+POINT\s+({_SYMBOL})\s+OF\s+"
            r"(?:TRIANGLE\s+)?([A-Z])([A-Z])([A-Z])\b",
            plain,
        )
    }

    atoms = tuple(
        sorted(
            [
                f"acute({','.join(triangle)})"
                for triangle in acute_triangles
            ]
            + [
                f"between({point},{left},{right})"
                for point, left, right in segment_memberships
            ]
            + [
                f"arc_midpoint_through({point},{left},{through},{right})"
                for point, left, through, right in arc_midpoints_through
            ]
            + [
                "circle_intersection_pair("
                f"{first_root},{second_root},"
                f"circumcircle({','.join(first_circle)}),"
                f"circumcircle({','.join(second_circle)}))"
                for first_root, second_root, first_circle, second_circle
                in circle_intersection_pairs
            ]
            + [
                "exists_circle_pair_labelling("
                f"{first_root},{second_root},"
                f"circumcircle({','.join(first_circle)}),"
                f"circumcircle({','.join(second_circle)}))"
                for first_root, second_root, first_circle, second_circle
                in existential_circle_pair_labellings
            ]
            + [
                "second_circle_intersection("
                f"{point},{known},"
                f"circumcircle({','.join(first_circle)}),"
                f"circumcircle({','.join(second_circle)}))"
                for point, known, first_circle, second_circle
                in second_circle_intersections
            ]
            + [
                "exists_midpoint_on_circumcircle("
                f"{base},{first_root},{second_root},{','.join(triangle)})"
                for base, first_root, second_root, triangle
                in existential_midpoints_on_circumcircles
            ]
            + [
                f"miquel_point({point},{first},{second},{third})"
                for point, first, second, third in miquel_points
            ]
        )
    )
    return NaturalGeometrySemantics(
        parser_version="geometry-natural-semantics-v5",
        statement_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        normalized_text=plain,
        acute_triangles=tuple(sorted(acute_triangles)),
        segment_memberships=tuple(sorted(segment_memberships)),
        arc_midpoints_through=tuple(sorted(arc_midpoints_through)),
        circle_intersection_pairs=tuple(sorted(circle_intersection_pairs)),
        existential_circle_pair_labellings=tuple(
            sorted(existential_circle_pair_labellings)
        ),
        second_circle_intersections=tuple(sorted(second_circle_intersections)),
        existential_midpoints_on_circumcircles=tuple(
            sorted(existential_midpoints_on_circumcircles)
        ),
        miquel_points=tuple(sorted(miquel_points)),
        typed_atoms=atoms,
    )


__all__ = [
    "NaturalGeometrySemantics",
    "extract_geometry_natural_semantics",
]
