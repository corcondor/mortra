import copy
import hashlib
import inspect
import json
import random

import numpy as np
import pytest

from experiments.game_frontier_v1.frozen import BASELINE, BASELINE_SHA256_LF, StructuralLearner, run_fixed_field_policy, solve_fixed_field
from experiments.game_frontier_v1.player import fingerprint
from experiments.game_frontier_v11.designer import FAMILIES, SIZE_FAMILIES, Feedback, choose, generate, mutate
from experiments.game_frontier_v11.measurement import curve_metrics, evaluate_tasks, full_information, learn, make_port, rule_relevance, sample_tasks
from experiments.game_frontier_v11.runner import config, sources
from experiments.game_frontier_v11.world import Engine, OpaqueMap, canonical, game_hash, oracle, validate


def fixture():
    # A correctness fixture, not a benchmark candidate or an authored solution.
    return {"version": "finite-program-v1.1", "domains": [12, 12], "actions": 4,
            "walls": [[x, y] for x in range(12) for y in range(12) if x in (0, 11) or y in (0, 11)],
            "initial": [1, 1], "rendering": {},
            "rules": [{"action": a, "guard": [], "assign": [{"var": i, "op": "add", "value": v}]}
                      for a, (i, v) in enumerate([(0, -1), (0, 1), (1, -1), (1, 1)])]}


def test_frozen_core_and_v1_sources():
    assert hashlib.sha256(BASELINE.read_text(encoding="utf-8").encode()).hexdigest() == BASELINE_SHA256_LF
    assert solve_fixed_field.__defaults__ == (.90, 300, 1e-8)
    src = inspect.getsource(run_fixed_field_policy)
    assert src.count("1e-7") == 2
    assert sources()["scripts/evaluate_cross_domain_generalization.py"] == BASELINE_SHA256_LF


@pytest.mark.parametrize("seed", range(12))
def test_generator_is_finite_deterministic_roundtrip(seed):
    g = generate(random.Random(seed))
    assert g == generate(random.Random(seed))
    e, e2 = Engine(g), Engine(json.loads(canonical(g)))
    s = e.initial
    for a in [random.Random(seed + i).randrange(e.num_actions) for i in range(150)]:
        assert e.step(s, a) == e2.step(s, a)
        s = e.step(s, a)
        assert all(0 <= v < n for v, n in zip(s, e.domains))


def test_rule_priority_atomicity_and_simultaneous_rhs():
    g = fixture()
    g["domains"].append(2)
    g["initial"].append(0)
    g["rules"] = [{"action": 0, "guard": [], "assign": [
        {"var": 0, "op": "set", "value": 0}, {"var": 2, "op": "set", "value": 1}]}]
    e = Engine(g)
    assert e.step(e.initial, 0) == e.initial  # wall rejection is atomic
    g["rules"][0]["assign"] = [{"var": 0, "op": "set", "value": 3}, {"var": 1, "op": "copy_mod", "value": 0}]
    e = Engine(g)
    assert e.step(e.initial, 0)[:2] == (3, 1)
    for bad in (-1, 0, float("inf"), True):
        changed = copy.deepcopy(g)
        changed["domains"][2] = bad
        with pytest.raises(ValueError):
            validate(changed)


def test_task_stratification_distinct_and_nontrivial():
    stats, graph = oracle(Engine(fixture()), 250000)
    assert stats["reachable_states"] == 100
    tasks, population = sample_tasks(graph, 100, 9)
    assert len(tasks) == len({(tuple(t["start"]), tuple(t["target"])) for t in tasks}) == 100
    assert all(t["distance"] >= 4 for t in tasks)
    assert np.median([t["distance"] for t in tasks]) >= 8
    assert tasks == sample_tasks(graph, 100, 9)[0]
    assert population["32+"] == 0


def test_api_and_opaque_labels():
    e = Engine(fixture())
    labels = OpaqueMap(7)
    p = make_port(e, labels)
    assert p.reset() == p.reset() and isinstance(p.reset(), str)
    assert p.reset() != make_port(e, OpaqueMap(8)).reset()
    assert {x for x in dir(p) if not x.startswith("_")} == {"reset", "step", "num_actions", "current_observation", "available_actions"}
    assert all(isinstance(a, int) for a in p.available_actions())
    for name in ("genome", "domains", "walls", "rules", "engine", "hidden_state"):
        assert not hasattr(p, name)


