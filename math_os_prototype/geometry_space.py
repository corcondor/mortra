"""The same fragment in one more dimension, and what the sign kernel buys there.

Points are triples of rationals. The predicates are the plane's, written in
three coordinates, plus the one the plane cannot have: `coplanar`. The
primitives are the plane's, plus the two a plane has no room for -- the foot on
a plane and the reflection in one.

Two things are worth stating before anything is built.

**The obstruction is the same, and it is sharper here.** Every primitive below is
defined by metric conditions alone, so every one of them commutes with every
isometry of space, a reflection in a plane included. If such a reflection fixes
the given points, it fixes everything constructed from them. In the plane that
says: from two points you never leave their line. Here it says: **from three
points you never leave their plane**, because the reflection in that plane fixes
all three. So a three-dimensional fragment does not become three-dimensional by
being given three-dimensional coordinates; it becomes so when it is given a
fourth point off the plane. `escapes_the_plane` measures exactly that.

Two cautions belong with that statement. It is about the *equivariance of this
list of primitives*, not about arithmetic: rational rotations are plentiful in
both dimensions -- (3/5, 4/5) turns the plane -- and the slogan "no rotation is
rational" would be wrong. And the reflection has to be in a *plane*: the plane
fragment's `reflect` in a line has determinant -1 in two dimensions and +1 in
three, where it is a half turn, so quoting it here would invert the argument.

**And one thing is genuinely easier here than in the plane.** An equilateral
triangle with rational vertices does not exist in the plane -- its area would be
sqrt(3)/4 times a rational, and the shoelace sum says the area of a rational
triangle is rational -- which is why `geometry_quadratic` had to adjoin sqrt 3.
In space it is free: (0,0,0), (1,1,0), (1,0,1) has all three squared edges equal
to 2. The sign kernel predicts exactly this, because sqrt 3 needs three rational
squares and "three squares" means "a distance between rational points of space
but not of the plane" -- it is the diagonal of the unit cube.

**Order is where three dimensions start to pay.** Which side of a plane a point
falls on, whether a solid is convex, whether a face is turned towards the eye --
all of these are signs of determinants, and none of them is an equality. They are
handed to `geometry_sign`, which turns each into an equation with a witness. The
five Platonic solids are the demonstration: three of them have rational vertices
and their convexity is certified here face by face; the other two do not, and the
reason is a regular pentagon.
"""
from __future__ import annotations

from fractions import Fraction
from itertools import combinations

import sympy as sp

from math_os_prototype import geometry_sign as sign

# ---------------------------------------------------------------------------
# Points, and the small amount of vector arithmetic the predicates need
# ---------------------------------------------------------------------------

def point(value):
    return tuple(Fraction(v) if not isinstance(v, sp.Expr) else v for v in value)


def subtract(a, b):
    return tuple(x-y for x, y in zip(a, b))


def dot(a, b):
    return sum(x*y for x, y in zip(a, b))


def cross(a, b):
    return (a[1]*b[2]-a[2]*b[1], a[2]*b[0]-a[0]*b[2], a[0]*b[1]-a[1]*b[0])


def determinant(a, b, c):
    """The signed volume of the parallelepiped: the orientation of three vectors."""
    return dot(a, cross(b, c))


def squared_distance(a, b):
    d = subtract(a, b)
    return dot(d, d)


def scale(vector, factor):
    return tuple(v*factor for v in vector)


def add(a, b):
    return tuple(x+y for x, y in zip(a, b))


# ---------------------------------------------------------------------------
# The predicates
# ---------------------------------------------------------------------------

EQUALITY_PREDICATES = {"midp": 3, "coll": 3, "perp": 4, "para": 4, "cong": 4, "coplanar": 4}
NONZERO_PREDICATES = {"diff": 2, "ncoll": 3, "ncoplanar": 4}
PREDICATE_ARITIES = {**EQUALITY_PREDICATES, **NONZERO_PREDICATES}


