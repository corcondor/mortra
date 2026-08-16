"""証明DAG付きChordal消去とSingular lift実験の固定成果物を検査する。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    args = parser.parse_args()
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    root = args.manifest.resolve().parents[1]
    reports = {
        relative: json.loads((root / relative).read_text(encoding="utf-8"))
        for relative in manifest["reference_artifacts"]
    }
    checks = {
        f"{relative}:sha256": _sha256(root / relative) == expected
        for relative, expected in manifest["reference_artifacts"].items()
    }
    for relative, report in reports.items():
        checks[f"{relative}:no_llm"] = report["uses_llm"] is False
        checks[f"{relative}:no_problem_specific_solver"] = (
            report["uses_problem_specific_solver_logic"] is False
        )

    singular_relative = "data/singular-lift-fixed4-2026-08-16.json"
    singular = reports[singular_relative]
    checks.update(
        {
            "singular:fixed4": singular["fixed_problem_names"]
            == ["2008_p6", "2010_p2", "2020_p1", "2021_p3"],
            "singular:summary": {
                key: singular["summary"][key]
                for key in (
                    "completed",
                    "timeouts",
                    "first_stage_replayed",
                    "end_to_end_goals_replayed",
                    "false_acceptances",
                )
            }
            == {
                "completed": 0,
                "timeouts": 4,
                "first_stage_replayed": 4,
                "end_to_end_goals_replayed": 0,
                "false_acceptances": 0,
            },
            "singular:all_first_stages_replayed": all(
                item["first_stage_replayed"] is True
                for item in singular["results"].values()
            ),
            "singular:timeouts_are_not_proofs": all(
                item["status"] == "timeout"
                and item["singular_certificate"]["proved"] is False
                and item["singular_certificate"]["replayed"] is False
                for item in singular["results"].values()
            ),
            "singular:no_nonlinear_resultant_prepass": singular["method"][
                "nonlinear_resultant_before_singular"
            ]
            is False,
        }
    )

    for relative in (
        "data/hybrid-polynomial-stalk-smoke-2020-p1-2026-08-16.json",
        "data/hybrid-polynomial-stalk-goal-directed-smoke-2020-p1-2026-08-16.json",
        "data/hybrid-polynomial-stalk-linear-first-smoke-2020-p1-2026-08-16.json",
    ):
        report = reports[relative]
        checks[f"{relative}:timeout_recorded"] = report["summary"]["timeouts"] == 1
        checks[f"{relative}:no_false_goal_claim"] = (
            report["summary"]["end_to_end_goals_replayed"] == 0
            and report["summary"]["chordal_goal_certificates"] == 0
        )
    linear = reports[
        "data/hybrid-polynomial-stalk-linear-first-smoke-2020-p1-2026-08-16.json"
    ]
    checks["linear_first:no_nonlinear_resultant"] = (
        linear["budgets"]["resultant_max_degree"] == 1
    )
    checks["linear_first:bounded_messages"] = (
        linear["budgets"]["max_incomplete_messages"] == 2
    )

    print(json.dumps(checks, ensure_ascii=False, indent=2))
    if not all(checks.values()):
        return 1
    print("Chordal/lift artifacts verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
