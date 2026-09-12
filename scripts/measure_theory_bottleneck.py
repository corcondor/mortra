"""Frozen-code single-factor study using the existing normal entry and evaluators."""
from pathlib import Path
from copy import deepcopy
from datetime import datetime, timezone
import argparse
import os
import subprocess
import sys
import time
import traceback

CONTROL = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(CONTROL))
from scripts.measure_persistent_learning import (
    ROOT, Theory, Domain, make_suite, read, write, digest, source_seal, evaluate,
    metrics, replay, final_comparison)
from scripts.analyze_capacity_study import lineage
from scripts.analyze_theory_bottleneck import (
    trace_blocked, ablations, profile_queries, profile_later_steps, candidate_census, scheduler_trace, jsonl)


def make_configs(plan):
    result = {}
    for cap in plan["term_caps"]:
        for name in plan["domains"]:
            config = read(ROOT/f"configs/{name}.json")
            config["budget"].update(plan["budget_override"], term_size=cap)
            config["seed"] = plan["seed"]
            result[f"{name}-size-{cap}"] = config
    name = "theory-fold-frames"
    if name in plan["domains"]:
        extended = deepcopy(result[f"{name}-size-{plan['term_caps'][0]}"])
        extended["budget"]["cycles"] = plan["extended_cycles"]
        result["theory-fold-frames-extended"] = extended
    return result


