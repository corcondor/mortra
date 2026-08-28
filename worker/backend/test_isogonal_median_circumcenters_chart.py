from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.isogonal_median_circumcenters_chart import (
    certify_isogonal_median_circumcenters_chart,
    certify_jgex_isogonal_median_circumcenters_application,
    render_isogonal_median_circumcenters_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2010CTSTp19.jgex.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_isogonal_circumcenter_identity() -> None:
    certificate = certify_isogonal_median_circumcenters_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 14
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_application_matches_renamed_structure_without_problem_id() -> None:
    renamed = (
        "r s t = triangle; u = midpoint t s; "
        "v = on_aline v r t s r u; w = circumcenter t s r; "
        "x = circumcenter s v r; y = circumcenter t r v; "
        "z = midpoint y x ? coll z r w"
    )
    application = certify_jgex_isogonal_median_circumcenters_application(renamed)

    assert application.replayed is True
    assert len(application.roles) == 9
    assert len(application.matched_constructions) == 5


def test_registry_selects_chart_and_rejects_unrelated_goal() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE, include_diagram=False)
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "isogonal-median-two-circumcenters-midpoint-on-euler-radius"
    )
    assert result.selected.identity_count == 14

    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? perp a o n",
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_isogonal_median_circumcenters_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
