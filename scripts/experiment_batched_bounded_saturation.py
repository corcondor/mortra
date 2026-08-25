"""Batch exact bounded certificates for one terminal geometry checkpoint."""

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

from scripts.experiment_guarded_linear_singular import (  # noqa: E402
    _bounded_goal_degree,
    _parse_multipliers,
)
from scripts.experiment_terminal_checkpoint_singular import (  # noqa: E402
    factor_terminal_systems,
    load_terminal_checkpoint,
)
from worker.backend.singular_lift_backend import (  # noqa: E402
    prove_ideal_membership_with_singular,
    prove_ideal_memberships_with_singular,
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
    retarget_source_preserving_reduction,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--max-linear-steps", type=int, default=2)
    parser.add_argument("--max-linear-expression-ops", type=int, default=100_000)
    parser.add_argument("--max-linear-total-ops", type=int, default=300_000)
    parser.add_argument("--max-triangular-degree", type=int, default=2)
    parser.add_argument("--max-certificate-degree", type=int, required=True)
    parser.add_argument("--max-saturation-rounds", type=int, default=1)
    parser.add_argument("--max-saturation-candidates", type=int, default=16)
    parser.add_argument("--saturation-start-index", type=int, default=0)
    parser.add_argument("--admissible-branch-index", type=int, default=0)
    parser.add_argument("--goal-factor-index", type=int)
    parser.add_argument("--all-goal-factors", action="store_true")
    parser.add_argument("--unfactored", action="store_true")
    parser.add_argument(
        "--execution-mode",
        choices=("batch", "sequential"),
        default="batch",
    )
    args = parser.parse_args()
    if args.all_goal_factors and args.goal_factor_index is not None:
        raise ValueError("choose one goal factor mode")

    started = time.perf_counter()
    terminal = load_terminal_checkpoint(
        args.checkpoint.resolve(),
        include_nondegeneracy_factors=True,
    )
    if args.unfactored:
        branches: tuple[dict[str, object], ...] = ()
        branch = {
            "polynomials": terminal["polynomials"],
            "choice_indices": None,
            "factorization_certificates": (),
        }
    else:
        branches = factor_terminal_systems(terminal)
        if not 0 <= args.admissible_branch_index < len(branches):
            raise ValueError("admissible branch index is out of range")
        branch = branches[args.admissible_branch_index]

    reduced = eliminate_source_guarded_linear_variables(
        branch["polynomials"],
        terminal["variables"],
        terminal["goal"],
        terminal["nonzero_factor_expressions"],
        max_steps=args.max_linear_steps,
        max_expression_operation_count=args.max_linear_expression_ops,
        max_total_operation_count=args.max_linear_total_ops,
    )
    goal_factors = source_preserving_goal_factor_candidates(
        reduced.reduced_goal,
        proof_variables=reduced.reduced_variables,
    )
    if args.all_goal_factors:
        selected_goal_factors = (
            (None, None),
            *tuple(enumerate(goal_factors)),
        )
    elif args.goal_factor_index is not None:
        if not 0 <= args.goal_factor_index < len(goal_factors):
            raise ValueError("goal factor index is out of range")
        selected_goal_factors = (
            (args.goal_factor_index, goal_factors[args.goal_factor_index]),
        )
    else:
        selected_goal_factors = ((None, None),)

    saturation_factors = source_proved_nondegeneracy_factors(
        reduced,
        allowed_symbols=(
            *reduced.reduced_variables,
            *terminal["coefficient_parameters"],
        ),
        proof_variables=reduced.reduced_variables,
    )
    saturation_multiplier_specs: list[tuple[int, sp.Expr]] = [
        (0, sp.Integer(1))
    ]
    candidate_index = -1
    accepted_candidates = 0
    for depth in range(1, args.max_saturation_rounds + 1):
        for selected_factors in combinations(saturation_factors, depth):
            candidate_index += 1
            if candidate_index < args.saturation_start_index:
                continue
            if accepted_candidates >= args.max_saturation_candidates:
                break
            saturation_multiplier_specs.append((depth, sp.Mul(*selected_factors)))
            accepted_candidates += 1
        if accepted_candidates >= args.max_saturation_candidates:
            break

    prepared: list[dict[str, object]] = []
    triangular_base = None
    skipped: list[dict[str, object]] = []
    for goal_factor_index, selected_goal_factor in selected_goal_factors:
        proof_goal = (
            selected_goal_factor.factor
            if selected_goal_factor is not None
            else reduced.reduced_goal
        )
        for depth, multiplier in saturation_multiplier_specs:
            target = sp.sympify(multiplier) * proof_goal
            triangular_source_reused = triangular_base is not None
            if triangular_base is None:
                triangular = reduce_by_monic_univariate_relations(
                    reduced.reduced_polynomials,
                    reduced.reduced_variables,
                    target,
                    max_degree=args.max_triangular_degree,
                )
                triangular_base = triangular
            else:
                triangular = retarget_source_preserving_reduction(
                    triangular_base,
                    target,
                )
            required_degree = _bounded_goal_degree(
                triangular.reduced_goal,
                variables=triangular.reduced_variables,
                coefficient_parameters=terminal["coefficient_parameters"],
            )
            if required_degree > args.max_certificate_degree:
                skipped.append(
                    {
                        "goal_factor_index": goal_factor_index,
                        "depth": depth,
                        "multiplier": sp.sstr(multiplier),
                        "status": "skipped_certificate_degree_budget",
                        "required_certificate_degree": required_degree,
                    }
                )
                continue
            prepared.append(
                {
                    "goal_factor_index": goal_factor_index,
                    "selected_goal_factor": selected_goal_factor,
                    "depth": depth,
                    "multiplier": multiplier,
                    "triangular": triangular,
                    "triangular_source_reused": triangular_source_reused,
                    "required_certificate_degree": required_degree,
                }
            )

    if not prepared:
        raise ValueError("no target fits the requested certificate degree")
    base = prepared[0]["triangular"]
    source_polynomials = tuple(item.expression for item in base.reduced_polynomials)
    proof_variables = base.reduced_variables
    if any(
        item["triangular"].reduced_variables != proof_variables
        or tuple(
            polynomial.expression
            for polynomial in item["triangular"].reduced_polynomials
        )
        != source_polynomials
        for item in prepared[1:]
    ):
        raise AssertionError("batched targets do not share one reduced source system")

    backend_started = time.perf_counter()
    if args.execution_mode == "batch":
        certificates = prove_ideal_memberships_with_singular(
            source_polynomials,
            proof_variables,
            tuple(item["triangular"].reduced_goal for item in prepared),
            timeout_seconds=args.timeout_seconds,
            max_certificate_degree=args.max_certificate_degree,
            coefficient_parameters=terminal["coefficient_parameters"],
        )
    else:
        certificates = tuple(
            prove_ideal_membership_with_singular(
                source_polynomials,
                proof_variables,
                item["triangular"].reduced_goal,
                timeout_seconds=args.timeout_seconds,
                basis_engine="bounded_linear",
                max_certificate_degree=args.max_certificate_degree,
                coefficient_parameters=terminal["coefficient_parameters"],
            )
            for item in prepared
        )
    backend_seconds = time.perf_counter() - backend_started

    attempts: list[dict[str, object]] = []
    selected_index = None
    for index, (prepared_item, certificate) in enumerate(
        zip(prepared, certificates, strict=True)
    ):
        triangular = prepared_item["triangular"]
        multiplier = prepared_item["multiplier"]
        selected_goal_factor = prepared_item["selected_goal_factor"]
        lifted = None
        strictly_accepted = False
        if certificate.proved and certificate.replayed:
            reduced_multipliers = _parse_multipliers(
                certificate.initial_multipliers,
                (*proof_variables, *terminal["coefficient_parameters"]),
            )
            reduced_multipliers = lift_reduced_multipliers(
                triangular,
                reduced_multipliers,
            )
            if selected_goal_factor is not None:
                reduced_multipliers = tuple(
                    item * selected_goal_factor.complementary_multiplier
                    for item in reduced_multipliers
                )
            lifted = lift_guarded_linear_certificate(
                reduced,
                reduced_multipliers,
                reduced_goal_multiplier=multiplier,
            )
            strictly_accepted = bool(
                (args.unfactored or len(branches) == 1)
                and lifted.replayed
                and lifted.multiplier_source_proved_nonzero
            )
        if strictly_accepted and selected_index is None:
            selected_index = index
        attempts.append(
            {
                "goal_factor_index": prepared_item["goal_factor_index"],
                "depth": prepared_item["depth"],
                "multiplier": sp.sstr(multiplier),
                "required_certificate_degree": prepared_item[
                    "required_certificate_degree"
                ],
                "certificate": asdict(certificate),
                "lifted_source_certificate": (
                    None
                    if lifted is None
                    else {
                        "goal_multiplier": sp.sstr(lifted.goal_multiplier),
                        "source_multipliers": tuple(
                            sp.sstr(item) for item in lifted.source_multipliers
                        ),
                        "replay_residual": sp.sstr(lifted.replay_residual),
                        "replayed": lifted.replayed,
                        "multiplier_source_proved_nonzero": (
                            lifted.multiplier_source_proved_nonzero
                        ),
                    }
                ),
                "strictly_accepted": strictly_accepted,
            }
        )

    report = {
        "experiment": "batched-bounded-source-certificate-search",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_expected_answer": False,
        "uses_problem_specific_solver_logic": False,
        "source_checkpoint": args.checkpoint.resolve().as_posix(),
        "source_checkpoint_sha256": terminal["source"]["certificate_sha256"],
        "proof_scope": (
            "unfactored_source_system" if args.unfactored else "selected_factor_branch"
        ),
        "source_shape": [len(branch["polynomials"]), len(terminal["variables"])],
        "reduced_shape": [len(source_polynomials), len(proof_variables)],
        "linear_step_count": len(reduced.steps),
        "certificate_degree": args.max_certificate_degree,
        "candidate_count": len(attempts),
        "skipped_candidates": skipped,
        "execution_mode": args.execution_mode,
        "shared_basis_computation_count": (
            1 if args.execution_mode == "batch" else len(prepared)
        ),
        "backend_elapsed_seconds": backend_seconds,
        "total_elapsed_seconds": time.perf_counter() - started,
        "goal_factor_indices": tuple(
            item[0] for item in selected_goal_factors
        ),
        "saturation_factors": tuple(sp.sstr(item) for item in saturation_factors),
        "attempts": attempts,
        "strictly_accepted": selected_index is not None,
        "selected_attempt_index": selected_index,
        "claim_scope": (
            "Each target is reduced and lifted separately against one shared exact "
            "Macaulay basis. Acceptance requires source-level replay and a "
            "source-proved nonzero multiplier."
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
                "candidate_count": len(attempts),
                "shared_basis_computation_count": report[
                    "shared_basis_computation_count"
                ],
                "strictly_accepted": report["strictly_accepted"],
                "selected_attempt_index": selected_index,
                "backend_elapsed_seconds": backend_seconds,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
