from itertools import product
from pathlib import Path
import re

import pytest
import sympy as sp

from worker.backend.arc_midpoint_reflection_center_axis_chart import (
    certify_arc_midpoint_reflection_center_axis_chart,
    certify_jgex_arc_midpoint_reflection_center_axis_application,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2023SAGFp8.jgex.txt").read_text(
    encoding="utf-8"
).strip()


def _rename_points(source: str) -> str:
    names = tuple(dict.fromkeys(re.findall(r"\b[a-z][a-z0-9_]*\b", source)))
    reserved = {
        "triangle",
        "circumcenter",
        "on_bline",
        "on_circle",
        "mirror",
        "reflect",
        "orthocenter",
        "para",
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


def test_chart_replays_all_independent_arc_branches() -> None:
    certificate = certify_arc_midpoint_reflection_center_axis_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 22
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_chart_matches_frozen_construction_without_problem_id() -> None:
    application = certify_jgex_arc_midpoint_reflection_center_axis_application(SOURCE)

    assert application.replayed is True
    assert len(application.roles) == 19
    assert application.goal == "para h1 o1 o h"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_chart_is_invariant_under_complete_point_renaming() -> None:
    application = certify_jgex_arc_midpoint_reflection_center_axis_application(
        _rename_points(SOURCE)
    )

    assert application.replayed is True
    assert len(application.roles) == 19


def _unit_complex(t: sp.Rational) -> sp.Expr:
    return sp.cancel((1 - t * t + 2 * sp.I * t) / (1 + t * t))


def _vector(value: sp.Expr) -> sp.Matrix:
    real, imaginary = sp.expand_complex(value).as_real_imag()
    return sp.Matrix((sp.cancel(real), sp.cancel(imaginary)))


def _complex(vector: sp.Matrix) -> sp.Expr:
    return sp.cancel(vector[0] + sp.I * vector[1])


def _reflect(point: sp.Expr, left: sp.Expr, right: sp.Expr) -> sp.Expr:
    point_v, left_v, right_v = _vector(point), _vector(left), _vector(right)
    direction = right_v - left_v
    projection = left_v + direction * (
        (point_v - left_v).dot(direction) / direction.dot(direction)
    )
    return _complex((2 * projection - point_v).applyfunc(sp.cancel))


def _circumcenter(points: tuple[sp.Expr, sp.Expr, sp.Expr]) -> sp.Matrix:
    vectors = tuple(_vector(point) for point in points)
    first = vectors[0]
    matrix = sp.Matrix([list(2 * (other - first)) for other in vectors[1:]])
    rhs = sp.Matrix(
        [other.dot(other) - first.dot(first) for other in vectors[1:]]
    )
    return (matrix.inv() * rhs).applyfunc(sp.cancel)


def test_direct_center_axis_on_all_branches_and_rational_samples() -> None:
    samples = (
        (sp.Rational(-1, 3), sp.Rational(1, 4), sp.Rational(2, 5)),
        (sp.Rational(-2, 5), sp.Rational(1, 6), sp.Rational(3, 7)),
        (sp.Rational(-1, 7), sp.Rational(2, 9), sp.Rational(4, 11)),
        (sp.Rational(-3, 8), sp.Rational(1, 5), sp.Rational(5, 12)),
    )
    checked = 0
    for tx, ty, tz in samples:
        x, y, z = _unit_complex(tx), _unit_complex(ty), _unit_complex(tz)
        a, b, c = x * x, y * y, z * z
        original_h = _vector(a + b + c)
        for sd, se, sf in product((1, -1), repeat=3):
            d, e, f = sd * y * z, se * z * x, sf * x * y
            r, s, t = -d, -e, -f
            d1, e1, f1 = (
                _reflect(d, b, c),
                _reflect(e, c, a),
                _reflect(f, a, b),
            )
            r1, s1, t1 = (
                _reflect(r, b, c),
                _reflect(s, c, a),
                _reflect(t, a, b),
            )
            first_center = _circumcenter((d1, e1, f1))
            h1 = _vector(d1 + e1 + f1) - 2 * first_center
            o1 = _circumcenter((r1, s1, t1))
            axis = h1 - o1
            cross = sp.cancel(axis[0] * original_h[1] - axis[1] * original_h[0])
            assert cross == 0
            checked += 1
    assert checked == len(samples) * 8


@pytest.mark.parametrize(
    "mutated",
    (
        SOURCE.replace("d1 = reflect d b c", "d1 = reflect d a c"),
        SOURCE.replace("r = mirror d o", "r = mirror d a"),
        SOURCE.replace("o1 = circumcenter r1 s1 t1", "o1 = circumcenter r1 s1 d1"),
        SOURCE.replace("h1 = orthocenter d1 e1 f1", "h1 = orthocenter d1 e1 r1"),
        SOURCE.replace("? para h1 o1 o h", "? para h1 o1 a h"),
    ),
)
def test_chart_rejects_nearby_broken_constructions(mutated: str) -> None:
    application = certify_jgex_arc_midpoint_reflection_center_axis_application(mutated)

    assert application.replayed is False
    assert application.roles == {}


def test_portfolio_returns_proof_and_diagram() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE)

    assert result.solved is True
    assert result.conditional is False
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == "arc-midpoint-antipode-reflection-center-axis"
    assert result.selected.identity_count == 22
    assert result.selected.proof_status == "proved"
    assert result.selected.undischarged_obligations == ()
    assert result.selected.diagram_svg is not None
    assert "<svg" in result.selected.diagram_svg[:512]
    assert "real scalar" in result.selected.proof_markdown
