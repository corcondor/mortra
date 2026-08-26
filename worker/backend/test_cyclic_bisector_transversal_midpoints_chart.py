from itertools import product
from pathlib import Path
import re

import pytest
import sympy as sp

from worker.backend.cyclic_bisector_transversal_midpoints_chart import (
    certify_cyclic_bisector_transversal_midpoints_chart,
    certify_jgex_cyclic_bisector_transversal_midpoints_application,
)
from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    (ROOT / "data" / "fixtures" / "2016CTSTp5.jgex.txt")
    .read_text(encoding="utf-8")
    .strip()
)


def _rename_points(source: str) -> str:
    names = tuple(dict.fromkeys(re.findall(r"\b[a-z][a-z0-9_]*\b", source)))
    reserved = {
        "triangle",
        "on_circum",
        "circumcenter",
        "angle_bisector",
        "on_line",
        "midpoint",
        "perp",
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


def test_chart_replays_all_arc_midpoint_branches() -> None:
    certificate = certify_cyclic_bisector_transversal_midpoints_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 20
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_chart_matches_frozen_construction_without_problem_id() -> None:
    application = certify_jgex_cyclic_bisector_transversal_midpoints_application(SOURCE)

    assert application.replayed is True
    assert len(application.roles) == 13
    assert application.goal == "perp m o n o"
    assert application.undischarged_nondegeneracy_obligations == ()


def test_chart_is_invariant_under_complete_point_renaming() -> None:
    application = certify_jgex_cyclic_bisector_transversal_midpoints_application(
        _rename_points(SOURCE)
    )

    assert application.replayed is True
    assert len(application.roles) == 13


def _unit_complex(t: sp.Rational) -> sp.Expr:
    return sp.cancel((1 - t * t + 2 * sp.I * t) / (1 + t * t))


def _vector(value: sp.Expr) -> sp.Matrix:
    real, imaginary = sp.expand_complex(value).as_real_imag()
    return sp.Matrix((sp.cancel(real), sp.cancel(imaginary)))


def _intersection(
    first_left: sp.Matrix,
    first_right: sp.Matrix,
    second_left: sp.Matrix,
    second_right: sp.Matrix,
) -> sp.Matrix:
    first_direction = first_right - first_left
    second_direction = second_right - second_left
    system = sp.Matrix.hstack(first_direction, -second_direction)
    parameter = system.inv() * (second_left - first_left)
    return (first_left + parameter[0] * first_direction).applyfunc(sp.cancel)


def test_direct_euclidean_identity_on_independent_rational_samples() -> None:
    samples = (
        (
            sp.Rational(-2, 5),
            sp.Rational(-1, 8),
            sp.Rational(1, 5),
            sp.Rational(3, 5),
        ),
        (
            sp.Rational(-3, 7),
            sp.Rational(-1, 6),
            sp.Rational(2, 9),
            sp.Rational(4, 7),
        ),
        (
            sp.Rational(-1, 2),
            sp.Rational(-2, 11),
            sp.Rational(1, 7),
            sp.Rational(5, 8),
        ),
        (
            sp.Rational(-4, 9),
            sp.Rational(-1, 9),
            sp.Rational(3, 10),
            sp.Rational(7, 10),
        ),
    )
    checked = 0
    for tx, ty, tz, tw in samples:
        x, y, z, w = map(_unit_complex, (tx, ty, tz, tw))
        a, b, c, d = map(_vector, (x * x, y * y, z * z, w * w))
        for sign_i, sign_j in product((1, -1), repeat=2):
            u = _vector(sign_i * y * w)
            v = _vector(sign_j * x * z)
            point_i = _intersection(a, u, c, -u)
            point_j = _intersection(b, v, d, -v)
            point_p = _intersection(point_i, point_j, a, b)
            point_q = _intersection(point_i, point_j, b, c)
            point_r = _intersection(point_i, point_j, c, d)
            point_s = _intersection(point_i, point_j, d, a)
            point_m = (point_p + point_r) / 2
            point_n = (point_q + point_s) / 2
            assert sp.cancel(point_m.dot(point_n)) == 0
            checked += 1
    assert checked == len(samples) * 4


@pytest.mark.parametrize(
    "mutated",
    (
        SOURCE.replace("angle_bisector i b c d", "angle_bisector i a c d"),
        SOURCE.replace("on_line p a b", "on_line p a c"),
        SOURCE.replace("on_line r c d", "on_line r b d"),
        SOURCE.replace("m = midpoint m p r", "m = midpoint m p q"),
        SOURCE.replace("? perp m o n o", "? perp m o p o"),
    ),
)
def test_chart_rejects_nearby_broken_constructions(mutated: str) -> None:
    application = certify_jgex_cyclic_bisector_transversal_midpoints_application(
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
        == "cyclic-opposite-bisectors-transversal-midpoints-perpendicular"
    )
    assert result.selected.identity_count == 20
    assert result.selected.proof_status == "proved"
    assert result.selected.undischarged_obligations == ()
    assert result.selected.diagram_svg is not None
    assert "<svg" in result.selected.diagram_svg[:512]
    assert "arc-midpoint" in result.selected.proof_markdown