def test_same_original_readout_cached_vs_uncached_and_reuse():
    e = Engine(fixture())
    stats, graph = oracle(e, 250000)
    states, edges, _ = graph
    labels = OpaqueMap(12)
    learner = StructuralLearner(e.num_actions)
    for s in states:
        learner.get_or_add_id(labels.encode(s))
    for u, row in enumerate(edges):
        for a, v in enumerate(row):
            learner.record_transition(u, a, v)
    tasks, _ = sample_tasks(graph, 12, 42)
    before = fingerprint(learner)
    a = evaluate_tasks(learner, e, labels, tasks, 2048)
    b = evaluate_tasks(learner, e, labels, tasks, 2048, cache_enabled=False)
    assert a["task_results"] == b["task_results"]
    assert a["K_sha256"] == b["K_sha256"] and fingerprint(learner) == before
    for t, r in zip(tasks, a["task_results"]):
        ok, steps, reason = run_fixed_field_policy(make_port(e, labels), labels.encode(tuple(t["start"])),
           labels.encode(tuple(t["target"])), learner.build_k_support(), learner.state_to_id, learner.counts, max_steps=2048)
        assert (ok, steps, reason) == (r["success"], r["core_reported_steps"], r["reason"])
    full = full_information(e, graph, tasks, 2048, 12)
    assert full["task_results"] == a["task_results"]


def test_goal_not_inserted_as_learned_transition_or_state():
    e = Engine(fixture())
    stats, graph = oracle(e, 250000)
    tasks, _ = sample_tasks(graph, 12, 42)
    rows = learn(e, tasks, [1, 2, 4, 8], 2048, 19, stats)
    assert rows[0]["learned_states"] <= 2
    assert all(r["evaluation"]["graph_reuse_verified"] and r["evaluation"]["evaluation_updates"] == 0 for r in rows)
    assert [r["learned_transitions"] for r in rows] == sorted(r["learned_transitions"] for r in rows)


def test_difficulty_integral():
    rows = [{"budget": b, "evaluation": {"success_rate": s, "median_success_steps": 7}} for b, s in [(1, 0), (2, .5), (8, 1)]]
    assert curve_metrics(rows) == {"D": 1.25, "B50": 2, "B80": 8, "B90": 8, "final_success": 1, "median_success_steps": 7}


def test_selection_ties_seeded_not_hash_and_failure_gates():
    p = Feedback("zzzz", True, 1, 1, 3, 8, 16, 4)
    c = Feedback("aaaa", True, 1, 1, 3, 8, 16, 4)
    outcomes = [choose("mortra", p, [c], random.Random(i), 8192) for i in range(20)]
    assert p in outcomes and c in outcomes
    assert choose("mortra", p, [c], random.Random(9), 8192) == choose("mortra", p, [c], random.Random(9), 8192)
    renamed_p = Feedback("0000", *list(p.__dict__.values())[1:])
    renamed_c = Feedback("ffff", *list(c.__dict__.values())[1:])
    assert [choose("mortra", renamed_p, [renamed_c], random.Random(i), 8192) is renamed_p for i in range(20)] == [r is p for r in outcomes]
    bad = Feedback("bad", True, .1, 1, 99, 8192, None, 300)
    assert choose("mortra", p, [bad], random.Random(1), 8192) == p
    assert choose("random", p, [bad], random.Random(1), 8192) == bad


@pytest.mark.parametrize("family", FAMILIES)
def test_generic_mutations_and_size_control(family):
    g = generate(random.Random(6))
    for seed in range(30):
        try:
            child = mutate(g, family, random.Random(seed), 32)
        except ValueError:
            continue
        assert game_hash(child) != game_hash(g)
        validate(child)
        if family in SIZE_FAMILIES:
            assert child["rules"] == g["rules"] and child["domains"][2:] == g["domains"][2:]
        break
    # Some edit preconditions are absent; explicit rejection is valid.


def test_rule_relevance_and_oracle_cap():
    g = fixture()
    _, graph = oracle(Engine(g), 250000)
    tasks, _ = sample_tasks(graph, 12, 42)
    audit = rule_relevance(g, tasks, 250000)
    assert audit["nonzero_relevance"] and any(r["fraction"] > 0 for r in audit["rules"])
    status, graph = oracle(Engine(g), 4)
    assert status["status"] == "UNRESOLVED" and graph is None


def test_registered_protocol():
    assert config(2)["checkpoints"] == [2**i for i in range(14)]
    assert config(1)["candidates"] == 6 and config(1)["tasks"] == 40
    assert config(2)["tasks"] == 100 and config(2)["initial_pool"] == 32
    assert config(2)["q"] == .90 and config(2)["cutoff"] == 1e-7


def test_new_harness_artifacts_and_saved_replay_summary(tmp_path, monkeypatch):
    from experiments.game_frontier_v11 import runner, summarize
    cfg = config(1)
    cfg.update(seeds=[201], initial_pool=1, generations=1, candidates=1, tasks=8, checkpoints=[1, 64], horizon=64)
    monkeypatch.setattr(runner, "config", lambda stage: cfg)
    monkeypatch.setattr(summarize, "config", lambda stage: cfg)
    monkeypatch.setattr(runner, "generate", lambda rng: fixture())
    runner.run_seed(1, 201, tmp_path / "input")
    result = summarize.summarize(tmp_path / "input", tmp_path / "summary", 1)
    assert result["runs"] == 3 and result["verified_first_task_replays"] >= 6
    assert (tmp_path / "summary/figures/recorded_worlds.png").exists()
    assert (tmp_path / "input/completed.json").exists()
    with pytest.raises(FileExistsError):
        runner.run_seed(1, 201, tmp_path / "input")