def value_at(predicate, arguments, coordinates):
    """The predicate's defining quantity, exactly. Zero is what an equality means."""
    points = [point(coordinates[name]) for name in arguments]
    if predicate == "midp":
        m, a, b = points
        return sum((2*m[i]-a[i]-b[i])**2 for i in range(3))
    if predicate in ("coll", "ncoll"):
        a, b, c = points
        normal = cross(subtract(b, a), subtract(c, a))
        return dot(normal, normal)
    if predicate in ("coplanar", "ncoplanar"):
        a, b, c, d = points
        return determinant(subtract(b, a), subtract(c, a), subtract(d, a))
    if predicate == "cong":
        a, b, c, d = points
        return squared_distance(a, b)-squared_distance(c, d)
    if predicate == "perp":
        a, b, c, d = points
        return dot(subtract(b, a), subtract(d, c))
    if predicate == "para":
        a, b, c, d = points
        normal = cross(subtract(b, a), subtract(d, c))
        return dot(normal, normal)
    if predicate == "diff":
        a, b = points
        return squared_distance(a, b)
    raise ValueError(f"unknown predicate {predicate}")


def conditions(predicate, arguments):
    """The non-degeneracy a predicate needs before it means anything."""
    if predicate in ("perp", "para"):
        return [("diff", tuple(arguments[:2])), ("diff", tuple(arguments[2:]))]
    if predicate in ("coplanar", "ncoplanar"):
        return [("ncoll", tuple(arguments[:3]))]
    return []


def atom_holds(predicate, arguments, coordinates):
    """Decide an atom exactly, with its prerequisites certified first.

    The shape is the plane fragment's: an equality holds when its polynomial
    vanishes, a non-vanishing predicate when it does not, and a refusal is
    returned as `False` for both -- so a `False` here means "not proved", and
    the caller who needs the difference asks for the value.
    """
    if predicate not in PREDICATE_ARITIES:
        raise ValueError(f"unknown predicate {predicate}")
    if len(arguments) != PREDICATE_ARITIES[predicate]:
        raise ValueError(f"{predicate} takes {PREDICATE_ARITIES[predicate]} points")
    for needed, names in conditions(predicate, arguments):
        if not atom_holds(needed, names, coordinates):
            return False
    value = value_at(predicate, arguments, coordinates)
    value = sp.simplify(value) if isinstance(value, sp.Expr) else value
    return value != 0 if predicate in NONZERO_PREDICATES else value == 0


# ---------------------------------------------------------------------------
# The primitives
# ---------------------------------------------------------------------------

ARITY = {"midpoint": 2, "mirror": 2, "centroid": 3, "foot_line": 3, "foot_plane": 4,
         "reflect_plane": 4, "intersection_lp": 5, "circumcentre": 3}


def execute(family, arguments, coordinates):
    """One construction, exactly, or a refusal with its reason.

    Every witness here is a rational function of its inputs, so from rational
    points only rational points are reached -- the same closure property the
    plane fragment has, and the reason a quadratic extension has to be asked for
    rather than stumbled into.
    """
    if family not in ARITY:
        return None, f"unknown primitive {family}"
    if len(arguments) != ARITY[family]:
        return None, "arity"
    points = [point(coordinates[name]) for name in arguments]
    if family == "midpoint":
        a, b = points
        return scale(add(a, b), Fraction(1, 2)), None
    if family == "mirror":
        a, b = points
        return subtract(scale(b, 2), a), None
    if family == "centroid":
        a, b, c = points
        return scale(add(add(a, b), c), Fraction(1, 3)), None
    if family == "foot_line":
        p, a, b = points
        direction = subtract(b, a)
        length = dot(direction, direction)
        if length == 0:
            return None, "unproved_applicability:diff"
        return add(a, scale(direction, dot(subtract(p, a), direction)/length)), None
    if family in ("foot_plane", "reflect_plane"):
        p, a, b, c = points
        normal = cross(subtract(b, a), subtract(c, a))
        length = dot(normal, normal)
        if length == 0:
            return None, "unproved_applicability:ncoll"
        away = scale(normal, dot(subtract(p, a), normal)/length)
        foot = subtract(p, away)
        return (foot if family == "foot_plane" else subtract(scale(foot, 2), p)), None
    if family == "intersection_lp":
        p, q, a, b, c = points
        normal = cross(subtract(b, a), subtract(c, a))
        if dot(normal, normal) == 0:
            return None, "unproved_applicability:ncoll"
        direction = subtract(q, p)
        along = dot(direction, normal)
        if along == 0:
            return None, "unproved_applicability:the line runs in the plane's direction"
        return add(p, scale(direction, dot(subtract(a, p), normal)/along)), None
    if family == "circumcentre":
        a, b, c = points
        normal = cross(subtract(b, a), subtract(c, a))
        if dot(normal, normal) == 0:
            return None, "unproved_applicability:ncoll"
        # the centre is a + x(b-a) + y(c-a) with the two equal-distance equations
        u, v = subtract(b, a), subtract(c, a)
        matrix = sp.Matrix([[2*dot(u, u), 2*dot(u, v)], [2*dot(u, v), 2*dot(v, v)]])
        right = sp.Matrix([dot(u, u), dot(v, v)])
        if matrix.det() == 0:
            return None, "primitive_degeneracy"
        solved = matrix.solve(right)
        centre = add(a, add(scale(u, sp.nsimplify(solved[0])), scale(v, sp.nsimplify(solved[1]))))
        return tuple(Fraction(str(sp.nsimplify(value))) for value in centre), None
    return None, f"unhandled {family}"


