"""Run one frozen exact-lowering vocabulary on every baseline-unsolved problem."""

from __future__ import annotations

import argparse
from collections import deque
import hashlib
import json
import multiprocessing as mp
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newclid.jgex.formulation import JGEXFormulation, jgex_formulation_from_txt_file

from worker.backend.jgex_exact_constraint_bridge import (
    SUPPORTED_CONSTRUCTION_VOCABULARY,
    lower_jgex_to_exact_obligation,
)
from worker.backend.jgex_exact_solution_writer import (
    build_jgex_exact_solution_artifact,
)


def _compact_progress_event(
    event: dict[str, object],
    progress_file: Path,
) -> dict[str, object]:
    """Persist a full partial certificate once and keep progress JSON bounded."""

    compact = dict(event)
    checkpoint = compact.get("checkpoint_node")
    if not isinstance(checkpoint, dict):
        return compact
    serialized = json.dumps(
        checkpoint,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    )
    digest = str(checkpoint.get("certificate_sha256") or "")
    if not digest:
        digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    checkpoint_dir = progress_file.parent / f"{progress_file.stem}.checkpoints"
    checkpoint_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = checkpoint_dir / f"{digest}.json"
    if not checkpoint_path.exists():
        temporary = checkpoint_path.with_suffix(".json.tmp")
        temporary.write_text(serialized + "\n", encoding="utf-8")
        temporary.replace(checkpoint_path)
    compact["checkpoint_node"] = {
        "variable": checkpoint.get("variable"),
        "method": checkpoint.get("method"),
        "input_polynomial_count": len(checkpoint.get("input_polynomials", ())),
        "output_polynomial_count": len(checkpoint.get("output_polynomials", ())),
        "witness_count": len(checkpoint.get("ideal_membership_witnesses", ())),
        "nonzero_condition_count": len(checkpoint.get("nonzero_conditions", ())),
        "replayed": checkpoint.get("replayed"),
        "certificate_sha256": digest,
    }
    compact["checkpoint_artifact"] = (
        f"{checkpoint_dir.name}/{checkpoint_path.name}"
    )
    return compact


def _exact_worker(
    text: str,
    output_path: str,
    progress_path: str,
    representation: str,
    max_saturation_rounds: int,
    enable_affine_local_lemmas: bool,
    groebner_method: str = "f5b",
    local_max_output_terms: int = 64,
    local_max_resultant_degree: int = 1,
) -> None:
    progress_events: deque[dict[str, object]] = deque(maxlen=64)
    progress_event_count = 0
    last_progress_write = 0.0
    last_written_stage: str | None = None

    def record_progress(event: dict[str, object], *, force: bool = False) -> None:
        nonlocal last_progress_write, last_written_stage, progress_event_count
        progress_file = Path(progress_path)
        compact_event = _compact_progress_event(event, progress_file)
        progress_events.append(compact_event)
        progress_event_count += 1
        now = time.monotonic()
        stage = str(compact_event.get("stage", "unknown"))
        stage_identity = (
            f"{stage}:{compact_event.get('saturation_stage')}"
            if compact_event.get("saturation_stage") is not None
            else stage
        )
        if (
            not force
            and stage_identity == last_written_stage
            and now - last_progress_write < 0.5
        ):
            return
        temporary = progress_file.with_suffix(progress_file.suffix + ".tmp")
        temporary.write_text(
            json.dumps(
                {
                    "event_count": progress_event_count,
                    "latest": compact_event,
                    "recent": list(progress_events),
                },
                ensure_ascii=False,
                indent=2,
                default=str,
            )
            + "\n",
            encoding="utf-8",
        )
        temporary.replace(progress_file)
        last_progress_write = now
        last_written_stage = stage_identity

    try:
        obligation = lower_jgex_to_exact_obligation(
            text,
            representation=representation,
            max_saturation_rounds=max_saturation_rounds,
            enable_affine_local_lemmas=enable_affine_local_lemmas,
            groebner_method=groebner_method,
            local_max_output_terms=local_max_output_terms,
            local_max_resultant_degree=local_max_resultant_degree,
            progress_callback=record_progress,
        )
        certificate = asdict(obligation)
        solution = build_jgex_exact_solution_artifact(text, certificate)
        payload = {
            "kind": "result",
            "certificate": certificate,
            "solution": solution.to_dict(),
        }
    except ValueError as error:
        payload = {"kind": "unsupported", "reason": str(error)}
    except Exception as error:
        payload = {
            "kind": "execution_error",
            "reason": f"{type(error).__name__}: {error}",
        }
    record_progress(
        {"stage": "worker_completed", "kind": payload["kind"]},
        force=True,
    )
    Path(output_path).write_text(json.dumps(payload), encoding="utf-8")


def _run_isolated(
    text: str,
    timeout_seconds: float,
    *,
    representation: str = "explicit",
    max_saturation_rounds: int = 1,
    enable_affine_local_lemmas: bool = False,
    groebner_method: str = "f5b",
    local_max_output_terms: int = 64,
    local_max_resultant_degree: int = 1,
    progress_path: Path | None = None,
) -> dict:
    context = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="mortra-jgex-exact-") as directory:
        output_path = Path(directory) / "result.json"
        process = context.Process(
            target=_exact_worker,
            args=(
                text,
                str(output_path),
                str(progress_path) if progress_path is not None else str(Path(directory) / "progress.json"),
                representation,
                max_saturation_rounds,
                enable_affine_local_lemmas,
                groebner_method,
                local_max_output_terms,
                local_max_resultant_degree,
            ),
        )
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
        "solution": payload["solution"],
    }


