"""Adapter for the official AlphaGeometry2 DDAR symbolic engine.

MathOS supplies an AG2-formalized problem.  The base path saturates its
predicate database.  The optional LLM-free path searches a finite typed
construction grammar and accepts a construction only when DDAR proves the
original goal.  Neither path receives a worked solution or target answer.
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


def solve_with_auxiliary_search(
    problem_text: str,
    *,
    directory: Path,
    max_depth: int = 2,
    beam_width: int = 8,
    max_attempts: int = 96,
    ensemble: bool = False,
) -> dict[str, Any]:
    AGProblem, DDAR = load_engine(directory)
    problem = AGProblem.parse(problem_text)
    if ensemble:
        from alphageometry2_ensemble_search import ensemble_search

        return ensemble_search(
            problem,
            AGProblem=AGProblem,
            DDAR=DDAR,
            max_depth=max_depth,
            beam_width=beam_width,
            max_attempts=max_attempts,
        )
    from alphageometry2_auxiliary_search import search_auxiliary_constructions

    return search_auxiliary_constructions(
        problem,
        AGProblem=AGProblem,
        DDAR=DDAR,
        max_depth=max_depth,
        beam_width=beam_width,
        max_attempts=max_attempts,
    )


def solve_natural_problem(
    problem_text: str,
    *,
    directory: Path,
    max_depth: int = 4,
    beam_width: int = 16,
    max_attempts: int = 384,
    max_restarts: int = 20,
) -> dict[str, Any]:
    from geometry_natural_formalizer import formalize_geometry_text

    formalization = formalize_geometry_text(problem_text, max_restarts=max_restarts)
    if formalization.status != "formalized" or formalization.formal_problem is None:
        return {
            "status": "unformalized",
            "proved": False,
            "backend": "MathOS typed geometry formalizer",
            "formalization": formalization.to_dict(),
            "uses_language_model": False,
        }
    try:
        result = solve_with_auxiliary_search(
            formalization.formal_problem,
            directory=directory,
            max_depth=max_depth,
            beam_width=beam_width,
            max_attempts=max_attempts,
            ensemble=True,
        )
    except (AssertionError, KeyError, ValueError, ZeroDivisionError) as error:
        formalization.status = "backend_rejected"
        formalization.unresolved_relations.append(
            f"DDAR rejected the numerical realization: {type(error).__name__}: {error}"
        )
        return {
            "status": "unformalized",
            "proved": False,
            "backend": "MathOS typed geometry formalizer",
            "formalization": formalization.to_dict(),
            "uses_language_model": False,
        }
    result["formalization"] = formalization.to_dict()
    result["input_mode"] = "natural_or_tex"
    return result


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
    parser.add_argument("--auto-aux", action="store_true")
    parser.add_argument("--ensemble", action="store_true")
    parser.add_argument("--input-format", choices=("auto", "formal", "natural"), default="auto")
    parser.add_argument("--max-depth", type=int, default=2)
    parser.add_argument("--beam-width", type=int, default=8)
    parser.add_argument("--max-attempts", type=int, default=96)
    parser.add_argument("--max-restarts", type=int, default=20)
    args = parser.parse_args()
    directory = engine_directory(args.engine_dir)
    if args.official_suite:
        result = run_official_suite(directory=directory, limit=args.limit)
    else:
        payload = json.load(sys.stdin)
        problem_text = str(payload["problem"])
        input_format = args.input_format
        if input_format == "auto":
            input_format = "formal" if "@" in problem_text and "?" in problem_text else "natural"
        if input_format == "natural":
            result = solve_natural_problem(
                problem_text,
                directory=directory,
                max_depth=args.max_depth,
                beam_width=args.beam_width,
                max_attempts=args.max_attempts,
                max_restarts=args.max_restarts,
            )
        elif args.auto_aux:
            result = solve_with_auxiliary_search(
                problem_text,
                directory=directory,
                max_depth=args.max_depth,
                beam_width=args.beam_width,
                max_attempts=args.max_attempts,
                ensemble=args.ensemble,
            )
        else:
            result = solve_formal_problem(problem_text, directory=directory)
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
