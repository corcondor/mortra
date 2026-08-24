from worker.backend.geometry_proof_hypergraph import Atom, Theorem
from worker.backend.typed_candidate_alignment import (
    align_candidate_atoms,
    align_candidate_cone_to_proof_branches,
    align_candidate_groups_lazily,
    align_candidate_to_proof_branches,
)
from worker.backend.typed_open_proof_dag import (
    NativeProofDAGIncrement,
    OpenProofBranch,
    assess_native_proof_dag_progress,
    compile_candidate_forward_cone,
    compile_open_proof_dag,
    native_proof_dag_increment,
    review_decomposition_progress,
)


def test_native_progress_preserves_or_branches_and_ignores_numeric_guards() -> None:
    branches = (
        OpenProofBranch(
            "left",
            None,
            1,
            ("left-rule",),
            (
                Atom("coll", ("a", "m", "b")),
                Atom("ncoll", ("a", "b", "c")),
            ),
            (),
        ),
        OpenProofBranch(
            "right",
            None,
            1,
            ("right-rule",),
            (Atom("perp", ("a", "m", "b", "c")),),
            (),
        ),
    )

    progress = assess_native_proof_dag_progress(
        (Atom("coll", ("m", "b", "a")),),
        branches,
    )

    assert progress.branch_count == 2
    assert progress.progressed_branch_count == 1
    assert progress.structurally_closed_branch_count == 1
    assert progress.best_structural_residual_count == 0
    assert progress.max_exact_covered_atoms == 1
    assert progress.unique_exact_covered_atoms == 1
    assert progress.support_improved_branch_count == 1
    assert progress.max_support_overlap_gain == 3
    assert progress.total_support_overlap_gain == 3


def test_native_progress_measures_typed_support_gain_against_baseline() -> None:
    branch = OpenProofBranch(
        "branch",
        None,
        1,
        ("rule",),
        (Atom("eqangle", ("a", "b", "c", "d")),),
        (),
    )
    baseline = (Atom("eqangle", ("a", "x", "y", "z")),)
    current = (*baseline, Atom("eqangle", ("a", "b", "c", "w")))

    progress = assess_native_proof_dag_progress(
        current,
        (branch,),
        baseline_facts=baseline,
    )

    assert progress.progressed_branch_count == 0
    assert progress.support_improved_branch_count == 1
    assert progress.max_support_overlap_gain == 2
    assert progress.total_support_overlap_gain == 2


def test_native_progress_increment_does_not_recredit_parent_gain() -> None:
    branch = OpenProofBranch(
        "branch",
        None,
        1,
        ("rule",),
        (Atom("eqangle", ("a", "b", "c", "d")),),
        (),
    )
    baseline = (Atom("eqangle", ("a", "x", "y", "z")),)
    parent = assess_native_proof_dag_progress(
        (*baseline, Atom("eqangle", ("a", "b", "c", "w"))),
        (branch,),
        baseline_facts=baseline,
    )
    improved_child = assess_native_proof_dag_progress(
        (
            *baseline,
            Atom("eqangle", ("a", "b", "c", "w")),
            Atom("eqangle", ("a", "b", "c", "d")),
        ),
        (branch,),
        baseline_facts=baseline,
    )

    assert native_proof_dag_increment(parent, parent) == (
        NativeProofDAGIncrement(0, 0, 0, 0, 0, 0)
    )
    assert native_proof_dag_increment(parent, improved_child) == (
        NativeProofDAGIncrement(1, 1, 1, 1, 0, 1)
    )


def _or_rules(a: str = "a") -> tuple[Theorem, ...]:
    return (
        Theorem(
            "left",
            (Atom("p", ("?x",)), Atom("anchor", (a,))),
            Atom("goal", (a,)),
        ),
        Theorem(
            "right",
            (Atom("q", ("?x",)), Atom("witness", (a,))),
            Atom("goal", (a,)),
        ),
    )


