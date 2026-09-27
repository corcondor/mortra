"""Integration wiring tests, not an additional game-design experiment."""
import json

from experiments.self_design_v2_feedback_loop.adapter import FeedbackLoopAdapter
from experiments.v2_online_feedback.adapter import FeedbackPlayer, load_v2, fingerprint
from experiments.v2_online_feedback.prepare import write


def test_loop_wiring_preserves_design_functions_and_resets_learners(tmp_path, monkeypatch):
    module = load_v2()
    names = ("MicroGame", "StructuralLearner", "solve_fixed_field", "critique_game",
             "apply_targeted_mutation", "apply_random_mutation", "decide_acceptance", "run_self_design_loop")
    original = {name: getattr(module, name) for name in names}
    original_evaluate = module.evaluate_game
    players, budgets = [], []
    def observe_only(self, budget):
        # Test only the connection and fresh initialization, no policy outcomes.
        players.append(self)
        budgets.append(budget)
    monkeypatch.setattr(FeedbackPlayer, "advance_to", observe_only)
    adapter = FeedbackLoopAdapter(module, tmp_path)
    adapter.install()
    game = module.MicroGame(seed=101)
    game.generate_random()
    try:
        module.run_self_design_loop(game, num_iterations=0)
        different_version = game.copy()
        different_version.goal_pos = (1, 1)
        adapter.evaluate(different_version)
    finally:
        adapter.restore()
    assert module.evaluate_game is original_evaluate
    assert all(getattr(module, name) is value for name, value in original.items())
    assert budgets == [5000, 5000]
    assert players[0].learner is not players[1].learner
    assert players[0].selector is not players[1].selector
    for i in (0, 1):
        initial = json.loads((tmp_path / f"evaluation_{i:03d}/initial_learner.json").read_text())
        assert sum(n for _, counts in initial["counts"] for _, n in counts) == 2500


def test_full_original_metrics_preserved_when_feedback_is_a_wiring_stub(tmp_path, monkeypatch):
    from experiments.self_design_v2_integration.adapter import Integration
    module = load_v2()
    game = module.MicroGame(seed=101)
    game.generate_random()
    expected = Integration(module, "virtual_frontier", tmp_path / "reference").evaluate(game, 64, 3, 20)
    monkeypatch.setattr(FeedbackPlayer, "advance_to", lambda self, budget: None)
    adapter = FeedbackLoopAdapter(module, tmp_path / "connection")
    actual = adapter.evaluate(game, 64, 3, 20)
    assert actual.pop("additional_feedback_actions") == 5000
    assert actual.pop("total_learning_actions") == 5064
    assert actual == expected
