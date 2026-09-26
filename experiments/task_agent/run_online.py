"""The online agent on the registered tasks, from the budget-512 model. Protocol fixed here.

PROTOCOL (written after a three-task pilot on world 2505 and before any other run)

  worlds      the eight archived worlds of theory-registration, reproduced exactly
  start       the canonical learner's budget-512 snapshot, a private copy per episode
  tasks       the 368 registered task specifications, all of them, no subsampling
  planner     SparseProductPlanner -- ProductPlanner with a sparse LU, checked equal
  policies    structural, frontier, uncertainty, task_conditioned: the package's
              classes with their default parameters, as delivered
  budget      4096 environment steps per episode, exploration and execution together
  outcomes    success within 512 / 1024 / 2048 / 4096 steps, from one run each;
              steps to success; reported separately for tasks with and without an
              accepting path in the starting model
  no retries, no tuning, no change of any of the above after the run

POST-HOC, and labelled as such: the pilot showed task_conditioned taking the same
number of steps as frontier, and both taking three to five times as many as
structural. One hypothesis explains both: every policy that navigates to a
"frontier" uses `low_count_threshold=1`, so a state whose actions have each been
tried once still counts as unexplored -- and in a deterministic world one try is
all there is to learn. The two extra rows, `frontier_t0` and
`task_conditioned_t0`, are the same classes with `low_count_threshold=0`. They
test that hypothesis; they are not part of the preregistered comparison.

CONFIRMATION (written after the full run above, before any confirmation episode)

  The post-hoc finding to be confirmed: with low_count_threshold=0, the
  task-conditioned policy reaches success sooner than the canonical structural
  explorer, and sooner than the same frontier navigation without task
  relevance. It is tested on NEW tasks -- the same generators with seeds
  320000+seed and 420000+seed instead of 120000+seed and 220000+seed -- on the
  same eight worlds, from the same budget-512 start, with the same budget.
  Policies: structural, task_conditioned (as delivered), frontier_t0,
  task_conditioned_t0. Primary outcomes, fixed now: on the tasks that start out
  of model, (1) success within 512 steps, and (2) the paired count of tasks on
  which task_conditioned_t0 finishes in fewer steps than structural against the
  count on which structural does. The finding is confirmed only if both favour
  task_conditioned_t0; otherwise it is reported as not confirmed.

    python -m experiments.task_agent.run_online --registration <dir> --output <dir> \
        [--seeds 2101 2202 ...] [--shard name] [--task-seed-offset 200000]
"""
from __future__ import annotations

import argparse
import csv
import json
import time
from pathlib import Path

from experiments.task_agent import checkpoint, online_eval
from experiments.task_agent import FrontierFieldPolicy

PREREGISTERED = ("structural", "frontier", "uncertainty", "task_conditioned")
POST_HOC = ("frontier_t0", "task_conditioned_t0")
CAPS = (512, 1024, 2048, 4096)


def say(message):
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def policy_for(name, planner):
    if name == "frontier_t0":
        return FrontierFieldPolicy(low_count_threshold=0)
    if name == "task_conditioned_t0":
        return online_eval.FastTaskConditionedPolicy(planner, low_count_threshold=0)
    if name == "task_conditioned":
        return online_eval.FastTaskConditionedPolicy(planner)
    return online_eval.make_policy(name, planner)


def episode(snapshot_core, engine, spec, start, name, max_steps):
    import copy

    learner = copy.deepcopy(snapshot_core)
    planner = online_eval.CachingSparsePlanner(q=0.90)
    agent = online_eval.OnlineTaskAgent(learner, policy_for(name, planner), planner=planner,
                                        max_task_steps=max_steps, max_exploration_steps=max_steps)
    started = time.perf_counter()
    result = agent.run_task(online_eval.WorldEnv(engine), online_eval.task_from_spec(spec),
                            tuple(start))
    return {"success": bool(result.success), "task_steps": int(result.task_steps),
            "exploration_steps": int(result.exploration_steps), "replans": int(result.replans),
            "failure_reason": result.failure_reason,
            "states_known_at_end": len(learner.id_to_state),
            "seconds": round(time.perf_counter()-started, 3)}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--registration", default=None)
    parser.add_argument("--output", required=True)
    parser.add_argument("--seeds", nargs="*", type=int, default=list(checkpoint.SEEDS))
    parser.add_argument("--policies", nargs="*", default=list(PREREGISTERED+POST_HOC))
    parser.add_argument("--max-steps", type=int, default=4096)
    parser.add_argument("--shard", default="all")
    parser.add_argument("--task-seed-offset", type=int, default=0)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    path = output/f"episodes-{arguments.shard}.csv"
    fields = ["seed", "task_id", "task_type", "policy", "starts_in_model", "shortest_at_512",
              "success", "task_steps", "exploration_steps", "replans", "failure_reason",
              "states_known_at_end", "seconds", "post_hoc"]
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for seed in arguments.seeds:
            parent, engine = checkpoint.load_world(arguments.registration, seed)
            snapshots = checkpoint.train_snapshots(engine)
            final = snapshots[8192]
            offset = arguments.task_seed_offset
            tasks = checkpoint.generate_basic_tasks(final, 120000+offset+seed)
            tasks += checkpoint.generate_branch_tasks(final, 220000+offset+seed)
            start_model = snapshots[512]
            for task_id, (task_type, start, spec) in enumerate(tasks):
                automaton = checkpoint.TaskAutomaton(spec)
                shortest = checkpoint.product_shortest_path(start_model, automaton, start)
                for name in arguments.policies:
                    row = episode(start_model.core, engine, spec, start, name, arguments.max_steps)
                    writer.writerow({"seed": seed, "task_id": task_id, "task_type": task_type,
                                     "policy": name, "starts_in_model": shortest is not None,
                                     "shortest_at_512": shortest, "post_hoc": name in POST_HOC,
                                     **row})
                handle.flush()
            say(f"world {seed} done ({len(tasks)} tasks x {len(arguments.policies)} policies)")
    say(f"wrote {path}")


if __name__ == "__main__":
    main()
