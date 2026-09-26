"""The online Task Agent on tasks its model does not yet contain.

The checkpoint experiment asks whether a task can be executed on a model that
already holds a path for it. This one asks the harder question the online agent
exists for: start from a partial model -- the budget-512 snapshot, where 211 of
the 368 registered tasks have no accepting path yet -- and let the agent explore
until it can execute. The package under test is `experiments.task_agent` as
delivered; nothing in `core`, `exploration` or `online` is modified.

Two things are added, and both are about speed rather than behaviour.

`SparseProductPlanner` is `ProductPlanner` with the dense `np.linalg.solve`
replaced by a sparse LU. The product graph has a handful of edges per state, and
the dense solve allocates and factors an n-by-n matrix at every replan, which on
these worlds makes one online episode take minutes. The product construction,
the source, q, the reachability rule and the action choice are line for line the
same; `planners_agree` checks the two on real product graphs.

`WorldEnv` is the minimal `reset`/`step` wrapper the agent expects, around the
canonical Engine.
"""
from __future__ import annotations

import copy
import time
from collections import deque

import numpy as np
from scipy.sparse import csr_matrix, identity
from scipy.sparse.linalg import splu

from experiments.task_agent import (AllTask, BranchTask, CountUncertaintyPolicy, ExactState,
                                    FrontierFieldPolicy, FrozenStructuralPolicy, OnlineTaskAgent,
                                    ProductPlanner, SequenceTask, TaskConditionedPolicy, VarEquals)
from experiments.task_agent.core import (ProductModel, _learner_id_to_state, _learner_state_to_id,
                                         modal_successors, support_reachable)


# ---------------------------------------------------------------------------
# Tasks and the world, in the online package's terms
# ---------------------------------------------------------------------------

def predicate(spec):
    if spec["kind"] == "exact":
        return ExactState(tuple(spec["state"]))
    if spec["kind"] == "var_eq":
        return VarEquals(int(spec["var"]), int(spec["value"]))
    raise ValueError(spec["kind"])


def task_from_spec(spec):
    """The registered task specification as one of the online package's task classes."""
    if spec["op"] == "SEQ":
        return SequenceTask([predicate(p) for p in spec["goals"]])
    if spec["op"] == "ALL":
        return AllTask([predicate(p) for p in spec["goals"]])
    if spec["op"] == "BRANCH":
        return BranchTask(predicate(spec["A"]), predicate(spec["CA"]),
                          predicate(spec["B"]), predicate(spec["CB"]))
    raise ValueError(spec["op"])


class WorldEnv:
    """reset/step around the canonical, deterministic Engine."""

    def __init__(self, engine):
        self.engine = engine
        self.num_actions = engine.num_actions
        self.state = engine.initial

    def reset(self, state=None):
        if state is not None:
            self.state = tuple(state)
        return self.state

    def step(self, action):
        self.state = self.engine.step(self.state, int(action))
        return self.state


# ---------------------------------------------------------------------------
# The same planner, solved sparsely
# ---------------------------------------------------------------------------

class SparseProductPlanner(ProductPlanner):
    """`ProductPlanner.build` with a sparse LU in place of the dense solve. Nothing else."""

    def build(self, learner, task, start_state, memory=None):
        s2i = _learner_state_to_id(learner)
        i2s = _learner_id_to_state(learner)
        if start_state not in s2i:
            return ProductModel([], {}, [], np.zeros((0, 0)), [], set(), None)
        m0 = task.initial_memory if memory is None else memory
        m0 = task.advance(m0, start_state)
        z0 = (s2i[start_state], m0)
        index = {z0: 0}
        states = [z0]
        actions = []
        queue = deque([z0])
        while queue:
            u, m = queue.popleft()
            row = {}
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
        rows, cols, weights = [], [], []
        for i, row in enumerate(actions):
            if not row:
                continue
            w = 1.0/len(row)
            for j in row.values():
                rows.append(i)
                cols.append(j)
                weights.append(w)
        K = csr_matrix((weights, (rows, cols)), shape=(n, n), dtype=float)
        accepting = [i for i, (_, m) in enumerate(states) if task.accepting(m)]
        adjacency = [list(row.values()) for row in actions]
        reachable = support_reachable(adjacency, accepting)
        psi = None
        if accepting:
            g = np.zeros(n, dtype=float)
            g[accepting] = 1.0
            psi = splu((identity(n, format="csc")-self.q*K.tocsc())).solve(g)
        return ProductModel(states, index, actions, K, accepting, reachable, psi)


def planners_agree(learner, task, state, memory, *, tolerance=1e-10):
    """Dense and sparse build: same graph, same reachability, the same field to rounding."""
    dense = ProductPlanner().build(learner, task, state, memory)
    sparse = SparseProductPlanner().build(learner, task, state, memory)
    same_graph = dense.states == sparse.states and dense.actions == sparse.actions
    same_reach = dense.reachable_to_accept == sparse.reachable_to_accept
    if dense.psi is None or sparse.psi is None:
        same_field = dense.psi is None and sparse.psi is None
        gap = 0.0
    else:
        gap = float(np.max(np.abs(dense.psi-sparse.psi))) if len(dense.psi) else 0.0
        same_field = gap < tolerance
    same_choice = (ProductPlanner().choose_action(learner, task, state, memory, dense)
                   == SparseProductPlanner().choose_action(learner, task, state, memory, sparse))
    return {"same_graph": same_graph, "same_reachability": same_reach,
            "same_field": same_field, "largest_field_gap": gap, "same_action": same_choice,
            "product_states": len(dense.states)}


