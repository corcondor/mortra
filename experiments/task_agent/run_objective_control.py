"""Preregistered eight-world mechanism/readout experiment, not a fresh cohort."""
import argparse
import collections
import copy
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

import numpy as np
import psutil

from . import online_eval
from .objective_control import ObjectiveControlPolicy, audit_fields
from .run_virtual_frontier_fresh70 import (
    FROZEN_SHA, digest, dump_model, load_model, read_json, source_audit,
    verify_registration,
)
from .run_virtual_frontier_pilot import ROOT, file_hash, save_json, write_csv
from .virtual_frontier import VirtualFrontierPolicy, build_frontier_fields

SEEDS = tuple(range(73000000, 73000008))
POLICIES = ("fixed_generic", "fixed_task", "doob_generic", "doob_task",
            "deadline_generic", "deadline_task")
REPEATS = 10
MAX_STEPS = 4096
SOURCE_RUN = 36220511321
NEW_FILES = ("experiments/task_agent/objective_control.py",
             "experiments/task_agent/run_objective_control.py",
             "tests/test_objective_control.py",
             "docs/research/TASK-OBJECTIVE-CONTROL-20260927.md",
             ".github/workflows/task-objective-control.yml")


def config():
    return {"study": "registered retrospective mechanism pilot; no confirmatory generalization claim",
            "source_run": SOURCE_RUN, "world_seeds": list(SEEDS), "policies": list(POLICIES),
            "starting_snapshot_steps": 512, "tasks_per_world": 12, "max_steps": MAX_STEPS,
            "doob_repeats": REPEATS, "deterministic_repeats": 1,
            "rng_formula": "76000000 + world_index*10000 + task_id*100 + repeat",
            "execution_planner": "unchanged CachingSparsePlanner q=0.90",
            "source_weights": "unchanged: 1 or exp(progress before unknown action)",
            "deadline_objective": "maximize terminal weight reachable within remaining action budget; then minimize steps",
            "unknown_successors": "not predicted; existing separate virtual terminal per untried action",
            "all_policies_same_no_frontier_fallback": True,
            "finite_policy_also_computes_frozen_reference_fields_for_common_graph_interface": True,
            "primary_descriptive_endpoints": ["task success", "failure-capped steps"],
            "inference_unit": "world; average repeats within task before world aggregation",
            "bootstrap_seed": 76099999, "bootstrap_resamples": 20000,
            "pass_threshold": None, "no_outcome_tuning": True,
            "missing_worlds": "retained, never replaced",
            "resource_exhaustion": "RUN INCOMPLETE; not task failure"}


def snapshot():
    original = source_audit()
    original["experiment_files_sha256"] = {p: file_hash(ROOT / p) for p in NEW_FILES}
    original["source_run"] = SOURCE_RUN
    return original


def preregister(registration, output):
    output.mkdir(parents=True, exist_ok=False)
    manifest = verify_registration(registration)
    save_json(output / "source_snapshot.json", snapshot())
    save_json(output / "config.json", config())
    (output / "preregistration.md").write_bytes((ROOT / NEW_FILES[3]).read_bytes())
    selected = [r for r in manifest if r["seed"] in SEEDS]
    assert [r["seed"] for r in selected] == list(SEEDS)
    save_json(output / "selected_worlds.json", selected)
    hashes = {}
    for row in selected:
        if row["status"] != "ready":
            continue
        folder = registration / str(row["seed"])
        for name, key in (("genome.json", "genome_sha256"), ("tasks.json", "tasks_sha256"),
                          ("snapshot_512.json", "snapshot_512_sha256")):
            assert file_hash(folder / name) == row[key]
            hashes[f"{row['seed']}/{name}"] = file_hash(folder / name)
    save_json(output / "shared_input_sha256.json", hashes)
    save_json(output / "rng_seeds.json", {str(s): {
        str(t): [76000000 + i * 10000 + t * 100 + r for r in range(REPEATS)]
        for t in range(12)} for i, s in enumerate(SEEDS)})
    save_json(output / "registration_complete.json", {"policy_outcomes_run": 0,
              "fixed_worlds": len(SEEDS), "ready": sum(r["status"] == "ready" for r in selected),
              "config_sha256": file_hash(output / "config.json")})
    print(json.dumps(config()), flush=True)


