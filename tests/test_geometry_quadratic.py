"""A quadratic extension, and the one operation that actually reaches it.

The point being guarded is that widening the coordinate type buys nothing: the
seven primitive witnesses are rational functions, so from rational points they
reach rational points and no more. What grows the reachable set is an operation
whose witness leaves the field, and a turn by a sixth is the smallest one. The
extension is opt-in, so the rational fragment must behave exactly as it did.
"""
from fractions import Fraction

import pytest
import sympy as sp

from math_os_prototype import geometry_quadratic as qf
from math_os_prototype import geometry_relational_dsl as rdsl

A, B = (Fraction(0), Fraction(0)), (Fraction(1), Fraction(0))
TWO_POINTS = {"a": A, "b": B}


# ---------------------------------------------------------------------------
# The rational fragment is untouched
# ---------------------------------------------------------------------------

def test_the_turn_is_refused_unless_the_field_is_asked_for():
    value, reason = qf.execute("rot60", ["a", "b"], TWO_POINTS)
    assert value is None
    assert qf.FIELD in reason


def test_without_the_field_a_primitive_behaves_exactly_as_before():
    for family in ("midpoint", "mirror"):
        theirs = rdsl.execute_primitive(family, ["a", "b"], TWO_POINTS)
        ours = qf.execute(family, ["a", "b"], TWO_POINTS)
        assert ours == theirs


def test_from_two_points_the_rational_primitives_stay_on_their_line():
    """Every one of them commutes with the reflection that fixes both inputs."""
    reached = []
    for family, arity in ((f, len(rdsl.primitive_contracts()[f]["params"]))
                          for f in rdsl.primitive_contracts()):
        if arity != 2:
            continue
        for arguments in (["a", "b"], ["b", "a"]):
            value, _ = rdsl.execute_primitive(family, arguments, TWO_POINTS)
            if value is not None:
                reached.append(value)
    assert reached
    assert all(sp.simplify(point[1]) == 0 for point in reached)


# ---------------------------------------------------------------------------
# What the turn reaches
# ---------------------------------------------------------------------------

def test_a_sixth_turn_lands_on_the_equilateral_point():
    value, reason = qf.execute("rot60", ["a", "b"], TWO_POINTS, field=qf.FIELD)
    assert reason is None
    assert sp.simplify(value[0]-sp.Rational(1, 2)) == 0
    assert sp.simplify(value[1]-sp.sqrt(3)/2) == 0
    assert not sp.sympify(value[1]).is_Rational          # it left the rationals


def test_what_the_turn_guarantees_is_decided_exactly():
    value, _ = qf.execute("rot60", ["a", "b"], TWO_POINTS, field=qf.FIELD)
    coordinates = dict(TWO_POINTS, c=value)
    assert qf.atom_holds("cong", ("a", "b", "a", "c"), coordinates)
    assert qf.atom_holds("cong", ("b", "c", "a", "b"), coordinates)
    assert qf.atom_holds("ncoll", ("a", "b", "c"), coordinates)
    assert not qf.atom_holds("coll", ("a", "b", "c"), coordinates)


def test_the_two_turns_are_the_two_orientations():
    one, _ = qf.execute("rot60", ["a", "b"], TWO_POINTS, field=qf.FIELD)
    other, _ = qf.execute("rot300", ["a", "b"], TWO_POINTS, field=qf.FIELD)
    assert sp.simplify(one[0]-other[0]) == 0
    assert sp.simplify(one[1]+other[1]) == 0            # mirror images in the line ab


def test_six_turns_close_into_a_regular_hexagon():
    coordinates = {"o": (Fraction(0), Fraction(0)), "p0": (Fraction(1), Fraction(0))}
    names = ["p0"]
    for index in range(1, 6):
        value, reason = qf.execute("rot60", ["o", names[-1]], coordinates, field=qf.FIELD)
        assert reason is None
        coordinates[f"p{index}"] = value
        names.append(f"p{index}")
    assert len(names) == 6
    closes, _ = qf.execute("rot60", ["o", names[-1]], coordinates, field=qf.FIELD)
    assert qf.point(closes) == qf.point(coordinates["p0"])
    assert all(qf.atom_holds("cong", ("o", "p0", "o", name), coordinates) for name in names)
    assert all(qf.atom_holds("cong", (names[i], names[i+1], "p0", "p1"), coordinates)
               for i in range(len(names)-1))


def test_the_coordinates_stay_in_the_field():
    coordinates = {"o": (Fraction(0), Fraction(0)), "p": (Fraction(1), Fraction(0))}
    value, _ = qf.execute("rot60", ["o", "p"], coordinates, field=qf.FIELD)
    coordinates["q"] = value
    for family in ("midpoint", "mirror"):
        moved, reason = qf.execute(family, ["p", "q"], coordinates, field=qf.FIELD)
        assert reason is None, reason
        assert qf.in_field(moved)


# ---------------------------------------------------------------------------
# What it does not reach, said plainly
# ---------------------------------------------------------------------------

def test_a_right_angle_is_still_out_of_reach():
    """Two sixth-turns make a third of a turn, not a quarter. QQ(sqrt3) has no sqrt2."""
    coordinates = dict(TWO_POINTS)
    once, _ = qf.execute("rot60", ["a", "b"], coordinates, field=qf.FIELD)
    coordinates["c"] = once
    twice, _ = qf.execute("rot60", ["a", "c"], coordinates, field=qf.FIELD)
    coordinates["d"] = twice
    assert not qf.atom_holds("perp", ("a", "b", "a", "d"), coordinates)
    assert qf.element(sp.sqrt(2)) is None                # sqrt2 is not in the field


def test_a_coordinate_outside_the_field_is_refused_rather_than_approximated():
    coordinates = {"a": (Fraction(0), Fraction(0)), "b": (sp.sqrt(2), Fraction(0))}
    value, reason = qf.execute("rot60", ["a", "b"], coordinates, field=qf.FIELD)
    assert value is None and "outside the field" in reason


def test_the_contract_table_only_offers_the_turns_when_the_field_is_asked_for():
    assert set(qf.contracts()) == set(rdsl.primitive_contracts())
    with_field = qf.contracts(field=qf.FIELD)
    assert set(with_field)-set(rdsl.primitive_contracts()) == {"rot60", "rot300"}
    assert with_field["rot60"]["post"]
