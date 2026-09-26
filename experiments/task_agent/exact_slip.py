"""Planning fields under action slip, evaluated exactly instead of by sampling.

This replaces the Monte-Carlo slip run (`run_noisy.py`), which a review showed
could not support a ranking of the fields: one episode per task, task sets and
learned models that changed with the slip level, an executor that failed on the
first unseen state, and success differences that were coverage artefacts. Every
planner here defines a stationary policy on (world state, task memory) -- a field
computed on a forward-closed product graph equals the global field restricted to
it -- so its performance under a known slip kernel can be computed exactly by
propagating the state distribution. Nothing is sampled at evaluation time.

PROTOCOL (fixed before any exact run)

  tasks      the 368 registered tasks, the same at every slip level
  worlds     the eight archived worlds; the true dynamics are the Engine's,
             enumerated from the initial state and every task start
  slip       e in {0, 0.05, 0.10, 0.20}; the true kernel is
             P(s'|s,a) = (1-e) [s' = T(s,a)] + (e/A) sum_b [s' = T(s,b)]
  models     learned: the canonical StructuralLearner, 8192 steps in the
             e-slipping world (training seed "train:{world}:{e}", as before)
             oracle:  the true deterministic transition graph
  planners   on the learned model --
               linear                (I - qK)^-1 g, K uniform over tried actions,
                                     modal successors with the delivered
                                     core.modal_successors tie-break
               shortest              q^d on the same modal graph
               linear_empirical      the linear field with each action spread
                                     over its observed successors in proportion
               certainty_equivalent  discounted-reach value iteration on the
                                     empirical frequencies (optimal for E[q^tau]
                                     on the plug-in model, not for steps)
             on the oracle model --
               linear_oracle         the linear field over all actions
               shortest_oracle       q^d on the true graph
             ceiling --
               ssp_optimal           minimises expected steps to acceptance under
                                     the true slip kernel; knows e and T
  policy     greedy on the field, lowest action index on ties (the delivered rule);
             undefined where the world state is unknown to the model or no
             accepting path exists in it -- the episode fails there
  evaluation exact distribution propagation for H = 512 steps
  outcomes   per task: P(success within 512); expected cost with failure charged
             at 512. Aggregates are means over the 368 tasks; comparisons are
             paired per task, with sign tests and a per-world breakdown
"""
from __future__ import annotations

from collections import deque

import numpy as np
from scipy.sparse import csr_matrix, identity
from scipy.sparse.linalg import splu

from experiments.game_frontier_v11.world import oracle as world_oracle
from experiments.task_agent import checkpoint, noisy

Q = checkpoint.Q
HORIZON = 512
SLIPS = (0.0, 0.05, 0.10, 0.20)
LEARNED = ("linear", "shortest", "linear_empirical", "certainty_equivalent")
ORACLE = ("linear_oracle", "shortest_oracle")
PLANNERS = LEARNED + ORACLE + ("ssp_optimal",)


# ---------------------------------------------------------------------------
# The true world
# ---------------------------------------------------------------------------

def true_graph(engine, starts):
    """Every state reachable from the initial state and the task starts, with T(s,a)."""
    roots = [engine.initial] + [tuple(s) for s in starts]
    status, graph = world_oracle(engine.core, 100000, roots)
    if graph is None:
        raise RuntimeError(status)
    ordered, edges, ids = graph
    return ordered, edges, ids


# ---------------------------------------------------------------------------
# Models: for each state index and action, a distribution over successor indices
# ---------------------------------------------------------------------------

def learned_model(learner, *, empirical):
    """Per learned state: {action: [(successor, probability)]}, over tried actions only."""
    rows = []
    for u in range(len(learner.i2s)):
        row = {}
        for a in range(learner.A):
            d = learner.counts.get((u, a))
            if not d:
                continue
            if empirical:
                total = sum(d.values())
                row[a] = [(v, c/total) for v, c in sorted(d.items())]
            else:
                # the delivered tie-break: highest count, then lowest successor id
                row[a] = [(max(d.items(), key=lambda kv: (kv[1], -kv[0]))[0], 1.0)]
        rows.append(row)
    return rows


def oracle_model(edges):
    return [{a: [(v, 1.0)] for a, v in enumerate(row)} for row in edges]


