"""Policy-only experiment against the current Congruence working-tree source.

The original builder is split mechanically at its existing merge_map statement.
Its classifier, predictive merging, K construction and purity code are compiled
verbatim. Only the collection loop is replaced to expose action selection and
to defer goal labeling until collection has stopped. Generated functions are
exported with the experiment for inspection, and compared against the baseline
by regression tests. This is infrastructure, not an acquired MORTRA algorithm.
"""
from __future__ import annotations

import argparse
import ast
import copy
import ctypes
import gzip
import hashlib
import inspect
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from collections import Counter, defaultdict, deque
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
from types import FunctionType

import numpy as np
from scripts import evaluate_fixed_field_congruence as base

ROOT = Path(__file__).resolve().parents[1]
MODES = ("random", "structural", "active", "u_only", "nearest_unseen")
BUILDER_SOURCE = inspect.getsource(base.build_predictive_graph)


def hash_file(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def save_json(path, data):
    Path(path).write_text(json.dumps(data, indent=2, ensure_ascii=True, allow_nan=False), encoding="utf-8")


def deep_bytes(obj, seen=None):
    seen = set() if seen is None else seen
    if id(obj) in seen:
        return 0
    seen.add(id(obj))
    n = sys.getsizeof(obj)
    if isinstance(obj, dict):
        n += sum(deep_bytes(k, seen) + deep_bytes(v, seen) for k, v in obj.items())
    elif isinstance(obj, (list, tuple, set, deque)):
        n += sum(deep_bytes(v, seen) for v in obj)
    return n


class Policy:
    """Opaque-ID interface: choose(state), observe(state, action, successor)."""
    def __init__(self, actions, seed, mode):
        if mode not in MODES:
            raise ValueError(mode)
        self.actions = tuple(range(actions))
        self.rng = random.Random(seed)
        self.mode = mode
        self.counts = Counter()
        self.visits = Counter()
        self.successors = defaultdict(Counter)
        self.graph = defaultdict(dict)
        self.states = set()
        self.target = None
        self.replans = 0
        self.candidates_scored = 0
        self.path_invalidations = 0
        self.values = {}

    def observe(self, s, a, v):
        self.states.update((s, v))
        self.visits[s] += 1
        self.counts[s, a] += 1
        self.successors[s, a][v] += 1
        # Same first-observed tie rule as the original modal transition builder.
        self.graph[s][a] = max(self.successors[s, a], key=self.successors[s, a].get)
        self.values[s, a] = self.uncertainty(s, a)

    def uncertainty(self, s, a):
        n = self.counts[s, a]
        if not n:
            return 1.0 + 1.0 + 1.0 + 0.0
        hist = self.successors[s, a]
        entropy = (-sum((v / n) * math.log(v / n) for v in hist.values())
                   / math.log(len(hist))) if len(hist) > 1 else 0.0
        # Disagreement inside this constructed state only, no invented partition.
        distinction = 1.0 - max(hist.values()) / n
        return 1.0 / math.sqrt(1.0 + n) + entropy + distinction

    def routes(self, current):
        dist, first = {current: 0}, {}
        queue = deque([current])
        while queue:
            u = queue.popleft()
            for a in self.actions:
                for v in self.successors.get((u, a), {}):
                    if v not in dist:
                        dist[v] = dist[u] + 1
                        first[v] = a if u == current else first[u]
                        queue.append(v)
        return dist, first

    def choose(self, current):
        self.states.add(current)
        if self.mode == "random":
            return self.rng.choice(self.actions)
        if self.mode == "structural":
            return min(self.actions, key=lambda a: self.counts[current, a])
        dist, first = self.routes(current)
        if self.target is not None:
            s, a = self.target
            if s == current:
                self.target = None
                return a
            if s in dist:
                return first[s]
            self.path_invalidations += 1
            self.target = None
        self.replans += 1
        candidates = []
        for s in sorted(dist):
            for a in self.actions:
                self.candidates_scored += 1
                if self.mode == "nearest_unseen":
                    if self.counts[s, a]:
                        continue
                    score = 1.0 / (1 + dist[s])
                else:
                    score = self.values.get((s, a), 3.0)
                    if self.mode == "active":
                        score /= 1 + dist[s]
                candidates.append((-score, s, a))
        if not candidates:
            return min(self.actions, key=lambda a: self.counts[current, a])
        _, s, a = min(candidates)
        if s == current:
            return a
        self.target = (s, a)
        return first[s]


def original_fragments():
    """No rewriting inside the state encoder or the predictive/K finalizer."""
    tree = ast.parse(BUILDER_SOURCE).body[0]
    lines = BUILDER_SOURCE.splitlines(keepends=True)
    def segment(start, end):
        return "".join(lines[start - 1:end])
    action_line = next(n.lineno for n in tree.body if isinstance(n, ast.Assign)
                       and any(isinstance(t, ast.Name) and t.id == "action_visits" for t in n.targets))
    merge_line = next(n.lineno for n in tree.body if isinstance(n, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "merge_map" for t in n.targets))
    classifier = ("def make_classifier(vis_thresh=0.52, explore_steps=0):\n"
                  + segment(2, action_line - 1)
                  + "    return get_provisional_cluster, prototypes, proto_counts\n")
    finalizer = ("def finish_model(prototypes, transitions_raw, goal_clusters, cluster_to_gt, "
                 "gt_to_cluster, get_provisional_cluster):\n" + segment(merge_line, tree.end_lineno))
    namespace = dict(vars(base))
    exec(compile(classifier + "\n" + finalizer, "<verbatim-congruence-fragments>", "exec"), namespace)
    return namespace["make_classifier"], namespace["finish_model"], classifier + "\n" + finalizer


make_classifier, finish_model, EXTRACTED_SOURCE = original_fragments()


def with_action_count(fn, count):
    """Same code object, explicit action alphabet for generic finite-system tests."""
    namespace = dict(fn.__globals__)
    namespace["NUM_ACTIONS"] = count
    return FunctionType(fn.__code__, namespace, fn.__name__, fn.__defaults__, fn.__closure__)


class WorldView:
    def __init__(self, world, permutation=None, predicate=None):
        self.world = world
        self.permutation = tuple(range(base.NUM_ACTIONS)) if permutation is None else tuple(permutation)
        self.predicate = predicate

    def __getattr__(self, name):
        return getattr(self.world, name)

    def step(self, state, action):
        return self.world.step(state, self.permutation[action])

    def is_goal(self, state):
        return self.world.is_goal(state) if self.predicate is None else self.predicate(state)


def true_graph(world, actions):
    start = world.get_initial_state()
    states, edges, triples = {start}, set(), set()
    queue = deque([start])
    while queue:
        s = queue.popleft()
        for a in range(actions):
            v = world.step(s, a)
            edges.add((s, v))
            triples.add((s, a, v))
            if v not in states:
                states.add(v)
                queue.append(v)
    return states, edges, triples


class UnionFind:
    def __init__(self):
        self.parent = {}
        self.size = {}
        self.largest = 0

    def add(self, u):
        if u not in self.parent:
            self.parent[u] = u
            self.size[u] = 1
            self.largest = max(1, self.largest)

    def root(self, u):
        while self.parent[u] != u:
            self.parent[u] = self.parent[self.parent[u]]
            u = self.parent[u]
        return u

    def join(self, u, v):
        self.add(u)
        self.add(v)
        u, v = self.root(u), self.root(v)
        if u != v:
            self.parent[v] = u
            self.size[u] += self.size[v]
            self.largest = max(self.largest, self.size[u])


def rss_bytes():
    if os.name == "nt":
        class Counters(ctypes.Structure):
            _fields_ = [("cb", ctypes.c_ulong), ("faults", ctypes.c_ulong)] + [
                (k, ctypes.c_size_t) for k in ("peak", "working", "quota_peak_paged", "quota_paged",
                                             "quota_peak_nonpaged", "quota_nonpaged", "pagefile", "peak_pagefile")]
        counters = Counters()
        counters.cb = ctypes.sizeof(counters)
        kernel = ctypes.windll.kernel32
        kernel.GetCurrentProcess.restype = ctypes.c_void_p
        ok = ctypes.windll.psapi.GetProcessMemoryInfo(ctypes.c_void_p(kernel.GetCurrentProcess()),
                                                    ctypes.byref(counters), counters.cb)
        return int(counters.working) if ok else None
    return None


class RandomLabels:
    """Seeded injective random renaming, without inspecting future state IDs."""
    def __init__(self, seed):
        self.rng = random.Random(seed)
        self.labels = {}
        self.used = set()

    def __call__(self, state):
        if state not in self.labels:
            value = self.rng.getrandbits(63)
            while value in self.used:
                value = self.rng.getrandbits(63)
            self.labels[state] = value
            self.used.add(value)
        return self.labels[state]


class Collection:
    """Evaluator owns observations/ground truth. Policy never receives this object."""
    def __init__(self, world, policy, rng_seed, surface=False):
        self.world = world
        self.policy = policy
        self.label = RandomLabels(rng_seed + 500000) if surface else (lambda c: c)
        self.classify, self.prototypes, self.proto_counts = make_classifier()
        np.random.seed(rng_seed)
        self.state = world.get_initial_state()
        self.cluster = self.classify(base.render_visual_frame(world, self.state, 0))
        self.raw = defaultdict(lambda: defaultdict(lambda: defaultdict(int)))
        self.cluster_gt = defaultdict(lambda: defaultdict(int))
        self.gt_cluster = defaultdict(lambda: defaultdict(int))
        self.observations = [(self.cluster, self.state)]
        self.true_states = {self.state}
        self.true_edges, self.true_triples = set(), set()
        self.edges, self.relations, self.pairs = set(), set(), set()
        self.components = UnionFind()
        self.components.add(self.cluster)
        self.elapsed = self.cpu = self.instrumentation = 0.0
        self.step_count = 0

    def step(self):
        wall, cpu = time.perf_counter(), time.process_time()
        s, c = self.state, self.cluster
        self.cluster_gt[c][s] += 1
        self.gt_cluster[s][c] += 1
        a = self.policy.choose(self.label(c))
        v = self.world.step(s, a)
        self.step_count += 1
        cv = self.classify(base.render_visual_frame(self.world, v, self.step_count))
        self.raw[c][a][cv] += 1
        self.policy.observe(self.label(c), a, self.label(cv))
        self.state, self.cluster = v, cv
        self.elapsed += time.perf_counter() - wall
        self.cpu += time.process_time() - cpu
        start = time.perf_counter()
        self.observations.append((cv, v))
        self.true_states.add(v)
        self.true_edges.add((s, v))
        self.true_triples.add((s, a, v))
        self.edges.add((c, cv))
        self.relations.add((c, a, cv))
        self.pairs.add((c, a))
        self.components.join(c, cv)
        row = {"step": self.step_count, "state_id": self.label(c), "action_id": a,
               "successor_id": self.label(cv), "policy_target": self.policy.target,
               "constructed_states": len(self.prototypes),
               "state_action_pairs": len(self.pairs), "successor_relations": len(self.relations),
               "edges": len(self.edges), "largest_weak_component": self.components.largest,
               "quotient_states": None, "partition_changes": None,
               "quotient_status": "not_constructed_during_exploration",
               "true_states": len(self.true_states), "true_edges": len(self.true_edges),
               "true_transitions": len(self.true_triples), "process_rss_bytes": rss_bytes(),
               "exploration_wall_seconds": self.elapsed, "exploration_cpu_seconds": self.cpu}
        self.instrumentation += time.perf_counter() - start
        return row

    def finish(self, predicate):
        # This is the first invocation of a task goal predicate.
        goals = {c for c, s in self.observations if predicate(s)}
        return finish_model(self.prototypes, copy.deepcopy(self.raw), goals,
                            self.cluster_gt, self.gt_cluster, self.classify)

    def model_bytes(self):
        return deep_bytes((self.prototypes, self.proto_counts, self.raw, vars(self.policy),
                           vars(self.label) if isinstance(self.label, RandomLabels) else {}))


def reachable(dest, start):
    graph = defaultdict(list)
    for (s, _), v in dest.items():
        graph[s].append(v)
    seen, queue = {start}, deque([start])
    while queue:
        for v in graph[queue.popleft()]:
            if v not in seen:
                seen.add(v)
                queue.append(v)
    return seen


def quotient_checked(pred, actions=5):
    fn = base.construct_congruence_quotient if actions == 5 else with_action_count(base.construct_congruence_quotient, actions)
    result = fn(pred["K"], pred["dest_map"], q=0.90, goal_indices=pred["goal_indices"])
    if not result["fixed_point_verified"] or result["eps_K"] > 1e-10 or result["eps_action"] > 1e-10:
        raise RuntimeError("Frozen quotient failed its certificate; do not silently use it.")
    return result


def timed_planning(world, pred, cong, trials, steps):
    timing = {"solver_cpu_seconds": 0.0, "solver_calls": 0}
    def solver(*args, **kwargs):
        start = time.process_time()
        result = base.solve_fixed_field(*args, **kwargs)
        timing["solver_cpu_seconds"] += time.process_time() - start
        timing["solver_calls"] += 1
        return result
    namespace = dict(base.evaluate_congruence_planning.__globals__)
    namespace["solve_fixed_field"] = solver
    original = base.evaluate_congruence_planning
    measured = FunctionType(original.__code__, namespace, original.__name__, original.__defaults__)
    return measured(world, pred, cong, trials=trials, max_play_steps=steps), timing


def evaluate_checkpoint(collection, row, truth, goals, config, eval_seed, model_path=None):
    rng_state = np.random.get_state()
    start_wall, start_cpu = time.perf_counter(), time.process_time()
    try:
        world = collection.world
        pred = collection.finish(world.is_goal)
        construction_cpu = time.process_time() - start_cpu
        t = time.process_time()
        cong = quotient_checked(pred)
        quotient_cpu = time.process_time() - t
        if model_path is not None:
            np.savez_compressed(model_path, K=pred["K"], C=cong["C"], K_bar=cong["K_bar"],
                                dest=np.array([(u, a, v) for (u, a), v in pred["dest_map"].items()], dtype=np.int64),
                                goal_indices=np.array(pred["goal_indices"], dtype=np.int64))
        np.random.seed(eval_seed)
        t = time.process_time()
        primary, timing = timed_planning(world, pred, cong, config["trials"], config["play_steps"])
        solver_cpu = timing["solver_cpu_seconds"]
        planning_cpu = time.process_time() - t
        initial_c = pred["get_canon"](collection.observations[0][0])
        reachable_indices = reachable(pred["dest_map"], pred["c_to_idx"].get(initial_c, -1))
        multi = []
        reasoning_cpu = 0.0
        for j, target in enumerate(goals):
            predicate = lambda s, target=target: (s[0], s[1]) == tuple(target)
            task_pred = dict(pred)
            task_pred["goal_indices"] = sorted({pred["c_to_idx"][pred["get_canon"](c)]
                for c, s in collection.observations if predicate(s)
                and pred["get_canon"](c) in pred["c_to_idx"]})
            # Same world model. Refine its quotient for each newly supplied goal.
            t = time.process_time()
            task_cong = quotient_checked(task_pred)
            quotient_cpu += time.process_time() - t
            goal_view = WorldView(world, predicate=predicate)
            np.random.seed(eval_seed + 100 + j)
            t = time.process_time()
            result, timing = timed_planning(goal_view, task_pred, task_cong, config["multi_trials"], config["play_steps"])
            solver_cpu += timing["solver_cpu_seconds"]
            reasoning_cpu += time.process_time() - t
            result.update(target=target, reachable=bool(set(task_pred["goal_indices"]) & reachable_indices))
            multi.append(result)
        states, edges, triples = truth
        return {**row, "edge_coverage": len(collection.true_edges) / len(edges),
                "transition_coverage": len(collection.true_triples) / len(triples),
                "state_coverage": len(collection.true_states) / len(states),
                "true_edge_denominator": len(edges), "true_state_denominator": len(states),
                "predictive_states": pred["N"], "quotient_states": cong["M"],
                "partition_changes": len(cong["refinement_history"]) - 1,
                "refinement_history": cong["refinement_history"], "quotient_status": "measured_after_exploration",
                "K_nonzero": int(np.count_nonzero(pred["K"])), "eps_K": cong["eps_K"],
                "eps_action": cong["eps_action"], "fixed_point_verified": cong["fixed_point_verified"],
                "success": primary["success_rate"], "mean_steps_original_zero_based": primary["mean_steps"],
                "multi_goal_success": float(np.mean([x["success_rate"] for x in multi])),
                "reachable_goal_fraction": float(np.mean([x["reachable"] for x in multi])), "goals": multi,
                "model_heap_bytes": collection.model_bytes(),
                "operator_heap_bytes": deep_bytes((pred["K"], pred["dest_map"], cong)),
                "evaluation_evidence_heap_bytes": deep_bytes((collection.observations, collection.cluster_gt,
                                                              collection.gt_cluster, collection.true_triples)),
                "construction_cpu_seconds": construction_cpu, "quotient_cpu_seconds": quotient_cpu,
                "planning_cpu_seconds": planning_cpu + reasoning_cpu,
                "reasoning_solver_cpu_seconds": solver_cpu,
                "evaluation_wall_seconds": time.perf_counter() - start_wall,
                "instrumentation_wall_seconds": collection.instrumentation,
                "candidates_scored": collection.policy.candidates_scored,
                "path_invalidations": collection.policy.path_invalidations}
    finally:
        np.random.set_state(rng_state)


def micro_job(job):
    out, config, game_seed, seed, mode, control = job
    ident = f"micro-{game_seed}-{seed}-{mode}-{control}"
    world = base.MicroGame(seed=game_seed)
    world.generate_random(wall_density=0.18)
    permutation = list(range(5))
    if control == "action":
        random.Random(config["permutation_seed"] + game_seed + seed).shuffle(permutation)
    wrapped = WorldView(world, permutation)
    t = time.perf_counter()
    truth = true_graph(wrapped, 5)
    oracle_wall = time.perf_counter() - t
    collector = Collection(wrapped, Policy(5, seed, mode), seed, surface=control == "surface")
    checkpoints = config["budgets"] if control == "original" else [2000]
    goals = config["micro_goals"][str(game_seed)]
    results = []
    trace_path = Path(out) / "traces" / (ident + ".jsonl.gz")
    with gzip.open(trace_path, "xt", encoding="utf-8") as trace:
        for _ in range(max(checkpoints)):
            row = collector.step()
            trace.write(json.dumps(row, separators=(",", ":")) + "\n")
            if row["step"] in checkpoints:
                r = evaluate_checkpoint(collector, row, truth, goals, config, seed + 100000,
                                        Path(out) / "models" / f"{ident}-{row['step']}.npz")
                r.update(game_seed=game_seed, rng_seed=seed, mode=mode, control=control,
                         action_permutation=permutation, oracle_evaluation_wall_seconds=oracle_wall)
                results.append(r)
    save_json(Path(out) / "jobs" / (ident + ".json"), results)
    return ident, results


class FiniteWorld:
    """Uniformly generated deterministic finite transition system, no game rules."""
    def __init__(self, n, actions, seed):
        rng = np.random.default_rng(seed)
        self.table = rng.integers(n, size=(n, actions))
        self.start = 0

    def get_initial_state(self):
        return self.start

    def step(self, s, a):
        return int(self.table[s, a])


def finite_job(job):
    out, config, n, actions, seed, mode = job
    ident = f"finite-{n}-{actions}-{seed}-{mode}"
    world = FiniteWorld(n, actions, seed + 300000)
    truth = true_graph(world, actions)
    policy = Policy(actions, seed, mode)
    state = 0
    seen_edges, seen_relations = set(), set()
    budget = config["finite_budget_multiplier"] * n * actions
    first = {"50": None, "80": None}
    rows = []
    start, cpu = time.perf_counter(), time.process_time()
    for step in range(1, budget + 1):
        a = policy.choose(state)
        v = world.step(state, a)
        policy.observe(state, a, v)
        seen_edges.add((state, v))
        seen_relations.add((state, a, v))
        state = v
        coverage = len(seen_edges) / len(truth[1])
        for key, threshold in (("50", 0.5), ("80", 0.8)):
            if first[key] is None and coverage >= threshold:
                first[key] = step
        if step % max(1, budget // 100) == 0:
            rows.append({"step": step, "edge_coverage": coverage, "states": len(policy.states)})
    exploration_cpu = time.process_time() - cpu
    exploration_wall = time.perf_counter() - start
    ordered = sorted(policy.states)
    index = {s: i for i, s in enumerate(ordered)}
    K = np.zeros((len(index), len(index)))
    dest = {}
    for s in ordered:
        tried = sorted(policy.graph.get(s, {}))
        if not tried:
            K[index[s], index[s]] = 1.0
        for a in tried:
            v = policy.graph[s][a]
            dest[index[s], a] = index[v]
            K[index[s], index[v]] += 1 / len(tried)
    # Goals are selected from the truth graph by an evaluator-only RNG.
    goals = random.Random(seed + 400000).sample(sorted(truth[0]), min(10, len(truth[0])))
    successes = 0
    t = time.process_time()
    for target in goals:
        pred = {"K": K, "dest_map": dest, "goal_indices": [index[target]] if target in index else []}
        cong = quotient_checked(pred, actions)
        psi, _, _, _ = base.solve_fixed_field(cong["K_bar"], [cong["u_to_q"][index[target]]] if target in index else [])
        s = 0
        # Generic readout, reported separately from the unchanged microgame planner.
        for tr in range(config["finite_goal_steps"]):
            if s == target:
                break
            u = index.get(s)
            choices = [(a, psi[cong["u_to_q"][dest[u, a]]]) for a in range(actions) if (u, a) in dest]
            a = max(choices, key=lambda p: (p[1], -p[0]))[0] if choices else 0
            s = world.step(s, a)
        successes += s == target
    result = {"n": n, "actions": actions, "rng_seed": seed, "mode": mode, "budget": budget,
              "steps_to_50": first["50"], "steps_to_80": first["80"],
              "restricted_steps_to_80": first["80"] if first["80"] is not None else budget + 1,
              "censored_80": first["80"] is None, "edge_coverage": coverage,
              "held_out_goal_success": successes / len(goals), "goals": goals, "curve": rows,
              "exploration_cpu_seconds": exploration_cpu, "exploration_wall_seconds": exploration_wall,
              "downstream_cpu_seconds": time.process_time() - t, "model_heap_bytes": deep_bytes(vars(policy))}
    save_json(Path(out) / "jobs" / (ident + ".json"), result)
    return ident, result


def frozen_config(repetitions=10):
    game_seeds = [201, 302, 403, 504, 605]
    goals = {}
    for seed in game_seeds:
        world = base.MicroGame(seed=seed)
        world.generate_random(wall_density=0.18)
        states, _, _ = true_graph(world, 5)
        positions = sorted({(s[0], s[1]) for s in states} - {world.start_pos, world.goal_pos})
        goals[str(seed)] = random.Random(800000 + seed).sample(positions, min(5, len(positions)))
    return {"game_seeds": game_seeds, "rng_seeds": list(range(11000, 11000 + repetitions)),
            "budgets": [250, 500, 1000, 2000, 4000], "modes": list(MODES), "q": 0.90,
            "trials": 50, "multi_trials": 10, "play_steps": 100, "micro_goals": goals,
            "permutation_seed": 710000, "finite_n": [50, 100, 250, 500], "finite_actions": [4, 8],
            "finite_budget_multiplier": 10, "finite_goal_steps": 100,
            "weights": {"unseen": 1, "count": 1, "entropy": 1, "distinction": 1},
            "entropy": "H(observed successor frequencies)/log(observed successor count); unseen=1",
            "distinction": "1-max successor frequency/total; unseen=0; provisional constructed IDs only",
            "routing": "BFS on all observed successor edges; target retained until reached or unreachable; replan route after each observation",
            "ties": "ascending opaque state then action IDs; structural ascending action IDs; random uniform",
            "quotient_sampling": "not constructed at intermediate steps; measured at each budget endpoint",
            "surface_control_scope": "seeded random injective renaming of opaque state IDs at policy interface; RNG seed+500000; not pixel invariance",
            "edge_coverage": "distinct evaluator-only true directed (s,v) edges / reachable true edges",
            "recovery_rule": "seed201 or302 structural<=0.05 and active>=structural+0.20 and active>random at2000",
            "retention_rule": "min(permuted/original mean true edge coverage, permuted/original multi-goal success); zero denominator undefined",
            "finite_comparison": "paired mean restricted steps-to80 (right censor at 10*N*A +1); also report censor counts",
            "primary_criteria": ["active edge coverage > both at2000", "active multi-goal success > both at2000",
                "at least one seed recovers by predeclared rule", "action retention>=0.95", "surface retention>=0.95",
                "finite paired restricted steps80 < random"],
            "evaluation_rng_isolated": True, "prefix_checkpoints": True,
            "mean_steps_note": "original planner zero-based successful step counter preserved, not corrected",
            "goal_blackout_scope": "policy has only IDs/counts; frozen image encoder still observes unchanged goal sprite"}


def summarize(micro, finite):
    def mean(rows, key):
        return float(np.mean([r[key] for r in rows])) if rows else None
    primary = [r for r in micro if r["control"] == "original" and r["step"] == 2000]
    comparison = {m: {k: mean([r for r in primary if r["mode"] == m], k)
                    for k in ("edge_coverage", "transition_coverage", "success", "multi_goal_success", "reachable_goal_fraction")}
                  for m in MODES}
    seeds = {str(s): {m: mean([r for r in primary if r["mode"] == m and r["game_seed"] == s], "success")
                     for m in MODES[:3]} for s in (201, 302)}
    retention = {}
    for control in ("action", "surface"):
        rows = [r for r in micro if r["control"] == control]
        ratios = {k: (mean(rows, k) / comparison["active"][k] if comparison["active"][k] else None)
                  for k in ("edge_coverage", "multi_goal_success")}
        retention[control] = {**ratios, "minimum": min(ratios.values()) if all(v is not None for v in ratios.values()) else None}
    finite_means = {m: mean([r for r in finite if r["mode"] == m], "restricted_steps_to_80") for m in MODES[:3]}
    criteria = {
        "coverage": all(comparison["active"]["edge_coverage"] > comparison[m]["edge_coverage"] for m in ("random", "structural")),
        "multi_goal": all(comparison["active"]["multi_goal_success"] > comparison[m]["multi_goal_success"] for m in ("random", "structural")),
        "recovery": any(v["structural"] <= 0.05 and v["active"] >= v["structural"] + 0.20 and v["active"] > v["random"] for v in seeds.values()),
        "action": retention["action"]["minimum"] is not None and retention["action"]["minimum"] >= 0.95,
        "surface": retention["surface"]["minimum"] is not None and retention["surface"]["minimum"] >= 0.95,
        "finite": finite_means["active"] < finite_means["random"]}
    size = {k: mean([r for r in micro if r["control"] == "original" and r["mode"] == "active" and r["step"] == 4000], k)
            for k in ("constructed_states", "edges", "predictive_states", "quotient_states", "model_heap_bytes", "operator_heap_bytes")}
    return {"at_2000": comparison, "seeds": seeds, "retention": retention,
            "finite_restricted_steps80": finite_means, "finite_censored": {m: sum(r["censored_80"] for r in finite if r["mode"] == m) for m in MODES[:3]},
            "at_4000_active": size, "criteria": criteria, "primary_pass": all(criteria.values()),
            "claims": {"A": "PARTIAL" if criteria["recovery"] else "NO",
                       "B": "YES" if criteria["coverage"] and criteria["multi_goal"] else "NO",
                       "C": "YES" if criteria["action"] and criteria["surface"] else "NO",
                       "D": "YES" if criteria["finite"] else "NO",
                       "E": "YES" if all(mean([r for r in micro if r["control"] == "original" and r["mode"] == "active" and r["step"] == 4000], k) > mean([r for r in micro if r["control"] == "original" and r["mode"] == "active" and r["step"] == 250], k) for k in ("constructed_states", "edges")) else "NO"}}


def plots(out, micro, finite, summary):
    import matplotlib.pyplot as plt
    def bars(name, data, ylabel):
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.bar(list(data), list(data.values()))
        ax.set_ylabel(ylabel)
        fig.tight_layout()
        fig.savefig(Path(out) / name, dpi=130)
        plt.close(fig)
    for filename, key in (("coverage_curves.png", "edge_coverage"), ("downstream_success.png", "multi_goal_success")):
        fig, ax = plt.subplots(figsize=(8, 4))
        for mode in MODES[:3]:
            rows = [r for r in micro if r["control"] == "original" and r["mode"] == mode]
            budgets = sorted({r["step"] for r in rows})
            ax.plot(budgets, [np.mean([r[key] for r in rows if r["step"] == b]) for b in budgets], marker="o", label=mode)
        ax.set(xlabel="Exploration interactions", ylabel=key)
        ax.legend()
        fig.tight_layout()
        fig.savefig(Path(out) / filename, dpi=130)
        plt.close(fig)
    bars("seed201_302.png", {f"{s}\n{m}": v for s, row in summary["seeds"].items() for m, v in row.items()}, "Original goal success")
    for control in ("action", "surface"):
        bars(control + "_permutation.png", {k: v or 0 for k, v in summary["retention"][control].items()}, "Retention (ratio; undefined shown as zero)")
    bars("random_systems.png", summary["finite_restricted_steps80"], "Restricted mean steps to 80% (censored at budget+1)")
    bars("ablation.png", {m: summary["at_2000"][m]["edge_coverage"] for m in ("active", "u_only", "nearest_unseen")}, "True edge coverage at 2000")
    fig, axes = plt.subplots(2, 2, figsize=(10, 7))
    rows = [r for r in micro if r["control"] == "original" and r["mode"] == "active"]
    for ax, k in zip(axes.flat, ("constructed_states", "edges", "quotient_states", "model_heap_bytes")):
        budgets = sorted({r["step"] for r in rows})
        ax.plot(budgets, [np.mean([r[k] for r in rows if r["step"] == b]) for b in budgets], marker="o")
        ax.set(xlabel="Interactions", ylabel=k)
    fig.tight_layout()
    fig.savefig(Path(out) / "model_size_scaling.png", dpi=130)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--smoke", action="store_true")
    args = parser.parse_args()
    out = args.output.resolve()
    if not (out / "source_snapshot.json").exists() and not args.smoke:
        raise SystemExit("Create the required pre-edit source_snapshot.json first")
    out.mkdir(parents=True, exist_ok=True)
    for path in ("config.json", "run.log", "metrics.json"):
        if (out / path).exists():
            raise SystemExit(f"Refusing to overwrite existing experiment: {path}")
    (out / "jobs").mkdir()
    (out / "traces").mkdir()
    (out / "models").mkdir()
    config = frozen_config()
    if args.smoke:
        config.update(game_seeds=[999], rng_seeds=[900001], budgets=[20, 40], modes=["structural"],
                      trials=2, multi_trials=1, micro_goals={"999": [[1, 1]]}, finite_n=[], finite_actions=[])
    save_json(out / "config.json", config)
    save_json(out / "rng_seeds.json", {k: config[k] for k in ("rng_seeds", "game_seeds", "permutation_seed")})
    (out / "extracted_frozen_builder.py").write_text(EXTRACTED_SOURCE, encoding="utf-8")
    paths = [Path(__file__), Path(base.__file__), ROOT / "scripts/evaluate_active_world_discovery.py"]
    source = {str(p.relative_to(ROOT)): hash_file(p) for p in paths}
    for p in paths:
        (out / ("executed_" + p.name)).write_bytes(p.read_bytes())
    save_json(out / "run_manifest.json", {"timestamp": datetime.now(timezone.utc).isoformat(), "sources": source,
              "python": sys.version, "numpy": np.__version__, "argv": sys.argv,
              "thread_env": {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
              "config_sha256": hash_file(out / "config.json"), "smoke_not_research_evidence": args.smoke})
    micro_jobs = [(str(out), config, game, seed, mode, "original") for game in config["game_seeds"]
                  for seed in config["rng_seeds"] for mode in config["modes"]]
    if not args.smoke:
        micro_jobs += [(str(out), config, game, seed, "active", control) for game in config["game_seeds"]
                       for seed in config["rng_seeds"] for control in ("action", "surface")]
    finite_jobs = [(str(out), config, n, a, seed, mode) for n in config["finite_n"] for a in config["finite_actions"]
                   for seed in config["rng_seeds"] for mode in MODES[:3]]
    start = time.perf_counter()
    micro, finite, errors = [], [], []
    with (out / "run.log").open("x", encoding="utf-8", buffering=1) as log:
        def emit(value):
            line = json.dumps(value, ensure_ascii=True)
            print(line, flush=True)
            log.write(line + "\n")
        emit({"event": "fixed_run_start", "sources": source, "jobs": len(micro_jobs) + len(finite_jobs)})
        with ProcessPoolExecutor(max_workers=args.workers) as pool:
            futures = {pool.submit(micro_job, job): ("micro", job[2:]) for job in micro_jobs}
            futures.update({pool.submit(finite_job, job): ("finite", job[2:]) for job in finite_jobs})
            for future in as_completed(futures):
                kind, key = futures[future]
                try:
                    ident, result = future.result()
                    if kind == "micro":
                        micro.extend(result)
                    else:
                        finite.append(result)
                    emit({"event": "job_complete", "job": ident, "completed": len(micro) + len(finite),
                          "elapsed_seconds": time.perf_counter() - start})
                except Exception as exc:
                    import traceback
                    error = {"kind": kind, "key": key, "error": repr(exc), "traceback": traceback.format_exc()}
                    errors.append(error)
                    emit({"event": "job_failed", **error})
        micro.sort(key=lambda r: (r["game_seed"], r["rng_seed"], r["mode"], r["control"], r["step"]))
        finite.sort(key=lambda r: (r["n"], r["actions"], r["rng_seed"], r["mode"]))
        summary = summarize(micro, finite) if not args.smoke and not errors else None
        result = {"micro": micro, "finite": finite, "errors": errors, "summary": summary,
                  "wall_seconds": time.perf_counter() - start, "source_hashes_unchanged": all(hash_file(p) == source[str(p.relative_to(ROOT))] for p in paths)}
        save_json(out / "metrics.json", result)
        if summary:
            plots(out, micro, finite, summary)
        emit({"event": "finished", "summary": summary, "errors": len(errors), "wall_seconds": result["wall_seconds"]})
    if errors:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
