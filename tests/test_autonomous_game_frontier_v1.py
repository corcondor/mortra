import copy
import hashlib
import inspect
import json
from pathlib import Path
import random

import numpy as np
import pytest

from experiments.game_frontier_v1.designer import (
    FAMILIES, SIZE_FAMILIES, Feedback, _add_object, _rule, choose, complexity, initial_game, mutate,
)
from experiments.game_frontier_v1.frozen import (
    BASELINE, BASELINE_SHA256_LF, StructuralLearner, load_baseline, run_fixed_field_policy, solve_fixed_field,
)
from experiments.game_frontier_v1.player import evaluate_frozen, fingerprint, learn_game, random_policy, rollout
from experiments.game_frontier_v1.runner import config, sources
from experiments.game_frontier_v1.world import Engine, OpaqueMap, State, canonical, exact_oracle, game_hash, make_port, validate


def test_original_source_sha_and_defaults():
    assert hashlib.sha256(BASELINE.read_text(encoding="utf-8").encode()).hexdigest() == BASELINE_SHA256_LF
    assert solve_fixed_field.__defaults__ == (0.90, 300, 1e-8)
    assert sources()["scripts/evaluate_cross_domain_generalization.py"] == BASELINE_SHA256_LF
    assert set(load_baseline()) >= {"StructuralLearner", "solve_fixed_field", "run_fixed_field_policy"}


def test_loading_does_not_execute_legacy_preamble():
    log = BASELINE.parent.parent / "reports/cross_domain_generalization/run.log"
    before = log.read_bytes() if log.exists() else None
    load_baseline()
    assert (log.read_bytes() if log.exists() else None) == before


@pytest.mark.parametrize("seed", [201, 302, 403])
def test_json_determinism_and_oracle(seed):
    genome = initial_game(seed)
    clone = json.loads(json.dumps(genome))
    assert clone == genome and game_hash(genome) == game_hash(clone)
    first, second = Engine(genome), Engine(clone)
    s1, s2 = first.initial, second.initial
    for i in range(300):
        action = random.Random(i).randrange(8)
        assert first.step(s1, action) == first.step(s1, action)
        s1, s2 = first.step(s1, action), second.step(s2, action)
        assert s1 == s2
    oracle, states = exact_oracle(first)
    assert oracle["status"] == "SOLVABLE"
    assert oracle["shortest_solution_length"] == 1
    assert oracle["examined_transitions"] == 8 * len(states)


def test_opaque_mapping_and_public_interface():
    engine = Engine(initial_game(201))
    a, b = OpaqueMap(1), OpaqueMap(2)
    assert a.encode(engine.initial) == a.encode(engine.initial)
    assert a.encode(engine.initial) != b.encode(engine.initial)
    oracle, states = exact_oracle(engine)
    labels = [a.encode(s) for s in states]
    assert len(labels) == len(set(labels)) == oracle["reachable_states"]
    assert all(v.startswith("state_") and len(v) == 38 for v in labels)
    port = make_port(engine, a)
    assert {n for n in dir(port) if not n.startswith("_")} == {
        "reset", "current_observation", "available_actions", "step", "is_goal"}
    for name in ("genome", "rules", "engine", "state", "inventory", "map", "oracle", "goal", "__dict__"):
        with pytest.raises(AttributeError):
            getattr(port, name)
    assert port.available_actions() == tuple(range(8))
    assert isinstance(port.reset(), str)
    assert isinstance(port.step(0), str)
    assert type(port.is_goal()) is bool


def test_unsolvable_and_cap_are_different():
    game = initial_game(201)
    game["goal"] = [10, 10]
    game["board"]["walls"].remove([10, 10])
    oracle, _ = exact_oracle(Engine(game))
    assert oracle["status"] == "UNSOLVABLE" and oracle["solvable"] is False
    capped, _ = exact_oracle(Engine(initial_game(201)), cap=1)
    assert capped["status"] == "UNRESOLVED_TOO_LARGE" and capped["solvable"] is None


def test_trivial_game_is_learned_and_evaluation_is_read_only():
    engine = Engine(initial_game(201))
    opaque = OpaqueMap(19)
    rows = learn_game(make_port(engine, opaque), make_port(engine, opaque), [250, 500, 1000, 2000], 30, 2048, 17)
    assert rows[-1]["evaluation"]["successes"] == 30
    assert all(r["evaluation"]["evaluation_updates"] == 0 for r in rows)
    assert rows[-1]["learned_states"] >= rows[0]["learned_states"]
    assert all(0 <= r["evaluation"]["successes"] <= 30 for r in rows)


