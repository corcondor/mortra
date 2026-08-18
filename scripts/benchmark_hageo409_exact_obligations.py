"""Batch the generic exact-obligation agent over a fixed HAGeo slice."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def run_one(
    *,
    python: Path,
    dataset: Path,
    problem: str,
    run_dir: Path,
    timeout_seconds: float,
    representation: str,
) -> dict[str, object]:
    output = (run_dir / f"{problem}.json").resolve()
    command = [
        str(python),
        "-B",
        str(ROOT / "scripts" / "experiment_hageo_exact_obligation.py"),
        "--dataset",
        str(dataset),
        "--problem-name",
        problem,
        "--output",
        str(output),
        "--timeout-seconds",
        str(timeout_seconds),
        "--representation",
        representation,
    ]
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            timeout=None if timeout_seconds <= 0 else timeout_seconds + 30.0,
        )
    except subprocess.TimeoutExpired:
        return {"problem": problem, "status": "right_censored_timeout", "solved": False}
    if completed.returncode != 0 or not output.is_file():
        return {
            "problem": problem,
            "status": "execution_error",
            "solved": False,
            "returncode": completed.returncode,
            "stderr_tail": completed.stderr[-2000:],
        }
    report = json.loads(output.read_text(encoding="utf-8"))
    return {
        "problem": problem,
        "status": report["status"],
        "solved": bool(report["solved"] and report["native_confirmed"]),
        "native_confirmed": bool(report["native_confirmed"]),
        "artifact": output.relative_to(ROOT).as_posix(),
        "artifact_sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
        "reason": (report.get("result") or {}).get("reason"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problems", nargs="+", required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument(
        "--representation",
        choices=(
            "explicit",
            "relational",
            "local_relational",
            "goal_local_relational",
        ),
        default="explicit",
    )
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    args.run_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, object]] = []
    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                run_one,
                python=args.python.resolve(),
                dataset=dataset,
                problem=problem,
                run_dir=args.run_dir,
                timeout_seconds=args.timeout_seconds,
                representation=args.representation,
            ): problem
            for problem in sorted(set(args.problems))
        }
        for future in as_completed(futures):
            result = future.result()
            results.append(result)
            print(json.dumps(result, ensure_ascii=False), flush=True)

    results.sort(key=lambda item: str(item["problem"]))
    statuses = sorted({str(item["status"]) for item in results})
    summary = {
        "total": len(results),
        "proved": sum(bool(item["solved"]) for item in results),
        "right_censored": sum(item["status"] == "right_censored_timeout" for item in results),
        "by_status": {
            status: sum(item["status"] == status for item in results)
            for status in statuses
        },
    }
    report = {
        "experiment": "hageo409_generic_exact_obligation_batch",
        "created_at": datetime.now(UTC).isoformat(),
        "protocol": {
            "uses_external_llm": False,
            "uses_problem_specific_solver_logic": False,
            "dataset_auxiliary_clauses_hidden": True,
            "truth_plane": "exact polynomial certificate replay only",
            "timeout_semantics": "right-censored unknown",
            "timeout_seconds_per_problem": args.timeout_seconds,
            "representation": args.representation,
            "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        },
        "summary": summary,
        "results": results,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
