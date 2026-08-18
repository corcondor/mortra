from worker.backend.geometry_proof_hypergraph import Atom, Theorem
from worker.backend.typed_bidirectional_priority import search_bidirectionally


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
