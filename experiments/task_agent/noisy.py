"""The same worlds with slip, and the fields that can be ascended in them.

Every archived world is deterministic, which is why the optimal product field
is a shortest path by construction and why the linear field can only lose to
it there. The case for the linear field is the other one: in a world where
actions sometimes do something else, a field that counts *every* discounted
path to the goal prefers routes with many ways through, and a shortest path is
brittle. This module puts that case to a test instead of arguing it.

The world is the archived Engine with slip: with probability `slip` the
executed action is replaced by one drawn uniformly from all actions. The draw is
a hash of an episode seed and a step counter, so every run is reproducible, and
every planner in an episode faces the same sequence of draws.

The learner is the canonical StructuralLearner trained in the slipping world, so
its counts hold every successor it saw for an action.

Four planners, all on the product of that learned model with the task
automaton, all replanning from the current product state when a slip has
carried the agent outside the graph the current plan covers:

  linear            the delivered field, (I - qK)^-1 g on modal successors with
                    equal weight per tried action -- what ProductPlanner does
  linear_empirical  the same field with each action's weight spread over the
                    successors it was seen to have, in proportion: the linear
                    field's best case in a noisy world
  shortest          q^d on the modal graph: optimal if the modal model were true
  expected          value iteration on the empirical frequencies,
                    V = max_a E[1 if next accepts else q V(next)]: optimal for the
                    model the learner actually has
"""
from __future__ import annotations

import hashlib
from collections import deque

import numpy as np
from scipy.sparse import csr_matrix, identity
from scipy.sparse.linalg import splu

from experiments.task_agent import checkpoint

METHODS = ("linear", "linear_empirical", "shortest", "expected")
Q = checkpoint.Q


NOISES = ("uniform", "drift_state", "drift_global")


def drift_action(state, num_actions, noise):
    """The action a drift executes instead: fixed per state, or action 0 everywhere."""
    if noise == "drift_global":
        return 0
    digest = hashlib.sha256(repr(tuple(int(v) for v in state)).encode()).digest()
    return int.from_bytes(digest[:4], "big") % num_actions


class SlipEngine:
    """The canonical Engine; with probability `slip` the action is replaced by another.

    `noise="uniform"` replaces it by one drawn uniformly from all actions (the
    original model). `drift_state` replaces it by a fixed action per state and
    `drift_global` by action 0 -- noise that is not the averaging a
    uniform-policy field performs.
    """

    def __init__(self, genome, slip, seed, noise="uniform"):
        if noise not in NOISES:
            raise ValueError(noise)
        self.base = checkpoint.Engine(genome)
        self.initial = self.base.initial
        self.num_actions = self.base.num_actions
        self.dom = self.base.dom
        self.slip = float(slip)
        self.seed = str(seed)
        self.noise = noise
        self.clock = 0

    def step(self, state, action):
        digest = hashlib.sha256(f"{self.seed}:{self.clock}".encode()).digest()
        self.clock += 1
        draw = int.from_bytes(digest[:8], "big")/2**64
        if draw >= self.slip:
            return self.base.step(state, action)
        if self.noise == "uniform":
            other = int.from_bytes(digest[8:12], "big") % self.num_actions
        else:
            other = drift_action(state, self.num_actions, self.noise)
        return self.base.step(state, other)


def train(engine, budget):
    learner = checkpoint.Learner(engine.num_actions)
    cur = engine.initial
    u = learner.add(cur)
    for _ in range(budget):
        a = learner.select(u)
        ns = engine.step(cur, a)
        v = learner.add(ns)
        learner.rec(u, a, v)
        cur, u = ns, v
    return learner


# ---------------------------------------------------------------------------
# The product graph, as a list of (state, action) pairs with outcome distributions
# ---------------------------------------------------------------------------

def _outcomes(learner, u, empirical):
    out = {}
    for a in range(learner.A):
        d = learner.counts.get((u, a))
        if not d:
            continue
        if empirical:
            total = sum(d.values())
            out[a] = [(v, c/total) for v, c in sorted(d.items())]
        else:
            out[a] = [(max(d.items(), key=lambda kv: kv[1])[0], 1.0)]
    return out


