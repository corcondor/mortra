from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.reflected_chord_circle_pair_chart import (
    certify_jgex_reflected_chord_circle_pair_application,
    certify_reflected_chord_circle_pair_chart,
    render_reflected_chord_circle_pair_chart_svg,
)


FIXTURE = (
    Path(__file__).parents[2]
    / "data"
    / "fixtures"
    / "reflected-chord-circle-pair.jgex.txt"
)
NATURAL = FIXTURE.with_name("reflected-chord-circle-pair.natural.txt")


def test_exact_chart_replays_known_root_existential_branch() -> None:
    certificate = certify_reflected_chord_circle_pair_chart()
    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) == 38
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.branch_certificate["N"].startswith("the non-R point")
    assert certificate.branch_certificate["M"].startswith("the non-Q point")


def test_jgex_application_matches_full_unlabelled_pair() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    natural = NATURAL.read_text(encoding="utf-8")
    application = certify_jgex_reflected_chord_circle_pair_application(
        source,
        natural,
    )
    assert application.replayed
    assert application.roles["C"] == "c"
    assert application.roles["D"] == "d"
    assert {application.roles["M"], application.roles["N"]} == {"m", "n"}
    assert application.undischarged_nondegeneracy_obligations == ()
    assert application.natural_semantic_atoms


def test_portfolio_returns_proof_and_diagram() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    natural = NATURAL.read_text(encoding="utf-8")
    result = certify_jgex_with_exact_chart_portfolio(
        source,
        include_diagram=True,
        natural_statement=natural,
    )
    assert result.solved
    assert not result.ambiguous
    assert result.selected is not None
    assert result.selected.chart_id == "reflected-chord-existential-circle-pair-return"
    assert result.selected.proof_status == "proved"
    assert result.selected.identity_count == 38
    assert "<svg" in (result.selected.diagram_svg or "")


def test_wrong_reflection_or_goal_is_rejected() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    natural = NATURAL.read_text(encoding="utf-8")
    wrong_reflection = source.replace("reflect a c d", "reflect b c d")
    wrong_goal = source.replace("cyclic z p q r", "cyclic z a q r")
    assert not certify_jgex_reflected_chord_circle_pair_application(
        wrong_reflection,
        natural,
    ).replayed
    assert not certify_jgex_reflected_chord_circle_pair_application(
        wrong_goal,
        natural,
    ).replayed


def test_missing_existential_labelling_semantics_is_rejected() -> None:
    source = FIXTURE.read_text(encoding="utf-8")
    assert not certify_jgex_reflected_chord_circle_pair_application(source).replayed
    result = certify_jgex_with_exact_chart_portfolio(source)
    assert not result.solved


def test_renderer_returns_svg() -> None:
    first = render_reflected_chord_circle_pair_chart_svg()
    second = render_reflected_chord_circle_pair_chart_svg()
    assert "<svg" in first
    assert "<svg" in second
