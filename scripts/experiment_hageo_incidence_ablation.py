"""Paired ablation for HAGeo-style numerical incidence proposals.

The numerical layer only ranks auxiliary constructions.  A run is counted as
solved only when the unchanged native Yuclid verifier replays the certificate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
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
    treatment: str,
    output: Path,
    per_family_limit: int,
    branch_limit: int,
    beam_width: int,
    max_depth: int,
    max_workers: int,
    candidate_alignment: str,
    incidence_oversample_per_family: int,
) -> dict[str, Any]:
    incidence = "hageo" if treatment == "hageo" else "off"
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
        str(max_workers),
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
        candidate_alignment,
        "--candidate-incidence",
        incidence,
        "--incidence-oversample-per-family",
        str(incidence_oversample_per_family),
        "--branch-build-mode",
        "incremental",
        "--proof-dag-depth",
        "2",
        "--proof-dag-branches",
        "96",
        "--proof-dag-states",
        "20000",
        "--candidate-cone-depth",
        "2",
        "--candidate-cone-fragments",
        "48",
        "--candidate-cone-states",
        "500",
        "--candidate-cone-initial-states",
        "64",
        "--candidate-promotion-limit",
        "8",
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
        env={**os.environ, "PYTHONHASHSEED": "0"},
    )
    wall_seconds = time.perf_counter() - started
    if completed.returncode != 0:
        return {
            "problem": problem,
            "treatment": treatment,
            "returncode": completed.returncode,
            "wall_seconds": wall_seconds,
            "stderr_tail": completed.stderr[-2000:],
        }
    artifact = json.loads(output.read_text(encoding="utf-8"))
    incidence_audit = artifact["candidate_incidence"]
    alignment = artifact["candidate_alignment"]
    return {
        "problem": problem,
        "treatment": treatment,
        "returncode": 0,
        "wall_seconds": wall_seconds,
        "solved": artifact["solved"],
        "solved_path": artifact["solved_path"],
        "evaluated_paths": artifact["evaluated_paths"],
        "error_count": artifact["error_count"],
        "incidence_checked": incidence_audit["checked_candidates"],
        "incidence_heuristic": incidence_audit["heuristic_candidates"],
        "cone_search_states": alignment["cone_search_states"],
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
    parser.add_argument("--per-family-limit", type=int, default=2)
    parser.add_argument("--branch-limit", type=int, default=32)
    parser.add_argument("--beam-width", type=int, default=8)
    parser.add_argument("--max-depth", type=int, default=1)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument(
        "--candidate-alignment",
        choices=("proof-dag-lazy", "proof-dag-priority"),
        default="proof-dag-priority",
    )
    parser.add_argument("--incidence-oversample-per-family", type=int, default=16)
    parser.add_argument(
        "--treatments",
        nargs="+",
        choices=("control", "hageo"),
        default=("control", "hageo"),
    )
    args = parser.parse_args()

    args.run_dir.mkdir(parents=True, exist_ok=True)
    runs: list[dict[str, Any]] = []
    for problem in args.problems:
        for treatment in args.treatments:
            artifact = args.run_dir / f"{problem}-{treatment}.json"
            result = run_once(
                python=args.python.resolve(),
                dataset=args.dataset.resolve(),
                yuclid_exe=args.yuclid_exe.resolve(),
                runtime_path=args.runtime_path.resolve(),
                problem=problem,
                treatment=treatment,
                output=artifact.resolve(),
                per_family_limit=args.per_family_limit,
                branch_limit=args.branch_limit,
                beam_width=args.beam_width,
                max_depth=args.max_depth,
                max_workers=args.max_workers,
                candidate_alignment=args.candidate_alignment,
                incidence_oversample_per_family=(
                    args.incidence_oversample_per_family
                ),
            )
            runs.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    pairs: list[dict[str, Any]] = []
    for problem in args.problems:
        by_treatment = {
            run["treatment"]: run for run in runs if run["problem"] == problem
        }
        control = by_treatment.get("control", {})
        hageo = by_treatment.get("hageo", {})
        valid = control.get("returncode") == hageo.get("returncode") == 0
        pairs.append(
            {
                "problem": problem,
                "valid_pair": valid,
                "control_solved": control.get("solved"),
                "hageo_solved": hageo.get("solved"),
                "coverage_delta": (
                    int(bool(hageo.get("solved"))) - int(bool(control.get("solved")))
                    if valid
                    else None
                ),
                "evaluated_path_delta": (
                    hageo["evaluated_paths"] - control["evaluated_paths"]
                    if valid
                    else None
                ),
                "wall_seconds_delta": (
                    hageo["wall_seconds"] - control["wall_seconds"]
                    if valid
                    else None
                ),
            }
        )

    valid_runs = [run for run in runs if run["returncode"] == 0]
    summary = {
        "experiment": "hageo_numerical_incidence_ablation",
        "protocol": {
            "uses_external_llm": False,
            "numerical_layer": "proposal_ranking_only",
            "truth_plane": "yuclid_native_certificate_replay",
            "treatments": list(args.treatments),
            "problems": args.problems,
            "candidate_alignment": args.candidate_alignment,
            "incidence_oversample_per_family": (
                args.incidence_oversample_per_family
            ),
        },
        "runs": runs,
        "pairs": pairs,
        "aggregate": {
            "valid_run_count": len(valid_runs),
            "control_solved": sum(
                bool(run.get("solved"))
                for run in valid_runs
                if run["treatment"] == "control"
            ),
            "hageo_solved": sum(
                bool(run.get("solved"))
                for run in valid_runs
                if run["treatment"] == "hageo"
            ),
            "coverage_delta": sum(
                pair["coverage_delta"] or 0 for pair in pairs if pair["valid_pair"]
            ),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