class LinePort:
    def __init__(self, length):
        self.length = length
        self.s = 0
    def reset(self, state=None):
        self.s = 0 if state is None else int(state)
        return self.current_observation()
    def current_observation(self):
        return str(self.s)
    def available_actions(self):
        return (0,)
    def step(self, action):
        self.s = min(self.length, self.s + 1)
        return self.current_observation()
    def is_goal(self):
        return self.s == self.length
    num_actions = 1


@pytest.mark.parametrize("length,horizon,expected", [(1, 4, 50), (4, 4, 50), (5, 4, 0)])
def test_no_random_success_double_count(length, horizon, expected):
    assert random_policy(LinePort(length), 50, horizon, 42)["successes"] == expected


def test_readout_agrees_with_original_on_single_goal():
    learner = StructuralLearner(1)
    for s in range(5):
        learner.get_or_add_id(str(s))
    for s in range(5):
        learner.record_transition(s, 0, min(s + 1, 4))
    before = fingerprint(learner)
    report = evaluate_frozen(learner, {"4"}, LinePort(4), 30, 10, 1)
    old_success, old_steps, old_reason = run_fixed_field_policy(
        LinePort(4), "0", "4", learner.build_k_support(), learner.state_to_id, learner.counts, max_steps=10)
    assert report["first_trial"]["success"] == old_success
    assert report["first_trial"]["steps"] == old_steps
    assert report["first_trial"]["reason"] == old_reason
    assert fingerprint(learner) == before


def test_original_support_and_multi_goal_superposition():
    learner = StructuralLearner(2)
    for i in range(3):
        learner.get_or_add_id(str(i))
    for s in range(3):
        learner.record_transition(s, 0, (s + 1) % 3)
        learner.record_transition(s, 1, s)
    K = learner.build_k_support()
    assert np.all(K.sum(axis=1) == 1)
    both = solve_fixed_field(K, [1, 2])[0]
    separate = solve_fixed_field(K, 1)[0] + solve_fixed_field(K, 2)[0]
    np.testing.assert_allclose(both, separate, atol=2e-7, rtol=0)


@pytest.mark.parametrize("family", FAMILIES)
def test_all_mutation_families_generate_valid_changed_game(family):
    parent = initial_game(201)
    child = mutate(parent, family, random.Random(53), 16)
    validate(child)
    assert game_hash(child) != game_hash(parent)
    assert child["board"]["width"] <= 16
    engine = Engine(child)
    state = engine.initial
    for i in range(100):
        action = i % 8
        assert engine.step(state, action) == engine.step(state, action)
        state = engine.step(state, action)


@pytest.mark.parametrize("family", SIZE_FAMILIES)
def test_size_control_does_not_change_mechanics(family):
    parent = initial_game(201)
    parent = mutate(parent, "dependency_chain", random.Random(1), 16)
    child = mutate(parent, family, random.Random(5), 16)
    assert child["objects"] == parent["objects"]
    assert child["rules"] == parent["rules"]
    assert child["flags"] == parent["flags"]


def test_designer_has_no_privileged_input_and_random_ignores_scores():
    parent = Feedback("p", True, 250, 0, 1)
    harder = Feedback("b", True, 500, 1, 1)
    impossible = Feedback("u", False, None, 4, 0)
    censored = Feedback("c", True, None, 4, 0)
    assert choose("mortra", parent, [harder, censored, impossible], random.Random(1)) == harder
    assert choose("random", parent, [censored], random.Random(1)) == censored
    assert choose("mortra", parent, [censored], random.Random(1)) == parent
    changed = [Feedback("a", True, 250, 0, 1), Feedback("b", True, 8000, 5, 1)]
    flipped = [Feedback("a", True, 8000, 5, 1), Feedback("b", True, 250, 0, 1)]
    assert choose("random", parent, changed, random.Random(2)).game_hash == choose("random", parent, flipped, random.Random(2)).game_hash
    assert list(Feedback.__dataclass_fields__) == ["game_hash", "solvable", "b80", "difficulty_area", "final_success"]
    assert not any(n in inspect.signature(learn_game).parameters for n in ("genome", "engine", "oracle", "coordinates"))


def test_fixed_protocol():
    assert config(2)["checkpoints"] == [250, 500, 1000, 2000, 4000, 8000]
    assert config(2)["generations"] == 10 and config(2)["candidates"] == 8
    assert len(config(2)["seeds"]) == 8
    assert config(1)["max_board"] == 16


