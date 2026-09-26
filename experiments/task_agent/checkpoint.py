"""The 2026-09-26 checkpoint Task-Agent experiment, on the canonical learner and world.

The original script (`mortra_task_agent_experiment.py`) ran in a sandbox against
`/mnt/data/mortra_integrated_response_system.py`, a module that is not in this
repository. This file is that script with one change: the learner and the world
are the repository's canonical ones -- `experiments.game_frontier_v1.frozen`
(the hash-checked StructuralLearner) and `experiments.game_frontier_v11.world`
(the finite-program Engine) -- reached through a thin adapter that renames
methods and nothing else. Every function below that carries the original's name
is the original's code.

Whether the port is faithful is not argued; it is checked. `compare` reads the
registered CSVs of the original run and reports every row that differs.

One method is added, and only one: `optimal_product`, which plans on exactly the
same product graph as `product_compiler` but with the Bellman-optimal first-exit
value q^d (d the shortest distance to acceptance in that graph) in place of the
linear field (I - qK)^-1 g. Nothing else about it differs -- the same product
construction, the same tie-breaking, the same executor, the same horizon -- so
any difference between the two is the difference between a linear field and an
optimal one.
"""
from __future__ import annotations

import copy
import csv
import json
import random
import time
from collections import deque
from pathlib import Path

import numpy as np
from scipy.sparse import csr_matrix, identity
from scipy.sparse.linalg import splu

from experiments.game_frontier_v1.frozen import StructuralLearner
from experiments.game_frontier_v11.world import Engine as CanonicalEngine

Q = 0.90
BUDGETS = (512, 2048, 4096, 8192)
TASKS_PER_BASIC_TYPE = 12
BRANCH_TASKS_PER_WORLD = 10
HORIZON = 512
SEEDS = (2101, 2202, 2303, 2404, 2505, 2606, 2707, 2808)
METHODS = ("static_source", "dynamic_source", "product_compiler", "optimal_product")


# ---------------------------------------------------------------------------
# The adapter: the original's method names on the canonical classes
# ---------------------------------------------------------------------------

class Learner:
    """The canonical StructuralLearner under the names the original script used."""

    def __init__(self, num_actions):
        self.core = StructuralLearner(num_actions)

    # names ---------------------------------------------------------------
    @property
    def A(self):
        return self.core.num_actions

    @property
    def i2s(self):
        return self.core.id_to_state

    @property
    def s2i(self):
        return self.core.state_to_id

    @property
    def counts(self):
        return self.core.counts

    # methods -------------------------------------------------------------
    def add(self, state):
        return self.core.get_or_add_id(state)

    def rec(self, u, a, v):
        self.core.record_transition(u, a, v)

    def select(self, u):
        return self.core.select_action(u)

    def K(self):
        return csr_matrix(self.core.build_k_support())


class Engine:
    """The canonical finite-program Engine; `dom` is its `domains`."""

    def __init__(self, genome):
        self.core = CanonicalEngine(genome)
        self.initial = self.core.initial
        self.num_actions = self.core.num_actions
        self.dom = self.core.domains

    def step(self, state, action):
        return self.core.step(state, action)


# ---------------------------------------------------------------------------
# The original script's functions, unchanged
# ---------------------------------------------------------------------------

def train_snapshots(engine, budgets=BUDGETS):
    learner = Learner(engine.num_actions)
    cur = engine.initial
    u = learner.add(cur)
    out = {}
    prev = 0
    for B in budgets:
        for _ in range(prev, B):
            a = learner.select(u)
            ns = engine.step(cur, a)
            v = learner.add(ns)
            learner.rec(u, a, v)
            cur, u = ns, v
        out[B] = copy.deepcopy(learner)
        prev = B
    return out


def modal_actions(learner, u):
    out = {}
    for a in range(learner.A):
        d = learner.counts.get((u, a))
        if d:
            out[a] = max(d.items(), key=lambda kv: kv[1])[0]
    return out


def modal_edges(learner):
    return [list(modal_actions(learner, u).values()) for u in range(len(learner.i2s))]


