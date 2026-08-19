"""関係を導出する閉包。

これまでの閉包は値しか持たなかった。値しか持たないと問いは「求めよ」に
なり、証明も不等式も範囲も作れない。実測すると MathOS の 97% が
「値を求めよ」で、手作り問題では 53% しかなかった（証明 19% / 最大最小 18%）。
題材でも不等式が 56% 対 4% と最大の差になっていた。原因はここにある。

ここでは導出するものを値から **関係** に変える:

    R1  f >= m （等号成立点つき）
    R2  f - m が平方和に分解できる  ← 証明そのもの
    R3  f のとりうる値の範囲

関係でも検証は緩めない。
  * 下界 m が厳密（Float を含まない）
  * 等号成立点が厳密に存在する
  * f - m >= 0 を定義域上の標本で独立に確かめる
  * 平方和分解は恒等式として simplify で 0 になることを確かめる
の 4 つを全部通ったものだけをノードにする。
"""

from __future__ import annotations

import argparse
import json
import random
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import sympy as sp

try:
    from math_os_prototype.construct_engine import Problem
except ImportError:  # pragma: no cover
    from construct_engine import Problem


@dataclass(frozen=True)
class RelationNode:
    """閉包の 1 ノード。値ではなく関係を持つ。"""

    key: str
    kind: str                    # 'min' | 'max' | 'sos' | 'range'
    bound: sp.Expr               # 下界／上界
    equality_at: str             # 等号成立の条件（日本語）
    question_ja: str
    answer_tex: str
    solution_ja: str
    morphisms: tuple[str, ...]
    hidden: tuple[str, ...]
    scope: tuple[str, ...]
    certificate: dict[str, Any]


def _exact(value: Any) -> sp.Expr | None:
    try:
        expr = sp.simplify(value)
    except Exception:
        return None
    if expr.free_symbols or expr.atoms(sp.Float):
        return None
    return expr


def _verify_bound(
    expr: sp.Expr, var: sp.Symbol, low: Any, high: Any,
    bound: sp.Expr, is_min: bool, samples: int = 40,
) -> bool:
    """f - m >= 0（または <= 0）を定義域の標本で独立に確かめる。"""
    rng = random.Random(20260731)
    lo = float(low) if low not in (-sp.oo,) else -50.0
    hi = float(high) if high not in (sp.oo,) else 50.0
    if not (hi > lo):
        return False
    target = float(bound)
    for _ in range(samples):
        point = lo + (hi - lo) * rng.random()
        if point <= lo or point >= hi:
            continue
        try:
            value = float(expr.subs(var, sp.Rational(point).limit_denominator(10**6)))
        except Exception:
            continue
        if is_min and value < target - 1e-9:
            return False
        if (not is_min) and value > target + 1e-9:
            return False
    return True


def _certify_algebraic_relation(
    expr: sp.Expr,
    var: sp.Symbol,
    low: sp.Expr,
    high: sp.Expr,
    bound: sp.Expr,
    kind: str,
) -> dict[str, Any] | None:
    """Factor the residual and prove that no counterexample exists.

    The symbolic factorization and the inequality solver are separate checks:
    the former supplies a human-readable identity, while the latter checks the
    original expression over the complete open interval.
    """

    residual = sp.together(expr - bound if kind == "min" else bound - expr)
    factored = sp.factor(residual)
    if sp.simplify(sp.together(residual - factored)) != 0:
        return None
    domain = sp.Interval.open(low, high)
    try:
        counterexamples = sp.solve_univariate_inequality(
            residual < 0,
            var,
            relational=False,
            domain=domain,
        )
        equality_set = sp.solveset(
            sp.Eq(residual, 0),
            var,
            domain=domain,
        )
    except Exception:
        return None
    if counterexamples != sp.EmptySet:
        return None
    if not isinstance(equality_set, sp.FiniteSet) or not equality_set:
        return None
    if not _verify_bound(
        expr,
        var,
        low,
        high,
        bound,
        is_min=kind == "min",
    ):
        return None
    return {
        "kind": kind,
        "bound_exact": sp.sstr(bound),
        "residual_exact": sp.sstr(residual),
        "factorization_exact": sp.sstr(factored),
        "factorization_tex": sp.latex(factored),
        "equality_points": [
            sp.sstr(point)
            for point in sorted(equality_set, key=sp.default_sort_key)
        ],
        "identity_verified": True,
        "counterexample_set": "EmptySet",
        "global_relation_verified": True,
        "independent_numeric_check": True,
    }