def product(model_rows, states, automaton):
    """The product over every model state and every memory value, with acceptance."""
    memories = range(automaton.num_memory)
    index = {(u, m): k for k, (u, m) in enumerate((u, m) for u in range(len(model_rows))
                                                  for m in memories)}
    n = len(index)
    pair_state, pair_action, r, c, p = [], [], [], [], []
    for (u, m), k in index.items():
        for a, outcomes in model_rows[u].items():
            row = len(pair_state)
            pair_state.append(k)
            pair_action.append(a)
            for v, prob in outcomes:
                m2 = automaton.update(m, states[v])
                r.append(row)
                c.append(index[(v, m2)])
                p.append(prob)
    P = csr_matrix((p, (r, c)), shape=(len(pair_state), n))
    accept = np.array([automaton.done(m) for (u, m) in index], dtype=bool)
    pairs_of = [[] for _ in range(n)]
    for row, k in enumerate(pair_state):
        pairs_of[k].append(row)
    return {"index": index, "P": P, "pair_state": np.array(pair_state, dtype=int),
            "pair_action": np.array(pair_action, dtype=int), "pairs_of": pairs_of,
            "accept": accept}


def can_accept(prod):
    """States with a positive-probability path to acceptance: graph reachability, no cutoff."""
    n = len(prod["accept"])
    reverse = [[] for _ in range(n)]
    P = prod["P"].tocoo()
    for row, col in zip(P.row, P.col):
        reverse[col].append(prod["pair_state"][row])
    seen = set(np.flatnonzero(prod["accept"]).tolist())
    queue = deque(seen)
    while queue:
        v = queue.popleft()
        for u in reverse[v]:
            if u not in seen:
                seen.add(u)
                queue.append(u)
    mask = np.zeros(n, dtype=bool)
    mask[list(seen)] = True
    return mask


# ---------------------------------------------------------------------------
# Fields and the policies they induce
# ---------------------------------------------------------------------------

def linear_field(prod):
    n = len(prod["accept"])
    counts = np.array([len(x) for x in prod["pairs_of"]], dtype=float)
    share = np.divide(1.0, counts, out=np.zeros_like(counts), where=counts > 0)
    S = csr_matrix((share[prod["pair_state"]], (prod["pair_state"],
                                               np.arange(len(prod["pair_state"])))),
                   shape=(n, len(prod["pair_state"])))
    K = (S @ prod["P"]).tocsc()
    return splu(identity(n, format="csc")-Q*K).solve(prod["accept"].astype(float))


def depth_field(prod):
    """q^d with d the fewest steps to acceptance in a deterministic product graph."""
    n = len(prod["accept"])
    reverse = [[] for _ in range(n)]
    P = prod["P"].tocoo()
    for row, col in zip(P.row, P.col):
        reverse[col].append(prod["pair_state"][row])
    depth = {int(k): 0 for k in np.flatnonzero(prod["accept"])}
    queue = deque(depth)
    while queue:
        v = queue.popleft()
        for u in reverse[v]:
            if u not in depth:
                depth[u] = depth[v]+1
                queue.append(u)
    field = np.zeros(n)
    for k, d in depth.items():
        field[k] = Q**d
    return field


def reach_value(prod, *, sweeps=20000, tolerance=1e-14):
    """V = 1 on acceptance, else q max_a E[V(next)]: discounted reach on the given model."""
    accept = prod["accept"]
    n = len(accept)
    V = accept.astype(float)
    owner, P = prod["pair_state"], prod["P"]
    for _ in range(sweeps):
        pair = P @ np.where(accept, 1.0, Q*V)
        best = np.zeros(n)
        np.maximum.at(best, owner, pair)
        fresh = np.where(accept, 1.0, best)
        if np.max(np.abs(fresh-V)) < tolerance*max(1.0, float(np.max(fresh))):
            return fresh
        V = fresh
    return V


