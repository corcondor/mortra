from __future__ import annotations

from worker.backend.incircle_three_circle_axis_chart import (
    certify_incircle_three_circle_axis_chart,
    certify_jgex_incircle_three_circle_axis_application,
    render_incircle_three_circle_axis_chart_svg,
)


def test_three_circle_axis_chart_replays_every_identity() -> None:
    certificate = certify_incircle_three_circle_axis_chart()

    assert certificate.replayed
    assert len(certificate.replay_residuals) == 32
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_chart_is_problem_identifier_independent() -> None:
    serialized = str(certify_incircle_three_circle_axis_chart().to_dict())

    assert "XinXing" not in serialized
    assert "problem_id" not in serialized
    assert "expected_answer" not in serialized


def test_renamed_jgex_construction_matches_chart() -> None:
    source = (
        "aa bb cc = triangle; oo = circumcenter aa bb cc; ii = incenter aa bb cc; "
        "jj1 = on_line aa ii, on_circle oo aa; jj = mirror jj1 oo; "
        "kk1 = on_line bb ii, on_circle oo aa; kk = mirror kk1 oo; "
        "ll1 = on_line cc ii, on_circle oo aa; ll = mirror ll1 oo; "
        "dd = foot ii bb cc; ee = foot ii aa cc; ff = foot ii aa bb; "
        "xx = on_line jj dd, on_circle oo aa; "
        "yy = on_line kk ee, on_circle oo aa; "
        "zz = on_line ll ff, on_circle oo aa; "
        "oo1 = circumcenter xx ee ff; oo2 = circumcenter yy ff dd; "
        "oo3 = circumcenter zz dd ee; "
        "uu = on_circle oo1 ff, on_circle oo2 ff; "
        "vv = on_circle oo1 ee, on_circle oo3 ee; "
        "tt = on_line uu ff, on_line vv ee ? coll ii oo tt"
    )

    application = certify_jgex_incircle_three_circle_axis_application(source)

    assert application.replayed
    assert application.roles["T"] == "tt"
    assert application.roles["O3"] == "oo3"


def test_application_rejects_wrong_goal() -> None:
    source = (
        "a b c = triangle; o = circumcenter a b c; i = incenter a b c; "
        "j1 = on_line a i, on_circle o a; j = mirror j1 o; "
        "k1 = on_line b i, on_circle o a; k = mirror k1 o; "
        "l1 = on_line c i, on_circle o a; l = mirror l1 o; "
        "d = foot i b c; e = foot i a c; f = foot i a b; "
        "x = on_line j d, on_circle o a; y = on_line k e, on_circle o a; "
        "z = on_line l f, on_circle o a; o1 = circumcenter x e f; "
        "o2 = circumcenter y f d; o3 = circumcenter z d e; "
        "u = on_circle o1 f, on_circle o2 f; "
        "v = on_circle o1 e, on_circle o3 e; "
        "t = on_line u f, on_line v e ? perp i o i t"
    )

    assert not certify_jgex_incircle_three_circle_axis_application(source).replayed


def test_focus_diagram_contains_both_construction_stages() -> None:
    svg = render_incircle_three_circle_axis_chart_svg()

    assert svg.lstrip().startswith("<?xml")
    assert "内心軸と外接円上の反対点" in svg
    assert "3円の共通弦と内心・外心軸" in svg
    assert "<!-- T -->" in svg
