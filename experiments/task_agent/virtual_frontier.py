"""Goal-free and task-weighted hitting fields for untried actions.

Only learned transitions enter the graph. An unknown action ends at its own
virtual node, without an observation or a predicted successor.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass
from math import exp
from time import perf_counter

import numpy as np
from scipy.sparse import csr_matrix, identity
from scipy.sparse.linalg import splu

from .core import _learner_id_to_state, _learner_num_actions, _learner_state_to_id
from .exploration import CountUncertaintyPolicy, ExplorationDecision

NUMERICAL_TOLERANCE = 1e-12
Q = 0.90


@dataclass
class FrontierFields:
    states: list
    actions: list
    virtual: list
    kernel: csr_matrix
    sources: np.ndarray
    values: np.ndarray
    solve_seconds: float
    residual: float

    @property
    def signal_available(self):
        weights = self.sources[len(self.states):, 1]
        return bool(len(weights) and np.ptp(weights) > NUMERICAL_TOLERANCE)


def build_frontier_fields(learner, world_state, task, memory, *, task_source=True):
    """Reachable real product nodes followed by terminal unknown-action nodes."""
    state_ids = _learner_state_to_id(learner)
    observations = _learner_id_to_state(learner)
    action_count = _learner_num_actions(learner)
    if action_count <= 0 or world_state not in state_ids:
        raise ValueError("a known current state and a nonempty action alphabet are required")
    initial = (state_ids[world_state], task.advance(memory, world_state))
    states, index, actions, virtual = [initial], {initial: 0}, [], []
    queue = deque([initial])
    while queue:
        u, m = queue.popleft()
        row = {}
        for a in range(action_count):
            visits = learner.action_visits.get((u, a), 0)
            if visits < 0:
                raise ValueError("negative action visit count")
            if visits == 0:
                # Negative indices refer to virtual nodes until real BFS ends.
                row[a] = -1 - len(virtual)
                virtual.append((u, m, a))
                continue
            counts = learner.counts.get((u, a))
            if not counts:
                raise ValueError("tried action has no recorded successor")
            v = max(counts, key=lambda x: (counts[x], -x))
            successor = (v, task.advance(m, observations[v]))
            if successor not in index:
                index[successor] = len(states)
                states.append(successor)
                queue.append(successor)
            row[a] = index[successor]
        actions.append(row)

    n_real = len(states)
    rows, columns, weights = [], [], []
    for i, row in enumerate(actions):
        for a, j in row.items():
            if j < 0:
                j = n_real + (-j - 1)
                row[a] = j
            rows.append(i)
            columns.append(j)
            weights.append(1.0 / action_count)
    n = n_real + len(virtual)
    kernel = csr_matrix((weights, (rows, columns)), shape=(n, n))
    sources = np.zeros((n, 2))
    for i, (_, memory_before_unknown, _) in enumerate(virtual, n_real):
        sources[i, 0] = 1.0
        sources[i, 1] = exp(float(task.progress(memory_before_unknown))) if task_source else 1.0
    if not np.isfinite(sources).all():
        raise ValueError("nonfinite task source")
    seconds = 0.0
    values = np.zeros_like(sources)
    if virtual:
        started = perf_counter()
        factor = splu(identity(n, format="csc") - Q * kernel.tocsc())
        values = factor.solve(sources)  # One factorization, two right-hand sides.
        seconds = perf_counter() - started
    residual = float(np.max(np.abs(sources + Q * (kernel @ values) - values)))
    return FrontierFields(states, actions, virtual, kernel, sources, values, seconds, residual)


class VirtualFrontierPolicy:
    def __init__(self, *, task_aware=False, task_source=True):
        self.task_aware = bool(task_aware)
        self.task_source = bool(task_source)
        self.name = "task_virtual_frontier" if task_aware else "virtual_frontier"
        self.last_telemetry = None

    def choose(self, learner, world_state, task, memory):
        started = perf_counter()
        fields = build_frontier_fields(learner, world_state, task, memory,
                                       task_source=self.task_source)
        row = fields.actions[0]
        generic_scores = {a: float(fields.values[j, 0]) for a, j in row.items()}
        task_scores = {a: float(fields.values[j, 1]) for a, j in row.items()}
        generic_action = max(row, key=lambda a: (generic_scores[a], -a))
        task_action = max(row, key=lambda a: (task_scores[a], -a))
        constant_source = bool(fields.virtual and
                               np.all(fields.sources[len(fields.states):, 1] ==
                                      fields.sources[len(fields.states), 1]))
        raw_task_action = task_action
        if constant_source:
            # A constant source multiplier cannot change the exact argmax.
            # Reuse that argmax rather than promote roundoff to task evidence.
            task_action = generic_action
        if not self.task_source:
            assert np.array_equal(fields.values[:, 0], fields.values[:, 1])
            assert task_action == generic_action

        action = task_action if self.task_aware else generic_action
        reason = "discounted terminal-frontier hitting field"
        if not fields.virtual:
            action = CountUncertaintyPolicy().choose(learner, world_state, task, memory).action
            generic_action = task_action = action
            reason = "no reachable virtual frontier; unchanged local count fallback"
        changed = bool(self.task_aware and action != generic_action)
        self.last_telemetry = {
            "virtual_field_decision": bool(fields.virtual),
            "task_signal_available": fields.signal_available,
            "field_changed": changed,
            "generic_counterfactual_action": int(generic_action),
            "task_action": int(task_action),
            "selected_action": int(action),
            "raw_task_action": int(raw_task_action),
            "constant_source_roundoff_corrected": constant_source and raw_task_action != generic_action,
            "virtual_nodes": len(fields.virtual),
            "real_product_nodes": len(fields.states),
            "kernel_nnz": fields.kernel.nnz,
            "source_min": float(fields.sources[len(fields.states):, 1].min()) if fields.virtual else None,
            "source_max": float(fields.sources[len(fields.states):, 1].max()) if fields.virtual else None,
            "field_solve_seconds": fields.solve_seconds,
            "field_residual": fields.residual,
            "policy_seconds": perf_counter() - started,
            "generic_scores": generic_scores,
            "task_scores": task_scores,
        }
        return ExplorationDecision(action=int(action), policy=self.name,
                                   score=task_scores if self.task_aware else generic_scores,
                                   reason=reason)
