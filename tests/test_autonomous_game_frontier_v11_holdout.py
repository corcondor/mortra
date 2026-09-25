import copy
import inspect
import random

import pytest

from experiments.game_frontier_v11 import measurement as frozen
from experiments.game_frontier_v11.world import Engine, oracle
from experiments.game_frontier_v11_holdout import audit


def fixture():
    return {"version": "finite-program-v1.1", "domains": [12, 12], "actions": 4,
        "walls": [[x, y] for x in range(12) for y in range(12) if x in (0, 11) or y in (0, 11)],
        "initial": [1, 1], "rendering": {},
        "rules": [{"action": a, "guard": [], "assign": [{"var": i, "op": "add", "value": v}]}
                  for a, (i, v) in enumerate([(0, -1), (0, 1), (1, -1), (1, 1)])]}


def test_frozen_source_identity():
    assert len(audit.verified_sources()) == 18
    assert audit.CONFIG["task_seed_root"] == 2026092501
    assert audit.CONFIG["checkpoints"][-1] == 8192


@pytest.mark.parametrize("seed", [1, 9, 2026092501])
def test_sampler_no_exclusions_identical_to_original(seed):
    _, graph = oracle(Engine(fixture()), 1000)
    tasks, pop = audit.sample_holdout(graph, set(), 100, seed)
    reference, original_pop = frozen.sample_tasks(graph, 100, seed)
    assert tasks == reference and pop["available_by_bin"] == original_pop


def test_exclusion_distinct_strata_and_reproducibility():
    _, graph = oracle(Engine(fixture()), 1000)
    selected, _ = frozen.sample_tasks(graph, 100, 9)
    banned = set(map(audit.pair, selected))
    tasks, pop = audit.sample_holdout(graph, banned, 500, 31)
    assert len(tasks) == len(set(map(audit.pair, tasks))) == 500
    assert not banned & set(map(audit.pair, tasks))
    assert all(t["distance"] >= 4 for t in tasks)
    assert sum(pop["original_by_bin"].values()) - sum(pop["available_by_bin"].values()) == 100
    assert (tasks, pop) == audit.sample_holdout(graph, banned, 500, 31)


def test_shortage_census_and_empty_without_padding():
    states = [(i,) for i in range(7)]
    edges = [[min(i + 1, 6)] for i in range(7)]
    graph = states, edges, {s: i for i, s in enumerate(states)}
    tasks, pop = audit.sample_holdout(graph, set(), 500, 5)
    assert len(tasks) == 6 and pop["exhaustive"]
    empty, pop = audit.sample_holdout(graph, set(map(audit.pair, tasks)), 500, 5)
    assert empty == [] and pop["actual"] == 0


def test_same_frozen_training_with_secondary_evaluation(monkeypatch):
    g = fixture()
    stats, graph = oracle(Engine(g), 1000)
    selected, _ = frozen.sample_tasks(graph, 8, 18)
    holdout, _ = audit.sample_holdout(graph, set(map(audit.pair, selected)), 20, 21)
    checkpoints = [1, 4, 32, 256]
    monkeypatch.setitem(audit.CONFIG, "checkpoints", checkpoints)
    monkeypatch.setitem(audit.CONFIG, "horizon", 64)
    original = frozen.learn(Engine(g), selected, checkpoints, 64, 917, stats)
    bundle = {"genome": g, "player_seed": 917, "holdout_tasks": holdout,
              "archived_final": {"tasks": selected, "learning": original, "oracle": stats}}
    paired, rows = audit.paired_learning(bundle)
    assert len(paired) == 4
    for new, old in zip(rows, original):
        audit.reproduce_evaluation(new["evaluation"], old["evaluation"])
    broken = copy.deepcopy(bundle)
    broken["archived_final"]["learning"][1]["evaluation"]["K_sha256"] = "tampered"
    with pytest.raises(AssertionError, match="K_sha256"):
        audit.paired_learning(broken)


def test_common_bin_standardization_and_missing_mass():
    s = {"tasks": 100, "success_by_distance_bin": {
        "4-7": {"tasks": 50, "successes": 40}, "8-15": {"tasks": 50, "successes": 10},
        "16-31": {"tasks": 0, "successes": 0}, "32+": {"tasks": 0, "successes": 0}}}
    h = {"tasks": 500, "success_by_distance_bin": {
        "4-7": {"tasks": 500, "successes": 400}, "8-15": {"tasks": 0, "successes": 0},
        "16-31": {"tasks": 0, "successes": 0}, "32+": {"tasks": 0, "successes": 0}}}
    r = audit.standardized(s, h)
    assert r["selection_mass_covered"] == .5 and r["delta"] == 0


def test_no_world_generation_or_selection_call_in_audit():
    source = inspect.getsource(audit)
    assert "designer import" not in source
    for call in ("generate(", "mutate(", "choose("):
        assert call not in source
