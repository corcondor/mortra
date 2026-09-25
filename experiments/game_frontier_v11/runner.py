"""Preregistered generic-world pools, graph-reuse evaluation and evolution."""
import argparse
import hashlib
import json
from pathlib import Path
import random
import statistics
import time

from experiments.game_frontier_v1 import runner as base
from .designer import CONDITIONS, FAMILIES, SIZE_FAMILIES, Feedback, choose, generate, mutate
from .measurement import curve_metrics, full_information, learn, rule_relevance, sample_tasks
from .world import Engine, canonical, complexity, game_hash, oracle

CHECKPOINTS = [2**i for i in range(14)]
V1_COMMIT = "137d784f32884600a27da4e146db3a77103d665f"


def config(stage):
    return {"protocol": "generic-world-frontier-v1.1", "stage": stage,
            "seeds": base.SEEDS[:3] if stage == 1 else base.SEEDS, "conditions": list(CONDITIONS),
            "generations": 5 if stage == 1 else 10, "candidates": 6 if stage == 1 else 8,
            "tasks": 40 if stage == 1 else 100, "checkpoints": CHECKPOINTS[:12] if stage == 1 else CHECKPOINTS,
            "max_board": 16 if stage == 1 else 32, "initial_pool": 32, "oracle_cap": 250000,
            "dense_K_guard_bytes": 536870912, "horizon": 2048, "q": .90, "cutoff": 1e-7,
            "rule_order": "first matching rule; simultaneous RHS; invalid position/domain rejects whole assignment; default identity",
            "generator_prior": "random spatial unit-displacement rules, opaque action permutation, random guards/assignments/extra finite variables/layout",
            "generator_scope": "human-defined finite language and sampling distribution; not universal sampling or learned mutation grammar",
            "pool_gate": "complete graph, >=64 states, >=2 branching states, enough distinct tasks, median distance>=8, relevant rule, full-info>=.8",
            "task_sampling": "all reachable ordered pairs with distance>=4; seeded bin reservoirs; equal bin quota then random redistribution",
            "common_valid_gate": "complete graph, enough distinct tasks, at least one nonzero-relevance rule",
            "performance_gate": "common valid + full-info>=.8 + final learned>=.8",
            "random_gate": "common valid only; never use player performance",
            "selection": "max D, B80, B90, median successful steps; seeded random exact ties; parent eligible",
            "D": "trapezoidal integral of 1-S against log2 budget",
            "censored_order": "missing B80/B90 ranks above finite values, represented internally by max_budget+1; reported >max_budget",
            "seed_pairing": "same G0 across conditions, paired mutation slot seeds, tasks depend on genome not condition",
            "full_information_scope": "same core with complete graph; diagnostic not an upper bound on partial-model success",
            "resource_scope": "oracle/dense guard or external interruption is UNRESOLVED or RUN_NOT_COMPLETED, never task failure",
            "player_cache": "one K per checkpoint; memoize identical target solver requests without altering solver/readout bytecode",
            "freeze": "no algorithm tuning after outcomes; Stage 2 then stop"}


def sources():
    files = [base.ROOT / "scripts/evaluate_cross_domain_generalization.py",
             *sorted((base.ROOT / "experiments/game_frontier_v1").glob("*.py")),
             *sorted((base.ROOT / "experiments/game_frontier_v11").glob("*.py")),
             base.ROOT / "scripts/evaluate_autonomous_game_frontier_v11.py",
             base.ROOT / "tests/test_autonomous_game_frontier_v11.py",
             base.ROOT / ".github/workflows/autonomous-game-frontier-v11.yml",
             base.ROOT / "docs/research/AUTONOMOUS-GAME-FRONTIER-V11-20260925.md"]
    hashes = {str(p.relative_to(base.ROOT)).replace("\\", "/"): hashlib.sha256(p.read_text(encoding="utf-8").encode()).hexdigest() for p in files}
    import subprocess
    for name, sha in hashes.items():
        if name.startswith("experiments/game_frontier_v1/") or name == "scripts/evaluate_cross_domain_generalization.py":
            old = subprocess.check_output(["git", "-C", str(base.ROOT), "show", f"{V1_COMMIT}:{name}"])
            assert hashlib.sha256(old.replace(b"\r\n", b"\n")).hexdigest() == sha, name
    return hashes