def test_or_branches_are_not_flattened_for_candidate_credit() -> None:
    dag = compile_open_proof_dag((), Atom("goal", ("a",)), _or_rules())
    candidate = (Atom("p", ("d",)), Atom("q", ("d",)))

    coherent = align_candidate_to_proof_branches(candidate, dag.open_branches)
    flattened = align_candidate_atoms(candidate, dag.unique_frontier_atoms, {})

    assert coherent.direct_match_count == 1
    assert flattened.direct_match_count == 2
    assert coherent.matching_branch_count == 2


def test_depth_two_exposes_typed_intermediate_hole() -> None:
    rules = (
        Theorem("goal-from-bridge", (Atom("bridge", ("?x", "a")),), Atom("goal", ("a",))),
        Theorem(
            "bridge-from-coll",
            (Atom("coll", ("?x", "a", "b")),),
            Atom("bridge", ("?x", "a")),
        ),
    )
    dag = compile_open_proof_dag(
        (), Atom("goal", ("a",)), rules, max_rule_depth=2
    )

    alignment = align_candidate_to_proof_branches(
        (Atom("coll", ("d", "a", "b")),), dag.open_branches
    )

    assert alignment.direct_match_count == 1
    assert alignment.direct_hole_binding_count == 1
    assert alignment.best_branch_depth == 2


def test_decomposition_reviewer_rejects_restatement_and_extra_work() -> None:
    parent = (Atom("goal", ("?x",)),)

    same = review_decomposition_progress(parent, (Atom("goal", ("?y",)),))
    larger = review_decomposition_progress(
        parent,
        (Atom("goal", ("?y",)), Atom("guard", ("?y",))),
    )
    useful = review_decomposition_progress(parent, (Atom("premise", ("?y",)),))

    assert not same.accepted
    assert same.reason == "alpha_equivalent_frontier"
    assert not larger.accepted
    assert larger.reason == "strict_frontier_superset"
    assert useful.accepted


def test_open_dag_prunes_nonprogressing_and_cyclic_decompositions() -> None:
    rules = (
        Theorem("self", (Atom("goal", ("?x",)),), Atom("goal", ("?x",))),
        Theorem("inflate", (
            Atom("goal", ("?x",)),
            Atom("guard", ("?x",)),
        ), Atom("goal", ("?x",))),
        Theorem("goal-from-mid", (Atom("mid", ("?x",)),), Atom("goal", ("?x",))),
        Theorem("mid-from-goal", (Atom("goal", ("?x",)),), Atom("mid", ("?x",))),
    )

    dag = compile_open_proof_dag(
        (),
        Atom("goal", ("a",)),
        rules,
        max_rule_depth=6,
        max_search_states=100,
    )

    assert dag.rejected_nonprogressing_decompositions == 2
    assert dag.rejected_revisited_frontiers >= 1
    assert dag.search_states < 20
    assert any(branch.frontier == (Atom("mid", ("a",)),) for branch in dag.branches)

    control = compile_open_proof_dag(
        (),
        Atom("goal", ("a",)),
        rules,
        max_rule_depth=6,
        max_search_states=100,
        review_decompositions=False,
    )
    assert control.rejected_nonprogressing_decompositions == 0
    assert control.rejected_revisited_frontiers == 0
    assert control.search_states > dag.search_states


def test_candidate_alignment_is_entity_renaming_invariant() -> None:
    first = compile_open_proof_dag((), Atom("goal", ("a",)), _or_rules())
    renamed = compile_open_proof_dag((), Atom("goal", ("u",)), _or_rules("u"))

    first_alignment = align_candidate_to_proof_branches(
        (Atom("p", ("d",)),), first.open_branches
    )
    renamed_alignment = align_candidate_to_proof_branches(
        (Atom("p", ("v",)),), renamed.open_branches
    )

    assert first_alignment.rank == renamed_alignment.rank


def test_fact_closure_preserves_remaining_and_premise() -> None:
    rules = (
        Theorem(
            "joined",
            (Atom("known", ("?x",)), Atom("open", ("?x",))),
            Atom("goal", ("a",)),
        ),
    )
    dag = compile_open_proof_dag(
        (Atom("known", ("d",)),), Atom("goal", ("a",)), rules
    )

    assert any(branch.frontier == (Atom("open", ("d",)),) for branch in dag.branches)


