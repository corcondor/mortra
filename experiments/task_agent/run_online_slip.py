"""P2: the online agent in slipping worlds, against the frozen model evaluated exactly.

    python -m experiments.task_agent.run_online_slip --output reports/task-agent-p2-online-slip \
        [--seeds ...] [--slips ...] [--shard name]
    python -m experiments.task_agent.run_online_slip --summarise reports/task-agent-p2-online-slip
"""
from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
from collections import defaultdict
from math import comb
from pathlib import Path

from experiments.task_agent import checkpoint, noisy, online_eval
from experiments.task_agent.exploration import FrontierFieldPolicy
from experiments.task_agent.online import OnlineTaskAgent
from experiments.task_agent.online_slip import FieldPlanner, SlipEnv, VersionedLearner

PLANNERS = ("linear", "shortest")
SLIPS = (0.05, 0.10, 0.20)
REPLICATES = 3
BUDGET = 2048
FROZEN = Path("reports/task-agent-exact-slip/tasks-0.0-0.05-0.1-0.2.csv")


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def episode(base_core, genome, spec, start, slip, planner_kind, tag, budget=BUDGET):
    learner = VersionedLearner.from_learner(base_core)
    planner = FieldPlanner(planner_kind)
    agent = OnlineTaskAgent(learner, FrontierFieldPolicy(low_count_threshold=0), planner=planner,
                            max_task_steps=budget, max_exploration_steps=budget)
    known_before = len(learner.id_to_state)
    started = time.perf_counter()
    result = agent.run_task(SlipEnv(genome, slip, tag), online_eval.task_from_spec(spec),
                            tuple(start))
    return {"success": bool(result.success), "steps": int(result.task_steps),
            "exploration_steps": int(result.exploration_steps),
            "states_added": len(learner.id_to_state)-known_before,
            "model_changes": learner.version, "builds": planner.builds,
            "failure_reason": result.failure_reason,
            "seconds": round(time.perf_counter()-started, 3)}


def run(output, seeds, slips):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output/f"episodes-{'-'.join(str(s) for s in seeds)}.csv"
    fields = ["slip", "seed", "task_id", "task_type", "planner", "replicate", "success", "steps",
              "exploration_steps", "states_added", "model_changes", "builds", "failure_reason",
              "seconds"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for seed in seeds:
            parent, engine = checkpoint.load_world(None, seed)
            final = checkpoint.train_snapshots(engine, (8192,))[8192]
            tasks = checkpoint.generate_basic_tasks(final, 120000+seed)
            tasks += checkpoint.generate_branch_tasks(final, 220000+seed)
            for slip in slips:
                trained = noisy.train(noisy.SlipEngine(parent["genome"], slip,
                                                       f"train:{seed}:{slip}"), 8192)
                started = time.perf_counter()
                for task_id, (task_type, start, spec) in enumerate(tasks):
                    for replicate in range(1, REPLICATES+1):
                        tag = f"online:{seed}:{task_id}:{slip}:{replicate}"
                        for kind in PLANNERS:
                            row = episode(trained.core, parent["genome"], spec, start, slip, kind,
                                          tag)
                            writer.writerow({"slip": slip, "seed": seed, "task_id": task_id,
                                             "task_type": task_type, "planner": kind,
                                             "replicate": replicate, **row})
                handle.flush()
                say(f"world {seed} slip {slip}: {len(tasks)} tasks, "
                    f"{time.perf_counter()-started:.1f}s")
    say(f"wrote {path}")


def sign_p(wins, losses):
    n = wins+losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2*sum(comb(n, i) for i in range(k+1))/2**n)


def summarise(output, horizon=512):
    """Online against frozen, per task: the frozen number is exact, the online one a mean."""
    output = Path(output)
    rows = []
    for p in sorted(output.glob("episodes-*.csv")):
        with open(p, encoding="utf-8") as handle:
            rows += list(csv.DictReader(handle))
    frozen = {}
    with open(FROZEN, encoding="utf-8") as handle:
        for r in csv.DictReader(handle):
            frozen[(float(r["slip"]), r["seed"], r["task_id"], r["planner"])] = \
                (float(r["p_success"]), float(r["expected_cost"]))
    per_task = defaultdict(list)
    for r in rows:
        steps = int(r["steps"])
        ok = r["success"] == "True"
        per_task[(float(r["slip"]), r["seed"], r["task_id"], r["planner"])].append(
            (ok and steps <= horizon, steps if ok and steps <= horizon else horizon, ok, steps))
    table, pairs = [], []
    for slip in sorted({k[0] for k in per_task}):
        for planner in PLANNERS:
            keys = [k for k in per_task if k[0] == slip and k[3] == planner]
            online_cost = [statistics.mean(x[1] for x in per_task[k]) for k in keys]
            online_success = [statistics.mean(x[0] for x in per_task[k]) for k in keys]
            online_success_any = [statistics.mean(x[2] for x in per_task[k]) for k in keys]
            frozen_cost = [frozen[k][1] for k in keys]
            frozen_success = [frozen[k][0] for k in keys]
            wins = sum(o < f-1e-9 for o, f in zip(online_cost, frozen_cost))
            losses = sum(o > f+1e-9 for o, f in zip(online_cost, frozen_cost))
            table.append({"slip": slip, "planner": planner, "tasks": len(keys),
                          "frozen_p_success_512": round(statistics.mean(frozen_success), 4),
                          "online_success_512": round(statistics.mean(online_success), 4),
                          "online_success_2048": round(statistics.mean(online_success_any), 4),
                          "frozen_mean_cost": round(statistics.mean(frozen_cost), 3),
                          "online_mean_cost": round(statistics.mean(online_cost), 3),
                          "tasks_online_cheaper": wins, "tasks_frozen_cheaper": losses,
                          "sign_test_p": sign_p(wins, losses)})
        a_keys = {k[:3] for k in per_task if k[0] == slip}
        wins = losses = 0
        for key in a_keys:
            la = per_task.get(key+("linear",))
            sa = per_task.get(key+("shortest",))
            if not la or not sa:
                continue
            ca = statistics.mean(x[1] for x in la)
            cb = statistics.mean(x[1] for x in sa)
            wins += ca < cb-1e-9
            losses += ca > cb+1e-9
        pairs.append({"slip": slip, "comparison": "online linear vs online shortest",
                      "linear_cheaper": wins, "shortest_cheaper": losses,
                      "sign_test_p": sign_p(wins, losses)})
    result = {"horizon_for_cost": horizon, "table": table, "paired": pairs,
              "failure_reasons": dict(defaultdict(int, {k: sum(1 for r in rows
                                                               if r["failure_reason"] == k)
                                                        for k in {r["failure_reason"]
                                                                  for r in rows}}))}
    (output/"summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/task-agent-p2-online-slip")
    parser.add_argument("--seeds", nargs="*", type=int, default=list(checkpoint.SEEDS))
    parser.add_argument("--slips", nargs="*", type=float, default=list(SLIPS))
    parser.add_argument("--summarise", default=None)
    arguments = parser.parse_args()
    if arguments.summarise:
        print(json.dumps(summarise(arguments.summarise), indent=2))
        return
    run(arguments.output, arguments.seeds, arguments.slips)


if __name__ == "__main__":
    main()
