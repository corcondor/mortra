from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.benchmark_hageo409_auxiliary import require_same_report_cohort
from scripts.rebuild_hageo_auxiliary_cohort import rebuild_report


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_rebuilds_artifacts_and_preserves_censored_fallback(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    problems = tmp_path / "problems.txt"
    run_dir = tmp_path / "runs"
    fallback = tmp_path / "fallback.json"
    _write(
        baseline,
        {
            "summary": {"solved": 1, "total": 3},
            "results": {
                "base": {"status": "solved"},
                "new": {"status": "unsolved"},
                "slow": {"status": "unsolved"},
            },
        },
    )
    problems.write_text("new\nslow\n", encoding="utf-8")
    _write(
        run_dir / "new.json",
        {
            "problem_name": "new",
            "protocol": {"uses_external_llm": False},
            "solved": True,
            "solved_path": ["midpoint(a,b)"],
            "evaluated_paths": 2,
            "right_censored_count": 0,
            "candidate_incidence": {
                "checked_candidates": 4,
                "heuristic_candidates": 1,
            },
            "records": [{"elapsed_seconds": 2.5}],
            "confirmation": {
                "solved": True,
                "input_sha256": "a",
                "proof_sha256": "b",
            },
        },
    )
    _write(
        fallback,
        {
            "runs": [
                {
                    "problem": "slow",
                    "status": "right_censored_timeout",
                    "solved": None,
                    "elapsed_seconds": 30.0,
                }
            ]
        },
    )

    report = rebuild_report(
        baseline_path=baseline,
        problem_file=problems,
        run_dir=run_dir,
        fallback_reports=[fallback],
    )

    assert report["run_state"]["complete"] is True
    assert report["summary"]["newly_solved_names"] == ["new"]
    assert report["summary"]["time_censored"] == 1
    assert report["summary"]["execution_errors"] == 0
    assert report["summary"]["certified_score_lower_bound"] == 2 / 3


def test_refuses_to_replace_a_different_cohort(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="different problem cohort"):
        require_same_report_cohort(
            {"selected_problem_names": ["a", "b"]},
            ["c"],
            output=tmp_path / "report.json",
        )
