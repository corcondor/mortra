"""Preregistered task holdout for the 24 archived Frontier v1.1 final worlds."""
import argparse
from collections import Counter, defaultdict
import copy
import hashlib
import json
from pathlib import Path
import pickle
import random
import statistics
import time
from types import FunctionType

from experiments.game_frontier_v1 import runner as io
from experiments.game_frontier_v1.player import fingerprint
from experiments.game_frontier_v11 import measurement as frozen
from experiments.game_frontier_v11.runner import sources
from experiments.game_frontier_v11.world import Engine, canonical, distances, game_hash, oracle

SOURCE_COMMIT = "c0f9f7b2c55d01bdb300b1ebb060f55b6c4d0902"
SOURCE_RUN = 36080469660
TASK_SEED_ROOT = 2026092501
CONDITIONS = ("mortra", "random", "size_only")
SEEDS = (201, 302, 403, 504, 605, 706, 807, 908)
CONFIG = {
    "protocol": "frontier-v11-fixed-world-holdout-v1", "source_commit": SOURCE_COMMIT,
    "source_run": SOURCE_RUN, "task_seed_root": TASK_SEED_ROOT,
    "seeds": list(SEEDS), "conditions": list(CONDITIONS), "requested_holdout_tasks": 500,
    "checkpoints": [2**i for i in range(14)], "horizon": 2048, "oracle_cap": 250000,
    "task_seed_derivation": "derive(root, world_seed, game_hash, 'holdout-tasks'); no condition argument",
    "exclusion": "all same-genome task pairs in archived Stage 1/2 candidate and initial-pool evaluations",
    "sampling": "distance>=4, per-bin reservoir, 125 per bin then random redistribution; distinct pairs only",
    "shortage": "enumerate all remaining eligible pairs when fewer than 500; retain actual denominator",
    "training": "execute frozen learn bytecode, original player seed and original selection evaluations",
    "secondary_evaluation": "same frozen learner; copy opaque-label registry to prevent training contamination",
    "reproduction_gate": "all original checkpoint fingerprints, K hashes, task results and solver outcomes equal",
    "metrics": "S_selection and S_holdout, delta at 8192, B80, D, distance-bin rates and common-bin standardized gap",
    "standardization": "selection-bin weights renormalized over bins observed in both sets; absent mass reported",
    "interpretation": "final-world within-world reuse only; no independent across-generation hardening test",
    "stop": "24 fixed-world audits and reporting; no generation, mutation, selection, transfer or outcome tuning",
}


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def pair(task):
    return tuple(task["start"]), tuple(task["target"])


def verified_sources():
    hashes = sources()
    for name, value in hashes.items():
        original = io.git("show", f"{SOURCE_COMMIT}:{name}") + "\n"
        assert hashlib.sha256(original.encode()).hexdigest() == value, name
    return hashes


def provenance():
    extra = [*sorted((io.ROOT / "experiments/game_frontier_v11_holdout").glob("*.py")),
             io.ROOT / "scripts/evaluate_autonomous_game_frontier_v11_holdout.py",
             io.ROOT / "tests/test_autonomous_game_frontier_v11_holdout.py",
             io.ROOT / ".github/workflows/autonomous-game-frontier-v11-holdout.yml",
             io.ROOT / "docs/research/AUTONOMOUS-GAME-FRONTIER-V11-HOLDOUT-20260925.md"]
    result = io.provenance(CONFIG, TASK_SEED_ROOT)
    result["frozen_source_hashes_lf"] = verified_sources()
    result["audit_source_hashes_lf"] = {str(p.relative_to(io.ROOT)).replace("\\", "/"):
        hashlib.sha256(p.read_text(encoding="utf-8").encode()).hexdigest() for p in extra}
    return result