def greedy_policy(prod, field, *, kind):
    """Action per product state, or -1 where the policy is undefined (no accepting path)."""
    ok = can_accept(prod)
    accept = prod["accept"]
    target = field if kind == "linear" else np.where(accept, 1.0, Q*field)
    pair_value = prod["P"] @ target
    reach_of_pair = prod["P"] @ ok.astype(float)
    policy = np.full(len(accept), -1, dtype=int)
    for k, rows in enumerate(prod["pairs_of"]):
        if accept[k] or not ok[k]:
            continue
        best = None
        for row in rows:
            if reach_of_pair[row] <= 0.0:            # delivered rule: only successors that can accept
                continue
            a = int(prod["pair_action"][row])
            key = (float(pair_value[row]), -a, a)
            if best is None or key > best:
                best = key
        if best is not None:
            policy[k] = best[2]
    return policy


# ---------------------------------------------------------------------------
# The true process under slip, and exact evaluation
# ---------------------------------------------------------------------------

def true_product(states, edges, automaton, start, num_actions):
    """Product states reachable from the task's start under ANY action (slip can take any)."""
    ids = {s: i for i, s in enumerate(states)}
    s0 = ids[tuple(start)]
    z0 = (s0, automaton.initial_memory(states[s0]))
    index = {z0: 0}
    order = [z0]
    queue = deque([z0])
    while queue:
        s, m = queue.popleft()
        for a in range(num_actions):
            t = edges[s][a]
            z = (t, automaton.update(m, states[t]))
            if z not in index:
                index[z] = len(order)
                order.append(z)
                queue.append(z)
    return index, order


def executed(noise, slip, state, action, num_actions):
    """The law of the executed action given the intended one: {action: probability}."""
    weights = {action: 1.0-slip}
    if slip > 0:
        if noise == "uniform":
            for b in range(num_actions):
                weights[b] = weights.get(b, 0.0)+slip/num_actions
        else:
            b = noisy.drift_action(state, num_actions, noise)
            weights[b] = weights.get(b, 0.0)+slip
    return weights


def slip_matrix(order, index, edges, automaton, states, actions, slip, num_actions,
                noise="uniform"):
    """Transitions of the true process for a policy: actions[k] per product state, -1 = fail."""
    n = len(order)
    r, c, p = [], [], []
    fail = np.zeros(n)
    for k, (s, m) in enumerate(order):
        if automaton.done(m):
            continue
        a = actions[k]
        if a < 0:
            fail[k] = 1.0
            continue
        weights = executed(noise, slip, states[s], a, num_actions)
        for b, w in weights.items():
            t = edges[s][b]
            z = (t, automaton.update(m, states[t]))
            r.append(k)
            c.append(index[z])
            p.append(w)
    return csr_matrix((p, (r, c)), shape=(n, n)), fail


def evaluate(order, index, edges, automaton, states, actions, slip, num_actions,
             horizon=HORIZON, noise="uniform"):
    """P(success within the horizon) and expected cost with failure charged at the horizon."""
    M, fail = slip_matrix(order, index, edges, automaton, states, actions, slip, num_actions,
                          noise)
    accept = np.array([automaton.done(m) for (_, m) in order], dtype=bool)
    live = np.zeros(len(order))
    live[0] = 1.0
    if accept[0]:
        return {"p_success": 1.0, "expected_cost": 0.0, "expected_steps_given_success": 0.0}
    MT = M.T.tocsr()
    p_success = 0.0
    time_weighted = 0.0
    for t in range(1, horizon+1):
        live = MT @ live
        arrived = float(live[accept].sum())
        if arrived:
            p_success += arrived
            time_weighted += t*arrived
            live[accept] = 0.0
        if live.sum() < 1e-15:
            break
    cost = time_weighted+(1.0-p_success)*horizon
    return {"p_success": p_success, "expected_cost": cost,
            "expected_steps_given_success": time_weighted/p_success if p_success > 0 else None}


