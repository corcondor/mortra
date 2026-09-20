"""Reading letters out of raster images, and the line between measuring and deciding.

The claims guarded here are the ones the work stands on: that the measurement
layer does what it says on ink it has never seen, that the corners are
constructed by the fragment rather than read off the pixels, that a description
made of relations is invariant under the changes a drawing can undergo, that the
rotation theorem really does bite when the frame is removed, and that the
alphabet is read -- at held-out sizes, with a different nib, with a ragged edge,
and in a second style no reference was built from.

Two of these tests exist to stop a particular kind of dishonesty. One asserts
that nothing in the reading path imports OpenCV, tesseract or a font; the
repository contains a cv2 template reader and a pytesseract call, and neither
may creep in. The other asserts that the control -- the same recovery compared
by coordinates instead of by relations -- fails where the reader succeeds,
because if it did not, the fragment would be decoration.
"""
from fractions import Fraction
import sys

import pytest

from math_os_prototype import geometry_alphabet as alphabet
from math_os_prototype import geometry_raster as raster
from math_os_prototype import geometry_reading as reading
from math_os_prototype import geometry_relational_dsl as rdsl

F = Fraction


# ---------------------------------------------------------------------------
# The measurement layer: counting, morphology, and nothing claimed
# ---------------------------------------------------------------------------

def test_a_cell_is_inked_exactly_when_its_centre_is_within_the_radius():
    strokes = [((F(5), F(5)), (F(25), F(5)))]
    bitmap = raster.render(strokes, F(3, 2), 32, 12)
    assert (10, 5) in bitmap.black                      # centre (10.5, 5.5) is 0.5 away
    assert (10, 6) in bitmap.black                      # (10.5, 6.5) is 1.5 away
    assert (10, 7) not in bitmap.black                  # (10.5, 7.5) is 2.5 away
    assert (2, 5) not in bitmap.black                   # past the end by more than r


def test_two_strokes_that_do_not_touch_are_two_components():
    apart = raster.render([((F(2), F(2)), (F(2), F(20))), ((F(20), F(2)), (F(20), F(20)))],
                          F(1), 24, 24)
    assert len(raster.components(apart)) == 2


@pytest.mark.parametrize("letter,wanted", [("O", 1), ("B", 2), ("C", 0), ("R", 1), ("I", 0)])
def test_the_hole_count_is_what_the_letter_encloses(letter, wanted):
    bitmap = alphabet.draw(alphabet.ROMAN[letter], height=48, radius=F(3, 2))
    body = raster.components(bitmap)[0]
    assert raster.holes(body, bitmap.width, bitmap.height) == wanted


def test_every_letter_of_both_styles_is_one_connected_piece():
    for style in (alphabet.ROMAN, alphabet.NARROW):
        for letter, strokes in style.items():
            for pen in ("round", "square"):
                bitmap = alphabet.draw(strokes, height=48, radius=F(3, 2), pen=pen)
                assert len(raster.components(bitmap)) == 1, (letter, pen)


def test_a_thick_stroke_thins_to_one_pixel_wide():
    bitmap = raster.render([((F(4), F(10)), (F(28), F(10)))], F(5, 2), 32, 20)
    skeleton = raster.thin(bitmap.black)
    rows = {j for _, j in skeleton}
    assert len(rows) == 1
    assert len(skeleton) < bitmap.count()//3


def test_a_staircase_pixel_is_interior_although_it_has_three_neighbours():
    """The reason the graph is built on the connectivity number and not on a count."""
    staircase = {(0, 0), (1, 0), (1, 1), (2, 1), (2, 2)}
    assert raster._degree((1, 1), staircase) == 4        # a plain count says 'branch'
    assert raster.crossings((1, 1), staircase) == 2
    assert raster.crossings((0, 0), staircase) == 1


def test_a_crossing_gives_one_node_of_degree_four_and_four_ends():
    bitmap = alphabet.draw(alphabet.ROMAN["X"], height=72, radius=F(5, 2))
    body = raster.components(bitmap)[0]
    nodes, edges = raster.skeleton_graph(raster.thin(body), junction_radius=2)
    nodes, edges = raster.prune(nodes, edges, 4)
    nodes, edges = raster.dissolve(nodes, edges)
    degrees = {}
    for a, b, _ in edges:
        degrees[a] = degrees.get(a, 0)+1
        degrees[b] = degrees.get(b, 0)+1
    assert sorted(degrees.values()) == [1, 1, 1, 1, 4]


