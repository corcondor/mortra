"""The connection from constructed points to ink, checked where it could quietly go wrong.

The regression configuration is the one worked out by hand: a light at the
origin, a segment occluder from (1,-1) to (1,1), and the window [2,4]x[-5,5],
whose shadow is the trapezium with corners (2,-2), (2,2), (4,4), (4,-4) and area
12. Those numbers appear here, as the expectation of a test; they appear nowhere
in the code that draws, which is given a light, a segment and a window and
nothing else.
"""
from fractions import Fraction

import pytest

from math_os_prototype import geometry_ink as ink
from math_os_prototype import geometry_relational_dsl as rdsl

LIGHT = (Fraction(0), Fraction(0))
A = (Fraction(1), Fraction(-1))
B = (Fraction(1), Fraction(1))
WINDOW = (Fraction(2), Fraction(-5), Fraction(4), Fraction(5))


def occluded(point):
    return ink.occluded(point, LIGHT, A, B)[0]


# ---------------------------------------------------------------------------
# The region relations
# ---------------------------------------------------------------------------

def test_the_disk_relation_is_the_one_the_fragment_can_write():
    """P is the midpoint of two points of the circle exactly when P is in the disk."""
    centre, through = (Fraction(0), Fraction(0)), (Fraction(2), Fraction(0))
    assert ink.in_closed_disk((Fraction(1), Fraction(1)), centre, through)      # inside
    assert ink.in_closed_disk((Fraction(2), Fraction(0)), centre, through)      # on the circle
    assert not ink.in_closed_disk((Fraction(2), Fraction(1)), centre, through)  # outside


def test_a_point_of_the_segment_is_on_the_line_and_in_the_disk_on_it():
    a, b = (Fraction(0), Fraction(0)), (Fraction(4), Fraction(0))
    assert ink.on_closed_segment((Fraction(1), Fraction(0)), a, b)
    assert ink.on_closed_segment(a, a, b)                       # closed at the ends
    assert not ink.on_closed_segment((Fraction(5), Fraction(0)), a, b)   # on the line, past the end
    assert not ink.on_closed_segment((Fraction(1), Fraction(1)), a, b)   # off the line
    assert not ink.strictly_between(a, a, b)                    # the ends are excluded


def test_collinearity_alone_would_not_be_enough():
    """The occluder behind the light is collinear with light and point, and casts nothing."""
    behind_a, behind_b = (Fraction(-1), Fraction(-1)), (Fraction(-1), Fraction(1))
    point = (Fraction(3), Fraction(0))
    crossing, _ = rdsl.execute_primitive(
        "intersection_ll", ["l", "x", "a", "b"],
        {"l": LIGHT, "x": point, "a": behind_a, "b": behind_b})
    assert crossing == (Fraction(-1), Fraction(0))              # the lines do meet
    assert ink.on_closed_segment(crossing, behind_a, behind_b)  # on the occluder
    assert not ink.occluded(point, LIGHT, behind_a, behind_b)[0]  # but not between light and point


def test_an_occluder_beyond_the_point_casts_no_shadow_on_it():
    far_a, far_b = (Fraction(5), Fraction(-5)), (Fraction(5), Fraction(5))
    assert not ink.occluded((Fraction(3), Fraction(0)), LIGHT, far_a, far_b)[0]
    assert ink.occluded((Fraction(6), Fraction(0)), LIGHT, far_a, far_b)[0]


def test_a_ray_parallel_to_the_occluder_is_reported_as_unoccluded_not_as_an_error():
    parallel_a, parallel_b = (Fraction(1), Fraction(0)), (Fraction(2), Fraction(0))
    hit, reason = ink.occluded((Fraction(3), Fraction(1)), LIGHT, parallel_a, parallel_b)
    assert hit is False and reason


# ---------------------------------------------------------------------------
# The regression configuration
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("point,expected", [
    ((Fraction(3), Fraction(0)), True),          # straight down the middle
    ((Fraction(3), Fraction(3)), True),          # on the boundary y = x
    ((Fraction(3), Fraction(-3)), True),         # on the boundary y = -x
    ((Fraction(3), Fraction(31, 10)), False),    # just outside
    ((Fraction(2), Fraction(2)), True),          # a corner of the shadow
    ((Fraction(4), Fraction(41, 10)), False),
    ((Fraction(4), Fraction(4)), True),
])
def test_membership_matches_the_region_worked_out_by_hand(point, expected):
    assert occluded(point) is expected