def compare_inputs(configs, plan):
    for name in plan["domains"]:
        base = deepcopy(configs[f"{name}-size-{plan['term_caps'][0]}"])
        base["budget"].pop("term_size")
        for cap in plan["term_caps"]:
            trial = deepcopy(configs[f"{name}-size-{cap}"])
            if trial["budget"].pop("term_size") != cap or trial != base:
                raise ValueError("single-factor term comparison changed another input")
    if "theory-fold-frames-extended" in configs:
        base = deepcopy(configs[f"theory-fold-frames-size-{plan['term_caps'][0]}"])
        extended = deepcopy(configs["theory-fold-frames-extended"])
        base["budget"].pop("cycles")
        if extended["budget"].pop("cycles") != plan["extended_cycles"] or extended != base:
            raise ValueError("scheduler comparison changed more than cycle cap")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--development-smoke", action="store_true")
    args = parser.parse_args()
    out = args.output.resolve()
    out.mkdir(parents=True, exist_ok=False)
    plan = read(args.plan)
    if args.development_smoke:
        plan.update(domains=["theory-ring"], term_caps=[9, 12], heldout_contexts=1,
                    evaluation_repeats=1, normalised_proof_calls=2)
        plan["budget_override"]["cycles"] = 30
    sha = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    if sha != plan["baseline_sha"] and not args.development_smoke:
        raise ValueError("frozen mathematical SHA mismatch")
    subprocess.run(["git", "diff", "--exit-code", "--", "math_os_prototype",
                    "scripts/run_theory_formation.py", "scripts/verify_theory_formation.py"], cwd=ROOT, check=True)
    configs = make_configs(plan)
    compare_inputs(configs, plan)
    source = source_seal()
    record = {"mathematical_sha": sha, "source_seal": source, "plan": plan,
        "control_sha": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=CONTROL, text=True).strip(),
        "repository": os.environ.get("GITHUB_REPOSITORY"), "ref": os.environ.get("GITHUB_REF"),
        "run_id": os.environ.get("GITHUB_RUN_ID"), "generated_at": datetime.now(timezone.utc).isoformat(),
        "development_only": args.development_smoke, "commands": [], "results": {}, "errors": [],
        "infrastructure_passed": False}
    write(out/"verification.json", record)
    write(out/"plan.json", plan)
    with (out/"environment.txt").open("w", encoding="utf-8") as stream:
        subprocess.run([sys.executable, "-m", "pip", "freeze"], stdout=stream, check=True)
    suites, oracles, initial = {}, {}, {}
    for key, config in configs.items(): write(out/(key+"-config.json"), config)
    # ALL held-out inputs and initial results are frozen before ANY learning.
    for name in plan["domains"]:
        config = configs[f"{name}-size-{plan['term_caps'][0]}"]
        suite = make_suite(config, plan["heldout_seed"], plan["heldout_contexts"])
        d = Domain(config["domain"])
        oracle = {r["id"]: d.settle(r["left"], r["right"], r["kind"]) for r in suite}
        k0 = Theory(config).snapshot()
        result = evaluate(k0, suite, oracle, repeats=plan["evaluation_repeats"], proof_node_budget=plan["proof_node_budget"])
        if not 0 < result["summary"]["solved_count"] < len(suite):
            raise ValueError("K0 must contain solved and unsolved tasks; no retuning")
        suites[name], oracles[name], initial[name] = suite, oracle, result
        for label, data in [("heldout", suite), ("oracle", oracle), ("K0", k0), ("K0-heldout", result)]:
            write(out/f"{name}-{label}.json", data)
    record["heldout_hashes"] = {k: digest(v) for k, v in suites.items()}
    write(out/"verification.json", record)
    # Insertion order runs both cap9 controls and the complete blocked-parent
    # diagnosis before a larger term bound is ever passed to a learner.
    for key, config in configs.items():
        name = next(n for n in plan["domains"] if key.startswith(n+"-"))
        directory = out/key
        directory.mkdir()
        started = time.perf_counter()
        command = [sys.executable, str(CONTROL/"scripts/observe_theory_run.py"),
                   "--config", str(out/(key+"-config.json")), "--output", str(directory/"normal"),
                   "--observations", str(directory/"observations"),
                   "--cycle-marks", "1000", "4000", "12000", "--proof-marks",
                   str(plan["normalised_proof_calls"]), str(plan["scheduler_proof_calls"])]
        record["commands"].append(command)
        write(out/"verification.json", record)
        try:
            with (directory/"normal.log").open("w", encoding="utf-8") as log:
                subprocess.run(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT,
                               timeout=plan["process_watchdog_seconds"], check=True)
            normal_wall = time.perf_counter()-started
            state = read(directory/"normal/state.json")
            verification = read(directory/"normal/verification.json")
            if verification["sha"] != sha:
                raise AssertionError("normal entry ran a different checkout")
            if not verification["execution_completed"] or not verification["sources_unchanged"]:
                raise AssertionError("normal execution failed")
            if read(directory/"normal/input.json")["source_seal"] != source:
                raise AssertionError("source seal changed")
            regression = replay(state)
            write(directory/"regression.json", regression)
            if not regression["passed"]: raise AssertionError("independent replay failed")
            observations = directory/"observations"
            trajectory = []
            for file in [*sorted(observations.glob("cycle-*.json")), *sorted(observations.glob("proof-*.json")), directory/"normal/state.json"]:
                snapshot = read(file)
                result = evaluate(snapshot, suites[name], oracles[name], repeats=plan["evaluation_repeats"], proof_node_budget=plan["proof_node_budget"])
                label = "final" if file.name == "state.json" else file.stem
                write(directory/(label+"-heldout.json"), result)
                measurement = metrics(snapshot)
                measurement.update(snapshot=label, heldout=result["summary"],
                    capability_change=final_comparison(initial[name], result), lineage=lineage(snapshot))
                trajectory.append(measurement)
            write(directory/"trajectory.json", trajectory)
            row = trajectory[-1]
            row.update(normal_wall_seconds=normal_wall, observer=read(observations/"observer.json"),
                       diagnostic_cycle_target=config["budget"]["cycles"], regression=regression,
                       diagnostic_censored=state["cycle"] < config["budget"]["cycles"] and state["stop_reason"] != "bounded_frontier_exhausted")
            row["ablations"] = ablations(state, suites[name], oracles[name], directory/"ablations", plan["evaluation_repeats"], plan["proof_node_budget"])
            row["remaining_active_concepts"] = scheduler_trace(state, observations, directory/"scheduler")
            row["candidate_census"] = candidate_census(state, observations, directory/"candidate-census.json")
            if config["budget"]["term_size"] == plan["term_caps"][0] and not key.endswith("extended"):
                row["size_blocked_trace"] = trace_blocked(state, observations, directory/"blocked-concepts")
                if not args.development_smoke and name == "theory-ring" and len(row["size_blocked_trace"]) != 29:
                    raise AssertionError("baseline blocked-parent count did not reproduce; stop sweep")
            # More expensive profiling is segregated from primary timings.
            if not args.development_smoke and config["budget"]["term_size"] in (plan["term_caps"][0], plan["term_caps"][-1]) and not key.endswith("extended"):
                profile_queries(state, suites[name], oracles[name], directory/"profile")
                checkpoint = observations/"cycle-1000.json"
                if checkpoint.exists(): profile_later_steps(read(checkpoint), directory/"profile-later-steps")
            row["complete_arm_wall_seconds"] = time.perf_counter()-started
            record["results"][key] = row
            print({"arm": key, "cycles": state["cycle"], "heldout": row["heldout"]["solved_count"],
                   "semantic_concepts": row["semantic_concepts_acquired"], "stop": state["stop_reason"]}, flush=True)
        except Exception:
            record["errors"].append({"arm": key, "traceback": traceback.format_exc()})
            write(out/"verification.json", record)
            # Never silently revise a failed run or mix a repaired continuation.
            raise
        write(out/"verification.json", record)
    record["sources_unchanged"] = source_seal() == source
    record["infrastructure_passed"] = record["sources_unchanged"] and not record["errors"]
    record["normalised_note"] = "proof-N checkpoints share exact existing prover-call count, not equal CPU work; differing input nodes and rule inspections remain reported"
    write(out/"verification.json", record)


if __name__ == "__main__":
    main()