def test_two_sided_meet_finds_intermediate_two_steps_from_candidate() -> None:
    rules = (
        Theorem("seed-to-mid", (Atom("seed", ("?x",)),), Atom("mid", ("?x",))),
        Theorem("mid-to-bridge", (Atom("mid", ("?x",)),), Atom("bridge", ("?x",))),
        Theorem("bridge-to-goal", (Atom("bridge", ("?x",)),), Atom("goal", ("a",))),
    )
    dag = compile_open_proof_dag(
        (), Atom("goal", ("a",)), rules, max_rule_depth=1
    )
    cone = compile_candidate_forward_cone(
        (),
        (Atom("seed", ("d",)),),
        rules,
        targets=dag.unique_frontier_atoms,
        max_rule_depth=2,
    )

    alignment = align_candidate_cone_to_proof_branches(cone, dag.open_branches)

    assert alignment.has_meet
    assert alignment.best_forward_depth == 2
    assert alignment.best_backward_depth == 1
    assert alignment.best_residual_size == 0
    assert alignment.best_meet_atom == "bridge(?h0)"


def test_forward_fragment_keeps_unproved_and_premise_explicit() -> None:
    rules = (
        Theorem(
            "conditional-bridge",
            (Atom("seed", ("?x",)), Atom("guard", ("?x",))),
            Atom("bridge", ("?x",)),
        ),
    )
    cone = compile_candidate_forward_cone(
        (),
        (Atom("seed", ("d",)),),
        rules,
        targets=(Atom("bridge", ("?x",)),),
        max_rule_depth=1,
    )

    fragments = [item for item in cone.fragments if item.conclusion == Atom("bridge", ("d",))]

    assert fragments
    assert fragments[0].residual_frontier == (Atom("guard", ("d",)),)


def test_forward_fragment_can_use_multiple_candidate_atoms() -> None:
    rules = (
        Theorem(
            "pair-to-bridge",
            (Atom("left", ("?x",)), Atom("right", ("?x",))),
            Atom("bridge", ("?x",)),
        ),
    )
    cone = compile_candidate_forward_cone(
        (),
        (Atom("left", ("d",)), Atom("right", ("d",))),
        rules,
        targets=(Atom("bridge", ("?x",)),),
        max_rule_depth=1,
    )

    fragments = [
        item
        for item in cone.fragments
        if item.conclusion == Atom("bridge", ("d",))
        and not item.residual_frontier
    ]

    assert fragments
    assert len(fragments[0].source_atoms) == 2


def test_two_sided_meet_is_entity_renaming_invariant() -> None:
    rules = (
        Theorem("seed-to-bridge", (Atom("seed", ("?x",)),), Atom("bridge", ("?x",))),
        Theorem("bridge-to-goal", (Atom("bridge", ("?x",)),), Atom("goal", ("?g",))),
    )

    def rank(goal_name: str, source_name: str) -> tuple[int, ...]:
        dag = compile_open_proof_dag(
            (), Atom("goal", (goal_name,)), rules, max_rule_depth=1
        )
        cone = compile_candidate_forward_cone(
            (),
            (Atom("seed", (source_name,)),),
            rules,
            targets=dag.unique_frontier_atoms,
            max_rule_depth=1,
        )
        return align_candidate_cone_to_proof_branches(
            cone, dag.open_branches
        ).rank

    assert rank("a", "d") == rank("u", "v")


def test_executable_side_condition_ranks_before_new_structural_obligation() -> None:
    rules = (
        Theorem(
            "side-condition-path",
            (Atom("seed", ("?x",)), Atom("diff", ("?x", "a"))),
            Atom("bridge", ("?x",)),
        ),
        Theorem(
            "structural-obligation-path",
            (Atom("seed", ("?x",)), Atom("midp", ("?x", "a", "b"))),
            Atom("bridge", ("?x",)),
        ),
        Theorem("bridge-to-goal", (Atom("bridge", ("?x",)),), Atom("goal", ("a",))),
    )
    dag = compile_open_proof_dag(
        (), Atom("goal", ("a",)), rules, max_rule_depth=1
    )
    cone = compile_candidate_forward_cone(
        (),
        (Atom("seed", ("d",)),),
        rules,
        targets=dag.unique_frontier_atoms,
        max_rule_depth=1,
    )

    alignment = align_candidate_cone_to_proof_branches(cone, dag.open_branches)

    assert alignment.best_structural_residual_count == 0
    assert alignment.best_residual_atoms == ("diff(a,d)",)


