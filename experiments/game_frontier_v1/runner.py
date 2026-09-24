"""Pre-registered stages; no other research stack is imported."""
import argparse
import csv
from dataclasses import asdict
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time

import psutil

from .designer import CONDITIONS, FAMILIES, SIZE_FAMILIES, Feedback, choose, complexity, initial_game, mutate
from .frozen import BASE_COMMIT, BASELINE_SHA256_LF, ROOT, load_baseline
from .player import learn_game, random_policy
from .world import Engine, OpaqueMap, canonical, exact_oracle, game_hash, make_port

SEEDS = [201, 302, 403, 504, 605, 706, 807, 908]
STAGES = {1: {"generations": 5, "candidates": 4, "max_board": 16, "checkpoints": [250, 500, 1000, 2000], "seeds": SEEDS[:3]},
          2: {"generations": 10, "candidates": 8, "max_board": 32, "checkpoints": [250, 500, 1000, 2000, 4000, 8000], "seeds": SEEDS}}


def config(stage):
    return {"protocol": "autonomous-game-frontier-v1", "stage": stage, **STAGES[stage],
            "conditions": list(CONDITIONS), "trials": 30, "max_play_steps": 2048,
            "oracle_state_cap": 250000, "q": 0.90,
            "difficulty_area": "sum(1 - success_rate) over registered checkpoints; unweighted",
            "selection": "max B80, then max difficulty_area, then ascending game hash; parent eligible",
            "random_selection": "uniform valid SOLVABLE candidate; no player performance gate",
            "size_only_selection": "same objective/gate as MORTRA; only size/layout mutations",
            "final_learnability_gate": 0.80, "stage1_gate_budget": 2000,
            "opaque_labels": "per-candidate seeded random injection into 128-bit labels; exact observation",
            "evaluation_goal": "any goal confirmed by public is_goal; field sources only training-observed goals",
            "repeated_trials": "30 actual rollouts from same start; deterministic trials are not independent tasks",
            "goal_nonterminal": True, "hazard": "reset position only; no extra training resets",
            "invalid_action": "unsupported interaction self-loop; attempted move still updates facing",
            "rule_order": "ascending id; conditions see preceding effects; no recursive event emission",
            "oracle_cap": "UNRESOLVED_TOO_LARGE excluded even when a solution witness was found",
            "mutation_schedule": "paired seed/generation/slot seeds, uniform family; invalid attempts consume candidate budget",
            "random_baseline": "30 independent random action streams, same start and horizon, once per candidate",
            "memory_scope": "process high-water RSS through each candidate; not independent per-game peak",
            "core_loading": "unchanged AST definitions from SHA-verified baseline, no module preamble",
            "preregistration": "before Stage 1 outcomes; no outcome-based parameter adjustment"}


def derive(*parts):
    return int(hashlib.sha256(canonical(parts).encode()).hexdigest()[:15], 16)


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True, allow_nan=False) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def sources():
    files = [ROOT / "scripts/evaluate_cross_domain_generalization.py",
             ROOT / "scripts/evaluate_autonomous_game_frontier_v1.py",
             ROOT / "tests/test_autonomous_game_frontier_v1.py",
             ROOT / ".github/workflows/autonomous-game-frontier-v1.yml",
             ROOT / "docs/research/AUTONOMOUS-GAME-FRONTIER-V1-20260925.md",
             *sorted((ROOT / "experiments/game_frontier_v1").glob("*.py"))]
    return {str(p.relative_to(ROOT)).replace("\\", "/"): hashlib.sha256(p.read_text(encoding="utf-8").encode()).hexdigest() for p in files}


def provenance(cfg, seed):
    load_baseline()
    subprocess.run(["git", "-C", str(ROOT), "merge-base", "--is-ancestor", BASE_COMMIT, "HEAD"], check=True)
    return {"baseline_commit": BASE_COMMIT, "git_head": git("rev-parse", "HEAD"),
            "branch": git("branch", "--show-current"), "git_status": git("status", "--short"),
            "python": sys.version, "platform": platform.platform(), "seed": seed,
            "dependencies": {n: importlib.metadata.version(n) for n in ("numpy", "matplotlib", "psutil", "pytest")},
            "config_hash": hashlib.sha256(canonical(cfg).encode()).hexdigest(), "source_hashes_lf": sources(),
            "baseline_sha256_lf": BASELINE_SHA256_LF,
            "github_run_id": os.environ.get("GITHUB_RUN_ID"), "github_run_attempt": os.environ.get("GITHUB_RUN_ATTEMPT")}


