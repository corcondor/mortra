"""Registered development pilot. This entry point cannot run the 70-world study."""
from __future__ import annotations

import argparse
import copy
import csv
import hashlib
import json
import os
from pathlib import Path
import resource
import subprocess
import sys
import time

import psutil

from . import checkpoint, online_eval
from .run_online import policy_for
from .virtual_frontier import NUMERICAL_TOLERANCE, VirtualFrontierPolicy

BASE_SHA = "6f9fc5018dd067fa693afb3b4d3ad1cfa04485e6"
ROOT = Path(__file__).resolve().parents[2]
POLICIES = ("structural", "frontier_t0", "virtual_frontier", "task_virtual_frontier")
STAGES = {"smoke": (2101,), "cohort": (2202, 2303, 2505)}
TASK_OFFSET = 600000
MAX_STEPS = 4096
TASKS_PER_TYPE = 3
FROZEN_PATHS = (
    "experiments/task_agent/core.py", "experiments/task_agent/exploration.py",
    "experiments/task_agent/online.py", "experiments/task_agent/online_eval.py",
    "experiments/task_agent/checkpoint.py", "experiments/task_agent/run_online.py",
    "experiments/task_agent/data/archived_worlds.json",
    "experiments/game_frontier_v1/frozen.py", "experiments/game_frontier_v11/world.py",
    "scripts/evaluate_cross_domain_generalization.py",
    "tests/test_task_agent.py", "tests/test_task_agent_fields.py",
)


def save_json(path, value):
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def file_hash(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_snapshot():
    changed = git("diff", "--name-only", BASE_SHA, "HEAD", "--", *FROZEN_PATHS,
                  "experiments/task_agent/data/registered", "reports/task-agent*")
    if changed:
        raise RuntimeError("frozen source or registered outputs changed: " + changed)
    paths = set(FROZEN_PATHS)
    paths.update(str(p.relative_to(ROOT)) for p in (ROOT / "experiments/task_agent").glob("*.py"))
    paths.update(("tests/test_virtual_frontier.py", "docs/research/TASK-VIRTUAL-FRONTIER-PILOT-20260926.md"))
    return {"base_sha": BASE_SHA, "commit_sha": git("rev-parse", "HEAD"),
            "branch": git("branch", "--show-current"), "git_status": git("status", "--short"),
            "frozen_paths_unchanged": True,
            "source_sha256": {p: file_hash(ROOT / p) for p in sorted(paths)},
            "command": sys.argv, "run_id": os.environ.get("GITHUB_RUN_ID"),
            "python": sys.version}


class Recorder:
    """Instrumentation around an unchanged policy/agent boundary."""
    def __init__(self, policy, sink, identity):
        self.policy, self.sink, self.identity = policy, sink, identity
        self.telemetry = []
        self.peak_rss = psutil.Process().memory_info().rss

    def choose(self, learner, world_state, task, memory):
        decision = self.policy.choose(learner, world_state, task, memory)
        details = dict(getattr(self.policy, "last_telemetry", None) or {})
        entry = {**self.identity, "exploration_decision": len(self.telemetry),
                 "world_state": repr(world_state), "memory": repr(memory),
                 "selected_action": decision.action, **details}
        self.sink.write(json.dumps(entry, sort_keys=True) + "\n")
        self.telemetry.append(details)
        self.peak_rss = max(self.peak_rss, psutil.Process().memory_info().rss)
        return decision


def episode(snapshot, engine, task_spec, start, name, sink, identity):
    learner = copy.deepcopy(snapshot)
    planner = online_eval.CachingSparsePlanner(q=0.90)
    if name in ("virtual_frontier", "task_virtual_frontier"):
        policy = VirtualFrontierPolicy(task_aware=name == "task_virtual_frontier")
    else:
        policy = policy_for(name, planner)
    recorded = Recorder(policy, sink, identity)
    agent = online_eval.OnlineTaskAgent(learner, recorded, planner=planner,
                                       max_task_steps=MAX_STEPS, max_exploration_steps=MAX_STEPS)
    task = online_eval.task_from_spec(task_spec)
    wall_start, cpu_start = time.perf_counter(), time.process_time()
    result = agent.run_task(online_eval.WorldEnv(engine), task, tuple(start))
    cpu_seconds, seconds = time.process_time() - cpu_start, time.perf_counter() - wall_start
    telemetry = recorded.telemetry
    assert len(telemetry) == result.exploration_steps
    previous_generic = None
    counterfactual_switches = 0
    for item in telemetry:
        current = item.get("generic_counterfactual_action")
        if current is not None:
            counterfactual_switches += previous_generic is not None and current != previous_generic
            previous_generic = current
    changed = sum(bool(item.get("field_changed")) for item in telemetry)
    result_row = {
        "success": result.success, "task_steps": result.task_steps,
        "capped_steps": result.task_steps if result.success else MAX_STEPS,
        "exploration_steps": result.exploration_steps, "replans": result.replans,
        "failure_reason": result.failure_reason,
        "final_memory": repr(result.final_memory),
        "final_memory_accepting": task.accepting(result.final_memory),
        "exploration_decisions": len(telemetry),
        "virtual_field_decisions": sum(bool(t.get("virtual_field_decision")) for t in telemetry),
        "task_signal_available_decisions": sum(bool(t.get("task_signal_available")) for t in telemetry),
        "field_changed_decisions": changed, "has_changed_decision": bool(changed),
        "generic_counterfactual_action_switches": counterfactual_switches,
        "virtual_nodes_total": sum(t.get("virtual_nodes", 0) for t in telemetry),
        "virtual_nodes_max": max((t.get("virtual_nodes", 0) for t in telemetry), default=0),
        "real_product_nodes_max": max((t.get("real_product_nodes", 0) for t in telemetry), default=0),
        "field_solve_seconds": sum(t.get("field_solve_seconds", 0) for t in telemetry),
        "max_field_residual": max((t.get("field_residual", 0) for t in telemetry), default=0),
        "constant_source_roundoff_corrections": sum(bool(t.get("constant_source_roundoff_corrected")) for t in telemetry),
        "wall_seconds": seconds, "cpu_seconds": cpu_seconds,
        "sampled_peak_rss_bytes": max(recorded.peak_rss, psutil.Process().memory_info().rss),
        "process_peak_rss_bytes_so_far": int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024),
        "states_known_at_end": len(learner.id_to_state),
    }
    result_row["virtual_nodes_mean"] = result_row["virtual_nodes_total"] / max(1, len(telemetry))
    return result_row


