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


def run_problem(
    *,
    python: Path,
    dataset: Path,
    yuclid_exe: Path,
    runtime_path: Path,
    problem: str,
    output: Path,
    timeout_seconds: float,
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
        "1",
        "--branch-limit",
        "16",
        "--beam-width",
        "6",
        "--max-depth",
        "1",
        "--max-workers",
        "2",
        "--seed",
        "0",
        "--obligation-guided",
        "--ranking",
        "structural",
        "--beam-ranking",
        "ar-residual-pareto",
        "--ar-profile",
        "all",
        "--candidate-gate",
        "combined",
        "--candidate-alignment",
        "proof-dag-priority",
        "--candidate-incidence",
        "hageo",
        "--incidence-oversample-per-family",
        "16",
        "--branch-build-mode",
        "incremental",
        "--proof-dag-depth",
        "2",
        "--proof-dag-branches",
        "48",
        "--proof-dag-states",
        "10000",
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
        "--progress",
        "none",
    ]
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
        return {
            "problem": problem,
            "status": "timeout",
            "elapsed_seconds": time.perf_counter() - started,
        }
    if completed.returncode != 0 or not output.is_file():
        return {
            "problem": problem,
            "status": "execution_error",
            "returncode": completed.returncode,
            "stderr_tail": completed.stderr[-2000:],
            "elapsed_seconds": time.perf_counter() - started,
        }
    artifact = json.loads(output.read_text(encoding="utf-8"))
    return {
        "problem": problem,
        "status": "solved" if artifact["solved"] else "unsolved",
        "solved": artifact["solved"],
        "solved_path": artifact["solved_path"],
        "evaluated_paths": artifact["evaluated_paths"],
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
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument(
        "--report-only",
        action="store_true",
        help="Rebuild summary metadata from an existing complete report.",
    )
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    unsolved = sorted(
        name
        for name in baseline["problem_names"]
        if baseline["results"][name]["status"] != "solved"
    )
    selected = unsolved[: args.limit] if args.limit > 0 else unsolved
    args.run_dir.mkdir(parents=True, exist_ok=True)
    previous: dict[str, dict[str, Any]] = {}
    if (args.resume or args.report_only) and args.output.is_file():
        prior_report = json.loads(args.output.read_text(encoding="utf-8"))
        previous = {
            item["problem"]: item
            for item in prior_report.get("runs", [])
            if args.report_only
            or item.get("status") in {"solved", "unsolved"}
        }
    if args.report_only and len(previous) != len(selected):
        raise ValueError("report-only requires one existing run for every selected ID")
    runs: list[dict[str, Any]] = [
        previous[name] for name in selected if name in previous
    ]
    pending = [name for name in selected if name not in previous]
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
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
            ): problem
            for problem in pending
        }
        for future in as_completed(futures):
            result = future.result()
            runs.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    runs.sort(key=lambda item: item["problem"])
    newly_solved = [item["problem"] for item in runs if item.get("solved")]
    baseline_solved = int(baseline["summary"]["solved"])
    report = {
        "experiment": "hageo409_typed_auxiliary_heldout_pilot",
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "selection": "lexicographically first baseline-unsolved held_out IDs",
            "selected_count": len(selected),
            "truth_plane": "native_yuclid_certificate_replay",
            "candidate_proposal": "typed HAGeo numerical incidence",
            "scheduler": "unified bidirectional priority queue",
            "search_budget": {
                "auxiliary_depth": 1,
                "candidate_paths": 16,
                "candidate_beam": 6,
                "incidence_oversample_per_family": 16,
                "workers": args.workers,
                "timeout_seconds_per_problem": args.timeout_seconds,
            },
            "paper_comparability": (
                "bounded MORTRA ablation; not HAGeo N=6, K=2048/8192"
            ),
        },
        "summary": {
            "baseline_total": baseline["summary"]["total"],
            "baseline_solved": baseline_solved,
            "pilot_total": len(selected),
            "newly_solved": len(newly_solved),
            "newly_solved_names": newly_solved,
            "heldout_portfolio_solved": baseline_solved + len(newly_solved),
            "heldout_portfolio_score": (
                (baseline_solved + len(newly_solved))
                / int(baseline["summary"]["total"])
            ),
            "time_censored": sum(
                item.get("status") == "timeout" for item in runs
            ),
            "score_is_lower_bound": any(
                item.get("status") == "timeout" for item in runs
            ),
        },
        "selected_problem_names": selected,
        "runs": runs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
