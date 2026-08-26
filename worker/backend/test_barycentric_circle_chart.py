from __future__ import annotations

from worker.backend.barycentric_circle_chart import (
    certify_incenter_excenter_radical_axis_chart,
    certify_jgex_incenter_excenter_radical_axis_application,
    render_incenter_excenter_radical_axis_chart_svg,
)


def test_incenter_excenter_radical_axis_chart_replays_all_identities() -> None:
    certificate = certify_incenter_excenter_radical_axis_chart()

    assert certificate.replayed
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert certificate.side_trace == "E=(0:b^2*t:c^2*s)"
    assert len(certificate.certificate_sha256) == 64


def test_chart_is_problem_identifier_independent() -> None:
    certificate = certify_incenter_excenter_radical_axis_chart()
    serialized = str(certificate.to_dict())

    assert "2023USAMO" not in serialized
    assert "problem_id" not in serialized
    assert "expected_answer" not in serialized


def test_readable_proof_contains_the_machine_replay_boundary() -> None:
    certificate = certify_incenter_excenter_radical_axis_chart()
    markdown = certificate.to_markdown()

    assert "根軸" in markdown
    assert "等角共役" in markdown
    assert "全恒等式再生: `True`" in markdown


def test_renamed_jgex_problem_matches_the_general_chart() -> None:
    source = (
        "u v w = triangle; j = incenter u v w; "
        "ja = excenter u v w; jb = excenter v w u; jc = excenter w u v; "
        "q = circumcenter u v w; p = on_circle q u; "
        "q1 = circumcenter p j ja; q2 = circumcenter p jb jc; "
        "z = on_circle q1 p, on_circle q2 p; "
        "x = on_line p z, on_line v w "
        "? eqangle u v u p u x u w"
    )

    application = certify_jgex_incenter_excenter_radical_axis_application(source)

    assert application.replayed
    assert application.roles["D"] == "p"
    assert application.roles["E"] == "x"
    assert application.goal == "eqangle p u u v u w u x"


def test_application_rejects_a_different_goal() -> None:
    source = (
        "a b c = triangle; i = incenter a b c; "
        "ia = excenter a b c; ib = excenter b c a; ic = excenter c a b; "
        "o = circumcenter a b c; d = on_circle o a; "
        "o1 = circumcenter d i ia; o2 = circumcenter d ib ic; "
        "f = on_circle o1 d, on_circle o2 d; "
        "e = on_line d f, on_line b c ? cong a b a c"
    )

    application = certify_jgex_incenter_excenter_radical_axis_application(source)

    assert not application.replayed


def test_focus_diagram_contains_radical_axis_and_isogonal_stages() -> None:
    svg = render_incenter_excenter_radical_axis_chart_svg()

    assert svg.lstrip().startswith("<?xml")
    assert "内心・傍心を通る2円" in svg
    assert "根軸の辺上トレースと等角共役" in svg
    assert "<!-- E -->" in svg
