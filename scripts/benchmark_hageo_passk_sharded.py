"""Run HAGeo-style independent attempts in separate CPU processes."""

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


def _run_shard(
    *,
    shard: int,
    count: int,
    offset: int,
    args: argparse.Namespace,
    output: Path,
) -> dict[str, Any]:
    command = [
        str(args.python),
        "-B",
        str(ROOT / "scripts" / "experiment_hageo_passk.py"),
        "--dataset",
        str(args.dataset),
        "--problem-name",
        args.problem_name,
        "--yuclid-exe",
        str(args.yuclid_exe),
        "--runtime-path",
        str(args.runtime_path),
        "--output",
        str(output),
        "--rounds",
        str(args.rounds),
        "--attempts",
        str(count),
        "--attempt-offset",
        str(offset),
        "--workers",
        "1",
        "--seed",
        str(args.seed),
        "--per-family-limit",
        str(args.per_family_limit),
        "--incidence-oversample-per-family",
        str(args.incidence_oversample_per_family),
        "--candidate-limit",
        str(args.candidate_limit),
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
            timeout=args.timeout_seconds,
            env={**os.environ, "PYTHONHASHSEED": "0"},
        )
    except subprocess.TimeoutExpired:
        return {
            "shard": shard,
            "status": "right_censored_timeout",
            "count": count,
            "elapsed_seconds": time.perf_counter() - started,
        }
    if completed.returncode != 0 or not output.is_file():
        return {
            "shard": shard,
            "status": "execution_error",
            "count": count,
            "returncode": completed.returncode,
            "stderr_tail": completed.stderr[-2000:],
            "elapsed_seconds": time.perf_counter() - started,
        }
    artifact = json.loads(output.read_text(encoding="utf-8"))
    return {
        "shard": shard,
        "status": "completed",
        "count": count,
        "seed": args.seed,
        "attempt_offset": offset,
        "solved": artifact["solved"],
        "unique_paths": artifact["unique_paths"],
        "completed_attempts": artifact["completed_attempts"],
        "attempt_results": artifact["attempt_results"],
        "certificate": artifact.get("certificate"),
        "artifact": output.resolve().relative_to(ROOT).as_posix(),
        "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-name", required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--attempts", type=int, default=64)
    parser.add_argument("--shards", type=int, default=8)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--per-family-limit", type=int, default=4)
    parser.add_argument("--incidence-oversample-per-family", type=int, default=16)
    parser.add_argument("--candidate-limit", type=int, default=64)
    parser.add_argument("--timeout-seconds", type=float, default=3600.0)
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    args = parser.parse_args()
    if args.attempts < 1 or args.shards < 1:
        parser.error("--attempts and --shards must be positive")

    shard_count = min(args.shards, args.attempts)
    counts = [args.attempts // shard_count] * shard_count
    for index in range(args.attempts % shard_count):
        counts[index] += 1
    args.run_dir.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    offsets: list[int] = []
    running_offset = 0
    for count in counts:
        offsets.append(running_offset)
        running_offset += count
    with ThreadPoolExecutor(max_workers=shard_count) as executor:
        futures = {
            executor.submit(
                _run_shard,
                shard=shard,
                count=count,
                offset=offsets[shard],
                args=args,
                output=args.run_dir / f"shard-{shard:02d}.json",
            ): shard
            for shard, count in enumerate(counts)
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(
                json.dumps(
                    {
                        "shard": result["shard"],
                        "status": result["status"],
                        "solved": result.get("solved"),
                        "elapsed_seconds": result["elapsed_seconds"],
                    }
                ),
                flush=True,
            )
    results.sort(key=lambda item: item["shard"])

    attempts: list[dict[str, Any]] = []
    for result in results:
        for item in result.get("attempt_results", []):
            attempts.append(
                {
                    **item,
                    "shard": result["shard"],
                    "local_attempt": item["attempt"] - result["attempt_offset"],
                }
            )
    attempts.sort(key=lambda item: item["attempt"])
    solved = any(item.get("solved", False) for item in attempts)
    artifact = {
        "experiment": "hageo_independent_pass_at_k_process_sharded_no_llm",
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "uses_problem_id_in_search": False,
            "uses_expected_answer": False,
            "rounds_n": args.rounds,
            "attempts_k": args.attempts,
            "process_shards": shard_count,
            "seed": args.seed,
            "trajectory_policy": "independent_seeded_numerical_incidence_sampling",
            "truth_plane": "yuclid_native_certificate_replay_only",
        },
        "problem_name": args.problem_name,
        "solved": solved,
        "pass_at_k": solved,
        "completed_attempts": len(attempts),
        "unique_paths": len({tuple(item["path"]) for item in attempts}),
        "right_censored_shards": sum(
            item["status"] == "right_censored_timeout" for item in results
        ),
        "execution_error_shards": sum(
            item["status"] == "execution_error" for item in results
        ),
        "elapsed_seconds": time.perf_counter() - started,
        "shards": results,
        "attempt_results": attempts,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "problem": args.problem_name,
                "rounds": args.rounds,
                "attempts": args.attempts,
                "shards": shard_count,
                "solved": solved,
                "unique_paths": artifact["unique_paths"],
                "elapsed_seconds": artifact["elapsed_seconds"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
