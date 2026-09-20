"""Interpolation between masters, and what survives it.

The claims guarded here are the ones a type engineer would want held to: that
lerp really is this fragment's `midpoint` with a parameter, that a relation
holding at both masters can still fail between them and that the failure is
decided rather than sampled, and that a point under interpolation travels a
straight line and not an arc.
"""
from fractions import Fraction

import pytest
import sympy as sp

from math_os_prototype import geometry_drawing_program as dp
from math_os_prototype import geometry_glyph as glyph
from math_os_prototype import geometry_quadratic as qf


# ---------------------------------------------------------------------------
# Interpolation is this fragment's own operation
# ---------------------------------------------------------------------------

def test_lerp_at_a_half_is_the_fragment_s_midpoint():
    a, b = (Fraction(0), Fraction(0)), (Fraction(4), Fraction(6))
    halved = glyph.lerp(a, b, Fraction(1, 2))
    program = glyph.dyadic_lerp_program(1)
    emitted, _ = dp.run(program, {"p0": a, "p1": b}, 1)
    assert dp.exact(emitted[0]) == dp.exact(halved)


def test_a_dyadic_slider_is_reachable_by_halving_and_a_third_is_not():
    a, b = (Fraction(0), Fraction(0)), (Fraction(8), Fraction(0))
    program = glyph.dyadic_lerp_program(3)
    assert program["t"] == Fraction(1, 8)
    emitted, _ = dp.run(program, {"p0": a, "p1": b}, 1)
    assert dp.exact(emitted[0]) == (Fraction(1), Fraction(0))
    assert glyph.reachable_by_halving(Fraction(3, 8))
    assert not glyph.reachable_by_halving(Fraction(1, 3))


def test_de_casteljau_is_repeated_lerp():
    """The subdivision the search returned is three midpoints, which is three lerps."""
    a, b, c = (Fraction(0), Fraction(0)), (Fraction(4), Fraction(6)), (Fraction(8), Fraction(0))
    subdivision = {"name": "r", "params": ["p0", "p1", "p2"],
                   "body": [{"let": "v1", "op": "midpoint", "args": ["p0", "p1"]},
                            {"let": "v2", "op": "midpoint", "args": ["p1", "p2"]},
                            {"let": "v3", "op": "midpoint", "args": ["v1", "v2"]}],
                   "emit": ["v3"], "calls": []}
    emitted, _ = dp.run(subdivision, {"p0": a, "p1": b, "p2": c}, 1)
    half = Fraction(1, 2)
    by_lerp = glyph.lerp(glyph.lerp(a, b, half), glyph.lerp(b, c, half), half)
    assert dp.exact(emitted[0]) == dp.exact(by_lerp)


# ---------------------------------------------------------------------------
# What survives every interpolation, decided rather than sampled
# ---------------------------------------------------------------------------

def test_an_affine_relation_survives_because_its_polynomial_in_t_vanishes():
    """A point that is the midpoint of two others stays their midpoint throughout."""
    light = {"p": (Fraction(0), Fraction(0)), "q": (Fraction(4), Fraction(0)),
             "m": (Fraction(2), Fraction(0))}
    bold = {"p": (Fraction(1), Fraction(1)), "q": (Fraction(7), Fraction(3)),
            "m": (Fraction(4), Fraction(2))}
    verdict = glyph.preserved_for_all_t("midp", ("m", "p", "q"), light, bold)
    assert verdict["preserved"]
    assert verdict["degree_in_t"] == 0


def test_three_points_in_line_at_both_masters_can_leave_the_line_between_them():
    light = {"u": (Fraction(7), Fraction(0)), "v": (Fraction(8), Fraction(0)),
             "w": (Fraction(10), Fraction(0))}
    bold = {"u": (Fraction(7), Fraction(0)), "v": (Fraction(7), Fraction(1)),
            "w": (Fraction(7), Fraction(2))}
    verdict = glyph.preserved_for_all_t("coll", ("u", "v", "w"), light, bold)
    assert verdict["holds_at_the_masters"] == {"0": True, "1": True}
    assert not verdict["preserved"]
    assert verdict["holds_only_at"] == ["0", "1"]
    # the same symbol, or two symbols with different assumptions will not cancel
    written = sp.sympify(verdict["polynomial_in_t"], locals={"t": glyph.T})
    assert sp.simplify(written-glyph.T*(glyph.T-1)) == 0


