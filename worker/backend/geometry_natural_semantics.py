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
        )
    )
    return NaturalGeometrySemantics(
        parser_version="geometry-natural-semantics-v2",
        statement_sha256=hashlib.sha256(normalized.encode("utf-8")).hexdigest(),
        normalized_text=plain,
        acute_triangles=tuple(sorted(acute_triangles)),
        segment_memberships=tuple(sorted(segment_memberships)),
        arc_midpoints_through=tuple(sorted(arc_midpoints_through)),
        typed_atoms=atoms,
    )


__all__ = [
    "NaturalGeometrySemantics",
    "extract_geometry_natural_semantics",
]