def write_csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows):
    aggregate, per_world = [], []
    for seed in [None] + sorted({r["seed"] for r in rows}):
        for policy in POLICIES:
            subset = [r for r in rows if r["policy"] == policy and (seed is None or r["seed"] == seed)]
            if not subset:
                continue
            result = {"seed": seed, "policy": policy, "episodes": len(subset),
                      "successes": sum(r["success"] for r in subset),
                      "mean_capped_steps": sum(r["capped_steps"] for r in subset) / len(subset),
                      "tasks_with_changed_decision": sum(r["has_changed_decision"] for r in subset)}
            for key in ("exploration_decisions", "virtual_field_decisions", "task_signal_available_decisions",
                        "field_changed_decisions", "field_solve_seconds", "wall_seconds", "cpu_seconds"):
                result[key] = sum(r[key] for r in subset)
            result["peak_process_rss_bytes"] = max(r["process_peak_rss_bytes_so_far"] for r in subset)
            (aggregate if seed is None else per_world).append(result)
    pairs = []
    for seed in sorted({r["seed"] for r in rows}):
        generic = {r["task_id"]: r for r in rows if r["seed"] == seed and r["policy"] == "virtual_frontier"}
        aware = {r["task_id"]: r for r in rows if r["seed"] == seed and r["policy"] == "task_virtual_frontier"}
        pairs.append({"seed": seed, "tasks": len(generic),
                      "task_minus_generic_mean_capped_steps": sum(aware[k]["capped_steps"] - generic[k]["capped_steps"] for k in generic) / len(generic),
                      "task_minus_generic_successes": sum(aware[k]["success"] - generic[k]["success"] for k in generic),
                      "task_faster": sum(aware[k]["capped_steps"] < generic[k]["capped_steps"] for k in generic),
                      "generic_faster": sum(aware[k]["capped_steps"] > generic[k]["capped_steps"] for k in generic)})
    return {"aggregate": aggregate, "per_world": per_world, "paired_worlds": pairs,
            "claim": "DEVELOPMENT mechanism pilot; no inferential performance claim"}


