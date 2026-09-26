"""Exploration policies for online Task-Agent learning.

Policies only inspect the learned model.  None receives the oracle graph or an
unknown action's successor.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field
from math import sqrt
from typing import Dict, Hashable, List, Optional, Tuple

from .core import (
    ProductPlanner,
    _learner_id_to_state,
    _learner_num_actions,
    _learner_state_to_id,
    modal_successors,
)


@dataclass
class ExplorationDecision:
    action: int
    policy: str
    unknownness: Dict[int, float] = field(default_factory=dict)
    task_relevance: Dict[int, float] = field(default_factory=dict)
    score: Dict[int, float] = field(default_factory=dict)
    target_frontier: Optional[int] = None
    reason: str = ""


class FrozenStructuralPolicy:
    name = "structural"

    def choose(self, learner, world_state, task, memory) -> ExplorationDecision:
        s2i = _learner_state_to_id(learner)
        u = s2i[world_state]
        # Use canonical MORTRA action selector. It owns node_visits bookkeeping.
        if hasattr(learner, "select_action"):
            a = int(learner.select_action(u))
        else:
            a = int(learner.select(u))
        return ExplorationDecision(action=a, policy=self.name, reason="canonical StructuralLearner")


class CountUncertaintyPolicy:
    name = "uncertainty"

    def choose(self, learner, world_state, task, memory) -> ExplorationDecision:
        s2i = _learner_state_to_id(learner)
        u = s2i[world_state]
        A = _learner_num_actions(learner)
        unknown = {
            a: 1.0 / sqrt(1.0 + learner.action_visits.get((u, a), 0))
            for a in range(A)
        }
        a = max(range(A), key=lambda x: (unknown[x], -x))
        return ExplorationDecision(
            action=a, policy=self.name,
            unknownness=unknown, score=dict(unknown),
            reason="maximum count-based uncertainty at current state",
        )


def _shortest_known_path_to_any(learner, start_u: int, targets: set[int]) -> Optional[List[int]]:
    if start_u in targets:
        return []
    q = deque([start_u])
    prev = {start_u: None}
    prev_action = {}
    while q:
        u = q.popleft()
        for a, v in modal_successors(learner, u).items():
            if v in prev:
                continue
            prev[v] = u
            prev_action[v] = a
            if v in targets:
                actions = []
                x = v
                while prev[x] is not None:
                    actions.append(prev_action[x])
                    x = prev[x]
                actions.reverse()
                return actions
            q.append(v)
    return None


def _frontier_states(learner, low_count_threshold: int = 1) -> set[int]:
    A = _learner_num_actions(learner)
    n = len(_learner_id_to_state(learner))
    result = set()
    for u in range(n):
        if any(learner.action_visits.get((u, a), 0) <= low_count_threshold for a in range(A)):
            result.add(u)
    return result


class FrontierFieldPolicy:
    """Navigate over known transitions to an underexplored state, then probe there."""
    name = "frontier"

    def __init__(self, low_count_threshold: int = 1):
        self.low_count_threshold = int(low_count_threshold)
        self._uncertainty = CountUncertaintyPolicy()

    def choose(self, learner, world_state, task, memory) -> ExplorationDecision:
        s2i = _learner_state_to_id(learner)
        u = s2i[world_state]
        frontier = _frontier_states(learner, self.low_count_threshold)

        if u in frontier:
            d = self._uncertainty.choose(learner, world_state, task, memory)
            d.policy = self.name
            d.target_frontier = u
            d.reason = "probe underexplored action at current frontier"
            return d

        path = _shortest_known_path_to_any(learner, u, frontier)
        if path:
            return ExplorationDecision(
                action=path[0], policy=self.name,
                target_frontier=None,
                reason="follow known shortest path toward an underexplored frontier",
            )
        d = self._uncertainty.choose(learner, world_state, task, memory)
        d.policy = self.name
        d.reason = "no reachable known frontier; local uncertainty fallback"
        return d


class TaskConditionedPolicy:
    """Task-directed frontier exploration without oracle successor leakage.

    Relevance is assigned to *known frontier states*, not to unknown successors.
    A frontier state is preferred when its product-state memory has more task
    progress and/or when it has high value in the currently known product field.

    When the current state itself is the selected frontier, the actual probe
    action is chosen only from count-based unknownness; the policy never assumes
    where an untried action will lead.
    """
    name = "task_conditioned"

    def __init__(
        self,
        planner: Optional[ProductPlanner] = None,
        *,
        alpha_unknownness: float = 1.0,
        beta_task: float = 1.0,
        low_count_threshold: int = 1,
    ):
        self.planner = planner or ProductPlanner()
        self.alpha = float(alpha_unknownness)
        self.beta = float(beta_task)
        self.low_count_threshold = int(low_count_threshold)

    def _frontier_relevance(self, learner, task, memory, world_state) -> Dict[int, float]:
        i2s = _learner_id_to_state(learner)
        frontier = _frontier_states(learner, self.low_count_threshold)
        relevance: Dict[int, float] = {}

        # Build what the current learned model knows from the current task state.
        model = self.planner.build(learner, task, world_state, memory)

        # product field may not have an accepting state yet; task progress is always available.
        max_psi = float(model.psi.max()) if model.psi is not None and len(model.psi) else 0.0

        for u in frontier:
            s = i2s[u]
            m = task.advance(memory, s)
            progress = float(task.progress(m))
            field_term = 0.0
            if model.psi is not None and max_psi > 0.0:
                z = (u, m)
                j = model.index.get(z)
                if j is not None:
                    field_term = float(model.psi[j] / max_psi)
            relevance[u] = 0.5 * progress + 0.5 * field_term
        return relevance

    def choose(self, learner, world_state, task, memory) -> ExplorationDecision:
        s2i = _learner_state_to_id(learner)
        u = s2i[world_state]
        A = _learner_num_actions(learner)
        relevance = self._frontier_relevance(learner, task, memory, world_state)
        frontier = set(relevance)

        # Select a frontier target by task relevance first, then path length.
        best_target = None
        best_path = None
        best_tuple = None
        for target in frontier:
            path = _shortest_known_path_to_any(learner, u, {target})
            if path is None:
                continue
            key = (relevance[target], -len(path), -target)
            if best_tuple is None or key > best_tuple:
                best_tuple = key
                best_target = target
                best_path = path

        if best_target is not None and best_path:
            a = best_path[0]
            return ExplorationDecision(
                action=a,
                policy=self.name,
                task_relevance={a: relevance[best_target]},
                score={a: self.beta * relevance[best_target]},
                target_frontier=best_target,
                reason="navigate through known graph toward task-relevant frontier",
            )

        # At frontier (or no navigable frontier): probe unknown action locally.
        unknown = {
            a: 1.0 / sqrt(1.0 + learner.action_visits.get((u, a), 0))
            for a in range(A)
        }
        current_rel = relevance.get(u, float(task.progress(task.advance(memory, world_state))))
        task_rel = {a: current_rel for a in range(A)}
        score = {a: self.alpha * unknown[a] + self.beta * task_rel[a] for a in range(A)}
        a = max(range(A), key=lambda x: (score[x], -x))
        return ExplorationDecision(
            action=a,
            policy=self.name,
            unknownness=unknown,
            task_relevance=task_rel,
            score=score,
            target_frontier=u if u in frontier else None,
            reason="probe locally; unknown successor is never assumed",
        )
