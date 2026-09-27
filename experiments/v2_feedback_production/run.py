"""Gated actual V2 design runs and selection-independent final evaluation."""
import argparse
from collections import Counter
from contextlib import redirect_stdout
import gc
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time

import numpy as np
import psutil
import scipy

from experiments.self_design_v2_feedback_loop.adapter import FeedbackLoopAdapter
from experiments.v2_online_feedback.adapter import ARMS, fingerprint, load_v2, restore_game
from experiments.v2_online_feedback.prepare import ROOT, FROZEN, write
from .adapter import ArmFeedbackLoopAdapter
from .observe import LoopObserver

BASE = "90a7bba04ce8895869b6b2eb7b3dd7d8cae25207"
SEEDS = list(range(79020000, 79020008))
MODES = ("targeted", "random")
IMMUTABLE = FROZEN + ["experiments/v2_online_feedback/adapter.py", "experiments/self_design_v2_feedback_loop/adapter.py"]


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def git_blob(path):
    return subprocess.check_output(["git", "show", f"{BASE}:{path}"], cwd=ROOT)


def initial_data(seed):
    assert seed in SEEDS
    return json.loads(git_blob(f"reports/v2_online_feedback_36281122365/registered_inputs/{seed}/game.json"))


def source_check():
    checks = {}
    for name in IMMUTABLE:
        expected = git_blob(name).replace(b"\r\n", b"\n")
        actual = (ROOT / name).read_bytes().replace(b"\r\n", b"\n")
        assert expected == actual, name
        checks[name] = hashlib.sha256(actual).hexdigest()
    return checks