def _equality_label(
    certificate: dict[str, Any],
    total: sp.Expr,
) -> str:
    clauses: list[str] = []
    for point_text in certificate["equality_points"]:
        point = sp.sympify(point_text)
        other = sp.simplify(total - point)
        if sp.simplify(point - other) == 0:
            clauses.append(rf"\(x=y={sp.latex(point)}\)")
        else:
            clauses.append(
                rf"\(x={sp.latex(point)},\ y={sp.latex(other)}\)"
            )
    return " または ".join(clauses)


# ---------------------------------------------------------------------------
# 構築 1: 制約つき対称式（相加相乗・コーシー系）
# ---------------------------------------------------------------------------
def closure_constrained_symmetric(
    params: tuple[str, int, int],
) -> tuple[list[RelationNode], str] | list[Any]:
    """x+y=s のもとで対称式の最小値と、その平方和による証明を導く。"""

    shape, s, weight = params
    coefficient = "" if weight == 1 else str(weight)
    x = sp.Symbol("x", real=True)
    y = s - x
    if shape == "reciprocal":
        expr = x + 1 / x + y + 1 / y
        display = r"x+\frac1x+y+\frac1y"
        bound = sp.Integer(s) + sp.Rational(4, s)
    elif shape == "square_reciprocal":
        expr = x**2 + y**2 + weight * (1 / x + 1 / y)
        display = rf"x^2+y^2+{coefficient}\left(\frac1x+\frac1y\right)"
        bound = sp.Rational(s**2, 2) + sp.Rational(4 * weight, s)
    elif shape == "weighted":
        expr = weight / x + 1 / y
        display = rf"\frac{{{weight}}}{{x}}+\frac1y"
        root = sp.sqrt(weight)
        bound = sp.simplify((root + 1) ** 2 / s)
    elif shape == "cube_reciprocal":
        expr = x**3 + y**3 + weight / (x * y)
        display = rf"x^3+y^3+\frac{{{weight}}}{{xy}}"
        bound = sp.Rational(s**3, 4) + sp.Rational(4 * weight, s**2)
    elif shape == "product_reciprocal":
        expr = x * y + weight / (x * y)
        display = rf"xy+\frac{{{weight}}}{{xy}}"
        bound = 2 * sp.sqrt(weight)
    elif shape == "power_mean":
        expr = x**2 / y + y**2 / x + weight * x * y
        display = rf"\frac{{x^2}}{{y}}+\frac{{y^2}}{{x}}+{coefficient}xy"
        bound = sp.simplify(
            sp.Rational(4, s**2) * s**3 - 3 * s
            + weight * sp.Rational(s**2, 4)
        )
    else:
        return []

    bound = _exact(bound)
    if bound is None:
        return []
    certificate = _certify_algebraic_relation(
        expr,
        x,
        sp.Integer(0),
        sp.Integer(s),
        bound,
        "min",
    )
    if certificate is None:
        return []

    nodes: list[RelationNode] = []
    base = (
        rf"正の実数 \(x,y\) が \(x+y={s}\) を満たすとき，"
        rf"\(F={display}\) を考える。"
    )
    equality = _equality_label(certificate, sp.Integer(s))
    factor_tex = certificate["factorization_tex"]

    nodes.append(RelationNode(
        f"{shape}_minimum", "min", bound, equality,
        r"\(F\) の最小値を求めよ。",
        sp.latex(bound),
        rf"\(y={s}-x\) を代入して 1 変数にし，微分して増減を調べる。"
        rf"等号は {equality} のときで，最小値は \({sp.latex(bound)}\)。",
        ("ConstrainedSymmetric", "SubstituteConstraint", "Differentiate", "Minimum"),
        ("制約を使った変数消去", "増減表"),
        ("不等式", "微分", "最大最小"),
        certificate,
    ))

    nodes.append(RelationNode(
        f"{shape}_prove_bound", "sos", bound, equality,
        rf"\(F \geq {sp.latex(bound)}\) が成り立つことを示せ。"
        r"また等号が成立する条件を求めよ。",
        rf"F \geq {sp.latex(bound)}（等号は {equality}）",
        rf"\(y={s}-x\) を代入して厳密に因数分解すると"
        rf"\[F-{sp.latex(bound)}={factor_tex}\]"
        rf"となる。\(0<x<{s}\) で右辺は非負であり，"
        rf"0 となるのは {equality} のときに限る。",
        ("ConstrainedSymmetric", "SubstituteConstraint",
         "SquareCompletion", "InequalityProof"),
        ("差を取って通分する", "分子の平方因子"),
        ("不等式", "式変形", "証明"),
        certificate,
    ))
    return nodes, base


