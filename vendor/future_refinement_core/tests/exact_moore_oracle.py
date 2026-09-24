from __future__ import annotations
from collections import defaultdict, deque
from dataclasses import dataclass
from enum import Enum
from typing import Dict, FrozenSet, Hashable, Iterable, Mapping, Optional, Sequence, Tuple

State=Hashable; Action=Hashable; Output=Hashable; Word=Tuple[Action,...]

@dataclass(frozen=True)
class MooreMachine:
    states: Tuple[State,...]
    actions: Tuple[Action,...]
    output: Mapping[State,Output]
    transition: Mapping[Tuple[State,Action],State]
    def __post_init__(self):
        if not self.states or not self.actions: raise ValueError("non-empty states/actions required")
        if len(set(self.states))!=len(self.states): raise ValueError("duplicate states")
        if len(set(self.actions))!=len(self.actions): raise ValueError("duplicate actions")
        S=set(self.states)
        for s in self.states:
            if s not in self.output: raise ValueError(f"missing output for {s!r}")
            for a in self.actions:
                if (s,a) not in self.transition: raise ValueError(f"missing transition {(s,a)!r}")
                if self.transition[(s,a)] not in S: raise ValueError("transition leaves state set")
    def step(self,s,a): return self.transition[(s,a)]
    def run(self,s,word):
        for a in word: s=self.step(s,a)
        return s
    def output_after(self,s,word): return self.output[self.run(s,word)]
    def reachable(self,initial)->FrozenSet[State]:
        initial=tuple(initial); S=set(self.states)
        if any(s not in S for s in initial): raise KeyError("initial outside machine")
        seen=set(initial); q=deque(initial)
        while q:
            s=q.popleft()
            for a in self.actions:
                t=self.step(s,a)
                if t not in seen: seen.add(t); q.append(t)
        return frozenset(seen)

def _ordered_subset(machine,states):
    if states is None: return machine.states
    wanted=set(states)
    if not wanted.issubset(machine.states): raise KeyError("unknown state")
    ordered=tuple(s for s in machine.states if s in wanted)
    for s in ordered:
        for a in machine.actions:
            if machine.step(s,a) not in wanted:
                raise ValueError("subset must be transition-closed")
    return ordered

def canonical_partition(blocks,machine):
    rank={s:i for i,s in enumerate(machine.states)}
    out=[tuple(sorted(b,key=rank.__getitem__)) for b in blocks]
    out.sort(key=lambda b: tuple(rank[s] for s in b))
    return tuple(out)

def partition_refinement(machine:MooreMachine,states=None):
    S=_ordered_subset(machine,states)
    groups={}; order=[]
    for s in S:
        o=machine.output[s]
        if o not in groups: groups[o]=[]; order.append(o)
        groups[o].append(s)
    blocks=[tuple(groups[o]) for o in order]
    while True:
        block_of={s:i for i,b in enumerate(blocks) for s in b}
        new=[]; changed=False
        for block in blocks:
            g={}; sig_order=[]
            for s in block:
                sig=tuple(block_of[machine.step(s,a)] for a in machine.actions)
                if sig not in g: g[sig]=[]; sig_order.append(sig)
                g[sig].append(s)
            if len(g)>1: changed=True
            new.extend(tuple(g[sig]) for sig in sig_order)
        blocks=new
        if not changed: return canonical_partition(blocks,machine)

def distinguishing_word(machine:MooreMachine,s,t)->Optional[Word]:
    if s not in machine.states or t not in machine.states: raise KeyError("state outside machine")
    if machine.output[s]!=machine.output[t]: return ()
    index={x:i for i,x in enumerate(machine.states)}
    def key(x,y): return (x,y) if index[x]<=index[y] else (y,x)
    start=key(s,t); q=deque([(start,())]); seen={start}
    while q:
        (x,y),word=q.popleft()
        for a in machine.actions:
            nx,ny=machine.step(x,a),machine.step(y,a)
            nw=word+(a,)
            if machine.output[nx]!=machine.output[ny]: return nw
            p=key(nx,ny)
            if p not in seen: seen.add(p); q.append((p,nw))
    return None

def equivalent_by_pair_bfs(machine,s,t): return distinguishing_word(machine,s,t) is None
def distinguishing_depth(machine,s,t):
    w=distinguishing_word(machine,s,t); return None if w is None else len(w)

def assert_oracles_agree(machine,states=None):
    S=_ordered_subset(machine,states)
    p=partition_refinement(machine,S)
    block={s:i for i,b in enumerate(p) for s in b}
    for i,s in enumerate(S):
        for t in S[i:]:
            if (block[s]==block[t]) != equivalent_by_pair_bfs(machine,s,t):
                raise AssertionError(f"oracle disagreement: {s!r},{t!r}")

class Relation(str,Enum):
    DIFFERENT="DIFFERENT"; EQUIVALENT="EQUIVALENT"; UNKNOWN="UNKNOWN"

def relation_under_partial_transition_knowledge(machine,observed_edges,s,t):
    observed=set(observed_edges)
    if machine.output[s]!=machine.output[t]: return Relation.DIFFERENT
    index={x:i for i,x in enumerate(machine.states)}
    def key(x,y): return (x,y) if index[x]<=index[y] else (y,x)
    q=deque([key(s,t)]); seen=set(); missing=False
    while q:
        x,y=q.popleft()
        if (x,y) in seen: continue
        seen.add((x,y))
        if machine.output[x]!=machine.output[y]: return Relation.DIFFERENT
        for a in machine.actions:
            if (x,a) not in observed or (y,a) not in observed:
                missing=True; continue
            nx,ny=machine.step(x,a),machine.step(y,a)
            if machine.output[nx]!=machine.output[ny]: return Relation.DIFFERENT
            p=key(nx,ny)
            if p not in seen: q.append(p)
    return Relation.UNKNOWN if missing else Relation.EQUIVALENT

def permute_actions(machine,permutation):
    if set(permutation)!=set(machine.actions) or set(permutation.values())!=set(machine.actions):
        raise ValueError("action permutation must be bijective")
    inv={new:old for old,new in permutation.items()}
    T={(s,a):machine.step(s,inv[a]) for s in machine.states for a in machine.actions}
    return MooreMachine(machine.states,machine.actions,dict(machine.output),T)

def relabel_states(machine,relabel):
    if set(relabel)!=set(machine.states) or set(relabel.values())!=set(machine.states):
        raise ValueError("state relabel must be bijective")
    S=tuple(relabel[s] for s in machine.states)
    O={relabel[s]:machine.output[s] for s in machine.states}
    T={(relabel[s],a):relabel[machine.step(s,a)] for s in machine.states for a in machine.actions}
    return MooreMachine(S,machine.actions,O,T)
