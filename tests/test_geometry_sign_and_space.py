"""The sign kernel, the letters built from three points, and the fragment in space.

What is guarded here is the line between a decision and a certificate. The
decision is a comparison and always will be; the certificate is an equation with
a witness, and the tests check that the witness exists, that checking it uses no
order, and that it is refused exactly where the theorem stops -- one step outside
QQ, where a positive element need not be a sum of squares at all.

The three-layer separation around the disk has a test of its own, because it is
the place the kernel could most easily lie: a point can be inside the disk and
have no rational pair of circle points witnessing it. Membership is still
decided; only the illustration leaves QQ.
"""
from fractions import Fraction

import pytest
import sympy as sp

from math_os_prototype import geometry_alphabet as alphabet
from math_os_prototype import geometry_letter_construction as construction
from math_os_prototype import geometry_sign as sign
from math_os_prototype import geometry_space as space

F = Fraction


# ---------------------------------------------------------------------------
# The arithmetic kernel
# ---------------------------------------------------------------------------

def test_the_sign_is_exact_and_an_irrational_is_refused():
    assert sign.sign(F(-3, 7)) == -1
    assert sign.sign(0) == 0
    assert sign.sign(F(5)) == 1
    with pytest.raises(ValueError):
        sign.sign(sp.sqrt(3))


@pytest.mark.parametrize("value", [F(0), F(1), F(2), F(3), F(7), F(1, 2), F(7, 9), F(23, 5),
                                   F(169, 4), F(1000003)])
def test_every_non_negative_rational_is_a_sum_of_at_most_four_squares(value):
    report = sign.certify_nonnegative(value)
    assert report["holds"] and report["certified"]
    assert report["how_many"] <= 4
    # the check itself: an addition and an equality, and no order anywhere in it
    assert sum(F(s)**2 for s in report["squares"]) == value


def test_four_is_sharp_and_three_is_the_cube_diagonal():
    assert sign.realisable_in_dimension(F(7)) == 4
    assert sign.realisable_in_dimension(F(3)) == 3      # sqrt 3, the unit cube's diagonal
    assert sign.realisable_in_dimension(F(2)) == 2      # the unit square's diagonal
    assert sign.realisable_in_dimension(F(9)) == 1


@pytest.mark.parametrize("value", [F(1), F(2), F(3), F(5), F(6), F(7), F(9, 4), F(23, 5), F(50)])
def test_the_two_square_criterion_agrees_with_the_search(value):
    assert sign.two_squares_criterion(value) == (sign.realisable_in_dimension(value) <= 2)


def test_a_negative_value_has_no_certificate():
    report = sign.certify_nonnegative(F(-1))
    assert not report["holds"] and not report["certified"]


def test_a_value_too_large_to_search_still_has_its_sign():
    report = sign.certify_nonnegative(F(10**14), limit=10**6)
    assert report["holds"] and not report["certified"]
    assert "the sign is still decided" in report["why"].lower()


# ---------------------------------------------------------------------------
# The geometric relations, as constructions
# ---------------------------------------------------------------------------

def test_the_witness_implies_membership_by_an_identity():
    report = sign.witness_implies_membership()
    assert report["certified"]


def test_a_point_inside_the_disk_can_have_no_rational_witness():
    """Membership is decided by the four squares; the pair U, V only illustrates it."""
    report = sign.witness_in_closed_disk((F(1), F(1)), (F(0), F(0)), (F(2), F(1)))
    assert report["holds"]                                  # 5 - 2 = 3 >= 0
    assert report["the_decision"]["certified"]              # and the decision is certified
    assert not report["witness_is_rational"]                # 3 * 2 = 6 is no square
    assert report["witness_field"].startswith("QQ(sqrt")
    assert all(report["atoms"].values())                    # the three atoms still hold


def test_the_disk_witness_is_rational_when_the_ratio_is_a_square():
    report = sign.witness_in_closed_disk((F(1), F(1)), (F(0), F(0)), (F(2), F(0)))
    assert report["holds"] and report["certified"] and report["witness_is_rational"]
    assert all(report["atoms"].values())


def test_a_point_outside_the_disk_is_refused_with_the_reason():
    report = sign.witness_in_closed_disk((F(9), F(0)), (F(0), F(0)), (F(2), F(0)))
    assert not report["holds"] and not report["certified"]
    assert "outside" in report["why"]


def test_an_inked_cell_has_a_rational_certificate_and_the_foot_is_why():
    near = sign.certify_within_of_segment((F(5, 2), F(1, 2)), (F(0), F(0)), (F(10), F(0)), F(1))
    assert near["holds"] and near["certified"]
    assert near["Q"] == ["5/2", "0"]                        # the foot, by the fragment's `foot`
    far = sign.certify_within_of_segment((F(5, 2), F(5)), (F(0), F(0)), (F(10), F(0)), F(1))
    assert not far["holds"]
    assert sign.certify_the_foot_is_nearest()["certified"]


