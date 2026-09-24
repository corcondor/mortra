"""Read saved artifacts; validate, plot and describe without rerunning a player."""
import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

from .designer import CONDITIONS, FAMILIES
from .runner import config, csv_write, sources, write_json
from .world import Engine, canonical

COLORS = {"mortra": "#157a6e", "random": "#c45159", "size_only": "#4465a4"}


def validate_run(run):
    cfg = config(run["stage"])
    assert run["status"] == "COMPLETED"
    assert run["config"] == cfg
    assert len(run["frontier"]) == cfg["generations"] + 1
    assert len(run["mutation_history"]) == cfg["generations"] * cfg["candidates"]
    assert run["provenance"]["source_hashes_lf"] == sources()
    for record in run["candidates"]:
        oracle = record["oracle"]
        if oracle["status"] != "SOLVABLE":
            assert not record["learning"] and record["final_success"] is None
            continue
        assert [c["budget"] for c in record["learning"]] == cfg["checkpoints"]
        rates = []
        for point in record["learning"]:
            ev = point["evaluation"]
            assert ev["trials"] == cfg["trials"] == len(ev["trials_detail"])
            assert 0 <= ev["successes"] <= ev["trials"]
            assert sum(t["success"] for t in ev["trials_detail"]) == ev["successes"]
            assert ev["success_rate"] == ev["successes"] / ev["trials"]
            assert 0 <= point["state_coverage"] <= 1 and 0 <= point["edge_coverage"] <= 1
            assert ev["q"] == 0.90 and ev["evaluation_updates"] == 0
            assert ev["first_trial"]["evaluator_replay_verified"]
            rates.append(ev["success_rate"])
        b80 = next((b for b, s in zip(cfg["checkpoints"], rates) if s >= 0.8), None)
        assert record["b80"] == b80
        assert record["difficulty_area"] == sum(1 - s for s in rates)
        assert record["final_success"] == rates[-1]
        assert len(record["random_policy"]["trials_detail"]) == cfg["trials"]
        assert record["random_policy"]["successes"] == sum(t["success"] for t in record["random_policy"]["trials_detail"])
    return True


