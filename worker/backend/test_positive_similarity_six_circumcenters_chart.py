from __future__ import annotations

from worker.backend.positive_similarity_six_circumcenters_chart import (
    certify_jgex_positive_similarity_six_circumcenters_application,
    certify_positive_similarity_six_circumcenters_chart,
    render_positive_similarity_six_circumcenters_chart_svg,
)


SOURCE = (
    "p1 p3 p5 = triangle; p4 = free p4; p6 = free p6; "
    "p2 = on_aline p4 p6 p5 p1 p3, on_aline p6 p4 p5 p3 p1; "
    "y1 = on_line p1 p3, on_line p2 p6; "
    "y2 = on_line p1 p3, on_line p2 p4; "
    "y3 = on_line p2 p4, on_line p3 p5; "
    "y4 = on_line p3 p5, on_line p4 p6; "
    "y5 = on_line p1 p5, on_line p4 p6; "
    "y6 = on_line p1 p5, on_line p2 p6; "
    "c1 = circumcenter p1 y1 p2; c2 = circumcenter p2 y2 p3; "
    "c3 = circumcenter p3 y3 p4; c4 = circumcenter p4 y4 p5; "
    "c5 = circumcenter p5 y5 p6; c6 = circumcenter p6 y6 p1; "
    "z = on_line c1 c4, on_line c2 c5 ? coll z c3 c6"
)


def test_chart_replays_homogeneous_concurrency_identity() -> None:
    certificate = certify_positive_similarity_six_circumcenters_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.determinant_operation_count > 1_000
    assert len(certificate.certificate_sha256) == 64


def test_chart_is_not_problem_or_answer_dispatched() -> None:
    serialized = str(certify_positive_similarity_six_circumcenters_chart().to_dict())

    assert "MOSTMock" not in serialized
    assert "problem_id" not in serialized
    assert "expected_answer" not in serialized


def test_renamed_jgex_structure_matches() -> None:
    application = certify_jgex_positive_similarity_six_circumcenters_application(SOURCE)

    assert application.replayed
    assert application.roles["A2"] == "p2"
    assert application.roles["X4"] == "y4"
    assert application.roles["O6"] == "c6"
    assert application.roles["K"] == "z"


def test_wrong_goal_is_rejected() -> None:
    source = SOURCE.replace("? coll z c3 c6", "? perp z c3 z c6")

    assert not certify_jgex_positive_similarity_six_circumcenters_application(source).replayed


def test_missing_similarity_clause_is_rejected() -> None:
    source = SOURCE.replace(
        "p2 = on_aline p4 p6 p5 p1 p3, on_aline p6 p4 p5 p3 p1; ",
        "p2 = on_aline p4 p6 p5 p1 p3; ",
    )

    assert not certify_jgex_positive_similarity_six_circumcenters_application(source).replayed


def test_wrong_carrier_intersection_is_rejected() -> None:
    source = SOURCE.replace(
        "y4 = on_line p3 p5, on_line p4 p6; ",
        "y4 = on_line p1 p3, on_line p4 p6; ",
    )

    assert not certify_jgex_positive_similarity_six_circumcenters_application(source).replayed


def test_diagram_contains_six_centres_and_concurrency_point() -> None:
    svg = render_positive_similarity_six_circumcenters_chart_svg()

    assert svg.lstrip().startswith("<?xml")
    assert "Six circumcenters from two directly similar triangles" in svg
    assert "O1" in svg
    assert "O6" in svg
    assert "<!-- K -->" in svg
