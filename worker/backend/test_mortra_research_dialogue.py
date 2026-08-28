import json

import pytest

from worker.backend.mortra_research_dialogue import (
    ResearchDialogueLedger,
)


def test_dialogue_ledger_round_trips_and_detects_tampering(tmp_path) -> None:
    path = tmp_path / "dialogue.json"
    ledger = ResearchDialogueLedger.create(
        objective_code="test_objective",
        frozen_cohort_sha256="a" * 64,
    )
    ledger.append(
        role="mortra",
        kind="cohort_observation",
        cycle_fingerprint="b" * 64,
        payload={"goal": {"predicate": "cong", "arity": 4}},
    )
    ledger.append(
        role="codex",
        kind="typed_hypothesis",
        cycle_fingerprint="b" * 64,
        payload={"chart_id": "structural-chart"},
    )
    ledger.save(path)

    loaded = ResearchDialogueLedger.load(path)
    loaded.verify()
    assert loaded.to_dict() == ledger.to_dict()

    tampered = json.loads(path.read_text(encoding="utf-8"))
    tampered["entries"][0]["payload"]["goal"]["arity"] = 8
    path.write_text(json.dumps(tampered), encoding="utf-8")
    with pytest.raises(ValueError, match="digest"):
        ResearchDialogueLedger.load(path)


def test_completed_cycle_requires_governor_decision() -> None:
    ledger = ResearchDialogueLedger.create(
        objective_code="test_objective",
        frozen_cohort_sha256="a" * 64,
    )
    fingerprint = "b" * 64
    ledger.append(
        role="mortra",
        kind="controlled_experiment",
        cycle_fingerprint=fingerprint,
        payload={"new_exact_solves": 1},
    )
    assert not ledger.completed_cycle(fingerprint)

    ledger.append(
        role="governor",
        kind="decision",
        cycle_fingerprint=fingerprint,
        payload={"accepted": True},
    )
    assert ledger.completed_cycle(fingerprint)