def prepare(genome, cfg, seed):
    t0 = time.process_time()
    engine = Engine(genome)
    stats, graph = oracle(engine, cfg["oracle_cap"])
    r = {"game_hash": game_hash(genome), "oracle": stats, "valid": False, "tasks": [], "full_info": None,
         "relevance": None, "classification": "UNRESOLVED", "complexity": None}
    if graph is not None:
        r["complexity"] = complexity(genome, stats)
        if len(graph[0]) ** 2 * 8 > cfg["dense_K_guard_bytes"]:
            r["reason"] = "dense diagnostic resource guard"
        else:
            tasks, totals = sample_tasks(graph, cfg["tasks"], base.derive(seed, r["game_hash"], "tasks"))
            r.update(tasks=tasks, pair_population_by_bin=totals)
            if len(tasks) == cfg["tasks"]:
                r["task_median_distance"] = statistics.median(t["distance"] for t in tasks)
                r["tasks_sha256"] = hashlib.sha256(canonical(tasks).encode()).hexdigest()
                r["relevance"] = rule_relevance(genome, tasks, cfg["oracle_cap"])
                r["full_info"] = full_information(engine, graph, tasks, cfg["horizon"], base.derive(seed, r["game_hash"], "diagnostic"))
                r["valid"] = r["relevance"]["nonzero_relevance"]
                r["classification"] = "REASONER_LIMITED" if r["full_info"]["success_rate"] < .8 else "NOT_TRAINED"
            else:
                r["reason"] = "insufficient distinct reachable tasks with distance >=4"
    r["preparation_cpu_seconds"] = time.process_time() - t0
    return r


def train_candidate(genome, prepared, cfg, seed, context, directory):
    t0 = time.process_time()
    record = {**prepared, **context, "learning": [], "D": None, "B50": None, "B80": None, "B90": None,
              "final_success": None, "median_success_steps": 0}
    gd = directory / "games" / record["game_hash"]
    base.write_json(gd / "genome.json", genome)
    base.write_json(gd / "tasks.json", prepared["tasks"])
    if prepared["full_info"] is not None:
        rows = learn(Engine(genome), prepared["tasks"], cfg["checkpoints"], cfg["horizon"],
                     base.derive(seed, record["game_hash"], "player"), prepared["oracle"])
        record.update(learning=rows, **curve_metrics(rows))
        record["classification"] = ("REASONER_LIMITED" if prepared["full_info"]["success_rate"] < .8 else
                                      "LEARNED_SUCCESS" if record["final_success"] >= .8 else "EXPLORATION_LIMITED")
    record.update(training_and_evaluation_cpu_seconds=time.process_time() - t0, peak_rss_bytes=base.peak_rss())
    base.write_json(gd / f"g{context['generation']:02d}_c{context['candidate']:02d}.json", record)
    return record


def feedback(r):
    return Feedback(r["game_hash"], r["valid"], r["full_info"]["success_rate"] if r["full_info"] else 0,
                    r["final_success"] or 0, r["D"] or 0, r["B80"], r["B90"], r["median_success_steps"])


