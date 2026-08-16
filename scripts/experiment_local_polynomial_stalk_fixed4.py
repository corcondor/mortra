"""Measure bounded polynomial-stalk decomposition on a frozen geometry slice."""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import tempfile
import time
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newclid.jgex.formulation import (  # noqa: E402
    JGEXFormulation,
    jgex_formulation_from_txt_file,
)

from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
    inspect_jgex_exact_system,
    inspect_jgex_local_elimination,
)
from worker.backend.polynomial_stalk_adapter import (  # noqa: E402
    coordinate_polynomial_stalk,
)


DEFAULT_NEWCLID = Path.home() / ".cache" / "mortra-research-sources" / "Newclid"
DEFAULT_PROBLEMS = ("2008_p6", "2010_p2", "2020_p1", "2021_p3")


def _setup_only(problem: JGEXFormulation) -> str:
    return str(
        JGEXFormulation(
            name=problem.name,
            setup_clauses=problem.setup_clauses,
            auxiliary_clauses=(),
            goals=problem.goals,
        )
    )


def _worker(
    kind: str,
    text: str,
    width: int,
    max_separator_variables: int,
    ordering_strategy: str,
    output_path: str,
) -> None:
    try:
        if kind == "explicit":
            result = inspect_jgex_exact_system(
                text,
                representation="explicit",
                enable_affine_local_lemmas=False,
                enable_structural_lemmas=False,
            )
        elif kind == "relational":
            result = inspect_jgex_exact_system(
                text,
                representation="relational",
                enable_affine_local_lemmas=False,
                enable_structural_lemmas=True,
            )
        elif kind == "local":
            result = inspect_jgex_local_elimination(
                text,
                enable_structural_lemmas=True,
                max_steps=None,
                max_output_terms=width,
                max_resultant_degree=2,
                max_separator_variables=(max_separator_variables or None),
                ordering_strategy=ordering_strategy,
            )
            payload = {
                "status": "completed",
                "result": asdict(result),
                "coordination": asdict(
                    coordinate_polynomial_stalk(
                        result.local_elimination,
                        external_goal_polynomial=result.goal_polynomial,
                    )
                ),
            }
            Path(output_path).write_text(json.dumps(payload), encoding="utf-8")
            return
        else:
            raise ValueError(kind)
        payload = {"status": "completed", "result": asdict(result)}
    except Exception as error:
        payload = {
            "status": "execution_error",
            "reason": f"{type(error).__name__}: {error}",
        }
    Path(output_path).write_text(json.dumps(payload), encoding="utf-8")


