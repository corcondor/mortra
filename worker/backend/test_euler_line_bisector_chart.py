from __future__ import annotations

from collections import Counter

from worker.backend.euler_line_bisector_chart import (
    certify_euler_line_bisector_chart,
    certify_jgex_euler_line_bisector_application,
    render_euler_line_bisector_chart_svg,
)


def test_euler_line_bisector_chart_replays_every_identity() -> None:
    certificate = certify_euler_line_bisector_chart()

    assert certificate.replayed
    assert len(certificate.replay_residuals) == 21
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_chart_does_not_depend_on_a_problem_identifier() -> None:
    serialized = str(certify_euler_line_bisector_chart().to_dict())

    assert "Planet" not in serialized
    assert "problem_id" not in serialized
    assert "expected_answer" not in serialized


def test_renamed_jgex_construction_matches_chart() -> None:
    source = (
        "u v w = triangle; z = circumcenter u v w; hh = orthocenter u v w; "
        "ee = on_line z hh, on_line u w; ff = on_line z hh, on_line u v; "
        "z1 = circumcenter u hh z; kk = on_circle z1 u, on_circle z u; "
        "ll = on_line kk hh, on_circle z u; mm = midpoint v w; "
        "pp = on_line hh mm, on_bline ee ff; "
        "qq = on_line pp ll, on_line v w ? cong hh qq z qq"
    )

    application = certify_jgex_euler_line_bisector_application(source)

    assert application.replayed
    assert application.roles["Q"] == "qq"
    assert application.goal.split()[0] == "cong"
    assert Counter(application.goal.split()[1:]) == Counter(("hh", "qq", "z", "qq"))


def test_application_rejects_wrong_goal() -> None:
    source = (
        "a b c = triangle; o = circumcenter a b c; h = orthocenter a b c; "
        "e = on_line o h, on_line a c; f = on_line o h, on_line a b; "
        "o1 = circumcenter a h o; k = on_circle o1 a, on_circle o a; "
        "l = on_line k h, on_circle o a; m = midpoint b c; "
        "p = on_line h m, on_bline e f; "
        "q = on_line p l, on_line b c ? coll h o q"
    )

    assert not certify_jgex_euler_line_bisector_application(source).replayed


def test_focus_diagram_contains_construction_and_goal_stages() -> None:
    svg = render_euler_line_bisector_chart_svg()

    assert svg.lstrip().startswith("<?xml")
    assert "円とEuler線の構成" in svg
    assert "垂直二等分線から距離等式へ" in svg
    assert "<!-- Q -->" in svg
