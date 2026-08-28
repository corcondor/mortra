from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.median_projection_second_circle_midpoint_chart import (
    certify_jgex_median_projection_second_circle_midpoint_application,
    certify_median_projection_second_circle_midpoint_chart,
    render_median_projection_second_circle_midpoint_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2023USAMOp1.jgex.txt").read_text(
    encoding="utf-8"
)
NATURAL = (ROOT / "data" / "fixtures" / "2023USAMOp1.natural.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_all_identities() -> None:
    certificate = certify_median_projection_second_circle_midpoint_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 9
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_application_requires_distinct_second_intersection_semantics() -> None:
    application = certify_jgex_median_projection_second_circle_midpoint_application(
        SOURCE,
        NATURAL,
    )
    assert application.replayed is True
    assert application.natural_semantic_atoms

    ambiguous = certify_jgex_median_projection_second_circle_midpoint_application(
        SOURCE,
        "Circle ABP meets line BC at Q.",
    )
    assert ambiguous.replayed is False
    assert ambiguous.undischarged_nondegeneracy_obligations == ("Q != B",)


def test_registry_selects_chart_and_rejects_missing_natural_branch() -> None:
    result = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        include_diagram=False,
        natural_statement=NATURAL,
    )
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "median-projection-second-circle-intersection-midpoint-equidistant"
    )
    assert result.selected.identity_count == 9

    missing = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        include_diagram=False,
    )
    assert missing.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_median_projection_second_circle_midpoint_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
