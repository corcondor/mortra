"""Shared RGB evidence for live Mario observations.

Exact repeated captures take the zero-noise fast path.  If the same blocked
frame actually varies, comparison falls back to the 2026-09-28 shrinking-floor
statistic with SAME/DIFFERENT/UNRESOLVED semantics.  Consecutive advancing game
frames are never treated as repeated samples of one state.
"""
from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256

import numpy as np

from experiments.noisy_rgb_discovery.core import Emission, Statistics
from experiments.noisy_rgb_version_space.core import SAME, DIFFERENT, UNRESOLVED, stability


def image_hash(image):
    array = np.asarray(image, dtype=np.uint8)
    return sha256(array.tobytes()).hexdigest()


def emission(images):
    x = np.asarray(images, dtype=np.uint8)
    if x.ndim != 4 or x.shape[-1] != 3:
        raise ValueError("expected [samples,height,width,3] RGB batch")
    flat = x.reshape(len(x), -1).astype(np.float32) / 255.
    if len(flat) == 1:
        var = np.zeros(flat.shape[1], dtype=np.float32)
    else:
        var = flat.var(0, ddof=1)
    return Emission(flat.mean(0), var, len(flat))


@dataclass(frozen=True)
class ObservationBelief:
    candidates: tuple[int, ...]
    confirmed_same: tuple[int, ...]
    new_state_possible: bool
    status: str
    evidence: tuple

    @property
    def resolved_state(self):
        return self.confirmed_same[0] if self.status == SAME and len(self.confirmed_same) == 1 else None


class LiveRGBRegistry:
    def __init__(self, *, threshold=1.22,
                 stages=(8, 16, 32, 64, 128, 256, 512, 1024),
                 base_floor=.01, reference_n=32):
        self.threshold = float(threshold)
        self.stages = tuple(int(n) for n in stages)
        if tuple(sorted(self.stages)) != self.stages or self.stages[0] < 2:
            raise ValueError("stages must be increasing and start at >=2")
        self.statistics = Statistics(
            None, noise_floor=base_floor, floor_mode="shrinking",
            reference_n=reference_n)
        self.prototypes = []
        self.events = []

    def _exact_probe(self, port):
        first = np.asarray(port.last_image, dtype=np.uint8).copy()
        second, packet = port.snap()
        exact = bool(np.array_equal(first, second))
        return np.stack([first, second]), exact, packet

    def _noisy_compare(self, port, prototype, replay):
        if replay is None:
            return UNRESOLVED, []
        rows = []
        for n in self.stages:
            current, _ = port.repeated_observation(2*n)
            reference = replay(prototype["history"], 2*n)
            scores = []
            for part in (slice(0, n), slice(n, 2*n)):
                a = emission(current[part])
                b = emission(reference[part])
                scores.append(self.statistics.z(a, b))
            result = stability(scores, self.threshold, n, decision_stage=32)
            rows.append(dict(stage=n, scores=scores, result=result,
                             floor=self.statistics.effective_noise_floor(
                                 emission(current[:n]), emission(reference[:n]))))
            if result != UNRESOLVED:
                return result, rows
        return UNRESOLVED, rows

    def observe(self, port, history, *, replay=None, allow_new=True):
        """Classify the currently blocked frame without advancing the game."""
        history = tuple(int(a) for a in history)
        pair, current_exact, packet = self._exact_probe(port)
        current_hash = image_hash(pair[0]) if current_exact else None

        possible, same, excluded, certificates = [], [], [], []
        for q, prototype in enumerate(self.prototypes):
            if current_exact and prototype["exact_hash"] is not None:
                result = SAME if current_hash == prototype["exact_hash"] else DIFFERENT
                detail = [dict(stage="exact", result=result)]
            else:
                result, detail = self._noisy_compare(port, prototype, replay)
            certificates.append((q, detail))
            if result == DIFFERENT:
                excluded.append(q)
            else:
                possible.append(q)
                if result == SAME:
                    same.append(q)

        if len(same) == 1:
            belief = ObservationBelief(tuple(possible), tuple(same), False, SAME,
                                       tuple(certificates))
        elif len(same) > 1:
            # Do not silently union approximately matching observation classes.
            belief = ObservationBelief(tuple(possible), tuple(same), True, UNRESOLVED,
                                       tuple(certificates))
        elif not possible:
            if allow_new:
                q = len(self.prototypes)
                self.prototypes.append(dict(
                    history=history,
                    exact_hash=current_hash,
                    exact_reference=pair[0].copy() if current_exact else None,
                ))
                self.events.append(dict(event="observation_class_added", observation=q,
                                        history=history, exact=current_exact,
                                        frame=packet["frame"]))
                belief = ObservationBelief((q,), (q,), False, SAME,
                                           tuple(certificates))
            else:
                belief = ObservationBelief((), (), True, DIFFERENT,
                                           tuple(certificates))
        else:
            belief = ObservationBelief(tuple(possible), (), True, UNRESOLVED,
                                       tuple(certificates))

        self.events.append(dict(
            event="observation_belief", history=history,
            candidates=list(belief.candidates),
            confirmed_same=list(belief.confirmed_same),
            new_state_possible=belief.new_state_possible,
            status=belief.status, frame=packet["frame"]))
        return belief
