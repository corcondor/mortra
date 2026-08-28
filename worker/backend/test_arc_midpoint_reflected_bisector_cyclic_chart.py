import json
from pathlib import Path

from worker.backend.arc_midpoint_reflected_bisector_cyclic_chart import (
    certify_arc_midpoint_reflected_bisector_cyclic_chart,
    certify_jgex_arc_midpoint_reflected_bisector_cyclic_application,
    render_arc_midpoint_reflected_bisector_cyclic_chart_svg,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT / "data/fixtures/arc-midpoint-reflected-bisector-cyclic.jgex.txt"
).read_text(encoding="utf-8").strip()
NATURAL = json.loads(
    (ROOT / "data/hageo-409-natural-language-2026-08-26.json").read_text(
        encoding="utf-8"
    )
)["2020IranTSTp9"]


def test_exact_chart_replays_all_incidence_and_circle_residuals() -> None:
    certificate = certify_arc_midpoint_reflected_bisector_cyclic_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) >= 30
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_application_requires_and_uses_the_arc_branch_atom() -> None:
    application = certify_jgex_arc_midpoint_reflected_bisector_cyclic_application(
        SOURCE,
        NATURAL,
    )

    assert application.replayed
    assert application.roles["T"] == "t"
    assert "arc_midpoint_through(T,B,A,C)" in application.natural_semantic_atoms
    assert application.undischarged_nondegeneracy_obligations == ()


def test_missing_or_wrong_arc_branch_is_rejected() -> None:
    missing = certify_jgex_arc_midpoint_reflected_bisector_cyclic_application(
        SOURCE,
        "Let T be a point on the perpendicular bisector of BC.",
    )
    wrong = certify_jgex_arc_midpoint_reflected_bisector_cyclic_application(
        SOURCE,
        NATURAL.replace("arc $BAC$", "arc $BSC$"),
    )

    assert not missing.replayed
    assert not wrong.replayed


def test_wrong_goal_and_broken_reflection_are_rejected() -> None:
    wrong_goal = SOURCE.replace("? cyclic t j i x", "? cyclic t s i x")
    wrong_reflection = SOURCE.replace("s1 = reflect s a i", "s1 = reflect s e f")

    assert not certify_jgex_arc_midpoint_reflected_bisector_cyclic_application(
        wrong_goal,
        NATURAL,
    ).replayed
    assert not certify_jgex_arc_midpoint_reflected_bisector_cyclic_application(
        wrong_reflection,
        NATURAL,
    ).replayed


def test_portfolio_selects_one_exact_chart_and_svg_renders() -> None:
    result = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        natural_statement=NATURAL,
        include_diagram=False,
    )
    svg = render_arc_midpoint_reflected_bisector_cyclic_chart_svg()

    assert result.solved
    assert not result.ambiguous
    assert result.selected is not None
    assert result.selected.chart_id == "arc-midpoint-reflected-bisector-two-circle-cyclicity"
    assert svg.startswith("<?xml")
    assert "<svg" in svg[:512]
