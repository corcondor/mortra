"""Immutable shared trajectories and a frozen readout of legacy visual clusters.

Only observations, action IDs and episode boundaries belong in a learning
dataset. Hidden-state diagnostics must be stored separately by the evaluator.
"""
from collections import defaultdict
import hashlib
from pathlib import Path

import numpy as np

from .adapters import readonly_episode
from .core import UnknownActionResponse


def save_episodes(path, episodes):
    """Exclusive creation: never overwrite an earlier experiment's experience."""
    episodes = tuple(readonly_episode(obs, actions) for obs, actions in episodes)
    if not episodes:
        raise ValueError("No episodes")
    if len({obs[0].size for obs, _ in episodes}) != 1:
        raise ValueError("Observation dimensions differ")
    # Persist opaque integer IDs, not action names or semantic annotations.
    if any(not isinstance(a, (int, np.integer)) for _, acts in episodes for a in acts):
        raise TypeError("The saved benchmark format requires opaque integer action IDs")
    path = Path(path)
    with path.open("xb") as handle:
        np.savez_compressed(handle,
                            observations=np.vstack([obs for obs, _ in episodes]),
                            actions=np.concatenate([np.asarray(acts, dtype=np.int64) for _, acts in episodes]),
                            episode_lengths=np.array([len(acts) for _, acts in episodes], dtype=np.int64))
    return {"path": str(path.resolve()), "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "episodes": len(episodes), "transitions": sum(len(a) for _, a in episodes),
            "raw_dimension": episodes[0][0][0].size, "file_bytes": path.stat().st_size}


def load_episodes(path, expected_sha256):
    path = Path(path)
    if hashlib.sha256(path.read_bytes()).hexdigest() != expected_sha256:
        raise ValueError("Shared trajectory SHA-256 mismatch")
    with np.load(path, allow_pickle=False) as data:
        if set(data.files) != {"observations", "actions", "episode_lengths"}:
            raise ValueError("Learning dataset contains unexpected fields")
        obs, acts, lengths = data["observations"], data["actions"], data["episode_lengths"]
    if np.any(lengths < 0) or len(acts) != sum(lengths) or len(obs) != sum(lengths) + len(lengths):
        raise ValueError("Invalid episode boundaries")
    episodes, oi, ai = [], 0, 0
    for length in lengths:
        episodes.append(readonly_episode(obs[oi:oi + length + 1], acts[ai:ai + length]))
        oi += length + 1
        ai += length
    return tuple(episodes)


class FrozenLegacyVisual:
    """Original training code, frozen inference for the perception-only comparison.

    The historical complete-system evaluator changes its prototypes while
    playing. That is deliberately NOT executed here: held-out observations may
    not update any condition's perception model. Outside the original match
    radius, inference returns None rather than inserting a test-time prototype.
    This adapter is not a claim that the historical complete system is frozen.
    """
    def __init__(self, legacy, frame_shape=(24, 24), actions=tuple(range(5))):
        self.legacy = legacy
        self.frame_shape = tuple(frame_shape)
        self.actions = tuple(actions)
        self.constructor = legacy.VisualStateConstructor(num_actions=len(actions))
        self._means = {}
        self.frozen = False

    def _frame(self, observation):
        return np.asarray(observation).reshape(self.frame_shape)

    def fit(self, episodes):
        if self.frozen:
            raise RuntimeError("Already frozen")
        episodes = tuple(readonly_episode(obs, acts) for obs, acts in episodes)
        for obs, acts in episodes:
            current = self.constructor.map_observation_to_cluster(self._frame(obs[0]))
            for action, following in zip(acts, obs[1:], strict=True):
                nxt = self.constructor.map_observation_to_cluster(self._frame(following))
                self.constructor.record_transition(current, action, nxt)
                current = nxt
        self.constructor.run_behavioral_merge()
        self.prototypes = np.array(self.constructor.prototypes)
        self.prototypes.flags.writeable = False
        self.frozen = True
        # Common action-conditioned response readout fitted on training only.
        # This is an evaluation readout, not a replacement for OLD's planner.
        samples = defaultdict(list)
        for obs, acts in episodes:
            for t, action in enumerate(acts):
                symbol = self.encode(obs[t])
                if symbol is not None:
                    samples[symbol, int(action), "absolute"].append(obs[t+1])
                    samples[symbol, int(action), "delta"].append(obs[t+1] - obs[t])
        self._means = {key: np.mean(values, axis=0) for key, values in samples.items()}
        return self

    def encode(self, observation):
        if not self.frozen:
            raise RuntimeError("fit() first")
        descriptor = self.legacy.extract_visual_descriptor(self._frame(observation))
        distances = np.linalg.norm(self.prototypes - descriptor, axis=1)
        index = int(np.argmin(distances))
        if not distances[index] < self.constructor.vis_dist_thresh:
            return None
        return self.constructor.get_canonical(index)

    def predict(self, symbol, action, target):
        key = symbol, int(action), target
        if key not in self._means:
            raise UnknownActionResponse(key)
        return self._means[key].copy()