def summarize(inputs, output, stage, enforce_gate=False):
    paths = sorted(Path(inputs).rglob("results.json"))
    loaded = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in paths]
    loaded = [(p, r) for p, r in loaded if r.get("stage") == stage and "condition" in r]
    cfg = config(stage)
    expected = {(s, c) for s in cfg["seeds"] for c in CONDITIONS}
    actual = [(r["seed"], r["condition"]) for _, r in loaded]
    assert len(actual) == len(set(actual)), "duplicate seed/condition run"
    assert set(actual) == expected, f"incomplete stage: {len(actual)}/{len(expected)}"
    for _, run in loaded:
        validate_run(run)
    assert len({r["provenance"]["git_head"] for _, r in loaded}) == 1
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False)
    figures = output / "figures"
    figures.mkdir()
    records = [c for _, r in loaded for c in r["candidates"]]
    measured = [r for r in records if r["learning"]]
    frontier = [(r["seed"], r["condition"], g, f) for _, r in loaded for g, f in enumerate(r["frontier"])]
    changing = sum(len({x["evaluation"]["success_rate"] for x in c["learning"]}) > 1 for c in measured)
    generated_solvable = sum(c["generation"] > 0 and c["oracle"]["status"] == "SOLVABLE" for c in records)
    gates = {"all_registered_runs_complete": True, "all_metrics_valid": True,
             "generated_solvable_candidates": generated_solvable > 0,
             "learning_curves_change": changing > 0}
    by_condition = {}
    for cond in CONDITIONS:
        rs = [r for _, r in loaded if r["condition"] == cond]
        initial = [r["frontier"][0] for r in rs]
        final = [r["frontier"][-1] for r in rs]
        finite = [r["b80"] for r in final if r["b80"] is not None]
        by_condition[cond] = {
            "independent_seeds": len(rs), "initial_b80": [r["b80"] for r in initial],
            "final_b80": [r["b80"] for r in final], "final_b80_censored_count": len(final) - len(finite),
            "final_b80_mean_uncensored_only": float(np.mean(finite)) if finite else None,
            "final_success_mean": float(np.mean([r["final_success"] for r in final])),
            "frontier_increased_seeds": sum(a["b80"] is not None and b["b80"] is not None and b["b80"] > a["b80"] for a, b in zip(initial, final)),
            "final_board_areas": [r["board_width"] * r["board_height"] for r in final],
            "final_reachable_states": [r["oracle"]["reachable_states"] for r in final],
            "final_rule_depth": [r["rule_dependency_depth"] for r in final],
            "wall_seconds_sum": sum(r["wall_seconds"] for r in rs),
            "process_peak_rss_bytes_max": max(r["process_peak_rss_bytes"] for r in rs),
            "oracle_status_counts": dict(Counter(c["oracle"]["status"] for r in rs for c in r["candidates"])),
            "invalid_mutations": sum(m["status"] == "INVALID" for r in rs for m in r["mutation_history"]),
            "solvable_but_final_unlearned": sum(c["oracle"]["status"] == "SOLVABLE" and c["final_success"] < 0.8 for r in rs for c in r["candidates"]),
            "training_cpu_seconds": sum(c["learning"][-1]["training_cpu_seconds"] for r in rs for c in r["candidates"] if c["learning"]),
            "evaluation_cpu_seconds": sum(pt["evaluation"]["evaluation_cpu_seconds"] for r in rs for c in r["candidates"] for pt in c["learning"]),
            "oracle_cpu_seconds": sum(c["oracle"]["cpu_seconds"] for r in rs for c in r["candidates"]),
        }
    summary = {"stage": stage, "status": "COMPLETED", "runs": len(loaded),
               "gates": gates, "stage1_pass": all(gates.values()) if stage == 1 else None,
               "measured_candidates": len(measured), "generated_solvable": generated_solvable,
               "changing_learning_curves": changing, "conditions": by_condition,
               "provenance": loaded[0][1]["provenance"], "limitations": [
                   "Exact opaque complete-state observation; no perception or latent-state discovery.",
                   "No cross-game memory, transfer or semantic abstraction tested.",
                   "Thirty deterministic repetitions are not independent tasks.",
                   "State/action labels and tie rules frozen; no action-relabel invariance claim.",
                   "Syntactic rule dependency need not lie on a successful solution.",
                   "B80 is interval-measured; right-censored values are not numeric 8000.",
                   "Oracle cap exhaustion is unresolved, never unsolvable.",
                   "Reported complexity relations are associations, not causal effects."]}
    write_json(output / "results.json", summary)
    write_json(output / "config.json", cfg)
    write_json(output / "source_sha.json", sources())
    write_json(output / "environment.json", [r["provenance"] for _, r in loaded])
    write_json(output / "mutation_history.json", [m for _, r in loaded for m in r["mutation_history"]])
    (output / "run.log").write_text(f"Validated {len(loaded)} runs; {len(measured)} measured candidates; {changing} changing curves.\n", encoding="utf-8")
    frontier_rows = [{"seed": s, "condition": c, "generation": g, "game_hash": f["game_hash"],
                      "b80": f["b80"], "b80_label": f["b80_label"], "final_success": f["final_success"],
                      "board_area": f["board_width"] * f["board_height"], "reachable_states": f["oracle"]["reachable_states"],
                      "b80_per_reachable_state": f["b80"] / f["oracle"]["reachable_states"] if f["b80"] is not None else None,
                      "rules": f["rules"], "objects": f["objects"], "rule_dependency_depth": f["rule_dependency_depth"]}
                     for s, c, g, f in frontier]
    csv_write(output / "frontier.csv", frontier_rows)
    curve_rows = [{"seed": s, "condition": c, "generation": g, "budget": p["budget"],
                   "success_rate": p["evaluation"]["success_rate"], "state_coverage": p["state_coverage"], "edge_coverage": p["edge_coverage"]}
                  for s, c, g, f in frontier for p in f["learning"]]
    csv_write(output / "learning_curves.csv", curve_rows)
    figure_frontiers(frontier_rows, figures, cfg)
    figure_curves(curve_rows, figures, cfg)
    figure_complexity(frontier_rows, figures)
    figure_coverage(records, figures)
    figure_mutations([m for _, r in loaded for m in r["mutation_history"]], figures)
    render_recorded_games(loaded, figures, cfg)
    lines = [f"# Autonomous Game Frontier v1: Stage {stage}", "", f"Completed condition/seed runs: {len(loaded)}/{len(expected)}.",
             f"Measured candidate occurrences: {len(measured)}; changing checkpoint curves: {changing}.", "",
             "| Condition | Final B80 by seed (null = right-censored) | Final success mean | Increased seeds | Unlearned solvable candidates |",
             "| --- | --- | --- | --- | --- |"]
    for cond, values in by_condition.items():
        lines.append(f"| {cond} | {values['final_b80']} | {values['final_success_mean']:.3f} | {values['frontier_increased_seeds']}/{values['independent_seeds']} | {values['solvable_but_final_unlearned']} |")
    lines += ["", "## Measured result versus interpretation", "",
              "B80 changes describe this frozen player's learning budget, not general intelligence or semantic understanding.",
              "The control and complexity figures show associations; no mechanic-level causal ablation was performed.",
              "A flat frontier, oracle exclusions or unlearned solvable candidates are retained, not tuned away.", "",
              "## Limitations", "", *["- " + x for x in summary["limitations"]], "",
              "## Gate", "", canonical(gates), "",
              "Representative images use the first registered seed (201), generation 0/middle/final, and trial 0.",
              "They replay saved actions and verify full-state-sequence hashes and terminal success, without generating new actions."]
    (output / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)
    if enforce_gate and not all(gates.values()):
        raise SystemExit("STAGE_1_GATE_NOT_MET: no Stage 2; no algorithm retuning")
    return summary