def distances(edges, start):
    d = {start: 0}
    q = deque([start])
    while q:
        u = q.popleft()
        for v in edges[u]:
            if v not in d:
                d[v] = d[u] + 1
                q.append(v)
    return d


class Predicate:
    def __init__(self, spec):
        self.spec = spec

    def __call__(self, state):
        kind = self.spec["kind"]
        if kind == "exact":
            return tuple(state) == tuple(self.spec["state"])
        if kind == "var_eq":
            return state[self.spec["var"]] == self.spec["value"]
        raise ValueError(kind)


class TaskAutomaton:
    def __init__(self, task_spec):
        self.spec = task_spec
        self.op = task_spec["op"]
        if self.op in ("SEQ", "ALL"):
            self.preds = [Predicate(p) for p in task_spec["goals"]]
            if self.op == "SEQ":
                self.num_memory = len(self.preds) + 1
                self.accept = len(self.preds)
            else:
                self.num_memory = 1 << len(self.preds)
                self.accept = self.num_memory - 1
        elif self.op == "BRANCH":
            self.A = Predicate(task_spec["A"])
            self.B = Predicate(task_spec["B"])
            self.CA = Predicate(task_spec["CA"])
            self.CB = Predicate(task_spec["CB"])
            self.num_memory = 4
            self.accept = 3
        else:
            raise ValueError(self.op)

    def update(self, memory, world_state):
        if self.op == "SEQ":
            while memory < self.accept and self.preds[memory](world_state):
                memory += 1
            return memory
        if self.op == "ALL":
            for i, pred in enumerate(self.preds):
                if pred(world_state):
                    memory |= (1 << i)
            return memory
        if memory == 0:
            if self.A(world_state):
                memory = 1
            elif self.B(world_state):
                memory = 2
        if memory == 1 and self.CA(world_state):
            memory = 3
        if memory == 2 and self.CB(world_state):
            memory = 3
        return memory

    def initial_memory(self, world_state):
        return self.update(0, world_state)

    def done(self, memory):
        return memory == self.accept

    def static_goal_ids(self, learner):
        predicates = self.preds if self.op in ("SEQ", "ALL") else [self.A, self.B, self.CA, self.CB]
        ids = set()
        for pred in predicates:
            ids.update(u for u, s in enumerate(learner.i2s) if pred(s))
        return sorted(ids)

    def current_goal_ids(self, memory, learner):
        if self.done(memory):
            return []
        if self.op == "SEQ":
            pred = self.preds[memory]
            return [u for u, s in enumerate(learner.i2s) if pred(s)]
        if self.op == "ALL":
            ids = set()
            for i, pred in enumerate(self.preds):
                if not ((memory >> i) & 1):
                    ids.update(u for u, s in enumerate(learner.i2s) if pred(s))
            return sorted(ids)
        preds = [self.A, self.B] if memory == 0 else ([self.CA] if memory == 1 else [self.CB])
        ids = set()
        for pred in preds:
            ids.update(u for u, s in enumerate(learner.i2s) if pred(s))
        return sorted(ids)


def solve_base_field(learner, goal_ids):
    if not goal_ids:
        return None
    K = learner.K()
    g = np.zeros(K.shape[0], dtype=float)
    g[goal_ids] = 1.0
    return splu(identity(K.shape[0], format="csc") - Q * K.tocsc()).solve(g)


def reverse_reachable_base(learner, goal_ids):
    n = len(learner.i2s)
    rev = [[] for _ in range(n)]
    for u in range(n):
        for v in modal_actions(learner, u).values():
            rev[v].append(u)
    seen = set(goal_ids)
    q = deque(goal_ids)
    while q:
        v = q.popleft()
        for u in rev[v]:
            if u not in seen:
                seen.add(u)
                q.append(u)
    return seen


