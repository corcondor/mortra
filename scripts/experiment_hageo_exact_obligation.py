"""Run the generic exact JGEX lowering on one HAGeo problem.

This is an independent proof agent, not another auxiliary-point scheduler.
It hides dataset auxiliary clauses, lowers the typed construction semantics to
polynomial constraints, and admits a result only after exact replay.
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
import hashlib
import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from newclid.jgex.formulation import JGEXFormulation, jgex_formulation_from_txt_file

from scripts.experiment_jgex_exact_unsolved_set import _run_isolated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--problem-name", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--timeout-seconds", type=float, default=600.0)
    parser.add_argument(
        "--representation",
        choices=(
            "explicit",
            "relational",
            "local_relational",
            "goal_local_relational",
        ),
        default="explicit",
    )
    parser.add_argument("--max-saturation-rounds", type=int, default=1)
    args = parser.parse_args()

    dataset = args.dataset.resolve()
    formulations = jgex_formulation_from_txt_file(dataset)
    formulation = formulations[args.problem_name]
    setup_only = JGEXFormulation(
        name=formulation.name,
        setup_clauses=formulation.setup_clauses,
        auxiliary_clauses=(),
        goals=formulation.goals,
    )
    result = _run_isolated(
        str(setup_only),
        args.timeout_seconds,
        representation=args.representation,
        max_saturation_rounds=args.max_saturation_rounds,
    )
    if result.get("status") == "timeout":
        result["status"] = "right_censored_timeout"
    certificate = result.get("certificate") or {}
    native_confirmed = bool(
        result.get("status") == "proved" and certificate.get("exact_replay")
    )
    report = {
        "experiment": "hageo_generic_exact_obligation",
        "created_at": datetime.now(UTC).isoformat(),
        "protocol": {
            "uses_external_llm": False,
            "uses_problem_specific_solver_logic": False,
            "dataset_auxiliary_clauses_hidden": True,
            "truth_plane": "exact polynomial certificate replay only",
            "timeout_semantics": "right-censored unknown",
            "representation": args.representation,
            "max_saturation_rounds": args.max_saturation_rounds,
            "dataset_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
        },
        "problem": args.problem_name,
        "status": result.get("status"),
        "solved": native_confirmed,
        "native_confirmed": native_confirmed,
        "result": result,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "problem": args.problem_name,
        "status": report["status"],
        "solved": native_confirmed,
        "output": str(args.output),
    }, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
