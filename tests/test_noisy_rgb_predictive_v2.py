import ast
from pathlib import Path

from experiments.noisy_rgb_predictive_v2 import core
from experiments.noisy_rgb_predictive_v2.core import CandidateBelief,AdaptiveDiscriminationTree,ProvisionalLearner
from experiments.noisy_rgb_version_space.core import SAME,DIFFERENT,UNRESOLVED


class Evidence:
    def __init__(self,result):
        self.result=result
        self.cache={}
        self.version=0
    def compare(self,h,r,e=(),stage=32):
        pair=tuple(sorted((tuple(h)+tuple(e),tuple(r)+tuple(e))))
        if pair[0]==pair[1]:
            return dict(result=SAME,id=None,stage=32)
        if pair not in self.cache:
            self.version+=1
            self.cache[pair]=dict(result=self.result(*pair),id=self.version,stage=stage)
        return self.cache[pair]
    def cached_result(self,h,r,e):
        pair=tuple(sorted((tuple(h)+tuple(e),tuple(r)+tuple(e))))
        return SAME if pair[0]==pair[1] else self.cache.get(pair,{}).get('result',UNRESOLVED)


def test_new_is_not_removed_by_same_or_unresolved():
    for outcome in (SAME,UNRESOLVED):
        tree=AdaptiveDiscriminationTree(Evidence(lambda h,r:outcome),lambda e:None)
        belief,_=tree.classify((0,),[()],recognize_replay=False)
        assert belief.existing_candidates=={0}
        assert belief.new_state_possible


def test_different_only_removes_that_candidate():
    evidence=Evidence(lambda h,r: DIFFERENT if (1,) in (h,r) else UNRESOLVED)
    tree=AdaptiveDiscriminationTree(evidence,lambda e:None)
    belief,proof=tree.classify((0,),[(),(1,)],recognize_replay=False)
    assert belief.existing_candidates=={0} and set(proof)=={1}
    assert belief.new_state_possible


def test_provisional_with_new_executes_actions():
    observed=[]
    events=[]
    model=ProvisionalLearner(Evidence(lambda h,r:UNRESOLVED),[0,1],observed.append,events.append)
    model.start()
    for _ in range(8):
        model.step()
    assert len(model.reps)==1
    assert any(e['event']=='observed_transition' and e['source_NEW'] for e in events)
    assert len(observed)>1
    assert all(n.belief.new_state_possible for h,n in model.nodes.items() if h)


def test_empirical_merge_requires_all_tests_and_edges():
    observed=[]
    model=ProvisionalLearner(Evidence(lambda h,r:SAME),[0],observed.append,lambda e:None,
                             label_equality=lambda h,r,e:SAME)
    model.start()
    model.step()
    child=model.nodes[(0,)]
    assert child.status=='provisional'
    for _ in range(8):
        model.step()
    assert any(n.status=='merged' for n in model.nodes.values())
    for n in model.nodes.values():
        if n.status=='merged':
            assert n.belief.identity_scope==core.EMPIRICAL
            assert not n.belief.new_state_possible


def test_local_witness_does_not_clear_unrelated_leaves():
    tree=AdaptiveDiscriminationTree(Evidence(lambda h,r:DIFFERENT),lambda e:None)
    tree.leaves[frozenset({0,1})]={'sentinel':True}
    tree.leaves[frozenset({2,3})]={'sentinel':True}
    tree.add_witness(0,1,(0,),dict(id=1,result=DIFFERENT,stage=32))
    assert frozenset({0,1}) not in tree.leaves
    assert frozenset({2,3}) in tree.leaves


def test_classifier_cannot_use_transitivity():
    table={((),(0,)):SAME, ((0,),(1,)):SAME, ((),(1,)):DIFFERENT}
    evidence=Evidence(lambda h,r:table.get((h,r),UNRESOLVED))
    tree=AdaptiveDiscriminationTree(evidence,lambda e:None)
    belief,_=tree.classify((0,),[(),(1,)],recognize_replay=False)
    assert belief.existing_candidates=={0,1} and belief.new_state_possible


def test_probes_unknown_new_and_depth_two():
    events=[]
    model=ProvisionalLearner(Evidence(lambda h,r:UNRESOLVED),[0,1],lambda h:None,events.append)
    model.start()
    for _ in range(12):
        model.step()
    probes=[e for e in events if e['event']=='active_probe']
    assert probes
    assert all(e['new_prediction']=='UNKNOWN' and len(e['selected'])<=2 for e in probes)


def test_core_has_no_hidden_or_goal_access():
    source=Path(core.__file__).read_text()
    tree=ast.parse(source)
    forbidden={'raw_step','start_raw','raw_goal','truth','partition','make_game','render_rgb','q','goal'}
    assert not {n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)} & forbidden


def test_records_separate_provisional_and_confirmed():
    model=ProvisionalLearner(Evidence(lambda h,r:UNRESOLVED),[0],lambda h:None,lambda e:None)
    model.start()
    model.step()
    record=model.record()
    assert len(record['representatives'])==1
    assert sum(n['status']=='provisional' for n in record['nodes'])==1
    assert record['nodes'][1]['belief']['new_state_possible']


def merge_fixture(outcome=SAME,label=SAME):
    ev=Evidence(lambda h,r:outcome)
    model=ProvisionalLearner(ev,range(5),lambda h:None,lambda e:None,label_equality=lambda h,r,e:label)
    model.reps=[(),(4,)]
    h=(3,3,3)
    for history in [(),(4,),h]:
        model.nodes[history]=core.PredictiveNode(history,CandidateBelief({0,1}),
                                               outgoing={a:history+(a,) for a in range(5)})
    for q in range(2):
        for e in [()]+model.probes:
            ev.compare(h,model.reps[q],e)
    return model,model.nodes[h]


def test_all_31_include_empty_and_public_labels():
    for label in (DIFFERENT,UNRESOLVED):
        model,node=merge_fixture(label=label)
        model.maybe_merge(node)
        assert node.belief.new_state_possible and node.status=='provisional'
    model,node=merge_fixture()
    pair=tuple(sorted((node.history,model.reps[0])))
    model.evidence.cache[pair]['result']=UNRESOLVED
    model.maybe_merge(node)
    assert node.belief.new_state_possible


def test_multiple_complete_matches_are_not_arbitrarily_collapsed():
    model,node=merge_fixture()
    model.maybe_merge(node)
    assert node.status=='merged' and not node.belief.new_state_possible
    assert node.belief.existing_candidates=={0,1} and node.representative is None
    record=node.merge_records[0]
    assert record['tested_sequences']==31 and record['tested_suffixes'][0]==()
    assert all(len(c)==31 for c in record['SAME_certificates'].values())
    assert record['reversible'] and record['identity_scope']==core.EMPIRICAL


def test_later_observed_future_revokes_without_deleting_or_deeper_probe():
    model,node=merge_fixture()
    model.maybe_merge(node)
    old_edges=dict(node.outgoing)
    suffix=(1,1,1)
    model.receive_certificate(dict(event='comparison',result=DIFFERENT,stage=32,id=999,
                                  pair=[node.history+suffix,model.reps[0]+suffix]))
    assert node.status=='provisional' and node.belief.new_state_possible
    assert node.belief.existing_candidates=={1}
    assert node.outgoing==old_edges and node.history in model.nodes
    assert node.merge_records[0]['revocation']['counterexamples'][0]['certificate']==999
    assert max(map(len,model.probes))==2
    assert node.history in model.agenda
