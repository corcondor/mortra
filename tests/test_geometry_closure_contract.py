"""Finite reference models test planner contracts, not mathematical discovery."""
import pytest

from math_os_prototype.runtime_typed_planner import PrimitiveResult, RuntimeSearchProgress
from math_os_prototype.theory_action_domain import search_action_domain


class ResidueActions:
    sort = "ResidueState"
    families = ("successor", "double")
    fair_state_streams = True

    def __init__(self, modulus, goal=None):
        self.modulus, self.goal = modulus, goal

    def initial(self):
        return 0

    def key(self, state):
        return str(state)

    def is_goal(self, state):
        return state == self.goal

    def alternatives(self, family, state):
        result = (state + 1 if family == "successor" else 2 * state) % self.modulus
        yield lambda: PrimitiveResult(result, {"input": state, "output": result})


@pytest.mark.parametrize("modulus", [5, 7, 11])
def test_fair_planner_matches_independent_least_fixed_point(modulus):
    reached = {0}
    while True:
        later = reached | {(x + 1) % modulus for x in reached} | {2 * x % modulus for x in reached}
        if later == reached:
            break
        reached = later
    progress = RuntimeSearchProgress()
    plan = search_action_domain(ResidueActions(modulus), max_depth=modulus,
                               max_states=1000, progress=progress)
    assert {f.value for f in plan.facts} == reached
    assert progress.pending_streams == 0
    assert progress.applications_completed == 2 * len(reached)
    assert not plan.complete  # Fixed point without a goal is not a solved task.


def test_forward_backward_meeting_has_an_executable_witness():
    size, goal = 7, 5
    backward = {goal}
    while True:
        later = backward | {x for x in range(size)
                            if (x + 1) % size in backward or 2 * x % size in backward}
        if later == backward:
            break
        backward = later
    assert 0 in backward
    plan = search_action_domain(ResidueActions(size, goal), max_depth=size, max_states=1000)
    value = 0
    for step in plan.proof_program:
        assert step["input"] == value
        value = (value + 1 if step["rule"] == "successor" else 2 * value) % size
        assert value == step["output"]
    assert plan.complete and value == goal


def test_budget_stop_does_not_establish_fixed_point_or_impossibility():
    plan = search_action_domain(ResidueActions(11, 9), max_depth=11, max_states=2)
    reached = {f.value for f in plan.facts}
    assert not plan.complete
    assert reached != reached | {(x + 1) % 11 for x in reached}
