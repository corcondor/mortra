"""Report fixed paired contrasts without interpreting different games as equals."""
import argparse
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from experiments.v2_online_feedback.adapter import ARMS
from experiments.v2_online_feedback.prepare import write
from .run import MODES, SEEDS, read


def csv_write(path, rows):
    with path.open("x", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(inputs, output):
    output.mkdir(parents=True, exist_ok=False)
    worlds = [read(p) for p in inputs.rglob("world_complete.json")]
    commons = [read(p) for p in inputs.rglob("common_complete.json")]
    assert len(worlds) == len(commons) == 8
    assert {w["seed"] for w in worlds} == {w["seed"] for w in commons} == set(SEEDS)
    series = [s for w in worlds for s in w["series"]]
    common = {(r["seed"], r["origin_arm"], r["mode"]): r for w in commons for r in w["results"]}
    assert len(series) == len(common) == 48
    rows = []
    for s in sorted(series, key=lambda s: (s["seed"], ARMS.index(s["arm"]), s["mode"])):
        c = common[s["seed"], s["arm"], s["mode"]]
        rows.append({"seed": s["seed"], "arm": s["arm"], "mode": s["mode"],
            "initial_successes": s["initial_metrics"]["successes"], "series_final_successes": s["final_metrics"]["successes"],
            "series_final_cost": s["final_mean_capped_cost"], "series_final_gap": s["final_metrics"]["strategic_gap"],
            "common_c_successes": c["successes"], "common_c_cost": c["mean_capped_cost"],
            "common_random_successes": c["random_successes"], "common_c_gap": c["metrics"]["strategic_gap"],
            "accepted_edits": s["accepted_edits"], "final_game_changed": s["final_game_changed"],
            "final_goal_changed": s["final_goal_changed"], "final_start_changed": s["final_start_changed"],
            "accepted_goal_changes": s["accepted_goal_changes"], "proposed_goal_changes": s["proposed_goal_changes"],
            "initial_training_actions": s["phase_actions"]["initial"], "additional_actions": s["phase_actions"]["additional"],
            "series_total_environment_actions": s["total_environment_actions"],
            "series_cpu_seconds": s["series_cpu_seconds"], "evaluation_cpu_seconds": s["evaluation_cpu_seconds"],
            "common_total_environment_actions": c["total_environment_actions"], "common_cpu_seconds": c["evaluation_cpu_seconds"]})
    csv_write(output / "all_final_worlds.csv", rows)
    aggregates, differences = [], []
    for mode in MODES:
        for arm in ARMS:
            group = [r for r in rows if r["arm"] == arm and r["mode"] == mode]
            aggregates.append({"mode": mode, "arm": arm, "games": len(group), "trials": len(group) * 50,
                "series_final_successes": sum(r["series_final_successes"] for r in group),
                "series_final_mean_cost": float(np.mean([r["series_final_cost"] for r in group])),
                "common_c_successes": sum(r["common_c_successes"] for r in group),
                "common_c_mean_cost": float(np.mean([r["common_c_cost"] for r in group])),
                "common_random_successes": sum(r["common_random_successes"] for r in group),
                "accepted_edits": sum(r["accepted_edits"] for r in group),
                "final_goal_changed_games": sum(r["final_goal_changed"] for r in group),
                "total_environment_actions": sum(r["series_total_environment_actions"] for r in group),
                "series_cpu_seconds": sum(r["series_cpu_seconds"] for r in group)})
        for label, x, y in (("C-B", ARMS[2], ARMS[1]), ("B-A", ARMS[1], ARMS[0]), ("C-A", ARMS[2], ARMS[0])):
            for metric in ("series_final_cost", "common_c_cost", "series_final_successes", "common_c_successes", "common_random_successes", "common_c_gap", "accepted_edits"):
                values = []
                for seed in SEEDS:
                    rx = next(r for r in rows if (r["seed"], r["arm"], r["mode"]) == (seed, x, mode))
                    ry = next(r for r in rows if (r["seed"], r["arm"], r["mode"]) == (seed, y, mode))
                    values.append(rx[metric] - ry[metric])
                differences.append({"mode": mode, "contrast": label, "metric": metric,
                    "mean_world_difference": float(np.mean(values)), "median_world_difference": float(np.median(values)),
                    "negative_worlds": sum(v < 0 for v in values), "equal_worlds": sum(v == 0 for v in values),
                    "positive_worlds": sum(v > 0 for v in values), "raw_differences_seed_order": values})
    csv_write(output / "aggregate.csv", aggregates)
    write(output / "paired_contrasts.json", differences)
    changes = [{"seed": s["seed"], "arm": s["arm"], "mode": s["mode"], **c} for s in series for c in s["changes"]]
    csv_write(output / "all_game_changes.csv", changes)
    resources = [read(p) for p in inputs.rglob("resources.json")]
    totals = {"worker_cpu_seconds": sum(r["cpu_seconds"] for r in resources),
        "worker_wall_seconds_sum_not_elapsed": sum(r["wall_seconds"] for r in resources),
        "max_peak_working_set_bytes": max((r["peak_working_set_bytes"] or 0 for r in resources), default=0),
        "production_environment_actions": sum(s["total_environment_actions"] for s in series),
        "production_learning_actions": 1008 * 7500,
        "common_environment_actions": sum(r["total_environment_actions"] for r in common.values()),
        "common_learning_actions": 48 * 7500,
        "production_verification_replay_actions": sum(s["verification_replay_actions"] for s in series),
        "common_verification_replay_actions": sum(r["verification_replay_actions"] for r in common.values())}
    write(output / "summary.json", {"status": "COMPLETE", "development_only": True, "series": 48,
        "production_evaluations": 1008, "common_evaluations": 48, "aggregate": aggregates, "resources": totals,
        "interpretation": "Different arms produce different games; own-series success is not a game-quality comparison."})
    fig, axes = plt.subplots(1, 2, figsize=(12, 4), constrained_layout=True)
    for ax, mode in zip(axes, MODES):
        g = [a for a in aggregates if a["mode"] == mode]
        x = np.arange(3)
        ax.bar(x - .18, [r["series_final_successes"] / 400 for r in g], .36, label="Own evaluator")
        ax.bar(x + .18, [r["common_c_successes"] / 400 for r in g], .36, label="Common C evaluator")
        ax.set(xticks=x, xticklabels=["A", "B", "C"], ylim=(0, 1.08), title=mode, ylabel="Final-game success / 400 trials")
        ax.legend()
    fig.savefig(output / "final_success.png", dpi=150)
    plt.close(fig)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    summarize(a.input, a.output)