def peak_rss():
    info = psutil.Process().memory_info()
    if hasattr(info, "peak_wset"):
        return int(info.peak_wset)
    import resource
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * (1 if sys.platform == "darwin" else 1024))


def evaluate_candidate(genome, cfg, seed, context, directory, prov):
    t0, cpu0 = time.perf_counter(), time.process_time()
    gh = game_hash(genome)
    gd = directory / "games" / gh
    write_json(gd / "genome.json", genome)
    engine = Engine(genome)
    oracle_start = time.process_time()
    oracle, oracle_states = exact_oracle(engine, cfg["oracle_state_cap"])
    oracle["cpu_seconds"] = time.process_time() - oracle_start
    del oracle_states
    record = {**context, "game_hash": gh, "seed": seed, "provenance": prov, **complexity(genome),
              "oracle": oracle, "learning": [], "random_policy": None,
              "b80": None, "b80_censored": True, "b80_label": ">" + str(cfg["checkpoints"][-1]),
              "difficulty_area": None, "final_success": None}
    if oracle["status"] == "SOLVABLE":
        opaque = OpaqueMap(derive(seed, gh, context["generation"], context["candidate"], "opaque"))
        train, evaluation = make_port(engine, opaque), make_port(engine, opaque)
        record["learning"] = learn_game(train, evaluation, cfg["checkpoints"], cfg["trials"], cfg["max_play_steps"], derive(seed, gh, "eval"))
        for item in record["learning"]:
            item["state_coverage"] = item["learned_states"] / oracle["reachable_states"]
            item["edge_coverage"] = item["learned_transitions"] / oracle["examined_transitions"]
            assert 0 <= item["state_coverage"] <= 1 and 0 <= item["edge_coverage"] <= 1
        random_start = time.process_time()
        record["random_policy"] = random_policy(make_port(engine, opaque), cfg["trials"], cfg["max_play_steps"], derive(seed, gh, "random"))
        record["random_policy_cpu_seconds"] = time.process_time() - random_start
        # Evaluator-only replay audit, after learning/evaluation have completed.
        for item in record["learning"]:
            first = item["evaluation"]["first_trial"]
            state = engine.initial
            sequence = [state]
            labels = [opaque.encode(state)]
            for action in first["actions"]:
                state = engine.step(state, action)
                sequence.append(state)
                labels.append(opaque.encode(state))
            assert labels == first["observations"]
            assert engine.is_goal(state) == first["success"]
            first["evaluator_state_sequence_sha256"] = hashlib.sha256(canonical([asdict(s) for s in sequence]).encode()).hexdigest()
            first["evaluator_replay_verified"] = True
        curve = record["learning"]
        record["b80"] = next((r["budget"] for r in curve if r["evaluation"]["success_rate"] >= 0.8), None)
        record["b80_censored"] = record["b80"] is None
        record["b80_label"] = str(record["b80"]) if record["b80"] is not None else record["b80_label"]
        record["difficulty_area"] = sum(1 - r["evaluation"]["success_rate"] for r in curve)
        record["final_success"] = curve[-1]["evaluation"]["success_rate"]
    else:
        record["b80_label"] = "NOT_EVALUATED"
        record["b80_censored"] = False
    record.update(wall_seconds=time.perf_counter() - t0, cpu_seconds=time.process_time() - cpu0,
                  process_peak_rss_bytes=peak_rss())
    # Each occurrence is preserved, including repeated genomes: no player caching.
    occurrence = f"g{context['generation']:02d}_c{context['candidate']:02d}"
    write_json(gd / occurrence / "oracle.json", {"provenance": prov, **oracle})
    write_json(gd / occurrence / "learning.json", {"provenance": prov, "checkpoints": record["learning"]})
    write_json(gd / occurrence / "evaluation.json", record)
    return record


