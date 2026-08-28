import json
from pathlib import Path

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.miquel_cevian_coaxial_chart import (
    certify_jgex_miquel_cevian_coaxial_application,
    certify_miquel_cevian_coaxial_chart,
    render_miquel_cevian_coaxial_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data/fixtures/miquel-cevian-coaxial.jgex.txt").read_text(
    encoding="utf-8"
).strip()
NATURAL = json.loads(
    (ROOT / "data/hageo-409-natural-language-2026-08-26.json").read_text(
        encoding="utf-8"
    )
)["ShuZhiMiGeo128"]


def test_exact_chart_replays_miquel_closure_and_both_coaxial_charts() -> None:
    certificate = certify_miquel_cevian_coaxial_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) >= 31
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.replay_residuals["Q_on_CDE_Miquel_closure"] == "0"
    assert certificate.replay_residuals["exceptional_R_equals_Q_coaxial_3"] == "0"


def test_application_requires_hash_bound_miquel_branch() -> None:
    application = certify_jgex_miquel_cevian_coaxial_application(SOURCE, NATURAL)

    assert application.replayed
    assert application.roles["Q"] == "q"
    assert "miquel_point(Q,D,E,F)" in application.natural_semantic_atoms
    assert application.undischarged_nondegeneracy_obligations == ()


def test_missing_or_wrong_miquel_point_is_rejected() -> None:
    missing = certify_jgex_miquel_cevian_coaxial_application(
        SOURCE,
        "The circumcircles AEF and BDF meet at F and Q.",
    )
    wrong = certify_jgex_miquel_cevian_coaxial_application(
        SOURCE,
        NATURAL.replace("Miquel point $Q$", "Miquel point $X$"),
    )

    assert not missing.replayed
    assert not wrong.replayed


def test_broken_carrier_and_wrong_goal_are_rejected() -> None:
    broken_carrier = SOURCE.replace("r = on_line r p q", "r = on_line r p d")
    wrong_goal = SOURCE.replace("? cyclic c f l t", "? cyclic c e l t")

    assert not certify_jgex_miquel_cevian_coaxial_application(
        broken_carrier,
        NATURAL,
    ).replayed
    assert not certify_jgex_miquel_cevian_coaxial_application(
        wrong_goal,
        NATURAL,
    ).replayed


def test_portfolio_selects_one_chart_and_svg_renders() -> None:
    result = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        natural_statement=NATURAL,
        include_diagram=False,
    )
    svg = render_miquel_cevian_coaxial_chart_svg()

    assert result.solved
    assert not result.ambiguous
    assert result.selected is not None
    assert result.selected.chart_id == "miquel-cevian-three-target-circles-coaxial"
    assert svg.startswith("<?xml")
    assert "<svg" in svg[:512]
