from worker.backend.geometry_proof_hypergraph import Atom, Theorem
from worker.backend.typed_candidate_alignment import (
    align_candidate_atoms,
    align_candidate_cone_to_proof_branches,
    align_candidate_to_proof_branches,
)
from worker.backend.typed_open_proof_dag import (
    OpenProofBranch,
    compile_candidate_forward_cone,
    compile_open_proof_dag,
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
    assert alignment.best_residual_atoms == ("diff(d,a)",)


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