def execute_source_policy(learner, engine, automaton, start, dynamic_memory=False, horizon=HORIZON):
    start = tuple(start)
    if start not in learner.s2i:
        return False, 0
    cur = start
    memory = automaton.initial_memory(cur)
    cache = {}
    steps = 0
    if not dynamic_memory:
        goals = automaton.static_goal_ids(learner)
        psi = solve_base_field(learner, goals)
        reachable = reverse_reachable_base(learner, goals) if goals else set()
    while steps < horizon and not automaton.done(memory):
        if cur not in learner.s2i:
            return False, steps
        u = learner.s2i[cur]
        if dynamic_memory:
            if memory not in cache:
                goals = automaton.current_goal_ids(memory, learner)
                cache[memory] = (solve_base_field(learner, goals),
                                 reverse_reachable_base(learner, goals) if goals else set())
            psi, reachable = cache[memory]
        if psi is None or u not in reachable:
            return False, steps
        choices = []
        for a, v in modal_actions(learner, u).items():
            choices.append((float(psi[v]), -a, a))
        if not choices:
            return False, steps
        action = max(choices)[2]
        cur = engine.step(cur, action)
        memory = automaton.update(memory, cur)
        steps += 1
    return automaton.done(memory), steps


def build_product_model(learner, automaton, start, *, solve=True):
    start = tuple(start)
    if start not in learner.s2i:
        return None
    u0 = learner.s2i[start]
    m0 = automaton.initial_memory(start)
    z0 = (u0, m0)
    ids = {z0: 0}
    states = [z0]
    transitions = []
    q = deque([z0])
    while q:
        u, m = q.popleft()
        row = {}
        for a, v in modal_actions(learner, u).items():
            m2 = automaton.update(m, learner.i2s[v])
            z2 = (v, m2)
            if z2 not in ids:
                ids[z2] = len(states)
                states.append(z2)
                q.append(z2)
            row[a] = ids[z2]
        transitions.append(row)
    n = len(states)
    rr, cc, vv = [], [], []
    for i, row in enumerate(transitions):
        if not row:
            continue
        w = 1.0 / len(row)
        for _, j in row.items():
            rr.append(i)
            cc.append(j)
            vv.append(w)
    K = csr_matrix((vv, (rr, cc)), shape=(n, n), dtype=float)
    goals = [i for i, (_, m) in enumerate(states) if automaton.done(m)]
    rev = [[] for _ in range(n)]
    for i, row in enumerate(transitions):
        for j in row.values():
            rev[j].append(i)
    reachable = set(goals)
    qq = deque(goals)
    while qq:
        v = qq.popleft()
        for u in rev[v]:
            if u not in reachable:
                reachable.add(u)
                qq.append(u)
    if 0 not in reachable:
        return {"reachable": False, "n_product_states": n, "ids": ids, "states": states,
                "transitions": transitions}
    # solve=False is for the optimal field, which needs the graph and not psi;
    # the default keeps the original's behaviour exactly
    psi = None
    if solve:
        g = np.zeros(n, dtype=float)
        g[goals] = 1.0
        psi = splu(identity(n, format="csc") - Q * K.tocsc()).solve(g)
    return {"reachable": True, "n_product_states": n, "ids": ids, "states": states,
            "transitions": transitions, "psi": psi, "goals": goals, "reverse": rev}


def product_shortest_path(learner, automaton, start):
    start = tuple(start)
    if start not in learner.s2i:
        return None
    z0 = (learner.s2i[start], automaton.initial_memory(start))
    q = deque([(z0, 0)])
    seen = {z0}
    while q:
        (u, m), d = q.popleft()
        if automaton.done(m):
            return d
        for _, v in modal_actions(learner, u).items():
            m2 = automaton.update(m, learner.i2s[v])
            z2 = (v, m2)
            if z2 not in seen:
                seen.add(z2)
                q.append((z2, d + 1))
    return None


