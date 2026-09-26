"""Run the exact noise evaluation (protocols in exact_slip.py and PROTOCOLS.md) and summarise it.

    python -m experiments.task_agent.run_exact_slip --output reports/task-agent-exact-slip \
        [--noise uniform|drift_state|drift_global] [--slips ...]
    python -m experiments.task_agent.run_exact_slip --summarise reports/task-agent-exact-slip
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from collections import defaultdict
from math import comb
from pathlib import Path

from experiments.task_agent import checkpoint, exact_slip, noisy


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def run(output, slips, seeds, noise="uniform"):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    tag = "-".join(str(s) for s in slips)
    path = output/(f"tasks-{tag}.csv" if noise == "uniform" else f"tasks-{noise}-{tag}.csv")
    fields = ["noise", "slip", "seed", "task_id", "task_type", "planner", "p_success",
              "expected_cost", "expected_steps_given_success", "true_product_states",
              "learned_states"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for seed in seeds:
            parent, engine = checkpoint.load_world(None, seed)
            final = checkpoint.train_snapshots(engine, (8192,))[8192]
            tasks = checkpoint.generate_basic_tasks(final, 120000+seed)
            tasks += checkpoint.generate_branch_tasks(final, 220000+seed)
            states, edges, ids = exact_slip.true_graph(engine, [t[1] for t in tasks])
            for slip in slips:
                train_tag = f"train:{seed}:{slip}" if noise == "uniform" else \
                    f"train:{seed}:{slip}:{noise}"
                learner = noisy.train(noisy.SlipEngine(parent["genome"], slip, train_tag,
                                                       noise=noise), 8192)
                started = time.perf_counter()
                for task_id, (task_type, start, spec) in enumerate(tasks):
                    for row in exact_slip.task_rows(seed, slip, task_id, task_type, start, spec,
                                                    learner, states, edges, ids,
                                                    engine.num_actions, noise=noise):
                        writer.writerow(row)
                handle.flush()
                say(f"{noise} world {seed} slip {slip}: {len(tasks)} tasks, {len(states)} true "
                    f"states, {len(learner.i2s)} learned, {time.perf_counter()-started:.1f}s")
    say(f"wrote {path}")
    return path


def sign_p(wins, losses):
    n = wins+losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2*sum(comb(n, i) for i in range(k+1))/2**n)


COMPARISONS = (("linear", "shortest"), ("linear", "certainty_equivalent"),
               ("linear_empirical", "certainty_equivalent"), ("shortest", "certainty_equivalent"),
               ("linear_oracle", "shortest_oracle"), ("linear", "ssp_optimal"),
               ("certainty_equivalent", "ssp_optimal"), ("shortest_oracle", "ssp_optimal"),
               ("linear_oracle", "ssp_optimal"))


def summarise(output):
    output = Path(output)
    rows = []
    for p in sorted(output.glob("tasks-*.csv")):
        with open(p, encoding="utf-8") as handle:
            rows += list(csv.DictReader(handle))
    for r in rows:
        r["noise"] = r.get("noise") or "uniform"
        r["p_success"] = float(r["p_success"])
        r["expected_cost"] = float(r["expected_cost"])
    table = []
    groups = defaultdict(list)
    for r in rows:
        groups[(r["noise"], float(r["slip"]), r["planner"])].append(r)
    for (noise, slip, planner), items in sorted(groups.items()):
        table.append({"noise": noise, "slip": slip, "planner": planner, "tasks": len(items),
                      "mean_p_success": round(sum(r["p_success"] for r in items)/len(items), 5),
                      "tasks_certain_success": sum(r["p_success"] > 1-1e-12 for r in items),
                      "mean_expected_cost": round(sum(r["expected_cost"] for r in items)/len(items),
                                                  4)})
    by = defaultdict(dict)
    for r in rows:
        by[(r["noise"], float(r["slip"]), r["seed"], r["task_id"])][r["planner"]] = r
    pairs = []
    for noise, slip in sorted({k[:2] for k in by}):
        for a, b in COMPARISONS:
            wins = losses = ties = 0
            diff = 0.0
            per_world = defaultdict(lambda: [0, 0])
            n = 0
            for (nz, s, seed, task_id), per in by.items():
                if nz != noise or s != slip or a not in per or b not in per:
                    continue
                n += 1
                ca, cb = per[a]["expected_cost"], per[b]["expected_cost"]
                diff += ca-cb
                if abs(ca-cb) < 1e-9:
                    ties += 1
                elif ca < cb:
                    wins += 1
                    per_world[seed][0] += 1
                else:
                    losses += 1
                    per_world[seed][1] += 1
            pairs.append({"noise": noise, "slip": slip, "a": a, "b": b, "tasks": n,
                          "a_cheaper": wins, "b_cheaper": losses, "tied": ties,
                          "sign_test_p": round(sign_p(wins, losses), 6),
                          "mean_cost_a_minus_b": round(diff/n, 4) if n else None,
                          "per_world_a_cheaper_b_cheaper": {k: v for k, v in
                                                            sorted(per_world.items())}})
    result = {"table": table, "paired": pairs}
    (output/"summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/task-agent-exact-slip")
    parser.add_argument("--slips", nargs="*", type=float, default=list(exact_slip.SLIPS))
    parser.add_argument("--seeds", nargs="*", type=int, default=list(checkpoint.SEEDS))
    parser.add_argument("--noise", default="uniform", choices=noisy.NOISES)
    parser.add_argument("--summarise", default=None)
    arguments = parser.parse_args()
    if arguments.summarise:
        print(json.dumps(summarise(arguments.summarise), indent=2))
        return
    run(arguments.output, arguments.slips, arguments.seeds, arguments.noise)


if __name__ == "__main__":
    main()
