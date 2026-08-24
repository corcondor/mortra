"""Private OpenMath-style geometry vocabulary with exact point-IR views.

OpenMath's experimental ``plangeo1``/``plangeo3`` dictionaries distinguish
objects from relations, while Hilbert-Geo keeps Point/Line/Plane/Sphere sorts
explicit.  MORTRA's native Euclidean engines use point tuples instead.  This
module is the lossless boundary between those representations; it contains no
theorems and never treats a change of notation as a proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from worker.backend.geometry_proof_hypergraph import Atom


OPENMATH_CD_BASE = "http://www.openmath.org/cd"
MORTRA_GEOMETRY_CD = "https://mortra.dev/cd/private_mortra_geometry"

POINT2 = f"{MORTRA_GEOMETRY_CD}#Point2"
POINT3 = f"{MORTRA_GEOMETRY_CD}#Point3"
LINE2 = f"{MORTRA_GEOMETRY_CD}#Line2"
LINE3 = f"{MORTRA_GEOMETRY_CD}#Line3"
PLANE3 = f"{MORTRA_GEOMETRY_CD}#Plane3"
CIRCLE2 = f"{MORTRA_GEOMETRY_CD}#Circle2"
SPHERE3 = f"{MORTRA_GEOMETRY_CD}#Sphere3"

VARIABLE = f"{MORTRA_GEOMETRY_CD}#variable"
LINE_THROUGH = f"{OPENMATH_CD_BASE}/plangeo1#line"
PLANE_THROUGH = f"{MORTRA_GEOMETRY_CD}#plane_through"

COLLINEAR = f"{MORTRA_GEOMETRY_CD}#collinear"
COCIRCULAR = f"{MORTRA_GEOMETRY_CD}#cocircular"
COPLANAR = f"{MORTRA_GEOMETRY_CD}#coplanar"
COSPHERICAL = f"{MORTRA_GEOMETRY_CD}#cospherical"
INCIDENT = f"{OPENMATH_CD_BASE}/plangeo1#incident"
PARALLEL = f"{OPENMATH_CD_BASE}/plangeo3#parallel"
PERPENDICULAR = f"{OPENMATH_CD_BASE}/plangeo3#perpendicular"
EQUAL_DISTANCE = f"{MORTRA_GEOMETRY_CD}#equal_distance"
EQUAL_ANGLE = f"{MORTRA_GEOMETRY_CD}#equal_angle"

POINT_RELATION_URIS = {
    "coll": COLLINEAR,
    "cong": f"{MORTRA_GEOMETRY_CD}#equal_distance_by_points",
    "cyclic": COCIRCULAR,
    "eqangle": f"{MORTRA_GEOMETRY_CD}#equal_angle_by_points",
    "para": f"{MORTRA_GEOMETRY_CD}#parallel_lines_by_points",
    "perp": f"{MORTRA_GEOMETRY_CD}#perpendicular_lines_by_points",
}


@dataclass(frozen=True)
class GeometryTerm:
    sort_uri: str
    symbol_uri: str
    arguments: tuple["GeometryTerm", ...] = ()
    name: str | None = None

    def __post_init__(self) -> None:
        if not self.sort_uri or not self.symbol_uri:
            raise ValueError("geometry terms require named sorts and symbols")
        if (self.name is None) == (not self.arguments):
            raise ValueError("a geometry term must be either a variable or an application")

    def render(self) -> str:
        if self.name is not None:
            return self.name
        return f"{self.symbol_uri}({','.join(item.render() for item in self.arguments)})"


@dataclass(frozen=True)
class GeometryStatement:
    symbol_uri: str
    arguments: tuple[GeometryTerm, ...]
    expected_sorts: tuple[str, ...]

    def __post_init__(self) -> None:
        if len(self.arguments) != len(self.expected_sorts):
            raise ValueError("statement arity does not match its signature")
        actual = tuple(item.sort_uri for item in self.arguments)
        if actual != self.expected_sorts:
            raise ValueError(f"statement sort mismatch: {actual} != {self.expected_sorts}")

    def render(self) -> str:
        return f"{self.symbol_uri}({','.join(item.render() for item in self.arguments)})"


def point(name: str, *, dimension: int = 2) -> GeometryTerm:
    if dimension not in {2, 3}:
        raise ValueError("only Euclidean dimensions 2 and 3 are supported")
    return GeometryTerm(POINT2 if dimension == 2 else POINT3, VARIABLE, name=name)


def line_through(left: GeometryTerm, right: GeometryTerm) -> GeometryTerm:
    if left.sort_uri != right.sort_uri or left.sort_uri not in {POINT2, POINT3}:
        raise ValueError("a line requires two points in the same ambient dimension")
    if left == right:
        raise ValueError("a line requires two distinct points")
    ordered = tuple(sorted((left, right), key=GeometryTerm.render))
    return GeometryTerm(
        LINE2 if left.sort_uri == POINT2 else LINE3,
        LINE_THROUGH,
        ordered,
    )


def plane_through(first: GeometryTerm, second: GeometryTerm, third: GeometryTerm) -> GeometryTerm:
    points = (first, second, third)
    if any(item.sort_uri != POINT3 for item in points):
        raise ValueError("a plane requires three 3D points")
    if len(set(points)) != 3:
        raise ValueError("a plane requires three distinct points")
    return GeometryTerm(
        PLANE3,
        PLANE_THROUGH,
        tuple(sorted(points, key=GeometryTerm.render)),
    )


def relation(symbol_uri: str, arguments: Iterable[GeometryTerm]) -> GeometryStatement:
    args = tuple(arguments)
    signatures = {
        PARALLEL: {(LINE2, LINE2), (LINE3, LINE3), (PLANE3, PLANE3), (LINE3, PLANE3)},
        PERPENDICULAR: {
            (LINE2, LINE2),
            (LINE3, LINE3),
            (PLANE3, PLANE3),
            (LINE3, PLANE3),
        },
        INCIDENT: {
            (POINT2, LINE2),
            (POINT3, LINE3),
            (POINT3, PLANE3),
            (LINE3, PLANE3),
        },
        EQUAL_DISTANCE: {(LINE2, LINE2), (LINE3, LINE3)},
        EQUAL_ANGLE: {(LINE2, LINE2, LINE2, LINE2), (LINE3, LINE3, LINE3, LINE3)},
    }
    actual = tuple(item.sort_uri for item in args)
    if symbol_uri in signatures and actual not in signatures[symbol_uri]:
        raise ValueError(f"unsupported signature for {symbol_uri}: {actual}")
    if symbol_uri == COLLINEAR and (
        len(args) < 3 or len(set(actual)) != 1 or actual[0] not in {POINT2, POINT3}
    ):
        raise ValueError("collinear expects at least three points in one dimension")
    if symbol_uri == COCIRCULAR and (
        len(args) < 4 or len(set(actual)) != 1 or actual[0] not in {POINT2, POINT3}
    ):
        raise ValueError("cocircular expects at least four points in one dimension")
    if symbol_uri == COPLANAR and (len(args) < 4 or set(actual) != {POINT3}):
        raise ValueError("coplanar expects at least four 3D points")
    if symbol_uri == COSPHERICAL and (len(args) < 5 or set(actual) != {POINT3}):
        raise ValueError("cospherical expects at least five 3D points")
    return GeometryStatement(symbol_uri, args, actual)


def lower_point_atom(atom: Atom, *, dimension: int = 2) -> GeometryStatement | None:
    """Lower MORTRA's point-only predicates into structured geometry objects."""

    canonical = atom.canonical()
    args = canonical.arguments
    points = tuple(point(item, dimension=dimension) for item in args)
    if canonical.predicate == "coll" and len(points) == 3:
        return relation(COLLINEAR, points)
    if canonical.predicate in {"para", "perp", "cong"} and len(points) == 4:
        lines = (line_through(points[0], points[1]), line_through(points[2], points[3]))
        symbol = {
            "para": PARALLEL,
            "perp": PERPENDICULAR,
            "cong": EQUAL_DISTANCE,
        }[canonical.predicate]
        return relation(symbol, lines)
    if canonical.predicate == "cyclic" and len(points) == 4:
        return relation(COCIRCULAR, points)
    if canonical.predicate == "eqangle" and len(points) == 8:
        lines = tuple(
            line_through(points[index], points[index + 1])
            for index in range(0, 8, 2)
        )
        return relation(EQUAL_ANGLE, lines)
    if canonical.predicate == "coplanar" and dimension == 3 and len(points) >= 4:
        return relation(COPLANAR, points)
    if canonical.predicate == "cospherical" and dimension == 3 and len(points) >= 5:
        return relation(COSPHERICAL, points)
    return None


