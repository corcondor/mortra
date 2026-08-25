"""Seek an exact radical certificate from one terminal geometry checkpoint."""

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

from scripts.experiment_guarded_linear_singular import _parse_multipliers  # noqa: E402
from scripts.experiment_terminal_checkpoint_singular import (  # noqa: E402
    factor_terminal_systems,
    load_terminal_checkpoint,
)
from worker.backend.singular_lift_backend import (  # noqa: E402
    prove_radical_membership_with_singular,
)
from worker.backend.source_guarded_linear_elimination import (  # noqa: E402
    eliminate_source_guarded_linear_variables,
    lift_guarded_linear_power_certificate,
    source_proved_nondegeneracy_factors,
)
from worker.backend.source_preserving_polynomial_reduction import (  # noqa: E402
    lift_reduced_power_multipliers,
    reduce_by_monic_univariate_relations,
    retarget_source_preserving_reduction,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument("--max-linear-steps", type=int, default=2)
    parser.add_argument("--max-linear-expression-ops", type=int, default=100_000)
    parser.add_argument("--max-linear-total-ops", type=int, default=300_000)
    parser.add_argument("--max-triangular-degree", type=int, default=2)
    parser.add_argument("--max-saturation-rounds", type=int, default=1)
    parser.add_argument("--max-saturation-candidates", type=int, default=8)
    parser.add_argument("--skip-unsaturated", action="store_true")
    parser.add_argument("--all-saturation-product", action="store_true")
    parser.add_argument("--admissible-branch-index", type=int, default=0)
    parser.add_argument("--unfactored", action="store_true")
    parser.add_argument(
        "--basis-engine",
        choices=("liftstd", "slimgb_lift", "module_slimgb"),
        default="slimgb_lift",
    )
    args = parser.parse_args()

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

    guarded = eliminate_source_guarded_linear_variables(
        branch["polynomials"],
        terminal["variables"],
        terminal["goal"],
        terminal["nonzero_factor_expressions"],
        max_steps=args.max_linear_steps,
        max_expression_operation_count=args.max_linear_expression_ops,
        max_total_operation_count=args.max_linear_total_ops,
    )
    triangular_base = reduce_by_monic_univariate_relations(
        guarded.reduced_polynomials,
        guarded.reduced_variables,
        guarded.reduced_goal,
        max_degree=args.max_triangular_degree,
    )
    proof_polynomials = tuple(
        item.expression for item in triangular_base.reduced_polynomials
    )
    saturation_factors = source_proved_nondegeneracy_factors(
        guarded,
        allowed_symbols=(
            *guarded.reduced_variables,
            *terminal["coefficient_parameters"],
        ),
        proof_variables=guarded.reduced_variables,
    )
    multiplier_specs: list[tuple[int, sp.Expr]] = (
        [] if args.skip_unsaturated else [(0, sp.Integer(1))]
    )
    accepted_candidates = 0
    if args.all_saturation_product and saturation_factors:
        multiplier_specs.append(
            (len(saturation_factors), sp.Mul(*saturation_factors))
        )
    else:
        for depth in range(1, args.max_saturation_rounds + 1):
            for selected_factors in combinations(saturation_factors, depth):
                if accepted_candidates >= args.max_saturation_candidates:
                    break
                multiplier_specs.append((depth, sp.Mul(*selected_factors)))
                accepted_candidates += 1
            if accepted_candidates >= args.max_saturation_candidates:
                break

    attempts: list[dict[str, object]] = []
    selected_attempt_index = None
    for index, (depth, multiplier) in enumerate(multiplier_specs):
        target = multiplier * guarded.reduced_goal
        triangular = (
            triangular_base
            if depth == 0
            else retarget_source_preserving_reduction(triangular_base, target)
        )
        certificate = prove_radical_membership_with_singular(
            proof_polynomials,
            triangular.reduced_variables,
            triangular.reduced_goal,
            timeout_seconds=args.timeout_seconds,
            basis_engine=args.basis_engine,
            coefficient_parameters=terminal["coefficient_parameters"],
        )
        triangular_multipliers = None
        guarded_lift = None
        strictly_accepted = False
        if (
            certificate.proved
            and certificate.replayed
            and certificate.radical_exponent is not None
        ):
            reduced_multipliers = _parse_multipliers(
                certificate.source_multipliers,
                (
                    *triangular.reduced_variables,
                    *terminal["coefficient_parameters"],
                ),
            )
            triangular_multipliers = lift_reduced_power_multipliers(
                triangular,
                reduced_multipliers,
                exponent=certificate.radical_exponent,
            )
            guarded_lift = lift_guarded_linear_power_certificate(
                guarded,
                triangular_multipliers,
                exponent=certificate.radical_exponent,
                reduced_goal_power_multiplier=(
                    multiplier**certificate.radical_exponent
                ),
            )
            strictly_accepted = bool(
                (args.unfactored or len(branches) == 1)
                and guarded_lift.replayed
                and guarded_lift.multiplier_source_proved_nonzero
            )
        if strictly_accepted and selected_attempt_index is None:
            selected_attempt_index = index
        attempts.append(
            {
                "depth": depth,
                "multiplier": sp.sstr(multiplier),
                "certificate": asdict(certificate),
                "triangular_lifted_multipliers": (
                    None
                    if triangular_multipliers is None
                    else tuple(sp.sstr(item) for item in triangular_multipliers)
                ),
                "source_lift": (
                    None
                    if guarded_lift is None
                    else {
                        "exponent": guarded_lift.exponent,
                        "reduced_goal_power_multiplier": sp.sstr(
                            guarded_lift.reduced_goal_power_multiplier
                        ),
                        "goal_power_multiplier": sp.sstr(
                            guarded_lift.goal_power_multiplier
                        ),
                        "source_multipliers": tuple(
                            sp.sstr(item) for item in guarded_lift.source_multipliers
                        ),
                        "replay_residual": sp.sstr(guarded_lift.replay_residual),
                        "replayed": guarded_lift.replayed,
                        "nonzero_multiplier_factor_keys": (
                            guarded_lift.nonzero_multiplier_factor_keys
                        ),
                        "multiplier_source_proved_nonzero": (
                            guarded_lift.multiplier_source_proved_nonzero
                        ),
                    }
                ),
                "strictly_accepted": strictly_accepted,
            }
        )

    report = {
        "experiment": "terminal-radical-source-certificate-search",
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
        "guarded_shape": [
            len(guarded.reduced_polynomials),
            len(guarded.reduced_variables),
        ],
        "triangular_shape": [
            len(proof_polynomials),
            len(triangular_base.reduced_variables),
        ],
        "linear_step_count": len(guarded.steps),
        "basis_engine": args.basis_engine,
        "saturation_factors": tuple(sp.sstr(item) for item in saturation_factors),
        "attempts": attempts,
        "strictly_accepted": selected_attempt_index is not None,
        "selected_attempt_index": selected_attempt_index,
        "elapsed_seconds": time.perf_counter() - started,
        "claim_scope": (
            "Rabinowitsch membership is accepted only after the resulting goal "
            "power is replayed over the original checkpoint polynomials. Guarded "
            "elimination coefficients must be source-proved nonzero."
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
                "attempt_count": len(attempts),
                "statuses": tuple(
                    item["certificate"]["status"] for item in attempts
                ),
                "strictly_accepted": selected_attempt_index is not None,
                "selected_attempt_index": selected_attempt_index,
                "elapsed_seconds": report["elapsed_seconds"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
