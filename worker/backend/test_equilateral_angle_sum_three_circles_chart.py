from pathlib import Path

from worker.backend.equilateral_angle_sum_three_circles_chart import (
    certify_equilateral_angle_sum_three_circles_chart,
    certify_jgex_equilateral_angle_sum_three_circles_application,
    render_equilateral_angle_sum_three_circles_chart_svg,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT / "data/fixtures/equilateral-angle-sum-three-circles.jgex.txt"
).read_text(encoding="utf-8").strip()


def test_exact_chart_replays_angle_composition_and_circle_pencil() -> None:
    certificate = certify_equilateral_angle_sum_three_circles_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) >= 27
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.replay_residuals["C0_first_on_aline"] == "0"
    assert certificate.replay_residuals["C1_second_on_aline"] == "0"
    assert certificate.replay_residuals["three_circles_pencil_3"] == "0"


def test_application_consumes_the_constructed_common_point() -> None:
    application = certify_jgex_equilateral_angle_sum_three_circles_application(SOURCE)

    assert application.replayed
    assert application.roles["X"] == "x"
    assert application.roles["C1"] == "c1"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_broken_angle_composition_and_wrong_goal_are_rejected() -> None:
    broken = SOURCE.replace(
        "on_aline c1 a b c0 a o",
        "on_aline c1 a b c0 b o",
    )
    wrong_goal = SOURCE.replace("? cyclic x c c1 c2", "? cyclic x a c1 c2")

    assert not certify_jgex_equilateral_angle_sum_three_circles_application(
        broken
    ).replayed
    assert not certify_jgex_equilateral_angle_sum_three_circles_application(
        wrong_goal
    ).replayed


def test_portfolio_selects_one_chart_and_svg_renders() -> None:
    result = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        include_diagram=False,
    )
    svg = render_equilateral_angle_sum_three_circles_chart_svg()

    assert result.solved
    assert not result.ambiguous
    assert result.selected is not None
    assert result.selected.chart_id == "equilateral-angle-sum-three-circle-pencil"
    assert svg.startswith("<?xml")
    assert "<svg" in svg[:512]