def test_pruning_removes_a_spur_and_keeps_a_short_real_arm():
    nodes = [{(0, 0)}, {(10, 0)}, {(11, 2)}, {(16, 0)}]
    edges = [(0, 1, [(i, 0) for i in range(11)]),
             (1, 2, [(10, 1), (11, 2)]),                       # a two-pixel spur
             (1, 3, [(i, 0) for i in range(10, 17)])]          # a six-pixel arm
    kept = raster.prune(nodes, list(edges), 4)[1]
    assert len(kept) == 2
    assert all(len(chain) > 2 for _, _, chain in kept)


def test_the_polyline_keeps_the_corner_and_nothing_else():
    chain = [(i, 0) for i in range(10)]+[(9, j) for j in range(1, 10)]
    assert raster.simplify(chain, 1) == [(0, 0), (9, 0), (9, 9)]


def test_a_straight_piece_is_taken_from_inside_itself():
    chain = [(i, 0) for i in range(10)]+[(9, j) for j in range(1, 10)]
    pieces = raster.straight_pieces(chain, 1, margin=2)
    assert len(pieces) == 2
    (first_a, first_b, _), (second_a, second_b, _) = pieces
    assert first_a == (2, 0) and first_b == (7, 0)             # the margin was dropped
    assert second_b == (9, 7)


def test_the_square_nib_draws_a_different_picture_of_the_same_letter():
    strokes = alphabet.ROMAN["A"]
    round_pen = alphabet.draw(strokes, height=48, radius=F(3, 2), pen="round")
    square_pen = alphabet.draw(strokes, height=48, radius=F(3, 2), pen="square")
    assert round_pen.black != square_pen.black
    assert square_pen.count() > round_pen.count()              # a square reaches the corners
    assert round_pen.black <= square_pen.black


def test_the_ragged_edge_is_the_same_every_run_and_only_touches_the_edge():
    bitmap = alphabet.draw(alphabet.ROMAN["H"], height=48, radius=F(5, 2))
    once = raster.speckle(bitmap, seed=3, rate=4)
    twice = raster.speckle(bitmap, seed=3, rate=4)
    assert once.black == twice.black
    assert once.black != bitmap.black
    interior = {c for c in bitmap.black
                if all((c[0]+d[0], c[1]+d[1]) in bitmap.black for d in raster.NEIGHBOURS_8)}
    assert interior <= once.black


# ---------------------------------------------------------------------------
# The fragment's part: corners are constructed, not measured
# ---------------------------------------------------------------------------

def test_a_corner_is_where_two_lines_meet_and_parallel_lines_are_refused():
    meeting, _ = reading._meet(((F(0), F(0)), (F(4), F(0))), ((F(3), F(-2)), (F(3), F(5))))
    assert meeting == (F(3), F(0))
    refused, reason = reading._meet(((F(0), F(0)), (F(4), F(0))),
                                    ((F(0), F(1)), (F(4), F(1))))
    assert refused is None and "applicability" in reason


def test_the_crossing_of_X_is_constructed_and_is_no_stroke_end():
    glyph = reading.arrangement(alphabet.ROMAN["X"])
    written = {tuple(map(Fraction, point))
               for chain in alphabet.ROMAN["X"] for point in chain}
    centre = [v for v, d in zip(glyph.vertices, glyph.degrees()) if d == 4]
    assert len(centre) == 1
    assert centre[0] not in written                    # it was produced by intersection_ll


def test_coll_dissolves_a_corner_that_is_not_one_and_keeps_one_that_is():
    straight = [(F(0), F(0)), (F(2), F(0)), (F(5), F(0))]
    vertices, edges, dissolved = reading.straighten(straight, [(0, 1), (1, 2)])
    assert dissolved == 1 and len(vertices) == 2 and edges == [(0, 1)]
    bent = [(F(0), F(0)), (F(2), F(0)), (F(2), F(5))]
    vertices, edges, dissolved = reading.straighten(bent, [(0, 1), (1, 2)])
    assert dissolved == 0 and len(vertices) == 3


def test_the_frame_relations_are_the_fragments_own_atoms():
    glyph = reading.arrangement(alphabet.ROMAN["T"])
    coordinates = glyph.coordinates()
    on_the_cap = [name for name in coordinates
                  if name.startswith("v")
                  and rdsl.atom_holds("coll", ("__cap0", "__cap1", name), coordinates)]
    assert len(on_the_cap) == 3                        # T's bar has three corners on it


# ---------------------------------------------------------------------------
# What a description made of relations is invariant under
# ---------------------------------------------------------------------------

