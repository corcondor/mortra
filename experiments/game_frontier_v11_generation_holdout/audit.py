"""Holdout curves for every archived MORTRA-performance frontier generation."""
import argparse
from collections import Counter, defaultdict
from fractions import Fraction
import hashlib
import json
from pathlib import Path
import statistics
import time

from experiments.game_frontier_v11_holdout import audit as previous
from experiments.game_frontier_v11 import measurement as frozen
from experiments.game_frontier_v11.world import Engine, game_hash, oracle

io = previous.io
SEEDS = previous.SEEDS
SOURCE_RUN = previous.SOURCE_RUN
SOURCE_COMMIT = previous.SOURCE_COMMIT
PRIOR_HOLDOUT_RUN = 36085588461
TASK_SEED_ROOT = 2026092502
CONFIG = {
    "protocol": "frontier-v11-all-generations-holdout-v1",
    "source_run": SOURCE_RUN, "source_commit": SOURCE_COMMIT,
    "prior_holdout_run": PRIOR_HOLDOUT_RUN, "task_seed_root": TASK_SEED_ROOT,
    "seeds": list(SEEDS), "condition": "mortra", "generations": list(range(11)),
    "requested_holdout_tasks": 500, "checkpoints": [2**i for i in range(14)],
    "horizon": 2048, "oracle_cap": 250000, "q": .90, "cutoff": 1e-7,
    "exclusions": "all same-genome selection pairs from Stage 1/2 candidates and initial pool, plus previous final-world holdout",
    "tasks": "derive(root, seed, game_hash, 'generation-holdout'); distance>=4; original stratified reservoir sampling",
    "shortage": "census of all unused eligible pairs, no replacement or synthetic padding",
    "unchanged_world": "one task set and one audit per (seed, game_hash); reuse identical result across retained generations",
    "training": "frozen learn bytecode, original seed, original selection evaluation, exact archived reproduction gate",
    "holdout_isolation": "evaluate same learner with copied opaque-label registry; zero learning updates",
    "full_information": "same holdout tasks and frozen core; separate complete graph, never supplied to training",
    "D": "trapezoidal integral of 1-S over log2 budget; rational counts for trend sign",
    "Bx": "first measured success>=x%; null means not reached by 8192, not infinite difficulty",
    "classification": "full<.8: REASONER_LIMITED; otherwise learned<.8: EXPLORATION_LIMITED; otherwise LEARNED_SUCCESS",
    "capacity_control": "also report D on the subset solved by full-information core, and per-task learned/full contingency",
    "interpretation": "descriptive within archived performance arm; no new random-selection causal comparison",
    "stop": "audit fixed worlds only, no generation/mutation/selection/player tuning",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def provenance():
    p = previous.provenance()
    p["generation_audit_config"] = CONFIG
    files = [*sorted((io.ROOT / "experiments/game_frontier_v11_generation_holdout").glob("*.py")),
             io.ROOT / "scripts/evaluate_autonomous_game_frontier_v11_generation_holdout.py",
             io.ROOT / "tests/test_autonomous_game_frontier_v11_generation_holdout.py",
             io.ROOT / ".github/workflows/autonomous-game-frontier-v11-generation-holdout.yml",
             io.ROOT / "docs/research/AUTONOMOUS-GAME-FRONTIER-V11-GENERATION-HOLDOUT-20260925.md"]
    p["generation_audit_sources_lf"] = {f.relative_to(io.ROOT).as_posix():
        hashlib.sha256(f.read_text(encoding="utf-8").encode()).hexdigest() for f in files}
    return p


def group_frontier(frontier):
    assert len(frontier) == 11
    groups = {}
    for generation, record in enumerate(frontier):
        key = record["game_hash"]
        if key in groups:
            assert groups[key]["record"] == record, "same genome has conflicting saved measurements"
            groups[key]["generations"].append(generation)
        else:
            groups[key] = {"record": record, "generations": [generation]}
    return groups


def prepare(input_dir, prior_dir, output):
    root, prior, out = Path(input_dir), Path(prior_dir), Path(output)
    out.mkdir(parents=True, exist_ok=False)
    prov = provenance()
    io.write_json(out / "source_snapshot.json", prov)
    io.write_json(out / "config.json", CONFIG)
    excluded, old_holdout = defaultdict(set), defaultdict(set)
    inputs, frontiers, seen = {}, [], set()
    for p in sorted(root.rglob("results.json")):
        r = read(p)
        assert r["status"] == "COMPLETED"
        assert r["provenance"]["git_head"] == SOURCE_COMMIT
        assert int(r["provenance"]["github_run_id"]) == SOURCE_RUN
        assert r["provenance"]["source_hashes_lf"] == prov["frozen_source_hashes_lf"]
        key = r["stage"], r["seed"], r["condition"]
        assert key not in seen
        seen.add(key)
        inputs[p.relative_to(root).as_posix()] = previous.file_digest(p)
        for c in r["candidates"]:
            excluded[c["game_hash"]].update(map(previous.pair, c["tasks"]))
        if r["stage"] == 2 and r["condition"] == "mortra":
            assert r["config"]["checkpoints"] == CONFIG["checkpoints"]
            assert r["config"]["horizon"] == CONFIG["horizon"]
            frontiers.append((p, r["seed"], group_frontier(r["frontier"])))
    expected = {(2, s, c) for s in SEEDS for c in previous.CONDITIONS} | {
        (1, s, c) for s in SEEDS[:3] for c in previous.CONDITIONS}
    assert seen == expected and {s for _, s, _ in frontiers} == set(SEEDS)
    for p in sorted(root.glob("**/initial_pool/candidate_*.json")):
        r = read(p)["prepared"]
        excluded[r["game_hash"]].update(map(previous.pair, r["tasks"]))
        inputs[p.relative_to(root).as_posix()] = previous.file_digest(p)
    old_manifest = read(prior / "manifest.json")
    assert old_manifest["config"] == previous.CONFIG
    assert len(old_manifest["cases"]) == 24
    for c in old_manifest["cases"]:
        p = prior / "cases" / c["file"]
        assert previous.file_digest(p) == c["bundle_sha256"]
        b = read(p)
        assert previous.digest(b["holdout_tasks"]) == c["holdout_tasks_sha256"]
        old_holdout[c["game_hash"]].update(map(previous.pair, b["holdout_tasks"]))
        inputs["prior_holdout/" + c["file"]] = previous.file_digest(p)
    io.write_json(out / "input_artifact_hashes.json", inputs)
    manifest = {"status": "FROZEN_BEFORE_PLAYER_EXECUTION", "config": CONFIG, "cases": [], "generation_map": []}
    with (out / "run.log").open("x", encoding="utf-8", buffering=1) as log:
        for p, seed, groups in frontiers:
            for gh, group in groups.items():
                record = group["record"]
                genome_path = p.parent / "games" / gh / "genome.json"
                genome = read(genome_path)
                assert game_hash(genome) == gh
                assert previous.digest(record["tasks"]) == record["tasks_sha256"]
                assert len(record["tasks"]) == 100
                blocked = excluded[gh] | old_holdout[gh]
                task_seed = io.derive(TASK_SEED_ROOT, seed, gh, "generation-holdout")
                stats, graph = oracle(Engine(genome), CONFIG["oracle_cap"])
                assert graph is not None and stats == record["oracle"]
                tasks, population = previous.sample_holdout(graph, blocked, CONFIG["requested_holdout_tasks"], task_seed)
                assert population["original_by_bin"] == record["pair_population_by_bin"]
                name = f"{seed}_{gh}.json"
                bundle = {"seed": seed, "condition": "mortra", "game_hash": gh, "genome": genome,
                    "generations": group["generations"], "archived_final": record,
                    "original_result_sha256": previous.file_digest(p), "genome_file_sha256": previous.file_digest(genome_path),
                    "holdout_tasks": tasks, "holdout_tasks_sha256": previous.digest(tasks), "population": population,
                    "holdout_task_seed": task_seed, "player_seed": io.derive(seed, gh, "player"),
                    "diagnostic_seed": io.derive(seed, gh, "diagnostic"),
                    "excluded_selection_pairs": [[list(a), list(b)] for a, b in sorted(excluded[gh])],
                    "excluded_previous_holdout_pairs": [[list(a), list(b)] for a, b in sorted(old_holdout[gh])],
                    "source_run": SOURCE_RUN, "source_commit": SOURCE_COMMIT, "config_hash": previous.digest(CONFIG)}
                io.write_json(out / "cases" / name, bundle)
                manifest["cases"].append({k: bundle[k] for k in ("seed", "game_hash", "generations", "population", "holdout_task_seed", "holdout_tasks_sha256")}
                    | {"file": name, "bundle_sha256": previous.file_digest(out / "cases" / name)})
                for generation in group["generations"]:
                    manifest["generation_map"].append({"seed": seed, "generation": generation, "game_hash": gh, "file": name})
                message = f"FROZEN seed={seed} generations={group['generations']} tasks={len(tasks)} hash={gh}"
                print(message, flush=True)
                log.write(message + "\n")
        assert len(manifest["generation_map"]) == 88
        io.write_json(out / "manifest.json", manifest)
        io.write_json(out / "rng_seeds.json", [{k: c[k] for k in ("seed", "game_hash", "holdout_task_seed")} for c in manifest["cases"]])
        assert previous.verified_sources() == prov["frozen_source_hashes_lf"]
        log.write("ALL TASK SETS FROZEN BEFORE ANY PLAYER EXECUTION\n")


def classification(learned, full):
    if learned is None or full is None:
        return "NO_UNUSED_TASKS"
    if full < .8:
        return "REASONER_LIMITED"
    return "EXPLORATION_LIMITED" if learned < .8 else "LEARNED_SUCCESS"


def curve(paired, key, indices=None):
    rows = []
    for p in paired:
        if p[key] is None:
            return None
        records = p[key]["task_results"]
        if indices is not None:
            records = [records[i] for i in indices]
        if not records:
            return None
        successes = sum(r["success"] for r in records)
        rows.append({"budget": p["budget"], "evaluation": {"success_rate": successes / len(records),
            "median_success_steps": statistics.median([r["actual_actions"] for r in records if r["success"]]) if successes else 0},
            "fraction": Fraction(successes, len(records))})
    result = frozen.curve_metrics(rows)
    # All checkpoints are adjacent powers of two, so D has an exact rational form.
    assert all(b["budget"] == 2 * a["budget"] for a, b in zip(rows, rows[1:]))
    exact = sum((2 - a["fraction"] - b["fraction"]) / 2 for a, b in zip(rows, rows[1:]))
    result["D_exact"] = str(exact)
    return result


def contingency(learned, full):
    assert len(learned["task_results"]) == len(full["task_results"])
    counts = Counter((bool(a["success"]), bool(b["success"])) for a, b in zip(learned["task_results"], full["task_results"]))
    return {"both_success": counts[True, True], "learned_failure_full_success": counts[False, True],
        "learned_success_full_failure": counts[True, False], "both_failure": counts[False, False]}


def run_seed(frozen_dir, output, seed):
    root, out = Path(frozen_dir), Path(output)
    out.mkdir(parents=True, exist_ok=False)
    manifest, prov = read(root / "manifest.json"), provenance()
    assert manifest["config"] == CONFIG and manifest["status"] == "FROZEN_BEFORE_PLAYER_EXECUTION"
    assert seed in SEEDS
    io.write_json(out / "source_snapshot.json", prov)
    io.write_json(out / "config.json", CONFIG)
    io.write_json(out / "manifest_reference.json", {"sha256": previous.file_digest(root / "manifest.json")})
    start = time.perf_counter()
    with (out / "run.log").open("x", encoding="utf-8", buffering=1) as log:
        def emit(message):
            print(message, flush=True)
            log.write(message + "\n")
        try:
            cases = [c for c in manifest["cases"] if c["seed"] == seed]
            for c in cases:
                path = root / "cases" / c["file"]
                assert previous.file_digest(path) == c["bundle_sha256"]
                b = read(path)
                assert game_hash(b["genome"]) == c["game_hash"]
                assert previous.digest(b["holdout_tasks"]) == c["holdout_tasks_sha256"]
                blocked = {(tuple(a), tuple(v)) for k in ("excluded_selection_pairs", "excluded_previous_holdout_pairs") for a, v in b[k]}
                assert not blocked & set(map(previous.pair, b["holdout_tasks"]))
                emit(f"START seed={seed} generations={c['generations']} world={c['game_hash']}")
                cpu, wall = time.process_time(), time.perf_counter()
                paired, learned = previous.paired_learning(b, emit)
                engine = Engine(b["genome"])
                stats, graph = oracle(engine, CONFIG["oracle_cap"])
                assert stats == b["archived_final"]["oracle"] and graph is not None
                full_selection = frozen.full_information(engine, graph, b["archived_final"]["tasks"], CONFIG["horizon"], b["diagnostic_seed"])
                previous.reproduce_evaluation(full_selection, b["archived_final"]["full_info"])
                full = frozen.full_information(engine, graph, b["holdout_tasks"], CONFIG["horizon"], b["diagnostic_seed"]) if b["holdout_tasks"] else None
                s, h = curve(paired, "selection"), curve(paired, "holdout")
                for k in ("D", "B50", "B80", "B90", "final_success"):
                    assert s[k] == b["archived_final"][k], k
                indices = [i for i, r in enumerate(full["task_results"]) if r["success"]] if full else []
                result = {"status": "COMPLETED" if h else "NO_UNUSED_TASKS", "seed": seed,
                    "game_hash": c["game_hash"], "generations": c["generations"], "provenance": prov,
                    "source_bundle_sha256": c["bundle_sha256"], "holdout_tasks_sha256": c["holdout_tasks_sha256"],
                    "population": c["population"], "paired": paired, "selection_metrics": s, "holdout_metrics": h,
                    "full_info_selection": full_selection, "full_info_holdout": full,
                    "core_solvable_metrics": curve(paired, "holdout", indices),
                    "core_unsolvable_metrics": curve(paired, "holdout", [i for i in range(len(b["holdout_tasks"])) if i not in set(indices)]),
                    "classification": classification(h["final_success"] if h else None, full["success_rate"] if full else None),
                    "per_budget_contingency": [{"budget": p["budget"], **contingency(p["holdout"], full)} for p in paired] if full else [],
                    "common_bin_standardization": [{"budget": p["budget"], **previous.standardized(p["selection"], p["holdout"])} for p in paired] if h else [],
                    "training_counts": [{k: r[k] for k in ("budget", "learned_states", "learned_transitions", "state_coverage", "edge_coverage")} for r in learned],
                    "all_original_checkpoints_reproduced": True, "original_full_info_reproduced": True,
                    "holdout_learning_updates": 0, "genome_unchanged": True,
                    "cpu_seconds": time.process_time() - cpu, "wall_seconds": time.perf_counter() - wall,
                    "peak_rss_bytes": io.peak_rss()}
                io.write_json(out / c["file"], result)
                emit(f"COMPLETE generations={c['generations']} holdout={h} full={full['success_rate'] if full else None}")
            assert previous.verified_sources() == prov["frozen_source_hashes_lf"]
            io.write_json(out / "completed.json", {"status": "COMPLETED", "seed": seed, "unique_worlds": len(cases), "wall_seconds": time.perf_counter() - start})
        except BaseException as exc:
            io.write_json(out / "incomplete.json", {"status": "RUN_NOT_COMPLETED", "error": repr(exc)})
            raise


def validate_evaluation(e, tasks, engine):
    assert e["tasks"] == len(tasks)
    assert e["successes"] == sum(r["success"] for r in e["task_results"])
    assert e["success_rate"] == e["successes"] / len(tasks)
    assert e["q"] == .9 and e["psi_cutoff"] == 1e-7 and e["evaluation_updates"] == 0
    r = e["task_results"][0]
    trace = r["recorded_trajectory"]
    assert previous.digest(trace) == r["trajectory_sha256"]
    state = tuple(tasks[0]["start"])
    assert list(state) == trace["states"][0]
    assert len(trace["states"]) == len(trace["actions"]) + 1
    for action, expected in zip(trace["actions"], trace["states"][1:]):
        state = engine.step(state, action)
        assert list(state) == expected
    assert (list(state) == tasks[0]["target"]) == r["success"]


def sign_delta(a, b):
    if a is None or b is None:
        return "unmeasured"
    return "increase" if Fraction(b) > Fraction(a) else "decrease" if Fraction(b) < Fraction(a) else "tie"


def summarize(input_dir, frozen_dir, output):
    out, root = Path(output), Path(frozen_dir)
    out.mkdir(parents=True, exist_ok=False)
    manifest = read(root / "manifest.json")
    assert manifest["config"] == CONFIG
    flat, curves, distributions, unique_results, replay_count = [], [], [], [], 0
    for c in manifest["cases"]:
        matches = list(Path(input_dir).rglob(c["file"]))
        assert len(matches) == 1
        r, b = read(matches[0]), read(root / "cases" / c["file"])
        assert previous.file_digest(root / "cases" / c["file"]) == c["bundle_sha256"] == r["source_bundle_sha256"]
        assert r["holdout_tasks_sha256"] == previous.digest(b["holdout_tasks"])
        assert r["all_original_checkpoints_reproduced"] and r["original_full_info_reproduced"]
        engine = Engine(b["genome"])
        for p in r["paired"]:
            assert p["archived_reproduction_verified"] and p["same_model_verified"]
            for key, tasks in (("selection", b["archived_final"]["tasks"]), ("holdout", b["holdout_tasks"])):
                if tasks:
                    validate_evaluation(p[key], tasks, engine)
                    replay_count += 1
        for key, tasks in (("full_info_selection", b["archived_final"]["tasks"]), ("full_info_holdout", b["holdout_tasks"])):
            if tasks:
                validate_evaluation(r[key], tasks, engine)
                replay_count += 1
        assert curve(r["paired"], "holdout") == r["holdout_metrics"]
        h, s, f = r["holdout_metrics"], r["selection_metrics"], r["full_info_holdout"]
        core = r["core_solvable_metrics"]
        unique_results.append(r)
        for generation in c["generations"]:
            row = {"seed": r["seed"], "generation": generation, "game_hash": r["game_hash"],
                "holdout_tasks": len(b["holdout_tasks"]), "tasks_sha256": r["holdout_tasks_sha256"],
                "D_selection": s["D"], "D_holdout": h["D"] if h else None,
                "D_holdout_exact": h["D_exact"] if h else None,
                "D_core_solvable": core["D"] if core else None,
                "D_core_solvable_exact": core["D_exact"] if core else None,
                "selection_success": s["final_success"], "holdout_success": h["final_success"] if h else None,
                "full_info_success": f["success_rate"] if f else None,
                "selection_full_info_success": r["full_info_selection"]["success_rate"], "classification": r["classification"],
                **{f"B{x}_{name}": metrics[f"B{x}"] if metrics else None for name, metrics in (("selection", s), ("holdout", h)) for x in (50, 80, 90)},
                "common_bin_selection_mass": r["common_bin_standardization"][-1]["selection_mass_covered"] if h else None,
                "common_bin_success_gap": r["common_bin_standardization"][-1]["delta"] if h else None}
            flat.append(row)
            for p in r["paired"]:
                curves.append({"seed": r["seed"], "generation": generation, "game_hash": r["game_hash"], "budget": p["budget"],
                    "S_selection": p["selection"]["success_rate"], "S_holdout": p["holdout"]["success_rate"] if h else None,
                    "full_info_success": row["full_info_success"]})
            distributions.append({"seed": r["seed"], "generation": generation, "game_hash": r["game_hash"],
                "population": b["population"], "selection_distance_counts": dict(Counter(t["distance"] for t in b["archived_final"]["tasks"])),
                "holdout_distance_counts": dict(Counter(t["distance"] for t in b["holdout_tasks"]))})
    flat.sort(key=lambda r: (r["seed"], r["generation"]))
    assert len(flat) == 88
    transitions, per_seed = [], []
    for seed in SEEDS:
        rows = [r for r in flat if r["seed"] == seed]
        assert [r["generation"] for r in rows] == list(range(11))
        local = []
        for a, b in zip(rows, rows[1:]):
            same = a["game_hash"] == b["game_hash"]
            if same:
                assert a["tasks_sha256"] == b["tasks_sha256"] and a["D_holdout_exact"] == b["D_holdout_exact"]
            t = {"seed": seed, "from_generation": a["generation"], "to_generation": b["generation"], "same_world": same,
                "holdout_direction": sign_delta(a["D_holdout_exact"], b["D_holdout_exact"]),
                "core_solvable_direction": sign_delta(a["D_core_solvable_exact"], b["D_core_solvable_exact"]),
                "delta_D": b["D_holdout"] - a["D_holdout"] if a["D_holdout"] is not None and b["D_holdout"] is not None else None,
                "delta_full_info": b["full_info_success"] - a["full_info_success"] if a["full_info_success"] is not None and b["full_info_success"] is not None else None,
                "both_full_info_at_least_80": all(r["full_info_success"] is not None and r["full_info_success"] >= .8 for r in (a, b)),
                "both_learned_at_least_80": all(r["holdout_success"] is not None and r["holdout_success"] >= .8 for r in (a, b))}
            local.append(t)
        transitions.extend(local)
        first = next((r for r in rows if r["selection_success"] >= .8 and r["selection_full_info_success"] >= .8), None)
        per_seed.append({"seed": seed, "G0": rows[0], "G10": rows[-1],
            "G0_G10_direction": sign_delta(rows[0]["D_holdout_exact"], rows[-1]["D_holdout_exact"]),
            "generation_change_counts": dict(Counter(t["holdout_direction"] for t in local)),
            "changed_worlds": sum(not t["same_world"] for t in local),
            "full_info_preserving_increases": sum(t["holdout_direction"] == "increase" and t["delta_full_info"] >= 0 for t in local),
            "core_solvable_increases": sum(t["core_solvable_direction"] == "increase" for t in local),
            "first_selection_eligible_generation": first["generation"] if first else None,
            "first_eligible_to_final_direction": sign_delta(first["D_holdout_exact"], rows[-1]["D_holdout_exact"]) if first else None})
    metrics = {"status": "COMPLETED", "source_run": SOURCE_RUN, "config": CONFIG,
        "audit_heads": sorted({r["provenance"]["git_head"] for r in unique_results}),
        "audit_runs": sorted({r["provenance"]["github_run_id"] for r in unique_results}),
        "unique_worlds": len(unique_results), "seed_generation_entries": len(flat),
        "new_holdout_pairs": sum(r["population"]["actual"] for r in unique_results),
        "reproduced_checkpoints": sum(len(r["paired"]) for r in unique_results), "verified_task_zero_replays": replay_count,
        "cpu_seconds": sum(r["cpu_seconds"] for r in unique_results), "peak_rss_bytes": max(r["peak_rss_bytes"] for r in unique_results),
        "per_seed": per_seed, "world_generations": flat}
    io.write_json(out / "metrics.json", metrics)
    io.write_json(out / "oracle_task_distances.json", distributions)
    io.csv_write(out / "generation_comparison.csv", flat)
    io.csv_write(out / "learning_curves.csv", curves)
    io.csv_write(out / "generation_changes.csv", transitions)
    io.csv_write(out / "borderline_706_807_908.csv", [r for r in flat if r["seed"] in (706, 807, 908)])
    plots(out, flat, curves)
    print(json.dumps({k: v for k, v in metrics.items() if k not in ("world_generations", "per_seed", "config")}, indent=2), flush=True)


def plots(out, flat, curves):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    for field, title in (("D", "Learning difficulty: higher = larger unsolved area"), ("B80", "First measured 80% success budget")):
        fig, axes = plt.subplots(4, 2, figsize=(11, 13), constrained_layout=True)
        for ax, seed in zip(axes.flat, SEEDS):
            rows = [r for r in flat if r["seed"] == seed]
            for suffix, style in (("selection", "--"), ("holdout", "-")):
                vals = [r[f"{field}_{suffix}"] for r in rows]
                ax.plot(range(11), [v if v is not None else (16384 if field == "B80" else float("nan")) for v in vals], style, marker="o", label=suffix)
            ax.set(title=f"Seed {seed}", xlabel="Archived frontier generation", ylabel=field, xticks=range(11))
            if field == "B80":
                ax.set_yscale("log", base=2)
                ax.set(yticks=[128, 512, 2048, 8192, 16384], yticklabels=["128", "512", "2048", "8192", "not reached"])
            ax.legend()
        fig.suptitle(title + "\nSame retained world = same holdout tasks and measurement")
        fig.savefig(out / f"{field}_by_generation.png", dpi=140)
        plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), constrained_layout=True)
    for ax, seed in zip(axes, (706, 807, 908)):
        rows = [r for r in flat if r["seed"] == seed]
        for field, label in (("selection_success", "Selection learned"), ("holdout_success", "Holdout learned"), ("full_info_success", "Holdout full information")):
            ax.plot(range(11), [r[field] for r in rows], marker="o", label=label)
        ax.axhline(.8, color="gray", linestyle=":")
        ax.set(title=f"Seed {seed}", xlabel="Archived frontier generation", ylabel="Success @8192", xticks=range(11), ylim=(-.03, 1.03))
        ax.legend()
    fig.savefig(out / "borderline_seeds.png", dpi=140)
    plt.close(fig)
    fig, axes = plt.subplots(4, 2, figsize=(11, 13), constrained_layout=True)
    for ax, seed in zip(axes.flat, SEEDS):
        for g in range(11):
            rows = [r for r in curves if r["seed"] == seed and r["generation"] == g]
            ax.plot([r["budget"] for r in rows], [r["S_holdout"] for r in rows], color=plt.cm.viridis(g / 10), label=f"G{g}")
        ax.set_xscale("log", base=2)
        ax.set(title=f"Seed {seed}", xlabel="Interactions", ylabel="Holdout success", ylim=(-.03, 1.03))
        ax.legend(ncol=4, fontsize=7)
    fig.savefig(out / "holdout_learning_curves.png", dpi=140)
    plt.close(fig)
    fig, axes = plt.subplots(4, 2, figsize=(11, 13), constrained_layout=True)
    for ax, seed in zip(axes.flat, SEEDS):
        rows = [r for r in flat if r["seed"] == seed]
        ax.plot(range(11), [r["D_holdout"] for r in rows], label="All holdout tasks", marker="o")
        ax.plot(range(11), [r["D_core_solvable"] for r in rows], label="Tasks solved with full information", marker="o")
        ax.set(title=f"Seed {seed}", xlabel="Archived frontier generation", ylabel="D", xticks=range(11))
        ax.legend(fontsize=8)
    fig.suptitle("Capacity diagnostic: each world's own full-information-solvable subset")
    fig.savefig(out / "capacity_control.png", dpi=140)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("prepare", "run", "summarize"))
    p.add_argument("--input", type=Path)
    p.add_argument("--prior", type=Path)
    p.add_argument("--frozen", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seed", type=int)
    a = p.parse_args()
    if a.mode == "prepare":
        prepare(a.input, a.prior, a.output)
    elif a.mode == "run":
        run_seed(a.frozen, a.output, a.seed)
    else:
        summarize(a.input, a.frozen, a.output)
