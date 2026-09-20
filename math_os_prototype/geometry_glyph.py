"""Outlines, interpolation between masters, and what survives it — decided, not sampled.

A variable font interpolates linearly between masters. That is this fragment's
`midpoint` with a parameter: lerp(a, b, t) = a + t(b - a), and at t = 1/2 it is
`midpoint` exactly. Repeated lerp is de Casteljau, which is why an outline is
drawn by it and why the search in `reports/drawing-round` returned the
subdivision rule by itself when it was asked for seven points of a quadratic.

Two things follow, and they are the reason this module exists.

**Only straight motion.** Under interpolation every point travels the straight
segment from its master position to the other. A point cannot be made to travel
an arc, which is the complaint a type engineer makes about a fan opening or a pie
chart: the shape at t = 1/2 is not the shape you meant. That is the same wall
this fragment has — all seven primitives commute with a reflection and are
rational, so no rotation is among them — and the same escape works:
`geometry_quadratic.rot60` moves a point along an arc exactly, at the cost of
leaving the rationals.

**Master compatibility is decidable.** Whether a relation the designer cares
about — these three points stay in line, these two widths stay equal, this stem
stays upright — survives every interpolation is not a question about samples. The
interpolated coordinates are polynomials in t, so the relation's own polynomial
becomes a polynomial in t, and "it holds for every t" is exactly "that polynomial
is the zero polynomial". This module decides that with sympy over QQ[t], and the
answer is often no: a relation that holds at both masters need not hold between
them, because these relations are quadratic in the coordinates while the motion
is linear. Where it fails, the value of t at which it fails comes back with it.

Nothing here adds a predicate or a primitive. The relations are the fragment's
own, lowered by its own `dsl.lower`.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction

import sympy as sp

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_quadratic as qf
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_semantic_dsl as dsl

T = sp.Symbol("t", real=True)


# ---------------------------------------------------------------------------
# Interpolation, which is this fragment's own operation with a parameter
# ---------------------------------------------------------------------------

def lerp(a, b, t):
    """a + t (b - a), exactly. At t = 1/2 this is the fragment's `midpoint`."""
    return tuple(sp.expand(ai+t*(bi-ai)) for ai, bi in zip(a, b, strict=True))


def dyadic_lerp_program(depth):
    """lerp at t = 1/2**depth, as a drawing program over `midpoint` alone.

    A variable font's slider is continuous; what this fragment can construct
    exactly is the dyadic values, by halving. That is a real restriction and it
    is stated here rather than hidden: t = 3/8 is reachable, t = 1/3 is not.
    """
    body, previous = [], "p1"
    for level in range(depth):
        name = f"h{level}"
        body.append({"let": name, "op": "midpoint", "args": ["p0", previous]})
        previous = name
    return {"name": "lerp", "params": ["p0", "p1"], "body": body, "emit": [previous],
            "calls": [], "t": Fraction(1, 2**depth)}


def interpolate(master_a, master_b, t):
    """The whole glyph at one interpolation value."""
    return {name: lerp(master_a[name], master_b[name], sp.Rational(t))
            for name in master_a}


def reachable_by_halving(t, *, depth=8):
    """Whether this interpolation value is a dyadic the fragment can construct."""
    value = sp.Rational(t)
    return value.q & (value.q-1) == 0 and value.q <= 2**depth


# ---------------------------------------------------------------------------
# What survives every interpolation
# ---------------------------------------------------------------------------

def relation_along(predicate, arguments, master_a, master_b):
    """The relation's polynomial at the interpolated glyph, as a polynomial in t."""
    elaborator = gc._JGEXElaborator()
    for name in set(arguments):
        elaborator.coordinates[name] = lerp(master_a[name], master_b[name], T)
    value = sp.expand(dsl.lower(elaborator, predicate, tuple(arguments)))
    return sp.Poly(value, T)


