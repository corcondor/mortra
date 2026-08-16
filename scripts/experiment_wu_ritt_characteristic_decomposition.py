"""固定幾何義務で論文準拠Wu--Ritt特性集合・零点分解を測定する。"""

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
from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
    inspect_jgex_exact_system,
)
from worker.backend.wu_ritt_zero_decomposition import (  # noqa: E402
    decompose_wu_ritt_zero_set,
    verify_wu_ritt_zero_decomposition,
)


DEFAULT_NEWCLID = Path.home() / ".cache" / "mortra-research-sources" / "Newclid"
DEFAULT_BASELINE = (
    ROOT / "data" / "certified-wu-relational-construction-fixed4-micro-2026-08-16.json"
)


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
    try:
        analysis = inspect_jgex_exact_system(text, representation="relational")
        variable_names = tuple(reversed(analysis.variables))
        symbols = {name: sp.Symbol(name) for name in variable_names}
        equations = tuple(
            sp.sympify(item, locals=symbols)
            for item in analysis.construction_equations
        )
        goal = sp.sympify(analysis.goal_polynomial, locals=symbols)
        decomposition = decompose_wu_ritt_zero_set(
            equations,
            tuple(symbols[name] for name in variable_names),
            goal,
            known_nonzero_conditions=analysis.executable_regularity_conditions,
            max_depth=int(settings["max_depth"]),
            max_solver_branches=int(settings["max_solver_branches"]),
            max_rounds=int(settings["max_rounds"]),
            max_reductions=int(settings["max_reductions"]),
            max_terms=int(settings["max_terms"]),
            timeout_seconds_per_branch=float(settings["branch_timeout_seconds"]),
            basic_set_mode=str(settings["basic_set_mode"]),
            initial_branch_mode=str(settings["initial_branch_mode"]),
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
            "decomposition": asdict(decomposition),
            "cover_verified": verify_wu_ritt_zero_decomposition(decomposition),
        }
    except Exception as error:
        payload = {
            "status": "execution_error",
            "reason": f"{type(error).__name__}: {error}",
        }
    output.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")


def _isolated(
    text: str,
    settings: dict[str, object],
    external_timeout_seconds: float,
) -> dict[str, object]:
    context = mp.get_context("spawn")
    with tempfile.TemporaryDirectory(prefix="mortra-wu-ritt-") as directory:
        output = Path(directory) / "result.json"
        process = context.Process(target=_worker, args=(text, settings, str(output)))
        started = time.perf_counter()
        process.start()
        process.join(external_timeout_seconds)
        elapsed = time.perf_counter() - started
        if process.is_alive():
            process.terminate()
            process.join(5)
            return {"status": "timeout", "elapsed_seconds": elapsed}
        if not output.exists():
            return {
                "status": "execution_error",
                "return_code": process.exitcode,
                "elapsed_seconds": elapsed,
            }
        payload = json.loads(output.read_text(encoding="utf-8"))
        payload["elapsed_seconds"] = elapsed
        return payload


def _eligible_names(
    baseline: dict[str, object],
    requested: tuple[str, ...],
) -> tuple[str, ...]:
    results = baseline["results"]
    return tuple(
        name
        for name in requested
        if results[name]["status"] == "completed"
        and results[name]["coordination"]["conditional_goal_solved"]
        and results[name]["coordination"]["open_regularity_count"] > 0
    )


