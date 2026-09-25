import copy
import math
import random
from pathlib import Path
import numpy as np
import pytest

from experiments.frontier_v12_theory import maths,data,landscape
from experiments.game_frontier_v12 import run as original
from experiments.game_frontier_v12.proposal import Context,ContextualUCB,Outcome,reward


def test_source_freeze():
    hashes=data.frozen_sources()
    assert len(original.holdout.verified_sources())==18 and len(hashes)>18


@pytest.mark.parametrize('s,expected', [([0,0,1,1],(True,0,1.5)),([0,1,0,1],(False,1,1.5)),([0,0,0,0],(True,0,3)),([1,1,1,1],(True,0,0))])
def test_threshold(s,expected):
    r=maths.threshold_audit(s,[1,2,4,8])
    assert (r['monotone'],r['reversals'],r['D_task'])==expected
    assert r['D_task']==r['capped_log_threshold']-r['trapezoid_half_bin']+r['nonmonotonicity_penalty']


def test_all_binary_thresholds():
    import itertools
    for bits in itertools.product((0,1),repeat=7):
        r=maths.threshold_audit(bits,[2**i for i in range(7)])
        assert r['nonmonotonicity_penalty']>=0


def test_attenuation():
    r=maths.path_attenuation([.2]*10)
    assert np.isclose(r['A_path'],(.9/5)**10,rtol=1e-14,atol=0)
    assert r['below_cutoff'] and np.isclose(r['b_eff'],5)


def test_field_series_solve_and_greedy():
    k=np.array([[.5,.5,0],[0,.5,.5],[0,0,1.]])
    g=np.array([0.,0.,1.]);exact=np.linalg.solve(np.eye(3)-.9*k,g)
    from experiments.game_frontier_v1.frozen import solve_fixed_field
    approx,_,_,_=solve_fixed_field(k,2)
    assert np.max(np.abs(exact-approx))<1e-7
    total=np.zeros(3);term=g.copy()
    for _ in range(400): total+=term;term=.9*k@term
    assert np.allclose(total,exact,atol=1e-12)
    assert exact[2]>exact[1]>exact[0]>0


def test_normal_maximum_and_response():
    c=maths.max_normal_constant()
    assert abs(c['value']-1.4236003060452778)<1e-10
    pairs=[(-2,-3),(-1,-1),(0,1),(1,3),(2,5)]
    pred=maths.gaussian_response(pairs,c['value'])
    assert np.isclose(pred,1+2*np.std([-2,-1,0,1,2],ddof=1)*c['value'])
    b=maths.resampled_response(pairs,42,draws=2000)
    assert b['expected_max_X_response']>b['expected_random_response']


def test_probability_and_ties():
    mu=np.arange(14,dtype=float)
    c=maths.calibration(mu,[1/14]*14,[None]*14)
    assert c['Delta_E']==pytest.approx(0) and c['rho_P'] is None and c['rho_UCB'] is None
    assert c['top3_expected_overlap']==pytest.approx(9/14)
    c=maths.calibration(mu,[0]*13+[1],list(mu))
    assert c['R1']==0 and c['Delta_E']==6.5 and c['rho_UCB']==pytest.approx(1)


def test_frozen_reward_and_state_replay():
    ctx=Context(100,5,2,4,144,10,8192);m=ContextualUCB(13);n=ContextualUCB(13)
    for i in range(40):
        out=Outcome(True,True,10+(i%3)-1,8192,8192,.9,1.)
        a=original.FAMILIES[i%14]
        assert m.update(ctx,a,out)==reward(ctx.selection_D,out)==n.update(ctx,a,out)
        assert m.snapshot()==n.snapshot() and m.decision(ctx,2)==n.decision(ctx,2)
    assert reward(10,Outcome(False,False,None,None,None,None,None))==0


def test_seeds_all_arms_and_no_parent_update(tmp_path,monkeypatch):
    g=original.frozen.generate(random.Random(42))
    parent=dict(parent_id='test',seed=2101,game_hash=original.frozen.game_hash(g),genome=g,D_parent=10,
                context_id='6:reached',context={},generations=[0])
    before=copy.deepcopy(parent);attempts=[]
    def invalid(genome,arm,rng,cap):
        attempts.append(arm);raise ValueError('fixture invalid')
    monkeypatch.setattr(original.frozen,'mutate',invalid)
    for arm in original.FAMILIES:
        seed,rng=landscape.mutation_rng(parent['game_hash'],arm,0)
        seed2,rng2=landscape.mutation_rng(parent['game_hash'],arm,0)
        assert seed==seed2 and rng.random()==rng2.random()
        r,_=landscape.evaluate_one(parent,arm,0,original.config(),tmp_path)
        assert r['reward']==0 and r['mutation_attempts']==1 and r['parent_unchanged']
    assert attempts==list(original.FAMILIES) and parent==before
    assert len({landscape.mutation_rng(parent['game_hash'],a,r)[0] for a in original.FAMILIES for r in range(10)})==140


def test_leak_rejected(tmp_path):
    with pytest.raises(AssertionError):
        landscape.evaluate_one(dict(holdout_D=0),'guard',0,original.config(),tmp_path)


def test_no_missing_y_imputation():
    assert maths.gaussian_response([],1.4) is None
    assert maths.resampled_response([],42) is None
    assert maths.response_stats([])['Pearson'] is None
