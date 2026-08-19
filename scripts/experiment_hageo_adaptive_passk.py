"""Anytime HAGeo search with typed-residual budget allocation.

Every stage executes the same finite construction grammar and native checker.
The controller changes only depth and the number of independent trajectories;
it never reads answers, dataset auxiliaries, or problem-specific rules.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.adaptive_search_budget import (  # noqa: E402
    AdaptiveBudgetPolicy,
    ProofResidual,
    SearchStage,
    StageObservation,
    best_attempt_residual,
)


def _write_checkpoint(
    output: Path,
    *,
    args: argparse.Namespace,
    stages: list[dict[str, Any]],
    decision_reason: str,
    started: float,
) -> None:
    solved = any(item.get("solved", False) for item in stages)
    report = {
        "experiment": "hageo_anytime_typed_residual_adaptive_pass_at_k_no_llm",
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "uses_problem_id_in_search": False,
            "uses_expected_answer": False,
            "candidate_policy": args.candidate_policy,
            "rank_temperature": args.rank_temperature,
            "incremental_prefix": args.incremental_prefix,
            "feedback_candidates": args.feedback_candidates,
            "max_feedback_candidates": args.max_feedback_candidates,
            "feedback_workers": args.feedback_workers,
            "budget_signal": "typed_native_proof_residual_only",
            "start_depth": args.start_depth,
            "max_depth": args.max_depth,
            "depth_step": args.depth_step,
            "initial_attempts": args.initial_attempts,
            "max_attempts": args.max_attempts,
            "truth_plane": "yuclid_native_certificate_replay_only",
        },
        "problem_name": args.problem_name,
        "solved": solved,
        "decision_reason": decision_reason,
        "elapsed_seconds": time.perf_counter() - started,
        "completed_stages": len(stages),
        "completed_attempts": sum(item.get("completed_attempts", 0) for item in stages),
        "unique_paths": len(
            {
                tuple(attempt.get("path", ()))
                for stage in stages
                for attempt in stage.get("attempt_results", ())
            }
        ),
        "stages": stages,
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _run_stage(
    stage: SearchStage,
    *,
    attempt_offset: int,
    stage_index: int,
    args: argparse.Namespace,
) -> tuple[dict[str, Any], StageObservation, ProofResidual | None]:
    stage_output = args.run_dir / (
        f"stage-{stage_index:02d}-n{stage.depth}-k{stage.attempts}"
        f"-f{stage.feedback_candidates}.json"
    )
    command = [
        str(args.python),
        "-B",
        str(ROOT / "scripts" / "experiment_hageo_passk.py"),
        "--dataset",
        str(args.dataset),
        "--problem-name",
        args.problem_name,
        "--yuclid-exe",
        str(args.yuclid_exe),
        "--runtime-path",
        str(args.runtime_path),
        "--output",
        str(stage_output),
        "--rounds",
        str(stage.depth),
        "--attempts",
        str(stage.attempts),
        "--attempt-offset",
        str(attempt_offset),
        "--workers",
        str(args.workers),
        "--seed",
        str(args.seed),
        "--per-family-limit",
        str(args.per_family_limit),
        "--incidence-oversample-per-family",
        str(args.incidence_oversample_per_family),
        "--incidence-preselect-limit",
        str(args.incidence_preselect_limit),
        "--incidence-workers",
        str(args.incidence_workers),
        "--candidate-limit",
        str(args.candidate_limit),
        "--candidate-policy",
        args.candidate_policy,
        "--rank-temperature",
        str(args.rank_temperature),
        "--feedback-candidates",
        str(stage.feedback_candidates),
        "--feedback-workers",
        str(args.feedback_workers),
        "--ar-profile",
        args.ar_profile,
    ]
    if args.incremental_prefix:
        command.append("--incremental-prefix")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=args.stage_timeout_seconds,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
    except subprocess.TimeoutExpired as exc:
        elapsed = time.perf_counter() - started
        observation = StageObservation(
            stage=stage,
            solved=False,
            completed_attempts=0,
            unique_paths=0,
            execution_errors=0,
            best_residual=None,
            right_censored=True,
        )
        summary = {
            "stage_index": stage_index,
            "depth": stage.depth,
            "attempts": stage.attempts,
            "feedback_candidates": stage.feedback_candidates,
            "attempt_offset": attempt_offset,
            "status": "right_censored_timeout",
            "solved": False,
            "completed_attempts": 0,
            "unique_paths": 0,
            "execution_errors": 0,
            "best_residual": None,
            "elapsed_seconds": elapsed,
            "artifact": None,
            "attempt_results": [],
            "timeout_seconds": args.stage_timeout_seconds,
            "stdout_tail": (exc.stdout or "")[-2000:] if isinstance(exc.stdout, str) else "",
            "stderr_tail": (exc.stderr or "")[-2000:] if isinstance(exc.stderr, str) else "",
        }
        return summary, observation, None
    if completed.returncode != 0 or not stage_output.is_file():
        raise RuntimeError(
            f"adaptive stage failed with exit code {completed.returncode}: "
            f"{completed.stderr[-2000:]}"
        )
    artifact = json.loads(stage_output.read_text(encoding="utf-8"))
    attempts = artifact.get("attempt_results", [])
    residual = best_attempt_residual(attempts)
    baseline = ProofResidual.from_mapping(artifact["baseline_proof_residual"])
    observation = StageObservation(
        stage=stage,
        solved=bool(artifact["solved"]),
        completed_attempts=sum(
            int(item.get("rounds_completed", 0)) == stage.depth for item in attempts
        ),
        unique_paths=int(artifact["unique_paths"]),
        execution_errors=sum(
            item.get("status") == "execution_error" for item in attempts
        ),
        best_residual=residual,
        right_censored=False,
    )
    summary = {
        "stage_index": stage_index,
        "depth": stage.depth,
        "attempts": stage.attempts,
        "feedback_candidates": stage.feedback_candidates,
        "attempt_offset": attempt_offset,
        "solved": observation.solved,
        "completed_attempts": observation.completed_attempts,
        "unique_paths": observation.unique_paths,
        "execution_errors": observation.execution_errors,
        "best_residual": residual.to_dict() if residual is not None else None,
        "elapsed_seconds": time.perf_counter() - started,
        "artifact": stage_output.resolve().relative_to(ROOT).as_posix(),
        "attempt_results": attempts,
        "certificate": artifact.get("certificate"),
    }
    return summary, observation, baseline


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-name", required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--start-depth", type=int, default=2)
    parser.add_argument("--max-depth", type=int, default=8)
    parser.add_argument("--depth-step", type=int, default=2)
    parser.add_argument("--initial-attempts", type=int, default=1)
    parser.add_argument("--max-attempts", type=int, default=32)
    parser.add_argument("--attempt-growth", type=int, default=2)
    parser.add_argument("--max-stages", type=int, default=8)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--per-family-limit", type=int, default=64)
    parser.add_argument("--incidence-oversample-per-family", type=int, default=64)
    parser.add_argument("--incidence-preselect-limit", type=int, default=0)
    parser.add_argument("--incidence-workers", type=int, default=1)
    parser.add_argument("--candidate-limit", type=int, default=0)
    parser.add_argument(
        "--candidate-policy",
        choices=("random", "typed-sheaf"),
        default="typed-sheaf",
    )
    parser.add_argument("--rank-temperature", type=float, default=2.0)
    parser.add_argument("--incremental-prefix", action="store_true")
    parser.add_argument("--feedback-candidates", type=int, default=16)
    parser.add_argument("--max-feedback-candidates", type=int, default=48)
    parser.add_argument("--feedback-growth", type=int, default=3)
    parser.add_argument("--feedback-workers", type=int, default=8)
    parser.add_argument("--stage-timeout-seconds", type=float, default=1800.0)
    parser.add_argument("--total-timeout-seconds", type=float, default=7200.0)
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    args = parser.parse_args()

    policy = AdaptiveBudgetPolicy(
        start_depth=args.start_depth,
        max_depth=args.max_depth,
        depth_step=args.depth_step,
        initial_attempts=args.initial_attempts,
        max_attempts=args.max_attempts,
        attempt_growth=args.attempt_growth,
        initial_feedback_candidates=args.feedback_candidates,
        max_feedback_candidates=args.max_feedback_candidates,
        feedback_growth=args.feedback_growth,
    )
    args.run_dir.mkdir(parents=True, exist_ok=True)
    observations: list[StageObservation] = []
    stages: list[dict[str, Any]] = []
    baseline: ProofResidual | None = None
    next_stage = policy.initial_stage
    attempt_offset = 0
    started = time.perf_counter()
    decision_reason = "initial"
    for stage_index in range(args.max_stages):
        if time.perf_counter() - started >= args.total_timeout_seconds:
            decision_reason = "right_censored_total_time_budget"
            break
        summary, observation, observed_baseline = _run_stage(
            next_stage,
            attempt_offset=attempt_offset,
            stage_index=stage_index,
            args=args,
        )
        if baseline is None and observed_baseline is not None:
            baseline = observed_baseline
        elif observed_baseline is not None and baseline != observed_baseline:
            raise RuntimeError("baseline residual changed across adaptive stages")
        observations.append(observation)
        stages.append(summary)
        attempt_offset += next_stage.attempts
        if baseline is None:
            decision_reason = "right_censored_before_baseline_observation"
            _write_checkpoint(
                args.output,
                args=args,
                stages=stages,
                decision_reason=decision_reason,
                started=started,
            )
            break
        decision = policy.decide(observations, baseline=baseline)
        decision_reason = decision.reason
        _write_checkpoint(
            args.output,
            args=args,
            stages=stages,
            decision_reason=decision_reason,
            started=started,
        )
        print(
            json.dumps(
                {
                    "stage": stage_index,
                    "depth": next_stage.depth,
                    "attempts": next_stage.attempts,
                    "feedback_candidates": next_stage.feedback_candidates,
                    "solved": observation.solved,
                    "decision": decision.reason,
                    "next_stage": asdict(decision.next_stage) if decision.next_stage else None,
                }
            ),
            flush=True,
        )
        if not decision.continue_search or decision.next_stage is None:
            break
        next_stage = decision.next_stage
    else:
        decision_reason = "right_censored_max_stages"
    _write_checkpoint(
        args.output,
        args=args,
        stages=stages,
        decision_reason=decision_reason,
        started=started,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
