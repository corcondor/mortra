"""Evaluate the unchanged exact-chart registry outside a certified union."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from worker.backend.exact_geometry_chart_portfolio import (  # noqa: E402
    certify_jgex_with_exact_chart_portfolio,
    registered_exact_chart_contracts,
)
from worker.backend.mortra_research_dialogue import payload_sha256  # noqa: E402


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _dataset(path: Path) -> dict[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) % 2:
        raise ValueError("dataset must contain name/source line pairs")
    return {lines[index]: lines[index + 1] for index in range(0, len(lines), 2)}


def _primary_union(payload: dict[str, Any]) -> set[str]:
    sets = payload.get("sets", {})
    names = sets.get("primary_union", sets.get("primary_certified_solved", ()))
    return set(map(str, names))


def _problem_names(path: Path | None) -> set[str]:
    if path is None:
        return set()
    return {
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    }


def audit_transfer(
    *,
    excluded_union_path: Path,
    dataset_path: Path,
    natural_dataset_path: Path,
    development_problems_path: Path | None = None,
    limit: int | None = None,
    progress_every: int = 25,
) -> dict[str, object]:
    """Run the registry unchanged on the deterministic complement cohort."""

    union_payload = json.loads(excluded_union_path.read_text(encoding="utf-8"))
    sources = _dataset(dataset_path)
    natural_sources = json.loads(
        natural_dataset_path.read_text(encoding="utf-8")
    )
    excluded = _primary_union(union_payload)
    development_problems = _problem_names(development_problems_path)
    cohort = sorted(set(sources) - excluded - development_problems)
    if limit is not None:
        cohort = cohort[:limit]

    started = time.perf_counter()
    results: dict[str, dict[str, object]] = {}
    chart_histogram: Counter[str] = Counter()
    for index, name in enumerate(cohort, start=1):
        result = certify_jgex_with_exact_chart_portfolio(
            sources[name],
            include_diagram=False,
            natural_statement=natural_sources.get(name),
        )
        selected = result.selected
        repair_only = bool(
            selected
            and selected.application.get("formalization_repair_required", False)
        )
        strict_match = bool(result.solved and not repair_only and not result.ambiguous)
        near_attempts = sorted(
            (
                attempt.to_dict()
                for attempt in result.attempts
                if not attempt.replayed
                and attempt.error != "structural_prefilter_miss"
            ),
            key=lambda attempt: (
                -len(attempt["matched_constructions"]),
                -int(attempt["role_count"]),
                str(attempt["chart_id"]),
            ),
        )
        if strict_match and selected is not None:
            chart_histogram[selected.chart_id] += 1
        results[name] = {
            "strict_match": strict_match,
            "raw_chart_solved": result.solved,
            "proved_after_quantifier_repair_only": repair_only,
            "ambiguous": result.ambiguous,
            "chart_id": selected.chart_id if selected is not None else None,
            "certificate_sha256": (
                selected.chart_certificate_sha256 if selected is not None else None
            ),
            "source_sha256": result.source_sha256,
            "natural_statement_sha256": result.natural_statement_sha256,
            "near_attempts": near_attempts,
        }
        if progress_every and index % progress_every == 0:
            print(
                f"evaluated={index}/{len(cohort)} strict_matches="
                f"{sum(bool(item['strict_match']) for item in results.values())}",
                file=sys.stderr,
                flush=True,
            )

    elapsed = time.perf_counter() - started
    strict_matches = sum(bool(item["strict_match"]) for item in results.values())
    raw_solves = sum(bool(item["raw_chart_solved"]) for item in results.values())
    repair_only = sum(
        bool(item["proved_after_quantifier_repair_only"])
        for item in results.values()
    )
    ambiguous = sum(bool(item["ambiguous"]) for item in results.values())
    problems_with_near_attempts = sum(
        bool(item["near_attempts"]) for item in results.values()
    )
    return {
        "experiment": "exact_chart_unchanged_complement_transfer_audit",
        "protocol": {
            "uses_external_llm": False,
            "uses_expected_answer": False,
            "uses_problem_id_in_solver": False,
            "cohort_rule": (
                "sorted(dataset problem names minus excluded primary union "
                "minus observed chart-development problems)"
            ),
            "excluded_union": excluded_union_path.as_posix(),
            "excluded_union_sha256": _sha256(excluded_union_path),
            "dataset": dataset_path.as_posix(),
            "dataset_sha256": _sha256(dataset_path),
            "natural_dataset": natural_dataset_path.as_posix(),
            "natural_dataset_sha256": _sha256(natural_dataset_path),
            "development_problems": (
                development_problems_path.as_posix()
                if development_problems_path is not None
                else None
            ),
            "development_problems_sha256": (
                _sha256(development_problems_path)
                if development_problems_path is not None
                else None
            ),
            "registered_chart_contracts_sha256": payload_sha256(
                registered_exact_chart_contracts()
            ),
            "limit": limit,
        },
        "summary": {
            "dataset_total": len(sources),
            "excluded_certified": len(set(sources) & excluded),
            "excluded_development": len(set(sources) & development_problems),
            "evaluated": len(cohort),
            "strict_matches": strict_matches,
            "raw_chart_solves": raw_solves,
            "proved_after_quantifier_repair_only": repair_only,
            "ambiguous": ambiguous,
            "problems_with_near_attempts": problems_with_near_attempts,
            "strict_transfer_rate": (
                strict_matches / len(cohort) if cohort else 0.0
            ),
            "elapsed_seconds": elapsed,
            "chart_histogram": dict(sorted(chart_histogram.items())),
        },
        "sets": {
            "excluded_development": sorted(set(sources) & development_problems),
            "strict_matches": sorted(
                name for name, item in results.items() if item["strict_match"]
            ),
            "repair_only": sorted(
                name
                for name, item in results.items()
                if item["proved_after_quantifier_repair_only"]
            ),
            "ambiguous": sorted(
                name for name, item in results.items() if item["ambiguous"]
            ),
        },
        "results": results,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--excluded-union", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--natural-dataset", type=Path, required=True)
    parser.add_argument("--development-problems", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--progress-every", type=int, default=25)
    args = parser.parse_args()
    report = audit_transfer(
        excluded_union_path=args.excluded_union,
        dataset_path=args.dataset,
        natural_dataset_path=args.natural_dataset,
        development_problems_path=args.development_problems,
        limit=args.limit,
        progress_every=args.progress_every,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0 if not report["summary"]["ambiguous"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