def test_the_shadow_has_a_witness_and_the_light_has_none():
    dark = sign.certify_occluded((F(5), F(0)), (F(0), F(0)), (F(2), F(-1)), (F(2), F(1)))
    assert dark["holds"] and dark["certified"] and dark["P"] == ["2", "0"]
    lit = sign.certify_occluded((F(5), F(5)), (F(0), F(0)), (F(2), F(-1)), (F(2), F(1)))
    assert not lit["holds"]


def test_between_and_same_side():
    assert sign.certify_between((F(0), F(0)), (F(1), F(1)), (F(3), F(3)))["holds"]
    assert not sign.certify_between((F(0), F(0)), (F(4), F(4)), (F(3), F(3)))["holds"]
    assert sign.certify_same_side((F(1), F(1)), (F(2), F(3)), (F(0), F(0)), (F(5), F(0)))["holds"]
    assert not sign.certify_same_side((F(1), F(1)), (F(2), F(-3)),
                                      (F(0), F(0)), (F(5), F(0)))["holds"]


# ---------------------------------------------------------------------------
# The universal layer
# ---------------------------------------------------------------------------

def test_cauchy_schwarz_in_the_plane_is_one_square():
    a, b, c, d = sp.symbols("a b c d", real=True)
    report = sign.sum_of_squares((a**2+b**2)*(c**2+d**2)-(a*c+b*d)**2, [a, b, c, d])
    assert report["certified"]
    assert len(report["squares"]) == 1


def test_lagranges_identity_in_space_is_the_cross_product():
    a, b, c, d, e, f = sp.symbols("a b c d e f", real=True)
    report = sign.sum_of_squares((a**2+b**2+c**2)*(d**2+e**2+f**2)-(a*d+b*e+c*f)**2,
                                 [a, b, c, d, e, f])
    assert report["certified"]
    assert len(report["squares"]) == 3         # the three components of the cross product


def test_a_wrong_certificate_is_rejected():
    a, b = sp.symbols("a b", real=True)
    assert not sign.verify_sum_of_squares(a**2+b**2, [(1, a), (1, a)], [a, b])["certified"]
    assert sign.verify_sum_of_squares(a**2+b**2, [(1, a), (1, b)], [a, b])["certified"]


# ---------------------------------------------------------------------------
# Where an ordering decision was actually wrong, and now is not
# ---------------------------------------------------------------------------

def test_a_light_on_the_occluders_own_line_is_still_blocked_by_it():
    """`intersection_ll` refuses two coincident lines, and that is not "no shadow"."""
    from math_os_prototype import geometry_ink as ink

    light, a, b = (F(0), F(0)), (F(2), F(0)), (F(4), F(0))
    assert ink.occluded((F(6), F(0)), light, a, b)[0]          # beyond the occluder: dark
    assert not ink.occluded((F(1), F(0)), light, a, b)[0]      # short of it: lit
    assert ink.occluded((F(3), F(0)), light, a, b)[0]          # inside its span: dark


def test_the_shadow_outline_is_ordered_by_signs_and_not_by_an_angle_in_floats():
    from math_os_prototype import geometry_ink as ink

    corners = ink.shadow_polygon((F(0), F(0)), ((F(1), F(-10)), (F(1), F(10))),
                                 (F(1, 2), F(-1), F(3, 2), F(1)))
    assert len(corners) == 4
    assert ink.polygon_area(corners) == 1                      # the frozen regression
    assert all(isinstance(v, Fraction) or v.is_Rational for p in corners for v in p)


def test_a_skeleton_branch_is_kept_or_cut_by_exact_arithmetic():
    """The length that decides a branch used to go through a float square root."""
    from math_os_prototype import geometry_raster as raster

    centre = raster.centre_of({(0, 0), (1, 0), (0, 1)})
    assert all(isinstance(v, Fraction) for v in centre)
    nodes = [{(0, 0)}, {(9, 0)}, {(9, 3)}, {(16, 0)}]
    edges = [(0, 1, [(i, 0) for i in range(10)]),
             (1, 2, [(9, 1), (9, 2), (9, 3)]),
             (1, 3, [(i, 0) for i in range(9, 17)])]
    kept = raster.prune(nodes, list(edges), 4)[1]
    assert len(kept) == 2                                      # the three-pixel stub goes


# ---------------------------------------------------------------------------
# The letters, built from three points
# ---------------------------------------------------------------------------

def test_every_letter_coordinate_is_the_output_of_a_primitive():
    report = construction.constructed(alphabet.ROMAN)
    assert report["agrees_with_the_table"]
    assert report["steps"] < 100
    assert set(report["seeds"]) == {"o", "ex", "ey"}
    assert all(step["op"] in ("midpoint", "mirror") for step in report["program"])


def test_the_narrow_style_is_built_from_the_same_three_points():
    assert construction.constructed(alphabet.NARROW)["agrees_with_the_table"]


