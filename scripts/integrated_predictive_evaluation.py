"""External measurements for frozen models. No fitting or experiment selection.

The neutral reasoner below operates only on exported observed relations. It
does not call either MORTRA reasoner. Its guarantees are model-relative.
"""
from __future__ import annotations

from collections import Counter, defaultdict, deque
from fractions import Fraction
import sys
import time

import numpy as np

from mortra_predictive_perception.core import _Node, UnknownActionResponse
from mortra_predictive_perception.evaluation import partition_quality

UNKNOWN = -1


def heap_bytes(value, seen=None):
    seen = set() if seen is None else seen
    if id(value) in seen:
        return 0
    seen.add(id(value))
    size = sys.getsizeof(value)
    if isinstance(value, dict):
        size += sum(heap_bytes(k, seen) + heap_bytes(v, seen) for k, v in value.items())
    elif isinstance(value, (tuple, list, set, frozenset, deque)):
        size += sum(heap_bytes(v, seen) for v in value)
    elif isinstance(value, np.ndarray):
        if value.base is not None:
            size += heap_bytes(value.base, seen)
    elif hasattr(value, "__dict__") and not callable(value):
        size += heap_bytes(vars(value), seen)
    return size


class NeutralModel:
    """An independent export format shared by OLD and both NEW conditions."""
    def __init__(self, actions, labels, rows, initial):
        self.actions = tuple(actions)
        self.labels = dict(labels)
        self.rows = {key: frozenset(value) for key, value in rows.items()}
        self.initial = frozenset(initial)

    def begin(self, observation):
        return frozenset(s for s in self.initial if self.labels[s] == observation) or frozenset({UNKNOWN})

    def advance(self, belief, action, observation):
        successors = set()
        for s in belief:
            for v in self.rows.get((s, action), (UNKNOWN,)):
                if v == UNKNOWN or self.labels[v] == observation:
                    successors.add(v)
        return frozenset(successors)

    def branches(self, belief, action):
        # UNKNOWN permits every emission, including emissions not yet represented.
        known = defaultdict(set)
        unknown = False
        for s in belief:
            for v in self.rows.get((s, action), (UNKNOWN,)):
                if v == UNKNOWN:
                    unknown = True
                else:
                    known[self.labels[v]].add(v)
        result = {frozenset(states | ({UNKNOWN} if unknown else set())) for states in known.values()}
        if unknown:
            result.add(frozenset({UNKNOWN}))
        return frozenset(result)

    def solve(self, initial, goals):
        """Finite closure followed by the least guaranteed-reachability attractor."""
        started = time.process_time()
        if not initial:
            return {"ranks": {}, "policy": {}, "cpu_seconds": time.process_time()-started,
                    "belief_nodes": 0, "method": "MODEL CONTRADICTION"}
        frontier, seen, transitions = deque([initial]), {initial}, {}
        while frontier:
            belief = frontier.popleft()
            for a in self.actions:
                branches = self.branches(belief, a)
                transitions[belief, a] = branches
                for following in branches:
                    if following not in seen:
                        seen.add(following)
                        frontier.append(following)
        ranks = {b: 0 for b in seen if b and UNKNOWN not in b and b <= goals}
        policy = {}
        while True:
            additions = {}
            for b in seen - ranks.keys():
                options = [(1 + max(ranks[v] for v in transitions[b, a]), a)
                           for a in self.actions if transitions[b, a]
                           and all(v in ranks for v in transitions[b, a])]
                if options:
                    distance, action = min(options)
                    additions[b] = distance
                    policy[b] = action
            if not additions:
                break
            ranks.update(additions)
        return {"ranks": ranks, "policy": policy, "cpu_seconds": time.process_time()-started,
                "belief_nodes": len(seen), "method": "exact belief least fixed point"}


def audit_operator(labels, availability, counts, blocks, quotient_rows):
    """Independently compute the action-wise projected row residual with rationals."""
    residual = Fraction(0)
    checked = 0
    for (s, a), successors in counts.items():
        projected = defaultdict(Fraction)
        total = sum(successors.values())
        for v, count in successors.items():
            projected[blocks[v]] += Fraction(count, total)
        row = quotient_rows[blocks[s], a]
        residual = max(residual, sum((abs(projected.get(v, 0) - row.get(v, 0))
                                     for v in projected.keys() | row.keys()), Fraction(0)))
        checked += 1
    groups = defaultdict(list)
    for s, block in enumerate(blocks):
        groups[block].append(s)
    availability_preserved = all(len({tuple(availability[s]) for s in group}) == 1 for group in groups.values())
    observations_preserved = all(len({labels[s] for s in group}) == 1 for group in groups.values())
    return {"eps_action": float(residual), "exact_residual": str(residual), "checked_action_rows": checked,
            "availability_preserved": availability_preserved, "observations_preserved": observations_preserved,
            "scope": "observed empirical operator only; no claim about unobserved true transitions"}