# ---------------------------------------------------------------------------
# The obstruction: three points and the plane they span
# ---------------------------------------------------------------------------

def escapes_the_plane(seeds, *, rounds=2, limit=400):
    """Whether any composition of the primitives leaves the plane of the seeds.

    It cannot, and the reason is one line: the reflection in that plane fixes
    every seed, and every primitive here commutes with every isometry, so it
    fixes everything built from them. This function is the check, not the proof
    -- it builds what it can within a budget and reports that nothing left.
    """
    names = {f"s{i}": point(p) for i, p in enumerate(seeds)}
    if len(seeds) < 3:
        return {"escaped": False, "why": "fewer than three seeds span no plane"}
    base = list(names)[:3]
    built = 0
    for _ in range(rounds):
        fresh = {}
        keys = list(names)
        for family, arity in sorted(ARITY.items()):
            for choice in combinations(keys, arity):
                if built >= limit:
                    break
                value, _ = execute(family, list(choice), names)
                built += 1
                if value is None:
                    continue
                key = tuple(str(v) for v in value)
                if key not in {tuple(str(v) for v in p) for p in names.values()}:
                    fresh[f"n{len(names)+len(fresh)}"] = value
        names.update(fresh)
    off = [name for name, value in names.items()
           if not atom_holds("coplanar", tuple(base)+(name,),
                             {**names, name: value})]
    return {"escaped": bool(off), "points_built": len(names), "constructions_tried": built,
            "off_the_plane": off,
            "why": "every primitive commutes with the reflection in the plane of the seeds, "
                   "and that reflection fixes the seeds, so it fixes everything built from "
                   "them. Three points do not make a fragment three-dimensional"}


# ---------------------------------------------------------------------------
# The five solids
# ---------------------------------------------------------------------------

PHI = (1+sp.sqrt(5))/2


def tetrahedron():
    vertices = [(1, 1, 1), (1, -1, -1), (-1, 1, -1), (-1, -1, 1)]
    faces = [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)]
    return vertices, faces


def cube():
    vertices = [(x, y, z) for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]
    index = {v: i for i, v in enumerate(vertices)}
    faces = []
    for axis in range(3):
        for value in (-1, 1):
            ring = [v for v in vertices if v[axis] == value]
            ring.sort(key=lambda v: sp.atan2(*[float(v[i]) for i in range(3) if i != axis]))
            faces.append(tuple(index[v] for v in ring))
    return vertices, faces


def octahedron():
    vertices = [(1, 0, 0), (-1, 0, 0), (0, 1, 0), (0, -1, 0), (0, 0, 1), (0, 0, -1)]
    faces = [(a, b, c) for a in (0, 1) for b in (2, 3) for c in (4, 5)]
    return vertices, faces


def icosahedron():
    """The standard coordinates, which need the golden ratio and so leave QQ."""
    vertices = []
    for s in (1, -1):
        for t in (1, -1):
            vertices += [(0, s, t*PHI), (s, t*PHI, 0), (t*PHI, 0, s)]
    return [tuple(sp.nsimplify(c) for c in v) for v in vertices], []


SOLIDS = {"tetrahedron": tetrahedron, "cube": cube, "octahedron": octahedron,
          "icosahedron": icosahedron}


def is_rational(vertices):
    return all(not isinstance(c, sp.Expr) or c.is_Rational for v in vertices for c in v)


def certify_regular(vertices, *, edges=None):
    """Every edge the same length, decided by `cong` and nothing else.

    The edges are taken to be the closest pairs, which is a measurement; what is
    certified is that all of them are congruent, and that is an atom.
    """
    names = {f"v{i}": point(v) for i, v in enumerate(vertices)}
    lengths = {}
    for a, b in combinations(names, 2):
        lengths[(a, b)] = sp.nsimplify(squared_distance(names[a], names[b]))
    shortest = min(lengths.values(), key=lambda v: float(v))
    edges = edges or [pair for pair, value in lengths.items() if value == shortest]
    first = edges[0]
    decided = all(atom_holds("cong", (first[0], first[1], a, b), names) for a, b in edges)
    return {"edges": len(edges), "all_congruent": decided,
            "edge_squared_length": str(shortest),
            "atoms": f"cong(v{first[0]},v{first[1]},.,.) for every edge"}


