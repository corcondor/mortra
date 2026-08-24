from __future__ import annotations

import pytest

from scripts.verify_hageo_passk_artifact import _solved_trajectory


def test_normalizes_current_auxiliary_artifact() -> None:
    artifact = {
        "protocol": {"seed": 7, "branch_build_mode": "incremental"},
        "solved": True,
        "solved_path": ["reflect(a,m,l)->e"],
        "confirmation": {"input_sha256": "input", "proof_sha256": "proof"},
    }

    assert _solved_trajectory(artifact) == (
        None,
        7,
        ["reflect(a,m,l)->e"],
        "incremental",
        {"input_sha256": "input", "proof_sha256": "proof"},
    )


def test_normalizes_legacy_passk_artifact() -> None:
    artifact = {
        "protocol": {"seed": 3},
        "attempt_results": [
            {"attempt": 0, "solved": False, "path": []},
            {
                "attempt": 2,
                "solved": True,
                "path": ["circle(a,b,c)->d"],
                "input_sha256": "input",
                "proof_sha256": "proof",
            },
        ],
    }

    assert _solved_trajectory(artifact) == (
        2,
        2_000_009,
        ["circle(a,b,c)->d"],
        "full-path",
        {"input_sha256": "input", "proof_sha256": "proof"},
    )


def test_rejects_unsolved_artifact() -> None:
    with pytest.raises(ValueError, match="no solved trajectory"):
        _solved_trajectory({"protocol": {"seed": 0}, "solved": False})