def preserved_for_all_t(predicate, arguments, master_a, master_b):
    """Decide whether a relation holds at every interpolation, not at samples.

    The answer is exact: the relation's polynomial in t is the zero polynomial or
    it is not, and when it is not, the interpolation values where it does hold
    are the roots, which come back with the verdict.
    """
    polynomial = relation_along(predicate, arguments, master_a, master_b)
    holds_at = {"0": bool(polynomial.eval(0) == 0), "1": bool(polynomial.eval(1) == 0)}
    if polynomial.is_zero:
        return {"predicate": predicate, "arguments": list(arguments),
                "preserved": True, "degree_in_t": 0,
                "holds_at_the_masters": holds_at,
                "decided": "the polynomial in t is identically zero, so the relation holds at "
                           "every interpolation value, exactly"}
    roots = sp.solve(sp.Eq(polynomial.as_expr(), 0), T)
    rational = sorted({str(r) for r in roots if getattr(r, "is_real", False)})
    return {"predicate": predicate, "arguments": list(arguments),
            "preserved": False, "degree_in_t": polynomial.degree(),
            "holds_at_the_masters": holds_at,
            "holds_only_at": rational,
            "polynomial_in_t": str(sp.factor(polynomial.as_expr())),
            "decided": "the polynomial in t is not the zero polynomial, so the relation fails "
                       "between the masters even when it holds at both of them"}


def compatibility_report(relations, master_a, master_b):
    """Every relation the designer names, decided along the whole axis."""
    rows = [preserved_for_all_t(predicate, arguments, master_a, master_b)
            for predicate, arguments in relations]
    return {"relations": rows,
            "preserved": sum(1 for row in rows if row["preserved"]),
            "broken_between_the_masters": sum(1 for row in rows if not row["preserved"]
                                              and all(row["holds_at_the_masters"].values())),
            "of": len(rows)}


# ---------------------------------------------------------------------------
# The structure of an outline, and matching one against another
# ---------------------------------------------------------------------------

STRUCTURAL = ("coll", "para", "perp", "cong")


def signature(points, *, predicates=STRUCTURAL, names=None):
    """Every relation of the fragment that holds of this outline, decided exactly.

    This is what a glyph is, structurally: not where its points are but which of
    them are in line, which segments are parallel, which are equal. Two outlines
    at different coordinates have the same signature exactly when the same
    relations hold, which is the sense in which they are the same letter.
    """
    names = list(names or points)
    coordinates = {name: qf.point(points[name]) for name in names}
    found = []
    for predicate in predicates:
        arity = rdsl.PREDICATE_ARITIES[predicate]
        for arguments in _tuples(names, arity):
            if qf.atom_holds(predicate, arguments, coordinates):
                found.append((predicate, tuple(arguments)))
    return sorted(set(found))


def _tuples(names, arity):
    """The argument tuples of an arity, without repeats and in one canonical order."""
    from itertools import combinations, permutations
    if arity == 3:
        return [tuple(c) for c in combinations(names, 3)]
    if arity == 4:
        seen, out = set(), []
        for first in combinations(names, 2):
            for second in combinations(names, 2):
                key = tuple(sorted((first, second)))
                if key in seen or first == second:
                    continue
                seen.add(key)
                out.append(first+second)
        return out
    return [tuple(p) for p in permutations(names, arity)]


def match(signature_a, signature_b):
    """How two signatures compare, with what each has that the other does not."""
    left, right = set(signature_a), set(signature_b)
    return {"same": left == right, "shared": len(left & right),
            "only_in_the_first": sorted(f"{p}{a}" for p, a in left-right),
            "only_in_the_second": sorted(f"{p}{a}" for p, a in right-left)}


# ---------------------------------------------------------------------------
# Motion along an arc, which interpolation cannot do
# ---------------------------------------------------------------------------

def straight_motion(start, end, steps):
    """Where interpolation takes a point: along the segment, and nowhere else."""
    return [lerp(start, end, sp.Rational(index, steps)) for index in range(steps+1)]


def arc_motion(centre, start, turns):
    """Where a sixtieth turn takes it: along the circle, exactly, in QQ(sqrt(3))."""
    coordinates = {"o": centre, "p": start}
    points, name = [qf.point(start)], "p"
    for index in range(turns):
        value, reason = qf.execute("rot60", ["o", name], coordinates, field=qf.FIELD)
        if value is None:
            raise ValueError(f"the turn was refused: {reason}")
        name = f"q{index}"
        coordinates[name] = value
        points.append(value)
    return points


def on_one_circle(centre, points):
    """Whether every point is the same distance from the centre, decided exactly."""
    coordinates = {"o": qf.point(centre)}
    for index, value in enumerate(points):
        coordinates[f"p{index}"] = qf.point(value)
    return all(qf.atom_holds("cong", ("o", "p0", "o", f"p{index}"), coordinates)
               for index in range(len(points)))
