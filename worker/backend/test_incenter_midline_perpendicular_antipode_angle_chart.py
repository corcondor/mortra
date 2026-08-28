from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.incenter_midline_perpendicular_antipode_angle_chart import (
    certify_incenter_midline_perpendicular_antipode_angle_chart,
    certify_jgex_incenter_midline_perpendicular_antipode_angle_application,
    render_incenter_midline_perpendicular_antipode_angle_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2022CGMOp3.jgex.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_unit_incircle_angle_identity() -> None:
    certificate = certify_incenter_midline_perpendicular_antipode_angle_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 8
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_application_matches_renamed_structure_without_problem_id() -> None:
    renamed = (
        "r s t = triangle; u = incenter r s t; v = midpoint s t; "
        "w = on_tline u s t, on_line r v; x = mirror u r "
        "? eqangle r s s x u s s w"
    )
    application = (
        certify_jgex_incenter_midline_perpendicular_antipode_angle_application(
            renamed
        )
    )

    assert application.replayed is True
    assert len(application.roles) == 7
    assert len(application.matched_constructions) == 4


def test_registry_selects_chart_and_rejects_unrelated_goal() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE, include_diagram=False)
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "unit-incircle-midline-perpendicular-antipode-equal-angle"
    )
    assert result.selected.identity_count == 8

    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? coll i l j",
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_incenter_midline_perpendicular_antipode_angle_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
