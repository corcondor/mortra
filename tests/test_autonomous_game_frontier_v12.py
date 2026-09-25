from dataclasses import asdict, fields, FrozenInstanceError
import inspect
import math
import random

import pytest

from experiments.game_frontier_v12 import run, audit
from experiments.game_frontier_v12.proposal import Context, ContextualUCB, Outcome, FAMILIES, reward
from tests.test_autonomous_game_frontier_v11 import fixture


def ctx():
    return Context(100, 4, 2, 4, 144, 8., 1024)


def good(d=9.):
    return Outcome(True, True, d, 2048, 4096, .9, 1.)


def test_frozen_sources_and_no_core_changes():
    assert len(run.holdout.verified_sources()) == 18
    assert run.run_condition.__globals__["frozen"].choose is run.frozen.choose
    assert run.run_condition.__globals__["frozen"].train_candidate is run.frozen.train_candidate
    old, new = run.frozen.config(2), run.config(2)
    assert {k for k in old if old[k] != new[k]} == {"seeds", "conditions"}
    assert new["q"] == .90 and new["cutoff"] == 1e-7
    assert run.config(1)["candidates"] == 8 and run.config(1)["generations"] == 5
    assert run.config(1)["checkpoints"] == old["checkpoints"]


def test_new_seeds_and_predeclared_protocol():
    assert run.SEEDS == [2101, 2202, 2303, 2404, 2505, 2606, 2707, 2808]
    assert not set(run.SEEDS) & set(run.SMOKE_SEEDS)
    assert run.PROTOCOL["prior_experiment_inputs"] == []
    assert run.PROTOCOL["pass_criterion"] is None


def test_same_frozen_G0_path_and_seed_pairing():
    wrapper = run.seed_callable(2)
    assert wrapper.__code__ is run.frozen.run_seed.__code__
    for key, val in run.frozen.run_seed.__globals__.items():
        if key not in ("config", "CONDITIONS", "run_condition"):
            assert wrapper.__globals__[key] is val


def test_no_leakage_strict_numeric_api():
    assert {f.name for f in fields(Context)} == {"reachable_states", "rules", "variables", "actions", "board_area", "selection_D", "B80"}
    assert {f.name for f in fields(Outcome)} == {"valid", "eligible", "D", "B80", "B90", "final_success", "full_info_success"}
    for forbidden in ("holdout_tasks", "holdout_D", "holdout_success", "oracle_path"):
        with pytest.raises(TypeError):
            Context(**asdict(ctx()), **{forbidden: []})
        with pytest.raises((FrozenInstanceError, TypeError, AttributeError)):
            setattr(ctx(), forbidden, [])
    with pytest.raises(AssertionError):
        ContextualUCB(13).update(ctx(), FAMILIES[0], {**asdict(good()), "holdout_D": 13})


def test_first_generation_uniform_despite_online_updates():
    model = ContextualUCB(13)
    for i in range(8):
        d = model.decision(ctx(), 1)
        assert all(p == 1/14 for p in d["probabilities"].values())
        model.update(ctx(), FAMILIES[i], good())
    d = model.decision(ctx(), 2)
    assert all(d["probabilities"][a] == 0 for a in FAMILIES[:8])
    assert all(d["probabilities"][a] == 1/6 for a in FAMILIES[8:])


def test_reward_gate_negative_and_missing():
    assert reward(8, good(9)) == 1
    assert reward(8, good(7)) == -1
    assert reward(8, Outcome(True, False, 13, None, None, .2, .4)) == 0
    assert reward(8, run.outcome_of(None)) == 0
    assert run.delta_crossing(None, 1024)["delta"] is None
    with pytest.raises(AssertionError):
        reward(8, Outcome(True, True, 13, None, None, .2, .4))


def test_context_updates_independent_and_deterministic():
    a, b = ContextualUCB(13), ContextualUCB(13)
    for i in range(100):
        arm = FAMILIES[i % 14]
        outcome = good(7. if i % 2 else 9.)
        assert a.update(ctx(), arm, outcome) == b.update(ctx(), arm, outcome)
        assert a.decision(ctx(), 2) == b.decision(ctx(), 2)
    other = Context(400, 4, 2, 4, 576, 8., 1024)
    assert all(n == 0 for n in a.decision(other, 2)["counts"].values())
    assert all(math.isfinite(v) for v in a.decision(ctx(), 2)["ucb"].values())


@pytest.mark.parametrize("condition", ["uniform", "random", "size_only"])
def test_static_proposal_matches_frozen_RNG_and_mutation(condition):
    g = fixture()
    for generation in (1, 4):
        for slot in range(8):
            rng = random.Random(run.io.derive(700001, generation, slot, "mutation"))
            arm = rng.choice(run.frozen.SIZE_FAMILIES if condition == "size_only" else FAMILIES)
            new_arm, new_rng, _ = run.proposal(ContextualUCB(13), ctx(), condition, 700001, generation, slot)
            assert new_arm == arm and new_rng.getstate() == rng.getstate()
            try:
                expected = run.frozen.mutate(g, arm, rng, 32)
            except ValueError:
                with pytest.raises(ValueError):
                    run.frozen.mutate(g, new_arm, new_rng, 32)
            else:
                assert expected == run.frozen.mutate(g, new_arm, new_rng, 32)


def test_generation_one_adaptive_uniform_identical_proposals():
    model = ContextualUCB(13)
    for slot in range(8):
        a, ar, _ = run.proposal(model, ctx(), "adaptive", 700001, 1, slot)
        b, br, _ = run.proposal(model, ctx(), "uniform", 700001, 1, slot)
        assert a == b and ar.getstate() == br.getstate()
        model.update(ctx(), a, good())


@pytest.mark.parametrize("condition", ["uniform", "random", "size_only", "adaptive"])
def test_harness_budget_replay_and_uniform_end_to_end_fixture(tmp_path, monkeypatch, condition):
    cfg = run.config()
    cfg["generations"] = 2
    def prepare(g, cfg, seed):
        return {"game_hash": run.frozen.game_hash(g), "oracle": {"reachable_states": 100},
                "valid": True, "full_info": {"success_rate": 1.}, "preparation_cpu_seconds": 0}
    def train(g, p, cfg, seed, meta, directory):
        return {**p, **meta, "D": float(len(g["rules"])), "B50": 32, "B80": 64, "B90": 128,
                "final_success": 1., "median_success_steps": 5, "classification": "LEARNED_SUCCESS"}
    monkeypatch.setattr(run.frozen, "prepare", prepare)
    monkeypatch.setattr(run.frozen, "train_candidate", train)
    monkeypatch.setattr(run, "provenance", lambda stage: {})
    g = fixture()
    chosen = {"genome": g, "prepared": prepare(g, cfg, 700001)}
    result = run.run_condition(cfg, 700001, condition, chosen, tmp_path / "new", {}, lambda _: None)
    assert run.validate_run(result)
    assert len(result["mutation_history"]) == 16
    if condition != "size_only":
        assert any(h["status"] == "INVALID" for h in result["mutation_history"])
    if condition != "adaptive":
        before = run.frozen.run_condition(cfg, 700001, "mortra" if condition == "uniform" else condition,
                                          chosen, tmp_path / "old", {}, lambda _: None)
        assert result["frontier"] == before["frontier"]
        assert result["candidates"] == before["candidates"]


def test_holdout_audit_preserves_prior_player_function():
    src = inspect.getsource(audit.audit_seed)
    assert "rep.audit_seed.__code__" in src
    assert run.config()["checkpoints"] == run.holdout.CONFIG["checkpoints"]
