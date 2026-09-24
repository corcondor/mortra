from __future__ import annotations
import itertools, random, pytest
from exact_moore_oracle import (
    MooreMachine, Relation, assert_oracles_agree, canonical_partition,
    distinguishing_depth, partition_refinement, permute_actions,
    relation_under_partial_transition_knowledge, relabel_states,
)
from microbench_fixtures import ALL_FIXTURES, delayed_bit_effect, unreachable_state

@pytest.mark.parametrize("factory",ALL_FIXTURES,ids=lambda f:f.__name__)
def test_hand_audited_fixture_partition_and_depths(factory):
    fx=factory(); m=fx.machine
    assert_oracles_agree(m)
    assert partition_refinement(m)==fx.expected_partition
    for pair,expected in fx.expected_depths.items():
        assert distinguishing_depth(m,*pair)==expected

def test_reachable_only_excludes_unreachable():
    fx=unreachable_state(); m=fx.machine
    r=m.reachable(fx.initial_states)
    assert r==frozenset({0,1})
    assert partition_refinement(m,r)==((0,),(1,))
    assert_oracles_agree(m,r)

def test_action_permutation_invariance():
    fx=delayed_bit_effect(); m=fx.machine
    mp=permute_actions(m,{"tick":"read","read":"tick"})
    assert partition_refinement(mp)==partition_refinement(m)
    for pair,d in fx.expected_depths.items():
        assert distinguishing_depth(mp,*pair)==d

def test_state_relabel_invariance():
    fx=delayed_bit_effect(); m=fx.machine
    relabel={s:(s+3)%len(m.states) for s in m.states}
    mr=relabel_states(m,relabel)
    mapped=canonical_partition([[relabel[s] for s in b] for b in partition_refinement(m)],mr)
    assert partition_refinement(mr)==mapped

def test_partial_unknown_then_different():
    m=delayed_bit_effect().machine
    observed={(4,"tick"),(5,"tick")}
    assert relation_under_partial_transition_knowledge(m,observed,4,5)==Relation.UNKNOWN
    observed|={(4,"read"),(5,"read")}
    assert relation_under_partial_transition_knowledge(m,observed,4,5)==Relation.DIFFERENT

def test_partial_can_certify_equivalent_when_closed_and_fully_observed():
    from microbench_fixtures import equivalent_states
    m=equivalent_states().machine
    observed={(s,a) for s in m.states for a in m.actions}
    assert relation_under_partial_transition_knowledge(m,observed,0,1)==Relation.EQUIVALENT

def test_exhaustive_all_3state_2action_2output_machines():
    states=(0,1,2); actions=(0,1); checked=0
    for outputs in itertools.product((0,1),repeat=3):
        O=dict(zip(states,outputs))
        for dests in itertools.product(states,repeat=6):
            T={}; k=0
            for s in states:
                for a in actions:
                    T[(s,a)]=dests[k]; k+=1
            assert_oracles_agree(MooreMachine(states,actions,O,T))
            checked+=1
    assert checked==5832

def test_random_4state_crosscheck_and_relabelings():
    rng=random.Random(20260924); states=(0,1,2,3); actions=(0,1,2)
    for _ in range(200):
        O={s:rng.randrange(3) for s in states}
        T={(s,a):rng.choice(states) for s in states for a in actions}
        m=MooreMachine(states,actions,O,T); assert_oracles_agree(m)
        p=list(states); rng.shuffle(p); relabel=dict(zip(states,p))
        assert_oracles_agree(relabel_states(m,relabel))
