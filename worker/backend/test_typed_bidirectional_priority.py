from worker.backend.geometry_proof_hypergraph import Atom, Theorem
import worker.backend.typed_bidirectional_priority as priority_module
from worker.backend.typed_open_proof_dag import (
    OpenProofBranch,
    OpenProofDAG,
    compile_open_proof_dag,
)
from worker.backend.typed_bidirectional_priority import (
    search_bidirectionally,
    search_bidirectionally_iterative,
)


def test_unified_queue_finds_a_two_sided_typed_meet() -> None:
    rules = (
        Theorem("seed-mid", (Atom("seed", ("?x",)),), Atom("mid", ("?x",))),
        Theorem("mid-bridge", (Atom("mid", ("?x",)),), Atom("bridge", ("?x",))),
        Theorem("bridge-goal", (Atom("bridge", ("?x",)),), Atom("goal", ("a",))),
    )
    result = search_bidirectionally(
        (),
        (Atom("goal", ("a",)),),
        {
            "reachable": (Atom("seed", ("d",)),),
            "noise": (Atom("noise", ("d",)),),
        },
        rules,
        max_backward_depth=1,
        max_forward_depth=2,
    )

    assert result.candidates["reachable"].has_closed_structural_residual
    assert not result.candidates["noise"].has_closed_structural_residual
    assert result.audit.backward_task_count == 1
    assert result.audit.forward_task_count >= 2


def test_partial_meet_records_strict_residual_reduction() -> None:
    rules = (
        Theorem("seed-bridge", (Atom("seed", ("?x",)),), Atom("bridge", ("?x",))),
        Theorem(
            "bridge-and-condition-goal",
            (Atom("bridge", ("?x",)), Atom("condition", ("?x",))),
            Atom("goal", ("?x",)),
        ),
    )
    result = search_bidirectionally(
        (),
        (Atom("goal", ("a",)),),
        {"candidate": (Atom("seed", ("a",)),)},
        rules,
        max_backward_depth=1,
        max_forward_depth=1,
    )

    candidate = result.candidates["candidate"]
    assert candidate.has_residual_reduction
    assert not candidate.has_closed_structural_residual
    assert candidate.alignment.best_backward_frontier_size == 2
    assert candidate.alignment.best_residual_size == 1


def test_unified_queue_is_entity_renaming_invariant() -> None:
    rules = (
        Theorem("seed-bridge", (Atom("seed", ("?x",)),), Atom("bridge", ("?x",))),
        Theorem("bridge-goal", (Atom("bridge", ("?x",)),), Atom("goal", ("?g",))),
    )

    def rank(goal: str, point: str) -> tuple[object, ...]:
        result = search_bidirectionally(
            (),
            (Atom("goal", (goal,)),),
            {"candidate": (Atom("seed", (point,)),)},
            rules,
            max_backward_depth=1,
            max_forward_depth=1,
        )
        return result.candidates["candidate"].rank

    assert rank("a", "d") == rank("u", "v")


def test_unified_queue_has_a_hard_global_state_budget() -> None:
    rules = tuple(
        Theorem(
            f"step-{index}",
            (Atom(f"p{index}", ("?x",)),),
            Atom(f"p{index + 1}", ("?x",)),
        )
        for index in range(8)
    )
    result = search_bidirectionally(
        (),
        (Atom("p8", ("a",)),),
        {"candidate": (Atom("p0", ("d",)),)},
        rules,
        max_backward_depth=5,
        max_forward_depth=5,
        per_task_search_states=4,
        max_total_search_states=12,
    )

    assert (
        result.audit.backward_search_states + result.audit.forward_search_states
        <= 12
    )
    assert result.audit.truncated


def test_backward_and_forward_deepening_share_a_total_priority_type() -> None:
    rules = (
        Theorem("p-goal", (Atom("p", ("?x",)),), Atom("goal", ("?x",))),
        Theorem("seed-p", (Atom("seed", ("?x",)),), Atom("p", ("?x",))),
    )
    result = search_bidirectionally(
        (),
        (Atom("goal", ("a",)), Atom("goal", ("b",))),
        {
            "left": (Atom("seed", ("a",)),),
            "right": (Atom("noise", ("b",)),),
        },
        rules,
        max_backward_depth=2,
        max_forward_depth=2,
    )

    assert result.audit.task_count > 0
    assert result.candidates["left"].has_closed_structural_residual


def test_iterative_deepening_finds_an_unseen_two_step_intermediate_chain() -> None:
    rules = (
        Theorem("seed-mid", (Atom("seed", ("?x",)),), Atom("mid", ("?x",))),
        Theorem("mid-bridge", (Atom("mid", ("?x",)),), Atom("bridge", ("?x",))),
        Theorem("bridge-goal", (Atom("bridge", ("?x",)),), Atom("goal", ("?x",))),
    )

    result = search_bidirectionally_iterative(
        (),
        (Atom("goal", ("z",)),),
        {"candidate": (Atom("seed", ("z",)),)},
        rules,
        max_depth=3,
        per_task_search_states=128,
        max_total_search_states=2048,
        max_tasks=64,
    )

    assert len(result.stages) >= 2
    assert not result.stages[0].typed_meet_candidates
    assert result.candidates["candidate"].has_closed_structural_residual
    assert result.stop_reason == "typed_meet_found_native_replay_required"