def certify_convex(vertices, faces):
    """Every vertex on one side of every face plane, each side a certified sign.

    This is the kernel's job in three dimensions: `which side` is the sign of a
    determinant, and a sign becomes an equation the moment it is handed a sum of
    squares. A face whose plane has a vertex strictly on each side would make the
    solid non-convex, and would be reported as such rather than quietly passed.
    """
    vertices = [point(v) for v in vertices]
    report, convex = [], True
    for face in faces:
        a, b, c = (vertices[i] for i in face[:3])
        normal = cross(subtract(b, a), subtract(c, a))
        signs = set()
        witnesses = []
        for index, v in enumerate(vertices):
            if index in face:
                continue
            value = dot(subtract(v, a), normal)
            signs.add(sign.sign(value))
            if len(witnesses) < 1:
                witnesses.append(sign.certify_positive(abs(Fraction(str(sp.nsimplify(value))))))
        on_one_side = len(signs-{0}) <= 1
        convex = convex and on_one_side
        report.append({"face": list(face), "sides_seen": sorted(signs),
                       "all_on_one_side": on_one_side,
                       "a_certificate": witnesses[0] if witnesses else None})
    return {"convex": convex, "faces": report,
            "relation": "for every face, sign(det(b-a, c-a, v-a)) is the same for every other "
                        "vertex v, and each such sign is certified as a sum of squares"}


def the_rational_equilateral_triangle():
    """The triangle the plane cannot have, with rational vertices, in space.

    In the plane a rational equilateral triangle is impossible: the shoelace sum
    makes the area of a triangle with rational vertices rational, while an
    equilateral triangle of squared side s has area sqrt(3) s / 4. In space the
    constraint is gone, and the witness is small.
    """
    vertices = [(0, 0, 0), (1, 1, 0), (1, 0, 1)]
    names = {f"v{i}": point(v) for i, v in enumerate(vertices)}
    equal = (atom_holds("cong", ("v0", "v1", "v0", "v2"), names)
             and atom_holds("cong", ("v0", "v1", "v1", "v2"), names))
    return {"vertices": [list(v) for v in vertices],
            "squared_edge": str(squared_distance(names["v0"], names["v1"])),
            "all_edges_congruent": equal,
            "rational": is_rational(vertices),
            "in_the_plane": "impossible: a triangle with rational vertices has rational area by "
                            "the shoelace sum, and an equilateral triangle of squared side s has "
                            "area sqrt(3) s / 4",
            "why_space_is_different": "sqrt 3 is a sum of three rational squares and not of two, "
                                      "and the sign kernel reads that as: it is a distance "
                                      "between rational points of space and not of the plane. "
                                      "The plane had to adjoin it; space already had it"}


def no_rotation_of_order_five():
    """Why the icosahedron leaves QQ, from the trace of a rotation rather than a pentagon.

    Suppose the twelve vertices lie in K^3 for a subfield K of the reals. Move
    the centroid, which is a K-point, to the origin. The rotation group is A_5
    and holds an element of order five; three independent vertices are a K-basis
    that it maps to K-vectors, so it lies in GL_3(K) and its trace is in K. The
    trace of a rotation through t is 1 + 2 cos t, and for t = 2 pi / 5 that is
    the golden ratio. So sqrt 5 lies in K, at every edge length and every
    orientation -- this is not a matter of choosing better coordinates.

    The same argument the other way is Niven's theorem: a rational rotation
    matrix has rational trace, so 2 cos t is rational, so the only finite orders
    in SO(3, QQ) are 1, 2, 3, 4 and 6. There is no rational five-fold symmetry.
    """
    traces = [sp.simplify(1+2*sp.cos(2*sp.pi/5)), sp.simplify(1+2*sp.cos(4*sp.pi/5))]
    return {"trace_of_a_turn_through_t": "1 + 2 cos t",
            "traces_of_a_fifth_turn": [str(sp.radsimp(v)) for v in traces],
            "any_of_them_rational": any(v.is_Rational for v in traces),
            "they_generate": "QQ(sqrt(5))",
            "nivens_theorem": "a rational rotation has rational trace, so 2 cos t is rational, "
                              "so the finite orders in SO(3,QQ) are 1, 2, 3, 4, 6 -- never 5",
            "conclusion": "no regular icosahedron and no regular dodecahedron has all vertices "
                          "in any field missing sqrt 5, at any edge length or orientation"}