def _baseline_state(
    baseline: dict,
    available_problems: set[str],
) -> tuple[int, int, list[str]]:
    """Read either a native baseline or a chained certified-union ledger."""

    sets = baseline.get("sets", {})
    summary = baseline.get("summary", {})
    if isinstance(sets.get("unresolved_frozen_problems"), list):
        unresolved = [
            str(name)
            for name in sets["unresolved_frozen_problems"]
            if str(name) in available_problems
        ]
        return (
            int(summary["primary_certified_solved"]),
            int(summary["total"]),
            unresolved,
        )

    if isinstance(sets.get("primary_union"), list):
        certified = {str(name) for name in sets["primary_union"]}
        unresolved = sorted(available_problems - certified)
        return (
            int(summary["primary_certified_solved"]),
            int(summary["total"]),
            unresolved,
        )

    score = baseline["scores"]["original_imo_ag_30"]
    unresolved = [
        str(name)
        for name, result in baseline["results"].items()
        if result["status"] != "solved" and str(name) in available_problems
    ]
    return int(score["solved"]), int(score["total"]), unresolved


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--run-dir",
        type=Path,
        help="Directory for one replayable proof/solution artifact per problem.",
    )
    parser.add_argument(
        "--timeout-seconds",
        type=float,
        default=120.0,
        help="Per-problem process limit; use 0 for an unbounded deep-research run.",
    )
    parser.add_argument("--problems", nargs="*")
    parser.add_argument(
        "--representation",
        choices=(
            "explicit",
            "relational",
            "goal_relational",
            "local_relational",
            "goal_local_relational",
        ),
        default="explicit",
    )
    parser.add_argument("--max-saturation-rounds", type=int, default=1)
    parser.add_argument("--enable-affine-local-lemmas", action="store_true")
    parser.add_argument(
        "--groebner-method",
        choices=("f5b", "buchberger"),
        default="f5b",
    )
    parser.add_argument("--local-max-output-terms", type=int, default=64)
    parser.add_argument("--local-max-resultant-degree", type=int, default=1)
    args = parser.parse_args()

    problems = jgex_formulation_from_txt_file(args.dataset)
    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline_solved, benchmark_total, unresolved = _baseline_state(
        baseline,
        set(problems),
    )
    if args.problems:
        selected = set(args.problems)
        unresolved = [name for name in unresolved if name in selected]

    results = {}
    run_dir = (
        args.run_dir.resolve()
        if args.run_dir is not None
        else (args.output.parent / f"{args.output.stem}-runs").resolve()
    )
    run_dir.mkdir(parents=True, exist_ok=True)
    for name in unresolved:
        print(f"[{len(results) + 1}/{len(unresolved)}] {name}: running", flush=True)
        formulation = problems[name]
        setup_only = JGEXFormulation(
            name=formulation.name,
            setup_clauses=formulation.setup_clauses,
            auxiliary_clauses=(),
            goals=formulation.goals,
        )
        artifact_path = run_dir / f"{name}.json"
        progress_path = run_dir / f"{name}.progress.json"
        started = time.perf_counter()
        result = _run_isolated(
            str(setup_only),
            args.timeout_seconds,
            representation=args.representation,
            max_saturation_rounds=args.max_saturation_rounds,
            enable_affine_local_lemmas=args.enable_affine_local_lemmas,
            groebner_method=args.groebner_method,
            local_max_output_terms=args.local_max_output_terms,
            local_max_resultant_degree=args.local_max_resultant_degree,
            progress_path=progress_path,
        )
        result["elapsed_seconds"] = time.perf_counter() - started
        if progress_path.is_file():
            result["progress_path"] = _display_path(progress_path)
        artifact_path.write_text(
            json.dumps(
                {
                    "status": result["status"],
                    **(
                        {
                            "certificate": result["certificate"],
                            "solution": result["solution"],
                        }
                        if "certificate" in result
                        else {key: value for key, value in result.items() if key != "elapsed_seconds"}
                    ),
                },
                ensure_ascii=False,
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        result["artifact_path"] = _display_path(artifact_path)
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
    portfolio_solved = baseline_solved + gained
    report = {
        "experiment": "jgex_exact_frozen_unsolved_set",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "representation": args.representation,
        "max_saturation_rounds": args.max_saturation_rounds,
        "affine_local_lemmas": args.enable_affine_local_lemmas,
        "groebner_method": args.groebner_method,
        "local_max_output_terms": args.local_max_output_terms,
        "local_max_resultant_degree": args.local_max_resultant_degree,
        "run_dir": _display_path(run_dir),
        "per_problem_timeout_seconds": (
            args.timeout_seconds if args.timeout_seconds > 0 else None
        ),
        "frozen_vocabulary": sorted(SUPPORTED_CONSTRUCTION_VOCABULARY),
        "summary": {
            "unresolved_total": len(unresolved),
            **counts,
            "baseline_solved": baseline_solved,
            "portfolio_solved": portfolio_solved,
            "total": benchmark_total,
            "portfolio_score": portfolio_solved / benchmark_total,
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
