from __future__ import annotations

from worker.backend.mixtilinear_tangent_circle_chart import (
    certify_jgex_mixtilinear_tangent_circle_application,
    certify_mixtilinear_tangent_circle_chart,
    render_mixtilinear_tangent_circle_chart_svg,
)


def test_mixtilinear_chart_replays_every_identity() -> None:
    certificate = certify_mixtilinear_tangent_circle_chart()

    assert certificate.replayed
    assert len(certificate.replay_residuals) == 19
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_chart_is_problem_identifier_independent() -> None:
    serialized = str(certify_mixtilinear_tangent_circle_chart().to_dict())

    assert "Serbia" not in serialized
    assert "problem_id" not in serialized
    assert "expected_answer" not in serialized


def test_renamed_jgex_construction_matches_chart() -> None:
    source = (
        "aa bb cc = triangle; ii = incenter aa bb cc; oo = circumcenter aa bb cc; "
        "dd = foot ii bb cc; ee = on_line aa bb, on_tline ii aa ii; "
        "ff = on_line aa cc, on_tline ii aa ii; zz = circumcenter aa ee ff; "
        "gg = on_circle zz aa, on_circle oo aa; "
        "hh = on_circle zz aa, on_line aa ii; "
        "jj = on_tline gg oo gg, on_line bb cc; "
        "kk = on_line aa jj, on_circle oo aa; "
        "uu = circumcenter dd jj kk; vv = circumcenter gg ii hh; "
        "tt = on_circle vv ii, on_circle uu dd ? coll uu vv tt"
    )

    application = certify_jgex_mixtilinear_tangent_circle_application(source)

    assert application.replayed
    assert application.roles["T"] == "tt"
    assert application.roles["O4"] == "vv"


def test_application_rejects_wrong_goal() -> None:
    source = (
        "a b c = triangle; i = incenter a b c; o = circumcenter a b c; "
        "d = foot i b c; e = on_line a b, on_tline i a i; "
        "f = on_line a c, on_tline i a i; o1 = circumcenter a e f; "
        "g = on_circle o1 a, on_circle o a; "
        "h = on_circle o1 a, on_line a i; "
        "j = on_tline g o g, on_line b c; "
        "k = on_line a j, on_circle o a; o3 = circumcenter d j k; "
        "o4 = circumcenter g i h; t = on_circle o4 i, on_circle o3 d "
        "? perp o3 o4 o3 t"
    )

    assert not certify_jgex_mixtilinear_tangent_circle_application(source).replayed


def test_focus_diagram_contains_construction_and_tangent_circles() -> None:
    svg = render_mixtilinear_tangent_circle_chart_svg()

    assert svg.lstrip().startswith("<?xml")
    assert "接線から2円を構成" in svg
    assert "接触判別式から中心線へ" in svg
    assert "<!-- O3 -->" in svg
