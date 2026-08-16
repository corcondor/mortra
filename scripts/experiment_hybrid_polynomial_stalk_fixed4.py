"""局所Resultantの残差へ証明DAG付きChordal Buchbergerを適用する。"""

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

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newclid.jgex.formulation import (  # noqa: E402
    JGEXFormulation,
    jgex_formulation_from_txt_file,
)

from worker.backend.chordal_buchberger_elimination import (  # noqa: E402
    eliminate_with_certified_chordal_buchberger,
)
from worker.backend.chordal_polynomial_stalk import (  # noqa: E402
    coordinate_chordal_polynomial_stalk,
)
from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
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


def _worker(text: str, budgets: dict[str, int], output_path: str) -> None:
    progress_path = Path(output_path + ".progress.json")

    def progress(event: dict[str, object]) -> None:
        progress_path.write_text(json.dumps(event), encoding="utf-8")
        print(json.dumps(event, ensure_ascii=False), flush=True)

    try:
        progress({"stage": "resultant_started"})
        first = inspect_jgex_local_elimination(
            text,
            max_output_terms=budgets["resultant_max_terms"],
            max_resultant_degree=budgets["resultant_max_degree"],
            max_separator_variables=budgets["max_separator_variables"],
            ordering_strategy="min_fill",
        )
        first_coordination = coordinate_polynomial_stalk(
            first.local_elimination,
            external_goal_polynomial=first.goal_polynomial,
        )
        progress(
            {
                "stage": "resultant_completed",
                "remaining_variable_count": len(
                    first.local_elimination.remaining_variables
                ),
                "remaining_polynomial_count": len(
                    first.local_elimination.remaining_polynomials
                ),
                "derived_goal_count": first_coordination.derived_goal_count,
                "replayed_goal_count": first_coordination.replayed_goal_count,
            }
        )
        reduced_polynomials = tuple(
            sp.sympify(item) for item in first.local_elimination.remaining_polynomials
        )
        reduced_variables = tuple(
            sp.Symbol(item) for item in first.local_elimination.remaining_variables
        )
        goal = sp.sympify(first.goal_polynomial)
        second = eliminate_with_certified_chordal_buchberger(
            reduced_polynomials,
            reduced_variables,
            protected_variables=goal.free_symbols,
            goal_polynomial=goal,
            max_separator_variables=budgets["max_separator_variables"],
            max_clique_polynomials=budgets["max_clique_polynomials"],
            max_pairs_per_clique=budgets["max_pairs_per_clique"],
            max_basis_size_per_clique=budgets["max_basis_size_per_clique"],
            max_polynomial_terms=budgets["max_polynomial_terms"],
            max_witness_terms=budgets["max_certificate_terms"],
            terminal_max_pairs=budgets["terminal_max_pairs"],
            terminal_max_basis_size=budgets["terminal_max_basis_size"],
            max_incomplete_messages=budgets["max_incomplete_messages"],
            progress_callback=progress,
        )
        second_coordination = coordinate_chordal_polynomial_stalk(second)
        first_stage_replayed = (
            first.all_local_certificates_replayed
            and first_coordination.derived_goal_count
            == first_coordination.replayed_goal_count
        )
        end_to_end = (
            first_stage_replayed
            and second_coordination.goal_solved
            and second_coordination.goal_replayed
        )
        payload = {
            "status": "completed",
            "resultant": asdict(first),
            "resultant_coordination": asdict(first_coordination),
            "chordal": asdict(second),
            "chordal_coordination": asdict(second_coordination),
            "first_stage_replayed": first_stage_replayed,
            "end_to_end_goal_replayed": end_to_end,
        }
    except Exception as error:
        payload = {
            "status": "execution_error",
            "reason": f"{type(error).__name__}: {error}",
        }
    Path(output_path).write_text(json.dumps(payload), encoding="utf-8")


