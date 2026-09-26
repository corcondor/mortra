"""Mechanism gate, not a performance benchmark. Historical tests stay unchanged."""
import copy
from unittest.mock import patch

import numpy as np
import pytest

from experiments.task_agent import checkpoint, online_eval
from experiments.task_agent.core import ExactState, SequenceTask, ProductPlanner
from experiments.task_agent.exploration import FrontierFieldPolicy
from experiments.task_agent.online import OnlineTaskAgent
from experiments.task_agent.run_online import policy_for
from experiments.task_agent.virtual_frontier import VirtualFrontierPolicy, build_frontier_fields


def fixture():
    learner = checkpoint.Learner(2).core
    for state in ("S", "L", "R"):
        learner.get_or_add_id(state)
    learner.record_transition(0, 0, 1)
    learner.record_transition(0, 1, 2)
    return learner


def tasks():
    return [SequenceTask([ExactState(side), ExactState("MISSING")]) for side in ("L", "R")]


def test_one_learned_graph_two_tasks_different_exploration_actions():
    learner = fixture()
    before = copy.deepcopy(learner.__dict__)
    generic, aware = [], []
    for task in tasks():
        assert ProductPlanner().choose_action(learner, task, "S", 0) is None
        plain = VirtualFrontierPolicy()
        conditioned = VirtualFrontierPolicy(task_aware=True)
        generic.append(plain.choose(learner, "S", task, 0).action)
        aware.append(conditioned.choose(learner, "S", task, 0).action)
        assert conditioned.last_telemetry["task_signal_available"]
    assert generic == [0, 0]
    assert aware == [0, 1]
    assert learner.__dict__ == before


def test_one_factorization_two_rhs_and_terminal_rows():
    import experiments.task_agent.virtual_frontier as module
    real_lu = module.splu
    with patch.object(module, "splu", wraps=real_lu) as lu:
        model = build_frontier_fields(fixture(), "S", tasks()[0], 0)
    assert lu.call_count == 1
    assert model.sources.shape[1] == 2
    assert len(model.virtual) == 4
    assert model.kernel[len(model.states):].nnz == 0
    assert np.array_equal(np.asarray(model.kernel[:3].sum(axis=1)).ravel(), np.ones(3))
    assert np.array_equal(model.sources[:3], np.zeros((3, 2)))
    assert np.allclose(model.values[3:], model.sources[3:], atol=1e-15, rtol=0)
    assert model.residual < 1e-12
    assert model.values[0, 0] == pytest.approx(0.9**2)


def test_sources_use_pre_unknown_memory_only():
    model = build_frontier_fields(fixture(), "S", tasks()[0], 0)
    for index, (_, memory, _) in enumerate(model.virtual, len(model.states)):
        assert model.sources[index, 1] == np.exp(tasks()[0].progress(memory))


@pytest.mark.parametrize("task", tasks())
def test_task_off_exactly_equals_generic(task):
    learner = fixture()
    generic = VirtualFrontierPolicy().choose(learner, "S", task, 0)
    off = VirtualFrontierPolicy(task_aware=True, task_source=False)
    decision = off.choose(learner, "S", task, 0)
    assert decision.action == generic.action
    assert decision.score == generic.score
    assert not off.last_telemetry["field_changed"]
    assert not off.last_telemetry["task_signal_available"]


def test_uniform_progress_explicitly_reports_no_signal():
    policy = VirtualFrontierPolicy(task_aware=True)
    task = SequenceTask([ExactState("MISSING")])
    policy.choose(fixture(), "S", task, 0)
    assert not policy.last_telemetry["task_signal_available"]
    assert not policy.last_telemetry["field_changed"]


def test_uniform_nonzero_progress_cannot_change_action():
    policy = VirtualFrontierPolicy(task_aware=True)
    task = SequenceTask([ExactState("S"), ExactState("MISSING")])
    policy.choose(fixture(), "S", task, 1)
    assert policy.last_telemetry["source_min"] > 1
    assert not policy.last_telemetry["task_signal_available"]
    assert not policy.last_telemetry["field_changed"]


