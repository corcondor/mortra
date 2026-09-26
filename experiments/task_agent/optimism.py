"""Exploration a field can actually steer: optimism about untried actions.

Inside `OnlineTaskAgent` the delivered TaskConditionedPolicy is consulted only
when the product graph has no accepting state, which is exactly when its field is
`None`; its field term never fired. The remedy is the classical one (R-max,
optimism in the face of uncertainty): give the field something to be about when
nothing known reaches acceptance. Every untried action at a product state (u, m)
is made to lead to a virtual absorbing node omega_m that carries a value W(m).
The field is then never empty while an untried action is reachable, and greedy
ascent on it decides where to explore.

Three choices of W, each stated as what it is:

  rmax     W(m) = 1/(1-q), the value of an absorbing accepting state. An untried
           action might lead straight to acceptance; this is an upper bound on
           the true value for every automaton here (admissible), and it ignores
           the task.
  shaped   W(m) = q^(r(m)-1)/(1-q), with r(m) the number of automaton steps from
           memory m to acceptance. It assumes an unknown state advances the task
           by at most one predicate, so untried actions *after* known subgoals
           are worth exponentially more. It is task-directed, and it is not
           admissible when one state can satisfy two consecutive predicates.
  goal     W(m, u) = q^(r(m)-1+h(u))/(1-q), with h(u) the L1 distance in the world's
           variables from state u to the nearest predicate still to be satisfied.
           The only variant that uses what the task SAYS -- the target state's
           values -- and so the only one that can steer exploration toward a goal
           the model has never seen. A heuristic, not a bound: one action may
           change a variable by more than one.

Two fields on the augmented graph, as in the rest of this work:

  linear   psi = (I - qK)^-1 (g + q b): K uniform over ALL actions, tried ones to
           their modal successor, untried ones contributing W(m) through b
  optimal  V(z) = q max( max_known V(z'), W(m) if an action is untried ): the
           value of heading for the best untried action by the shortest route

The field depends only on the forward-reachable part of the product, so it is
recomputed when the model changes (a new tried pair) and otherwise reused; the
decisions are those of a fresh computation up to floating-point ties.
"""
from __future__ import annotations

from collections import deque
from math import sqrt

import numpy as np
from scipy.sparse import csr_matrix, identity
from scipy.sparse.linalg import splu

from experiments.task_agent.core import (AllTask, BranchTask, SequenceTask, _learner_id_to_state,
                                         _learner_num_actions, _learner_state_to_id,
                                         modal_successors)
from experiments.task_agent.exploration import ExplorationDecision

Q = 0.90


def automaton_distance(task, memory):
    """r(m): how many predicates remain to be satisfied before acceptance."""
    m = int(memory)
    if isinstance(task, SequenceTask):
        return max(0, len(task.goals)-m)
    if isinstance(task, AllTask):
        return len(task.goals)-bin(m).count("1")
    if isinstance(task, BranchTask):
        return {0: 2, 1: 1, 2: 1, 3: 0}[m]
    if hasattr(task, "distance"):
        return int(task.distance(m))
    raise TypeError(f"no automaton distance for {type(task).__name__}")


def _l1(state, target):
    return sum(abs(int(x)-int(y)) for x, y in zip(state, target))


def _predicate_distance(predicate, state):
    """How far a state is from satisfying a predicate, in the world's own variables."""
    if hasattr(predicate, "index"):                        # VarEquals
        return abs(int(state[predicate.index])-int(predicate.value))
    if hasattr(predicate, "value"):                        # ExactState
        return _l1(state, predicate.value)
    return 0


def goal_distance(task, memory, state):
    """L1 distance to the nearest predicate still to be satisfied at this memory."""
    m = int(memory)
    if isinstance(task, SequenceTask):
        return _predicate_distance(task.goals[m], state) if m < len(task.goals) else 0
    if isinstance(task, AllTask):
        pending = [p for i, p in enumerate(task.goals) if not (m >> i) & 1]
        return min((_predicate_distance(p, state) for p in pending), default=0)
    if isinstance(task, BranchTask):
        if m == 0:
            return min(_predicate_distance(task.trigger_a, state),
                       _predicate_distance(task.trigger_b, state))
        if m == 1:
            return _predicate_distance(task.target_a, state)
        if m == 2:
            return _predicate_distance(task.target_b, state)
    return 0


