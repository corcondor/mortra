from pathlib import Path
import json
import re

import pytest
import sympy as sp

from worker.backend.exact_geometry_chart_portfolio import (
    certify_jgex_with_exact_chart_portfolio,
)
from worker.backend.midpoint_bisector_equal_power_chart import (
    certify_jgex_midpoint_bisector_equal_power_application,
    certify_midpoint_bisector_equal_power_chart,
)


ROOT = Path(__file__).resolve().parents[2]
SOURCE = (ROOT / "data" / "fixtures" / "2019IranTSTp15.jgex.txt").read_text(
    encoding="utf-8"
).strip()
NATURAL = json.loads(
    (ROOT / "data" / "hageo-409-natural-language-2026-08-26.json").read_text(
        encoding="utf-8"
    )
)["2019IranTSTp15"]


def _rename_points(source: str) -> str:
    names = tuple(dict.fromkeys(re.findall(r"\b[a-z][a-z0-9_]*\b", source)))
    reserved = {
        "triangle",
        "mirror",
        "on_line",
        "angle_bisector",
        "midpoint",
        "foot",
        "circumcenter",
        "on_circle",
        "coll",
    }
    mapping = {
        name: f"node_{index}"
        for index, name in enumerate(name for name in names if name not in reserved)
    }
    return re.sub(
        r"\b[a-z][a-z0-9_]*\b",
        lambda match: mapping.get(match.group(0), match.group(0)),
        source,
    )


def _cross(left: sp.Matrix, right: sp.Matrix) -> sp.Expr:
    return sp.det(sp.Matrix.hstack(left, right))


def _intersection(
    first: sp.Matrix,
    first_direction: sp.Matrix,
    second: sp.Matrix,
    second_direction: sp.Matrix,
) -> sp.Matrix:
    parameter = sp.cancel(
        _cross(second - first, second_direction)
        / _cross(first_direction, second_direction)
    )
    return (first + parameter * first_direction).applyfunc(sp.cancel)


def _circle_coefficients(
    first: sp.Matrix,
    second: sp.Matrix,
    third: sp.Matrix,
) -> sp.Matrix:
    matrix = sp.Matrix(
        [
            [first[0], first[1], 1],
            [second[0], second[1], 1],
            [third[0], third[1], 1],
        ]
    )
    right = -sp.Matrix((first.dot(first), second.dot(second), third.dot(third)))
    return matrix.inv() * right


def _power(point: sp.Matrix, coefficients: sp.Matrix) -> sp.Expr:
    return sp.cancel(
        point.dot(point)
        + coefficients[0] * point[0]
        + coefficients[1] * point[1]
        + coefficients[2]
    )


def test_chart_replays_all_local_identities() -> None:
    certificate = certify_midpoint_bisector_equal_power_chart()

    assert certificate.replayed is True
    assert certificate.all_conditions_discharged is True
    assert len(certificate.replay_residuals) == 24
    assert set(certificate.replay_residuals.values()) == {"0"}


def test_chart_matches_structure_without_problem_id() -> None:
    application = certify_jgex_midpoint_bisector_equal_power_application(SOURCE)

    assert application.replayed is True
    assert len(application.roles) == 16
    assert application.goal == "coll x h l"
    assert application.formalization_repair_required is True
    assert "l != h" in application.repaired_quantified_goal


def test_natural_second_intersection_elaborates_without_repair() -> None:
    application = certify_jgex_midpoint_bisector_equal_power_application(
        SOURCE,
        NATURAL,
    )

    assert application.replayed is True
    assert application.formalization_repair_required is False
    assert any(
        atom.startswith("second_circle_intersection(")
        for atom in application.natural_semantic_atoms
    )


def test_chart_is_invariant_under_complete_point_renaming() -> None:
    application = certify_jgex_midpoint_bisector_equal_power_application(
        _rename_points(SOURCE)
    )

    assert application.replayed is True
    assert len(application.roles) == 16


def test_two_circle_power_identity_on_64_independent_rational_samples() -> None:
    checked = 0
    for side_b in (sp.Rational(2), sp.Rational(3), sp.Rational(5), sp.Rational(7)):
        for side_c in (sp.Rational(4), sp.Rational(6), sp.Rational(8), sp.Rational(9)):
            if side_b == side_c:
                continue
            for tangent in (
                sp.Rational(1, 3),
                sp.Rational(2, 5),
                sp.Rational(3, 7),
                sp.Rational(4, 9),
            ):
                denominator = 1 + tangent**2
                cosine = (1 - tangent**2) / denominator
                sine = 2 * tangent / denominator
                k = sp.Matrix((0, 0))
                b = sp.Matrix((side_b * cosine, side_b * sine))
                c = sp.Matrix((side_c * cosine, -side_c * sine))
                a = sp.Matrix(
                    (-2 * side_b * side_c * cosine / (side_b + side_c), 0)
                )
                m = (b + c) / 2
                n = (c + a) / 2
                p = (a + b) / 2
                e = _intersection(m, n - m, k, b - k)
                f = _intersection(m, p - m, k, c - k)
                x = _intersection(m, k - m, e, f - e)
                h = (
                    b
                    + (c - b)
                    * sp.cancel((a - b).dot(c - b) / (c - b).dot(c - b))
                ).applyfunc(sp.cancel)
                first_circle = _circle_coefficients(a, k, h)
                second_circle = _circle_coefficients(h, e, f)
                assert sp.cancel(_power(x, first_circle) - _power(x, second_circle)) == 0
                checked += 1
    assert checked == 64


@pytest.mark.parametrize(
    "mutated",
    (
        SOURCE.replace("n = midpoint c a", "n = midpoint c b"),
        SOURCE.replace("e = on_line m n, on_line b k", "e = on_line m p, on_line b k"),
        SOURCE.replace("h = foot a b c", "h = foot k b c"),
        SOURCE.replace("o2 = circumcenter h e f", "o2 = circumcenter k e f"),
        SOURCE.replace("x = on_line m k, on_line e f", "x = on_line m a, on_line e f"),
        SOURCE.replace("? coll x h l", "? coll x a l"),
    ),
)
def test_chart_rejects_nearby_broken_constructions(mutated: str) -> None:
    application = certify_jgex_midpoint_bisector_equal_power_application(mutated)

    assert application.replayed is False
    assert application.roles == {}


def test_portfolio_returns_natural_proof_but_not_raw_frozen_admission() -> None:
    result = certify_jgex_with_exact_chart_portfolio(SOURCE)

    assert result.solved is True
    assert result.conditional is False
    assert result.ambiguous is False
    assert result.strict_frozen_score_eligible is False
    assert result.selected is not None
    assert result.selected.chart_id == "midpoint-bisector-two-circles-equal-power"
    assert result.selected.identity_count == 24
    assert result.selected.application["formalization_repair_required"] is True
    assert "量化監査" in result.selected.proof_markdown
    assert result.selected.diagram_svg is not None
    assert "<svg" in result.selected.diagram_svg[:512]


def test_portfolio_accepts_hash_bound_typed_second_root() -> None:
    result = certify_jgex_with_exact_chart_portfolio(
        SOURCE,
        natural_statement=NATURAL,
        include_diagram=False,
    )

    assert result.solved is True
    assert result.selected is not None
    assert result.selected.application["formalization_repair_required"] is False
    assert "量化監査" not in result.selected.proof_markdown