class TraceEnv(online_eval.WorldEnv):
    def __init__(self, engine):
        super().__init__(engine)
        self.steps = 0
        self.trace = []

    def reset(self, state=None):
        self.steps, self.trace = 0, []
        return super().reset(state)

    def step(self, action):
        before = self.state
        after = super().step(action)
        self.steps += 1
        self.trace.append({"step": self.steps, "before": list(before),
                           "action": int(action), "after": list(after)})
        return after


class RecordingPolicy:
    def __init__(self, policy, sink, identity):
        self.policy, self.sink, self.identity = policy, sink, identity
        self.count = 0
        self.cpu = 0.0
        self.peak = psutil.Process().memory_info().rss

    def choose(self, *args):
        started = time.process_time()
        decision = self.policy.choose(*args)
        self.cpu += time.process_time() - started
        details = dict(self.policy.last_telemetry or {})
        self.sink.write(json.dumps({**self.identity, "decision": self.count, **details}) + "\n")
        self.count += 1
        self.peak = max(self.peak, psutil.Process().memory_info().rss)
        return decision


def episode(model_data, engine, task_row, policy_name, repeat, seed, sink):
    learner = load_model(model_data).core
    env = TraceEnv(engine)
    aware = policy_name.endswith("_task")
    if policy_name.startswith("fixed_"):
        policy = VirtualFrontierPolicy(task_aware=aware)
    else:
        policy = ObjectiveControlPolicy(policy_name.split("_")[0], aware, seed,
                                        lambda: MAX_STEPS - env.steps)
    identity = {"seed": task_row["seed"], "task_id": task_row["task_id"],
                "task_type": task_row["task_type"], "policy": policy_name, "repeat": repeat}
    recorded = RecordingPolicy(policy, sink, identity)
    planner = online_eval.CachingSparsePlanner(q=0.90)
    task = online_eval.task_from_spec(task_row["spec"])
    agent = online_eval.OnlineTaskAgent(learner, recorded, planner=planner,
                                       max_task_steps=MAX_STEPS, max_exploration_steps=MAX_STEPS)
    wall, cpu = time.perf_counter(), time.process_time()
    result = agent.run_task(env, task, tuple(task_row["start"]))
    assert recorded.count == result.exploration_steps
    assert env.steps == result.task_steps
    return {**identity, "rng_seed": seed, "success": bool(result.success),
            "task_steps": result.task_steps,
            "capped_steps": result.task_steps if result.success else MAX_STEPS,
            "exploration_steps": result.exploration_steps, "replans": result.replans,
            "failure_reason": result.failure_reason,
            "final_memory_accepting": bool(task.accepting(result.final_memory)),
            "cpu_seconds": time.process_time() - cpu, "wall_seconds": time.perf_counter() - wall,
            "exploration_policy_cpu_seconds": recorded.cpu,
            "sampled_peak_rss_bytes": max(recorded.peak, psutil.Process().memory_info().rss),
            "process_peak_rss_bytes_so_far": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            "states_at_end": len(learner.id_to_state)}, env.trace