def test_membership_agrees_with_the_hand_derived_inequality_over_a_grid():
    """For this configuration the shadow is -x <= y <= x; the procedure must say the same."""
    disagreements = []
    for i in range(0, 21):
        x = Fraction(2)+Fraction(2*i, 20)
        for j in range(0, 41):
            y = Fraction(-5)+Fraction(10*j, 40)
            expected = -x <= y <= x
            if occluded((x, y)) is not expected:
                disagreements.append((float(x), float(y)))
    assert not disagreements


def test_the_outline_is_constructed_and_its_area_is_twelve():
    outline = ink.shadow_polygon(LIGHT, (A, B), WINDOW)
    assert set(outline) == {(Fraction(2), Fraction(-2)), (Fraction(2), Fraction(2)),
                            (Fraction(4), Fraction(4)), (Fraction(4), Fraction(-4))}
    assert ink.polygon_area(outline) == Fraction(12)


def test_the_outline_moves_when_the_configuration_moves():
    moved = ink.shadow_polygon(LIGHT, (A, (Fraction(1), Fraction(0))), WINDOW)
    assert ink.polygon_area(moved) == Fraction(6)          # half the occluder, half the shadow
    assert set(moved) != set(ink.shadow_polygon(LIGHT, (A, B), WINDOW))


# ---------------------------------------------------------------------------
# The drawing convention
# ---------------------------------------------------------------------------

def test_the_lattice_is_evenly_spaced_and_its_disks_do_not_overlap():
    points, statistics = ink.paper_lattice(2, 2, 3)
    spacing = Fraction(1, 8)
    assert len(points) == (2*8+1)**2
    assert statistics["primitive_applications"] > 0
    assert len({xy for xy in points.values()}) == len(points)
    separated, offender = ink.pairwise_separation_ok([(k, v) for k, v in points.items()], spacing/2)
    assert separated, offender


def test_the_selection_is_deterministic_and_denser_when_asked_for_more():
    points, _ = ink.paper_lattice(2, 2, 3)
    pale = ink.select(points, lambda xy: 0.2)
    again = ink.select(points, lambda xy: 0.2)
    dark = ink.select(points, lambda xy: 0.7)
    assert [p for _, p in pale] == [p for _, p in again]
    assert len(dark) > len(pale)


def test_a_coverage_above_what_the_radius_can_reach_is_refused():
    spacing = Fraction(1, 8)
    assert ink.maximum_coverage(spacing/2, spacing) == pytest.approx(0.7853981, abs=1e-6)
    with pytest.raises(ValueError):
        ink.fill_for_coverage(0.9, spacing/2, spacing)


def test_the_written_svg_is_black_circles_of_one_radius(tmp_path):
    points, _ = ink.paper_lattice(1, 1, 3)
    chosen = ink.select(points, lambda xy: 0.5)
    path = tmp_path/"sheet.svg"
    ink.write_svg(path, chosen, Fraction(1, 16), (Fraction(0), Fraction(0), Fraction(1), Fraction(1)))
    check = ink.check_svg_is_one_radius_black_circles(path)
    assert check["one_radius"] and check["all_black"] and check["no_other_marks"]
    assert check["distinct_fills"] == ["#000000"]


def test_the_measured_coverage_follows_the_number_of_dots():
    points, _ = ink.paper_lattice(2, 2, 4)
    spacing, window = Fraction(1, 16), (Fraction(0), Fraction(0), Fraction(2), Fraction(2))
    pale = ink.coverage(ink.select(points, lambda xy: 0.2), spacing/2, window, samples=120)
    dark = ink.coverage(ink.select(points, lambda xy: 0.7), spacing/2, window, samples=120)
    assert dark["black_coverage"] > pale["black_coverage"]
    assert pale["black_coverage"] == pytest.approx(0.2*0.7853981, abs=0.02)
