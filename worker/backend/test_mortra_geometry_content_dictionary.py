from worker.backend.geometry_proof_hypergraph import Atom
from worker.backend.mortra_geometry_content_dictionary import (
    LINE2,
    LINE3,
    PARALLEL,
    PERPENDICULAR,
    PLANE3,
    LINE_THROUGH,
    lower_point_atom,
    line_through,
    plane_through,
    point,
    reelaborate_point_atom,
    relation,
)


def test_openmath_symbols_use_canonical_content_dictionary_uris() -> None:
    assert LINE_THROUGH == "http://www.openmath.org/cd/plangeo1#line"
    assert PARALLEL == "http://www.openmath.org/cd/plangeo3#parallel"


def test_point_predicate_views_round_trip_without_surface_templates() -> None:
    atoms = (
        Atom("coll", ("a", "b", "c")),
        Atom("para", ("a", "b", "c", "d")),
        Atom("perp", ("a", "b", "c", "d")),
        Atom("cong", ("a", "b", "c", "d")),
        Atom("cyclic", ("a", "b", "c", "d")),
        Atom("eqangle", ("a", "b", "c", "d", "e", "f", "g", "h")),
    )

    for atom in atoms:
        lowered = lower_point_atom(atom)
        assert lowered is not None
        assert reelaborate_point_atom(lowered) == atom.canonical()


def test_parallel_line_and_plane_remains_distinct_from_parallel_lines() -> None:
    a, b, c, d, e = (point(name, dimension=3) for name in "abcde")
    line = line_through(a, b)
    other_line = line_through(c, d)
    plane = plane_through(c, d, e)

    line_relation = relation(PARALLEL, (line, other_line))
    mixed_relation = relation(PARALLEL, (line, plane))

    assert line_relation.expected_sorts == (LINE3, LINE3)
    assert mixed_relation.expected_sorts == (LINE3, PLANE3)
    assert reelaborate_point_atom(line_relation) is not None
    assert reelaborate_point_atom(mixed_relation) is None


def test_2d_and_3d_lines_cannot_be_silently_mixed() -> None:
    line_2d = line_through(point("a"), point("b"))
    line_3d = line_through(point("c", dimension=3), point("d", dimension=3))

    assert line_2d.sort_uri == LINE2
    assert line_3d.sort_uri == LINE3
    try:
        relation(PERPENDICULAR, (line_2d, line_3d))
    except ValueError as error:
        assert "unsupported signature" in str(error)
    else:
        raise AssertionError("mixed-dimensional relation must be rejected")


def test_3d_point_relation_round_trip_preserves_ambient_sort() -> None:
    atom = Atom("para", ("a", "b", "c", "d"))
    lowered = lower_point_atom(atom, dimension=3)

    assert lowered is not None
    assert lowered.expected_sorts == (LINE3, LINE3)
    assert reelaborate_point_atom(lowered) == atom.canonical()
