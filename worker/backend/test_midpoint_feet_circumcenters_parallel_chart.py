from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.midpoint_feet_circumcenters_parallel_chart import (
    certify_jgex_midpoint_feet_circumcenters_parallel_application,
    certify_midpoint_feet_circumcenters_parallel_chart,
    render_midpoint_feet_circumcenters_parallel_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT / "data" / "fixtures" / "2017CHNSouthEastMOg10p2.jgex.txt"
).read_text(encoding="utf-8")


def test_exact_chart_replays_shared_height_identity() -> None:
    certificate = certify_midpoint_feet_circumcenters_parallel_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 18
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_application_matches_renamed_structure_without_problem_id() -> None:
    renamed = (
        "r s t = triangle; u = midpoint t s; v = midpoint u r; "
        "w = foot u s r; x = foot u r t; "
        "y = on_line w v, on_line s t; z = on_line t s, on_line v x; "
        "j = circumcenter y u w; k = circumcenter x z u ? para t s k j"
    )
    application = certify_jgex_midpoint_feet_circumcenters_parallel_application(
        renamed
    )

    assert application.replayed is True
    assert len(application.roles) == 11
    assert len(application.matched_constructions) == 5


def test_registry_selects_chart_and_rejects_unrelated_goal() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE, include_diagram=False)
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "midpoint-feet-two-circumcenters-parallel-to-base"
    )
    assert result.selected.identity_count == 18

    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? coll o1 o2 a",
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_midpoint_feet_circumcenters_parallel_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
