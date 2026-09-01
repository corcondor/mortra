"""Exact centroid-locus area for equilateral triangles on monic cubics.

The backend derives the locus from the three-fold rotational Fourier modes of
an equilateral triangle.  Curve coefficients are input data; no solved problem
or coefficient-specific answer is stored.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

import sympy as sp

try:
    from math_os_prototype.latex_frontend import parse_latex_problem
except ImportError:
    from latex_frontend import parse_latex_problem


@dataclass(frozen=True)
class CubicCentroidLocusQuery:
    curve_expression: str
    variable: str
    output_sort: str
    lowering_certificate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_cubic_centroid_locus_query(text: str) -> CubicCentroidLocusQuery | None:
    required = ("正三角形", "重心", "軌跡", "面積")
    if not all(marker in text for marker in required):
        return None
    parsed = parse_latex_problem(text)
    x, y = sp.symbols("x y", real=True)
    expressions: list[sp.Basic] = []
    for segment in parsed.math_segments:
        if "=" not in segment:
            continue
        left, right = segment.split("=", 1)
        if left.strip() != "y":
            continue
        try:
            expressions.append(sp.sympify(right, locals={"x": x, "y": y}))
        except Exception:
            continue
    if len(expressions) != 1:
        return None
    expression = sp.expand(expressions[0])
    if expression.free_symbols != {x}:
        return None
    polynomial = sp.Poly(expression, x)
    if polynomial.degree() != 3 or polynomial.LC() not in {sp.S.One, -sp.S.One}:
        return None
    return CubicCentroidLocusQuery(
        curve_expression=str(expression),
        variable="x",
        output_sort="Area(Region2)",
        lowering_certificate={
            "kind": "equilateral_centroid_cubic_elimination",
            "curve_degree": 3,
            "leading_coefficient_isometry": str(polynomial.LC()),
            "memorized_answer": False,
        },
    )


def execute_cubic_centroid_locus_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = CubicCentroidLocusQuery(**payload)
    x = sp.symbols(query.variable, real=True)
    source_curve = sp.sympify(query.curve_expression, locals={query.variable: x})
    polynomial = sp.Poly(source_curve, x)
    leading = polynomial.LC()
    if leading == -1:
        source_curve = -source_curve
        polynomial = sp.Poly(source_curve, x)
    if polynomial.degree() != 3 or polynomial.LC() != 1:
        raise ValueError("backend requires a monic cubic up to reflection")

    quadratic_coefficient = polynomial.all_coeffs()[1]
    horizontal_shift = sp.simplify(-quadratic_coefficient / 3)
    X = sp.symbols("X", real=True)
    depressed = sp.Poly(sp.expand(source_curve.subs(x, X + horizontal_shift)), X)
    coefficients = depressed.all_coeffs()
    if len(coefficients) != 4 or coefficients[1] != 0:
        raise ValueError("failed to depress the cubic by translation")
    linear_coefficient = sp.simplify(coefficients[2])
    constant = sp.simplify(coefficients[3])

    radius_squared = sp.symbols("u", real=True)
    first_mode = sp.simplify(3 * X**2 + linear_coefficient + 3 * radius_squared / 4)
    mode_constraint = sp.factor(
        first_mode**2 + 1 - sp.Rational(9, 4) * X**2 * radius_squared
    )
    radius_branches = sp.solve(mode_constraint, radius_squared)
    if len(radius_branches) != 2:
        raise ValueError("phase elimination did not yield two radius branches")
    discriminant = sp.factor(sp.discriminant(sp.Poly(mode_constraint, radius_squared)))
    domain = sp.solve_univariate_inequality(discriminant >= 0, X, relational=False)
    intervals = bounded_intervals(domain)
    positive_intervals = [interval for interval in intervals if interval.start.is_nonnegative]
    negative_intervals = [interval for interval in intervals if interval.end.is_nonpositive]
    if len(positive_intervals) != 1 or len(negative_intervals) != 1:
        raise ValueError("the cubic does not produce the supported pair of bounded locus lobes")

    positive_interval = positive_intervals[0]
    midpoint = sp.simplify((positive_interval.start + positive_interval.end) / 2)
    if any(sp.N(branch.subs(X, midpoint)) <= 0 for branch in radius_branches):
        raise ValueError("an eliminated radius branch is not geometrically admissible")

    depressed_curve = X**3 + linear_coefficient * X + constant
    second_derivative = 6 * X
    centroid_y_branches = [
        sp.factor(
            depressed_curve
            + second_derivative * branch / 4
            - branch * (3 * X**2 + linear_coefficient + 3 * branch / 4) / second_derivative
        )
        for branch in radius_branches
    ]
    gap = sp.simplify(centroid_y_branches[1] - centroid_y_branches[0])
    if sp.N(gap.subs(X, midpoint)) < 0:
        gap = -gap
    one_lobe_area = integrate_symmetric_quadratic_radical(gap, X, positive_interval)
    total_area = sp.simplify(2 * one_lobe_area)
    if total_area.has(sp.Integral) or sp.N(total_area) <= 0:
        raise ValueError("locus area did not close to a positive exact value")

    numeric_check = numeric_lobe_integral(gap, X, positive_interval)
    if abs(float(sp.N(one_lobe_area, 30)) - numeric_check) > 1e-9:
        raise ValueError("independent numerical area check failed")
    return {
        "status": "solved",
        "query_operator": "equilateral_centroid_locus_area",
        "answer_exact": str(total_area),
        "answer_tex": rf"\({sp.latex(total_area)}\)",
        "source_curve": str(polynomial.as_expr()),
        "horizontal_shift": str(horizontal_shift),
        "depressed_linear_coefficient": str(linear_coefficient),
        "mode_constraint": str(mode_constraint),
        "radius_branches": [str(branch) for branch in radius_branches],
        "centroid_y_branches": [str(branch) for branch in centroid_y_branches],
        "x_domain": str(domain),
        "one_lobe_area": str(one_lobe_area),
        "numeric_lobe_check": numeric_check,
        "lowering_certificate": query.lowering_certificate,
        "derivation_tex": [
            "正三角形の頂点を重心のまわりに位相差 \\(2\\pi/3\\) の3点として置く。",
            "三次曲線へ代入し，3点で一致すべき一次・二次Fourierモードを消去する。",
            f"半径の二乗 \\(u\\) は \\({sp.latex(mode_constraint)}=0\\) を満たす。",
            "二つの半径枝から重心軌跡の上下境界を得て，閉じた二成分を厳密積分する。",
            f"各成分の面積は \\({sp.latex(one_lobe_area)}\\) なので，全体は \\({sp.latex(total_area)}\\) である。",
        ],
    }


def bounded_intervals(domain: sp.Set) -> list[sp.Interval]:
    candidates = list(domain.args) if isinstance(domain, sp.Union) else [domain]
    return [
        item
        for item in candidates
        if isinstance(item, sp.Interval) and item.start.is_finite and item.end.is_finite
    ]


def integrate_symmetric_quadratic_radical(
    gap: sp.Basic,
    variable: sp.Symbol,
    interval: sp.Interval,
) -> sp.Basic:
    z = sp.symbols("z", positive=True)
    lower = sp.simplify(interval.start**2)
    upper = sp.simplify(interval.end**2)
    transformed = sp.factor(gap.subs(variable, sp.sqrt(z)) / (2 * sp.sqrt(z)))
    kernel = sp.sqrt((z - lower) * (upper - z))
    rational = sp.simplify(transformed / kernel)
    constant_term = sp.simplify(sp.limit(rational, z, sp.oo))
    reciprocal_term = sp.simplify(z * (rational - constant_term))
    if z in reciprocal_term.free_symbols:
        raise ValueError("area density is outside the supported A+B/z radical form")
    first_moment = sp.pi * (upper - lower) ** 2 / 8
    reciprocal_moment = sp.pi * ((lower + upper) / 2 - sp.sqrt(lower * upper))
    return sp.simplify(constant_term * first_moment + reciprocal_term * reciprocal_moment)


def numeric_lobe_integral(gap: sp.Basic, variable: sp.Symbol, interval: sp.Interval) -> float:
    import mpmath

    function = sp.lambdify(variable, gap, "mpmath")
    value = mpmath.quad(function, [float(sp.N(interval.start)), float(sp.N(interval.end))])
    if abs(mpmath.im(value)) > mpmath.mpf("1e-20"):
        raise ValueError("numerical locus integral acquired a non-real component")
    return float(mpmath.re(value))
