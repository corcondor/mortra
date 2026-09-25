"""Post-evolution holdout and descriptive proposal audit, never learner input."""
from collections import Counter, defaultdict
from dataclasses import asdict
import math
from pathlib import Path
import statistics
from types import FunctionType

from . import run
from .proposal import Context, ContextualUCB, FAMILIES

io, old, rep = run.io, run.holdout, run.replication
analysis = rep.analysis
read = rep.read


def freeze(input_dir, output):
    root, out = Path(input_dir), Path(output)
    out.mkdir(parents=True, exist_ok=False)
    prov = run.provenance()
    io.write_json(out / "source_snapshot.json", prov)
    io.write_json(out / "config.json", run.config())
    groups, exclusions, seen, starts = {}, defaultdict(set), set(), defaultdict(set)
    candidate_counts, invalid_counts = Counter(), Counter()
    for p in sorted(root.rglob("results.json")):
        r = read(p)
        assert r["status"] == "COMPLETED" and r["config"] == run.config()
        assert r["provenance"]["git_head"] == prov["git_head"]
        assert r["provenance"]["github_run_id"] == prov["github_run_id"]
        assert r["provenance"]["v12_source_hashes_lf"] == prov["v12_source_hashes_lf"]
        assert r["provenance"]["source_hashes_lf"] == prov["source_hashes_lf"]
        run.validate_run(r)
        key = r["seed"], r["condition"]
        assert key not in seen
        seen.add(key)
        starts[r["seed"]].add(r["frontier"][0]["game_hash"])
        for c in r["candidates"]:
            exclusions[c["game_hash"]].update(map(old.pair, c["tasks"]))
            candidate_counts[r["condition"]] += 1
        invalid_counts[r["condition"]] += sum(h["status"] == "INVALID" for h in r["mutation_history"])
        assert len(r["frontier"]) == 11
        for generation, record in enumerate(r["frontier"]):
            key = r["seed"], record["game_hash"]
            if key not in groups:
                genome = read(p.parent / "games" / record["game_hash"] / "genome.json")
                assert rep.game_hash(genome) == record["game_hash"]
                groups[key] = {"seed": r["seed"], "game_hash": record["game_hash"], "genome": genome,
                               "archived_final": record, "references": []}
            rep.same_measurement(record, groups[key]["archived_final"])
            groups[key]["references"].append({"condition": r["condition"], "generation": generation,
                "performance_eligible": rep.eligible(record),
                "native_selection_eligible": record["valid"] if r["condition"] == "random" else rep.eligible(record),
                "evolution_result_sha256": old.file_digest(p)})
    assert seen == {(s, c) for s in run.SEEDS for c in run.CONDITIONS}
    assert all(len(v) == 1 for v in starts.values())
    pools = list(root.glob("**/initial_pool/candidate_*.json"))
    assert len(pools) == 256
    for p in pools:
        c = read(p)["prepared"]
        exclusions[c["game_hash"]].update(map(old.pair, c["tasks"]))
    manifest = {"status": "FROZEN_AFTER_ALL_32_EVOLUTION_RUNS", "protocol": run.PROTOCOL,
        "evolution_config": run.config(), "evolution_run": prov["github_run_id"], "evolution_head": prov["git_head"],
        "cases": [], "candidate_occurrences": dict(candidate_counts), "invalid_slots": dict(invalid_counts)}
    with (out / "run.log").open("x", encoding="utf-8", buffering=1) as log:
        for (seed, gh), b in sorted(groups.items()):
            stats, graph = rep.oracle(rep.Engine(b["genome"]), run.config()["oracle_cap"])
            assert stats == b["archived_final"]["oracle"] and graph is not None
            task_seed = io.derive(rep.TASK_SEED_ROOT, seed, gh, "generation-holdout")
            tasks, population = old.sample_holdout(graph, exclusions[gh], 500, task_seed)
            assert population["original_by_bin"] == b["archived_final"]["pair_population_by_bin"]
            b.update(holdout_tasks=tasks, holdout_tasks_sha256=old.digest(tasks), population=population,
                holdout_task_seed=task_seed, player_seed=io.derive(seed, gh, "player"), diagnostic_seed=io.derive(seed, gh, "diagnostic"),
                excluded_pairs=[[list(a), list(v)] for a, v in sorted(exclusions[gh])])
            filename = f"{seed}_{gh}.json"
            io.write_json(out / "cases" / filename, b)
            manifest["cases"].append({k: b[k] for k in ("seed", "game_hash", "references", "holdout_tasks_sha256", "population", "holdout_task_seed")}
                | {"file": filename, "bundle_sha256": old.file_digest(out / "cases" / filename)})
            msg = f"FROZEN {seed} {gh} tasks={len(tasks)}"
            print(msg, flush=True)
            log.write(msg + "\n")
        assert sum(len(c["references"]) for c in manifest["cases"]) == 352
        io.write_json(out / "manifest.json", manifest)
        io.write_json(out / "rng_seeds.json", [{k: c[k] for k in ("seed", "game_hash", "holdout_task_seed")} for c in manifest["cases"]])