def test_two_equal_lengths_at_both_masters_can_differ_between_them():
    light = {"u": (Fraction(7), Fraction(0)), "v": (Fraction(8), Fraction(0)),
             "x": (Fraction(10), Fraction(3)), "y": (Fraction(9), Fraction(3))}
    bold = {"u": (Fraction(7), Fraction(0)), "v": (Fraction(7), Fraction(1)),
            "x": (Fraction(10), Fraction(7)), "y": (Fraction(11), Fraction(7))}
    verdict = glyph.preserved_for_all_t("cong", ("u", "v", "x", "y"), light, bold)
    assert verdict["holds_at_the_masters"] == {"0": True, "1": True}
    assert not verdict["preserved"]
    assert verdict["holds_only_at"] == ["0", "1"]


def test_the_middle_really_does_break_it():
    """The verdict is not a formality: the relation fails at the midpoint of the axis."""
    light = {"u": (Fraction(7), Fraction(0)), "v": (Fraction(8), Fraction(0)),
             "w": (Fraction(10), Fraction(0))}
    bold = {"u": (Fraction(7), Fraction(0)), "v": (Fraction(7), Fraction(1)),
            "w": (Fraction(7), Fraction(2))}
    middle = glyph.interpolate(light, bold, Fraction(1, 2))
    assert not qf.atom_holds("coll", ("u", "v", "w"), middle)
    assert qf.atom_holds("coll", ("u", "v", "w"), glyph.interpolate(light, bold, 0))
    assert qf.atom_holds("coll", ("u", "v", "w"), glyph.interpolate(light, bold, 1))


def test_a_relation_that_does_not_hold_at_the_masters_is_reported_as_such():
    light = {"a": (Fraction(1), Fraction(0)), "b": (Fraction(2), Fraction(0)),
             "d": (Fraction(1), Fraction(6))}
    bold = {"a": (Fraction(1), Fraction(0)), "b": (Fraction(3), Fraction(0)),
            "d": (Fraction(1), Fraction(6))}
    verdict = glyph.preserved_for_all_t("coll", ("a", "d", "b"), light, bold)
    assert not verdict["preserved"]
    assert verdict["holds_at_the_masters"] == {"0": False, "1": False}


# ---------------------------------------------------------------------------
# The motion a slider cannot make
# ---------------------------------------------------------------------------

def test_a_point_under_interpolation_travels_a_line_not_an_arc():
    centre, start, end = (Fraction(0), Fraction(0)), (Fraction(3), Fraction(0)), \
        (Fraction(-3), Fraction(0))
    travelled = glyph.straight_motion(start, end, 6)
    assert travelled[0] == start and travelled[-1] == end
    assert not glyph.on_one_circle(centre, travelled)
    assert glyph.on_one_circle(centre, [start, end])      # the ends are on it; the way is not


def test_a_sixtieth_turn_travels_the_arc_exactly():
    centre, start = (Fraction(0), Fraction(0)), (Fraction(3), Fraction(0))
    travelled = glyph.arc_motion(centre, start, 6)
    assert len(travelled) == 7
    assert glyph.on_one_circle(centre, travelled)
    assert qf.point(travelled[-1]) == qf.point(start)     # six turns close the circle


# ---------------------------------------------------------------------------
# Matching one outline against another by its relations
# ---------------------------------------------------------------------------

def test_the_signature_is_the_relations_that_hold_not_the_coordinates():
    light = {"a": (Fraction(1), Fraction(0)), "b": (Fraction(2), Fraction(0)),
             "c": (Fraction(2), Fraction(6)), "d": (Fraction(1), Fraction(6))}
    bold = {"a": (Fraction(1), Fraction(0)), "b": (Fraction(3), Fraction(0)),
            "c": (Fraction(3), Fraction(6)), "d": (Fraction(1), Fraction(6))}
    left, right = glyph.signature(light), glyph.signature(bold)
    assert left and glyph.match(left, right)["same"]
    assert light != bold                                   # different coordinates, one structure


def test_a_different_shape_does_not_match():
    light = {"a": (Fraction(1), Fraction(0)), "b": (Fraction(2), Fraction(0)),
             "c": (Fraction(2), Fraction(6)), "d": (Fraction(1), Fraction(6))}
    skewed = dict(light, c=(Fraction(2), Fraction(5)))
    comparison = glyph.match(glyph.signature(light), glyph.signature(skewed))
    assert not comparison["same"]
    assert comparison["only_in_the_first"]


def test_matching_is_not_naming_a_character():
    """The signature says two outlines have the same relations. It names nothing."""
    light = {"a": (Fraction(0), Fraction(0)), "b": (Fraction(1), Fraction(0)),
             "c": (Fraction(1), Fraction(1)), "d": (Fraction(0), Fraction(1))}
    turned = {"a": (Fraction(0), Fraction(0)), "b": (Fraction(0), Fraction(1)),
              "c": (Fraction(-1), Fraction(1)), "d": (Fraction(-1), Fraction(0))}
    # a square and the same square turned a quarter: the same relations hold of both
    assert glyph.match(glyph.signature(light), glyph.signature(turned))["same"]
