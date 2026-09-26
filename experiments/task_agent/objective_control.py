"""Separate algebraic certificates from experimental exploration readouts.

The learned product graph, terminal sources, fallback and execution planner
are imported unchanged. No environment or unknown successor is queried here.
"""
from collections import deque
import random

import numpy as np
from scipy.sparse import diags, identity
from scipy.sparse.linalg import splu

from .core import support_reachable
from .exploration import CountUncertaintyPolicy, ExplorationDecision
from .virtual_frontier import Q, build_frontier_fields

AUDIT_TOL = 1e-9  # Numerical verification only, never an action threshold.


def doob_distribution(fields, column, state=0):
    row = fields.actions[state]
    actions = sorted(row)
    h = fields.values[:, column]
    if not h[state] > 0:
        raise ArithmeticError("No positive hitting field; no invented probabilities")
    good = support_reachable(
        [list(r.values()) for r in fields.actions] + [[] for _ in fields.virtual],
        range(len(fields.states), len(h)),
    )
    values = []
    for a in actions:
        j = row[a]
        if j not in good:
            assert abs(h[j]) <= AUDIT_TOL
            values.append(0.0)
        else:
            if not h[j] > 0:
                raise ArithmeticError("Positive-support field underflow")
            values.append(Q * h[j] / (len(actions) * h[state]))
    p = np.asarray(values)
    row_error = abs(float(p.sum()) - 1.0)
    assert row_error <= AUDIT_TOL
    # Only repair the floating-point normalization, not the support or weights.
    p /= p.sum()
    raw_mode = max(actions, key=lambda a: (h[row[a]], -a))
    probability_mode = max(range(len(actions)), key=lambda i: (p[i], -actions[i]))
    return actions, p, {
        "doob_row_error": row_error,
        "field_mode": int(raw_mode),
        "probability_mode": int(actions[probability_mode]),
        "numeric_mode_agreement": raw_mode == actions[probability_mode],
    }


def deadline_target(fields, column, remaining):
    """Exact terminal-utility/shortest-cost lexicographic control on known edges.

    Unknown actions end at their existing virtual terminals. Maximize the
    existing terminal weight reachable within the actual remaining budget;
    among equal weights minimize steps, then use the smallest first action.
    """
    n = len(fields.states)
    distance, first = {0: 0}, {}
    queue = deque([0])
    while queue:
        u = queue.popleft()
        if u >= n or distance[u] >= remaining:
            continue
        for a, v in sorted(fields.actions[u].items()):
            if v not in distance:
                distance[v] = distance[u] + 1
                first[v] = a if u == 0 else first[u]
                queue.append(v)
    candidates = [f for f in range(n, n + len(fields.virtual))
                  if f in distance and distance[f] <= remaining]
    if not candidates:
        return None
    target = max(candidates, key=lambda f: (
        fields.sources[f, column], -distance[f], -first[f], -f))
    return {"action": first[target], "terminal": target,
            "terminal_weight": float(fields.sources[target, column]),
            "known_steps_including_probe": distance[target]}


def scaling_certificate(P, boundary, original=None):
    """P must be transient; callers check structural applicability first."""
    n = P.shape[0]
    factor = splu(identity(n, format="csc") - P.tocsc())
    t = factor.solve(np.ones(n))
    assert np.all(np.isfinite(t)) and np.all(t >= 1 - AUDIT_TOL)
    transformed = diags(1 / t) @ P @ diags(t)
    rows = np.asarray(transformed.sum(axis=1)).ravel()
    expected_rows = 1 - 1 / t
    alpha = float(rows.max())
    assert alpha < 1
    x = factor.solve(boundary) if original is None else original
    y = splu(identity(n, format="csc") - transformed.tocsc()).solve(boundary / t[:, None])
    reconstructed = t[:, None] * y
    relative = float(np.max(np.abs(x - reconstructed)) / max(1.0, float(np.max(np.abs(x)))))
    equation_residual = float(np.max(np.abs(t - 1 - P @ t)))
    row_residual = float(np.max(np.abs(rows - expected_rows)))
    assert relative <= AUDIT_TOL and row_residual <= AUDIT_TOL
    assert equation_residual / max(1., float(t.max())) <= AUDIT_TOL
    return {"states": n, "t_min": float(t.min()), "t_max": float(t.max()),
            "alpha": alpha, "time_equation_residual": equation_residual,
            "row_identity_residual": row_residual, "reconstructed_field_relative_error": relative}


