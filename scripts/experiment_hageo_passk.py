"""Independent HAGeo-style N-round auxiliary construction attempts.

Unlike the layer-wise beam experiment, every attempt keeps its own construction
trajectory for N rounds and calls DDAR only for the completed trajectory.  This
matches the experimental unit in HAGeo's Pass@K protocol without using a neural
model, dataset auxiliary clauses, problem identifiers, or expected answers.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict
from pathlib import Path
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

# Importing this module also installs the Yuclid/Boost runtime paths from this
# script's identical command-line arguments.
from scripts.experiment_newclid_construction_stalk import (  # noqa: E402
    ConstructionStep,
    EXTENDED_POINT_FAMILIES,
    JGEXFormulation,
    JGEXProblemBuilder,
    backward_relation_distances,
    branch_seed,
    build_branch,
    candidate_extensions,
    formulation_goal_atoms,
    formulation_structure,
    jgex_formulation_from_txt_file,
    native_rule_theorems,
    normalize_legacy_formulation,
    proof_hypergraph_relevance,
    proof_state_obligations,
    yuclid_assertion_keys,
    DEFAULT_RULES,
)
from worker.backend.yuclid_native_verifier import verify_problem  # noqa: E402


def _goal_channels(formulation: JGEXFormulation) -> set[str]:
    channels: set[str] = set()
    for goal in formulation.goals:
        name = getattr(goal, "name", None)
        if hasattr(name, "value"):
            name = name.value
        channels.add(str(name or str(goal).split()[0]).lower())
    return channels


def _candidate_pool(
    extensions: list[ConstructionStep], audit: dict[str, Any]
) -> list[ConstructionStep]:
    profiles = {
        item["step_key"]: item
        for item in audit["numerical_incidence"].get("selected_candidates", [])
    }
    executable = [step for step in extensions if step.key in profiles]
    heuristic = [
        step
        for step in executable
        if profiles[step.key].get("is_heuristic_candidate")
    ]
    return heuristic or executable


def _attempt(
    *,
    attempt_index: int,
    seed: int,
    rounds: int,
    base_problem: Any,
    base_points: set[str],
    base_graph: dict[str, set[str]],
    base_role_graph: dict[str, set[str]],
    base_role_weights: dict[tuple[str, str], int],
    goal_multiplicity: dict[str, int],
    proof_relevance: dict[str, float],
    relation_demands: tuple[Any, ...],
    reachable_channels: set[str],
    target_channels: set[str],
    per_family_limit: int,
    incidence_oversample_per_family: int,
    candidate_limit: int,
    yuclid_exe: Path,
    ar_profile: str,
) -> dict[str, Any]:
    started = time.perf_counter()
    attempt_seed = seed + 1_000_003 * attempt_index
    rng = random.Random(attempt_seed)
    steps: tuple[ConstructionStep, ...] = ()
    rounds_trace: list[dict[str, Any]] = []
    current_problem = base_problem.model_copy(deep=True)

    try:
        for round_index in range(rounds):
            extensions, audit = candidate_extensions(
                base_problem=base_problem,
                base_points=base_points,
                base_graph=base_graph,
                base_role_graph=base_role_graph,
                base_role_weights=base_role_weights,
                goal_multiplicity=goal_multiplicity,
                proof_relevance=proof_relevance,
                steps=steps,
                families=EXTENDED_POINT_FAMILIES,
                per_family_limit=per_family_limit,
                branch_limit=candidate_limit,
                ranking="random",
                seed=branch_seed(attempt_seed + round_index, steps),
                relation_demands=relation_demands,
                require_generated_input=False,
                candidate_gate="executable-precondition",
                candidate_reachable_channels=reachable_channels,
                candidate_target_channels=target_channels,
                candidate_alignment="off",
                candidate_incidence="hageo",
                incidence_oversample_per_family=incidence_oversample_per_family,
                current_problem=current_problem,
                construction_seed=attempt_seed,
            )
            pool = _candidate_pool(extensions, audit)
            if not pool:
                return {
                    "attempt": attempt_index,
                    "status": "no_executable_candidate",
                    "solved": False,
                    "rounds_completed": round_index,
                    "path": [step.key for step in steps],
                    "rounds": rounds_trace,
                    "elapsed_seconds": time.perf_counter() - started,
                }
            chosen = rng.choice(pool)
            steps = (*steps, chosen)
            current_problem = build_branch(base_problem, steps, seed=attempt_seed)
            incidence = audit["numerical_incidence"]
            rounds_trace.append(
                {
                    "round": round_index + 1,
                    "enumerated": audit["relation_reachability"]["input_count"],
                    "incidence_checked": incidence["checked_candidates"],
                    "heuristic_candidates": incidence["heuristic_candidates"],
                    "eligible_pool": len(pool),
                    "chosen": chosen.key,
                }
            )

        result = verify_problem(
            current_problem,
            yuclid_exe=yuclid_exe,
            ar_profile=ar_profile,
        )
        return {
            "attempt": attempt_index,
            "status": "solved" if result.solved else "unsolved",
            "solved": result.solved,
            "rounds_completed": len(steps),
            "path": [step.key for step in steps],
            "rounds": rounds_trace,
            "all_deduction_count": result.all_deduction_count,
            "goal_deduction_count": result.goal_deduction_count,
            "input_sha256": result.input_sha256,
            "proof_sha256": result.proof_sha256,
            "proof": result.payload if result.solved else None,
            "elapsed_seconds": time.perf_counter() - started,
        }
    except Exception as exc:
        return {
            "attempt": attempt_index,
            "status": "execution_error",
            "solved": False,
            "error_type": type(exc).__name__,
            "error": str(exc),
            "rounds_completed": len(steps),
            "path": [step.key for step in steps],
            "rounds": rounds_trace,
            "elapsed_seconds": time.perf_counter() - started,
        }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-name", required=True)
    parser.add_argument("--yuclid-exe", type=Path, required=True)
    parser.add_argument("--runtime-path", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--rounds", type=int, default=6)
    parser.add_argument("--attempts", type=int, default=64)
    parser.add_argument("--attempt-offset", type=int, default=0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--per-family-limit", type=int, default=8)
    parser.add_argument("--incidence-oversample-per-family", type=int, default=32)
    parser.add_argument("--candidate-limit", type=int, default=0)
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    args = parser.parse_args()
    if args.rounds < 1 or args.attempts < 1:
        parser.error("--rounds and --attempts must be positive")

    started = time.perf_counter()
    formulations = jgex_formulation_from_txt_file(args.dataset.resolve())
    raw = formulations[args.problem_name]
    raw = JGEXFormulation(
        name=raw.name,
        setup_clauses=raw.setup_clauses,
        auxiliary_clauses=(),
        goals=raw.goals,
    )
    builder = JGEXProblemBuilder(np.random.default_rng(args.seed))
    formulation, normalization = normalize_legacy_formulation(raw, builder.jgex_defs)
    base_problem = builder.with_problem(formulation).include_auxiliary_clauses(False).build()
    baseline = verify_problem(
        base_problem,
        yuclid_exe=args.yuclid_exe.resolve(),
        ar_profile=args.ar_profile,
    )
    base_points, base_graph, base_role_graph, base_role_weights, goal_multiplicity = (
        formulation_structure(formulation)
    )
    goal_atoms = formulation_goal_atoms(formulation)
    rules = native_rule_theorems()
    _, relation_demands = proof_state_obligations(baseline.payload, goal_atoms, rules)
    goal_support = set(goal_multiplicity)
    proof_relevance = proof_hypergraph_relevance(baseline.payload, goal_support)
    target_channels = {atom.predicate.lower() for atom in relation_demands} or _goal_channels(formulation)
    rule_channels = [
        ([premise.name for premise in rule.premises], [conclusion.name for conclusion in rule.conclusions])
        for rule in DEFAULT_RULES
    ]
    reachable_channels = set(
        backward_relation_distances(rule_channels, goal_channels=target_channels)
    )

    attempts: list[dict[str, Any]] = []
    if not baseline.solved:
        kwargs = {
            "seed": args.seed,
            "rounds": args.rounds,
            "base_problem": base_problem,
            "base_points": base_points,
            "base_graph": base_graph,
            "base_role_graph": base_role_graph,
            "base_role_weights": base_role_weights,
            "goal_multiplicity": goal_multiplicity,
            "proof_relevance": proof_relevance,
            "relation_demands": relation_demands,
            "reachable_channels": reachable_channels,
            "target_channels": target_channels,
            "per_family_limit": args.per_family_limit,
            "incidence_oversample_per_family": args.incidence_oversample_per_family,
            "candidate_limit": args.candidate_limit,
            "yuclid_exe": args.yuclid_exe.resolve(),
            "ar_profile": args.ar_profile,
        }
        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {
                executor.submit(_attempt, attempt_index=index, **kwargs): index
                for index in range(
                    args.attempt_offset,
                    args.attempt_offset + args.attempts,
                )
            }
            for future in as_completed(futures):
                attempts.append(future.result())
        attempts.sort(key=lambda item: item["attempt"])

    solved_attempts = [item for item in attempts if item["solved"]]
    first_solved = solved_attempts[0] if solved_attempts else None
    artifact = {
        "experiment": "hageo_independent_n_round_pass_at_k_no_llm",
        "protocol": {
            "uses_external_llm": False,
            "uses_dataset_auxiliary_clauses": False,
            "uses_problem_id_in_search": False,
            "uses_expected_answer": False,
            "trajectory_policy": "independent_seeded_numerical_incidence_sampling",
            "ddAR_calls": "baseline_plus_one_terminal_call_per_complete_attempt",
            "rounds_n": args.rounds,
            "attempts_k": args.attempts,
            "attempt_offset": args.attempt_offset,
            "workers": args.workers,
            "seed": args.seed,
            "per_family_limit": args.per_family_limit,
            "incidence_oversample_per_family": args.incidence_oversample_per_family,
            "candidate_limit": args.candidate_limit,
            "truth_plane": "yuclid_native_certificate_replay_only",
        },
        "problem_name": args.problem_name,
        "normalization": asdict(normalization),
        "baseline_solved": baseline.solved,
        "solved": baseline.solved or bool(solved_attempts),
        "pass_at_k": bool(solved_attempts),
        "first_solved_attempt": first_solved["attempt"] if first_solved else None,
        "unique_paths": len({tuple(item["path"]) for item in attempts}),
        "completed_attempts": sum(item["rounds_completed"] == args.rounds for item in attempts),
        "execution_errors": sum(item["status"] == "execution_error" for item in attempts),
        "elapsed_seconds": time.perf_counter() - started,
        "attempt_results": attempts,
    }
    if first_solved is not None:
        proof_path = args.output.with_suffix(".proof.json")
        proof_path.parent.mkdir(parents=True, exist_ok=True)
        proof_path.write_text(json.dumps(first_solved["proof"], indent=2) + "\n", encoding="utf-8")
        artifact["certificate"] = {
            "input_sha256": first_solved["input_sha256"],
            "proof_sha256": first_solved["proof_sha256"],
            "proof_path": proof_path.resolve().relative_to(ROOT).as_posix(),
            "proof_file_sha256": hashlib.sha256(proof_path.read_bytes()).hexdigest(),
        }
        for item in attempts:
            item.pop("proof", None)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(artifact, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "problem": args.problem_name,
                "rounds": args.rounds,
                "attempts": args.attempts,
                "solved": artifact["solved"],
                "unique_paths": artifact["unique_paths"],
                "elapsed_seconds": artifact["elapsed_seconds"],
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
