from worker.backend.isosceles_two_circle_perpendicular_chart import (
    certify_isosceles_two_circle_perpendicular_chart,
    certify_jgex_isosceles_two_circle_perpendicular_application,
    render_isosceles_two_circle_perpendicular_chart_svg,
)


SOURCE = (
    "a b c = iso_triangle; i = incenter a b c; o3 = on_bline b i; "
    "p = on_circle a b, on_circle o3 b; "
    "q = on_circle i b, on_circle o3 b; "
    "r = on_line p i, on_line b q ? perp b r c r"
)


def test_exact_chart_replays_and_discharges_every_condition() -> None:
    certificate = certify_isosceles_two_circle_perpendicular_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert certificate.replay_residuals
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert "P != B, hence t != v" in certificate.discharged_conditions
    assert "Q != B, hence t != 2v" in certificate.discharged_conditions


def test_application_matches_structure_without_problem_id() -> None:
    application = certify_jgex_isosceles_two_circle_perpendicular_application(SOURCE)

    assert application.replayed is True
    assert application.undischarged_nondegeneracy_obligations == ()
    assert len(application.roles) == 8


def test_application_is_invariant_under_point_renaming() -> None:
    renamed = (
        "u v w = iso_triangle; j = incenter u v w; z = on_bline v j; "
        "x = on_circle u v, on_circle z v; "
        "y = on_circle j v, on_circle z v; "
        "s = on_line x j, on_line v y ? perp v s w s"
    )
    application = certify_jgex_isosceles_two_circle_perpendicular_application(renamed)

    assert application.replayed is True
    assert application.roles["R"] == "s"


def test_application_rejects_a_different_goal() -> None:
    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    application = certify_jgex_isosceles_two_circle_perpendicular_application(
        f"{setup}? coll a b c"
    )

    assert application.replayed is False


def test_renderer_produces_svg() -> None:
    svg = render_isosceles_two_circle_perpendicular_chart_svg()

    assert "<svg" in svg[:512]
