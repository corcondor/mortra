"""Share scheduling only; every identity decision stays in frozen V2."""
from collections import Counter, defaultdict
from dataclasses import dataclass, field
import hashlib
from itertools import product
import json

from experiments.noisy_rgb_predictive_v2.core import ProvisionalLearner

WORDS = ((),) + tuple((a,) for a in range(5)) + tuple(product(range(5), repeat=2))
SATURATION_ATTEMPTS = len(WORDS)


def signature(node, representatives, labels, cached):
    """No histories, RGB distances, certificate IDs, or truth in the key."""
    h = tuple(node.history)
    candidates = tuple(sorted(node.belief.existing_candidates))
    return (
        candidates, bool(node.belief.new_state_possible),
        tuple(None if h + e not in labels else tuple(sorted(labels[h + e].items())) for e in WORDS),
        tuple(a in node.outgoing for a in range(5)),
        tuple(tuple(cached(h, representatives[q], e) for e in WORDS) for q in candidates),
        tuple(sorted(map(tuple, node.tested_probes))),
    )


def signature_id(value):
    return hashlib.sha256(json.dumps(value, separators=(',', ':')).encode()).hexdigest()


@dataclass
class Family:
    signature: tuple
    members: set = field(default_factory=set)
    trials: Counter = field(default_factory=Counter)
    last_uninformative: dict = field(default_factory=dict)
    sources: dict = field(default_factory=lambda: defaultdict(set))
    stagnant: int = 0
    saturated: bool = False
    last_served: int = -1


