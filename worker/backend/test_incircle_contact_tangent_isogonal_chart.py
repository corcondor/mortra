from pathlib import Path
import re

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.incircle_contact_tangent_isogonal_chart import (
    certify_incircle_contact_tangent_isogonal_chart,
    certify_jgex_incircle_contact_tangent_isogonal_application,
)


ROOT = Path(__file__).resolve().parents[2]
JGEX = (
    ROOT / "data/fixtures/incircle-contact-tangent-isogonal.jgex.txt"
).read_text(encoding="utf-8").strip()


def test_exact_chart_replays_contact_polar_and_final_angle_factorization() -> None:
    certificate = certify_incircle_contact_tangent_isogonal_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) >= 25
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.elimination_identity["goal_to_polar_quotient"] == (
        "-8*u*v*(u**2*w + 2*u - w)"
    )
    assert "does not select" in certificate.elimination_identity["branch_independence"]


def test_application_matches_complete_construction_and_goal() -> None:
    application = certify_jgex_incircle_contact_tangent_isogonal_application(JGEX)

    assert application.replayed
    assert application.undischarged_nondegeneracy_obligations == ()
    assert application.roles == {
        "A": "a",
        "B": "b",
        "C": "c",
        "I": "i",
        "D": "d",
        "E": "e",
        "F": "f",
        "O": "o",
        "M": "m",
        "S": "s",
        "T": "t",
        "J": "j",
    }


def test_match_is_alpha_invariant_and_has_no_problem_identifier_branch() -> None:
    names = {
        "a": "q0",
        "b": "q1",
        "c": "q2",
        "i": "q3",
        "d": "q4",
        "e": "q5",
        "f": "q6",
        "o": "q7",
        "m": "q8",
        "s": "q9",
        "t": "q10",
        "j": "q11",
    }
    renamed = JGEX
    for old in sorted(names, key=len, reverse=True):
        renamed = re.sub(rf"\b{old}\b", names[old], renamed)

    application = certify_jgex_incircle_contact_tangent_isogonal_application(renamed)

    assert application.replayed
    assert application.roles["A"] == "q0"
    assert application.roles["J"] == "q11"


def test_wrong_goal_and_missing_contact_chord_are_rejected() -> None:
    wrong_goal = JGEX.replace(
        "? eqangle a s s j i s s t",
        "? eqangle a s s t i s s j",
    )
    missing_contact_chord = JGEX.replace(
        "m = on_line e f, on_circle o a",
        "m = on_circle o a",
    )

    assert not certify_jgex_incircle_contact_tangent_isogonal_application(
        wrong_goal
    ).replayed
    assert not certify_jgex_incircle_contact_tangent_isogonal_application(
        missing_contact_chord
    ).replayed


def test_portfolio_returns_replayed_raw_construction_proof() -> None:
    result = certify_jgex_with_exact_chart_portfolio(
        JGEX,
        include_diagram=False,
    )

    assert result.solved
    assert not result.conditional
    assert not result.ambiguous
    assert result.selected is not None
    assert result.selected.chart_id == "incircle-contact-chord-circumtangent-isogonality"
    assert result.selected.proof_status == "proved"
    assert result.selected.application.get("formalization_repair_required") is None
