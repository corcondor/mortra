from pathlib import Path

from worker.backend.euler_midpoints_cross_perpendicular_chart import (
    certify_euler_midpoints_cross_perpendicular_chart,
    certify_jgex_euler_midpoints_cross_perpendicular_application,
    render_euler_midpoints_cross_perpendicular_chart_svg,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2009G6.jgex.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_all_identities() -> None:
    certificate = certify_euler_midpoints_cross_perpendicular_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 18
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_application_matches_structure_without_problem_id() -> None:
    renamed = (
        "q r s t = quadrangle; u = on_line q t, on_line r s; "
        "v1 = circumcenter q r u; w1 = orthocenter q r u; "
        "v2 = circumcenter s t u; w2 = orthocenter s t u; "
        "y1 = midpoint v1 w1; y2 = midpoint v2 w2; "
        "z = on_tline y1 s t, on_tline y2 q r ? coll z w1 w2"
    )
    application = certify_jgex_euler_midpoints_cross_perpendicular_application(
        renamed
    )

    assert application.replayed is True
    assert len(application.roles) == 12
    assert len(application.matched_constructions) == 6


def test_registry_selects_chart_and_rejects_unrelated_goal() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE, include_diagram=False)
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "two-euler-midpoints-cross-perpendiculars-orthocenter-line"
    )
    assert result.selected.identity_count == 18

    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? coll a b c",
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_euler_midpoints_cross_perpendicular_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
