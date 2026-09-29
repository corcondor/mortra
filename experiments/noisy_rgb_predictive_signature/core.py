"""Direct predictive-signature state acquisition.

This is the structural forward-port of the 2026-09-28 P1 result. It does not
materialize one provisional node per history. A history is assigned to an
existing representative only when the complete configured one-step signature is
SAME; a new representative is created only when every existing representative
has a confirmed DIFFERENT component. Otherwise the history stays unresolved.

The class does not assume that depth one is universally sufficient. Its
predictive_scope field makes the assumption explicit. For environments where
P1=P_infty has not been established, the learned object is the one-step quotient
rather than a certified infinite-horizon predictive quotient.
"""
from __future__ import annotations

from collections import Counter, deque
from dataclasses import dataclass
from typing import Callable, Iterable

from experiments.noisy_rgb_version_space.core import SAME, DIFFERENT, UNRESOLVED


@dataclass(frozen=True)
class SignatureBelief:
    history: tuple
    stage: int
    candidates: tuple[int, ...]
    confirmed_same: tuple[int, ...]
    excluded: tuple[int, ...]
    new_state_possible: bool
    status: str
    certificates: tuple

    @property
    def resolved_state(self):
        return self.confirmed_same[0] if self.status == SAME and len(self.confirmed_same) == 1 else None