def test_rule_order_inventory_counter_hazard_and_schema():
    g = initial_game(201)
    i = _add_object(g, random.Random(0), portable=True)
    g["objects"][i]["position"] = [2, 2]
    g["flags"] = [False]
    _rule(g, {"event": "PICK", "object": i}, [{"kind": "set_flag", "flag": 0, "value": True}])
    _rule(g, {"event": "PICK", "object": i}, [{"kind": "increment", "object": i, "value": 1}], [{"kind": "flag", "flag": 0, "value": True}])
    engine = Engine(g)
    s = engine.step(engine.initial, 5)
    assert s.flags == (True,) and s.objects[0][:2] == (-1, -1) and s.objects[0][4] == 1
    s = engine.step(s, 6)
    assert s.objects[0][:2] == (2, 2)
    for _ in range(10):
        s = engine.step(engine.step(s, 5), 6)
    assert s.objects[0][4] == 3
    bad = copy.deepcopy(g)
    bad["rules"][0]["effects"][0]["flag"] = 99
    with pytest.raises(ValueError):
        validate(bad)
    assert complexity(g)["rule_dependency_depth"] >= 1


def test_push_and_unavailable_action_semantics():
    g = initial_game(201)
    i = _add_object(g, random.Random(3), portable=True, solid=True)
    g["objects"][i]["position"] = [2, 1]
    g["board"]["walls"].remove([2, 0])
    e = Engine(g)
    pushed = e.step(e.initial, 7)
    assert (pushed.x, pushed.y) == (2, 1) and pushed.objects[0][:2] == (2, 0)
    empty = Engine(initial_game(201))
    assert empty.step(empty.initial, 4) == empty.initial
    assert empty.step(empty.initial, 5) == empty.initial
    assert empty.step(empty.initial, 6) == empty.initial
    assert empty.step(empty.initial, 7) == empty.initial


def test_all_effects_and_conditions_are_executable():
    from experiments.game_frontier_v1.world import CONDITIONS, EFFECTS
    g = initial_game(201)
    i = _add_object(g, random.Random(3), portable=True)
    g["objects"][i]["position"] = [2, 2]
    g["flags"] = [False]
    effects = [
        {"kind": "set_flag", "flag": 0, "value": True}, {"kind": "toggle_flag", "flag": 0},
        {"kind": "set_active", "object": 0, "value": False},
        {"kind": "set_passability", "object": 0, "value": False},
        {"kind": "toggle_passability", "object": 0}, {"kind": "teleport", "position": [1, 1]},
        {"kind": "give", "object": 0}, {"kind": "take", "object": 0},
        {"kind": "consume", "object": 0}, {"kind": "move", "object": 0, "position": [1, 1]},
        {"kind": "increment", "object": 0, "value": 1},
        {"kind": "set_hazard", "object": 0, "value": True},
    ]
    assert {e["kind"] for e in effects} == EFFECTS
    for effect in effects:
        example = copy.deepcopy(g)
        _rule(example, {"event": "INTERACT", "object": i}, [effect])
        e = Engine(example)
        result = e.step(e.initial, 4)
        assert result == e.step(e.initial, 4)
        if effect["kind"] == "teleport":
            assert (result.x, result.y) == (1, 1)
        if effect["kind"] == "give":
            assert result.objects[0][:2] == (-1, -1)
        if effect["kind"] == "consume":
            assert result.objects[0][:2] == (-2, -2)
    objects = [[-1, -1, True, False, 1, 0, False]]
    conds = [{"kind": "carrying", "object": 0}, {"kind": "not_carrying", "object": 0},
             {"kind": "flag", "flag": 0, "value": True}, {"kind": "active", "object": 0, "value": True},
             {"kind": "counter", "object": 0, "op": "eq", "value": 1}, {"kind": "region", "cells": [[2, 2]]}]
    assert {c["kind"] for c in conds} == CONDITIONS
    assert [Engine._condition(c, 2, 2, [True], objects) for c in conds] == [True, False, True, True, True, True]


def test_runner_artifacts_and_summary_end_to_end(tmp_path, monkeypatch):
    from experiments.game_frontier_v1 import runner
    from experiments.game_frontier_v1.summarize import summarize
    # Development-only protocol, never included in benchmark output or claims.
    monkeypatch.setitem(runner.STAGES, 1, {"generations": 1, "candidates": 1, "max_board": 16,
                                        "checkpoints": [50, 100], "seeds": [201]})
    for condition in ("mortra", "random", "size_only"):
        result = runner.run(1, 201, condition, tmp_path / "input" / condition)
        assert result["status"] == "COMPLETED"
        for candidate in result["candidates"]:
            directory = tmp_path / "input" / condition / "games" / candidate["game_hash"]
            assert all((directory / name).exists() for name in ("genome.json", "oracle.json", "learning.json", "evaluation.json"))
    summary = summarize(tmp_path / "input", tmp_path / "summary", 1)
    assert summary["runs"] == 3
    assert (tmp_path / "summary/figures/recorded_games.png").exists()
    with pytest.raises(FileExistsError):
        runner.run(1, 201, "mortra", tmp_path / "input/mortra")
