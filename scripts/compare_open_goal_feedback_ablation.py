"""Compare two fixed-budget open-goal construction feedback reports."""

from __future__ import annotations

import argparse
import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def total_paths(result: dict[str, Any]) -> int:
    return sum(int(stage.get("evaluated_paths", 0)) for stage in result.get("stages", ()))


def compare_reports(
    structural: dict[str, Any], random: dict[str, Any]
) -> dict[str, Any]:
    names = sorted(set(structural["results"]) & set(random["results"]))
    cases = []
    for name in names:
        left = structural["results"][name]
        right = random["results"][name]
        cases.append(
            {
                "problem_name": name,
                "structural_proved": left.get("status") == "proved",
                "random_proved": right.get("status") == "proved",
                "structural_paths": total_paths(left),
                "random_paths": total_paths(right),
            }
        )
    structural_proved = sum(case["structural_proved"] for case in cases)
    random_proved = sum(case["random_proved"] for case in cases)
    structural_paths = sum(case["structural_paths"] for case in cases)
    random_paths = sum(case["random_paths"] for case in cases)
    return {
        "paired_problem_count": len(cases),
        "structural_proved": structural_proved,
        "random_proved": random_proved,
        "structural_total_paths": structural_paths,
        "random_total_paths": random_paths,
        "path_ratio_random_over_structural": (
            random_paths / structural_paths if structural_paths else None
        ),
        "cases": cases,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--structural", type=Path, required=True)
    parser.add_argument("--random", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    structural = json.loads(args.structural.read_text(encoding="utf-8"))
    random = json.loads(args.random.read_text(encoding="utf-8"))
    comparison = compare_reports(structural, random)
    report = {
        "experiment": "open-goal-feedback-paired-ranking-ablation",
        "generated_at": datetime.now(UTC).isoformat(),
        "protocol": {
            "same_candidate_grammar": True,
            "same_search_budget": True,
            "same_seed": True,
            "only_candidate_ranking_changed": True,
            "uses_external_llm": False,
        },
        "summary": {key: value for key, value in comparison.items() if key != "cases"},
        "cases": comparison["cases"],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