def _isolated(text: str, budgets: dict[str, int], timeout_seconds: float) -> dict:
    context = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="mortra-hybrid-stalk-") as directory:
        output = Path(directory) / "result.json"
        process = context.Process(target=_worker, args=(text, budgets, str(output)))
        started = time.perf_counter()
        process.start()
        process.join(None if timeout_seconds <= 0 else timeout_seconds)
        elapsed = time.perf_counter() - started
        if timeout_seconds > 0 and process.is_alive():
            progress_path = Path(str(output) + ".progress.json")
            last_progress = (
                json.loads(progress_path.read_text(encoding="utf-8"))
                if progress_path.exists()
                else None
            )
            process.terminate()
            process.join(5)
            return {
                "status": "timeout",
                "elapsed_seconds": elapsed,
                "last_progress": last_progress,
            }
        if not output.exists():
            return {
                "status": "execution_error",
                "return_code": process.exitcode,
                "elapsed_seconds": elapsed,
            }
        payload = json.loads(output.read_text(encoding="utf-8"))
        payload["elapsed_seconds"] = elapsed
        return payload


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_NEWCLID / "newclid" / "problems_datasets" / "imo.txt",
    )
    parser.add_argument("--problems", nargs="*", default=DEFAULT_PROBLEMS)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--resultant-max-terms", type=int, default=32)
    parser.add_argument("--resultant-max-degree", type=int, default=1)
    parser.add_argument("--max-separator-variables", type=int, default=12)
    parser.add_argument("--max-clique-polynomials", type=int, default=32)
    parser.add_argument("--max-pairs-per-clique", type=int, default=16)
    parser.add_argument("--max-basis-size-per-clique", type=int, default=48)
    parser.add_argument("--max-polynomial-terms", type=int, default=1_000)
    parser.add_argument("--max-certificate-terms", type=int, default=8_000)
    parser.add_argument("--terminal-max-pairs", type=int, default=128)
    parser.add_argument("--terminal-max-basis-size", type=int, default=96)
    parser.add_argument("--max-incomplete-messages", type=int, default=4)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "hybrid-polynomial-stalk-fixed4-2026-08-16.json",
    )
    args = parser.parse_args()
    budgets = {
        "resultant_max_terms": args.resultant_max_terms,
        "resultant_max_degree": args.resultant_max_degree,
        "max_separator_variables": args.max_separator_variables,
        "max_clique_polynomials": args.max_clique_polynomials,
        "max_pairs_per_clique": args.max_pairs_per_clique,
        "max_basis_size_per_clique": args.max_basis_size_per_clique,
        "max_polynomial_terms": args.max_polynomial_terms,
        "max_certificate_terms": args.max_certificate_terms,
        "terminal_max_pairs": args.terminal_max_pairs,
        "terminal_max_basis_size": args.terminal_max_basis_size,
        "max_incomplete_messages": args.max_incomplete_messages,
    }
    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    results: dict[str, dict] = {}
    for name in args.problems:
        print(f"[{name}]", flush=True)
        results[name] = _isolated(
            _setup_only(formulations[name]),
            budgets,
            args.timeout_seconds,
        )
    completed = [item for item in results.values() if item["status"] == "completed"]
    report = {
        "experiment": "hybrid-resultant-chordal-buchberger-fixed4",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "fixed_problem_names": list(args.problems),
        "hypothesis": (
            "Cheap exact local projections reduce the factor graph enough for a "
            "certificate-DAG chordal Groebner stage to close original goals."
        ),
        "budgets": {**budgets, "timeout_seconds": args.timeout_seconds},
        "summary": {
            "completed": len(completed),
            "timeouts": sum(item["status"] == "timeout" for item in results.values()),
            "execution_errors": sum(
                item["status"] == "execution_error" for item in results.values()
            ),
            "first_stage_replayed": sum(
                item["first_stage_replayed"] for item in completed
            ),
            "chordal_goal_certificates": sum(
                item["chordal_coordination"]["goal_certificate_available"]
                for item in completed
            ),
            "end_to_end_goals_replayed": sum(
                item["end_to_end_goal_replayed"] for item in completed
            ),
            "rejected_certificates": sum(
                item["resultant_coordination"]["rejected_certificate_count"]
                + item["chordal_coordination"]["rejected_certificate_count"]
                for item in completed
            ),
            "elapsed_seconds": sum(item["elapsed_seconds"] for item in completed),
        },
        "results": results,
        "claim_scope": (
            "The stages are composed only when every intermediate polynomial is "
            "replayed. Incomplete nonzero remainders remain abstentions."
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
