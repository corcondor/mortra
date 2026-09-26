"""Preregistered fresh-world evaluation; imports the unchanged pilot executor."""
from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import random
import subprocess
import sys
import time
import traceback

import numpy as np

from . import checkpoint
from .run_virtual_frontier_pilot import (
    FROZEN_PATHS, POLICIES, ROOT, episode, file_hash, save_json, write_csv,
)
from experiments.game_frontier_v11.designer import generate
from experiments.game_frontier_v11.world import game_hash

FROZEN_SHA = "24c44da50aac2c084a91fdd9f6754f0429da9350"
REPORT_SHA = "3b69e943531e7d3b182442e43a245f0cdbdcc65a"
SEEDS = tuple(range(73000000, 73000070))
BOOTSTRAP_SEED = 74000000
BOOTSTRAPS = 20000
MARGIN = 0.05
N_SHARDS = 14
TASKS_EACH = 3
PREREG = "docs/research/TASK-VIRTUAL-FRONTIER-FRESH70-20260926.md"
RUNNER = "experiments/task_agent/run_virtual_frontier_fresh70.py"
FROZEN = tuple(sorted(set(FROZEN_PATHS) | {
    "experiments/task_agent/virtual_frontier.py",
    "experiments/task_agent/run_virtual_frontier_pilot.py",
    "experiments/game_frontier_v1/world.py",
    "experiments/game_frontier_v11/designer.py",
    "tests/test_virtual_frontier.py",
}))


def utc():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def source_audit():
    hashes = {}
    for name in FROZEN:
        baseline = subprocess.check_output(["git", "show", f"{FROZEN_SHA}:{name}"], cwd=ROOT)
        actual = (ROOT / name).read_bytes()
        if actual != baseline:
            raise RuntimeError(f"Frozen source is not byte-identical: {name}")
        hashes[name] = hashlib.sha256(actual).hexdigest()
    for name in (RUNNER, PREREG, "tests/test_virtual_frontier_fresh70.py",
                 ".github/workflows/task-virtual-frontier-fresh70.yml"):
        hashes[name] = file_hash(ROOT / name)
    return {
        "timestamp": utc(), "algorithm_commit": FROZEN_SHA, "pilot_report_commit": REPORT_SHA,
        "runner_commit": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "branch": os.environ.get("GITHUB_REF_NAME"), "source_sha256": hashes,
        "git_status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
        "all_frozen_files_byte_identical": True, "command": sys.argv,
        "run_id": os.environ.get("GITHUB_RUN_ID"), "python": sys.version,
    }


def config():
    return {
        "world_seeds": list(SEEDS), "policies": list(POLICIES), "q": 0.90,
        "source": "exp(task.progress(memory_before_unknown_action))",
        "starting_snapshot_steps": 512, "task_generation_snapshot_steps": 8192,
        "task_seed_basic_offset": 720000, "task_seed_branch_offset": 820000,
        "tasks_per_type": TASKS_EACH, "tasks_per_world": 12,
        "basic_attempt_limit": 50000, "branch_attempt_limit": 100000,
        "failure_cap": 4096, "max_task_steps": 4096, "max_exploration_steps": 4096,
        "bootstrap_unit": "world", "bootstrap_resamples": BOOTSTRAPS,
        "bootstrap_seed": BOOTSTRAP_SEED, "ci": "95% percentile, numpy linear quantiles",
        "relative_equivalence_margin": [-MARGIN, MARGIN],
        "equivalence_rule": "95% CI for mean R_w wholly inside [-0.05,+0.05], all 70 worlds required",
        "world_replacement": "never; engineering failure retained as RUN INCOMPLETE",
        "task_unavailability": "retain fixed world; no policies; confirmatory primary INCOMPLETE",
        "policy_order": list(POLICIES), "worlds_per_shard": 5, "shards": N_SHARDS,
    }


def dump_model(learner):
    c = learner.core
    expected = {"num_actions", "state_to_id", "id_to_state", "node_visits", "action_visits", "counts", "dest_map"}
    assert set(vars(c)) == expected
    return {
        "num_actions": c.num_actions, "states": [list(s) for s in c.id_to_state],
        "state_to_id": [[list(s), i] for s, i in c.state_to_id.items()],
        "node_visits": list(c.node_visits.items()),
        "action_visits": [[list(k), v] for k, v in c.action_visits.items()],
        "counts": [[list(k), list(v.items())] for k, v in c.counts.items()],
        "dest_map": [[list(k), v] for k, v in c.dest_map.items()],
    }