def snapshot(output):
    output.mkdir(parents=True, exist_ok=False)
    sources = source_check()
    new = {str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
           for p in (ROOT / "experiments/v2_feedback_production").glob("*.py")}
    write(output / "source_snapshot.json", {
        "base": BASE, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "status": subprocess.check_output(["git", "status", "--short"], cwd=ROOT, text=True),
        "command": sys.argv, "python": sys.version, "platform": platform.platform(),
        "numpy": np.__version__, "scipy": scipy.__version__, "psutil": psutil.__version__,
        "frozen_sha256_lf": sources, "new_source_sha256": new,
        "actions_run": os.getenv("GITHUB_RUN_ID"), "attempt": os.getenv("GITHUB_RUN_ATTEMPT"),
        "threads": {k: os.getenv(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")}})
    write(output / "input_registry.json", {str(s): {"game": initial_data(s), "sha256": fingerprint(initial_data(s))} for s in SEEDS})


def series(directory, seed, arm, mode, iterations, original=False):
    directory.mkdir(parents=True, exist_ok=False)
    module = load_v2()
    identities = {k: getattr(module, k) for k in ("MicroGame", "StructuralLearner", "solve_fixed_field",
        "critique_game", "apply_targeted_mutation", "apply_random_mutation", "decide_acceptance", "run_self_design_loop")}
    game = restore_game(module, initial_data(seed))
    adapter = FeedbackLoopAdapter(module, directory / "evaluations") if original else ArmFeedbackLoopAdapter(module, directory / "evaluations", arm)
    adapter.install()
    observer = LoopObserver(module, adapter)
    observer.install()
    cpu, wall = time.process_time(), time.perf_counter()
    try:
        final, history, accepted = observer.run(game, iterations, seed, mode)
    finally:
        adapter.restore()
    assert all(getattr(module, k) is value for k, value in identities.items())
    write(directory / "initial_game.json", game.to_dict())
    write(directory / "final_game.json", final.to_dict())
    write(directory / "history.json", history)
    write(directory / "critique_calls.json", observer.critique_calls)
    write(directory / "acceptance_calls.json", observer.acceptance_calls)
    retained = 0
    changes = []
    for i in range(1, len(history)):
        previous, entry = history[i - 1]["game"], history[i]
        candidate = entry["candidate_game"]
        changed = candidate != previous
        changes.append({"iteration": i, "accepted": entry["accepted"], "game_changed": changed,
            "goal_changed": candidate["goal_pos"] != previous["goal_pos"],
            "start_changed": candidate["start_pos"] != previous["start_pos"],
            "previous_successes": observer.metrics[retained]["successes"],
            "candidate_successes": entry["candidate_metrics"]["successes"],
            "success_change_on_changed_game": changed and entry["candidate_metrics"]["successes"] != observer.metrics[retained]["successes"]})
        if entry["accepted"]:
            retained = i
    counts = Counter()
    for audit in observer.audits:
        counts.update(audit["phase_actions"])
    result = {"status": "COMPLETE", "seed": seed, "arm": arm, "mode": mode, "iterations": iterations,
        "evaluations": len(observer.audits), "accepted_edits": accepted, "retained_evaluation": retained,
        "initial_metrics": observer.metrics[0], "final_metrics": observer.metrics[retained],
        "initial_mean_capped_cost": observer.audits[0]["mean_capped_cost"],
        "final_mean_capped_cost": observer.audits[retained]["mean_capped_cost"],
        "final_game_changed": game.to_dict() != final.to_dict(), "final_goal_changed": game.goal_pos != final.goal_pos,
        "final_start_changed": game.start_pos != final.start_pos,
        "accepted_goal_changes": sum(c["accepted"] and c["goal_changed"] for c in changes),
        "proposed_goal_changes": sum(c["goal_changed"] for c in changes), "changes": changes,
        "phase_actions": dict(counts), "total_environment_actions": sum(counts.values()),
        "verification_replay_actions": sum(a["verification_replay_actions"] for a in observer.audits),
        "evaluation_cpu_seconds": sum(a["evaluation_cpu_seconds"] for a in observer.audits),
        "series_cpu_seconds": time.process_time() - cpu, "series_wall_seconds": time.perf_counter() - wall,
        "same_learner_and_metric_forwarding_audited": True}
    write(directory / "series.json", result)
    return result


def single(directory, data, arm):
    directory.mkdir(parents=True, exist_ok=False)
    module = load_v2()
    adapter = ArmFeedbackLoopAdapter(module, directory / "evaluations", arm)
    adapter.install()
    observer = LoopObserver(module, adapter)
    observer.install()
    try:
        observer.standalone(restore_game(module, data))
    finally:
        adapter.restore()
    return observer.audits[0]


def normalized(value):
    if isinstance(value, dict):
        return {k: normalized(v) for k, v in value.items() if k not in ("field_solve_seconds", "policy_seconds")}
    if isinstance(value, list):
        return [normalized(v) for v in value]
    return value


def read_rows(path):
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        return [json.loads(line) for line in stream]


def gate(output):
    for seed in (79020000, 79020004):
        for mode in MODES:
            series(output / f"smoke_{seed}_{mode}", seed, ARMS[2], mode, 5, original=True)
            gc.collect()
    checks = []
    for seed in (79020000, 79020004):
        single(output / f"equivalence_{seed}", initial_data(seed), ARMS[2])
    verify_gate(output, output)


def verify_gate(data, output):
    checks = []
    for seed in (79020000, 79020004):
        for mode in MODES:
            result = read(data / f"smoke_{seed}_{mode}/series.json")
            assert result["status"] == "COMPLETE" and result["iterations"] == 5 and result["evaluations"] == 6
            assert result["same_learner_and_metric_forwarding_audited"]
            for i in range(6):
                directory = data / f"smoke_{seed}_{mode}/evaluations/evaluation_{i:03d}"
                audit = read(directory / "execution_audit.json")
                assert audit["phase_actions"]["initial"] == 2500 and audit["phase_actions"]["additional"] == 5000
                assert audit["same_learner_before_after_feedback_and_frozen"] and audit["no_random_or_evaluation_learning"]
        expected = data / f"smoke_{seed}_targeted/evaluations/evaluation_000"
        actual = data / f"equivalence_{seed}/evaluations/evaluation_000"
        for name in ("initial_learner.json", "final_learner.json", "evaluation_metrics.json", "frozen_trials.json"):
            assert read(expected / name) == read(actual / name), (seed, name)
            checks.append({"seed": seed, "file": name, "exact": True})
        for name in ("initial_training.jsonl.gz", "additional_actions.jsonl.gz", "all_actions.jsonl.gz"):
            assert normalized(read_rows(expected / name)) == normalized(read_rows(actual / name)), (seed, name)
            checks.append({"seed": seed, "file": name, "exact_excluding_timing": True})
        historical = json.loads(git_blob(f"reports/v2_online_feedback_36281122365/registered_inputs/{seed}/learner.json"))
        assert read(actual / "initial_learner.json") == historical
        gc.collect()
    write(output / "gate_pass.json", {"passed": True, "real_loop_runs": 4, "real_loop_evaluations": 24,
        "additional_equivalence_evaluations": 2, "checks": checks, "mocks_used": False,
        "timing_fields_excluded": ["telemetry.field_solve_seconds", "telemetry.policy_seconds"],
        "verification_input": str(data), "prior_run": 36284251256 if data != output else None})


def production(output, seed):
    results = []
    for arm in ARMS:
        for mode in MODES:
            results.append(series(output / f"{arm}_{mode}", seed, arm, mode, 20))
            gc.collect()
    write(output / "world_complete.json", {"seed": seed, "series": results, "status": "COMPLETE"})


def common(output, seed, inputs):
    completed = list(inputs.rglob("world_complete.json"))
    worlds = {read(p)["seed"]: p for p in completed}
    assert set(worlds) == set(SEEDS) and len(completed) == 8, "All production worlds must finish before common evaluation"
    rows = []
    parent = worlds[seed].parent
    for arm in ARMS:
        for mode in MODES:
            source = parent / f"{arm}_{mode}"
            data = read(source / "final_game.json")
            audit = single(output / f"{arm}_{mode}", data, ARMS[2])
            rows.append({"seed": seed, "origin_arm": arm, "mode": mode, "game_hash": fingerprint(data), **audit})
            gc.collect()
    write(output / "common_complete.json", {"seed": seed, "results": rows, "status": "COMPLETE", "fed_back_to_selection": False})


def main():
    p = argparse.ArgumentParser()
    p.add_argument("phase", choices=("gate", "gate-resume", "production", "common"))
    p.add_argument("--seed", type=int, choices=SEEDS)
    p.add_argument("--output", type=Path, required=True)
    p.add_argument("--inputs", type=Path)
    p.add_argument("--gate", type=Path)
    a = p.parse_args()
    snapshot(a.output)
    start_cpu, start_wall = time.process_time(), time.perf_counter()
    status, error = "RUN_NOT_COMPLETED", None
    try:
        with (a.output / "run.log").open("x", encoding="utf-8", buffering=1) as log, redirect_stdout(log):
            if a.phase == "gate":
                gate(a.output)
            elif a.phase == "gate-resume":
                previous = read(a.inputs / "source_snapshot.json")
                assert previous["head"] == "8aefadc21004cee6842ffb9aac6c09e5e6b62a8b"
                assert previous["frozen_sha256_lf"] == source_check()
                verify_gate(a.inputs, a.output)
            else:
                assert a.seed is not None and read(a.gate)["passed"]
                if a.phase == "production":
                    production(a.output, a.seed)
                else:
                    common(a.output, a.seed, a.inputs)
            source_check()
            status = "COMPLETE"
    except BaseException as exc:
        error = repr(exc)
        raise
    finally:
        mem = psutil.Process().memory_info()
        write(a.output / "resources.json", {"status": status, "error": error,
            "cpu_seconds": time.process_time() - start_cpu, "wall_seconds": time.perf_counter() - start_wall,
            "peak_working_set_bytes": getattr(mem, "peak_wset", None), "rss_bytes_at_end": mem.rss,
            "phase": a.phase, "seed": a.seed, "attempt": os.getenv("GITHUB_RUN_ATTEMPT")})
    print(f"{a.phase}: {status}", flush=True)


if __name__ == "__main__":
    main()
