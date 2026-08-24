"""Run HAGeo-style independent attempts in separate CPU processes."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.geometry_backend_options import (  # noqa: E402
    EXACT_SPECIALIST_REPRESENTATIONS,
)


def _aggregate_solved(
    shard_results: list[dict[str, Any]],
    attempts: list[dict[str, Any]],
) -> bool:
    """Preserve a native baseline proof even when no search attempt is needed."""

    return any(item.get("solved", False) for item in shard_results) or any(
        item.get("solved", False) for item in attempts
    )


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def _load_completed_shard(
    *,
    shard: int,
    count: int,
    offset: int,
    args: argparse.Namespace,
    output: Path,
) -> dict[str, Any] | None:
    if not args.resume_existing_shards or not output.is_file():
        return None
    artifact = json.loads(output.read_text(encoding="utf-8"))
    protocol = artifact.get("protocol", {})
    expected = {
        "rounds_n": args.rounds,
        "attempts_k": count,
        "attempt_offset": offset,
        "workers": 1,
        "seed": args.seed,
        "per_family_limit": args.per_family_limit,
        "incidence_oversample_per_family": args.incidence_oversample_per_family,
        "incidence_preselect_limit": args.incidence_preselect_limit,
        "incidence_workers": args.incidence_workers,
        "candidate_limit": args.candidate_limit,
        "candidate_policy": args.candidate_policy,
        "rank_temperature": args.rank_temperature,
        "incremental_prefix": args.incremental_prefix,
        "feedback_candidates": args.feedback_candidates,
        "feedback_workers": args.feedback_workers,
        "max_verification_concurrency": (
            getattr(args, "max_verification_concurrency", 0)
            or args.feedback_workers
        ),
        "exact_specialist_timeout_seconds": getattr(
            args, "exact_specialist_timeout_seconds", 0.0
        ),
        "exact_specialist_representation": getattr(
            args, "exact_specialist_representation", "goal_local_relational"
        ),
        "exact_specialist_saturation_rounds": getattr(
            args, "exact_specialist_saturation_rounds", 1
        ),
        "exact_lemma_limit": getattr(args, "exact_lemma_limit", 0),
        "gclc_exe": (
            getattr(args, "gclc_exe").resolve().as_posix()
            if getattr(args, "gclc_exe", None)
            else None
        ),
        "gclc_methods": getattr(args, "gclc_methods", "wu"),
        "gclc_timeout_seconds": getattr(args, "gclc_timeout_seconds", 0),
        "gclc_lemma_limit": getattr(args, "gclc_lemma_limit", 0),
        "gclc_incidence_samples": getattr(args, "gclc_incidence_samples", 0),
        "wolfram_exe": (
            getattr(args, "wolfram_exe").resolve().as_posix()
            if getattr(args, "wolfram_exe", None)
            else None
        ),
        "wolfram_timeout_seconds": getattr(args, "wolfram_timeout_seconds", 0),
        "wolfram_preprocessing": getattr(
            args, "wolfram_preprocessing", "local_relational"
        ),
        "wolfram_reduction_mode": getattr(
            args, "wolfram_reduction_mode", "extended_groebner"
        ),
        "wolfram_saturation_mode": getattr(args, "wolfram_saturation_mode", "none"),
        "wolfram_max_saturation_factors": getattr(
            args, "wolfram_max_saturation_factors", 12
        ),
        "terminal_credit_ledger_input_sha256": (
            hashlib.sha256(getattr(args, "credit_ledger_input").read_bytes()).hexdigest()
            if getattr(args, "credit_ledger_input", None)
            else None
        ),
        "terminal_credit_ledger_frozen": getattr(args, "freeze_credit_ledger", None),
    }
    observed = {
        key: protocol.get(
            key,
            expected[key]
            if key.startswith("exact_specialist_")
            or key
            in {
                "max_verification_concurrency",
                "exact_lemma_limit",
                "gclc_exe",
                "gclc_methods",
                "gclc_timeout_seconds",
                "gclc_lemma_limit",
                "gclc_incidence_samples",
                "wolfram_exe",
                "wolfram_timeout_seconds",
                "wolfram_preprocessing",
                "wolfram_reduction_mode",
                "wolfram_saturation_mode",
                "wolfram_max_saturation_factors",
            }
            else None,
        )
        for key in expected
    }
    if (
        artifact.get("problem_name") != args.problem_name
        or observed != expected
        or len(artifact.get("attempt_results", [])) != count
    ):
        return None
    return {
        "shard": shard,
        "status": (
            "right_censored_timeout"
            if artifact.get("right_censored") and not artifact.get("solved")
            else "completed"
        ),
        "count": count,
        "seed": args.seed,
        "attempt_offset": offset,
        "solved": artifact["solved"],
        "unique_paths": artifact["unique_paths"],
        "completed_attempts": artifact["completed_attempts"],
        "attempt_results": artifact["attempt_results"],
        "certificate": artifact.get("certificate"),
        "artifact": _display_path(output),
        "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "elapsed_seconds": 0.0,
        "reused": True,
    }


def _run_shard(
    *,
    shard: int,
    count: int,
    offset: int,
    args: argparse.Namespace,
    output: Path,
) -> dict[str, Any]:
    existing = _load_completed_shard(
        shard=shard,
        count=count,
        offset=offset,
        args=args,
        output=output,
    )
    if existing is not None:
        return existing
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
        str(output),
        "--rounds",
        str(args.rounds),
        "--attempts",
        str(count),
        "--attempt-offset",
        str(offset),
        "--workers",
        "1",
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
        str(args.feedback_candidates),
        "--feedback-workers",
        str(args.feedback_workers),
        "--max-verification-concurrency",
        str(getattr(args, "max_verification_concurrency", 0)),
        "--exact-specialist-timeout-seconds",
        str(getattr(args, "exact_specialist_timeout_seconds", 0.0)),
        "--exact-specialist-representation",
        str(getattr(args, "exact_specialist_representation", "goal_local_relational")),
        "--exact-specialist-saturation-rounds",
        str(getattr(args, "exact_specialist_saturation_rounds", 1)),
        "--exact-lemma-limit",
        str(getattr(args, "exact_lemma_limit", 0)),
        "--ar-profile",
        args.ar_profile,
    ]
    if args.credit_ledger_input:
        command.extend(("--credit-ledger-input", str(args.credit_ledger_input)))
    if args.freeze_credit_ledger:
        command.append("--freeze-credit-ledger")
    if args.incremental_prefix:
        command.append("--incremental-prefix")
    if getattr(args, "gclc_exe", None):
        command.extend(
            (
                "--gclc-exe",
                str(args.gclc_exe),
                "--gclc-methods",
                str(getattr(args, "gclc_methods", "wu")),
                "--gclc-timeout-seconds",
                str(args.gclc_timeout_seconds),
                "--gclc-lemma-limit",
                str(getattr(args, "gclc_lemma_limit", 0)),
                "--gclc-incidence-samples",
                str(getattr(args, "gclc_incidence_samples", 0)),
            )
        )
    if getattr(args, "wolfram_exe", None):
        command.extend(
            (
                "--wolfram-exe",
                str(args.wolfram_exe),
                "--wolfram-timeout-seconds",
                str(getattr(args, "wolfram_timeout_seconds", 0)),
                "--wolfram-preprocessing",
                str(getattr(args, "wolfram_preprocessing", "local_relational")),
                "--wolfram-reduction-mode",
                str(getattr(args, "wolfram_reduction_mode", "extended_groebner")),
                "--wolfram-saturation-mode",
                str(getattr(args, "wolfram_saturation_mode", "none")),
                "--wolfram-max-saturation-factors",
                str(getattr(args, "wolfram_max_saturation_factors", 12)),
            )
        )
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=args.timeout_seconds,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
    except subprocess.TimeoutExpired:
        return {
            "shard": shard,
            "status": "right_censored_timeout",
            "count": count,
            "elapsed_seconds": time.perf_counter() - started,
        }
    if completed.returncode != 0 or not output.is_file():
        return {
            "shard": shard,
            "status": "execution_error",
            "count": count,
            "returncode": completed.returncode,
            "stderr_tail": completed.stderr[-2000:],
            "elapsed_seconds": time.perf_counter() - started,
        }
    artifact = json.loads(output.read_text(encoding="utf-8"))
    return {
        "shard": shard,
        "status": (
            "right_censored_timeout"
            if artifact.get("right_censored") and not artifact.get("solved")
            else "completed"
        ),
        "count": count,
        "seed": args.seed,
        "attempt_offset": offset,
        "solved": artifact["solved"],
        "unique_paths": artifact["unique_paths"],
        "completed_attempts": artifact["completed_attempts"],
        "attempt_results": artifact["attempt_results"],
        "certificate": artifact.get("certificate"),
        "artifact": output.resolve().relative_to(ROOT).as_posix(),
        "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-name", required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--attempts", type=int, default=64)
    parser.add_argument("--shards", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--per-family-limit", type=int, default=4)
    parser.add_argument("--incidence-oversample-per-family", type=int, default=16)
    parser.add_argument("--incidence-preselect-limit", type=int, default=0)
    parser.add_argument("--incidence-workers", type=int, default=1)
    parser.add_argument("--candidate-limit", type=int, default=64)
    parser.add_argument(
        "--candidate-policy",
        choices=(
            "random",
            "typed-sheaf",
            "mmt-sheaf",
            "mmt-hageo",
            "mmt-hageo-lite",
            "residual-static",
            "residual-feedback",
            "residual-portfolio",
            "terminal-credit",
            "terminal-credit-mixed",
            "obligation-credit-mixed",
            "contract-portfolio",
            "residual-construction",
        ),
        default="random",
    )
    parser.add_argument("--rank-temperature", type=float, default=2.0)
    parser.add_argument("--incremental-prefix", action="store_true")
    parser.add_argument("--feedback-candidates", type=int, default=0)
    parser.add_argument("--feedback-workers", type=int, default=1)
    parser.add_argument("--max-verification-concurrency", type=int, default=0)
    parser.add_argument("--exact-specialist-timeout-seconds", type=float, default=0.0)
    parser.add_argument(
        "--exact-specialist-representation",
        choices=EXACT_SPECIALIST_REPRESENTATIONS,
        default="goal_local_relational",
    )
    parser.add_argument("--exact-specialist-saturation-rounds", type=int, default=1)
    parser.add_argument("--exact-lemma-limit", type=int, default=0)
    parser.add_argument("--gclc-exe", type=Path)
    parser.add_argument("--gclc-methods", default="wu")
    parser.add_argument("--gclc-timeout-seconds", type=int, default=0)
    parser.add_argument("--gclc-lemma-limit", type=int, default=0)
    parser.add_argument("--gclc-incidence-samples", type=int, default=0)
    parser.add_argument("--wolfram-exe", type=Path)
    parser.add_argument("--wolfram-timeout-seconds", type=int, default=0)
    parser.add_argument(
        "--wolfram-preprocessing",
        choices=("local_relational", "relational", "explicit"),
        default="local_relational",
    )
    parser.add_argument(
        "--wolfram-reduction-mode",
        choices=("direct", "extended_groebner"),
        default="extended_groebner",
    )
    parser.add_argument(
        "--wolfram-saturation-mode",
        choices=("none", "single", "cumulative"),
        default="none",
    )
    parser.add_argument("--wolfram-max-saturation-factors", type=int, default=12)
    parser.add_argument("--credit-ledger-input", type=Path)
    parser.add_argument("--freeze-credit-ledger", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    parser.add_argument("--resume-existing-shards", action="store_true")
    args = parser.parse_args()
    if args.attempts < 1 or args.shards < 1:
        parser.error("--attempts and --shards must be positive")
    if args.wolfram_timeout_seconds < 0 or args.wolfram_max_saturation_factors < 0:
        parser.error("Wolfram budgets must be non-negative")
    if args.freeze_credit_ledger and not args.credit_ledger_input:
        parser.error("--freeze-credit-ledger requires --credit-ledger-input")

    shard_count = min(args.shards, args.attempts)
    counts = [args.attempts // shard_count] * shard_count
    for index in range(args.attempts % shard_count):
        counts[index] += 1
    args.run_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    offsets: list[int] = []
    running_offset = 0
    for count in counts:
        offsets.append(running_offset)
        running_offset += count
    with ThreadPoolExecutor(max_workers=shard_count) as executor:
        futures = {
            executor.submit(
                _run_shard,
                shard=shard,
                count=count,
                offset=offsets[shard],
                args=args,
                output=args.run_dir / f"shard-{shard:02d}.json",
            ): shard
            for shard, count in enumerate(counts)
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                json.dumps(
                    {
                        "shard": result["shard"],
                        "status": result["status"],
                        "solved": result.get("solved"),
                        "elapsed_seconds": result["elapsed_seconds"],
                    }
                ),
                flush=True,
            )
    results.sort(key=lambda item: item["shard"])

    attempts: list[dict[str, Any]] = []
    for result in results:
        for item in result.get("attempt_results", []):
            attempts.append(
                {
                    **item,
                    "shard": result["shard"],
                    "local_attempt": item["attempt"] - result["attempt_offset"],
                }
            )
    attempts.sort(key=lambda item: item["attempt"])
    solved = _aggregate_solved(results, attempts)
    certificate = next(
        (
            item["certificate"]
            for item in results
            if item.get("solved") and isinstance(item.get("certificate"), dict)
        ),
        None,
    )
    artifact = {
        "experiment": "hageo_independent_pass_at_k_process_sharded_no_llm",
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "uses_problem_id_in_search": False,
            "uses_expected_answer": False,
            "rounds_n": args.rounds,
            "attempts_k": args.attempts,
            "process_shards": shard_count,
            "seed": args.seed,
            "candidate_policy": args.candidate_policy,
            "rank_temperature": args.rank_temperature,
            "incremental_prefix": args.incremental_prefix,
            "feedback_candidates": args.feedback_candidates,
            "feedback_workers": args.feedback_workers,
            "max_verification_concurrency": (
                args.max_verification_concurrency or args.feedback_workers
            ),
            "exact_specialist_timeout_seconds": getattr(
                args, "exact_specialist_timeout_seconds", 0.0
            ),
            "exact_specialist_representation": getattr(
                args, "exact_specialist_representation", "goal_local_relational"
            ),
            "exact_specialist_saturation_rounds": getattr(
                args, "exact_specialist_saturation_rounds", 1
            ),
            "exact_lemma_limit": getattr(args, "exact_lemma_limit", 0),
            "gclc_exe": (
                getattr(args, "gclc_exe").resolve().as_posix()
                if getattr(args, "gclc_exe", None)
                else None
            ),
            "gclc_methods": getattr(args, "gclc_methods", "wu"),
            "gclc_timeout_seconds": getattr(args, "gclc_timeout_seconds", 0),
            "gclc_lemma_limit": getattr(args, "gclc_lemma_limit", 0),
            "gclc_incidence_samples": getattr(args, "gclc_incidence_samples", 0),
            "wolfram_exe": (
                getattr(args, "wolfram_exe").resolve().as_posix()
                if getattr(args, "wolfram_exe", None)
                else None
            ),
            "wolfram_timeout_seconds": getattr(args, "wolfram_timeout_seconds", 0),
            "wolfram_preprocessing": getattr(
                args, "wolfram_preprocessing", "local_relational"
            ),
            "wolfram_reduction_mode": getattr(
                args, "wolfram_reduction_mode", "extended_groebner"
            ),
            "wolfram_saturation_mode": getattr(
                args, "wolfram_saturation_mode", "none"
            ),
            "wolfram_max_saturation_factors": getattr(
                args, "wolfram_max_saturation_factors", 12
            ),
            "terminal_credit_ledger_input_sha256": (
                hashlib.sha256(args.credit_ledger_input.read_bytes()).hexdigest()
                if args.credit_ledger_input
                else None
            ),
            "terminal_credit_ledger_frozen": args.freeze_credit_ledger,
            "incidence_workers": args.incidence_workers,
            "incidence_preselect_limit": args.incidence_preselect_limit,
            "trajectory_policy": (
                "hageo_incidence_gate_then_mmt_theory_view_ranking"
                if args.candidate_policy in {"mmt-hageo", "mmt-hageo-lite"}
                else "mmt_theory_view_rank_biased_sampling"
                if args.candidate_policy == "mmt-sheaf"
                else "typed_formal_sheaf_rank_biased_sampling"
                if args.candidate_policy == "typed-sheaf"
                else "typed_atom_static_residual_native_feedback"
                if args.candidate_policy == "residual-static"
                else "typed_atom_closed_loop_residual_native_feedback"
                if args.candidate_policy == "residual-feedback"
                else "typed_atom_open_incidence_residual_portfolio_per_shard"
                if args.candidate_policy == "residual-portfolio"
                else "typed_atom_terminal_certificate_credit_per_shard"
                if args.candidate_policy == "terminal-credit"
                else "typed_atom_one_credit_plus_residual_portfolio_per_shard"
                if args.candidate_policy == "terminal-credit-mixed"
                else "typed_atom_obligation_unification_verified_credit_portfolio_per_shard"
                if args.candidate_policy == "obligation-credit-mixed"
                else "typed_contract_reverse_unification_residual_portfolio_per_shard"
                if args.candidate_policy == "contract-portfolio"
                else "typed_residual_bidirectional_construction_synthesis_per_shard"
                if args.candidate_policy == "residual-construction"
                else "independent_seeded_numerical_incidence_sampling"
            ),
            "truth_plane": (
                "native_or_gclc_or_replayed_wolfram_cofactor_certificate"
                if getattr(args, "gclc_exe", None)
                or getattr(args, "wolfram_exe", None)
                else "yuclid_native_certificate_replay_only"
            ),
        },
        "problem_name": args.problem_name,
        "solved": solved,
        "pass_at_k": solved,
        "completed_attempts": len(attempts),
        "unique_paths": len({tuple(item["path"]) for item in attempts}),
        "right_censored_shards": sum(
            item["status"] == "right_censored_timeout" for item in results
        ),
        "execution_error_shards": sum(
            item["status"] == "execution_error" for item in results
        ),
        "reused_shards": sum(bool(item.get("reused")) for item in results),
        "elapsed_seconds": time.perf_counter() - started,
        "certificate": certificate,
        "shards": results,
        "attempt_results": attempts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "problem": args.problem_name,
                "rounds": args.rounds,
                "attempts": args.attempts,
                "shards": shard_count,
                "solved": solved,
                "unique_paths": artifact["unique_paths"],
                "elapsed_seconds": artifact["elapsed_seconds"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
