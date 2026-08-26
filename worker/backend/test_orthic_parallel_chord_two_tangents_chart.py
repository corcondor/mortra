from pathlib import Path
import re

import pytest
import sympy as sp

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.orthic_parallel_chord_two_tangents_chart import (
    certify_jgex_orthic_parallel_chord_two_tangents_application,
    certify_orthic_parallel_chord_two_tangents_chart,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    (ROOT / "data" / "fixtures" / "2023VietnamTSTp3.jgex.txt")
    .read_text(encoding="utf-8")
    .strip()
)


def _rename_points(source: str) -> str:
    names = tuple(dict.fromkeys(re.findall(r"\b[a-z][a-z0-9_]*\b", source)))
    reserved = {
        "triangle",
        "circumcenter",
        "foot",
        "on_line",
        "midpoint",
        "on_circle",
        "on_pline",
        "on_tline",
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


def test_chart_replays_general_parallel_chord_identity() -> None:
    certificate = certify_orthic_parallel_chord_two_tangents_chart()
    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 23
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_chart_matches_frozen_construction_without_problem_id() -> None:
    application = certify_jgex_orthic_parallel_chord_two_tangents_application(SOURCE)
    assert application.replayed is True
    assert len(application.roles) == 14
    assert application.goal == "coll x m k"


def test_chart_is_invariant_under_complete_point_renaming() -> None:
    application = certify_jgex_orthic_parallel_chord_two_tangents_application(
        _rename_points(SOURCE)
    )
    assert application.replayed is True
    assert len(application.roles) == 14


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.cancel(left[0] * right[1] - left[1] * right[0])


def _intersection(p: sp.Matrix, q: sp.Matrix, r: sp.Matrix, s: sp.Matrix) -> sp.Matrix:
    first, second = q - p, s - r
    parameter = sp.cancel(_cross(r - p, second) / _cross(first, second))
    return (p + parameter * first).applyfunc(sp.cancel)


def _foot(point: sp.Matrix, first: sp.Matrix, second: sp.Matrix) -> sp.Matrix:
    direction = second - first
    return (
        first
        + sp.cancel((point - first).dot(direction) / direction.dot(direction))
        * direction
    ).applyfunc(sp.cancel)


def _center(p: sp.Matrix, q: sp.Matrix, r: sp.Matrix) -> sp.Matrix:
    matrix = sp.Matrix([list(2 * (other - p)) for other in (q, r)])
    rhs = sp.Matrix([other.dot(other) - p.dot(p) for other in (q, r)])
    return (matrix.inv() * rhs).applyfunc(sp.cancel)


def test_direct_tangent_intersection_on_independent_rational_samples() -> None:
    samples = (
        (sp.Rational(1, 4), sp.Rational(5, 4), sp.Rational(1, 3)),
        (sp.Rational(2, 5), sp.Rational(6, 5), sp.Rational(-1, 4)),
        (sp.Rational(-1, 3), sp.Rational(7, 5), sp.Rational(2, 5)),
        (sp.Rational(3, 7), sp.Rational(4, 3), sp.Rational(-2, 7)),
        (sp.Rational(-2, 5), sp.Rational(3, 2), sp.Rational(1, 6)),
        (sp.Rational(1, 5), sp.Rational(7, 6), sp.Rational(3, 8)),
        (sp.Rational(-1, 4), sp.Rational(5, 3), sp.Rational(-3, 10)),
        (sp.Rational(2, 7), sp.Rational(8, 5), sp.Rational(1, 7)),
    )
    for u, v, t in samples:
        a, b, c = sp.Matrix((0, 0)), sp.Matrix((1, 0)), sp.Matrix((u, v))
        beta = sp.cancel((u - u**2 - v**2) / v)
        e, f = _foot(b, a, c), _foot(c, a, b)
        h = _intersection(b, e, c, f)
        m, k = ((a + h) / 2).applyfunc(sp.cancel), _foot(h, e, f)
        px = sp.cancel((1 - beta * t) / (1 + t**2))
        p = sp.Matrix((px, sp.cancel(t * px)))
        direction = c - b
        parameter = sp.symbols("sample_chord")
        point = p + parameter * direction
        expression = sp.factor(point.dot(point) - point[0] + beta * point[1])
        polynomial = sp.Poly(expression, parameter)
        other = sp.cancel(
            -polynomial.coeff_monomial(parameter)
            / polynomial.coeff_monomial(parameter**2)
        )
        q = (p + other * direction).applyfunc(sp.cancel)
        o1, o2 = _center(c, q, e), _center(b, p, f)
        te = e + sp.Matrix((-(e - o1)[1], (e - o1)[0]))
        tf = f + sp.Matrix((-(f - o2)[1], (f - o2)[0]))
        x = _intersection(e, te, f, tf)
        assert _cross(x - m, k - m) == 0


@pytest.mark.parametrize(
    "mutated",
    (
        SOURCE.replace("e = foot e b a c", "e = foot e c a b"),
        SOURCE.replace("h = on_line h b e", "h = on_line h a e"),
        SOURCE.replace(
            "q = on_circle q o a, on_pline q p b c",
            "q = on_circle q o a, on_pline q p a c",
        ),
        SOURCE.replace("o1 = circumcenter o1 c q e", "o1 = circumcenter o1 b q e"),
        SOURCE.replace("x = on_tline x e o1 e", "x = on_tline x e o2 e"),
        SOURCE.replace("? coll x m k", "? coll x m h"),
    ),
)
def test_chart_rejects_nearby_broken_constructions(mutated: str) -> None:
    application = certify_jgex_orthic_parallel_chord_two_tangents_application(mutated)
    assert application.replayed is False
    assert application.roles == {}


def test_portfolio_returns_proof_and_diagram() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE)
    assert result.solved is True
    assert result.conditional is False
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == "orthic-parallel-chord-two-tangents-collinearity"
    assert result.selected.identity_count == 23
    assert result.selected.proof_status == "proved"
    assert result.selected.diagram_svg is not None
    assert "<svg" in result.selected.diagram_svg[:512]