def save(fig, path):
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def figure_frontiers(rows, dest, cfg):
    fig, axes = plt.subplots(1, 2, figsize=(11, 4))
    for cond in CONDITIONS:
        selected = [r for r in rows if r["condition"] == cond]
        for seed in cfg["seeds"]:
            seq = sorted([r for r in selected if r["seed"] == seed], key=lambda r: r["generation"])
            axes[0].plot([r["generation"] for r in seq], [np.nan if r["b80"] is None else r["b80"] for r in seq], color=COLORS[cond], alpha=.3)
        means = [np.mean([r["b80"] for r in selected if r["generation"] == g and r["b80"] is not None])
                 if any(r["generation"] == g and r["b80"] is not None for r in selected) else np.nan for g in range(cfg["generations"] + 1)]
        axes[0].plot(range(cfg["generations"] + 1), means, color=COLORS[cond], label=cond, linewidth=2)
        axes[1].plot(range(cfg["generations"] + 1), [np.mean([r["final_success"] for r in selected if r["generation"] == g]) for g in range(cfg["generations"] + 1)], label=cond, color=COLORS[cond])
    axes[0].set(title="B80 (uncensored means only; missing = censored)", xlabel="Generation", ylabel="Interactions")
    axes[1].set(title="Final-checkpoint success", xlabel="Generation", ylabel="Success fraction", ylim=(-.02, 1.02))
    axes[0].legend()
    axes[1].legend()
    fig.tight_layout()
    fig.savefig(dest / "control_comparison.png", dpi=150)
    save(fig, dest / "frontier_b80.png")


