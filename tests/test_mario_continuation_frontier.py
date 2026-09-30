import numpy as np

from experiments.mario_continual.port import estimate_profile_shift
from experiments.mario_continual.predictive import PredictiveRegistry
from experiments.task_agent.continuation_frontier import ContinuationFrontierPolicy
from experiments.task_agent.virtual_frontier import VirtualFrontierPolicy


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
    memory.history_visual_position[(0, 0)] = 2.0
    memory.history_visual_motion_count[(0, 0)] = 1

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
    memory.history_visual_position[(0,)] = 1.0
    memory.history_visual_motion_count[(0,)] = 1

    policy = ContinuationFrontierPolicy()
    decision = policy.choose(memory, memory.state_token(q1), None, 0)
    assert decision.action == 0
    assert policy.last_telemetry["target_state"] == q1
    assert policy.last_telemetry["planned_actions"] == (0,)


def test_edge_profile_shift_recovers_global_translation():
    rng = np.random.default_rng(20260930)
    previous = rng.normal(size=64)
    current = np.roll(previous, -3)
    shift, score, margin, reliable = estimate_profile_shift(previous, current)
    assert shift == 3
    assert reliable
    assert score > .99
    assert margin > .02


def test_visual_position_propagates_only_from_rgb_motion_evidence():
    memory = PredictiveRegistry(2)
    source = memory.belief("A", ())
    target, _ = memory.update(
        source, 0, "B", (), (0,),
        visual_delta=2, visual_reliable=True)
    q1 = target.resolved_state
    assert memory.visual_position(q1) == 2.0
    assert memory.visual_motion_count(q1) == 1

    source2 = memory.belief("B", (0,))
    target2, _ = memory.update(
        source2, 1, "C", (0,), (0, 1),
        visual_delta=7, visual_reliable=False)
    q2 = target2.resolved_state
    # Ambiguous image registration must not manufacture progress.
    assert memory.visual_position(q2) == 2.0
    assert memory.visual_motion_count(q2) == 1


def test_visual_displacement_outranks_history_depth_once_observed():
    memory = PredictiveRegistry(2)
    q0 = memory.add_state("S0", (), reason="test")
    q_visual = memory.add_state("SV", (0,), reason="test")
    q_deep = memory.add_state("SD", (1, 1, 1, 1), reason="test")
    memory.record_transition(q0, 0, q_visual)
    memory.record_transition(q0, 1, q_deep)
    memory.history_visual_position[(0,)] = 3.0
    memory.history_visual_motion_count[(0,)] = 1
    memory.history_visual_position[(1, 1, 1, 1)] = 0.0
    memory.history_visual_motion_count[(1, 1, 1, 1)] = 0

    policy = ContinuationFrontierPolicy()
    decision = policy.choose(memory, memory.state_token(q0), None, 0)
    assert decision.action == 0
    assert policy.last_telemetry["target_state"] == q_visual
    assert policy.last_telemetry["target_visual_extent"] == 3.0


def test_no_motion_signal_reproduces_virtual_frontier_action():
    memory = PredictiveRegistry(3)
    q0 = memory.add_state("S0", (), reason="test")
    q1 = memory.add_state("S1", (0,), reason="test")
    memory.record_transition(q0, 0, q1)

    class Task:
        initial_memory = 0
        def advance(self, memory, world_state): return 0
        def accepting(self, memory): return False
        def progress(self, memory): return 0.0

    task = Task()
    continuation = ContinuationFrontierPolicy()
    virtual = VirtualFrontierPolicy(task_aware=False, task_source=False)
    a = continuation.choose(memory, memory.state_token(q0), task, 0)
    b = virtual.choose(memory, memory.state_token(q0), task, 0)
    assert a.action == b.action
    assert continuation.last_telemetry["bootstrap_virtual"]
