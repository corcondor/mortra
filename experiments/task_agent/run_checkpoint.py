"""Reproduce the checkpoint Task-Agent run, then compare the linear and optimal product fields.

    python -m experiments.task_agent.run_checkpoint \
        --registration <theory-registration dir> \
        --registered   <dir holding the original run's task_agent_*.csv> \
        --output       reports/task-agent-checkpoint
"""
from __future__ import annotations

import argparse
import csv
import json
import platform
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

from experiments.task_agent import checkpoint


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def write_csv(path, rows):
    rows = list(rows)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarise(records):
    """Success, steps, and optimality against the product graph's own shortest path."""
    groups = defaultdict(list)
    for r in records:
        groups[(r["budget"], r["task_type"], r["method"])].append(r)
    rows = []
    for (budget, task_type, method), items in sorted(groups.items()):
        solved = [r for r in items if r["success"]]
        optimal = [r for r in solved if r["shortest_product_steps"] is not None
                   and r["steps"] == r["shortest_product_steps"]]
        excess = [r["steps"]-r["shortest_product_steps"] for r in solved
                  if r["shortest_product_steps"] is not None]
        rows.append({"budget": budget, "task_type": task_type, "method": method,
                     "tasks": len(items), "solved": len(solved),
                     "success_rate": round(len(solved)/len(items), 4),
                     "optimal_among_solved": len(optimal),
                     "mean_excess_steps": round(sum(excess)/len(excess), 4) if excess else 0.0,
                     "max_excess_steps": max(excess) if excess else 0})
    return rows


def head_to_head(records, budget=8192):
    """Linear against optimal field, task by task, on the same product graph."""
    by = defaultdict(dict)
    for r in records:
        if r["budget"] == budget:
            by[(r["seed"], r["task_id"], r["task_type"])][r["method"]] = r
    table = defaultdict(lambda: {"tasks": 0, "linear_optimal": 0, "optimal_optimal": 0,
                                 "optimal_faster": 0, "linear_faster": 0, "same_steps": 0,
                                 "linear_steps": 0, "optimal_steps": 0, "shortest_steps": 0})
    worst = []
    for (seed, task_id, task_type), m in by.items():
        lin, opt = m["product_compiler"], m["optimal_product"]
        if not (lin["success"] and opt["success"]):
            continue
        t = table[task_type]
        t["tasks"] += 1
        best = lin["shortest_product_steps"]
        t["linear_optimal"] += lin["steps"] == best
        t["optimal_optimal"] += opt["steps"] == best
        t["optimal_faster"] += opt["steps"] < lin["steps"]
        t["linear_faster"] += lin["steps"] < opt["steps"]
        t["same_steps"] += lin["steps"] == opt["steps"]
        t["linear_steps"] += lin["steps"]
        t["optimal_steps"] += opt["steps"]
        t["shortest_steps"] += best
        if lin["steps"] > best:
            worst.append({"seed": seed, "task_id": task_id, "task_type": task_type,
                          "linear_steps": lin["steps"], "optimal_steps": opt["steps"],
                          "shortest": best})
    worst.sort(key=lambda w: (w["linear_steps"]-w["shortest"]) / max(1, w["shortest"]), reverse=True)
    return dict(table), worst


def field_costs(worlds, repeats=3):
    """Time the two fields on the same final-budget product graphs: one LU solve, one BFS."""
    import numpy as np
    from scipy.sparse import csr_matrix, identity
    from scipy.sparse.linalg import splu

    linear = optimal = 0.0
    sizes = []
    for seed, (engine, snapshots, tasks) in worlds.items():
        learner = snapshots[8192]
        for _, start, spec in tasks:
            model = checkpoint.build_product_model(learner, checkpoint.TaskAutomaton(spec), start)
            if model is None or not model["reachable"]:
                continue
            n = model["n_product_states"]
            sizes.append(n)
            r, c, w = [], [], []
            for i, row in enumerate(model["transitions"]):
                for j in row.values():
                    r.append(i)
                    c.append(j)
                    w.append(1.0/len(row))
            K = csr_matrix((w, (r, c)), shape=(n, n))
            g = np.zeros(n)
            g[model["goals"]] = 1.0
            for _ in range(repeats):
                t = time.perf_counter()
                splu(identity(n, format="csc")-checkpoint.Q*K.tocsc()).solve(g)
                linear += time.perf_counter()-t
                t = time.perf_counter()
                checkpoint.optimal_field(model)
                optimal += time.perf_counter()-t
    count = len(sizes)*repeats
    return {"product_graphs": len(sizes), "mean_product_states": round(sum(sizes)/len(sizes), 1),
            "linear_field_seconds_each": round(linear/count, 6),
            "optimal_field_seconds_each": round(optimal/count, 6),
            "note": "the linear field is a sparse LU solve of I - qK; the optimal field is one "
                    "reverse breadth-first search. Both on the identical product graph"}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registration", default=None)
    parser.add_argument("--registered", default=str(checkpoint.REGISTERED))
    parser.add_argument("--output", required=True)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()

    say("training the eight worlds and running every task with every method")
    records, task_specs, world_rows, timings, worlds = checkpoint.run(arguments.registration,
                                                                      log=say)

    say("comparing with the registered run")
    comparison = checkpoint.compare(arguments.registered, records, task_specs, world_rows)

    summary = summarise(records)
    table, worst = head_to_head(records)
    write_csv(output/"results.csv", records)
    write_csv(output/"task_specs.csv", task_specs)
    write_csv(output/"worlds.csv", world_rows)
    write_csv(output/"summary.csv", summary)
    if worst:
        write_csv(output/"linear_field_not_optimal_8192.csv", worst)

    report = {
        "environment": {
            "sha": subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True,
                                  text=True).stdout.strip(),
            "python": sys.version.split()[0], "platform": platform.platform()},
        "reproduction": comparison,
        "linear_against_optimal_at_8192": table,
        "linear_not_optimal_examples": worst[:10],
        "seconds_per_method": {k: round(v, 2) for k, v in timings.items()},
        "field_costs_at_8192": field_costs(worlds),
        "total_seconds": round(time.perf_counter()-started, 1),
    }
    (output/"result.json").write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")

    say(f"reproduction: worlds {len(comparison['worlds']['differences'])} differences, "
        f"task specs {comparison['task_specs']['difference_count']} differences, "
        f"results {comparison['results']['difference_count']} differences "
        f"of {comparison['results']['compared']} compared rows")
    for task_type, t in sorted(table.items()):
        say(f"8192 {task_type:15s} tasks {t['tasks']:3d}  linear optimal {t['linear_optimal']:3d}  "
            f"optimal optimal {t['optimal_optimal']:3d}  steps linear/optimal/shortest "
            f"{t['linear_steps']}/{t['optimal_steps']}/{t['shortest_steps']}")
    say(f"seconds per method {report['seconds_per_method']}")
    say(f"wrote {output/'result.json'}")


if __name__ == "__main__":
    main()
