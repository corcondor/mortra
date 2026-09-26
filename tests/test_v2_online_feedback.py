import copy
import json
from collections import Counter

import numpy as np
import pytest

from experiments.v2_online_feedback.adapter import (
    ARMS, FeedbackPlayer, FrozenPlayback, fingerprint, load_v2, payload,
    restore_game, restore_learner,
)
from experiments.task_agent.pretraining import TaskBlindSelector


class LineGame:
    def __init__(self, goal=3):
        self.goal = goal

    def get_initial_state(self):
        return (0, 0)

    def is_goal(self, state):
        return state[0] == self.goal

    def step(self, state, action):
        return (min(state[0] + 1, self.goal), 0) if action == 0 else state

    def to_dict(self):
        return {"goal": self.goal}


def make(arm, goal=3):
    module = load_v2()
    learner = module.StructuralLearner(module.NUM_ACTIONS)
    learner.get_or_add_id((0, 0))
    game = LineGame(goal)
    playback = FrozenPlayback(module)
    return FeedbackPlayer(module, playback, game, learner, arm)


@pytest.mark.parametrize("seed", [101, 201])
def test_ast_snapshot_play_matches_original_whole_evaluator(seed):
    module = load_v2()
    game = module.MicroGame(seed=seed)
    game.generate_random()
    expected = module.evaluate_game(game, 96, 50, 100)
    learner = module.StructuralLearner(5)
    state = game.get_initial_state()
    u = learner.get_or_add_id(state)
    for _ in range(96):
        action = learner.select_action(u)
        state = game.step(state, action)
        v = learner.get_or_add_id(state)
        learner.record_transition(u, action, v)
        u = v
    result = FrozenPlayback(module).evaluate(game, learner)
    assert result["successes"] == expected["successes"]
    assert result["trials"][0]["actions"] == expected["mortra_replay"]["actions"]
    assert result["trials"][0]["states"] == expected["mortra_replay"]["states"]
    roundtrip = restore_learner(module, payload(learner))
    assert fingerprint(payload(roundtrip)) == fingerprint(payload(learner))
    assert restore_game(module, game.to_dict()).to_dict() == game.to_dict()
    serialized = json.loads(json.dumps(game.to_dict(), sort_keys=True))
    assert fingerprint(restore_game(module, serialized).to_dict()) == fingerprint(serialized)
    serialized_learner = json.loads(json.dumps(payload(learner), sort_keys=True))
    assert payload(restore_learner(module, serialized_learner)) == payload(learner)


@pytest.mark.parametrize("arm", ARMS)
def test_exact_budget_reset_and_counts(arm):
    player = make(arm)
    initial = fingerprint(payload(player.learner))
    player.advance_to(4)
    player.advance_to(107)
    assert player.steps == len(player.actions) == 107
    assert player.actions[3]["state"] == (0, 0)
    assert player.actions[3]["trial"] == 1
    assert player.resets == max(r["trial"] for r in player.actions)
    if arm == ARMS[0]:
        assert fingerprint(payload(player.learner)) == initial
    else:
        expected = Counter((r["state"], r["action"], r["next_state"]) for r in player.actions)
        actual = Counter({(player.learner.id_to_state[u], a, player.learner.id_to_state[v]): n
                          for (u, a), counts in player.learner.counts.items() for v, n in counts.items()})
        assert actual == expected


def test_frozen_and_recording_keep_trial_number_fallback(monkeypatch):
    def forbidden(*args):
        raise AssertionError("B must never use the new selector")
    monkeypatch.setattr(TaskBlindSelector, "choose", forbidden)
    for arm in ARMS[:2]:
        player = make(arm, goal=1000)
        player.advance_to(250)
        assert all(r["fallback"] and r["action"] == r["trial"] % 5 for r in player.actions)
        assert player.selector_calls == 0


def test_c_selector_only_when_original_fallback_true():
    player = make(ARMS[2], goal=2)
    player.advance_to(20)
    assert player.selector_calls == player.fallback_calls
    assert player.selector_calls > 0
    assert any(not r["fallback"] for r in player.actions)
    assert all(r["selector_called"] == r["fallback"] for r in player.actions)
    assert player.first_known_goal is not None
    assert any(f["known_goal_ids"] for f in player.fields)


def test_discovery_replans_and_freezes_evaluation():
    player = make(ARMS[1], goal=2)
    player.advance_to(2)
    assert player.first_known_goal == 2
    assert player.fields[-1]["step"] == 2
    before = fingerprint(payload(player.learner))
    result = player.playback.evaluate(player.game, player.learner)
    assert result["successes"] == 50
    assert result["actual_actions"] == 100
    assert fingerprint(payload(player.learner)) == before
    np.testing.assert_array_equal(result["psi"], player.psi)


@pytest.mark.parametrize("arm", ARMS)
def test_success_on_action_100_counted_once(arm):
    player = make(arm, goal=100)
    # Teach the same observed deterministic path, for a terminal-boundary fixture.
    for i in range(100):
        u = player.learner.get_or_add_id((i, 0))
        v = player.learner.get_or_add_id((i + 1, 0))
        player.learner.record_transition(u, 0, v)
    player.known_goals = {100}
    player.recompute("fixture path")
    result = player.playback.evaluate(player.game, player.learner, trials=1, max_steps=100)
    assert result["successes"] == 1
    assert result["actual_actions"] == 100
    player.advance_to(100)
    assert player.successes == 1 and len(player.rollouts) == 1
    player.advance_to(101)
    assert player.successes == 1 and player.resets == 1


@pytest.mark.parametrize("arm", ARMS)
def test_checkpoint_evaluation_cannot_change_online_trajectory(arm):
    a, b = make(arm), make(arm)
    a.advance_to(75)
    b.advance_to(25)
    b.playback.evaluate(b.game, b.learner)
    b.advance_to(75)
    assert [(r["state"], r["action"]) for r in a.actions] == [(r["state"], r["action"]) for r in b.actions]
    assert payload(a.learner) == payload(b.learner)


def test_singleton_goal_methods_remain_forbidden():
    memory = TaskBlindSelector("virtual_frontier").memory
    for name in ("progress", "accepting"):
        with pytest.raises(AssertionError):
            getattr(memory, name)(0)


def test_successful_nonfallback_does_not_invoke_selector(monkeypatch):
    player = make(ARMS[2], goal=1)
    u = player.learner.get_or_add_id((0, 0))
    v = player.learner.get_or_add_id((1, 0))
    player.learner.record_transition(u, 0, v)
    player.known_goals = {v}
    player.recompute("fixture path")
    def forbidden(*args):
        raise AssertionError("Selector outside fallback")
    monkeypatch.setattr(TaskBlindSelector, "choose", forbidden)
    player.advance_to(5)
    assert player.successes == 5 and player.selector_calls == 0
