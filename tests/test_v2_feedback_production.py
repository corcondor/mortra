"""Structural and observer checks; real full-budget gates run separately."""
import ast
import inspect
import textwrap

import pytest

from experiments.self_design_v2_feedback_loop.adapter import FeedbackLoopAdapter
from experiments.v2_feedback_production.adapter import ArmFeedbackLoopAdapter
from experiments.v2_feedback_production.observe import LoopObserver
from experiments.v2_online_feedback.adapter import ARMS, load_v2


def test_arm_extension_changes_only_feedback_method():
    for name in ("evaluate", "training_action", "install", "restore"):
        assert getattr(ArmFeedbackLoopAdapter, name) is getattr(FeedbackLoopAdapter, name)
    source = textwrap.dedent(inspect.getsource(FeedbackLoopAdapter.feedback))
    assert source.count("ARMS[2]") == 1
    from experiments.v2_feedback_production import adapter
    assert 'if ast.unparse(node) == "ARMS[2]"' in inspect.getsource(adapter.compile_feedback)
    assert ast.parse(source)


@pytest.mark.parametrize("arm", ARMS)
def test_frozen_functions_and_real_feedback_binding(tmp_path, arm):
    m = load_v2()
    funcs = {k: getattr(m, k) for k in ("MicroGame", "StructuralLearner", "solve_fixed_field",
        "critique_game", "apply_targeted_mutation", "apply_random_mutation", "decide_acceptance", "run_self_design_loop")}
    original_evaluate = m.evaluate_game
    adapter = ArmFeedbackLoopAdapter(m, tmp_path, arm)
    assert adapter.arm == arm
    assert adapter.evaluator.__globals__["_feedback"].__self__ is adapter
    assert adapter.feedback.__globals__["FeedbackPlayer"] is __import__(
        "experiments.v2_online_feedback.adapter", fromlist=["FeedbackPlayer"]).FeedbackPlayer
    adapter.install()
    observer = LoopObserver(m, adapter)
    observer.install()
    assert m.run_self_design_loop.__globals__["evaluate_game"].__self__ is observer
    assert all(getattr(m, k) is v for k, v in funcs.items())
    adapter.restore()
    assert m.evaluate_game is original_evaluate


def test_metric_forwarding_requires_identity(tmp_path):
    m = load_v2()
    adapter = FeedbackLoopAdapter(m, tmp_path)
    adapter.install()
    observer = LoopObserver(m, adapter)
    metric = {"successes": 1}
    observer.metrics.append(metric)
    assert observer.metric_index(metric) == 0
    with pytest.raises(AssertionError):
        observer.metric_index(dict(metric))
