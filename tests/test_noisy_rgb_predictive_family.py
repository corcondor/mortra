"""Abstract fixtures only; no development world is sampled by these tests."""
import ast
from collections import Counter, deque
from copy import deepcopy
import gzip
import hashlib
import json
from pathlib import Path

import pytest

from experiments.noisy_rgb_predictive_v2.core import ProvisionalLearner, PredictiveNode, CandidateBelief
from experiments.noisy_rgb_predictive_family import core
from experiments.noisy_rgb_predictive_family.core import FamilyLearner, WORDS, signature, signature_id


class Evidence:
    def __init__(self, emit, result='UNRESOLVED'):
        self.cache, self.version, self.calls = {}, 0, []
        self.emit, self.result = emit, result

    def compare(self, h, r, e=(), stage=32):
        pair = tuple(sorted((tuple(h)+tuple(e), tuple(r)+tuple(e))))
        self.calls.append((tuple(h),tuple(r),tuple(e)))
        if pair[0] == pair[1]:
            return dict(result='SAME', id=None, stage=stage)
        key = (pair,stage)
        if key not in self.cache:
            self.version += 1
            row = dict(event='comparison', result=self.result, id=self.version, stage=stage, pair=pair)
            self.cache[key] = row
            self.emit(row)
        return self.cache[key]

    def cached_result(self, h, r, e):
        pair = tuple(sorted((tuple(h)+tuple(e), tuple(r)+tuple(e))))
        return 'SAME' if pair[0] == pair[1] else self.cache.get((pair,32),{}).get('result','UNRESOLVED')


def make(family=True, sharing=True, result='UNRESOLVED'):
    events, observed = [], []
    holder = []
    def emit(row):
        events.append(deepcopy(row))
        if holder:
            holder[0].receive_certificate(row)
    evidence = Evidence(emit,result)
    arguments = (evidence,range(5),observed.append,emit)
    keywords = dict(label_equality=lambda h,r,e:'SAME')
    model = (FamilyLearner(*arguments,labels={},sharing=sharing,**keywords) if family else
             ProvisionalLearner(*arguments,**keywords))
    holder.append(model)
    model.start()
    return model, evidence, events, observed


def add_node(model, h, candidates=(0,)):
    node = PredictiveNode(h,CandidateBelief(set(candidates)))
    model.nodes[h] = node
    model.evidence.compare(h,(),())
    model.refresh(node)
    return node


def test_sharing_disabled_reproduces_original_actions_nodes_evidence_and_order():
    a, ea, events_a, oa = make(family=False)
    b, eb, events_b, ob = make(sharing=False)
    for _ in range(40):
        assert a.step() == b.step()
    assert oa == ob and ea.calls == eb.calls and ea.cache == eb.cache
    assert a.record() == ProvisionalLearner.record(b)
    assert list(a.nodes) == list(b.nodes)
    original_events = [e for e in events_b if not e['event'].startswith('family_')]
    assert events_a == original_events


def test_family_signature_has_no_history_identity_or_certificate_id():
    model, ev, _, _ = make()
    a = add_node(model,(3,3,3))
    b = add_node(model,(4,4,4))
    assert model.membership[a.history] == model.membership[b.history]
    assert a is not b and a.belief is not b.belief
    a.certificates.append(999)
    model.refresh(a)
    assert model.membership[a.history] == model.membership[b.history]
    a.belief.new_state_possible = False
    model.refresh(a)
    assert model.membership[a.history] != model.membership[b.history]


def test_peer_low_information_changes_probe_not_identity_or_evidence():
    model, ev, events, _ = make()
    a = add_node(model,(3,3,3))
    b = add_node(model,(4,4,4))
    original_b = deepcopy(b.record())
    model.probe(a)
    assert b.record() == original_b
    assert model.cached(b.history,(),(0,)) == 'NOT_COMPARED'
    model.probe(b)
    decisions = [e for e in events if e['event']=='family_probe_choice']
    assert decisions[0]['selected'] == (0,)
    assert decisions[1]['baseline_selected'] == (0,)
    assert decisions[1]['selected'] == (1,)
    assert decisions[1]['shared'] and decisions[1]['avoided_redundant_opportunity']
    assert (b.history,(),(1,)) in ev.calls
    assert model.cached(b.history,(),(0,)) == 'NOT_COMPARED'
    assert b.status == 'provisional' and b.belief.new_state_possible


