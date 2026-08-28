from pathlib import Path

from worker.backend.euler_line_equal_angle_radical_altitude_chart import (
    certify_euler_line_equal_angle_radical_altitude_chart,
    certify_jgex_euler_line_equal_angle_radical_altitude_application,
    render_euler_line_equal_angle_radical_altitude_chart_svg,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT / "data/fixtures/euler-line-equal-angle-radical-altitude.jgex.txt"
).read_text(encoding="utf-8").strip()


def test_exact_chart_replays_radical_axis_and_angle_ideal_membership() -> None:
    certificate = certify_euler_line_equal_angle_radical_altitude_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) >= 20
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.replay_residuals["X_on_radical_axis"] == "0"
    assert certificate.replay_residuals["Q_on_radical_axis"] == "0"
    assert certificate.replay_residuals["equal_angle_implies_altitude_numerator"] == "0"
    assert certificate.polynomial_evidence["equal_angle_degree_in_x"] == "2"


def test_application_uses_the_second_circle_root_without_ordering_it() -> None:
    application = certify_jgex_euler_line_equal_angle_radical_altitude_application(
        SOURCE
    )

    assert application.replayed
    assert application.roles["P"] == "p"
    assert application.roles["Q"] == "q"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_broken_angle_locus_and_wrong_goal_are_rejected() -> None:
    broken = SOURCE.replace("eqangle3 x e f a b c", "eqangle3 x e f a c b")
    wrong_goal = SOURCE.replace("? coll q a h", "? coll q b h")

    assert not certify_jgex_euler_line_equal_angle_radical_altitude_application(
        broken
    ).replayed
    assert not certify_jgex_euler_line_equal_angle_radical_altitude_application(
        wrong_goal
    ).replayed


def test_portfolio_selects_one_chart_and_svg_renders() -> None:
    result = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        include_diagram=False,
    )
    svg = render_euler_line_equal_angle_radical_altitude_chart_svg()

    assert result.solved
    assert not result.ambiguous
    assert result.selected is not None
    assert result.selected.chart_id == "euler-line-equal-angle-radical-altitude"
    assert svg.startswith("<?xml")
    assert "<svg" in svg[:512]