class DirectPredictiveLearner:
    """Acquire a quotient directly from complete one-step signatures."""

    def __init__(
        self,
        evidence,
        actions: Iterable[int],
        emit: Callable[[dict], None] = lambda row: None,
        *,
        stages=None,
        label_equality=None,
        predictive_scope="P1_ONLY_UNLESS_FIXED_POINT_AUDITED",
    ):
        self.evidence = evidence
        self.actions = tuple(actions)
        if not self.actions or len(set(self.actions)) != len(self.actions):
            raise ValueError("actions must be a nonempty unique sequence")
        self.emit = emit
        self.stages = tuple(stages if stages is not None else getattr(evidence, "stages", (32,)))
        if not self.stages:
            raise ValueError("at least one evidence stage is required")
        self.label_equality = label_equality or (lambda h, r, e, stage=None: SAME)
        self.predictive_scope = predictive_scope
        self.reps = [()]
        self.transitions = {}
        self.assignments = {(): 0}
        self.unresolved = {}
        self.expanded = set()
        self.counts = Counter()
        self.emit(dict(event="signature_representative", state=0, history=(),
                       predictive_scope=self.predictive_scope))

    @property
    def suffixes(self):
        return ((),) + tuple((a,) for a in self.actions)

    def _component(self, h, r, suffix, stage):
        visual = self.evidence.compare(h, r, suffix, stage=stage)
        labels = self.label_equality(h, r, suffix, stage=stage)
        label_result = labels["result"] if isinstance(labels, dict) else labels
        if visual["result"] == DIFFERENT or label_result == DIFFERENT:
            result = DIFFERENT
        elif visual["result"] == SAME and label_result == SAME:
            result = SAME
        else:
            result = UNRESOLVED
        return dict(suffix=tuple(suffix), result=result,
                    visual_certificate=visual.get("id"),
                    visual_result=visual["result"], label_result=label_result)

    def compare_signature(self, h, r, stage):
        h, r = tuple(h), tuple(r)
        components = []
        for suffix in self.suffixes:
            row = self._component(h, r, suffix, stage)
            components.append(row)
            if row["result"] == DIFFERENT:
                return dict(result=DIFFERENT, stage=stage, components=components)
        result = SAME if all(row["result"] == SAME for row in components) else UNRESOLVED
        return dict(result=result, stage=stage, components=components)

    def belief(self, h, stage):
        h = tuple(h)
        if h in self.assignments:
            q = self.assignments[h]
            return SignatureBelief(h, stage, (q,), (q,), (), False, SAME, ())

        possible, same, excluded, certificates = [], [], [], []
        for q, r in enumerate(self.reps):
            comparison = self.compare_signature(h, r, stage)
            certificates.append((q, comparison))
            if comparison["result"] == DIFFERENT:
                excluded.append(q)
            else:
                possible.append(q)
                if comparison["result"] == SAME:
                    same.append(q)

        if len(same) > 1:
            raise AssertionError("two representatives have the same complete signature")
        if len(same) == 1:
            status, new_possible = SAME, False
        elif not possible:
            status, new_possible = DIFFERENT, True
        else:
            status, new_possible = UNRESOLVED, True

        result = SignatureBelief(
            h, int(stage), tuple(possible), tuple(same), tuple(excluded),
            new_possible, status, tuple(certificates))
        self.emit(dict(event="signature_belief", history=h, stage=stage,
                       candidates=list(result.candidates),
                       confirmed_same=list(result.confirmed_same),
                       excluded=list(result.excluded),
                       new_state_possible=result.new_state_possible,
                       status=result.status))
        return result

    def resolve(self, h, *, allow_new=True):
        h = tuple(h)
        if h in self.assignments:
            return self.assignments[h]
        last = None
        for stage in self.stages:
            last = self.belief(h, stage)
            if last.status == SAME:
                q = last.resolved_state
                self.assignments[h] = q
                self.unresolved.pop(h, None)
                self.counts["existing_assignments"] += 1
                return q
            if last.status == DIFFERENT:
                if not allow_new:
                    self.unresolved[h] = last
                    return None
                q = len(self.reps)
                self.reps.append(h)
                self.assignments[h] = q
                self.unresolved.pop(h, None)
                self.counts["new_states"] += 1
                self.emit(dict(event="signature_representative", state=q, history=h,
                               evidence_stage=stage,
                               reason="all_existing_signatures_confirmed_different",
                               predictive_scope=self.predictive_scope))
                return q

        self.unresolved[h] = last
        self.counts["unresolved_histories"] += 1
        self.emit(dict(event="signature_unresolved", history=h,
                       stage=None if last is None else last.stage,
                       candidates=[] if last is None else list(last.candidates),
                       new_state_possible=True))
        return None

    def learn(self):
        """Breadth-first direct quotient construction; unresolved histories are obligations, not nodes."""
        queue = deque([0])
        while queue:
            q = queue.popleft()
            if q in self.expanded:
                continue
            h = self.reps[q]
            before = len(self.reps)
            for a in self.actions:
                target = self.resolve(h + (a,))
                if target is None:
                    return self.model(), "INCOMPLETE_UNRESOLVED_SIGNATURE"
                self.transitions[q, a] = target
            self.expanded.add(q)
            for new_q in range(before, len(self.reps)):
                queue.append(new_q)
        return self.model(), "COMPLETED_ONE_STEP_QUOTIENT"

    def model(self):
        return dict(reps=list(self.reps), trans=dict(self.transitions), start=0,
                    unresolved={h: b for h, b in self.unresolved.items()},
                    predictive_scope=self.predictive_scope)

    def _closed_candidates(self, h, stage, suffixes):
        candidates = set(range(len(self.reps)))
        certificates = []
        for suffix in suffixes:
            for q in list(candidates):
                row = self._component(h, self.reps[q], suffix, stage)
                certificates.append((q, tuple(suffix), row))
                if row["result"] == DIFFERENT:
                    candidates.remove(q)
        return candidates, certificates

    def choose_identification_probe(self, candidates, used, stage):
        """Choose the action with the most confirmed pair separations; no fixed probe rule."""
        candidates = tuple(sorted(candidates))
        available = [a for a in self.actions if a not in used]
        if not available:
            return None
        scored = []
        for a in available:
            separated = unresolved = 0
            for i, q in enumerate(candidates):
                for r in candidates[i+1:]:
                    row = self._component(self.reps[q], self.reps[r], (a,), stage)
                    separated += row["result"] == DIFFERENT
                    unresolved += row["result"] == UNRESOLVED
            scored.append((separated, -unresolved, -self.actions.index(a), a))
        return max(scored)[-1]

    def identify_closed(self, h, *, max_probes=None):
        """Identify among known representatives in a reset/replay setting."""
        h = tuple(h)
        stage = self.stages[-1]
        candidates, certs = self._closed_candidates(h, stage, [()])
        used = []
        limit = len(self.actions) if max_probes is None else int(max_probes)
        while len(candidates) > 1 and len(used) < limit:
            action = self.choose_identification_probe(candidates, used, stage)
            if action is None:
                break
            used.append(action)
            suffixes = [()] + [(a,) for a in used]
            candidates, more = self._closed_candidates(h, stage, suffixes)
            certs.extend(more)
            self.emit(dict(event="active_identification_probe", history=h,
                           action=action, candidates=sorted(candidates),
                           probes=list(used)))
        result = next(iter(candidates)) if len(candidates) == 1 else None
        return dict(state=result, candidates=sorted(candidates), probes=used,
                    certificates=certs, closed_world=True)
