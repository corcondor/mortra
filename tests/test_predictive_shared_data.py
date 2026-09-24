import hashlib
from pathlib import Path

import numpy as np
import pytest

from mortra_predictive_perception.adapters import load_legacy_visual
from mortra_predictive_perception.shared_data import (
    FrozenLegacyVisual, load_episodes, save_episodes,
)


def test_shared_dataset_roundtrip_and_no_overwrite(tmp_path):
    episodes = [(np.arange(6.).reshape(3, 2), [0, 1]), (np.ones((2, 2)), [1])]
    path = tmp_path / "raw.npz"
    manifest = save_episodes(path, episodes)
    restored = load_episodes(path, manifest["sha256"])
    for (obs, acts), (original, controls) in zip(restored, episodes, strict=True):
        np.testing.assert_array_equal(obs, original)
        assert acts == tuple(controls)
        assert not obs[0].flags.writeable
    with pytest.raises(FileExistsError):
        save_episodes(path, episodes)


def test_reject_changed_dataset_and_evaluation_fields(tmp_path):
    path = tmp_path / "raw.npz"
    np.savez(path, observations=np.zeros((2, 1)), actions=[0], episode_lengths=[1], hidden_state=[0, 1])
    sha = hashlib.sha256(path.read_bytes()).hexdigest()
    with pytest.raises(ValueError, match="unexpected fields"):
        load_episodes(path, sha)
    with pytest.raises(ValueError, match="SHA-256"):
        load_episodes(path, "0" * 64)


def test_legacy_perception_evaluation_cannot_update_prototypes():
    root = Path(__file__).resolve().parents[1]
    legacy = load_legacy_visual(root / "scripts/evaluate_visual_state_construction.py")
    episodes = [(np.zeros((3, 576)), [0, 1])]
    model = FrozenLegacyVisual(legacy).fit(episodes)
    prototypes = model.prototypes.copy()
    counts = list(model.constructor.proto_counts)
    assert model.encode(np.ones(576)) is None
    for _ in range(10):
        assert model.encode(np.zeros(576)) == 0
    np.testing.assert_array_equal(model.prototypes, prototypes)
    assert model.constructor.proto_counts == counts
    assert len(model.constructor.prototypes) == 1
    np.testing.assert_array_equal(model.predict(0, 0, "delta"), np.zeros(576))
