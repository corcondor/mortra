"""RGB evidence and public-label equality. No hidden state or task reward."""
from collections import Counter, deque
from dataclasses import dataclass, field
from itertools import product

from experiments.noisy_rgb_version_space.core import SAME, DIFFERENT, UNRESOLVED

EMPIRICAL='EMPIRICALLY_EQUIVALENT_DEPTH_2'


@dataclass
class CandidateBelief:
    existing_candidates: set[int]
    new_state_possible: bool = True
    identity_scope: str = 'OPEN'

    def record(self):
        return dict(existing_candidates=sorted(self.existing_candidates),
                    new_state_possible=self.new_state_possible, identity_scope=self.identity_scope)


@dataclass
class PredictiveNode:
    history: tuple
    belief: CandidateBelief
    status: str = 'provisional'
    outgoing: dict = field(default_factory=dict)
    tested_probes: list = field(default_factory=list)
    certificates: list = field(default_factory=list)
    evidence_version: int = 0
    representative: int | None = None
    merge_records: list = field(default_factory=list)

    def record(self):
        return dict(history=self.history, belief=self.belief.record(),status=self.status,
                    outgoing=sorted(self.outgoing.items()),tested_probes=self.tested_probes,
                    certificates=self.certificates,evidence_version=self.evidence_version,
                    representative=self.representative,merge_records=self.merge_records)


class AdaptiveDiscriminationTree:
    """A ternary, overlapping branch tree, without transitivity assumptions.

    A branch records direct pair outcomes. SAME never prunes a different
    representative merely because it followed another historical branch.
    Only suffixes witnessing a local candidate-pair difference refine a leaf.
    """
    def __init__(self,evidence,emit):
        self.evidence,self.emit=evidence,emit
        self.witnesses={}
        self.leaves={}
        self.counts=Counter()

    def add_witness(self,q,r,e,certificate):
        assert q!=r and certificate['result']==DIFFERENT
        assert certificate['stage']==32 and len(e)<=2
        key=(min(q,r),max(q,r),tuple(e))
        if key in self.witnesses:
            return
        self.witnesses[key]=certificate['id']
        affected=[pool for pool in self.leaves if q in pool and r in pool]
        for pool in affected:
            self.leaves.pop(pool)
        self.emit(dict(event='local_tree_refinement',q=q,r=r,suffix=e,
                       certificate=certificate['id'],affected_leaves=[list(x) for x in affected]))

    def select_suffix(self,candidates,used):
        pool=frozenset(candidates)
        options={e for q,r,e in self.witnesses if q in pool and r in pool and e not in used}
        if not options:
            return None
        def score(e):
            separated=sum(q in pool and r in pool and s==e for q,r,s in self.witnesses)
            return (-separated,len(e),e)
        e=min(options,key=score)
        self.leaves[pool]=dict(suffix=e,branches={})
        return e

    def classify(self,h,reps,extra_tests=(),recognize_replay=True):
        h=tuple(h)
        if recognize_replay and h in reps:
            return CandidateBelief({reps.index(h)},False,'EXACT_REPLAY'),{}
        candidates=set(range(len(reps)))
        exclusions={}
        used=set()
        e=()
        extras=list(dict.fromkeys(map(tuple,extra_tests)))
        while candidates and e is not None:
            before=frozenset(candidates)
            outcomes=[]
            for q in sorted(candidates):
                c=self.evidence.compare(h,reps[q],e)
                outcomes.append((q,c['result']))
                if c['result']==DIFFERENT:
                    candidates.remove(q)
                    exclusions[q]=dict(suffix=e,certificate=c['id'])
            used.add(e)
            self.counts['path_suffix_tests']+=1
            self.emit(dict(event='tree_test',history=h,suffix=e,outcomes=outcomes,
                           candidates=sorted(candidates),new_state_possible=True))
            branch=tuple(outcomes)
            if before in self.leaves:
                self.leaves[before]['branches'][branch]=sorted(candidates)
            extra=next((s for s in extras if s not in used),None)
            e=extra if extra is not None else self.select_suffix(candidates,used)
        return CandidateBelief(candidates,True),exclusions


