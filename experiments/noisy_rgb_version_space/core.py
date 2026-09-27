"""No hidden-world access: only repeated RGB Statistics and opaque actions."""
from collections import Counter
from itertools import product

SAME, DIFFERENT, UNRESOLVED = 'SAME', 'DIFFERENT', 'UNRESOLVED'
STAGES = (8, 16, 32)


def stability(scores, threshold, stage):
    if stage != 32:
        return UNRESOLVED
    lo, hi = min(scores), max(scores)
    spread = hi-lo
    if hi+spread < threshold:
        return SAME
    if max(0., lo-spread) > threshold:
        return DIFFERENT
    return UNRESOLVED


class Evidence:
    def __init__(self, statistics, threshold, camera, emit, check=lambda: None):
        self.statistics, self.threshold = statistics, threshold
        self.camera, self.emit, self.check = camera, emit, check
        self.cache = {}
        self.version = 0
        self.counts = Counter()

    def compare(self, h, r, e=(), stage=32):
        h, r, e = tuple(h), tuple(r), tuple(e)
        pair = tuple(sorted((h+e, r+e)))
        key = (pair, stage)
        self.check()
        if key in self.cache:
            self.counts['certificate_reuse'] += 1
            return self.cache[key]
        if pair[0] == pair[1]:
            return dict(id=None, result=SAME, scores=[], stage=stage, reflexive=True)
        scores = []
        for n in STAGES:
            if n > stage:
                break
            s = self.statistics[n]
            scores.extend(s.z(s.summary(pair[0], j), s.summary(pair[1], j)) for j in (0, 1))
        outcome = stability(scores, self.threshold, stage)
        self.version += 1
        row = dict(event='comparison', id=self.version, history_a=h, history_b=r,
                   suffix=e, pair=pair, stage=stage, scores=scores, threshold=self.threshold,
                   result=outcome, label='SAME-under-current-tests' if outcome == SAME else outcome,
                   camera=self.camera, evidence_version=self.version)
        self.cache[key] = row
        self.counts['comparisons'] += 1
        self.counts[outcome+'_comparisons'] += 1
        if stage == 32:
            self.counts[outcome+'_certificates'] += 1
        self.emit(row)
        return row

    def cached_result(self, h, r, e):
        pair = tuple(sorted((tuple(h)+tuple(e), tuple(r)+tuple(e))))
        if pair[0] == pair[1]:
            return SAME
        return self.cache.get((pair, 32), {}).get('result', UNRESOLVED)