def audit_fields(fields):
    n = len(fields.states)
    out = {"real_states": n, "frontiers": len(fields.virtual), "q": Q}
    if not fields.virtual:
        return {**out, "status": "NO_FRONTIER", "undiscounted_applicable": False}
    P = fields.kernel[:n, :n]
    boundary = fields.kernel[:n, n:] @ fields.sources[n:]
    out["discounted_certificate"] = scaling_certificate(Q * P, Q * boundary, fields.values[:n])
    # Every state in this graph is reachable from its initial state. For the
    # finite full-support reference policy, no nonterminal closed class is
    # equivalent to every real state having a path to a virtual terminal.
    good = support_reachable([list(r.values()) for r in fields.actions] +
                             [[] for _ in fields.virtual], range(n, fields.kernel.shape[0]))
    out["nonterminal_states_without_frontier_path"] = sum(i not in good for i in range(n))
    proper = all(i in good for i in range(n))
    out["undiscounted_applicable"] = proper
    if proper:
        out["undiscounted_certificate"] = scaling_certificate(P, boundary)
        h = splu(identity(n, format="csc") - P.tocsc()).solve(boundary)
        out["undiscounted_generic_max_error_from_one"] = float(np.max(np.abs(h[:, 0] - 1)))
        assert out["undiscounted_generic_max_error_from_one"] <= AUDIT_TOL
    else:
        out["undiscounted_status"] = "NOT_APPLICABLE_NONTERMINAL_RECURRENT_CLASS"
    out["doob"] = [doob_distribution(fields, c)[2] for c in (0, 1)]
    # Resolvent derivative of the first-terminal path generating function.
    factor = splu(identity(n, format="csc") - Q * P.tocsc())
    dh = factor.solve(P @ fields.values[:n] + boundary)
    out["discounted_tilted_expected_hitting_steps"] = [
        float(Q * dh[0, c] / fields.values[0, c]) for c in (0, 1)]
    out["status"] = "VERIFIED"
    return out


class ObjectiveControlPolicy:
    def __init__(self, method, task_aware, seed, budget_clock):
        assert method in ("doob", "deadline")
        self.method, self.column = method, int(task_aware)
        self.rng = random.Random(seed)
        self.budget_clock = budget_clock
        self.name = method + ("_task" if task_aware else "_generic")
        self.last_telemetry = None

    def choose(self, learner, world_state, task, memory):
        fields = build_frontier_fields(learner, world_state, task, memory)
        row = fields.actions[0]
        telemetry = {"method": self.method, "remaining_steps": self.budget_clock(),
                     "real_states": len(fields.states), "frontiers": len(fields.virtual),
                     "reference_field_solve_seconds": fields.solve_seconds,
                     "reference_field_residual": fields.residual}
        chosen = None
        if fields.virtual and self.method == "doob":
            actions, probabilities, check = doob_distribution(fields, self.column)
            u, cumulative = self.rng.random(), 0.0
            positive = [i for i, p in enumerate(probabilities) if p > 0]
            chosen = actions[positive[-1]]
            for i in positive:
                cumulative += probabilities[i]
                if u < cumulative:
                    chosen = actions[i]
                    break
            telemetry.update(check)
            telemetry.update({"actions": actions, "probabilities": probabilities.tolist(), "uniform_draw": u})
        elif fields.virtual:
            target = deadline_target(fields, self.column, self.budget_clock())
            if target is not None:
                chosen = target["action"]
                telemetry.update(target)
        if chosen is None:
            chosen = CountUncertaintyPolicy().choose(learner, world_state, task, memory).action
            telemetry["fallback"] = "frozen_count_policy_no_frontier_or_no_budget_feasible_frontier"
        telemetry["selected_action"] = int(chosen)
        self.last_telemetry = telemetry
        return ExplorationDecision(action=int(chosen), policy=self.name,
                                   reason="registered " + self.method + " frontier readout")