def feedback(record):
    return Feedback(record["game_hash"], record["oracle"]["status"] == "SOLVABLE",
                    record["b80"], record["difficulty_area"] or 0.0, record["final_success"] or 0.0)


def run(stage, seed, condition, output):
    cfg = config(stage)
    if seed not in cfg["seeds"] or condition not in CONDITIONS:
        raise ValueError("unregistered seed/condition")
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=False)
    prov = provenance(cfg, seed)
    write_json(directory / "config.json", cfg)
    write_json(directory / "source_sha.json", prov["source_hashes_lf"])
    write_json(directory / "environment.json", prov)
    log = (directory / "run.log").open("x", encoding="utf-8", buffering=1)
    def emit(message):
        print(message, flush=True)
        log.write(message + "\n")
    candidates, frontier, mutations = [], [], []
    start = time.perf_counter()
    try:
        genome = initial_game(seed)
        parent = evaluate_candidate(genome, cfg, seed, {"generation": 0, "candidate": 0, "condition": condition,
                                    "parent_game_hash": None, "mutation": "initial"}, directory, prov)
        candidates.append(parent)
        frontier.append(parent)
        emit(f"Stage {stage} seed {seed} {condition} G0 B80={parent['b80_label']} S={parent['final_success']}")
        for generation in range(1, cfg["generations"] + 1):
            current, genomes = [], {}
            for slot in range(cfg["candidates"]):
                mutation_seed = derive(seed, generation, slot, "mutation")
                rng = random.Random(mutation_seed)
                family = rng.choice(SIZE_FAMILIES if condition == "size_only" else FAMILIES)
                context = {"generation": generation, "candidate": slot, "condition": condition,
                           "parent_game_hash": parent["game_hash"], "mutation": family, "mutation_seed": mutation_seed}
                try:
                    changed = mutate(genome, family, rng, cfg["max_board"])
                except ValueError as exc:
                    invalid = {**context, "status": "INVALID", "reason": str(exc), "provenance": prov}
                    mutations.append(invalid)
                    emit(f"G{generation} C{slot} {family} INVALID: {exc}")
                    continue
                result = evaluate_candidate(changed, cfg, seed, context, directory, prov)
                current.append(result)
                candidates.append(result)
                genomes[result["game_hash"]] = changed
                mutations.append({**context, "game_hash": result["game_hash"], "status": result["oracle"]["status"], "provenance": prov})
                emit(f"G{generation} C{slot} {family} {result['oracle']['status']} B80={result['b80_label']} S={result['final_success']} wall={result['wall_seconds']:.2f}s")
                write_json(directory / "partial_results.json", {"status": "RUNNING", "candidates": candidates, "frontier": frontier})
            offers = [feedback(c) for c in current]
            chosen = choose(condition, feedback(parent), offers, random.Random(derive(seed, generation, "selection")))
            selected_index = next((i for i, offer in enumerate(offers) if offer is chosen), None)
            selected = current[selected_index] if selected_index is not None else parent
            for mutation in mutations:
                if mutation["generation"] == generation:
                    mutation["selected"] = bool(selected_index is not None and mutation.get("game_hash") == selected["game_hash"]
                                                and mutation["candidate"] == selected["candidate"])
            if selected_index is not None:
                genome = genomes[chosen.game_hash]
            frontier.append({**selected, "selected_at_generation": generation, "selected_parent_hash": parent["game_hash"]})
            parent = selected
            emit(f"SELECT G{generation} {parent['game_hash'][:12]} B80={parent['b80_label']} S={parent['final_success']}")
        assert prov["source_hashes_lf"] == sources(), "source changed during run"
        result = {"status": "COMPLETED", "stage": stage, "seed": seed, "condition": condition,
                  "provenance": prov, "config": cfg, "candidates": candidates, "frontier": frontier,
                  "mutation_history": mutations, "wall_seconds": time.perf_counter() - start,
                  "process_peak_rss_bytes": peak_rss()}
        write_json(directory / "results.json", result)
        write_json(directory / "mutation_history.json", mutations)
        for gh in {c["game_hash"] for c in candidates}:
            occurrences = [c for c in candidates if c["game_hash"] == gh]
            gd = directory / "games" / gh
            write_json(gd / "oracle.json", {"provenance": prov, **occurrences[0]["oracle"]})
            write_json(gd / "learning.json", {"provenance": prov, "occurrences": [
                {"generation": c["generation"], "candidate": c["candidate"], "checkpoints": c["learning"]} for c in occurrences]})
            write_json(gd / "evaluation.json", {"provenance": prov, "occurrences": [
                {"generation": c["generation"], "candidate": c["candidate"],
                 "b80": c["b80"], "final_success": c["final_success"], "random_policy": c["random_policy"]} for c in occurrences]})
        export_tables(result, directory)
        (directory / "summary.md").write_text(
            f"# Completed Stage {stage}: seed {seed}, {condition}\n\n"
            f"Initial B80: {frontier[0]['b80_label']}. Final B80: {frontier[-1]['b80_label']}.\n"
            f"Final success: {frontier[-1]['final_success']}. See results.json for all candidates.\n"
            "Thirty deterministic repetitions are not thirty independent tasks.\n", encoding="utf-8")
        emit(f"COMPLETED stage={stage} seed={seed} condition={condition} candidates={len(candidates)} wall={result['wall_seconds']:.2f}s")
        return result
    except BaseException as exc:
        write_json(directory / "incomplete.json", {"status": "RUN_NOT_COMPLETED", "exception": type(exc).__name__,
                    "message": str(exc), "wall_seconds": time.perf_counter() - start, "provenance": prov,
                    "candidates": candidates, "frontier": frontier, "mutation_history": mutations})
        raise
    finally:
        log.close()