def run_condition(cfg, seed, condition, chosen, directory, prov, emit):
    directory.mkdir(parents=True, exist_ok=False)
    genome = chosen["genome"]
    parent = train_candidate(genome, chosen["prepared"], cfg, seed,
                              {"generation": 0, "candidate": 0, "mutation": "initial", "parent_hash": None}, directory)
    candidates, frontier, history = [parent], [parent], []
    for generation in range(1, cfg["generations"] + 1):
        current, genomes = [], []
        for slot in range(cfg["candidates"]):
            rng = random.Random(base.derive(seed, generation, slot, "mutation"))
            family = rng.choice(SIZE_FAMILIES if condition == "size_only" else FAMILIES)
            context = {"generation": generation, "candidate": slot, "mutation": family, "parent_hash": parent["game_hash"]}
            try:
                g = mutate(genome, family, rng, cfg["max_board"])
            except ValueError as exc:
                history.append({**context, "status": "INVALID", "reason": str(exc)})
                continue
            prepared = prepare(g, cfg, seed)
            result = train_candidate(g, prepared, cfg, seed, context, directory)
            candidates.append(result)
            current.append(result)
            genomes.append(g)
            history.append({**context, "status": result["classification"], "game_hash": result["game_hash"]})
            emit(f"{condition} G{generation} C{slot} {family} {result['classification']} D={result['D']} B80={result['B80']} S={result['final_success']}")
            base.write_json(directory / "partial_results.json", {"status": "RUNNING", "candidates": candidates, "frontier": frontier})
        offers = [feedback(r) for r in current]
        parent_offer = feedback(parent)
        selected_offer = choose(condition, parent_offer, offers, random.Random(base.derive(seed, generation, "selection")), cfg["checkpoints"][-1])
        index = next((i for i, c in enumerate(offers) if c is selected_offer), None)
        if index is not None:
            parent, genome = current[index], genomes[index]
        for h in history:
            if h["generation"] == generation:
                h["selected"] = index is not None and h.get("game_hash") == parent["game_hash"] and h["candidate"] == parent["candidate"]
        frontier.append(parent)
        emit(f"SELECT {condition} G{generation} D={parent['D']} B80={parent['B80']} S={parent['final_success']}")
    result = {"status": "COMPLETED", "stage": cfg["stage"], "seed": seed, "condition": condition, "config": cfg,
              "provenance": prov, "candidates": candidates, "frontier": frontier, "mutation_history": history}
    base.write_json(directory / "results.json", result)
    base.write_json(directory / "mutation_history.json", history)
    base.csv_write(directory / "frontier.csv", [{"generation": i, "game_hash": r["game_hash"],
         **{k: r[k] for k in ("D", "B50", "B80", "B90", "final_success", "classification")}} for i, r in enumerate(frontier)])
    return result


def run_seed(stage, seed, output):
    cfg = config(stage)
    if seed not in cfg["seeds"]:
        raise ValueError("unregistered seed")
    directory = Path(output)
    directory.mkdir(parents=True, exist_ok=False)
    prov = base.provenance(cfg, seed)
    prov["source_hashes_lf"] = sources()
    for name, value in (("config", cfg), ("environment", prov), ("source_sha", prov["source_hashes_lf"]),
                        ("rng_seeds", {"seed": seed, "derivation": "SHA256 canonical tuple first 15 hex digits", "paired": True})):
        base.write_json(directory / (name + ".json"), value)
    start = time.perf_counter()
    pool = []
    with (directory / "run.log").open("x", encoding="utf-8", buffering=1) as log:
        def emit(s):
            print(s, flush=True)
            log.write(s + "\n")
        try:
            for i in range(cfg["initial_pool"]):
                g = generate(random.Random(base.derive(seed, i, "initial-pool")))
                r = prepare(g, cfg, seed)
                eligible = (r["valid"] and r["oracle"]["reachable_states"] >= 64 and r["oracle"]["branching_states"] >= 2
                            and r["task_median_distance"] >= 8 and r["full_info"]["success_rate"] >= .8)
                item = {"slot": i, "genome": g, "prepared": r, "eligible": eligible}
                pool.append(item)
                base.write_json(directory / "initial_pool" / f"candidate_{i:02d}.json", item)
                emit(f"POOL {i}/32 eligible={eligible} states={r['oracle'].get('reachable_states')} full={r['full_info']['success_rate'] if r['full_info'] else None}")
            eligible = [r for r in pool if r["eligible"]]
            if not eligible:
                raise RuntimeError("NO_ELIGIBLE_G0: fixed initial pool exhausted; no adaptive regeneration")
            chosen = random.Random(base.derive(seed, "select-G0")).choice(eligible)
            base.write_json(directory / "chosen_g0.json", chosen)
            emit(f"G0 selected slot={chosen['slot']} hash={chosen['prepared']['game_hash']}")
            for condition in CONDITIONS:
                run_condition(cfg, seed, condition, chosen, directory / condition, prov, emit)
            assert sources() == prov["source_hashes_lf"]
            base.write_json(directory / "completed.json", {"status": "COMPLETED", "seed": seed, "stage": stage,
                            "wall_seconds": time.perf_counter() - start, "peak_rss_bytes": base.peak_rss()})
            emit("COMPLETED; no next stage is started by this process")
        except BaseException as exc:
            base.write_json(directory / "incomplete.json", {"status": "RUN_NOT_COMPLETED", "reason": str(exc),
                            "wall_seconds": time.perf_counter() - start, "provenance": prov})
            raise


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--stage", type=int, choices=(1, 2), required=True)
    p.add_argument("--seed", type=int, required=True)
    p.add_argument("--output", type=Path, required=True)
    a = p.parse_args()
    run_seed(a.stage, a.seed, a.output)
