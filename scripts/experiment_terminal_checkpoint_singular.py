"""Resume an exact JGEX terminal ideal with Singular and replay its proof."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import product
import json
from pathlib import Path
import sys
import time

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.jgex_exact_constraint_bridge import (  # noqa: E402
    _canonical_nonconstant_factor_keys,
)
from worker.backend.singular_lift_backend import (  # noqa: E402
    probe_ideal_membership_with_singular,
    prove_ideal_membership_with_singular,
)


def load_terminal_checkpoint(
    path: Path,
    *,
    include_nondegeneracy_factors: bool = False,
) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if payload.get("schema") != "mortra.terminal_groebner_system.v1":
        raise ValueError("unsupported terminal checkpoint schema")

    names = tuple(
        dict.fromkeys(
            (
                *payload.get("variables", ()),
                *payload.get("coefficient_parameters", ()),
            )
        )
    )
    symbols = {name: sp.Symbol(name) for name in names}
    equations = tuple(
        sp.sympify(item, locals=symbols) for item in payload["input_polynomials"]
    )
    goal = sp.sympify(payload["goal_polynomial"], locals=symbols)
    nonzero_expressions = tuple(
        sp.sympify(str(item).removesuffix(" != 0"), locals=symbols)
        for item in payload.get("nonzero_conditions", ())
    )
    all_declared_symbols = tuple(symbols.values())

    def cleared_fraction(expression: sp.Expr) -> tuple[sp.Expr, sp.Expr]:
        if expression.is_polynomial(*all_declared_symbols) is True:
            return expression, sp.S.One
        return sp.fraction(sp.cancel(expression))

    cleared_equations = tuple(cleared_fraction(item) for item in equations)
    goal_numerator, goal_denominator = cleared_fraction(goal)
    requires_denominator_proof = any(
        denominator is not sp.S.One
        for _, denominator in (*cleared_equations, (goal_numerator, goal_denominator))
    )
    known_nonzero_keys = (
        frozenset().union(
            *(
                _canonical_nonconstant_factor_keys(item)
                for item in nonzero_expressions
            )
        )
        if requires_denominator_proof or include_nondegeneracy_factors
        else frozenset()
    )

    polynomial_equations: list[sp.Expr] = []
    cleared_denominators: list[str] = []
    for numerator, denominator in cleared_equations:
        missing = (
            _canonical_nonconstant_factor_keys(denominator) - known_nonzero_keys
        )
        if missing:
            raise ValueError(
                "checkpoint equation has an unproved denominator: "
                + ", ".join(sorted(missing))
            )
        polynomial_equations.append(numerator)
        if denominator is not sp.S.One:
            cleared_denominators.append(sp.sstr(denominator))

    missing_goal = (
        _canonical_nonconstant_factor_keys(goal_denominator) - known_nonzero_keys
    )
    if missing_goal:
        raise ValueError(
            "checkpoint goal has an unproved denominator: "
            + ", ".join(sorted(missing_goal))
        )
    if goal_denominator is not sp.S.One:
        cleared_denominators.append(sp.sstr(goal_denominator))

    all_symbols = set(goal_numerator.free_symbols)
    for equation in polynomial_equations:
        all_symbols.update(equation.free_symbols)
    proof_variables = tuple(
        symbols[name]
        for name in payload.get("variables", ())
        if symbols[name] in all_symbols
    )
    coefficient_parameters = tuple(
        symbols[name]
        for name in payload.get("coefficient_parameters", ())
        if symbols[name] in all_symbols
    )
    omitted = all_symbols - set((*proof_variables, *coefficient_parameters))
    proof_variables += tuple(sorted(omitted, key=sp.default_sort_key))
    full_ring_variables = (*proof_variables, *coefficient_parameters)

    return {
        "source": payload,
        "polynomials": tuple(polynomial_equations),
        "variables": proof_variables,
        "coefficient_parameters": coefficient_parameters,
        "nonzero_expressions": nonzero_expressions,
        "nonzero_factor_expressions": tuple(
            sp.sympify(key, locals=symbols) for key in sorted(known_nonzero_keys)
        ),
        "known_nonzero_factor_keys": tuple(sorted(known_nonzero_keys)),
        "full_ring_variables": full_ring_variables,
        "goal": goal_numerator,
        "cleared_denominators": tuple(cleared_denominators),
        "all_denominators_source_proved_nonzero": True,
    }


def factor_terminal_systems(terminal: dict[str, object]) -> tuple[dict[str, object], ...]:
    """Cover a product-defined terminal variety by its admissible factor cases.

    A source-proved nonzero irreducible factor cannot be the zero factor of a
    product equation.  Removing that case is the exact saturation step induced
    by the construction's nondegeneracy conditions; it is not a search
    heuristic.
    """

    proof_variables = terminal["variables"]
    coefficient_parameters = terminal["coefficient_parameters"]
    domain = (
        sp.QQ.frac_field(*coefficient_parameters)
        if coefficient_parameters
        else sp.QQ
    )
    known_nonzero_factor_keys = frozenset(
        terminal.get("known_nonzero_factor_keys", ())
    )
    equation_options: list[tuple[tuple[int, sp.Expr], ...]] = []
    factorization_certificates: list[dict[str, object]] = []
    for equation in terminal["polynomials"]:
        polynomial = sp.Poly(equation, *proof_variables, domain=domain)
        unit, factors = polynomial.factor_list()
        all_options = tuple(
            (index, sp.expand(factor.as_expr()))
            for index, (factor, _) in enumerate(factors)
        )
        excluded_options = tuple(
            (index, factor)
            for index, factor in all_options
            if (
                _canonical_nonconstant_factor_keys(factor)
                and _canonical_nonconstant_factor_keys(factor)
                <= known_nonzero_factor_keys
            )
        )
        options = tuple(
            (index, factor)
            for index, factor in all_options
            if (index, factor) not in excluded_options
        )
        if not options:
            if all_options:
                raise ValueError(
                    "every zero-factor case is excluded by source-proved "
                    "nonzero conditions"
                )
            options = ((0, sp.expand(equation)),)
        product_expression = sp.sympify(unit)
        for factor, multiplicity in factors:
            product_expression *= factor.as_expr() ** multiplicity
        residual = sp.cancel(sp.expand(equation) - sp.expand(product_expression))
        if residual != 0:
            raise AssertionError("terminal factorization did not replay")
        equation_options.append(options)
        factorization_certificates.append(
            {
                "source_polynomial": sp.sstr(sp.expand(equation)),
                "unit": sp.sstr(unit),
                "factors": tuple(
                    (sp.sstr(sp.expand(factor.as_expr())), multiplicity)
                    for factor, multiplicity in factors
                ),
                "excluded_source_nonzero_factors": tuple(
                    (index, sp.sstr(factor)) for index, factor in excluded_options
                ),
                "replay_residual": sp.sstr(residual),
                "replayed": True,
            }
        )

    branches: list[dict[str, object]] = []
    for branch_index, indexed_choices in enumerate(product(*equation_options)):
        choice_indices = tuple(index for index, _ in indexed_choices)
        choices = tuple(factor for _, factor in indexed_choices)
        branches.append(
            {
                "branch_index": branch_index,
                "choice_indices": choice_indices,
                "polynomials": tuple(choices),
                "factorization_certificates": tuple(factorization_certificates),
                "cover_theorem": (
                    "Over an integral domain, product(f_i)=0 iff at least one "
                    "irreducible factor f_i=0; the Cartesian product of these "
                    "choices covers the zero set of all source equations."
                ),
            }
        )
    return tuple(branches)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    parser.add_argument("--monomial-order", choices=("dp", "lp"), default="dp")
    parser.add_argument(
        "--basis-engine",
        choices=("liftstd", "slimgb_lift", "module_slimgb", "direct_lift"),
        default="liftstd",
    )
    parser.add_argument(
        "--coefficient-mode",
        choices=("fraction_field", "full_ring"),
        default="fraction_field",
    )
    parser.add_argument("--probe-first", action="store_true")
    parser.add_argument("--probe-only", action="store_true")
    parser.add_argument(
        "--probe-engine",
        choices=("std", "slimgb"),
        default="slimgb",
    )
    parser.add_argument("--probe-timeout-seconds", type=float, default=60.0)
    parser.add_argument("--factor-branch-index", type=int)
    args = parser.parse_args()

    preprocessing_started = time.perf_counter()
    terminal = load_terminal_checkpoint(
        args.checkpoint,
        include_nondegeneracy_factors=args.factor_branch_index is not None,
    )
    # Factor-cover enumeration is only required for an explicitly selected
    # branch.  Ordinary ideal membership proves the unsplit source system and
    # must not pay an unbounded factorization cost just to report branch counts.
    factor_branches: tuple[dict[str, object], ...] = ()
    selected_branch = None
    proof_polynomials = terminal["polynomials"]
    if args.factor_branch_index is not None:
        factor_branches = factor_terminal_systems(terminal)
        if not 0 <= args.factor_branch_index < len(factor_branches):
            raise ValueError(
                f"factor branch index must be in [0, {len(factor_branches) - 1}]"
            )
        selected_branch = factor_branches[args.factor_branch_index]
        proof_polynomials = selected_branch["polynomials"]
    preprocessing_seconds = time.perf_counter() - preprocessing_started
    ring_variables = (
        terminal["full_ring_variables"]
        if args.coefficient_mode == "full_ring"
        else terminal["variables"]
    )
    coefficient_parameters = (
        ()
        if args.coefficient_mode == "full_ring"
        else terminal["coefficient_parameters"]
    )
    probe = None
    if args.probe_first or args.probe_only:
        probe = probe_ideal_membership_with_singular(
            proof_polynomials,
            ring_variables,
            terminal["goal"],
            timeout_seconds=args.probe_timeout_seconds,
            monomial_order=args.monomial_order,
            coefficient_parameters=coefficient_parameters,
            engine=args.probe_engine,
        )
    should_construct_certificate = not args.probe_only and (
        probe is None or (probe.status == "computed" and probe.member)
    )
    certificate = (
        prove_ideal_membership_with_singular(
            proof_polynomials,
            ring_variables,
            terminal["goal"],
            timeout_seconds=args.timeout_seconds,
            monomial_order=args.monomial_order,
            basis_engine=args.basis_engine,
            coefficient_parameters=coefficient_parameters,
        )
        if should_construct_certificate
        else None
    )
    factor_cover_complete = selected_branch is None or len(factor_branches) == 1
    source = terminal["source"]
    report = {
        "experiment": "terminal-jgex-checkpoint-singular-lift",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_expected_answer": False,
        "uses_problem_specific_solver_logic": False,
        "source_checkpoint": args.checkpoint.resolve().as_posix(),
        "source_checkpoint_sha256": source["certificate_sha256"],
        "terminal_system": {
            "equation_count": len(proof_polynomials),
            "variable_count": len(ring_variables),
            "coefficient_parameter_count": len(
                source.get("coefficient_parameters", ())
            ),
            "cleared_denominators": terminal["cleared_denominators"],
            "all_denominators_source_proved_nonzero": terminal[
                "all_denominators_source_proved_nonzero"
            ],
        },
        "method": {
            "backend": f"Singular {args.basis_engine}",
            "basis_engine": args.basis_engine,
            "monomial_order": args.monomial_order,
            "timeout_seconds": args.timeout_seconds,
            "coefficient_mode": args.coefficient_mode,
            "factor_case_split": selected_branch is not None,
            "preprocessing_seconds": preprocessing_seconds,
            "probe_first": args.probe_first,
            "probe_only": args.probe_only,
            "probe_engine": args.probe_engine if probe is not None else None,
            "probe_timeout_seconds": (
                args.probe_timeout_seconds if probe is not None else None
            ),
        },
        "factor_cover": {
            "enumerated": args.factor_branch_index is not None,
            "total_branch_count": (
                len(factor_branches)
                if args.factor_branch_index is not None
                else None
            ),
            "selected_branch_index": (
                selected_branch["branch_index"] if selected_branch else None
            ),
            "selected_choice_indices": (
                selected_branch["choice_indices"] if selected_branch else None
            ),
            "factorizations_replayed": (
                all(
                    item["replayed"]
                    for item in factor_branches[0]["factorization_certificates"]
                )
                if factor_branches
                else None
            ),
            "coverage_complete": factor_cover_complete,
            "promotion_requires_all_branches": True,
        },
        "probe": asdict(probe) if probe is not None else None,
        "certificate": asdict(certificate) if certificate is not None else None,
        "strictly_accepted": bool(
            certificate is not None
            and certificate.proved
            and certificate.replayed
            and factor_cover_complete
        ),
        "claim_scope": (
            "Accepted only when Singular returns ideal membership and the returned "
            "source-polynomial multipliers replay to the exact goal with zero residual."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "status": (
                    certificate.status
                    if certificate is not None
                    else f"probe_{probe.status}" if probe is not None else "skipped"
                ),
                "probe_member": probe.member if probe is not None else None,
                "proved": certificate.proved if certificate is not None else False,
                "replayed": (
                    certificate.replayed if certificate is not None else False
                ),
                "elapsed_seconds": (
                    certificate.elapsed_seconds if certificate is not None else 0.0
                ),
                "preprocessing_seconds": preprocessing_seconds,
                "equation_count": len(terminal["polynomials"]),
                "variable_count": len(ring_variables),
                "factor_branch_count": (
                    len(factor_branches)
                    if args.factor_branch_index is not None
                    else None
                ),
                "selected_branch_index": args.factor_branch_index,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
