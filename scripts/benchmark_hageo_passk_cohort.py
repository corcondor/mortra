"""Run one fixed HAGeo Pass@K protocol across a problem cohort.

The cohort runner only schedules independent existing search trajectories.  It
does not inspect expected answers, auxiliary clauses, or problem identifiers
while constructing a trajectory.
"""

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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _artifact_result(
    problem_name: str,
    output: Path,
    *,
    args: argparse.Namespace,
    elapsed_seconds: float,
    reused: bool,
) -> dict[str, Any]:
    artifact = json.loads(output.read_text(encoding="utf-8"))
    protocol = artifact.get("protocol", {})
    expected = {
        "rounds_n": args.rounds,
        "attempts_k": args.attempts,
        "seed": args.seed,
        "candidate_policy": args.candidate_policy,
        "incremental_prefix": args.incremental_prefix,
        "incidence_preselect_limit": args.incidence_preselect_limit,
        "incidence_workers": args.incidence_workers,
        "rank_temperature": args.rank_temperature,
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
    if artifact.get("problem_name") != problem_name or observed != expected:
        raise ValueError(
            f"incompatible resume artifact for {problem_name}: "
            f"expected={expected}, observed={observed}"
        )
    right_censored_shards = int(artifact["right_censored_shards"])
    execution_error_shards = int(artifact["execution_error_shards"])
    completed_attempts = int(artifact["completed_attempts"])
    if artifact["solved"]:
        status = "solved"
    elif right_censored_shards > 0 or completed_attempts < args.attempts:
        status = "right_censored_timeout"
    elif execution_error_shards > 0:
        status = "execution_error"
    else:
        status = "unsolved"
    return {
        "problem_name": problem_name,
        "status": status,
        "solved": bool(artifact["solved"]),
        "completed_attempts": completed_attempts,
        "unique_paths": int(artifact["unique_paths"]),
        "right_censored_shards": right_censored_shards,
        "execution_error_shards": execution_error_shards,
        "artifact": output.resolve().relative_to(ROOT).as_posix(),
        "artifact_sha256": _sha256(output),
        "elapsed_seconds": elapsed_seconds,
        "reused": reused,
    }


def _run_problem(
    problem_name: str,
    *,
    args: argparse.Namespace,
    run_dir: Path,
) -> dict[str, Any]:
    safe_name = "".join(char if char.isalnum() or char in "-_" else "_" for char in problem_name)
    output = run_dir / f"{safe_name}.json"
    shard_dir = run_dir / safe_name
    if args.resume_existing and output.is_file():
        return _artifact_result(
            problem_name,
            output,
            args=args,
            elapsed_seconds=0.0,
            reused=True,
        )
    command = [
        str(args.python),
        "-B",
        str(ROOT / "scripts" / "benchmark_hageo_passk_sharded.py"),
        "--python",
        str(args.python),
        "--dataset",
        str(args.dataset),
        "--problem-name",
        problem_name,
        "--yuclid-exe",
        str(args.yuclid_exe),
        "--runtime-path",
        str(args.runtime_path),
        "--output",
        str(output),
        "--run-dir",
        str(shard_dir),
        "--rounds",
        str(args.rounds),
        "--attempts",
        str(args.attempts),
        "--shards",
        str(args.shards_per_problem),
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
        "--timeout-seconds",
        str(args.problem_timeout_seconds),
        "--ar-profile",
        args.ar_profile,
    ]
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
    if args.credit_ledger_input:
        command.extend(("--credit-ledger-input", str(args.credit_ledger_input)))
    if args.freeze_credit_ledger:
        command.append("--freeze-credit-ledger")
    if args.resume_existing:
        command.append("--resume-existing-shards")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=args.problem_timeout_seconds + 30.0,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
    except subprocess.TimeoutExpired:
        return {
            "problem_name": problem_name,
            "status": "right_censored_timeout",
            "solved": False,
            "elapsed_seconds": time.perf_counter() - started,
        }
    if completed.returncode != 0 or not output.is_file():
        return {
            "problem_name": problem_name,
            "status": "execution_error",
            "solved": False,
            "returncode": completed.returncode,
            "stderr_tail": completed.stderr[-2000:],
            "stdout_tail": completed.stdout[-2000:],
            "elapsed_seconds": time.perf_counter() - started,
        }
    return _artifact_result(
        problem_name,
        output,
        args=args,
        elapsed_seconds=time.perf_counter() - started,
        reused=False,
    )


def _problem_names(args: argparse.Namespace) -> list[str]:
    if args.problem_name:
        names = list(dict.fromkeys(args.problem_name))
    elif args.problem_file:
        names = [
            line.strip()
            for line in args.problem_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        names = list(dict.fromkeys(names))
    else:
        raise ValueError("provide --problem-name or --problem-file")
    if not names:
        raise ValueError("problem cohort is empty")
    return names


def _build_report(
    names: list[str],
    results: list[dict[str, Any]],
    *,
    args: argparse.Namespace,
    started: float,
) -> dict[str, Any]:
    by_name = {item["problem_name"]: item for item in results}
    ordered = [by_name[name] for name in names if name in by_name]
    missing = [name for name in names if name not in by_name]
    solved_names = [item["problem_name"] for item in ordered if item["solved"]]
    right_censored = sum(
        item["status"] == "right_censored_timeout" for item in ordered
    )
    execution_errors = sum(item["status"] == "execution_error" for item in ordered)
    fully_observed = [
        item for item in ordered if item["status"] in {"solved", "unsolved"}
    ]
    return {
        "experiment": "hageo_fixed_cohort_independent_pass_at_k_no_llm",
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "uses_problem_id_in_search": False,
            "uses_expected_answer": False,
            "cohort_fixed_before_search": True,
            "rounds_n": args.rounds,
            "attempts_k_per_problem": args.attempts,
            "seed": args.seed,
            "per_family_limit": args.per_family_limit,
            "incidence_oversample_per_family": args.incidence_oversample_per_family,
            "candidate_limit": args.candidate_limit,
            "candidate_policy": args.candidate_policy,
            "rank_temperature": args.rank_temperature,
            "incremental_prefix": args.incremental_prefix,
            "incidence_workers": args.incidence_workers,
            "incidence_preselect_limit": args.incidence_preselect_limit,
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
            "wolfram_saturation_mode": getattr(
                args, "wolfram_saturation_mode", "none"
            ),
            "wolfram_max_saturation_factors": getattr(
                args, "wolfram_max_saturation_factors", 12
            ),
            "terminal_credit_ledger_input_sha256": (
                hashlib.sha256(getattr(args, "credit_ledger_input").read_bytes()).hexdigest()
                if getattr(args, "credit_ledger_input", None)
                else None
            ),
            "terminal_credit_ledger_frozen": getattr(
                args, "freeze_credit_ledger", None
            ),
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
                else "typed_atom_open_incidence_residual_portfolio"
                if args.candidate_policy == "residual-portfolio"
                else "typed_atom_terminal_certificate_credit"
                if args.candidate_policy == "terminal-credit"
                else "typed_atom_one_credit_plus_residual_portfolio"
                if args.candidate_policy == "terminal-credit-mixed"
                else "typed_atom_obligation_unification_verified_credit_portfolio"
                if args.candidate_policy == "obligation-credit-mixed"
                else "typed_contract_reverse_unification_residual_portfolio"
                if args.candidate_policy == "contract-portfolio"
                else "typed_residual_bidirectional_construction_synthesis"
                if args.candidate_policy == "residual-construction"
                else "independent_seeded_numerical_incidence_sampling"
            ),
            "truth_plane": (
                "native_or_typed_exchange_or_gclc_or_replayed_wolfram_cofactor_or_terminal_exact_replay"
                if getattr(args, "exact_specialist_timeout_seconds", 0) > 0
                or getattr(args, "gclc_timeout_seconds", 0) > 0
                or getattr(args, "wolfram_timeout_seconds", 0) > 0
                else "yuclid_native_certificate_replay_only"
            ),
        },
        "summary": {
            "problems": len(names),
            "completed_problems": len(ordered),
            "missing_problems": len(missing),
            "complete": not missing and right_censored == 0 and execution_errors == 0,
            "solved": len(solved_names),
            "pass_at_k": (
                len(solved_names) / len(names)
                if not missing and right_censored == 0 and execution_errors == 0
                else None
            ),
            "fully_observed_problems": len(fully_observed),
            "fully_observed_pass_at_k": (
                len(solved_names) / len(fully_observed) if fully_observed else None
            ),
            "pass_at_k_lower_bound": len(solved_names) / len(names),
            "completed_attempts": sum(item.get("completed_attempts", 0) for item in ordered),
            "right_censored_problems": right_censored,
            "execution_errors": execution_errors,
            "reused_problems": sum(bool(item.get("reused")) for item in ordered),
            "elapsed_seconds": time.perf_counter() - started,
        },
        "solved_names": solved_names,
        "missing_names": missing,
        "results": ordered,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-name", action="append", default=[])
    parser.add_argument("--problem-file", type=Path)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--attempts", type=int, default=16)
    parser.add_argument("--max-parallel-problems", type=int, default=8)
    parser.add_argument("--shards-per-problem", type=int, default=1)
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
    parser.add_argument("--problem-timeout-seconds", type=float, default=1200.0)
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    parser.add_argument("--resume-existing", action="store_true")
    args = parser.parse_args()
    if min(args.rounds, args.attempts, args.max_parallel_problems, args.shards_per_problem) < 1:
        parser.error("rounds, attempts, parallelism, and shards must be positive")
    if args.wolfram_timeout_seconds < 0 or args.wolfram_max_saturation_factors < 0:
        parser.error("Wolfram budgets must be non-negative")
    if args.freeze_credit_ledger and not args.credit_ledger_input:
        parser.error("--freeze-credit-ledger requires --credit-ledger-input")

    names = _problem_names(args)
    args.run_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(args.max_parallel_problems, len(names))) as executor:
        futures = {
            executor.submit(_run_problem, name, args=args, run_dir=args.run_dir): name
            for name in names
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                json.dumps(
                    {
                        "problem": result["problem_name"],
                        "status": result["status"],
                        "completed_attempts": result.get("completed_attempts", 0),
                        "elapsed_seconds": result["elapsed_seconds"],
                    }
                ),
                flush=True,
            )
            checkpoint = _build_report(names, results, args=args, started=started)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(checkpoint, indent=2) + "\n", encoding="utf-8"
            )
    report = _build_report(names, results, args=args, started=started)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(report["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
