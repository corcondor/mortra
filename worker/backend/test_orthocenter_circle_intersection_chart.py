from __future__ import annotations

from worker.backend.orthocenter_circle_intersection_chart import (
    certify_jgex_orthocenter_circle_chart_application,
    certify_orthocenter_circle_intersection_chart,
    render_orthocenter_circle_chart_svg,
)


def test_exact_chart_replays_every_construction_and_final_incidence() -> None:
    certificate = certify_orthocenter_circle_intersection_chart()

    assert certificate.replayed
    assert len(certificate.replay_residuals) == 26
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.replay_residuals["K_as_positive_domain_quadratic"] == "0"
    assert certificate.replay_residuals["K_completed_square_for_A_gt_1"] == "0"
    assert certificate.all_conditions_discharged
    assert certificate.source_branch_counterexample["replayed"]
    assert len(certificate.certificate_sha256) == 64


def test_chart_is_problem_identifier_and_expected_answer_independent() -> None:
    certificate = certify_orthocenter_circle_intersection_chart()
    serialized = str(certificate.to_dict())

    assert "2016USATSTST" not in serialized
    assert "problem_id" not in serialized
    assert "expected_answer" not in serialized


def test_renamed_jgex_construction_matches_the_general_chart() -> None:
    source = (
        "u v w = triangle; hh = orthocenter u v w; "
        "oo = circumcenter u v w; mm = midpoint u hh; nn = midpoint v w; "
        "gg = on_circle mm u, on_circle oo u; "
        "qq = on_line u nn, on_circle mm u; "
        "pp = on_tline gg mm gg, on_line oo mm; "
        "z1 = circumcenter gg nn qq; z2 = circumcenter mm v w; "
        "tt = on_circle z1 gg, on_circle z2 mm ? coll nn pp tt"
    )

    application = certify_jgex_orthocenter_circle_chart_application(source)

    assert application.replayed
    assert application.roles["T"] == "tt"
    assert application.goal == "coll nn pp tt"
    assert len(application.matched_constructions) == 6
    assert application.source_formalization_status == "branch_quantifier_mismatch"
    assert application.formalization_repair_required
    assert application.natural_statement_proved
    assert not application.arbitrary_source_branch_proved
    assert application.undischarged_nondegeneracy_obligations == ()


def test_application_rejects_a_different_goal() -> None:
    source = (
        "a b c = triangle; h = orthocenter a b c; "
        "o = circumcenter a b c; m = midpoint a h; n = midpoint b c; "
        "g = on_circle m a, on_circle o a; "
        "q = on_line a n, on_circle m a; "
        "p = on_tline g m g, on_line o m; "
        "o1 = circumcenter g n q; o2 = circumcenter m b c; "
        "t = on_circle o1 g, on_circle o2 m ? cong n p n t"
    )

    application = certify_jgex_orthocenter_circle_chart_application(source)

    assert not application.replayed


def test_proof_focus_diagram_contains_both_stages_and_target_points() -> None:
    svg = render_orthocenter_circle_chart_svg()

    assert svg.lstrip().startswith("<?xml")
    assert "構成" in svg
    assert "証明に使う2円と直線" in svg
    assert "<!-- T -->" in svg
