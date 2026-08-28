from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.incenter_bisector_orthocenters_midpoint_chart import (
    certify_incenter_bisector_orthocenters_midpoint_chart,
    certify_jgex_incenter_bisector_orthocenters_midpoint_application,
    render_incenter_bisector_orthocenters_midpoint_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2023IranGOAp4.jgex.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_all_identities() -> None:
    certificate = certify_incenter_bisector_orthocenters_midpoint_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 29
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_application_matches_renamed_structure_without_problem_id() -> None:
    renamed = (
        "u v w = triangle; r = on_line u w, angle_bisector u v w; "
        "s = on_line u v, angle_bisector u w v; j = incenter u v w; "
        "t = foot j v w; g = orthocenter u j s; h = orthocenter u j r; "
        "z = on_line r g, on_line s h; n = midpoint v w; "
        "y = on_line u t, on_tline n j z; k = midpoint n y ? coll k u j"
    )
    application = certify_jgex_incenter_bisector_orthocenters_midpoint_application(
        renamed
    )

    assert application.replayed is True
    assert len(application.roles) == 13
    assert len(application.matched_constructions) == 7


def test_registry_selects_chart_and_rejects_unrelated_goal() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE, include_diagram=False)
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "incenter-bisector-orthocenters-midpoint-on-bisector"
    )
    assert result.selected.identity_count == 29

    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? coll a b c",
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_incenter_bisector_orthocenters_midpoint_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