def ssp_policy(order, index, edges, automaton, states, slip, num_actions,
               *, sweeps=100000, tolerance=1e-10, noise="uniform"):
    """Minimise expected steps to acceptance under the true noise kernel. The ceiling."""
    n = len(order)
    accept = np.array([automaton.done(m) for (_, m) in order], dtype=bool)
    succ = np.zeros((n, num_actions), dtype=int)
    for k, (s, m) in enumerate(order):
        for b in range(num_actions):
            t = edges[s][b]
            succ[k, b] = index[(t, automaton.update(m, states[t]))]
    # E[k, a, b] = P(execute b | intend a) at product state k
    E = np.zeros((n, num_actions, num_actions))
    for k, (s, m) in enumerate(order):
        for a in range(num_actions):
            for b, w in executed(noise, slip, states[s], a, num_actions).items():
                E[k, a, b] += w
    # start from the deterministic distance, a lower bound on expected steps under any
    # slip (no sequence of actions reaches acceptance in fewer), so the iteration only
    # has to climb, and states that cannot reach acceptance start and stay at the cap
    reverse = [[] for _ in range(n)]
    for k in range(n):
        for b in range(num_actions):
            reverse[succ[k, b]].append(k)
    V = np.full(n, 1e9)
    V[accept] = 0.0
    queue = deque(np.flatnonzero(accept).tolist())
    while queue:
        v = queue.popleft()
        for u in reverse[v]:
            if V[u] >= 1e9 and not accept[u]:
                V[u] = V[v]+1
                queue.append(u)
    for _ in range(sweeps):
        q_values = 1.0+np.einsum("kab,kb->ka", E, V[succ])
        fresh = np.where(accept, 0.0, np.minimum(q_values.min(axis=1), 1e9))
        if np.max(np.abs(fresh-V)) < tolerance:
            V = fresh
            break
        V = fresh
    q_values = 1.0+np.einsum("kab,kb->ka", E, V[succ])
    actions = np.argmin(q_values, axis=1)                   # lowest index on ties
    actions[accept] = -1
    actions[V >= 1e8] = -1
    return actions


# ---------------------------------------------------------------------------
# One task, every planner
# ---------------------------------------------------------------------------

def policies_on_true_states(order, states, learner, prods, policies):
    """Map a model-level policy onto the true product states it is asked about."""
    out = {}
    for name, (prod, policy) in policies.items():
        acts = np.full(len(order), -1, dtype=int)
        for k, (s, m) in enumerate(order):
            if prod is None:
                continue
            state = states[s]
            if prods[name] == "learned":
                u = learner.s2i.get(state)
                if u is None:
                    continue
            else:
                u = s
            j = prod["index"].get((u, m))
            if j is not None:
                acts[k] = policy[j]
        out[name] = acts
    return out


def task_rows(world, slip, task_id, task_type, start, spec, learner, states, edges, ids,
              num_actions, noise="uniform"):
    automaton = checkpoint.TaskAutomaton(spec)
    index, order = true_product(states, edges, automaton, start, num_actions)
    learned_det = product(learned_model(learner, empirical=False), learner.i2s, automaton)
    learned_emp = product(learned_model(learner, empirical=True), learner.i2s, automaton)
    oracle_prod = product(oracle_model(edges), states, automaton)
    policies = {
        "linear": (learned_det, greedy_policy(learned_det, linear_field(learned_det), kind="linear")),
        "shortest": (learned_det, greedy_policy(learned_det, depth_field(learned_det), kind="optimal")),
        "linear_empirical": (learned_emp, greedy_policy(learned_emp, linear_field(learned_emp),
                                                        kind="linear")),
        "certainty_equivalent": (learned_emp, greedy_policy(learned_emp, reach_value(learned_emp),
                                                            kind="optimal")),
        "linear_oracle": (oracle_prod, greedy_policy(oracle_prod, linear_field(oracle_prod),
                                                     kind="linear")),
        "shortest_oracle": (oracle_prod, greedy_policy(oracle_prod, depth_field(oracle_prod),
                                                       kind="optimal")),
    }
    kinds = {name: ("learned" if name in LEARNED else "oracle") for name in policies}
    acts = policies_on_true_states(order, states, learner, kinds, policies)
    acts["ssp_optimal"] = ssp_policy(order, index, edges, automaton, states, slip, num_actions,
                                     noise=noise)
    rows = []
    for name in PLANNERS:
        result = evaluate(order, index, edges, automaton, states, acts[name], slip, num_actions,
                          noise=noise)
        rows.append({"noise": noise, "slip": slip, "seed": world, "task_id": task_id,
                     "task_type": task_type,
                     "planner": name, "true_product_states": len(order),
                     "learned_states": len(learner.i2s), **result})
    return rows
