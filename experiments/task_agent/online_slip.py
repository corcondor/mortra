"""The online agent in a slipping world: model errors become cost instead of failure.

The exact slip evaluation froze the learned model: a state it had never seen was
a failure, and an action whose single training sample had slipped sent the agent
round a loop until the horizon. `OnlineTaskAgent` does neither -- it adds unseen
states, records every executed transition, and replans -- so here it runs in the
slipping world itself, starting from the same budget-8192 model the exact
evaluation used.

Two pieces of machinery, neither of which changes a decision:

`VersionedLearner` is the canonical StructuralLearner with a counter that moves
whenever the modal graph does (a new tried pair, or a modal successor that
changes because counts overtook). In a slipping world the number of tried pairs
no longer fingerprints the modal graph, so the caching used in deterministic
worlds would be wrong here; the counter is what makes reuse sound.

`FieldPlanner` is ProductPlanner (sparse) with a choice of field -- the
delivered linear one, or q^d -- that reuses its last model while the learner's
version is unchanged and the current product state lies inside it. A field on a
forward-closed subgraph equals the field restricted to it, so the decisions are
those of a fresh build, up to floating-point ties for the linear field and
exactly for q^d.
"""
from __future__ import annotations

import copy
from collections import deque

import numpy as np
from scipy.sparse import csr_matrix, identity
from scipy.sparse.linalg import splu

from experiments.game_frontier_v1.frozen import StructuralLearner
from experiments.task_agent.core import (ProductModel, ProductPlanner, _learner_id_to_state,
                                         _learner_state_to_id, modal_successors, support_reachable)
from experiments.task_agent.noisy import SlipEngine


class VersionedLearner(StructuralLearner):
    """The canonical learner, counting changes to its modal graph."""

    def __init__(self, num_actions):
        super().__init__(num_actions)
        self.version = 0

    @classmethod
    def from_learner(cls, other):
        learner = cls(other.num_actions)
        for name in ("state_to_id", "id_to_state", "node_visits", "action_visits", "counts",
                     "dest_map"):
            setattr(learner, name, copy.deepcopy(getattr(other, name)))
        return learner

    def _modal(self, key):
        d = self.counts.get(key)
        return None if not d else max(d.items(), key=lambda kv: (kv[1], -kv[0]))[0]

    def record_transition(self, u, a, v):
        before = self._modal((u, a))
        super().record_transition(u, a, v)
        if self._modal((u, a)) != before:
            self.version += 1


class FieldPlanner(ProductPlanner):
    """ProductPlanner with a choice of field and sound reuse between model changes."""

    def __init__(self, kind="linear", q=0.90):
        super().__init__(q)
        if kind not in ("linear", "shortest"):
            raise ValueError(kind)
        self.kind = kind
        self._cached = None
        self.builds = 0
        self.reuses = 0

    def build(self, learner, task, start_state, memory=None):
        s2i = _learner_state_to_id(learner)
        version = getattr(learner, "version", None)
        if (self._cached is not None and version is not None and start_state in s2i
                and self._cached[0] == version and self._cached[2] is task):
            m = task.advance(task.initial_memory if memory is None else memory, start_state)
            if (s2i[start_state], m) in self._cached[1].index:
                self.reuses += 1
                return self._cached[1]
        model = self._fresh(learner, task, start_state, memory)
        self.builds += 1
        if version is not None:
            # the task is held, not just its id(), so a later task cannot inherit this model
            self._cached = (version, model, task)
        return model

    def _fresh(self, learner, task, start_state, memory):
        s2i = _learner_state_to_id(learner)
        i2s = _learner_id_to_state(learner)
        if start_state not in s2i:
            return ProductModel([], {}, [], np.zeros((0, 0)), [], set(), None)
        m0 = task.advance(task.initial_memory if memory is None else memory, start_state)
        z0 = (s2i[start_state], m0)
        index, states, actions = {z0: 0}, [z0], []
        queue = deque([z0])
        while queue:
            u, m = queue.popleft()
            row = {}
            for a, v in modal_successors(learner, u).items():
                z2 = (v, task.advance(m, i2s[v]))
                if z2 not in index:
                    index[z2] = len(states)
                    states.append(z2)
                    queue.append(z2)
                row[a] = index[z2]
            actions.append(row)
        n = len(states)
        accepting = [i for i, (_, m) in enumerate(states) if task.accepting(m)]
        adjacency = [list(row.values()) for row in actions]
        reachable = support_reachable(adjacency, accepting)
        psi = None
        if accepting:
            if self.kind == "linear":
                r, c, w = [], [], []
                for i, row in enumerate(actions):
                    for j in row.values():
                        r.append(i)
                        c.append(j)
                        w.append(1.0/len(row))
                K = csr_matrix((w, (r, c)), shape=(n, n))
                g = np.zeros(n)
                g[accepting] = 1.0
                psi = splu((identity(n, format="csc")-self.q*K).tocsc()).solve(g)
            else:
                reverse = [[] for _ in range(n)]
                for i, row in enumerate(actions):
                    for j in row.values():
                        reverse[j].append(i)
                depth = {i: 0 for i in accepting}
                queue = deque(accepting)
                while queue:
                    v = queue.popleft()
                    for u in reverse[v]:
                        if u not in depth:
                            depth[u] = depth[v]+1
                            queue.append(u)
                psi = np.zeros(n)
                for i, d in depth.items():
                    psi[i] = self.q**d
        return ProductModel(states, index, actions, None, accepting, reachable, psi)


class SlipEnv:
    """reset/step around the slipping world, one execution seed per episode."""

    def __init__(self, genome, slip, seed, noise="uniform"):
        self.engine = SlipEngine(genome, slip, seed, noise)
        self.num_actions = self.engine.num_actions
        self.state = self.engine.initial

    def reset(self, state=None):
        if state is not None:
            self.state = tuple(state)
        return self.state

    def step(self, action):
        self.state = self.engine.step(self.state, int(action))
        return self.state
