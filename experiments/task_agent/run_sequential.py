"""P4: one model carried across a sequence of tasks. Protocol in PROTOCOLS.md.

Every experiment so far reset the model for each task, which is the setting in
which exploring *only what this task needs* is free to win. Carrying one model
across a sequence is the setting in which exploring broadly might pay for itself:
what one task maps, the next can use.

    python -m experiments.task_agent.run_sequential --output reports/task-agent-p4-sequential \
        [--seeds ...] [--policies ...] [--orders 3] [--shard name]
    python -m experiments.task_agent.run_sequential --summarise reports/task-agent-p4-sequential
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

from experiments.task_agent import checkpoint, online_eval, run_online
from experiments.task_agent.online import OnlineTaskAgent
from experiments.task_agent.online_slip import FieldPlanner, VersionedLearner

POLICIES = ("structural", "frontier_t0", "optimistic_optimal_goal", "optimistic_linear_rmax")
BUDGET = 4096
HALF = 23                                   # 46 tasks per world: positions 0-22 and 23-45
# the preregistered contrast: task-directed exploration against broad exploration
DIRECTED, BROAD = "optimistic_optimal_goal", "optimistic_linear_rmax"


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def order_of(seed, k, n):
    order = list(range(n))
    random.Random(f"order:{seed}:{k}").shuffle(order)
    return order


def sequence(snapshot_core, engine, tasks, order, policy_name):
    """Solve the tasks in this order with ONE learner; return a row per task."""
    learner = VersionedLearner.from_learner(snapshot_core)
    # the delivered task-conditioned policy reads its planner's model, so it gets the
    # planner it was verified with; every other policy gets the reusing one
    planner = online_eval.CachingSparsePlanner() if policy_name.startswith("task_conditioned") \
        else FieldPlanner("linear")
    policy = run_online.policy_for(policy_name, planner)
    rows = []
    for position, task_id in enumerate(order):
        task_type, start, spec = tasks[task_id]
        automaton = checkpoint.TaskAutomaton(spec)
        had_path = checkpoint.product_shortest_path(
            _as_checkpoint_learner(learner), automaton, start) is not None \
            if tuple(start) in learner.state_to_id else False
        agent = OnlineTaskAgent(learner, policy, planner=planner, max_task_steps=BUDGET,
                                max_exploration_steps=BUDGET)
        known = len(learner.id_to_state)
        result = agent.run_task(online_eval.WorldEnv(engine), online_eval.task_from_spec(spec),
                                tuple(start))
        rows.append({"position": position, "task_id": task_id, "task_type": task_type,
                     "had_path_at_start": had_path, "success": bool(result.success),
                     "steps": int(result.task_steps),
                     "exploration_steps": int(result.exploration_steps),
                     "states_added": len(learner.id_to_state)-known,
                     "states_known": len(learner.id_to_state)})
    return rows


class _as_checkpoint_learner:
    """The checkpoint module's names over a canonical learner, read-only."""

    def __init__(self, core):
        self.core = core

    A = property(lambda self: self.core.num_actions)
    i2s = property(lambda self: self.core.id_to_state)
    s2i = property(lambda self: self.core.state_to_id)
    counts = property(lambda self: self.core.counts)


