"""P5: the task automaton inferred from labelled traces. Protocol in PROTOCOLS.md.

    python -m experiments.task_agent.run_synthesis --output reports/task-agent-p5-synthesis \
        [--seeds ...] [--shard name]
    python -m experiments.task_agent.run_synthesis --summarise reports/task-agent-p5-synthesis
"""
from __future__ import annotations

import argparse
import csv
import json
import random
import statistics
import time
from collections import defaultdict
from math import comb
from pathlib import Path

from experiments.task_agent import checkpoint, exact_slip
from experiments.task_agent.synthesis import (GoalSet, TrueTask, counterexample_loop, disagreement,
                                              execute, labelled_prefixes, material, rpni, sample)

SIZES = (2, 4, 8, 16)
HELD_OUT = 16
ROUNDS = 16
CONDITIONS = ("goal_set", "rpni_random", "rpni_near_miss", "rpni_counterexample")
FIELDS = ["seed", "task_id", "task_type", "n", "condition", "true_memory", "memory_states",
          "equivalent", "registered_success", "held_out", "held_out_success",
          "held_out_optimal", "mean_step_ratio", "rounds", "sample_traces", "seconds"]


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def hypotheses(task, rows, n, start, key):
    yield "goal_set", GoalSet(sample(rows, n, "none")), None, n
    for negatives in ("random", "near_miss"):
        traces = sample(rows, n, negatives)
        yield f"rpni_{negatives}", rpni(labelled_prefixes(traces)), None, len(traces)
    hypothesis, rounds, traces = counterexample_loop(
        task, sample(rows, n, "random"), start, rounds=ROUNDS, rng=random.Random(f"cx:{key}:{n}"))
    yield "rpni_counterexample", hypothesis, (ROUNDS+1 if rounds is None else rounds), len(traces)


def judge(task, hypothesis, start, held_out):
    success = optimal = 0
    ratios = []
    for s in held_out:
        accomplished, steps, _ = execute(task, hypothesis, s)
        if accomplished:
            success += 1
            best = task.optimal_steps(s)
            optimal += steps == best
            ratios.append(steps/best if best else 1.0)
    return {"equivalent": not disagreement(task, hypothesis, [start]+list(held_out)),
            "registered_success": execute(task, hypothesis, start)[0],
            "held_out": len(held_out), "held_out_success": success,
            "held_out_optimal": optimal,
            "mean_step_ratio": round(statistics.mean(ratios), 4) if ratios else ""}


def run(output, seeds, shard, limit=None):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output/f"tasks-{shard}.csv"
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        for seed in seeds:
            started_world = time.perf_counter()
            _, engine = checkpoint.load_world(None, seed)
            snapshots = checkpoint.train_snapshots(engine)
            tasks = checkpoint.generate_basic_tasks(snapshots[8192], 120000+seed)
            tasks += checkpoint.generate_branch_tasks(snapshots[8192], 220000+seed)
            states, edges, ids = exact_slip.true_graph(engine, [s for _, s, _ in tasks])
            for task_id, (task_type, start, spec) in enumerate(tasks):
                automaton = checkpoint.TaskAutomaton(spec)
                task = TrueTask(states, edges, automaton, engine.num_actions)
                s0 = ids[tuple(start)]
                pool = [s for s in task.solvable() if s != s0]
                random.Random(f"pool:{seed}:{task_id}").shuffle(pool)
                held_out, demo_starts = pool[:HELD_OUT], pool[HELD_OUT:HELD_OUT+max(SIZES)]
                key = f"{seed}:{task_id}"
                rows = material(task, demo_starts, key)
                for n in SIZES:
                    if n > len(rows):
                        continue
                    # the generator infers each hypothesis when asked for it, so the time from
                    # one row to the next covers inference and judging both
                    began = time.perf_counter()
                    for condition, hypothesis, rounds, traces in hypotheses(task, rows, n, s0, key):
                        writer.writerow({"seed": seed, "task_id": task_id, "task_type": task_type,
                                         "n": n, "condition": condition,
                                         "true_memory": automaton.num_memory,
                                         "memory_states": hypothesis.num_memory,
                                         **judge(task, hypothesis, s0, held_out),
                                         "rounds": "" if rounds is None else rounds,
                                         "sample_traces": traces,
                                         "seconds": round(time.perf_counter()-began, 3)})
                        began = time.perf_counter()
                if limit and task_id+1 >= limit:
                    break
                handle.flush()
            say(f"world {seed}: {len(tasks)} tasks, {len(states)} states, "
                f"{time.perf_counter()-started_world:.1f}s")
    say(f"wrote {path}")


def sign_p(wins, losses):
    n = wins+losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2*sum(comb(n, i) for i in range(k+1))/2**n)


def summarise(output):
    output = Path(output)
    rows = []
    for p in sorted(output.glob("tasks-*.csv")):
        with open(p, encoding="utf-8") as handle:
            rows += list(csv.DictReader(handle))
    cell = defaultdict(list)
    for r in rows:
        cell[(r["condition"], int(r["n"]), r["task_type"])].append(r)
        cell[(r["condition"], int(r["n"]), "all")].append(r)
    table = []
    for (condition, n, task_type), group in sorted(cell.items()):
        held = sum(int(r["held_out"]) for r in group)
        table.append({
            "condition": condition, "n": n, "task_type": task_type, "tasks": len(group),
            "held_out_success_rate": round(sum(int(r["held_out_success"]) for r in group)/held, 4),
            "held_out_optimal_rate": round(sum(int(r["held_out_optimal"]) for r in group)/held, 4),
            "equivalent": sum(r["equivalent"] == "True" for r in group),
            "registered_success": sum(r["registered_success"] == "True" for r in group),
            "median_memory_states": statistics.median(int(r["memory_states"]) for r in group),
            "median_rounds": (statistics.median(int(r["rounds"]) for r in group)
                              if group[0]["rounds"] != "" else "")})
    by_task = {(r["seed"], r["task_id"], int(r["n"]), r["condition"]): r for r in rows}
    paired = []
    for n in SIZES:
        for a, b in (("rpni_random", "goal_set"), ("rpni_near_miss", "goal_set"),
                     ("rpni_counterexample", "goal_set"), ("rpni_near_miss", "rpni_random"),
                     ("rpni_counterexample", "rpni_random")):
            wins = losses = 0
            for (seed, task_id, m, c), r in by_task.items():
                if m != n or c != a or (seed, task_id, n, b) not in by_task:
                    continue
                x, y = int(r["held_out_success"]), int(by_task[(seed, task_id, n, b)]["held_out_success"])
                wins += x > y
                losses += x < y
            paired.append({"n": n, "a": a, "b": b, "a_more_held_out_successes": wins,
                           "b_more": losses, "sign_test_p": sign_p(wins, losses)})
    result = {"rows": len(rows), "table": table, "paired": paired}
    (output/"summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/task-agent-p5-synthesis")
    parser.add_argument("--seeds", nargs="*", type=int, default=list(checkpoint.SEEDS))
    parser.add_argument("--shard", default="all")
    parser.add_argument("--summarise", default=None)
    parser.add_argument("--limit-tasks", type=int, default=None,
                        help="timing smoke runs only; the protocol runs every task")
    arguments = parser.parse_args()
    if arguments.summarise:
        print(json.dumps(summarise(arguments.summarise), indent=2))
        return
    run(arguments.output, arguments.seeds, arguments.shard, arguments.limit_tasks)


if __name__ == "__main__":
    main()
