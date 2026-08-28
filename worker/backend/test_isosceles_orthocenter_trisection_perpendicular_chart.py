from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.isosceles_orthocenter_trisection_perpendicular_chart import (
    certify_isosceles_orthocenter_trisection_perpendicular_chart,
    certify_jgex_isosceles_orthocenter_trisection_perpendicular_application,
    render_isosceles_orthocenter_trisection_perpendicular_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2021IranGOMp1.jgex.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_all_identities() -> None:
    certificate = certify_isosceles_orthocenter_trisection_perpendicular_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 11
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_application_matches_renamed_structure_without_problem_id() -> None:
    source = (
        "u v w = iso_triangle; k = orthocenter u v w; n = midpoint u w; "
        "r s = trisegment r s w v ? perp v n k r"
    )
    application = (
        certify_jgex_isosceles_orthocenter_trisection_perpendicular_application(
            source
        )
    )

    assert application.replayed is True
    assert len(application.roles) == 7


def test_registry_selects_chart_and_rejects_reversed_trisegment_role() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE, include_diagram=False)
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "isosceles-orthocenter-midpoint-trisection-perpendicular"
    )
    assert result.selected.identity_count == 11

    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? perp b e h f",
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_isosceles_orthocenter_trisection_perpendicular_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
