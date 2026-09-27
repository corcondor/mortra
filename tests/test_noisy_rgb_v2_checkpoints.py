import copy
import itertools

import numpy as np

from experiments.noisy_rgb_discovery.core import Emission
from experiments.noisy_rgb_predictive_v2.core import CandidateBelief,EMPIRICAL
from experiments.noisy_rgb_predictive_v2.evaluate import FrozenEvidence,FrozenReadout,unanimous_action
from experiments.noisy_rgb_predictive_v2.snapshots import CheckpointBudget,confirmed_graph,save_checkpoint,load_statistics,verify_checkpoint


def fixture():
    words=[()]+[(a,) for a in range(5)]+list(itertools.product(range(5),repeat=2))
    data={n:{(h,j):Emission(np.zeros(1728,np.float32),np.ones(1728,np.float32),n)
             for h in words for j in (0,1)} for n in (8,16,32)}
    class FakeStats:
        def __init__(self,n):
            self.n=n
        def summary(self,h,rep):
            return Emission(np.zeros(1728,np.float32),np.ones(1728,np.float32),self.n)
    stats={n:FakeStats(n) for n in data}
    state=dict(representatives=[[]],tree_witnesses=[],nodes=[
        dict(history=[],status='representative',representative=0,outgoing=[(a,[a]) for a in range(5)])
    ]+[dict(history=[a],status='merged',representative=0,outgoing=[]) for a in range(5)])
    return data,stats,state


def test_checkpoint_is_before_crossing_not_future_data():
    seen=[]
    budget=CheckpointBudget(lambda target,actual:seen.append((target,actual)),max_wall_seconds=1800)
    budget.exposures=49984
    budget.reserve((),32)
    assert seen==[(50000,49984)]
    assert budget.exposures==50016


def test_missing_prototype_keeps_new():
    data,stats,state=fixture()
    del data[32][((0,0),1)]
    reader=FrozenReadout(state,'V2',FrozenEvidence(data,stats,1),lambda h,r,e:'SAME')
    result=reader.classify((4,4,4))
    assert result.existing_candidates=={0} and result.new_state_possible


def test_empirical_readout_is_not_an_exact_identity_claim():
    data,stats,state=fixture()
    original=copy.deepcopy(state)
    reader=FrozenReadout(state,'V2',FrozenEvidence(data,stats,1),lambda h,r,e:'SAME')
    result=reader.classify((4,4,4))
    assert not result.new_state_possible
    assert result.identity_scope==EMPIRICAL
    assert state==original
    assert all(not e.mean.any() for entries in data.values() for e in entries.values())


def test_partial_transitions_are_not_filled():
    _,_,state=fixture()
    state['nodes'][1]['status']='provisional'
    state['nodes'][1]['representative']=None
    graph=confirmed_graph(state,'V2')
    assert (0,0) not in graph and len(graph)==4


def test_multiple_merged_candidates_are_not_a_deterministic_edge():
    _,_,state=fixture()
    state['nodes'][1]['representative']=None
    graph=confirmed_graph(state,'V2')
    assert (0,0) not in graph


def test_unknown_public_label_blocks_frozen_merge():
    data,stats,state=fixture()
    result=FrozenReadout(state,'V2',FrozenEvidence(data,stats,1)).classify((4,4,4))
    assert result.new_state_possible


def test_consensus_and_new_guard():
    trans={(0,0):2,(1,0):2,(0,1):0,(1,1):1}
    psi=np.array([0.,0.,1.])
    assert unanimous_action(CandidateBelief({0,1},False),trans,psi)==0
    assert unanimous_action(CandidateBelief({0,1},True),trans,psi) is None
    assert unanimous_action(CandidateBelief({0,3},False),trans,psi) is None
    assert (3,0) not in trans


def test_disagreeing_best_actions_require_probe():
    trans={(0,0):2,(1,1):2}
    assert unanimous_action(CandidateBelief({0,1},False),trans,np.array([0.,0.,1.])) is None


def test_checkpoint_statistics_roundtrip(tmp_path):
    data,_,state=fixture()
    class Saved:
        def __init__(self,cache):
            self.cache=cache
    folder=tmp_path/'checkpoint'
    save_checkpoint(folder,state,{n:Saved(entries) for n,entries in data.items()},dict(actual_exposures=0))
    verify_checkpoint(folder)
    loaded=load_statistics(folder)
    assert {n:set(entries) for n,entries in loaded.items()}=={n:set(entries) for n,entries in data.items()}
    assert all(np.array_equal(loaded[n][key].mean,emission.mean) for n,entries in data.items() for key,emission in entries.items())
