"""Summaries of the online run: success at each step cap, steps, and paired comparisons."""
from __future__ import annotations

import csv
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path

CAPS = (512, 1024, 2048, 4096)


def load(paths):
    rows = []
    for p in paths:
        with open(p, encoding="utf-8") as handle:
            rows += list(csv.DictReader(handle))
    for r in rows:
        r["success"] = r["success"] == "True"
        r["starts_in_model"] = r["starts_in_model"] == "True"
        r["task_steps"] = int(r["task_steps"])
        r["exploration_steps"] = int(r["exploration_steps"])
        r["seconds"] = float(r["seconds"])
    return rows


POST_HOC = {"frontier_t0", "task_conditioned_t0"}


def success_table(rows, budget=4096):
    """Success by cap, and the median with every failure counted at the budget.

    The subset is named for what it is: whether an accepting path already exists
    in the budget-512 product graph -- not whether the start state is known.
    """
    groups = defaultdict(list)
    for r in rows:
        subset = "accepting_path_at_512" if r["starts_in_model"] else "needs_exploration"
        groups[(subset, r["policy"])].append(r)
        groups[("all", r["policy"])].append(r)
    out = []
    for (subset, policy), items in sorted(groups.items()):
        solved = [r for r in items if r["success"]]
        censored = sorted(r["task_steps"] if r["success"] else budget for r in items)
        row = {"subset": subset, "policy": policy, "post_hoc": policy in POST_HOC,
               "episodes": len(items),
               "median_steps_failures_at_budget": statistics.median(censored),
               "mean_seconds": round(statistics.mean(r["seconds"] for r in items), 3)}
        for cap in CAPS:
            row[f"success_at_{cap}"] = sum(1 for r in solved if r["task_steps"] <= cap)
        out.append(row)
    return out


def sign_p(wins, losses):
    from math import comb

    n = wins+losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    return min(1.0, 2*sum(comb(n, i) for i in range(k+1))/2**n)


def paired(rows, a, b, budget=4096):
    """a against b on the tasks that needed exploration; a failure costs more than any success."""
    by = defaultdict(dict)
    for r in rows:
        by[(r["seed"], r["task_id"])][r["policy"]] = r
    wins = losses = ties = 0
    per_world = defaultdict(lambda: [0, 0, 0])
    for (seed, task_id), per in by.items():
        if a not in per or b not in per or per[a]["starts_in_model"]:
            continue
        ca = per[a]["task_steps"] if per[a]["success"] else budget+1
        cb = per[b]["task_steps"] if per[b]["success"] else budget+1
        if ca < cb:
            wins += 1
            per_world[seed][0] += 1
        elif cb < ca:
            losses += 1
            per_world[seed][1] += 1
        else:
            ties += 1
            per_world[seed][2] += 1
    return {"a": a, "b": b, "post_hoc": a in POST_HOC or b in POST_HOC,
            "a_fewer_steps": wins, "b_fewer_steps": losses, "tied": ties,
            "sign_test_p": sign_p(wins, losses),
            "per_world_a_b_tied": {k: v for k, v in sorted(per_world.items())}}


def identical(rows, one, two):
    """How often two policies produced exactly the same episode length on the same task."""
    by = defaultdict(dict)
    for r in rows:
        by[(r["seed"], r["task_id"])][r["policy"]] = r
    same = total = 0
    for per in by.values():
        if one in per and two in per and not per[one]["starts_in_model"]:
            total += 1
            same += (per[one]["success"], per[one]["task_steps"]) == \
                (per[two]["success"], per[two]["task_steps"])
    return {"pair": [one, two], "out_of_model_tasks": total, "identical_episodes": same}


COMPARISONS = (("task_conditioned", "structural"), ("frontier", "structural"),
               ("uncertainty", "structural"), ("task_conditioned", "frontier"),
               ("frontier_t0", "structural"), ("task_conditioned_t0", "structural"),
               ("task_conditioned_t0", "frontier_t0"))


def main(output_dir):
    output = Path(output_dir)
    rows = load(sorted(output.glob("episodes-*.csv")))
    policies = {r["policy"] for r in rows}
    report = {"episodes": len(rows),
              "note": "'needs_exploration' = no accepting path in the budget-512 product graph; "
                      "medians count every failure at the 4096 budget; rows marked post_hoc were "
                      "designed after the world-2505 pilot",
              "success": success_table(rows),
              "paired": [paired(rows, a, b) for a, b in COMPARISONS
                         if a in policies and b in policies],
              "identical_episodes": [identical(rows, a, b) for a, b in
                                     (("task_conditioned", "frontier"),
                                      ("task_conditioned_t0", "frontier_t0"))
                                     if a in policies and b in policies]}
    (output/"summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1]), indent=2))
