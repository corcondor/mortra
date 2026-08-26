from pathlib import Path

import pytest

from worker.backend.tangent_triangle_secant_midpoint_chart import (
    certify_jgex_tangent_triangle_secant_midpoint_application,
    certify_tangent_triangle_secant_midpoint_chart,
    render_tangent_triangle_secant_midpoint_chart_svg,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2017G4.jgex.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_every_identity() -> None:
    certificate = certify_tangent_triangle_secant_midpoint_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 19
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.circle_coefficients["Gamma1_d"] == "0"
    assert len(certificate.certificate_sha256) == 64


def test_current_excenter_formulation_matches_without_problem_id() -> None:
    application = certify_jgex_tangent_triangle_secant_midpoint_application(SOURCE)

    assert application.replayed is True
    assert application.roles["I"] == "i1"
    assert application.roles["O2"] == "o2"
    assert application.roles["U"] == "u"
    assert application.goal == "coll i1 u o2"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_renamed_incenter_variant_matches_the_same_chart() -> None:
    source = (
        "x y z = triangle x y z; j = incenter j x y z; "
        "r = foot r j z y; s = foot s j z x; t = foot t j y x; "
        "h = circumcenter h t x s; "
        "q2 = on_circle q2 h x, on_line q2 z y; "
        "q1 = on_line q1 y z, on_circle q1 h x; "
        "n = midpoint n r x; k = circumcenter k q2 n q1; "
        "w = on_circle w j r, on_circle w k n ? coll w j k"
    )

    application = certify_jgex_tangent_triangle_secant_midpoint_application(source)

    assert application.replayed is True
    assert application.roles["A"] == "x"
    assert application.roles["I"] == "j"
    assert {application.roles["P"], application.roles["Q"]} == {"q1", "q2"}
    assert application.roles["U"] == "w"


@pytest.mark.parametrize(
    "mutated",
    (
        SOURCE.replace("midpoint m a d", "midpoint m a e"),
        SOURCE.replace("circumcenter o1 a e f", "circumcenter o1 a d f"),
        SOURCE.replace("on_line p b c", "on_line p a c"),
        SOURCE.replace("on_circle u i1 d", "on_circle u i1 e"),
        SOURCE.replace("? coll i1 u o2", "? coll i1 u o1"),
        SOURCE.replace("excenter i1 a b c", "circumcenter i1 a b c"),
    ),
)
def test_nearby_but_invalid_structures_are_rejected(mutated: str) -> None:
    application = certify_jgex_tangent_triangle_secant_midpoint_application(mutated)

    assert application.replayed is False


def test_renderer_returns_a_complete_svg() -> None:
    rendered = render_tangent_triangle_secant_midpoint_chart_svg()

    assert rendered.startswith("<?xml")
    assert "<svg" in rendered[:512]
    assert "Tangent triangle" in rendered