class OptimisticFieldPolicy:
    """Greedy ascent on a field in which untried actions lead to valued virtual nodes."""

    def __init__(self, *, field="linear", shaping="rmax", q=Q):
        if field not in ("linear", "optimal") or shaping not in ("rmax", "shaped", "goal"):
            raise ValueError((field, shaping))
        self.field_kind = field
        self.shaping = shaping
        self.q = float(q)
        self.name = f"optimistic_{field}_{shaping}"
        self._cache = None
        self.solves = 0
        self.reuses = 0

    # -- the value of an untried action ------------------------------------------------
    def omega_value(self, task, memory, state=None):
        if self.shaping == "rmax":
            return 1.0/(1.0-self.q)
        r = automaton_distance(task, memory)
        if self.shaping == "shaped" or state is None:
            return self.q**max(0, r-1)/(1.0-self.q)
        return self.q**(max(0, r-1)+goal_distance(task, memory, state))/(1.0-self.q)

    # -- the augmented product graph ---------------------------------------------------
    def _build(self, learner, task, world_state, memory):
        s2i = _learner_state_to_id(learner)
        i2s = _learner_id_to_state(learner)
        A = _learner_num_actions(learner)
        z0 = (s2i[world_state], task.advance(memory, world_state))
        index, states, known, untried = {z0: 0}, [z0], [], []
        queue = deque([z0])
        while queue:
            u, m = queue.popleft()
            successors = modal_successors(learner, u)
            row, missing = {}, []
            for a in range(A):
                if a in successors:
                    v = successors[a]
                    z2 = (v, task.advance(m, i2s[v]))
                    if z2 not in index:
                        index[z2] = len(states)
                        states.append(z2)
                        queue.append(z2)
                    row[a] = index[z2]
                else:
                    missing.append(a)
            known.append(row)
            untried.append(missing)
        n = len(states)
        accept = np.array([task.accepting(m) for (_, m) in states], dtype=bool)
        omega = np.array([self.omega_value(task, m, i2s[u]) for (u, m) in states])
        return {"index": index, "states": states, "known": known, "untried": untried,
                "accept": accept, "omega": omega, "A": A}

    def _linear(self, model):
        n, A, q = len(model["states"]), model["A"], self.q
        r, c, w = [], [], []
        b = np.zeros(n)
        for i, row in enumerate(model["known"]):
            for j in row.values():
                r.append(i)
                c.append(j)
                w.append(1.0/A)
            b[i] = len(model["untried"][i])*model["omega"][i]/A
        K = csr_matrix((w, (r, c)), shape=(n, n))
        g = model["accept"].astype(float)
        return splu((identity(n, format="csc")-q*K).tocsc()).solve(g+q*b)

    def _optimal(self, model, *, sweeps=10000):
        n, q = len(model["states"]), self.q
        accept = model["accept"]
        V = np.where(accept, 1.0/(1.0-q), 0.0)
        best_untried = np.array([model["omega"][i] if model["untried"][i] else 0.0
                                 for i in range(n)])
        for _ in range(sweeps):
            fresh = V.copy()
            for i, row in enumerate(model["known"]):
                if accept[i]:
                    continue
                known = max((V[j] for j in row.values()), default=0.0)
                fresh[i] = q*max(known, best_untried[i])
            if np.array_equal(fresh, V):
                break
            V = fresh
        return V

    def _field(self, learner, task, world_state, memory):
        s2i = _learner_state_to_id(learner)
        key = (len(learner.counts), id(task))
        z = (s2i[world_state], task.advance(memory, world_state))
        if self._cache is not None and self._cache[0] == key and z in self._cache[1]["index"]:
            self.reuses += 1
            return self._cache[1], self._cache[2]
        model = self._build(learner, task, world_state, memory)
        field = self._linear(model) if self.field_kind == "linear" else self._optimal(model)
        self.solves += 1
        self._cache = (key, model, field)
        return model, field

    # -- the decision ------------------------------------------------------------------
    def choose(self, learner, world_state, task, memory):
        s2i = _learner_state_to_id(learner)
        A = _learner_num_actions(learner)
        u = s2i[world_state]
        model, field = self._field(learner, task, world_state, memory)
        i = model["index"][(u, task.advance(memory, world_state))]
        scores = {}
        for a in range(A):
            if a in model["known"][i]:
                scores[a] = float(field[model["known"][i][a]])
            else:
                scores[a] = float(model["omega"][i])
        best = max(range(A), key=lambda a: (scores[a], -a))
        if scores[best] > 0.0:
            probe = best in model["untried"][i]
            return ExplorationDecision(
                action=best, policy=self.name, score=scores,
                target_frontier=u if probe else None,
                reason="probe an untried action: its virtual node is worth the most" if probe
                else "ascend the optimistic field towards untried actions")
        unknown = {a: 1.0/sqrt(1.0+learner.action_visits.get((u, a), 0)) for a in range(A)}
        a = max(range(A), key=lambda x: (unknown[x], -x))
        return ExplorationDecision(action=a, policy=self.name, unknownness=unknown,
                                   reason="nothing untried is reachable: local count probe")