def old_contexts(episodes, model):
    sequences = []
    for observations, actions in episodes:
        context = (int(observations[0][0]),)
        seq = [model.encode(context)]
        for action, obs in zip(actions, observations[1:], strict=True):
            context = (context + (int(action), int(obs[0])))[-(2 * model.max_depth + 1):]
            seq.append(model.encode(context))
        sequences.append(seq)
    return sequences


def new_symbols(model, episodes):
    return [[model.encode_history(obs[:t+1], actions[:t]) for t in range(len(obs))]
            for obs, actions in episodes]


def available_depths(model, episodes):
    histogram = Counter()
    for observations, actions in episodes:
        for t in range(len(actions)):
            node, depth = model.tree, 0
            while isinstance(node, _Node):
                value, valid = model._feature_value_from_history(node.spec, observations, actions, t)
                if valid:
                    depth = max(depth, node.spec.lag)
                    node = node.left if value <= node.threshold else node.right
                else:
                    node = node.left if node.missing_left else node.right
            histogram[depth] += 1
    return dict(sorted(histogram.items()))


def old_response_means(episodes, assignments):
    data = defaultdict(list)
    for (observations, actions), symbols in zip(episodes, assignments, strict=True):
        for t, action in enumerate(actions):
            if symbols[t] is not None:
                data[symbols[t], int(action)].append(observations[t+1] - observations[t])
    return {key: np.mean(values, axis=0) for key, values in data.items()}


def response_error(episodes, assignments, predict, target):
    sse = 0.0
    predicted = unpredicted = scalars = 0
    for (observations, actions), symbols in zip(episodes, assignments, strict=True):
        for t, action in enumerate(actions):
            try:
                estimate = predict(symbols[t], int(action))
            except (KeyError, UnknownActionResponse):
                unpredicted += 1
                continue
            if target == "delta":
                estimate = estimate + observations[t]
            residual = observations[t+1] - estimate
            sse += float(np.sum(residual * residual))
            scalars += len(residual)
            predicted += 1
    return {"future_error": sse/scalars if scalars else None, "response_sse": sse,
            "predicted_scalars": scalars, "predicted_transitions": predicted,
            "unpredicted_transitions": unpredicted,
            "prediction_coverage": predicted/(predicted+unpredicted) if predicted+unpredicted else None,
            "response_error_definition": "held-out next raw observation MSE in unnormalized units; unknown responses not imputed"}


def memory_records(world, episodes, symbols):
    records, beliefs = [], []
    recursive_cpu = replay_cpu = 0.0
    for episode, ((obs, acts), seq) in enumerate(zip(episodes, symbols, strict=True)):
        start = time.process_time()
        belief = world.begin(seq[0])
        recursive_cpu += time.process_time()-start
        current = []
        for t, symbol in enumerate(seq):
            if t:
                start = time.process_time()
                belief = world.update(belief, int(acts[t-1]), symbol)
                recursive_cpu += time.process_time()-start
            start = time.process_time()
            reconstructed = world.reconstruct(seq[:t+1], acts[:t])
            replay_cpu += time.process_time()-start
            records.append({"episode": episode, "step": t, "agrees": belief == reconstructed,
                            "belief_size": len(belief), "unknown": UNKNOWN in belief,
                            "contradiction": not belief, "belief": sorted(belief),
                            "full_history_belief": sorted(reconstructed)})
            current.append(belief)
        beliefs.append(current)
    return records, beliefs, {"recursive_belief_cpu": recursive_cpu, "independent_replay_cpu": replay_cpu}


def common_partition(assignments, true_classes):
    result = partition_quality(assignments, true_classes)
    result["learned_same_pairs"] = result["over_merge_denominator"]
    result["true_same_pairs"] = result["over_split_denominator"]
    result["true_different_pairs"] = result["pairs"] - result["true_same_pairs"]
    result["predictive_violation"] = result["over_merge_rate"]
    result["false_merge"] = (result["over_merge_pairs"] / result["true_different_pairs"]
                             if result["true_different_pairs"] else None)
    result["false_split"] = result["over_split_rate"]
    return result


def ambiguity_diagnostics(raw, truth, assignments):
    groups = defaultdict(list)
    for i, row in enumerate(raw):
        groups[tuple(map(float, row))].append(i)
    pair_cases = collisions = 0
    participating = set()
    for indices in groups.values():
        if len({truth[i] for i in indices}) < 2:
            continue
        participating.update(indices)
        quality = common_partition([assignments[i] for i in indices], [truth[i] for i in indices])
        pair_cases += quality["true_different_pairs"]
        collisions += quality["over_merge_pairs"]
    return {"same_observation_different_future_pairs": pair_cases,
            "history_occurrences_in_ambiguous_groups": len(participating),
            "collision_pairs": collisions,
            "collision_rate": collisions/pair_cases if pair_cases else None}, participating


def raw_support_by_state(episodes, assignments):
    support = defaultdict(set)
    for (obs, _), seq in zip(episodes, assignments, strict=True):
        for row, state in zip(obs, seq, strict=True):
            if state is not None:
                support[state].add(tuple(map(float, row)))
    return dict(support)


