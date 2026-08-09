"""Adapter for the official AlphaGeometry2 DDAR symbolic engine.

MathOS supplies only an AG2-formalized problem. The adapter does not use a
worked solution or target answer: DDAR saturates its predicate database and
checks whether the requested predicate is derivable.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib
import io
import json
import os
import sys
from pathlib import Path
from typing import Any


def engine_directory(explicit: str | None = None) -> Path:
    value = explicit or os.environ.get("MATHOS_AG2_DIR")
    if not value:
        raise FileNotFoundError("set MATHOS_AG2_DIR to the official google-deepmind/alphageometry2 checkout")
    directory = Path(value).expanduser().resolve()
    for name in ("ddar.py", "elimination.py", "parse.py"):
        if not (directory / name).exists():
            raise FileNotFoundError(f"invalid AlphaGeometry2 checkout: missing {name}")
    return directory


def load_engine(directory: Path):
    source = str(directory)
    if source not in sys.path:
        sys.path.insert(0, source)
    parse_module = importlib.import_module("parse")
    ddar_module = importlib.import_module("ddar")
    return parse_module.AGProblem, ddar_module.DDAR


def solve_formal_problem(problem_text: str, *, directory: Path) -> dict[str, Any]:
    AGProblem, DDAR = load_engine(directory)
    problem = AGProblem.parse(problem_text)
    engine = DDAR(problem.points)
    for predicate in problem.preds:
        engine.force_pred(predicate)
    trace = io.StringIO()
    with contextlib.redirect_stdout(trace):
        engine.deduction_closure()
    proved = bool(engine.check_pred(problem.goal))
    return {
        "status": "proved" if proved else "unproved",
        "proved": proved,
        "goal": str(problem.goal),
        "point_count": len(problem.points),
        "premise_count": len(problem.preds),
        "closure_rounds": trace.getvalue().count("."),
        "backend": "google-deepmind/alphageometry2-DDAR",
    }


def run_official_suite(*, directory: Path, limit: int | None = None) -> dict[str, Any]:
    source = str(directory)
    if source not in sys.path:
        sys.path.insert(0, source)
    official_test = importlib.import_module("test")
    groups = [
        ("without_auxiliary_points", official_test.problems_without_aux),
        ("with_manually_supplied_auxiliary_points", official_test.problems_with_aux),
    ]
    records: list[dict[str, Any]] = []
    for group, problems in groups:
        for name, problem in problems.items():
            if limit is not None and len(records) >= limit:
                break
            records.append({"group": group, "name": name, **solve_formal_problem(problem, directory=directory)})
        if limit is not None and len(records) >= limit:
            break
    proved = sum(record["proved"] for record in records)
    return {
        "total": len(records),
        "proved": proved,
        "proof_rate": proved / len(records) if records else 0.0,
        "records": records,
        "source_revision_expected": "google-deepmind/alphageometry2",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--engine-dir")
    parser.add_argument("--official-suite", action="store_true")
    parser.add_argument("--limit", type=int)
    args = parser.parse_args()
    directory = engine_directory(args.engine_dir)
    if args.official_suite:
        result = run_official_suite(directory=directory, limit=args.limit)
    else:
        payload = json.load(sys.stdin)
        result = solve_formal_problem(str(payload["problem"]), directory=directory)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
