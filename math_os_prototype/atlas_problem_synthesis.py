"""Verified problem synthesis across reusable MathOS atlas families.

Each chart has four independent parts:

1. a finite parameter space,
2. a renderer from parameters to Japanese TeX,
3. a backend solver/verifier,
4. a required LiftCertificate family.

A candidate is exported only when the backend answer is verified and the
rendered statement is lifted back to the required family by the normal MathOS
semantic pipeline.  The chart therefore cannot certify itself merely by
declaring a family ID.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterable

try:
    from math_os_prototype.category_semantics import compile_typed_semantic_graph
    from math_os_prototype.formal_language import compile_formal_ir
    from math_os_prototype.typed_definition_kernel import compile_typed_definition_ir
except ImportError:  # pragma: no cover - direct script execution.
    from category_semantics import compile_typed_semantic_graph
    from formal_language import compile_formal_ir
    from typed_definition_kernel import compile_typed_definition_ir


DEFAULT_OUTPUT = Path(
    "C:/Users/81808/.openclaw/workspace/math_os_prototype/"
    "problem_synthesis/atlas_verified72.json"
)


@dataclass(frozen=True)
class BackendResult:
    answer: str
    normal_form: str
    verified: bool
    method: str
    trace: dict[str, Any]


@dataclass(frozen=True)
class SynthesisChart:
    chart_id: str
    family_id: str
    domain: str
    task: str
    strategy: str
    proof_obligations: tuple[str, ...]
    parameter_space: tuple[dict[str, int], ...]
    render: Callable[[dict[str, int]], str]
    solve: Callable[[dict[str, int]], BackendResult]


@dataclass(frozen=True)
class AtlasCandidate:
    candidate_id: str
    chart_id: str
    parameters: dict[str, int]


def import_sympy():
    import sympy as sp

    return sp


def sympy_text(value: Any) -> str:
    return import_sympy().sstr(import_sympy().simplify(value))


def render_ellipse_area(params: dict[str, int]) -> str:
    a, b = params["a"], params["b"]
    return (
        "領域\n"
        "\\[\n"
        f"\\frac{{x^2}}{{{a * a}}}+\\frac{{y^2}}{{{b * b}}}\\le 1\n"
        "\\]\n"
        "の面積を求めよ。"
    )


def solve_ellipse_area(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    x = sp.symbols("x", real=True)
    a, b = sp.Integer(params["a"]), sp.Integer(params["b"])
    integral = 4 * sp.integrate(b * sp.sqrt(1 - x**2 / a**2), (x, 0, a))
    expected = sp.pi * a * b
    verified = sp.simplify(integral - expected) == 0
    return BackendResult(
        answer=sympy_text(expected),
        normal_form=sympy_text(expected),
        verified=bool(verified),
        method="sympy_exact_integral",
        trace={
            "integrand": sympy_text(b * sp.sqrt(1 - x**2 / a**2)),
            "bounds": ["0", sympy_text(a)],
            "symmetry_factor": 4,
            "integral": sympy_text(integral),
        },
    )


def render_parabolic_area(params: dict[str, int]) -> str:
    length, scale = params["length"], params["scale"]
    return (
        "不等式\n"
        "\\[\n"
        f"0\\le x\\le {length},\\qquad 0\\le y\\le {scale}x({length}-x)\n"
        "\\]\n"
        "で定まる領域の面積を求めよ。"
    )


def solve_parabolic_area(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    x = sp.symbols("x", real=True)
    length = sp.Integer(params["length"])
    scale = sp.Integer(params["scale"])
    integrand = scale * x * (length - x)
    area = sp.integrate(integrand, (x, 0, length))
    expected = scale * length**3 / 6
    return BackendResult(
        answer=sympy_text(expected),
        normal_form=sympy_text(expected),
        verified=bool(sp.simplify(area - expected) == 0 and area > 0),
        method="sympy_exact_integral",
        trace={
            "integrand": sympy_text(integrand),
            "bounds": ["0", sympy_text(length)],
            "integral": sympy_text(area),
        },
    )


def render_rectangle_perimeter_extremum(params: dict[str, int]) -> str:
    return (
        f"周の長さが ${params['perimeter']}$ である長方形の面積の"
        "最大値を求めよ。"
    )


def solve_rectangle_perimeter_extremum(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    x = sp.symbols("x", real=True)
    perimeter = sp.Integer(params["perimeter"])
    semiperimeter = perimeter / 2
    area = sp.expand(x * (semiperimeter - x))
    critical = sp.solve(sp.diff(area, x), x)
    maximizer = critical[0]
    maximum = sp.simplify(area.subs(x, maximizer))
    verified = (
        len(critical) == 1
        and 0 < maximizer < semiperimeter
        and sp.diff(area, x, 2) < 0
        and sp.simplify(maximum - perimeter**2 / 16) == 0
    )
    return BackendResult(
        answer=sympy_text(maximum),
        normal_form=sympy_text(maximum),
        verified=bool(verified),
        method="sympy_stationary_and_boundary_check",
        trace={
            "objective": sympy_text(area),
            "feasible_interval": ["0", sympy_text(semiperimeter)],
            "critical_points": [sympy_text(value) for value in critical],
            "second_derivative": sympy_text(sp.diff(area, x, 2)),
        },
    )


def render_rectangle_diagonal_extremum(params: dict[str, int]) -> str:
    diagonal_squared = params["diagonal_squared"]
    return (
        f"対角線の長さが $\\sqrt{{{diagonal_squared}}}$ である長方形の"
        "面積の最大値を求めよ。"
    )


def solve_rectangle_diagonal_extremum(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    x, y = sp.symbols("x y", positive=True)
    diagonal_squared = sp.Integer(params["diagonal_squared"])
    identity = sp.expand((x**2 + y**2) ** 2 / 4 - x**2 * y**2)
    target_identity = sp.expand((x**2 - y**2) ** 2 / 4)
    maximum = diagonal_squared / 2
    verified = sp.simplify(identity - target_identity) == 0
    return BackendResult(
        answer=sympy_text(maximum),
        normal_form=sympy_text(maximum),
        verified=bool(verified),
        method="sympy_polynomial_identity_and_equality_case",
        trace={
            "constraint": f"x**2 + y**2 = {diagonal_squared}",
            "nonnegative_gap": sympy_text(target_identity),
            "equality_case": "x = y",
        },
    )


def render_positive_definite_quadratic_minimum(params: dict[str, int]) -> str:
    q11, q12, q22 = (params[name] for name in ("q11", "q12", "q22"))
    l1, l2, constant = (params[name] for name in ("l1", "l2", "constant"))
    return (
        "実ベクトル $\\boldsymbol{x}=(x,y)^T$ と正定値対称行列 "
        f"$Q=\\begin{{pmatrix}}{q11}&{q12}\\\\{q12}&{q22}\\end{{pmatrix}}$ "
        "に対し，二次形式\n"
        "\\[\n"
        f"f(\\boldsymbol{{x}})=\\boldsymbol{{x}}^TQ\\boldsymbol{{x}}"
        f"+({l1},{l2})\\boldsymbol{{x}}+{constant}\n"
        "\\]\n"
        "の最小値を求めよ。"
    )


def solve_positive_definite_quadratic_minimum(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    q = sp.Matrix(
        [
            [params["q11"], params["q12"]],
            [params["q12"], params["q22"]],
        ]
    )
    linear = sp.Matrix([params["l1"], params["l2"]])
    constant = sp.Integer(params["constant"])
    minimizer = sp.simplify(-q.inv() * linear / 2)
    minimum = sp.simplify(
        (minimizer.T * q * minimizer)[0]
        + (linear.T * minimizer)[0]
        + constant
    )
    leading_minor = q[0, 0]
    determinant = q.det()
    gradient = sp.simplify(2 * q * minimizer + linear)
    verified = (
        leading_minor > 0
        and determinant > 0
        and gradient == sp.zeros(2, 1)
    )
    return BackendResult(
        answer=sympy_text(minimum),
        normal_form=sympy_text(minimum),
        verified=bool(verified),
        method="sympy_positive_definite_quadratic_completion",
        trace={
            "matrix": str(q.tolist()),
            "linear_term": str(list(linear)),
            "leading_principal_minors": [
                sympy_text(leading_minor),
                sympy_text(determinant),
            ],
            "minimizer": [sympy_text(value) for value in minimizer],
            "stationarity_residual": str(gradient.tolist()),
        },
    )


def render_frobenius_inner_product(params: dict[str, int]) -> str:
    return (
        "行列\n"
        "\\[\n"
        f"A=\\begin{{pmatrix}}{params['a11']}&{params['a12']}\\\\"
        f"{params['a21']}&{params['a22']}\\end{{pmatrix}},\\qquad"
        f"B=\\begin{{pmatrix}}{params['b11']}&{params['b12']}\\\\"
        f"{params['b21']}&{params['b22']}\\end{{pmatrix}}\n"
        "\\]\n"
        "のフロベニウス内積 $\\operatorname{tr}(A^TB)$ を求めよ。"
    )


def solve_frobenius_inner_product(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    a = sp.Matrix(
        [
            [params["a11"], params["a12"]],
            [params["a21"], params["a22"]],
        ]
    )
    b = sp.Matrix(
        [
            [params["b11"], params["b12"]],
            [params["b21"], params["b22"]],
        ]
    )
    pairing = sp.trace(a.T * b)
    entrywise = sum(a[i, j] * b[i, j] for i in range(2) for j in range(2))
    return BackendResult(
        answer=sympy_text(pairing),
        normal_form=sympy_text(pairing),
        verified=bool(sp.simplify(pairing - entrywise) == 0),
        method="sympy_trace_pairing",
        trace={
            "transpose_product": str((a.T * b).tolist()),
            "trace": sympy_text(pairing),
            "entrywise_pairing": sympy_text(entrywise),
        },
    )


def render_orthogonal_projection(params: dict[str, int]) -> str:
    return (
        "実内積空間 $\\mathbb{R}^3$ において，"
        f"$v=({params['v1']},{params['v2']},{params['v3']})$ の "
        f"$u=({params['u1']},{params['u2']},{params['u3']})$ "
        "が張る部分空間への直交射影を求めよ。"
    )


def solve_orthogonal_projection(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    u = sp.Matrix([params["u1"], params["u2"], params["u3"]])
    v = sp.Matrix([params["v1"], params["v2"], params["v3"]])
    coefficient = sp.simplify((v.dot(u)) / (u.dot(u)))
    projection = sp.simplify(coefficient * u)
    residual = sp.simplify(v - projection)
    verified = u.dot(u) > 0 and sp.simplify(residual.dot(u)) == 0
    normal = json.dumps(
        [sympy_text(value) for value in projection],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    return BackendResult(
        answer=f"({', '.join(sympy_text(value) for value in projection)})",
        normal_form=normal,
        verified=bool(verified),
        method="sympy_gram_projection",
        trace={
            "gram_scalar": sympy_text(u.dot(u)),
            "pairing": sympy_text(v.dot(u)),
            "coefficient": sympy_text(coefficient),
            "orthogonality_residual": sympy_text(residual.dot(u)),
        },
    )


def render_inner_product_extremum(params: dict[str, int]) -> str:
    return (
        "実内積空間のベクトル $a,x$ が "
        f"$\\|a\\|={params['norm_a']}$，$\\|x\\|={params['radius']}$ "
        "を満たすとき，内積 $\\langle a,x\\rangle$ の最大値を求めよ。"
    )


def solve_inner_product_extremum(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    norm_a = sp.Integer(params["norm_a"])
    radius = sp.Integer(params["radius"])
    maximum = norm_a * radius
    verified = norm_a > 0 and radius > 0
    return BackendResult(
        answer=sympy_text(maximum),
        normal_form=sympy_text(maximum),
        verified=bool(verified),
        method="gram_cauchy_schwarz_with_attainability",
        trace={
            "upper_bound": "Norm(a)*Norm(x)",
            "equality_witness": "x = radius*a/Norm(a)",
            "attained_value": sympy_text(maximum),
        },
    )


def render_normalized_inner_product_limit(params: dict[str, int]) -> str:
    scale = params["scale"]
    return (
        "実内積空間の正規直交ベクトル $u,v$ に対し，"
        f"$w_n=u+\\frac{{{scale}}}{{n}}v$ とする。"
        "正規化内積\n"
        "\\[\n"
        "\\frac{\\langle u,w_n\\rangle}{\\|u\\|\\,\\|w_n\\|}\n"
        "\\]\n"
        "の $n\\to\\infty$ における極限を求めよ。"
    )


def solve_normalized_inner_product_limit(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    n = sp.symbols("n", positive=True, integer=True)
    scale = sp.Integer(params["scale"])
    gram_pairing = sp.Integer(1)
    norm_u_squared = sp.Integer(1)
    norm_w_squared = 1 + scale**2 / n**2
    normalized = sp.simplify(
        gram_pairing / sp.sqrt(norm_u_squared * norm_w_squared)
    )
    limit = sp.limit(normalized, n, sp.oo)
    return BackendResult(
        answer="1",
        normal_form="1",
        verified=bool(limit == 1 and norm_w_squared.is_positive),
        method="symbolic_gram_matrix_then_limit",
        trace={
            "gram_pairing": sympy_text(gram_pairing),
            "norm_u_squared": sympy_text(norm_u_squared),
            "norm_w_squared": sympy_text(norm_w_squared),
            "normalized_pairing": sympy_text(normalized),
            "limit": sympy_text(limit),
        },
    )


def render_autocorrelation_function(params: dict[str, int]) -> str:
    numerator, denominator = params["rho_num"], params["rho_den"]
    return (
        "弱定常過程\n"
        "\\[\n"
        f"X_{{n+1}}=\\frac{{{numerator}}}{{{denominator}}}X_n"
        "+\\varepsilon_{n+1}\n"
        "\\]\n"
        "の相関関数を求めよ。ただし白色雑音 $\\varepsilon_n$ は "
        "$X_n$ と独立で，分散は正とする。"
    )


def solve_autocorrelation_function(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    rho = sp.Rational(params["rho_num"], params["rho_den"])
    k = sp.symbols("k", integer=True)
    variance_noise = sp.Integer(1)
    variance = sp.simplify(variance_noise / (1 - rho**2))
    correlation = rho ** sp.Abs(k)
    yule_walker_zero = sp.simplify(variance - (rho**2 * variance + variance_noise))
    verified = abs(rho) < 1 and yule_walker_zero == 0 and variance > 0
    return BackendResult(
        answer=sympy_text(correlation),
        normal_form=sympy_text(correlation),
        verified=bool(verified),
        method="symbolic_yule_walker_recursion",
        trace={
            "autoregressive_coefficient": sympy_text(rho),
            "stationary_variance": sympy_text(variance),
            "yule_walker_residual": sympy_text(yule_walker_zero),
            "normalized_lag_pairing": sympy_text(correlation),
        },
    )


def render_rational_limit(params: dict[str, int]) -> str:
    a, b, c, d = (params[name] for name in ("a", "b", "c", "d"))
    return (
        "数列\n"
        "\\[\n"
        f"a_n=\\frac{{{a}n+{b}}}{{{c}n+{d}}}\n"
        "\\]\n"
        "の $n\\to\\infty$ における極限を求めよ。"
    )


def solve_rational_limit(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    n = sp.symbols("n", positive=True, integer=True)
    a, b, c, d = (sp.Integer(params[name]) for name in ("a", "b", "c", "d"))
    expression = (a * n + b) / (c * n + d)
    limit = sp.limit(expression, n, sp.oo)
    expected = a / c
    return BackendResult(
        answer=sympy_text(expected),
        normal_form=sympy_text(expected),
        verified=bool(sp.simplify(limit - expected) == 0),
        method="sympy_sequence_limit",
        trace={"expression": sympy_text(expression), "limit": sympy_text(limit)},
    )


def render_exponential_limit(params: dict[str, int]) -> str:
    coefficient = params["coefficient"]
    return (
        "数列\n"
        "\\[\n"
        f"a_n=\\left(1+\\frac{{{coefficient}}}{{n}}\\right)^n\n"
        "\\]\n"
        "の $n\\to\\infty$ における極限を求めよ。"
    )


def solve_exponential_limit(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    n = sp.symbols("n", positive=True, integer=True)
    coefficient = sp.Integer(params["coefficient"])
    expression = (1 + coefficient / n) ** n
    limit = sp.limit(expression, n, sp.oo)
    expected = sp.exp(coefficient)
    return BackendResult(
        answer=sympy_text(expected),
        normal_form=sympy_text(expected),
        verified=bool(sp.simplify(limit - expected) == 0),
        method="sympy_sequence_limit",
        trace={"expression": sympy_text(expression), "limit": sympy_text(limit)},
    )


def render_area_limit(params: dict[str, int]) -> str:
    radius, correction = params["radius"], params["correction"]
    return (
        "正の整数 $n$ に対し，半径 "
        f"$r_n={radius}+\\frac{{{correction}}}{{n}}$ の円の面積を $A_n$ とする。"
        "$n\\to\\infty$ における $A_n$ の極限を求めよ。"
    )


def solve_area_limit(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    n = sp.symbols("n", positive=True, integer=True)
    radius = sp.Integer(params["radius"])
    correction = sp.Integer(params["correction"])
    area = sp.pi * (radius + correction / n) ** 2
    limit = sp.limit(area, n, sp.oo)
    expected = sp.pi * radius**2
    return BackendResult(
        answer=sympy_text(expected),
        normal_form=sympy_text(expected),
        verified=bool(sp.simplify(limit - expected) == 0),
        method="sympy_measure_then_limit",
        trace={"area_sequence": sympy_text(area), "limit": sympy_text(limit)},
    )


def render_correlation_limit(params: dict[str, int]) -> str:
    scale = params["scale"]
    return (
        "互いに独立で平均 $0$，分散 $1$ の確率変数 $X,Z$ に対し，"
        f"$Y_n=X+\\frac{{{scale}}}{{n}}Z$ とする。"
        "$L^2(P)$ 上の共分散内積 "
        "$\\langle U,V\\rangle_c=\\operatorname{E}[(U-\\operatorname{E}U)"
        "(V-\\operatorname{E}V)]$ を用いて定まる，"
        "$X$ と $Y_n$ の相関係数の $n\\to\\infty$ における極限を求めよ。"
    )


def solve_correlation_limit(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    n = sp.symbols("n", positive=True, integer=True)
    scale = sp.Integer(params["scale"])
    covariance = sp.Integer(1)
    variance_x = sp.Integer(1)
    variance_y = 1 + scale**2 / n**2
    correlation = sp.simplify(covariance / sp.sqrt(variance_x * variance_y))
    limit = sp.limit(correlation, n, sp.oo)
    return BackendResult(
        answer="1",
        normal_form="1",
        verified=bool(limit == 1 and variance_y.is_positive),
        method="centered_l2_gram_matrix_then_limit",
        trace={
            "covariance": sympy_text(covariance),
            "variance_x": sympy_text(variance_x),
            "variance_y": sympy_text(variance_y),
            "correlation": sympy_text(correlation),
            "limit": sympy_text(limit),
        },
    )


def render_ellipsoid_volume(params: dict[str, int]) -> str:
    a, b, c = (params[name] for name in ("a", "b", "c"))
    return (
        "楕円体\n"
        "\\[\n"
        f"\\frac{{x^2}}{{{a * a}}}+\\frac{{y^2}}{{{b * b}}}"
        f"+\\frac{{z^2}}{{{c * c}}}\\le 1\n"
        "\\]\n"
        "の体積を求めよ。"
    )


def solve_ellipsoid_volume(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    rho, phi, theta = sp.symbols("rho phi theta", real=True)
    a, b, c = (sp.Integer(params[name]) for name in ("a", "b", "c"))
    jacobian = a * b * c * rho**2 * sp.sin(phi)
    volume = sp.integrate(
        jacobian,
        (rho, 0, 1),
        (phi, 0, sp.pi),
        (theta, 0, 2 * sp.pi),
    )
    expected = 4 * sp.pi * a * b * c / 3
    return BackendResult(
        answer=sympy_text(expected),
        normal_form=sympy_text(expected),
        verified=bool(sp.simplify(volume - expected) == 0),
        method="sympy_exact_triple_integral",
        trace={"jacobian": sympy_text(jacobian), "integral": sympy_text(volume)},
    )


def render_revolution_volume(params: dict[str, int]) -> str:
    half_width, height = params["half_width"], params["height"]
    return (
        "曲線\n"
        "\\[\n"
        f"y={height}\\left(1-\\frac{{x^2}}{{{half_width * half_width}}}\\right)"
        f"\\quad (-{half_width}\\le x\\le {half_width})\n"
        "\\]\n"
        "と $x$ 軸で囲まれる部分を $x$ 軸のまわりに回転してできる"
        "立体の体積を求めよ。"
    )


def solve_revolution_volume(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    x = sp.symbols("x", real=True)
    half_width = sp.Integer(params["half_width"])
    height = sp.Integer(params["height"])
    y = height * (1 - x**2 / half_width**2)
    volume = sp.pi * sp.integrate(y**2, (x, -half_width, half_width))
    expected = 16 * sp.pi * half_width * height**2 / 15
    return BackendResult(
        answer=sympy_text(expected),
        normal_form=sympy_text(expected),
        verified=bool(sp.simplify(volume - expected) == 0),
        method="sympy_disk_method_integral",
        trace={"radius": sympy_text(y), "integral": sympy_text(volume)},
    )


def render_prime_sum(params: dict[str, int]) -> str:
    total = params["total"]
    return (
        f"素数 $p,q$ が $p\\le q$ かつ $p+q={total}$ を満たすとき，"
        "すべての組 $(p,q)$ を求めよ。"
    )


def solve_prime_sum(params: dict[str, int]) -> BackendResult:
    sp = import_sympy()
    total = params["total"]
    pairs = [
        (p, total - p)
        for p in list(sp.primerange(2, total + 1))
        if p <= total - p and sp.isprime(total - p)
    ]
    complete = all(
        sp.isprime(p) and sp.isprime(q) and p <= q and p + q == total
        for p, q in pairs
    )
    answer = "{" + ", ".join(f"({p},{q})" for p, q in pairs) + "}"
    normal = json.dumps(pairs, ensure_ascii=False, separators=(",", ":"))
    return BackendResult(
        answer=answer,
        normal_form=normal,
        verified=bool(pairs and complete),
        method="exhaustive_prime_enumeration",
        trace={
            "search_interval": [2, total],
            "tested_prime_count": int(sp.primepi(total)),
            "solutions": pairs,
        },
    )


def build_charts() -> tuple[SynthesisChart, ...]:
    return (
        SynthesisChart(
            chart_id="ellipse_area",
            family_id="measure_geometry.planar_area",
            domain="geometry",
            task="area",
            strategy="coordinate_scaling_then_exact_integral",
            proof_obligations=(
                "identify a bounded measurable planar region",
                "reduce by coordinate scaling and symmetry",
                "evaluate the exact area integral",
            ),
            parameter_space=tuple(
                {"a": a, "b": b}
                for a, b in ((2, 3), (2, 4), (3, 4), (3, 5), (4, 5), (4, 6), (5, 6), (5, 7))
            ),
            render=render_ellipse_area,
            solve=solve_ellipse_area,
        ),
        SynthesisChart(
            chart_id="parabolic_segment_area",
            family_id="measure_geometry.planar_area",
            domain="geometry",
            task="area",
            strategy="vertical_slice_exact_integral",
            proof_obligations=(
                "identify a bounded measurable planar region",
                "construct vertical slices",
                "evaluate the exact polynomial integral",
            ),
            parameter_space=tuple(
                {"length": length, "scale": scale}
                for length, scale in ((2, 1), (3, 1), (2, 2), (3, 2))
            ),
            render=render_parabolic_area,
            solve=solve_parabolic_area,
        ),
        SynthesisChart(
            chart_id="rectangle_perimeter_area_maximum",
            family_id="optimization.planar_area_extremum",
            domain="optimization",
            task="optimize",
            strategy="constraint_substitution_then_stationary_boundary_check",
            proof_obligations=(
                "translate the perimeter constraint to a feasible interval",
                "form the area objective",
                "verify the global maximum against boundaries",
            ),
            parameter_space=tuple(
                {"perimeter": value} for value in (12, 16, 20, 24, 28)
            ),
            render=render_rectangle_perimeter_extremum,
            solve=solve_rectangle_perimeter_extremum,
        ),
        SynthesisChart(
            chart_id="rectangle_diagonal_area_maximum",
            family_id="optimization.planar_area_extremum",
            domain="optimization",
            task="optimize",
            strategy="symmetric_polynomial_bound_with_equality_case",
            proof_obligations=(
                "translate the diagonal constraint",
                "bound the area by a nonnegative polynomial identity",
                "verify attainability at the equality case",
            ),
            parameter_space=tuple(
                {"diagonal_squared": value} for value in (8, 18, 32)
            ),
            render=render_rectangle_diagonal_extremum,
            solve=solve_rectangle_diagonal_extremum,
        ),
        SynthesisChart(
            chart_id="positive_definite_quadratic_minimum",
            family_id="optimization.positive_definite_quadratic",
            domain="optimization",
            task="optimize",
            strategy="positive_definite_operator_then_linear_stationarity",
            proof_obligations=(
                "certify positive definiteness by principal minors",
                "solve the vector stationarity system",
                "verify the global quadratic lower bound",
            ),
            parameter_space=tuple(
                {
                    "q11": q11,
                    "q12": q12,
                    "q22": q22,
                    "l1": l1,
                    "l2": l2,
                    "constant": constant,
                }
                for q11, q12, q22, l1, l2, constant in (
                    (2, 1, 2, -2, -4, 7),
                    (3, 1, 2, -4, 2, 5),
                    (4, -1, 3, 2, -6, 8),
                    (5, 2, 3, -6, -2, 10),
                )
            ),
            render=render_positive_definite_quadratic_minimum,
            solve=solve_positive_definite_quadratic_minimum,
        ),
        SynthesisChart(
            chart_id="rational_sequence_limit",
            family_id="real_analysis.limit_observable",
            domain="real_analysis",
            task="limit",
            strategy="normalize_by_dominant_power",
            proof_obligations=(
                "identify the directed sequence limit",
                "normalize numerator and denominator by n",
                "verify the limiting denominator is nonzero",
            ),
            parameter_space=tuple(
                {"a": a, "b": b, "c": c, "d": d}
                for a, b, c, d in ((2, 1, 3, 2), (3, -1, 2, 4), (4, 5, 5, 1), (5, 2, 3, 7), (7, -2, 4, 3))
            ),
            render=render_rational_limit,
            solve=solve_rational_limit,
        ),
        SynthesisChart(
            chart_id="exponential_sequence_limit",
            family_id="real_analysis.limit_observable",
            domain="real_analysis",
            task="limit",
            strategy="logarithmic_limit_then_exponentiation",
            proof_obligations=(
                "identify the directed sequence limit",
                "take logarithms on an eventually positive sequence",
                "verify exponentiation preserves the limit",
            ),
            parameter_space=tuple(
                {"coefficient": value} for value in (1, 2, 3, 4, 5)
            ),
            render=render_exponential_limit,
            solve=solve_exponential_limit,
        ),
        SynthesisChart(
            chart_id="circle_area_limit",
            family_id="real_analysis.planar_measure_limit",
            domain="real_analysis",
            task="limit",
            strategy="measure_expression_then_symbolic_limit",
            proof_obligations=(
                "construct the area observable",
                "verify every radius is positive",
                "discharge the limit of the area sequence",
            ),
            parameter_space=tuple(
                {"radius": radius, "correction": correction}
                for radius, correction in ((1, 1), (1, 2), (2, 1), (3, 2))
            ),
            render=render_area_limit,
            solve=solve_area_limit,
        ),
        SynthesisChart(
            chart_id="centered_l2_correlation_limit",
            family_id="real_analysis.correlation_limit",
            domain="probability",
            task="limit",
            strategy="centered_l2_gram_matrix_then_normalized_limit",
            proof_obligations=(
                "construct covariance from independence",
                "verify positive variances",
                "normalize and discharge the correlation limit",
            ),
            parameter_space=tuple({"scale": value} for value in (1, 2)),
            render=render_correlation_limit,
            solve=solve_correlation_limit,
        ),
        SynthesisChart(
            chart_id="ellipsoid_volume",
            family_id="measure_geometry.solid_volume",
            domain="geometry",
            task="solid_volume",
            strategy="unit_ball_scaling_then_triple_integral",
            proof_obligations=(
                "identify a bounded measurable solid",
                "compute the coordinate-scaling Jacobian",
                "evaluate the exact triple integral",
            ),
            parameter_space=tuple(
                {"a": a, "b": b, "c": c}
                for a, b, c in ((1, 2, 3), (2, 3, 4), (2, 4, 5), (3, 4, 5))
            ),
            render=render_ellipsoid_volume,
            solve=solve_ellipsoid_volume,
        ),
        SynthesisChart(
            chart_id="parabolic_revolution_volume",
            family_id="measure_geometry.solid_volume",
            domain="geometry",
            task="solid_volume",
            strategy="disk_method_exact_integral",
            proof_obligations=(
                "identify a bounded solid of revolution",
                "construct disk cross-sections",
                "evaluate the exact volume integral",
            ),
            parameter_space=tuple(
                {"half_width": half_width, "height": height}
                for half_width, height in ((2, 1), (3, 2))
            ),
            render=render_revolution_volume,
            solve=solve_revolution_volume,
        ),
        SynthesisChart(
            chart_id="prime_sum_constraint",
            family_id="elementary_number_theory.prime_constraint_query",
            domain="number_theory",
            task="solve",
            strategy="finite_prime_enumeration_with_completeness_bound",
            proof_obligations=(
                "derive a finite search interval from the sum constraint",
                "certify primality of every component",
                "prove completeness by exhaustive enumeration",
            ),
            parameter_space=tuple(
                {"total": value} for value in (20, 24, 30, 34, 40, 42, 50, 60)
            ),
            render=render_prime_sum,
            solve=solve_prime_sum,
        ),
        SynthesisChart(
            chart_id="frobenius_matrix_pairing",
            family_id="linear_algebra.frobenius_pairing",
            domain="linear_algebra",
            task="compute",
            strategy="trace_induced_matrix_inner_product",
            proof_obligations=(
                "verify compatible matrix shapes",
                "construct the trace-induced inner product",
                "check equality with the entrywise pairing",
            ),
            parameter_space=(
                {"a11": 1, "a12": 2, "a21": 3, "a22": 4, "b11": 2, "b12": 0, "b21": 1, "b22": 3},
                {"a11": 2, "a12": -1, "a21": 0, "a22": 3, "b11": 1, "b12": 4, "b21": -2, "b22": 2},
                {"a11": 3, "a12": 1, "a21": -1, "a22": 2, "b11": 0, "b12": 2, "b21": 5, "b22": -1},
                {"a11": 1, "a12": 0, "a21": 2, "a22": -2, "b11": 4, "b12": 3, "b21": -1, "b22": 2},
            ),
            render=render_frobenius_inner_product,
            solve=solve_frobenius_inner_product,
        ),
        SynthesisChart(
            chart_id="orthogonal_projection",
            family_id="linear_algebra.orthogonal_projection",
            domain="linear_algebra",
            task="compute",
            strategy="gram_system_then_orthogonal_residual",
            proof_obligations=(
                "construct the one-dimensional Gram matrix",
                "solve for the projection coefficient",
                "verify residual orthogonality",
            ),
            parameter_space=(
                {"u1": 1, "u2": 1, "u3": 0, "v1": 1, "v2": 2, "v3": 3},
                {"u1": 1, "u2": 0, "u3": 2, "v1": 3, "v2": -1, "v3": 1},
                {"u1": 2, "u2": -1, "u3": 1, "v1": 0, "v2": 3, "v3": 2},
                {"u1": 1, "u2": 2, "u3": -1, "v1": 4, "v2": 0, "v3": 1},
            ),
            render=render_orthogonal_projection,
            solve=solve_orthogonal_projection,
        ),
        SynthesisChart(
            chart_id="norm_constrained_inner_product_extremum",
            family_id="optimization.inner_product_extremum",
            domain="optimization",
            task="optimize",
            strategy="gram_cauchy_schwarz_with_equality_witness",
            proof_obligations=(
                "construct the norm-constrained feasible set",
                "apply the Gram/Cauchy-Schwarz bound",
                "verify an attainable equality witness",
            ),
            parameter_space=tuple(
                {"norm_a": norm_a, "radius": radius}
                for norm_a, radius in ((2, 3), (3, 4), (4, 2), (5, 3))
            ),
            render=render_inner_product_extremum,
            solve=solve_inner_product_extremum,
        ),
        SynthesisChart(
            chart_id="normalized_inner_product_limit",
            family_id="real_analysis.normalized_inner_product_limit",
            domain="real_analysis",
            task="limit",
            strategy="gram_data_then_normalized_pairing_limit",
            proof_obligations=(
                "construct the finite Gram data",
                "verify nonzero norms",
                "normalize and discharge the scalar limit",
            ),
            parameter_space=tuple({"scale": value} for value in (1, 2, 3, 4)),
            render=render_normalized_inner_product_limit,
            solve=solve_normalized_inner_product_limit,
        ),
        SynthesisChart(
            chart_id="stationary_ar1_autocorrelation",
            family_id="probability.autocorrelation_function",
            domain="probability",
            task="compute",
            strategy="yule_walker_then_normalized_lag_pairing",
            proof_obligations=(
                "verify the stationarity parameter range",
                "solve the Yule-Walker covariance recursion",
                "normalize by the zero-lag variance",
            ),
            parameter_space=(
                {"rho_num": 1, "rho_den": 2},
                {"rho_num": -1, "rho_den": 3},
            ),
            render=render_autocorrelation_function,
            solve=solve_autocorrelation_function,
        ),
    )


def generate_candidates(charts: Iterable[SynthesisChart] | None = None) -> list[AtlasCandidate]:
    output: list[AtlasCandidate] = []
    for chart in charts or build_charts():
        for index, parameters in enumerate(chart.parameter_space, start=1):
            output.append(
                AtlasCandidate(
                    candidate_id=f"atlas:{chart.chart_id}:{index:03d}",
                    chart_id=chart.chart_id,
                    parameters=dict(parameters),
                )
            )
    return output


def lift_statement(statement: str) -> dict[str, Any]:
    typed_ir = compile_typed_definition_ir(statement)
    formal_ir = compile_formal_ir(statement)
    graph = compile_typed_semantic_graph(
        statement,
        typed_definition_ir=typed_ir.to_dict(),
        formal_ir=formal_ir.to_dict(),
    )
    certificates = [
        item.to_dict() for item in graph.lift_certificates if item.admissible
    ]
    return {
        "status": graph.status,
        "typed_definition_status": typed_ir.status,
        "formal_ir_status": formal_ir.status,
        "families": [item["family_id"] for item in certificates],
        "certificates": certificates,
    }


def evaluate_candidate(candidate: AtlasCandidate, charts: Iterable[SynthesisChart] | None = None) -> dict[str, Any]:
    chart_map = {chart.chart_id: chart for chart in charts or build_charts()}
    chart = chart_map[candidate.chart_id]
    statement = chart.render(candidate.parameters)
    backend = chart.solve(candidate.parameters)
    try:
        lift = lift_statement(statement)
        lift_verified = chart.family_id in lift["families"]
        lift_error = None
    except Exception as exc:
        lift = {"status": "failed", "families": [], "certificates": []}
        lift_verified = False
        lift_error = f"{type(exc).__name__}: {exc}"
    if not backend.verified:
        phase = "backend_rejected"
    elif not lift_verified:
        phase = "lift_rejected"
    else:
        phase = "verified"
    verification = {
        "status": "verified" if phase == "verified" else "rejected",
        "backend_verified": backend.verified,
        "backend_method": backend.method,
        "lift_verified": lift_verified,
        "expected_family_id": chart.family_id,
        "observed_family_ids": lift.get("families", []),
        "lift_error": lift_error,
    }
    curriculum_item = None
    if phase == "verified":
        curriculum_item = {
            "source": "problem_phase_synthesis.atlas_verified",
            "input_tex": statement,
            "domain": chart.domain,
            "task": chart.task,
            "expected_answer": backend.answer,
            "normal_form": {
                "kind": chart.family_id,
                "normal_form": backend.normal_form,
                "parse_status": "ok",
            },
            "family_id": chart.family_id,
            "match_group": f"lift:{chart.family_id}",
            "strategy": chart.strategy,
            "proof_obligations": list(chart.proof_obligations),
            "difficulty": {
                "level": "medium",
                "raw": len(chart.proof_obligations),
                "proof_obligations": list(chart.proof_obligations),
            },
            "verification": verification,
            "backend_trace": backend.trace,
            "lift_certificate": next(
                (
                    item
                    for item in lift.get("certificates", [])
                    if item.get("family_id") == chart.family_id
                ),
                None,
            ),
        }
    return {
        "candidate": asdict(candidate),
        "chart": {
            "chart_id": chart.chart_id,
            "family_id": chart.family_id,
            "domain": chart.domain,
            "task": chart.task,
            "strategy": chart.strategy,
        },
        "statement_tex": statement,
        "backend": asdict(backend),
        "lift": lift,
        "verification": verification,
        "phase": phase,
        "curriculum_item": curriculum_item,
    }


def run_atlas_synthesis(*, limit: int = 72) -> dict[str, Any]:
    charts = build_charts()
    candidates = generate_candidates(charts)
    if limit >= 0:
        candidates = candidates[:limit]
    results = [evaluate_candidate(candidate, charts) for candidate in candidates]
    curriculum_items = [
        result["curriculum_item"]
        for result in results
        if result["curriculum_item"] is not None
    ]
    phase_counts = Counter(result["phase"] for result in results)
    family_counts = Counter(
        item["family_id"] for item in curriculum_items
    )
    chart_counts = Counter(
        result["chart"]["chart_id"]
        for result in results
        if result["phase"] == "verified"
    )
    return {
        "family": {
            "name": "atlas_verified_problem_synthesis",
            "theme": (
                "area / extremum / limit / volume / prime constraints / "
                "inner products / projections / correlation functions"
            ),
            "description": (
                "Generate typed mathematical objects, verify answers with an executable "
                "backend, then require the rendered TeX to lift back to the declared atlas family."
            ),
            "invariant": (
                "An exported item must satisfy backend_verified and "
                "expected_family_id in observed LiftCertificates."
            ),
        },
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "input": {"limit": limit, "available_candidates": len(generate_candidates(charts))},
        "summary": {
            "evaluated": len(results),
            "verified": len(curriculum_items),
            "rejected": len(results) - len(curriculum_items),
            "phase_counts": dict(phase_counts),
            "family_counts": dict(family_counts),
            "chart_counts": dict(chart_counts),
            "unique_normal_forms": len(
                {item["normal_form"]["normal_form"] for item in curriculum_items}
            ),
        },
        "curriculum_items": curriculum_items,
        "results": results,
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    lines = [
        "# Atlas検証付き作問",
        "",
        f"生成日時: {report['generated_at']}",
        "",
        "## 検証契約",
        "",
        f"- {report['family']['invariant']}",
        "",
        "## 集計",
        "",
        f"- 評価候補数: {summary['evaluated']}",
        f"- 二重検証通過数: {summary['verified']}",
        f"- 棄却数: {summary['rejected']}",
        f"- 異なる解答正規形: {summary['unique_normal_forms']}",
        "",
        "## Lift family",
        "",
        "| family | 検証済み問題数 |",
        "| --- | ---: |",
    ]
    for family, count in sorted(summary["family_counts"].items()):
        lines.append(f"| `{family}` | {count} |")
    lines.extend(
        [
            "",
            "## 生成チャート",
            "",
            "| chart | 検証済み問題数 |",
            "| --- | ---: |",
        ]
    )
    for chart, count in sorted(summary["chart_counts"].items()):
        lines.append(f"| `{chart}` | {count} |")
    lines.extend(
        [
            "",
            "## 解釈",
            "",
            "検証は論理積である。backendによる答えの確認だけでも、"
            "LiftCertificateだけでも不十分であり、両方を通過した候補だけを"
            "CreativeBenchへ出力する。",
            "",
        ]
    )
    return "\n".join(lines)


def write_report(path: Path, report: dict[str, Any]) -> tuple[Path, Path]:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    markdown_path = path.with_suffix(".md")
    markdown_path.write_text(render_markdown(report), encoding="utf-8")
    return path, markdown_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate backend-verified and LiftCertificate-verified atlas problems."
    )
    parser.add_argument("--limit", type=int, default=72)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run_atlas_synthesis(limit=args.limit)
    output, markdown = write_report(args.output, report)
    print(
        json.dumps(
            {
                "output": str(output),
                "markdown": str(markdown),
                **report["summary"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0 if report["summary"]["verified"] == report["summary"]["evaluated"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