def _point_name(term: GeometryTerm) -> str | None:
    if term.symbol_uri != VARIABLE or term.name is None or term.arguments:
        return None
    return term.name


def _line_point_names(term: GeometryTerm) -> tuple[str, str] | None:
    if term.symbol_uri != LINE_THROUGH or len(term.arguments) != 2:
        return None
    names = tuple(_point_name(item) for item in term.arguments)
    if any(item is None for item in names):
        return None
    return names  # type: ignore[return-value]


def reelaborate_point_atom(statement: GeometryStatement) -> Atom | None:
    """Return to point predicates only when the structured view is lossless."""

    if statement.symbol_uri in {COLLINEAR, COCIRCULAR, COPLANAR, COSPHERICAL}:
        names = tuple(_point_name(item) for item in statement.arguments)
        if any(item is None for item in names):
            return None
        predicate = {
            COLLINEAR: "coll",
            COCIRCULAR: "cyclic",
            COPLANAR: "coplanar",
            COSPHERICAL: "cospherical",
        }[statement.symbol_uri]
        return Atom(predicate, names).canonical()  # type: ignore[arg-type]
    if statement.symbol_uri in {PARALLEL, PERPENDICULAR, EQUAL_DISTANCE}:
        if len(statement.arguments) != 2:
            return None
        lines = tuple(_line_point_names(item) for item in statement.arguments)
        if any(item is None for item in lines):
            return None
        predicate = {
            PARALLEL: "para",
            PERPENDICULAR: "perp",
            EQUAL_DISTANCE: "cong",
        }[statement.symbol_uri]
        return Atom(predicate, (*lines[0], *lines[1])).canonical()  # type: ignore[misc]
    if statement.symbol_uri == EQUAL_ANGLE and len(statement.arguments) == 4:
        lines = tuple(_line_point_names(item) for item in statement.arguments)
        if any(item is None for item in lines):
            return None
        return Atom("eqangle", tuple(value for line in lines for value in line)).canonical()  # type: ignore[union-attr]
    return None
