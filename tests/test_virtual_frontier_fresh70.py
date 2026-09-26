"""Harness-only checks on fixtures/archived worlds, never fresh evaluation worlds."""
import json
from unittest.mock import patch

import numpy as np
import pytest

from experiments.task_agent import checkpoint
from experiments.task_agent import run_virtual_frontier_fresh70 as study


def test_seeds_and_equivalence_preregistered():
    assert study.SEEDS == tuple(range(73000000, 73000070))
    assert not set(study.SEEDS) & set(checkpoint.SEEDS)
    assert study.MARGIN == .05
    assert study.config()["failure_cap"] == 4096
    assert study.config()["tasks_per_world"] == 12


def test_exact_snapshot_roundtrip_including_insertion_order():
    _, engine = checkpoint.load_world(None, 2101)
    original = checkpoint.train_snapshots(engine, budgets=(512,))[512]
    data = study.dump_model(original)
    restored = study.load_model(json.loads(json.dumps(data)))
    assert vars(original.core) == vars(restored.core)
    assert study.digest(data) == study.digest(study.dump_model(restored))
    assert list(original.core.counts) == list(restored.core.counts)
    np.testing.assert_array_equal(original.K().toarray(), restored.K().toarray())
    u = 0
    for _ in range(25):
        a, b = original.select(u), restored.select(u)
        assert a == b
        v = original.add(engine.step(original.i2s[u], a))
        w = restored.add(engine.step(restored.i2s[u], b))
        assert v == w
        original.rec(u, a, v)
        restored.rec(u, b, w)
        u = v
    assert vars(original.core) == vars(restored.core)


def test_task_generation_failure_retained_no_retries():
    learner = checkpoint.Learner(1)
    learner.add((0, 0))
    with patch.object(checkpoint, "generate_basic_tasks", side_effect=RuntimeError(("task generation failed", {}))) as basic, \
         patch.object(checkpoint, "generate_branch_tasks", side_effect=RuntimeError(("branch task generation failed", 0))) as branch:
        tasks, failures = study.freeze_tasks(learner, 123)
    assert tasks == []
    assert len(failures) == 2
    assert all(f["category"] == "insufficient_reachable_states" for f in failures)
    basic.assert_called_once_with(learner, 720123, n=3)
    branch.assert_called_once_with(learner, 820123, n=3)


def test_unexpected_engineering_error_is_not_task_unavailability():
    with patch.object(checkpoint, "generate_basic_tasks", side_effect=RuntimeError("infrastructure")):
        with pytest.raises(RuntimeError, match="infrastructure"):
            study.freeze_tasks(None, 123)


def test_generator_outputs_not_filtered():
    basic = [("sequence", (0, 0), {"op": "SEQ", "goals": []})] * 9
    branch = [("branch", (0, 0), {"op": "BRANCH"})] * 3
    with patch.object(checkpoint, "generate_basic_tasks", return_value=basic), \
         patch.object(checkpoint, "generate_branch_tasks", return_value=branch):
        tasks, failures = study.freeze_tasks(None, 123)
    assert tasks == basic + branch
    assert not failures


def fixture_records():
    return [{"seed": 123, "task_id": i, "task_type": "fixture", "policy": p,
             "success": p != "structural", "capped_steps": {
                 "structural": 4096, "frontier_t0": 12, "virtual_frontier": 10,
                 "task_virtual_frontier": 9}[p]} for i in range(12) for p in study.POLICIES]


def test_world_pairing_and_relative_denominator():
    pairs, world = study.pair_world(fixture_records())
    assert len(pairs) == 12
    assert world["D_w"] == -1
    assert world["G_w"] == -2
    assert world["R_w"] == -.1
    assert world["structural_mean_capped"] == 4096
    assert world["success_task_minus_generic"] == 0


def test_missing_policy_never_imputed_as_task_failure():
    with pytest.raises(AssertionError):
        study.pair_world(fixture_records()[:-1])


def test_zero_relative_denominator_not_silently_imputed():
    records = fixture_records()
    for row in records:
        if row["policy"] == "virtual_frontier":
            row["capped_steps"] = 0
    assert study.pair_world(records)[1]["R_w"] is None


def test_bootstrap_units_are_worlds_and_reproducible():
    result = study.endpoint([-2, 0, 5])
    assert result == study.endpoint([-2, 0, 5])
    assert result["n_worlds"] == 3
    assert result["mean"] == 1
    assert result["median"] == 0
    assert (result["lower"], result["higher"], result["tied"]) == (1, 1, 1)
    assert result["ci95"] == [-2, 5]
    assert study.endpoint([])["ci95"] is None


def test_unavailable_world_runs_no_policy(tmp_path):
    output = tmp_path / "world"
    row = {"seed": 123, "status": "task_generation_unavailable"}
    with patch.object(study, "episode") as execute:
        study.evaluate_world(tmp_path, row, output)
    execute.assert_not_called()
    status = study.read_json(output / "status.json")
    assert status["policy_failure"] is False
    assert status["policy_episodes"] == 0


def test_incomplete_70_world_sample_not_redefined(tmp_path):
    registered = [{"seed": s, "status": "task_generation_unavailable"} for s in study.SEEDS]
    with patch.object(study, "source_audit", return_value={}), \
         patch.object(study, "verify_registration", return_value=registered):
        study.aggregate(tmp_path, tmp_path / "missing", tmp_path / "summary")
    result = study.read_json(tmp_path / "summary/summary.json")
    assert result["fixed_worlds"] == 70
    assert result["analyzable_worlds"] == 0
    assert result["confirmatory_status"] == "INCOMPLETE"
    assert result["confirmatory_practical_equivalence"] is None
    assert result["policies"]["structural"]["episodes"] == 0


def test_telemetry_uses_same_state_counterfactual(tmp_path):
    path = tmp_path / "decisions.jsonl"
    entry = {"task_id": 0, "policy": "task_virtual_frontier", "exploration_decision": 0,
             "task_signal_available": True, "field_changed": True,
             "selected_action": 1, "generic_counterfactual_action": 0}
    row = {"task_id": 0, "policy": "task_virtual_frontier", "exploration_decisions": 1,
           "task_signal_available_decisions": 1, "field_changed_decisions": 1}
    path.write_text(json.dumps(entry) + "\n")
    assert study.audit_telemetry(path, [row])["rows"] == 1
    entry["generic_counterfactual_action"] = 1
    path.write_text(json.dumps(entry) + "\n")
    with pytest.raises(AssertionError):
        study.audit_telemetry(path, [row])
