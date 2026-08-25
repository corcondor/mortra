"""Probe several frozen terminal ideals in one initialized Python process."""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import UTC, datetime
import json
from pathlib import Path
import sys
import time


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.experiment_terminal_checkpoint_singular import (  # noqa: E402
    load_terminal_checkpoint,
)
from worker.backend.singular_lift_backend import (  # noqa: E402
    probe_ideal_membership_with_singular,
)


def parse_case(value: str) -> tuple[str, Path]:
    name, separator, path = value.partition("=")
    if not separator or not name or not path:
        raise argparse.ArgumentTypeError("case must be PROBLEM=CHECKPOINT")
    return name, Path(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--case", action="append", type=parse_case, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=60.0)
    parser.add_argument("--engine", choices=("std", "slimgb"), default="slimgb")
    parser.add_argument("--monomial-order", choices=("dp", "lp"), default="dp")
    args = parser.parse_args()

    results: dict[str, object] = {}
    started = time.perf_counter()
    for problem, checkpoint_path in args.case:
        terminal = load_terminal_checkpoint(checkpoint_path)
        probe = probe_ideal_membership_with_singular(
            terminal["polynomials"],
            terminal["variables"],
            terminal["goal"],
            timeout_seconds=args.timeout_seconds,
            monomial_order=args.monomial_order,
            coefficient_parameters=terminal["coefficient_parameters"],
            engine=args.engine,
        )
        results[problem] = {
            "checkpoint": checkpoint_path.resolve().as_posix(),
            "checkpoint_sha256": terminal["source"]["certificate_sha256"],
            "equation_count": len(terminal["polynomials"]),
            "variable_count": len(terminal["variables"]),
            "coefficient_parameter_count": len(
                terminal["coefficient_parameters"]
            ),
            "probe": asdict(probe),
        }
        print(
            f"{problem}: {probe.status}, member={probe.member}, "
            f"elapsed={probe.elapsed_seconds:.3f}s",
            flush=True,
        )

    report = {
        "experiment": "frozen-terminal-ideal-membership-probe-batch",
        "generated_at": datetime.now(UTC).isoformat(),
        "uses_llm": False,
        "uses_expected_answer": False,
        "uses_problem_specific_solver_logic": False,
        "method": {
            "backend": f"Singular {args.engine}",
            "monomial_order": args.monomial_order,
            "per_problem_timeout_seconds": args.timeout_seconds,
        },
        "summary": {
            "problems": len(results),
            "computed_members": sum(
                item["probe"]["status"] == "computed"
                and item["probe"]["member"] is True
                for item in results.values()
            ),
            "computed_nonmembers": sum(
                item["probe"]["status"] == "computed"
                and item["probe"]["member"] is False
                for item in results.values()
            ),
            "timeouts": sum(
                item["probe"]["status"] == "timeout"
                for item in results.values()
            ),
            "wall_seconds": time.perf_counter() - started,
        },
        "results": results,
        "claim_scope": (
            "A computed nonmember only rejects ideal membership in the saved "
            "terminal system; it does not refute the geometry theorem."
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