def run_world(index, registration, prereg, old_runs, output):
    output.mkdir(parents=True, exist_ok=False)
    assert read_json(prereg / "config.json") == config()
    audit = snapshot()
    assert audit["experiment_files_sha256"] == read_json(prereg / "source_snapshot.json")["experiment_files_sha256"]
    save_json(output / "source_snapshot.json", audit)
    seed = SEEDS[index]
    row = next(r for r in verify_registration(registration) if r["seed"] == seed)
    save_json(output / "status.json", {"seed": seed, "status": "RUN INCOMPLETE"})
    if row["status"] != "ready":
        save_json(output / "status.json", {"seed": seed, "status": row["status"], "policy_failure": False})
        return
    folder = registration / str(seed)
    hashes = read_json(prereg / "shared_input_sha256.json")
    for name in ("genome.json", "tasks.json", "snapshot_512.json"):
        assert file_hash(folder / name) == hashes[f"{seed}/{name}"]
    from .checkpoint import Engine
    engine = Engine(read_json(folder / "genome.json"))
    model_data = read_json(folder / "snapshot_512.json")
    tasks = read_json(folder / "tasks.json")
    assert len(tasks) == 12
    old_path = list(old_runs.glob(f"**/{seed}/episodes.json"))
    assert len(old_path) == 1
    old = {(r["task_id"], r["policy"]): r for r in read_json(old_path[0])}
    save_json(output / "input_provenance.json", {"source_run": SOURCE_RUN,
              "old_episodes_sha256": file_hash(old_path[0]),
              "input_sha256": {n: hashes[f"{seed}/{n}"] for n in ("genome.json", "tasks.json", "snapshot_512.json")}})
    records, certificates, baseline_checks = [], [], []
    with (output / "telemetry.jsonl").open("x", encoding="utf-8") as sink, \
         (output / "trajectories.jsonl").open("x", encoding="utf-8") as trace_sink, \
         (output / "run.log").open("x", encoding="utf-8") as log:
        for task_row in tasks:
            learner = load_model(model_data).core
            start = tuple(task_row["start"])
            learner.get_or_add_id(start)  # Same starting-state registration as frozen OnlineTaskAgent.
            task = online_eval.task_from_spec(task_row["spec"])
            memory = task.advance(task.initial_memory, start)
            fields = build_frontier_fields(learner, start, task, memory)
            cert = {"seed": seed, "task_id": task_row["task_id"], **audit_fields(fields)}
            certificates.append(cert)
            save_json(output / "certificates.json", certificates)
            for policy in POLICIES:
                for repeat in range(REPEATS if policy.startswith("doob") else 1):
                    rng_seed = 76000000 + index * 10000 + task_row["task_id"] * 100 + repeat
                    result, trajectory = episode(model_data, engine, task_row, policy, repeat, rng_seed, sink)
                    if policy.startswith("fixed"):
                        historical = "task_virtual_frontier" if policy.endswith("task") else "virtual_frontier"
                        expected = old[task_row["task_id"], historical]
                        keys = ("success", "task_steps", "capped_steps", "exploration_steps", "replans", "failure_reason", "final_memory_accepting")
                        check = {"seed": seed, "task_id": task_row["task_id"], "policy": policy,
                                 "differences": {k: [expected[k], result[k]] for k in keys if expected[k] != result[k]}}
                        baseline_checks.append(check)
                        save_json(output / "baseline_reproduction.json", baseline_checks)
                        if check["differences"]:
                            raise AssertionError(f"Baseline reproduction mismatch: {check}")
                    records.append(result)
                    trace_sink.write(json.dumps({**{k: result[k] for k in ("seed", "task_id", "policy", "repeat", "success")},
                                                 "trajectory": trajectory}) + "\n")
                    sink.flush()
                    trace_sink.flush()
                    save_json(output / "episodes.json", records)
                    message = f"seed={seed} task={task_row['task_id']} policy={policy} repeat={repeat} success={result['success']} capped={result['capped_steps']}"
                    print(message, flush=True)
                    log.write(message + "\n")
                    log.flush()
            assert digest(model_data) == digest(read_json(folder / "snapshot_512.json"))
    assert len(records) == 12 * (4 + 2 * REPEATS)
    write_csv(output / "episodes.csv", records)
    save_json(output / "status.json", {"seed": seed, "status": "COMPLETE", "episodes": len(records),
              "baseline_reproductions": len(baseline_checks)})


