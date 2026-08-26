from pathlib import Path

import pytest

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)


ROOT = Path(__file__).resolve().parents[2]
INPUTS = ROOT / "data" / "reverify-unit8-exact-sequential-v21" / "inputs"


@pytest.mark.parametrize(
    ("problem", "chart_id", "identity_count"),
    (
        (
            "2016USATSTSTp2",
            "orthocenter-midpoint-two-circle-common-point-on-line",
            26,
        ),
    ),
)
def test_registry_replays_each_general_chart_once(
    problem: str,
    chart_id: str,
    identity_count: int,
) -> None:
    source = (INPUTS / f"{problem}.txt").read_text(encoding="utf-8")
    result = certify_jgex_with_exact_chart_portfolio(source)

    assert result.solved is True
    assert result.conditional is False
    assert result.ambiguous is False
    assert result.strict_frozen_score_eligible is False
    assert result.selected is not None
    assert result.selected.chart_id == chart_id
    assert result.selected.proof_status == "proved"
    assert result.selected.undischarged_obligations == ()
    assert result.selected.identity_count == identity_count
    assert result.selected.diagram_svg is not None
    assert "<svg" in result.selected.diagram_svg[:512]
    assert result.selected.chart_certificate_sha256 in result.selected.proof_markdown
    assert result.selected.application["formalization_repair_required"] is True
    assert result.selected.application["natural_statement_proved"] is True
    assert result.selected.application["arbitrary_source_branch_proved"] is False
    assert result.selected.application["source_formalization_status"] == (
        "branch_quantifier_mismatch"
    )
    witness = result.selected.certificate["existential_witness"]
    assert witness["replayed"] is True
    assert witness["repair_required"] is True
    assert result.selected.certificate["all_conditions_discharged"] is True
    counterexample = result.selected.certificate["source_branch_counterexample"]
    assert counterexample["replayed"] is True
    assert counterexample["other_branch_collinearity"] == (
        "det(P,T_other)=-300249/383720 != 0"
    )
    assert "元入力の任意交点版: `not proved`" in result.selected.proof_markdown
    assert "not a raw benchmark solve" in result.benchmark_admission
    assert sum(attempt.replayed for attempt in result.attempts) == 1


def test_registry_rejects_an_unrelated_goal() -> None:
    source = (INPUTS / "2016USATSTSTp2.txt").read_text(encoding="utf-8")
    setup = source.rsplit("?", maxsplit=1)[0]
    result = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? coll a b c",
        include_diagram=False,
    )

    assert result.solved is False
    assert result.conditional is False
    assert result.ambiguous is False
    assert result.selected is None
    assert not any(attempt.replayed for attempt in result.attempts)


def test_registry_marks_discharged_chart_as_proved() -> None:
    source = (
        ROOT
        / "data"
        / "reverify-unit8-nonvacuous-2026-08-23"
        / "inputs"
        / "2017CHNGaoLian.txt"
    ).read_text(encoding="utf-8")
    result = certify_jgex_with_exact_chart_portfolio(source, include_diagram=False)

    assert result.solved is True
    assert result.conditional is False
    assert result.selected is not None
    assert result.selected.proof_status == "proved"
    assert result.selected.undischarged_obligations == ()


@pytest.mark.parametrize(
    ("problem", "chart_id", "identity_count"),
    (
        ("2021GOWACAp3", "incircle-diameter-circle-reflection", 24),
        ("2023PlanetCupp9", "euler-line-circle-bisector-equal-distance", 21),
        ("2023SerbiaMOp6", "mixtilinear-two-circumcircles-tangent", 19),
        (
            "2023USAMOp6",
            "incenter-excenter-radical-axis-isogonal-trace",
            10,
        ),
        ("XinXingV28p2", "incircle-antipodes-three-circle-axis", 32),
    ),
)
def test_registry_discharges_construction_domain_for_existing_charts(
    problem: str,
    chart_id: str,
    identity_count: int,
) -> None:
    source = (INPUTS / f"{problem}.txt").read_text(encoding="utf-8")
    result = certify_jgex_with_exact_chart_portfolio(source, include_diagram=False)

    assert result.solved is True
    assert result.conditional is False
    assert result.selected is not None
    assert result.selected.chart_id == chart_id
    assert result.selected.proof_status == "proved"
    assert result.selected.identity_count == identity_count
    assert result.selected.undischarged_obligations == ()


def test_registry_replaces_2005_numeric_orientation_guards_with_exact_chart() -> None:
    source = (
        ROOT
        / "data"
        / "reverify-unit8-nonvacuous-2026-08-23"
        / "inputs"
        / "2005CTSTp19.txt"
    ).read_text(encoding="utf-8")
    result = certify_jgex_with_exact_chart_portfolio(source, include_diagram=False)

    assert result.solved is True
    assert result.conditional is False
    assert result.selected is not None
    assert result.selected.chart_id == "intersecting-chords-three-circles-collinearity"
    assert result.selected.proof_status == "proved"
    assert result.selected.undischarged_obligations == ()
