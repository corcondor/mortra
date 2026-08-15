"""Measure an exact JGEX backend as an addition to a frozen Yuclid baseline."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path

from newclid.jgex.formulation import (
    JGEXFormulation,
    jgex_formulation_from_txt_file,
)
from newclid.problem import PredicateConstruction

from worker.backend.jgex_exact_constraint_bridge import (
    lower_jgex_to_exact_obligation,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-name", required=True)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    problems = jgex_formulation_from_txt_file(args.dataset)
    formulation = problems[args.problem_name]
    setup_only = JGEXFormulation(
        name=formulation.name,
        setup_clauses=formulation.setup_clauses,
        auxiliary_clauses=(),
        goals=formulation.goals,
    )
    obligation = lower_jgex_to_exact_obligation(str(setup_only))
    canonical_goal = str(
        PredicateConstruction.from_str(
            " ".join((obligation.channel, *obligation.points))
        )
    )

    baseline = json.loads(args.baseline.read_text(encoding="utf-8"))
    baseline_score = baseline["scores"]["original_imo_ag_30"]
    native_result = baseline["results"][args.problem_name]
    newly_solved = native_result["status"] != "solved" and obligation.exact_replay
    portfolio_solved = int(baseline_score["solved"]) + int(newly_solved)

    report = {
        "experiment": "jgex_exact_constraint_portfolio",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_problem_specific_solver_logic": False,
        "problem_selection_is_benchmark_only": True,
        "dataset_auxiliary_clauses_hidden": True,
        "problem_name": args.problem_name,
        "native_yuclid": {
            "status": native_result["status"],
            "baseline_solved": baseline_score["solved"],
            "baseline_total": baseline_score["total"],
        },
        "exact_backend": {
            "canonical_goal": canonical_goal,
            "certificate": asdict(obligation),
        },
        "portfolio": {
            "newly_solved": newly_solved,
            "solved": portfolio_solved,
            "total": baseline_score["total"],
            "score": portfolio_solved / int(baseline_score["total"]),
            "delta_solved": int(newly_solved),
        },
        "claim_scope": (
            "One frozen IMO-AG-30 obligation is solved by a generic four-construction "
            "JGEX lowering. This is a symbolic portfolio result, not a Newclid-native "
            "proof and not yet evidence for broad held-out generalization."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["portfolio"], ensure_ascii=False, indent=2))
    return 0 if newly_solved else 1


if __name__ == "__main__":
    raise SystemExit(main())
