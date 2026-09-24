"""Development equivalence checks, distinct from the unchanged supplied tests."""
import numpy as np
import pytest

from mortra_predictive_perception.adapters import ResponseSymbolizer
from mortra_predictive_perception.optimized import SweepResponseSymbolizer


def compare(episodes, actions, target):
    reference = ResponseSymbolizer(actions, target)
    optimized = SweepResponseSymbolizer(actions, target)
    for observations, controls in episodes:
        reference.add_episode(observations, controls)
        optimized.add_episode(observations, controls)
    reference.fit()
    optimized.fit()
    assert reference.export_tree() == optimized.export_tree()
    assert reference.report == optimized.report
    for observations, controls in episodes:
        for t in range(len(observations)):
            assert reference.encode_history(observations[:t+1], controls[:t]) == (
                optimized.encode_history(observations[:t+1], controls[:t]))
    for old, new in zip(reference._leaves(reference.tree), optimized._leaves(optimized.tree), strict=True):
        np.testing.assert_array_equal(old.row_indices, new.row_indices)
        for action in old.action_means:
            np.testing.assert_array_equal(old.action_means[action], new.action_means[action])
    return reference, optimized


@pytest.mark.parametrize("target", ["delta", "absolute"])
@pytest.mark.parametrize("seed", range(20))
def test_sweep_exact_reference_equality(seed, target):
    rng = np.random.default_rng(seed)
    episodes = [(rng.integers(-3, 4, (length + 1, 3)).astype(float),
                 rng.integers(0, 3, length).tolist()) for length in (1, 2, 4, 7)]
    compare(episodes, [0, 1, 2], target)


@pytest.mark.parametrize("target", ["delta", "absolute"])
@pytest.mark.parametrize("offset", [0.0, 1e12])
def test_missing_history_ties_and_large_offset(target, offset):
    episodes = []
    for _ in range(4):
        for cue in (0, 1):
            episodes.append((np.array([[cue, cue], [5, 5], [9, 9],
                                       [20 if cue == 0 else -20] * 2], dtype=float) + offset,
                             [0, 0, 1]))
    compare(episodes, [0, 1], target)


@pytest.mark.parametrize("target", ["delta", "absolute"])
def test_constant_responses(target):
    compare([(np.ones((8, 2)), [0, 1, 0, 1, 0, 1, 0])], [0, 1], target)


def test_lazy_columns_equal_reference_arrays():
    episodes = [(np.arange(15, dtype=float).reshape(5, 3), [0, 1, 0, 1]),
                (np.ones((2, 3)), [1])]
    models = [cls([0, 1]) for cls in (ResponseSymbolizer, SweepResponseSymbolizer)]
    for model in models:
        for obs, acts in episodes:
            model.add_episode(obs, acts)
    old, new = [model._build_training_arrays() for model in models]
    assert old[4] == list(new[4])
    for j in range(len(old[4])):
        np.testing.assert_array_equal(old[0][:, j], new[0][:, j])
        np.testing.assert_array_equal(old[1][:, j], new[1][:, j])
    np.testing.assert_array_equal(old[2], new[2])


def test_adjacent_floats_midpoint_rounding():
    x = np.array([1., np.nextafter(1., 2.), np.nextafter(np.nextafter(1., 2.), 2.)])
    compare([(np.array([[v], [v + (1 if i % 2 else -1)]]), [0])
             for i, v in enumerate(x)] * 4, [0], "delta")
