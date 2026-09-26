"""One registered historical world, three private arms, exact nested budgets."""
import argparse
from collections import Counter
import copy
import gzip
import importlib.metadata
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import numpy as np

from .adapter import ARMS, FeedbackPlayer, FrozenPlayback, fingerprint, load_v2, payload
from .gate import load_input
from .prepare import ROOT, SEEDS, source_check, write, sha
from experiments.self_design_v2_integration.run import peak_memory

CHECKPOINTS = (0, 1000, 5000)


def rows_write(path, rows):
    with gzip.open(path, "xt", encoding="utf-8") as stream:
        for row in rows:
            stream.write(json.dumps(row, allow_nan=False) + "\n")


def transitions(learner):
    return Counter({(learner.id_to_state[u], a, learner.id_to_state[v]): n
                    for (u, a), dests in learner.counts.items() for v, n in dests.items()})


def verify_trace(player, initial):
    learned = copy.deepcopy(initial)
    initial_fingerprint = fingerprint(payload(initial))
    state, trial, rollout_steps = player.game.get_initial_state(), 0, 0
    successes = 0
    for row in player.actions:
        if rollout_steps == 100 or player.game.is_goal(state):
            state, rollout_steps, trial = player.game.get_initial_state(), 0, trial + 1
        assert row["trial"] == trial and tuple(row["state"]) == state
        nxt = player.game.step(state, row["action"])
        assert nxt == tuple(row["next_state"])
        assert bool(player.game.is_goal(nxt)) == row["success"]
        successes += int(row["success"])
        if player.arm != ARMS[0]:
            u = learned.get_or_add_id(state)
            v = learned.get_or_add_id(nxt)
            learned.record_transition(u, row["action"], v)
        state, rollout_steps = nxt, rollout_steps + 1
    if player.arm == ARMS[0]:
        assert initial_fingerprint == fingerprint(payload(player.learner))
    else:
        for key in ("id_to_state", "state_to_id", "counts", "action_visits", "dest_map"):
            assert getattr(learned, key) == getattr(player.learner, key), key
    assert successes == player.successes
    assert sum(transitions(player.learner).values()) == 2500 + (0 if player.arm == ARMS[0] else len(player.actions))
    assert player.resets == trial
    assert fingerprint(payload(initial)) == initial_fingerprint
    return {"all_executed_transitions_replayed": True, "reset_edges_absent": True,
            "recorded_counts_exact": True, "all_rollout_successes_match": True,
            "node_visit_updates": "Existing selector bookkeeping retained; recorder never invents node visits"}


