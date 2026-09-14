"""Stateful domains on the existing typed proof-program planner.

Adapters own meanings and certificates; the planner owns composition, fair
selection, depth/application budgets, dependencies and goal termination.
"""
from __future__ import annotations

from typing import Protocol, Any

from math_os_prototype.runtime_typed_planner import (
    RuntimePrimitive, initial_fact, synthesize_typed_plan,
)


class ActionDomain(Protocol):
    sort: str
    families: tuple[str, ...]

    def initial(self) -> Any: ...
    def alternatives(self, family, state): ...
    def key(self, state) -> str: ...
    def is_goal(self, state) -> bool: ...


def search_action_domain(domain: ActionDomain, *, max_depth, max_states, progress=None):
    primitives = tuple(RuntimePrimitive(
        family, (domain.sort,), domain.sort, lambda args: None,
        alternatives=lambda args, family=family: domain.alternatives(family, args[0].value),
    ) for family in domain.families)
    return synthesize_typed_plan(
        [initial_fact(domain.sort, domain.initial())], primitives, [domain.sort],
        goal_predicates={domain.sort: lambda fact: domain.is_goal(fact.value)},
        value_key=lambda sort, state: domain.key(state),
        max_depth=max_depth, max_states=max_states, fair=True, progress=progress,
    )
