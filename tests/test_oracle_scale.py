"""Gate the adapter against the supplied definitions, not a new oracle theory."""
import copy
import io
import random

import numpy as np
import pytest

from experiments.task_agent import checkpoint, online_eval
from experiments.task_agent.oracle_diagnostics import OraclePolicy, reference
from experiments.task_agent.run_oracle_scale import episode, reference_audit
from experiments.task_agent.run_virtual_frontier_fresh70 import dump_model, load_model
from experiments.task_agent.virtual_frontier import VirtualFrontierPolicy
from experiments.game_frontier_v11.designer import generate


class TableEngine:
    num_actions = 2
    initial = (0,)

    def step(self, state, action):
        return ((state[0] + action + 1) % 4,)


def fixture(complete=False):
    engine = TableEngine()
    model = checkpoint.Learner(engine.num_actions)
    for i in range(4 if complete else 1):
        model.add((i,))
    if complete:
        for i in range(4):
            for a in range(2):
                model.rec(i, a, model.s2i[engine.step((i,), a)])
    return engine, dump_model(model)


def exact(i):
    return {"kind": "exact", "state": [i]}


SPECS = [
    {"op": "SEQ", "goals": [exact(1), exact(3)]},
    {"op": "ALL", "goals": [exact(1), exact(2), exact(3)]},
    {"op": "SEQ", "goals": [{"kind": "var_eq", "var": 0, "value": 1}, exact(3)]},
    {"op": "BRANCH", "A": exact(1), "CA": exact(3), "B": exact(2), "CB": exact(0)},
]


def test_preserved_bundle_and_780_rows():
    audit = reference_audit()
    assert audit["bundle_checksums_match"] and audit["four_shards_exact_match"]
    assert audit["unique_tasks"] == 780
    assert audit["recovery_fraction"] == pytest.approx(0.881611661244264)


@pytest.mark.parametrize("name", ["run_oracle_headroom.py", "run_oracle_source_linear_shard.py"])
def test_definitions_loaded_without_original_batch_io(name):
    ref = reference(name)
    assert ref.Q == .90 and ref.CAP == 4096
    assert not hasattr(ref, "saved") and not hasattr(ref, "rows")


@pytest.mark.parametrize("seed", [77000000, 77000001])
def test_reference_and_frozen_world_transitions(seed):
    genome = generate(random.Random(seed))
    original = reference().Engine(genome)
    frozen = checkpoint.Engine(genome)
    states, seen = [frozen.initial], {frozen.initial}
    for s in states:
        for a in range(frozen.num_actions):
            ns = frozen.step(s, a)
            assert ns == original.step(s, a)
            if ns not in seen:
                states.append(ns)
                seen.add(ns)


@pytest.mark.parametrize("spec", SPECS)
@pytest.mark.parametrize("complete", [False, True])
def test_frozen_task_planner_and_virtual_policy_match_reference(spec, complete):
    engine, data = fixture(complete)
    learner = load_model(data).core
    ref = reference()
    original = ref.Learner.from_json(data)
    task = online_eval.task_from_spec(spec)
    original_task = ref.task_from(spec)
    for state in learner.id_to_state:
        m = task.advance(task.initial_memory, state)
        assert m == original_task.advance(original_task.initial_memory, state)
        fp, rp = online_eval.CachingSparsePlanner(), ref.Planner()
        fm = fp.build(learner, task, state, m)
        rm = rp.build(original, original_task, state, m)
        assert fm.states == rm[0] and fm.actions == rm[2]
        assert fm.reachable_to_accept == rm[3]
        if fm.psi is not None:
            np.testing.assert_array_equal(fm.psi, rm[4])
        assert fp.choose_action(learner, task, state, m, fm) == rp.choose(original, original_task, state, m, rm)
        for aware in [False, True]:
            policy = VirtualFrontierPolicy(task_aware=aware)
            expected, _ = ref.policy_action(original, state, original_task, m, "current" if aware else "generic")
            assert policy.choose(learner, state, task, m).action == expected


@pytest.mark.parametrize("mode", ["oracle_source", "oracle_direct"])
def test_oracle_reads_but_does_not_fill_learned_transitions(mode):
    engine, data = fixture()
    learner = load_model(data).core
    before = copy.deepcopy(vars(learner))
    task = online_eval.task_from_spec({"op": "SEQ", "goals": [exact(2)]})
    policy = OraclePolicy(engine, learner.id_to_state, task, mode)
    assert policy.choose(learner, (0,), task, 0).action == 1
    # The unknown action reaches the goal immediately: remaining distance is zero.
    assert policy.last_telemetry["true_remaining_distances_after_action"][1] == 0
    assert vars(learner) == before


@pytest.mark.parametrize("spec", SPECS)
@pytest.mark.parametrize("mode", ["generic", "current_task", "oracle_source", "oracle_direct"])
def test_canonical_executor_matches_original_episode(spec, mode):
    engine, data = fixture()
    before = copy.deepcopy(data)
    ref = reference()
    original = ref.Learner.from_json(data)
    task = ref.task_from(spec)
    if mode == "oracle_source":
        expected = ref.run_episode_oracle_source(original, engine, task, (0,))
    elif mode == "oracle_direct":
        expected = ref.run_oracle_episode(original, engine, task, (0,))
    else:
        expected = ref.run_episode(original, engine, task, (0,), "current" if mode == "current_task" else "generic")
    row, trace = episode(data, engine, {"seed": -1, "task_id": 0, "task_type": "fixture",
                         "spec": spec, "start": [0]}, mode, io.StringIO())
    assert (row["success"], row["capped_steps"], row["exploration_steps"]) == expected[:3]
    assert len(trace) == row["task_steps"]
    assert data == before


def test_unreachable_distance_keeps_original_sentinel():
    class Disconnected(TableEngine):
        def step(self, state, action):
            return state
    engine, data = fixture()
    task = online_eval.task_from_spec({"op": "SEQ", "goals": [exact(3)]})
    oracle = reference().TrueOracle(Disconnected(), [(0,), (3,)], task)
    action, distances = oracle.action((0,), 0)
    assert action == 0 and distances == {0: 10**9, 1: 10**9}
