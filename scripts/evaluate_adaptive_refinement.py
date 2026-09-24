"""Frozen finite-data refinement experiment; hidden state is evaluator-only.

History suffixes are evidence, not predeclared learned states. Leaves select their
own shortest distinguishing depth. Certificates concern the empirical graph;
they do not certify unseen transitions or finite-history identifiability.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict, deque
from datetime import datetime, timezone
from fractions import Fraction as F
import hashlib
import json
import math
from pathlib import Path
import random
import shutil
import subprocess
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from scripts import evaluate_fixed_field_congruence as base
from scripts.active_world_discovery_v2 import deep_bytes, make_classifier

Q = F(9, 10)
MODES = ("no_split", "split_only", "split_merge")


def dump(path, obj):
    Path(path).write_text(json.dumps(obj, indent=2, allow_nan=False), encoding="utf-8")


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def numbered(signatures):
    ids = {}
    return [ids.setdefault(s, len(ids)) for s in signatures]


def exact_quotient(labels, availability, counts, merge=True):
    """Observation-preserving stochastic congruence, exact rational signatures.

Unknown action rows remain absent. They are not asserted to be self loops.
The aggregate K uses a self loop only for a state with no observed actions.
"""
    n = len(labels)
    observed_sets = [set() for _ in range(n)]
    for s, a in counts:
        observed_sets[s].add(a)
    observed = [tuple(sorted(a)) for a in observed_sets]
    tags = [(labels[u], availability[u], observed[u]) for u in range(n)]
    blocks = numbered(tags) if merge else list(range(n))

    def row(u, a, partition):
        dest = Counter()
        for v, c in counts.get((u, a), {}).items():
            dest[partition[v]] += c
        total = sum(dest.values())
        return tuple((v, F(c, total)) for v, c in sorted(dest.items())) if total else ()

    rounds = 0
    if merge:
        while True:
            sig = [(blocks[u], tuple((a, row(u, a, blocks)) for a in observed[u]))
                   for u in range(n)]
            new = numbered(sig)
            rounds += 1
            if new == blocks:
                break
            blocks = new
    groups = defaultdict(list)
    for u, b in enumerate(blocks):
        groups[b].append(u)
    action_rows, k_rows = {}, []
    exact_ok = True
    for b, members in groups.items():
        u = members[0]
        aggregate = defaultdict(F)
        for a in observed[u]:
            r = row(u, a, blocks)
            action_rows[b, a] = dict(r)
            for v, p in r:
                aggregate[v] += p / len(observed[u])
            exact_ok &= all(row(v, a, blocks) == r for v in members)
        if not observed[u]:
            aggregate[b] = F(1)
        exact_ok &= all(tags[v] == tags[u] for v in members)
        k_rows.append(dict(aggregate))
    # Independently project each original action and aggregate row, then compare
    # with its quotient row. Values here are measured rational residuals.
    eps_k, eps_a = F(), F()
    for u in range(n):
        projected_k = defaultdict(F)
        for a in observed[u]:
            projected = dict(row(u, a, blocks))
            target = action_rows[blocks[u], a]
            eps_a = max(eps_a, sum((abs(projected.get(v,F())-target.get(v,F()))
                                   for v in projected.keys() | target.keys()), F()))
            for v, p in projected.items():
                projected_k[v] += p/len(observed[u])
        if not observed[u]:
            projected_k[blocks[u]] = F(1)
        target = k_rows[blocks[u]]
        eps_k = max(eps_k, sum((abs(projected_k.get(v,F())-target.get(v,F()))
                               for v in projected_k.keys() | target.keys()), F()))
    if not exact_ok or eps_k or eps_a:
        raise AssertionError("Refused a non-congruent quotient")
    return {"blocks": blocks, "groups": dict(groups), "rows": action_rows,
            "K": k_rows, "rounds": rounds, "exact_certificate": exact_ok,
            "eps_K": float(eps_k), "eps_action": float(eps_a),
            "complete": all(observed[u] == availability[u] for u in range(n)),
            "scope": "observed empirical transitions, not unobserved environment"}


class HistoryModel:
    """Only observation/action histories enter this learner."""
    def __init__(self, actions, mode="split_merge", max_depth=6, fixed_depth=None):
        self.actions = tuple(range(actions))
        self.mode, self.max_depth, self.fixed_depth = mode, max_depth, fixed_depth
        self.contexts, self.context_index, self.rules = [], {}, {}
        self.raw = defaultdict(Counter)
        self.events, self.trajectory = [], []
        self.split_count = self.merge_count = self.reopened_count = 0
        self.mapping, self.leaf_keys, self.depths = [], [], []
        self.leaf_counts = defaultdict(Counter)
        self.model = None
        self.current = None
        self.last_groups = []
        self.model_seconds = 0.0

    def _intern(self, context):
        if context not in self.context_index:
            self.context_index[context] = len(self.contexts)
            self.contexts.append(context)
        return self.context_index[context]

    def _classify(self, context):
        depth = self.fixed_depth or 0
        key = (context[-1], self.actions)
        if self.fixed_depth is not None:
            return (key, context[-(2 * depth + 1):]), depth
        while key in self.rules:
            depth = self.rules[key]
            key = (key, context[-(2 * depth + 1):])
        return key, depth

    def begin(self, observation):
        self.current = (int(observation),)
        self._intern(self.current)
        self.rebuild(0)

    def rebuild(self, step):
        start = time.perf_counter()
        while True:
            info = [self._classify(c) for c in self.contexts]
            ids = {}
            self.mapping = [ids.setdefault(k, len(ids)) for k, _ in info]
            self.leaf_keys = list(ids)
            self.depths = [0] * len(ids)
            for i, (_, d) in enumerate(info):
                self.depths[self.mapping[i]] = d
            counts = defaultdict(Counter)
            witnesses = defaultdict(lambda: defaultdict(set))
            for (u, a), hist in self.raw.items():
                s = self.mapping[u]
                for v, c in hist.items():
                    z = self.mapping[v]
                    counts[s, a][z] += c
                    witnesses[s, a][z].add(u)
            chosen = None
            if self.mode != "no_split" and self.fixed_depth is None:
                for (s, a), cases in witnesses.items():
                    pairs = list(cases.items())
                    if len(pairs) < 2:
                        continue
                    for i, (v, sources) in enumerate(pairs):
                        for w, others in pairs[i + 1:]:
                            for depth in range(self.depths[s] + 1, self.max_depth + 1):
                                left={self.contexts[u][-(2*depth+1):]:u for u in sorted(sources)}
                                right={self.contexts[t][-(2*depth+1):]:t for t in sorted(others)}
                                pair=next(((u,t) for x,u in left.items() for y,t in right.items() if x!=y),None)
                                if pair is not None:
                                    u,t=pair
                                    candidate = (depth, s, a, u, t, v, w)
                                    if chosen is None or candidate < chosen:
                                        chosen = candidate
                                    break
            if chosen is None:
                break
            depth, s, a, u, t, v, w = chosen
            self.rules[self.leaf_keys[s]] = depth
            self.split_count += 1
            self.events.append({"step": step, "kind": "split", "depth": depth,
                                "source_contexts": [u, t], "action": a,
                                "different_successor_leaves": [v, w]})
        self.leaf_counts = counts
        labels = [None] * len(ids)
        for i, s in enumerate(self.mapping):
            labels[s] = self.contexts[i][-1]
        old_groups = self.last_groups
        self.model = exact_quotient(labels, [self.actions]*len(ids), counts,
                                    merge=self.mode == "split_merge")
        context_blocks = [self.model["blocks"][s] for s in self.mapping]
        new_groups = [set() for _ in self.model["groups"]]
        for i, b in enumerate(context_blocks):
            new_groups[b].add(i)
        # Count actual coalescence of formerly distinct blocks, not repeated
        # rediscovery of the same quotient on every update.
        merged = sum(max(0, sum(bool(g & old) for old in old_groups) - 1) for g in new_groups)
        reopened = sum(max(0, sum(bool(g & old) for g in new_groups) - 1) for old in old_groups)
        self.merge_count += merged
        self.reopened_count += reopened
        if merged:
            self.events.append({"step": step, "kind": "merge", "count": merged,
                                "certificate": "exact observation/action/K congruence on empirical graph"})
        if reopened:
            self.events.append({"step": step, "kind": "partition_refinement", "count": reopened})
        self.last_groups = new_groups
        self.context_blocks = context_blocks
        self.labels = [labels[m[0]] for m in self.model["groups"].values()]
        self.model_seconds += time.perf_counter() - start

    def observe(self, action, observation, step):
        u = self.context_index[self.current]
        context = (self.current + (int(action), int(observation)))[-(2*self.max_depth+1):]
        v = self._intern(context)
        self.raw[u, int(action)][v] += 1
        self.current = context
        self.rebuild(step)
        edges = sum(len(r) for r in self.model["rows"].values())
        size = len(self.model["groups"])
        previous = self.trajectory[-1]["N_blocks"] if self.trajectory else 1
        # A logical encoded byte count is distinct from Python object heap size.
        logical = 8*(sum(len(c) for c in self.contexts) + 3*sum(len(r) for r in self.raw.values()))
        self.trajectory.append({"step": step, "N_states": len(self.leaf_keys),
                                "N_blocks": size, "N_edges": edges,
                                "split_count": self.split_count, "merge_count": self.merge_count,
                                "net_state_change": size-previous, "evidence_logical_bytes": logical,
                                "elapsed_model_seconds": self.model_seconds})

    def state(self):
        return self.context_blocks[self.context_index[self.current]]

    def encode(self, context):
        key, _ = self._classify(context)
        try:
            leaf = self.leaf_keys.index(key)
        except ValueError:
            return None
        return self.model["blocks"][leaf]

    def policy_counts(self):
        counts = defaultdict(Counter)
        for (s, a), hist in self.leaf_counts.items():
            for v, c in hist.items():
                counts[self.model["blocks"][s], a][self.model["blocks"][v]] += c
        return counts

    def summary(self):
        unresolved = []
        for (s, a), hist in self.policy_counts().items():
            if len(hist) > 1:
                unresolved.append({"state": s, "action": a, "successor_blocks": sorted(hist)})
        used_depths = [self.depths[s] for s in self.mapping]
        return {"initial_states": 1, "peak_states": max([1]+[t["N_blocks"] for t in self.trajectory]),
                "final_states": len(self.model["groups"]), "leaf_states": len(self.leaf_keys),
                "split_count": self.split_count, "merge_count": self.merge_count,
                "reopened_count": self.reopened_count, "history_independent": not unresolved,
                "sufficiency_counterexamples": unresolved, "mean_depth": float(np.mean(used_depths)),
                "max_depth_usage": sum(d == self.max_depth for d in used_depths)/len(used_depths),
                "depths": dict(Counter(used_depths)), "heap_bytes": deep_bytes(self.__dict__),
                "evidence_heap_bytes": deep_bytes((self.contexts,self.context_index,self.raw)),
                "active_model_heap_bytes": deep_bytes((self.rules,self.leaf_keys,self.model)),
                "telemetry_heap_bytes": deep_bytes((self.events,self.trajectory)),
                "model_seconds": self.model_seconds, "eps_K": self.model["eps_K"],
                "eps_action": self.model["eps_action"], "certificate_scope": self.model["scope"],
                "observed_actions_complete": self.model["complete"]}


class IdentificationPolicy:
    """Opaque IDs and observed counts only; no goals or environment reference."""
    def __init__(self, actions, seed):
        self.actions = tuple(range(actions))
        self.rng = random.Random(seed)
        self.target = None
        self.remaining = 0
        self.expected = None
        self.invalidations = self.expirations = 0

    def choose(self, current, counts, partition_changed=False):
        if partition_changed or (self.expected is not None and self.expected != current):
            self.invalidations += int(self.target is not None)
            self.target = None
        graph = defaultdict(dict)
        for (s, a), row in counts.items():
            graph[s][a] = max(row, key=row.get)
        dist, first = {current: 0}, {}
        queue = deque([current])
        while queue:
            u = queue.popleft()
            for a, v in graph[u].items():
                if v not in dist:
                    dist[v] = dist[u]+1
                    first[v] = a if u == current else first[u]
                    queue.append(v)
        if self.target is not None and self.remaining <= 0:
            self.expirations += 1
            self.target = None
        if self.target is not None and self.target[0] not in dist:
            self.invalidations += 1
            self.target = None
        if self.target is None:
            best, candidates = -1.0, []
            for s, d in dist.items():
                for a in self.actions:
                    row = counts.get((s, a), {})
                    n = sum(row.values())
                    disagreement = 1-max(row.values())/n if n else 0
                    score = ((n == 0)+1/math.sqrt(1+n)+disagreement)/(1+d)
                    if score > best:
                        best, candidates = score, [(s, a)]
                    elif score == best:
                        candidates.append((s, a))
            self.target = self.rng.choice(candidates)
            self.remaining = 2*dist[self.target[0]]+3
        s, a = self.target
        action = a if s == current else first[s]
        if s == current:
            self.target = None
        self.remaining -= 1
        self.expected = graph[current].get(action)
        return action


def dense(rows):
    k = np.zeros((len(rows), len(rows)))
    for u, row in enumerate(rows):
        for v, p in row.items():
            k[u, v] = float(p)
    return k


def exact_margin_certificate(rows, actions, g, values, selected):
    """Rational residual for the exact stored float vector, not its rounded norm."""
    x = [F(float(v)) for v in values]
    residual = max(abs(F(g[u])+Q*sum((p*x[v] for v, p in row.items()), F())-x[u])
                   for u, row in enumerate(rows))
    norm = max(sum((abs(p) for p in row.values()), F()) for row in rows)
    if norm > 1 or any(p<0 for row in rows for p in row.values()):
        raise ValueError("K is not substochastic")
    epsilon = residual/(1-Q)
    scores = {a: sum((p*x[v] for v, p in row.items()), F()) for a, row in actions.items()}
    other = [a for a in scores if a != selected]
    lower = min((scores[selected]-scores[a] - epsilon*(sum((abs(p) for p in actions[selected].values()), F())
                 + sum((abs(p) for p in actions[a].values()), F())) for a in other), default=F(1))
    return lower > 0, float(epsilon), float(lower)


def reason(rows, actions, goals, mode, cheap=5, tolerance=1e-8):
    """Same score/readout; only stopping rule differs. A resource cap is refusal."""
    n = len(rows)
    g = np.zeros(n)
    g[list(goals)] = 1
    x = np.zeros(n)
    started = time.process_time()
    wall_started = time.perf_counter()
    certification_seconds = 0.0
    checks = matvecs = 0
    if not actions:
        return {"action": None, "iterations": 0, "certified": False, "status": "no_observed_action",
                "matvecs": 0, "cpu_seconds": 0.0, "certificate_seconds": 0.0,
                "certificate_checks": 0, "residual": 0.0, "margin": 0.0}
    source, destination, probability = [], [], []
    for u, row in enumerate(rows):
        for v, p in row.items():
            source.append(u); destination.append(v); probability.append(float(p))
    source, destination, probability = np.array(source), np.array(destination), np.array(probability)
    def mv(v):
        return np.bincount(source, weights=probability*v[destination], minlength=n)
    for iteration in range(1, 10001):
        new = g+float(Q)*mv(x)
        matvecs += 1
        delta = float(np.max(np.abs(new-x)))
        x = new
        scores = {a: sum(float(p)*x[v] for v, p in row.items()) for a, row in actions.items()}
        selected = max(sorted(scores), key=scores.get)
        ordered = sorted(scores.values(), reverse=True)
        margin = ordered[0]-ordered[1] if len(ordered)>1 else 0.0
        residual = None
        if mode == "certified":
            residual = float(np.max(np.abs(g+float(Q)*mv(x)-x)))
            matvecs += 1
        certified, status = False, None
        if mode == "certified" and (len(scores)==1 or margin > 2*residual/(1-float(Q))):
            then = time.process_time()
            certified, epsilon, lower = exact_margin_certificate(rows, actions, g, x, selected)
            certification_seconds += time.process_time()-then
            checks += 1
            if certified:
                status = "certified_margin"
        if status is None and mode == "cheap" and iteration >= cheap:
            status = "fixed_cheap_uncertified"
        if status is None and mode != "cheap" and delta < tolerance:
            status = "full_tolerance_uncertified" if not certified else "certified_margin"
        if status:
            if residual is None:
                residual = float(np.max(np.abs(g+float(Q)*mv(x)-x)))
                matvecs += 1
            return {"action": int(selected), "iterations": iteration, "matvecs": matvecs,
                    "certified": certified, "status": status, "margin": margin, "residual": residual,
                    "cpu_seconds": time.process_time()-started, "wall_seconds":time.perf_counter()-wall_started,
                    "certificate_seconds": certification_seconds,
                    "certificate_checks": checks}
    raise RuntimeError("Fixed-field resource cap reached, no certified answer")


def true_partition(table, observations):
    """Independent evaluator: pair-distinguishability fixed point, not learner code."""
    n, actions = table.shape
    labels=np.asarray(observations)
    different=labels[:,None]!=labels[None,:]
    while True:
        updated=different.copy()
        for a in range(actions):
            dest=table[:,a]
            updated |= different[dest[:,None],dest[None,:]]
        if np.array_equal(updated,different):break
        different=updated
    blocks=numbered([tuple(row) for row in different])
    groups=defaultdict(list)
    for s,b in enumerate(blocks):groups[b].append(s)
    return {"blocks":blocks,"groups":dict(groups)}


def finite_world(n, actions, seed, kind):
    rng = np.random.default_rng(seed)
    if kind == "lifted":
        m = n//2
        coarse = rng.integers(0, m, size=(m, actions))
        table = np.array([[2*coarse[s//2, a]+rng.integers(2) for a in range(actions)] for s in range(n)])
        colors = rng.integers(0, max(2, int(math.sqrt(m))), size=m)
        observations = np.repeat(colors, 2)
    elif kind == "history":
        table = np.array([[(s*actions+a) % n for a in range(actions)] for s in range(n)])
        observations = rng.integers(0, 2, size=n)
    else:
        table = rng.integers(0, n, size=(n, actions))
        observations = rng.integers(0, max(2, int(math.sqrt(n))), size=n)
    return table, observations


def recovery(model, hidden_contexts, truth, table):
    """Truth never changes learned labels. Require full reachable-state coverage."""
    reachable, queue = {0}, deque([0])
    while queue:
        for v in table[queue.popleft()]:
            if int(v) not in reachable:
                reachable.add(int(v)); queue.append(int(v))
    z_to_truth, truth_to_z = defaultdict(set), defaultdict(set)
    coverage = set()
    for context, hidden in hidden_contexts:
        z = model.encode(context)
        if z is None:
            continue
        b = truth["blocks"][hidden]
        z_to_truth[z].add(b); truth_to_z[b].add(z); coverage.add(hidden)
    pure = all(len(x)==1 for x in z_to_truth.values())
    no_extra = all(len(x)==1 for x in truth_to_z.values())
    complete = reachable <= coverage
    # Witness-level split precision and final merged-block purity, not guessed
    # causal accuracy of every historical merge event.
    context_truth = defaultdict(set)
    for c, h in hidden_contexts:
        context_truth[model.context_index[c]].add(truth["blocks"][h])
    suffix_truth = [defaultdict(set) for _ in range(7)]
    for c, h in hidden_contexts:
        for depth in range(7):
            suffix_truth[depth][c[-(2*depth+1):]].add(truth["blocks"][h])
    unnecessary, unresolved_history = 0, 0
    for i,c in enumerate(model.contexts):
        minimum = next((d for d in range(7) if len(suffix_truth[d][c[-(2*d+1):]])==1), None)
        unresolved_history += int(minimum is None)
        selected = model.depths[model.mapping[i]]
        unnecessary += int(selected==6 and minimum is not None and minimum<6)
    split_valid = []
    for e in model.events:
        if e["kind"] == "split":
            u, v = e["source_contexts"]
            split_valid.append(context_truth[u].isdisjoint(context_truth[v]))
    merged_groups = [m for m in model.model["groups"].values() if len(m)>1]
    merged_pure = []
    for members in merged_groups:
        hidden_blocks = set()
        for i, leaf in enumerate(model.mapping):
            if leaf in members:
                hidden_blocks.update(context_truth[i])
        merged_pure.append(len(hidden_blocks)==1)
    return {"recovered": complete and pure and no_extra and model.summary()["history_independent"],
            "covered_hidden_states": len(coverage), "reachable_hidden_states": len(reachable),
            "true_quotient_states": len({truth["blocks"][h] for h in reachable}),
            "representation_pure": pure, "no_extra_distinctions": no_extra,
            "split_precision": float(np.mean(split_valid)) if split_valid else None,
            "merge_precision": float(np.mean(merged_pure)) if merged_pure else None,
            "split_precision_denominator": len(split_valid), "merge_precision_denominator": len(merged_pure),
            "empirically_unnecessary_max_history_fraction":unnecessary/len(model.contexts),
            "history_limit_unidentifiable_contexts":unresolved_history}


def replay_stream(stream, actions, mode, fixed_depth=None):
    model = HistoryModel(actions, mode, fixed_depth=fixed_depth)
    model.begin(stream[0][1])
    for step, (a, o) in enumerate(stream[1:], 1):
        model.observe(a, o, step)
    return model


def evaluate_goals(model, transition, observe, starts, goals, horizon, seed, backend="full"):
    """Post-exploration only. Goal labels are observation IDs, never oracle paths."""
    rng = random.Random(seed)
    successes, total, decisions, audits = 0, 0, [], []
    for goal in goals:
        target = [s for s, label in enumerate(model.labels) if label == goal]
        if not target:
            total += len(starts)
            continue
        # Field independent of decision state; cache FULL values for real play.
        psi = None
        if backend == "full":
            psi, iterations, _, converged = base.solve_fixed_field(dense(model.model["K"]), target, q=.90)
            if not converged:
                raise RuntimeError("Canonical FULL solver did not converge")
        for start in starts:
            state, context = start, (int(observe(start, 0)),)
            total += 1
            for t in range(horizon+1):
                if context[-1] == goal:
                    successes += 1
                    break
                z = model.encode(context)
                choices = {} if z is None else {a: model.model["rows"][z, a] for a in model.actions
                                               if (z, a) in model.model["rows"]}
                if not choices or t == horizon:
                    break
                if backend == "certified":
                    audit = compute_comparison(model, [(z, tuple(target), choices)])[0]
                    audits.append(audit)
                    action = audit["adaptive"]["action"]
                else:
                    scores = {a: sum(float(p)*psi[v] for v, p in row.items()) for a, row in choices.items()}
                    action = max(sorted(scores), key=scores.get)
                if len(decisions) < 12:
                    decisions.append((z, tuple(target), choices))
                state = transition(state, action)
                observation = int(observe(state, t+1))
                context = (context+(action, observation))[-13:]
    result={"successes":successes,"trials":total,"success":successes/total if total else None}
    if backend=="certified": result["decision_audits"]=audits
    return result, decisions


def compute_comparison(model, decisions):
    records = []
    for z, goals, choices in decisions:
        # Selection occurs before the evaluator computes FULL.
        adaptive = reason(model.model["K"], choices, goals, "certified")
        cheap = reason(model.model["K"], choices, goals, "cheap")
        full = reason(model.model["K"], choices, goals, "full")
        then=time.perf_counter()
        psi, canonical_iters, _, _ = base.solve_fixed_field(dense(model.model["K"]), goals, q=.90)
        canonical_action = max(sorted(choices), key=lambda a: sum(float(p)*psi[v] for v, p in choices[a].items()))
        records.append({"state": z, "goals": goals, "adaptive": adaptive, "full": full, "cheap": cheap,
                        "adaptive_agrees": adaptive["action"] == full["action"],
                        "cheap_agrees": cheap["action"] == full["action"],
                        "canonical_full_agrees": canonical_action == full["action"],
                        "canonical_full_iterations": canonical_iters,
                        "canonical_verification_seconds":time.perf_counter()-then,
                        "state_uncertainty": sum(len(r)>1 for r in choices.values())})
    return records


def run_finite(spec, config):
    n, actions, seed, kind = spec["n"], spec["actions"], spec["seed"], spec["kind"]
    table, observations = finite_world(n, actions, seed, kind)
    learner = HistoryModel(actions)
    learner.begin(observations[0])
    policy = IdentificationPolicy(actions, seed+100000)
    hidden, stream, evidence = 0, [(None, int(observations[0]))], [(learner.current, 0)]
    previous_partition = None
    for t in range(1, spec["steps"]+1):
        partition = tuple(learner.mapping), tuple(learner.model["blocks"])
        action = policy.choose(learner.state(), learner.policy_counts(), partition != previous_partition)
        previous_partition = partition
        hidden = int(table[hidden, action])
        obs = int(observations[hidden])
        learner.observe(action, obs, t)
        stream.append((action, obs)); evidence.append((learner.current, hidden))
    truth = true_partition(table, observations)
    models = {"split_merge": learner}
    for mode in ("no_split", "split_only"):
        models[mode] = replay_stream(stream, actions, mode)
    output = {"spec": spec, "policy_invalidations": policy.invalidations, "policy_expirations": policy.expirations,
              "stream": stream, "evaluation_hidden_trace": [h for _, h in evidence], "conditions": {}}
    goals = sorted(set(map(int, observations)))[:config["evaluation_goals"]]
    for mode, model in models.items():
        score, decisions = evaluate_goals(model, lambda s,a: int(table[s,a]),
                                         lambda s,t: int(observations[s]), [0], goals,
                                         config["planning_horizon"], seed)
        result = model.summary()
        result.update(recovery(model, evidence, truth, table))
        result["planning"] = score
        result["trajectory"] = model.trajectory
        result["events"] = model.events
        result["stable_after_last_partition_change"] = max(
            [0]+[e["step"] for e in model.events])
        if mode == "split_merge":
            result["compute"] = compute_comparison(model, decisions)
            result["certified_planning"], _ = evaluate_goals(
                model, lambda s,a: int(table[s,a]), lambda s,t: int(observations[s]),
                [0], goals, config["planning_horizon"], seed, backend="certified")
        output["conditions"][mode] = result
    return output


def run_game(seed, config):
    # Existing environment and image encoder; semantic internals never enter learner.
    game = base.MicroGame(seed=seed)
    game.generate_random(wall_density=.18)
    np.random.seed(seed+700000)
    classify, prototypes, counts = make_classifier()
    def observe(state, t, evaluation=False):
        frame = base.render_visual_frame(game, state, t)
        return classify(frame, eval_mode=evaluation)
    hidden = game.get_initial_state()
    learner = HistoryModel(base.NUM_ACTIONS)
    first = int(observe(hidden, 0))
    learner.begin(first)
    policy = IdentificationPolicy(base.NUM_ACTIONS, seed+100000)
    stream, previous = [(None, first)], None
    for t in range(1, config["game_steps"]+1):
        partition = tuple(learner.mapping), tuple(learner.model["blocks"])
        action = policy.choose(learner.state(), learner.policy_counts(), partition != previous)
        previous = partition
        hidden = game.step(hidden, action)
        obs = int(observe(hidden, t))
        learner.observe(action, obs, t)
        stream.append((action, obs))
    models = {"split_merge": learner,
              "split_only": replay_stream(stream, base.NUM_ACTIONS, "split_only"),
              "fixed_history_2": replay_stream(stream, base.NUM_ACTIONS, "no_split", fixed_depth=2),
              "no_split": replay_stream(stream, base.NUM_ACTIONS, "no_split")}
    models["split_merge_certified"] = learner
    # Evaluate actual game success, goal identification from post-exploration
    # observed episodes, never from enumerating hidden states or goal coordinates.
    output = {"seed": seed, "stream": stream, "conditions": {}}
    for mode, model in models.items():
        goal_labels = set()
        state = game.get_initial_state()
        if game.is_goal(state): goal_labels.add(stream[0][1])
        for a, obs in stream[1:]:
            state = game.step(state, a)
            if game.is_goal(state): goal_labels.add(obs)
        target = [s for s,label in enumerate(model.labels) if label in goal_labels]
        successes, decisions, audits = 0, [], []
        then = time.perf_counter()
        psi = base.solve_fixed_field(dense(model.model["K"]), target, q=.90)[0] if target and mode!="split_merge_certified" else None
        np.random.seed(seed+900000)
        for trial in range(config["game_trials"]):
            state = game.get_initial_state()
            context = (int(observe(state, 0, True)),)
            for t in range(config["planning_horizon"]+1):
                if game.is_goal(state):
                    successes += 1; break
                z = model.encode(context)
                choices = {} if z is None else {a:model.model["rows"][z,a] for a in model.actions
                                               if (z,a) in model.model["rows"]}
                if not target or not choices or t == config["planning_horizon"]:
                    break
                if mode == "split_merge_certified":
                    audit=compute_comparison(model,[(z,tuple(target),choices)])[0]
                    audits.append(audit)
                    action=audit["adaptive"]["action"]
                else:
                    action = max(sorted(choices), key=lambda a: sum(float(p)*psi[v] for v,p in choices[a].items()))
                if len(decisions)<12 and trial==0:
                    decisions.append((z, tuple(target), choices))
                state = game.step(state, action)
                context = (context+(action, int(observe(state,t+1,True))))[-13:]
        result = model.summary()
        result.update({"successes":successes,"trials":config["game_trials"],
                       "success":successes/config["game_trials"],"observed_goal_labels":sorted(goal_labels),
                       "evaluation_seconds":time.perf_counter()-then,"trajectory":model.trajectory,"events":model.events})
        if mode == "split_merge": result["compute"] = compute_comparison(model, decisions)
        if mode == "split_merge_certified":result["decision_audits"]=audits
        output["conditions"][mode] = result
    return output


def default_config():
    finite = [{"n":(20,50,100)[i%3], "actions":(2,4,8)[(i//3)%3],
               "seed":930000+i,"kind":"lifted" if i%2 else "random",
               "steps":min(800, 8*(20,50,100)[i%3]*(2,4,8)[(i//3)%3])} for i in range(100)]
    partial = [{"n":2**(2+i%3),"actions":2,"seed":940000+i,"kind":"history","steps":600} for i in range(20)]
    return {"schema":1,"q":"9/10","finite_systems":finite,"partial_systems":partial,
            "games":[201,302,403,504,605],"game_steps":800,"game_trials":20,
            "planning_horizon":100,"evaluation_goals":4,"max_history":6,
            "initial_partition":"current observation and declared action availability",
            "ground_truth":"coarsest observation-preserving action congruence on reachable hidden states",
            "ablation_stream":"one split+merge exploration stream, frozen then replayed without evaluator feedback",
            "compute_sequence":"post-exploration FULL trajectories; all stopping rules receive identical decisions",
            "finite_budget_note":"bounded at 800 interactions; no guarantee of complete graph recovery",
            "observation_note":"finite random/lifted systems may not be identifiable by a suffix of depth <=6",
            "finite_generation":"100 total: 50 iid transition tables and 50 randomized two-copy lifts; balanced N/action settings",
            "partial_generation":"20 random observation colorings of binary shift-register finite systems; no register given to learner",
            "compute_selection":"first 12 FULL-trajectory decisions per model plus every certified-backend rollout decision",
            "development_exposure":"35-step smoke prefixes of finite seeds 930000/930001, partial 940000, game 201 were seen; this is not a blind held-out generalization claim",
            "dynamic_size_note":"peak/final are post-step active quotient counts, not retained evidence size",
            "merge_scope":"empirical graph only; unseen actions remain unknown",
            "tie_rule":"seeded uniform exploration; smallest action ID for planner ties",
            "success_criteria":{"recovery":.99,"eps":1e-10,"certified_agreement":1.,
                                "iteration_ratio":.5,"dynamic_fraction":.5,"partial_success":.90,
                                "max_history_fraction":.20,"game_not_worse":True}}


def aggregate(results, partial, games, config):
    finite = [r["conditions"]["split_merge"] for r in results]
    history = [r["conditions"]["split_merge"] for r in partial]
    compute = [c for r in results+partial+games for c in r["conditions"]["split_merge"].get("compute",[])]
    compute += [c for r in results+partial for c in r["conditions"]["split_merge"]["certified_planning"]["decision_audits"]]
    compute += [c for r in games for c in r["conditions"]["split_merge_certified"]["decision_audits"]]
    certified = [c for c in compute if c["adaptive"]["certified"]]
    avg = lambda xs: float(np.mean(xs)) if xs else None
    def rate(items, success="successes", total="trials"):
        den = sum(x[total] for x in items)
        return sum(x[success] for x in items)/den if den else None
    full = avg([c["full"]["iterations"] for c in compute])
    adaptive = avg([c["adaptive"]["iterations"] for c in compute])
    game_rates = {m:rate([r["conditions"][m] for r in games]) for m in
                  ("fixed_history_2","no_split","split_only","split_merge","split_merge_certified")}
    metrics = {"finite_system_count":len(finite),"true_quotient_recovery":avg([r["recovered"] for r in finite]),
               "eps_K":max([r["eps_K"] for r in finite],default=0),
               "eps_action":max([r["eps_action"] for r in finite],default=0),
               "initial_states_mean":avg([r["initial_states"] for r in finite]),
               "peak_states_mean":avg([r["peak_states"] for r in finite]),
               "final_states_mean":avg([r["final_states"] for r in finite]),
               "split_count":sum(r["split_count"] for r in finite),"merge_count":sum(r["merge_count"] for r in finite),
               "dynamic_fraction":avg([r["peak_states"]>r["final_states"] for r in finite]),
               "partial_success":rate([r["planning"] for r in history]),
               "partial_mean_depth":avg([r["mean_depth"] for r in history]),
               "partial_max_depth_usage":avg([r["max_depth_usage"] for r in history]),
               "decision_count":len(compute),"certified_decisions":len(certified),
               "certified_action_agreement":avg([c["adaptive_agrees"] for c in certified]),
               "all_adaptive_action_agreement":avg([c["adaptive_agrees"] for c in compute]),
               "canonical_full_agreement":avg([c["canonical_full_agrees"] for c in compute]),
               "full_mean_iterations":full,"adaptive_mean_iterations":adaptive,
               "iteration_reduction":1-adaptive/full if full else None,
               "full_solve_fraction":avg([not c["adaptive"]["certified"] for c in compute]),
               "max_adaptive_iterations":max([c["adaptive"]["iterations"] for c in compute],default=0),
               "compute_cpu_seconds":{m:sum(c[m]["cpu_seconds"] for c in compute) for m in ("full","cheap","adaptive")},
               "matvecs":{m:sum(c[m]["matvecs"] for c in compute) for m in ("full","cheap","adaptive")},
               "rational_certification_seconds":sum(c["adaptive"]["certificate_seconds"] for c in compute),
               "canonical_verification_seconds":sum(c["canonical_verification_seconds"] for c in compute),
               "game_success":game_rates,"certificate_scope":"exact learned empirical graph; not true unobserved environment"}
    criteria = config["success_criteria"]
    metrics["pass"] = {"recovery":metrics["true_quotient_recovery"]>=criteria["recovery"],
                       "congruence":max(metrics["eps_K"],metrics["eps_action"])<=criteria["eps"],
                       "certified_agreement":bool(certified) and metrics["certified_action_agreement"]==1,
                       "compute":bool(full) and adaptive/full<=.5,
                       "dynamic":metrics["dynamic_fraction"]>=.5,
                       "partial_history":metrics["partial_success"] is not None and metrics["partial_success"]>=.9,
                       "history_usage":metrics["partial_max_depth_usage"]<.2,
                       "game":game_rates["split_merge"]>=game_rates["fixed_history_2"]}
    return metrics


def plots(out, results, partial, games, metrics):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    def save(name, title, xlabel, ylabel):
        plt.title(title); plt.xlabel(xlabel); plt.ylabel(ylabel)
        plt.tight_layout(); plt.savefig(out/name,dpi=140); plt.close()
    records = [r["conditions"]["split_merge"] for r in results]
    for r in records:
        plt.plot([t["step"] for t in r["trajectory"]],[t["N_blocks"] for t in r["trajectory"]],alpha=.15)
    save("state_count_over_time.png","Observed model size (100 systems)","Interactions","Blocks")
    plt.bar(["split","merge"],[metrics["split_count"],metrics["merge_count"]])
    save("split_merge_events.png","Actual events","Event","Count")
    plt.bar(["recovered","not recovered"],[sum(r["recovered"] for r in records),sum(not r["recovered"] for r in records)])
    save("quotient_recovery.png","Full reachable quotient recovery","Result","Systems")
    plt.hist([r["conditions"]["split_merge"]["mean_depth"] for r in partial],bins=7)
    save("history_depth.png","Selected history depth (partial observation)","Mean depth","Systems")
    cs=[c for r in results+partial+games for c in r["conditions"]["split_merge"].get("compute",[])]
    plt.bar(["FULL","CHEAP","ADAPTIVE"],[np.mean([c[m]["iterations"] for c in cs]) for m in ("full","cheap","adaptive")])
    save("compute_iterations.png","Same decision sequence","Stopping rule","Mean iterations")
    plt.scatter([c["full"]["margin"] for c in cs],[c["adaptive"]["iterations"] for c in cs],s=8)
    save("margin_vs_compute.png","Measured margin and work","FULL action margin","Adaptive iterations")
    for r in records:
        plt.plot([t["step"] for t in r["trajectory"]],[t["evidence_logical_bytes"] for t in r["trajectory"]],alpha=.15)
    save("memory_scaling.png","Stored history/transition evidence (logical bytes)","Interactions","Bytes")
    modes=list(MODES)
    plt.bar(modes,[np.mean([r["conditions"][m]["recovered"] for r in results]) for m in modes])
    save("ablation.png","Representation ablation on identical observed stream","Condition","Quotient recovery fraction")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--output",required=True)
    parser.add_argument("--development-smoke",action="store_true")
    args=parser.parse_args()
    out=Path(args.output)
    out.mkdir(parents=True,exist_ok=True)
    if (out/"config.json").exists():
        raise SystemExit("Refusing to overwrite an existing run")
    config=default_config()
    if args.development_smoke:
        config["finite_systems"]=config["finite_systems"][:2]
        config["partial_systems"]=config["partial_systems"][:1]
        for s in config["finite_systems"]+config["partial_systems"]: s["steps"]=35
        config["games"]=[201];config["game_steps"]=35;config["game_trials"]=2
        config["development_only"]=True
    files=[Path(__file__),ROOT/"scripts/evaluate_fixed_field_congruence.py",ROOT/"scripts/active_world_discovery_v2.py",
           ROOT/"tests/test_adaptive_refinement.py"]
    snapshot={"experiment_id":out.name,"timestamp":datetime.now(timezone.utc).isoformat(),
              "branch":subprocess.check_output(["git","branch","--show-current"],cwd=ROOT,text=True).strip(),
              "HEAD":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
              "git_status":subprocess.check_output(["git","status","--short"],cwd=ROOT,text=True).splitlines(),
              "sha256":{str(p.relative_to(ROOT)):digest(p) for p in files},
              "python":sys.version,"numpy":np.__version__,"command":sys.argv}
    snapshot_path=out/"source_snapshot.json"
    if snapshot_path.exists():
        snapshot["before_development"]=json.loads(snapshot_path.read_text(encoding="utf-8-sig"))
    dump(snapshot_path,snapshot);dump(out/"config.json",config)
    dump(out/"environment.json",{"python":sys.version,"executable":sys.executable,
                                "dependencies":subprocess.check_output([sys.executable,"-m","pip","freeze"],text=True).splitlines()})
    dump(out/"rng_seeds.json",{"finite":[s["seed"] for s in config["finite_systems"]],
                              "partial":[s["seed"] for s in config["partial_systems"]],"games":config["games"]})
    shutil.copy2(__file__,out/Path(__file__).name)
    for p in files[1:]:
        target=out/("executed_"+p.name)
        if target.exists():raise RuntimeError("Source snapshot already exists")
        shutil.copy2(p,target)
    results,partial,games=[],[],[]
    started=time.perf_counter()
    with (out/"run.log").open("x",encoding="utf-8",buffering=1) as log:
        def emit(msg): print(msg,flush=True);log.write(msg+"\n")
        emit("FROZEN "+snapshot["sha256"][str(Path(__file__).relative_to(ROOT))])
        for name,specs,bucket in (("finite",config["finite_systems"],results),("partial",config["partial_systems"],partial)):
            for i,spec in enumerate(specs):
                r=run_finite(spec,config);bucket.append(r)
                dump(out/f"{name}_{i:03d}.json",r)
                emit(f"{name} {i+1}/{len(specs)} seed={spec['seed']} completed seconds={time.perf_counter()-started:.2f}")
        for seed in config["games"]:
            r=run_game(seed,config);games.append(r);dump(out/f"game_{seed}.json",r)
            emit(f"game {seed} completed seconds={time.perf_counter()-started:.2f}")
        metrics=aggregate(results,partial,games,config)
        metrics["experiment_id"]=out.name;metrics["source_sha256"]=digest(__file__)
        metrics["wall_seconds"]=time.perf_counter()-started
        metrics["source_unchanged"]=all(digest(ROOT/p)==h for p,h in snapshot["sha256"].items())
        dump(out/"metrics.json",metrics)
        plots(out,results,partial,games,metrics)
        emit(json.dumps(metrics,indent=2))


if __name__ == "__main__":
    main()
