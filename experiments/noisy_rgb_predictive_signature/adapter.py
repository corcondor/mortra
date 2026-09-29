"""Adapter from predictive-signature quotient to the unchanged MORTRA field core."""
from __future__ import annotations

from collections import Counter


class PredictiveGraphAdapter:
    """Expose a learned predictive quotient through StructuralLearner's interface.

    The task-agent core already consumes only the public learner fields below.
    This adapter does not copy or alter ProductPlanner/VirtualFrontier.
    """

    def __init__(self, model, num_actions):
        self.num_actions = int(num_actions)
        self.id_to_state = [self.state_token(q) for q in range(len(model["reps"]))]
        self.state_to_id = {state: q for q, state in enumerate(self.id_to_state)}
        self.node_visits = Counter()
        self.action_visits = Counter()
        self.counts = {}
        self.dest_map = {}
        for (q, action), target in model["trans"].items():
            q, action, target = int(q), int(action), int(target)
            if not (0 <= q < len(self.id_to_state) and 0 <= target < len(self.id_to_state)):
                raise ValueError("transition references unknown predictive state")
            if not 0 <= action < self.num_actions:
                raise ValueError("transition action outside alphabet")
            self.counts[q, action] = {target: 1}
            self.action_visits[q, action] = 1
            self.dest_map[q, action] = target

    @staticmethod
    def state_token(q):
        return ("predictive", int(q))

    def get_or_add_id(self, state):
        if state not in self.state_to_id:
            raise KeyError("predictive adapter is closed over the acquired quotient")
        return self.state_to_id[state]

    def record_transition(self, u, action, v):
        """Record additional observed support without inventing a new state identity."""
        key = (int(u), int(action))
        v = int(v)
        self.action_visits[key] += 1
        row = self.counts.setdefault(key, {})
        row[v] = row.get(v, 0) + 1
        self.dest_map[key] = max(row.items(), key=lambda item: (item[1], -item[0]))[0]