def test_forward_cone_tables_alpha_equivalent_states_once() -> None:
    duplicate_rules = (
        Theorem("first", (Atom("seed", ("?x",)),), Atom("bridge", ("?x",))),
        Theorem("second", (Atom("seed", ("?y",)),), Atom("bridge", ("?y",))),
    )

    cone = compile_candidate_forward_cone(
        (),
        (Atom("seed", ("d",)),),
        duplicate_rules,
        max_rule_depth=1,
    )

    assert [item.conclusion for item in cone.fragments].count(Atom("bridge", ("d",))) == 1
    assert cone.search_states == 2


def test_meet_rejects_circular_residual_goal() -> None:
    goal = Atom("goal", ("a",))
    cone = compile_candidate_forward_cone(
        (),
        (Atom("seed", ("d",)),),
        (
            Theorem(
                "circular",
                (Atom("seed", ("?x",)), goal),
                goal,
            ),
        ),
        targets=(goal,),
        max_rule_depth=1,
    )
    branch = OpenProofBranch("goal-branch", None, 1, (), (goal,))

    alignment = align_candidate_cone_to_proof_branches(cone, (branch,))

    assert not alignment.has_meet
    assert alignment.cyclic_match_rejections > 0


def test_lazy_alignment_promotes_only_reachable_candidate_to_depth_two() -> None:
    rules = (
        Theorem("seed-to-mid", (Atom("seed", ("?x",)),), Atom("mid", ("?x",))),
        Theorem("mid-to-bridge", (Atom("mid", ("?x",)),), Atom("bridge", ("?x",))),
        Theorem("bridge-to-goal", (Atom("bridge", ("?x",)),), Atom("goal", ("a",))),
    )
    dag = compile_open_proof_dag((), Atom("goal", ("a",)), rules, max_rule_depth=1)

    results, _cones = align_candidate_groups_lazily(
        (),
        {
            "reachable": (Atom("seed", ("d",)),),
            "unreachable": (Atom("noise", ("d",)),),
        },
        rules,
        dag.open_branches,
        max_rule_depth=2,
        initial_search_states=8,
        promoted_search_states=32,
        promotion_limit=1,
    )

    assert results["reachable"].has_meet
    assert results["reachable"].promoted
    assert results["reachable"].explored_depth == 2
    assert not results["unreachable"].promoted
    assert results["unreachable"].explored_depth == 1
    assert len(results["reachable"].stage_search_states) == 2
    assert len(results["unreachable"].stage_search_states) == 1


def test_lazy_alignment_uses_parent_prefix_as_fact_not_candidate_credit() -> None:
    rules = (
        Theorem(
            "join",
            (Atom("parent", ("?x",)), Atom("extension", ("?x",))),
            Atom("bridge", ("?x",)),
        ),
        Theorem("finish", (Atom("bridge", ("?x",)),), Atom("goal", ("a",))),
    )
    dag = compile_open_proof_dag((), Atom("goal", ("a",)), rules, max_rule_depth=1)

    results, _cones = align_candidate_groups_lazily(
        (Atom("parent", ("d",)),),
        {"extension": (Atom("extension", ("d",)),)},
        rules,
        dag.open_branches,
        max_rule_depth=1,
        initial_search_states=16,
    )

    result = results["extension"]
    assert result.has_meet
    assert result.alignment.best_source_atom_count == 1
    assert result.alignment.best_source_atoms == ("extension(d)",)


