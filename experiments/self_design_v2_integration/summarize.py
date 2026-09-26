"""Fixed descriptive comparisons; no feedback to the Designer."""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import statistics

from .run import MANIFEST
from .verify import write

METRICS = ("success_rate", "random_success_rate", "strategic_gap", "mean_actions_to_goal",
           "state_coverage", "edge_coverage", "unique_successful_trajectories", "action_entropy",
           "repeated_loop_rate", "dead_end_rate", "unexplored_regions", "goal_reuse_rate")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", choices=("smoke", "full"), required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--smoke-input", type=Path)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    seeds = MANIFEST["fresh_creation_seeds"] if args.stage == "full" else [MANIFEST["smoke_seed"]]
    expected = {(s, m) for s in seeds for m in MANIFEST["methods"]}
    found, rows, histories = {}, [], {}
    initial_hashes = {}
    issues = []
    for path in sorted(args.input.rglob("completed.json")):
        item = read(path)
        key = (item["seed"], item["method"])
        if key in found or key not in expected or item["stage"] != args.stage:
            issues.append(f"unexpected/duplicate completion: {path}")
            continue
        found[key] = path
        for control in MANIFEST["controls"]:
            directory = path.parent / control
            summary = read(directory / "summary.json")
            history = read(directory / "history.json")
            resources = read(directory / "resources.json")
            initial = read(directory / "game_initial.json")
            game_hash = hashlib.sha256(json.dumps(initial, sort_keys=True).encode()).hexdigest()
            initial_hashes.setdefault(item["seed"], set()).add(game_hash)
            for audit in summary["evaluations"]:
                if (audit["training_steps"] != 2500 or audit["oracle_calls"] != 0
                        or audit["goal_queries_during_training"] != 0 or not audit["replay_all_recorded_actions_verified"]):
                    issues.append(f"evaluation audit: {path}")
            if len(summary["evaluations"]) != item["iterations"] + 1 or len(history) != item["iterations"] + 1:
                issues.append(f"evaluation/history length: {path}")
            if sum(h["accepted"] for h in history[1:]) != summary["accepted_edits"]:
                issues.append(f"acceptance count: {path}")
            row = {"seed": item["seed"], "method": item["method"], "control": control,
                   "accepted_edits": summary["accepted_edits"], "iterations": item["iterations"],
                   **{name: summary["final"][name] for name in METRICS},
                   "successes": summary["final"]["successes"], "trials": summary["final"]["trials"],
                   "initial_exploration_known_states": summary["evaluations"][0]["known_states"],
                   "final_exploration_known_pairs": summary["evaluations"][-1]["known_state_action_pairs"],
                   "virtual_solve_cpu_seconds": sum(e["virtual_factorization_and_solve_cpu_seconds"] for e in summary["evaluations"]),
                   "evaluation_cpu_seconds": sum(e["total_evaluation_cpu_seconds"] for e in summary["evaluations"]),
                   "total_cpu_seconds": resources["cpu_seconds"], "wall_seconds": resources["wall_seconds"],
                   "peak_process_memory_bytes": resources["peak_process_memory_bytes"]}
            rows.append(row)
            histories[(item["seed"], item["method"], control)] = history
    if set(found) != expected:
        issues.append(f"missing units: {sorted(expected - set(found))}")
    if any(len(hashes) != 1 for hashes in initial_hashes.values()):
        issues.append("initial game differs between conditions")
    if args.smoke_input:
        for path in args.smoke_input.rglob("completed.json"):
            item = read(path)
            for control in MANIFEST["controls"]:
                small = read(path.parent / control / "history.json")
                large = histories.get((item["seed"], item["method"], control), [])
                if small != large[:len(small)]:
                    issues.append(f"smoke/full first-five prefix mismatch: {item['method']} {control}")
    paired = []
    contrasts = (("virtual_frontier", "structural"), ("frontier_t0", "structural"), ("virtual_frontier", "frontier_t0"))
    index = {(r["seed"], r["method"], r["control"]): r for r in rows}
    for control in MANIFEST["controls"]:
        for left, right in contrasts:
            for metric in (*METRICS, "accepted_edits", "evaluation_cpu_seconds"):
                differences = [{"seed": s, "left_minus_right": index[s, left, control][metric] - index[s, right, control][metric]}
                               for s in seeds if (s, left, control) in index and (s, right, control) in index]
                if differences:
                    values = [d["left_minus_right"] for d in differences]
                    paired.append({"control": control, "left": left, "right": right, "metric": metric,
                        "world_count": len(values), "mean_difference": statistics.mean(values),
                        "median_difference": statistics.median(values), "positive": sum(v > 0 for v in values),
                        "zero": sum(v == 0 for v in values), "negative": sum(v < 0 for v in values), "raw": differences})
    write(args.output / "audit.json", {"passed": not issues, "issues": issues, "completed_units": len(found),
          "expected_units": len(expected), "scope": "correctness and completeness, not a performance pass criterion"})
    write(args.output / "metrics.json", {"stage": args.stage, "rows": rows, "paired_comparisons": paired,
          "analysis_unit": "creation seed; deterministic trials are not independent worlds"})
    if rows:
        with (args.output / "per_seed_condition.csv").open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    print(json.dumps({"passed": not issues, "issues": issues, "completed_units": len(found)}, indent=2))
    if issues:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