def execute_product_policy(learner, engine, automaton, start, horizon=HORIZON, *, value="linear"):
    """The original executor. `value` chooses the field it ascends; nothing else changes.

    `value="linear"` is the original: psi = (I - qK)^-1 g on the product graph.
    `value="optimal"` is the Bellman-optimal first-exit value on the same graph,
    q^d with d the shortest distance to acceptance, which is computed by one
    reverse breadth-first search and no linear solve at all.
    """
    model = build_product_model(learner, automaton, start, solve=(value != "optimal"))
    if model is None or not model["reachable"]:
        return False, 0, (0 if model is None else model["n_product_states"])
    if value == "optimal":
        field = optimal_field(model)
    else:
        field = model["psi"]
    cur = tuple(start)
    memory = automaton.initial_memory(cur)
    steps = 0
    while steps < horizon and not automaton.done(memory):
        if cur not in learner.s2i:
            return False, steps, model["n_product_states"]
        z = (learner.s2i[cur], memory)
        if z not in model["ids"]:
            return False, steps, model["n_product_states"]
        i = model["ids"][z]
        choices = []
        for a, j in model["transitions"][i].items():
            choices.append((float(field[j]), -a, a))
        if not choices:
            return False, steps, model["n_product_states"]
        action = max(choices)[2]
        cur = engine.step(cur, action)
        memory = automaton.update(memory, cur)
        steps += 1
    return automaton.done(memory), steps, model["n_product_states"]


def optimal_field(model):
    """q^d on the product graph: the value of acting optimally, not of acting at random.

    The linear field (I - qK)^-1 g is the discounted value of the *uniform
    random* policy over tried actions -- the successor representation of that
    policy applied to the source. Ascending it greedily is a heuristic. The
    optimal first-exit value is V(z) = 1 on acceptance and q * max_a V(z')
    elsewhere, which for a deterministic graph is q^d(z), and ascending it is a
    shortest path by construction. States that cannot reach acceptance get 0.
    """
    n = model["n_product_states"]
    reverse = model["reverse"]
    depth = {g: 0 for g in model["goals"]}
    queue = deque(model["goals"])
    while queue:
        v = queue.popleft()
        for u in reverse[v]:
            if u not in depth:
                depth[u] = depth[v] + 1
                queue.append(u)
    field = np.zeros(n, dtype=float)
    for i, d in depth.items():
        field[i] = Q ** d
    return field


def generate_basic_tasks(learner, seed, n=TASKS_PER_BASIC_TYPE):
    edges = modal_edges(learner)
    rng = random.Random(seed)
    N = len(learner.i2s)
    out = []
    counts = {"sequence": 0, "all_of": 0, "condition_then": 0}
    tries = 0
    while min(counts.values()) < n and tries < 50000:
        tries += 1
        s = rng.randrange(N)
        ds = distances(edges, s)
        A = [v for v, d in ds.items() if 3 <= d <= 10 and v != s]
        if not A:
            continue
        a = rng.choice(A)
        da = distances(edges, a)
        B = [v for v, d in da.items() if 3 <= d <= 10 and v not in (s, a)]
        if not B:
            continue
        b = rng.choice(B)
        db = distances(edges, b)
        C = [v for v, d in db.items() if 3 <= d <= 10 and v not in (s, a, b)]
        if C and counts["sequence"] < n:
            c = rng.choice(C)
            spec = {"op": "SEQ",
                    "goals": [{"kind": "exact", "state": list(learner.i2s[x])} for x in (a, b, c)]}
            out.append(("sequence", learner.i2s[s], spec))
            counts["sequence"] += 1
        if C and counts["all_of"] < n:
            c = rng.choice(C)
            goals = [a, b, c]
            rng.shuffle(goals)
            spec = {"op": "ALL",
                    "goals": [{"kind": "exact", "state": list(learner.i2s[x])} for x in goals]}
            out.append(("all_of", learner.i2s[s], spec))
            counts["all_of"] += 1
        if counts["condition_then"] < n:
            s0 = learner.i2s[s]
            sx = learner.i2s[a]
            differing_vars = [j for j, (x, y) in enumerate(zip(s0, sx)) if x != y]
            if differing_vars:
                j = rng.choice(differing_vars)
                value = sx[j]
                dy = distances(edges, a)
                ys = [v for v, d in dy.items() if 3 <= d <= 10 and learner.i2s[v][j] != value]
                if not ys:
                    ys = [v for v, d in dy.items() if 3 <= d <= 10]
                if ys:
                    y = rng.choice(ys)
                    spec = {"op": "SEQ",
                            "goals": [{"kind": "var_eq", "var": j, "value": value},
                                      {"kind": "exact", "state": list(learner.i2s[y])}]}
                    out.append(("condition_then", learner.i2s[s], spec))
                    counts["condition_then"] += 1
    if min(counts.values()) != n:
        raise RuntimeError(("task generation failed", counts))
    return out