def test_lazy_alignment_is_entity_renaming_invariant() -> None:
    rules = (
        Theorem("seed-to-bridge", (Atom("seed", ("?x",)),), Atom("bridge", ("?x",))),
        Theorem("bridge-to-goal", (Atom("bridge", ("?x",)),), Atom("goal", ("?g",))),
    )

    def rank(goal: str, point: str) -> tuple[int, ...]:
        dag = compile_open_proof_dag(
            (), Atom("goal", (goal,)), rules, max_rule_depth=1
        )
        results, _cones = align_candidate_groups_lazily(
            (),
            {"candidate": (Atom("seed", (point,)),)},
            rules,
            dag.open_branches,
            max_rule_depth=1,
            initial_search_states=16,
        )
        return results["candidate"].rank

    assert rank("a", "d") == rank("u", "v")


def test_lazy_partial_meet_cannot_override_base_scheduler() -> None:
    rules = (
        Theorem(
            "conditional",
            (Atom("seed", ("?x",)), Atom("guard", ("?x",))),
            Atom("bridge", ("?x",)),
        ),
        Theorem("finish", (Atom("bridge", ("?x",)),), Atom("goal", ("a",))),
    )
    dag = compile_open_proof_dag((), Atom("goal", ("a",)), rules, max_rule_depth=1)
    results, _cones = align_candidate_groups_lazily(
        (),
        {"candidate": (Atom("seed", ("d",)),)},
        rules,
        dag.open_branches,
        max_rule_depth=1,
        initial_search_states=16,
    )

    result = results["candidate"]
    assert result.has_meet
    assert result.alignment.best_structural_residual_count == 1
    assert not result.has_closed_structural_residual
    assert result.rank == (1,)
    assert result.exploration_rank[0] == 0


def test_low_budget_keeps_generated_open_theorem_branches() -> None:
    rules = (
        Theorem(
            "cyclic-from-angle",
            (Atom("eqangle", ("?a", "?b")), Atom("guard", ("?a",))),
            Atom("cyclic", ("?a", "?b", "?c", "?d")),
        ),
    )

    dag = compile_open_proof_dag(
        (),
        Atom("cyclic", ("p", "q", "r", "s")),
        rules,
        max_rule_depth=2,
        max_search_states=2,
    )

    assert dag.truncated
    assert dag.open_branches
    assert dag.open_branches[0].theorem_chain == ("cyclic-from-angle",)


def test_predicate_distance_prioritizes_a_closable_and_branch() -> None:
    facts = (Atom("zseed", ("a",)),)
    theorems = (
        Theorem(
            "good",
            (Atom("zseed", ("?x",)),),
            Atom("goal", ("?x",)),
        ),
        Theorem(
            "dead",
            (Atom("a_missing", ("?x",)),),
            Atom("goal", ("?x",)),
        ),
    )
    ranked = compile_open_proof_dag(
        facts,
        Atom("goal", ("a",)),
        theorems,
        max_rule_depth=1,
        max_branches=1,
        max_search_states=32,
        review_decompositions=False,
        rank_by_predicate_distance=True,
    )
    unranked = compile_open_proof_dag(
        facts,
        Atom("goal", ("a",)),
        theorems,
        max_rule_depth=1,
        max_branches=1,
        max_search_states=32,
        review_decompositions=False,
        rank_by_predicate_distance=False,
    )

    assert any(not branch.frontier for branch in ranked.branches)
    assert not any(not branch.frontier for branch in unranked.branches)


def test_open_proof_dag_wall_budget_is_a_truncation_not_a_proof() -> None:
    dag = compile_open_proof_dag(
        (Atom("coll", ("a", "b", "c")),),
        Atom("cyclic", ("a", "b", "c", "d")),
        (),
        max_rule_depth=4,
        max_branches=32,
        max_search_states=10_000,
        max_wall_seconds=1e-12,
    )

    assert dag.truncated is True
    assert dag.search_states == 0


def test_candidate_forward_cone_wall_budget_is_a_truncation() -> None:
    rules = tuple(
        Theorem(
            f"step-{index}",
            (Atom("seed", (f"?x{index}",)),),
            Atom("seed", (f"?y{index}",)),
        )
        for index in range(64)
    )

    cone = compile_candidate_forward_cone(
        (),
        (Atom("seed", ("a",)),),
        rules,
        max_rule_depth=8,
        max_fragments=1024,
        max_search_states=100_000,
        max_wall_seconds=1e-12,
    )

    assert cone.truncated is True
