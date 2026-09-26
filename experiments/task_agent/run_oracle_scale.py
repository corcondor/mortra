"""Exact historical gate, then a preregistered independent 280-world diagnostic."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
import os
from pathlib import Path
import random
import resource
import time
import traceback

import numpy as np
import psutil

from . import checkpoint, online_eval
from .run_objective_control import TraceEnv, RecordingPolicy
from .oracle_diagnostics import OraclePolicy, REFERENCE, reference
from .run_virtual_frontier_fresh70 import (
    digest, dump_model, load_model, read_json, source_audit, verify_registration,
    freeze_tasks, utc,
)
from .run_virtual_frontier_pilot import ROOT, file_hash, save_json, write_csv
from .virtual_frontier import VirtualFrontierPolicy
from experiments.game_frontier_v11.designer import generate
from experiments.game_frontier_v11.world import game_hash

SEEDS = tuple(range(77000000, 77000280))
POLICIES = ("generic", "current_task", "oracle_source", "oracle_direct")
CAP = 4096
NEW_FILES = (
    "experiments/task_agent/oracle_diagnostics.py",
    "experiments/task_agent/run_oracle_scale.py",
    "tests/test_oracle_scale.py",
    "docs/research/TASK-ORACLE-SCALE-20260927.md",
    ".github/workflows/task-oracle-scale.yml",
)


def config():
    return {"world_seeds": list(SEEDS), "policies": list(POLICIES),
            "q": 0.90, "start_snapshot": 512, "task_generation_snapshot": 8192,
            "tasks_per_type": 3, "tasks_per_world": 12, "task_cap": CAP,
            "exploration_cap": CAP, "source_run": 36220511321,
            "basic_seed_offset": 720000, "branch_seed_offset": 820000,
            "bootstrap_seed": 77100000, "bootstrap_resamples": 20000,
            "sampling_unit": "world", "replacement": False,
            "primary": "oracle_source minus generic mean failure-capped steps",
            "source_target": "0.90**true_remaining_distance_after_unknown_action",
            "oracle_flags": ["oracle_source", "oracle_direct"],
            "learning_estimator_tested": False, "pass_threshold": None,
            "full_cohort_status": "INCOMPLETE if any fixed world unavailable or unfinished",
            "partial_scope": "descriptive, conditional on task generation and completion"}


def snapshot():
    data = source_audit()
    files = [ROOT / name for name in NEW_FILES] + sorted(REFERENCE.iterdir())
    data["new_files_sha256"] = {str(p.relative_to(ROOT)): file_hash(p) for p in files if p.is_file()}
    data["no_algorithm_tuning"] = True
    return data


def key(row):
    return (row["seed"], row["task_id"])


def reference_audit():
    for line in (REFERENCE / "SHA256SUMS.txt").read_text().splitlines():
        expected, name = line.split(maxsplit=1)
        assert file_hash(REFERENCE / name) == expected, name
    source = read_json(REFERENCE / "oracle_source_linear_result_780.json")
    headroom = read_json(REFERENCE / "oracle_headroom_result.json")
    old = read_json(REFERENCE / "oracle_source_linear_result.json")
    cross = read_json(REFERENCE / "oracle_120_crosscheck_summary.json")
    import csv
    with (REFERENCE / "oracle_120_same_task_condition_comparison.csv").open(newline="") as f:
        csv_rows = list(csv.DictReader(f))
    s, h = ({key(r): r for r in d["rows"]} for d in (source, headroom))
    shards = [r for i in range(4) for r in read_json(REFERENCE/f"osrc_{i}.json")["rows"]]
    assert len(shards) == 780 and {key(r): r for r in shards} == s
    assert len(s) == len(h) == len(source["rows"]) == len(headroom["rows"]) == 780
    assert s.keys() == h.keys()
    for k in s:
        assert s[k]["generic_steps"] == h[k]["generic_steps"]
        assert s[k]["current_steps"] == h[k]["current_steps"]
        assert s[k]["task_type"] == h[k]["task_type"]
    for r in old["rows"]:
        assert all(s[key(r)][k] == v for k, v in r.items())
    assert len(csv_rows) == len(cross["rows"]) == 120
    for a, b in zip(csv_rows, cross["rows"]):
        assert all(a[k] == str(v) for k, v in b.items())
    sm = np.mean([r["oracle_source_steps"] for r in s.values()])
    gm = np.mean([r["generic_steps"] for r in h.values()])
    om = np.mean([r["oracle_steps"] for r in h.values()])
    assert sm == source["summary"]["oracle_source"]["mean_steps"]
    return {"unique_tasks": 780, "worlds": 65, "old_120_exact_match": True,
            "bundle_checksums_match": True, "four_shards_exact_match": True,
            "crosscheck_csv_exact_match": True, "source_mean": float(sm),
            "generic_mean": float(gm), "oracle_mean": float(om),
            "recovery_fraction": float((gm-sm)/(gm-om))}


def register(registration, output):
    output.mkdir(parents=True, exist_ok=False)
    previous = verify_registration(registration)
    save_json(output / "source_snapshot.json", snapshot())
    save_json(output / "config.json", config())
    save_json(output / "reference_audit.json", reference_audit())
    save_json(output / "rng_seeds.json", {str(s): {"world": s, "basic": s+720000,
              "branch": s+820000} for s in SEEDS})
    (output / "preregistration.md").write_bytes((ROOT / NEW_FILES[3]).read_bytes())
    old_hashes = {r["game_hash"] for r in previous if "game_hash" in r}
    archived = read_json(ROOT / "experiments/task_agent/data/archived_worlds.json")
    old_hashes.update(game_hash(r["genome"]) for r in archived["worlds"].values())
    manifests, seen = [], set()
    for seed in SEEDS:
        folder = output / str(seed)
        folder.mkdir()
        genome = generate(random.Random(seed))
        gh = game_hash(genome)
        save_json(folder / "genome.json", genome)
        manifests.append({"seed": seed, "game_hash": gh,
                          "genome_sha256": file_hash(folder / "genome.json"),
                          "duplicate_prior": gh in old_hashes, "duplicate_fresh": gh in seen})
        seen.add(gh)
    save_json(output / "world_manifest.json", manifests)
    save_json(output / "registration_complete.json", {"worlds": len(manifests),
              "policy_outcomes_run": 0, "timestamp": utc(),
              "manifest_sha256": file_hash(output / "world_manifest.json")})
    print(json.dumps({"reference": reference_audit(), "new_worlds_registered": len(manifests)}), flush=True)


def episode(data, engine, task_row, policy_name, sink):
    learner = load_model(data).core
    task = online_eval.task_from_spec(task_row["spec"])
    wall, cpu = time.perf_counter(), time.process_time()
    env = TraceEnv(engine)
    if policy_name in ("generic", "current_task"):
        policy = VirtualFrontierPolicy(task_aware=policy_name == "current_task")
    else:
        policy = OraclePolicy(engine, learner.id_to_state, task, policy_name)
    oracle_setup_cpu = time.process_time() - cpu
    identity = {k: task_row[k] for k in ("seed", "task_id", "task_type")}
    identity["policy"] = policy_name
    recorded = RecordingPolicy(policy, sink, identity)
    planner = online_eval.CachingSparsePlanner(q=0.90)
    agent = online_eval.OnlineTaskAgent(learner, recorded, planner=planner,
                                       max_task_steps=CAP, max_exploration_steps=CAP)
    result = agent.run_task(env, task, tuple(task_row["start"]))
    assert env.steps == result.task_steps and recorded.count == result.exploration_steps
    row = {**identity, "success": bool(result.success), "task_steps": result.task_steps,
           "capped_steps": result.task_steps if result.success else CAP,
           "exploration_steps": result.exploration_steps, "replans": result.replans,
           "failure_reason": result.failure_reason, "final_memory": repr(result.final_memory),
           "final_memory_accepting": bool(task.accepting(result.final_memory)),
           "cpu_seconds": time.process_time()-cpu, "wall_seconds": time.perf_counter()-wall,
           "oracle_setup_cpu_seconds": oracle_setup_cpu if policy_name.startswith("oracle") else 0,
           "exploration_policy_cpu_seconds": recorded.cpu,
           "sampled_peak_rss_bytes": max(recorded.peak, psutil.Process().memory_info().rss),
           "process_peak_rss_bytes_so_far": resource.getrusage(resource.RUSAGE_SELF).ru_maxrss*1024,
           "states_known_at_end": len(learner.id_to_state)}
    return row, env.trace


def expected_reproduction(row):
    name = "oracle_source_linear_result_780.json" if row["policy"] == "oracle_source" else "oracle_headroom_result.json"
    expected = next(r for r in read_json(REFERENCE/name)["rows"] if key(r) == key(row))
    prefix = {"generic": "generic", "current_task": "current",
              "oracle_source": "oracle_source", "oracle_direct": "oracle"}[row["policy"]]
    return {"success": expected[prefix+"_success"], "capped_steps": expected[prefix+"_steps"]}


def execute_world(seed, folder, output, reproduce):
    engine = checkpoint.Engine(read_json(folder / "genome.json"))
    data = read_json(folder / "snapshot_512.json")
    tasks = read_json(folder / "tasks.json")
    assert len(tasks) == 12
    assert Counter(t["task_type"] for t in tasks) == dict.fromkeys(
        ("sequence", "all_of", "condition_then", "branch"), 3)
    rows, mismatches = [], []
    before = digest(data)
    save_json(output / "input_sha256.json", {n: file_hash(folder/n) for n in
              ("genome.json", "snapshot_512.json", "tasks.json")})
    with gzip.open(output / "telemetry.jsonl.gz", "xt", encoding="utf-8") as sink, \
         gzip.open(output / "trajectories.jsonl.gz", "xt", encoding="utf-8") as traces, \
         (output / "run.log").open("x", encoding="utf-8") as log:
        for task in tasks:
            for name in POLICIES:
                row, trajectory = episode(data, engine, task, name, sink)
                if reproduce:
                    expected = expected_reproduction(row)
                    differences = {k: [v, row[k]] for k, v in expected.items() if row[k] != v}
                    if differences:
                        mismatches.append({"seed": seed, "task_id": task["task_id"],
                                           "policy": name, "differences": differences})
                rows.append(row)
                traces.write(json.dumps({**{k: row[k] for k in ("seed", "task_id", "policy", "success")},
                                        "trajectory": trajectory}) + "\n")
                traces.flush()
                sink.flush()
                save_json(output / "episodes.json", rows)
                save_json(output / "reproduction_mismatches.json", mismatches)
                message = f"seed={seed} task={task['task_id']} policy={name} success={row['success']} capped={row['capped_steps']}"
                print(message, flush=True)
                log.write(message+"\n")
                log.flush()
                assert digest(data) == before
    write_csv(output / "episodes.csv", rows)
    save_json(output / "status.json", {"seed": seed, "status": "COMPLETE", "episodes": len(rows),
              "reproduction_mismatches": len(mismatches), "finished_at": utc()})


def shard(mode, index, registration, prereg, output):
    output.mkdir(parents=True, exist_ok=False)
    assert read_json(prereg / "config.json") == config()
    actual = snapshot()
    assert actual["new_files_sha256"] == read_json(prereg/"source_snapshot.json")["new_files_sha256"]
    save_json(output / "source_snapshot.json", actual)
    if mode == "reproduce":
        manifest = verify_registration(registration)[5*index:5*index+5]
    else:
        complete = read_json(prereg/"registration_complete.json")
        assert file_hash(prereg/"world_manifest.json") == complete["manifest_sha256"]
        manifest = read_json(prereg/"world_manifest.json")[10*index:10*index+10]
    for registered in manifest:
        seed = registered["seed"]
        out = output / str(seed)
        out.mkdir()
        save_json(out / "status.json", {"seed": seed, "status": "RUN INCOMPLETE", "started_at": utc()})
        try:
            if mode == "reproduce":
                if registered["status"] != "ready":
                    save_json(out / "status.json", {"seed": seed, "status": registered["status"], "policy_failure": False})
                    continue
                folder = registration / str(seed)
                for n, k in (("genome.json", "genome_sha256"), ("tasks.json", "tasks_sha256"),
                             ("snapshot_512.json", "snapshot_512_sha256")):
                    assert file_hash(folder/n) == registered[k]
            else:
                if registered["duplicate_prior"] or registered["duplicate_fresh"]:
                    save_json(out / "status.json", {"seed": seed, "status": "duplicate_world_retained", "policy_failure": False})
                    continue
                source = prereg / str(seed) / "genome.json"
                assert file_hash(source) == registered["genome_sha256"]
                (out / "genome.json").write_bytes(source.read_bytes())
                engine = checkpoint.Engine(read_json(source))
                wall, cpu = time.perf_counter(), time.process_time()
                snapshots = checkpoint.train_snapshots(engine)
                data = dump_model(snapshots[512])
                assert dump_model(load_model(data)) == data
                save_json(out / "snapshot_512.json", data)
                tasks, failures = freeze_tasks(snapshots[8192], seed)
                specs = [{"seed": seed, "task_id": i, "task_type": kind,
                          "start": list(start), "spec": spec}
                         for i, (kind, start, spec) in enumerate(tasks)]
                save_json(out / "tasks.json", specs)
                save_json(out / "task_registration.json", {"seed": seed, "timestamp": utc(),
                          "policy_outcomes_run": 0, "tasks": len(specs), "failures": failures,
                          "wall_seconds": time.perf_counter()-wall, "cpu_seconds": time.process_time()-cpu})
                if failures:
                    save_json(out / "status.json", {"seed": seed, "status": "task_generation_unavailable",
                              "failures": failures, "policy_failure": False})
                    print(f"seed={seed} task_generation_unavailable", flush=True)
                    continue
                folder = out
            execute_world(seed, folder, out, mode == "reproduce")
        except Exception:
            error = traceback.format_exc()
            save_json(out / "status.json", {"seed": seed, "status": "RUN INCOMPLETE",
                      "policy_failure": False, "exception": error})
            print(error, flush=True)


def aggregate(mode, runs, output):
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "source_snapshot.json", snapshot())
    seeds = list(range(73000000, 73000070)) if mode == "reproduce" else list(SEEDS)
    statuses, episodes, mismatches, worlds = [], [], [], []
    for seed in seeds:
        paths = list(runs.glob(f"**/{seed}/status.json"))
        assert len(paths) <= 1
        status = read_json(paths[0]) if paths else {"seed": seed, "status": "RUN INCOMPLETE"}
        statuses.append(status)
        if status["status"] != "COMPLETE":
            continue
        records = read_json(paths[0].parent/"episodes.json")
        assert len(records) == 48 and len({(r["task_id"], r["policy"]) for r in records}) == 48
        episodes.extend(records)
        mismatches.extend(read_json(paths[0].parent/"reproduction_mismatches.json"))
        worlds.append({"seed": seed, **{p: float(np.mean([r["capped_steps"] for r in records
                       if r["policy"] == p])) for p in POLICIES}})
    save_json(output/"world_statuses.json", statuses)
    save_json(output/"reproduction_mismatches.json", mismatches)
    save_json(output/"episodes.json", episodes)
    if episodes:
        write_csv(output/"episodes.csv", episodes)
        write_csv(output/"world_means.csv", worlds)
    counts = dict(Counter(r["status"] for r in statuses))
    expected_keys = {key(r) for r in read_json(REFERENCE/"oracle_source_linear_result_780.json")["rows"]}
    actual_keys = {key(r) for r in episodes}
    gate = mode == "reproduce" and not mismatches and actual_keys == expected_keys and len(episodes) == 3120
    result = {"phase": mode, "fixed_worlds": len(seeds), "completed_worlds": len(worlds),
              "unique_tasks": len(actual_keys), "episodes": len(episodes), "status_counts": counts,
              "all_fixed_worlds_complete": len(worlds) == len(seeds),
              "analysis_scope": "full cohort" if len(worlds) == len(seeds) else "PARTIAL / DESCRIPTIVE",
              "reproduction_gate_passed": gate, "reproduction_mismatches": len(mismatches),
              "policies": {}, "world_paired": {}, "no_outcome_tuning": True}
    for p in POLICIES:
        sub = [r for r in episodes if r["policy"] == p]
        result["policies"][p] = {"n": len(sub), "successes": sum(r["success"] for r in sub),
             "mean_capped_steps": float(np.mean([r["capped_steps"] for r in sub])) if sub else None,
             "median_capped_steps": float(np.median([r["capped_steps"] for r in sub])) if sub else None,
             "exploration_episodes": sum(r["exploration_steps"] > 0 for r in sub),
             "cpu_seconds": sum(r["cpu_seconds"] for r in sub),
             "wall_seconds": sum(r["wall_seconds"] for r in sub),
             "peak_process_rss_bytes": max((r["process_peak_rss_bytes_so_far"] for r in sub), default=0)}
    if worlds:
        w = np.asarray([[r[p] for p in POLICIES] for r in worlds])
        rng = np.random.default_rng(77100000)
        # Resample worlds jointly; never resample individual task rows.
        sample = w[rng.integers(0, len(w), size=(20000, len(w)))].mean(axis=1)
        for i, p in enumerate(POLICIES[1:], 1):
            d, bs = w[:, i]-w[:, 0], sample[:, i]-sample[:, 0]
            result["world_paired"][p+"_minus_generic"] = {
                "mean": float(d.mean()), "median_world_difference": float(np.median(d)),
                "ci95": np.quantile(bs, [.025, .975]).tolist(),
                "worlds_better": int((d < 0).sum()), "worlds_worse": int((d > 0).sum()),
                "worlds_tied": int((d == 0).sum())}
        g, _, s, o = w.mean(axis=0)
        denom = sample[:, 0]-sample[:, 3]
        valid = denom > 0
        result["headroom_recovery"] = {
            "ratio_of_mean_differences": float((g-s)/(g-o)) if g > o else None,
            "bootstrap_nonpositive_denominator": int((~valid).sum()),
            "ci95": np.quantile((sample[valid, 0]-sample[valid, 2])/denom[valid], [.025, .975]).tolist()
                    if np.any(valid) else None,
            "causal_attribution": False}
        table = {(r["seed"], r["task_id"], r["policy"]): r for r in episodes}
        worse = []
        for seed, task_id in sorted(actual_keys):
            baseline = table[seed, task_id, "generic"]
            for p in POLICIES[1:]:
                r = table[seed, task_id, p]
                if r["capped_steps"] > baseline["capped_steps"]:
                    worse.append({"seed": seed, "task_id": task_id, "task_type": r["task_type"],
                                  "policy": p, "generic_steps": baseline["capped_steps"],
                                  "steps": r["capped_steps"], "difference": r["capped_steps"]-baseline["capped_steps"]})
        save_json(output/"worse_cases.json", worse)
        if worse:
            write_csv(output/"worse_cases.csv", worse)
        by_type = []
        for typ in ("sequence", "all_of", "condition_then", "branch"):
            for p in POLICIES:
                sub = [r for r in episodes if r["task_type"] == typ and r["policy"] == p]
                by_type.append({"task_type": typ, "policy": p, "n": len(sub),
                                "successes": sum(r["success"] for r in sub),
                                "mean_steps": float(np.mean([r["capped_steps"] for r in sub]))})
        write_csv(output/"by_task_type.csv", by_type)
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        fig, axes = plt.subplots(1, 2, figsize=(12, 4.8))
        labels = ["Generic", "Current\ntask", "Oracle source\n+ frozen field", "Oracle\ndirect"]
        for ax, values, title in (
            (axes[0], [result["policies"][p]["mean_capped_steps"] for p in POLICIES], "Mean capped task steps (lower is better)"),
            (axes[1], [100*result["policies"][p]["successes"]/result["policies"][p]["n"] for p in POLICIES], "Task success (%)")):
            bars = ax.bar(labels, values, color=["#526777", "#237f77", "#aa536f", "#b68a34"])
            ax.bar_label(bars, fmt="%.2f", padding=3)
            ax.set_title(title)
            ax.set_ylim(0, max(values)*1.15)
        fig.suptitle(f"{mode}: {len(worlds)}/{len(seeds)} worlds, {len(actual_keys)} tasks | oracle arms are privileged diagnostics")
        fig.tight_layout()
        fig.savefig(output/"comparison.png", dpi=160)
        plt.close(fig)
    save_json(output/"metrics.json", result)
    (output/"REPORT.md").write_text(
        "# Oracle source diagnostic\n\n" + json.dumps(result, indent=2) +
        "\n\n![Saved results](comparison.png)\n\nNo outcome-driven algorithm changes. "
        "Oracle methods use privileged true transitions and are not learned policies. "
        "Process memory peaks are cumulative within a shard.\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k not in ("config",)}), flush=True)
    if mode == "reproduce" and not gate:
        raise RuntimeError("REPRODUCTION GATE FAILED; fresh cohort must not start")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("register", "reproduce", "fresh", "summary"))
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--prereg", type=Path)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--index", type=int)
    parser.add_argument("--phase", choices=("reproduce", "fresh"))
    args = parser.parse_args()
    if args.command == "register":
        register(args.registration, args.output)
    elif args.command == "summary":
        aggregate(args.phase, args.runs, args.output)
    else:
        shard(args.command, args.index, args.registration, args.prereg, args.output)


if __name__ == "__main__":
    main()
