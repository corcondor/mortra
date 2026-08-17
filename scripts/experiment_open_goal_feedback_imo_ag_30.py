"""Run the open-goal -> construction -> native-proof loop on IMO-AG-30.

Every unresolved problem receives the same staged search schedule.  The child
search never reads dataset auxiliary clauses, problem IDs, or known answers.
Only a replayed Yuclid proof can add a problem to the portfolio score.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_NEWCLID = Path.home() / ".cache" / "mortra-research-sources" / "Newclid"
DEFAULT_RUNTIME = (
    Path.home()
    / ".cache"
    / "mortra-research-sources"
    / "boost_1_88_dlls"
    / "app"
    / "lib64-msvc-14.3"
)


@dataclass(frozen=True)
class SearchStage:
    name: str
    arguments: tuple[str, ...]


DEFAULT_STAGES = (
    SearchStage(
        "extended_frontier_depth1",
        (
            "--family-set",
            "extended",
            "--per-family-limit",
            "4",
            "--branch-limit",
            "42",
            "--beam-width",
            "8",
            "--max-depth",
            "1",
            "--beam-ranking",
            "frontier-pareto",
            "--goal-directed-families",
        ),
    ),
    SearchStage(
        "core_frontier_depth2",
        (
            "--families",
            "midpoint,mirror",
            "--per-family-limit",
            "20",
            "--branch-limit",
            "32",
            "--beam-width",
            "16",
            "--max-depth",
            "2",
            "--beam-ranking",
            "frontier-pareto",
            "--goal-directed-families",
        ),
    ),
)


def _native_proof_valid(artifact_path: Path, artifact: dict[str, Any]) -> bool:
    confirmation = artifact.get("confirmation") or {}
    proof_path = artifact_path.with_suffix(".proof.json")
    if not (
        artifact.get("solved") is True
        and confirmation.get("solved") is True
        and confirmation.get("status") == "solved"
        and int(confirmation.get("goal_deduction_count", 0)) > 0
        and proof_path.is_file()
    ):
        return False
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    return bool(
        proof.get("status") == "solved"
        and len(proof.get("deductions_for_goal", ()))
        == int(confirmation["goal_deduction_count"])
    )


def portfolio_summary(
    *,
    baseline_names: Iterable[str],
    strict_exchange_names: Iterable[str],
    construction_names: Iterable[str],
    total: int,
) -> dict[str, Any]:
    baseline = set(baseline_names)
    strict = set(strict_exchange_names)
    constructions = set(construction_names)
    portfolio = baseline | strict | constructions
    return {
        "baseline_solved": len(baseline),
        "strict_exchange_solved": len(strict),
        "construction_feedback_solved": len(constructions),
        "new_strict_exchange_names": sorted(strict - baseline),
        "new_construction_feedback_names": sorted(constructions - baseline - strict),
        "portfolio_solved": len(portfolio),
        "total": total,
        "portfolio_score": len(portfolio) / total if total else 0.0,
        "portfolio_names": sorted(portfolio),
    }


def original_benchmark_names(baseline: dict[str, Any]) -> set[str]:
    """Use the frozen original benchmark, excluding README reformulations."""

    score = baseline.get("scores", {}).get("original_imo_ag_30", {})
    names = score.get("solved_names")
    if not isinstance(names, list):
        raise ValueError("baseline has no original_imo_ag_30 solved_names")
    return {str(name) for name in names}


def _stage_argument(stage: SearchStage, name: str) -> str | None:
    try:
        return stage.arguments[stage.arguments.index(name) + 1]
    except (ValueError, IndexError):
        return None


def stage_artifact_matches(
    artifact: dict[str, Any],
    *,
    stage: SearchStage,
    candidate_ranking: str,
    beam_ranking_override: str | None,
) -> bool:
    protocol = artifact.get("protocol", {})
    expected_beam = beam_ranking_override or _stage_argument(stage, "--beam-ranking")
    expected_numbers = {
        "per_family_limit": _stage_argument(stage, "--per-family-limit"),
        "branch_limit": _stage_argument(stage, "--branch-limit"),
        "beam_width": _stage_argument(stage, "--beam-width"),
        "max_depth": _stage_argument(stage, "--max-depth"),
    }
    return bool(
        artifact.get("experiment") == "newclid_dynamic_typed_construction_stalk_no_llm"
        and protocol.get("ranking") == candidate_ranking
        and protocol.get("beam_ranking") == expected_beam
        and all(
            expected is not None and int(protocol.get(key, -1)) == int(expected)
            for key, expected in expected_numbers.items()
        )
    )


def _run_stage(
    *,
    stage: SearchStage,
    problem_name: str,
    dataset: Path,
    yuclid_exe: Path,
    runtime_path: Path,
    output: Path,
    max_workers: int,
    timeout_seconds: float,
    gclc_executable: Path | None,
    gclc_timeout_seconds: int,
    exact_timeout_seconds: float,
    candidate_ranking: str,
    beam_ranking_override: str | None,
) -> dict[str, Any]:
    if output.is_file():
        artifact = json.loads(output.read_text(encoding="utf-8"))
        if stage_artifact_matches(
            artifact,
            stage=stage,
            candidate_ranking=candidate_ranking,
            beam_ranking_override=beam_ranking_override,
        ):
            native_proof_valid = _native_proof_valid(output, artifact)
            return {
                "stage": stage.name,
                "status": "proved" if native_proof_valid else "unproved",
                "artifact": output.resolve().relative_to(ROOT).as_posix(),
                "evaluated_paths": int(artifact.get("evaluated_paths", 0)),
                "error_count": int(artifact.get("error_count", 0)),
                "solved_path": artifact.get("solved_path"),
                "native_proof_valid": native_proof_valid,
                "elapsed_seconds": 0.0,
                "reused_completed_artifact": True,
            }
    command = [
        sys.executable,
        str(ROOT / "scripts" / "experiment_newclid_construction_stalk.py"),
        "--dataset",
        str(dataset),
        "--problem-name",
        problem_name,
        "--yuclid-exe",
        str(yuclid_exe),
        "--runtime-path",
        str(runtime_path),
        "--output",
        str(output),
        "--max-workers",
        str(max_workers),
        "--ar-profile",
        "all",
        *stage.arguments,
        "--ranking",
        candidate_ranking,
    ]
    if beam_ranking_override is not None:
        command.extend(("--beam-ranking", beam_ranking_override))
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout_seconds,
        )
    except subprocess.TimeoutExpired as error:
        return {
            "stage": stage.name,
            "status": "timeout",
            "elapsed_seconds": time.perf_counter() - started,
            "stdout_tail": (error.stdout or "")[-2000:],
            "stderr_tail": (error.stderr or "")[-2000:],
        }
    if completed.returncode != 0 or not output.is_file():
        return {
            "stage": stage.name,
            "status": "error",
            "return_code": completed.returncode,
            "elapsed_seconds": time.perf_counter() - started,
            "stdout_tail": completed.stdout[-2000:],
            "stderr_tail": completed.stderr[-2000:],
        }
    artifact = json.loads(output.read_text(encoding="utf-8"))
    native_proof_valid = _native_proof_valid(output, artifact)
    result = {
        "stage": stage.name,
        "status": "proved" if native_proof_valid else "unproved",
        "artifact": output.resolve().relative_to(ROOT).as_posix(),
        "evaluated_paths": int(artifact.get("evaluated_paths", 0)),
        "error_count": int(artifact.get("error_count", 0)),
        "solved_path": artifact.get("solved_path"),
        "native_proof_valid": native_proof_valid,
        "elapsed_seconds": time.perf_counter() - started,
    }
    if result["native_proof_valid"] and gclc_executable is not None:
        exchange_output = output.with_name(output.stem + "-independent-exchange.json")
        try:
            exchange = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "verify_open_goal_independent_exchange.py"),
                    "--artifact",
                    str(output),
                    "--gclc-executable",
                    str(gclc_executable),
                    "--gclc-timeout-seconds",
                    str(gclc_timeout_seconds),
                    "--exact-timeout-seconds",
                    str(exact_timeout_seconds),
                    "--output",
                    str(exchange_output),
                ],
                cwd=ROOT,
                check=False,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=max(
                    60.0, exact_timeout_seconds + 2 * gclc_timeout_seconds + 60.0
                ),
            )
        except subprocess.TimeoutExpired as error:
            result["independent_exchange"] = {
                "status": "timeout",
                "stdout_tail": (error.stdout or "")[-2000:],
                "stderr_tail": (error.stderr or "")[-2000:],
            }
            return result
        if exchange.returncode == 0 and exchange_output.is_file():
            exchange_payload = json.loads(exchange_output.read_text(encoding="utf-8"))
            result["independent_exchange"] = {
                "status": (
                    "strict_exchange_proved"
                    if exchange_payload.get("strict_exchange_proved")
                    else "not_strictly_proved"
                ),
                "artifact": exchange_output.resolve().relative_to(ROOT).as_posix(),
                "gclc_proved": exchange_payload.get("gclc", {}).get("proved", False),
                "exact_status": exchange_payload.get("exact", {}).get("status"),
                "typed_goal_agreement": exchange_payload.get("typed_goal_agreement", False),
            }
        else:
            result["independent_exchange"] = {
                "status": "error",
                "stdout_tail": exchange.stdout[-2000:],
                "stderr_tail": exchange.stderr[-2000:],
            }
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_NEWCLID / "newclid" / "problems_datasets" / "imo.txt",
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=ROOT / "data" / "yuclid-imo-ag-30-lazy-circuit-control-2026-08-17.json",
    )
    parser.add_argument(
        "--strict-exchange",
        type=Path,
        default=ROOT
        / "data"
        / "real-symbolic-coordination-imo-ag-30-relation-expanded-2026-08-16.json",
    )
    parser.add_argument(
        "--yuclid-exe",
        type=Path,
        default=DEFAULT_NEWCLID / ".venv" / "Scripts" / "yuclid.exe",
    )
    parser.add_argument("--runtime-path", type=Path, default=DEFAULT_RUNTIME)
    parser.add_argument("--max-workers", type=int, default=8)
    parser.add_argument("--stage-timeout-seconds", type=float, default=900.0)
    parser.add_argument(
        "--gclc-executable",
        type=Path,
        default=Path.home()
        / ".cache"
        / "mortra-research-sources"
        / "gclc"
        / "build"
        / "Release"
        / "gclc.exe",
    )
    parser.add_argument("--gclc-timeout-seconds", type=int, default=60)
    parser.add_argument("--exact-timeout-seconds", type=float, default=120.0)
    parser.add_argument("--skip-independent-exchange", action="store_true")
    parser.add_argument(
        "--candidate-ranking", choices=("structural", "random"), default="structural"
    )
    parser.add_argument(
        "--beam-ranking-override",
        choices=("closure", "relation", "relation-transition", "frontier", "frontier-pareto"),
    )
    parser.add_argument("--problems", nargs="*")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "open-goal-feedback-imo-ag-30-2026-08-17.json",
    )
    args = parser.parse_args()

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline_results = baseline["results"]
    baseline_names = original_benchmark_names(baseline)
    unresolved = [
        name for name, result in baseline_results.items() if result.get("status") != "solved"
    ]
    if args.problems:
        requested = set(args.problems)
        unresolved = [name for name in unresolved if name in requested]

    strict_names: set[str] = set()
    if args.strict_exchange.is_file():
        strict = json.loads(args.strict_exchange.read_text(encoding="utf-8"))
        strict_names.update(strict.get("summary", {}).get("strict_exchange_proved_names", ()))

    run_dir = args.output.with_suffix("")
    run_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Any] = {}
    construction_names: set[str] = set()
    started = time.perf_counter()
    for index, name in enumerate(unresolved, start=1):
        print(f"[{index}/{len(unresolved)}] open goal {name}", flush=True)
        stages: list[dict[str, Any]] = []
        for stage in DEFAULT_STAGES:
            stage_output = run_dir / f"{name}-{stage.name}.json"
            result = _run_stage(
                stage=stage,
                problem_name=name,
                dataset=args.dataset.resolve(),
                yuclid_exe=args.yuclid_exe.resolve(),
                runtime_path=args.runtime_path.resolve(),
                output=stage_output,
                max_workers=args.max_workers,
                timeout_seconds=args.stage_timeout_seconds,
                gclc_executable=(
                    None
                    if args.skip_independent_exchange
                    else args.gclc_executable.resolve()
                ),
                gclc_timeout_seconds=args.gclc_timeout_seconds,
                exact_timeout_seconds=args.exact_timeout_seconds,
                candidate_ranking=args.candidate_ranking,
                beam_ranking_override=args.beam_ranking_override,
            )
            stages.append(result)
            print(
                f"  {stage.name}: {result['status']} "
                f"paths={result.get('evaluated_paths', 0)}",
                flush=True,
            )
            if result["status"] == "proved":
                construction_names.add(name)
                break
        results[name] = {
            "status": "proved" if name in construction_names else "unproved",
            "stages": stages,
        }

    summary = portfolio_summary(
        baseline_names=baseline_names,
        strict_exchange_names=strict_names,
        construction_names=construction_names,
        total=30,
    )
    report = {
        "experiment": "imo-ag-30-open-goal-construction-feedback-no-llm",
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "uses_problem_id_in_search": False,
            "uses_known_answers_or_known_auxiliaries": False,
            "same_stage_schedule_for_every_open_goal": True,
            "search_order": "breadth-first extended depth 1, then core depth 2",
            "completed_stage_artifacts_are_resumable": True,
            "candidate_ranking": args.candidate_ranking,
            "beam_ranking_override": args.beam_ranking_override,
            "acceptance": "replayed native Yuclid proof only",
            "stages": [
                {"name": stage.name, "arguments": list(stage.arguments)}
                for stage in DEFAULT_STAGES
            ],
        },
        "selected_open_goals": unresolved,
        "summary": summary,
        "results": results,
        "wall_seconds": time.perf_counter() - started,
        "claim_scope": (
            "The score is a symbolic portfolio result. Candidate constructions are "
            "generated from a finite typed grammar and native deduction frontier; "
            "no learned auxiliary-point generator is claimed."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
