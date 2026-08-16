"""固定4問を線形局所消去からSingular liftstdへ接続する。"""

from __future__ import annotations

import argparse
import json
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
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

from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
    inspect_jgex_local_elimination,
)
from worker.backend.polynomial_stalk_adapter import (  # noqa: E402
    coordinate_polynomial_stalk,
)
from worker.backend.singular_lift_backend import (  # noqa: E402
    prove_ideal_membership_with_singular,
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


def _run_case(
    dataset: str,
    problem_name: str,
    timeout_seconds: float,
    monomial_order: str,
) -> tuple[str, dict]:
    started = time.perf_counter()
    formulation = jgex_formulation_from_txt_file(Path(dataset))[problem_name]
    first = inspect_jgex_local_elimination(
        _setup_only(formulation),
        max_output_terms=32,
        max_resultant_degree=1,
        max_separator_variables=12,
        ordering_strategy="min_fill",
    )
    coordination = coordinate_polynomial_stalk(
        first.local_elimination,
        external_goal_polynomial=first.goal_polynomial,
    )
    first_replayed = (
        first.all_local_certificates_replayed
        and coordination.derived_goal_count == coordination.replayed_goal_count
        and coordination.rejected_certificate_count == 0
    )
    certificate = prove_ideal_membership_with_singular(
        tuple(sp.sympify(item) for item in first.local_elimination.remaining_polynomials),
        tuple(sp.Symbol(item) for item in first.local_elimination.remaining_variables),
        sp.sympify(first.goal_polynomial),
        timeout_seconds=timeout_seconds,
        monomial_order=monomial_order,
    )
    return problem_name, {
        "status": certificate.status,
        "initial_variable_count": first.initial_variable_count,
        "initial_equation_count": first.initial_equation_count,
        "remaining_variable_count": len(first.local_elimination.remaining_variables),
        "remaining_polynomial_count": len(first.local_elimination.remaining_polynomials),
        "first_stage_replayed": first_replayed,
        "first_stage_coordination": asdict(coordination),
        "singular_certificate": asdict(certificate),
        "end_to_end_goal_replayed": bool(
            first_replayed and certificate.proved and certificate.replayed
        ),
        "elapsed_seconds": time.perf_counter() - started,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--dataset",
        type=Path,
        default=DEFAULT_NEWCLID / "newclid" / "problems_datasets" / "imo.txt",
    )
    parser.add_argument("--problems", nargs="*", default=DEFAULT_PROBLEMS)
    parser.add_argument("--timeout-seconds", type=float, default=180.0)
    parser.add_argument("--workers", type=int, default=2)
    parser.add_argument("--monomial-order", choices=("dp", "lp"), default="dp")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "singular-lift-fixed4-2026-08-16.json",
    )
    args = parser.parse_args()
    started = time.perf_counter()
    results: dict[str, dict] = {}
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                _run_case,
                str(args.dataset.resolve()),
                problem,
                args.timeout_seconds,
                args.monomial_order,
            ): problem
            for problem in args.problems
        }
        for future in as_completed(futures):
            problem, result = future.result()
            results[problem] = result
            print(
                f"[{problem}] {result['status']} "
                f"replayed={result['end_to_end_goal_replayed']}",
                flush=True,
            )

    ordered_results = {name: results[name] for name in args.problems}
    report = {
        "experiment": "singular-liftstd-after-linear-chordal-preconditioner-fixed4",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "fixed_problem_names": list(args.problems),
        "method": {
            "preconditioner": "linear-local-elimination/min-fill/separator<=12",
            "nonlinear_resultant_before_singular": False,
            "singular_algorithm": "liftstd + lift",
            "monomial_order": args.monomial_order,
            "timeout_seconds": args.timeout_seconds,
        },
        "summary": {
            "completed": sum(
                item["status"] in {"proved", "not_proved"}
                for item in ordered_results.values()
            ),
            "timeouts": sum(
                item["status"] == "timeout" for item in ordered_results.values()
            ),
            "first_stage_replayed": sum(
                item["first_stage_replayed"] for item in ordered_results.values()
            ),
            "end_to_end_goals_replayed": sum(
                item["end_to_end_goal_replayed"] for item in ordered_results.values()
            ),
            "false_acceptances": sum(
                item["singular_certificate"]["proved"]
                and not item["singular_certificate"]["replayed"]
                for item in ordered_results.values()
            ),
            "wall_seconds": time.perf_counter() - started,
        },
        "results": ordered_results,
        "claim_scope": (
            "A goal counts only when every preconditioner certificate and the final "
            "source-level polynomial identity replay independently. Timeouts abstain."
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
