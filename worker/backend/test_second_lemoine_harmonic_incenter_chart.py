from __future__ import annotations

import math
import re

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.geometry_natural_semantics import (
    extract_geometry_natural_semantics,
)
from worker.backend.second_lemoine_harmonic_incenter_chart import (
    certify_jgex_second_lemoine_harmonic_incenter_application,
    certify_second_lemoine_harmonic_incenter_chart,
    render_second_lemoine_harmonic_incenter_chart_svg,
)


SOURCE = (
    "a b c = triangle; d = foot a b c; o = circumcenter a b c; "
    "m m1 m2 g = centroid m m1 m2 g a b c; "
    "k = on_aline k a c b a g, on_aline k b a c b g; "
    "d1 = mirror d m; "
    "d2 = on_line b c, on_aline d2 a b c a d1; "
    "p = on_tline k a o, on_line a d2; "
    "x = on_line b c, on_tline k b o; "
    "y = on_line b c, on_tline k c o; "
    "i = incenter p x y ? coll i a d"
)
NATURAL = (
    "Let $ABC$ be an acute triangle with altitude $\\overline{AD}$, "
    "circumcenter $O$, and symmedian point $K$. Let $D_1$, $D_2$ be points "
    "on segment $\\overline{BC}$. Prove that the incenter $I$ of triangle "
    "$PXY$ lies on $\\overline{AD}$."
)


def test_natural_semantics_extracts_the_dropped_domain_conditions() -> None:
    semantics = extract_geometry_natural_semantics(NATURAL)

    assert semantics.has_acute_triangle(("a", "b", "c"))
    assert semantics.point_on_segment("d1", ("b", "c"))
    assert semantics.point_on_segment("d2", ("c", "b"))
    assert semantics.typed_atoms == (
        "acute(A,B,C)",
        "between(D1,B,C)",
        "between(D2,B,C)",
    )
    assert extract_geometry_natural_semantics(
        "Let ABC be an acute-angled triangle."
    ).has_acute_triangle(("a", "b", "c"))


def test_exact_chart_replays_every_identity_and_internal_branch() -> None:
    certificate = certify_second_lemoine_harmonic_incenter_chart()

    assert certificate.replayed
    assert certificate.all_conditions_discharged
    assert len(certificate.replay_residuals) == 41
    assert set(certificate.replay_residuals.values()) == {"0"}
    assert "XW_internal_branch" in certificate.domain_sign_certificate
    assert "YV_internal_branch" in certificate.domain_sign_certificate


def test_structural_application_requires_hash_bound_natural_semantics() -> None:
    accepted = certify_jgex_second_lemoine_harmonic_incenter_application(
        SOURCE, NATURAL
    )
    missing_natural = certify_jgex_second_lemoine_harmonic_incenter_application(
        SOURCE, None
    )
    missing_acute = certify_jgex_second_lemoine_harmonic_incenter_application(
        SOURCE, NATURAL.replace("an acute triangle", "a triangle")
    )

    assert accepted.replayed
    assert len(accepted.roles) == 14
    assert accepted.goal == "coll i a d"
    assert accepted.undischarged_nondegeneracy_obligations == ()
    assert not missing_natural.replayed
    assert not missing_acute.replayed


def test_bare_jgex_is_not_misreported_as_a_proof() -> None:
    without_domain = certify_jgex_with_exact_chart_portfolio(
        SOURCE, include_diagram=False
    )
    with_domain = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        include_diagram=False,
        natural_statement=NATURAL,
    )

    assert not without_domain.solved
    assert with_domain.solved
    assert not with_domain.ambiguous
    assert with_domain.selected is not None
    assert (
        with_domain.selected.chart_id
        == "second-lemoine-harmonic-pascal-incenter-altitude"
    )
    assert with_domain.selected.natural_statement_sha256


def test_nonacute_counterexample_explains_why_the_domain_is_required() -> None:
    # B=(0,0), C=(1,0), A=(0.4,0.3) is not acute at A.  The same algebraic
    # construction gives a different internal incenter, so bare JGEX is false.
    u, v = 0.4, 0.3
    s = u * u + v * v
    h = 1 - u + s
    p = (-u * (u * u - 2 * u - v * v) / h, -2 * u * v * (u - 1) / h)
    x = (s / h, 0.0)
    y = (u / h, 0.0)

    def distance(left: tuple[float, float], right: tuple[float, float]) -> float:
        return math.hypot(left[0] - right[0], left[1] - right[1])

    opposite_p = distance(x, y)
    opposite_x = distance(p, y)
    opposite_y = distance(p, x)
    denominator = opposite_p + opposite_x + opposite_y
    incenter_x = (
        opposite_p * p[0] + opposite_x * x[0] + opposite_y * y[0]
    ) / denominator

    assert not math.isclose(incenter_x, u, abs_tol=1e-9)


def test_chart_is_problem_identifier_independent_and_renders() -> None:
    certificate = certify_second_lemoine_harmonic_incenter_chart()
    serialized = str(certificate.to_dict())
    svg = render_second_lemoine_harmonic_incenter_chart_svg()

    assert "GOWACA" not in serialized
    assert "problem_id" not in serialized
    assert "expected_answer" not in serialized
    assert svg.startswith("<?xml")
    assert "<svg" in svg


def test_structural_match_survives_complete_point_renaming() -> None:
    mapping = {
        "a": "q",
        "b": "r",
        "c": "s",
        "d": "t",
        "o": "o0",
        "m": "m0",
        "m1": "m4",
        "m2": "m5",
        "g": "g0",
        "k": "k0",
        "d1": "t1",
        "d2": "t2",
        "p": "p0",
        "x": "x0",
        "y": "y0",
        "i": "i0",
    }
    renamed = SOURCE
    for old, new in sorted(mapping.items(), key=lambda item: -len(item[0])):
        renamed = re.sub(rf"\b{re.escape(old)}\b", new, renamed)
    natural = (
        "Let QRS be an acute triangle. Let T1, T2 be points on segment RS. "
        "The remaining clauses define the corresponding construction."
    )

    application = certify_jgex_second_lemoine_harmonic_incenter_application(
        renamed, natural
    )

    assert application.replayed
    assert application.roles["A"] == "q"
    assert application.roles["D2"] == "t2"
    assert application.goal == "coll i0 q t"
