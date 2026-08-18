from worker.backend.numerical_incidence_auxiliary import NumericalIncidenceAtlas


def test_midpoint_requires_a_nontrivial_extra_locus() -> None:
    atlas = NumericalIncidenceAtlas.build({"a": (-1.0, 0.0), "b": (1.0, 0.0)})
    profile = atlas.profile((0.0, 0.0), family="midpoint", inputs=("a", "b"))

    assert not profile.is_heuristic_candidate
    assert not profile.nontrivial_lines


def test_midpoint_on_another_line_is_selected() -> None:
    atlas = NumericalIncidenceAtlas.build(
        {
            "a": (-1.0, 0.0),
            "b": (1.0, 0.0),
            "c": (0.0, -2.0),
            "d": (0.0, 2.0),
        }
    )
    profile = atlas.profile((0.0, 0.0), family="midpoint", inputs=("a", "b"))

    assert "midpoint_extra_locus" in profile.heuristic_categories
    assert len(profile.nontrivial_lines) == 1


def test_three_line_intersection_matches_hageo_category_one() -> None:
    atlas = NumericalIncidenceAtlas.build(
        {
            "a": (-2.0, 0.0),
            "b": (2.0, 0.0),
            "c": (0.0, -2.0),
            "d": (0.0, 2.0),
            "e": (-1.0, -1.0),
            "f": (1.0, 1.0),
        }
    )
    profile = atlas.profile(
        (0.0, 0.0), family="intersection_ll", inputs=("a", "b", "c", "d")
    )

    assert "multiple_lines" in profile.heuristic_categories
    assert len(profile.incident_lines) == 3
    assert len(profile.nontrivial_lines) == 1


def test_foot_source_must_not_lie_on_the_extra_line() -> None:
    atlas = NumericalIncidenceAtlas.build(
        {
            "a": (0.0, 2.0),
            "b": (-2.0, 0.0),
            "c": (2.0, 0.0),
            "d": (0.0, -1.0),
            "e": (0.0, 1.0),
        }
    )
    profile = atlas.profile((0.0, 0.0), family="foot", inputs=("a", "b", "c"))

    assert "foot_extra_line" not in profile.heuristic_categories


def test_incidence_profile_is_similarity_invariant() -> None:
    base = {
        "a": (-1.0, 0.0),
        "b": (1.0, 0.0),
        "c": (0.0, -2.0),
        "d": (0.0, 2.0),
    }
    transformed = {
        name: (3.0 - 7.0 * point[1], -5.0 + 7.0 * point[0])
        for name, point in base.items()
    }
    first = NumericalIncidenceAtlas.build(base).profile(
        (0.0, 0.0), family="midpoint", inputs=("a", "b")
    )
    second = NumericalIncidenceAtlas.build(transformed).profile(
        (3.0, -5.0), family="midpoint", inputs=("a", "b")
    )

    assert first.rank == second.rank
    assert first.heuristic_categories == second.heuristic_categories
