from pathlib import Path
import re

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.incenter_ninepoint_power_midpoint_chart import (
    certify_incenter_ninepoint_power_midpoint_chart,
    certify_jgex_incenter_ninepoint_power_midpoint_application,
)


ROOT = Path(__file__).resolve().parents[2]
JGEX = (
    ROOT / "data/fixtures/incenter-ninepoint-power-midpoint.jgex.txt"
).read_text(encoding="utf-8").strip()
NATURAL = (
    ROOT / "data/fixtures/incenter-ninepoint-power-midpoint.natural.txt"
).read_text(encoding="utf-8").strip()


def test_exact_chart_replays_every_identity() -> None:
    certificate = certify_incenter_ninepoint_power_midpoint_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) >= 45
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_application_elaborates_typed_natural_existential() -> None:
    application = certify_jgex_incenter_ninepoint_power_midpoint_application(
        JGEX,
        NATURAL,
    )

    assert application.replayed
    assert not application.formalization_repair_required
    assert application.undischarged_nondegeneracy_obligations == ()
    assert application.roles["A"] == "a"
    assert application.roles["raw_intersection_branch"] == "l"
    assert application.roles["L_star"].startswith("exists_intersection(")


def test_match_is_alpha_invariant_and_does_not_use_problem_identifier() -> None:
    names = {
        "a": "u",
        "b": "v",
        "c": "w",
        "o": "r",
        "i": "j",
        "d": "e",
        "m": "f",
        "k": "g",
        "s": "h",
        "n": "t",
        "o1": "r1",
        "o2": "r2",
        "l": "x",
        "p": "y",
    }
    renamed = JGEX
    for old in sorted(names, key=len, reverse=True):
        renamed = re.sub(rf"\b{old}\b", names[old], renamed)

    renamed_natural = (
        "Let UVW be a scalene triangle with circumcircle Omega and incenter J. "
        "Ray UJ meets VW at E and Omega again at F; the circle with diameter EF "
        "cuts Omega again at G. Lines FG and VW meet at H, and T is the midpoint "
        "of JH. The circumcircles of GJE and FUT intersect at points X1 and X2. "
        "Prove that Omega passes through the midpoint of either JX1 or JX2."
    )
    application = certify_jgex_incenter_ninepoint_power_midpoint_application(
        renamed,
        renamed_natural,
    )

    assert application.replayed
    assert application.roles["A"] == "u"
    assert application.roles["T_star"] == "midpoint(j,L_star)"


def test_missing_existential_natural_semantics_is_rejected() -> None:
    application = certify_jgex_incenter_ninepoint_power_midpoint_application(
        JGEX,
        "The two circles meet at L. Prove the midpoint lies on the circle.",
    )

    assert not application.replayed
    assert application.roles == {}


def test_portfolio_reports_typed_natural_solve() -> None:
    result = certify_jgex_with_exact_chart_portfolio(
        JGEX,
        natural_statement=NATURAL,
        include_diagram=False,
    )

    assert result.solved
    assert not result.ambiguous
    assert not result.strict_frozen_score_eligible
    assert result.selected is not None
    assert result.selected.chart_id == "incenter-nine-point-power-chain-midpoint"
    assert result.selected.application["formalization_repair_required"] is False
