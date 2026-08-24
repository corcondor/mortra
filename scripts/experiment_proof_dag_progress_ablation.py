"""Paired LEAP-style decomposition-review ablation on fixed HAGeo problems."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
import time

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# The imported experiment installs Yuclid/Boost paths from the identical CLI
# arguments before importing Newclid's native modules.
from scripts.experiment_hageo_passk import (  # noqa: E402
    Atom,
    JGEXFormulation,
    JGEXProblemBuilder,
    formulation_goal_atoms,
    goal_conditioned_proof_basis,
    jgex_formulation_from_txt_file,
    native_rule_theorems,
    normalize_legacy_formulation,
    verify_problem,
    yuclid_assertion_keys,
)
from worker.backend.typed_open_proof_dag import compile_open_proof_dag  # noqa: E402


def _problem_names(args: argparse.Namespace) -> tuple[str, ...]:
    names = list(args.problem_name)
    if args.problem_file:
        names.extend(
            line.strip()
            for line in args.problem_file.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        )
    return tuple(dict.fromkeys(names))


def _arm(dag: object) -> dict[str, object]:
    branches = getattr(dag, "branches")
    return {
        "solved_frontier": any(not item.frontier for item in branches),
        "search_states": getattr(dag, "search_states"),
        "branch_count": len(branches),
        "open_branch_count": len(getattr(dag, "open_branches")),
        "rule_unifications": getattr(dag, "rule_unifications"),
        "fact_unifications": getattr(dag, "fact_unifications"),
        "rejected_nonprogressing_decompositions": getattr(
            dag, "rejected_nonprogressing_decompositions"
        ),
        "rejected_revisited_frontiers": getattr(
            dag, "rejected_revisited_frontiers"
        ),
        "truncated": getattr(dag, "truncated"),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-name", action="append", default=[])
    parser.add_argument("--problem-file", type=Path)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--depth", type=int, default=6)
    parser.add_argument("--branches", type=int, default=256)
    parser.add_argument("--states", type=int, default=10_000)
    args = parser.parse_args()
    names = _problem_names(args)
    if not names:
        parser.error("provide --problem-name or --problem-file")

    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    rules = native_rule_theorems()
    records: list[dict[str, object]] = []
    started = time.perf_counter()
    for offset, name in enumerate(names):
        raw = formulations[name]
        raw = JGEXFormulation(
            name=raw.name,
            setup_clauses=raw.setup_clauses,
            auxiliary_clauses=(),
            goals=raw.goals,
        )
        builder = JGEXProblemBuilder(np.random.default_rng(args.seed + offset))
        formulation, _ = normalize_legacy_formulation(raw, builder.jgex_defs)
        base_problem = (
            builder.with_problem(formulation).include_auxiliary_clauses(False).build()
        )
        baseline = verify_problem(
            base_problem,
            yuclid_exe=args.yuclid_exe.resolve(),
            ar_profile="all",
        )
        facts = tuple(
            Atom(predicate, points)
            for predicate, points in yuclid_assertion_keys(baseline.payload)
        )
        goal_records: list[dict[str, object]] = []
        for goal in formulation_goal_atoms(formulation):
            basis = goal_conditioned_proof_basis(
                facts,
                (goal,),
                rules,
                point_radius=1,
                max_facts=192,
                max_obligations=64,
            )
            control = compile_open_proof_dag(
                basis,
                goal,
                rules,
                max_rule_depth=args.depth,
                max_branches=args.branches,
                max_search_states=args.states,
                review_decompositions=False,
                rank_by_predicate_distance=False,
            )
            treatment = compile_open_proof_dag(
                basis,
                goal,
                rules,
                max_rule_depth=args.depth,
                max_branches=args.branches,
                max_search_states=args.states,
                review_decompositions=True,
                rank_by_predicate_distance=True,
            )
            control_arm = _arm(control)
            treatment_arm = _arm(treatment)
            goal_records.append(
                {
                    "goal": f"{goal.predicate}({','.join(goal.arguments)})",
                    "control": control_arm,
                    "treatment": treatment_arm,
                    "causal_difference": {
                        "solve_change": int(treatment_arm["solved_frontier"])
                        - int(control_arm["solved_frontier"]),
                        "search_state_change": int(treatment_arm["search_states"])
                        - int(control_arm["search_states"]),
                        "branch_count_change": int(treatment_arm["branch_count"])
                        - int(control_arm["branch_count"]),
                    },
                }
            )
        records.append(
            {
                "problem": name,
                "native_baseline_solved": baseline.solved,
                "goals": goal_records,
            }
        )

    goals = [goal for record in records for goal in record["goals"]]
    payload = {
        "experiment": "typed_proof_dag_decomposition_progress_ablation",
        "uses_external_llm": False,
        "problem_specific_rules_added": False,
        "protocol": {
            "evaluation_scope": "setup_only_proof_dag_ablation",
            "system_score": False,
            "excluded_capabilities": [
                "dataset_auxiliary_constructions",
                "newclid_native_portfolio",
                "gclc_wu_groebner",
                "exact_elimination_specialists",
            ],
            "depth": args.depth,
            "branches": args.branches,
            "states": args.states,
            "seed": args.seed,
            "truth_criterion": "empty_exact_typed_frontier",
        },
        "summary": {
            "problems": len(records),
            "goals": len(goals),
            "control_solves": sum(
                bool(goal["control"]["solved_frontier"]) for goal in goals
            ),
            "treatment_solves": sum(
                bool(goal["treatment"]["solved_frontier"]) for goal in goals
            ),
            "lost_solves": sum(
                goal["causal_difference"]["solve_change"] < 0 for goal in goals
            ),
            "additional_solves": sum(
                goal["causal_difference"]["solve_change"] > 0 for goal in goals
            ),
            "control_search_states": sum(
                int(goal["control"]["search_states"]) for goal in goals
            ),
            "treatment_search_states": sum(
                int(goal["treatment"]["search_states"]) for goal in goals
            ),
            "rejected_nonprogressing_decompositions": sum(
                int(goal["treatment"]["rejected_nonprogressing_decompositions"])
                for goal in goals
            ),
            "rejected_revisited_frontiers": sum(
                int(goal["treatment"]["rejected_revisited_frontiers"])
                for goal in goals
            ),
            "elapsed_seconds": time.perf_counter() - started,
        },
        "records": records,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(payload["summary"], indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