def build(learner, automaton, state, memory, *, empirical):
    """Reachable product graph from (state, memory), modal or with every observed outcome."""
    if state not in learner.s2i:
        return None
    z0 = (learner.s2i[state], automaton.update(memory, state))
    ids, states = {z0: 0}, [z0]
    pair_state, pair_action, rows, cols, probs = [], [], [], [], []
    queue = deque([z0])
    while queue:
        u, m = queue.popleft()
        i = ids[(u, m)]
        for a, outcomes in _outcomes(learner, u, empirical).items():
            k = len(pair_state)
            pair_state.append(i)
            pair_action.append(a)
            for v, p in outcomes:
                z2 = (v, automaton.update(m, learner.i2s[v]))
                if z2 not in ids:
                    ids[z2] = len(states)
                    states.append(z2)
                    queue.append(z2)
                rows.append(k)
                cols.append(ids[z2])
                probs.append(p)
    n = len(states)
    P = csr_matrix((probs, (rows, cols)), shape=(len(pair_state), n))
    accept = np.zeros(n, dtype=bool)
    for i, (_, m) in enumerate(states):
        accept[i] = automaton.done(m)
    pairs_of = [[] for _ in range(n)]
    for k, i in enumerate(pair_state):
        pairs_of[i].append(k)
    return {"ids": ids, "states": states, "P": P, "pair_state": np.array(pair_state),
            "pair_action": np.array(pair_action), "pairs_of": pairs_of, "accept": accept}


def linear_field(model):
    """(I - qK)^-1 g with K the uniform choice over tried actions, then the outcome spread."""
    n = len(model["states"])
    if not model["accept"].any():
        return None
    counts = np.array([len(p) for p in model["pairs_of"]], dtype=float)
    share = np.divide(1.0, counts, out=np.zeros_like(counts), where=counts > 0)
    S = csr_matrix((share[model["pair_state"]], (model["pair_state"],
                                                np.arange(len(model["pair_state"])))),
                   shape=(n, len(model["pair_state"])))
    K = (S @ model["P"]).tocsc()
    g = model["accept"].astype(float)
    return splu(identity(n, format="csc")-Q*K).solve(g)


def optimal_field(model, *, sweeps=5000, tolerance=1e-13):
    """First exit: V = 1 on acceptance, else q * max_a E[V(next)] -- iterated to a fixed point.

    For the modal model this is q^(d-1) off acceptance, and ascending it is a
    shortest path; for the empirical model it is the value of the best policy
    the learned model can support.
    """
    accept = model["accept"]
    if not accept.any():
        return None
    n = len(accept)
    V = accept.astype(float)
    P, owner = model["P"], model["pair_state"]
    has_pairs = np.array([bool(p) for p in model["pairs_of"]])
    for _ in range(sweeps):
        target = np.where(accept, 1.0, Q*V)
        pair_value = P @ target
        best = np.zeros(n)
        np.maximum.at(best, owner, pair_value)
        fresh = np.where(accept, 1.0, np.where(has_pairs, best, 0.0))
        if np.max(np.abs(fresh-V)) < tolerance:
            V = fresh
            break
        V = fresh
    return V


def choose(model, field, z, *, kind):
    """Greedy on the field with the delivered tie-break (the lowest action index wins)."""
    i = model["ids"].get(z)
    if i is None or field is None:
        return None
    P, accept = model["P"], model["accept"]
    target = field if kind == "linear" else np.where(accept, 1.0, Q*field)
    pairs = model["pairs_of"][i]
    values = P[pairs] @ target if pairs else []
    best = None
    for k, value in zip(pairs, values):
        score = float(value)
        a = int(model["pair_action"][k])
        key = (score, -a, a)
        if best is None or key > best:
            best = key
    if best is None or best[0] <= 0.0:
        return None
    return best[2]


def run_episode(learner, engine, automaton, start, method, *, horizon=checkpoint.HORIZON):
    """Execute in the slipping world; replan whenever the current graph does not cover us."""
    empirical = method in ("linear_empirical", "expected")
    kind = "linear" if method.startswith("linear") else "optimal"
    cur = tuple(start)
    memory = automaton.initial_memory(cur)
    model = field = None
    steps = replans = 0
    while steps < horizon and not automaton.done(memory):
        if cur not in learner.s2i:
            return {"success": False, "steps": steps, "replans": replans,
                    "why": "slipped into a state the model has never seen"}
        z = (learner.s2i[cur], memory)
        if model is None or z not in model["ids"]:
            model = build(learner, automaton, cur, memory, empirical=empirical)
            replans += 1
            field = linear_field(model) if kind == "linear" else optimal_field(model)
        action = choose(model, field, z, kind=kind)
        if action is None:
            return {"success": False, "steps": steps, "replans": replans,
                    "why": "no accepting path in the model from here"}
        cur = engine.step(cur, action)
        memory = automaton.update(memory, cur)
        steps += 1
    done = automaton.done(memory)
    return {"success": done, "steps": steps, "replans": replans,
            "why": "success" if done else "horizon"}
