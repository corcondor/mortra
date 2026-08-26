from pathlib import Path
import re

import pytest
import sympy as sp

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.three_circumcenters_radical_reflection_chart import (
    certify_jgex_three_circumcenters_radical_reflection_application,
    certify_three_circumcenters_radical_reflection_chart,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    (ROOT / "data" / "fixtures" / "2023RMMSLG3.jgex.txt")
    .read_text(encoding="utf-8")
    .strip()
)


def _rename_points(source: str) -> str:
    names = tuple(dict.fromkeys(re.findall(r"\b[a-z][a-z0-9_]*\b", source)))
    reserved = {
        "triangle",
        "free",
        "circumcenter",
        "on_circle",
        "reflect",
        "eqangle",
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


def test_chart_replays_minimal_complex_identity() -> None:
    certificate = certify_three_circumcenters_radical_reflection_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 18
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_chart_matches_frozen_construction_without_problem_id() -> None:
    application = certify_jgex_three_circumcenters_radical_reflection_application(
        SOURCE
    )

    assert application.replayed is True
    assert len(application.roles) == 12
    assert application.goal == "eqangle a b a p a q a c"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_chart_is_invariant_under_complete_point_renaming() -> None:
    application = certify_jgex_three_circumcenters_radical_reflection_application(
        _rename_points(SOURCE)
    )

    assert application.replayed is True
    assert len(application.roles) == 12


def _unit_point(t: sp.Rational) -> sp.Matrix:
    return sp.Matrix(((1 - t * t) / (1 + t * t), 2 * t / (1 + t * t)))


def _circumcenter(points: tuple[sp.Matrix, sp.Matrix, sp.Matrix]) -> sp.Matrix:
    first = points[0]
    matrix = sp.Matrix([list(2 * (other - first)) for other in points[1:]])
    rhs = sp.Matrix([other.dot(other) - first.dot(first) for other in points[1:]])
    return (matrix.inv() * rhs).applyfunc(sp.cancel)


def _complex(point: sp.Matrix) -> sp.Expr:
    return sp.cancel(point[0] + sp.I * point[1])


def test_direct_circumcenter_reflection_on_independent_rational_samples() -> None:
    samples = (
        (sp.Rational(-2, 3), sp.Rational(-1, 6), sp.Rational(3, 5)),
        (sp.Rational(-3, 4), sp.Rational(1, 8), sp.Rational(4, 7)),
        (sp.Rational(-4, 5), sp.Rational(-1, 7), sp.Rational(2, 3)),
        (sp.Rational(-5, 7), sp.Rational(1, 9), sp.Rational(5, 8)),
        (sp.Rational(-3, 5), sp.Rational(-1, 9), sp.Rational(7, 10)),
        (sp.Rational(-7, 9), sp.Rational(1, 10), sp.Rational(3, 4)),
        (sp.Rational(-5, 8), sp.Rational(-2, 11), sp.Rational(4, 5)),
        (sp.Rational(-8, 11), sp.Rational(1, 12), sp.Rational(5, 7)),
    )
    checked = 0
    for ta, tb, tc in samples:
        a, b, c = map(_unit_point, (ta, tb, tc))
        p = ((a + b + c) / 3).applyfunc(sp.cancel)
        o1 = _circumcenter((a, p, b))
        o2 = _circumcenter((b, p, c))
        o3 = _circumcenter((c, p, a))
        og = _circumcenter((o1, o2, o3))
        radius_squared = sp.cancel((o1 - og).dot(o1 - og))

        # Subtract the unit-circle equation from the three-center circle.
        normal = -2 * og
        constant = sp.cancel(og.dot(og) - radius_squared + 1)
        assert sp.cancel(normal.dot(normal) - constant**2) > 0
        parameter = sp.cancel((normal.dot(p) + constant) / normal.dot(normal))
        q = (p - 2 * parameter * normal).applyfunc(sp.cancel)

        ratio = sp.cancel(
            (_complex(p) - _complex(a))
            * (_complex(q) - _complex(a))
            / ((_complex(b) - _complex(a)) * (_complex(c) - _complex(a)))
        )
        assert sp.simplify(sp.im(sp.expand_complex(ratio))) == 0
        checked += 1
    assert checked == len(samples)


@pytest.mark.parametrize(
    "mutated",
    (
        SOURCE.replace("o2 = circumcenter o2 b p c", "o2 = circumcenter o2 a p c"),
        SOURCE.replace(
            "o_g = circumcenter o_g o1 o2 o3", "o_g = circumcenter o_g o1 o2 a"
        ),
        SOURCE.replace("x = on_circle x o a", "x = on_circle x o b"),
        SOURCE.replace("q = reflect q p x y", "q = reflect q a x y"),
        SOURCE.replace("? eqangle a b a p a q a c", "? eqangle a b a p b q b c"),
    ),
)
def test_chart_rejects_nearby_broken_constructions(mutated: str) -> None:
    application = certify_jgex_three_circumcenters_radical_reflection_application(
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
        == "three-circumcenters-radical-axis-reflection-isogonal"
    )
    assert result.selected.identity_count == 18
    assert result.selected.proof_status == "proved"
    assert result.selected.undischarged_obligations == ()
    assert result.selected.diagram_svg is not None
    assert "<svg" in result.selected.diagram_svg[:512]
    assert "cross-ratio" in result.selected.proof_markdown