def _summary(results: dict[str, dict[str, object]]) -> dict[str, object]:
    completed = [item for item in results.values() if item["status"] == "completed"]
    decompositions = [item["decomposition"] for item in completed]
    branches = [
        branch
        for decomposition in decompositions
        for branch in decomposition["branches"]
    ]
    return {
        "completed": len(completed),
        "timeouts": sum(item["status"] == "timeout" for item in results.values()),
        "execution_errors": sum(
            item["status"] == "execution_error" for item in results.values()
        ),
        "cover_certificates_verified": sum(
            item["cover_verified"] for item in completed
        ),
        "coverage_complete": sum(
            item["decomposition"]["coverage_complete"] for item in completed
        ),
        "solver_branches": sum(
            item["solver_branch_count"] for item in decompositions
        ),
        "regular_leaves": sum(item["regular_leaf_count"] for item in decompositions),
        "proved_leaves": sum(item["proved_leaf_count"] for item in decompositions),
        "empty_leaves": sum(item["empty_leaf_count"] for item in decompositions),
        "unresolved_leaves": sum(
            item["unresolved_leaf_count"] for item in decompositions
        ),
        "distinct_initial_factors": sum(
            item["distinct_initial_factor_count"] for item in decompositions
        ),
        "rank_decrease_violations": sum(
            item["rank_decrease_violations"] for item in decompositions
        ),
        "characteristic_incomplete_branches": sum(
            branch["status"] == "characteristic_incomplete" for branch in branches
        ),
        "depth_budget_leaves": sum(
            branch["status"] == "depth_budget" for branch in branches
        ),
        "all_characteristic_sets_verified": all(
            item["all_characteristic_sets_verified"] for item in decompositions
        ),
        "all_computed_identities_replayed": all(
            item["all_computed_identities_replayed"] for item in decompositions
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
    parser.add_argument("--baseline-artifact", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--problems", nargs="*", default=None)
    parser.add_argument("--max-depth", type=int, default=1)
    parser.add_argument("--max-solver-branches", type=int, default=16)
    parser.add_argument("--max-rounds", type=int, default=16)
    parser.add_argument("--branch-timeout-seconds", type=float, default=70.0)
    parser.add_argument("--external-timeout-seconds", type=float, default=480.0)
    parser.add_argument("--max-reductions", type=int, default=20_000)
    parser.add_argument("--max-terms", type=int, default=20_000)
    parser.add_argument(
        "--basic-set-mode",
        choices=("standard", "weak"),
        default="standard",
    )
    parser.add_argument(
        "--initial-branch-mode",
        choices=("initial", "irreducible"),
        default="initial",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "wu-ritt-characteristic-fixed4-2026-08-17.json",
    )
    args = parser.parse_args()
    baseline = json.loads(args.baseline_artifact.read_text(encoding="utf-8"))
    requested = tuple(args.problems or baseline["fixed_problem_names"])
    eligible = _eligible_names(baseline, requested)
    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    settings: dict[str, object] = {
        "max_depth": args.max_depth,
        "max_solver_branches": args.max_solver_branches,
        "max_rounds": args.max_rounds,
        "branch_timeout_seconds": args.branch_timeout_seconds,
        "max_reductions": args.max_reductions,
        "max_terms": args.max_terms,
        "basic_set_mode": args.basic_set_mode,
        "initial_branch_mode": args.initial_branch_mode,
    }
    results = {
        name: _isolated(
            _setup_only(formulations[name]),
            settings,
            args.external_timeout_seconds,
        )
        for name in eligible
    }
    report = {
        "experiment": "certified-wu-ritt-characteristic-zero-decomposition",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "theoretical_basis": [
            "https://arxiv.org/abs/2604.14912",
            "https://github.com/WuProver/lean_characteristic_set",
            "https://arxiv.org/abs/2404.06405",
        ],
        "hypotheses": {
            "H1": (
                "completing BasicSet by repeated set pseudo-remainders gives a "
                "verified characteristic set rather than an approximate triangular chain"
            ),
            "H2": (
                "passing P union CS union {initial factor} to each degenerate child "
                "strictly decreases triangular rank and reduces repeated factor growth"
            ),
            "H3": (
                "the stricter algorithm may abstain more often, but cannot promote a "
                "conditional regular-locus proof until every degenerate branch closes"
            ),
        },
        "baseline_artifact": args.baseline_artifact.name,
        "generic_split_baseline_artifact": (
            "wu-zero-decomposition-fixed4-depth1-2026-08-17.json"
        ),
        "requested_problem_names": list(requested),
        "eligible_conditional_problem_names": list(eligible),
        "settings": settings,
        "results": results,
        "summary": _summary(results),
        "claim_scope": (
            "The experiment measures a bounded executable reconstruction of the "
            "published BasicSet/characteristicSet/zeroDecomposition control structure. "
            "It does not claim Lean kernel certification; exact polynomial identities "
            "and branch inheritance are independently replayed in Python."
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
