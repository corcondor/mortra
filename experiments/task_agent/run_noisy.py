"""Linear against optimal fields when actions slip. Protocol fixed here, before any noisy run.

PROTOCOL

  worlds    the eight archived worlds, with slip 0, 0.05, 0.10, 0.20
  learner   the canonical StructuralLearner, 8192 steps in the slipping world
  tasks     the registered generators (same seeds) run on that learned model:
            46 per world, 368 per slip level
  planners  linear, linear_empirical, shortest, expected (see noisy.py)
  episodes  horizon 512; one execution seed per (world, slip, task), shared by
            every planner, so all four face the same sequence of slips
  outcome   success within 512 steps; steps among successes; paired per task
  slip 0    must reproduce the checkpoint run: linear = product_compiler and
            shortest = optimal_product, step for step. If it does not, the run
            is wrong and nothing else in it is reported

    python -m experiments.task_agent.run_noisy --registration <dir> --output <dir>
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from pathlib import Path

from experiments.task_agent import checkpoint, noisy

SLIPS = (0.0, 0.05, 0.10, 0.20)


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registration", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--slips", nargs="*", type=float, default=list(SLIPS))
    parser.add_argument("--seeds", nargs="*", type=int, default=list(checkpoint.SEEDS))
    parser.add_argument("--shard", default="all")
    parser.add_argument("--replicates", type=int, default=0,
                        help="0 = the preregistered single episode per task; R > 0 = a "
                             "replication with R further execution seeds, rep1..repR, none of "
                             "them the preregistered one")
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    path = output/f"episodes-{arguments.shard}.csv"
    replicates = [None] if arguments.replicates == 0 else list(range(1, arguments.replicates+1))
    fields = ["slip", "seed", "task_id", "task_type", "method", "replicate", "success", "steps",
              "replans", "why", "shortest_in_model", "learned_states"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for slip in arguments.slips:
            for seed in arguments.seeds:
                parent, _ = checkpoint.load_world(arguments.registration, seed)
                trainer = noisy.SlipEngine(parent["genome"], slip, f"train:{seed}:{slip}")
                learner = noisy.train(trainer, 8192)
                tasks = checkpoint.generate_basic_tasks(learner, 120000+seed)
                tasks += checkpoint.generate_branch_tasks(learner, 220000+seed)
                for task_id, (task_type, start, spec) in enumerate(tasks):
                    automaton = checkpoint.TaskAutomaton(spec)
                    shortest = checkpoint.product_shortest_path(learner, automaton, start)
                    for replicate in replicates:
                        tag = f"exec:{seed}:{task_id}:{slip}" + \
                            ("" if replicate is None else f":rep{replicate}")
                        for method in noisy.METHODS:
                            engine = noisy.SlipEngine(parent["genome"], slip, tag)
                            result = noisy.run_episode(learner, engine, automaton, start, method)
                            writer.writerow({"slip": slip, "seed": seed, "task_id": task_id,
                                             "task_type": task_type, "method": method,
                                             "replicate": 0 if replicate is None else replicate,
                                             "shortest_in_model": shortest,
                                             "learned_states": len(learner.i2s), **result})
                handle.flush()
                say(f"slip {slip} world {seed}: {len(tasks)} tasks, "
                    f"{len(learner.i2s)} learned states")
    say(f"wrote {path}")


def expected_cost(paths, output, *, horizon=512, draws=10000, seed=20260926):
    """Per task, the mean cost over replicates (steps, or the horizon on failure), paired.

    The comparison of two planners is the mean over tasks of their per-task cost
    difference, with a 95% interval from resampling tasks. A task is the unit
    because tasks, not episodes, are what was sampled.
    """
    import random

    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as handle:
            rows += list(csv.DictReader(handle))
    cost = defaultdict(list)
    for r in rows:
        c = int(r["steps"]) if r["success"] == "True" else horizon
        cost[(float(r["slip"]), r["seed"], r["task_id"], r["method"])].append(c)
    mean_cost = {k: sum(v)/len(v) for k, v in cost.items()}
    slips = sorted({k[0] for k in mean_cost})
    tasks_at = defaultdict(set)
    for (slip, seed, task_id, _method) in mean_cost:
        tasks_at[slip].add((seed, task_id))
    rng = random.Random(seed)
    table, pairs = [], []
    for slip in slips:
        tasks = sorted(tasks_at[slip])
        for method in noisy.METHODS:
            values = [mean_cost[(slip, s, t, method)] for s, t in tasks]
            episodes = sum(len(cost[(slip, s, t, method)]) for s, t in tasks)
            failures = sum(v == horizon for s, t in tasks for v in cost[(slip, s, t, method)])
            table.append({"slip": slip, "method": method, "tasks": len(tasks),
                          "episodes": episodes, "failures": failures,
                          "mean_cost": round(sum(values)/len(values), 3)})
        for a, b in (("linear", "expected"), ("linear_empirical", "expected"),
                     ("shortest", "expected"), ("linear", "shortest")):
            diffs = [mean_cost[(slip, s, t, a)]-mean_cost[(slip, s, t, b)] for s, t in tasks]
            n = len(diffs)
            boot = sorted(sum(diffs[rng.randrange(n)] for _ in range(n))/n for _ in range(draws))
            pairs.append({"slip": slip, "comparison": f"{a} minus {b}",
                          "mean_cost_difference": round(sum(diffs)/n, 3),
                          "ci95": [round(boot[int(0.025*draws)], 3), round(boot[int(0.975*draws)], 3)],
                          "tasks_a_cheaper": sum(d < 0 for d in diffs),
                          "tasks_b_cheaper": sum(d > 0 for d in diffs),
                          "tasks_tied": sum(d == 0 for d in diffs)})
    out = {"horizon_as_cost_of_failure": horizon, "table": table, "paired": pairs}
    Path(output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


def summarise(paths, output):
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as handle:
            rows += list(csv.DictReader(handle))
    groups = defaultdict(list)
    for r in rows:
        groups[(float(r["slip"]), r["method"])].append(r)
    table = []
    for (slip, method), items in sorted(groups.items()):
        solved = [r for r in items if r["success"] == "True"]
        table.append({"slip": slip, "method": method, "tasks": len(items), "solved": len(solved),
                      "success_rate": round(len(solved)/len(items), 4),
                      "mean_steps_solved": round(sum(int(r["steps"]) for r in solved)/len(solved), 3)
                      if solved else None})
    paired = defaultdict(lambda: defaultdict(int))
    by = defaultdict(dict)
    for r in rows:
        by[(float(r["slip"]), r["seed"], r["task_id"])][r["method"]] = r
    for (slip, seed, task_id), m in by.items():
        if len(m) < len(noisy.METHODS):
            continue
        for a, b in (("linear", "expected"), ("linear_empirical", "expected"),
                     ("linear", "shortest"), ("shortest", "expected")):
            ra, rb = m[a], m[b]
            sa, sb = ra["success"] == "True", rb["success"] == "True"
            key = f"{a} vs {b}"
            paired[(slip, key)]["only_" + a] += sa and not sb
            paired[(slip, key)]["only_" + b] += sb and not sa
            if sa and sb:
                paired[(slip, key)][a + "_fewer_steps"] += int(ra["steps"]) < int(rb["steps"])
                paired[(slip, key)][b + "_fewer_steps"] += int(rb["steps"]) < int(ra["steps"])
                paired[(slip, key)]["same_steps"] += int(ra["steps"]) == int(rb["steps"])
    out = {"table": table,
           "paired": [{"slip": s, "comparison": k, **v} for (s, k), v in sorted(paired.items())]}
    Path(output).write_text(json.dumps(out, indent=2), encoding="utf-8")
    return out


if __name__ == "__main__":
    main()
