from pathlib import Path

from worker.backend.cross_altitudes_right_angle_pedal_chart import (
    certify_cross_altitudes_right_angle_pedal_chart,
    certify_jgex_cross_altitudes_right_angle_pedal_application,
    render_cross_altitudes_right_angle_pedal_chart_svg,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2011ARMOg10p6.jgex.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_diameter_circle_identity() -> None:
    certificate = certify_cross_altitudes_right_angle_pedal_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 10
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_application_matches_renamed_structure_without_problem_id() -> None:
    renamed = (
        "r s t = triangle; u = foot s r t; v = foot t r s; "
        "w = on_line s u; x = on_line t v, on_tline r r w; "
        "y = foot r w x ? perp s y y t"
    )
    application = certify_jgex_cross_altitudes_right_angle_pedal_application(
        renamed
    )

    assert application.replayed is True
    assert len(application.roles) == 8
    assert len(application.matched_constructions) == 5


def test_registry_selects_chart_and_rejects_unrelated_goal() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE, include_diagram=False)
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "cross-altitudes-right-angle-pedal-on-diameter-circle"
    )
    assert result.selected.identity_count == 10

    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? coll b f c",
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_cross_altitudes_right_angle_pedal_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
