"""Development fixtures are not evidence of autonomous acquisition."""
from collections import Counter
from fractions import Fraction as F
import itertools

import numpy as np
import pytest

from scripts.evaluate_adaptive_refinement import (
    HistoryModel, IdentificationPolicy, exact_quotient, exact_margin_certificate,
    reason, true_partition, evaluate_goals, replay_stream, default_config,
)


def test_observation_labels_cannot_merge():
    q=exact_quotient([0,1],[(0,),(0,)],{(0,0):Counter({0:1}),(1,0):Counter({1:1})})
    assert len(q["groups"])==2


def test_action_availability_cannot_merge():
    q=exact_quotient([0,0],[(0,),(0,1)],{})
    assert len(q["groups"])==2


def test_unknown_is_not_evidence_for_known_self_loop():
    q=exact_quotient([0,0],[(0,),(0,)],{(0,0):Counter({0:1})})
    assert len(q["groups"])==2
    assert not q["complete"]


def test_exact_rational_rows_merge_equal_ratios():
    q=exact_quotient([0,0,1,2],[(0,)]*4,
                    {(0,0):Counter({2:1,3:2}),(1,0):Counter({2:2,3:4}),
                     (2,0):Counter({2:1}),(3,0):Counter({3:1})})
    assert q["blocks"][0]==q["blocks"][1]
    assert q["rows"][0,0]=={q["blocks"][2]:F(1,3),q["blocks"][3]:F(2,3)}


def test_exact_rows_refuse_different_probabilities():
    q=exact_quotient([0,0,1,2],[(0,)]*4,
                    {(0,0):Counter({2:1,3:2}),(1,0):Counter({2:2,3:3})})
    assert q["blocks"][0]!=q["blocks"][1]


def test_refinement_propagates_beyond_one_step():
    table=np.array([[1],[2],[2],[4],[5],[5]])
    q=true_partition(table,[0,0,1,0,0,2])
    assert q["blocks"][0]!=q["blocks"][3]


def test_shortest_history_counterexample_and_no_hidden_input():
    m=HistoryModel(2)
    m.begin(0)
    for i,(a,o) in enumerate([(0,1),(0,2),(1,0),(1,1),(0,3)],1):
        m.observe(a,o,i)
    events=[e for e in m.events if e["kind"]=="split"]
    assert events and events[0]["depth"]==1
    assert all(e["depth"]<=6 for e in events)
    assert m.model["exact_certificate"]


def test_no_split_ablation_keeps_conflict():
    m=replay_stream([(None,0),(0,1),(0,2),(1,0),(1,1),(0,3)],2,"no_split")
    assert m.split_count==0
    assert not m.summary()["history_independent"]


def test_unresolvable_identical_context_is_not_certified_deterministic():
    m=HistoryModel(1)
    m.begin(0)
    u=m.context_index[m.current]
    v=m._intern((1,));w=m._intern((2,))
    m.raw[u,0][v]=1;m.raw[u,0][w]=1
    m.rebuild(1)
    assert not m.summary()["history_independent"]


def test_merge_retains_original_history_evidence():
    m=replay_stream([(None,0)]+[(0,0)]*8,1,"split_merge",fixed_depth=1)
    assert len(m.model["groups"])==1
    assert len(m.contexts)>1 and len(m.raw)>1
    assert m.summary()["peak_states"]>=m.summary()["final_states"]


@pytest.mark.parametrize("seed",range(10))
def test_exact_certificate_against_independent_rational_solution(seed):
    import sympy as sp
    rng=np.random.default_rng(seed)
    table=rng.integers(0,5,size=(5,2))
    rows=[]
    for targets in table:
        c=Counter(map(int,targets));rows.append({v:F(n,2) for v,n in c.items()})
    choices={0:{int(table[0,0]):F(1)},1:{int(table[0,1]):F(1)}}
    result=reason(rows,choices,[4],"certified")
    k=sp.zeros(5)
    for i,row in enumerate(rows):
        for j,p in row.items():k[i,j]=sp.Rational(p.numerator,p.denominator)
    x=(sp.eye(5)-sp.Rational(9,10)*k).inv()*sp.Matrix([0,0,0,0,1])
    scores={a:sum(sp.Rational(p.numerator,p.denominator)*x[v] for v,p in row.items()) for a,row in choices.items()}
    if result["certified"]:
        best=result["action"]
        assert all(scores[best]>s for a,s in scores.items() if a!=best)


def test_ties_do_not_get_margin_certificate():
    r=reason([{0:F(1)}],{0:{0:F(1)},1:{0:F(1)}},[0],"certified")
    assert not r["certified"] and r["status"]=="full_tolerance_uncertified"


def test_non_substochastic_rejected():
    with pytest.raises(ValueError):
        exact_margin_certificate([{0:F(2)}],{0:{0:F(1)}},[1],[0.],0)


def test_unknown_goal_counted_as_failure():
    m=replay_stream([(None,0),(0,0)],1,"no_split")
    result,_=evaluate_goals(m,lambda s,a:s,lambda s,t:0,[0],[7],10,0)
    assert result=={"successes":0,"trials":1,"success":0.}


def test_policy_expiry_and_unexpected_transition():
    p=IdentificationPolicy(2,0)
    p.target=(1,0);p.remaining=0
    p.choose(0,{(0,0):Counter({1:1})})
    assert p.expirations==1
    p.target=(1,0);p.expected=1
    p.choose(2,{(2,0):Counter({2:1})})
    assert p.invalidations==1


def test_predeclared_design_and_thresholds():
    c=default_config()
    assert len(c["finite_systems"])==100
    assert {s["n"] for s in c["finite_systems"]}=={20,50,100}
    assert {s["actions"] for s in c["finite_systems"]}=={2,4,8}
    assert c["success_criteria"]["recovery"]==.99


def test_minimal_quotient_against_exhaustive_partitions():
    table=np.array([[1,2],[1,2],[3,3],[3,3]])
    labels=[0,0,1,1]
    valid=[]
    for p in itertools.product(range(4),repeat=4):
        if p[0]!=0:continue
        if any(p[i]>max(p[:i],default=-1)+1 for i in range(4)):continue
        if all(p[i]!=p[j] or (labels[i]==labels[j] and all(p[table[i,a]]==p[table[j,a]] for a in range(2)))
               for i in range(4) for j in range(4)):
            valid.append(len(set(p)))
    assert len(true_partition(table,labels)["groups"])==min(valid)
