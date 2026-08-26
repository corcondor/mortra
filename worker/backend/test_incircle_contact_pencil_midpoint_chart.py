from pathlib import Path
import re

import pytest
import sympy as sp

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.incircle_contact_pencil_midpoint_chart import (
    certify_incircle_contact_pencil_midpoint_chart,
    certify_jgex_incircle_contact_pencil_midpoint_application,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2016USATSTSTp6.jgex.txt").read_text(
    encoding="utf-8"
).strip()


def _rename_points(source: str) -> str:
    names = tuple(dict.fromkeys(re.findall(r"\b[a-z][a-z0-9_]*\b", source)))
    reserved = {
        "triangle",
        "incenter",
        "foot",
        "circumcenter",
        "on_circle",
        "midpoint",
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


def test_chart_replays_minimal_two_parameter_identity() -> None:
    certificate = certify_incircle_contact_pencil_midpoint_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 22
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_chart_matches_frozen_construction_without_problem_id() -> None:
    application = certify_jgex_incircle_contact_pencil_midpoint_application(SOURCE)

    assert application.replayed is True
    assert len(application.roles) == 19
    assert application.goal == "coll m p1 p2"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_chart_is_invariant_under_complete_point_renaming() -> None:
    application = certify_jgex_incircle_contact_pencil_midpoint_application(
        _rename_points(SOURCE)
    )

    assert application.replayed is True
    assert len(application.roles) == 19


def _unit_point(t: sp.Rational) -> sp.Matrix:
    return sp.Matrix(((1 - t * t) / (1 + t * t), 2 * t / (1 + t * t)))


def _tangent_intersection(left: sp.Matrix, right: sp.Matrix) -> sp.Matrix:
    matrix = sp.Matrix(((left[0], left[1]), (right[0], right[1])))
    return matrix.inv() * sp.ones(2, 1)


def _circle_through_origin(first: sp.Matrix, second: sp.Matrix) -> sp.Matrix:
    matrix = sp.Matrix(((first[0], first[1]), (second[0], second[1])))
    rhs = sp.Matrix((-first.dot(first), -second.dot(second)))
    return matrix.inv() * rhs


def _foot(point: sp.Matrix, left: sp.Matrix, right: sp.Matrix) -> sp.Matrix:
    direction = right - left
    parameter = sp.cancel((point - left).dot(direction) / direction.dot(direction))
    return (left + parameter * direction).applyfunc(sp.cancel)


def test_direct_equal_power_identity_on_independent_rational_samples() -> None:
    samples = (
        (sp.Rational(-1, 3), sp.Rational(2, 5)),
        (sp.Rational(-2, 5), sp.Rational(1, 4)),
        (sp.Rational(1, 5), sp.Rational(3, 7)),
        (sp.Rational(-3, 8), sp.Rational(2, 9)),
        (sp.Rational(2, 7), sp.Rational(4, 9)),
        (sp.Rational(-1, 6), sp.Rational(5, 8)),
        (sp.Rational(-4, 9), sp.Rational(3, 10)),
        (sp.Rational(1, 7), sp.Rational(5, 11)),
    )
    d = sp.Matrix((1, 0))
    for u, v in samples:
        e, f = _unit_point(u), _unit_point(v)
        a = _tangent_intersection(e, f)
        b = _tangent_intersection(f, d)
        c = _tangent_intersection(d, e)
        k = _foot(d, e, f)
        m = (d + k) / 2

        g_b = _circle_through_origin(a, c)
        g_c = _circle_through_origin(a, b)

        def gamma(point: sp.Matrix) -> sp.Expr:
            return sp.cancel(point.dot(point) - 1)

        def chord(g: sp.Matrix, point: sp.Matrix) -> sp.Expr:
            return sp.cancel(g.dot(point) + 1)

        power_b = gamma(m) - gamma(b) * chord(g_b, m) / chord(g_b, b)
        power_c = gamma(m) - gamma(c) * chord(g_c, m) / chord(g_c, c)
        assert sp.cancel(power_b - power_c) == 0


@pytest.mark.parametrize(
    "mutated",
    (
        SOURCE.replace("k = foot d e f", "k = foot d a f"),
        SOURCE.replace("o1 = circumcenter a i b", "o1 = circumcenter a i c"),
        SOURCE.replace(
            "c2 = on_circle o1 a, on_circle i d",
            "c2 = on_circle o1 a, on_circle o1 a",
        ),
        SOURCE.replace("m = midpoint d k", "m = midpoint d e"),
        SOURCE.replace("? coll m p1 p2", "? coll m p1 b"),
    ),
)
def test_chart_rejects_nearby_broken_constructions(mutated: str) -> None:
    application = certify_jgex_incircle_contact_pencil_midpoint_application(mutated)

    assert application.replayed is False
    assert application.roles == {}


def test_portfolio_returns_proof_and_diagram() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE)

    assert result.solved is True
    assert result.conditional is False
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == "incircle-contact-circle-pencil-midpoint-radical-axis"
    assert result.selected.identity_count == 22
    assert result.selected.proof_status == "proved"
    assert result.selected.undischarged_obligations == ()
    assert result.selected.diagram_svg is not None
    assert "<svg" in result.selected.diagram_svg[:512]
    assert "circle-pencil" in result.selected.proof_markdown
