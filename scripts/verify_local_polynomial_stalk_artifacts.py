"""Verify local polynomial-stalk artifacts and their exact certificates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _sha256(path: Path) -> str:
    payload = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha256(payload).hexdigest()


def _certificate_checks(report: dict) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for problem, case in report["results"].items():
        for width, run in case["local_widths"].items():
            key = f"{problem}:width={width}"
            if run["status"] != "completed":
                checks[f"{key}:timeout_recorded"] = run["status"] == "timeout"
                continue
            elimination = run["result"]["local_elimination"]
            coordination = run["coordination"]
            witnesses = [
                witness
                for step in elimination["steps"]
                for witness in step["ideal_membership_witnesses"]
            ]
            outputs = [
                output
                for step in elimination["steps"]
                for output in step["output_polynomials"]
            ]
            checks[f"{key}:exact_replay"] = elimination["exact_replay"] is True
            checks[f"{key}:witness_count"] = len(witnesses) == len(outputs)
            checks[f"{key}:zero_residuals"] = all(
                item["replay_residual"] == "0" for item in witnesses
            )
            checks[f"{key}:all_goals_replayed"] = (
                coordination["derived_goal_count"]
                == coordination["solved_goal_count"]
                == coordination["replayed_goal_count"]
            )
            checks[f"{key}:no_rejected_certificate"] = (
                coordination["rejected_certificate_count"] == 0
            )
            checks[f"{key}:all_agents_active"] = (
                coordination["local_agent_count"] == coordination["active_agent_count"]
            )
            checks[f"{key}:no_false_global_claim"] = (
                coordination["external_goal_replayed"] is False
            )
    return checks


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
    artifact_checks = {
        relative: _sha256(root / relative) == expected
        for relative, expected in manifest["reference_artifacts"].items()
    }
    protocol_checks = {
        f"{relative}:no_llm": report["uses_llm"] is False
        for relative, report in reports.items()
    }
    protocol_checks.update(
        {
            f"{relative}:no_problem_specific_solver": (
                report["uses_problem_specific_solver_logic"] is False
            )
            for relative, report in reports.items()
        }
    )
    certificate_checks = {
        f"{relative}:{key}": value
        for relative, report in reports.items()
        for key, value in _certificate_checks(report).items()
    }

    width_path = "data/polynomial-stalk-width-ablation-fixed4-2026-08-16.json"
    width_report = reports[width_path]
    expected = manifest["semantic_acceptance"]
    semantic_checks = {
        "fixed_problem_names": (
            width_report["fixed_problem_names"] == expected["fixed_problem_names"]
        ),
        "explicit_inspection_completed": (
            width_report["summary"]["explicit_inspection_completed"]
            == expected["explicit_inspection_completed"]
        ),
        "relational_inspection_completed": (
            width_report["summary"]["relational_inspection_completed"]
            == expected["relational_inspection_completed"]
        ),
        "term_width_32": (
            {
                key: width_report["summary"]["widths"]["32"][key]
                for key in expected["term_width_32"]
            }
            == expected["term_width_32"]
        ),
    }
    for cap in ("4", "8", "12"):
        relative = f"data/polynomial-stalk-separator{cap}-fixed4-2026-08-16.json"
        summary = reports[relative]["summary"]["widths"]["32"]
        semantic_checks[f"separator_cap_{cap}"] = all(
            summary[key] == value
            for key, value in expected["separator_caps"][cap].items()
        )
    min_fill_path = "data/polynomial-stalk-min-fill-separator12-fixed4-2026-08-16.json"
    min_fill_report = reports[min_fill_path]
    min_fill_summary = min_fill_report["summary"]["widths"]["32"]
    min_fill_expected = expected["min_fill_separator_12"]
    semantic_checks["min_fill_separator_12"] = min_fill_report["budgets"][
        "ordering_strategy"
    ] == min_fill_expected["ordering_strategy"] and all(
        min_fill_summary[key] == value
        for key, value in min_fill_expected.items()
        if key != "ordering_strategy"
    )

    all_checks = {
        **artifact_checks,
        **protocol_checks,
        **certificate_checks,
        **semantic_checks,
    }
    print(json.dumps(all_checks, ensure_ascii=False, indent=2))
    if not all(all_checks.values()):
        return 1
    print("Local polynomial-stalk artifacts verified.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