def load_model(data):
    learner = checkpoint.Learner(data["num_actions"])
    c = learner.core
    c.id_to_state = [tuple(s) for s in data["states"]]
    c.state_to_id = {tuple(s): i for s, i in data["state_to_id"]}
    c.node_visits = dict(data["node_visits"])
    c.action_visits = {tuple(k): v for k, v in data["action_visits"]}
    c.counts = {tuple(k): dict(v) for k, v in data["counts"]}
    c.dest_map = {tuple(k): v for k, v in data["dest_map"]}
    assert {s: i for i, s in enumerate(c.id_to_state)} == c.state_to_id
    return learner


def task_failure_reason(learner, kind):
    """Post-failure structural diagnostics only; never extend generator attempts."""
    edges = checkpoint.modal_edges(learner)
    if len(edges) < 4:
        return "insufficient_reachable_states"
    distances = [checkpoint.distances(edges, u) for u in range(len(edges))]
    if not any(3 <= d <= 10 for ds in distances for d in ds.values()):
        return "no_eligible_3_10_step_target"
    if kind != "branch":
        return "other_deterministic_generator_failure"
    has_construction = False
    for ds in distances:
        for a, d_a in ds.items():
            if not 2 <= d_a <= 5:
                continue
            ca = [d for d in distances[a].values() if 8 <= d <= 16]
            if not ca:
                continue
            for b, d_b in ds.items():
                if a == b or not 4 <= d_b <= 8:
                    continue
                cb = [d for d in distances[b].values() if 2 <= d <= 5]
                if not cb:
                    continue
                has_construction = True
                if d_a + max(ca) >= d_b + min(cb) + 4:
                    return "other_deterministic_generator_failure"
    return "insufficient_branch_path_length_contrast" if has_construction else "no_eligible_branch_construction"


def freeze_tasks(learner, seed):
    tasks, failures = [], []
    for kind, generator, offset in (
        ("basic", checkpoint.generate_basic_tasks, 720000),
        ("branch", checkpoint.generate_branch_tasks, 820000),
    ):
        try:
            tasks.extend(generator(learner, seed + offset, n=TASKS_EACH))
        except RuntimeError as exc:
            expected = "branch task generation failed" if kind == "branch" else "task generation failed"
            if not exc.args or not isinstance(exc.args[0], tuple) or exc.args[0][0] != expected:
                raise
            failures.append({"generator": kind, "category": task_failure_reason(learner, kind),
                             "exception": repr(exc), "seed": seed + offset})
    return tasks, failures


