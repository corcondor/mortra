"""固定幾何義務でWu--Ritt型の正則/退化枝被覆を測定する。"""

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
from worker.backend.wu_zero_decomposition import (  # noqa: E402
    decompose_wu_zero_set,
    verify_zero_decomposition_cover,
)
from worker.backend.wu_experiment_selection import (  # noqa: E402
    eligible_conditional_names,
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
        decomposition = decompose_wu_zero_set(
            equations,
            tuple(symbols[name] for name in variable_names),
            goal,
            known_nonzero_conditions=analysis.executable_regularity_conditions,
            max_depth=int(settings["max_depth"]),
            max_solver_branches=int(settings["max_solver_branches"]),
            max_reductions=int(settings["max_reductions"]),
            max_terms=int(settings["max_terms"]),
            timeout_seconds_per_branch=float(settings["branch_timeout_seconds"]),
            root_timeout_seconds=float(settings["root_timeout_seconds"]),
            max_content_terms=int(settings["max_content_terms"]),
            zero_first_elimination=bool(settings["zero_first_elimination"]),
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
            "cover_verified": verify_zero_decomposition_cover(decomposition),
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
    with tempfile.TemporaryDirectory(prefix="mortra-wu-zero-") as directory:
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
        "distinct_branch_factors": sum(
            item["distinct_branch_factor_count"] for item in decompositions
        ),
        "regularity_cycles": sum(
            branch["status"] == "regularity_cycle" for branch in branches
        ),
        "branch_budget_leaves": sum(
            branch["status"] == "branch_budget" for branch in branches
        ),
        "term_budget_leaves": sum(
            branch["stopped_reason"] == "term_budget" for branch in branches
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
    parser.add_argument("--root-timeout-seconds", type=float, default=70.0)
    parser.add_argument("--branch-timeout-seconds", type=float, default=20.0)
    parser.add_argument("--external-timeout-seconds", type=float, default=360.0)
    parser.add_argument("--max-reductions", type=int, default=10_000)
    parser.add_argument("--max-terms", type=int, default=20_000)
    parser.add_argument("--max-content-terms", type=int, default=5_000)
    parser.add_argument("--no-zero-first", action="store_true")
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "wu-zero-decomposition-fixed4-2026-08-17.json",
    )
    args = parser.parse_args()
    baseline = json.loads(args.baseline_artifact.read_text(encoding="utf-8"))
    requested = tuple(args.problems or baseline["fixed_problem_names"])
    eligible = eligible_conditional_names(baseline, requested)
    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    settings: dict[str, object] = {
        "max_depth": args.max_depth,
        "max_solver_branches": args.max_solver_branches,
        "root_timeout_seconds": args.root_timeout_seconds,
        "branch_timeout_seconds": args.branch_timeout_seconds,
        "max_reductions": args.max_reductions,
        "max_terms": args.max_terms,
        "max_content_terms": args.max_content_terms,
        "zero_first_elimination": not args.no_zero_first,
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
        "experiment": "wu-ritt-constructible-zero-decomposition",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "theoretical_basis": [
            "https://arxiv.org/abs/2604.14912",
            "https://arxiv.org/abs/1702.08664",
            "https://arxiv.org/abs/1907.13537",
        ],
        "hypotheses": {
            "H1": "factor canonicalization reduces duplicate power conditions before branching",
            "H2": "zero-first elimination turns some regularity-zero loci into smaller provable systems",
            "H3": "a root proof is promoted only if every regular and degenerate child closes",
        },
        "baseline_artifact": args.baseline_artifact.name,
        "requested_problem_names": list(requested),
        "eligible_conditional_problem_names": list(eligible),
        "settings": settings,
        "results": results,
        "summary": _summary(results),
        "claim_scope": (
            "Only conditional baseline proofs with open regularity obligations enter the "
            "experiment. A finite cover is proved only when every regular leaf and every "
            "factor-zero branch is proved or contradicted by an input nondegeneracy fact."
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
