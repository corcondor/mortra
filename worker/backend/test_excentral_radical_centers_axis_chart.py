from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.excentral_radical_centers_axis_chart import (
    certify_excentral_radical_centers_axis_chart,
    certify_jgex_excentral_radical_centers_axis_application,
    render_excentral_radical_centers_axis_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data/fixtures/excentral-radical-centers-axis.jgex.txt").read_text(
    encoding="utf-8"
).strip()


def test_exact_chart_replays_every_signed_distance_and_radical_identity() -> None:
    certificate = certify_excentral_radical_centers_axis_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) >= 40
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.replay_residuals["I_O1_O2_collinear"] == "0"


def test_application_consumes_circle_pairs_only_as_order_free_chords() -> None:
    application = certify_jgex_excentral_radical_centers_axis_application(SOURCE)

    assert application.replayed
    assert application.roles["I"] == "i"
    assert application.roles["O2"] == "o2"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_swapping_each_pair_preserves_the_application() -> None:
    swapped = (
        SOURCE.replace("x1 =", "tmp =", 1)
        .replace("x2 =", "x1 =", 1)
        .replace("tmp =", "x2 =", 1)
        .replace("y1 =", "tmp =", 1)
        .replace("y2 =", "y1 =", 1)
        .replace("tmp =", "y2 =", 1)
    )

    assert certify_jgex_excentral_radical_centers_axis_application(swapped).replayed


def test_broken_radical_center_and_wrong_goal_are_rejected() -> None:
    broken = SOURCE.replace(
        "x = on_line y1 y2, on_line z1 z2",
        "x = on_line x1 x2, on_line z1 z2",
    )
    wrong_goal = SOURCE.replace("? coll i o1 o2", "? coll a o1 o2")

    assert not certify_jgex_excentral_radical_centers_axis_application(broken).replayed
    assert not certify_jgex_excentral_radical_centers_axis_application(wrong_goal).replayed


def test_portfolio_selects_one_chart_and_svg_renders() -> None:
    result = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        include_diagram=False,
    )
    svg = render_excentral_radical_centers_axis_chart_svg()

    assert result.solved
    assert not result.ambiguous
    assert result.selected is not None
    assert result.selected.chart_id == "excentral-contact-radical-centers-incenter-axis"
    assert svg.startswith("<?xml")
    assert "<svg" in svg[:512]