def test_a_description_does_not_change_when_the_letter_is_moved_or_enlarged():
    small = reading.recover(alphabet.draw(alphabet.ROMAN["E"], height=48, radius=F(3, 2),
                                          at=(2, 2)))
    large = reading.recover(alphabet.draw(alphabet.ROMAN["E"], height=96, radius=F(3),
                                          at=(17, 5)))
    assert reading.description(small) == reading.description(large)


def test_without_the_frame_N_and_Z_have_the_same_description():
    """coll, para, perp and cong are similarity-invariant; Z is N turned a quarter."""
    n = reading.arrangement(alphabet.ROMAN["N"])
    z = reading.arrangement(alphabet.ROMAN["Z"])
    assert reading.description(n, frame=False) == reading.description(z, frame=False)
    assert reading.description(n) != reading.description(z)
    assert reading.agreement(reading.description(n), reading.description(z)) < F(1, 2)


def test_the_twenty_six_descriptions_are_pairwise_different():
    shelf = alphabet.library()
    letters = sorted(shelf)
    for i, first in enumerate(letters):
        for second in letters[i+1:]:
            assert shelf[first] != shelf[second], (first, second)


def test_a_letter_read_from_an_image_can_match_its_definition_exactly():
    shelf = alphabet.library()
    exact = 0
    for letter in ("E", "H", "L", "T", "X", "Z"):
        glyph = reading.recover(alphabet.draw(alphabet.ROMAN[letter], height=72,
                                              radius=F(5, 2)))
        exact += reading.description(glyph) == shelf[letter]
    assert exact >= 5


# ---------------------------------------------------------------------------
# Reading
# ---------------------------------------------------------------------------

def _accuracy(style, shelf, **drawing):
    right = []
    for letter, strokes in style.items():
        answer = reading.read(alphabet.draw(strokes, **drawing), shelf)
        right.append(answer["letter"] == letter)
    return sum(right)


def test_the_alphabet_is_read_at_a_size_no_reference_was_built_from():
    assert _accuracy(alphabet.ROMAN, alphabet.library(), height=60, radius=F(2),
                     at=(5, 3)) == 26


def test_the_alphabet_is_read_when_drawn_with_the_square_nib():
    assert _accuracy(alphabet.ROMAN, alphabet.library(), height=72, radius=F(5, 2),
                     pen="square") >= 25


def test_the_alphabet_is_read_when_the_edge_of_the_ink_is_ragged():
    shelf = alphabet.library()
    right = 0
    for letter, strokes in alphabet.ROMAN.items():
        bitmap = raster.speckle(alphabet.draw(strokes, height=72, radius=F(5, 2)),
                                seed=11, rate=5)
        right += reading.read(bitmap, shelf)["letter"] == letter
    assert right >= 24


def test_the_second_style_is_read_although_no_reference_was_built_from_it():
    assert _accuracy(alphabet.NARROW, alphabet.library(), height=72, radius=F(5, 2)) >= 24


def test_the_coordinate_control_fails_where_the_relations_do_not():
    """If this ever passes, the fragment is decoration and the work is misnamed."""
    shelf = alphabet.library()
    templates = alphabet.template_library()
    by_relations = by_coordinates = 0
    for letter, strokes in alphabet.NARROW.items():
        bitmap = alphabet.draw(strokes, height=72, radius=F(5, 2))
        by_relations += reading.read(bitmap, shelf)["letter"] == letter
        by_coordinates += alphabet.read_by_coordinates(bitmap, templates)["letter"] == letter
    assert by_relations >= 24
    assert by_coordinates <= 12
    assert by_relations > 2*by_coordinates


def test_an_answer_comes_with_a_runner_up_and_a_margin():
    answer = reading.read(alphabet.draw(alphabet.ROMAN["K"], height=72, radius=F(5, 2)),
                          alphabet.library())
    assert answer["letter"] == "K"
    assert answer["runner_up"] != "K"
    assert answer["margin"] > 0


def test_an_empty_image_is_refused_rather_than_guessed():
    with pytest.raises(ValueError):
        reading.recover(raster.Bitmap(12, 12))


# ---------------------------------------------------------------------------
# Nothing that already knows what a letter looks like
# ---------------------------------------------------------------------------

def test_the_reading_path_imports_no_optical_character_recognition():
    """The repository has a cv2 template reader and a pytesseract call. Not here."""
    before = set(sys.modules)
    reading.read(alphabet.draw(alphabet.ROMAN["G"], height=48, radius=F(3, 2)),
                 alphabet.library())
    for forbidden in ("cv2", "pytesseract", "PIL.ImageFont", "torch", "sklearn",
                      "numpy.linalg", "tensorflow"):
        assert forbidden not in sys.modules, forbidden
    assert "PIL" not in set(sys.modules)-before