def _isolated(
    kind: str,
    text: str,
    *,
    width: int = 0,
    max_separator_variables: int = 0,
    ordering_strategy: str = "local_degree",
    timeout_seconds: float,
) -> dict:
    context = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="mortra-polynomial-stalk-") as directory:
        output = Path(directory) / "result.json"
        process = context.Process(
            target=_worker,
            args=(
                kind,
                text,
                width,
                max_separator_variables,
                ordering_strategy,
                str(output),
            ),
        )
        started = time.perf_counter()
        process.start()
        process.join(None if timeout_seconds <= 0 else timeout_seconds)
        elapsed = time.perf_counter() - started
        if timeout_seconds > 0 and process.is_alive():
            process.terminate()
            process.join(5)
            return {"status": "timeout", "elapsed_seconds": elapsed}
        if not output.exists():
            return {
                "status": "execution_error",
                "return_code": process.exitcode,
                "elapsed_seconds": elapsed,
            }
        result = json.loads(output.read_text(encoding="utf-8"))
        result["elapsed_seconds"] = elapsed
        return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_NEWCLID / "newclid" / "problems_datasets" / "imo.txt",
    )
    parser.add_argument("--problems", nargs="*", default=DEFAULT_PROBLEMS)
    parser.add_argument("--widths", nargs="*", type=int, default=(32, 64, 128))
    parser.add_argument("--inspection-timeout-seconds", type=float, default=30.0)
    parser.add_argument("--local-timeout-seconds", type=float, default=180.0)
    parser.add_argument("--max-separator-variables", type=int, default=0)
    parser.add_argument("--skip-inspections", action="store_true")
    parser.add_argument(
        "--ordering-strategy",
        choices=("local_degree", "min_fill"),
        default="local_degree",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "local-polynomial-stalk-fixed4-2026-08-16.json",
    )
    args = parser.parse_args()

    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    results: dict[str, dict] = {}
    for name in args.problems:
        print(f"[{name}]", flush=True)
        text = _setup_only(formulations[name])
        case = {
            "explicit_inspection": (
                {"status": "skipped"}
                if args.skip_inspections
                else _isolated(
                    "explicit",
                    text,
                    timeout_seconds=args.inspection_timeout_seconds,
                )
            ),
            "relational_inspection": (
                {"status": "skipped"}
                if args.skip_inspections
                else _isolated(
                    "relational",
                    text,
                    timeout_seconds=args.inspection_timeout_seconds,
                )
            ),
            "local_widths": {},
        }
        for width in args.widths:
            print(f"  width={width}", flush=True)
            case["local_widths"][str(width)] = _isolated(
                "local",
                text,
                width=width,
                max_separator_variables=args.max_separator_variables,
                ordering_strategy=args.ordering_strategy,
                timeout_seconds=args.local_timeout_seconds,
            )
        results[name] = case

    width_summary: dict[str, dict] = {}
    for width in args.widths:
        key = str(width)
        completed = [
            case["local_widths"][key]
            for case in results.values()
            if case["local_widths"][key]["status"] == "completed"
        ]
        width_summary[key] = {
            "completed": len(completed),
            "timeouts": sum(
                case["local_widths"][key]["status"] == "timeout"
                for case in results.values()
            ),
            "eliminated_variables": sum(
                len(item["result"]["local_elimination"]["eliminated_variables"])
                for item in completed
            ),
            "local_certificates_replayed": sum(
                item["result"]["all_local_certificates_replayed"] for item in completed
            ),
            "derived_goals": sum(
                item["coordination"]["derived_goal_count"] for item in completed
            ),
            "local_agents": sum(
                item["coordination"]["local_agent_count"] for item in completed
            ),
            "active_agents": sum(
                item["coordination"]["active_agent_count"] for item in completed
            ),
            "maximum_separator_variable_width": max(
                (
                    item["coordination"]["maximum_separator_variable_width"]
                    for item in completed
                ),
                default=0,
            ),
            "coordinator_solved_goals": sum(
                item["coordination"]["solved_goal_count"] for item in completed
            ),
            "coordinator_replayed_goals": sum(
                item["coordination"]["replayed_goal_count"] for item in completed
            ),
            "coordinator_rejected_certificates": sum(
                item["coordination"]["rejected_certificate_count"] for item in completed
            ),
            "maximum_proof_depth": max(
                (item["coordination"]["maximum_proof_depth"] for item in completed),
                default=0,
            ),
            "global_goals_matched": sum(
                item["coordination"]["external_goal_matched"] for item in completed
            ),
            "global_goals_replayed": sum(
                item["coordination"]["external_goal_replayed"] for item in completed
            ),
        }
    report = {
        "experiment": "bounded-local-polynomial-stalk-fixed4",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "fixed_problem_names": list(args.problems),
        "hypothesis": (
            "Relational construction blocks plus width-bounded local resultants "
            "can replace monolithic substitution with replayable separator lemmas."
        ),
        "budgets": {
            "inspection_timeout_seconds": args.inspection_timeout_seconds,
            "local_timeout_seconds": args.local_timeout_seconds,
            "separator_term_widths": args.widths,
            "max_separator_variables": args.max_separator_variables or None,
            "ordering_strategy": args.ordering_strategy,
        },
        "summary": {
            "explicit_inspection_completed": sum(
                case["explicit_inspection"]["status"] == "completed"
                for case in results.values()
            ),
            "relational_inspection_completed": sum(
                case["relational_inspection"]["status"] == "completed"
                for case in results.values()
            ),
            "widths": width_summary,
        },
        "results": results,
        "claim_scope": (
            "This measures exact local certificate exchange and expression width. "
            "It does not count a local projection as a solved global theorem."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
