"""固定4問で証明書付きWu三角鎖とprimitive-part正規化を測る。"""

from __future__ import annotations

import argparse
import json
import multiprocessing as mp
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
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

from worker.backend.certified_wu_characteristic import (  # noqa: E402
    certified_sparse_wu_characteristic_proof,
    structural_min_fill_elimination_order,
    structural_variable_matching,
)
from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
    inspect_jgex_exact_system,
)
from worker.backend.wu_polynomial_stalk import (  # noqa: E402
    coordinate_wu_polynomial_stalk,
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


def _worker(text: str, settings: dict[str, object], output_path: str) -> None:
    output = Path(output_path)
    progress_path = Path(output_path + ".progress.json")

    def record_progress(event: dict[str, object]) -> None:
        progress_path.write_text(
            json.dumps(event, ensure_ascii=False),
            encoding="utf-8",
        )

    try:
        record_progress({"stage": "exact_elaboration_started"})
        analysis = inspect_jgex_exact_system(
            text,
            representation=str(settings["representation"]),
        )
        record_progress(
            {
                "stage": "exact_elaboration_completed",
                "variable_count": analysis.variable_count,
                "equation_count": analysis.equation_count,
                "maximum_expanded_terms": analysis.maximum_expanded_terms,
            }
        )
        # The exact bridge reports reverse construction order.  Wu's chain
        # eliminates in reverse, so restore construction order at this boundary.
        variable_names = tuple(reversed(analysis.variables))
        symbols = {name: sp.Symbol(name) for name in variable_names}
        record_progress({"stage": "sparse_input_parse_started"})
        equations = tuple(
            sp.sympify(item, locals=symbols)
            for item in analysis.construction_equations
        )
        goal = sp.sympify(analysis.goal_polynomial, locals=symbols)
        record_progress({"stage": "sparse_input_parse_completed"})
        elimination_order = None
        if settings["variable_order"] == "min_fill":
            record_progress({"stage": "variable_order_started", "method": "min_fill"})
            matching = structural_variable_matching(
                equations,
                tuple(symbols[name] for name in variable_names),
            )
            dependent = tuple(symbols[name] for name in matching.dependent_variables)
            elimination_order = structural_min_fill_elimination_order(
                equations,
                dependent,
                protected_variables=goal.free_symbols,
            )
            record_progress(
                {
                    "stage": "variable_order_completed",
                    "method": "min_fill",
                    "first_variable": str(elimination_order[0]),
                }
            )
        record_progress({"stage": "wu_triangulation_started"})
        result = certified_sparse_wu_characteristic_proof(
            equations,
            tuple(symbols[name] for name in variable_names),
            goal,
            max_reductions=int(settings["max_reductions"]),
            max_terms=int(settings["max_terms"]),
            timeout_seconds=float(settings["internal_timeout_seconds"]),
            normalize_remainders=bool(settings["normalize_remainders"]),
            max_content_terms=int(settings["max_content_terms"]),
            elimination_order=elimination_order,
            progress_callback=record_progress,
        )
        record_progress(
            {
                "stage": "wu_triangulation_completed",
                "triangularization_complete": result.triangularization_complete,
                "stopped_reason": result.stopped_reason,
            }
        )
        payload = {
            "status": "completed",
            "input": {
                "variable_count": analysis.variable_count,
                "equation_count": analysis.equation_count,
                "goal_channel": analysis.channel,
                "construction_vocabulary": analysis.construction_vocabulary,
                "normalization_assumptions": analysis.normalization_assumptions,
                "nondegeneracy_conditions": analysis.nondegeneracy_conditions,
                "executable_regularity_conditions": (
                    analysis.executable_regularity_conditions
                ),
            },
            "result": asdict(result),
            "coordination": asdict(
                coordinate_wu_polynomial_stalk(
                    result,
                    known_nonzero_conditions=(
                        analysis.executable_regularity_conditions
                    ),
                )
            ),
        }
    except Exception as error:
        payload = {
            "status": "execution_error",
            "reason": f"{type(error).__name__}: {error}",
        }
    output.write_text(
        json.dumps(payload, ensure_ascii=False),
        encoding="utf-8",
    )


def _isolated(
    text: str,
    settings: dict[str, object],
    timeout_seconds: float,
) -> dict[str, object]:
    context = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="mortra-certified-wu-") as directory:
        output = Path(directory) / "result.json"
        process = context.Process(
            target=_worker,
            args=(text, settings, str(output)),
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


def _summary(results: dict[str, dict[str, object]]) -> dict[str, object]:
    completed = [item for item in results.values() if item["status"] == "completed"]
    payloads = [item["result"] for item in completed]
    return {
        "completed": len(completed),
        "timeouts": sum(item["status"] == "timeout" for item in results.values()),
        "execution_errors": sum(
            item["status"] == "execution_error" for item in results.values()
        ),
        "structural_matching_complete": sum(
            item["matching"]["complete"] for item in payloads
        ),
        "triangularization_complete": sum(
            item["triangularization_complete"] for item in payloads
        ),
        "conditional_goals_proved": sum(
            item["conditional_goal_proved"] for item in payloads
        ),
        "unconditional_goals_proved": sum(
            item["unconditional_goal_proved"] for item in payloads
        ),
        "input_conditioned_goals_solved": sum(
            item["coordination"]["input_conditioned_goal_solved"]
            for item in completed
        ),
        "discharged_regularity_obligations": sum(
            item["coordination"]["discharged_regularity_count"]
            for item in completed
        ),
        "open_regularity_obligations": sum(
            item["coordination"]["open_regularity_count"]
            for item in completed
        ),
        "all_identities_replayed": sum(
            item["all_identities_replayed"] for item in payloads
        ),
        "pseudo_division_steps": sum(
            len(item["triangulation_steps"]) + len(item["goal_steps"])
            for item in payloads
        ),
        "normalization_obligations": sum(
            sum(
                step["normalization_nonzero_obligation"] is not None
                for step in item["triangulation_steps"]
            )
            for item in payloads
        ),
        "accepted_local_certificates": sum(
            item["coordination"]["accepted_certificate_count"]
            for item in completed
        ),
        "oversized_local_certificates": sum(
            item["coordination"]["oversized_certificate_count"]
            for item in completed
        ),
        "expanded_micro_certificates": sum(
            item["coordination"]["expanded_micro_certificate_count"]
            for item in completed
        ),
        "skipped_micro_certificates": sum(
            item["coordination"]["skipped_micro_certificate_count"]
            for item in completed
        ),
        "content_addressed_fallback_certificates": sum(
            item["coordination"][
                "content_addressed_fallback_certificate_count"
            ]
            for item in completed
        ),
        "elapsed_seconds": sum(float(item["elapsed_seconds"]) for item in results.values()),
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
    parser.add_argument("--max-workers", type=int, default=2)
    parser.add_argument("--max-reductions", type=int, default=10_000)
    parser.add_argument("--max-terms", type=int, default=20_000)
    parser.add_argument("--max-content-terms", type=int, default=5_000)
    parser.add_argument("--no-normalize", action="store_true")
    parser.add_argument(
        "--variable-order",
        choices=("construction", "min_fill"),
        default="construction",
    )
    parser.add_argument(
        "--representation",
        choices=("explicit", "relational"),
        default="explicit",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "certified-wu-fixed4-2026-08-16.json",
    )
    args = parser.parse_args()
    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    settings: dict[str, object] = {
        "max_reductions": args.max_reductions,
        "max_terms": args.max_terms,
        "max_content_terms": args.max_content_terms,
        "normalize_remainders": not args.no_normalize,
        "variable_order": args.variable_order,
        "representation": args.representation,
        "internal_timeout_seconds": max(1.0, args.timeout_seconds - 5.0),
    }
    texts = {
        name: _setup_only(formulations[name])
        for name in args.problems
    }
    results: dict[str, dict[str, object]] = {}
    with ThreadPoolExecutor(max_workers=max(1, args.max_workers)) as executor:
        futures = {
            executor.submit(
                _isolated,
                text,
                settings,
                args.timeout_seconds,
            ): name
            for name, text in texts.items()
        }
        for future in as_completed(futures):
            name = futures[future]
            results[name] = future.result()
            print(name, json.dumps(results[name], ensure_ascii=False)[:500], flush=True)

    ordered_results = {name: results[name] for name in args.problems}
    report = {
        "experiment": "certified-wu-characteristic-fixed4",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "fixed_problem_names": list(args.problems),
        "hypothesis": (
            "A construction-ordered characteristic set with replayable pseudo-division "
            "identities and explicit regularity obligations reduces expression swell "
            "without accepting degenerate branches as proofs."
        ),
        "settings": {**settings, "external_timeout_seconds": args.timeout_seconds},
        "summary": _summary(ordered_results),
        "results": ordered_results,
        "claim_scope": (
            "Only a zero final remainder with every polynomial identity replayed is a "
            "conditional proof. Every nonconstant multiplier remains an explicit "
            "nonzero obligation; timeout and nonzero remainder are abstentions."
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
    mp.freeze_support()
    raise SystemExit(main())
