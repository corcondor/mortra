"""Task-blind initial exploration using existing frozen MORTRA policies.

New code: a singleton-memory adapter, selector factory, and training loop.
No target/task, source predictor, environment table, or oracle is passed to a
selector. StructuralLearner.record_transition is unchanged. In a checkout of
MORTRA, this module uses the repository's normal imports without local shims.
"""
from __future__ import annotations

import copy
import time
from dataclasses import dataclass
from typing import Any, Callable, Protocol

from experiments.game_frontier_v1.frozen import StructuralLearner
from .exploration import FrozenStructuralPolicy, FrontierFieldPolicy
from .virtual_frontier import VirtualFrontierPolicy

METHODS = ('structural', 'frontier_t0', 'virtual_frontier')


class TrainingWorld(Protocol):
    initial: Any
    num_actions: int
    def step(self, state: Any, action: int) -> Any: ...


class SingletonMemory:
    """Product with a singleton: (u, 0) is simply u; no task is encoded."""
    initial_memory = 0

    @staticmethod
    def advance(memory, world_state):
        # world_state is deliberately not inspected (not even indexed).
        return 0

    @staticmethod
    def progress(memory):
        raise AssertionError('Task progress must never be requested during pretraining')

    @staticmethod
    def accepting(memory):
        raise AssertionError('Task acceptance must never be requested during pretraining')


@dataclass
class TrainingOutput:
    snapshots: dict[int, Any]
    metrics: list[dict[str, Any]]


class TaskBlindSelector:
    """Expose only learner + observed state, never a task or environment."""
    def __init__(self, method: str):
        if method not in METHODS:
            raise ValueError(f'Unknown method {method!r}; expected one of {METHODS}')
        self.method = method
        if method == 'structural':
            self.policy = FrozenStructuralPolicy()
        elif method == 'frontier_t0':
            self.policy = FrontierFieldPolicy(low_count_threshold=0)
        else:
            self.policy = VirtualFrontierPolicy(task_aware=False, task_source=False)
        self.memory = SingletonMemory()

    def choose(self, learner, world_state):
        decision = self.policy.choose(learner, world_state, self.memory, 0)
        telemetry = dict(getattr(self.policy, 'last_telemetry', None) or {})
        return decision, telemetry


def train_snapshots_with_policy(
    engine: TrainingWorld,
    method: str,
    budgets: tuple[int, ...] = (128, 512, 2048),
    *,
    trace_sink: Callable[[dict[str, Any]], None] | None = None,
) -> TrainingOutput:
    """Start empty; take exactly max(budgets) environment interactions.

    Budgets are nested checkpoints of one uninterrupted training trajectory.
    Non-structural selectors retain their existing node_visits behavior; the
    frozen recorder is not modified or given invented visits.
    """
    if (not budgets or any(type(b) is not int or b < 0 for b in budgets)
            or tuple(sorted(set(budgets))) != budgets):
        raise ValueError('budgets must be sorted distinct nonnegative integers')
    selector = TaskBlindSelector(method)
    learner = StructuralLearner(engine.num_actions)
    state = engine.initial
    u = learner.get_or_add_id(state)
    snapshots, metrics = {}, []
    interactions = new_pairs = virtual_decisions = 0
    field_seconds = 0.0
    residual_max = 0.0
    cpu0, wall0 = time.process_time(), time.perf_counter()
    for budget in budgets:
        while interactions < budget:
            decision, telemetry = selector.choose(learner, state)
            action = int(decision.action)
            if not 0 <= action < learner.num_actions:
                raise RuntimeError('selector returned illegal action')
            untried = learner.action_visits.get((u, action), 0) == 0
            nxt = engine.step(state, action)  # the only source of new transitions
            v = learner.get_or_add_id(nxt)
            learner.record_transition(u, action, v)
            interactions += 1
            new_pairs += int(untried)
            virtual_decisions += int(telemetry.get('virtual_field_decision', False))
            field_seconds += telemetry.get('field_solve_seconds', 0.0)
            residual_max = max(residual_max, telemetry.get('field_residual', 0.0))
            if trace_sink is not None:
                trace_sink({'step': interactions, 'state': state, 'u': u, 'action': action,
                            'next_state': nxt, 'v': v, 'new_pair': untried,
                            'generic_scores': telemetry.get('generic_scores'),
                            'field_residual': telemetry.get('field_residual', 0.0)})
            state, u = nxt, v
        assert sum(learner.action_visits.values()) == budget
        snapshots[budget] = copy.deepcopy(learner)
        metrics.append({'budget': budget, 'method': method, 'environment_steps': interactions,
                        'known_states': len(learner.id_to_state), 'known_pairs': len(learner.counts),
                        'new_pairs': new_pairs, 'virtual_decisions': virtual_decisions,
                        'field_solve_seconds': field_seconds, 'max_field_residual': residual_max,
                        'train_cpu_seconds_cumulative': time.process_time()-cpu0,
                        'train_wall_seconds_cumulative': time.perf_counter()-wall0})
    return TrainingOutput(snapshots, metrics)