def register(output):
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "source_snapshot.json", source_audit())
    save_json(output / "config.json", config())
    (output / "preregistration.md").write_bytes((ROOT / PREREG).read_bytes())
    save_json(output / "rng_seeds.json", {str(s): {"world": s, "basic": s + 720000,
              "branch": s + 820000} for s in SEEDS})
    archived = read_json(ROOT / "experiments/task_agent/data/archived_worlds.json")
    archived_hashes = {game_hash(w["genome"]) for w in archived["worlds"].values()}
    rows, seen = [], set()
    # All genomes are saved before any model training or task construction.
    for seed in SEEDS:
        folder = output / str(seed)
        folder.mkdir()
        try:
            genome = generate(random.Random(seed))
            gh = game_hash(genome)
        except Exception:
            row = {"seed": seed, "status": "generation_engineering_failure",
                   "exception": traceback.format_exc(), "matches_archived_world": False,
                   "duplicates_new_world": False}
            save_json(folder / "registration.json", row)
            rows.append(row)
            continue
        save_json(folder / "genome.json", genome)
        row = {"seed": seed, "game_hash": gh, "genome_sha256": file_hash(folder / "genome.json"),
               "matches_archived_world": gh in archived_hashes,
               "duplicates_new_world": gh in seen, "status": "genome_registered"}
        rows.append(row)
        seen.add(gh)
    save_json(output / "world_manifest.json", rows)
    if any(r["matches_archived_world"] or r["duplicates_new_world"] for r in rows):
        raise RuntimeError("Freshness violation; retained all genomes, no replacement or policy evaluation")
    with (output / "run.log").open("x", encoding="utf-8") as log:
        for row in rows:
            seed, folder = row["seed"], output / str(row["seed"])
            if row["status"] == "generation_engineering_failure":
                continue
            engine = checkpoint.Engine(read_json(folder / "genome.json"))
            start = time.perf_counter()
            snapshots = checkpoint.train_snapshots(engine)
            snapshot_data = dump_model(snapshots[512])
            restored = load_model(json.loads(json.dumps(snapshot_data)))
            assert vars(restored.core) == vars(snapshots[512].core)
            assert digest(dump_model(restored)) == digest(snapshot_data)
            save_json(folder / "snapshot_512.json", snapshot_data)
            tasks, failures = freeze_tasks(snapshots[8192], seed)
            specs = [{"seed": seed, "task_id": i, "task_type": kind, "start": list(start_state),
                      "spec": spec} for i, (kind, start_state, spec) in enumerate(tasks)]
            save_json(folder / "tasks.json", specs)
            row.update({"status": "task_generation_unavailable" if failures else "ready",
                        "failures": failures, "tasks": len(specs), "states_512": len(snapshots[512].i2s),
                        "states_8192": len(snapshots[8192].i2s), "registration_seconds": time.perf_counter() - start,
                        "tasks_sha256": file_hash(folder / "tasks.json"),
                        "snapshot_512_sha256": file_hash(folder / "snapshot_512.json"), "registered_at": utc()})
            if not failures:
                assert collections.Counter(t["task_type"] for t in specs) == {
                    "sequence": 3, "all_of": 3, "condition_then": 3, "branch": 3}
            save_json(folder / "registration.json", row)
            save_json(output / "world_manifest.json", rows)
            message = f"REGISTER seed={seed} status={row['status']} tasks={len(specs)} failures={failures}"
            print(message, flush=True)
            log.write(message + "\n")
            log.flush()
    save_json(output / "registration_complete.json", {
        "timestamp": utc(), "worlds": len(rows), "ready": sum(r["status"] == "ready" for r in rows),
        "unavailable": sum(r["status"] == "task_generation_unavailable" for r in rows),
        "manifest_sha256": file_hash(output / "world_manifest.json"), "policy_outcomes_run": 0})


def verify_registration(registration):
    complete = read_json(registration / "registration_complete.json")
    assert file_hash(registration / "world_manifest.json") == complete["manifest_sha256"]
    rows = read_json(registration / "world_manifest.json")
    assert [r["seed"] for r in rows] == list(SEEDS)
    assert read_json(registration / "config.json") == config()
    return rows


def evaluate_world(registration, row, output):
    seed = row["seed"]
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "registration.json", row)
    if row["status"] != "ready":
        status = "task_generation_unavailable" if row["status"] == "task_generation_unavailable" else "RUN INCOMPLETE"
        save_json(output / "status.json", {"seed": seed, "status": status,
                  "policy_failure": False, "policy_episodes": 0})
        return
    source = registration / str(seed)
    for filename, key in (("genome.json", "genome_sha256"), ("tasks.json", "tasks_sha256"),
                          ("snapshot_512.json", "snapshot_512_sha256")):
        assert file_hash(source / filename) == row[key]
    engine = checkpoint.Engine(read_json(source / "genome.json"))
    model_data = read_json(source / "snapshot_512.json")
    snapshot = load_model(model_data)
    tasks = read_json(source / "tasks.json")
    assert len(tasks) == 12
    records = []
    save_json(output / "status.json", {"seed": seed, "status": "RUN INCOMPLETE", "started_at": utc()})
    with (output / "mechanism_telemetry.jsonl").open("x", encoding="utf-8") as sink, \
         (output / "run.log").open("x", encoding="utf-8") as log:
        for task in tasks:
            for policy in POLICIES:
                identity = {"seed": seed, "task_id": task["task_id"], "task_type": task["task_type"], "policy": policy}
                record = {**identity, **episode(snapshot.core, engine, task["spec"], task["start"], policy, sink, identity)}
                assert digest(dump_model(snapshot)) == digest(model_data)
                records.append(record)
                save_json(output / "episodes.json", records)
                write_csv(output / "episodes.csv", records)
                sink.flush()
                message = f"EPISODE {identity} success={record['success']} capped={record['capped_steps']} signal={record['task_signal_available_decisions']} changed={record['field_changed_decisions']}"
                print(message, flush=True)
                log.write(message + "\n")
                log.flush()
    save_json(output / "status.json", {"seed": seed, "status": "COMPLETE", "episodes": len(records), "finished_at": utc()})


