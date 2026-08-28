from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.incircle_two_contacts_bci_circumcenter_angle_chart import (
    certify_incircle_two_contacts_bci_circumcenter_angle_chart,
    certify_jgex_incircle_two_contacts_bci_circumcenter_angle_application,
    render_incircle_two_contacts_bci_circumcenter_angle_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2012CGMOp5.jgex.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_all_identities() -> None:
    certificate = certify_incircle_two_contacts_bci_circumcenter_angle_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 9
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_application_matches_renamed_structure_without_problem_id() -> None:
    source = (
        "u v w = triangle; j = incenter u v w; r = foot j u v; "
        "s = foot j u w; z = circumcenter v w j ? eqangle z r r v w s s z"
    )
    application = certify_jgex_incircle_two_contacts_bci_circumcenter_angle_application(
        source
    )
    assert application.replayed is True
    assert len(application.roles) == 7


def test_registry_selects_chart_and_rejects_unrelated_angle() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE, include_diagram=False)
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "incircle-two-contacts-bci-circumcenter-equal-angle"
    )
    assert result.selected.identity_count == 9

    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? eqangle o d d c b e e o",
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_incircle_two_contacts_bci_circumcenter_angle_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
