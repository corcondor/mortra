"""Read saved trials only; report all worlds and all three paired contrasts."""
import argparse
import csv
import gzip
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from .adapter import ARMS
from .prepare import SEEDS, write, sha
from .run import CHECKPOINTS

LABELS = dict(zip(ARMS, ("A: frozen", "B: record + replan", "C: record + replan + explore")))


def csv_write(path, rows):
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def trials(path):
    with gzip.open(path, "rt") as stream:
        return [json.loads(line) for line in stream]


def draw_trials(seed, root, output):
    game = json.loads((root / "game.json").read_text())
    fig, axes = plt.subplots(1, 3, figsize=(14, 5.4))
    for axis, arm in zip(axes, ARMS):
        record = trials(root / arm / "checkpoint_5000/evaluation_trials.jsonl.gz")[0]
        for x, y in game["walls"]:
            axis.add_patch(Rectangle((x - .5, y - .5), 1, 1, color="#454b55"))
        for x, y in game["hazards"]:
            axis.scatter(x, y, color="#d13c50", marker="x", s=65)
        for key, label, color in (("key_pos", "K", "#cf9c13"), ("door_pos", "D", "#b57716"),
                                 ("switch_pos", "S", "#805ac3"), ("gate_pos", "G", "#9b71c9"),
                                 ("block_pos", "B", "#7b8e90"), ("teleport_a", "P", "#188dad"),
                                 ("teleport_b", "P", "#188dad")):
            if game[key] is not None:
                axis.text(*game[key], label, ha="center", va="center", color=color, weight="bold")
        states = record["states"]
        axis.plot([s[0] for s in states], [s[1] for s in states], color="#197a65", lw=2, alpha=.65)
        axis.scatter(*game["start_pos"], marker="s", s=90, color="#2274af", label="start")
        axis.scatter(*game["goal_pos"], marker="*", s=160, color="#e09f22", label="goal")
        axis.scatter(states[-1][0], states[-1][1], s=40, color="#171b1e", label="final position")
        axis.set(xlim=(-.5, game["width"] - .5), ylim=(game["height"] - .5, -.5), aspect="equal")
        axis.set_title(f"{LABELS[arm]}\ntrial 0: {len(record['actions'])} actions; success={record['success']}", fontsize=10)
        axis.set_xticks([])
        axis.set_yticks([])
    axes[0].legend(loc="lower left", fontsize=7)
    fig.suptitle(f"Seed {seed}: frozen evaluation at +5000 actions\nSaved state/action trace visualization, not live frames; all conditions' first trial", fontsize=11)
    fig.tight_layout()
    fig.savefig(output / f"saved_trial_{seed}.png", dpi=140)
    plt.close(fig)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    worlds, rows, resources, hashes = {}, [], [], {}
    for file in args.input.rglob("completed.json"):
        record = json.loads(file.read_text())
        if record.get("seed") not in SEEDS or record.get("status") != "COMPLETED":
            continue
        seed = record["seed"]
        assert seed not in worlds, f"Duplicate completed world {seed}"
        worlds[seed] = file.parent
        resources.append(record)
        metrics = json.loads((file.parent / "metrics.json").read_text())
        assert {(r["arm"], r["checkpoint"]) for r in metrics} == {(a, b) for a in ARMS for b in CHECKPOINTS}
        assert len(metrics) == 9
        assert len({r["game_hash"] for r in metrics}) == 1
        assert len({r["learner_hash"] for r in metrics if r["checkpoint"] == 0}) == 1
        assert all(r["evaluation_learner_unchanged"] and r["recomputed_field_bitwise_equal"] for r in metrics)
        assert all(r["additional_actions"] == r["checkpoint"] for r in metrics)
        for arm in ARMS:
            assert all(json.loads((file.parent / arm / "trace_audit.json").read_text())[key]
                       for key in ("all_executed_transitions_replayed", "reset_edges_absent", "recorded_counts_exact"))
        rows.extend(metrics)
        hashes[str(seed)] = {p.relative_to(file.parent).as_posix(): sha(p.read_bytes())
                            for p in file.parent.rglob("*") if p.is_file()}
        draw_trials(seed, file.parent, args.output)
    csv_write(args.output / "all_checkpoints.csv", rows)
    write(args.output / "input_hashes.json", hashes)
    write(args.output / "resources.json", resources)
    index = {(r["seed"], r["arm"], r["checkpoint"]): r for r in rows}
    paired, regressions = [], []
    for seed in sorted(worlds):
        for budget in CHECKPOINTS:
            for left, right in ((ARMS[2], ARMS[1]), (ARMS[1], ARMS[0]), (ARMS[2], ARMS[0])):
                a, b = index[seed, left, budget], index[seed, right, budget]
                paired.append({"seed": seed, "checkpoint": budget, "contrast": f"{left} minus {right}",
                    "success_count_difference": a["evaluation_successes"] - b["evaluation_successes"],
                    "mean_capped_cost_difference": a["mean_capped_cost"] - b["mean_capped_cost"],
                    "known_states_difference": a["known_states"] - b["known_states"],
                    "online_cpu_seconds_difference": a["online_cpu_seconds"] - b["online_cpu_seconds"]})
                first = trials(worlds[seed] / left / f"checkpoint_{budget}/evaluation_trials.jsonl.gz")
                second = trials(worlds[seed] / right / f"checkpoint_{budget}/evaluation_trials.jsonl.gz")
                for t, (x, y) in enumerate(zip(first, second)):
                    cx, cy = len(x["actions"]) if x["success"] else 100, len(y["actions"]) if y["success"] else 100
                    if cx > cy or x["success"] < y["success"]:
                        regressions.append({"seed": seed, "checkpoint": budget, "contrast": f"{left} minus {right}",
                            "trial": t, "cost_difference": cx - cy, "left_success": x["success"], "right_success": y["success"]})
    csv_write(args.output / "world_paired_comparisons.csv", paired)
    csv_write(args.output / "all_regressed_trials.csv", regressions)
    headline = {"status": "COMPLETED" if set(worlds) == set(SEEDS) else "INCOMPLETE",
        "completed_worlds": len(worlds), "registered_worlds": 8, "missing_seeds": sorted(set(SEEDS) - set(worlds)),
        "analysis": "Outcome-selected development; descriptive paired worlds, no fresh confirmatory claim",
        "by_checkpoint": [], "paired_summary": [], "resources": resources}
    for budget in CHECKPOINTS:
        for arm in ARMS:
            selected = [r for r in rows if r["arm"] == arm and r["checkpoint"] == budget]
            if selected:
                headline["by_checkpoint"].append({"arm": arm, "checkpoint": budget,
                    "successes": sum(r["evaluation_successes"] for r in selected), "trials": 50 * len(selected),
                    "mean_capped_cost": statistics.mean(r["mean_capped_cost"] for r in selected),
                    "mean_known_states": statistics.mean(r["known_states"] for r in selected),
                    "mean_known_pairs": statistics.mean(r["known_pairs"] for r in selected),
                    "total_online_cpu_seconds": sum(r["online_cpu_seconds"] for r in selected)})
        for contrast in sorted({r["contrast"] for r in paired}):
            selected = [r for r in paired if r["contrast"] == contrast and r["checkpoint"] == budget]
            differences = [r["mean_capped_cost_difference"] for r in selected]
            headline["paired_summary"].append({"checkpoint": budget, "contrast": contrast,
                "mean_cost_difference": statistics.mean(differences), "median_cost_difference": statistics.median(differences),
                "cost_improved_worlds": sum(d < 0 for d in differences), "cost_equal_worlds": differences.count(0),
                "cost_worsened_worlds": sum(d > 0 for d in differences)})
    write(args.output / "headline.json", headline)
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for arm, color in zip(ARMS, ("#657783", "#ba7f1d", "#18866c")):
        selected = [r for r in headline["by_checkpoint"] if r["arm"] == arm]
        axes[0].plot([r["checkpoint"] for r in selected], [100*r["successes"]/r["trials"] for r in selected], "o-", color=color, label=LABELS[arm])
        axes[1].plot([r["checkpoint"] for r in selected], [r["mean_capped_cost"] for r in selected], "o-", color=color)
    axes[0].set(ylabel="Frozen evaluation success (%)", ylim=(0, 105))
    axes[1].set(ylabel="Mean capped task cost (actions)")
    for axis in axes:
        axis.set_xlabel("Additional actual training actions")
        axis.grid(alpha=.2)
    axes[0].legend(fontsize=8)
    fig.suptitle(f"V2 online feedback: {len(worlds)}/8 historical worlds; development comparison")
    fig.tight_layout()
    fig.savefig(args.output / "comparison.png", dpi=150)
    plt.close(fig)
    print(json.dumps(headline, indent=2))


if __name__ == "__main__":
    main()