def execute(seed, directory, output):
    module = load_v2()
    playback = FrozenPlayback(module)
    _, game, initial = load_input(directory, seed, module)
    frozen_source = source_check()
    output.mkdir(parents=True, exist_ok=False)
    metadata = {"seed": seed, "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "sources": frozen_source, "python": sys.version, "platform": platform.platform(),
        "packages": {n: importlib.metadata.version(n) for n in ("numpy", "scipy", "pytest", "psutil")},
        "attempt": os.environ.get("GITHUB_RUN_ATTEMPT", "local"), "run_id": os.environ.get("GITHUB_RUN_ID"),
        "thread_limits": {k: os.environ.get(k) for k in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
        "new_source_sha256": {p.name: sha(p.read_bytes()) for p in Path(__file__).parent.glob("*.py")},
        "game_hash": fingerprint(game.to_dict()), "snapshot_hash": fingerprint(payload(initial)),
        "input_registry": json.loads((directory / "input_registry.json").read_text())[str(seed)],
        "timing_scope": "Fixed A,B,C order per isolated world worker; diagnostics, not strict speed benchmark"}
    write(output / "source_snapshot.json", metadata)
    write(output / "config.json", {"study": "outcome-selected development", "seeds": SEEDS,
        "arms": ARMS, "initial_actions": 2500, "additional_actions": 5000, "checkpoints": CHECKPOINTS,
        "rollout_cap": 100, "evaluation_trials": 50, "q": 0.90, "fallback_threshold": 1e-8,
        "training_source": 1, "game_edits": False, "new_initial_training": False})
    write(output / "game.json", game.to_dict())
    total_cpu, total_wall = time.process_time(), time.perf_counter()
    summaries = []
    prior_profile = sys.getprofile()
    def guard(frame, event, result):
        if event == "call" and "oracle" in frame.f_code.co_name.lower():
            raise RuntimeError("Oracle execution prohibited")
    with (output / "run.log").open("x", encoding="utf-8", buffering=1) as log:
        for arm in ARMS:
            arm_dir = output / arm
            arm_dir.mkdir()
            player = None
            try:
                sys.setprofile(guard)
                player = FeedbackPlayer(module, playback, copy.deepcopy(game), copy.deepcopy(initial), arm)
                for budget in CHECKPOINTS:
                    player.advance_to(budget)
                    stats = player.stats()
                    result = playback.evaluate(player.game, player.learner)
                    same_field = bool(np.array_equal(player.psi, result["psi"]))
                    max_difference = float(np.max(np.abs(player.psi - result["psi"])))
                    assert same_field, (arm, budget, max_difference)
                    checkpoint = arm_dir / f"checkpoint_{budget}"
                    checkpoint.mkdir()
                    write(checkpoint / "learner.json", payload(player.learner))
                    rows_write(checkpoint / "evaluation_trials.jsonl.gz", result["trials"])
                    np.save(checkpoint / "psi.npy", result["psi"])
                    summary = {"seed": seed, "arm": arm, "checkpoint": budget,
                        "game_hash": metadata["game_hash"], "learner_hash": fingerprint(payload(player.learner)),
                        **stats, "evaluation_successes": result["successes"], "evaluation_trials": 50,
                        "evaluation_actual_actions": result["actual_actions"], "mean_capped_cost": result["mean_capped_cost"],
                        "evaluation_cpu_seconds": result["cpu_seconds"], "evaluation_learner_unchanged": result["learner_unchanged"],
                        "recomputed_field_bitwise_equal": same_field, "field_max_absolute_difference": max_difference,
                        "peak_process_memory_bytes": peak_memory()}
                    write(checkpoint / "metrics.json", summary)
                    summaries.append(summary)
                    message = json.dumps(summary, allow_nan=False)
                    print(message, flush=True)
                    log.write(message + "\n")
                assert player.steps == 5000
                if not player.rollouts or player.rollouts[-1]["end_step"] != player.steps:
                    player.rollouts.append({"trial": player.trial, "end_step": player.steps,
                        "actions": player.rollout_steps, "success": False, "termination": "budget_truncation"})
                write(arm_dir / "trace_audit.json", verify_trace(player, initial))
                rows_write(arm_dir / "training_actions.jsonl.gz", player.actions)
                write(arm_dir / "training_rollouts.json", player.rollouts)
                write(arm_dir / "field_recomputations.json", player.fields)
            except BaseException as error:
                write(arm_dir / "incomplete.json", {"status": "RUN_NOT_COMPLETED", "reason": repr(error),
                    "actions_completed": player.steps if player else 0, "traceback": traceback.format_exc()})
                if player:
                    rows_write(arm_dir / "partial_training_actions.jsonl.gz", player.actions)
                    write(arm_dir / "partial_learner.json", payload(player.learner))
                raise
            finally:
                sys.setprofile(prior_profile)
    assert source_check() == frozen_source
    write(output / "metrics.json", summaries)
    write(output / "completed.json", {"status": "COMPLETED", "seed": seed,
        "additional_training_actions": 15000, "checkpoint_evaluation_trials": 450,
        "total_cpu_seconds": time.process_time() - total_cpu, "total_wall_seconds": time.perf_counter() - total_wall,
        "peak_process_memory_bytes": peak_memory(), "oracle_calls": 0})


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, choices=SEEDS, required=True)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--gate", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    gate = json.loads((args.gate / "passed.json").read_text())
    assert gate["all_seeds"] == SEEDS and gate["all_discrete_traces_equal"]
    execute(args.seed, args.input, args.output)


if __name__ == "__main__":
    main()
