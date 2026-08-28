from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.incenter_midpoint_perpendicular_radical_axis_chart import (
    certify_incenter_midpoint_perpendicular_radical_axis_chart,
    certify_jgex_incenter_midpoint_perpendicular_radical_axis_application,
    render_incenter_midpoint_perpendicular_radical_axis_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2021GOWACAp4.jgex.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_all_identities() -> None:
    certificate = certify_incenter_midpoint_perpendicular_radical_axis_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 31
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_application_matches_renamed_structure_without_problem_id() -> None:
    renamed = (
        "u v w = triangle; j = incenter u v w; "
        "n1 = midpoint v w; n2 = midpoint u w; n3 = midpoint u v; "
        "r = on_tline n2 v j, on_tline n3 w j; "
        "s = on_tline n1 u j, on_tline n3 w j; "
        "t = on_tline n1 u j, on_tline n2 v j; "
        "k = orthocenter r s t; n = midpoint j k; "
        "z = circumcenter u v w; z1 = circumcenter r s t; "
        "d = on_circle z u, on_circle z1 r; "
        "e = on_circle z u, on_circle z1 r ? coll d e n"
    )
    application = (
        certify_jgex_incenter_midpoint_perpendicular_radical_axis_application(
            renamed
        )
    )

    assert application.replayed is True
    assert len(application.roles) == 16
    assert len(application.matched_constructions) == 7


def test_registry_selects_chart_and_rejects_unrelated_goal() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE, include_diagram=False)
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "incenter-side-midpoint-perpendicular-triangle-radical-axis"
    )
    assert result.selected.identity_count == 31

    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? coll a b c",
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_incenter_midpoint_perpendicular_radical_axis_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
