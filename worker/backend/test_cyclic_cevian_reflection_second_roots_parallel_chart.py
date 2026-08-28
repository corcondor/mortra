from pathlib import Path

from worker.backend.cyclic_cevian_reflection_second_roots_parallel_chart import (
    certify_cyclic_cevian_reflection_second_roots_parallel_chart,
    certify_jgex_cyclic_cevian_reflection_second_roots_parallel_application,
    render_cyclic_cevian_reflection_second_roots_parallel_chart_svg,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2020POGCHAMPp1.jgex.txt").read_text(
    encoding="utf-8"
)
NATURAL = (ROOT / "data" / "fixtures" / "2020POGCHAMPp1.natural.txt").read_text(
    encoding="utf-8"
)


def test_exact_chart_replays_known_root_reduction() -> None:
    certificate = certify_cyclic_cevian_reflection_second_roots_parallel_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 22
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert len(certificate.certificate_sha256) == 64


def test_application_matches_renamed_structure_without_problem_id() -> None:
    renamed = (
        "r s t = triangle; u = circumcenter r s t; v = on_circle u r; "
        "w = on_line r v, on_line s t; x = midpoint s t; y = mirror w x; "
        "j = circumcenter v w y; k = on_line r y, on_circle j v; "
        "l = circumcenter r k v; m = on_line r s, on_circle l r; "
        "n = on_line r t, on_circle l r; q = on_line m n, on_line k v "
        "? para r q s t"
    )
    natural = (
        "Let RY meet circle VWY again at K. Circle RKV meets RS and RT "
        "again at M and N respectively."
    )
    application = (
        certify_jgex_cyclic_cevian_reflection_second_roots_parallel_application(
            renamed,
            natural,
        )
    )

    assert application.replayed is True
    assert len(application.roles) == 14
    assert len(application.natural_semantic_atoms) == 3


def test_registry_selects_chart_and_requires_secondary_roots() -> None:
    result = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        natural_statement=NATURAL,
        include_diagram=False,
    )
    assert result.solved is True
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == (
        "cyclic-cevian-reflection-second-roots-parallel"
    )
    assert result.selected.identity_count == 22

    missing_domain = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        natural_statement="The constructed points are G, E, and F.",
        include_diagram=False,
    )
    assert missing_domain.solved is False


def test_registry_rejects_unrelated_goal() -> None:
    setup = SOURCE.rsplit("?", maxsplit=1)[0]
    unrelated = certify_jgex_with_exact_chart_portfolio(
        f"{setup}? coll a q b",
        natural_statement=NATURAL,
        include_diagram=False,
    )
    assert unrelated.solved is False


def test_chart_renders_a_nonempty_svg() -> None:
    svg = render_cyclic_cevian_reflection_second_roots_parallel_chart_svg()
    assert "<svg" in svg[:512]
    assert len(svg) > 10_000