def future_support_quality(episodes, states, view, raw_support, selected_indices):
    checked = correct = excluded = ambiguous = unknown = 0
    index = 0
    for (obs, actions), seq in zip(episodes, states, strict=True):
        for t, action in enumerate(actions):
            if index in selected_indices:
                current = seq[t]
                belief = current if isinstance(current, frozenset) else frozenset({current if current is not None else UNKNOWN})
                destinations = set()
                for state in belief:
                    destinations.update(view.rows.get((state, int(action)), {UNKNOWN}))
                prediction = set().union(*(raw_support.get(s, set()) for s in destinations))
                checked += 1
                if UNKNOWN in destinations or not belief or not prediction:
                    unknown += 1
                else:
                    correct += tuple(map(float, obs[t+1])) in prediction
                    excluded += tuple(map(float, obs[t+1])) not in prediction
                    ambiguous += len(prediction) > 1
            index += 1
        index += 1
    return {"cases": checked, "correct_supported_next_observation": correct,
            "excluded_actual_observation": excluded, "unknown_prediction": unknown,
            "ambiguous_prediction": ambiguous,
            "correct_fraction_all_cases": correct/checked if checked else None}


def task_goal_states(raw_support, goal):
    # A task readout is supplied after model fitting. Mixed observed task truth
    # cannot certify a whole model state as a target.
    targets = {s for s, observations in raw_support.items()
               if observations and all(row[0] == goal for row in observations)}
    mixed = sum(any(row[0] == goal for row in rows) and any(row[0] != goal for row in rows)
                for rows in raw_support.values())
    return targets, mixed


def neutral_rollouts(view, encode, table, observations, goals, raw_support, horizon):
    successes = at_reset = predicted_guarantees = 0
    steps, distances = [], []
    cpu = 0.0
    details = []
    for goal in goals:
        raw = [np.array([float(observations[0])])]
        actions, hidden = [], 0
        initial = view.begin(encode(raw, actions))
        targets, mixed = task_goal_states(raw_support, goal)
        solved = view.solve(initial, targets)
        cpu += solved["cpu_seconds"]
        guaranteed = initial in solved["ranks"]
        predicted_guarantees += guaranteed
        distance = solved["ranks"].get(initial)
        if distance is not None:
            distances.append(distance)
        belief = initial
        for t in range(horizon+1):
            if int(observations[hidden]) == goal:
                successes += 1
                at_reset += t == 0
                steps.append(t)
                break
            if t == horizon or belief not in solved["policy"]:
                break
            action = solved["policy"][belief]
            hidden = int(table[hidden, action])
            actions.append(action)
            raw.append(np.array([float(observations[hidden])]))
            belief = view.advance(belief, action, encode(raw, actions))
        details.append({"goal": goal, "guaranteed_in_model": guaranteed, "guaranteed_steps": distance,
                        "actual_success": int(observations[hidden]) == goal, "actions": actions,
                        "goal_mixed_states": mixed})
    return {"successes": successes, "trials": len(goals), "success": successes/len(goals) if goals else None,
            "success_at_reset": at_reset, "model_guaranteed_tasks": predicted_guarantees,
            "mean_guaranteed_steps": float(np.mean(distances)) if distances else None,
            "mean_actual_success_steps": float(np.mean(steps)) if steps else None,
            "reasoning_cpu": cpu, "tasks": details, "method": "external exact belief reachability (singleton case is graph reachability)"}


def new_rollouts(world, perception, table, observations, goals, raw_support, horizon):
    successes = at_reset = 0
    cpu = 0.0
    details = []
    for goal in goals:
        raw, actions, hidden = [np.array([float(observations[0])])], [], 0
        belief = world.begin(perception.encode_history(raw, actions))
        targets, mixed = task_goal_states(raw_support, goal)
        cache = {}
        statuses = []
        for t in range(horizon+1):
            if int(observations[hidden]) == goal:
                successes += 1
                at_reset += t == 0
                break
            if t == horizon:
                break
            if belief not in cache:
                started = time.process_time()
                plan = world.plan(belief, targets)
                if not plan.actions and plan.guaranteed_steps is None:
                    plan = world.identify(belief)
                cpu += time.process_time()-started
                cache[belief] = plan
            plan = cache[belief]
            statuses.append(plan.status)
            if not plan.actions:
                break
            action = min(plan.actions)
            hidden = int(table[hidden, action])
            actions.append(action)
            raw.append(np.array([float(observations[hidden])]))
            belief = world.update(belief, action, perception.encode_history(raw, actions))
        details.append({"goal": goal, "actual_success": int(observations[hidden]) == goal,
                        "actions": actions, "statuses": statuses, "goal_mixed_states": mixed})
    return {"successes": successes, "trials": len(goals), "success": successes/len(goals) if goals else None,
            "success_at_reset": at_reset, "reasoning_cpu": cpu, "tasks": details,
            "scope": "frozen observed model, not an all-possible-worlds guarantee"}
