"""Finite task memory composed with MORTRA's learned transition operator.

This module deliberately does not change MORTRA's StructuralLearner.  It consumes
the learner's learned state/action counts and builds a product process

    (world_state, task_memory)

on which the same scalar fixed-field equation is solved:

    psi = g + q K psi,  q = .90.

Semantic reachability is graph-theoretic.  There is no absolute psi cutoff.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from typing import Any, Dict, Hashable, Iterable, List, Mapping, Optional, Protocol, Sequence, Tuple

import numpy as np

Q_DEFAULT = 0.90


class Predicate(Protocol):
    def matches(self, state: Hashable) -> bool: ...


@dataclass(frozen=True)
class ExactState:
    value: Hashable

    def matches(self, state: Hashable) -> bool:
        return state == self.value


@dataclass(frozen=True)
class VarEquals:
    index: int
    value: int

    def matches(self, state: Hashable) -> bool:
        try:
            return state[self.index] == self.value
        except (TypeError, IndexError):
            return False


class FiniteTask(Protocol):
    @property
    def initial_memory(self) -> Hashable: ...
    def advance(self, memory: Hashable, world_state: Hashable) -> Hashable: ...
    def accepting(self, memory: Hashable) -> bool: ...
    def progress(self, memory: Hashable) -> float: ...


@dataclass(frozen=True)
class SequenceTask:
    goals: Tuple[Predicate, ...]

    def __init__(self, goals: Sequence[Predicate]):
        if not goals:
            raise ValueError("SequenceTask requires at least one goal")
        object.__setattr__(self, "goals", tuple(goals))

    @property
    def initial_memory(self) -> int:
        return 0

    def advance(self, memory: int, world_state: Hashable) -> int:
        m = int(memory)
        # A state may satisfy several consecutive predicates.
        while m < len(self.goals) and self.goals[m].matches(world_state):
            m += 1
        return m

    def accepting(self, memory: int) -> bool:
        return int(memory) >= len(self.goals)

    def progress(self, memory: int) -> float:
        return min(1.0, int(memory) / len(self.goals))


@dataclass(frozen=True)
class AllTask:
    goals: Tuple[Predicate, ...]

    def __init__(self, goals: Sequence[Predicate]):
        if not goals:
            raise ValueError("AllTask requires at least one goal")
        if len(goals) > 20:
            raise ValueError("AllTask bitmask intentionally capped at 20 predicates")
        object.__setattr__(self, "goals", tuple(goals))

    @property
    def initial_memory(self) -> int:
        return 0

    @property
    def accept_mask(self) -> int:
        return (1 << len(self.goals)) - 1

    def advance(self, memory: int, world_state: Hashable) -> int:
        m = int(memory)
        for i, predicate in enumerate(self.goals):
            if predicate.matches(world_state):
                m |= 1 << i
        return m

    def accepting(self, memory: int) -> bool:
        return int(memory) == self.accept_mask

    def progress(self, memory: int) -> float:
        return int(memory).bit_count() / len(self.goals)


@dataclass(frozen=True)
class BranchTask:
    """First trigger reached commits the future obligation.

    Memory:
      0 = no trigger yet
      1 = A fired; require target_a
      2 = B fired; require target_b
      3 = accepting
    """
    trigger_a: Predicate
    target_a: Predicate
    trigger_b: Predicate
    target_b: Predicate

    @property
    def initial_memory(self) -> int:
        return 0

    def advance(self, memory: int, world_state: Hashable) -> int:
        m = int(memory)
        if m == 0:
            if self.trigger_a.matches(world_state):
                m = 1
            elif self.trigger_b.matches(world_state):
                m = 2
        if m == 1 and self.target_a.matches(world_state):
            return 3
        if m == 2 and self.target_b.matches(world_state):
            return 3
        return m

    def accepting(self, memory: int) -> bool:
        return int(memory) == 3

    def progress(self, memory: int) -> float:
        return (0.0, 0.5, 0.5, 1.0)[int(memory)]


def _learner_state_to_id(learner) -> Mapping[Hashable, int]:
    if hasattr(learner, "state_to_id"):
        return learner.state_to_id
    if hasattr(learner, "s2i"):
        return learner.s2i
    raise TypeError("learner has no state_to_id/s2i mapping")


def _learner_id_to_state(learner) -> Sequence[Hashable]:
    if hasattr(learner, "id_to_state"):
        return learner.id_to_state
    if hasattr(learner, "i2s"):
        return learner.i2s
    raise TypeError("learner has no id_to_state/i2s sequence")


def _learner_num_actions(learner) -> int:
    if hasattr(learner, "num_actions"):
        return int(learner.num_actions)
    if hasattr(learner, "A"):
        return int(learner.A)
    raise TypeError("learner has no num_actions/A")


def modal_successors(learner, u: int) -> Dict[int, int]:
    """Return known modal successor per tried action."""
    out: Dict[int, int] = {}
    counts = learner.counts
    for a in range(_learner_num_actions(learner)):
        d = counts.get((u, a))
        if d:
            out[a] = max(d.items(), key=lambda kv: (kv[1], -kv[0]))[0]
    return out


def support_reachable(adjacency: Sequence[Iterable[int]], goals: Iterable[int]) -> set[int]:
    """States that can reach any goal through positive-support directed edges."""
    n = len(adjacency)
    reverse: List[List[int]] = [[] for _ in range(n)]
    for u, row in enumerate(adjacency):
        for v in row:
            if 0 <= v < n:
                reverse[v].append(u)
    seen = set(int(g) for g in goals)
    q = deque(seen)
    while q:
        v = q.popleft()
        for u in reverse[v]:
            if u not in seen:
                seen.add(u)
                q.append(u)
    return seen


def solve_field_dense(K: np.ndarray, g: np.ndarray, q: float = Q_DEFAULT) -> np.ndarray:
    """Solve exactly enough for the small/medium product graphs used by experiments."""
    n = K.shape[0]
    if K.shape != (n, n) or g.shape != (n,):
        raise ValueError("shape mismatch")
    return np.linalg.solve(np.eye(n, dtype=float) - q * K, g)


@dataclass
class ProductModel:
    states: List[Tuple[int, Hashable]]
    index: Dict[Tuple[int, Hashable], int]
    actions: List[Dict[int, int]]
    K: np.ndarray
    accepting: List[int]
    reachable_to_accept: set[int]
    psi: Optional[np.ndarray]


class ProductPlanner:
    def __init__(self, q: float = Q_DEFAULT):
        self.q = float(q)

    def build(self, learner, task: FiniteTask, start_state: Hashable, memory: Optional[Hashable] = None) -> ProductModel:
        s2i = _learner_state_to_id(learner)
        i2s = _learner_id_to_state(learner)
        if start_state not in s2i:
            return ProductModel([], {}, [], np.zeros((0, 0)), [], set(), None)

        m0 = task.initial_memory if memory is None else memory
        m0 = task.advance(m0, start_state)
        z0 = (s2i[start_state], m0)

        index = {z0: 0}
        states = [z0]
        actions: List[Dict[int, int]] = []
        queue = deque([z0])

        while queue:
            u, m = queue.popleft()
            row: Dict[int, int] = {}
            for a, v in modal_successors(learner, u).items():
                s_next = i2s[v]
                m_next = task.advance(m, s_next)
                z_next = (v, m_next)
                if z_next not in index:
                    index[z_next] = len(states)
                    states.append(z_next)
                    queue.append(z_next)
                row[a] = index[z_next]
            actions.append(row)

        n = len(states)
        K = np.zeros((n, n), dtype=float)
        for i, row in enumerate(actions):
            if not row:
                continue
            # Preserve MORTRA's K_support convention: equal weight per tried action.
            w = 1.0 / len(row)
            for j in row.values():
                K[i, j] += w

        accepting = [i for i, (_, m) in enumerate(states) if task.accepting(m)]
        adjacency = [list(row.values()) for row in actions]
        reachable = support_reachable(adjacency, accepting)
        psi = None
        if accepting:
            g = np.zeros(n, dtype=float)
            g[accepting] = 1.0
            psi = solve_field_dense(K, g, self.q)

        return ProductModel(states, index, actions, K, accepting, reachable, psi)

    def choose_action(
        self,
        learner,
        task: FiniteTask,
        world_state: Hashable,
        memory: Hashable,
        model: Optional[ProductModel] = None,
    ) -> Optional[int]:
        model = model or self.build(learner, task, world_state, memory)
        if not model.states or model.psi is None:
            return None

        s2i = _learner_state_to_id(learner)
        if world_state not in s2i:
            return None
        memory = task.advance(memory, world_state)
        z = (s2i[world_state], memory)
        i = model.index.get(z)
        if i is None or i not in model.reachable_to_accept:
            return None

        row = model.actions[i]
        candidates = [(float(model.psi[j]), -a, a) for a, j in row.items() if j in model.reachable_to_accept]
        return max(candidates)[2] if candidates else None

    def has_accepting_path(self, learner, task: FiniteTask, world_state: Hashable, memory: Hashable) -> bool:
        model = self.build(learner, task, world_state, memory)
        if not model.states:
            return False
        z0 = (0 if not model.states else model.states[0])
        return bool(model.accepting and 0 in model.reachable_to_accept)
