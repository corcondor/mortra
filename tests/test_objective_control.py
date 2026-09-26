import copy
import io
from math import prod
from types import SimpleNamespace

import numpy as np
import pytest
from scipy.sparse import csr_matrix

from experiments.task_agent import checkpoint, online_eval
from experiments.task_agent.core import ExactState, SequenceTask
from experiments.task_agent.objective_control import (
    ObjectiveControlPolicy, audit_fields, deadline_target,
    doob_distribution, scaling_certificate,
)
from experiments.task_agent.run_objective_control import episode
from experiments.task_agent.run_virtual_frontier_fresh70 import dump_model
from experiments.task_agent.run_virtual_frontier_pilot import episode as old_episode
from experiments.task_agent.virtual_frontier import build_frontier_fields


def fixture():
    learner = checkpoint.Learner(2)
    for s in ("S", "L", "R"):
        learner.add(s)
    learner.rec(0, 0, 1)
    learner.rec(0, 1, 2)
    return learner.core


def task():
    return SequenceTask([ExactState("R"), ExactState("MISSING")])


def test_expected_hitting_time_weighted_contraction_exact_example():
    P = csr_matrix([[.5, .5], [0, .5]])
    result = scaling_certificate(P, np.array([[0.], [.5]]))
    assert result["t_min"] == 2
    assert result["t_max"] == 4
    assert result["alpha"] == .75
    assert result["reconstructed_field_relative_error"] == 0


def test_proper_frontier_undiscounted_generic_is_one():
    fields = build_frontier_fields(fixture(), "S", task(), 0)
    result = audit_fields(fields)
    assert result["undiscounted_applicable"]
    assert result["undiscounted_generic_max_error_from_one"] < 1e-12
    assert result["discounted_tilted_expected_hitting_steps"][0] == pytest.approx(2)


def test_closed_nonterminal_class_not_given_artificial_hitting_time():
    learner = fixture()
    for a in (0, 1):
        learner.record_transition(1, a, 1)
    fields = build_frontier_fields(learner, "S", task(), 0)
    result = audit_fields(fields)
    assert not result["undiscounted_applicable"]
    assert "undiscounted_certificate" not in result
    actions, p, _ = doob_distribution(fields, 0)
    assert dict(zip(actions, p)) == {0: 0., 1: 1.}


@pytest.mark.parametrize("column", (0, 1))
def test_doob_normalization_and_same_mode(column):
    fields = build_frontier_fields(fixture(), "S", task(), 0)
    actions, p, checks = doob_distribution(fields, column)
    assert p.sum() == pytest.approx(1)
    assert checks["numeric_mode_agreement"]
    expected = np.array([fields.values[fields.actions[0][a], column] for a in actions])
    assert np.allclose(p, expected / expected.sum(), rtol=1e-14, atol=0)


def test_ratio_is_relative_policy_reweighting():
    fields = build_frontier_fields(fixture(), "S", task(), 0)
    a, p0, _ = doob_distribution(fields, 0)
    _, p1, _ = doob_distribution(fields, 1)
    ratio = fields.values[:, 1] / fields.values[:, 0]
    assert np.allclose(p1 / p0, [ratio[fields.actions[0][x]] / ratio[0] for x in a])


def deadline_fixture():
    # Action 0 reaches utility 1 in one step. Action 1 reaches utility 2 in three.
    return SimpleNamespace(states=[0, 1, 2], virtual=[3, 4],
        actions=[{0: 3, 1: 1}, {0: 2, 1: 2}, {0: 4, 1: 4}],
        sources=np.array([[0., 0.], [0., 0.], [0., 0.], [1., 1.], [1., 2.]]))


def test_deadline_uses_remaining_budget_and_existing_weights():
    f = deadline_fixture()
    assert deadline_target(f, 1, 2)["action"] == 0
    assert deadline_target(f, 1, 3)["action"] == 1
    assert deadline_target(f, 0, 3)["action"] == 0
    assert deadline_target(f, 1, 0) is None


def test_deadline_matches_exhaustive_finite_paths():
    f = deadline_fixture()
    for budget in range(1, 5):
        paths = [(0, 0, None)]
        terminals = []
        while paths:
            u, length, first = paths.pop()
            if u >= len(f.states):
                terminals.append((f.sources[u, 1], -length, -first))
            elif length < budget:
                for a, v in f.actions[u].items():
                    paths.append((v, length + 1, a if first is None else first))
        result = deadline_target(f, 1, budget)
        assert (result["terminal_weight"], -result["known_steps_including_probe"], -result["action"]) == max(terminals)


@pytest.mark.parametrize("method", ("doob", "deadline"))
def test_new_readout_accesses_only_learned_interface(method):
    original = fixture()
    before = copy.deepcopy(vars(original))
    allowed = {"state_to_id", "id_to_state", "num_actions", "action_visits", "counts"}

    class LearnedOnly:
        def __getattribute__(self, name):
            if name not in allowed:
                raise AssertionError(name)
            return getattr(original, name)

    policy = ObjectiveControlPolicy(method, True, 99, lambda: 30)
    assert policy.choose(LearnedOnly(), "S", task(), 0).action in (0, 1)
    assert vars(original) == before


def test_fixed_seed_doob_stream_reproduces():
    streams = []
    for _ in range(2):
        policy = ObjectiveControlPolicy("doob", True, 200, lambda: 30)
        streams.append([policy.choose(fixture(), "S", task(), 0).action for _ in range(20)])
    assert streams[0] == streams[1]


def test_each_q_below_one_does_not_imply_vanishing_product():
    n = 1000
    assert prod(1 - 1 / (k + 2)**2 for k in range(n)) == pytest.approx((n + 2) / (2 * (n + 1)))


@pytest.mark.parametrize("aware", (False, True))
def test_instrumented_baseline_matches_frozen_executor(aware):
    class Engine:
        num_actions = 2
        initial = (0,)

        def step(self, s, a):
            return {(0,): ((1,), (2,)), (1,): ((3,), (1,)),
                    (2,): ((3,), (2,)), (3,): ((3,), (3,))}[s][a]

    learner = checkpoint.Learner(2)
    for s in ((0,), (1,), (2,)):
        learner.add(s)
    learner.rec(0, 0, 1)
    learner.rec(0, 1, 2)
    spec = {"op": "SEQ", "goals": [{"kind": "exact", "state": [2]}, {"kind": "exact", "state": [3]}]}
    row = {"seed": 1, "task_id": 0, "task_type": "sequence", "spec": spec, "start": [0]}
    new, trace = episode(dump_model(learner), Engine(), row, "fixed_task" if aware else "fixed_generic", 0, 1, io.StringIO())
    old = old_episode(learner.core, Engine(), spec, [0], "task_virtual_frontier" if aware else "virtual_frontier", io.StringIO(), {})
    for key in ("success", "task_steps", "exploration_steps", "replans", "failure_reason", "capped_steps"):
        assert new[key] == old[key]
    assert len(trace) == new["task_steps"]