def generate_branch_tasks(learner, seed, n=BRANCH_TASKS_PER_WORLD):
    edges = modal_edges(learner)
    rng = random.Random(seed)
    N = len(learner.i2s)
    cache = {}

    def D(u):
        if u not in cache:
            cache[u] = distances(edges, u)
        return cache[u]

    out = []
    tries = 0
    while len(out) < n and tries < 100000:
        tries += 1
        s = rng.randrange(N)
        ds = D(s)
        near = [v for v, d in ds.items() if 2 <= d <= 5 and v != s]
        far = [v for v, d in ds.items() if 4 <= d <= 8 and v != s]
        if not near or not far:
            continue
        a = rng.choice(near)
        b = rng.choice(far)
        if a == b:
            continue
        da = D(a)
        db = D(b)
        ca_candidates = [v for v, d in da.items() if 8 <= d <= 16]
        cb_candidates = [v for v, d in db.items() if 2 <= d <= 5]
        if not ca_candidates or not cb_candidates:
            continue
        ca = rng.choice(ca_candidates)
        cb = rng.choice(cb_candidates)
        route_a = ds[a] + da[ca]
        route_b = ds[b] + db[cb]
        if route_a < route_b + 4:
            continue
        spec = {"op": "BRANCH",
                "A": {"kind": "exact", "state": list(learner.i2s[a])},
                "B": {"kind": "exact", "state": list(learner.i2s[b])},
                "CA": {"kind": "exact", "state": list(learner.i2s[ca])},
                "CB": {"kind": "exact", "state": list(learner.i2s[cb])},
                "generation_distance_A": int(route_a),
                "generation_distance_B": int(route_b)}
        out.append(("branch", learner.i2s[s], spec))
    if len(out) != n:
        raise RuntimeError(("branch task generation failed", len(out)))
    return out


# ---------------------------------------------------------------------------
# The run, and the comparison with what the original registered
# ---------------------------------------------------------------------------

WORLDS = Path(__file__).with_name("data")/"archived_worlds.json"
REGISTERED = Path(__file__).with_name("data")/"registered"


def load_world(registration=None, seed=None):
    """One archived world: from the committed worlds file, or from a registration directory.

    The committed file holds the eight genomes copied out of
    `theory-registration/restored/{seed}.json` (element 0, as the original script
    read them), with each source file's SHA-256 and the workflow run it came from.
    """
    if registration is None or Path(registration).suffix == ".json":
        doc = json.loads(Path(registration or WORLDS).read_text(encoding="utf-8"))
        world = doc["worlds"][str(seed)]
        parent = {"game_hash": world["game_hash"], "genome": world["genome"]}
    else:
        path = Path(registration)/"restored"/f"{seed}.json"
        parent = json.loads(path.read_text(encoding="utf-8"))[0]
    return parent, Engine(parent["genome"])