def figure_curves(rows, dest, cfg):
    fig, axes = plt.subplots(1, 3, figsize=(12, 4), sharey=True)
    for ax, gen in zip(axes, (0, cfg["generations"] // 2, cfg["generations"])):
        for cond in CONDITIONS:
            ax.plot(cfg["checkpoints"], [np.mean([r["success_rate"] for r in rows if r["condition"] == cond and r["generation"] == gen and r["budget"] == b]) for b in cfg["checkpoints"]], "o-", color=COLORS[cond], label=cond)
        ax.set(title=f"Generation {gen}", xlabel="Training interactions", ylim=(-.02, 1.02))
    axes[0].set_ylabel("Mean success fraction")
    axes[-1].legend()
    save(fig, dest / "learning_curves.png")


def figure_complexity(rows, dest):
    fig, axes = plt.subplots(2, 3, figsize=(13, 8))
    for ax, metric in zip(axes.flat, ("board_area", "reachable_states", "rule_dependency_depth", "rules", "objects", "generation")):
        for cond in CONDITIONS:
            rs = [r for r in rows if r["condition"] == cond and r["b80"] is not None]
            ax.scatter([r[metric] for r in rs], [r["b80_per_reachable_state"] if metric == "generation" else r["b80"] for r in rs], color=COLORS[cond], label=cond, alpha=.45, s=16)
        ax.set(xlabel=metric, ylabel="B80 / reachable states" if metric == "generation" else "B80 (uncensored)")
    axes[0, 0].legend()
    save(fig, dest / "complexity_vs_b80.png")


def figure_coverage(records, dest):
    fig, ax = plt.subplots(figsize=(7, 4))
    for cond in CONDITIONS:
        ps = [p for r in records if r["condition"] == cond for p in r["learning"]]
        ax.scatter([p["edge_coverage"] for p in ps], [p["evaluation"]["success_rate"] for p in ps], color=COLORS[cond], alpha=.2, s=10, label=cond)
    ax.set(xlabel="Observed state-action coverage / exact reachable graph", ylabel="Success fraction")
    ax.legend()
    save(fig, dest / "coverage_vs_success.png")


def figure_mutations(mutations, dest):
    fig, ax = plt.subplots(figsize=(12, 5))
    for i, cond in enumerate(CONDITIONS):
        selected = Counter(m["mutation"] for m in mutations if m["condition"] == cond and m.get("selected"))
        proposed = Counter(m["mutation"] for m in mutations if m["condition"] == cond)
        ax.bar(np.arange(len(FAMILIES)) + (i - 1) * .25, [selected[f] / proposed[f] if proposed[f] else 0 for f in FAMILIES], width=.25, color=COLORS[cond], label=cond)
    ax.set_xticks(range(len(FAMILIES)), FAMILIES, rotation=50, ha="right")
    ax.set_ylabel("Selected occurrences / proposed occurrences (0 if not proposed)")
    ax.legend()
    save(fig, dest / "mutation_survival.png")


def render_recorded_games(loaded, dest, cfg):
    fig, axes = plt.subplots(3, 3, figsize=(12, 12))
    for row, condition in enumerate(CONDITIONS):
        path, run = next((p, r) for p, r in loaded if r["seed"] == 201 and r["condition"] == condition)
        for col, generation in enumerate((0, cfg["generations"] // 2, cfg["generations"])):
            r = run["frontier"][generation]
            genome = json.loads((path.parent / "games" / r["game_hash"] / "genome.json").read_text())
            engine = Engine(genome)
            first = r["learning"][-1]["evaluation"]["first_trial"]
            state, sequence = engine.initial, [engine.initial]
            for action in first["actions"]:
                state = engine.step(state, action)
                sequence.append(state)
            assert hashlib.sha256(canonical([asdict(s) for s in sequence]).encode()).hexdigest() == first["evaluator_state_sequence_sha256"]
            assert engine.is_goal(state) == first["success"]
            assert len(sequence) == first["steps"] + 1
            ax = axes[row, col]
            board = np.ones((engine.height, engine.width, 3))
            for x, y in engine.walls:
                board[y, x] = [.22, .24, .26]
            ax.imshow(board, origin="upper")
            ax.plot([s.x for s in sequence], [s.y for s in sequence], color="#397bac", linewidth=2)
            ax.scatter(*genome["start"], marker="o", color="#157a6e", s=70)
            ax.scatter(*genome["goal"], marker="*", color="#c45159", s=130)
            for o in genome["objects"]:
                ax.text(*o["position"], str(o["id"]), ha="center", va="center", color="#9d42a1", fontsize=9)
            ax.set_title(f"seed 201 / {condition} / G{generation}\ntrial 0 / {first['steps']} actions / success={first['success']}\nB80={r['b80_label']}", fontsize=9)
            ax.set_xticks([])
            ax.set_yticks([])
    fig.suptitle("Recorded-action replay, not new search; objects shown at initial positions", fontsize=13)
    fig.tight_layout(rect=(0, 0, 1, .95))
    fig.savefig(dest / "recorded_games.png", dpi=150)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--input", required=True)
    p.add_argument("--output", required=True)
    p.add_argument("--stage", type=int, choices=(1, 2), required=True)
    p.add_argument("--enforce-gate", action="store_true")
    a = p.parse_args()
    summarize(a.input, a.output, a.stage, a.enforce_gate)


if __name__ == "__main__":
    main()