def shard(registration, index, output):
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "source_snapshot.json", source_audit())
    rows = verify_registration(registration)
    assert 0 <= index < N_SHARDS
    failures = []
    for row in rows[5 * index:5 * index + 5]:
        folder = output / str(row["seed"])
        try:
            evaluate_world(registration, row, folder)
        except Exception:
            folder.mkdir(parents=True, exist_ok=True)
            error = traceback.format_exc()
            save_json(folder / "status.json", {"seed": row["seed"], "status": "RUN INCOMPLETE",
                      "policy_failure": False, "exception": error})
            failures.append(row["seed"])
            print(error, flush=True)
    save_json(output / "shard_status.json", {"index": index, "incomplete_worlds": failures})


def endpoint(values, seed=BOOTSTRAP_SEED):
    a = np.asarray(values, dtype=float)
    if not len(a):
        return {"n_worlds": 0, "mean": None, "median": None, "ci95": None, "lower": 0, "higher": 0, "tied": 0}
    assert np.all(np.isfinite(a))
    rng = np.random.default_rng(seed)
    means = a[rng.integers(0, len(a), size=(BOOTSTRAPS, len(a)))].mean(axis=1)
    return {"n_worlds": len(a), "mean": float(a.mean()), "median": float(np.median(a)),
            "ci95": np.quantile(means, [.025, .975], method="linear").tolist(),
            "lower": int(np.sum(a < 0)), "higher": int(np.sum(a > 0)), "tied": int(np.sum(a == 0)),
            "raw_world_values": a.tolist()}


def pair_world(records):
    table = {(r["task_id"], r["policy"]): r for r in records}
    assert len(table) == len(records) == 48
    tasks = sorted({r["task_id"] for r in records})
    assert tasks == list(range(12))
    pairs = []
    for t in tasks:
        rows = {p: table[t, p] for p in POLICIES}
        g, a, f = (rows[p] for p in ("virtual_frontier", "task_virtual_frontier", "frontier_t0"))
        pairs.append({"seed": g["seed"], "task_id": t, "task_type": g["task_type"],
                      **{p + "_capped": rows[p]["capped_steps"] for p in POLICIES},
                      **{p + "_success": rows[p]["success"] for p in POLICIES},
                      "D_task": a["capped_steps"] - g["capped_steps"],
                      "G_task": g["capped_steps"] - f["capped_steps"],
                      "success_task_minus_generic": int(a["success"]) - int(g["success"]),
                      "success_generic_minus_frontier": int(g["success"]) - int(f["success"])})
    means = {p: float(np.mean([table[t, p]["capped_steps"] for t in tasks])) for p in POLICIES}
    d = float(np.mean([p["D_task"] for p in pairs]))
    world = {"seed": records[0]["seed"], "tasks": len(tasks), "D_w": d,
             "G_w": float(np.mean([p["G_task"] for p in pairs])),
             "R_w": d / means["virtual_frontier"] if means["virtual_frontier"] else None,
             **{p + "_mean_capped": means[p] for p in POLICIES},
             **{p + "_success_rate": float(np.mean([table[t, p]["success"] for t in tasks])) for p in POLICIES},
             "success_task_minus_generic": float(np.mean([p["success_task_minus_generic"] for p in pairs])),
             "success_generic_minus_frontier": float(np.mean([p["success_generic_minus_frontier"] for p in pairs]))}
    return pairs, world


