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

from experiments.accelerator import device_info, z_score_rgb_batches
from experiments.noisy_rgb_discovery.core import Emission, Statistics
from experiments.noisy_rgb_version_space.core import SAME, DIFFERENT, UNRESOLVED, stability


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
                 base_floor=.01, reference_n=32, device="auto"):
        self.threshold = float(threshold)
        self.stages = tuple(int(n) for n in stages)
        if tuple(sorted(self.stages)) != self.stages or self.stages[0] < 2:
            raise ValueError("stages must be increasing and start at >=2")
        self.statistics = Statistics(
            None, noise_floor=base_floor, floor_mode="shrinking",
            reference_n=reference_n)
        self.device = str(device)
        self.prototypes = []
        self.exact_index = {}
        self.events = []

    def _ensure_exact_index(self):
        # Checkpoints created before the hash-index optimization remain readable.
        if not hasattr(self, "exact_index"):
            self.exact_index = {}
        if len(self.exact_index) < sum(p.get("exact_hash") is not None for p in self.prototypes):
            self.exact_index = {
                p["exact_hash"]: q for q, p in enumerate(self.prototypes)
                if p.get("exact_hash") is not None
            }

    def _exact_probe(self, port):
        first_hash = port.last_hash
        if first_hash is None:
            raise RuntimeError("missing current frame hash")
        second_hash, packet = port.snap_hash()
        exact = first_hash == second_hash
        return first_hash, second_hash, exact, packet

    def _noisy_compare(self, port, prototype, replay):
        if replay is None:
            return UNRESOLVED, []
        rows = []
        for n in self.stages:
            current, _ = port.repeated_observation(2*n)
            reference = replay(prototype["history"], 2*n)
            scores = []
            for part in (slice(0, n), slice(n, 2*n)):
                scores.append(z_score_rgb_batches(
                    current[part], reference[part],
                    noise_floor=self.statistics.noise_floor,
                    reference_n=self.statistics.reference_n,
                    device=getattr(self, "device", "auto")))
            result = stability(scores, self.threshold, n, decision_stage=32)
            floor = self.statistics.noise_floor * (
                self.statistics.reference_n / float(n)) ** .25
            rows.append(dict(stage=n, scores=scores, result=result,
                             floor=floor,
                             accelerator=device_info(getattr(self, "device", "auto"))["resolved"]))
            if result != UNRESOLVED:
                return result, rows
        return UNRESOLVED, rows

    def observe(self, port, history, *, replay=None, allow_new=True):
        """Classify the currently blocked frame without advancing the game."""
        history = tuple(int(a) for a in history)
        first_hash, second_hash, current_exact, packet = self._exact_probe(port)
        current_hash = first_hash if current_exact else None

        self._ensure_exact_index()
        possible, same, excluded, certificates = [], [], [], []

        # Deterministic screen captures take the O(1) hash path.  Pairwise SHA
        # equality has exactly the same semantics as the old all-prototype loop.
        if current_exact and current_hash in self.exact_index:
            q = self.exact_index[current_hash]
            belief = ObservationBelief((q,), (q,), False, SAME,
                                       ((q, [dict(stage="exact", result=SAME)]),))
            self.events.append(dict(
                event="observation_belief", history=history,
                candidates=[q], confirmed_same=[q],
                new_state_possible=False, status=SAME, frame=packet["frame"],
                lookup="sha256_index"))
            return belief

        noisy_candidates = []
        if current_exact:
            for q, prototype in enumerate(self.prototypes):
                if prototype.get("exact_hash") is not None:
                    excluded.append(q)
                    certificates.append((q, [dict(stage="exact", result=DIFFERENT)]))
                else:
                    noisy_candidates.append((q, prototype))
        else:
            noisy_candidates = list(enumerate(self.prototypes))

        for q, prototype in noisy_candidates:
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
                ))
                if current_hash is not None:
                    self.exact_index[current_hash] = q
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
