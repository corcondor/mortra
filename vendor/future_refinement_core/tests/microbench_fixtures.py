from __future__ import annotations
from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from exact_moore_oracle import MooreMachine

@dataclass(frozen=True)
class Fixture:
    name:str
    machine:MooreMachine
    expected_partition:Tuple[Tuple[int,...],...]
    expected_depths:Dict[Tuple[int,int],Optional[int]]
    initial_states:Tuple[int,...]=(0,)

def _total(states,actions,overrides):
    return {(s,a):overrides.get((s,a),s) for s in states for a in actions}

def equivalent_states():
    S=(0,1,2); A=("a","b")
    O={0:"x",1:"x",2:"y"}
    T=_total(S,A,{(0,"a"):0,(1,"a"):1,(0,"b"):2,(1,"b"):2,(2,"a"):2,(2,"b"):2})
    return Fixture("equivalent_states",MooreMachine(S,A,O,T),((0,1),(2,)),{(0,1):None,(0,2):0,(1,2):0})

def one_step_difference():
    S=(0,1,2,3); A=("a","b")
    O={0:"x",1:"x",2:"y",3:"z"}
    T=_total(S,A,{(0,"a"):2,(1,"a"):3,(0,"b"):0,(1,"b"):1,(2,"a"):2,(2,"b"):2,(3,"a"):3,(3,"b"):3})
    return Fixture("one_step_difference",MooreMachine(S,A,O,T),((0,),(1,),(2,),(3,)),{(0,1):1,(2,3):0})

def two_step_difference():
    S=(0,1,2,3,4,5); A=("a","b")
    O={0:"x",1:"x",2:"m",3:"m",4:"y",5:"z"}
    T=_total(S,A,{
        (0,"a"):2,(1,"a"):3,(2,"a"):4,(3,"a"):5,(4,"a"):4,(5,"a"):5,
        (0,"b"):0,(1,"b"):1,(2,"b"):2,(3,"b"):3,(4,"b"):4,(5,"b"):5})
    return Fixture("two_step_difference",MooreMachine(S,A,O,T),tuple((s,) for s in S),{(0,1):2,(2,3):1,(4,5):0})

def three_step_difference():
    S=tuple(range(8)); A=("a","b")
    O={0:"x",1:"x",2:"m",3:"m",4:"n",5:"n",6:"y",7:"z"}
    T=_total(S,A,{
        (0,"a"):2,(1,"a"):3,(2,"a"):4,(3,"a"):5,(4,"a"):6,(5,"a"):7,(6,"a"):6,(7,"a"):7,
        **{(s,"b"):s for s in S}})
    return Fixture("three_step_difference",MooreMachine(S,A,O,T),tuple((s,) for s in S),
                   {(0,1):3,(2,3):2,(4,5):1,(6,7):0})

def cycle_equivalence():
    S=(0,1,2); A=("tick","exit")
    O={0:"x",1:"x",2:"goal"}
    T=_total(S,A,{(0,"tick"):1,(1,"tick"):0,(0,"exit"):2,(1,"exit"):2,(2,"tick"):2,(2,"exit"):2})
    return Fixture("cycle_equivalence",MooreMachine(S,A,O,T),((0,1),(2,)),{(0,1):None})

def historical_cue():
    S=(0,1,2,3,4,5,6,7); A=("advance","choose")
    O={0:"cue0",1:"cue1",2:"corridor",3:"corridor",4:"junction",5:"junction",6:"good",7:"bad"}
    T=_total(S,A,{
        (0,"advance"):2,(1,"advance"):3,(2,"advance"):4,(3,"advance"):5,
        (4,"choose"):6,(5,"choose"):7,
        (6,"advance"):6,(6,"choose"):6,(7,"advance"):7,(7,"choose"):7})
    return Fixture("historical_cue",MooreMachine(S,A,O,T),tuple((s,) for s in S),
                   {(4,5):1,(2,3):2},initial_states=(0,1))

def delayed_bit_effect():
    S=tuple(range(8)); A=("tick","read")
    O={0:"same",1:"same",2:"same",3:"same",4:"same",5:"same",6:"zero",7:"one"}
    T=_total(S,A,{
        (0,"tick"):2,(1,"tick"):3,(2,"tick"):4,(3,"tick"):5,
        (4,"read"):6,(5,"read"):7,
        (0,"read"):0,(1,"read"):1,(2,"read"):2,(3,"read"):3,
        (4,"tick"):4,(5,"tick"):5,
        (6,"tick"):6,(7,"tick"):7,(6,"read"):6,(7,"read"):7})
    return Fixture("delayed_bit_effect",MooreMachine(S,A,O,T),tuple((s,) for s in S),
                   {(0,1):3,(2,3):2,(4,5):1})

def unreachable_state():
    S=(0,1,2); A=("a",)
    O={0:"start",1:"sink",2:"unreachable"}
    T={(0,"a"):1,(1,"a"):1,(2,"a"):2}
    return Fixture("unreachable_state",MooreMachine(S,A,O,T),((0,),(1,),(2,)),
                   {(0,1):0,(0,2):0,(1,2):0},initial_states=(0,))

ALL_FIXTURES=(equivalent_states,one_step_difference,two_step_difference,three_step_difference,
              cycle_equivalence,historical_cue,delayed_bit_effect,unreachable_state)
