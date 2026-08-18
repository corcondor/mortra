"""Paired ablation for finite OR-preserving proof-DAG candidate scheduling."""

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
    per_family_limit: int,
    branch_limit: int,
    max_workers: int,
    proof_dag_depth: int,
    proof_dag_branches: int,
    proof_dag_states: int,
    candidate_cone_depth: int,
    candidate_cone_fragments: int,
    candidate_cone_states: int,
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
        "7",
        "--max-depth",
        "1",
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
        mode,
        "--branch-build-mode",
        "incremental",
        "--proof-dag-depth",
        str(proof_dag_depth),
        "--proof-dag-branches",
        str(proof_dag_branches),
        "--proof-dag-states",
        str(proof_dag_states),
        "--candidate-cone-depth",
        str(candidate_cone_depth),
        "--candidate-cone-fragments",
        str(candidate_cone_fragments),
        "--candidate-cone-states",
        str(candidate_cone_states),
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
    alignment = artifact["candidate_alignment"]
    confirmation = artifact.get("confirmation") or {}
    return {
        "problem": problem,
        "mode": mode,
        "returncode": 0,
        "wall_seconds": wall_seconds,
        "solved": artifact["solved"],
        "solved_path": artifact["solved_path"],
        "evaluated_paths": artifact["evaluated_paths"],
        "error_count": artifact["error_count"],
        "input_sha256": confirmation.get("input_sha256"),
        "direct_or_meet_candidates": alignment["direct_match_candidates"],
        "cone_truncated_candidates": alignment["cone_truncated_candidates"],
        "cone_search_states": alignment["cone_search_states"],
        "proof_dag_branch_count": sum(
            item["branch_count"] for item in alignment["proof_dags"]
        ),
        "proof_dag_search_states": sum(
            item["search_states"] for item in alignment["proof_dags"]
        ),
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
    parser.add_argument("--per-family-limit", type=int, default=1)
    parser.add_argument("--branch-limit", type=int, default=32)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--proof-dag-depth", type=int, default=2)
    parser.add_argument("--proof-dag-branches", type=int, default=96)
    parser.add_argument("--proof-dag-states", type=int, default=20_000)
    parser.add_argument("--candidate-cone-depth", type=int, default=2)
    parser.add_argument("--candidate-cone-fragments", type=int, default=48)
    parser.add_argument("--candidate-cone-states", type=int, default=500)
    args = parser.parse_args()

    args.run_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    for problem in args.problems:
        for mode in ("off", "proof-dag-meet"):
            output = args.run_dir / f"{problem}-{mode}.json"
            result = run_once(
                python=args.python.resolve(),
                dataset=args.dataset.resolve(),
                yuclid_exe=args.yuclid_exe.resolve(),
                runtime_path=args.runtime_path.resolve(),
                problem=problem,
                mode=mode,
                output=output.resolve(),
                per_family_limit=args.per_family_limit,
                branch_limit=args.branch_limit,
                max_workers=args.max_workers,
                proof_dag_depth=args.proof_dag_depth,
                proof_dag_branches=args.proof_dag_branches,
                proof_dag_states=args.proof_dag_states,
                candidate_cone_depth=args.candidate_cone_depth,
                candidate_cone_fragments=args.candidate_cone_fragments,
                candidate_cone_states=args.candidate_cone_states,
            )
            runs.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    pairs: list[dict[str, Any]] = []
    for problem in args.problems:
        by_mode = {item["mode"]: item for item in runs if item["problem"] == problem}
        control = by_mode["off"]
        treatment = by_mode["proof-dag-meet"]
        valid = control["returncode"] == treatment["returncode"] == 0
        pairs.append(
            {
                "problem": problem,
                "valid_pair": valid,
                "control_success_preserved": (
                    valid
                    and (not control["solved"] or treatment["solved"])
                ),
                "same_solved_status": (
                    valid and control["solved"] == treatment["solved"]
                ),
                "same_path_when_both_solved": (
                    valid
                    and control["solved"]
                    and treatment["solved"]
                    and control["solved_path"] == treatment["solved_path"]
                ),
                "evaluated_path_delta": (
                    treatment["evaluated_paths"] - control["evaluated_paths"]
                    if valid
                    else None
                ),
                "wall_seconds_delta": (
                    treatment["wall_seconds"] - control["wall_seconds"]
                    if valid
                    else None
                ),
                "error_delta": (
                    treatment["error_count"] - control["error_count"]
                    if valid
                    else None
                ),
            }
        )

    valid_runs = [item for item in runs if item["returncode"] == 0]
    by_mode = {
        mode: [item for item in valid_runs if item["mode"] == mode]
        for mode in ("off", "proof-dag-meet")
    }
    summary = {
        "experiment": "or_preserving_proof_dag_meet_ablation",
        "uses_external_llm": False,
        "uses_problem_or_answer_memory": False,
        "acceptance_truth_plane": "yuclid_native_certificate_replay_only",
        "hypothesis": (
            "A finite typed forward/backward meet reduces exact candidate "
            "evaluations without changing proof outcomes."
        ),
        "search_budget": {
            "per_family_limit": args.per_family_limit,
            "branch_limit": args.branch_limit,
            "max_workers": args.max_workers,
            "proof_dag_depth": args.proof_dag_depth,
            "proof_dag_branches": args.proof_dag_branches,
            "proof_dag_states": args.proof_dag_states,
            "candidate_cone_depth": args.candidate_cone_depth,
            "candidate_cone_fragments": args.candidate_cone_fragments,
            "candidate_cone_states": args.candidate_cone_states,
        },
        "runs": runs,
        "pairs": pairs,
        "totals": {
            mode: {
                "solved": sum(item["solved"] for item in items),
                "evaluated_paths": sum(item["evaluated_paths"] for item in items),
                "errors": sum(item["error_count"] for item in items),
                "wall_seconds": sum(item["wall_seconds"] for item in items),
            }
            for mode, items in by_mode.items()
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