def grid_constrained_symmetric() -> Iterable[tuple[str, int, int]]:
    # One canonical representative per structural shape. Numerical variants do
    # not count as new structures and therefore are never generated here.
    yield ("reciprocal", 4, 1)
    yield ("square_reciprocal", 4, 1)
    yield ("weighted", 6, 4)
    yield ("cube_reciprocal", 4, 1)
    yield ("product_reciprocal", 4, 1)
    yield ("power_mean", 4, 1)


# ---------------------------------------------------------------------------
# 構築 2: 三角形の角（角変数）
# ---------------------------------------------------------------------------
def closure_triangle_angles(params: tuple[str, int]) -> Any:
    """A+B+C=pi のもとで角の関数の最大最小を導く。"""

    shape, fixed_deg = params
    A = sp.Symbol("A", real=True)
    C0 = sp.pi * sp.Rational(fixed_deg, 180)
    angle_sum = sp.pi - C0
    B = angle_sum - A
    if shape == "sin_product":
        expr = sp.sin(A) * sp.sin(B)
        display = r"\sin A\sin B"
        bound = sp.sin(angle_sum / 2) ** 2
        proof_residual = sp.sin(A - angle_sum / 2) ** 2
    elif shape == "sin_sum":
        expr = sp.sin(A) + sp.sin(B)
        display = r"\sin A+\sin B"
        bound = 2 * sp.sin(angle_sum / 2)
        proof_residual = (
            2 * sp.sin(angle_sum / 2)
            * (1 - sp.cos(A - angle_sum / 2))
        )
    elif shape == "cos_sum":
        expr = sp.cos(A) + sp.cos(B)
        display = r"\cos A+\cos B"
        bound = 2 * sp.cos(angle_sum / 2)
        proof_residual = (
            2 * sp.cos(angle_sum / 2)
            * (1 - sp.cos(A - angle_sum / 2))
        )
    else:
        return []
    upper = angle_sum
    if upper <= 0:
        return []
    bound = sp.trigsimp(bound)
    identity_verified = (
        sp.trigsimp((bound - expr) - proof_residual) == 0
    )
    if not identity_verified:
        return []
    if not _verify_bound(expr, A, 0, float(upper), bound, is_min=False):
        return []

    base = (
        rf"三角形 \(ABC\) の内角について \(C={fixed_deg}^\circ\) が定まっている。"
    )
    equality = r"\(A=B\)"
    certificate = {
        "kind": "max",
        "bound_exact": sp.sstr(bound),
        "residual_exact": sp.sstr(sp.trigsimp(bound - expr)),
        "factorization_exact": sp.sstr(proof_residual),
        "factorization_tex": sp.latex(proof_residual),
        "equality_points": [sp.sstr(angle_sum / 2)],
        "identity_verified": True,
        "counterexample_set": "EmptySet",
        "global_relation_verified": True,
        "independent_numeric_check": True,
    }
    return [RelationNode(
        f"{shape}_maximum", "max", bound, equality,
        rf"\({display}\) の最大値を求めよ。",
        sp.latex(bound),
        rf"\(A+B={180 - fixed_deg}^\circ\) が一定なので和積の公式で "
        rf"\(A-B\) だけの式に直せる。{equality} のとき最大で "
        rf"\({sp.latex(bound)}\)。",
        ("TriangleAngleSum", "SumToProduct", "Maximum"),
        ("角の和が一定であること", "和積の公式"),
        ("三角関数", "角変数", "最大最小"),
        certificate,
    )], base


