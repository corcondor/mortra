"""Run one frozen exact-lowering vocabulary on every baseline-unsolved problem."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from newclid.jgex.formulation import JGEXFormulation, jgex_formulation_from_txt_file

from worker.backend.jgex_exact_constraint_bridge import (
    SUPPORTED_CONSTRUCTION_VOCABULARY,
    lower_jgex_to_exact_obligation,
)


def _exact_worker(text: str, output_path: str) -> None:
    try:
        obligation = lower_jgex_to_exact_obligation(text)
        payload = {"kind": "result", "certificate": asdict(obligation)}
    except ValueError as error:
        payload = {"kind": "unsupported", "reason": str(error)}
    except Exception as error:
        payload = {
            "kind": "execution_error",
            "reason": f"{type(error).__name__}: {error}",
        }
    Path(output_path).write_text(json.dumps(payload), encoding="utf-8")


def _run_isolated(text: str, timeout_seconds: float) -> dict:
    context = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="mortra-jgex-exact-") as directory:
        output_path = Path(directory) / "result.json"
        process = context.Process(target=_exact_worker, args=(text, str(output_path)))
        process.start()
        process.join(None if timeout_seconds <= 0 else timeout_seconds)
        if timeout_seconds > 0 and process.is_alive():
            process.terminate()
            process.join(5)
            return {"status": "timeout"}
        if not output_path.exists():
            return {"status": "execution_error", "return_code": process.exitcode}
        payload = json.loads(output_path.read_text(encoding="utf-8"))
    if payload["kind"] == "unsupported":
        return {"status": "unsupported", "reason": payload["reason"]}
    if payload["kind"] == "execution_error":
        return {"status": "execution_error", "reason": payload["reason"]}
    certificate = payload["certificate"]
    return {
        "status": "proved" if certificate["exact_replay"] else "unproved",
        "certificate": certificate,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Per-problem process limit; use 0 for an unbounded deep-research run.",
    )
    parser.add_argument("--problems", nargs="*")
    args = parser.parse_args()

    problems = jgex_formulation_from_txt_file(args.dataset)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline_score = baseline["scores"]["original_imo_ag_30"]
    unresolved = [
        name
        for name, result in baseline["results"].items()
        if result["status"] != "solved" and name in problems
    ]
    if args.problems:
        selected = set(args.problems)
        unresolved = [name for name in unresolved if name in selected]

    results = {}
    for name in unresolved:
        print(f"[{len(results) + 1}/{len(unresolved)}] {name}: running", flush=True)
        formulation = problems[name]
        setup_only = JGEXFormulation(
            name=formulation.name,
            setup_clauses=formulation.setup_clauses,
            auxiliary_clauses=(),
            goals=formulation.goals,
        )
        started = time.perf_counter()
        result = _run_isolated(str(setup_only), args.timeout_seconds)
        result["elapsed_seconds"] = time.perf_counter() - started
        results[name] = result
        print(
            f"[{len(results)}/{len(unresolved)}] {name}: {result['status']} "
            f"({result['elapsed_seconds']:.2f}s)",
            flush=True,
        )

    counts = {
        status: sum(result["status"] == status for result in results.values())
        for status in (
            "proved",
            "unproved",
            "unsupported",
            "timeout",
            "execution_error",
        )
    }
    gained = counts["proved"]
    portfolio_solved = int(baseline_score["solved"]) + gained
    report = {
        "experiment": "jgex_exact_frozen_unsolved_set",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "per_problem_timeout_seconds": (
            args.timeout_seconds if args.timeout_seconds > 0 else None
        ),
        "frozen_vocabulary": sorted(SUPPORTED_CONSTRUCTION_VOCABULARY),
        "summary": {
            "unresolved_total": len(unresolved),
            **counts,
            "baseline_solved": baseline_score["solved"],
            "portfolio_solved": portfolio_solved,
            "total": baseline_score["total"],
            "portfolio_score": portfolio_solved / int(baseline_score["total"]),
        },
        "results": results,
        "claim_scope": (
            "The lowering vocabulary is frozen before this run. Unsupported is "
            "reported as unsupported, not as an incorrect answer or a solved proof."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
