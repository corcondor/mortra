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
    max_depth: int = 1,
    branch_limit: int = 16,
    beam_width: int = 6,
    seed: int = 0,
    beam_ranking: str = "ar-residual-pareto",
    controller: Path | None = None,
    per_family_limit: int = 1,
    incidence_oversample_per_family: int = 16,
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
        "2",
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
    if controller is not None:
        command.extend(("--controller", str(controller)))
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
            "status": "right_censored_timeout",
            "solved": None,
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
    confirmation = artifact.get("confirmation") or {}
    native_confirmed = bool(
        artifact.get("solved")
        and confirmation.get("solved")
        and confirmation.get("input_sha256")
        and confirmation.get("proof_sha256")
    )
    return {
        "problem": problem,
        "status": "solved" if artifact["solved"] else "unsolved",
        "solved": artifact["solved"],
        "native_confirmed": native_confirmed,
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
    parser.add_argument("--max-depth", type=int, default=1)
    parser.add_argument("--branch-limit", type=int, default=16)
    parser.add_argument("--beam-width", type=int, default=6)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--per-family-limit", type=int, default=1)
    parser.add_argument("--incidence-oversample-per-family", type=int, default=16)
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
        "--report-only",
        action="store_true",
        help="Rebuild summary metadata from an existing complete report.",
    )
    args = parser.parse_args()
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
    right_censored = sum(
        item.get("status") in {"timeout", "right_censored_timeout"}
        for item in runs
    )
    completed_searches = len(runs) - right_censored
    total = int(baseline["summary"]["total"])
    certified_solved = baseline_solved + len(newly_solved)
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
                "workers": args.workers,
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
            "optimistic_score_upper_bound": (certified_solved + right_censored) / total,
            "completed_auxiliary_searches": completed_searches,
            "conditional_new_solution_rate": (
                len(newly_solved) / completed_searches if completed_searches else None
            ),
            "time_censored": right_censored,
            "score_is_lower_bound": right_censored > 0,
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
