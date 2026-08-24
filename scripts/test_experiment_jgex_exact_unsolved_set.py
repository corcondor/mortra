import json

from scripts.experiment_jgex_exact_unsolved_set import (
    _baseline_state,
    _compact_progress_event,
    _exact_worker,
)


def test_certified_union_baseline_state_uses_frozen_unresolved_set() -> None:
    payload = {
        "summary": {"primary_certified_solved": 58, "total": 89},
        "sets": {
            "unresolved_frozen_problems": ["p1", "p2", "outside"],
        },
    }

    solved, total, unresolved = _baseline_state(payload, {"p1", "p2"})

    assert (solved, total) == (58, 89)
    assert unresolved == ["p1", "p2"]


def test_legacy_baseline_state_remains_supported() -> None:
    payload = {
        "scores": {"original_imo_ag_30": {"solved": 2, "total": 3}},
        "results": {
            "p1": {"status": "solved"},
            "p2": {"status": "unsolved"},
            "outside": {"status": "unsolved"},
        },
    }

    solved, total, unresolved = _baseline_state(payload, {"p1", "p2"})

    assert (solved, total) == (2, 3)
    assert unresolved == ["p2"]


def test_chained_certified_union_derives_the_unresolved_complement() -> None:
    payload = {
        "summary": {"primary_certified_solved": 2, "total": 3},
        "sets": {"primary_union": ["p1", "p3", "outside"]},
    }

    solved, total, unresolved = _baseline_state(payload, {"p1", "p2", "p3"})

    assert (solved, total) == (2, 3)
    assert unresolved == ["p2"]


def test_exact_worker_persists_research_progress(tmp_path) -> None:
    output = tmp_path / "result.json"
    progress = tmp_path / "progress.json"

    _exact_worker(
        "a b c = triangle a b c; x = on_tline x a b c ? perp x a b c",
        str(output),
        str(progress),
        "explicit",
        1,
        False,
    )

    result_payload = json.loads(output.read_text(encoding="utf-8"))
    progress_payload = json.loads(progress.read_text(encoding="utf-8"))
    assert result_payload["kind"] == "result"
    assert progress_payload["event_count"] > 1
    assert progress_payload["latest"] == {
        "stage": "worker_completed",
        "kind": "result",
    }


def test_progress_checkpoint_is_stored_once_as_a_sidecar(tmp_path) -> None:
    progress = tmp_path / "case.progress.json"
    event = {
        "stage": "local_elimination_progress",
        "checkpoint_node": {
            "variable": "x",
            "method": "resultant_projection",
            "input_polynomials": ["x + y", "x - y"],
            "output_polynomials": ["2*y"],
            "ideal_membership_witnesses": [{"replay_residual": "0"}],
            "nonzero_conditions": [],
            "replayed": True,
            "certificate_sha256": "a" * 64,
        },
    }

    compact = _compact_progress_event(event, progress)
    sidecar = tmp_path / compact["checkpoint_artifact"]

    assert sidecar.is_file()
    assert json.loads(sidecar.read_text(encoding="utf-8")) == event["checkpoint_node"]
    assert compact["checkpoint_node"] == {
        "variable": "x",
        "method": "resultant_projection",
        "input_polynomial_count": 2,
        "output_polynomial_count": 1,
        "witness_count": 1,
        "nonzero_condition_count": 0,
        "replayed": True,
        "certificate_sha256": "a" * 64,
    }
