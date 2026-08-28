from worker.backend.mortra_codex_fused_session import (
    FusedResearchSession,
    compare_snapshots,
)
from worker.backend.mortra_research_dialogue import ResearchDialogueLedger


def _snapshot(*, left_solved: bool = False) -> dict[str, object]:
    return {
        "summary": {"evaluated": 2},
        "problems": {
            "left": {
                "solved": left_solved,
                "ambiguous": False,
                "certificate_sha256": "a" * 64 if left_solved else None,
            },
            "right": {
                "solved": False,
                "ambiguous": False,
                "certificate_sha256": None,
            },
        },
    }


def _hypothesis() -> dict[str, object]:
    return {
        "intervention_class": "reusable_typed_chart",
        "target_obligation_signature": {
            "goal": "cyclic(P,Q,R,S)",
            "missing": "power_equality(P;Q,R;S,T)",
        },
        "morphism_sequence": [
            "directed_angle_to_power",
            "power_equality_to_cyclic",
        ],
        "predicted_shared_effect": {
            "minimum_problems": 1,
            "maximum_regressions": 0,
        },
    }


def test_fused_session_blocks_for_codex_then_closes_and_continues(tmp_path) -> None:
    ledger_path = tmp_path / "fused.json"
    session = FusedResearchSession(
        ledger=ResearchDialogueLedger.create(
            objective_code="fused_test",
            frozen_cohort_sha256="f" * 64,
        ),
        ledger_path=ledger_path,
        frozen_problem_names=("frozen-a", "frozen-b"),
    )
    observation = session.begin_cycle(_snapshot())
    assert observation["waiting_for"] == "typed_hypothesis"

    accepted = session.submit_hypothesis(
        cycle_fingerprint=observation["cycle_fingerprint"],
        payload=_hypothesis(),
    )
    assert accepted["waiting_for"] == "evaluate"

    evaluation = session.close_cycle(
        cycle_fingerprint=observation["cycle_fingerprint"],
        treatment_snapshot=_snapshot(left_solved=True),
        intervention_source_sha256={"worker/backend/chart.py": "b" * 64},
    )
    assert evaluation["decision"]["accepted"]
    assert evaluation["decision"]["evidence"]["new_exact_solves"] == 1

    next_observation = session.begin_cycle(_snapshot(left_solved=True))
    assert next_observation["cycle_fingerprint"] != observation["cycle_fingerprint"]
    assert next_observation["waiting_for"] == "typed_hypothesis"


def test_fused_hypothesis_rejects_problem_specific_conditioning(tmp_path) -> None:
    session = FusedResearchSession(
        ledger=ResearchDialogueLedger.create(
            objective_code="fused_test",
            frozen_cohort_sha256="f" * 64,
        ),
        ledger_path=tmp_path / "fused.json",
        frozen_problem_names=("frozen-a",),
    )
    observation = session.begin_cycle(_snapshot())
    payload = _hypothesis()
    payload["problem_name"] = "frozen-a"

    try:
        session.submit_hypothesis(
            cycle_fingerprint=observation["cycle_fingerprint"],
            payload=payload,
        )
    except ValueError as error:
        assert "forbidden conditioning" in str(error)
    else:
        raise AssertionError("problem-specific hypothesis was accepted")


def test_snapshot_comparison_rejects_no_gain() -> None:
    experiment, decision = compare_snapshots(
        _snapshot(),
        _snapshot(),
        intervention_source_sha256={},
    )
    assert not decision["accepted"]
    assert experiment["summary"]["new_exact_solves"] == 0
