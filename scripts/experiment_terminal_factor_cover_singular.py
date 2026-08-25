"""Prove every irreducible factor branch of a terminal JGEX ideal."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
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
    probe_ideal_membership_with_singular,
    prove_ideal_membership_with_singular,
)


def _run_branch(
    branch_index: int,
    polynomial_texts: tuple[str, ...],
    variable_names: tuple[str, ...],
    coefficient_names: tuple[str, ...],
    goal_text: str,
    choice_indices: tuple[int, ...],
    timeout_seconds: float,
    monomial_order: str,
    basis_engine: str,
    probe_first: bool,
    probe_timeout_seconds: float,
    probe_engine: str,
) -> tuple[int, dict[str, object]]:
    symbols = {
        name: sp.Symbol(name) for name in (*variable_names, *coefficient_names)
    }
    polynomials = tuple(
        sp.sympify(item, locals=symbols) for item in polynomial_texts
    )
    variables = tuple(symbols[name] for name in variable_names)
    parameters = tuple(symbols[name] for name in coefficient_names)
    goal = sp.sympify(goal_text, locals=symbols)
    probe = (
        probe_ideal_membership_with_singular(
            polynomials,
            variables,
            goal,
            timeout_seconds=probe_timeout_seconds,
            monomial_order=monomial_order,
            coefficient_parameters=parameters,
            engine=probe_engine,
        )
        if probe_first
        else None
    )
    certificate = (
        prove_ideal_membership_with_singular(
            polynomials,
            variables,
            goal,
            timeout_seconds=timeout_seconds,
            monomial_order=monomial_order,
            basis_engine=basis_engine,
            coefficient_parameters=parameters,
        )
        if probe is None or (probe.status == "computed" and probe.member)
        else None
    )
    return branch_index, {
        "branch_index": branch_index,
        "choice_indices": choice_indices,
        "probe": asdict(probe) if probe is not None else None,
        "certificate": asdict(certificate) if certificate is not None else None,
        "strictly_accepted": bool(
            certificate is not None and certificate.proved and certificate.replayed
        ),
    }


def strict_factor_cover(results: dict[int, dict[str, object]], total: int) -> bool:
    return len(results) == total and all(
        item.get("strictly_accepted") is True for item in results.values()
    )


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--progress", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--monomial-order", choices=("dp", "lp"), default="dp")
    parser.add_argument(
        "--basis-engine",
        choices=("liftstd", "slimgb_lift", "module_slimgb", "direct_lift"),
        default="liftstd",
    )
    parser.add_argument("--probe-first", action="store_true")
    parser.add_argument("--probe-timeout-seconds", type=float, default=30.0)
    parser.add_argument(
        "--probe-engine", choices=("std", "slimgb"), default="slimgb"
    )
    parser.add_argument("--max-branches", type=int, default=64)
    args = parser.parse_args()

    checkpoint = args.checkpoint.resolve()
    terminal = load_terminal_checkpoint(
        checkpoint,
        include_nondegeneracy_factors=True,
    )
    branches = factor_terminal_systems(terminal)
    if len(branches) > args.max_branches:
        raise ValueError(
            f"factor cover has {len(branches)} branches; cap is {args.max_branches}"
        )
    progress = args.progress or args.output.with_suffix(".progress.json")
    run_dir = args.run_dir or args.output.parent / f"{args.output.stem}-branches"
    run_dir.mkdir(parents=True, exist_ok=True)
    results: dict[int, dict[str, object]] = {}
    for index in range(len(branches)):
        artifact = run_dir / f"branch-{index:03d}.json"
        if artifact.is_file():
            saved = json.loads(artifact.read_text(encoding="utf-8"))
            if saved.get("branch_index") == index:
                results[index] = saved
    started = time.perf_counter()

    def branch_arguments(index: int) -> tuple[object, ...]:
        return (
            index,
            tuple(sp.sstr(item) for item in branches[index]["polynomials"]),
            tuple(map(str, terminal["variables"])),
            tuple(map(str, terminal["coefficient_parameters"])),
            sp.sstr(terminal["goal"]),
            branches[index]["choice_indices"],
            args.timeout_seconds,
            args.monomial_order,
            args.basis_engine,
            args.probe_first,
            args.probe_timeout_seconds,
            args.probe_engine,
        )

    def record_result(branch_index: int, result: dict[str, object]) -> None:
        results[branch_index] = result
        branch_artifact = run_dir / f"branch-{branch_index:03d}.json"
        branch_artifact.write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        compact = {
            "completed": len(results),
            "total": len(branches),
            "accepted": sum(
                item.get("strictly_accepted") is True for item in results.values()
            ),
            "latest_branch": branch_index,
            "latest_status": (
                result.get("certificate", {}).get("status")
                if isinstance(result.get("certificate"), dict)
                else (
                    "probe_" + result["probe"].get("status", "unknown")
                    if isinstance(result.get("probe"), dict)
                    else result.get("status")
                )
            ),
            "elapsed_seconds": time.perf_counter() - started,
        }
        progress.parent.mkdir(parents=True, exist_ok=True)
        progress.write_text(
            json.dumps(compact, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        print(
            f"[{compact['completed']}/{compact['total']}] branch {branch_index}: "
            f"{compact['latest_status']}",
            flush=True,
        )

    pending_indices = tuple(
        index for index in range(len(branches)) if index not in results
    )
    if args.workers == 1:
        for index in pending_indices:
            try:
                branch_index, result = _run_branch(*branch_arguments(index))
            except Exception as error:
                branch_index = index
                result = {
                    "branch_index": index,
                    "status": "execution_error",
                    "reason": f"{type(error).__name__}: {error}",
                    "strictly_accepted": False,
                }
            record_result(branch_index, result)
    else:
        with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
            futures = {
                executor.submit(_run_branch, *branch_arguments(index)): index
                for index in pending_indices
            }
            for future in as_completed(futures):
                index = futures[future]
                try:
                    branch_index, result = future.result()
                except Exception as error:
                    branch_index = index
                    result = {
                        "branch_index": index,
                        "status": "execution_error",
                        "reason": f"{type(error).__name__}: {error}",
                        "strictly_accepted": False,
                    }
                record_result(branch_index, result)

    ordered = {str(index): results[index] for index in sorted(results)}
    accepted = strict_factor_cover(results, len(branches))
    factorization_certificates = branches[0]["factorization_certificates"]
    report = {
        "experiment": "terminal-jgex-factor-cover-singular-lift",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_expected_answer": False,
        "uses_problem_specific_solver_logic": False,
        "source_checkpoint": checkpoint.as_posix(),
        "source_checkpoint_sha256": terminal["source"]["certificate_sha256"],
        "method": {
            "factorization_domain": terminal["source"]["coefficient_domain"],
            "backend": f"Singular {args.basis_engine}",
            "basis_engine": args.basis_engine,
            "monomial_order": args.monomial_order,
            "per_branch_timeout_seconds": args.timeout_seconds,
            "probe_first": args.probe_first,
            "probe_engine": args.probe_engine if args.probe_first else None,
            "probe_timeout_seconds": (
                args.probe_timeout_seconds if args.probe_first else None
            ),
            "workers": max(1, args.workers),
        },
        "factor_cover": {
            "branch_count": len(branches),
            "factorization_certificates": factorization_certificates,
            "factorizations_replayed": all(
                item["replayed"] for item in factorization_certificates
            ),
            "coverage_theorem": branches[0]["cover_theorem"],
            "coverage_complete": len(results) == len(branches),
        },
        "summary": {
            "branches": len(branches),
            "completed": len(results),
            "proved_and_replayed": sum(
                item.get("strictly_accepted") is True for item in results.values()
            ),
            "timeouts": sum(
                (
                    isinstance(item.get("certificate"), dict)
                    and item["certificate"].get("status") == "timeout"
                )
                or (
                    isinstance(item.get("probe"), dict)
                    and item["probe"].get("status") == "timeout"
                )
                for item in results.values()
            ),
            "probe_nonmembers": sum(
                isinstance(item.get("probe"), dict)
                and item["probe"].get("status") == "computed"
                and item["probe"].get("member") is False
                for item in results.values()
            ),
            "execution_errors": sum(
                item.get("status") == "execution_error" for item in results.values()
            ),
            "false_acceptances": sum(
                isinstance(item.get("certificate"), dict)
                and item["certificate"].get("proved") is True
                and item["certificate"].get("replayed") is not True
                for item in results.values()
            ),
            "strictly_accepted": accepted,
            "wall_seconds": time.perf_counter() - started,
        },
        "branches": ordered,
        "claim_scope": (
            "The root theorem is accepted only when exact factorization replays, "
            "the finite factor cover is complete, and every branch has a Singular "
            "source-polynomial lift whose residual replays to zero."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