def run_stage(stage, output):
    output.mkdir(parents=True, exist_ok=False)
    snapshot = source_snapshot()
    save_json(output / "source_snapshot.json", snapshot)
    save_json(output / "config.json", {"stage": stage, "seeds": STAGES[stage],
              "policies": POLICIES, "task_seed_offset": TASK_OFFSET, "q": 0.90,
              "source": "exp(task.progress(memory_before_unknown_action))", "numerical_tolerance": NUMERICAL_TOLERANCE,
              "start_budget": 512, "task_generation_budget": 8192, "max_steps": MAX_STEPS,
              "basic_tasks_each": TASKS_PER_TYPE, "branch_tasks": TASKS_PER_TYPE,
              "policy_order": "fixed, as listed; wall-time ratios are engineering diagnostics"})
    save_json(output / "rng_seeds.json", {str(seed): {"basic": 120000 + TASK_OFFSET + seed,
              "branch": 220000 + TASK_OFFSET + seed} for seed in STAGES[stage]})
    rows, specs = [], []
    with (output / "mechanism_telemetry.jsonl").open("x", encoding="utf-8") as sink, \
         (output / "run.log").open("x", encoding="utf-8") as log:
        for seed in STAGES[stage]:
            parent, engine = checkpoint.load_world(None, seed)
            snapshots = checkpoint.train_snapshots(engine)
            tasks = checkpoint.generate_basic_tasks(snapshots[8192], 120000 + TASK_OFFSET + seed, n=TASKS_PER_TYPE)
            tasks += checkpoint.generate_branch_tasks(snapshots[8192], 220000 + TASK_OFFSET + seed, n=TASKS_PER_TYPE)
            for task_id, (kind, start, spec) in enumerate(tasks):
                specs.append({"seed": seed, "task_id": task_id, "task_type": kind,
                              "start": start, "spec": spec, "game_hash": parent["game_hash"]})
            # Persist the whole world's task list BEFORE observing any policy outcome.
            save_json(output / "tasks.json", specs)
            for task_id, (kind, start, spec) in enumerate(tasks):
                shortest = checkpoint.product_shortest_path(snapshots[512], checkpoint.TaskAutomaton(spec), start)
                for policy in POLICIES:
                    identity = {"seed": seed, "task_id": task_id, "task_type": kind, "policy": policy}
                    row = {**identity, "starts_in_model": shortest is not None,
                           **episode(snapshots[512].core, engine, spec, start, policy, sink, identity)}
                    rows.append(row)
                    write_csv(output / "episodes.csv", rows)
                    save_json(output / "episodes.json", rows)
                    sink.flush()
                    message = (f"seed={seed} task={task_id} policy={policy} success={row['success']} "
                               f"steps={row['task_steps']} explore={row['exploration_decisions']} "
                               f"signal={row['task_signal_available_decisions']} changed={row['field_changed_decisions']}")
                    print(message, flush=True)
                    log.write(message + "\n")
                    log.flush()
    summary = summarize(rows)
    save_json(output / "summary.json", summary)
    write_csv(output / "per_world.csv", summary["per_world"])
    save_json(output / "task_hashes.json", {"tasks_sha256": file_hash(output / "tasks.json")})
    return summary


def final_gate(output):
    rows = []
    for stage in STAGES:
        rows.extend(json.loads((output / stage / "episodes.json").read_text()))
    summary = summarize(rows)
    aggregate = {r["policy"]: r for r in summary["aggregate"]}
    aware = aggregate["task_virtual_frontier"]
    frontier = aggregate["frontier_t0"]
    ratio = aware["wall_seconds"] / frontier["wall_seconds"]
    signal_rate = aware["task_signal_available_decisions"] / max(1, aware["exploration_decisions"])
    # Engineering and near-zero definitions are frozen in the pre-pilot protocol.
    checks = {"real_task_signal_present": aware["task_signal_available_decisions"] > 0,
              "real_action_changes_present": aware["field_changed_decisions"] > 0,
              "signal_not_near_zero": signal_rate >= 0.01,
              "runtime_ratio_at_most_20": ratio <= 20.0,
              "process_peak_rss_at_most_1GiB": max(r["process_peak_rss_bytes_so_far"] for r in rows) <= 1024**3,
              "finite_small_field_residual": max(r["max_field_residual"] for r in rows) <= 1e-10}
    import xml.etree.ElementTree as ET
    tests = ET.parse(output / "tests.xml").getroot()
    suites = [tests] if tests.tag == "testsuite" else list(tests.findall("testsuite"))
    checks["tests_pass"] = bool(suites) and all(int(s.get("failures", 0)) + int(s.get("errors", 0)) == 0 for s in suites)
    names = {case.get("name") for suite in suites for case in suite.findall("testcase")
             if case.find("skipped") is None and case.find("failure") is None and case.find("error") is None}
    checks["synthetic_mechanism_gate"] = "test_one_learned_graph_two_tasks_different_exploration_actions" in names
    checks["task_off_exact_equivalence"] = all(f"test_task_off_matches_generic_on_real_online_trajectory[{s}]" in names for s in (2202, 2505))
    summary["gate"] = {"checks": checks, "passed": all(checks.values()),
                       "N_exploration_decisions": aware["exploration_decisions"],
                       "N_task_signal_available": aware["task_signal_available_decisions"],
                       "N_field_changed_decisions": aware["field_changed_decisions"],
                       "number_of_tasks_with_at_least_one_changed_decision": aware["tasks_with_changed_decision"],
                       "signal_fraction": signal_rate, "runtime_ratio_relative_to_frontier_t0": ratio,
                       "large_experiment_started": False,
                       "next_action": "FREEZE AND REPORT; no automatic 70-world execution" if all(checks.values()) else "STOP BEFORE 70 WORLDS"}
    save_json(output / "summary.json", summary)
    write_csv(output / "per_world.csv", summary["per_world"])
    write_csv(output / "paired_worlds.csv", summary["paired_worlds"])
    print(json.dumps(summary, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("stage", choices=("smoke", "cohort", "summary"))
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    if args.stage == "summary":
        final_gate(Path(args.output))
    else:
        run_stage(args.stage, Path(args.output))


if __name__ == "__main__":
    main()
