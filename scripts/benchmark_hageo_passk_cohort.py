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
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


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
    }
    observed = {key: protocol.get(key) for key in expected}
    if artifact.get("problem_name") != problem_name or observed != expected:
        raise ValueError(
            f"incompatible resume artifact for {problem_name}: "
            f"expected={expected}, observed={observed}"
        )
    return {
        "problem_name": problem_name,
        "status": "solved" if artifact["solved"] else "unsolved",
        "solved": bool(artifact["solved"]),
        "completed_attempts": int(artifact["completed_attempts"]),
        "unique_paths": int(artifact["unique_paths"]),
        "right_censored_shards": int(artifact["right_censored_shards"]),
        "execution_error_shards": int(artifact["execution_error_shards"]),
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
        "--candidate-limit",
        str(args.candidate_limit),
        "--timeout-seconds",
        str(args.problem_timeout_seconds),
        "--ar-profile",
        args.ar_profile,
    ]
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
            "trajectory_policy": "independent_seeded_numerical_incidence_sampling",
            "truth_plane": "yuclid_native_certificate_replay_only",
        },
        "summary": {
            "problems": len(names),
            "completed_problems": len(ordered),
            "missing_problems": len(missing),
            "complete": not missing,
            "solved": len(solved_names),
            "pass_at_k": len(solved_names) / len(names),
            "completed_attempts": sum(item.get("completed_attempts", 0) for item in ordered),
            "right_censored_problems": sum(item["status"] == "right_censored_timeout" for item in ordered),
            "execution_errors": sum(item["status"] == "execution_error" for item in ordered),
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
    parser.add_argument("--candidate-limit", type=int, default=64)
    parser.add_argument("--problem-timeout-seconds", type=float, default=1200.0)
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    parser.add_argument("--resume-existing", action="store_true")
    args = parser.parse_args()
    if min(args.rounds, args.attempts, args.max_parallel_problems, args.shards_per_problem) < 1:
        parser.error("rounds, attempts, parallelism, and shards must be positive")

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
