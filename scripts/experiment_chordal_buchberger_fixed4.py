"""固定4問で局所Resultantと証明書付きChordal Buchbergerを比較する。"""

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

from worker.backend.chordal_polynomial_stalk import (  # noqa: E402
    coordinate_chordal_polynomial_stalk,
)
from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
    inspect_jgex_chordal_buchberger,
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

    def record_progress(event: dict[str, object]) -> None:
        progress_path.write_text(json.dumps(event), encoding="utf-8")
        print(json.dumps(event, ensure_ascii=False), flush=True)

    try:
        result = inspect_jgex_chordal_buchberger(
            text,
            max_separator_variables=budgets["max_separator_variables"],
            max_clique_polynomials=budgets["max_clique_polynomials"],
            max_pairs_per_clique=budgets["max_pairs_per_clique"],
            max_basis_size_per_clique=budgets["max_basis_size_per_clique"],
            max_polynomial_terms=budgets["max_polynomial_terms"],
            max_witness_terms=budgets["max_witness_terms"],
            terminal_max_pairs=budgets["terminal_max_pairs"],
            terminal_max_basis_size=budgets["terminal_max_basis_size"],
            progress_callback=record_progress,
        )
        payload = {
            "status": "completed",
            "result": asdict(result),
            "coordination": asdict(
                coordinate_chordal_polynomial_stalk(result.chordal_elimination)
            ),
        }
    except Exception as error:
        payload = {
            "status": "execution_error",
            "reason": f"{type(error).__name__}: {error}",
        }
    Path(output_path).write_text(json.dumps(payload), encoding="utf-8")


def _isolated(text: str, budgets: dict[str, int], timeout_seconds: float) -> dict:
    context = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="mortra-chordal-buchberger-") as directory:
        output = Path(directory) / "result.json"
        process = context.Process(
            target=_worker,
            args=(text, budgets, str(output)),
        )
        started = time.perf_counter()
        process.start()
        process.join(None if timeout_seconds <= 0 else timeout_seconds)
        elapsed = time.perf_counter() - started
        if timeout_seconds > 0 and process.is_alive():
            progress_path = Path(str(output) + ".progress.json")
            progress = (
                json.loads(progress_path.read_text(encoding="utf-8"))
                if progress_path.exists()
                else None
            )
            process.terminate()
            process.join(5)
            return {
                "status": "timeout",
                "elapsed_seconds": elapsed,
                "last_progress": progress,
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
    parser.add_argument("--timeout-seconds", type=float, default=240.0)
    parser.add_argument("--max-separator-variables", type=int, default=12)
    parser.add_argument("--max-clique-polynomials", type=int, default=32)
    parser.add_argument("--max-pairs-per-clique", type=int, default=256)
    parser.add_argument("--max-basis-size-per-clique", type=int, default=64)
    parser.add_argument("--max-polynomial-terms", type=int, default=2_000)
    parser.add_argument("--max-witness-terms", type=int, default=20_000)
    parser.add_argument("--terminal-max-pairs", type=int, default=1_000)
    parser.add_argument("--terminal-max-basis-size", type=int, default=128)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "chordal-buchberger-fixed4-2026-08-16.json",
    )
    args = parser.parse_args()
    budgets = {
        "max_separator_variables": args.max_separator_variables,
        "max_clique_polynomials": args.max_clique_polynomials,
        "max_pairs_per_clique": args.max_pairs_per_clique,
        "max_basis_size_per_clique": args.max_basis_size_per_clique,
        "max_polynomial_terms": args.max_polynomial_terms,
        "max_witness_terms": args.max_witness_terms,
        "terminal_max_pairs": args.terminal_max_pairs,
        "terminal_max_basis_size": args.terminal_max_basis_size,
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
        "experiment": "certified-chordal-buchberger-fixed4",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "fixed_problem_names": list(args.problems),
        "hypothesis": (
            "Keeping clique-local generators, appending a lex Groebner basis, and "
            "transporting coefficient witnesses can prove original geometry goals "
            "that pairwise resultants alone do not reach."
        ),
        "budgets": {**budgets, "timeout_seconds": args.timeout_seconds},
        "summary": {
            "completed": len(completed),
            "timeouts": sum(item["status"] == "timeout" for item in results.values()),
            "execution_errors": sum(
                item["status"] == "execution_error" for item in results.values()
            ),
            "eliminated_variables": sum(
                len(item["result"]["chordal_elimination"]["eliminated_variables"])
                for item in completed
            ),
            "local_complete_steps": sum(
                item["result"]["chordal_elimination"]["local_complete_step_count"]
                for item in completed
            ),
            "local_incomplete_steps": sum(
                item["result"]["chordal_elimination"]["local_incomplete_step_count"]
                for item in completed
            ),
            "transported_polynomials": sum(
                item["coordination"]["transported_polynomial_count"]
                for item in completed
            ),
            "goal_certificates": sum(
                item["coordination"]["goal_certificate_available"]
                for item in completed
            ),
            "global_goals_solved": sum(
                item["coordination"]["goal_solved"] for item in completed
            ),
            "global_goals_replayed": sum(
                item["coordination"]["goal_replayed"] for item in completed
            ),
            "rejected_certificates": sum(
                item["coordination"]["rejected_certificate_count"]
                for item in completed
            ),
            "elapsed_seconds": sum(item["elapsed_seconds"] for item in completed),
        },
        "results": results,
        "claim_scope": (
            "A zero remainder with a replayed coefficient witness proves ideal "
            "membership. A nonzero remainder from an incomplete bounded basis is "
            "only an abstention, never a disproof."
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