class ProvisionalLearner:
    def __init__(self,evidence,actions,observe,emit,check=lambda:None,label_equality=None):
        self.evidence,self.actions=evidence,tuple(actions)
        self.observe,self.emit,self.check=observe,emit,check
        self.tree=AdaptiveDiscriminationTree(evidence,emit)
        self.reps=[]
        self.nodes={}
        self.agenda=deque()
        self.counts=Counter()
        self.probes=[tuple(p) for d in (1,2) for p in product(self.actions,repeat=d)]
        self.local_tests={}
        self.exclusions={}
        self.label_equality=label_equality or (lambda h,r,e:UNRESOLVED)
        self.revoked_candidates={}
        self.differences={}

    def receive_certificate(self,row):
        """Consume new evidence, never request deeper active experiments."""
        if row.get('event')!='comparison' or row.get('result')!=DIFFERENT or row.get('stage')!=32:
            return
        pair=tuple(map(tuple,row['pair']))
        self.differences[pair]=row['id']
        for node in list(self.nodes.values()):
            if node.status=='merged':
                self.revalidate_merge(node)

    def observed_contradiction(self,h,q):
        r=self.reps[q]
        for (x,y),certificate in self.differences.items():
            for a,b in ((x,y),(y,x)):
                if a[:len(h)]==h and b[:len(r)]==r and a[len(h):]==b[len(r):]:
                    return dict(suffix=a[len(h):],certificate=certificate,
                                reason='observed_future_DIFFERENT')
        return None

    def revalidate_merge(self,node):
        contradictions={q:self.observed_contradiction(node.history,q)
                        for q in node.belief.existing_candidates}
        contradictions={q:c for q,c in contradictions.items() if c is not None}
        if not contradictions:
            return
        self.revoked_candidates.setdefault(node.history,{}).update(contradictions)
        node.status='provisional'
        node.representative=None
        node.belief.new_state_possible=True
        node.belief.identity_scope='OPEN_AFTER_COUNTEREXAMPLE'
        node.belief.existing_candidates.difference_update(contradictions)
        node.tested_probes.clear()
        node.merge_records[-1]['revocation']=dict(evidence_version=self.evidence.version,
                                                counterexamples=contradictions)
        self.counts['unmerges']+=1
        if node.history not in self.agenda:
            self.agenda.append(node.history)
        self.emit(dict(event='unmerge',history=node.history,counterexamples=contradictions,
                       restored_NEW=True,original_history_and_edges_preserved=True))

    def start(self):
        self.observe(())
        self.reps.append(())
        self.nodes[()]=PredictiveNode((),CandidateBelief({0},False,'EXACT_REPLAY'),
                                     status='representative',representative=0)
        self.agenda.append(())
        self.emit(dict(event='initial_representative',history=(),state=0))

    def classify(self,node):
        belief,excluded=self.tree.classify(node.history,self.reps,self.local_tests.get(node.history,()))
        for q,item in self.revoked_candidates.get(node.history,{}).items():
            belief.existing_candidates.discard(q)
            excluded[q]=item
        node.belief=belief
        node.evidence_version=self.evidence.version
        self.exclusions[node.history]=excluded
        node.certificates=list(dict.fromkeys(node.certificates+[v['certificate'] for v in excluded.values()]))
        self.counts['classifications']+=1
        self.emit(dict(event='belief',history=node.history,belief=belief.record(),
                       representative_count=len(self.reps),exclusions=excluded,
                       evidence_version=self.evidence.version))
        if not belief.existing_candidates:
            self.promote(node,excluded)
        elif node.status=='merged':
            self.revalidate_merge(node)
            if node.status=='merged':
                matches={q for q in belief.existing_candidates if self.empirical_match(node,q)}
                if matches==belief.existing_candidates:
                    node.belief.new_state_possible=False
                    node.belief.identity_scope=EMPIRICAL
                    node.representative=next(iter(matches)) if len(matches)==1 else None
                else:
                    node.status='provisional'
                    node.representative=None
                    node.tested_probes.clear()
                    if node.history not in self.agenda:
                        self.agenda.append(node.history)
                    self.emit(dict(event='merge_reopened',history=node.history,
                                   reason='not every current candidate has complete evidence'))

    def promote(self,node,excluded):
        assert set(excluded)==set(range(len(self.reps)))
        for item in excluded.values():
            assert item['certificate'] is not None
        q=len(self.reps)
        self.reps.append(node.history)
        node.status='representative'
        node.representative=q
        node.belief=CandidateBelief({q},False,'EXACT_REPLAY')
        self.counts['promotions']+=1
        for other in self.nodes.values():
            if other.status=='merged':
                other.status='provisional'
                other.representative=None
                other.belief.new_state_possible=True
                other.belief.identity_scope='OPEN_NEW_REPRESENTATIVE'
                self.emit(dict(event='merge_reopened',history=other.history,
                               reason='new representative not compared; no transitive exclusion'))
            if other.status=='provisional':
                other.belief.existing_candidates.add(q)
                # The old tests did not compare the newly represented
                # hypothesis. Reuse their RGB/cache; do not drop any edge.
                other.tested_probes.clear()
                if other.history not in self.agenda:
                    self.agenda.append(other.history)
        for r,item in excluded.items():
            if len(item['suffix'])>2:
                continue  # Passive future counterexample; not a new active-probe depth.
            cert=self.evidence.compare(node.history,self.reps[r],tuple(item['suffix']))
            self.tree.add_witness(q,r,tuple(item['suffix']),cert)
        self.emit(dict(event='promotion',history=node.history,state=q,evidence=excluded))

    def empirical_match(self,node,q):
        if q is None or q not in node.belief.existing_candidates:
            return False
        representative=self.nodes[self.reps[q]]
        if set(node.outgoing)!=set(self.actions) or set(representative.outgoing)!=set(self.actions):
            return False
        for e in [()]+self.probes:
            if self.evidence.cached_result(node.history,self.reps[q],e)!=SAME:
                return False
            if self.label_equality(node.history,self.reps[q],e)!=SAME:
                return False
        for a in self.actions:
            h=node.outgoing[a]
            r=representative.outgoing[a]
            if self.evidence.cached_result(h,r,())!=SAME:
                return False
        return self.observed_contradiction(node.history,q) is None

    def maybe_merge(self,node):
        if node.status!='provisional' or not node.belief.existing_candidates:
            return
        matches={q for q in node.belief.existing_candidates if self.empirical_match(node,q)}
        # Every still-possible candidate must have a complete certificate.
        # An unresolved alternative is not silently discarded.
        if matches==node.belief.existing_candidates:
            node.status='merged'
            node.representative=next(iter(matches)) if len(matches)==1 else None
            node.belief=CandidateBelief(matches,False,EMPIRICAL)
            certificates={q:[self.evidence.compare(node.history,self.reps[q],e)['id']
                             for e in [()]+self.probes] for q in sorted(matches)}
            record=dict(history=node.history,representatives=sorted(matches),depth=2,
                        tested_sequences=len(self.probes)+1,tested_suffixes=[()]+self.probes,
                        SAME_certificates=certificates,public_labels='SAME for every sequence',
                        evidence_version=self.evidence.version,reversible=True,
                        status='PROVISIONALLY_MERGED',identity_scope=EMPIRICAL)
            node.merge_records.append(record)
            self.counts['empirical_merges']+=1
            self.emit(dict(event='empirical_merge',**record))

    def probe_score(self,node,e):
        qs=sorted(node.belief.existing_candidates)
        if not qs:
            return 1
        # NEW has no imagined emission or successor: it contributes only an
        # unresolved hypothesis, the same constant for every probe.
        def endpoint(q):
            h=self.reps[q]
            for a in e:
                current=self.nodes.get(h)
                if current is None or a not in current.outgoing:
                    return None
                h=current.outgoing[a]
            return h
        remaining=0
        for q in qs:
            for r in qs:
                value=self.evidence.cached_result(self.reps[q],self.reps[r],e)
                x,y=endpoint(q),endpoint(r)
                if value!=DIFFERENT and x is not None and y is not None:
                    value=self.evidence.cached_result(x,y,())
                remaining+=value!=DIFFERENT
        return remaining/len(qs)+int(node.belief.new_state_possible)

    def probe(self,node):
        if node.status!='provisional':
            return
        available=[e for e in self.probes if e not in node.tested_probes]
        if not available:
            return
        depth=min(map(len,available))
        options=[(self.probe_score(node,e),e) for e in available if len(e)==depth]
        score,e=min(options)
        qs=sorted(node.belief.existing_candidates)
        self.emit(dict(event='active_probe',history=node.history,selected=e,candidates=qs,
                       new_state_possible=node.belief.new_state_possible,
                       candidate_scores=options,score=score,new_prediction='UNKNOWN'))
        # A probe is marked completed only after every needed comparison;
        # interruption never fabricates a certificate.
        for q in qs:
            cert=self.evidence.compare(node.history,self.reps[q],e)
            if cert['result']==DIFFERENT:
                tests=self.local_tests.setdefault(node.history,[])
                if e not in tests:
                    tests.append(e)
                self.emit(dict(event='local_suffix_certificate',history=node.history,
                               representative=q,suffix=e,certificate=cert['id']))
        node.tested_probes.append(e)
        self.counts['active_probe_depth_'+str(depth)]+=1
        self.classify(node)
        self.maybe_merge(node)

    def step(self):
        self.check()
        if not self.agenda:
            return False
        h=self.agenda.popleft()
        node=self.nodes[h]
        self.classify(node)
        pending=[a for a in self.actions if a not in node.outgoing]
        if pending:
            a=pending[0]
            child=h+(a,)
            self.observe(child)
            if child not in self.nodes:
                self.nodes[child]=PredictiveNode(child,CandidateBelief(set(range(len(self.reps)))))
                self.agenda.append(child)
                self.counts['provisional_nodes_created']+=1
                self.emit(dict(event='provisional_created',history=child,belief=self.nodes[child].belief.record()))
            node.outgoing[a]=child
            self.counts['observed_transitions']+=1
            self.emit(dict(event='observed_transition',history=h,action=a,successor=child,
                           source_status=node.status,source_NEW=node.belief.new_state_possible))
            self.classify(self.nodes[child])
        self.probe(node)
        self.maybe_merge(node)
        if len(node.outgoing)<len(self.actions) or (node.status=='provisional' and len(node.tested_probes)<len(self.probes)):
            self.agenda.append(h)
        return True

    def record(self):
        return dict(representatives=self.reps,nodes=[n.record() for n in self.nodes.values()],
                    agenda=list(self.agenda),local_tests=[(h,e) for h,e in self.local_tests.items()],
                    tree_witnesses=[(q,r,e,c) for (q,r,e),c in self.tree.witnesses.items()],
                    evidence_version=self.evidence.version,counts=dict(self.counts),tree_counts=dict(self.tree.counts),
                    revoked_candidates=[(h,d) for h,d in self.revoked_candidates.items()],
                    merge_scope='reversible empirical depth-2 identity; not universal predictive equivalence')
