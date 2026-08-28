from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.orthic_transversals_midpoint_right_angle_chart import (
    certify_jgex_orthic_transversals_midpoint_right_angle_application,
    certify_orthic_transversals_midpoint_right_angle_chart,
    render_orthic_transversals_midpoint_right_angle_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2019GOTEEMp2.jgex.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_orthic_midpoint_identity() -> None:
    certificate = certify_orthic_transversals_midpoint_right_angle_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 14
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_application_matches_renamed_structure_without_problem_id() -> None:
    renamed = (
        "r s t = triangle; u = foot r s t; v = foot s r t; "
        "w = foot t r s; x = on_line u v, on_tline r r s; "
        "y = on_line u w, on_tline r r t; z = on_line x y, on_line s t; "
        "k = midpoint s t ? perp k r r z"
    )
    application = (
        certify_jgex_orthic_transversals_midpoint_right_angle_application(
            renamed
        )
    )

    assert application.replayed is True
    assert len(application.roles) == 10
    assert len(application.matched_constructions) == 5


def test_registry_selects_chart_and_rejects_unrelated_goal() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE, include_diagram=False)
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == "orthic-transversals-midpoint-right-angle"
    assert result.selected.identity_count == 14

    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? coll m a t",
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_orthic_transversals_midpoint_right_angle_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