class CandidateLearner:
    def __init__(self, evidence, actions, emit, check=lambda: None):
        self.evidence, self.actions, self.emit, self.check = evidence, tuple(actions), emit, check
        self.S, self.E = [()], [()]
        self.trans, self.assignments, self.queue = {}, {}, {}
        self.events, self.counts = [], Counter()
        self.structure_version = 0
        self.probes = [tuple(e) for d in (1, 2) for e in product(self.actions, repeat=d)]

    @property
    def version(self):
        return (self.structure_version, self.evidence.version)

    def candidates(self, h, stage=32, suffixes=None):
        h = tuple(h)
        candidates, exclusions = [], []
        for q, r in enumerate(self.S):
            for e in self.E if suffixes is None else suffixes:
                cert = self.evidence.compare(h, r, e, stage)
                if cert['result'] == DIFFERENT:
                    exclusions.append(dict(q=q, representative=r, suffix=e, certificate=cert['id']))
                    break
            else:
                candidates.append(q)
        self.emit(dict(event='candidate_set', history=h, stage=stage, candidates=candidates,
                       representative_count=len(self.S), exclusions=exclusions, version=self.version))
        return candidates, exclusions

    def probe_score(self, candidates, e):
        def endpoint(q):
            for a in e:
                if (q, a) not in self.trans:
                    return None
                q = self.trans[q, a]
            return q
        remaining = 0
        for q in candidates:
            for r in candidates:
                result = self.evidence.cached_result(self.S[q], self.S[r], e)
                if result != DIFFERENT:
                    tq, tr = endpoint(q), endpoint(r)
                    if tq is not None and tr is not None:
                        result = self.evidence.cached_result(self.S[tq], self.S[tr], ())
                remaining += result != DIFFERENT
        return remaining / len(candidates)

    def add_suffix(self, h, r, e, certificate, cause):
        e = tuple(e)
        if not e or e in self.E:
            return False
        assert len(e) <= 2 and certificate['result'] == DIFFERENT
        prior = [self.evidence.compare(h, r, old) for old in self.E]
        if any(c['result'] == DIFFERENT for c in prior):
            return False
        row = dict(event='suffix_added', history_a=h, history_b=r, suffix=e,
                   certificate=certificate['id'], previous_suffixes=list(self.E),
                   previous_results=[c['result'] for c in prior], cause=cause)
        self.events.append(row)
        self.E.append(e)
        self.trans = {}
        self.structure_version += 1
        self.emit(row)
        return True

    def resolve(self, h, consistency=True):
        h = tuple(h)
        self.check()
        old = self.queue.get(h)
        if old and tuple(old['last_evidence_version']) == self.version:
            self.counts['unchanged_queue_skips'] += 1
            return None
        self.counts['membership_queries'] += 1
        query = self.counts['membership_queries']
        candidates, _ = self.candidates(h, 8)
        ambiguous = len(candidates) > 1
        self.counts['initial_ambiguous_memberships'] += ambiguous
        self.candidates(h, 16)
        candidates, excluded = self.candidates(h, 32)
        if ambiguous and len(candidates) == 1:
            self.counts['resolved_by_resampling'] += 1
        used, scored, cert_ids = [], [], []
        while len(candidates) > 1 and len(used) < len(self.probes):
            available = [e for e in self.probes if e not in used]
            depth = min(map(len, available))
            scores = [(self.probe_score(candidates, e), e) for e in available if len(e) == depth]
            score, e = min(scores)
            scored.append(dict(candidates=list(candidates), scores=[(p, s) for s, p in scores], selected=e))
            self.emit(dict(event='active_probe', history=h, candidates=list(candidates),
                           selected=e, score=score, candidate_scores=scores, query=query))
            used.append(e)
            self.counts['probe_depth_'+str(depth)] += 1
            for a in e:
                self.counts['probe_action_'+str(a)] += 1
            for q in list(candidates):
                c = self.evidence.compare(h, self.S[q], e)
                cert_ids.append(c['id'])
                if c['result'] == DIFFERENT:
                    self.add_suffix(h, self.S[q], e, c, 'active_discrimination')
                    candidates.remove(q)
                    excluded.append(dict(q=q, representative=self.S[q], suffix=e, certificate=c['id']))
            self.emit(dict(event='candidate_set', history=h, stage=32, probe=e,
                           candidates=list(candidates), representative_count=len(self.S),
                           exclusions=list(excluded), version=self.version))
            if len(candidates) == 1:
                self.counts['resolved_by_depth_'+str(depth)] += 1
        if not candidates:
            # Recheck every representative with the final global tests, not a
            # transient empty candidate list or a visual nearest-neighbor guess.
            candidates, excluded = self.candidates(h, 32)
            if not candidates:
                assert len(excluded) == len(self.S)
                self.S.append(h)
                self.structure_version += 1
                q = len(self.S)-1
                self.assignments[h] = q
                self.queue.pop(h, None)
                self.counts['new_states_created'] += 1
                self.emit(dict(event='state_added', history=h, state=q,
                               reason='all_representatives_confirmed_different_32', evidence=excluded))
                return q
        if len(candidates) == 1:
            q = candidates[0]
            self.queue.pop(h, None)
            self.assignments[h] = q
            if consistency and h != self.S[q]:
                for e in self.probes:
                    if e in self.E or e in used:
                        continue
                    c = self.evidence.compare(h, self.S[q], e)
                    self.counts['consistency_probes'] += 1
                    if c['result'] == DIFFERENT:
                        if self.add_suffix(h, self.S[q], e, c, 'consistency'):
                            return self.resolve(h, consistency=False)
            return q
        row = dict(event='unresolved', history=h, candidates=list(candidates), tested_probes=used,
                   probe_scores=scored, certificates=cert_ids, last_evidence_version=self.version,
                   retry_count=0 if old is None else old['retry_count']+1)
        self.queue[h] = row
        self.counts['unresolved_events'] += 1
        self.emit(row)
        return None

    def model(self):
        return dict(reps=list(self.S), groups=[[s] for s in self.S], trans=dict(self.trans),
                    start=0, goal={q: False for q in range(len(self.S))})

    def learn(self):
        while True:
            self.check()
            before = self.version
            structure_before = self.structure_version
            trans = {}
            for q, h in enumerate(list(self.S)):
                for a in self.actions:
                    target = self.resolve(h+(a,))
                    if target is not None:
                        trans[q, a] = target
            if trans != self.trans:
                self.trans = trans
                self.structure_version += 1
            if structure_before != self.structure_version:
                continue
            if len(self.trans) != len(self.S)*len(self.actions):
                if before == self.version:
                    return None, 'INCOMPLETE_UNRESOLVED_FIXED_POINT'
                continue
            counterexample = False
            for q, h in enumerate(list(self.S)):
                for x in [()]+self.probes:
                    predicted = q
                    previous = q
                    for a in x:
                        previous, predicted = predicted, self.trans[predicted, a]
                    actual = h+x
                    candidates, _ = self.candidates(actual)
                    if candidates == [predicted]:
                        continue
                    counterexample = True
                    self.emit(dict(event='counterexample', history=actual, predicted=predicted,
                                   candidates=candidates))
                    advanced = False
                    if x:
                        for e in list(self.E):
                            witness = (x[-1],)+e
                            if len(witness) > 2:
                                continue
                            c = self.evidence.compare(actual[:-1], self.S[previous], witness)
                            if c['result'] == DIFFERENT:
                                advanced |= self.add_suffix(actual[:-1], self.S[previous], witness,
                                                            c, 'counterexample_backward')
                    if not advanced:
                        target = self.resolve(actual)
                        advanced = self.structure_version != structure_before
                    if not advanced:
                        return None, 'INCOMPLETE_BOUNDED_CONFORMANCE'
                    break
                if counterexample:
                    break
            if counterexample:
                continue
            return self.model(), 'COMPLETED_BOUNDED_EMPIRICAL_TEST'
