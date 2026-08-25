"""Compare exact bounded membership with and without shared basis reuse."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys
import time

import sympy as sp

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.singular_lift_backend import (  # noqa: E402
    prove_ideal_membership_with_singular,
    prove_ideal_memberships_with_singular,
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=300.0)
    args = parser.parse_args()

    source = json.loads(args.source.read_text(encoding="utf-8"))
    attempts = tuple(source["attempts"])
    if not attempts:
        raise ValueError("source experiment has no prepared targets")
    certificate_degree = int(source["certificate_degree"])
    first = attempts[0]["certificate"]
    variable_names = tuple(first["variables"])
    local_symbols = {name: sp.Symbol(name) for name in variable_names}
    polynomials = tuple(
        sp.sympify(text, locals=local_symbols)
        for text in first["initial_polynomials"]
    )
    goals = tuple(
        sp.sympify(item["certificate"]["goal_polynomial"], locals=local_symbols)
        for item in attempts
    )
    variables = tuple(local_symbols[name] for name in variable_names)
    coefficient_parameters = tuple(
        sorted(
            set().union(
                *(polynomial.free_symbols for polynomial in polynomials),
                *(goal.free_symbols for goal in goals),
            )
            - set(variables),
            key=str,
        )
    )

    batch_started = time.perf_counter()
    batch = prove_ideal_memberships_with_singular(
        polynomials,
        variables,
        goals,
        timeout_seconds=args.timeout_seconds,
        max_certificate_degree=certificate_degree,
        coefficient_parameters=coefficient_parameters,
    )
    batch_seconds = time.perf_counter() - batch_started

    sequential_started = time.perf_counter()
    sequential = tuple(
        prove_ideal_membership_with_singular(
            polynomials,
            variables,
            goal,
            timeout_seconds=args.timeout_seconds,
            basis_engine="bounded_linear",
            max_certificate_degree=certificate_degree,
            coefficient_parameters=coefficient_parameters,
        )
        for goal in goals
    )
    sequential_seconds = time.perf_counter() - sequential_started

    comparisons = tuple(
        {
            "target_index": index,
            "batch_status": batch_item.status,
            "sequential_status": sequential_item.status,
            "same_status": batch_item.status == sequential_item.status,
            "same_proved": batch_item.proved == sequential_item.proved,
            "same_replayed": batch_item.replayed == sequential_item.replayed,
            "same_certificate_sha256": (
                batch_item.certificate_sha256
                == sequential_item.certificate_sha256
            ),
        }
        for index, (batch_item, sequential_item) in enumerate(
            zip(batch, sequential, strict=True)
        )
    )
    report = {
        "experiment": "bounded-membership-shared-basis-ablation",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_expected_answer": False,
        "source": args.source.resolve().as_posix(),
        "target_count": len(goals),
        "certificate_degree": certificate_degree,
        "batch_seconds": batch_seconds,
        "sequential_seconds": sequential_seconds,
        "speedup": sequential_seconds / batch_seconds if batch_seconds else None,
        "all_exact_results_match": all(
            item["same_status"]
            and item["same_proved"]
            and item["same_replayed"]
            and item["same_certificate_sha256"]
            for item in comparisons
        ),
        "comparisons": comparisons,
    }
    material = json.dumps(report, ensure_ascii=False, sort_keys=True)
    report["report_sha256"] = hashlib.sha256(material.encode()).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