def inside_tetrahedron(p, a, b, c, d):
    """Whether P is in the closed tetrahedron: four signs, no division, no epsilon.

    The barycentric coordinates are ratios of determinants, and a ratio is
    non-negative exactly when the product is, so the test is four products and
    four certificates from the sign kernel -- and no division anywhere.
    """
    points = [point(v) for v in (p, a, b, c, d)]
    p, a, b, c, d = points
    whole = determinant(subtract(b, a), subtract(c, a), subtract(d, a))
    parts = {"B": determinant(subtract(p, a), subtract(c, a), subtract(d, a)),
             "C": determinant(subtract(b, a), subtract(p, a), subtract(d, a)),
             "D": determinant(subtract(b, a), subtract(c, a), subtract(p, a))}
    parts["A"] = whole-parts["B"]-parts["C"]-parts["D"]
    if whole == 0:
        return {"holds": False, "certified": False,
                "why": "the four corners are coplanar, so there is no tetrahedron"}
    certificates = {name: sign.certify_nonnegative(Fraction(value*whole))
                    for name, value in parts.items()}
    return {"holds": all(report["holds"] for report in certificates.values()),
            "certified": all(report["certified"] for report in certificates.values()),
            "volume_six_times": str(whole), "certificates": certificates,
            "relation": "for each corner X, the product of its opposite determinant with the "
                        "whole one is non-negative -- four sums of squares and no division"}


def visible_faces(vertices, faces, eye):
    """Which faces of a convex solid an eye sees: one sign each, certified.

    A face is turned towards the eye when the eye and an interior point stand on
    opposite sides of its plane, and "opposite sides" is the sign of a product.
    So hidden-surface removal for a convex solid is a finite conjunction of
    certificates and holds no floating point at all.
    """
    vertices = [point(v) for v in vertices]
    eye = point(eye)
    inside = tuple(sum(v[i] for v in vertices)/len(vertices) for i in range(3))
    seen = []
    for face in faces:
        a, b, c = (vertices[i] for i in face[:3])
        normal = cross(subtract(b, a), subtract(c, a))
        towards = dot(subtract(eye, a), normal)
        away = dot(subtract(inside, a), normal)
        product = sp.nsimplify(-towards*away)
        visible = sign.sign(Fraction(str(product))) > 0 if product.is_Rational else None
        seen.append({"face": list(face), "visible": visible,
                     "certificate": sign.certify_positive(Fraction(str(product)))
                     if product.is_Rational and product > 0 else None})
    return {"eye": [str(v) for v in eye], "faces": seen,
            "visible": sum(1 for f in seen if f["visible"]), "of": len(faces),
            "relation": "sign( -det(b-a,c-a,E-a) * det(b-a,c-a,I-a) ) > 0 for an interior I"}


def the_pentagon_argument():
    """Why two of the five solids cannot have rational vertices, in one ratio.

    A regular pentagon's diagonal is its side times the golden ratio. If every
    vertex were rational both lengths would be square roots of rationals and
    their ratio would satisfy x^2 = x + 1 over QQ, which has no rational root
    because 5 is not a square. The icosahedron's vertex figure is a regular
    pentagon and the dodecahedron's faces are regular pentagons, so neither has
    a realisation with all vertices rational -- and the standard coordinates
    show the same thing from the other side: they lie in QQ(sqrt 5) and not in QQ.
    """
    x = sp.Symbol("x")
    roots = sp.solve(sp.Eq(x**2, x+1), x)
    vertices, _ = icosahedron()
    return {"golden_ratio_satisfies": "x^2 = x + 1",
            "roots": [str(r) for r in roots],
            "any_rational_root": any(r.is_Rational for r in roots),
            "icosahedron_vertices_rational": is_rational(vertices),
            "field_of_the_standard_coordinates": "QQ(sqrt(5))",
            "conclusion": "the ratio of a regular pentagon's diagonal to its side is a root of "
                          "x^2 = x + 1, which has none in QQ; a pentagon with rational vertices "
                          "would make that ratio rational, so there is none, and neither the "
                          "icosahedron nor the dodecahedron has rational vertices"}