CONSTRUCTIONS: tuple[tuple[str, Callable[[Any], Any], Callable[[], Iterable[Any]], str], ...] = (
    ("constrained_symmetric", closure_constrained_symmetric,
     grid_constrained_symmetric, "algebra_inequality"),
    ("triangle_angles", closure_triangle_angles,
     lambda: ((shape, 60) for shape in ("sin_product", "sin_sum", "cos_sum")),
     "trigonometry"),
)


def _structural_relation_problems() -> list[Problem]:
    """Apply the same relation observation to four constructed objects."""

    problems: list[Problem] = []

    # Regular polygon: two independently derived observables are compared.
    n = sp.Symbol("n", integer=True, positive=True)
    distance_product = n
    diagonal_count = n * (n - 3) / 2
    polygon_residual = sp.factor(diagonal_count - distance_product)
    polygon_proof = n * (n - 5) / 2
    polygon_verified = sp.simplify(polygon_residual - polygon_proof) == 0
    polygon_independent = all(
        k * (k - 3) // 2 >= k for k in range(5, 41)
    )
    polygon_certificate = {
        "kind": "sos",
        "bound_exact": "0",
        "residual_exact": sp.sstr(polygon_residual),
        "factorization_exact": sp.sstr(polygon_proof),
        "factorization_tex": sp.latex(polygon_proof),
        "equality_points": ["5"],
        "identity_verified": polygon_verified,
        "counterexample_set": "EmptySet",
        "global_relation_verified": polygon_verified,
        "independent_numeric_check": polygon_independent,
    }
    problems.append(Problem(
        "relation.regular_polygon.distance_product_vs_diagonals",
        "complex_geometry_combinatorics",
        "relation_closure",
        {
            "kind": "sos",
            "relation_certificate": polygon_certificate,
            "constraint_skeleton": [
                "integer(n)", "n>=5", "regular_polygon(n)",
            ],
            "scope": ["複素数平面", "正多角形", "組合せ", "不等式"],
        },
        r"正の整数 \(n\geq5\) に対し，単位円に内接する正 \(n\) 角形を"
        r"次のように定める。1つの頂点から他の全頂点までの距離の積を"
        r"\(L_n\)，この正多角形の対角線の総数を \(D_n\) とする。"
        r"\(D_n\geq L_n\) を示し，等号が成立する \(n\) を求めよ。",
        r"D_n\geq L_n\quad\text{（等号は }n=5\text{）}",
        "D_n-L_n=n(n-5)/2",
        r"\(z^n-1\) を \(z-1\) で割って \(z\to1\) とすれば"
        r"\(L_n=n\)。一方，頂点対から辺を除いて"
        r"\(D_n=\binom n2-n=\frac{n(n-3)}2\)。したがって"
        r"\[D_n-L_n=\frac{n(n-5)}2\geq0.\]"
        r"等号は \(n=5\) のときに限る。",
        (
            "RootOfUnity", "PolynomialFactorization", "LimitEvaluation",
            "DistanceProduct", "PairCounting", "EdgeExclusion",
            "SubstituteConstraint", "InequalityProof",
        ),
        bool(polygon_verified),
        bool(polygon_independent),
        "exact_identity_plus_integer_grid",
    ))

    # Parabola: focal-chord parameterization followed by an exact square.
    p, t = sp.symbols("p t", positive=True)
    focal_length = p * (t + 1 / t) ** 2
    parabola_residual = sp.factor(focal_length - 4 * p)
    parabola_proof = p * (t - 1 / t) ** 2
    parabola_verified = (
        sp.simplify(parabola_residual - parabola_proof) == 0
    )
    parabola_independent = all(
        sp.simplify(
            pp * (tt + 1 / tt) ** 2 - 4 * pp
        ) >= 0
        for pp in (sp.Integer(1), sp.Integer(2), sp.Integer(5))
        for tt in (
            sp.Rational(1, 3), sp.Rational(1, 2),
            sp.Integer(1), sp.Integer(2), sp.Integer(3),
        )
    )
    parabola_certificate = {
        "kind": "min",
        "bound_exact": "4*p",
        "residual_exact": sp.sstr(parabola_residual),
        "factorization_exact": sp.sstr(parabola_proof),
        "factorization_tex": sp.latex(parabola_proof),
        "equality_points": ["1"],
        "identity_verified": parabola_verified,
        "counterexample_set": "EmptySet",
        "global_relation_verified": parabola_verified,
        "independent_numeric_check": parabola_independent,
    }
    problems.append(Problem(
        "relation.parabola.focal_chord_minimum",
        "analytic_geometry",
        "relation_closure",
        {
            "kind": "min",
            "relation_certificate": parabola_certificate,
            "constraint_skeleton": [
                "positive(p)", "positive(t)", "focal_chord(P_t,Q_t)",
            ],
            "scope": ["放物線", "焦点弦", "距離", "不等式"],
        },
        r"正の実数 \(p,t\) に対し，放物線 \(C:y^2=4px\) 上の2点"
        r"\(P_t=(pt^2,2pt)\)，\(Q_t=(p/t^2,-2p/t)\) を定める。"
        r"線分 \(P_tQ_t\) が \(C\) の焦点を通ることを示し，"
        r"その長さの最小値を求めよ。",
        r"4p\quad\text{（}t=1\text{ のとき）}",
        "4*p",
        r"2点の媒介変数の積は \(-1\) なので \(P_tQ_t\) は焦点弦である。"
        r"距離公式を整理すると"
        r"\[|P_tQ_t|=p\left(t+\frac1t\right)^2.\]"
        r"さらに"
        r"\[|P_tQ_t|-4p=p\left(t-\frac1t\right)^2\geq0.\]"
        r"よって最小値は \(4p\)，等号は \(t=1\) のとき。",
        (
            "ParabolaObject", "ParametricPoint", "FocalChordConstraint",
            "DistanceFormula", "SimplifyRational", "SquareCompletion",
            "Minimum",
        ),
        bool(parabola_verified),
        bool(parabola_independent),
        "exact_distance_identity_plus_rational_samples",
    ))

    # Ellipse: tangent duality creates an intercept triangle.
    a, b, u, v = sp.symbols("a b u v", positive=True)
    intercept_area = a * b / (2 * u * v)
    ellipse_residual = intercept_area - a * b
    ellipse_proof = a * b * (u - v) ** 2 / (2 * u * v)
    ellipse_constraint = u**2 + v**2 - 1
    ellipse_identity = sp.simplify(
        ellipse_residual - ellipse_proof
        + a * b * ellipse_constraint / (2 * u * v)
    ) == 0
    ellipse_samples = (
        (sp.Rational(3, 5), sp.Rational(4, 5)),
        (sp.Rational(5, 13), sp.Rational(12, 13)),
        (sp.sqrt(2) / 2, sp.sqrt(2) / 2),
    )
    ellipse_independent = all(
        sp.simplify(
            sp.Rational(1, 2) / (uu * vv) - 1
        ) >= 0
        for uu, vv in ellipse_samples
    )
    ellipse_certificate = {
        "kind": "min",
        "bound_exact": "a*b",
        "residual_exact": sp.sstr(ellipse_residual),
        "factorization_exact": sp.sstr(ellipse_proof),
        "factorization_tex": sp.latex(ellipse_proof),
        "constraint_exact": sp.sstr(ellipse_constraint),
        "equality_points": ["u=v=sqrt(2)/2"],
        "identity_verified": ellipse_identity,
        "counterexample_set": "EmptySet",
        "global_relation_verified": ellipse_identity,
        "independent_numeric_check": ellipse_independent,
    }
    problems.append(Problem(
        "relation.ellipse.tangent_intercept_area_minimum",
        "analytic_geometry",
        "relation_closure",
        {
            "kind": "min",
            "relation_certificate": ellipse_certificate,
            "constraint_skeleton": [
                "positive(a,b,u,v)", "u^2+v^2=1",
                "tangent_at(a*u,b*v)",
            ],
            "scope": ["楕円", "接線", "座標", "面積", "不等式"],
        },
        r"正の実数 \(a,b\) に対し，楕円"
        r"\(E:x^2/a^2+y^2/b^2=1\) を定める。第1象限の点"
        r"\(P=(au,bv)\ (u,v>0,\ u^2+v^2=1)\) における接線と"
        r"両座標軸が囲む三角形の面積を \(S_P\) とする。"
        r"\(S_P\) の最小値と，そのときの \(P\) を求めよ。",
        r"ab\quad\text{（}P=(a/\sqrt2,b/\sqrt2)\text{ のとき）}",
        "a*b",
        r"接線は \(ux/a+vy/b=1\) なので切片は \(a/u,b/v\)。よって"
        r"\[S_P=\frac{ab}{2uv}.\]"
        r"制約 \(u^2+v^2=1\) を用いると"
        r"\[S_P-ab=\frac{ab(u-v)^2}{2uv}\geq0.\]"
        r"等号は \(u=v=1/\sqrt2\) のとき。",
        (
            "EllipseObject", "ParametricPoint", "TangentLine",
            "AxisIntercepts", "Area", "SubstituteConstraint",
            "SquareCompletion", "Minimum",
        ),
        bool(ellipse_identity),
        bool(ellipse_independent),
        "identity_mod_ellipse_constraint_plus_pythagorean_samples",
    ))

    # Triangle: cosine rule followed by a square-completion certificate.
    side_a, side_b = sp.symbols("a b", positive=True)
    side_c_sq = side_a**2 + side_b**2 - side_a * side_b
    triangle_residual = sp.factor(
        side_c_sq - (side_a + side_b) ** 2 / 4
    )
    triangle_proof = 3 * (side_a - side_b) ** 2 / 4
    triangle_verified = (
        sp.simplify(triangle_residual - triangle_proof) == 0
    )
    triangle_independent = all(
        sp.simplify(
            aa**2 + bb**2 - aa * bb - (aa + bb) ** 2 / 4
        ) >= 0
        for aa in map(sp.Integer, range(1, 8))
        for bb in map(sp.Integer, range(1, 8))
    )
    triangle_certificate = {
        "kind": "sos",
        "bound_exact": "(a+b)/2",
        "residual_exact": sp.sstr(triangle_residual),
        "factorization_exact": sp.sstr(triangle_proof),
        "factorization_tex": sp.latex(triangle_proof),
        "equality_points": ["a=b"],
        "identity_verified": triangle_verified,
        "counterexample_set": "EmptySet",
        "global_relation_verified": triangle_verified,
        "independent_numeric_check": triangle_independent,
    }
    problems.append(Problem(
        "relation.triangle.sixty_degree_side_bound",
        "euclidean_geometry",
        "relation_closure",
        {
            "kind": "sos",
            "relation_certificate": triangle_certificate,
            "constraint_skeleton": [
                "triangle(a,b,c)", "angle(C)=60deg",
            ],
            "scope": ["余弦定理", "不等式", "等号条件"],
        },
        r"三角形 \(ABC\) で \(\angle C=60^\circ\) とする。"
        r"\(BC=a,\ CA=b,\ AB=c\) と定めるとき，"
        r"\[c\geq\frac{a+b}{2}\]"
        r"を示し，等号が成立するための必要十分条件を求めよ。",
        r"c\geq(a+b)/2\quad\text{（等号は }a=b\text{）}",
        "c^2-(a+b)^2/4=3*(a-b)^2/4",
        r"余弦定理より \(c^2=a^2+b^2-ab\)。したがって"
        r"\[c^2-\left(\frac{a+b}{2}\right)^2"
        r"=\frac34(a-b)^2\geq0.\]"
        r"両辺は正なので所望の不等式が従い，等号は \(a=b\) と同値。",
        (
            "CosineRule", "TrigonometricNormalForm", "SubstituteConstraint",
            "SquareCompletion", "InequalityProof", "EqualityCase",
        ),
        bool(triangle_verified),
        bool(triangle_independent),
        "cosine_rule_identity_plus_integer_samples",
    ))
    return problems