def run(output, seeds, policies, orders, shard):
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    path = output/f"sequences-{shard}.csv"
    fields = ["seed", "order", "policy", "position", "task_id", "task_type", "had_path_at_start",
              "success", "steps", "exploration_steps", "states_added", "states_known"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for seed in seeds:
            parent, engine = checkpoint.load_world(None, seed)
            snapshots = checkpoint.train_snapshots(engine)
            tasks = checkpoint.generate_basic_tasks(snapshots[8192], 120000+seed)
            tasks += checkpoint.generate_branch_tasks(snapshots[8192], 220000+seed)
            for k in range(orders):
                order = order_of(seed, k, len(tasks))
                for name in policies:
                    started = time.perf_counter()
                    rows = sequence(snapshots[512].core, engine, tasks, order, name)
                    for row in rows:
                        writer.writerow({"seed": seed, "order": k, "policy": name, **row})
                    handle.flush()
                    say(f"world {seed} order {k} {name}: total steps "
                        f"{sum(r['steps'] for r in rows)}, failures "
                        f"{sum(not r['success'] for r in rows)}, "
                        f"{time.perf_counter()-started:.1f}s")
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
    for p in sorted(output.glob("sequences-*.csv")):
        with open(p, encoding="utf-8") as handle:
            rows += list(csv.DictReader(handle))
    total = defaultdict(int)
    explored = defaultdict(int)
    needed = defaultdict(int)
    first_half = defaultdict(int)
    second_half = defaultdict(int)
    failures = defaultdict(int)
    for r in rows:
        unit = (r["seed"], r["order"], r["policy"])
        total[unit] += int(r["steps"])
        explored[unit] += int(r["exploration_steps"])
        needed[unit] += r["had_path_at_start"] != "True"
        failures[unit] += r["success"] != "True"
        if int(r["position"]) < HALF:
            first_half[unit] += int(r["steps"])
        else:
            second_half[unit] += int(r["steps"])
    policies = sorted({u[2] for u in total})
    units = sorted({u[:2] for u in total})
    table = []
    for name in policies:
        values = [total[u+(name,)] for u in units if u+(name,) in total]
        table.append({"policy": name, "sequences": len(values),
                      "mean_total_steps": round(statistics.mean(values), 1),
                      "median_total_steps": statistics.median(values),
                      "mean_first_half_steps": round(statistics.mean(
                          first_half[u+(name,)] for u in units if u+(name,) in total), 1),
                      "mean_second_half_steps": round(statistics.mean(
                          second_half[u+(name,)] for u in units if u+(name,) in total), 1),
                      "mean_tasks_needing_exploration": round(statistics.mean(
                          needed[u+(name,)] for u in units if u+(name,) in total), 2),
                      "failures": sum(failures[u+(name,)] for u in units if u+(name,) in total)})
    pairs = []
    for i, a in enumerate(policies):
        for b in policies[i+1:]:
            wins = sum(total[u+(a,)] < total[u+(b,)] for u in units
                       if u+(a,) in total and u+(b,) in total)
            losses = sum(total[u+(a,)] > total[u+(b,)] for u in units
                         if u+(a,) in total and u+(b,) in total)
            pairs.append({"a": a, "b": b, "a_fewer_total_steps": wins,
                          "b_fewer_total_steps": losses, "sign_test_p": sign_p(wins, losses)})
    # H4: does the directed policy's advantage over the broad one shrink from the first half
    # of a sequence to the second? d = steps(directed) - steps(broad), per half, per unit
    shrink = grow = 0
    halves = []
    for u in units:
        if u+(DIRECTED,) not in total or u+(BROAD,) not in total:
            continue
        d1 = first_half[u+(DIRECTED,)]-first_half[u+(BROAD,)]
        d2 = second_half[u+(DIRECTED,)]-second_half[u+(BROAD,)]
        halves.append({"seed": u[0], "order": u[1], "first_half_gap": d1, "second_half_gap": d2})
        shrink += d2 > d1
        grow += d2 < d1
    h4 = {"directed": DIRECTED, "broad": BROAD, "units": len(halves),
          "gap_moves_towards_broad": shrink, "gap_moves_towards_directed": grow,
          "sign_test_p": sign_p(shrink, grow), "per_unit": halves}
    result = {"units": len(units), "table": table, "paired": pairs, "h4": h4}
    (output/"summary.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="reports/task-agent-p4-sequential")
    parser.add_argument("--seeds", nargs="*", type=int, default=list(checkpoint.SEEDS))
    parser.add_argument("--policies", nargs="*", default=list(POLICIES))
    parser.add_argument("--orders", type=int, default=3)
    parser.add_argument("--shard", default="all")
    parser.add_argument("--summarise", default=None)
    arguments = parser.parse_args()
    if arguments.summarise:
        print(json.dumps(summarise(arguments.summarise), indent=2))
        return
    run(arguments.output, arguments.seeds, arguments.policies, arguments.orders, arguments.shard)


if __name__ == "__main__":
    main()
