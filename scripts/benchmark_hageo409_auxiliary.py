"""Frozen HAGeo-409 held-out pilot for typed HAGeo auxiliary search."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
import os
from pathlib import Path
import subprocess
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def require_same_report_cohort(
    report: dict[str, Any], selected: list[str], *, output: Path
) -> None:
    """Prevent a subset retry from silently replacing a larger cohort report."""
    prior_selected = report.get("selected_problem_names")
    if prior_selected is None:
        return
    if set(map(str, prior_selected)) != set(selected):
        raise ValueError(
            "refusing to replace an existing report with a different problem cohort: "
            f"{output}. Use a distinct --output path for subset retries."
        )


def write_json_atomic(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f"{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    for attempt in range(8):
        try:
            temporary.replace(path)
            return
        except PermissionError:
            if attempt == 7:
                raise
            time.sleep(0.01 * (2**attempt))


def bounded_worker_counts(
    *,
    problem_workers: int,
    candidate_workers: int,
    max_total_native_workers: int,
) -> tuple[int, int]:
    """Optionally bound nested Yuclid concurrency without changing candidates."""

    if problem_workers < 1 or candidate_workers < 1:
        raise ValueError("worker counts must be positive")
    if max_total_native_workers <= 0:
        return problem_workers, candidate_workers
    budget = max_total_native_workers
    effective_problem_workers = min(problem_workers, budget)
    per_problem_budget = max(1, budget // effective_problem_workers)
    effective_candidate_workers = min(candidate_workers, per_problem_budget)
    return effective_problem_workers, effective_candidate_workers


def run_problem(
    *,
    python: Path,
    dataset: Path,
    yuclid_exe: Path,
    runtime_path: Path,
    problem: str,
    output: Path,
    timeout_seconds: float,
    max_depth: int = 1,
    branch_limit: int = 16,
    beam_width: int = 6,
    seed: int = 0,
    beam_ranking: str = "ar-residual-pareto",
    controller: Path | None = None,
    per_family_limit: int = 1,
    incidence_oversample_per_family: int = 16,
    candidate_contract_synthesis: bool = False,
    enumeration_limit_per_family: int = 64,
    candidate_cone_timeout_seconds: float = 10.0,
    proof_dag_timeout_seconds: float = 10.0,
    yuclid_timeout_seconds: float = 0.0,
    candidate_workers: int = 2,
    resume_progress: bool = False,
) -> dict[str, Any]:
    command = [
        str(python),
        "-B",
        str(ROOT / "scripts" / "experiment_newclid_construction_stalk.py"),
        "--dataset",
        str(dataset),
        "--problem-name",
        problem,
        "--yuclid-exe",
        str(yuclid_exe),
        "--runtime-path",
        str(runtime_path),
        "--output",
        str(output),
        "--family-set",
        "extended",
        "--per-family-limit",
        str(per_family_limit),
        "--branch-limit",
        str(branch_limit),
        "--beam-width",
        str(beam_width),
        "--max-depth",
        str(max_depth),
        "--max-workers",
        str(max(1, candidate_workers)),
        "--seed",
        str(seed),
        "--obligation-guided",
        "--ranking",
        "structural",
        "--beam-ranking",
        beam_ranking,
        "--ar-profile",
        "all",
        "--candidate-gate",
        "combined",
        "--candidate-alignment",
        "proof-dag-priority",
        "--candidate-incidence",
        "hageo",
        "--incidence-oversample-per-family",
        str(incidence_oversample_per_family),
        "--branch-build-mode",
        "incremental",
        "--proof-dag-depth",
        "2",
        "--proof-dag-branches",
        "48",
        "--proof-dag-states",
        "10000",
        "--proof-dag-timeout-seconds",
        str(proof_dag_timeout_seconds),
        "--yuclid-timeout-seconds",
        str(yuclid_timeout_seconds),
        "--candidate-cone-depth",
        "2",
        "--candidate-cone-fragments",
        "32",
        "--candidate-cone-states",
        "250",
        "--candidate-cone-initial-states",
        "32",
        "--candidate-promotion-limit",
        "6",
        "--enumeration-limit-per-family",
        str(enumeration_limit_per_family),
        "--candidate-cone-timeout-seconds",
        str(candidate_cone_timeout_seconds),
        "--progress",
        "none",
    ]
    if controller is not None:
        command.extend(("--controller", str(controller)))
    if candidate_contract_synthesis:
        command.append("--candidate-contract-synthesis")
    if resume_progress and output.with_suffix(".progress.json").is_file():
        command.append("--resume-progress")
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
    except subprocess.TimeoutExpired:
        result: dict[str, Any] = {
            "problem": problem,
            "status": "right_censored_timeout",
            "solved": None,
            "elapsed_seconds": time.perf_counter() - started,
        }
        progress_path = output.with_suffix(".progress.json")
        if progress_path.is_file():
            result["checkpoint"] = progress_path.resolve().relative_to(ROOT).as_posix()
            result["checkpoint_sha256"] = hashlib.sha256(
                progress_path.read_bytes()
            ).hexdigest()
        return result
    if completed.returncode != 0 or not output.is_file():
        return {
            "problem": problem,
            "status": "execution_error",
            "returncode": completed.returncode,
            "stderr_tail": completed.stderr[-2000:],
            "elapsed_seconds": time.perf_counter() - started,
        }
    artifact = json.loads(output.read_text(encoding="utf-8"))
    confirmation = artifact.get("confirmation") or {}
    native_confirmed = bool(
        artifact.get("solved")
        and confirmation.get("solved")
        and confirmation.get("input_sha256")
        and confirmation.get("proof_sha256")
    )
    candidate_timeouts = int(artifact.get("right_censored_count", 0))
    incomplete = not artifact["solved"] and candidate_timeouts > 0
    return {
        "problem": problem,
        "status": (
            "solved"
            if artifact["solved"]
            else "right_censored_timeout"
            if incomplete
            else "unsolved"
        ),
        "solved": artifact["solved"] if not incomplete else None,
        "native_confirmed": native_confirmed,
        "solved_path": artifact["solved_path"],
        "evaluated_paths": artifact["evaluated_paths"],
        "right_censored_candidate_count": candidate_timeouts,
        "incidence_checked": artifact["candidate_incidence"]["checked_candidates"],
        "incidence_heuristic": artifact["candidate_incidence"][
            "heuristic_candidates"
        ],
        "elapsed_seconds": time.perf_counter() - started,
        "artifact": output.resolve().relative_to(ROOT).as_posix(),
        "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Number of baseline-unsolved IDs to run; 0 (default) means all.",
    )
    parser.add_argument(
        "--problem-file",
        type=Path,
        help=(
            "Optional newline-delimited problem IDs. Every ID must belong to "
            "the baseline-unsolved set; this takes precedence over --limit."
        ),
    )
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument(
        "--candidate-workers",
        type=int,
        default=2,
        help="Native candidate verifications run in parallel inside each problem.",
    )
    parser.add_argument(
        "--max-total-native-workers",
        type=int,
        default=0,
        help=(
            "Optional maximum nested Yuclid processes across the cohort; zero "
            "disables the cap. This is a resource guard, not a speedup claim."
        ),
    )
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument(
        "--yuclid-timeout-seconds",
        type=float,
        default=0.0,
        help=(
            "Per-candidate native verification budget; zero is unbounded. "
            "Candidate timeouts remain right-censored and are retryable."
        ),
    )
    parser.add_argument("--max-depth", type=int, default=1)
    parser.add_argument("--branch-limit", type=int, default=16)
    parser.add_argument("--beam-width", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--per-family-limit", type=int, default=1)
    parser.add_argument("--incidence-oversample-per-family", type=int, default=16)
    parser.add_argument(
        "--enumeration-limit-per-family",
        type=int,
        default=64,
        help="Finite tuple budget per construction family; 0 explicitly requests exhaustive enumeration.",
    )
    parser.add_argument(
        "--candidate-cone-timeout-seconds",
        type=float,
        default=10.0,
        help="Per-candidate typed proof-cone compilation budget.",
    )
    parser.add_argument(
        "--proof-dag-timeout-seconds",
        type=float,
        default=10.0,
        help="Initial open-proof-DAG compilation budget per goal.",
    )
    parser.add_argument(
        "--candidate-contract-synthesis",
        action="store_true",
        help="Enable finite typed construction synthesis from coherent obligations.",
    )
    parser.add_argument(
        "--beam-ranking",
        choices=(
            "ar-residual-pareto",
            "differentiable-consensus",
            "consensus-portfolio",
            "native-formal-sheaf",
            "native-formal-sheaf-portfolio",
            "unified-formal-sheaf-portfolio",
        ),
        default="ar-residual-pareto",
    )
    parser.add_argument("--controller", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--retry-timeouts",
        action="store_true",
        help="With --resume, rerun right-censored and execution-error items.",
    )
    parser.add_argument(
        "--retry-unsolved",
        action="store_true",
        help="With --resume, continue completed unsolved items at a deeper budget.",
    )
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Rebuild summary metadata from an existing complete report.",
    )
    args = parser.parse_args()
    effective_problem_workers, effective_candidate_workers = bounded_worker_counts(
        problem_workers=args.workers,
        candidate_workers=args.candidate_workers,
        max_total_native_workers=args.max_total_native_workers,
    )
    if args.beam_ranking in {
        "differentiable-consensus",
        "consensus-portfolio",
        "unified-formal-sheaf-portfolio",
    }:
        if args.controller is None:
            parser.error(f"--beam-ranking {args.beam_ranking} requires --controller")

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    unsolved = sorted(
        name
        for name in baseline["problem_names"]
        if baseline["results"][name]["status"] != "solved"
    )
    if args.problem_file is not None:
        requested = [
            line.strip()
            for line in args.problem_file.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if len(requested) != len(set(requested)):
            raise ValueError("problem-file contains duplicate IDs")
        unknown = sorted(set(requested) - set(unsolved))
        if unknown:
            raise ValueError(
                "problem-file contains IDs outside the baseline-unsolved set: "
                + ", ".join(unknown)
            )
        selected = sorted(requested)
    else:
        selected = unsolved[: args.limit] if args.limit > 0 else unsolved
    args.run_dir.mkdir(parents=True, exist_ok=True)
    previous: dict[str, dict[str, Any]] = {}
    prior_report: dict[str, Any] | None = None
    if args.output.is_file():
        prior_report = json.loads(args.output.read_text(encoding="utf-8"))
        require_same_report_cohort(prior_report, selected, output=args.output)
    if (args.resume or args.report_only) and prior_report is not None:
        previous = {
            item["problem"]: item
            for item in prior_report.get("runs", [])
            if args.report_only
            or item.get("status") == "solved"
            or (
                item.get("status") == "unsolved"
                and not args.retry_unsolved
            )
            or (
                args.resume
                and not args.retry_timeouts
                and item.get("status")
                in {"timeout", "right_censored_timeout", "execution_error"}
            )
        }
    if args.report_only and len(previous) != len(selected):
        raise ValueError("report-only requires one existing run for every selected ID")
    runs: list[dict[str, Any]] = [
        previous[name] for name in selected if name in previous
    ]
    pending = [name for name in selected if name not in previous]

    def write_report(*, complete: bool) -> dict[str, Any]:
        ordered_runs = sorted(runs, key=lambda item: item["problem"])
        newly_solved = [item["problem"] for item in ordered_runs if item.get("solved")]
        baseline_solved = int(baseline["summary"]["solved"])
        right_censored = sum(
            item.get("status") in {"timeout", "right_censored_timeout"}
            for item in ordered_runs
        )
        execution_errors = sum(
            item.get("status") == "execution_error" for item in ordered_runs
        )
        pending_count = len(selected) - len(ordered_runs)
        completed_searches = len(ordered_runs) - right_censored - execution_errors
        total = int(baseline["summary"]["total"])
        certified_solved = baseline_solved + len(newly_solved)
        report = {
            "experiment": "hageo409_typed_auxiliary_heldout_pilot",
            "run_state": {
                "complete": complete,
                "finished_count": len(ordered_runs),
                "pending_count": pending_count,
                "finished_problem_names": [item["problem"] for item in ordered_runs],
            },
            "protocol": {
                "uses_external_llm": False,
                "uses_dataset_auxiliary_clauses": False,
                "selection": (
                    "explicit baseline-unsolved problem-file"
                    if args.problem_file is not None
                    else (
                        "all baseline-unsolved held_out IDs"
                        if args.limit <= 0
                        else "lexicographically first baseline-unsolved held_out IDs"
                    )
                ),
                "problem_file": (
                    args.problem_file.resolve().relative_to(ROOT).as_posix()
                    if args.problem_file is not None
                    and args.problem_file.resolve().is_relative_to(ROOT)
                    else (
                        args.problem_file.resolve().as_posix()
                        if args.problem_file is not None
                        else None
                    )
                ),
                "selected_count": len(selected),
                "truth_plane": "native_yuclid_certificate_replay",
                "candidate_proposal": "typed HAGeo numerical incidence",
                "scheduler": "unified bidirectional priority queue",
                "search_budget": {
                    "auxiliary_depth": args.max_depth,
                    "candidate_paths_per_prefix": args.branch_limit,
                    "candidate_beam": args.beam_width,
                    "beam_ranking": args.beam_ranking,
                    "controller": (
                        args.controller.resolve().relative_to(ROOT).as_posix()
                        if args.controller is not None
                        else None
                    ),
                    "per_family_limit": args.per_family_limit,
                    "incidence_oversample_per_family": (
                        args.incidence_oversample_per_family
                    ),
                    "candidate_contract_synthesis": (
                        args.candidate_contract_synthesis
                    ),
                    "enumeration_limit_per_family": (
                        args.enumeration_limit_per_family
                    ),
                    "candidate_cone_timeout_seconds": (
                        args.candidate_cone_timeout_seconds
                    ),
                    "proof_dag_timeout_seconds": args.proof_dag_timeout_seconds,
                    "workers": args.workers,
                    "effective_problem_workers": effective_problem_workers,
                    "candidate_workers": args.candidate_workers,
                    "effective_candidate_workers": effective_candidate_workers,
                    "max_total_native_workers": (
                        args.max_total_native_workers
                        if args.max_total_native_workers > 0
                        else None
                    ),
                    "timeout_seconds_per_problem": args.timeout_seconds,
                },
                "paper_comparability": (
                    "configurable MORTRA ablation; report max_depth and evaluated "
                    "paths rather than claiming HAGeo N=6, K=2048/8192"
                ),
                "timeout_semantics": (
                    "right-censored unknown; never counted as a wrong answer or a proof"
                ),
            },
            "summary": {
                "baseline_total": baseline["summary"]["total"],
                "baseline_solved": baseline_solved,
                "pilot_total": len(selected),
                "newly_solved": len(newly_solved),
                "newly_solved_names": newly_solved,
                "heldout_portfolio_solved": certified_solved,
                "heldout_portfolio_score": certified_solved / total,
                "certified_score_lower_bound": certified_solved / total,
                "optimistic_score_upper_bound": (
                    certified_solved
                    + right_censored
                    + execution_errors
                    + pending_count
                )
                / total,
                "completed_auxiliary_searches": completed_searches,
                "conditional_new_solution_rate": (
                    len(newly_solved) / completed_searches
                    if completed_searches
                    else None
                ),
                "time_censored": right_censored,
                "execution_errors": execution_errors,
                "unprocessed": pending_count,
                "score_is_lower_bound": (
                    not complete or right_censored > 0 or execution_errors > 0
                ),
            },
            "selected_problem_names": selected,
            "runs": ordered_runs,
        }
        write_json_atomic(args.output, report)
        return report

    write_report(complete=not pending)
    with ThreadPoolExecutor(max_workers=effective_problem_workers) as executor:
        futures = {
            executor.submit(
                run_problem,
                python=args.python.resolve(),
                dataset=args.dataset.resolve(),
                yuclid_exe=args.yuclid_exe.resolve(),
                runtime_path=args.runtime_path.resolve(),
                problem=problem,
                output=(args.run_dir / f"{problem}.json").resolve(),
                timeout_seconds=args.timeout_seconds,
                max_depth=args.max_depth,
                branch_limit=args.branch_limit,
                beam_width=args.beam_width,
                seed=args.seed,
                beam_ranking=args.beam_ranking,
                controller=(args.controller.resolve() if args.controller else None),
                per_family_limit=args.per_family_limit,
                incidence_oversample_per_family=(
                    args.incidence_oversample_per_family
                ),
                candidate_contract_synthesis=args.candidate_contract_synthesis,
                enumeration_limit_per_family=args.enumeration_limit_per_family,
                candidate_cone_timeout_seconds=args.candidate_cone_timeout_seconds,
                proof_dag_timeout_seconds=args.proof_dag_timeout_seconds,
                yuclid_timeout_seconds=args.yuclid_timeout_seconds,
                candidate_workers=effective_candidate_workers,
                resume_progress=(args.retry_timeouts or args.retry_unsolved),
            ): problem
            for problem in pending
        }
        for future in as_completed(futures):
            problem = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # preserve the rest of a long cohort run
                result = {
                    "problem": problem,
                    "status": "execution_error",
                    "solved": None,
                    "error": f"{type(exc).__name__}: {exc}",
                }
            runs.append(result)
            write_report(complete=len(runs) == len(selected))
            print(json.dumps(result, ensure_ascii=False), flush=True)

    report = write_report(complete=True)
    print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
