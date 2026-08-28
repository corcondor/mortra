from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
    registered_exact_chart_contracts,
)
from worker.backend.geometry_natural_semantics import (
    extract_geometry_natural_semantics,
)
from worker.backend.major_arc_homothety_tangent_chart import (
    certify_jgex_major_arc_homothety_tangent_application,
    certify_major_arc_homothety_tangent_chart,
    render_major_arc_homothety_tangent_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data/fixtures/major-arc-homothety-tangent.jgex.txt").read_text(
    encoding="utf-8"
).strip()
NATURAL = (
    ROOT / "data/fixtures/major-arc-homothety-tangent.natural.txt"
).read_text(encoding="utf-8").strip()
CHART_ID = "major-arc-homothety-right-circle-tangent"


def test_natural_semantics_preserve_arc_through_branch() -> None:
    semantics = extract_geometry_natural_semantics(NATURAL)

    assert semantics.parser_version == "geometry-natural-semantics-v2"
    assert semantics.has_acute_triangle(("A", "B", "C"))
    assert semantics.has_arc_midpoint_through("N", ("B", "C"), "A")
    assert "arc_midpoint_through(N,B,A,C)" in semantics.typed_atoms


def test_exact_chart_replays_every_identity() -> None:
    certificate = certify_major_arc_homothety_tangent_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) >= 40
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_application_requires_natural_arc_branch() -> None:
    accepted = certify_jgex_major_arc_homothety_tangent_application(
        SOURCE,
        NATURAL,
    )
    missing_natural = certify_jgex_major_arc_homothety_tangent_application(SOURCE)
    wrong_branch = certify_jgex_major_arc_homothety_tangent_application(
        SOURCE,
        NATURAL.replace("arc BAC", "arc BDC"),
    )

    assert accepted.replayed
    assert accepted.roles["N"] == "n"
    assert accepted.undischarged_nondegeneracy_obligations == ()
    assert not missing_natural.replayed
    assert not wrong_branch.replayed


def test_portfolio_ablation_attributes_the_new_solve_to_the_chart() -> None:
    control = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        include_diagram=False,
        natural_statement=NATURAL,
        disabled_chart_ids={CHART_ID},
    )
    treatment = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        include_diagram=False,
        natural_statement=NATURAL,
    )

    assert not control.solved
    assert any(
        attempt.chart_id == CHART_ID and attempt.error == "disabled_by_experiment"
        for attempt in control.attempts
    )
    assert treatment.solved
    assert not treatment.ambiguous
    assert treatment.selected is not None
    assert treatment.selected.chart_id == CHART_ID
    assert treatment.selected.proof_status == "proved"


def test_matcher_has_no_problem_identifier_branch() -> None:
    module = (
        ROOT / "worker/backend/major_arc_homothety_tangent_chart.py"
    ).read_text(encoding="utf-8")

    assert "2020IranGOAp2" not in module


def test_chart_renders_an_explanatory_svg() -> None:
    svg = render_major_arc_homothety_tangent_chart_svg()

    assert svg.startswith("<?xml")
    assert "H(A, 1/2)" in svg
    assert "<svg" in svg


def test_portfolio_exposes_a_data_only_structural_contract() -> None:
    contracts = {
        str(contract["chart_id"]): contract
        for contract in registered_exact_chart_contracts()
    }
    contract = contracts[CHART_ID]

    assert contract["goal_predicate"] == "cong"
    assert contract["required_operation_counts"]["mirror"] == 2
    assert contract["uses_natural_statement"] is True
    assert "apply" not in contract
