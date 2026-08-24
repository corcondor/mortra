from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.build_hageo_rerun_certified_union import build_union


def _write(path: Path, payload: object) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_union_accepts_only_independently_replayed_frozen_names(tmp_path: Path) -> None:
    frozen = _write(tmp_path / "frozen.json", {"problem_names": ["a", "b", "c"]})
    base = _write(
        tmp_path / "base.json",
        {"summary": {"total": 3}, "sets": {"primary_union": ["a"]}},
    )
    cohort = _write(
        tmp_path / "cohort.json",
        {
            "run_state": {"complete": True},
            "runs": [{"problem": "b", "solved": True}],
        },
    )
    audit = _write(
        tmp_path / "audit.json",
        {
            "summary": {
                "all_accepted": True,
                "all_trace_integrity_passed": True,
            },
            "audits": {
                "b": {
                    "accepted": True,
                    "trace_integrity": True,
                    "numerical_guard_count": 2,
                }
            },
        },
    )

    result = build_union(base, cohort, audit, frozen)

    assert result["sets"]["primary_union"] == ["a", "b"]
    assert result["sets"]["new_certified_unique"] == ["b"]
    assert result["summary"]["primary_certified_solved"] == 2


def test_union_rejects_incomplete_cohort(tmp_path: Path) -> None:
    frozen = _write(tmp_path / "frozen.json", {"problem_names": ["a"]})
    base = _write(
        tmp_path / "base.json",
        {"summary": {"total": 1}, "sets": {"primary_union": []}},
    )
    cohort = _write(
        tmp_path / "cohort.json", {"run_state": {"complete": False}, "runs": []}
    )
    audit = _write(
        tmp_path / "audit.json",
        {
            "summary": {
                "all_accepted": True,
                "all_trace_integrity_passed": True,
            },
            "audits": {},
        },
    )

    with pytest.raises(ValueError, match="incomplete"):
        build_union(base, cohort, audit, frozen)
