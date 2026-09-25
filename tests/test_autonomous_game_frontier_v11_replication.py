import inspect

import pytest

from experiments.game_frontier_v11_replication import run


def test_only_evolution_config_difference_is_seed_list():
    old, new = run.evolution.config(2), run.config()
    assert {k for k in old if old[k] != new[k]} == {"seeds"}
    assert new["seeds"] == [1101, 1202, 1303, 1404, 1505, 1606, 1707, 1808]
    assert not set(old["seeds"]) & set(new["seeds"])
    assert run.holdout.verified_sources() == run.evolution.sources()


def test_seed_wrapper_preserves_execution_bytecode_and_other_globals():
    copied = run.evolution_callable()
    assert copied.__code__ is run.evolution.run_seed.__code__
    assert copied.__defaults__ == run.evolution.run_seed.__defaults__
    for k, value in run.evolution.run_seed.__globals__.items():
        if k != "config":
            assert copied.__globals__[k] is value
    assert run.evolution.config(2)["seeds"] != run.SEEDS


def test_holdout_protocol_unchanged_and_no_old_inputs():
    assert run.TASK_SEED_ROOT == run.analysis.TASK_SEED_ROOT
    assert run.config()["checkpoints"] == run.holdout.CONFIG["checkpoints"]
    assert run.config()["horizon"] == run.holdout.CONFIG["horizon"]
    assert run.PROTOCOL["prior_experiment_inputs"] == []
    assert run.PROTOCOL["pass_criterion"] is None
    source = inspect.getsource(run)
    assert "initial-pool" not in source
    for forbidden in ("def mutate", "def generate", "def choose", "def solve_fixed_field", "class StructuralLearner"):
        assert forbidden not in source


def rows():
    return [{"generation": i, "game_hash": str(i), "performance_eligible": i >= 2,
        "D_selection": float(i), "D_holdout": float(i), "D_holdout_exact": str(i),
        "full_info_success": 1., "holdout_success": .9, "classification": "LEARNED_SUCCESS",
        "holdout_tasks": 500, "holdout_successes": 450} for i in range(11)]


def test_endpoints_first_eligible_and_changed_selection_increase_denominator():
    rs = rows()
    rs[4]["game_hash"] = rs[3]["game_hash"]
    rs[7]["D_selection"] = 5.
    rs[8]["D_holdout_exact"] = "6"
    result = run.endpoint(rs)
    assert result["first_eligible_generation"] == 2
    assert result["eligibility_to_final_direction"] == "increase"
    assert result["changed_count"] == 9
    assert result["selection_D_increases"] == 8
    assert result["replicated_holdout_increases"] == 7


def test_no_eligibility_is_not_zero_or_failed_seed():
    rs = rows()
    for r in rs:
        r["performance_eligible"] = False
    result = run.endpoint(rs)
    assert result["first_eligible_generation"] is None
    assert result["eligibility_to_final_direction"] == "NO_ELIGIBLE_GENERATION"


def test_first_eligible_at_final_is_tie_not_increase():
    rs = rows()
    for r in rs:
        r["performance_eligible"] = r["generation"] == 10
    result = run.endpoint(rs)
    assert result["eligible_at_final_only"]
    assert result["eligibility_to_final_direction"] == "tie"


def test_missing_holdout_remains_unmeasured():
    rs = rows()
    rs[-1]["D_holdout_exact"] = None
    rs[-1]["D_holdout"] = None
    result = run.endpoint(rs)
    assert result["eligibility_to_final_direction"] == "unmeasured"
    assert result["unmeasured_holdout_transitions"] == 1


def test_unregistered_seed_is_rejected_before_execution(tmp_path):
    with pytest.raises(AssertionError):
        run.evolve(201, tmp_path / "must-not-exist")
    assert not (tmp_path / "must-not-exist").exists()