def test_opaque_learned_interface_has_no_world_or_oracle():
    original = fixture()
    allowed = {"state_to_id", "id_to_state", "num_actions", "action_visits", "counts"}

    class LearnedOnly:
        __slots__ = ()

        def __getattribute__(self, name):
            if name not in allowed:
                raise AssertionError("policy accessed forbidden attribute: " + name)
            return getattr(original, name)

    policy = VirtualFrontierPolicy(task_aware=True)
    assert policy.choose(LearnedOnly(), "S", tasks()[1], 0).action == 1


def test_untried_action_never_reads_even_a_poisoned_successor_record():
    learner = fixture()
    original = learner.counts

    class RecordedOnly(dict):
        def get(self, key, default=None):
            assert learner.action_visits.get(key, 0) > 0
            return super().get(key, default)

    learner.counts = RecordedOnly(original)
    build_frontier_fields(learner, "S", tasks()[0], 0)


def test_unreachable_frontiers_are_not_added():
    learner = fixture()
    learner.get_or_add_id("DISCONNECTED")
    model = build_frontier_fields(learner, "S", tasks()[0], 0)
    assert all(u != 3 for u, _, _ in model.virtual)


def test_tried_action_without_evidence_is_an_error_not_a_self_loop():
    learner = fixture()
    learner.action_visits[(1, 0)] = 1
    with pytest.raises(ValueError, match="no recorded successor"):
        build_frontier_fields(learner, "S", tasks()[0], 0)


def test_no_frontier_fallback_and_telemetry():
    learner = fixture()
    for u in (1, 2):
        for action in (0, 1):
            learner.record_transition(u, action, u)
    policy = VirtualFrontierPolicy(task_aware=True)
    assert policy.choose(learner, "S", tasks()[0], 0).action == 0
    assert policy.last_telemetry["virtual_nodes"] == 0
    assert not policy.last_telemetry["virtual_field_decision"]
    assert not policy.last_telemetry["task_signal_available"]


def test_online_exploration_really_calls_the_new_policy_without_accepting_path():
    class Environment:
        def reset(self, state):
            self.state = state
            return state

        def step(self, action):
            self.state = {"S": ("L", "R"), "L": ("MISSING", "L"),
                          "R": ("MISSING", "R")}[self.state][action]
            return self.state

    for task, expected in zip(tasks(), (0, 1)):
        policy = VirtualFrontierPolicy(task_aware=True)
        result = OnlineTaskAgent(fixture(), policy, max_task_steps=10).run_task(Environment(), task, "S")
        assert result.success
        assert result.decisions[0]["kind"] == "exploration"
        assert result.decisions[0]["action"] == expected


def test_frontier_t0_factory_is_the_unchanged_baseline():
    left, right = fixture(), fixture()
    task = tasks()[0]
    baseline = FrontierFieldPolicy(low_count_threshold=0)
    registered = policy_for("frontier_t0", online_eval.SparseProductPlanner())
    assert type(baseline) is type(registered)
    for state in ("S", "L", "R"):
        assert baseline.choose(left, state, task, 0) == registered.choose(right, state, task, 0)
    assert left.__dict__ == right.__dict__


@pytest.mark.parametrize("seed", (2202, 2505))
def test_task_off_matches_generic_on_real_online_trajectory(seed):
    _, engine = checkpoint.load_world(None, seed)
    snapshots = checkpoint.train_snapshots(engine)
    task_type, start, spec = checkpoint.generate_basic_tasks(snapshots[8192], 720000 + seed, n=1)[0]
    results = []
    for policy in (VirtualFrontierPolicy(), VirtualFrontierPolicy(task_aware=True, task_source=False)):
        learner = copy.deepcopy(snapshots[512].core)
        agent = OnlineTaskAgent(learner, policy, planner=online_eval.CachingSparsePlanner(),
                                max_task_steps=128, max_exploration_steps=128)
        result = agent.run_task(online_eval.WorldEnv(engine), online_eval.task_from_spec(spec), start)
        results.append((result.success, result.task_steps, result.exploration_steps,
                        [(d["action"], d.get("world_state")) for d in result.decisions],
                        dict(learner.action_visits), dict(learner.counts)))
    assert results[0] == results[1]
