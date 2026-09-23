import importlib.util
from pathlib import Path

import pytest

SOURCE = Path(__file__).resolve().parents[1] / "scripts/evaluate_autonomous_game_design_loop.py"
spec = importlib.util.spec_from_file_location("self_game_design", SOURCE)
game_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(game_module)


class StepGoal:
    def __init__(self, goal):
        self.goal = goal

    def get_initial_state(self):
        return 0

    def step(self, state, action):
        return state + 1

    def is_goal(self, state):
        return state == self.goal


@pytest.mark.parametrize("goal,steps,expected", [(5, 5, 1), (2, 5, 1), (6, 5, 0), (0, 5, 1)])
def test_one_success_per_trial(goal, steps, expected):
    result = game_module.evaluate_random_player(StepGoal(goal), trials=1, max_steps=steps)
    assert result["successes"] == expected
    assert len(result["replay"]["states"]) == len(result["replay"]["actions"]) + 1


@pytest.mark.parametrize("goal", [0, 1, 2, 10, 100, 101])
def test_fifty_trials_never_exceed_fifty(goal):
    result = game_module.evaluate_random_player(StepGoal(goal), trials=50, max_steps=100)
    assert 0 <= result["successes"] <= result["trials"] == 50
    assert result["successes"] == (50 if goal <= 100 else 0)
    assert 0 <= result["success_rate"] <= 1


@pytest.mark.parametrize("seed", [101, 201, 302, 403, 504, 605])
def test_random_real_game_replay_and_count(seed):
    game = game_module.MicroGame(seed=seed)
    game.generate_random(wall_density=0.18)
    result = game_module.evaluate_random_player(game)
    assert 0 <= result["successes"] <= 50
    replay = result["replay"]
    state = game.get_initial_state()
    assert state == replay["states"][0]
    for action, expected in zip(replay["actions"], replay["states"][1:]):
        state = game.step(state, action)
        assert state == expected
    assert game.is_goal(state) == replay["reached_goal"]


def test_seed_201_regression_and_seed_101():
    for seed, expected in [(201, 30), (101, 16)]:
        game = game_module.MicroGame(seed=seed)
        game.generate_random(wall_density=0.18)
        assert game_module.evaluate_random_player(game)["successes"] == expected


def test_mortra_replay_is_actual_execution():
    game = game_module.MicroGame(seed=101)
    game.generate_random(wall_density=0.18)
    metrics = game_module.evaluate_game(game, explore_steps=150, self_play_trials=2, max_play_steps=12)
    replay = metrics["mortra_replay"]
    state = game.get_initial_state()
    for action, expected in zip(replay["actions"], replay["states"][1:]):
        state = game.step(state, action)
        assert state == expected
    assert game.is_goal(state) == replay["reached_goal"]


def test_refuse_existing_output(tmp_path):
    (tmp_path / "run.log").write_text("previous")
    with pytest.raises(ValueError, match="overwrite"):
        game_module.prepare_output(tmp_path)
    assert (tmp_path / "run.log").read_text() == "previous"


def test_refuse_legacy_output():
    with pytest.raises(ValueError, match="immutable"):
        game_module.prepare_output(Path(game_module.workspace_root) / "reports/self_game_design")


@pytest.mark.parametrize("trials,steps", [(0, 5), (1, -1)])
def test_invalid_budgets(trials, steps):
    with pytest.raises(ValueError):
        game_module.evaluate_random_player(StepGoal(1), trials, steps)
