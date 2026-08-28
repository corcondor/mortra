from pathlib import Path
import re

from worker.backend.contact_polar_reflection_secant_chart import (
    certify_contact_polar_reflection_secant_chart,
    certify_jgex_contact_polar_reflection_secant_application,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)


ROOT = Path(__file__).resolve().parents[2]
JGEX = (ROOT / "data/fixtures/contact-polar-reflection-secants.jgex.txt").read_text(
    encoding="utf-8"
).strip()


def test_exact_chart_replays_generic_and_exceptional_circle_charts() -> None:
    certificate = certify_contact_polar_reflection_secant_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) >= 35
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert "arbitrary circumcircle point" in certificate.branch_certificate[
        "radial_condition_unused"
    ]
    assert certificate.branch_certificate["circle_cover"].endswith("(-1,0)")


def test_application_matches_two_known_root_secants() -> None:
    application = certify_jgex_contact_polar_reflection_secant_application(JGEX)

    assert application.replayed
    assert application.undischarged_nondegeneracy_obligations == ()
    assert application.roles["A"] == "a"
    assert application.roles["M"] == "m"
    assert application.roles["Y1"] == "y1"


def test_match_is_alpha_invariant_and_not_problem_conditioned() -> None:
    names = {
        "a": "q0",
        "b": "q1",
        "c": "q2",
        "o": "q3",
        "i": "q4",
        "d": "q5",
        "e": "q6",
        "f": "q7",
        "h": "q8",
        "m": "q9",
        "t": "q10",
        "q": "q11",
        "o1": "q12",
        "y": "q13",
        "y1": "q14",
    }
    renamed = JGEX
    for old in sorted(names, key=len, reverse=True):
        renamed = re.sub(rf"\b{old}\b", names[old], renamed)

    application = certify_jgex_contact_polar_reflection_secant_application(renamed)

    assert application.replayed
    assert application.roles["A"] == "q0"
    assert application.roles["Y1"] == "q14"


def test_wrong_goal_and_missing_known_root_circle_are_rejected() -> None:
    wrong_goal = JGEX.replace("? coll y1 b c", "? coll y b c")
    missing_circle = JGEX.replace(
        "y = on_line m a, on_circle o1 q",
        "y = on_line m a",
    )

    assert not certify_jgex_contact_polar_reflection_secant_application(
        wrong_goal
    ).replayed
    assert not certify_jgex_contact_polar_reflection_secant_application(
        missing_circle
    ).replayed


def test_portfolio_returns_one_raw_replayed_proof() -> None:
    result = certify_jgex_with_exact_chart_portfolio(JGEX, include_diagram=False)

    assert result.solved
    assert not result.conditional
    assert not result.ambiguous
    assert result.selected is not None
    assert result.selected.chart_id == "contact-polar-reflection-two-secants-side-return"
    assert result.selected.proof_status == "proved"
