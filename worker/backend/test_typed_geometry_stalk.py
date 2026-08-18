from worker.backend.typed_geometry_stalk import (
    ConstructionFamily,
    TypedConstructionCandidate,
    augment_incidence_graph,
    balanced_stratified_beam,
    construction_semantic_edges,
    construction_semantic_weighted_edges,
    enumerate_typed_candidates,
    gate_candidates_by_relation_reachability,
    goal_relevant_families,
    numerical_precondition_holds,
    prioritize_morphism_orbit,
    proof_hypergraph_point_relevance,
    schema_first_score_fill,
    stratified_beam,
)


def test_relation_reachability_gate_rejects_only_unreachable_declared_outputs() -> None:
    families = (
        ConstructionFamily("line_point", 2, "all", ("coll",)),
        ConstructionFamily("circle_point", 2, "all", ("cyclic",)),
        ConstructionFamily("undeclared", 2, "all"),
    )
    candidates = tuple(
        TypedConstructionCandidate(family.name, ("a", "b"), ())
        for family in families
    )

    result = gate_candidates_by_relation_reachability(
        candidates,
        families=families,
        reachable_channels={"perp", "coll"},
        target_channels={"perp"},
    )

    assert [candidate.family for candidate in result.candidates] == [
        "line_point",
        "undeclared",
    ]
    assert result.audit.rejected_count == 1
    assert result.audit.rejected_by_family == (("circle_point", 1),)


def test_relation_reachability_gate_fails_open_without_type_evidence() -> None:
    family = ConstructionFamily("circle_point", 2, "all", ("cyclic",))
    candidate = TypedConstructionCandidate(family.name, ("a", "b"), ())

    result = gate_candidates_by_relation_reachability(
        (candidate,),
        families=(family,),
        reachable_channels=set(),
        target_channels={"perp"},
    )

    assert result.candidates == (candidate,)
    assert result.audit.fail_open_reason == "no_relation_reachability_evidence"


def test_schema_first_then_global_score_fills_remaining_budget() -> None:
    items = (("a", 1), ("a", 2), ("a", 3), ("b", 1))

    selected = schema_first_score_fill(
        items,
        category=lambda item: item[0],
        category_order=("a", "b"),
        limit=3,
    )

    assert selected == [("a", 1), ("b", 1), ("a", 2)]
from worker.backend.geometry_proof_hypergraph import Atom


def test_semantic_edges_preserve_angle_bisector_axis_without_clause_clique() -> None:
    edges = set(construction_semantic_edges("angle_bisector", ("o", "p", "c", "b")))

    assert ("o", "c") in edges
    assert ("o", "p") not in edges


def test_angle_bisector_axis_is_more_specific_than_triangle_edge() -> None:
    bisector = construction_semantic_weighted_edges(
        "angle_bisector", ("o", "p", "c", "b")
    )
    triangle = construction_semantic_weighted_edges("triangle", ("a", "b", "p"))

    assert ("o", "c", 4) in bisector
    assert all(weight == 1 for _, _, weight in triangle)


def test_relation_demand_prioritizes_matching_family_and_points() -> None:
    candidates = enumerate_typed_candidates(
        points=("a", "b", "c", "d"),
        graph={point: set() for point in "abcd"},
        goal_multiplicity={"a": 1},
        families=(
            ConstructionFamily("on_line", 2, "all", ("coll",)),
            ConstructionFamily("on_tline", 3, "ordered", ("perp",)),
        ),
        per_family_limit=20,
        relation_demands=(Atom("perp", ("x", "a", "b", "c")),),
    )
    assert candidates[0].family == "on_tline"
    assert set(candidates[0].inputs) == {"a", "b", "c"}


def test_required_generated_input_is_filtered_before_family_limit() -> None:
    candidates = enumerate_typed_candidates(
        points=("a", "b", "c", "x"),
        graph={point: set() for point in "abcx"},
        goal_multiplicity={"a": 1, "b": 1},
        families=(ConstructionFamily("reflect", 3, "head_pair"),),
        per_family_limit=1,
        required_input_points={"x"},
    )

    assert len(candidates) == 1
    assert "x" in candidates[0].inputs


