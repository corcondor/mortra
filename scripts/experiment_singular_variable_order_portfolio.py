"""Compare exact Singular membership probes over every variable permutation."""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict
from datetime import UTC, datetime
from itertools import permutations
import json
from pathlib import Path
import sys

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.singular_lift_backend import (  # noqa: E402
    probe_ideal_membership_with_singular,
)


def _greedy_min_fill_order(
    variable_names: tuple[str, ...],
    supports: tuple[frozenset[str], ...],
    goal_support: frozenset[str],
    *,
    goal_bias: int = 0,
) -> tuple[str, ...]:
    adjacency = {name: set() for name in variable_names}
    occurrences = {name: 0 for name in variable_names}
    for support in supports:
        active = tuple(name for name in variable_names if name in support)
        for name in active:
            occurrences[name] += 1
            adjacency[name].update(item for item in active if item != name)

    remaining = set(variable_names)
    order: list[str] = []
    original_index = {name: index for index, name in enumerate(variable_names)}
    while remaining:
        def score(name: str) -> tuple[int, int, int, int, int]:
            neighbors = adjacency[name] & remaining
            missing_edges = sum(
                other not in adjacency[first]
                for index, first in enumerate(sorted(neighbors))
                for other in sorted(neighbors)[index + 1 :]
            )
            goal_term = goal_bias if name in goal_support else 0
            return (
                missing_edges,
                len(neighbors),
                goal_term,
                occurrences[name],
                original_index[name],
            )

        selected = min(remaining, key=score)
        neighbors = tuple(adjacency[selected] & remaining)
        for first in neighbors:
            adjacency[first].update(item for item in neighbors if item != first)
        remaining.remove(selected)
        order.append(selected)
    return tuple(order)


def structural_variable_orders(
    variable_names: tuple[str, ...],
    polynomial_texts: tuple[str, ...],
    goal_text: str,
    *,
    max_orders: int = 16,
) -> tuple[tuple[str, ...], ...]:
    """Build a bounded, problem-agnostic elimination-order portfolio.

    The ordering uses only variable incidence, occurrence frequency and goal
    support.  It never inspects a problem identifier or an expected answer.
    """

    if max_orders < 1:
        raise ValueError("max_orders must be positive")
    symbols = {name: sp.Symbol(name) for name in variable_names}
    expressions = tuple(
        sp.sympify(text, locals=symbols) for text in polynomial_texts
    )
    goal = sp.sympify(goal_text, locals=symbols)
    supports = tuple(
        frozenset(str(symbol) for symbol in expression.free_symbols)
        & frozenset(variable_names)
        for expression in expressions
    )
    goal_support = (
        frozenset(str(symbol) for symbol in goal.free_symbols)
        & frozenset(variable_names)
    )
    occurrences = {
        name: sum(name in support for support in supports)
        for name in variable_names
    }
    graph_degree = {
        name: len(
            set().union(
                *(set(support) - {name} for support in supports if name in support)
            )
        )
        for name in variable_names
    }
    original_index = {name: index for index, name in enumerate(variable_names)}

    orders: list[tuple[str, ...]] = []

    def add(order: tuple[str, ...]) -> None:
        if order not in orders and set(order) == set(variable_names):
            orders.append(order)

    add(variable_names)
    add(tuple(reversed(variable_names)))
    for primary in (occurrences, graph_degree):
        ascending = tuple(
            sorted(variable_names, key=lambda name: (primary[name], original_index[name]))
        )
        add(ascending)
        add(tuple(reversed(ascending)))
    for goal_first in (True, False):
        ordered = tuple(
            sorted(
                variable_names,
                key=lambda name: (
                    (name not in goal_support) if goal_first else (name in goal_support),
                    occurrences[name],
                    graph_degree[name],
                    original_index[name],
                ),
            )
        )
        add(ordered)
        add(tuple(reversed(ordered)))
    for goal_bias in (-1, 0, 1):
        min_fill = _greedy_min_fill_order(
            variable_names,
            supports,
            goal_support,
            goal_bias=goal_bias,
        )
        add(min_fill)
        add(tuple(reversed(min_fill)))
    return tuple(orders[:max_orders])


