"""Saved-result validation, plots and faithful recorded-action re-rendering."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle
import numpy as np

from experiments.game_frontier_v1.runner import csv_write, write_json
from .measurement import curve_metrics
from .runner import config, sources
from .world import Engine, canonical

COLORS = {"mortra": "#167b63", "random": "#b95350", "size_only": "#4774b3"}


def summarize(input_dir, output, stage, enforce_gate=False):
    loaded = [(p, json.loads(p.read_text(encoding="utf-8"))) for p in sorted(Path(input_dir).rglob("results.json"))]
    cfg = config(stage)
    assert len(loaded) == len(cfg["seeds"]) * 3
    assert {(r["seed"], r["condition"]) for _, r in loaded} == {(s, c) for s in cfg["seeds"] for c in cfg["conditions"]}
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    figures = out / "figures"
    figures.mkdir()
    hashes = sources()
    heads = {r["provenance"]["git_head"] for _, r in loaded}
    assert len(heads) == 1
    flat, frontier, learning = [], [], []
    shape_set = set()
    replay_count = task_count = 0
    def row(r, run, gen):
        return {"seed": run["seed"], "condition": run["condition"], "generation": gen, "candidate": r["candidate"],
                "game_hash": r["game_hash"], "mutation": r["mutation"],
                **{k: r[k] for k in ("D", "B50", "B80", "B90", "final_success", "classification")},
                "full_info_success": r["full_info"]["success_rate"] if r["full_info"] else None,
                "rule_relevance": r["relevance"]["mean_fraction"] if r["relevance"] else None,
                "median_distance": r.get("task_median_distance"),
                **{k: (r["complexity"] or {}).get(k) for k in ("reachable_states", "transition_edges", "actions", "variables", "domain_product", "rules", "guard_terms", "assignments", "rule_dependency_depth", "rule_dependency_cycles", "board_area", "branching_factor")}}
    for p, run in loaded:
        assert run["status"] == "COMPLETED" and run["config"] == cfg
        assert run["provenance"]["source_hashes_lf"] == hashes
        assert len(run["frontier"]) == cfg["generations"] + 1
        for gen, r in enumerate(run["frontier"]):
            assert r["valid"] and r["relevance"]["nonzero_relevance"] and r["task_median_distance"] > 2
            frontier.append(row(r, run, gen))
        assert run["frontier"][0]["task_median_distance"] >= 8
        for r in run["candidates"]:
            flat.append(row(r, run, r["generation"]))
            if not r["learning"]:
                continue
            assert len(r["tasks"]) == cfg["tasks"]
            assert len({(tuple(t["start"]), tuple(t["target"])) for t in r["tasks"]}) == cfg["tasks"]
            assert all(t["distance"] >= 4 for t in r["tasks"])
            assert hashlib.sha256(canonical(r["tasks"]).encode()).hexdigest() == r["tasks_sha256"]
            assert [c["budget"] for c in r["learning"]] == cfg["checkpoints"]
            assert all(r[k] == v for k, v in curve_metrics(r["learning"]).items())
            shape_set.add(tuple(c["evaluation"]["success_rate"] for c in r["learning"]))
            engine = Engine(json.loads((p.parent / "games" / r["game_hash"] / "genome.json").read_text()))
            for c in r["learning"]:
                e = c["evaluation"]
                assert e["tasks"] == cfg["tasks"] and e["successes"] == sum(t["success"] for t in e["task_results"])
                assert e["success_rate"] == e["successes"] / e["tasks"]
                assert e["graph_reuse_verified"] and e["evaluation_updates"] == 0
                assert e["q"] == .9 and e["psi_cutoff"] == 1e-7
                first = e["task_results"][0]
                trace = first["recorded_trajectory"]
                assert hashlib.sha256(canonical(trace).encode()).hexdigest() == first["trajectory_sha256"]
                state = tuple(r["tasks"][0]["start"])
                assert list(state) == trace["states"][0]
                for a, expected in zip(trace["actions"], trace["states"][1:]):
                    state = engine.step(state, a)
                    assert list(state) == expected
                assert len(trace["states"]) == len(trace["actions"]) + 1
                assert (list(state) == r["tasks"][0]["target"]) == first["success"]
                task_count += len(e["task_results"])
                replay_count += 1
                learning.append({"seed": run["seed"], "condition": run["condition"], "game_hash": r["game_hash"],
                                 "generation": r["generation"], "candidate": r["candidate"], "budget": c["budget"],
                                 "success": e["success_rate"], "edge_coverage": c["edge_coverage"],
                                 "training_cpu": c["training_cpu_seconds"], "evaluation_cpu": e["cpu_seconds"],
                                 "reasoning_cpu": e["solver_cpu_seconds"], "learner_bytes": c["learner_serialized_bytes"]})
    for seed in cfg["seeds"]:
        assert len({r["frontier"][0]["game_hash"] for _, r in loaded if r["seed"] == seed}) == 1
        assert len({r["frontier"][0]["tasks_sha256"] for _, r in loaded if r["seed"] == seed}) == 1
    final = [r for r in frontier if r["generation"] == cfg["generations"]]
    summary = {"stage": stage, "runs": len(loaded), "git_head": next(iter(heads)), "candidates": len(flat),
               "task_evaluations": task_count, "verified_first_task_replays": replay_count,
               "distinct_curve_shapes": len(shape_set), "source_hashes_lf": hashes,
               "stage1_gate_passed": len(shape_set) >= 2, "conditions": {}, "final": final}
    for cond in cfg["conditions"]:
        cr = [r for r in flat if r["condition"] == cond]
        fr = [r for r in final if r["condition"] == cond]
        cases = [run for _, run in loaded if run["condition"] == cond]
        summary["conditions"][cond] = {"categories": dict(Counter(r["classification"] for r in cr)),
            "final_D": [r["D"] for r in fr], "final_B80": [r["B80"] for r in fr], "final_B90": [r["B90"] for r in fr],
            "final_success": [r["final_success"] for r in fr], "final_full_info": [r["full_info_success"] for r in fr],
            "increased_D_seeds": [run["seed"] for run in cases if run["frontier"][-1]["D"] is not None
                                   and run["frontier"][-1]["D"] > run["frontier"][0]["D"]],
            "learning_cpu_seconds": sum(r["learning"][-1]["training_cpu_seconds"] for run in cases for r in run["candidates"] if r["learning"]),
            "evaluation_cpu_seconds": sum(c["evaluation"]["cpu_seconds"] for run in cases for r in run["candidates"] for c in r["learning"]),
            "preparation_cpu_seconds": sum(r["preparation_cpu_seconds"] for run in cases for r in run["candidates"]),
            "peak_rss_bytes": max(r["peak_rss_bytes"] for run in cases for r in run["candidates"])}
    write_json(out / "results_summary.json", summary)
    for name, rows in (("frontier", frontier), ("all_candidates", flat), ("learning_curves", learning), ("final", final)):
        csv_write(out / (name + ".csv"), rows)
    def save(fig, name):
        fig.savefig(figures / (name + ".png"), dpi=140)
        plt.close(fig)
    fig, axs = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)
    for ax, key in zip(axs, ["D", "B80", "B90"]):
        for _, run in loaded:
            cond = run["condition"]
            ax.plot(range(len(run["frontier"])), [r[key] if r[key] is not None else np.nan for r in run["frontier"]],
                    color=COLORS[cond], alpha=.6, marker=".", label=cond if run["seed"] == cfg["seeds"][0] else None)
        ax.set(title=key, xlabel="Generation")
        ax.legend()
    save(fig, "frontier_D_B80_B90")
    fig, axs = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)
    for ax, cond in zip(axs, cfg["conditions"]):
        for _, run in loaded:
            if run["condition"] == cond:
                for gen in [0, cfg["generations"] // 2, cfg["generations"]]:
                    r = run["frontier"][gen]
                    ax.plot([c["budget"] for c in r["learning"]], [c["evaluation"]["success_rate"] for c in r["learning"]], alpha=.4)
        ax.set(title=cond, xlabel="Interactions (log2)", ylabel="Distinct-task success", ylim=(-.05, 1.05))
        ax.set_xscale("log", base=2)
    save(fig, "learning_curves")
    fig, axs = plt.subplots(1, 2, figsize=(11, 4), constrained_layout=True)
    categories = ["LEARNED_SUCCESS", "EXPLORATION_LIMITED", "REASONER_LIMITED", "UNRESOLVED"]
    for j, cond in enumerate(cfg["conditions"]):
        rows = [r for r in flat if r["condition"] == cond and r["D"] is not None]
        axs[0].scatter([r["full_info_success"] for r in rows], [r["final_success"] for r in rows], alpha=.3, color=COLORS[cond], label=cond)
        counts = Counter(r["classification"] for r in flat if r["condition"] == cond)
        axs[1].bar(np.arange(4) + j * .25, [counts[k] for k in categories], width=.25, label=cond, color=COLORS[cond])
    axs[0].set(xlabel="Full-information success", ylabel="Learned-graph success")
    axs[0].legend()
    axs[1].set_xticks(np.arange(4) + .25, ["Learned", "Exploration", "Reasoner", "Unresolved"])
    axs[1].legend()
    save(fig, "full_info_failure_taxonomy")
    fig, axs = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)
    for ax, key in zip(axs.flat, ["reachable_states", "rule_relevance", "rule_dependency_depth", "board_area", "branching_factor", "variables"]):
        for cond in cfg["conditions"]:
            rows = [r for r in flat if r["condition"] == cond and r["D"] is not None and r[key] is not None]
            ax.scatter([r[key] for r in rows], [r["D"] for r in rows], color=COLORS[cond], s=8, alpha=.3, label=cond)
        ax.set(xlabel=key, ylabel="D")
        ax.legend()
    save(fig, "complexity_correlations")
    fig, ax = plt.subplots(figsize=(8, 4), constrained_layout=True)
    bins = ["4-7", "8-15", "16-31", "32+"]
    for j, cond in enumerate(cfg["conditions"]):
        parts = [r["frontier"][-1]["learning"][-1]["evaluation"]["success_by_distance_bin"] for _, r in loaded if r["condition"] == cond]
        values = [sum(p[b]["successes"] for p in parts) / sum(p[b]["tasks"] for p in parts) if sum(p[b]["tasks"] for p in parts) else np.nan for b in bins]
        ax.bar(np.arange(4) + j * .25, values, width=.25, color=COLORS[cond], label=cond)
    ax.set_xticks(np.arange(4) + .25, bins)
    ax.set(xlabel="Oracle shortest-distance bin", ylabel="Final frontier task success", ylim=(0, 1))
    ax.legend()
    save(fig, "success_by_distance")
    # Common first seed, task zero, initial/middle/final: no success-based picking.
    fig, axs = plt.subplots(3, 3, figsize=(12, 12), constrained_layout=True)
    render_manifest = []
    for row_id, cond in enumerate(cfg["conditions"]):
        p, run = next((p, r) for p, r in loaded if r["condition"] == cond and r["seed"] == cfg["seeds"][0])
        for col, gen in enumerate([0, cfg["generations"] // 2, cfg["generations"]]):
            r = run["frontier"][gen]
            g = json.loads((p.parent / "games" / r["game_hash"] / "genome.json").read_text())
            result = r["learning"][-1]["evaluation"]["task_results"][0]
            trace, task = result["recorded_trajectory"], r["tasks"][0]
            ax = axs[row_id, col]
            for x, y in g["walls"]:
                ax.add_patch(Rectangle((x, y), 1, 1, facecolor="#555555"))
            ax.plot([s[0] + .5 for s in trace["states"]], [s[1] + .5 for s in trace["states"]], color=COLORS[cond], linewidth=2)
            ax.plot(task["start"][0] + .5, task["start"][1] + .5, "o", color="#2463af")
            ax.plot(task["target"][0] + .5, task["target"][1] + .5, "*", color="#bf7219", markersize=12)
            ax.set(xlim=(0, g["domains"][0]), ylim=(g["domains"][1], 0), aspect="equal", xticks=[], yticks=[],
                   title=f"{cond} seed={run['seed']} G{gen} task=0\nsuccess={result['success']} actions={result['actual_actions']}")
            render_manifest.append({"condition": cond, "seed": run["seed"], "generation": gen, "task": 0,
                                    "game_hash": r["game_hash"], "trajectory_sha256": result["trajectory_sha256"],
                                    "source": "recorded actions and states; spatial projection only; target includes all variables"})
    fig.suptitle("Recorded action trajectories re-rendered; target is full state, not just the marked cell")
    save(fig, "recorded_worlds")
    write_json(out / "render_manifest.json", render_manifest)
    lines = [f"# Frontier v1.1 Stage {stage}", "", f"Source: `{summary['git_head']}`", "",
             f"Completed runs: {len(loaded)}. Candidate occurrences: {len(flat)}. Distinct-task evaluations: {task_count}.", "",
             "| Condition | Final D (seed order) | B80 (null=censored) | Final success |", "|---|---|---|---|"]
    for cond, r in summary["conditions"].items():
        lines.append(f"| {cond} | {r['final_D']} | {r['final_B80']} | {r['final_success']} |")
    lines += ["", "Human-defined: language, sampling prior, generic edits and evaluation protocol.",
              "Automatic: concrete worlds, exploration, graph acquisition, evaluation and performance selection.",
              "Full-info categories are diagnostics, not causal upper bounds. Complexity plots are correlations.",
              "Different worlds have different task populations. No mutation-language learning or cross-world transfer is claimed.",
              "Stage 2 is the endpoint; no Stage 3 and no outcome-driven retuning."]
    (out / "summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    if enforce_gate:
        assert summary["stage1_gate_passed"], "Stage 1 gate failed; do not start Stage 2"
    return summary


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=int, choices=(1, 2), required=True)
    p.add_argument("--input", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--enforce-gate", action="store_true")
    a = p.parse_args()
    summarize(a.input, a.output, a.stage, a.enforce_gate)