def run(registration, *, seeds=SEEDS, methods=METHODS, log=print):
    """Every world, every budget, every task, every method. Returns the rows."""
    records, task_specs, world_rows, timings = [], [], [], {m: 0.0 for m in methods}
    worlds = {}
    for seed in seeds:
        parent, engine = load_world(registration, seed)
        snapshots = train_snapshots(engine)
        final_learner = snapshots[8192]
        tasks = generate_basic_tasks(final_learner, 120000+seed)
        tasks += generate_branch_tasks(final_learner, 220000+seed)
        worlds[seed] = (engine, snapshots, tasks)
        for task_id, (task_type, start, task_spec) in enumerate(tasks):
            task_specs.append({"seed": seed, "task_id": task_id, "task_type": task_type,
                               "start": json.dumps(list(start)),
                               "task_spec": json.dumps(task_spec, sort_keys=True)})
        for B, learner in snapshots.items():
            for task_id, (task_type, start, task_spec) in enumerate(tasks):
                automaton = TaskAutomaton(task_spec)
                shortest = product_shortest_path(learner, automaton, start)
                for method in methods:
                    started = time.perf_counter()
                    if method == "static_source":
                        success, steps = execute_source_policy(learner, engine, automaton, start,
                                                               dynamic_memory=False)
                        product_states = 0
                    elif method == "dynamic_source":
                        success, steps = execute_source_policy(learner, engine, automaton, start,
                                                               dynamic_memory=True)
                        product_states = 0
                    elif method == "product_compiler":
                        success, steps, product_states = execute_product_policy(
                            learner, engine, automaton, start, value="linear")
                    else:
                        success, steps, product_states = execute_product_policy(
                            learner, engine, automaton, start, value="optimal")
                    timings[method] += time.perf_counter()-started
                    records.append({"seed": seed, "budget": B, "task_id": task_id,
                                    "task_type": task_type, "method": method,
                                    "success": bool(success), "steps": int(steps),
                                    "shortest_product_steps": shortest,
                                    "base_learned_states": len(learner.i2s),
                                    "task_memory_states": automaton.num_memory,
                                    "reachable_product_states": int(product_states)})
        world_rows.append({"seed": seed, "game_hash": parent["game_hash"],
                           "actions": engine.num_actions, "variables": len(engine.dom),
                           **{f"learned_states_{B}": len(snapshots[B].i2s) for B in BUDGETS},
                           "tasks": len(tasks)})
        log(f"world {seed}: {len(tasks)} tasks, learned states "
            f"{[len(snapshots[B].i2s) for B in BUDGETS]}")
    return records, task_specs, world_rows, timings, worlds


def _read_csv(path):
    with open(path, encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def compare(registered_dir, records, task_specs, world_rows):
    """Every registered row against its reproduction. The count of differences is the result."""
    registered_dir = Path(registered_dir)
    out = {}
    worlds = {int(r["seed"]): r for r in _read_csv(registered_dir/"task_agent_worlds.csv")}
    world_diffs = []
    for row in world_rows:
        old = worlds[row["seed"]]
        for key in ("game_hash", "actions", "variables", "learned_states_512", "learned_states_2048",
                    "learned_states_4096", "learned_states_8192", "tasks"):
            if str(row[key]) != str(old[key]):
                world_diffs.append((row["seed"], key, old[key], row[key]))
    out["worlds"] = {"rows": len(world_rows), "differences": world_diffs}

    specs = {(int(r["seed"]), int(r["task_id"])): r for r in _read_csv(registered_dir/"task_agent_task_specs.csv")}
    spec_diffs = [(s["seed"], s["task_id"]) for s in task_specs
                  if specs.get((s["seed"], s["task_id"]), {}).get("task_spec") != s["task_spec"]
                  or specs.get((s["seed"], s["task_id"]), {}).get("start") != s["start"]]
    out["task_specs"] = {"rows": len(task_specs), "registered": len(specs), "differences": spec_diffs[:20],
                         "difference_count": len(spec_diffs)}

    old = {(int(r["seed"]), int(r["budget"]), int(r["task_id"]), r["method"]): r
           for r in _read_csv(registered_dir/"task_agent_results.csv")}
    diffs = []
    compared = 0
    for r in records:
        key = (r["seed"], r["budget"], r["task_id"], r["method"])
        if key not in old:
            continue
        compared += 1
        o = old[key]
        shortest_old = None if o["shortest_product_steps"] in ("", "nan") else int(float(o["shortest_product_steps"]))
        if (str(r["success"]) != o["success"] or str(r["steps"]) != o["steps"]
                or r["shortest_product_steps"] != shortest_old
                or str(r["reachable_product_states"]) != o["reachable_product_states"]):
            diffs.append({"key": key, "registered": [o["success"], o["steps"], shortest_old,
                                                     o["reachable_product_states"]],
                          "reproduced": [r["success"], r["steps"], r["shortest_product_steps"],
                                         r["reachable_product_states"]]})
    out["results"] = {"registered_rows": len(old), "compared": compared,
                      "difference_count": len(diffs), "differences": diffs[:20]}
    return out