@pytest.mark.parametrize('change', ['label','outgoing','candidate','outcome','tested'])
def test_public_changes_split_family_without_modifying_peer(change):
    model, ev, _, _ = make()
    a,b = (add_node(model,h) for h in ((3,3,3),(4,4,4)))
    peer = deepcopy(b.record())
    initial = model.membership[a.history]
    if change == 'label':
        model.labels[a.history] = {'goal':False}
    elif change == 'outgoing':
        a.outgoing[0] = a.history+(0,)
    elif change == 'candidate':
        a.belief.existing_candidates.clear()
    elif change == 'outcome':
        ev.compare(a.history,(),(2,))
    else:
        a.tested_probes.append((2,))
    model.refresh(a)
    assert model.membership[a.history] != initial == model.membership[b.history]
    assert b.record() == peer


def test_saturation_at_fixed_count_and_new_certificate_reactivation():
    model, ev, events, _ = make()
    initial = None
    for number in range(core.SATURATION_ATTEMPTS):
        h = (3,)*3+(4,)*number+(2,)
        node = add_node(model,h)
        initial = initial or model.membership[h]
        assert model.membership[h] == initial
        model.probe(node)
    family = model.families[initial]
    assert family.stagnant == 31 and family.saturated
    assert sum(e['event']=='FAMILY_SATURATED' for e in events)==1
    ev.compare((4,4,4,4),(3,3,3,3),(4,))
    assert not family.saturated and family.stagnant == 0


def test_state_identity_functions_are_inherited_without_replacement():
    for name in ('empirical_match','maybe_merge','revalidate_merge','observed_contradiction'):
        assert getattr(FamilyLearner,name) is getattr(ProvisionalLearner,name)


def test_all_31_direct_certificates_still_required_and_unmerge_preserves_data():
    model, ev, _, _ = make(result='SAME')
    model.reps.append((4,))
    model.nodes[(4,)] = PredictiveNode((4,),CandidateBelief({1},False),status='representative',representative=1)
    h = (3,3,3)
    node = add_node(model,h,candidates=(0,1))
    for item in model.nodes.values():
        item.outgoing = {a:item.history+(a,) for a in range(5)}
    for q in range(2):
        for e in WORDS:
            if (q,e)!=(1,(4,4)):
                ev.compare(h,model.reps[q],e)
    model.maybe_merge(node)
    assert node.belief.new_state_possible
    ev.compare(h,model.reps[1],(4,4))
    model.maybe_merge(node)
    assert node.status=='merged' and node.representative is None
    assert node.belief.existing_candidates=={0,1}
    assert node.merge_records[0]['tested_sequences']==31
    edges = dict(node.outgoing)
    ev.result = 'DIFFERENT'
    ev.compare(h,(),(2,2,2))
    assert node.status=='provisional' and node.belief.new_state_possible
    assert node.belief.existing_candidates=={1} and node.outgoing==edges


def test_representative_witness_is_only_a_priority_not_target_proof():
    model, ev, events, _ = make()
    model.reps.append((4,))
    model.nodes[(4,)] = PredictiveNode((4,),CandidateBelief({1},False),status='representative')
    ev.result='DIFFERENT'
    ev.compare((),(4,),(2,))
    ev.result='UNRESOLVED'
    node=add_node(model,(3,3,3),candidates=(0,1))
    model.probe(node)
    chosen=[e for e in events if e['event']=='family_probe_choice'][-1]
    assert chosen['selected']==(2,)
    assert (node.history,(),(2,)) in ev.calls and (node.history,(4,),(2,)) in ev.calls
    assert node.belief.existing_candidates=={0,1} and node.belief.new_state_possible


def test_saved_memberships_reconstruct_and_do_not_change_node_records():
    model, _, _, _ = make()
    for _ in range(15):
        model.step()
    before=ProvisionalLearner.record(model)
    record=model.record()
    assert before==ProvisionalLearner.record(model)
    actual={tuple(h):key for h,key in record['family_membership']}
    expected={h:signature_id(signature(n,model.reps,model.labels,model.cached))
              for h,n in model.nodes.items() if n.status=='provisional'}
    assert actual==expected


def test_learning_core_cannot_access_truth_physics_or_sensor_internals():
    tree=ast.parse(Path(core.__file__).read_text())
    forbidden={'raw_step','raw_goal','start_raw','truth','partition','make_game','render_rgb','noisy_rgb','noisy_batch'}
    assert not {n.attr for n in ast.walk(tree) if isinstance(n,ast.Attribute)} & forbidden
    imports=[n.module or '' for n in ast.walk(tree) if isinstance(n,ast.ImportFrom)]
    assert not any('evaluate' in x or 'truth_table' in x or 'sensor' in x for x in imports)


def test_saturated_family_is_deprioritized_without_dropping_histories(monkeypatch):
    model, _, _, _ = make()
    a = add_node(model,(3,3,3))
    b = add_node(model,(4,4,4))
    b.outgoing[0] = b.history+(0,)
    model.refresh(b)
    model.families[model.membership[a.history]].saturated = True
    model.agenda = deque([a.history,b.history])
    monkeypatch.setattr(ProvisionalLearner,'step',lambda self:self.agenda.popleft())
    assert model.step() == b.history
    assert list(model.agenda) == [a.history]
    assert a.history in model.nodes and a.belief.new_state_possible