def audit_seed(frozen_dir, output, seed):
    namespace = dict(rep.audit_seed.__globals__)
    namespace.update(PROTOCOL=run.PROTOCOL, config=run.config, provenance=run.provenance, SEEDS=run.SEEDS)
    # Keep the exact previously verified paired-evaluation/reasoning path.
    function = FunctionType(rep.audit_seed.__code__, namespace, rep.audit_seed.__name__, rep.audit_seed.__defaults__)
    function(frozen_dir, output, seed)


def proposal_audit(evolution_dir):
    events, generations, arms, runs, context_checks = [], [], [], [], []
    for p in sorted(Path(evolution_dir).rglob("results.json")):
        r = read(p)
        assert r["config"] == run.config()
        run.validate_run(r)
        seed, cond, history = r["seed"], r["condition"], r["mutation_history"]
        for h in history:
            events.append({"seed": seed, "condition": cond, **h})
        for g in range(1, 11):
            hs = [h for h in history if h["generation"] == g]
            for arm in FAMILIES:
                used = [h for h in hs if h["mutation"] == arm]
                generations.append({"seed": seed, "condition": cond, "generation": g, "arm": arm,
                    "probability": statistics.mean(h["decision"]["probabilities"][arm] for h in hs),
                    "usage": len(used), "mean_reward": statistics.mean(h["reward"] for h in used) if used else None,
                    "valid_count": sum(h["outcome"]["valid"] for h in used),
                    "eligible_count": sum(h["outcome"]["eligible"] for h in used),
                    "selected_count": sum(h["selected"] for h in used)})
        for arm in FAMILIES:
            used = [h for h in history if h["mutation"] == arm]
            arms.append({"seed": seed, "condition": cond, "arm": arm, "usage": len(used),
                "mean_reward": statistics.mean(h["reward"] for h in used) if used else None,
                "valid_rate": statistics.mean(h["outcome"]["valid"] for h in used) if used else None,
                "eligible_rate": statistics.mean(h["outcome"]["eligible"] for h in used) if used else None,
                "selection_rate": statistics.mean(h["selected"] for h in used) if used else None,
                "mean_proposal_probability": statistics.mean(h["decision"]["probabilities"][arm] for h in history)})
        counts = Counter(h["mutation"] for h in history)
        contexts = {h["decision"]["context_key"]: h["decision"]["context"] for h in history}
        if cond == "adaptive":
            model = ContextualUCB(13)
            model.tables = r["proposal_posterior"]
            for key, ctx in contexts.items():
                d = model.decision(Context(**ctx), 11)
                hs = [h for h in history if h["decision"]["context_key"] == key]
                for arm in FAMILIES:
                    observed = [h for h in hs if h["mutation"] == arm]
                    context_checks.append({"seed": seed, "context_key": key, "arm": arm,
                        "final_probability": d["probabilities"][arm], "ucb": d["ucb"][arm],
                        "count": len(observed), "observed_mean_reward": statistics.mean(h["reward"] for h in observed) if observed else None})
        runs.append({"seed": seed, "condition": cond, "slots": len(history),
            "valid_rate": statistics.mean(h["outcome"]["valid"] for h in history),
            "eligible_rate": statistics.mean(h["outcome"]["eligible"] for h in history),
            "mean_reward": statistics.mean(h["reward"] for h in history),
            "evaluated_candidates": len(r["candidates"])-1,
            "invalid_slots": sum(h["status"] == "INVALID" for h in history),
            "top_arm_usage_fraction": max(counts.values()) / len(history),
            "usage_entropy": -sum(n/len(history)*math.log2(n/len(history)) for n in counts.values()),
            "contexts": len(contexts), "distribution_changed": any(len(set(h["decision"]["probabilities"].values())) > 1 for h in history) if cond == "adaptive" else False,
            "proposal_cpu_seconds": sum(h["proposal_cpu_seconds"]+h["update_cpu_seconds"] for h in history),
            "candidate_cpu_seconds": sum(c["preparation_cpu_seconds"]+c["training_and_evaluation_cpu_seconds"] for c in r["candidates"]),
            "peak_rss_bytes": max(c["peak_rss_bytes"] for c in r["candidates"])})
    assert len(runs) == 32 and len(events) == 2560
    return events, generations, arms, runs, context_checks


