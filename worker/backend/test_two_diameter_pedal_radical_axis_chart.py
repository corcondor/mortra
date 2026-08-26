from pathlib import Path
import re

import pytest
import sympy as sp

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.two_diameter_pedal_radical_axis_chart import (
    certify_jgex_two_diameter_pedal_radical_axis_application,
    certify_two_diameter_pedal_radical_axis_chart,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2011G3.jgex.txt").read_text(
    encoding="utf-8"
).strip()


def _rename_points(source: str) -> str:
    names = tuple(
        dict.fromkeys(
            re.findall(r"\b[a-z][a-z0-9_]*\b", source)
        )
    )
    reserved = {
        "quadrangle",
        "midpoint",
        "on_circle",
        "foot",
        "circumcenter",
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


def test_chart_replays_local_identities() -> None:
    certificate = certify_two_diameter_pedal_radical_axis_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 15
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_chart_matches_the_frozen_construction_without_problem_id() -> None:
    application = certify_jgex_two_diameter_pedal_radical_axis_application(SOURCE)

    assert application.replayed is True
    assert len(application.roles) == 19
    assert application.goal == "coll m k1 k2"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_chart_is_invariant_under_complete_point_renaming() -> None:
    application = certify_jgex_two_diameter_pedal_radical_axis_application(
        _rename_points(SOURCE)
    )

    assert application.replayed is True
    assert len(application.roles) == 19


def _diameter_endpoints(t: sp.Rational, h: sp.Rational) -> tuple[sp.Matrix, sp.Matrix]:
    denominator = 1 + t * t - h * h
    horizontal = (1 - t * t + h * h) / denominator
    return (
        sp.Matrix((horizontal, 2 * (h + t) / denominator)),
        sp.Matrix((-horizontal, 2 * (h - t) / denominator)),
    )


def _foot(point: sp.Matrix, left: sp.Matrix, right: sp.Matrix) -> sp.Matrix:
    direction = right - left
    parameter = sp.cancel((point - left).dot(direction) / direction.dot(direction))
    return (left + parameter * direction).applyfunc(sp.cancel)


def _circle_constant(points: tuple[sp.Matrix, ...]) -> sp.Expr | None:
    denominator = sp.det(sp.Matrix([[point[0], point[1], 1] for point in points]))
    if denominator == 0:
        return None
    numerator = sp.det(
        sp.Matrix(
            [[point[0], point[1], -point.dot(point)] for point in points]
        )
    )
    return sp.cancel(numerator / denominator)


def test_direct_power_identity_on_independent_exact_rational_samples() -> None:
    e = sp.Matrix((-1, 0))
    f = sp.Matrix((1, 0))
    samples = (
        (1, 3, 2, 5),
        (2, 5, 3, 7),
        (1, 4, 3, 8),
        (3, 7, 2, 9),
        (2, 9, 4, 11),
        (4, 9, 5, 12),
        (1, 5, 4, 13),
        (5, 11, 3, 14),
    )
    checked = 0
    for t_num, t_den, r_num, r_den in samples:
        a, b = _diameter_endpoints(
            sp.Rational(t_num, t_den), sp.Rational(1, t_den + 2)
        )
        c, d = _diameter_endpoints(
            sp.Rational(r_num, r_den), sp.Rational(2, r_den + 3)
        )
        e_circle = _circle_constant(
            (_foot(e, a, b), _foot(e, b, c), _foot(e, c, d))
        )
        f_circle = _circle_constant(
            (_foot(f, c, d), _foot(f, d, a), _foot(f, a, b))
        )
        if e_circle is None or f_circle is None:
            continue
        assert sp.cancel(e_circle - f_circle) == 0
        checked += 1
    assert checked == len(samples)


@pytest.mark.parametrize(
    "mutated",
    (
        SOURCE.replace("e2 = foot e b c", "e2 = foot e a c"),
        SOURCE.replace("m = midpoint e f", "m = midpoint e a"),
        SOURCE.replace(
            "k2 = on_circle o_e e1, on_circle o_f f1",
            "k2 = on_circle o_e e1, on_circle o_e f1",
        ),
        SOURCE.replace("? coll m k1 k2", "? coll m k1 e"),
    ),
)
def test_chart_rejects_nearby_broken_constructions(mutated: str) -> None:
    application = certify_jgex_two_diameter_pedal_radical_axis_application(mutated)

    assert application.replayed is False
    assert application.roles == {}


def test_portfolio_returns_problem_statement_proof_and_diagram() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE)

    assert result.solved is True
    assert result.conditional is False
    assert result.ambiguous is False
    assert result.selected is not None
    assert result.selected.chart_id == "two-diameter-circles-pedal-radical-axis"
    assert result.selected.identity_count == 15
    assert result.selected.proof_status == "proved"
    assert result.selected.undischarged_obligations == ()
    assert result.selected.diagram_svg is not None
    assert "<svg" in result.selected.diagram_svg[:512]
    assert "E+F=U+V" in result.selected.proof_markdown