def mechanism_world(records):
    a = [r for r in records if r["policy"] == "task_virtual_frontier"]
    out = {"seed": records[0]["seed"], "tasks": len(a)}
    for key in ("exploration_decisions", "task_signal_available_decisions", "field_changed_decisions",
                "virtual_nodes_total", "field_solve_seconds", "constant_source_roundoff_corrections"):
        out[key] = sum(r[key] for r in a)
    n, s, c = (out[k] for k in ("exploration_decisions", "task_signal_available_decisions", "field_changed_decisions"))
    out.update({"source_variation_fraction": s / n if n else None,
                "changed_fraction_all": c / n if n else None, "changed_fraction_given_signal": c / s if s else None,
                "tasks_with_changes": sum(r["has_changed_decision"] for r in a), "world_has_changes": c > 0,
                "virtual_nodes_max": max(r["virtual_nodes_max"] for r in a),
                "virtual_nodes_mean": out["virtual_nodes_total"] / n if n else None,
                "max_field_residual": max(r["max_field_residual"] for r in a)})
    return out


def audit_telemetry(path, records):
    counts = collections.defaultdict(lambda: [0, 0, 0])
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            key = (item["task_id"], item["policy"])
            assert item["exploration_decision"] == counts[key][0]
            counts[key][0] += 1
            counts[key][1] += bool(item.get("task_signal_available"))
            counts[key][2] += bool(item.get("field_changed"))
            if item.get("field_changed"):
                assert item["policy"] == "task_virtual_frontier"
                assert item["task_signal_available"]
                assert item["selected_action"] != item["generic_counterfactual_action"]
    expected_keys = {(r["task_id"], r["policy"]) for r in records}
    assert set(counts) <= expected_keys
    for row in records:
        assert counts[row["task_id"], row["policy"]] == [row[k] for k in (
            "exploration_decisions", "task_signal_available_decisions", "field_changed_decisions")]
    return {"rows": sum(c[0] for c in counts.values()), "counts_match_episodes": True,
            "same_state_counterfactual_verified": True}