class CachingSparsePlanner(SparseProductPlanner):
    """Remember the last build: the agent and its policy ask for the same one each step.

    In a deterministic world the modal graph changes exactly when a new
    (state, action) pair is tried, so the number of tried pairs is a complete
    fingerprint of it; the build is keyed on that, the task, the state and the
    memory, and nothing is reused across a change in any of them.
    """

    def __init__(self, q=0.90):
        super().__init__(q)
        self._key = None
        self._model = None
        self.hits = 0
        self.builds = 0

    def build(self, learner, task, start_state, memory=None):
        key = (len(learner.counts), len(_learner_id_to_state(learner)), id(task), start_state,
               memory)
        if key == self._key:
            self.hits += 1
            return self._model
        self.builds += 1
        self._model = super().build(learner, task, start_state, memory)
        self._key = key
        return self._model


def _one_bfs(learner, start_u):
    """Every state's BFS depth and first action from start_u, in the package's discovery order.

    `_shortest_known_path_to_any` runs a breadth-first search that stops at its
    target. A search that does not stop discovers every node in the same order
    and gives it the same predecessor, so the path it implies to each target is
    the path the early-stopping search would have returned -- which is what makes
    one search per step equivalent to one search per frontier state.
    """
    depth = {start_u: 0}
    first = {}
    queue = deque([start_u])
    while queue:
        u = queue.popleft()
        for a, v in modal_successors(learner, u).items():
            if v in depth:
                continue
            depth[v] = depth[u]+1
            first[v] = a if u == start_u else first[u]
            queue.append(v)
    return depth, first


class FastTaskConditionedPolicy(TaskConditionedPolicy):
    """TaskConditionedPolicy.choose with one search per step instead of one per frontier state."""

    def choose(self, learner, world_state, task, memory):
        from math import sqrt

        from experiments.task_agent.core import _learner_num_actions
        from experiments.task_agent.exploration import ExplorationDecision

        s2i = _learner_state_to_id(learner)
        u = s2i[world_state]
        A = _learner_num_actions(learner)
        relevance = self._frontier_relevance(learner, task, memory, world_state)
        depth, first = _one_bfs(learner, u)
        best_target = best_tuple = best_action = None
        for target in relevance:
            if target not in depth:
                continue
            length = depth[target]
            key = (relevance[target], -length, -target)
            if best_tuple is None or key > best_tuple:
                best_tuple, best_target = key, target
                best_action = first.get(target)          # None when the target is u itself
        if best_target is not None and best_action is not None:
            return ExplorationDecision(
                action=best_action, policy=self.name,
                task_relevance={best_action: relevance[best_target]},
                score={best_action: self.beta*relevance[best_target]},
                target_frontier=best_target,
                reason="navigate through known graph toward task-relevant frontier")
        unknown = {a: 1.0/sqrt(1.0+learner.action_visits.get((u, a), 0)) for a in range(A)}
        current_rel = relevance.get(u, float(task.progress(task.advance(memory, world_state))))
        task_rel = {a: current_rel for a in range(A)}
        score = {a: self.alpha*unknown[a]+self.beta*task_rel[a] for a in range(A)}
        a = max(range(A), key=lambda x: (score[x], -x))
        return ExplorationDecision(
            action=a, policy=self.name, unknownness=unknown, task_relevance=task_rel,
            score=score, target_frontier=u if u in relevance else None,
            reason="probe locally; unknown successor is never assumed")


# ---------------------------------------------------------------------------
# Episodes
# ---------------------------------------------------------------------------

POLICIES = ("structural", "frontier", "uncertainty", "task_conditioned")


def make_policy(name, planner):
    if name == "structural":
        return FrozenStructuralPolicy()
    if name == "frontier":
        return FrontierFieldPolicy()
    if name == "uncertainty":
        return CountUncertaintyPolicy()
    if name == "task_conditioned":
        return TaskConditionedPolicy(planner)
    raise ValueError(name)


def run_episode(snapshot_core, engine, spec, start, policy_name, *, max_steps=4096):
    """One task, one exploration policy, a private copy of the starting model."""
    learner = copy.deepcopy(snapshot_core)
    planner = SparseProductPlanner(q=0.90)
    agent = OnlineTaskAgent(learner, make_policy(policy_name, planner), planner=planner,
                            max_task_steps=max_steps, max_exploration_steps=max_steps)
    task = task_from_spec(spec)
    started = time.perf_counter()
    result = agent.run_task(WorldEnv(engine), task, tuple(start))
    return {"success": bool(result.success), "task_steps": int(result.task_steps),
            "exploration_steps": int(result.exploration_steps), "replans": int(result.replans),
            "failure_reason": result.failure_reason,
            "states_known_at_end": len(learner.id_to_state),
            "seconds": round(time.perf_counter()-started, 3)}
