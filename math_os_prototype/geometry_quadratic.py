"""A quadratic extension of the coordinate field, and the one operation that reaches it.

The plane fragment works over the rationals. Every one of its seven primitives
has a witness that is a rational function of its inputs, so from rational points
it only ever reaches rational points — and `execute_primitive` says so, refusing
a non-rational output as `undefined_exact_witness`
(`geometry_relational_dsl.py:385`). Widening the coordinate type therefore buys
nothing on its own: the reachable set does not grow by allowing a larger field,
it grows by adding an operation whose witness leaves the old one.

That operation is a sixtieth turn:

    rot60(centre, source) = centre + R (source - centre),
        R = [[1/2, -s/2], [s/2, 1/2]],   s*s = 3,  s > 0

Its witness is linear over QQ(s), with no denominator and no degeneracy, so it is
total. It has two labels, the turn one way and the turn the other, and they are
conjugate under s -> -s: that label is a choice of orientation, which is the
thing the seven rational primitives cannot make. They all commute with a
reflection, so from two points they only ever reach that line; `rot60` does not,
and that is what lets a square be built on a segment and a hexagon on an edge.

What it guarantees is certifiable and is the point of it: the centre, the source
and the image are the corners of an equilateral triangle.

Nothing here changes the rational fragment. The extension is asked for: with no
field named, every function in this module behaves as the fragment always did.
"""
from __future__ import annotations

from collections import Counter
from fractions import Fraction

import sympy as sp

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_semantic_dsl as dsl

# The one irrationality admitted. Everything reachable lies in QQ(GENERATOR).
GENERATOR = sp.sqrt(3)
FIELD = "QQ(sqrt(3))"

ROTATIONS = {"rot60": 1, "rot300": -1}
ARITY = {"rot60": 2, "rot300": 2}

#: What a sixtieth turn guarantees, for every configuration, over QQ(s)(inputs).
#: `v` is the image, `f0` the centre and `f1` the source.
POST = {"rot60": [("cong", ("f0", "f1", "f0", "v")), ("cong", ("f1", "v", "f0", "f1"))],
        "rot300": [("cong", ("f0", "f1", "f0", "v")), ("cong", ("f1", "v", "f0", "f1"))]}


def element(value):
    """A coordinate of the extension, in a canonical form, or None if it is outside it."""
    expression = sp.nsimplify(sp.sympify(value)) if isinstance(value, str) else sp.sympify(value)
    expression = sp.expand(sp.radsimp(sp.expand(expression)))
    if expression.is_Rational:
        return expression
    coefficients = sp.Poly(expression, GENERATOR).all_coeffs() \
        if expression.has(GENERATOR) else None
    if coefficients is None or len(coefficients) > 2 or \
            not all(c.is_Rational for c in coefficients):
        return None
    return expression


def point(value):
    """A pair of coordinates of the extension, or None when either leaves it."""
    parts = tuple(element(v) for v in value)
    return None if any(p is None for p in parts) else parts


def in_field(value):
    return point(value) is not None


def is_rational(value):
    return all(sp.sympify(v).is_Rational for v in value)


def as_floats(value):
    """The point as floats, for a pixel position. This is the only inexact step."""
    return tuple(float(sp.N(v, 30)) for v in value)


def rotate(centre, source, turn):
    """centre + R (source - centre), exactly, in QQ(s)."""
    (cx, cy), (sx, sy) = point(centre), point(source)
    dx, dy = sp.expand(sx-cx), sp.expand(sy-cy)
    half, wing = sp.Rational(1, 2), turn*GENERATOR/2
    return (sp.expand(cx+half*dx-wing*dy), sp.expand(cy+wing*dx+half*dy))


def contracts(*, field=None):
    """The fragment's primitives, and the turns when the extension is asked for."""
    table = {family: {"params": list(contract["params"]), "arity": len(contract["params"]),
                      "kind": "primitive"}
             for family, contract in rdsl.primitive_contracts().items()}
    if field == FIELD:
        for family in ROTATIONS:
            table[family] = {"params": ["f0", "f1"], "arity": 2, "kind": "turn",
                             "post": [[atom, list(args)] for atom, args in POST[family]]}
    return table


