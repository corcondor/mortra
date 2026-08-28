from pathlib import Path

from worker.backend.circumcenter_diameter_parallelogram_chart import (
    certify_circumcenter_diameter_parallelogram_chart,
    certify_jgex_circumcenter_diameter_parallelogram_application,
    render_circumcenter_diameter_parallelogram_chart_svg,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2010AsiaPacificMOp1.jgex.txt").read_text(
    encoding="utf-8"
)
NATURAL = (
    ROOT / "data" / "fixtures" / "2010AsiaPacificMOp1.natural.txt"
).read_text(encoding="utf-8")


def test_exact_chart_replays_parallelogram_identity() -> None:
    certificate = certify_circumcenter_diameter_parallelogram_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 14
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_application_matches_renamed_structure_and_natural_branch() -> None:
    renamed = (
        "r s t = triangle; u = circumcenter r s t; "
        "v = circumcenter t u s; w = on_circle v u, on_line s r; "
        "x = on_line t r, on_circle v u; y = mirror u v ? para y x w r"
    )
    natural = (
        "The circle meets RS again at W different from S and RT at X "
        "different from T; Y is the antipode of U."
    )
    application = certify_jgex_circumcenter_diameter_parallelogram_application(
        renamed,
        natural,
    )

    assert application.replayed is True
    assert len(application.roles) == 8
    assert len(application.matched_constructions) == 5


def test_registry_selects_chart_and_requires_distinct_intersections() -> None:
    result = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        include_diagram=False,
        natural_statement=NATURAL,
    )
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "circumcenter-secondary-circle-diameter-parallelogram"
    )
    assert result.selected.identity_count == 14

    without_branch = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        include_diagram=False,
        natural_statement="The circle intersects the two side lines.",
    )
    assert without_branch.solved is False


def test_registry_rejects_unrelated_goal() -> None:
    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? coll a p n",
        include_diagram=False,
        natural_statement=NATURAL,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_circumcenter_diameter_parallelogram_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