def _probe(
    variable_order: tuple[str, ...],
    parameter_names: tuple[str, ...],
    polynomial_texts: tuple[str, ...],
    goal_text: str,
    timeout_seconds: float,
    monomial_order: str,
    engine: str,
) -> dict[str, object]:
    symbols = {
        name: sp.Symbol(name) for name in (*variable_order, *parameter_names)
    }
    result = probe_ideal_membership_with_singular(
        tuple(sp.sympify(item, locals=symbols) for item in polynomial_texts),
        tuple(symbols[name] for name in variable_order),
        sp.sympify(goal_text, locals=symbols),
        timeout_seconds=timeout_seconds,
        monomial_order=monomial_order,
        coefficient_parameters=tuple(symbols[name] for name in parameter_names),
        engine=engine,
    )
    return asdict(result)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=30.0)
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--monomial-order", choices=("dp", "lp"), default="lp")
    parser.add_argument("--engine", choices=("std", "slimgb"), default="slimgb")
    parser.add_argument(
        "--order-strategy",
        choices=("exhaustive", "structural"),
        default="exhaustive",
    )
    parser.add_argument("--max-orders", type=int, default=16)
    args = parser.parse_args()

    source_report = json.loads(args.source_report.read_text(encoding="utf-8"))
    singular = source_report["singular_certificate"]
    checkpoint_path = Path(source_report["source_checkpoint"])
    checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
    variable_names = tuple(singular["variables"])
    parameter_names = tuple(checkpoint.get("coefficient_parameters", ()))
    if args.order_strategy == "exhaustive":
        orders = tuple(permutations(variable_names))
    else:
        orders = structural_variable_orders(
            variable_names,
            tuple(singular["initial_polynomials"]),
            singular["goal_polynomial"],
            max_orders=args.max_orders,
        )
    results: list[dict[str, object]] = []
    with ProcessPoolExecutor(max_workers=max(1, args.workers)) as executor:
        futures = {
            executor.submit(
                _probe,
                order,
                parameter_names,
                tuple(singular["initial_polynomials"]),
                singular["goal_polynomial"],
                args.timeout_seconds,
                args.monomial_order,
                args.engine,
            ): order
            for order in orders
        }
        for future in as_completed(futures):
            order = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {
                    "variables": order,
                    "status": "execution_error",
                    "member": False,
                    "reason": f"{type(error).__name__}: {error}",
                }
            results.append(result)
            print(
                f"[{len(results)}/{len(orders)}] {order}: "
                f"{result.get('status')} member={result.get('member')}",
                flush=True,
            )

    results.sort(key=lambda item: tuple(item["variables"]))
    report = {
        "experiment": "singular-variable-order-membership-portfolio",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_expected_answer": False,
        "uses_problem_specific_solver_logic": False,
        "source_report": args.source_report.resolve().as_posix(),
        "method": {
            "engine": args.engine,
            "monomial_order": args.monomial_order,
            "per_order_timeout_seconds": args.timeout_seconds,
            "workers": max(1, args.workers),
            "permutation_count": len(orders),
            "order_strategy": args.order_strategy,
        },
        "summary": {
            "members": sum(item.get("member") is True for item in results),
            "computed_nonmembers": sum(
                item.get("status") == "computed" and item.get("member") is False
                for item in results
            ),
            "timeouts": sum(item.get("status") == "timeout" for item in results),
            "errors": sum(
                str(item.get("status", "")).startswith("execution_error")
                for item in results
            ),
        },
        "results": results,
        "claim_scope": (
            "A zero remainder is an exact ideal-membership probe. It is not "
            "promoted as a benchmark proof until source multipliers are emitted "
            "and replayed."
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
