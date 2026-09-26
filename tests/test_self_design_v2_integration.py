import copy
import gzip
import inspect
import json

import pytest

from experiments.self_design_v2_integration.adapter import Integration, load_v2, make_evaluator
from experiments.task_agent.pretraining import TaskBlindSelector


def fixture(seed=101):
    module = load_v2()
    game = module.MicroGame(seed=seed)
    game.generate_random(wall_density=.18)
    return module, game


@pytest.mark.parametrize("seed", [101, 201])
def test_structural_evaluation_exactly_matches_original(seed, tmp_path):
    module, game = fixture(seed)
    expected = module.evaluate_game(game)
    bridge = Integration(module, "structural", tmp_path)
    assert bridge.evaluate(game) == expected
    assert bridge.evaluations[0]["training_steps"] == 2500


@pytest.mark.parametrize("method", ["frontier_t0", "virtual_frontier"])
def test_same_v2_learner_and_direct_selector_trajectory(method, tmp_path):
    module, game = fixture()
    learner = module.StructuralLearner(5)
    selector = TaskBlindSelector(method)
    expected = []
    state = game.get_initial_state()
    u = learner.get_or_add_id(state)
    for _ in range(96):
        decision, _ = selector.choose(learner, state)
        action = int(decision.action)
        nxt = game.step(state, action)
        v = learner.get_or_add_id(nxt)
        learner.record_transition(u, action, v)
        expected.append((action, list(nxt)))
        state, u = nxt, v
    bridge = Integration(module, method, tmp_path)
    bridge.evaluate(game, 96, 2, 12)
    with gzip.open(tmp_path / "evaluation_000/training.jsonl.gz", "rt") as stream:
        actual = [json.loads(line) for line in stream]
    assert [(r["action"], r["next_state"]) for r in actual] == expected
    for name in ("id_to_state", "state_to_id", "node_visits", "action_visits", "counts", "dest_map"):
        assert getattr(bridge.recorder.learner, name) == getattr(learner, name)
    assert bridge.evaluations[0]["oracle_calls"] == 0
    assert bridge.evaluations[0]["goal_queries_during_training"] == 0


def test_singleton_raises_on_task_access():
    memory = TaskBlindSelector("virtual_frontier").memory
    for name in ("progress", "accepting"):
        with pytest.raises(AssertionError):
            getattr(memory, name)(0)


def test_core_mutation_and_acceptance_function_code_unchanged(tmp_path):
    module, _ = fixture()
    names = ("MicroGame", "StructuralLearner", "solve_fixed_field", "evaluate_random_player",
             "critique_game", "apply_targeted_mutation", "apply_random_mutation", "decide_acceptance", "run_self_design_loop")
    original = {name: getattr(module, name) for name in names}
    bridge = Integration(module, "virtual_frontier", tmp_path)
    bridge.install()
    for name in names:
        assert getattr(module, name) is original[name]
    bridge.restore()


def test_exactly_one_ast_call_replacement():
    module, _ = fixture()
    calls = []
    original = module.evaluate_game
    new, tree = make_evaluator(module, lambda *args: calls.append(args))
    assert module.evaluate_game is original
    assert tree.count("id='_training_action'") == 1
    assert "select_action" not in tree


def test_profile_removed_after_chooser_exception(tmp_path, monkeypatch):
    import sys
    module, game = fixture()
    bridge = Integration(module, "virtual_frontier", tmp_path)
    def fail(*args):
        raise TypeError("simulated interface error")
    monkeypatch.setattr(TaskBlindSelector, "choose", fail)
    before = sys.getprofile()
    with pytest.raises(TypeError, match="interface"):
        bridge.evaluate(game, 2, 1, 2)
    assert sys.getprofile() is before
