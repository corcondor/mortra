"""Live persistent online Task Agent.

Unlike the older checkpoint simulation, this loop interleaves planning,
exploration, learner update, and replanning.  It is suitable for
task-conditioned exploration because the trajectory may depend on the task.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Hashable, List, Optional

from .core import ProductPlanner, _learner_state_to_id
from .exploration import ExplorationDecision


@dataclass
class EpisodeResult:
    success: bool
    task_steps: int
    exploration_steps: int
    replans: int
    failure_reason: str
    final_memory: Hashable
    decisions: List[Dict[str, Any]] = field(default_factory=list)


class OnlineTaskAgent:
    def __init__(
        self,
        learner,
        exploration_policy,
        *,
        planner: Optional[ProductPlanner] = None,
        max_task_steps: int = 512,
        max_exploration_steps: int = 4096,
        replan_every: int = 1,
    ):
        self.learner = learner
        self.exploration_policy = exploration_policy
        self.planner = planner or ProductPlanner()
        self.max_task_steps = int(max_task_steps)
        self.max_exploration_steps = int(max_exploration_steps)
        self.replan_every = max(1, int(replan_every))

    def _get_or_add(self, state):
        if hasattr(self.learner, "get_or_add_id"):
            return self.learner.get_or_add_id(state)
        return self.learner.add(state)

    def _record(self, u, a, v):
        if hasattr(self.learner, "record_transition"):
            self.learner.record_transition(u, a, v)
        else:
            self.learner.rec(u, a, v)

    def run_task(self, env, task, start_state) -> EpisodeResult:
        world_state = env.reset(start_state)
        memory = task.advance(task.initial_memory, world_state)
        self._get_or_add(world_state)

        task_steps = 0
        exploration_steps = 0
        replans = 0
        decisions: List[Dict[str, Any]] = []

        while task_steps < self.max_task_steps:
            if task.accepting(memory):
                return EpisodeResult(
                    True, task_steps, exploration_steps, replans,
                    "success", memory, decisions
                )

            # Rebuild from the current learned K: no checkpoint shortcut.
            replans += 1
            model = self.planner.build(self.learner, task, world_state, memory)
            action = self.planner.choose_action(
                self.learner, task, world_state, memory, model
            )

            if action is not None:
                # Execute planned action and learn from any discrepancy/new successor.
                u = self._get_or_add(world_state)
                next_state = env.step(action)
                v = self._get_or_add(next_state)
                old_known = (u, action) in self.learner.counts
                old_modal = None
                if old_known:
                    old_modal = max(
                        self.learner.counts[(u, action)].items(),
                        key=lambda kv: (kv[1], -kv[0]),
                    )[0]
                self._record(u, action, v)
                world_state = next_state
                memory = task.advance(memory, world_state)
                task_steps += 1

                if not old_known or old_modal != v:
                    decisions.append({
                        "kind": "execution_model_update",
                        "task_memory": repr(memory),
                        "action": int(action),
                        "new_edge_or_successor": True,
                    })
                continue

            # No accepting support path in the learned product graph.
            if exploration_steps >= self.max_exploration_steps:
                return EpisodeResult(
                    False, task_steps, exploration_steps, replans,
                    "exploration_budget_exhausted", memory, decisions
                )

            s2i = _learner_state_to_id(self.learner)
            if world_state not in s2i:
                self._get_or_add(world_state)

            decision: ExplorationDecision = self.exploration_policy.choose(
                self.learner, world_state, task, memory
            )
            u = self._get_or_add(world_state)
            before_states = len(getattr(self.learner, "id_to_state", getattr(self.learner, "i2s", [])))
            before_edge = (u, decision.action) in self.learner.counts

            next_state = env.step(decision.action)
            v = self._get_or_add(next_state)
            self._record(u, decision.action, v)

            after_states = len(getattr(self.learner, "id_to_state", getattr(self.learner, "i2s", [])))
            discovered_state = after_states > before_states
            discovered_edge = not before_edge

            decisions.append({
                "kind": "exploration",
                "policy": decision.policy,
                "world_state": repr(world_state),
                "task_memory": repr(memory),
                "action": int(decision.action),
                "unknownness": decision.unknownness,
                "task_relevance": decision.task_relevance,
                "score": decision.score,
                "target_frontier": decision.target_frontier,
                "reason": decision.reason,
                "discovered_state": discovered_state,
                "discovered_edge": discovered_edge,
            })

            world_state = next_state
            memory = task.advance(memory, world_state)
            exploration_steps += 1
            task_steps += 1

        return EpisodeResult(
            False, task_steps, exploration_steps, replans,
            "task_step_limit", memory, decisions
        )