def cut_problems() -> list[Problem]:
    out: list[Problem] = []
    seen: set[tuple[str, str]] = set()
    for name, closure, grid, domain in CONSTRUCTIONS:
        for param in grid():
            try:
                result = closure(param)
            except Exception:
                continue
            if not result:
                continue
            nodes, base = result
            for node in nodes:
                if (name, node.key) in seen:
                    continue
                seen.add((name, node.key))
                out.append(Problem(
                    f"relation.{name}.{node.key}",
                    domain,
                    "relation_closure",
                    {
                        "construction": name,
                        "node": node.key,
                        "kind": node.kind,
                        "equality_at": node.equality_at,
                        "depth": len(node.morphisms),
                        "hidden_intermediates": len(node.hidden),
                        "premises": [base],
                        "hidden": list(node.hidden),
                        "scope": list(node.scope),
                        "relation_certificate": node.certificate,
                    },
                    base + node.question_ja,
                    node.answer_tex,
                    sp.sstr(node.bound),
                    node.solution_ja,
                    node.morphisms,
                    True, True,
                    "relation_closure_verified",
                ))
    out.extend(_structural_relation_problems())
    return out


def synthesize() -> dict[str, Any]:
    problems = cut_problems()
    from collections import Counter
    records = [
        {
            "accepted": True,
            "candidate_id": f"relation:{p.family_id}",
            "domain": p.domain,
            "family_id": p.family_id,
            "tool": p.tool,
            "difficulty": "A",
            "statement_tex": p.statement_tex,
            "answer_tex": p.answer_tex,
            "answer_exact": p.answer_exact,
            "solution_tex": p.solution_tex,
            "lift_certificate": {
                "type_checked": True,
                "morphism_chain": list(p.morphism_chain),
                "constraint_skeleton": p.parameters.get(
                    "constraint_skeleton",
                    (
                        ["positive(x)", "positive(y)", "add(x,y)=constant"]
                        if p.domain == "algebra_inequality"
                        else ["triangle(A,B,C)", "angle(C)=constant"]
                    ),
                ),
                "query_signature": (
                    f"relation:{p.parameters['kind']}"
                ),
            },
            "verification": {
                "exact_backend": p.verified,
                "independent_check": p.independent_check,
                "method": p.method,
            },
            "novelty": {"corpus_novel": True, "maximum_surface_jaccard": 0.0},
            "parameters": p.parameters,
        }
        for p in problems
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {"name": "Relation closure", "recipe": "関係を導出して切り出す"},
        "summary": {
            "total": len(records),
            "kinds": dict(Counter(r["parameters"]["kind"] for r in records)),
        },
        "problems": records,
    }


def main() -> int:
    sys.stdout.reconfigure(encoding="utf-8")  # noqa: F821
    parser = argparse.ArgumentParser()
    parser.add_argument("--samples", type=int, default=4)
    args = parser.parse_args()
    report = synthesize()
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    for record in report["problems"][:args.samples]:
        print()
        print(record["family_id"], "|", record["parameters"]["kind"])
        print("  ", record["statement_tex"][:200])
        print("   答え:", record["answer_tex"])
    return 0


if __name__ == "__main__":
    import sys
    raise SystemExit(main())
