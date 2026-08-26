from worker.backend.intersecting_chords_three_circles_chart import (
    certify_intersecting_chords_three_circles_chart,
    certify_jgex_intersecting_chords_three_circles_application,
    render_intersecting_chords_three_circles_chart_svg,
)


SOURCE = (
    "a b c = triangle; d = on_circum a b c; o = circumcenter a b c; "
    "p = on_line a c, on_line b d; o1 = on_bline p b; o2 = on_bline p a; "
    "q = on_circle o1 p, on_circle o2 p; "
    "e = on_circle o1 p, on_circle o a; "
    "f = on_circle o2 p, on_circle o a; "
    "x = on_line p q, on_line c e ? coll d f x"
)


def test_exact_chart_replays_without_numeric_orientation_guards() -> None:
    certificate = certify_intersecting_chords_three_circles_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.replay_residuals["goal_D_F_X_collinear"] == "0"


def test_application_matches_construction_graph() -> None:
    application = certify_jgex_intersecting_chords_three_circles_application(SOURCE)

    assert application.replayed is True
    assert application.undischarged_nondegeneracy_obligations == ()
    assert len(application.roles) == 12


def test_application_is_invariant_under_point_renaming() -> None:
    renamed = (
        "u v w = triangle; h = on_circum u v w; k = circumcenter u v w; "
        "j = on_line u w, on_line v h; m = on_bline j v; n = on_bline j u; "
        "q1 = on_circle m j, on_circle n j; "
        "e1 = on_circle m j, on_circle k u; "
        "f1 = on_circle n j, on_circle k u; "
        "x1 = on_line j q1, on_line w e1 ? coll h f1 x1"
    )
    application = certify_jgex_intersecting_chords_three_circles_application(renamed)

    assert application.replayed is True
    assert application.roles["X"] == "x1"


def test_application_rejects_a_different_goal() -> None:
    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    application = certify_jgex_intersecting_chords_three_circles_application(
        f"{setup}? perp a b c b"
    )

    assert application.replayed is False


def test_renderer_produces_svg() -> None:
    svg = render_intersecting_chords_three_circles_chart_svg()

    assert "<svg" in svg[:512]