class FamilyLearner(ProvisionalLearner):
    def __init__(self, *args, labels, sharing=True, **kwargs):
        super().__init__(*args, **kwargs)
        assert tuple(self.actions) == tuple(range(5))
        self.labels = labels
        self.sharing = sharing
        self.families = {}
        self.membership = {}
        self.dirty = set()
        self.family_counts = Counter()
        self.probe_attempts = Counter()
        self.unit_turns = {}
        self.turn = 0
        self.context = None
        self.saturated_ids = set()

    def cached(self, h, r, e):
        pair = tuple(sorted((tuple(h) + e, tuple(r) + e)))
        if pair[0] == pair[1]:
            return 'SAME'
        return self.evidence.cache.get((pair, 32), {}).get('result', 'NOT_COMPARED')

    def refresh(self, node):
        h = node.history
        old = self.membership.get(h)
        value = signature(node, self.reps, self.labels, self.cached) if node.status == 'provisional' else None
        new = signature_id(value) if value is not None else None
        self.dirty.discard(h)
        if old == new:
            return
        if old is not None:
            self.families[old].members.discard(h)
            del self.membership[h]
        if new is not None:
            if new not in self.families:
                self.families[new] = Family(value)
                self.emit(dict(event='family_created', family=new, signature=value,
                               state_identity_asserted=False))
            family = self.families[new]
            assert family.signature == value
            family.members.add(h)
            self.membership[h] = new
        self.family_counts['membership_changes'] += 1
        self.emit(dict(event='family_membership', history=h, previous=old, family=new,
                       identity_changed_by_family=False))

    def refresh_dirty(self):
        for h in sorted(self.dirty):
            if h in self.nodes:
                self.refresh(self.nodes[h])
        self.dirty.clear()

    def reactivate(self, reason):
        for key in sorted(self.saturated_ids):
            family = self.families[key]
            family.saturated = False
            family.stagnant = 0
            self.family_counts['reactivations'] += 1
            self.emit(dict(event='family_reactivated', family=key, reason=reason))
        self.saturated_ids.clear()

    def receive_certificate(self, row):
        super().receive_certificate(row)
        event = row.get('event')
        if event == 'comparison' and row['stage'] == 32:
            for endpoint in row['pair']:
                endpoint = tuple(endpoint)
                for size in range(min(2, len(endpoint)) + 1):
                    self.dirty.add(endpoint[:-size] if size else endpoint)
            self.reactivate('new_direct_certificate')
        elif event in ('unmerge', 'merge_reopened', 'empirical_merge'):
            self.dirty.add(tuple(row['history']))
            if event != 'empirical_merge':
                self.reactivate('identity_counterexample_or_reopening')
        elif event == 'local_tree_refinement':
            self.reactivate('new_representative_pair_witness')

    def classify(self, node):
        super().classify(node)
        self.refresh(node)

    def promote(self, node, excluded):
        super().promote(node, excluded)
        self.dirty.update(self.nodes)
        self.reactivate('new_representative')

    def step(self):
        if not self.sharing or not self.agenda:
            return super().step()
        self.check()
        self.refresh_dirty()
        choices = []
        for position, h in enumerate(self.agenda):
            node = self.nodes[h]
            family_id = self.membership.get(h) if node.status == 'provisional' else None
            if family_id is None and node.status == 'provisional':
                self.refresh(node)
                family_id = self.membership[h]
            unit = ('family', family_id) if family_id is not None else ('node', h)
            saturated = family_id is not None and self.families[family_id].saturated
            choices.append((bool(saturated), self.unit_turns.get(unit, -1), position, unit))
        saturated, _, position, unit = min(choices)
        h = self.agenda[position]
        del self.agenda[position]
        self.agenda.appendleft(h)
        self.unit_turns[unit] = self.turn
        self.turn += 1
        self.family_counts['agenda_family_turns'] += unit[0] == 'family'
        self.family_counts['agenda_reordered_turns'] += position != 0
        self.emit(dict(event='family_agenda', history=h, unit=unit, saturated=saturated,
                       previous_queue_position=position))
        return super().step()

    def probe_score(self, node, e):
        if self.context is not None:
            return self.context['priorities'][e]
        return super().probe_score(node, e)

    def probe(self, node):
        if not self.sharing:
            return super().probe(node)
        if node.status != 'provisional':
            return
        available = [e for e in self.probes if e not in node.tested_probes]
        if not available:
            return
        self.refresh(node)
        key = self.membership[node.history]
        family = self.families[key]
        depth = min(map(len, available))
        available = [e for e in available if len(e) == depth]
        candidates = set(node.belief.existing_candidates)
        scores = {e: super(FamilyLearner, self).probe_score(node, e) for e in available}
        separated = {e: sum(self.evidence.cached_result(self.reps[q], self.reps[r], e) == 'DIFFERENT'
                            for q in sorted(candidates) for r in sorted(candidates) if q < r)
                     for e in available}
        priorities = {e: (-separated[e], bool(family.last_uninformative.get(e, False)),
                          scores[e], family.trials[e]) for e in available}
        chosen = min(available, key=lambda e: (priorities[e], e))
        baseline = min(available, key=lambda e: (scores[e], e))
        shared = any(h != node.history for e in available for h in family.sources.get(e, set()))
        avoided = chosen != baseline and family.last_uninformative.get(baseline, False)
        repeated = self.probe_attempts[node.history, chosen] > 0
        self.probe_attempts[node.history, chosen] += 1
        self.family_counts['probe_attempts'] += 1
        self.family_counts['repeated_probe_attempts'] += repeated
        self.family_counts['family_shared_scheduling_decisions'] += shared
        self.family_counts['avoided_redundant_probe_opportunities'] += avoided
        before = (len(self.reps), len(self.tree.witnesses))
        self.emit(dict(event='family_probe_choice', history=node.history, family=key, selected=chosen,
                       baseline_selected=baseline, priorities=sorted(priorities.items()),
                       shared=shared, repeated_same_history_suffix=repeated,
                       avoided_redundant_opportunity=avoided, saved_exposures_claimed=False))
        self.context = dict(priorities=priorities)
        completed = False
        try:
            # All acquisition, comparison, exclusion, merge, and promotion code
            # runs unchanged. Only probe_score supplies a different ordering.
            super().probe(node)
            completed = True
        finally:
            self.context = None
        if completed:
            excluded = len(candidates - node.belief.existing_candidates)
            informative = excluded > 0 or before != (len(self.reps), len(self.tree.witnesses))
            family.trials[chosen] += 1
            family.sources[chosen].add(node.history)
            family.last_uninformative[chosen] = not informative
            family.stagnant = 0 if informative else family.stagnant + 1
            self.family_counts['completed_probe_attempts'] += 1
            if family.stagnant >= SATURATION_ATTEMPTS and not family.saturated:
                family.saturated = True
                self.saturated_ids.add(key)
                self.family_counts['saturations'] += 1
                self.emit(dict(event='FAMILY_SATURATED', family=key, consecutive=family.stagnant,
                               state_merge=False))
            self.emit(dict(event='family_probe_result', history=node.history, family=key,
                           selected=chosen, candidate_exclusions=excluded, informative=informative,
                           consecutive_no_progress=family.stagnant))
            self.refresh(node)

    def record(self):
        self.dirty.update(self.nodes)
        self.refresh_dirty()
        result = super().record()
        result['family_membership'] = [(h, key) for h, key in sorted(self.membership.items())]
        result['families'] = [dict(id=key, signature=f.signature, members=sorted(f.members),
            trials=sorted(f.trials.items()), last_uninformative=sorted(f.last_uninformative.items()),
            stagnant=f.stagnant, saturated=f.saturated,
            required_evidence='Direct target-history comparisons; no family evidence substitution')
            for key, f in sorted(self.families.items()) if f.members]
        result['family_counts'] = dict(self.family_counts)
        result['family_scheduler_memory'] = dict(turn=self.turn, unit_turns=list(self.unit_turns.items()),
            registry=[dict(id=key, signature=f.signature, trials=sorted(f.trials.items()),
                last_uninformative=sorted(f.last_uninformative.items()),
                sources=[(e,sorted(histories)) for e,histories in sorted(f.sources.items())],
                stagnant=f.stagnant, saturated=f.saturated)
                for key,f in sorted(self.families.items())],
            prior_probe_attempts=[(h,e,n) for (h,e),n in sorted(self.probe_attempts.items())])
        result['family_scope'] = 'Scheduling only; all PredictiveNode identities and certificates remain separate'
        return result
