import numpy as np
from mortra_predictive_perception import PredictiveMDLSymbolizer


def _selected_features(model):
    return set(model.report.selected_features)


def test_predictive_feature_selected_not_nuisance():
    m = PredictiveMDLSymbolizer(actions=["go"])

    for nuisance in (-12.0, -7.0, -2.0, 3.0, 8.0, 13.0):
        m.add_episode(
            [np.array([nuisance, 0.0]), np.array([nuisance + 1.0, 2.0])],
            ["go"],
        )
        m.add_episode(
            [np.array([nuisance, 1.0]), np.array([nuisance - 1.0, -2.0])],
            ["go"],
        )

    r = m.fit()
    feats = _selected_features(m)

    assert r.generated_symbols >= 2
    assert "obs[1]" in feats
    assert "obs[0]" not in feats


def test_history_depth_is_selected_from_data():
    m = PredictiveMDLSymbolizer(actions=["advance", "choose"])

    for _ in range(10):
        m.add_episode(
            [
                np.array([0.0]),
                np.array([5.0]),
                np.array([9.0]),
                np.array([20.0]),
            ],
            ["advance", "advance", "choose"],
        )
        m.add_episode(
            [
                np.array([1.0]),
                np.array([5.0]),
                np.array([9.0]),
                np.array([-20.0]),
            ],
            ["advance", "advance", "choose"],
        )

    r = m.fit()
    assert r.selected_history_depth >= 1
    assert any("obs[t-" in f or "action[t-" in f for f in r.selected_features)


def test_no_task_objective_parameters():
    m = PredictiveMDLSymbolizer(actions=[0, 1])
    assert not hasattr(m, "goal")
    assert not hasattr(m, "reward")
    assert not hasattr(m, "q")
    assert not hasattr(m, "discount")


def test_symbol_count_not_predeclared():
    m = PredictiveMDLSymbolizer(actions=["a"])
    for x in [0.0, 1.0, 2.0, 3.0]:
        m.add_episode(
            [np.array([x]), np.array([x + (1.0 if x < 2 else -1.0)])],
            ["a"],
        )
    r = m.fit()
    assert r.generated_symbols >= 1
    assert r.generated_symbols == len(m.partition_symbols()) if hasattr(m, "partition_symbols") else r.generated_symbols
