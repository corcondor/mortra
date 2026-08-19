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
import math
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
    extend_prefix_branch,
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
from worker.backend.geometry_ar_residual import yuclid_ar_residual  # noqa: E402
from worker.backend.geometry_proof_hypergraph import Atom  # noqa: E402
from worker.backend.hageo_search_control import (  # noqa: E402
    candidate_pool,
    proof_residual_order_key,
    rank_biased_shortlist,
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


def _rank_biased_choice(
    pool: list[ConstructionStep],
    *,
    rng: random.Random,
    temperature: float,
) -> ConstructionStep:
    """Sample a ranked finite pool while preserving independent trajectories.

    ``temperature=0`` is greedy.  Positive temperature uses a geometric rank
    distribution; no problem identifier, answer, or construction literal is
    inspected here.
    """

    if not pool:
        raise ValueError("candidate pool must not be empty")
    if temperature < 0:
        raise ValueError("rank temperature must be nonnegative")
    if temperature == 0 or len(pool) == 1:
        return pool[0]
    continuation = math.exp(-1.0 / temperature)
    weights = [continuation**index for index in range(len(pool))]
    return rng.choices(pool, weights=weights, k=1)[0]


def _proof_residual(
    payload: dict[str, Any],
    *,
    goal_atoms: tuple[Any, ...],
    rule_theorems: tuple[Any, ...],
) -> dict[str, Any]:
    obligations, demands = proof_state_obligations(
        payload, goal_atoms, rule_theorems
    )
    ar = yuclid_ar_residual(
        payload,
        ((atom.predicate, atom.arguments) for atom in goal_atoms),
    )
    return {
        "open_relation_demands": len(demands),
        "backward_obligations": len(obligations),
        "ar_supported_goals": ar.supported_goal_count,
        "ar_closed_goals": ar.closed_goal_count,
        "ar_residual_support": ar.residual_support_size,
        "ar_residual_l1": ar.residual_l1_weight,
        "ar_known_rank": ar.known_rank,
    }


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
    relation_distances: dict[str, dict[str, int]],
    goal_atoms: tuple[Any, ...],
    baseline_facts: tuple[Any, ...],
    rule_theorems: tuple[Any, ...],
    per_family_limit: int,
    incidence_oversample_per_family: int,
    incidence_preselect_limit: int,
    incidence_workers: int,
    candidate_limit: int,
    yuclid_exe: Path,
    ar_profile: str,
    candidate_policy: str,
    rank_temperature: float,
    incremental_prefix: bool,
    feedback_candidates: int,
    feedback_workers: int,
) -> dict[str, Any]:
    started = time.perf_counter()
    attempt_seed = seed + 1_000_003 * attempt_index
    rng = random.Random(attempt_seed)
    steps: tuple[ConstructionStep, ...] = ()
    rounds_trace: list[dict[str, Any]] = []
    current_problem = base_problem.model_copy(deep=True)
    last_verification = None
    verification_calls = 0

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
                ranking=(
                    "structural" if candidate_policy == "typed-sheaf" else "random"
                ),
                seed=branch_seed(attempt_seed + round_index, steps),
                relation_demands=relation_demands,
                require_generated_input=False,
                candidate_gate="executable-precondition",
                candidate_reachable_channels=reachable_channels,
                candidate_target_channels=target_channels,
                candidate_alignment=(
                    "native-formal-sheaf"
                    if candidate_policy == "typed-sheaf"
                    else "off"
                ),
                candidate_relation_distances=(
                    relation_distances if candidate_policy == "typed-sheaf" else None
                ),
                proof_dag_goals=(goal_atoms if candidate_policy == "typed-sheaf" else ()),
                proof_dag_facts=(
                    baseline_facts if candidate_policy == "typed-sheaf" else ()
                ),
                proof_dag_theorems=(
                    rule_theorems if candidate_policy == "typed-sheaf" else ()
                ),
                candidate_cone_depth=2,
                candidate_cone_fragments=32,
                candidate_cone_states=250,
                candidate_cone_initial_states=32,
                candidate_promotion_limit=8,
                candidate_incidence="hageo",
                incidence_oversample_per_family=incidence_oversample_per_family,
                incidence_preselect_limit=incidence_preselect_limit,
                incidence_workers=incidence_workers,
                current_problem=current_problem,
                construction_seed=attempt_seed,
            )
            pool = candidate_pool(
                extensions,
                audit,
                hard_incidence_gate=(candidate_policy == "random"),
                preserve_family_frontier=(candidate_policy == "typed-sheaf"),
                family_order=[family.name for family in EXTENDED_POINT_FAMILIES],
            )
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
            feedback_trace: list[dict[str, Any]] = []
            if candidate_policy == "typed-sheaf" and feedback_candidates > 0:
                shortlist = rank_biased_shortlist(
                    pool,
                    count=min(feedback_candidates, len(pool)),
                    rng=rng,
                    temperature=(0.0 if attempt_index == 0 else rank_temperature),
                    trajectory_index=attempt_index,
                )

                def evaluate_candidate(index_and_step):
                    index, candidate = index_and_step
                    candidate_steps = (*steps, candidate)
                    try:
                        candidate_problem = (
                            extend_prefix_branch(
                                current_problem,
                                candidate,
                                candidate_steps,
                                seed=attempt_seed,
                            )
                            if incremental_prefix
                            else build_branch(
                                base_problem,
                                candidate_steps,
                                seed=attempt_seed,
                            )
                        )
                        verification = verify_problem(
                            candidate_problem,
                            yuclid_exe=yuclid_exe,
                            ar_profile=ar_profile,
                        )
                        residual = _proof_residual(
                            verification.payload,
                            goal_atoms=goal_atoms,
                            rule_theorems=rule_theorems,
                        )
                        return (
                            index,
                            candidate,
                            candidate_problem,
                            verification,
                            residual,
                            None,
                        )
                    except Exception as exc:
                        return (
                            index,
                            candidate,
                            None,
                            None,
                            None,
                            f"{type(exc).__name__}: {exc}",
                        )

                with ThreadPoolExecutor(max_workers=feedback_workers) as executor:
                    evaluations = list(
                        executor.map(evaluate_candidate, shortlist)
                    )
                verification_calls += len(evaluations)
                successful = [item for item in evaluations if item[3] is not None]
                if successful:
                    selected = min(
                        successful,
                        key=lambda item: (
                            not item[3].solved,
                            proof_residual_order_key(item[4]),
                            item[0],
                        ),
                    )
                    _, chosen, current_problem, last_verification, _, _ = selected
                    steps = (*steps, chosen)
                else:
                    chosen = _rank_biased_choice(
                        pool,
                        rng=rng,
                        temperature=rank_temperature,
                    )
                    steps = (*steps, chosen)
                    current_problem = build_branch(
                        base_problem, steps, seed=attempt_seed
                    )
                    last_verification = None
                feedback_trace = [
                    {
                        "candidate": candidate.key,
                        "static_rank": index,
                        "solved": bool(verification and verification.solved),
                        "proof_residual": residual,
                        "error": error,
                        "selected": candidate == chosen,
                    }
                    for index, candidate, _, verification, residual, error in evaluations
                ]
            else:
                chosen = (
                    _rank_biased_choice(
                        pool,
                        rng=rng,
                        temperature=rank_temperature,
                    )
                    if candidate_policy == "typed-sheaf"
                    else rng.choice(pool)
                )
                steps = (*steps, chosen)
                current_problem = (
                    extend_prefix_branch(
                        current_problem,
                        chosen,
                        steps,
                        seed=attempt_seed,
                    )
                    if incremental_prefix
                    else build_branch(base_problem, steps, seed=attempt_seed)
                )
                last_verification = None
            incidence = audit["numerical_incidence"]
            sheaf = audit["candidate_alignment"].get("native_formal_sheaf")
            rounds_trace.append(
                {
                    "round": round_index + 1,
                    "candidate_extension_seconds": audit["elapsed_seconds"],
                    "enumerated": audit["relation_reachability"]["input_count"],
                    "incidence_checked": incidence["checked_candidates"],
                    "heuristic_candidates": incidence["heuristic_candidates"],
                    "eligible_pool": len(pool),
                    "ranked_candidates": [step.key for step in pool],
                    "chosen": chosen.key,
                    "native_feedback": feedback_trace,
                    "coordination": (
                        {
                            "agents": len(sheaf["agents"]),
                            "consensus_agents": len(
                                sheaf["consensus_agent_ids"]
                            ),
                            "restriction_edges": sheaf["restriction_edge_count"],
                            "shared_candidates": sheaf["shared_candidate_count"],
                            "primal_residual": sheaf["primal_residual"],
                            "dual_residual": sheaf["dual_residual"],
                            "sheaf_residual": sheaf["sheaf_residual"],
                            "local_top_candidates": sheaf[
                                "local_top_candidates"
                            ],
                            "proof_dag_specialist": sheaf[
                                "proof_dag_specialist"
                            ],
                            "timing_seconds": sheaf["timing_seconds"],
                            "incidence_seconds": incidence[
                                "elapsed_seconds"
                            ],
                        }
                        if sheaf is not None
                        else None
                    ),
                }
            )
            if last_verification is not None and last_verification.solved:
                break

        result = last_verification
        if result is None:
            result = verify_problem(
                current_problem,
                yuclid_exe=yuclid_exe,
                ar_profile=ar_profile,
            )
            verification_calls += 1
        return {
            "attempt": attempt_index,
            "status": "solved" if result.solved else "unsolved",
            "solved": result.solved,
            "rounds_completed": len(steps),
            "path": [step.key for step in steps],
            "rounds": rounds_trace,
            "verification_calls": verification_calls,
            "all_deduction_count": result.all_deduction_count,
            "goal_deduction_count": result.goal_deduction_count,
            "input_sha256": result.input_sha256,
            "proof_sha256": result.proof_sha256,
            "proof": result.payload if result.solved else None,
            "proof_residual": _proof_residual(
                result.payload,
                goal_atoms=goal_atoms,
                rule_theorems=rule_theorems,
            ),
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
    parser.add_argument("--incidence-preselect-limit", type=int, default=0)
    parser.add_argument("--incidence-workers", type=int, default=1)
    parser.add_argument("--candidate-limit", type=int, default=0)
    parser.add_argument(
        "--candidate-policy",
        choices=("random", "typed-sheaf"),
        default="random",
    )
    parser.add_argument("--rank-temperature", type=float, default=2.0)
    parser.add_argument("--incremental-prefix", action="store_true")
    parser.add_argument("--feedback-candidates", type=int, default=0)
    parser.add_argument("--feedback-workers", type=int, default=1)
    parser.add_argument("--ar-profile", choices=("ratio-only", "standard", "all"), default="all")
    args = parser.parse_args()
    if (
        args.rounds < 1
        or args.attempts < 1
        or args.rank_temperature < 0
        or args.incidence_workers < 1
        or args.incidence_preselect_limit < 0
        or args.feedback_candidates < 0
        or args.feedback_workers < 1
    ):
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
    baseline_facts = tuple(
        Atom(predicate, points)
        for predicate, points in yuclid_assertion_keys(baseline.payload)
    )
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
    relation_distances = {
        target: backward_relation_distances(
            rule_channels,
            goal_channels={target},
        )
        for target in target_channels
    }

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
            "relation_distances": relation_distances,
            "goal_atoms": goal_atoms,
            "baseline_facts": baseline_facts,
            "rule_theorems": rules,
            "per_family_limit": args.per_family_limit,
            "incidence_oversample_per_family": args.incidence_oversample_per_family,
            "incidence_preselect_limit": args.incidence_preselect_limit,
            "incidence_workers": args.incidence_workers,
            "candidate_limit": args.candidate_limit,
            "yuclid_exe": args.yuclid_exe.resolve(),
            "ar_profile": args.ar_profile,
            "candidate_policy": args.candidate_policy,
            "rank_temperature": args.rank_temperature,
            "incremental_prefix": args.incremental_prefix,
            "feedback_candidates": args.feedback_candidates,
            "feedback_workers": args.feedback_workers,
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
            "trajectory_policy": (
                "typed_obligation_ranked_stratified_trajectories"
                if args.candidate_policy == "typed-sheaf"
                else "independent_seeded_numerical_incidence_sampling"
            ),
            "ddAR_calls": (
                "baseline_plus_native_shortlist_feedback_with_terminal_reuse"
                if args.feedback_candidates
                else "baseline_plus_one_terminal_call_per_complete_attempt"
            ),
            "rounds_n": args.rounds,
            "attempts_k": args.attempts,
            "attempt_offset": args.attempt_offset,
            "workers": args.workers,
            "seed": args.seed,
            "per_family_limit": args.per_family_limit,
            "incidence_oversample_per_family": args.incidence_oversample_per_family,
            "incidence_preselect_limit": args.incidence_preselect_limit,
            "incidence_workers": args.incidence_workers,
            "candidate_limit": args.candidate_limit,
            "candidate_policy": args.candidate_policy,
            "rank_temperature": args.rank_temperature,
            "incremental_prefix": args.incremental_prefix,
            "feedback_candidates": args.feedback_candidates,
            "feedback_workers": args.feedback_workers,
            "proof_dag_specialist_budget": {
                "per_family_candidates": 16,
                "depth": 2,
                "fragments": 32,
                "initial_states_per_candidate": 32,
                "states_per_task": 250,
                "reserved_consensus": 8,
                "reserved_family_frontier": True,
            },
            "truth_plane": "yuclid_native_certificate_replay_only",
        },
        "problem_name": args.problem_name,
        "normalization": asdict(normalization),
        "baseline_solved": baseline.solved,
        "baseline_proof_residual": _proof_residual(
            baseline.payload,
            goal_atoms=goal_atoms,
            rule_theorems=rules,
        ),
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
