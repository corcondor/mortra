"""Read-only presentation of frozen run artifacts; never generate a game."""
import argparse
import ast
import csv
import hashlib
import json
from pathlib import Path
import statistics
import sys
from collections import Counter
import shutil

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from experiments.self_design_v2_integration.adapter import load_v2
from experiments.self_design_v2_integration.verify import write


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    module = load_v2()
    tree = ast.parse((ROOT / "scripts/evaluate_autonomous_game_design_loop.py").read_text(encoding="utf-8"))
    renderer = next(n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef) and n.name == "render_game_map")
    namespace = dict(vars(module))
    exec(compile(ast.Module(body=[renderer], type_ignores=[]), "<original-v2-renderer-only>", "exec"), namespace)
    render = namespace["render_game_map"]
    plt = module.plt
    histories, data, resources, files = {}, {}, {}, {}
    iterations, sources, verification = [], [], Counter()
    for path in args.artifacts.rglob("completed.json"):
        completed = read(path)
        if completed.get("stage") != "full":
            continue
        source = read(path.parent / "source_snapshot.json")
        assert source["head"] == "5f8b36744a29327928c87d6db888f2f045dbea79"
        assert source["github_run_id"] == "36273640831" and source["attempt"] == "1"
        assert all(s["identical_lf"] for s in source["sources"])
        sources.append({"seed": completed["seed"], "method": completed["method"], **source})
        for control in ("targeted", "random_mutation"):
            key = (completed["seed"], completed["method"], control)
            assert key not in data
            directory = path.parent / control
            history = read(directory / "history.json")
            summary = read(directory / "summary.json")
            assert len(history) == 21 and len(summary["evaluations"]) == 21
            assert read(directory / "game_final.json") == history[-1]["game"]
            assert read(directory / "game_initial.json") == history[0]["game"]
            assert summary["final"] == history[-1]["metrics"]
            for i, entry in enumerate(history):
                audit = summary["evaluations"][i]
                assert audit["oracle_calls"] == audit["goal_queries_during_training"] == 0
                assert audit["training_steps"] == 2500
                assert audit["replay_all_recorded_actions_verified"]
                verification["evaluations"] += 1
                verification["recorded_training_actions"] += audit["training_steps"]
                assert entry["critique"] == module.critique_game(entry["metrics"])
                if i:
                    previous = history[i - 1]
                    accepted, reason = module.decide_acceptance(previous["metrics"], entry["candidate_metrics"], previous["critique"])
                    assert (accepted, reason) == (entry["accepted"], entry["decision_reason"])
                    assert entry["game"] == (entry["candidate_game"] if accepted else previous["game"])
                    assert entry["metrics"] == (entry["candidate_metrics"] if accepted else previous["metrics"])
                    verification["rechecked_accept_reject_decisions"] += 1
                iterations.append({"seed": key[0], "method": key[1], "control": control,
                    "iteration": i, "accepted": entry["accepted"],
                    "critique_before": history[i - 1]["critique"] if i else "INITIAL",
                    "critique_after": entry["critique"], "mutation": entry["mutation"],
                    "decision_reason": entry.get("decision_reason", "Initial G0"),
                    "current_success_rate": entry["metrics"]["success_rate"],
                    "current_strategic_gap": entry["metrics"]["strategic_gap"],
                    "candidate_success_rate": entry.get("candidate_metrics", entry["metrics"])["success_rate"],
                    "candidate_strategic_gap": entry.get("candidate_metrics", entry["metrics"])["strategic_gap"]})
            accepted_index = max(i for i, h in enumerate(history) if h["accepted"])
            final_model = summary["evaluations"][accepted_index]
            assert final_model["known_states"] == history[-1]["metrics"]["state_coverage"]
            row = {"seed": key[0], "method": key[1], "control": key[2],
                   "accepted_edits": summary["accepted_edits"], "final_model_evaluation_index": accepted_index,
                   "final_known_state_action_pairs": final_model["known_state_action_pairs"],
                   "initial_known_states": summary["evaluations"][0]["known_states"],
                   "initial_known_state_action_pairs": summary["evaluations"][0]["known_state_action_pairs"],
                   "training_cpu_seconds": sum(e["training_cpu_seconds"] for e in summary["evaluations"]),
                   "evaluation_cpu_seconds": sum(e["total_evaluation_cpu_seconds"] for e in summary["evaluations"]),
                   "virtual_field_solve_cpu_seconds": sum(e["virtual_factorization_and_solve_cpu_seconds"] for e in summary["evaluations"]),
                   **{k: v for k, v in history[-1]["metrics"].items() if isinstance(v, (int, float))}}
            histories[key], data[key] = history, row
            resources[key] = read(directory / "resources.json")
            for name in ("summary.json", "history.json", "game_initial.json", "game_final.json", "resources.json"):
                p = directory / name
                files[p.relative_to(args.artifacts).as_posix()] = hashlib.sha256(p.read_bytes()).hexdigest()
            archive = args.output / "saved_games" / str(key[0]) / key[1] / control
            archive.mkdir(parents=True, exist_ok=False)
            for name in ("history.json", "game_initial.json", "game_final.json", "resources.json"):
                shutil.copyfile(directory / name, archive / name)
    seeds = list(range(79020000, 79020008))
    methods = ("structural", "frontier_t0", "virtual_frontier")
    controls = ("targeted", "random_mutation")
    assert set(data) == {(s, m, c) for s in seeds for m in methods for c in controls}
    for seed in seeds:
        initial = histories[seed, "structural", "targeted"][0]["game"]
        assert all(histories[seed, m, c][0]["game"] == initial for m in methods for c in controls)
        for method in methods:
            assert histories[seed, method, "targeted"][0] == histories[seed, method, "random_mutation"][0]
    overall = []
    for control in controls:
        for method in methods:
            selected = [data[s, method, control] for s in seeds]
            overall.append({"method": method, "control": control, "worlds": len(selected),
                            "successes": sum(r["successes"] for r in selected),
                            "random_successes": sum(r["random_successes"] for r in selected),
                            "trials": sum(r["trials"] for r in selected),
                            "success_rate": statistics.mean(r["success_rate"] for r in selected),
                            "random_success_rate": statistics.mean(r["random_success_rate"] for r in selected),
                            "strategic_gap": statistics.mean(r["strategic_gap"] for r in selected),
                            "initial_success_rate": statistics.mean(histories[s, method, control][0]["metrics"]["success_rate"] for s in seeds),
                            "initial_strategic_gap": statistics.mean(histories[s, method, control][0]["metrics"]["strategic_gap"] for s in seeds),
                            "mean_gap_change": statistics.mean(histories[s, method, control][-1]["metrics"]["strategic_gap"] - histories[s, method, control][0]["metrics"]["strategic_gap"] for s in seeds),
                            "mean_actions_to_goal": statistics.mean(r["mean_actions_to_goal"] for r in selected),
                            "accepted_edits": sum(r["accepted_edits"] for r in selected),
                            "attempted_edits": 160,
                            "mean_known_states": statistics.mean(r["state_coverage"] for r in selected),
                            "mean_known_pairs": statistics.mean(r["final_known_state_action_pairs"] for r in selected),
                            "mean_initial_known_states": statistics.mean(r["initial_known_states"] for r in selected),
                            "mean_initial_known_pairs": statistics.mean(r["initial_known_state_action_pairs"] for r in selected),
                            "training_cpu_seconds": sum(r["training_cpu_seconds"] for r in selected),
                            "evaluation_cpu_seconds": sum(r["evaluation_cpu_seconds"] for r in selected),
                            "virtual_field_solve_cpu_seconds": sum(r["virtual_field_solve_cpu_seconds"] for r in selected),
                            "total_cpu_seconds": sum(resources[s, method, control]["cpu_seconds"] for s in seeds),
                            "max_process_memory_bytes": max(resources[s, method, control]["peak_process_memory_bytes"] for s in seeds)})
    write(args.output / "headline.json", overall)
    write(args.output / "source_snapshots.json", sources)
    write(args.output / "report_audit.json", {"passed": True, **dict(verification),
        "full_jobs": len(sources), "series": len(histories),
        "no_policy_or_game_generation_in_postprocessing": True})
    for name, values in (("iteration_decisions.csv", iterations),):
        with (args.output / name).open("x", encoding="utf-8", newline="") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(values[0]))
            writer.writeheader()
            writer.writerows(values)
    control_comparison = []
    from experiments.self_design_v2_integration.summarize import METRICS
    for method in methods:
        for metric in (*METRICS, "accepted_edits"):
            differences = [{"seed": s, "targeted_minus_random_mutation": data[s, method, "targeted"][metric] - data[s, method, "random_mutation"][metric]} for s in seeds]
            values = [r["targeted_minus_random_mutation"] for r in differences]
            control_comparison.append({"method": method, "metric": metric, "mean_difference": statistics.mean(values),
                "median_difference": statistics.median(values), "positive_seeds": sum(v > 0 for v in values),
                "equal_seeds": sum(v == 0 for v in values), "negative_seeds": sum(v < 0 for v in values), "raw": differences})
    write(args.output / "designer_control_comparisons.json", control_comparison)
    write(args.output / "input_hashes.json", files)
    write(args.output / "column_audit.json", {
        "original_column": "final_exploration_known_pairs",
        "original_semantics": "last evaluated candidate, which may have been rejected",
        "report_column": "final_known_state_action_pairs",
        "report_semantics": "evaluation at last accepted iteration, including iteration zero",
        "impact": "reporting-only label/lookup correction; no changes to game, policy, acceptance or V2 metrics; original artifacts preserved"})
    rows = [data[k] for k in sorted(data)]
    with (args.output / "final_per_seed.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    for seed in seeds:
        fig, axes = plt.subplots(2, 3, figsize=(15, 10))
        for row, control in enumerate(controls):
            for column, method in enumerate(methods):
                history = histories[seed, method, control]
                saved = history[-1]["game"]
                game = module.MicroGame()
                for name, value in saved.items():
                    if name in ("walls", "hazards"):
                        value = set(map(tuple, value))
                    elif isinstance(value, list):
                        value = tuple(value)
                    setattr(game, name, value)
                replay = history[-1]["metrics"]["mortra_replay"]
                coords = [(s[0], s[1]) for s in replay["states"]]
                render(axes[row, column], game,
                       f"{method} / {control}\nseed {seed}; trial 0; reached={replay['reached_goal']}", [coords])
        fig.suptitle("Saved final games and recorded trial-0 paths, redrawn | run 36273640831", fontsize=12)
        fig.tight_layout()
        fig.savefig(args.output / f"games_{seed}.png", dpi=110)
        plt.close(fig)
    colors = {"structural": "#2864A1", "frontier_t0": "#CE5A26", "virtual_frontier": "#168377"}
    fig, axes = plt.subplots(2, 3, figsize=(15, 8))
    for row, control in enumerate(controls):
        for col, metric in enumerate(("success_rate", "strategic_gap", "state_coverage")):
            for method in methods:
                values = [statistics.mean(histories[s, method, control][i]["metrics"][metric] for s in seeds) for i in range(21)]
                axes[row, col].plot(range(21), values, label=method, color=colors[method])
            axes[row, col].set_title(f"{control}: {metric}")
            axes[row, col].set_xlabel("Design iteration")
            axes[row, col].grid(alpha=.2)
            axes[row, col].legend(fontsize=8)
    fig.suptitle("Means over all 8 fixed creation seeds; current accepted game at each iteration")
    fig.tight_layout()
    fig.savefig(args.output / "evolution_comparison.png", dpi=140)
    plt.close(fig)
    print(json.dumps(overall, indent=2))


if __name__ == "__main__":
    main()