def paired_interval(values):
    if not values:
        return None
    a = np.asarray(values, dtype=float)
    rng = np.random.default_rng(76099999)
    means = a[rng.integers(0, len(a), size=(20000, len(a)))].mean(axis=1)
    return {"worlds": len(a), "mean": float(a.mean()), "ci95_world_bootstrap": np.quantile(means, [.025, .975]).tolist(),
            "values": a.tolist()}


def summarize(runs, output):
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "source_snapshot.json", snapshot())
    statuses, records, certificates, checks, telemetry = [], [], [], [], []
    for seed in SEEDS:
        paths = list(runs.glob(f"**/{seed}/status.json"))
        assert len(paths) <= 1
        status = read_json(paths[0]) if paths else {"seed": seed, "status": "RUN INCOMPLETE"}
        statuses.append(status)
        if status["status"] != "COMPLETE":
            continue
        folder = paths[0].parent
        records.extend(read_json(folder / "episodes.json"))
        certificates.extend(read_json(folder / "certificates.json"))
        checks.extend(read_json(folder / "baseline_reproduction.json"))
        with (folder / "telemetry.jsonl").open(encoding="utf-8") as handle:
            for line in handle:
                item = json.loads(line)
                if "doob_row_error" in item:
                    telemetry.append((item["doob_row_error"], item["numeric_mode_agreement"]))
    complete_seeds = [s["seed"] for s in statuses if s["status"] == "COMPLETE"]
    task_means = []
    for seed in complete_seeds:
        for task in range(12):
            for policy in POLICIES:
                sub = [r for r in records if (r["seed"], r["task_id"], r["policy"]) == (seed, task, policy)]
                assert len(sub) == (REPEATS if policy.startswith("doob") else 1)
                task_means.append({"seed": seed, "task_id": task, "policy": policy,
                                   "success_rate": float(np.mean([r["success"] for r in sub])),
                                   "capped_steps": float(np.mean([r["capped_steps"] for r in sub]))})
    per_world = []
    for seed in complete_seeds:
        for policy in POLICIES:
            sub = [r for r in task_means if r["seed"] == seed and r["policy"] == policy]
            per_world.append({"seed": seed, "policy": policy,
                              "success_rate": float(np.mean([r["success_rate"] for r in sub])),
                              "mean_capped_steps": float(np.mean([r["capped_steps"] for r in sub]))})
    policy_results = {}
    for policy in POLICIES:
        sub = [r for r in per_world if r["policy"] == policy]
        raw = [r for r in records if r["policy"] == policy]
        policy_results[policy] = {"worlds": len(sub), "episodes": len(raw),
            "successes": sum(r["success"] for r in raw),
            "world_mean_success_rate": float(np.mean([r["success_rate"] for r in sub])) if sub else None,
            "world_mean_capped_steps": float(np.mean([r["mean_capped_steps"] for r in sub])) if sub else None,
            "cpu_seconds": sum(r["cpu_seconds"] for r in raw),
            "wall_seconds": sum(r["wall_seconds"] for r in raw),
            "exploration_policy_cpu_seconds": sum(r["exploration_policy_cpu_seconds"] for r in raw),
            "process_peak_rss_bytes_so_far": max((r["process_peak_rss_bytes_so_far"] for r in raw), default=0)}
    lookup = {(r["seed"], r["policy"]): r for r in per_world}
    paired = {}
    for column in ("generic", "task"):
        for method in ("doob", "deadline"):
            p, b = method + "_" + column, "fixed_" + column
            paired[p + "_minus_" + b] = {metric: paired_interval([
                lookup[s, p][metric] - lookup[s, b][metric] for s in complete_seeds])
                for metric in ("success_rate", "mean_capped_steps")}
    verified = [c for c in certificates if c["status"] == "VERIFIED"]
    alg = {"initial_graphs_audited": len(certificates), "graphs_with_frontier": len(verified),
           "undiscounted_applicable": sum(c["undiscounted_applicable"] for c in verified),
           "undiscounted_not_applicable": sum(not c["undiscounted_applicable"] for c in verified),
           "max_discounted_reconstruction_relative_error": max((c["discounted_certificate"]["reconstructed_field_relative_error"] for c in verified), default=0),
           "max_undiscounted_reconstruction_relative_error": max((c["undiscounted_certificate"]["reconstructed_field_relative_error"] for c in verified if c["undiscounted_applicable"]), default=0),
           "doob_decisions_checked": len(telemetry),
           "max_doob_row_error": max((t[0] for t in telemetry), default=0),
           "doob_numeric_mode_disagreements": sum(not t[1] for t in telemetry),
           "baseline_episode_reproductions": len(checks),
           "baseline_differences": sum(bool(c["differences"]) for c in checks)}
    summary = {"status": "COMPLETE" if len(complete_seeds) == len(SEEDS) else "INCOMPLETE",
               "scope": "8 previously observed fixed worlds; retrospective descriptive pilot, not fresh confirmation",
               "worlds_complete": len(complete_seeds), "worlds_fixed": len(SEEDS), "world_statuses": statuses,
               "config": config(), "policies": policy_results, "paired_world_differences": paired, "algebra": alg}
    save_json(output / "metrics.json", summary)
    save_json(output / "certificates.json", certificates)
    save_json(output / "baseline_reproduction.json", checks)
    for name, data in (("episodes", records), ("task_means", task_means), ("world_means", per_world)):
        if data:
            write_csv(output / (name + ".csv"), data)
    if complete_seeds:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        colors = ["#386cb0", "#386cb0", "#a65385", "#a65385", "#238b70", "#238b70"]
        labels = [p.replace("_", "\n") for p in POLICIES]
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.6))
        axes[0].bar(labels, [policy_results[p]["world_mean_success_rate"] * 100 for p in POLICIES], color=colors)
        axes[0].set_ylabel("Task success (%)")
        axes[0].set_ylim(0, 105)
        axes[1].bar(labels, [policy_results[p]["world_mean_capped_steps"] for p in POLICIES], color=colors)
        axes[1].set_ylabel("Failure-capped steps (lower is better)")
        fig.suptitle(f"Frozen MORTRA: exploration readout pilot | {len(complete_seeds)}/8 worlds\nDoob: 10 repeats/task; other methods: deterministic; old execution planner unchanged")
        fig.tight_layout()
        fig.savefig(output / "readout_comparison.png", dpi=170)
        plt.close(fig)
    lines = ["# Objective-derived exploration readout pilot", "", summary["scope"],
             f"Status: {summary['status']}; complete worlds: {len(complete_seeds)}/8", "",
             "Only exploration readout changes. World, task compiler, learner, terminal sources, and execution planner are frozen.",
             "Deadline optimizes a frontier proxy, not unknown task completion. It introduces no successor prediction.",
             "Doob sampling is a policy change; Doob argmax alone is algebraically unchanged.",
             "Algebraic scaling is a certificate, not a performance treatment.", "",
             "| Policy | Episodes | Success | Mean capped steps | CPU seconds |",
             "|---|---:|---:|---:|---:|"]
    for p, r in policy_results.items():
        lines.append(f"| {p} | {r['episodes']} | {r['world_mean_success_rate']} | {r['world_mean_capped_steps']} | {r['cpu_seconds']:.3f} |")
    lines += ["", "Process peak RSS is cumulative per world job. Timing includes common reference-field computation even for deadline readout.",
              "Success on the last allowed action retains the original executor's existing boundary semantics.",
              "Confidence intervals resample worlds after averaging repeats within task. No outcome-defined pass threshold is used.",
              "Full numerical certificates, baseline replay checks, action traces and per-decision probabilities are retained."]
    (output / "REPORT.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("command", choices=("register", "world", "summary"))
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--prereg", type=Path)
    parser.add_argument("--old-runs", type=Path)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--index", type=int)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "register":
        preregister(args.registration, args.output)
    elif args.command == "world":
        run_world(args.index, args.registration, args.prereg, args.old_runs, args.output)
    else:
        summarize(args.runs, args.output)


if __name__ == "__main__":
    main()
