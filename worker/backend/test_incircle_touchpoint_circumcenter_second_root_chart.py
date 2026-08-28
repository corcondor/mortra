from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.incircle_touchpoint_circumcenter_second_root_chart import (
    certify_incircle_touchpoint_circumcenter_second_root_chart,
    certify_jgex_incircle_touchpoint_circumcenter_second_root_application,
    render_incircle_touchpoint_circumcenter_second_root_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2012ARMOg10p2.jgex.txt").read_text(
    encoding="utf-8"
)
NATURAL = (ROOT / "data" / "fixtures" / "2012ARMOg10p2.natural.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_all_identities() -> None:
    certificate = certify_incircle_touchpoint_circumcenter_second_root_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 15
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_application_requires_the_other_intersection_semantics() -> None:
    application = certify_jgex_incircle_touchpoint_circumcenter_second_root_application(
        SOURCE,
        NATURAL,
    )
    assert application.replayed is True
    assert application.natural_semantic_atoms

    ambiguous = certify_jgex_incircle_touchpoint_circumcenter_second_root_application(
        SOURCE,
        "Circle ADI meets line AO at E.",
    )
    assert ambiguous.replayed is False
    assert ambiguous.undischarged_nondegeneracy_obligations == ("E != A",)


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
        "incircle-touchpoint-circumcenter-line-second-root-equals-inradius"
    )
    assert result.selected.identity_count == 15

    missing = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        include_diagram=False,
    )
    assert missing.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_incircle_touchpoint_circumcenter_second_root_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
