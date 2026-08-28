from pathlib import Path

from worker.backend.cevian_radical_axes_equal_angle_chart import (
    certify_cevian_radical_axes_equal_angle_chart,
    certify_jgex_cevian_radical_axes_equal_angle_application,
    render_cevian_radical_axes_equal_angle_chart_svg,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)


FIXTURE = (
    Path(__file__).parents[2]
    / "data"
    / "fixtures"
    / "cevian-radical-axes-equal-angle.jgex.txt"
)


def test_exact_chart_replays_factorized_ideal_membership() -> None:
    certificate = certify_cevian_radical_axes_equal_angle_chart()
    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) == 28
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.polynomial_evidence["division_remainder"] == "0"
    assert certificate.polynomial_evidence["quotient_replayed"] == "true"
    assert certificate.polynomial_evidence["quotient_factorization"] == (
        "2*(u*s-v*r-s)^2*(u^2+v^2)"
    )


def test_jgex_application_matches_full_construction() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    application = certify_jgex_cevian_radical_axes_equal_angle_application(source)
    assert application.replayed
    assert application.roles["P"] == "p"
    assert application.roles["K"] == "k"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_portfolio_returns_proof_and_diagram() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    result = certify_jgex_with_exact_chart_portfolio(source, include_diagram=True)
    assert result.solved
    assert not result.ambiguous
    assert result.selected is not None
    assert result.selected.chart_id == "cevian-three-radical-axes-equal-angle"
    assert result.selected.proof_status == "proved"
    assert result.selected.identity_count == 28
    assert "<svg" in (result.selected.diagram_svg or "")
    assert result.selected.certificate["polynomial_evidence"][
        "quotient_factorization"
    ] == "2*(u*s-v*r-s)^2*(u^2+v^2)"


def test_wrong_angle_or_goal_is_rejected() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    wrong_angle = source.replace(
        "eqangle3 p b c a c b",
        "eqangle3 p b c a b c",
    )
    wrong_goal = source.replace("cyclic k a p2 p3", "cyclic k b p2 p3")
    assert not certify_jgex_cevian_radical_axes_equal_angle_application(
        wrong_angle
    ).replayed
    assert not certify_jgex_cevian_radical_axes_equal_angle_application(
        wrong_goal
    ).replayed


def test_renderer_returns_svg() -> None:
    first = render_cevian_radical_axes_equal_angle_chart_svg()
    second = render_cevian_radical_axes_equal_angle_chart_svg()
    assert "<svg" in first
    assert "<svg" in second