def test_later_morphism_prefers_information_outside_parent_inputs() -> None:
    candidates = enumerate_typed_candidates(
        points=("a", "b", "c", "x"),
        graph={point: set() for point in "abcx"},
        goal_multiplicity={"a": 1},
        generated_points={"x"},
        families=(ConstructionFamily("reflect", 3, "head_pair"),),
        per_family_limit=1,
        orbit_inputs=("a", "b"),
        required_input_points={"x"},
        role_weights={("c", "x"): 4},
    )

    assert "c" in candidates[0].inputs


def test_family_limit_preserves_generated_head_and_line_roles() -> None:
    candidates = enumerate_typed_candidates(
        points=("a", "b", "c", "x"),
        graph={point: set() for point in "abcx"},
        goal_multiplicity={"a": 1},
        generated_points={"x"},
        families=(ConstructionFamily("reflect", 3, "head_pair"),),
        per_family_limit=2,
        required_input_points={"x"},
    )

    positions = [{index for index, point in enumerate(item.inputs) if point == "x"} for item in candidates]
    assert any(0 in item for item in positions)
    assert any(item.intersection({1, 2}) for item in positions)


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


def test_generated_frontier_uses_proof_relevance_before_goal_incidence() -> None:
    candidates = enumerate_typed_candidates(
        points=("a", "b", "c", "e"),
        graph={},
        goal_multiplicity={"a": 1},
        proof_relevance={"c": 2.0, "e": 1.0},
        generated_points={"e"},
        required_input_points={"e"},
        families=(ConstructionFamily("midpoint", 2, "all"),),
        per_family_limit=10,
    )
    assert candidates[0].key == "midpoint(c,e)"


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


def test_random_ranking_preserves_full_structural_rank_after_lazy_selection() -> None:
    common = dict(
        points=("a", "b", "c", "d", "e"),
        graph={"a": {"b"}, "b": {"a", "c"}, "c": {"b"}, "d": set(), "e": set()},
        goal_multiplicity={"a": 2, "d": 1},
        proof_relevance={"c": 0.75},
        generated_points={"e"},
        families=(ConstructionFamily("reflect", 3, "head_pair"),),
        role_weights={("a", "b"): 3, ("c", "e"): 4},
    )
    exhaustive = enumerate_typed_candidates(
        **common,
        per_family_limit=10_000,
        ranking="structural",
    )
    random_candidates = enumerate_typed_candidates(
        **common,
        per_family_limit=7,
        ranking="random",
        seed=19,
    )
    exhaustive_ranks = {candidate.key: candidate.structural_rank for candidate in exhaustive}

    assert random_candidates
    assert all(
        candidate.structural_rank == exhaustive_ranks[candidate.key]
        for candidate in random_candidates
    )


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


def test_goal_channel_prunes_only_type_incompatible_construction_families() -> None:
    families = (
        ConstructionFamily("midpoint", 2, "all", ("midp",)),
        ConstructionFamily("foot", 3, "head_pair", ("perp", "coll")),
        ConstructionFamily("angle_bisector", 3, "ordered", ("eqangle",)),
    )
    selected = goal_relevant_families(
        families,
        {"cong": 0, "midp": 1, "coll": 2},
    )
    assert [family.name for family in selected] == ["midpoint", "foot"]


def test_morphism_orbit_prioritizes_same_family_shared_role_without_labels() -> None:
    candidates = (
        TypedConstructionCandidate("mirror", ("a", "b"), (0,)),
        TypedConstructionCandidate("midpoint", ("c", "d"), (1,)),
        TypedConstructionCandidate("midpoint", ("b", "e"), (2,)),
    )
    ranked = prioritize_morphism_orbit(
        candidates,
        previous_family="midpoint",
        previous_inputs=("a", "b"),
    )
    assert [candidate.key for candidate in ranked] == [
        "midpoint(b,e)",
        "mirror(a,b)",
        "midpoint(c,d)",
    ]


def test_orbit_priority_is_applied_before_per_family_truncation() -> None:
    candidates = enumerate_typed_candidates(
        points=("a", "b", "c", "d"),
        graph={"a": {"b"}, "b": {"a"}, "c": set(), "d": set()},
        goal_multiplicity={"a": 1, "b": 1},
        families=(ConstructionFamily("midpoint", 2, "all"),),
        per_family_limit=1,
        orbit_family="midpoint",
        orbit_inputs=("c", "d"),
    )
    assert len(candidates) == 1
    assert "c" in candidates[0].inputs or "d" in candidates[0].inputs
