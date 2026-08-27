from __future__ import annotations

import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from scripts.benchmark_hageo409_auxiliary import (
    bounded_worker_counts,
    enrich_run_from_artifact,
    normalize_baseline_for_driver,
    run_command_with_process_tree_timeout,
    require_same_report_cohort,
)
from scripts.rebuild_hageo_auxiliary_cohort import rebuild_report


def _write(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_nested_native_workers_fit_the_available_budget() -> None:
    assert bounded_worker_counts(
        problem_workers=3,
        candidate_workers=8,
        max_total_native_workers=18,
    ) == (3, 6)
    assert bounded_worker_counts(
        problem_workers=1,
        candidate_workers=8,
        max_total_native_workers=18,
    ) == (1, 8)


def test_nested_native_worker_cap_is_opt_in() -> None:
    assert bounded_worker_counts(
        problem_workers=3,
        candidate_workers=8,
        max_total_native_workers=0,
    ) == (3, 8)


def test_normalizes_certified_union_against_its_frozen_split(
    tmp_path: Path,
) -> None:
    frozen = tmp_path / "frozen.json"
    _write(frozen, {"problem_names": ["a", "b", "c"]})
    raw = {
        "protocol": {
            "frozen_split": {
                "path": str(frozen),
                "sha256": hashlib.sha256(frozen.read_bytes()).hexdigest(),
            }
        },
        "summary": {"total": 3, "primary_certified_solved": 2},
        "sets": {"primary_union": ["a", "c"]},
    }

    normalized = normalize_baseline_for_driver(raw, baseline_path=tmp_path / "u.json")

    assert normalized["summary"]["solved"] == 2
    assert normalized["problem_names"] == ["a", "b", "c"]
    assert normalized["results"] == {
        "a": {"status": "solved"},
        "b": {"status": "unsolved"},
        "c": {"status": "solved"},
    }


def test_embeds_compact_generated_action_audit_and_artifact_hash(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    artifact = run_dir / "p.json"
    _write(
        artifact,
        {
            "evaluated_paths": 17,
            "protocol": {
                "generated_action_quotient": {
                    "enabled": True,
                    "equivalent_paths_skipped": 3,
                }
            },
        },
    )

    enriched = enrich_run_from_artifact(
        {"problem": "p", "status": "unsolved"}, run_dir=run_dir
    )

    assert enriched["evaluated_paths"] == 17
    assert enriched["generated_action_quotient"]["equivalent_paths_skipped"] == 3
    assert enriched["artifact_sha256"] == hashlib.sha256(artifact.read_bytes()).hexdigest()


def test_embeds_evaluated_paths_from_a_frozen_timeout_checkpoint(tmp_path: Path) -> None:
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    checkpoint = run_dir / "p.progress.json"
    _write(checkpoint, {"evaluated_path_count": 41})
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()

    enriched = enrich_run_from_artifact(
        {
            "problem": "p",
            "status": "right_censored_timeout",
            "checkpoint": str(checkpoint),
            "checkpoint_sha256": digest,
        },
        run_dir=run_dir,
    )

    assert enriched["evaluated_paths"] == 41


def test_command_timeout_terminates_the_process_tree(monkeypatch, tmp_path: Path) -> None:
    class FakeProcess:
        pid = 123
        returncode = None

        def communicate(self, *, timeout: float):
            raise subprocess.TimeoutExpired(["search"], timeout)

    process = FakeProcess()
    terminated: list[object] = []
    monkeypatch.setattr(
        "scripts.benchmark_hageo409_auxiliary.subprocess.Popen",
        lambda *args, **kwargs: process,
    )
    monkeypatch.setattr(
        "scripts.benchmark_hageo409_auxiliary.terminate_process_tree",
        lambda value: terminated.append(value),
    )

    with pytest.raises(subprocess.TimeoutExpired):
        run_command_with_process_tree_timeout(
            ["search"],
            cwd=tmp_path,
            timeout_seconds=1,
            env={},
        )

    assert terminated == [process]


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
    new_artifact = run_dir / "new.json"
    _write(
        new_artifact,
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
                    "problem": "new",
                    "status": "solved",
                    "solved": True,
                    "elapsed_seconds": 9.5,
                },
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
    runs = {run["problem"]: run for run in report["runs"]}
    assert runs["new"]["elapsed_seconds"] == 9.5
    assert runs["new"]["elapsed_is_lower_bound"] is False
    assert runs["new"]["candidate_elapsed_sum_seconds"] == 2.5
    assert runs["slow"]["elapsed_seconds"] == 30.0
    assert runs["slow"]["elapsed_is_lower_bound"] is False


def test_rejects_fallback_for_a_different_artifact(tmp_path: Path) -> None:
    baseline = tmp_path / "baseline.json"
    problems = tmp_path / "problems.txt"
    run_dir = tmp_path / "runs"
    fallback = tmp_path / "fallback.json"
    _write(
        baseline,
        {
            "summary": {"solved": 0, "total": 1},
            "results": {"p": {"status": "unsolved"}},
        },
    )
    problems.write_text("p\n", encoding="utf-8")
    _write(
        run_dir / "p.json",
        {
            "problem_name": "p",
            "protocol": {"uses_external_llm": False},
            "solved": False,
            "evaluated_paths": 1,
            "right_censored_count": 0,
            "candidate_incidence": {},
            "records": [{"elapsed_seconds": 1.0}],
        },
    )
    _write(
        fallback,
        {
            "runs": [
                {
                    "problem": "p",
                    "status": "unsolved",
                    "elapsed_seconds": 2.0,
                    "artifact_sha256": "not-the-current-artifact",
                }
            ]
        },
    )

    with pytest.raises(ValueError, match="fallback artifact hash mismatch"):
        rebuild_report(
            baseline_path=baseline,
            problem_file=problems,
            run_dir=run_dir,
            fallback_reports=[fallback],
        )


def test_refuses_to_replace_a_different_cohort(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="different problem cohort"):
        require_same_report_cohort(
            {"selected_problem_names": ["a", "b"]},
            ["c"],
            output=tmp_path / "report.json",
        )
