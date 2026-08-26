from __future__ import annotations

from worker.backend.incircle_reflection_chart import (
    certify_incircle_reflection_chart,
    certify_jgex_incircle_reflection_application,
    render_incircle_reflection_chart_svg,
)


def test_incircle_reflection_chart_replays_every_identity() -> None:
    certificate = certify_incircle_reflection_chart()

    assert certificate.replayed
    assert len(certificate.replay_residuals) == 24
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_chart_is_problem_identifier_independent() -> None:
    serialized = str(certify_incircle_reflection_chart().to_dict())

    assert "GOWACA" not in serialized
    assert "problem_id" not in serialized
    assert "expected_answer" not in serialized


def test_renamed_jgex_problem_matches_chart() -> None:
    source = (
        "u v w = triangle; j = incenter u v w; d = foot j v w; "
        "z = circumcenter u v w; m = midpoint u j; "
        "s = on_circle z u, on_circle m u; hh = orthocenter v j w; "
        "q = on_line hh s, on_circle m u; n = midpoint d q; "
        "x = mirror j n ? cong j x d j"
    )

    application = certify_jgex_incircle_reflection_application(source)

    assert application.replayed
    assert application.roles["Q"] == "q"
    assert application.roles["X"] == "x"


def test_application_rejects_wrong_goal() -> None:
    source = (
        "a b c = triangle; i = incenter a b c; d = foot i b c; "
        "o = circumcenter a b c; m1 = midpoint a i; "
        "s = on_circle o a, on_circle m1 a; h = orthocenter b i c; "
        "q = on_line h s, on_circle m1 a; m2 = midpoint d q; "
        "x = mirror i m2 ? coll i d x"
    )

    assert not certify_jgex_incircle_reflection_application(source).replayed


def test_focus_diagram_separates_construction_and_reflection() -> None:
    svg = render_incircle_reflection_chart_svg()

    assert svg.lstrip().startswith("<?xml")
    assert "内接円と直径AIの円" in svg
    assert "中点反転と最終距離" in svg
    assert "<!-- X -->" in svg
