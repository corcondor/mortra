from pathlib import Path
import re

import pytest
import sympy as sp

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.incircle_gergonne_three_circumcenters_chart import (
    certify_incircle_gergonne_three_circumcenters_chart,
    certify_jgex_incircle_gergonne_three_circumcenters_application,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    (ROOT / "data" / "fixtures" / "ShuZhiMiGeo635.jgex.txt")
    .read_text(encoding="utf-8")
    .strip()
)


def _rename_points(source: str) -> str:
    names = tuple(dict.fromkeys(re.findall(r"\b[a-z][a-z0-9_]*\b", source)))
    reserved = {
        "triangle",
        "incenter",
        "foot",
        "on_line",
        "circumcenter",
        "on_circle",
        "centroid",
        "coll",
    }
    mapping = {
        name: f"point_{index}"
        for index, name in enumerate(name for name in names if name not in reserved)
    }
    return re.sub(
        r"\b[a-z][a-z0-9_]*\b",
        lambda match: mapping.get(match.group(0), match.group(0)),
        source,
    )


def test_chart_replays_two_parameter_incircle_identity() -> None:
    certificate = certify_incircle_gergonne_three_circumcenters_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 30
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_chart_matches_frozen_construction_without_problem_id() -> None:
    application = certify_jgex_incircle_gergonne_three_circumcenters_application(SOURCE)

    assert application.replayed is True
    assert len(application.roles) == 16
    assert application.goal == "coll g i k"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_chart_is_invariant_under_complete_point_renaming() -> None:
    application = certify_jgex_incircle_gergonne_three_circumcenters_application(
        _rename_points(SOURCE)
    )

    assert application.replayed is True
    assert len(application.roles) == 16


def _unit_point(t: sp.Rational) -> sp.Matrix:
    return sp.Matrix(((1 - t * t) / (1 + t * t), 2 * t / (1 + t * t)))


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.cancel(left[0] * right[1] - left[1] * right[0])


def _intersection(p: sp.Matrix, q: sp.Matrix, r: sp.Matrix, s: sp.Matrix) -> sp.Matrix:
    direction = q - p
    other = s - r
    parameter = sp.cancel(_cross(r - p, other) / _cross(direction, other))
    return (p + parameter * direction).applyfunc(sp.cancel)


def _circle(p: sp.Matrix, q: sp.Matrix, r: sp.Matrix) -> tuple[sp.Expr, ...]:
    x, y, w = sp.symbols("sample_x sample_y sample_w")
    solution = sp.solve(
        [point.dot(point) + x * point[0] + y * point[1] + w for point in (p, q, r)],
        (x, y, w),
        dict=True,
        simplify=False,
    )[0]
    return tuple(sp.cancel(solution[symbol]) for symbol in (x, y, w))


def _second(
    known: sp.Matrix, line_point: sp.Matrix, circle: tuple[sp.Expr, ...]
) -> sp.Matrix:
    parameter = sp.symbols("sample_parameter")
    direction = line_point - known
    point = known + parameter * direction
    expression = sp.factor(
        point.dot(point) + circle[0] * point[0] + circle[1] * point[1] + circle[2]
    )
    polynomial = sp.Poly(expression, parameter)
    other = sp.cancel(
        -polynomial.coeff_monomial(parameter) / polynomial.coeff_monomial(parameter**2)
    )
    return (known + other * direction).applyfunc(sp.cancel)


def _center(p: sp.Matrix, q: sp.Matrix, r: sp.Matrix) -> sp.Matrix:
    matrix = sp.Matrix([list(2 * (other - p)) for other in (q, r)])
    rhs = sp.Matrix([other.dot(other) - p.dot(p) for other in (q, r)])
    return (matrix.inv() * rhs).applyfunc(sp.cancel)


def test_direct_centroid_collinearity_on_independent_rational_samples() -> None:
    samples = (
        (sp.Rational(1, 3), sp.Rational(2, 3)),
        (sp.Rational(1, 4), sp.Rational(3, 5)),
        (sp.Rational(2, 5), sp.Rational(4, 7)),
        (sp.Rational(-1, 4), sp.Rational(2, 3)),
        (sp.Rational(-2, 5), sp.Rational(3, 4)),
        (sp.Rational(1, 6), sp.Rational(5, 8)),
        (sp.Rational(-1, 5), sp.Rational(4, 9)),
        (sp.Rational(2, 7), sp.Rational(5, 6)),
    )
    checked = 0
    for u, v in samples:
        d = sp.Matrix((1, 0))
        e, f = _unit_point(u), _unit_point(v)
        a = sp.Matrix(((1 - u * v) / (1 + u * v), (u + v) / (1 + u * v)))
        b, c = sp.Matrix((1, v)), sp.Matrix((1, u))
        k = _intersection(a, d, b, e)
        assert _cross(k - c, f - c) == 0
        omega = _circle(a, b, c)
        x, y, z = (_second(a, k, omega), _second(b, k, omega), _second(c, k, omega))
        oa, ob, oc = _center(y, k, z), _center(z, k, x), _center(x, k, y)
        g = ((oa + ob + oc) / 3).applyfunc(sp.cancel)
        assert _cross(g, k) == 0
        checked += 1
    assert checked == len(samples)


@pytest.mark.parametrize(
    "mutated",
    (
        SOURCE.replace(
            "k = on_line k a d, on_line k b e", "k = on_line k a e, on_line k b d"
        ),
        SOURCE.replace("x = on_line x a k", "x = on_line x b k"),
        SOURCE.replace("oa = circumcenter oa y k z", "oa = circumcenter oa y k x"),
        SOURCE.replace("ob = circumcenter ob z k x", "ob = circumcenter ob z a x"),
        SOURCE.replace("centroid m1 m2 m3 g oa ob oc", "centroid m1 m2 m3 g oa ob o"),
        SOURCE.replace("? coll g i k", "? coll g i a"),
    ),
)
def test_chart_rejects_nearby_broken_constructions(mutated: str) -> None:
    application = certify_jgex_incircle_gergonne_three_circumcenters_application(
        mutated
    )

    assert application.replayed is False
    assert application.roles == {}


def test_portfolio_returns_proof_and_diagram() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE)

    assert result.solved is True
    assert result.conditional is False
    assert result.ambiguous is False
    assert result.selected is not None
    assert (
        result.selected.chart_id
        == "incircle-gergonne-three-circumcenters-centroid-axis"
    )
    assert result.selected.identity_count == 30
    assert result.selected.proof_status == "proved"
    assert result.selected.undischarged_obligations == ()
    assert result.selected.diagram_svg is not None
    assert "<svg" in result.selected.diagram_svg[:512]
    assert "scalar" in result.selected.proof_markdown