def aggregate(registration, runs, output):
    output.mkdir(parents=True, exist_ok=False)
    save_json(output / "source_snapshot.json", source_audit())
    registered = verify_registration(registration)
    task_pairs, world_pairs, mechanisms, all_records, statuses, compute, audits = [], [], [], [], [], [], []
    for row in registered:
        seed = row["seed"]
        paths = list(runs.glob(f"*/{seed}/status.json"))
        assert len(paths) <= 1, f"Duplicate execution for {seed}"
        status = read_json(paths[0]) if paths else {"seed": seed, "status": "RUN INCOMPLETE", "reason": "artifact missing"}
        statuses.append(status)
        if status["status"] != "COMPLETE":
            continue
        records = read_json(paths[0].parent / "episodes.json")
        audits.append({"seed": seed, **audit_telemetry(paths[0].parent / "mechanism_telemetry.jsonl", records)})
        pairs, world = pair_world(records)
        task_pairs.extend(pairs)
        world_pairs.append(world)
        mechanisms.append(mechanism_world(records))
        all_records.extend(records)
        for policy in POLICIES:
            sub = [r for r in records if r["policy"] == policy]
            compute.append({"seed": seed, "policy": policy,
                            "wall_seconds": sum(r["wall_seconds"] for r in sub),
                            "cpu_seconds": sum(r["cpu_seconds"] for r in sub),
                            "field_solve_seconds": sum(r["field_solve_seconds"] for r in sub),
                            "process_peak_rss_bytes_so_far": max(r["process_peak_rss_bytes_so_far"] for r in sub)})
    complete = len(world_pairs) == len(SEEDS)
    primary = endpoint([r["D_w"] for r in world_pairs])
    secondary = endpoint([r["G_w"] for r in world_pairs])
    relative_values = [r["R_w"] for r in world_pairs if r["R_w"] is not None]
    relative = endpoint(relative_values)
    equivalent = None
    if complete and len(relative_values) == 70:
        equivalent = relative["ci95"][0] >= -MARGIN and relative["ci95"][1] <= MARGIN
    policy_results = {}
    for p in POLICIES:
        sub = [r for r in all_records if r["policy"] == p]
        policy_results[p] = {"episodes": len(sub), "successes": sum(r["success"] for r in sub),
                             "mean_capped_steps": float(np.mean([r["capped_steps"] for r in sub])) if sub else None,
                             "cpu_seconds": sum(r["cpu_seconds"] for r in sub),
                             "wall_seconds": sum(r["wall_seconds"] for r in sub),
                             "peak_rss_bytes": max((r["process_peak_rss_bytes_so_far"] for r in sub), default=0)}
    mech = {key: sum(r[key] for r in mechanisms) for key in (
        "exploration_decisions", "task_signal_available_decisions", "field_changed_decisions",
        "tasks_with_changes", "world_has_changes", "field_solve_seconds", "constant_source_roundoff_corrections")}
    mech["max_field_residual"] = max((r["max_field_residual"] for r in mechanisms), default=0)
    n, s, c = (mech[k] for k in ("exploration_decisions", "task_signal_available_decisions", "field_changed_decisions"))
    mech.update({"source_variation_fraction": s / n if n else None, "changed_fraction_all": c / n if n else None,
                 "changed_fraction_given_signal": c / s if s else None})
    summary = {"confirmatory_status": "COMPLETE" if complete else "INCOMPLETE",
               "analysis_scope": "70-world confirmatory" if complete else "PARTIAL / DESCRIPTIVE; conditional on task-generatable and completed worlds",
               "fixed_worlds": 70, "analyzable_worlds": len(world_pairs),
               "task_generation_unavailable": sum(r["status"] == "task_generation_unavailable" for r in registered),
               "status_counts": dict(collections.Counter(s["status"] for s in statuses)),
               "primary_D": primary, "secondary_G": secondary, "relative_R": relative,
               "confirmatory_practical_equivalence": equivalent,
               "zero_relative_denominators": len(world_pairs) - len(relative_values),
               "success_difference": endpoint([r["success_task_minus_generic"] for r in world_pairs]),
               "secondary_success_difference": endpoint([r["success_generic_minus_frontier"] for r in world_pairs]),
               "policies": policy_results, "mechanism": mech,
               "task_wins_descriptive_only": {"lower": sum(p["D_task"] < 0 for p in task_pairs),
                   "higher": sum(p["D_task"] > 0 for p in task_pairs), "tied": sum(p["D_task"] == 0 for p in task_pairs)},
               "no_outcome_tuning": True, "config": config()}
    save_json(output / "summary.json", summary)
    save_json(output / "world_statuses.json", statuses)
    save_json(output / "telemetry_audit.json", audits)
    for name, data in (("paired_tasks.csv", task_pairs), ("paired_worlds.csv", world_pairs),
                       ("mechanism_worlds.csv", mechanisms), ("compute.csv", compute), ("episodes.csv", all_records)):
        if data:
            write_csv(output / name, data)
    save_json(output / "paired_worlds.json", world_pairs)
    lines = ["# Fresh 70-world virtual-frontier experiment", "",
             f"Confirmatory status: {summary['confirmatory_status']}",
             f"Analyzable worlds: {len(world_pairs)} / 70", f"Scope: {summary['analysis_scope']}", "",
             "Negative D or G means the first policy uses fewer capped steps.",
             "Bootstrap resampling uses worlds, never individual tasks.",
             f"Primary D: {primary}", f"Secondary G: {secondary}", f"Relative R: {relative}",
             f"Confirmatory practical equivalence: {equivalent}", "",
             "## Mechanism and interpretation", f"Source variation: {s}/{n}; action changes: {c}/{n}.",
             f"Changes conditional on signal: {c}/{s}; changed worlds: {mech['world_has_changes']}/{len(world_pairs)}.",
             "Zero source variation supports no available task information on these decisions.",
             "Source variation without action changes separates information from behavioral effect.",
             "Behavioral change and performance equivalence require both action changes and the preregistered relative CI criterion.",
             "Improvement/harm requires the frozen world-level D comparison; nonsignificance is not equivalence.",
             "When status is INCOMPLETE, these are conditional descriptive results, not the 70-world primary claim.",
             "Task-generation unavailability is not a policy failure. No worlds were replaced.",
             "Process peak RSS is cumulative within each shard, not isolated per-policy allocation."]
    (output / "REPORT.md").write_text("\n\n".join(lines) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit", "register", "shard", "aggregate"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--registration", type=Path)
    parser.add_argument("--runs", type=Path)
    parser.add_argument("--index", type=int)
    args = parser.parse_args()
    if args.command == "audit":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        save_json(args.output, source_audit())
    elif args.command == "register":
        register(args.output)
    elif args.command == "shard":
        shard(args.registration, args.index, args.output)
    else:
        aggregate(args.registration, args.runs, args.output)


if __name__ == "__main__":
    main()
