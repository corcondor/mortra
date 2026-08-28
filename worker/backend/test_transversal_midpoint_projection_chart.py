from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.transversal_midpoint_projection_chart import (
    certify_jgex_transversal_midpoint_projection_application,
    certify_transversal_midpoint_projection_chart,
    render_transversal_midpoint_projection_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2020AQGOp4.jgex.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_stronger_vector_identity() -> None:
    certificate = certify_transversal_midpoint_projection_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 13
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_application_matches_renamed_structure_without_problem_id() -> None:
    renamed = (
        "r s t = triangle; u = on_line r s; v = on_line r t; "
        "w = midpoint t u; x = midpoint s v; "
        "y = on_tline w u v, on_bline r t; "
        "z = on_bline r s, on_tline x v u ? para z y x w"
    )
    application = certify_jgex_transversal_midpoint_projection_application(renamed)

    assert application.replayed is True
    assert len(application.roles) == 9
    assert len(application.matched_constructions) == 5


def test_registry_selects_chart_and_rejects_unrelated_goal() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE, include_diagram=False)
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "transversal-cross-midpoints-perpendicular-bisectors-translation"
    )
    assert result.selected.identity_count == 13

    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? coll m n p",
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_transversal_midpoint_projection_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
