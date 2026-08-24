"""Rebuild an auxiliary cohort report from durable per-problem artifacts."""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def _load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _display(path: Path) -> str:
    resolved = path.resolve()
    return (
        resolved.relative_to(ROOT).as_posix()
        if resolved.is_relative_to(ROOT)
        else resolved.as_posix()
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def result_from_artifact(problem: str, path: Path) -> dict[str, Any]:
    artifact = _load(path)
    if str(artifact.get("problem_name")) != problem:
        raise ValueError(f"artifact problem mismatch: expected {problem}, got {artifact.get('problem_name')}")
    protocol = artifact.get("protocol") or {}
    if protocol.get("uses_external_llm") is not False:
        raise ValueError(f"artifact does not certify LLM-free execution: {path}")

    confirmation = artifact.get("confirmation") or {}
    solved = bool(artifact.get("solved"))
    native_confirmed = bool(
        solved
        and confirmation.get("solved")
        and confirmation.get("input_sha256")
        and confirmation.get("proof_sha256")
    )
    if solved and not native_confirmed:
        status = "unconfirmed_solution"
        result_solved: bool | None = None
    else:
        candidate_timeouts = int(artifact.get("right_censored_count", 0))
        status = (
            "solved"
            if solved
            else "right_censored_timeout"
            if candidate_timeouts > 0
            else "unsolved"
        )
        result_solved = solved if candidate_timeouts == 0 else None

    incidence = artifact.get("candidate_incidence") or {}
    records = artifact.get("records") or []
    elapsed_values = [
        float(record["elapsed_seconds"])
        for record in records
        if isinstance(record, dict) and record.get("elapsed_seconds") is not None
    ]
    return {
        "problem": problem,
        "status": status,
        "solved": result_solved,
        "native_confirmed": native_confirmed,
        "solved_path": artifact.get("solved_path"),
        "evaluated_paths": int(artifact.get("evaluated_paths", 0)),
        "right_censored_candidate_count": int(
            artifact.get("right_censored_count", 0)
        ),
        "incidence_checked": int(incidence.get("checked_candidates", 0)),
        "incidence_heuristic": int(incidence.get("heuristic_candidates", 0)),
        "elapsed_seconds": max(elapsed_values) if elapsed_values else None,
        "elapsed_semantics": (
            "maximum recorded candidate completion time; lower bound on wall-clock"
        ),
        "elapsed_is_lower_bound": True,
        "candidate_elapsed_sum_seconds": sum(elapsed_values),
        "candidate_elapsed_median_seconds": (
            statistics.median(elapsed_values) if elapsed_values else None
        ),
        "candidate_elapsed_max_seconds": max(elapsed_values) if elapsed_values else None,
        "artifact": _display(path),
        "artifact_sha256": _sha256(path),
    }


def rebuild_report(
    *,
    baseline_path: Path,
    problem_file: Path,
    run_dir: Path,
    fallback_reports: list[Path],
) -> dict[str, Any]:
    baseline = _load(baseline_path)
    selected = [
        line.strip()
        for line in problem_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if len(selected) != len(set(selected)):
        raise ValueError("problem-file contains duplicate IDs")
    baseline_unsolved = {
        str(name)
        for name, result in baseline["results"].items()
        if result["status"] != "solved"
    }
    outside = sorted(set(selected) - baseline_unsolved)
    if outside:
        raise ValueError(
            "problem-file contains IDs outside the baseline-unsolved set: "
            + ", ".join(outside)
        )

    fallback_runs: dict[str, dict[str, Any]] = {}
    for report_path in fallback_reports:
        for run in _load(report_path).get("runs", ()):
            fallback = dict(run)
            fallback["elapsed_source_report"] = _display(report_path)
            fallback_runs[str(run["problem"])] = fallback

    runs: list[dict[str, Any]] = []
    missing: list[str] = []
    for problem in selected:
        artifact = run_dir / f"{problem}.json"
        if artifact.is_file():
            result = result_from_artifact(problem, artifact)
            fallback = fallback_runs.get(problem)
            if fallback is not None and fallback.get("elapsed_seconds") is not None:
                fallback_sha = fallback.get("artifact_sha256")
                if fallback_sha and fallback_sha != result["artifact_sha256"]:
                    raise ValueError(
                        f"fallback artifact hash mismatch for {problem}: "
                        f"{fallback_sha} != {result['artifact_sha256']}"
                    )
                result["elapsed_seconds"] = float(fallback["elapsed_seconds"])
                result["elapsed_semantics"] = "wall-clock time from source cohort report"
                result["elapsed_is_lower_bound"] = False
                result["elapsed_source_report"] = fallback["elapsed_source_report"]
            runs.append(result)
        elif problem in fallback_runs:
            run = dict(fallback_runs[problem])
            if run.get("status") not in {
                "right_censored_timeout",
                "timeout",
                "execution_error",
            }:
                raise ValueError(
                    f"fallback for {problem} lacks a durable artifact and is not censored"
                )
            if run.get("elapsed_seconds") is not None:
                run["elapsed_semantics"] = "wall-clock time from source cohort report"
                run["elapsed_is_lower_bound"] = False
            runs.append(run)
        else:
            missing.append(problem)
    if missing:
        raise ValueError("missing durable results for: " + ", ".join(missing))

    runs.sort(key=lambda item: str(item["problem"]))
    solved_names = sorted(
        str(item["problem"]) for item in runs if item.get("solved") is True
    )
    right_censored = sum(
        item.get("status") in {"timeout", "right_censored_timeout"}
        for item in runs
    )
    execution_errors = sum(
        item.get("status") in {"execution_error", "unconfirmed_solution"}
        for item in runs
    )
    completed = len(runs) - right_censored - execution_errors
    baseline_solved = int(baseline["summary"]["solved"])
    total = int(baseline["summary"]["total"])
    certified_solved = baseline_solved + len(solved_names)
    return {
        "experiment": "hageo409_typed_auxiliary_reconstructed_cohort",
        "run_state": {
            "complete": True,
            "finished_count": len(runs),
            "pending_count": 0,
            "finished_problem_names": [str(item["problem"]) for item in runs],
        },
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "selection": "explicit baseline-unsolved problem-file",
            "problem_file": _display(problem_file),
            "selected_count": len(selected),
            "truth_plane": "native_yuclid_certificate_replay",
            "reconstruction": (
                "durable per-problem artifacts plus explicit censored fallback runs"
            ),
            "mixed_search_budgets": True,
            "timeout_semantics": (
                "right-censored unknown; never counted as a wrong answer or a proof"
            ),
            "inputs": {
                "baseline": {"path": _display(baseline_path), "sha256": _sha256(baseline_path)},
                "run_dir": _display(run_dir),
                "fallback_reports": [
                    {"path": _display(path), "sha256": _sha256(path)}
                    for path in fallback_reports
                ],
            },
        },
        "summary": {
            "baseline_total": total,
            "baseline_solved": baseline_solved,
            "pilot_total": len(selected),
            "newly_solved": len(solved_names),
            "newly_solved_names": solved_names,
            "heldout_portfolio_solved": certified_solved,
            "heldout_portfolio_score": certified_solved / total,
            "certified_score_lower_bound": certified_solved / total,
            "optimistic_score_upper_bound": (
                certified_solved + right_censored + execution_errors
            )
            / total,
            "completed_auxiliary_searches": completed,
            "conditional_new_solution_rate": (
                len(solved_names) / completed if completed else None
            ),
            "time_censored": right_censored,
            "execution_errors": execution_errors,
            "unprocessed": 0,
            "score_is_lower_bound": right_censored > 0 or execution_errors > 0,
        },
        "selected_problem_names": sorted(selected),
        "runs": runs,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--problem-file", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--fallback-report", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    report = rebuild_report(
        baseline_path=args.baseline.resolve(),
        problem_file=args.problem_file.resolve(),
        run_dir=args.run_dir.resolve(),
        fallback_reports=[path.resolve() for path in args.fallback_report],
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