def summarize(input_dir, frozen_dir, evolution_dir, output):
    out, root = Path(output), Path(frozen_dir)
    out.mkdir(parents=True, exist_ok=False)
    manifest = read(root / "manifest.json")
    assert manifest["protocol"] == run.PROTOCOL
    flat, curves, unique, distances = [], [], [], []
    replay_count = 0
    for c in manifest["cases"]:
        paths = list(Path(input_dir).rglob(c["file"]))
        assert len(paths) == 1
        r, b = read(paths[0]), read(root / "cases" / c["file"])
        assert old.file_digest(root / "cases" / c["file"]) == c["bundle_sha256"] == r["source_bundle_sha256"]
        assert r["all_selection_checkpoints_reproduced"]
        engine = rep.Engine(b["genome"])
        for p in r["paired"]:
            for key, tasks in (("selection", b["archived_final"]["tasks"]), ("holdout", b["holdout_tasks"])):
                if tasks:
                    analysis.validate_evaluation(p[key], tasks, engine)
                    replay_count += 1
        for key, tasks in (("full_info_selection", b["archived_final"]["tasks"]), ("full_info_holdout", b["holdout_tasks"])):
            if tasks:
                analysis.validate_evaluation(r[key], tasks, engine)
                replay_count += 1
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
                "holdout_tasks": len(b["holdout_tasks"]), "core_solvable_D": r["core_solvable_metrics"]["D"] if r["core_solvable_metrics"] else None,
                **{f"B{x}_{key}": val[f"B{x}"] if val else None for x in (50, 80, 90) for key, val in (("selection", s), ("holdout", h))}}
            flat.append(row)
            for p in r["paired"]:
                curves.append({"seed": r["seed"], "condition": ref["condition"], "generation": ref["generation"], "budget": p["budget"],
                    "S_selection": p["selection"]["success_rate"], "S_holdout": p["holdout"]["success_rate"] if h else None})
        distances.append({"seed": r["seed"], "game_hash": r["game_hash"], "population": b["population"],
            "selection_distances": dict(Counter(t["distance"] for t in b["archived_final"]["tasks"])),
            "holdout_distances": dict(Counter(t["distance"] for t in b["holdout_tasks"]))})
    flat.sort(key=lambda r: (r["condition"], r["seed"], r["generation"]))
    assert len(flat) == 352
    events, generations, arms, proposal_runs, context_checks = proposal_audit(evolution_dir)
    endpoints = []
    for cond in run.CONDITIONS:
        for seed in run.SEEDS:
            rows = [r for r in flat if (r["seed"], r["condition"]) == (seed, cond)]
            ep = rep.endpoint(rows)
            ep.pop("changed_transitions")
            ep.update(seed=seed, condition=cond, final_B80_holdout=rows[-1]["B80_holdout"], final_selection_D=rows[-1]["D_selection"],
                holdout_D_change=rows[-1]["D_holdout"]-ep["first_eligible_D_holdout"] if ep["first_eligible_D_holdout"] is not None and rows[-1]["D_holdout"] is not None else None,
                candidate_slots=80)
            endpoints.append(ep)
    paired = []
    for seed in run.SEEDS:
        a, b = [next(e for e in endpoints if e["seed"] == seed and e["condition"] == c) for c in ("adaptive", "uniform")]
        paired.append({"seed": seed, "adaptive": a, "uniform": b,
            "delta_final_D": a["G10_D_holdout"]-b["G10_D_holdout"] if a["G10_D_holdout"] is not None and b["G10_D_holdout"] is not None else None,
            "delta_final_success": a["final_holdout_success"]-b["final_holdout_success"] if a["final_holdout_success"] is not None and b["final_holdout_success"] is not None else None})
    conditions = {}
    for cond in run.CONDITIONS:
        es = [e for e in endpoints if e["condition"] == cond]
        ps = [p for p in proposal_runs if p["condition"] == cond]
        measured = [e for e in es if e["final_holdout_success"] is not None]
        conditions[cond] = {"first_eligibility": [e["first_eligible_generation"] for e in es],
            "eligibility_to_final_directions": dict(Counter(e["eligibility_to_final_direction"] for e in es)),
            "final_holdout_success_macro": statistics.mean(e["final_holdout_success"] for e in measured) if measured else None,
            "final_holdout_D_mean": statistics.mean(e["G10_D_holdout"] for e in measured) if measured else None,
            "final_selection_D_mean": statistics.mean(e["final_selection_D"] for e in es),
            "final_classes": dict(Counter(e["final_classification"] for e in es)),
            "valid_rate": statistics.mean(p["valid_rate"] for p in ps), "eligible_rate": statistics.mean(p["eligible_rate"] for p in ps),
            "mean_reward": statistics.mean(p["mean_reward"] for p in ps), "candidate_slots": sum(p["slots"] for p in ps),
            "candidate_cpu_seconds": sum(p["candidate_cpu_seconds"] for p in ps), "proposal_cpu_seconds": sum(p["proposal_cpu_seconds"] for p in ps)}
    metrics = {"status": "COMPLETED", "run": manifest["evolution_run"], "head": manifest["evolution_head"], "protocol": run.PROTOCOL,
        "evolution_runs": 32, "frontier_entries": 352, "unique_seed_worlds": len(unique),
        "holdout_pairs": sum(c["population"]["actual"] for c in manifest["cases"]),
        "holdout_shortage_worlds": sum(c["population"]["actual"] < 500 for c in manifest["cases"]),
        "reproduced_checkpoints": sum(len(r["paired"]) for r in unique), "verified_task_zero_replays": replay_count,
        "conditions": conditions, "paired": paired, "proposal_runs": proposal_runs,
        "audit_cpu_seconds": sum(r["cpu_seconds"] for r in unique), "peak_rss_bytes": max([r["peak_rss_bytes"] for r in unique]+[p["peak_rss_bytes"] for p in proposal_runs]),
        "counterfactual_limit": "Observed-arm association only; high UCB can reflect low evidence rather than high estimated reward. No untried mutations were evaluated or policy retuned."}
    io.write_json(out / "metrics.json", metrics)
    io.write_json(out / "counterfactual_proposal_audit.json", context_checks)
    io.write_json(out / "task_distance_distributions.json", distances)
    io.write_json(out / "proposal_events.json", events)
    for name, data in (("all_frontiers", flat), ("learning_curves", curves), ("endpoints", endpoints),
                       ("proposal_generations", generations), ("primitive_statistics", arms), ("proposal_runs", proposal_runs)):
        io.csv_write(out / (name + ".csv"), data)
    from .plots import plot
    plot(out, flat, generations, arms, endpoints, events, proposal_runs)
    print(conditions, flush=True)