def sample_holdout(graph, excluded, count, seed):
    """The archived sampler's strata/reservoir scheme, excluding prior task pairs."""
    states, edges, _ = graph
    rng = random.Random(seed)
    pools, totals, original_totals = [[] for _ in frozen.BINS], [0] * 4, [0] * 4
    for u in range(len(states)):
        for v, d in distances(edges, u).items():
            if d < 4:
                continue
            b = frozen.distance_bin(d)
            original_totals[b] += 1
            if (tuple(states[u]), tuple(states[v])) in excluded:
                continue
            totals[b] += 1
            row = {"start": list(states[u]), "target": list(states[v]), "distance": d, "bin": frozen.BINS[b]}
            if len(pools[b]) < count:
                pools[b].append(row)
            else:
                j = rng.randrange(totals[b])
                if j < count:
                    pools[b][j] = row
    for pool in pools:
        rng.shuffle(pool)
    tasks = []
    for pool in pools:
        take = min(count // 4, len(pool))
        tasks.extend(pool[:take])
        del pool[:take]
    remaining = [r for pool in pools for r in pool]
    rng.shuffle(remaining)
    tasks.extend(remaining[:count - len(tasks)])
    rng.shuffle(tasks)
    for i, task in enumerate(tasks):
        task["task_id"] = i
        task["rng_seed"] = io.derive(seed, i, "readout") % (2**32)
    assert len(tasks) == min(count, sum(totals))
    assert len(set(map(pair, tasks))) == len(tasks)
    assert not (set(map(pair, tasks)) & excluded)
    return tasks, {"available_by_bin": dict(zip(frozen.BINS, totals)),
                   "original_by_bin": dict(zip(frozen.BINS, original_totals)),
                   "sampled_by_bin": dict(Counter(t["bin"] for t in tasks)),
                   "requested": count, "actual": len(tasks), "exhaustive": len(tasks) == sum(totals)}


def prepare(input_dir, output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    prov = provenance()
    io.write_json(out / "source_snapshot.json", prov)
    io.write_json(out / "config.json", CONFIG)
    excluded, finals, input_files = defaultdict(set), [], {}
    seen = set()
    with (out / "run.log").open("x", encoding="utf-8", buffering=1) as log:
        def emit(message):
            print(message, flush=True)
            log.write(message + "\n")
        for p in sorted(Path(input_dir).rglob("results.json")):
            run = json.loads(p.read_text(encoding="utf-8"))
            assert run["status"] == "COMPLETED" and run["stage"] in (1, 2)
            assert run["provenance"]["git_head"] == SOURCE_COMMIT
            assert int(run["provenance"]["github_run_id"]) == SOURCE_RUN
            assert run["provenance"]["source_hashes_lf"] == prov["frozen_source_hashes_lf"]
            assert (run["stage"], run["seed"], run["condition"]) not in seen
            seen.add((run["stage"], run["seed"], run["condition"]))
            input_files[str(p.relative_to(input_dir))] = file_digest(p)
            for r in run["candidates"]:
                excluded[r["game_hash"]].update(map(pair, r["tasks"]))
            if run["stage"] == 2:
                final = run["frontier"][-1]
                gp = p.parent / "games" / final["game_hash"] / "genome.json"
                genome = json.loads(gp.read_text(encoding="utf-8"))
                assert game_hash(genome) == final["game_hash"]
                assert len(final["tasks"]) == 100 and digest(final["tasks"]) == final["tasks_sha256"]
                finals.append({"seed": run["seed"], "condition": run["condition"], "genome": genome,
                               "archived_final": final, "original_result_sha256": file_digest(p)})
            del run
        for p in sorted(Path(input_dir).glob("**/initial_pool/candidate_*.json")):
            item = json.loads(p.read_text(encoding="utf-8"))
            r = item["prepared"]
            excluded[r["game_hash"]].update(map(pair, r["tasks"]))
            input_files[str(p.relative_to(input_dir))] = file_digest(p)
        expected = {(2, s, c) for s in SEEDS for c in CONDITIONS} | {(1, s, c) for s in SEEDS[:3] for c in CONDITIONS}
        assert seen == expected and len(finals) == 24
        io.write_json(out / "input_artifact_hashes.json", input_files)
        manifest = {"status": "FROZEN_BEFORE_PLAYER_EXECUTION", "config": CONFIG, "cases": []}
        for item in finals:
            seed, condition, final = item["seed"], item["condition"], item["archived_final"]
            gh = final["game_hash"]
            task_seed = io.derive(TASK_SEED_ROOT, seed, gh, "holdout-tasks")
            stats, graph = oracle(Engine(item["genome"]), CONFIG["oracle_cap"])
            assert stats == final["oracle"] and graph is not None
            tasks, population = sample_holdout(graph, excluded[gh], CONFIG["requested_holdout_tasks"], task_seed)
            assert population["original_by_bin"] == final["pair_population_by_bin"]
            bundle = {**item, "holdout_tasks": tasks, "holdout_task_seed": task_seed,
                      "holdout_tasks_sha256": digest(tasks), "population": population,
                      "excluded_pairs": [[list(a), list(b)] for a, b in sorted(excluded[gh])],
                      "player_seed": io.derive(seed, gh, "player"), "source_run": SOURCE_RUN,
                      "source_commit": SOURCE_COMMIT, "config_hash": digest(CONFIG)}
            name = f"{seed}_{condition}.json"
            io.write_json(out / "cases" / name, bundle)
            manifest["cases"].append({"seed": seed, "condition": condition, "file": name,
                "bundle_sha256": file_digest(out / "cases" / name), "game_hash": gh,
                "holdout_task_seed": task_seed, "population": population,
                "excluded_pair_count": len(excluded[gh]), "holdout_tasks_sha256": digest(tasks)})
            emit(f"FROZEN seed={seed} condition={condition} tasks={len(tasks)} excluded={len(excluded[gh])}")
        io.write_json(out / "manifest.json", manifest)
        io.write_json(out / "rng_seeds.json", [{k: c[k] for k in ("seed", "condition", "holdout_task_seed")} for c in manifest["cases"]])
        assert provenance()["frozen_source_hashes_lf"] == prov["frozen_source_hashes_lf"]
        emit("ALL 24 TASK SETS FROZEN; NO PLAYER EVALUATION HAS RUN")


def reproduce_evaluation(actual, expected):
    keys = ("success_rate", "successes", "tasks", "median_success_steps", "task_results",
            "success_by_distance_bin", "K_sha256", "K_bytes", "K_nonzero", "learner_fingerprint",
            "graph_reuse_verified", "evaluation_updates", "q", "psi_cutoff", "solver_calls")
    for key in keys:
        assert actual[key] == expected[key], f"archived selection reproduction mismatch: {key}"


def paired_learning(bundle, emit=lambda _: None):
    final, holdout = bundle["archived_final"], bundle["holdout_tasks"]
    archived = final["learning"]
    assert [r["budget"] for r in archived] == CONFIG["checkpoints"]
    extra = []
    def paired_evaluation(learner, engine, labels, tasks, horizon):
        index = len(extra)
        selection = frozen.evaluate_tasks(learner, engine, labels, tasks, horizon)
        reproduce_evaluation(selection, archived[index]["evaluation"])
        before, label_bytes = fingerprint(learner), pickle.dumps(labels, protocol=5)
        # Evaluation can allocate new opaque labels. Never let those allocations
        # alter the frozen training stream's subsequent label assignment order.
        test = frozen.evaluate_tasks(learner, engine, copy.deepcopy(labels), holdout, horizon) if holdout else None
        assert fingerprint(learner) == before and pickle.dumps(labels, protocol=5) == label_bytes
        if test:
            assert test["K_sha256"] == selection["K_sha256"]
            assert test["learner_fingerprint"] == selection["learner_fingerprint"]
        extra.append({"budget": archived[index]["budget"], "selection": selection, "holdout": test,
                      "archived_reproduction_verified": True, "same_model_verified": True})
        emit(f"B={archived[index]['budget']} selection={selection['success_rate']} holdout={test['success_rate'] if test else None}")
        return selection
    namespace = dict(frozen.learn.__globals__)
    namespace["evaluate_tasks"] = paired_evaluation
    learn = FunctionType(frozen.learn.__code__, namespace, frozen.learn.__name__, frozen.learn.__defaults__)
    rows = learn(Engine(bundle["genome"]), final["tasks"], CONFIG["checkpoints"], CONFIG["horizon"],
                 bundle["player_seed"], final["oracle"])
    for row, old in zip(rows, archived):
        for key in ("budget", "learned_states", "learned_transitions", "state_coverage", "edge_coverage", "learner_serialized_bytes"):
            assert row[key] == old[key], key
    return extra, rows


def standardized(selection, holdout):
    a, b = selection["success_by_distance_bin"], holdout["success_by_distance_bin"]
    common = [k for k in frozen.BINS if a[k]["tasks"] and b[k]["tasks"]]
    mass = sum(a[k]["tasks"] for k in common)
    if not mass:
        return {"common_bins": [], "selection_mass_covered": 0, "delta": None}
    sa = sum(a[k]["successes"] for k in common) / mass
    sb = sum(a[k]["tasks"] * b[k]["successes"] / b[k]["tasks"] for k in common) / mass
    return {"common_bins": common, "selection_mass_covered": mass / selection["tasks"],
            "selection": sa, "holdout": sb, "delta": sa - sb}


def run_seed(frozen_dir, output, seed):
    assert seed in SEEDS
    root, out = Path(frozen_dir), Path(output)
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["status"] == "FROZEN_BEFORE_PLAYER_EXECUTION" and manifest["config"] == CONFIG
    prov = provenance()
    io.write_json(out / "source_snapshot.json", prov)
    io.write_json(out / "config.json", CONFIG)
    io.write_json(out / "manifest_reference.json", {"sha256": file_digest(root / "manifest.json"), "source_run": SOURCE_RUN})
    started = time.perf_counter()
    with (out / "run.log").open("x", encoding="utf-8", buffering=1) as log:
        def emit(message):
            print(message, flush=True)
            log.write(message + "\n")
        try:
            cases = [c for c in manifest["cases"] if c["seed"] == seed]
            assert {c["condition"] for c in cases} == set(CONDITIONS)
            for case in cases:
                path = root / "cases" / case["file"]
                assert file_digest(path) == case["bundle_sha256"]
                bundle = json.loads(path.read_text(encoding="utf-8"))
                assert game_hash(bundle["genome"]) == case["game_hash"]
                assert digest(bundle["holdout_tasks"]) == case["holdout_tasks_sha256"]
                assert not (set(map(pair, bundle["holdout_tasks"])) & {(tuple(a), tuple(b)) for a, b in bundle["excluded_pairs"]})
                emit(f"START {seed} {case['condition']} fixed_game={case['game_hash']}")
                cpu = time.process_time()
                paired, learned = paired_learning(bundle, emit)
                selection = frozen.curve_metrics([{ "budget": r["budget"], "evaluation": r["selection"]} for r in paired])
                holdout = frozen.curve_metrics([{ "budget": r["budget"], "evaluation": r["holdout"]} for r in paired]) if bundle["holdout_tasks"] else None
                result = {"status": "COMPLETED" if holdout else "NO_UNUSED_TASKS", "seed": seed, "condition": case["condition"],
                    "game_hash": case["game_hash"], "provenance": prov, "source_bundle_sha256": case["bundle_sha256"],
                    "population": case["population"], "holdout_tasks_sha256": case["holdout_tasks_sha256"],
                    "paired": paired, "selection_metrics": selection, "holdout_metrics": holdout,
                    "delta_success": selection["final_success"] - holdout["final_success"] if holdout else None,
                    "common_bin_standardization": standardized(paired[-1]["selection"], paired[-1]["holdout"]) if holdout else None,
                    "cpu_seconds": time.process_time() - cpu, "training_cpu_seconds": learned[-1]["training_cpu_seconds"],
                    "peak_rss_bytes": io.peak_rss(), "all_original_checkpoints_reproduced": True,
                    "holdout_learning_updates": 0, "genome_unchanged": True}
                io.write_json(out / f"{case['condition']}.json", result)
                emit(f"COMPLETE {case['condition']} delta={result['delta_success']}")
            assert verified_sources() == prov["frozen_source_hashes_lf"]
            io.write_json(out / "completed.json", {"status": "COMPLETED", "seed": seed,
                "wall_seconds": time.perf_counter() - started, "peak_rss_bytes": io.peak_rss()})
        except BaseException as exc:
            io.write_json(out / "incomplete.json", {"status": "RUN_NOT_COMPLETED", "error": repr(exc),
                "wall_seconds": time.perf_counter() - started})
            raise


def summarize(input_dir, frozen_dir, output):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle
    root, out = Path(frozen_dir), Path(output)
    out.mkdir(parents=True, exist_ok=False)
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    results = []
    for cond in CONDITIONS:
        results += [json.loads(p.read_text(encoding="utf-8")) for p in sorted(Path(input_dir).rglob(f"{cond}.json"))]
    assert {(r["seed"], r["condition"]) for r in results} == {(s, c) for s in SEEDS for c in CONDITIONS}
    assert len(results) == 24
    flat, curves, replays = [], [], []
    for r in results:
        c = next(c for c in manifest["cases"] if (c["seed"], c["condition"]) == (r["seed"], r["condition"]))
        assert r["source_bundle_sha256"] == c["bundle_sha256"] and r["all_original_checkpoints_reproduced"]
        bundle = json.loads((root / "cases" / c["file"]).read_text(encoding="utf-8"))
        engine = Engine(bundle["genome"])
        for step in r["paired"]:
            assert step["same_model_verified"] and step["archived_reproduction_verified"]
            for name, tasks in (("selection", bundle["archived_final"]["tasks"]), ("holdout", bundle["holdout_tasks"])):
                e = step[name]
                if not e:
                    continue
                assert e["successes"] == sum(x["success"] for x in e["task_results"])
                assert e["success_rate"] == e["successes"] / len(tasks)
                trace = e["task_results"][0]["recorded_trajectory"]
                assert digest(trace) == e["task_results"][0]["trajectory_sha256"]
                state = tuple(tasks[0]["start"])
                assert list(state) == trace["states"][0]
                for a, expected in zip(trace["actions"], trace["states"][1:]):
                    state = engine.step(state, a)
                    assert list(state) == expected
                assert len(trace["states"]) == len(trace["actions"]) + 1
                assert (list(state) == tasks[0]["target"]) == e["task_results"][0]["success"]
                replays.append({"seed": r["seed"], "condition": r["condition"], "set": name,
                    "budget": step["budget"], "task": 0, "trajectory_sha256": digest(trace)})
            curves.append({"seed": r["seed"], "condition": r["condition"], "budget": step["budget"],
                "selection": step["selection"]["success_rate"], "holdout": step["holdout"]["success_rate"] if step["holdout"] else None})
        sel, test = r["selection_metrics"], r["holdout_metrics"]
        flat.append({"seed": r["seed"], "condition": r["condition"], "game_hash": r["game_hash"],
            "selection_success": sel["final_success"], "holdout_success": test["final_success"] if test else None,
            "selection_B80": sel["B80"], "holdout_B80": test["B80"] if test else None,
            "selection_D": sel["D"], "holdout_D": test["D"] if test else None,
            "delta": r["delta_success"], "holdout_tasks": r["population"]["actual"],
            "standardized_delta": r["common_bin_standardization"]["delta"] if test else None,
            "standardized_selection_mass": r["common_bin_standardization"]["selection_mass_covered"] if test else None})
    aggregate = {}
    for cond in CONDITIONS:
        rows = [r for r in results if r["condition"] == cond]
        measured = [r for r in rows if r["holdout_metrics"]]
        tasks = sum(r["paired"][-1]["holdout"]["tasks"] for r in measured)
        succ = sum(r["paired"][-1]["holdout"]["successes"] for r in measured)
        aggregate[cond] = {"worlds": len(rows), "measured_worlds": len(measured),
            "holdout_tasks": tasks, "holdout_successes": succ, "pooled_holdout_success": succ / tasks if tasks else None,
            "macro_holdout_success": statistics.mean(r["holdout_metrics"]["final_success"] for r in measured) if measured else None,
            "macro_selection_success": statistics.mean(r["selection_metrics"]["final_success"] for r in rows),
            "macro_delta": statistics.mean(r["delta_success"] for r in measured) if measured else None,
            "holdout_at_least_80_worlds": sum(r["holdout_metrics"]["final_success"] >= .8 for r in measured),
            "same_B80_worlds": sum(r["holdout_metrics"]["B80"] == r["selection_metrics"]["B80"] for r in measured),
            "worlds_with_shortage": sum(r["population"]["actual"] < 500 for r in rows),
            "cpu_seconds": sum(r["cpu_seconds"] for r in rows), "peak_rss_bytes": max(r["peak_rss_bytes"] for r in rows)}
    summary = {"status": "COMPLETED", "source_run": SOURCE_RUN, "audit_heads": sorted({r["provenance"]["git_head"] for r in results}),
        "audit_runs": sorted({r["provenance"]["github_run_id"] for r in results}), "worlds": len(results),
        "original_checkpoints_reproduced": sum(len(r["paired"]) for r in results),
        "verified_task_zero_replays": len(replays), "aggregate": aggregate, "world_results": flat}
    io.write_json(out / "metrics.json", summary)
    io.csv_write(out / "comparison.csv", flat)
    io.csv_write(out / "learning_curves.csv", curves)
    io.write_json(out / "replay_checks.json", replays)
    colors = {"mortra": "#167b63", "random": "#b95350", "size_only": "#4774b3"}
    fig, axs = plt.subplots(1, 3, figsize=(14, 4), constrained_layout=True)
    for ax, cond in zip(axs, CONDITIONS):
        for seed in SEEDS:
            rows = [r for r in curves if (r["seed"], r["condition"]) == (seed, cond)]
            ax.plot([r["budget"] for r in rows], [r["selection"] for r in rows], "--", alpha=.4, color=colors[cond])
            ax.plot([r["budget"] for r in rows], [r["holdout"] for r in rows], alpha=.6, color=colors[cond])
        ax.set(title=cond, xlabel="Interactions (log2)", ylabel="Success", ylim=(-.03, 1.03))
        ax.set_xscale("log", base=2)
    fig.suptitle("Fixed final worlds: selection dashed, unused tasks solid; eight seeds per panel")
    fig.savefig(out / "selection_vs_holdout.png", dpi=140)
    plt.close(fig)
    fig, axs = plt.subplots(2, 3, figsize=(14, 8), constrained_layout=True)
    for col, cond in enumerate(CONDITIONS):
        rows = [r for r in flat if r["condition"] == cond]
        axs[0, col].bar([str(r["seed"]) for r in rows], [r["delta"] if r["delta"] is not None else float("nan") for r in rows], color=colors[cond])
        axs[0, col].axhline(0, color="black", linewidth=.7)
        axs[0, col].set(title=cond, ylabel="Selection minus holdout success")
        for offset, field, label in ((-.18, "selection_B80", "Selection"), (.18, "holdout_B80", "Holdout")):
            axs[1, col].bar([i + offset for i in range(len(rows))], [r[field] if r[field] is not None else 16384 for r in rows], width=.35, label=label)
        axs[1, col].set_xticks(range(len(rows)), [str(r["seed"]) for r in rows])
        axs[1, col].set_yscale("log", base=2)
        axs[1, col].set(yticks=[256, 1024, 4096, 8192, 16384], yticklabels=["256", "1024", "4096", "8192", ">8192"], ylabel="B80 (last level is censored)")
        axs[1, col].legend()
    fig.savefig(out / "gap_and_B80.png", dpi=140)
    plt.close(fig)
    fig, axs = plt.subplots(1, 3, figsize=(12, 4), constrained_layout=True)
    for ax, cond in zip(axs, CONDITIONS):
        r = next(r for r in results if (r["seed"], r["condition"]) == (201, cond))
        c = next(c for c in manifest["cases"] if (c["seed"], c["condition"]) == (201, cond))
        b = json.loads((root / "cases" / c["file"]).read_text())
        task = b["holdout_tasks"][0]
        result = r["paired"][-1]["holdout"]["task_results"][0]
        trace, g = result["recorded_trajectory"], b["genome"]
        for x, y in g["walls"]:
            ax.add_patch(Rectangle((x, y), 1, 1, facecolor="#555555"))
        ax.plot([s[0] + .5 for s in trace["states"]], [s[1] + .5 for s in trace["states"]], color=colors[cond])
        ax.plot(task["start"][0] + .5, task["start"][1] + .5, "o", color="#2463af")
        ax.plot(task["target"][0] + .5, task["target"][1] + .5, "*", color="#bf7219", markersize=12)
        ax.set(xlim=(0, g["domains"][0]), ylim=(g["domains"][1], 0), aspect="equal", xticks=[], yticks=[],
            title=f"{cond}, seed 201, holdout task 0\nsuccess={result['success']}, actions={result['actual_actions']}")
    fig.suptitle("Recorded actions re-rendered; spatial projection; budget 8192; no success-based selection")
    fig.savefig(out / "recorded_holdout.png", dpi=140)
    plt.close(fig)
    print(json.dumps(summary, indent=2), flush=True)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("prepare", "run", "summarize"))
    p.add_argument("--input", type=Path)
    p.add_argument("--frozen", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seed", type=int)
    args = p.parse_args()
    if args.mode == "prepare":
        prepare(args.input, args.output)
    elif args.mode == "run":
        run_seed(args.frozen, args.output, args.seed)
    else:
        summarize(args.input, args.frozen, args.output)
