"""Task sampling, isolated diagnostics and unchanged frozen-core graph reuse."""
from collections import Counter
import copy
import hashlib
import math
import pickle
import random
import statistics
import time
from types import FunctionType

import numpy as np

from experiments.game_frontier_v1.frozen import StructuralLearner, run_fixed_field_policy, solve_fixed_field
from experiments.game_frontier_v1.player import fingerprint
from experiments.game_frontier_v1.runner import derive
from .world import Engine, OpaqueMap, canonical, distances, oracle

BINS = ("4-7", "8-15", "16-31", "32+")


def distance_bin(d):
    return 0 if d < 8 else 1 if d < 16 else 2 if d < 32 else 3


def sample_tasks(graph, count, seed):
    states, edges, _ = graph
    rng = random.Random(seed)
    pools, totals = [[] for _ in BINS], [0] * 4
    # Reservoir per distance bin: no all-pairs table is materialized.
    for u in range(len(states)):
        for v, d in distances(edges, u).items():
            if d < 4:
                continue
            b = distance_bin(d)
            totals[b] += 1
            row = {"start": list(states[u]), "target": list(states[v]), "distance": d, "bin": BINS[b]}
            if len(pools[b]) < count:
                pools[b].append(row)
            else:
                j = rng.randrange(totals[b])
                if j < count:
                    pools[b][j] = row
    for pool in pools:
        rng.shuffle(pool)
    tasks = []
    for pool in pools:
        take = min(count // 4, len(pool))
        tasks.extend(pool[:take])
        del pool[:take]
    remaining = [r for pool in pools for r in pool]
    rng.shuffle(remaining)
    tasks.extend(remaining[:count - len(tasks)])
    rng.shuffle(tasks)
    for i, task in enumerate(tasks):
        task["task_id"] = i
        task["rng_seed"] = derive(seed, i, "readout") % (2**32)
    return tasks, dict(zip(BINS, totals))


class Port:
    __slots__ = ("reset", "step", "num_actions", "current_observation", "available_actions")


def make_port(engine, labels, trace=None):
    state = [engine.initial]
    reverse = {v: s for s, v in labels.states.items()}
    def encode(s):
        value = labels.encode(s)
        reverse[value] = s
        return value
    def reset(label=None):
        state[0] = engine.initial if label is None else reverse[label]
        if trace is not None:
            trace.clear()
            trace.update(actions=[], states=[list(state[0])])
        return encode(state[0])
    def step(a):
        state[0] = engine.step(state[0], int(a))
        if trace is not None:
            trace["actions"].append(int(a))
            trace["states"].append(list(state[0]))
        return encode(state[0])
    port = Port()
    port.reset, port.step, port.num_actions = reset, step, engine.num_actions
    port.current_observation = lambda: encode(state[0])
    port.available_actions = lambda: tuple(range(engine.num_actions))
    return port


def evaluate_tasks(learner, engine, labels, tasks, horizon, cache_enabled=True):
    """Same original function bytecode. Memoize identical fixed-field requests only."""
    t0 = time.process_time()
    original_fingerprint = fingerprint(learner)
    K = learner.build_k_support()
    K_digest = hashlib.sha256(K.tobytes()).hexdigest()
    cache, solves = {}, []
    solve_cpu = [0.0]
    def cached_solver(k, target, **kwargs):
        assert k is K
        if not cache_enabled or target not in cache:
            start = time.process_time()
            value = solve_fixed_field(k, target, **kwargs)
            solve_cpu[0] += time.process_time() - start
            cache[target] = value
            solves.append({"target_node": target, "iterations": value[1], "residual": value[2], "converged": value[3]})
        return cache[target]
    namespace = dict(run_fixed_field_policy.__globals__)
    namespace["solve_fixed_field"] = cached_solver
    policy = FunctionType(run_fixed_field_policy.__code__, namespace, run_fixed_field_policy.__name__, run_fixed_field_policy.__defaults__)
    # Task state IDs are public objective inputs, never added to the learned graph.
    for task in tasks:
        labels.encode(tuple(task["start"]))
        labels.encode(tuple(task["target"]))
    trace = {}
    port = make_port(engine, labels, trace)
    records = []
    old_rng = np.random.get_state()
    try:
        for task in tasks:
            before = fingerprint(learner)
            assert before == original_fingerprint
            start = labels.encode(tuple(task["start"]))
            target = labels.encode(tuple(task["target"]))
            port.reset(start)
            np.random.seed(task["rng_seed"])
            success, reported_steps, reason = policy(port, start, target, K, learner.state_to_id, learner.counts, max_steps=horizon)
            assert fingerprint(learner) == before
            assert success == (port.current_observation() == target)
            row = {"task_id": task["task_id"], "success": bool(success), "core_reported_steps": reported_steps,
                   "actual_actions": len(trace["actions"]), "reason": reason,
                   "trajectory_sha256": hashlib.sha256(canonical(trace).encode()).hexdigest()}
            if task["task_id"] == 0:
                row["recorded_trajectory"] = copy.deepcopy(trace)
            records.append(row)
    finally:
        np.random.set_state(old_rng)
    assert K_digest == hashlib.sha256(K.tobytes()).hexdigest()
    successes = sum(r["success"] for r in records)
    per_bin = {}
    for name in BINS:
        rows = [r for r, task in zip(records, tasks) if task["bin"] == name]
        per_bin[name] = {"tasks": len(rows), "successes": sum(r["success"] for r in rows)}
    return {"success_rate": successes / len(tasks), "successes": successes, "tasks": len(tasks),
            "median_success_steps": statistics.median([r["actual_actions"] for r in records if r["success"]]) if successes else 0,
            "task_results": records, "success_by_distance_bin": per_bin, "K_sha256": K_digest, "K_bytes": K.nbytes,
            "K_nonzero": int(np.count_nonzero(K)), "learner_fingerprint": original_fingerprint,
            "graph_reuse_verified": True, "evaluation_updates": 0, "q": .90, "psi_cutoff": 1e-7,
            "solver_calls": solves, "solver_cpu_seconds": solve_cpu[0], "cpu_seconds": time.process_time() - t0}


def full_information(engine, graph, tasks, horizon, seed):
    t0 = time.process_time()
    states, edges, _ = graph
    labels = OpaqueMap(seed)
    learner = StructuralLearner(engine.num_actions)
    for s in states:
        learner.get_or_add_id(labels.encode(s))
    for u, row in enumerate(edges):
        for a, v in enumerate(row):
            learner.record_transition(u, a, v)
    result = evaluate_tasks(learner, engine, labels, tasks, horizon)
    result["diagnostic_total_cpu_seconds"] = time.process_time() - t0
    return result


def learn(engine, tasks, checkpoints, horizon, seed, oracle_stats):
    labels = OpaqueMap(seed)
    train = make_port(engine, labels)
    learner = StructuralLearner(engine.num_actions)
    u = learner.get_or_add_id(train.reset())
    previous, cpu = 0, 0.0
    rows = []
    for budget in checkpoints:
        t0 = time.process_time()
        for _ in range(previous, budget):
            a = learner.select_action(u)
            v = learner.get_or_add_id(train.step(a))
            learner.record_transition(u, a, v)
            u = v
        cpu += time.process_time() - t0
        obs = train.current_observation()
        evaluation = evaluate_tasks(learner, engine, labels, tasks, horizon)
        assert train.current_observation() == obs
        rows.append({"budget": budget, "evaluation": evaluation, "training_cpu_seconds": cpu,
                     "learned_states": len(learner.id_to_state), "learned_transitions": len(learner.counts),
                     "state_coverage": len(learner.id_to_state) / oracle_stats["reachable_states"],
                     "edge_coverage": len(learner.counts) / oracle_stats["transition_edges"],
                     "learner_serialized_bytes": len(pickle.dumps(learner.__dict__, protocol=5))})
        previous = budget
    return rows


def curve_metrics(rows):
    rates = [r["evaluation"]["success_rate"] for r in rows]
    budgets = [r["budget"] for r in rows]
    D = sum((math.log2(budgets[i + 1]) - math.log2(budgets[i])) * (2 - rates[i] - rates[i + 1]) / 2 for i in range(len(rows) - 1))
    return {"D": D, **{f"B{pct}": next((b for b, s in zip(budgets, rates) if s >= pct / 100), None) for pct in (50, 80, 90)},
            "final_success": rates[-1], "median_success_steps": rows[-1]["evaluation"]["median_success_steps"]}


def rule_relevance(genome, tasks, cap):
    t0 = time.process_time()
    roots = list(dict.fromkeys(tuple(t["start"]) for t in tasks))
    records = []
    for i in range(len(genome["rules"])):
        g = copy.deepcopy(genome)
        g["rules"].pop(i)
        status, graph = oracle(Engine(g), cap, roots)
        if graph is None:
            records.append({"rule": i, "status": "UNRESOLVED", "fraction": None})
            continue
        _, edges, ids = graph
        all_d = {s: distances(edges, ids[s]) for s in roots}
        changed = 0
        for task in tasks:
            target = ids.get(tuple(task["target"]))
            d = all_d[tuple(task["start"])].get(target)
            changed += d != task["distance"]
        records.append({"rule": i, "status": "COMPLETE", "changed_tasks": changed, "tasks": len(tasks), "fraction": changed / len(tasks)})
    values = [r["fraction"] for r in records if r["fraction"] is not None]
    return {"rules": records, "nonzero_relevance": any(v > 0 for v in values),
            "mean_fraction": statistics.mean(values) if values else None, "cpu_seconds": time.process_time() - t0}