def test_iterative_deepening_reports_a_theorem_vocabulary_gap() -> None:
    result = search_bidirectionally_iterative(
        (),
        (Atom("unknown_goal", ("z",)),),
        {"candidate": (Atom("seed", ("z",)),)},
        (),
        max_depth=2,
    )

    assert result.stop_reason == "theorem_conclusion_vocabulary_gap"


def test_iterative_deepening_reserves_budget_for_deeper_queue_levels() -> None:
    rules = (
        Theorem("seed-mid", (Atom("seed", ("?x",)),), Atom("mid", ("?x",))),
        Theorem("mid-bridge", (Atom("mid", ("?x",)),), Atom("bridge", ("?x",))),
        Theorem("bridge-goal", (Atom("bridge", ("?x",)),), Atom("goal", ("?x",))),
    )
    candidates = {
        f"candidate-{index}": (Atom("seed", (str(index),)),)
        for index in range(4)
    }

    result = search_bidirectionally_iterative(
        (),
        (Atom("goal", ("0",)),),
        candidates,
        rules,
        max_depth=2,
        per_task_search_states=64,
        max_total_search_states=40,
        max_tasks=10,
    )

    assert result.stages[-1].audit.max_backward_depth_reached == 2
    assert result.stages[-1].audit.max_forward_depth_reached == 2
    assert result.candidates["candidate-0"].has_closed_structural_residual


def test_forward_candidates_deferred_until_deeper_backward_branch_exists(
    monkeypatch,
) -> None:
    rules = (
        Theorem("seed-left", (Atom("seed", ("?x",)),), Atom("left", ("?x",))),
    )

    def delayed_backward_dag(_facts, goal, _rules, *, max_rule_depth, **_kwargs):
        branches = (
            (
                OpenProofBranch(
                    branch_id="depth-2",
                    parent_id=None,
                    rule_depth=2,
                    theorem_chain=("delayed",),
                    frontier=(Atom("left", ("a",)),),
                ),
            )
            if max_rule_depth >= 2
            else ()
        )
        return OpenProofDAG(
            goal=goal,
            branches=branches,
            unique_frontier_atoms=(Atom("left", ("a",)),) if branches else (),
            max_rule_depth=max_rule_depth,
            search_states=1,
            fact_unifications=0,
            rule_unifications=0,
            rejected_nonprogressing_decompositions=0,
            rejected_revisited_frontiers=0,
            truncated=False,
        )

    monkeypatch.setattr(
        priority_module,
        "compile_open_proof_dag",
        delayed_backward_dag,
    )

    result = search_bidirectionally(
        (),
        (Atom("goal", ("a",)),),
        {"candidate": (Atom("seed", ("a",)),)},
        rules,
        max_backward_depth=2,
        max_forward_depth=1,
        per_task_search_states=8,
        max_total_search_states=32,
        max_tasks=16,
    )

    assert result.audit.forward_task_count == 1
    assert result.candidates["candidate"].has_residual_reduction


def test_iterative_deepening_wall_budget_is_audited() -> None:
    rules = tuple(
        Theorem(
            f"step-{index}",
            (Atom("seed", (f"?x{index}",)),),
            Atom("seed", (f"?y{index}",)),
        )
        for index in range(64)
    )

    result = search_bidirectionally_iterative(
        (),
        (Atom("goal", ("a",)),),
        {"candidate": (Atom("seed", ("a",)),)},
        rules,
        max_depth=8,
        max_total_search_states=100_000,
        max_tasks=10_000,
        max_wall_seconds=1e-12,
    )

    assert result.stop_reason == "wall_time_ceiling_before_typed_meet"
    assert result.audit.truncated is True
    assert result.audit.wall_time_exhausted is True


def test_precompiled_backward_dag_spends_runtime_on_forward_candidates() -> None:
    rules = (
        Theorem("seed-mid", (Atom("seed", ("?x",)),), Atom("mid", ("?x",))),
        Theorem("mid-goal", (Atom("mid", ("?x",)),), Atom("goal", ("?x",))),
    )
    dag = compile_open_proof_dag(
        (),
        Atom("goal", ("a",)),
        rules,
        max_rule_depth=1,
    )

    result = search_bidirectionally_iterative(
        (),
        (Atom("goal", ("a",)),),
        {"candidate": (Atom("seed", ("a",)),)},
        rules,
        max_depth=1,
        initial_proof_dags=(dag,),
    )

    assert result.audit.backward_task_count == 0
    assert result.audit.forward_task_count == 1
    assert result.candidates["candidate"].has_closed_structural_residual


def test_direct_candidate_meet_survives_zero_wall_for_expansion() -> None:
    rules = (
        Theorem("mid-goal", (Atom("mid", ("?x",)),), Atom("goal", ("?x",))),
    )
    dag = compile_open_proof_dag(
        (),
        Atom("goal", ("a",)),
        rules,
        max_rule_depth=1,
    )

    result = search_bidirectionally_iterative(
        (),
        (Atom("goal", ("a",)),),
        {"candidate": (Atom("mid", ("a",)),)},
        rules,
        max_depth=1,
        max_wall_seconds=1e-12,
        initial_proof_dags=(dag,),
    )

    assert result.candidates["candidate"].has_closed_structural_residual