def test_frozen_family_truth_diagnostic_does_not_authorize_merge():
    from experiments.noisy_rgb_predictive_family.analyze import checkpoint_metrics
    model, ev, events, _ = make()
    for h in ((3,3,3),(4,4,4)):
        add_node(model,h)
    state = model.record()
    state['public_labels'] = []
    meta=dict(seed=97027000,camera='base',target_exposures=50000,actual_exposures=49992,
        environment_actions=100,requested_checkpoint_reached=True,acquisition_cpu_seconds=1,
        acquisition_wall_seconds=1,peak_memory_bytes=100)
    cache={pair:value for (pair,stage),value in ev.cache.items() if stage==32}
    row, groups=checkpoint_metrics(state,meta,cache,Counter(e['event'] for e in events),Counter(),
        {'start':0,'transitions':[[0]*5]},[[0]],'B',None)
    assert row['provisional_nodes']==2 and row['families']==row['pure_families']==1
    assert row['mixed_families']==0
    assert all(n.belief.new_state_possible for n in model.nodes.values() if n.status=='provisional')
    assert all(n.status!='merged' for n in model.nodes.values())


def test_missing_heldout_or_checkpoint_is_not_a_success_claim():
    from experiments.noisy_rgb_predictive_family.aggregate import assess
    a=dict(checkpoint_reached=True,actual_exposures=50000,represented_union_classes=10,
        exposures_per_represented_class=5000,heldout_unresolved_rate=None,confirmed_representatives=2,
        control_success=False,heldout_wrong_unique_rate=None,heldout_cases=100,
        wrong_empirical_merges_active=0,wrong_empirical_merges_ever=0,transition_errors=0)
    b=dict(a,represented_union_classes=20,exposures_per_represented_class=2500)
    assert assess(a,b)['verdict']=='UNDETERMINED_SAFETY'
    a.update(heldout_wrong_unique_rate=0,heldout_cases=5000)
    b.update(heldout_wrong_unique_rate=0,heldout_cases=5000)
    assert assess(a,b)['verdict']=='SPECIFIED_IMPROVEMENT'
    b['transition_errors']=1
    assert assess(a,b)['verdict']=='SAFETY_WORSENED'
    b['checkpoint_reached']=False
    assert assess(a,b)['verdict']=='UNMATCHED_RESOURCE_CHECKPOINT'


def test_saved_artifact_audit_excludes_post_checkpoint_certificates(tmp_path):
    from experiments.noisy_rgb_predictive_family.analyze import analyze_arm
    model,ev,events,_=make()
    add_node(model,(3,3,3))
    add_node(model,(4,4,4))
    model.probe(model.nodes[(3,3,3)])
    state=model.record()
    state['public_labels']=[]
    folder=tmp_path/'saved'
    checkpoint=folder/'checkpoint_50000'
    checkpoint.mkdir(parents=True)
    output=tmp_path/'audit'
    output.mkdir()
    meta=dict(seed=97027000,camera='base',target_exposures=50000,actual_exposures=49992,
        environment_actions=100,requested_checkpoint_reached=True,acquisition_cpu_seconds=1,
        acquisition_wall_seconds=1,peak_memory_bytes=100,event_prefix_count=len(events))
    for path,value in ((checkpoint/'state.json',state),(checkpoint/'checkpoint.json',meta),
        (folder/'source_snapshot.json',{'commit':'abstract-fixture'}),
        (folder/'result.json',{'status':'ABSTRACT_FIXTURE','total_cpu_seconds':1,'total_wall_seconds':1,'peak_memory_bytes':100})):
        path.write_text(json.dumps(value),encoding='utf-8')
    future=dict(event='comparison',stage=32,id=ev.version+1,pair=[(3,3,3,4,4),(4,4)],result='DIFFERENT')
    with gzip.open(folder/'events.jsonl.gz','wt',encoding='utf-8') as f:
        for i,event in enumerate(events+[future],1):
            f.write(json.dumps(dict(event,event_index=i))+'\n')
    hashes={str(f.relative_to(folder)):hashlib.sha256(f.read_bytes()).hexdigest() for f in folder.rglob('*') if f.is_file()}
    (folder/'artifact_hashes.json').write_text(json.dumps(hashes),encoding='utf-8')
    result=analyze_arm(folder,'B',output,{'start':0,'transitions':[[0]*5],'observations':[0]})
    assert len(result['rows'])==1 and result['rows'][0]['provisional_nodes']==2
    assert result['rows'][0]['probe_count']==1