def execute(family, arguments, coordinates, *, field=None, stats=None):
    """One step, over the rationals or over the extension, with the field asked for.

    With no field named this is `execute_primitive` and refuses exactly what it
    always refused. With the extension named, a turn may be applied and a
    coordinate of QQ(s) is accepted where a rational was demanded.
    """
    stats = stats if stats is not None else Counter()
    if family in ROTATIONS:
        if field != FIELD:
            return None, f"{family} needs the field {FIELD}, which was not asked for"
        stats["turns"] += 1
        centre, source = (coordinates[name] for name in arguments)
        if point(centre) is None or point(source) is None:
            return None, "a coordinate is outside the field"
        if point(centre) == point(source):
            return None, "primitive_degeneracy"
        return rotate(centre, source, ROTATIONS[family]), None
    if field != FIELD:
        return rdsl.execute_primitive(family, list(arguments), coordinates, stats)
    return _execute_over_field(family, arguments, coordinates, stats)


def _execute_over_field(family, arguments, coordinates, stats):
    """The fragment's own primitive, with coordinates allowed in QQ(s).

    This repeats what `execute_primitive` does — the applicability atoms, the
    denominators, the witness — and differs in one place only: a coordinate of
    the extension is accepted where `is_Rational` was demanded.
    """
    contract = rdsl.primitive_contracts()[family]
    if len(arguments) != len(contract["params"]):
        return None, "arity"
    binding = dict(zip(contract["params"], arguments, strict=True))
    for requirement in contract["pre"]:
        names = tuple(binding[a] for a in requirement["args"])
        stats["guard_checks"] += 1
        if not rdsl.atom_holds(requirement["atom"], names, coordinates, stats):
            return None, f"unproved_applicability:{requirement['atom']}"
    elaborator = gc._JGEXElaborator()
    for name in arguments:
        given = point(coordinates[name])
        if given is None:
            return None, "a coordinate is outside the field"
        elaborator.coordinates[name] = given
    dsl.FRAGMENT.primitive(elaborator, family, "__out", list(arguments))
    if any(sp.simplify(d) == 0 for d in elaborator.denominators):
        return None, "primitive_degeneracy"
    xy = tuple(sp.expand(sp.radsimp(sp.cancel(v))) for v in elaborator.coordinates["__out"])
    result = point(xy)
    if result is None:
        return None, "the witness left the field"
    stats["primitive_applications"] += 1
    return result, None


def atom_holds(predicate, arguments, coordinates, stats=None):
    """Decide a relation at coordinates of the extension, exactly.

    The predicate's polynomial is the fragment's own; what changes is that it is
    evaluated in QQ(s) instead of QQ, and zero is decided by `simplify` rather
    than by a rational comparison.
    """
    stats = stats if stats is not None else Counter()
    needed = {name: coordinates[name] for name in set(arguments)}
    if all(is_rational(value) for value in needed.values()):
        # only the points the atom names go through: a coordinate of the
        # extension elsewhere in the dictionary would be converted and refused
        return rdsl.atom_holds(predicate, tuple(arguments), needed, stats)
    elaborator = gc._JGEXElaborator()
    for name, value in needed.items():
        given = point(value)
        if given is None:
            raise ValueError(f"{name} is outside {FIELD}")
        elaborator.coordinates[name] = given
    stats["relation_tests"] += 1
    lowered = sp.simplify(sp.expand(dsl.lower(elaborator, predicate, tuple(arguments))))
    # an equality predicate holds when its polynomial vanishes; diff, ncoll and
    # npara are the non-vanishing ones and hold when it does not
    if predicate in rdsl.NONZERO_PREDICATES:
        return lowered != 0
    return lowered == 0


def equilateral_on(a, b, *, turn=1):
    """The third corner of an equilateral triangle on the segment, as a construction."""
    return rotate(a, b, turn)
