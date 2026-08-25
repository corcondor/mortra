"""Prove a terminal JGEX branch after exact source-guarded linear elimination."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import hashlib
from itertools import combinations
import json
from pathlib import Path
import sys
import time

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.experiment_terminal_checkpoint_singular import (  # noqa: E402
    factor_terminal_systems,
    load_terminal_checkpoint,
)
from worker.backend.singular_lift_backend import (  # noqa: E402
    prove_ideal_membership_with_singular,
)
from worker.backend.source_guarded_linear_elimination import (  # noqa: E402
    eliminate_source_guarded_linear_variables,
    lift_guarded_linear_certificate,
    source_preserving_goal_factor_candidates,
    source_proved_nondegeneracy_factors,
)
from worker.backend.source_preserving_polynomial_reduction import (  # noqa: E402
    lift_reduced_multipliers,
    reduce_by_monic_univariate_relations,
)


def _parse_multipliers(
    texts: tuple[str, ...],
    symbols: tuple[sp.Symbol, ...],
) -> tuple[sp.Expr, ...]:
    local_symbols = {str(symbol): symbol for symbol in symbols}
    return tuple(sp.sympify(text, locals=local_symbols) for text in texts)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--monomial-order", choices=("dp", "lp"), default="dp")
    parser.add_argument(
        "--basis-engine",
        choices=(
            "liftstd",
            "slimgb_lift",
            "direct_lift",
            "module_slimgb",
            "bounded_linear",
        ),
        default="liftstd",
    )
    parser.add_argument("--max-linear-steps", type=int, default=2)
    parser.add_argument("--max-linear-expression-ops", type=int, default=100_000)
    parser.add_argument("--max-linear-total-ops", type=int, default=300_000)
    parser.add_argument("--max-triangular-degree", type=int, default=2)
    parser.add_argument("--max-certificate-degree", type=int)
    parser.add_argument("--max-saturation-rounds", type=int, default=0)
    parser.add_argument("--max-saturation-candidates", type=int, default=16)
    parser.add_argument("--admissible-branch-index", type=int, default=0)
    parser.add_argument(
        "--unfactored",
        action="store_true",
        help="Prove the original checkpoint equations without selecting factor cases",
    )
    parser.add_argument(
        "--variable-order",
        help="Comma-separated permutation of the reduced proof variables",
    )
    parser.add_argument(
        "--goal-factor-index",
        type=int,
        help=(
            "Prove one exact factor of the reduced goal and multiply its "
            "complement back into the source certificate"
        ),
    )
    args = parser.parse_args()
    if args.max_saturation_rounds < 0 or args.max_saturation_candidates < 0:
        raise ValueError("saturation bounds must be non-negative")

    terminal = load_terminal_checkpoint(
        args.checkpoint.resolve(),
        include_nondegeneracy_factors=True,
    )
    print("stage=checkpoint_loaded", flush=True)
    if args.unfactored:
        branches: tuple[dict[str, object], ...] = ()
        branch = {
            "polynomials": terminal["polynomials"],
            "choice_indices": None,
            "factorization_certificates": (),
        }
        print("stage=factor_cover_skipped scope=unfactored", flush=True)
    else:
        branches = factor_terminal_systems(terminal)
        print(f"stage=factor_cover_complete branches={len(branches)}", flush=True)
        if not 0 <= args.admissible_branch_index < len(branches):
            raise ValueError("admissible branch index is out of range")
        branch = branches[args.admissible_branch_index]
    preprocessing_started = time.perf_counter()

    def report_linear_progress(stage: str, details: dict[str, int | str]) -> None:
        rendered = " ".join(f"{key}={value}" for key, value in details.items())
        print(f"stage=linear_{stage} {rendered}".rstrip(), flush=True)

    reduced = eliminate_source_guarded_linear_variables(
        branch["polynomials"],
        terminal["variables"],
        terminal["goal"],
        terminal["nonzero_factor_expressions"],
        max_steps=args.max_linear_steps,
        max_expression_operation_count=args.max_linear_expression_ops,
        max_total_operation_count=args.max_linear_total_ops,
        progress_callback=report_linear_progress,
    )
    linear_elimination_seconds = time.perf_counter() - preprocessing_started
    print(
        "stage=linear_elimination_complete "
        f"seconds={linear_elimination_seconds:.3f} "
        f"steps={len(reduced.steps)} "
        f"stopped_reason={reduced.stopped_reason or 'none'}",
        flush=True,
    )
    goal_factor_candidates = source_preserving_goal_factor_candidates(
        reduced.reduced_goal,
        proof_variables=reduced.reduced_variables,
    )
    selected_goal_factor = None
    if args.goal_factor_index is not None:
        if not 0 <= args.goal_factor_index < len(goal_factor_candidates):
            raise ValueError("goal factor index is out of range")
        selected_goal_factor = goal_factor_candidates[args.goal_factor_index]
        print(
            "stage=goal_factor_selected "
            f"index={args.goal_factor_index} "
            f"factor_ops={int(sp.count_ops(selected_goal_factor.factor))} "
            "complement_ops="
            f"{int(sp.count_ops(selected_goal_factor.complementary_multiplier))}",
            flush=True,
        )

    def run_multiplier(multiplier: sp.Expr):
        proof_goal = (
            selected_goal_factor.factor
            if selected_goal_factor is not None
            else reduced.reduced_goal
        )
        target = sp.sympify(multiplier) * proof_goal
        triangular_started = time.perf_counter()
        triangular_result = reduce_by_monic_univariate_relations(
            reduced.reduced_polynomials,
            reduced.reduced_variables,
            target,
            max_degree=args.max_triangular_degree,
        )
        triangular_seconds = time.perf_counter() - triangular_started
        print(
            "stage=triangular_reduction_complete "
            f"seconds={triangular_seconds:.3f} "
            f"variables={len(triangular_result.reduced_variables)}",
            flush=True,
        )
        ordered_proof_variables = triangular_result.reduced_variables
        if args.variable_order:
            requested_names = tuple(
                item.strip()
                for item in args.variable_order.split(",")
                if item.strip()
            )
            by_name = {
                str(item): item for item in triangular_result.reduced_variables
            }
            if set(requested_names) != set(by_name) or len(requested_names) != len(
                by_name
            ):
                raise ValueError(
                    "variable order must be a permutation of reduced variables"
                )
            ordered_proof_variables = tuple(by_name[name] for name in requested_names)
        backend_started = time.perf_counter()
        result = prove_ideal_membership_with_singular(
            tuple(item.expression for item in triangular_result.reduced_polynomials),
            ordered_proof_variables,
            triangular_result.reduced_goal,
            timeout_seconds=args.timeout_seconds,
            monomial_order=args.monomial_order,
            basis_engine=args.basis_engine,
            max_certificate_degree=args.max_certificate_degree,
            coefficient_parameters=terminal["coefficient_parameters"],
        )
        backend_seconds = time.perf_counter() - backend_started
        print(
            "stage=singular_complete "
            f"seconds={backend_seconds:.3f} status={result.status}",
            flush=True,
        )
        lifted_result = None
        accepted = False
        if result.proved and result.replayed:
            multipliers = _parse_multipliers(
                result.initial_multipliers,
                (*ordered_proof_variables, *terminal["coefficient_parameters"]),
            )
            multipliers = lift_reduced_multipliers(
                triangular_result,
                multipliers,
            )
            if selected_goal_factor is not None:
                multipliers = tuple(
                    item * selected_goal_factor.complementary_multiplier
                    for item in multipliers
                )
            lifted_result = lift_guarded_linear_certificate(
                reduced,
                multipliers,
                reduced_goal_multiplier=multiplier,
            )
            accepted = bool(
                (args.unfactored or len(branches) == 1)
                and lifted_result.replayed
                and lifted_result.multiplier_source_proved_nonzero
            )
        return (
            triangular_result,
            ordered_proof_variables,
            result,
            lifted_result,
            accepted,
        )

    (
        triangular,
        proof_variables,
        certificate,
        lifted,
        strictly_accepted,
    ) = run_multiplier(sp.Integer(1))
    ordinary_certificate = certificate
    saturation_factors = source_proved_nondegeneracy_factors(
        reduced,
        allowed_symbols=(
            *reduced.reduced_variables,
            *terminal["coefficient_parameters"],
        ),
        proof_variables=reduced.reduced_variables,
    )
    saturation_attempts: list[dict[str, object]] = []
    attempted = 0
    if not strictly_accepted:
        for depth in range(1, args.max_saturation_rounds + 1):
            for selected_factors in combinations(saturation_factors, depth):
                if attempted >= args.max_saturation_candidates:
                    break
                attempted += 1
                multiplier = sp.Mul(*selected_factors)
                (
                    candidate_triangular,
                    candidate_variables,
                    candidate_certificate,
                    candidate_lifted,
                    candidate_accepted,
                ) = run_multiplier(multiplier)
                saturation_attempts.append(
                    {
                        "depth": depth,
                        "multiplier": sp.sstr(multiplier),
                        "status": candidate_certificate.status,
                        "proved": candidate_certificate.proved,
                        "replayed": candidate_certificate.replayed,
                        "strictly_accepted": candidate_accepted,
                        "certificate_sha256": (
                            candidate_certificate.certificate_sha256
                        ),
                    }
                )
                if candidate_accepted:
                    triangular = candidate_triangular
                    proof_variables = candidate_variables
                    certificate = candidate_certificate
                    lifted = candidate_lifted
                    strictly_accepted = True
                    break
            if strictly_accepted or attempted >= args.max_saturation_candidates:
                break

    source = terminal["source"]
    report = {
        "experiment": "source-guarded-linear-elimination-singular-lift",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_expected_answer": False,
        "uses_problem_specific_solver_logic": False,
        "source_checkpoint": args.checkpoint.resolve().as_posix(),
        "source_checkpoint_sha256": source["certificate_sha256"],
        "admissible_factor_cover": {
            "enumerated": not args.unfactored,
            "branch_count": None if args.unfactored else len(branches),
            "selected_branch_index": (
                None if args.unfactored else args.admissible_branch_index
            ),
            "selected_choice_indices": branch["choice_indices"],
            "factorizations_replayed": all(
                item["replayed"]
                for item in branch["factorization_certificates"]
            ),
        },
        "proof_scope": (
            "unfactored_source_system" if args.unfactored else "selected_factor_branch"
        ),
        "linear_elimination": {
            "source_equation_count": len(branch["polynomials"]),
            "source_variable_count": len(terminal["variables"]),
            "step_count": len(reduced.steps),
            "elapsed_seconds": linear_elimination_seconds,
            "stopped_reason": reduced.stopped_reason,
            "max_expression_operation_count": args.max_linear_expression_ops,
            "max_total_operation_count": args.max_linear_total_ops,
            "operation_counts_by_stage": reduced.operation_counts_by_stage,
            "reduced_equation_count": len(reduced.reduced_polynomials),
            "reduced_variable_count": len(reduced.reduced_variables),
            "steps": tuple(
                {
                    "pivot_source_index": step.pivot_source_index,
                    "pivot_variable": str(step.pivot_variable),
                    "coefficient": sp.sstr(step.coefficient),
                    "coefficient_factor_keys": step.coefficient_factor_keys,
                    "coefficient_source_proved_nonzero": (
                        step.coefficient_source_proved_nonzero
                    ),
                }
                for step in reduced.steps
            ),
        },
        "goal_factorization": {
            "candidate_count": len(goal_factor_candidates),
            "selected_index": args.goal_factor_index,
            "selected_factor": (
                sp.sstr(selected_goal_factor.factor)
                if selected_goal_factor is not None
                else None
            ),
            "selected_complementary_multiplier": (
                sp.sstr(selected_goal_factor.complementary_multiplier)
                if selected_goal_factor is not None
                else None
            ),
            "selected_replayed": (
                selected_goal_factor.replayed
                if selected_goal_factor is not None
                else None
            ),
            "candidates": tuple(
                {
                    "factor": sp.sstr(item.factor),
                    "complementary_multiplier": sp.sstr(
                        item.complementary_multiplier
                    ),
                    "factor_operation_count": int(sp.count_ops(item.factor)),
                    "replayed": item.replayed,
                }
                for item in goal_factor_candidates
            ),
        },
        "source_preserving_reduction": {
            "reducer_input_indices": triangular.reducer_input_indices,
            "eliminated_reducer_input_indices": (
                triangular.eliminated_reducer_input_indices
            ),
            "kept_input_indices": tuple(
                item.input_index for item in triangular.reduced_polynomials
            ),
            "input_operation_counts": tuple(
                int(sp.count_ops(reduced.reduced_polynomials[item.input_index]))
                for item in triangular.reduced_polynomials
            ),
            "reduced_operation_counts": tuple(
                int(sp.count_ops(item.expression))
                for item in triangular.reduced_polynomials
            ),
            "goal_operation_count_before": int(sp.count_ops(reduced.reduced_goal)),
            "goal_operation_count_after": int(sp.count_ops(triangular.reduced_goal)),
            "proof_variable_order": tuple(str(item) for item in proof_variables),
        },
        "ordinary_ideal_certificate": asdict(ordinary_certificate),
        "nondegeneracy_saturation_search": {
            "max_rounds": args.max_saturation_rounds,
            "max_candidates": args.max_saturation_candidates,
            "candidate_factors": tuple(sp.sstr(item) for item in saturation_factors),
            "attempts": tuple(saturation_attempts),
            "selected_multiplier": (
                sp.sstr(lifted.reduced_goal_multiplier)
                if lifted is not None and strictly_accepted
                else None
            ),
        },
        "singular_certificate": asdict(certificate),
        "lifted_saturation_certificate": (
            None
            if lifted is None
            else {
                "goal_multiplier": sp.sstr(lifted.goal_multiplier),
                "reduced_goal_multiplier": sp.sstr(lifted.reduced_goal_multiplier),
                "source_multipliers": tuple(
                    sp.sstr(item) for item in lifted.source_multipliers
                ),
                "replay_residual": sp.sstr(lifted.replay_residual),
                "replayed": lifted.replayed,
                "reduced_goal_multiplier_factor_keys": (
                    lifted.reduced_goal_multiplier_factor_keys
                ),
                "reduced_goal_multiplier_source_proved_nonzero": (
                    lifted.reduced_goal_multiplier_source_proved_nonzero
                ),
                "nonzero_multiplier_factor_keys": (
                    lifted.nonzero_multiplier_factor_keys
                ),
                "multiplier_source_proved_nonzero": (
                    lifted.multiplier_source_proved_nonzero
                ),
            }
        ),
        "strictly_accepted": strictly_accepted,
        "claim_scope": (
            "Accepted only when every source-nonzero factor case is pruned "
            "exactly, Singular's reduced lift replays, and the lifted "
            "source-level saturation identity replays with a proved-nonzero "
            "goal multiplier."
        ),
    }
    material = json.dumps(report, ensure_ascii=False, sort_keys=True)
    report["report_sha256"] = hashlib.sha256(material.encode()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": certificate.status,
                "proved": certificate.proved,
                "replayed": certificate.replayed,
                "strictly_accepted": strictly_accepted,
                "linear_steps": len(reduced.steps),
                "source_shape": [
                    len(branch["polynomials"]),
                    len(terminal["variables"]),
                ],
                "reduced_shape": [
                    len(reduced.reduced_polynomials),
                    len(reduced.reduced_variables),
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
