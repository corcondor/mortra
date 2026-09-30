from experiments.mario_continual.predictive import PredictiveRegistry
from experiments.task_agent.continuation_frontier import ContinuationFrontierPolicy


def test_identical_reset_history_is_reused_without_predictive_state_growth():
    memory = PredictiveRegistry(2)
    source = memory.belief("A", ())
    target, resolved = memory.update(source, 0, "B", (), (0,))
    assert resolved == 0
    assert target.resolved_state == 1
    baseline = len(memory.id_to_state)

    for _ in range(100):
        source = memory.belief("A", ())
        assert source.resolved_state == 0
        target, resolved = memory.update(source, 0, "B", (), (0,))
        assert resolved == 0
        assert target.resolved_state == 1

    assert len(memory.id_to_state) == baseline


def test_distinct_history_can_still_split_a_visual_alias():
    memory = PredictiveRegistry(2)
    first = memory.belief("A", ())
    memory.update(first, 0, "B", (), (0,))

    unseen_context = memory.belief("A", (1, 1))
    assert unseen_context.candidates == (0,)
    target, split = memory.update(
        unseen_context, 0, "C", (1, 1), (1, 1, 0))
    assert split not in (None, 0)
    assert target.resolved_state is not None

    # Once evidenced, the exact history resolves directly to the split state,
    # while an unseen history still carries the visual alias set.
    assert memory.belief("A", ()).resolved_state == 0
    assert memory.belief("A", (1, 1)).resolved_state == split
    assert set(memory.belief("A", (2, 2)).candidates) == {0, split}


def test_continuation_frontier_bypasses_shallow_local_unknowns():
    memory = PredictiveRegistry(3)
    q0 = memory.add_state("S0", (), reason="test")
    q1 = memory.add_state("S1", (0,), reason="test")
    q2 = memory.add_state("S2", (0, 0), reason="test")
    memory.record_transition(q0, 0, q1)
    memory.record_transition(q1, 0, q2)

    policy = ContinuationFrontierPolicy()
    decision = policy.choose(memory, memory.state_token(q0), None, 0)

    # q0 still has untried actions 1 and 2.  The old virtual frontier would
    # probe them locally.  Continuation frontier follows known action 0 toward
    # deeper q2 and only then appends an untried probe.
    assert decision.action == 0
    assert policy.last_telemetry["target_state"] == q2
    assert policy.last_telemetry["target_depth"] == 2
    assert policy.last_telemetry["bypassed_local_frontier"]
    assert policy.last_telemetry["planned_actions"] == (0, 0, 0)


def test_continuation_frontier_extends_when_already_at_deepest_boundary():
    memory = PredictiveRegistry(3)
    q0 = memory.add_state("S0", (), reason="test")
    q1 = memory.add_state("S1", (0,), reason="test")
    memory.record_transition(q0, 0, q1)

    policy = ContinuationFrontierPolicy()
    decision = policy.choose(memory, memory.state_token(q1), None, 0)
    assert decision.action == 0
    assert policy.last_telemetry["target_state"] == q1
    assert policy.last_telemetry["planned_actions"] == (0,)
