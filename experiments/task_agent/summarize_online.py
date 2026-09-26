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


def success_table(rows):
    groups = defaultdict(list)
    for r in rows:
        subset = "starts_in_model" if r["starts_in_model"] else "out_of_model"
        groups[(subset, r["policy"])].append(r)
        groups[("all", r["policy"])].append(r)
    out = []
    for (subset, policy), items in sorted(groups.items()):
        solved = [r for r in items if r["success"]]
        steps = sorted(r["task_steps"] for r in solved)
        row = {"subset": subset, "policy": policy, "episodes": len(items),
               "median_steps_solved": statistics.median(steps) if steps else None,
               "mean_steps_solved": round(statistics.mean(steps), 1) if steps else None,
               "mean_seconds": round(statistics.mean(r["seconds"] for r in items), 3)}
        for cap in CAPS:
            row[f"success_at_{cap}"] = sum(1 for r in solved if r["task_steps"] <= cap)
        out.append(row)
    return out


def paired(rows, reference="structural"):
    """Each policy against the reference on the same task: who finished first, and by how much."""
    by = defaultdict(dict)
    for r in rows:
        by[(r["seed"], r["task_id"])][r["policy"]] = r
    table = defaultdict(lambda: {"tasks": 0, "both_solved": 0, "policy_fewer_steps": 0,
                                 "reference_fewer_steps": 0, "same_steps": 0,
                                 "only_policy_solved": 0, "only_reference_solved": 0,
                                 "step_ratios": []})
    for key, per in by.items():
        if reference not in per:
            continue
        ref = per[reference]
        if ref["starts_in_model"]:
            continue                               # only the tasks that needed exploration
        for policy, r in per.items():
            if policy == reference:
                continue
            t = table[policy]
            t["tasks"] += 1
            if r["success"] and ref["success"]:
                t["both_solved"] += 1
                t["policy_fewer_steps"] += r["task_steps"] < ref["task_steps"]
                t["reference_fewer_steps"] += ref["task_steps"] < r["task_steps"]
                t["same_steps"] += r["task_steps"] == ref["task_steps"]
                t["step_ratios"].append(r["task_steps"]/max(1, ref["task_steps"]))
            elif r["success"]:
                t["only_policy_solved"] += 1
            elif ref["success"]:
                t["only_reference_solved"] += 1
    out = []
    for policy, t in sorted(table.items()):
        ratios = t.pop("step_ratios")
        out.append({"policy": policy, "reference": reference, **t,
                    "median_step_ratio": round(statistics.median(ratios), 3) if ratios else None})
    return out


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


def main(output_dir):
    output = Path(output_dir)
    rows = load(sorted(output.glob("episodes-*.csv")))
    report = {"episodes": len(rows),
              "success": success_table(rows),
              "paired_against_structural": paired(rows),
              "task_conditioned_vs_frontier": identical(rows, "task_conditioned", "frontier"),
              "task_conditioned_t0_vs_frontier_t0": identical(rows, "task_conditioned_t0",
                                                               "frontier_t0")}
    (output/"summary.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


if __name__ == "__main__":
    print(json.dumps(main(sys.argv[1]), indent=2))