def csv_write(path, rows):
    if not rows:
        Path(path).write_text("", encoding="utf-8")
        return
    with Path(path).open("w", encoding="utf-8", newline="") as out:
        writer = csv.DictWriter(out, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def export_tables(result, directory):
    rows = []
    for gen, r in enumerate(result["frontier"]):
        rows.append({"seed": result["seed"], "condition": result["condition"], "generation": gen,
                     "game_hash": r["game_hash"], "parent_game_hash": r.get("selected_parent_hash", r["parent_game_hash"]),
                     **{k: r[k] for k in ("mutation", "board_width", "board_height", "objects", "rules", "rule_dependency_depth", "b80", "b80_label", "b80_censored", "difficulty_area", "final_success")},
                     "reachable_states": r["oracle"]["reachable_states"], "shortest_solution_length": r["oracle"]["shortest_solution_length"],
                     "oracle_status": r["oracle"]["status"], "process_peak_rss_bytes": r["process_peak_rss_bytes"],
                     "git_head": result["provenance"]["git_head"], "config_hash": result["provenance"]["config_hash"]})
    csv_write(directory / "frontier.csv", rows)
    learning = []
    for r in result["candidates"]:
        for c in r["learning"]:
            learning.append({"seed": result["seed"], "condition": result["condition"], "generation": r["generation"],
                             "candidate": r["candidate"], "game_hash": r["game_hash"],
                             **{k: c[k] for k in ("budget", "learned_states", "learned_transitions", "unique_graph_edges", "tried_state_action_fraction", "state_coverage", "edge_coverage", "training_cpu_seconds", "learner_serialized_bytes")},
                             **{k: c["evaluation"][k] for k in ("success_rate", "successes", "trials", "mean_steps", "evaluation_cpu_seconds", "reasoning_cpu_seconds", "K_bytes")},
                             "random_policy_success": r["random_policy"]["success_rate"],
                             "git_head": result["provenance"]["git_head"], "config_hash": result["provenance"]["config_hash"]})
    csv_write(directory / "learning_curves.csv", learning)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--stage", type=int, choices=(1, 2), required=True)
    parser.add_argument("--seed", type=int, required=True)
    parser.add_argument("--condition", choices=CONDITIONS, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    run(args.stage, args.seed, args.condition, args.output)