def test_the_program_replays_from_the_seeds_alone():
    names, program, built = construction.build_lattice(6, 6)
    again = construction.replay(program)
    for index, value in built.items():
        assert again[index] == value


def test_from_two_points_nothing_ever_leaves_their_line():
    report = construction.stays_on_the_line(rounds=2, limit=200)
    assert not report["left_the_line"] and report["off_the_line"] == []


# ---------------------------------------------------------------------------
# Space
# ---------------------------------------------------------------------------

def test_the_three_dimensional_predicates():
    c = {"a": (0, 0, 0), "b": (1, 0, 0), "c": (0, 1, 0), "d": (0, 0, 1),
         "m": (F(1, 2), 0, 0)}
    assert space.atom_holds("midp", ("m", "a", "b"), c)
    assert space.atom_holds("coll", ("a", "b", "m"), c)
    assert not space.atom_holds("coll", ("a", "b", "c"), c)
    assert space.atom_holds("coplanar", ("a", "b", "c", "m"), c)
    assert not space.atom_holds("coplanar", ("a", "b", "c", "d"), c)
    assert space.atom_holds("perp", ("a", "b", "a", "c"), c)
    assert space.atom_holds("cong", ("a", "b", "a", "c"), c)


def test_perpendicular_does_not_mean_the_lines_meet():
    """A pitfall of three dimensions, written down so nobody imports a plane theorem."""
    c = {"a": (0, 0, 0), "b": (1, 0, 0), "c": (0, 0, 1), "d": (0, 1, 1)}
    assert space.atom_holds("perp", ("a", "b", "c", "d"), c)
    assert not space.atom_holds("coplanar", ("a", "b", "c", "d"), c)   # they are skew


def test_every_primitive_produces_a_rational_point_or_a_reason():
    c = {"a": (0, 0, 0), "b": (1, 0, 0), "c": (0, 1, 0), "d": (0, 0, 1), "m": (F(1, 2), 0, 0)}
    for family, arguments in (("midpoint", ["a", "b"]), ("mirror", ["a", "b"]),
                              ("centroid", ["a", "b", "c"]), ("foot_line", ["d", "a", "b"]),
                              ("foot_plane", ["d", "a", "b", "c"]),
                              ("reflect_plane", ["d", "a", "b", "c"]),
                              ("intersection_lp", ["d", "m", "a", "b", "c"]),
                              ("circumcentre", ["a", "b", "c"])):
        value, reason = space.execute(family, arguments, c)
        assert value is not None, (family, reason)
        assert all(isinstance(v, Fraction) or v.is_Rational for v in value)
    refused, reason = space.execute("circumcentre", ["a", "b", "m"], c)
    assert refused is None and "ncoll" in reason


def test_from_three_points_nothing_ever_leaves_their_plane():
    report = space.escapes_the_plane([(0, 0, 0), (1, 0, 0), (0, 1, 0)], rounds=2, limit=200)
    assert not report["escaped"] and report["off_the_plane"] == []
    assert report["points_built"] > 20


def test_the_equilateral_triangle_the_plane_cannot_have():
    report = space.the_rational_equilateral_triangle()
    assert report["rational"] and report["all_edges_congruent"]
    assert report["squared_edge"] == "2"
    assert sign.realisable_in_dimension(F(3)) == 3     # and sqrt 3 is why the plane could not


@pytest.mark.parametrize("name", ["tetrahedron", "cube", "octahedron"])
def test_three_solids_are_rational_regular_and_certified_convex(name):
    vertices, faces = space.SOLIDS[name]()
    assert space.is_rational(vertices)
    assert space.certify_regular(vertices)["all_congruent"]
    convex = space.certify_convex(vertices, faces)
    assert convex["convex"]
    assert all(face["all_on_one_side"] for face in convex["faces"])


def test_the_icosahedron_leaves_the_rationals_and_the_reason_is_a_fifth_turn():
    vertices, _ = space.icosahedron()
    assert not space.is_rational(vertices)
    assert space.certify_regular(vertices)["all_congruent"]
    report = space.no_rotation_of_order_five()
    assert not report["any_of_them_rational"]
    assert not space.the_pentagon_argument()["any_rational_root"]


def test_inside_a_tetrahedron_is_four_certificates_and_no_division():
    inside = space.inside_tetrahedron((F(1, 4), F(1, 4), F(1, 4)),
                                      (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    assert inside["holds"] and inside["certified"]
    assert len(inside["certificates"]) == 4
    outside = space.inside_tetrahedron((F(2), F(2), F(2)),
                                       (0, 0, 0), (1, 0, 0), (0, 1, 0), (0, 0, 1))
    assert not outside["holds"]


def test_an_eye_far_along_an_axis_sees_exactly_one_face_of_the_cube():
    vertices, faces = space.cube()
    seen = space.visible_faces(vertices, faces, (10, 0, 0))
    assert seen["visible"] == 1 and seen["of"] == 6
