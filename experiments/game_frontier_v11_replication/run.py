"""Seed-only replication of frozen v1.1; no historical experiment inputs."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from pathlib import Path
import statistics
import time
from types import FunctionType

from experiments.game_frontier_v11 import runner as evolution
from experiments.game_frontier_v11 import measurement as measure
from experiments.game_frontier_v11.world import Engine, game_hash, oracle
from experiments.game_frontier_v11_holdout import audit as holdout
from experiments.game_frontier_v11_generation_holdout import audit as analysis

io = holdout.io
SEEDS = [1101, 1202, 1303, 1404, 1505, 1606, 1707, 1808]
CONDITIONS = list(evolution.CONDITIONS)
TASK_SEED_ROOT = analysis.TASK_SEED_ROOT
PROTOCOL = {
    "name": "independent-evolution-replication-v1.1", "seeds": SEEDS,
    "frozen_evolution_source": holdout.SOURCE_COMMIT, "conditions": CONDITIONS,
    "evolution_config_difference": "seeds only", "prior_experiment_inputs": [],
    "holdout_seed_root": TASK_SEED_ROOT,
    "holdout_seed": "derive(root, seed, genome_hash, 'generation-holdout')",
    "holdout_sampling": "500 distinct distance>=4 pairs; frozen distance bins/reservoir/redistribution",
    "holdout_exclusion": "union of all same-genome selection pairs in this replication's initial pools and all candidates",
    "holdout_shortage": "census of remaining eligible pairs, no replacement or generation",
    "holdout_timing": "only after all 24 evolution runs complete; freeze all task sets before holdout player evaluation",
    "same_world": "same seed+genome uses same holdout tasks across generations and conditions",
    "endpoint_1": "number of seeds with D_holdout(G10)>D_holdout(first performance-eligible generation); report missing eligibility separately",
    "comparison_eligibility": "common MORTRA valid/full>=.8/learned>=.8 gate for all three arms; native random gate separately recorded",
    "endpoint_2": "holdout D increases / changed-world transitions with selection D strictly increasing; also show all changed transitions",
    "endpoint_2_selection": "strict comparison of frozen selection D floats, no new tolerance; holdout direction from rational counts",
    "endpoint_3": "final holdout success per seed, macro and task-pooled means",
    "endpoint_4": "same registered endpoints in mortra/random/size_only, paired by new seed",
    "endpoint_5": "learned/full-info classifications at all frontiers and finals, unique-world and generation counts separated",
    "holdout_diagnostics": "same frozen full-info core on holdout; core-solvable D; task-level contingency; oracle distances",
    "pass_criterion": None, "tuning": "none; never use prior eight-seed outcomes for parameters or criteria",
    "stopping": "fixed initial pool and ten generations, then all-frontier holdout audit and report; no next stage",
}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def config(stage=2):
    assert stage == 2
    cfg = evolution.config(stage)
    cfg["seeds"] = list(SEEDS)
    return cfg


def provenance():
    p = io.provenance(config(), SEEDS)
    p["source_hashes_lf"] = holdout.verified_sources()
    paths = [*sorted((io.ROOT / "experiments/game_frontier_v11_replication").glob("*.py")),
        io.ROOT / "scripts/evaluate_autonomous_game_frontier_v11_replication.py",
        io.ROOT / "tests/test_autonomous_game_frontier_v11_replication.py",
        io.ROOT / ".github/workflows/frontier-v11-independent-replication.yml",
        io.ROOT / "docs/research/FRONTIER-V11-INDEPENDENT-REPLICATION-20260925.md",
        io.ROOT / "experiments/game_frontier_v11_holdout/audit.py",
        io.ROOT / "experiments/game_frontier_v11_generation_holdout/audit.py"]
    p["replication_and_audit_source_hashes_lf"] = {x.relative_to(io.ROOT).as_posix():
        hashlib.sha256(x.read_text(encoding="utf-8").encode()).hexdigest() for x in paths}
    p["protocol"] = PROTOCOL
    p["protocol_hash"] = holdout.digest(PROTOCOL)
    return p


def register(output):
    out = Path(output)
    out.mkdir(parents=True, exist_ok=False)
    io.write_json(out / "source_snapshot.json", provenance())
    io.write_json(out / "config.json", config())
    io.write_json(out / "protocol.json", PROTOCOL)
    io.write_json(out / "rng_seeds.json", {"evolution": SEEDS, "holdout_root": TASK_SEED_ROOT})


def evolution_callable():
    namespace = dict(evolution.run_seed.__globals__)
    namespace["config"] = config
    return FunctionType(evolution.run_seed.__code__, namespace, evolution.run_seed.__name__, evolution.run_seed.__defaults__)


def evolve(seed, output):
    assert seed in SEEDS
    before = holdout.verified_sources()
    evolution_callable()(2, seed, output)
    assert holdout.verified_sources() == before
    io.write_json(Path(output) / "replication_provenance.json", provenance())


def same_measurement(a, b):
    for key in ("game_hash", "tasks_sha256", "tasks", "oracle", "valid", "D", "B50", "B80", "B90", "final_success"):
        assert a[key] == b[key], key
    assert len(a["learning"]) == len(b["learning"]) == 14
    for x, y in zip(a["learning"], b["learning"]):
        assert x["budget"] == y["budget"]
        holdout.reproduce_evaluation(x["evaluation"], y["evaluation"])
    holdout.reproduce_evaluation(a["full_info"], b["full_info"])


def eligible(record):
    return bool(record["valid"] and record["full_info"]["success_rate"] >= .8 and record["final_success"] >= .8)


def freeze(input_dir, output):
    root, out = Path(input_dir), Path(output)
    out.mkdir(parents=True, exist_ok=False)
    prov = provenance()
    io.write_json(out / "source_snapshot.json", prov)
    io.write_json(out / "config.json", config())
    io.write_json(out / "protocol.json", PROTOCOL)
    groups, exclusions, seen, inputs = {}, defaultdict(set), set(), {}
    candidate_counts, incomplete_reasons = Counter(), Counter()
    for p in sorted(root.rglob("results.json")):
        r = read(p)
        assert r["status"] == "COMPLETED" and r["config"] == config()
        assert r["provenance"]["git_head"] == prov["git_head"]
        assert r["provenance"]["github_run_id"] == prov["github_run_id"]
        assert r["provenance"]["source_hashes_lf"] == prov["source_hashes_lf"]
        key = r["seed"], r["condition"]
        assert key not in seen
        seen.add(key)
        inputs[p.relative_to(root).as_posix()] = holdout.file_digest(p)
        for candidate in r["candidates"]:
            exclusions[candidate["game_hash"]].update(map(holdout.pair, candidate["tasks"]))
            candidate_counts[r["condition"]] += 1
            if not candidate["learning"]:
                incomplete_reasons[candidate.get("reason", candidate["classification"])] += 1
        assert len(r["frontier"]) == 11
        for generation, record in enumerate(r["frontier"]):
            key = r["seed"], record["game_hash"]
            if key not in groups:
                gp = p.parent / "games" / record["game_hash"] / "genome.json"
                genome = read(gp)
                assert game_hash(genome) == record["game_hash"]
                groups[key] = {"seed": r["seed"], "game_hash": record["game_hash"], "genome": genome,
                    "archived_final": record, "references": [], "genome_file_sha256": holdout.file_digest(gp)}
            same_measurement(record, groups[key]["archived_final"])
            groups[key]["references"].append({"condition": r["condition"], "generation": generation,
                "performance_eligible": eligible(record),
                "native_selection_eligible": record["valid"] if r["condition"] == "random" else eligible(record),
                "evolution_result_sha256": holdout.file_digest(p)})
    assert seen == {(s, c) for s in SEEDS for c in CONDITIONS}
    for p in sorted(root.glob("**/initial_pool/candidate_*.json")):
        r = read(p)["prepared"]
        exclusions[r["game_hash"]].update(map(holdout.pair, r["tasks"]))
        inputs[p.relative_to(root).as_posix()] = holdout.file_digest(p)
    assert len(list(root.glob("**/initial_pool/candidate_*.json"))) == 8 * 32
    io.write_json(out / "input_artifact_hashes.json", inputs)
    manifest = {"status": "FROZEN_AFTER_ALL_EVOLUTION_BEFORE_HOLDOUT", "protocol": PROTOCOL,
        "evolution_config": config(), "cases": [], "generation_entries": 264,
        "candidate_occurrences": dict(candidate_counts), "unevaluated_candidate_reasons": dict(incomplete_reasons),
        "evolution_run": prov["github_run_id"], "evolution_head": prov["git_head"]}
    with (out / "run.log").open("x", encoding="utf-8", buffering=1) as log:
        for (seed, gh), b in sorted(groups.items()):
            stats, graph = oracle(Engine(b["genome"]), config()["oracle_cap"])
            assert graph is not None and stats == b["archived_final"]["oracle"]
            task_seed = io.derive(TASK_SEED_ROOT, seed, gh, "generation-holdout")
            tasks, population = holdout.sample_holdout(graph, exclusions[gh], 500, task_seed)
            assert population["original_by_bin"] == b["archived_final"]["pair_population_by_bin"]
            b.update(holdout_tasks=tasks, holdout_tasks_sha256=holdout.digest(tasks), population=population,
                holdout_task_seed=task_seed, player_seed=io.derive(seed, gh, "player"), diagnostic_seed=io.derive(seed, gh, "diagnostic"),
                excluded_pairs=[[list(a), list(v)] for a, v in sorted(exclusions[gh])])
            filename = f"{seed}_{gh}.json"
            io.write_json(out / "cases" / filename, b)
            manifest["cases"].append({k: b[k] for k in ("seed", "game_hash", "references", "holdout_tasks_sha256", "population", "holdout_task_seed")}
                | {"file": filename, "bundle_sha256": holdout.file_digest(out / "cases" / filename)})
            message = f"FROZEN seed={seed} world={gh} tasks={len(tasks)} references={len(b['references'])}"
            print(message, flush=True)
            log.write(message + "\n")
        assert sum(len(c["references"]) for c in manifest["cases"]) == 264
        io.write_json(out / "manifest.json", manifest)
        io.write_json(out / "rng_seeds.json", [{k: c[k] for k in ("seed", "game_hash", "holdout_task_seed")} for c in manifest["cases"]])
        log.write("ALL NEW HOLDOUT SETS FROZEN; NO HOLDOUT PLAYER EVALUATION HAS RUN\n")


def audit_seed(frozen_dir, output, seed):
    root, out = Path(frozen_dir), Path(output)
    out.mkdir(parents=True, exist_ok=False)
    manifest, prov = read(root / "manifest.json"), provenance()
    assert manifest["protocol"] == PROTOCOL and manifest["evolution_config"] == config()
    assert manifest["evolution_run"] == prov["github_run_id"] and manifest["evolution_head"] == prov["git_head"]
    io.write_json(out / "source_snapshot.json", prov)
    io.write_json(out / "manifest_reference.json", {"sha256": holdout.file_digest(root / "manifest.json")})
    started = time.perf_counter()
    with (out / "run.log").open("x", encoding="utf-8", buffering=1) as log:
        def emit(s):
            print(s, flush=True)
            log.write(s + "\n")
        try:
            cases = [c for c in manifest["cases"] if c["seed"] == seed]
            assert cases and seed in SEEDS
            for c in cases:
                path = root / "cases" / c["file"]
                assert holdout.file_digest(path) == c["bundle_sha256"]
                b = read(path)
                assert holdout.digest(b["holdout_tasks"]) == c["holdout_tasks_sha256"]
                assert game_hash(b["genome"]) == c["game_hash"]
                assert not set(map(holdout.pair, b["holdout_tasks"])) & {(tuple(a), tuple(v)) for a, v in b["excluded_pairs"]}
                emit(f"START {seed} {c['game_hash']}")
                cpu = time.process_time()
                paired, learned = holdout.paired_learning(b, emit)
                stats, graph = oracle(Engine(b["genome"]), config()["oracle_cap"])
                assert stats == b["archived_final"]["oracle"]
                original_full = measure.full_information(Engine(b["genome"]), graph, b["archived_final"]["tasks"], config()["horizon"], b["diagnostic_seed"])
                holdout.reproduce_evaluation(original_full, b["archived_final"]["full_info"])
                full = measure.full_information(Engine(b["genome"]), graph, b["holdout_tasks"], config()["horizon"], b["diagnostic_seed"]) if b["holdout_tasks"] else None
                s, h = analysis.curve(paired, "selection"), analysis.curve(paired, "holdout")
                for key in ("D", "B50", "B80", "B90", "final_success"):
                    assert s[key] == b["archived_final"][key]
                indices = [i for i, t in enumerate(full["task_results"]) if t["success"]] if full else []
                r = {"status": "COMPLETED" if h else "NO_UNUSED_TASKS", "seed": seed, "game_hash": c["game_hash"],
                    "references": c["references"], "source_bundle_sha256": c["bundle_sha256"], "provenance": prov,
                    "paired": paired, "selection_metrics": s, "holdout_metrics": h, "full_info_holdout": full,
                    "full_info_selection": original_full, "core_solvable_metrics": analysis.curve(paired, "holdout", indices),
                    "classification": analysis.classification(h["final_success"] if h else None, full["success_rate"] if full else None),
                    "per_budget_contingency": [{"budget": p["budget"], **analysis.contingency(p["holdout"], full)} for p in paired] if full else [],
                    "common_bin_standardization": [{"budget": p["budget"], **holdout.standardized(p["selection"], p["holdout"])} for p in paired] if h else [],
                    "training_counts": [{k: r[k] for k in ("budget", "learned_states", "learned_transitions", "state_coverage", "edge_coverage")} for r in learned],
                    "all_selection_checkpoints_reproduced": True, "holdout_learning_updates": 0,
                    "cpu_seconds": time.process_time() - cpu, "peak_rss_bytes": io.peak_rss()}
                io.write_json(out / c["file"], r)
                emit(f"COMPLETE {c['game_hash']} holdout={h} full={full['success_rate'] if full else None}")
            io.write_json(out / "completed.json", {"status": "COMPLETED", "seed": seed, "unique_worlds": len(cases), "wall_seconds": time.perf_counter() - started})
            assert holdout.verified_sources() == prov["source_hashes_lf"]
        except BaseException as exc:
            io.write_json(out / "incomplete.json", {"status": "RUN_NOT_COMPLETED", "reason": repr(exc)})
            raise


def endpoint(rows):
    assert [r["generation"] for r in rows] == list(range(11))
    first = next((r for r in rows if r["performance_eligible"]), None)
    final = rows[-1]
    changed = [dict(from_generation=a["generation"], to_generation=b["generation"],
        selection_D_increase=b["D_selection"] > a["D_selection"],
        holdout_direction=analysis.sign_delta(a["D_holdout_exact"], b["D_holdout_exact"]),
        full_info_change=(b["full_info_success"] - a["full_info_success"]) if a["full_info_success"] is not None and b["full_info_success"] is not None else None)
        for a, b in zip(rows, rows[1:]) if a["game_hash"] != b["game_hash"]]
    selected_up = [r for r in changed if r["selection_D_increase"]]
    return {"first_eligible_generation": first["generation"] if first else None,
        "first_eligible_D_holdout": first["D_holdout"] if first else None,
        "G10_D_holdout": final["D_holdout"],
        "eligibility_to_final_direction": analysis.sign_delta(first["D_holdout_exact"], final["D_holdout_exact"]) if first else "NO_ELIGIBLE_GENERATION",
        "eligible_at_final_only": first is not None and first["generation"] == 10,
        "changed_transitions": changed, "changed_count": len(changed),
        "selection_D_increases": len(selected_up),
        "replicated_holdout_increases": sum(r["holdout_direction"] == "increase" for r in selected_up),
        "unmeasured_holdout_transitions": sum(r["holdout_direction"] == "unmeasured" for r in selected_up),
        "final_holdout_success": final["holdout_success"], "final_full_info_success": final["full_info_success"],
        "final_classification": final["classification"], "final_tasks": final["holdout_tasks"],
        "final_successes": final["holdout_successes"]}


def summarize(input_dir, frozen_dir, output):
    out, root = Path(output), Path(frozen_dir)
    out.mkdir(parents=True, exist_ok=False)
    manifest = read(root / "manifest.json")
    assert manifest["protocol"] == PROTOCOL
    flat, curves, distances, unique, replays = [], [], [], [], 0
    for c in manifest["cases"]:
        ps = list(Path(input_dir).rglob(c["file"]))
        assert len(ps) == 1
        r, b = read(ps[0]), read(root / "cases" / c["file"])
        assert holdout.file_digest(root / "cases" / c["file"]) == c["bundle_sha256"] == r["source_bundle_sha256"]
        assert r["all_selection_checkpoints_reproduced"]
        engine = Engine(b["genome"])
        for p in r["paired"]:
            for key, tasks in (("selection", b["archived_final"]["tasks"]), ("holdout", b["holdout_tasks"])):
                if tasks:
                    analysis.validate_evaluation(p[key], tasks, engine)
                    replays += 1
        for key, tasks in (("full_info_selection", b["archived_final"]["tasks"]), ("full_info_holdout", b["holdout_tasks"])):
            if tasks:
                analysis.validate_evaluation(r[key], tasks, engine)
                replays += 1
        h, s, f = r["holdout_metrics"], r["selection_metrics"], r["full_info_holdout"]
        assert analysis.curve(r["paired"], "holdout") == h
        unique.append(r)
        for ref in c["references"]:
            row = {"seed": r["seed"], "condition": ref["condition"], "generation": ref["generation"], "game_hash": r["game_hash"],
                "performance_eligible": ref["performance_eligible"], "native_selection_eligible": ref["native_selection_eligible"],
                "D_selection": s["D"], "D_holdout": h["D"] if h else None, "D_holdout_exact": h["D_exact"] if h else None,
                "selection_success": s["final_success"], "holdout_success": h["final_success"] if h else None,
                "holdout_successes": r["paired"][-1]["holdout"]["successes"] if h else None,
                "full_info_success": f["success_rate"] if f else None, "classification": r["classification"],
                "holdout_tasks": len(b["holdout_tasks"]), "holdout_tasks_sha256": c["holdout_tasks_sha256"],
                "core_solvable_D": r["core_solvable_metrics"]["D"] if r["core_solvable_metrics"] else None,
                **{f"B{x}_{key}": val[f"B{x}"] if val else None for x in (50, 80, 90) for key, val in (("selection", s), ("holdout", h))}}
            flat.append(row)
            for p in r["paired"]:
                curves.append({"seed": r["seed"], "condition": ref["condition"], "generation": ref["generation"], "budget": p["budget"],
                    "S_selection": p["selection"]["success_rate"], "S_holdout": p["holdout"]["success_rate"] if h else None})
        distances.append({"seed": r["seed"], "game_hash": r["game_hash"], "references": c["references"], "population": b["population"],
            "selection_distances": dict(Counter(t["distance"] for t in b["archived_final"]["tasks"])),
            "holdout_distances": dict(Counter(t["distance"] for t in b["holdout_tasks"]))})
    flat.sort(key=lambda r: (r["condition"], r["seed"], r["generation"]))
    assert len(flat) == 264
    endpoints, conditions = [], {}
    for cond in CONDITIONS:
        for seed in SEEDS:
            rows = [r for r in flat if (r["seed"], r["condition"]) == (seed, cond)]
            endpoints.append({"seed": seed, "condition": cond, **endpoint(rows)})
        es = [r for r in endpoints if r["condition"] == cond]
        measured = [r for r in es if r["final_holdout_success"] is not None]
        selected_up = sum(r["selection_D_increases"] for r in es)
        replicated = sum(r["replicated_holdout_increases"] for r in es)
        unmeasured = sum(r["unmeasured_holdout_transitions"] for r in es)
        conditions[cond] = {"endpoint_1_directions": dict(Counter(r["eligibility_to_final_direction"] for r in es)),
            "seeds_total": 8, "seeds_ever_eligible": sum(r["first_eligible_generation"] is not None for r in es),
            "first_eligibility_at_G10": sum(r["eligible_at_final_only"] for r in es),
            "changed_transitions": sum(r["changed_count"] for r in es),
            "selection_D_increases": selected_up, "holdout_reproduced_increases": replicated,
            "endpoint_2_fraction": replicated / selected_up if selected_up and not unmeasured else None,
            "endpoint_2_unmeasured": unmeasured,
            "endpoint_2_bounds": [replicated / selected_up, (replicated + unmeasured) / selected_up] if selected_up else None,
            "final_success_macro": statistics.mean(r["final_holdout_success"] for r in measured) if measured else None,
            "final_success_pooled": sum(r["final_successes"] for r in measured) / sum(r["final_tasks"] for r in measured) if measured else None,
            "final_successes": sum(r["final_successes"] for r in measured), "final_tasks": sum(r["final_tasks"] for r in measured),
            "final_classes": dict(Counter(r["final_classification"] for r in es)),
            "all_generation_classes": dict(Counter(r["classification"] for r in flat if r["condition"] == cond)),
            "unique_world_classes": dict(Counter(r["classification"] for r in unique if any(ref["condition"] == cond for ref in r["references"])))}
    metrics = {"status": "COMPLETED", "protocol": PROTOCOL, "run": manifest["evolution_run"], "head": manifest["evolution_head"],
        "evolution_runs": 24, "seed_generation_entries": 264, "unique_seed_worlds": len(unique),
        "distinct_holdout_pairs": sum(c["population"]["actual"] for c in manifest["cases"]),
        "holdout_shortage_worlds": sum(c["population"]["actual"] < 500 for c in manifest["cases"]),
        "candidate_occurrences": manifest["candidate_occurrences"], "unevaluated_candidate_reasons": manifest["unevaluated_candidate_reasons"],
        "reproduced_checkpoints": sum(len(r["paired"]) for r in unique), "verified_task_zero_replays": replays,
        "audit_cpu_seconds": sum(r["cpu_seconds"] for r in unique), "audit_peak_rss_bytes": max(r["peak_rss_bytes"] for r in unique),
        "conditions": conditions, "per_seed_condition": endpoints}
    io.write_json(out / "metrics.json", metrics)
    io.write_json(out / "task_distance_distributions.json", distances)
    io.csv_write(out / "all_frontier_worlds.csv", flat)
    io.csv_write(out / "learning_curves.csv", curves)
    io.csv_write(out / "endpoints.csv", [{k: v for k, v in r.items() if k != "changed_transitions"} for r in endpoints])
    io.csv_write(out / "changed_transitions.csv", [{"seed": r["seed"], "condition": r["condition"], **t} for r in endpoints for t in r["changed_transitions"]])
    plot(out, flat, conditions)
    print(json.dumps({k: v for k, v in metrics.items() if k not in ("protocol", "per_seed_condition")}, indent=2), flush=True)


def plot(out, flat, conditions):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    colors = {"mortra": "#167b63", "random": "#b95350", "size_only": "#4774b3"}
    fig, axes = plt.subplots(4, 2, figsize=(11, 13), constrained_layout=True)
    for ax, seed in zip(axes.flat, SEEDS):
        for cond in CONDITIONS:
            rows = [r for r in flat if (r["seed"], r["condition"]) == (seed, cond)]
            ax.plot(range(11), [r["D_holdout"] for r in rows], marker=".", color=colors[cond], label=cond)
        ax.set(title=f"New seed {seed}", xlabel="Generation", ylabel="Holdout D", xticks=range(11))
        ax.legend(fontsize=8)
    fig.suptitle("Independent evolution: no prior worlds or outcome-based tuning\nHigher D can include permanent failures; see full-information classification")
    fig.savefig(out / "holdout_D_generations.png", dpi=140)
    plt.close(fig)
    fig, axes = plt.subplots(3, 1, figsize=(10, 10), constrained_layout=True)
    for ax, cond in zip(axes, CONDITIONS):
        rows = [r for r in flat if r["condition"] == cond and r["generation"] == 10]
        ax.bar([i - .18 for i in range(8)], [r["holdout_success"] if r["holdout_success"] is not None else float("nan") for r in rows], width=.36, color=colors[cond], label="Learned graph")
        ax.bar([i + .18 for i in range(8)], [r["full_info_success"] if r["full_info_success"] is not None else float("nan") for r in rows], width=.36, color="#888888", label="Full information")
        ax.set_xticks(range(8), [str(r["seed"]) for r in rows])
        ax.set(title=cond, ylabel="Final holdout success", ylim=(0, 1.05))
        ax.legend()
    fig.savefig(out / "final_success_full_info.png", dpi=140)
    plt.close(fig)


def main():
    p = argparse.ArgumentParser()
    p.add_argument("mode", choices=("register", "evolve", "freeze", "audit", "summarize"))
    p.add_argument("--input", type=Path)
    p.add_argument("--frozen", type=Path)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--seed", type=int)
    a = p.parse_args()
    if a.mode == "register": register(a.output)
    elif a.mode == "evolve": evolve(a.seed, a.output)
    elif a.mode == "freeze": freeze(a.input, a.output)
    elif a.mode == "audit": audit_seed(a.frozen, a.output, a.seed)
    else: summarize(a.input, a.frozen, a.output)
