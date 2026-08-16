from worker.backend.typed_geometry_stalk import (
    ConstructionFamily,
    TypedConstructionCandidate,
    augment_incidence_graph,
    balanced_stratified_beam,
    enumerate_typed_candidates,
    numerical_precondition_holds,
    proof_hypergraph_point_relevance,
    stratified_beam,
)


def test_symmetric_families_do_not_duplicate_permutations() -> None:
    candidates = enumerate_typed_candidates(
        points=("a", "b", "c"),
        graph={"a": {"b"}, "b": {"a", "c"}, "c": {"b"}},
        goal_multiplicity={"a": 1},
        families=(ConstructionFamily("midpoint", 2, "all"),),
        per_family_limit=10,
    )
    assert {candidate.key for candidate in candidates} == {
        "midpoint(a,b)",
        "midpoint(a,c)",
        "midpoint(b,c)",
    }


def test_ordered_family_preserves_roles() -> None:
    candidates = enumerate_typed_candidates(
        points=("a", "b"),
        graph={"a": {"b"}, "b": {"a"}},
        goal_multiplicity={"a": 1},
        families=(ConstructionFamily("mirror", 2, "ordered"),),
        per_family_limit=10,
    )
    assert {candidate.key for candidate in candidates} == {
        "mirror(a,b)",
        "mirror(b,a)",
    }


def test_line_pair_has_three_pairings_for_four_points() -> None:
    candidates = enumerate_typed_candidates(
        points=("a", "b", "c", "d"),
        graph={},
        goal_multiplicity={"a": 1},
        families=(ConstructionFamily("intersection_ll", 4, "line_pair"),),
        per_family_limit=10,
    )
    assert len(candidates) == 3


def test_generated_point_can_be_used_by_next_morphism() -> None:
    graph = augment_incidence_graph(
        {"a": {"b"}, "b": {"a", "c"}, "c": {"b"}},
        (("x", ("a", "c")),),
    )
    candidates = enumerate_typed_candidates(
        points=("a", "b", "c", "x"),
        graph=graph,
        goal_multiplicity={"a": 1},
        generated_points={"x"},
        families=(ConstructionFamily("reflect", 3, "head_pair"),),
        per_family_limit=20,
    )
    assert any("x" in candidate.inputs for candidate in candidates)


def test_used_candidate_is_not_repeated() -> None:
    candidates = enumerate_typed_candidates(
        points=("a", "b", "c"),
        graph={},
        goal_multiplicity={"a": 1},
        used_keys={"midpoint(a,b)"},
        families=(ConstructionFamily("midpoint", 2, "all"),),
        per_family_limit=10,
    )
    assert "midpoint(a,b)" not in {candidate.key for candidate in candidates}


def test_proof_hypergraph_relevance_ranks_within_goal_incident_candidates() -> None:
    candidates = enumerate_typed_candidates(
        points=("a", "b", "c", "d"),
        graph={},
        goal_multiplicity={"a": 1},
        proof_relevance={"d": 1.0, "c": 0.2},
        families=(ConstructionFamily("midpoint", 2, "all"),),
        per_family_limit=10,
    )
    assert candidates[0].key == "midpoint(a,d)"


def test_proof_hypergraph_point_relevance_reads_yuclid_json_lists() -> None:
    relevance = proof_hypergraph_point_relevance(
        (
            {"point_deps": ["a", "b", "o"]},
            {"point_deps": ["a", "i"]},
            {"point_deps": ["c", "d"]},
        ),
        {"a", "b"},
    )
    assert relevance["a"] == 1.0
    assert relevance["o"] > 0
    assert "c" not in relevance


def test_stratified_beam_keeps_mixed_families_per_parent() -> None:
    rows = (
        ("p1", "mirror", 10),
        ("p1", "midpoint", 4),
        ("p2", "mirror", 9),
        ("p2", "midpoint", 3),
        ("p1", "mirror", 8),
    )
    selected = stratified_beam(
        rows,
        score=lambda row: (row[2],),
        stratum=lambda row: row[:2],
        limit=4,
    )
    assert {(row[0], row[1]) for row in selected} == {
        ("p1", "mirror"),
        ("p1", "midpoint"),
        ("p2", "mirror"),
        ("p2", "midpoint"),
    }


def test_balanced_stratified_beam_prevents_one_family_from_monopolizing() -> None:
    rows = (
        ("p1", "mirror", 100),
        ("p2", "mirror", 90),
        ("p3", "mirror", 80),
        ("p1", "midpoint", 10),
        ("p2", "midpoint", 9),
        ("p3", "midpoint", 8),
    )
    selected = balanced_stratified_beam(
        rows,
        score=lambda row: (row[2],),
        category=lambda row: row[1],
        stratum=lambda row: row[:2],
        limit=4,
    )
    assert [row[1] for row in selected].count("mirror") == 2
    assert [row[1] for row in selected].count("midpoint") == 2


def test_random_ranking_is_seeded_and_keeps_the_same_budget() -> None:
    kwargs = dict(
        points=("a", "b", "c", "d", "e"),
        graph={},
        goal_multiplicity={"a": 1},
        families=(ConstructionFamily("midpoint", 2, "all"),),
        per_family_limit=4,
        ranking="random",
    )
    first = enumerate_typed_candidates(**kwargs, seed=7)
    repeated = enumerate_typed_candidates(**kwargs, seed=7)
    other = enumerate_typed_candidates(**kwargs, seed=8)
    assert [candidate.key for candidate in first] == [
        candidate.key for candidate in repeated
    ]
    assert len(first) == len(other) == 4
    assert [candidate.key for candidate in first] != [
        candidate.key for candidate in other
    ]


def test_numerical_filter_rejects_degenerate_constructions_only() -> None:
    coordinates = {
        "a": (0.0, 0.0),
        "b": (1.0, 0.0),
        "c": (2.0, 0.0),
        "d": (0.0, 1.0),
        "e": (1.0, 1.0),
    }
    assert not numerical_precondition_holds(
        TypedConstructionCandidate("circle", ("a", "b", "c"), ()), coordinates
    )
    assert numerical_precondition_holds(
        TypedConstructionCandidate("circle", ("a", "b", "d"), ()), coordinates
    )
    assert not numerical_precondition_holds(
        TypedConstructionCandidate("intersection_ll", ("a", "b", "d", "e"), ()),
        coordinates,
    )
    assert numerical_precondition_holds(
        TypedConstructionCandidate("intersection_ll", ("a", "b", "a", "d"), ()),
        coordinates,
    )
