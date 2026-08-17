"""Run paired exact-search ablations for the pre-evaluation candidate gate."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def run_once(
    *,
    python: Path,
    dataset: Path,
    yuclid_exe: Path,
    runtime_path: Path,
    problem: str,
    mode: str,
    output: Path,
    branch_limit: int,
    beam_width: int,
    max_depth: int,
    max_workers: int,
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
        "--goal-directed-families",
        "--per-family-limit",
        "8",
        "--branch-limit",
        str(branch_limit),
        "--beam-width",
        str(beam_width),
        "--max-depth",
        str(max_depth),
        "--max-workers",
        str(max_workers),
        "--seed",
        "0",
        "--obligation-guided",
        "--require-generated-input-after-first",
        "--ranking",
        "structural",
        "--beam-ranking",
        "ar-residual-pareto",
        "--ar-profile",
        "all",
        "--candidate-gate",
        mode,
        "--progress",
        "none",
    ]
    started = time.perf_counter()
    completed = subprocess.run(
        command,
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
    )
    wall_seconds = time.perf_counter() - started
    if completed.returncode != 0:
        return {
            "problem": problem,
            "mode": mode,
            "returncode": completed.returncode,
            "wall_seconds": wall_seconds,
            "stderr_tail": completed.stderr[-2000:],
        }
    artifact = json.loads(output.read_text(encoding="utf-8"))
    gate = artifact["candidate_gate"]
    return {
        "problem": problem,
        "mode": mode,
        "returncode": 0,
        "wall_seconds": wall_seconds,
        "solved": artifact["solved"],
        "solved_path": artifact["solved_path"],
        "evaluated_paths": artifact["evaluated_paths"],
        "error_count": artifact["error_count"],
        "enumerated_candidates": gate["enumerated_candidates"],
        "selected_candidates": gate["selected_after_branch_limit"],
        "preflight_checked": gate["preflight_checked_count"],
        "preflight_rejected": gate["preflight_rejected_count"],
        "artifact": output.resolve().relative_to(ROOT).as_posix(),
        "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--problems", nargs="+", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--branch-limit", type=int, default=64)
    parser.add_argument("--beam-width", type=int, default=8)
    parser.add_argument("--max-depth", type=int, default=1)
    parser.add_argument("--max-workers", type=int, default=8)
    args = parser.parse_args()

    args.run_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    for problem in args.problems:
        for mode in ("off", "combined"):
            output = args.run_dir / f"{problem}-{mode}.json"
            result = run_once(
                python=args.python.resolve(),
                dataset=args.dataset.resolve(),
                yuclid_exe=args.yuclid_exe.resolve(),
                runtime_path=args.runtime_path.resolve(),
                problem=problem,
                mode=mode,
                output=output.resolve(),
                branch_limit=args.branch_limit,
                beam_width=args.beam_width,
                max_depth=args.max_depth,
                max_workers=args.max_workers,
            )
            runs.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    pairs: list[dict[str, Any]] = []
    for problem in args.problems:
        by_mode = {run["mode"]: run for run in runs if run["problem"] == problem}
        off = by_mode["off"]
        combined = by_mode["combined"]
        valid = off["returncode"] == combined["returncode"] == 0
        pairs.append(
            {
                "problem": problem,
                "valid_pair": valid,
                "proof_preserved": (
                    valid
                    and off["solved"] == combined["solved"]
                    and (
                        not off["solved"]
                        or off["solved_path"] == combined["solved_path"]
                    )
                ),
                "evaluated_path_delta": (
                    combined["evaluated_paths"] - off["evaluated_paths"]
                    if valid
                    else None
                ),
                "error_delta": (
                    combined["error_count"] - off["error_count"]
                    if valid
                    else None
                ),
                "wall_seconds_delta": (
                    combined["wall_seconds"] - off["wall_seconds"]
                    if valid
                    else None
                ),
            }
        )
    summary = {
        "experiment": "exact_pre_evaluation_candidate_gate_ablation",
        "uses_external_llm": False,
        "uses_problem_or_answer_memory": False,
        "search_budget": {
            "branch_limit": args.branch_limit,
            "beam_width": args.beam_width,
            "max_depth": args.max_depth,
            "max_workers": args.max_workers,
        },
        "runs": runs,
        "pairs": pairs,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
