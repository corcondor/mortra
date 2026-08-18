"""Compare prefix replay with prefix-cached construction under one search budget."""

from __future__ import annotations

import argparse
import json
import subprocess
import time
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def exact_search_equivalent(
    replay: dict[str, Any], incremental: dict[str, Any]
) -> bool:
    return bool(
        replay["returncode"] == incremental["returncode"] == 0
        and replay["solved"]
        and replay["solved"] == incremental["solved"]
        and replay["solved_path"] == incremental["solved_path"]
        and replay["evaluated_paths"] == incremental["evaluated_paths"]
        and replay["error_count"] == incremental["error_count"]
        and replay["input_sha256"]
        and replay["input_sha256"] == incremental["input_sha256"]
    )


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
        "combined",
        "--candidate-alignment",
        "off",
        "--branch-build-mode",
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
            "mode": mode,
            "returncode": completed.returncode,
            "wall_seconds": wall_seconds,
            "stderr_tail": completed.stderr[-2000:],
        }
    artifact = json.loads(output.read_text(encoding="utf-8"))
    confirmation = artifact.get("confirmation", {})
    return {
        "mode": mode,
        "returncode": 0,
        "wall_seconds": wall_seconds,
        "solved": artifact["solved"],
        "solved_path": artifact["solved_path"],
        "evaluated_paths": artifact["evaluated_paths"],
        "error_count": artifact["error_count"],
        "input_sha256": confirmation.get("input_sha256"),
        "proof_sha256_order_sensitive": confirmation.get("proof_sha256"),
        "prefix_state_cache": artifact["prefix_state_cache"],
        "artifact": output.resolve().relative_to(ROOT).as_posix(),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--problem", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--branch-limit", type=int, default=24)
    parser.add_argument("--beam-width", type=int, default=8)
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--max-workers", type=int, default=8)
    args = parser.parse_args()

    args.run_dir.mkdir(parents=True, exist_ok=True)
    runs = [
        run_once(
            python=args.python.resolve(),
            dataset=args.dataset.resolve(),
            yuclid_exe=args.yuclid_exe.resolve(),
            runtime_path=args.runtime_path.resolve(),
            problem=args.problem,
            mode=mode,
            output=(args.run_dir / f"{args.problem}-{mode}.json").resolve(),
            branch_limit=args.branch_limit,
            beam_width=args.beam_width,
            max_depth=args.max_depth,
            max_workers=args.max_workers,
        )
        for mode in ("prefix-replay", "incremental")
    ]
    by_mode = {run["mode"]: run for run in runs}
    replay = by_mode["prefix-replay"]
    incremental = by_mode["incremental"]
    valid = replay["returncode"] == incremental["returncode"] == 0
    equivalent = exact_search_equivalent(replay, incremental)
    artifact = {
        "experiment": "prefix_stable_incremental_construction_ablation",
        "uses_external_llm": False,
        "uses_problem_or_answer_memory": False,
        "problem": args.problem,
        "search_budget": {
            "branch_limit": args.branch_limit,
            "beam_width": args.beam_width,
            "max_depth": args.max_depth,
            "max_workers": args.max_workers,
        },
        "runs": runs,
        "equivalent_exact_input_and_search_result": equivalent,
        "wall_seconds_delta": (
            incremental["wall_seconds"] - replay["wall_seconds"] if valid else None
        ),
        "wall_seconds_reduction_ratio": (
            (replay["wall_seconds"] - incremental["wall_seconds"])
            / replay["wall_seconds"]
            if valid and replay["wall_seconds"]
            else None
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(artifact, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(artifact, ensure_ascii=False, indent=2))
    raise SystemExit(0 if equivalent else 1)


if __name__ == "__main__":
    main()
