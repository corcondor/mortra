import math
import pathlib
import sys
import numpy as np

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from experiments.task_agent.core import (
    ExactState, VarEquals, SequenceTask, AllTask, BranchTask,
    ProductPlanner, solve_field_dense, support_reachable,
)
from experiments.task_agent.exploration import TaskConditionedPolicy
from experiments.task_agent.online import OnlineTaskAgent


class Learner:
    def __init__(self, A):
        self.num_actions=A
        self.state_to_id={}
        self.id_to_state=[]
        self.node_visits={}
        self.action_visits={}
        self.counts={}
        self.dest_map={}
    def get_or_add_id(self,s):
        if s not in self.state_to_id:
            self.state_to_id[s]=len(self.id_to_state); self.id_to_state.append(s)
        return self.state_to_id[s]
    def record_transition(self,u,a,v):
        self.action_visits[(u,a)]=self.action_visits.get((u,a),0)+1
        d=self.counts.setdefault((u,a),{})
        d[v]=d.get(v,0)+1
        self.dest_map[(u,a)]=max(d.items(), key=lambda kv:kv[1])[0]
    def select_action(self,u):
        un=[a for a in range(self.num_actions) if self.action_visits.get((u,a),0)==0]
        if un:return un[0]
        return min(range(self.num_actions),key=lambda a:self.action_visits[(u,a)])


class Env:
    def __init__(self, T, start):
        self.T=T; self.state=start; self.num_actions=len(next(iter(T.values())))
    def reset(self,s=None):
        if s is not None:self.state=s
        return self.state
    def step(self,a):
        self.state=self.T[self.state][a]
        return self.state


def full_learner(T):
    L=Learner(len(next(iter(T.values()))))
    for s in T:L.get_or_add_id(s)
    for s,row in T.items():
        u=L.state_to_id[s]
        for a,ns in enumerate(row):
            L.record_transition(u,a,L.state_to_id[ns])
    return L


def test_source_superposition():
    K=np.array([[0.,1.],[0.,1.]])
    g1=np.array([1.,0.]); g2=np.array([0.,1.])
    a=solve_field_dense(K,g1+g2)
    b=solve_field_dense(K,g1)+solve_field_dense(K,g2)
    assert np.max(np.abs(a-b)) < 1e-12


def test_support_reachability_no_cutoff():
    adj=[[1],[2],[]]
    assert support_reachable(adj,[2]) == {0,1,2}


def test_sequence_memory():
    t=SequenceTask([ExactState("A"),ExactState("B")])
    m=t.initial_memory
    m=t.advance(m,"A")
    assert m==1 and not t.accepting(m)
    m=t.advance(m,"B")
    assert t.accepting(m)


def test_all_memory():
    t=AllTask([ExactState("A"),ExactState("B"),ExactState("C")])
    m=t.advance(0,"B")
    m=t.advance(m,"A")
    assert not t.accepting(m)
    m=t.advance(m,"C")
    assert t.accepting(m)


def test_branch_memory():
    t=BranchTask(ExactState("A"),ExactState("X"),ExactState("B"),ExactState("Y"))
    assert t.advance(0,"A")==1
    assert t.advance(1,"Y")==1
    assert t.advance(1,"X")==3


def test_product_sequence_solves():
    T={
        "S":["A","S"],
        "A":["B","S"],
        "B":["B","B"],
    }
    L=full_learner(T)
    task=SequenceTask([ExactState("A"),ExactState("B")])
    p=ProductPlanner()
    m=task.advance(task.initial_memory,"S")
    a=p.choose_action(L,task,"S",m)
    assert a==0


def test_static_goal_sum_not_sequence_semantics():
    # The task automaton distinguishes A-before-B from B-before-A,
    # while a source vector over {A,B} cannot.
    task=SequenceTask([ExactState("A"),ExactState("B")])
    m0=task.initial_memory
    assert task.advance(m0,"B")==0
    assert task.advance(task.advance(m0,"A"),"B")==2


def test_task_conditioned_policy_never_needs_oracle():
    T={
        "S":["A","S"],
        "A":["A","B"],
        "B":["B","B"],
    }
    L=full_learner(T)
    # Make action 1 at A look underexplored.
    ua=L.state_to_id["A"]
    L.action_visits[(ua,1)]=0
    task=SequenceTask([ExactState("B")])
    policy=TaskConditionedPolicy()
    d=policy.choose(L,"A",task,task.initial_memory)
    assert d.action in (0,1)


def test_live_persistent_online_loop():
    T={
        "S":["A","S"],
        "A":["B","A"],
        "B":["B","B"],
    }
    env=Env(T,"S")
    L=Learner(2)
    L.get_or_add_id("S")
    task=SequenceTask([ExactState("B")])
    agent=OnlineTaskAgent(
        L, TaskConditionedPolicy(),
        max_task_steps=20, max_exploration_steps=20
    )
    result=agent.run_task(env,task,"S")
    assert result.success
    assert len(L.id_to_state) >= 3
