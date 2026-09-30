"""Depth-first continual frontier navigation over the learned predictive graph.

The generic virtual-frontier field treats every untried state-action pair as an
equivalent terminal source.  In a continually refining predictive quotient that
can create frontier mass faster than it is consumed.  This policy instead gives
priority to the deepest *already evidenced* frontier and uses only known modal
transitions to navigate there.

No unknown successor, game coordinate, reward, completion percentage, or oracle
state is read.  Depth comes from the representative real action history stored
when a predictive state was first evidenced.
"""
from __future__ import annotations

from collections import deque

from .core import _learner_num_actions, _learner_state_to_id, modal_successors
from .exploration import CountUncertaintyPolicy, ExplorationDecision


def _terminal_state(learner, q):
    observations = getattr(learner, "state_observation", None)
    if observations is None or not 0 <= int(q) < len(observations):
        return False
    observation = observations[int(q)]
    return (
        isinstance(observation, tuple)
        and len(observation) >= 2
        and observation[0] == "terminal"
    )


def _frontier_depth(learner, q):
    if hasattr(learner, "frontier_depth"):
        return int(learner.frontier_depth(int(q)))
    histories = getattr(learner, "representative_history", None)
    if histories is not None and 0 <= int(q) < len(histories):
        return len(histories[int(q)])
    return 0


def _path_to(target, start, previous, previous_action):
    actions = []
    states = [int(target)]
    q = int(target)
    while q != int(start):
        actions.append(int(previous_action[q]))
        q = int(previous[q])
        states.append(q)
    actions.reverse()
    states.reverse()
    return tuple(actions), tuple(states)


class ContinuationFrontierPolicy:
    """Navigate to the deepest reachable untried boundary, then extend it.

    Candidate frontier state q is ranked lexicographically by

        (evidenced_depth(q), -known_route_length(q), -q).

    Once q is selected, an untried primitive at q is appended to the known route.
    Thus a shallow local untried action no longer automatically dominates a
    known route to a deeper frontier.  The returned telemetry includes the full
    planned primitive prefix so reusable tools may be invoked only when their
    expansion is a prefix of that plan.
    """

    name = "continuation_frontier"

    def __init__(self):
        self.last_telemetry = None
        self._fallback = CountUncertaintyPolicy()

    def choose(self, learner, world_state, task, memory):
        state_ids = _learner_state_to_id(learner)
        if world_state not in state_ids:
            raise ValueError("current predictive state is not known")
        start = int(state_ids[world_state])
        action_count = _learner_num_actions(learner)

        queue = deque([start])
        previous = {start: None}
        previous_action = {}
        distance = {start: 0}
        frontiers = []

        while queue:
            u = queue.popleft()
            if not _terminal_state(learner, u):
                unknown = tuple(
                    a for a in range(action_count)
                    if learner.action_visits.get((u, a), 0) == 0
                )
                if unknown:
                    frontiers.append((
                        _frontier_depth(learner, u),
                        -distance[u],
                        -u,
                        u,
                        unknown,
                    ))

            for action, v in sorted(modal_successors(learner, u).items()):
                v = int(v)
                if v in previous or _terminal_state(learner, v):
                    continue
                previous[v] = u
                previous_action[v] = int(action)
                distance[v] = distance[u] + 1
                queue.append(v)

        if not frontiers:
            decision = self._fallback.choose(learner, world_state, task, memory)
            decision.policy = self.name
            decision.reason = "no reachable untried boundary; local count fallback"
            self.last_telemetry = {
                "planned_actions": (int(decision.action),),
                "target_state": None,
                "target_action": int(decision.action),
                "target_depth": None,
                "route_length": 0,
                "reachable_states": len(previous),
                "frontier_states": 0,
                "bypassed_local_frontier": False,
            }
            return decision

        _, _, _, target, unknown = max(frontiers)
        target_action = min(
            unknown,
            key=lambda a: (learner.action_visits.get((target, a), 0), a),
        )
        route_actions, route_states = _path_to(
            target, start, previous, previous_action)
        planned = route_actions + (int(target_action),)
        selected = int(planned[0])

        local_unknown = any(
            learner.action_visits.get((start, a), 0) == 0
            for a in range(action_count)
        )
        bypassed = bool(target != start and local_unknown)
        target_depth = _frontier_depth(learner, target)
        self.last_telemetry = {
            "planned_actions": planned,
            "route_states": route_states,
            "target_state": int(target),
            "target_action": int(target_action),
            "target_depth": int(target_depth),
            "current_depth": int(_frontier_depth(learner, start)),
            "route_length": len(route_actions),
            "reachable_states": len(previous),
            "frontier_states": len(frontiers),
            "bypassed_local_frontier": bypassed,
        }
        return ExplorationDecision(
            action=selected,
            policy=self.name,
            target_frontier=int(target),
            score={int(target_action): float(target_depth)},
            reason=(
                "follow known route to deepest evidenced frontier"
                if route_actions
                else "extend deepest evidenced frontier"
            ),
        )
