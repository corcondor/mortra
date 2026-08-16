"""独立変数を有理関数係数体へ局所化するWu--Ritt ablation。"""

from __future__ import annotations

import argparse
import gzip
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
from worker.backend.certified_wu_characteristic import (  # noqa: E402
    structural_goal_cone,
    structural_variable_matching,
)
from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
    inspect_jgex_exact_system,
)
from worker.backend.wu_ritt_characteristic import (  # noqa: E402
    certified_wu_ritt_goal_proof,
)


DEFAULT_NEWCLID = Path.home() / ".cache" / "mortra-research-sources" / "Newclid"


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
        variables = tuple(symbols[name] for name in variable_names)
        equations = tuple(
            sp.sympify(item, locals=symbols)
            for item in analysis.construction_equations
        )
        goal = sp.sympify(analysis.goal_polynomial, locals=symbols)
        matching = structural_variable_matching(equations, variables)
        cone = structural_goal_cone(equations, variables, goal)
        selected_equations = (
            tuple(equations[index] for index in cone.equation_indices)
            if bool(settings["goal_cone"])
            else equations
        )
        selected_variable_names = (
            cone.variable_names if bool(settings["goal_cone"]) else variable_names
        )
        selected_variables = tuple(symbols[name] for name in selected_variable_names)
        parameters = (
            tuple(
                symbols[name]
                for name in matching.parameter_variables
                if name in selected_variable_names
            )
            if bool(settings["coefficient_field"])
            else ()
        )
        proof = certified_wu_ritt_goal_proof(
            selected_equations,
            selected_variables,
            goal,
            coefficient_variables=parameters,
            basic_set_mode=str(settings["basic_set_mode"]),
            max_rounds=int(settings["max_rounds"]),
            max_reductions=int(settings["max_reductions"]),
            max_terms=int(settings["max_terms"]),
            timeout_seconds=float(settings["timeout_seconds"]),
        )
        payload = {
            "status": "completed",
            "input": {
                "variable_count": analysis.variable_count,
                "equation_count": analysis.equation_count,
                "parameter_variables": matching.parameter_variables,
                "dependent_variables": matching.dependent_variables,
                "matching_complete": matching.complete,
                "goal_cone_equation_indices": cone.equation_indices,
                "goal_cone_variable_names": cone.variable_names,
                "dropped_equation_indices": cone.dropped_equation_indices,
                "construction_vocabulary": analysis.construction_vocabulary,
            },
            "proof": asdict(proof),
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
    with tempfile.TemporaryDirectory(prefix="mortra-wu-parameter-field-") as directory:
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
    proofs = [item["proof"] for item in completed]
    characteristics = [item["characteristic"] for item in proofs]
    return {
        "completed": len(completed),
        "timeouts": sum(item["status"] == "timeout" for item in results.values()),
        "execution_errors": sum(
            item["status"] == "execution_error" for item in results.values()
        ),
        "characteristic_sets_verified": sum(
            item["characteristic_set_verified"] for item in characteristics
        ),
        "conditional_goals_proved": sum(
            item["conditional_goal_proved"] for item in proofs
        ),
        "completion_rounds": sum(len(item["rounds"]) for item in characteristics),
        "pseudo_division_steps": sum(
            item["reduction_count"] for item in characteristics
        ),
        "maximum_term_count": max(
            (item["maximum_term_count"] for item in characteristics),
            default=0,
        ),
        "all_identities_replayed": all(
            item["all_identities_replayed"] for item in proofs
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
    parser.add_argument("--problems", nargs="+", default=["2021_p3"])
    parser.add_argument("--max-rounds", type=int, default=16)
    parser.add_argument("--coefficient-field", action="store_true")
    parser.add_argument("--goal-cone", action="store_true")
    parser.add_argument("--weak-basic-set", action="store_true")
    parser.add_argument("--timeout-seconds", type=float, default=70.0)
    parser.add_argument("--external-timeout-seconds", type=float, default=240.0)
    parser.add_argument("--max-reductions", type=int, default=20_000)
    parser.add_argument("--max-terms", type=int, default=20_000)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "data" / "wu-ritt-parameter-field-2026-08-17.json",
    )
    args = parser.parse_args()
    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    settings: dict[str, object] = {
        "max_rounds": args.max_rounds,
        "coefficient_field": args.coefficient_field,
        "goal_cone": args.goal_cone,
        "basic_set_mode": "weak" if args.weak_basic_set else "standard",
        "timeout_seconds": args.timeout_seconds,
        "max_reductions": args.max_reductions,
        "max_terms": args.max_terms,
    }
    results = {
        name: _isolated(
            _setup_only(formulations[name]),
            settings,
            args.external_timeout_seconds,
        )
        for name in args.problems
    }
    report = {
        "experiment": "wu-ritt-structural-localization-ablation",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "dataset_auxiliary_clauses_hidden": True,
        "theoretical_basis": [
            "https://arxiv.org/abs/2604.14912",
            "https://github.com/WuProver/lean_characteristic_set",
            "https://www.cs.unm.edu/~kapur/mypapers/refutationalapproachgeometrytheoremproving.pdf",
        ],
        "hypothesis": (
            "A backward structural goal cone reduces irrelevant equations before "
            "characteristic-set completion; optional incidence-unmatched coefficient "
            "localization tests whether QQ(u) further reduces coefficient swell."
        ),
        "parameter_selection": (
            "Structural bipartite matching and goal-variable reachability only; no "
            "problem name, theorem answer, or auxiliary construction is visible."
        ),
        "settings": settings,
        "results": results,
        "summary": _summary(results),
        "claim_scope": (
            "A coefficient-field proof is conditional on every rational-function "
            "coefficient used as an initial being defined and nonzero. This experiment "
            "tests computational feasibility; full polynomial-space zero decomposition "
            "requires those numerator/denominator exceptional loci to be branched."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    encoded = (json.dumps(report, ensure_ascii=False, indent=2) + "\n").encode()
    if args.output.suffix == ".gz":
        args.output.write_bytes(gzip.compress(encoded, compresslevel=9, mtime=0))
    else:
        args.output.write_bytes(encoded)
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    print(args.output)
    return 0


if __name__ == "__main__":
    mp.freeze_support()
    raise SystemExit(main())
