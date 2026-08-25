from __future__ import annotations

from worker.backend.tangential_quadrilateral_second_tangent_chart import (
    certify_jgex_tangential_quadrilateral_second_tangent_application,
    certify_tangential_quadrilateral_second_tangent_chart,
    render_tangential_quadrilateral_second_tangent_chart_svg,
)


SOURCE = (
    "x1 x2 x3 = triangle; z = circumcenter x1 x2 x3; "
    "x4 = on_circle z x1; "
    "aa = on_tline x1 z x1, on_tline x2 z x2; "
    "bb = on_tline x2 z x2, on_tline x3 z x3; "
    "cc = on_tline x3 z x3, on_tline x4 z x4; "
    "dd = on_tline x1 z x1, on_tline x4 z x4; "
    "ss = on_circle z x1, on_tline z aa cc; "
    "pp = on_tline ss z ss, on_line bb dd; "
    "tt = reflect ss z pp; oo = circumcenter aa tt cc ? coll z oo tt"
)


def test_chart_replays_exact_elimination_and_construction_identities() -> None:
    certificate = certify_tangential_quadrilateral_second_tangent_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.quotient_term_count > 100
    assert len(certificate.certificate_sha256) == 64


def test_chart_is_not_problem_or_answer_dispatched() -> None:
    serialized = str(certify_tangential_quadrilateral_second_tangent_chart().to_dict())

    assert "KoMaLA" not in serialized
    assert "problem_id" not in serialized
    assert "expected_answer" not in serialized


def test_renamed_jgex_structure_matches() -> None:
    application = certify_jgex_tangential_quadrilateral_second_tangent_application(SOURCE)

    assert application.replayed
    assert application.roles["S"] == "ss"
    assert application.roles["T"] == "tt"
    assert application.roles["O"] == "oo"


def test_wrong_goal_is_rejected() -> None:
    source = SOURCE.replace("? coll z oo tt", "? perp z oo z tt")

    assert not certify_jgex_tangential_quadrilateral_second_tangent_application(source).replayed


def test_missing_parallel_tangent_is_rejected() -> None:
    source = SOURCE.replace(
        "ss = on_circle z x1, on_tline z aa cc; ",
        "ss = on_circle z x1; ",
    )

    assert not certify_jgex_tangential_quadrilateral_second_tangent_application(source).replayed


def test_diagram_contains_both_circles_and_second_tangent() -> None:
    svg = render_tangential_quadrilateral_second_tangent_chart_svg()

    assert svg.lstrip().startswith("<?xml")
    assert "Tangential quadrilateral and the second tangent" in svg
    assert "<!-- S -->" in svg
    assert "<!-- T -->" in svg
