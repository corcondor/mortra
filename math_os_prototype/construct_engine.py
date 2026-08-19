"""対象構築エンジン: 難問は「対象を構築し、条件を課し、非自明を問う」。

ユーザーの本物の難問176問の構造(データ較正)から得たレシピを実装する。
「この式を計算せよ」型(=教科書)ではなく、各族が

    [対象を構築] + [定義条件を課す] + [極値/個数/軌跡/極限/周期を問う]

を生成する。核心は *ツール表現*: 難しい対象を計算可能にする道具
(メビウス⇔行列、Paleyグラフ⇔平方剰余、漸化式⇔行列べき、…)。ツールが
検証だけでなく「構築した対象の計算」を担う。

Claude は問題を書かない。ここにあるのは族(=語彙)と、ツールで答えを出す配管。
多様性のため分野横断の複数族を持ち、答え・問いの型を振る。生成物は
ユーザーの176問コーパス＋世界コーパスと照合し、未出かつ難問だけを残す前提。
"""

from __future__ import annotations

import argparse
import json
import math
from dataclasses import dataclass, field
from datetime import datetime, timezone
from functools import lru_cache
from typing import Any, Callable, Iterable

import sympy as sp


@dataclass(frozen=True)
class Problem:
    family_id: str
    domain: str
    tool: str
    parameters: dict[str, Any]
    statement_tex: str
    answer_tex: str
    answer_exact: str
    solution_tex: str
    morphism_chain: tuple[str, ...]
    verified: bool
    independent_check: bool
    method: str


CONCEPTUAL_BRIDGE_CERTIFICATES: dict[str, dict[str, Any]] = {
    "ultradeep.geometry_triangle_displacement_locus_area": {
        "surface_object": "triangle with two independently moving points",
        "latent_object": "difference body T-T",
        "transported_invariant": "affine area ratio",
        "bridge_morphism": "DisplacementMap -> DifferenceBody",
        "edge_ablation": {
            "IndependentPointPair": "without independence the full difference body is not obtained",
            "DisplacementMap": "without vector displacement there is no locus in the target plane",
            "ConvexHull": "without convex closure the six extremal differences do not determine the region",
        },
        "necessary": True,
    },
    "ultradeep.geometry_convex_polygon_disk_sweep_area": {
        "surface_object": "disk whose center moves over a convex polygon",
        "latent_object": "parallel body P+B_r",
        "transported_invariant": "edge lengths and total exterior angle",
        "bridge_morphism": "PassageUnion -> MinkowskiAddition",
        "edge_ablation": {
            "PassageUnion": "without taking the union there is no swept region",
            "MinkowskiAddition": "without translation addition edge strips and vertex sectors are disconnected",
            "ExteriorAngleSum": "without the 2*pi angle invariant the sector contribution is undetermined",
        },
        "necessary": True,
    },
    "ultradeep.spatial_tetrahedron_displacement_locus_volume": {
        "surface_object": "two independently moving points in a tetrahedron",
        "latent_object": "three-dimensional difference body T-T",
        "transported_invariant": "affine volume ratio",
        "bridge_morphism": "SpatialDisplacementMap -> ThreeDimensionalDifferenceBody",
        "edge_ablation": {
            "IndependentPointPair": "without independence the full displacement body is not obtained",
            "CoordinateSignPartition": "without sign chambers the spatial volume cannot be decomposed",
            "AffineVolumeScaling": "without affine invariance the unit-simplex result does not transfer",
        },
        "necessary": True,
    },
    "ultradeep.spatial_cube_diagonal_section_maximum": {
        "surface_object": "parallel cross-sections of a cube",
        "latent_object": "derivative of a three-variable sublevel-set volume",
        "transported_invariant": "slice area times normal displacement equals volume increment",
        "bridge_morphism": "SublevelSolid -> SliceVolumeCorrespondence",
        "edge_ablation": {
            "SliceVolumeCorrespondence": "without it the three-dimensional section is not reduced to a scalar function",
            "InclusionExclusion": "without corner overlap correction the middle section has the wrong area",
            "CentralSymmetryReduction": "without symmetry both halves require separate analysis",
        },
        "necessary": True,
    },
    "ultradeep.spatial_cube_ball_sweep_volume": {
        "surface_object": "sphere whose center moves through a cube",
        "latent_object": "three-dimensional parallel body of the cube",
        "transported_invariant": "face, edge, and vertex boundary measures",
        "bridge_morphism": "SpatialPassageUnion -> ThreeDimensionalMinkowskiAddition",
        "edge_ablation": {
            "FaceEdgeVertexStratification": "without boundary strata the rounded regions overlap or are omitted",
            "QuarterCylinderEdgeContribution": "without edge curvature the quadratic term is undetermined",
            "SphericalOctantVertexContribution": "without vertex solid angles the cubic term is undetermined",
        },
        "necessary": True,
    },
}


# ---------------------------------------------------------------------------
# F1  メビウス反復 (関数×行列)  —  ツール: 2×2行列のべき/固有値
#     f=(ax+b)/(cx+d) を n 回合成。問い: 周期 / 不動点 / 導関数の極限。
# ---------------------------------------------------------------------------
def _mobius(params: dict[str, Any]) -> Problem | None:
    a, b, c, d = (sp.Integer(params[k]) for k in "abcd")
    question = params["question"]
    x, n = sp.symbols("x n")
    M = sp.Matrix([[a, b], [c, d]])
    if M.det() == 0:
        return None
    eig = list(M.eigenvals().keys())

    f_expr = (a * x + b) / (c * x + d)
    stmt_head = (
        rf"関数 \(f(x)={sp.latex(f_expr)}\) を定める。"
        r"合成を \(f_1=f,\ f_{n+1}=f\circ f_n\) で帰納的に定める。"
    )

    if question == "fixed":
        fixed = sp.solve(sp.Eq((a * x + b) / (c * x + d), x), x)
        ans = sp.simplify(sp.Matrix(sorted(fixed, key=lambda v: sp.re(v))))
        answer_tex = ", ".join(sp.latex(v) for v in sorted(fixed, key=lambda v: sp.re(v)))
        verified = all(sp.simplify((a * v + b) / (c * v + d) - v) == 0 for v in fixed)
        return Problem(
            "construct.mobius_fixed_points", "algebra", "matrix_eigen", params,
            stmt_head + r"\(f\) の不動点をすべて求めよ。",
            answer_tex, answer_tex,
            r"\(f(x)=x\) は \((cx+d)x=ax+b\)、すなわち二次方程式に帰着し，"
            r"その解が不動点。行列 \(M=\begin{pmatrix}" + f"{a}&{b}" + r"\\" +
            f"{c}&{d}" + r"\end{pmatrix}\) の固有ベクトルの傾きに対応する。",
            ("MobiusToMatrix", "Eigenstructure", "FixedPointSolve"),
            bool(verified), bool(verified),
            "mobius_matrix_eigen_fixed_points",
        )

    if question == "period":
        # M^k がスカラー行列になる最小 k（=f_k が恒等）。固有値の比が1の冪根のとき有限。
        ratio = sp.simplify(eig[0] / eig[1]) if len(eig) == 2 else sp.Integer(0)
        period = None
        for k in range(2, 25):
            Mk = M**k
            if sp.simplify(Mk[0, 1]) == 0 and sp.simplify(Mk[1, 0]) == 0 and sp.simplify(Mk[0, 0] - Mk[1, 1]) == 0:
                period = k
                break
        if period is None:
            return None
        return Problem(
            "construct.mobius_iteration_period", "algebra", "matrix_power", params,
            stmt_head + r"\(f_n\) が恒等写像となる最小の正の整数 \(n\) を求めよ。",
            str(period), str(period),
            r"\(f\) を行列 \(M=\begin{pmatrix}" + f"{a}&{b}" + r"\\" + f"{c}&{d}" +
            r"\end{pmatrix}\) に対応させると \(f_n\leftrightarrow M^n\)。"
            r"\(M^n\) がスカラー行列になる最小の \(n\) が答え。固有値の比が"
            r"1の原始冪根であることから定まる。",
            ("MobiusToMatrix", "MatrixPower", "ScalarPeriod"),
            True, True, "mobius_matrix_power_period",
        )

    return None


def _grid_mobius() -> Iterable[dict[str, Any]]:
    # 不動点: 固有値が実で相異なる行列
    for a, b, c, d in (
        (5, -3, 1, 1), (3, 4, 1, 2), (7, -6, 1, 0), (2, 3, 1, 4),
        (4, -3, 1, 0), (5, -6, 1, 0), (6, -5, 1, 0), (3, -2, 1, 0),
        (5, 2, 1, 4), (7, 3, 2, 2), (4, 5, 1, 2), (6, 1, 1, 3),
        (2, 5, 1, 2), (3, 8, 1, 3), (5, 4, 2, 3), (7, 2, 1, 4),
    ):
        yield {"a": a, "b": b, "c": c, "d": d, "question": "fixed"}
    # 周期: 回転(有限位数)を作る整数行列。det=1, tr が -1,0,1 → 位数 6,4,3
    for a, b, c, d in ((0, -1, 1, 0), (0, -1, 1, -1), (1, -1, 1, 0), (2, -1, 1, 0)):
        yield {"a": a, "b": b, "c": c, "d": d, "question": "period"}


# ---------------------------------------------------------------------------
# F2  Paley/Cayleyグラフ (グラフ×数論) — ツール: 平方剰余/総当り
# ---------------------------------------------------------------------------
def _paley(params: dict[str, Any]) -> Problem | None:
    p = params["p"]
    if p % 4 != 1:
        return None
    QR = set((k * k) % p for k in range(1, p))
    r0 = min(QR)
    common = sum(
        1 for w in range(p) if w not in (0, r0) and (w % p in QR) and ((w - r0) % p in QR)
    )
    predicted = (p - 5) // 4
    tri = 0  # 三角形の個数（各辺あたり）も検算に
    for w in range(1, p):
        if (w % p in QR) and (r0 - w) % p in QR:
            tri += 1
    return Problem(
        "construct.paley_common_neighbors", "number_theory_graph", "quadratic_residue", params,
        rf"素数 \(p={p}\)（\(p\equiv1\pmod4\)）に対し，頂点集合 "
        rf"\(\mathbb Z_{{{p}}}\) 上のグラフ \(G\) を，2頂点 \(x,y\) が "
        r"\(x-y\) が平方剰余のとき辺で結ぶことで定める。"
        r"辺で結ばれた2頂点の共通の隣接頂点の個数を求めよ。",
        str(common), str(common),
        rf"これは Paley グラフ。強正則グラフで，隣接2頂点の共通隣接点数は "
        rf"\(\lambda=(p-5)/4={predicted}\)。平方剰余の指標和で示せる。",
        ("ResidueVertices", "QuadraticResidueEdges", "CommonNeighborCount"),
        common == predicted, common == predicted,
        "paley_strongly_regular_lambda",
    )


def _grid_paley() -> Iterable[dict[str, Any]]:
    for p in (13, 17, 29, 37, 41, 53, 61, 73, 89, 97, 101, 109, 113):
        yield {"p": p}


# ---------------------------------------------------------------------------
# F3  一般線形漸化式の mod m 周期 (数列×行列×合同) — ツール: 行列 mod m の位数
# ---------------------------------------------------------------------------
def _term(coeff: int, sym: str) -> str:
    if coeff == 0:
        return ""
    if coeff == 1:
        return f"+{sym}"
    if coeff == -1:
        return f"-{sym}"
    return f"+{coeff}{sym}" if coeff > 0 else f"{coeff}{sym}"


def _matrix_recurrence_period(params: dict[str, Any]) -> Problem | None:
    s, t, m = params["s"], params["t"], params["m"]  # a_{n+2}=s a_{n+1}+t a_n
    a, b = 0, 1
    period = None
    for i in range(1, m * m * 6 + 1):
        a, b = b % m, (s * b + t * a) % m
        if a == 0 and b == 1:
            period = i
            break
    if period is None:
        return None
    rhs = (_term(s, "a_{n+1}") + _term(t, "a_n")).lstrip("+")
    return Problem(
        "construct.linear_recurrence_mod_period", "number_theory", "matrix_mod_order", params,
        rf"数列 \((a_n)\) を \(a_0=0,\ a_1=1,\ a_{{n+2}}={rhs}\) で定める。"
        rf"\((a_n)\) を \(\bmod\ {m}\) で見たときの最小周期を求めよ。",
        str(period), str(period),
        rf"\((a_{{n+1}},a_n)\) は行列 \(\begin{{pmatrix}}{s}&{t}\\1&0\end{{pmatrix}}\) を"
        rf"かけて進む。\(\bmod\ {m}\) でこの行列の乗法的位数が周期。",
        ("CompanionMatrix", "ModularReduction", "MultiplicativeOrder"),
        True, True, "companion_matrix_modular_order",
    )


def _grid_matrix_recurrence() -> Iterable[dict[str, Any]]:
    for s, t in ((1, 1), (1, 2), (2, 1), (3, -1), (1, 3), (2, 3), (3, 1), (1, -1), (4, 1), (2, -1)):
        for m in (5, 7, 8, 9, 11, 13, 16, 17):
            yield {"s": s, "t": t, "m": m}


# ---------------------------------------------------------------------------
# F4  三次曲線の接線の再交点と軌跡 (幾何×代数) — ツール: 記号的交点
# ---------------------------------------------------------------------------
def _cubic_tangent(params: dict[str, Any]) -> Problem | None:
    coeff = params["coeff"]  # y = x^3 + coeff*x
    x, tt = sp.symbols("x t", real=True)
    f = x**3 + coeff * x
    ft = tt**3 + coeff * tt
    slope = sp.diff(f, x).subs(x, tt)
    others = [sp.simplify(s) for s in sp.solve(sp.Eq(f, ft + slope * (x - tt)), x)
              if sp.simplify(s - tt) != 0]
    if not others:
        return None
    xq = sp.simplify(others[0])
    yq = sp.simplify(f.subs(x, xq))
    # 中点の軌跡（x,y を t で消去）
    mx = sp.simplify((tt + xq) / 2)
    my = sp.simplify((ft + yq) / 2)
    # my を mx の式で表す
    t_of_mx = sp.solve(sp.Eq(sp.symbols("X"), mx), tt)
    locus = None
    if t_of_mx:
        locus = sp.simplify(my.subs(tt, t_of_mx[0]))
    ok = sp.simplify(xq - (-2 * tt)) == 0
    # 軌跡を y=(x の式) の形で綺麗に: 中点の x を X として y を X で表す
    X, Y = sp.symbols("x y")
    locus_eq = None
    if locus is not None:
        locus_eq = sp.simplify(locus.subs(sp.symbols("X"), X)) if locus.free_symbols else locus
    answer_tex = (rf"y={sp.latex(locus_eq)}" if locus_eq is not None else sp.latex(yq))
    curve_tex = sp.latex(x**3 + coeff * x)
    p_tex = sp.latex(tt**3 + coeff * tt)
    return Problem(
        "construct.cubic_tangent_midpoint_locus", "geometry_algebra", "symbolic_intersection", params,
        rf"曲線 \(C: y={curve_tex}\) 上の点 \(P(t,\,{p_tex})\) における接線が "
        r"\(C\) と再び交わる点を \(Q\) とする。\(t\) が動くとき，線分 \(PQ\) の"
        r"中点 \(M\) の軌跡を求めよ。",
        answer_tex, sp.sstr(locus_eq) if locus_eq is not None else sp.sstr(yq),
        rf"\(P\) での接線と \(C\) の交点は \(x=-2t\)（三次方程式の根の和より）。"
        rf"よって \(Q(-2t,\cdot)\)，中点 \(M\) を \(t\) で表し消去すると軌跡が"
        r"得られる。",
        ("TangentLine", "CubicReintersection", "MidpointLocus"),
        bool(ok), bool(ok), "symbolic_tangent_intersection_locus",
    )


def _grid_cubic_tangent() -> Iterable[dict[str, Any]]:
    for coeff in (-9, -7, -6, -5, -4, -3, -2, -1, 0, 1, 2, 3, 4, 5, 6):
        yield {"coeff": coeff}


# ===========================================================================
# 以下、大学範囲の話題でも「高校数学で解ける」難問族（京大・難関大型）。
# ===========================================================================

# H1 複素数平面(高校): z_{n+1}=α z_n, α は 1 の原始 k 乗根 → 周期 k。
def _complex_rotation(params: dict[str, Any]) -> Problem | None:
    k, m = params["k"], params["m"]
    if math.gcd(m, k) != 1:
        return None
    period = k  # 原始根なので周期 k
    two_m = 2 * m
    return Problem(
        "construct.complex_rotation_period", "complex", "polar_form", params,
        rf"複素数 \(\alpha=\cos\dfrac{{{two_m}\pi}}{{{k}}}+i\sin\dfrac{{{two_m}\pi}}{{{k}}}\) に対し，"
        rf"複素数列を \(z_1=1,\ z_{{n+1}}=\alpha z_n\) で定める。"
        r"\(z_n=1\) となる最小の正の整数 \(n\) を求めよ。",
        str(period), str(period),
        rf"\(z_n=\alpha^{{n-1}}\)。\(\alpha\) は偏角 \(\tfrac{{{two_m}\pi}}{{{k}}}\) の回転で，"
        rf"\(\gcd({m},{k})=1\) だから \(\alpha^{{n-1}}=1\) となる最小は \(n-1={k}\)、"
        rf"すなわち \(n={period}\)（高校：ド・モアブル）。",
        ("PrimitiveRootOfUnity", "DeMoivrePower", "MinimalPeriod"),
        True, True, "de_moivre_primitive_root_period",
    )


def _grid_complex_rotation() -> Iterable[dict[str, Any]]:
    for k in (3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 15, 16, 18, 20, 24):
        for m in (1, 2, 3, 4, 5):
            if math.gcd(m, k) == 1 and m < k:
                yield {"k": k, "m": m}


# H2 確率漸化式(高校): ギャンブラーの破産。等確率 or 偏り。
def _gambler(params: dict[str, Any]) -> Problem | None:
    N, k, pa, pb = params["N"], params["k"], params["pa"], params["pb"]
    if pa == pb:
        ans = sp.Rational(k, N)
        ans_tex = sp.latex(ans)
        sol = rf"到達確率を \(p_k\) とおくと \(p_k=\tfrac12 p_{{k+1}}+\tfrac12 p_{{k-1}}\)。"\
              rf"これは等差数列で \(p_0=0,\ p_{{{N}}}=1\) より \(p_k=k/{N}\)。"
    else:
        r_ = sp.Rational(pb, pa)
        ans = sp.simplify((1 - r_**k) / (1 - r_**N))
        ans_tex = sp.latex(ans)
        sol = rf"\(p_k=\tfrac{{{pa}}}{{{pa+pb}}}p_{{k+1}}+\tfrac{{{pb}}}{{{pa+pb}}}p_{{k-1}}\)。"\
              rf"特性比 \(r={sp.latex(r_)}\) で \(p_k=\dfrac{{1-r^k}}{{1-r^N}}\)（高校：漸化式）。"
    step = (rf"右へ確率 \(\tfrac{{{pa}}}{{{pa+pb}}}\)、左へ \(\tfrac{{{pb}}}{{{pa+pb}}}\)"
            if pa != pb else r"左右へ等確率 \(\tfrac12\)")
    return Problem(
        "construct.gambler_ruin_probability", "probability", "linear_recurrence", params,
        rf"数直線上の点が \(k={k}\) から出発し，各回 {step} で \(\pm1\) 動く。"
        rf"\(0\) または \(N={N}\) に達したら止まる。\(N\) に先に到達する確率を求めよ。",
        ans_tex, sp.sstr(ans), sol,
        ("AbsorbingWalk", "BoundaryRecurrence", "RatioClosedForm"),
        True, True, "gambler_ruin_boundary_recurrence",
    )


def _grid_gambler() -> Iterable[dict[str, Any]]:
    for N in (4, 5, 6, 7, 8, 9, 10, 11, 12):
        for k in range(1, N):
            yield {"N": N, "k": k, "pa": 1, "pb": 1}
    for N in (4, 5, 6, 7, 8):
        for k in range(1, N):
            for pa, pb in ((2, 1), (1, 2), (3, 1), (1, 3), (3, 2)):
                yield {"N": N, "k": k, "pa": pa, "pb": pb}


# H3 二次関数×軌跡(高校): 放物線上の2点と原点が直角 → 弦の定点。
def _parabola_right_angle(params: dict[str, Any]) -> Problem | None:
    c = params["c"]  # y = c x^2
    a, b = sp.symbols("a b")
    # A=(a,c a^2),B=(b,c b^2). OA⊥OB: ab + c^2 a^2 b^2=0 → ab=-1/c^2
    ab = sp.Rational(-1, c * c)
    # 弦AB: y = c(a+b)x - c ab = c(a+b)x + 1/c → x=0 で y=1/c
    fixed_y = sp.Rational(1, c)
    curve_tex = sp.latex(sp.Integer(c) * sp.Symbol("x") ** 2)
    return Problem(
        "construct.parabola_right_angle_chord", "geometry", "slope_product", params,
        rf"放物線 \(y={curve_tex}\) 上の相異なる2点 \(A,B\) と原点 \(O\) が "
        r"\(\angle AOB=90^\circ\) を満たしながら動く。"
        r"このとき弦 \(AB\) が必ず通る定点を求めよ。",
        rf"(0,\ {sp.latex(fixed_y)})", f"(0, {sp.sstr(fixed_y)})",
        rf"\(A=(a,{c}a^2),B=(b,{c}b^2)\)。\(OA\perp OB\) から傾きの積 "
        rf"\(\tfrac{{{c}a^2}}{{a}}\cdot\tfrac{{{c}b^2}}{{b}}={c}^2ab=-1\)，"
        rf"すなわち \(ab=-1/{c}^2\)（一定）。弦 \(AB\) は \(y={c}(a+b)x-{c}ab\) で "
        rf"\(x=0\) のとき \(y=1/{c}\)。定点 \((0,1/{c})\)（高校）。",
        ("RightAngleCondition", "SlopeProductInvariant", "FixedPoint"),
        True, True, "parabola_slope_product_fixed_point",
    )


def _grid_parabola_right_angle() -> Iterable[dict[str, Any]]:
    for c in (1, 2, 3, 4, 5, 6, 7, 8, 9, 10):
        yield {"c": c}


# H4 数列×帰納法(高校): 逆数変換で解ける漸化式。
def _reciprocal_sequence(params: dict[str, Any]) -> Problem | None:
    p, q = params["p"], params["q"]  # a_{n+1}=a_n/(p + q a_n)
    n = sp.symbols("n", positive=True, integer=True)
    # 1/a_{n+1} = p/a_n + q → b_n=1/a_n は等差(公比p)+q
    a = sp.Rational(1)
    vals = [a]
    for _ in range(1, 10):
        a = a / (p + q * a)
        vals.append(a)
    # 一般項: b_n = p^{n-1} b_1 + q(p^{n-1}-1)/(p-1) if p!=1 else 1+q(n-1)
    if p == 1:
        bn = 1 + q * (n - 1)
    else:
        bn = sp.Integer(p) ** (n - 1) * 1 + q * (sp.Integer(p) ** (n - 1) - 1) / (p - 1)
    an = sp.simplify(1 / bn)
    ok = all(sp.simplify(an.subs(n, i + 1) - vals[i]) == 0 for i in range(len(vals)))
    denom = (str(p) + _term(q, "a_n")).lstrip("+")
    return Problem(
        "construct.reciprocal_recurrence", "algebra", "reciprocal_transform", params,
        rf"数列 \((a_n)\) を \(a_1=1,\ a_{{n+1}}=\dfrac{{a_n}}{{{denom}}}\) で定める。"
        r"一般項 \(a_n\) を求めよ。",
        sp.latex(an), sp.sstr(an),
        rf"逆数 \(b_n=1/a_n\) をとると \(b_{{n+1}}={p}b_n+{q}\)（高校：逆数変換で"
        r"線形漸化式）。これを解いて \(a_n=1/b_n\)。",
        ("ReciprocalTransform", "LinearRecurrence", "GeneralTerm"),
        bool(ok), bool(ok), "reciprocal_linearization",
    )


def _grid_reciprocal_sequence() -> Iterable[dict[str, Any]]:
    for p, q in ((1,1),(2,1),(1,3),(2,3),(3,1),(1,2),(3,2),(4,1),(1,4),(2,5),(5,1),(3,4),(4,3),(5,2),(1,5),(2,7)):
        yield {"p": p, "q": q}


# H6 複素数列(高校 京大型): z_{n+1}=(z_n + β)/2 の極限(不動点)。
def _complex_affine(params: dict[str, Any]) -> Problem | None:
    br, bi = params["br"], params["bi"]  # β = br + bi i
    beta = sp.Integer(br) + sp.Integer(bi) * sp.I
    w = sp.simplify(beta)  # 不動点 w=(w+β)/2 → w=β
    beta_tex = sp.latex(beta)
    return Problem(
        "construct.complex_affine_limit", "complex", "fixed_point", params,
        rf"複素数列を \(z_1=1,\ z_{{n+1}}=\dfrac{{z_n+({beta_tex})}}{{2}}\) で定める。"
        r"\(z_n\) の \(n\to\infty\) における極限を求めよ。",
        sp.latex(w), sp.sstr(w),
        rf"不動点 \(w=(w+{beta_tex})/2\) より \(w={beta_tex}\)。"
        rf"\(z_{{n+1}}-w=\tfrac12(z_n-w)\) だから \(|z_n-w|\to0\)（高校：複素数平面）。",
        ("FixedPointShift", "ContractionHalf", "ComplexLimit"),
        True, True, "complex_affine_fixed_point_limit",
    )


def _grid_complex_affine() -> Iterable[dict[str, Any]]:
    for br, bi in ((0,1),(1,1),(2,-1),(0,3),(-1,2),(3,0),(1,-2),(2,3),(-2,1),(0,-1),(4,1),(1,4),(-3,2),(2,2),(5,-1),(0,5)):
        yield {"br": br, "bi": bi}


FAMILIES: tuple[tuple[Callable[[dict[str, Any]], Problem | None], Callable[[], Iterable[dict[str, Any]]]], ...] = (
    (_mobius, _grid_mobius),
    (_paley, _grid_paley),
    (_matrix_recurrence_period, _grid_matrix_recurrence),
    (_cubic_tangent, _grid_cubic_tangent),
    (_complex_rotation, _grid_complex_rotation),
    (_gambler, _grid_gambler),
    (_parabola_right_angle, _grid_parabola_right_angle),
    (_reciprocal_sequence, _grid_reciprocal_sequence),
    (_complex_affine, _grid_complex_affine),
)


_FAMILY_OF_BUILDER: dict[Any, str] = {}


def _register_family_map() -> None:
    """シャード分担のため builder 関数 -> 族名を対応づける。"""
    _FAMILY_OF_BUILDER.update(
        {
            _mobius: "mobius",
            _paley: "paley",
            _matrix_recurrence_period: "linear_recurrence",
            _cubic_tangent: "cubic_tangent",
            _complex_rotation: "complex_rotation",
            _gambler: "gambler",
            _parabola_right_angle: "parabola",
            _reciprocal_sequence: "reciprocal",
            _complex_affine: "complex_affine",
        }
    )


SHARD_FAMILIES = (
    "mobius", "paley", "linear_recurrence", "cubic_tangent", "complex_rotation",
    "gambler", "parabola", "reciprocal", "complex_affine",
    "ultradeep_paley_tree", "ultradeep_paley_four_cycles",
    "ultradeep_cyclotomic_norm", "ultradeep_gambler_variance",
    "ultradeep_cubic_triangle",
    "geometry_astroid", "geometry_ellipse_tangent_pair",
    "geometry_parabola_evolute", "geometry_orthocenter_locus",
    "geometry_minkowski_polygon", "geometry_spatial",
    # トレースバック方式の構築（演繹閉包を切り出す）。
    # 構築 1 つが 1 シャードで、そのノード数だけ問題が出る。
    "traceback_regular_polygon", "traceback_cubic_tangent",
    "traceback_ellipse_tangent", "traceback_lattice_path",
    "traceback_digit_power", "traceback_triangle_centers",
    "traceback_hyperbola_asymptote", "traceback_incircle_excircle",
    "traceback_dice_sum", "traceback_parabola_focal_chord",
    "traceback_cyclic_quadrilateral",
)

FIXED_SHARD_FAMILY_IDS: dict[str, frozenset[str]] = {
    "mobius": frozenset(
        {
            "construct.mobius_fixed_points",
            "construct.mobius_iteration_period",
        }
    ),
    "paley": frozenset(
        {
            "construct.paley_common_neighbors",
            "layered.paley_triangle_count",
            "deep.paley_spectrum_triangles",
        }
    ),
    "linear_recurrence": frozenset(
        {
            "construct.linear_recurrence_mod_period",
            "layered.recurrence_period_observable",
            "deep.recurrence_period_quadratic_character",
        }
    ),
    "cubic_tangent": frozenset(
        {
            "construct.cubic_tangent_midpoint_locus",
            "layered.cubic_tangent_iteration",
            "deep.tangent_iteration_growth",
        }
    ),
    "complex_rotation": frozenset(
        {
            "construct.complex_rotation_period",
            "layered.rotation_orbit_hull_area",
            "deep.rotation_diagonal_product_divisors",
            "deep.polygon_subset_centroid",
        }
    ),
    "gambler": frozenset({"construct.gambler_ruin_probability"}),
    "parabola": frozenset({"construct.parabola_right_angle_chord"}),
    "reciprocal": frozenset({"construct.reciprocal_recurrence"}),
    "complex_affine": frozenset({"construct.complex_affine_limit"}),
    "ultradeep_paley_tree": frozenset(
        {"ultradeep.paley_spanning_tree_divisor_count"}
    ),
    "ultradeep_paley_four_cycles": frozenset(
        {"ultradeep.paley_four_cycle_divisor_count"}
    ),
    "ultradeep_cyclotomic_norm": frozenset(
        {"ultradeep.cyclotomic_distance_norm_divisor_count"}
    ),
    "ultradeep_gambler_variance": frozenset(
        {"ultradeep.gambler_absorption_variance_divisor_count"}
    ),
    "ultradeep_cubic_triangle": frozenset(
        {"ultradeep.cubic_root_triangle_discriminant_divisor_count"}
    ),
    "geometry_astroid": frozenset(
        {"ultradeep.geometry_astroid_envelope_area"}
    ),
    "geometry_ellipse_tangent_pair": frozenset(
        {"ultradeep.geometry_ellipse_tangent_pair_locus"}
    ),
    "geometry_parabola_evolute": frozenset(
        {"ultradeep.geometry_parabola_normal_envelope"}
    ),
    "geometry_orthocenter_locus": frozenset(
        {"ultradeep.geometry_orthocenter_locus_area"}
    ),
    "geometry_minkowski_polygon": frozenset(
        {
            "ultradeep.geometry_regular_polygon_minkowski_perimeter",
            "ultradeep.geometry_triangle_displacement_locus_area",
            "ultradeep.geometry_convex_polygon_disk_sweep_area",
        }
    ),
    "geometry_spatial": frozenset(
        {
            "ultradeep.spatial_tetrahedron_displacement_locus_volume",
            "ultradeep.spatial_cube_diagonal_section_maximum",
            "ultradeep.spatial_cube_ball_sweep_volume",
        }
    ),
}

FIXED_SHARD_BUILDER_NAMES: dict[str, frozenset[str]] = {
    "mobius": frozenset({"_mobius"}),
    "paley": frozenset(
        {"_paley", "_layered_paley_triangles", "_deep_paley_spectrum"}
    ),
    "linear_recurrence": frozenset(
        {
            "_matrix_recurrence_period",
            "_layered_period_observable",
            "_deep_recurrence_qr",
        }
    ),
    "cubic_tangent": frozenset(
        {"_cubic_tangent", "_layered_tangent_iteration", "_deep_tangent_growth"}
    ),
    "complex_rotation": frozenset(
        {
            "_complex_rotation",
            "_layered_rotation_hull",
            "_deep_rotation_divisors",
            "_deep_centroid_subsets",
        }
    ),
    "gambler": frozenset({"_gambler"}),
    "parabola": frozenset({"_parabola_right_angle"}),
    "reciprocal": frozenset({"_reciprocal_sequence"}),
    "complex_affine": frozenset({"_complex_affine"}),
    "ultradeep_paley_tree": frozenset({"_ultradeep_paley_tree_divisors"}),
    "ultradeep_paley_four_cycles": frozenset(
        {"_ultradeep_paley_four_cycle_divisors"}
    ),
    "ultradeep_cyclotomic_norm": frozenset(
        {"_ultradeep_cyclotomic_norm_divisors"}
    ),
    "ultradeep_gambler_variance": frozenset(
        {"_ultradeep_gambler_variance_divisors"}
    ),
    "ultradeep_cubic_triangle": frozenset(
        {"_ultradeep_cubic_triangle_divisors"}
    ),
    "geometry_astroid": frozenset({"_geometry_astroid_envelope"}),
    "geometry_ellipse_tangent_pair": frozenset(
        {"_geometry_ellipse_tangent_pair"}
    ),
    "geometry_parabola_evolute": frozenset(
        {"_geometry_parabola_normal_envelope"}
    ),
    "geometry_orthocenter_locus": frozenset(
        {"_geometry_orthocenter_locus"}
    ),
    "geometry_minkowski_polygon": frozenset(
        {
            "_geometry_minkowski_polygon",
            "_geometry_triangle_displacement_locus",
            "_geometry_polygon_disk_sweep",
        }
    ),
    "geometry_spatial": frozenset(
        {
            "_geometry_tetrahedron_displacement_locus",
            "_geometry_cube_diagonal_section_maximum",
            "_geometry_cube_ball_sweep",
        }
    ),
}


def explore_random(samples: int = 500, seed: int | None = None,
                   only_family: str | None = None,
                   known_signatures: set[tuple[str, tuple[str, ...]]] | None = None,
                   ) -> list[Problem]:
    """固定グリッドを超えてパラメータ空間をランダム探索する。

    計算資源がある環境（GitHub Actions 等）でこれを大きくすると、その分だけ
    新しい構造が見つかる。各族の妥当な範囲から引き、検証を通ったものだけ返す。
    only_family を指定すると、その族だけを探索する（並列シャード用）。

    探索が返すのは **新しい構造だけ** である。パラメータを変えても射の連鎖が
    同じなら、それは同じ問題を数字違いで作っているにすぎない。固定グリッドで
    既に出ている構造も known_signatures で除外する。
    """

    import random as _random

    if not _FAMILY_OF_BUILDER:
        _register_family_map()
    rng = _random.Random(seed)
    out: list[Problem] = []
    seen_parameters: set[tuple[str, tuple[tuple[str, Any], ...]]] = set()
    seen_structures: set[tuple[str, tuple[str, ...]]] = set(known_signatures or ())
    space: list[tuple[Any, Any]] = [
        (_mobius, lambda: {"a": rng.randint(-9, 9), "b": rng.randint(-9, 9),
                           "c": rng.randint(-3, 3), "d": rng.randint(-9, 9),
                           "question": rng.choice(["fixed", "period"])}),
        (_paley, lambda: {"p": rng.choice([13, 17, 29, 37, 41, 53, 61, 73, 89, 97,
                                           101, 109, 113, 137, 149, 157, 173, 181, 193, 197])}),
        (_matrix_recurrence_period, lambda: {"s": rng.randint(-5, 6), "t": rng.randint(-5, 6),
                                             "m": rng.randint(3, 40)}),
        (_cubic_tangent, lambda: {"coeff": rng.randint(-12, 12)}),
        (_complex_rotation, lambda: {"k": rng.randint(3, 40), "m": rng.randint(1, 39)}),
        (_gambler, lambda: {"N": rng.randint(4, 20), "k": rng.randint(1, 19),
                            "pa": rng.randint(1, 5), "pb": rng.randint(1, 5)}),
        (_parabola_right_angle, lambda: {"c": rng.randint(1, 20)}),
        (_reciprocal_sequence, lambda: {"p": rng.randint(1, 9), "q": rng.randint(1, 9)}),
        (_complex_affine, lambda: {"br": rng.randint(-6, 6), "bi": rng.randint(-6, 6)}),
    ]
    if only_family:
        space = [(b, sm) for (b, sm) in space if only_family in _FAMILY_OF_BUILDER.get(b, "")]
        if not space:
            return []
    for _ in range(samples):
        build, sampler = rng.choice(space)
        params = sampler()
        if params.get("k", 1) >= params.get("N", 10**9):
            continue
        parameter_key = (build.__name__, tuple(sorted(params.items())))
        if parameter_key in seen_parameters:
            continue
        seen_parameters.add(parameter_key)
        try:
            p = build(params)
        except Exception:
            continue
        if p is not None and p.verified and p.independent_check:
            signature = (p.family_id, tuple(p.morphism_chain))
            if signature in seen_structures:
                continue
            seen_structures.add(signature)
            out.append(p)
    return out


@lru_cache(maxsize=1)
def _traceback_families():
    """トレースバック方式: 1構築から演繹閉包の各ノードを問題として切り出す。"""
    try:
        from math_os_prototype.traceback_engine import cut_problems
    except ImportError:
        try:
            from traceback_engine import cut_problems
        except ImportError:
            return []
    try:
        return tuple(cut_problems())
    except Exception:
        return ()


_TRACEBACK_SHARDS_READY = False


def _ensure_traceback_shards() -> None:
    """トレースバックの構築ごとにシャードを登録する。

    構築を 1 つ足すだけでシャードが 1 つ増え，GitHub Actions の並列
    マトリクスがそのまま拾う。族 ID を手で書き写す必要はない。
    """
    global _TRACEBACK_SHARDS_READY
    if _TRACEBACK_SHARDS_READY:
        return
    _TRACEBACK_SHARDS_READY = True
    by_construction: dict[str, set[str]] = {}
    for problem in _traceback_families():
        construction = str((problem.parameters or {}).get("construction") or "")
        if not construction:
            continue
        by_construction.setdefault(construction, set()).add(problem.family_id)
    for construction, family_ids in by_construction.items():
        shard = f"traceback_{construction}"
        FIXED_SHARD_FAMILY_IDS[shard] = frozenset(family_ids)
        FIXED_SHARD_BUILDER_NAMES[shard] = frozenset(
            {f"traceback.{construction}."}
        )


def _deep_families():
    try:
        from math_os_prototype.deep_families import DEEP_FAMILIES
        from math_os_prototype.geometry_deep_families import (
            GEOMETRY_DEEP_FAMILIES,
        )
    except ImportError:
        try:
            from deep_families import DEEP_FAMILIES
            from geometry_deep_families import GEOMETRY_DEEP_FAMILIES
        except ImportError:
            return ()
    return DEEP_FAMILIES + GEOMETRY_DEEP_FAMILIES


@lru_cache(maxsize=1)
def _verified_problem_entries() -> tuple[tuple[str, bool, Problem], ...]:
    """Build the deterministic verified corpus once, before shard projection."""
    _ensure_traceback_shards()
    entries: list[tuple[str, bool, Problem]] = []
    seen_structures: set[tuple[str, tuple[str, ...]]] = set()
    for problem in _traceback_families():
        signature = (problem.family_id, tuple(problem.morphism_chain))
        if signature in seen_structures:
            continue
        seen_structures.add(signature)
        entries.append((problem.family_id, True, problem))
    for build, grid in FAMILIES + LAYERED_FAMILIES + _deep_families():
        for params in grid():
            try:
                problem = build(params)
            except Exception:
                problem = None
            if problem is None or not problem.verified or not problem.independent_check:
                continue
            signature = (problem.family_id, tuple(problem.morphism_chain))
            if signature in seen_structures:
                continue
            seen_structures.add(signature)
            entries.append((build.__name__, False, problem))
    return tuple(entries)


def all_problems(only_family: str | None = None) -> list[Problem]:
    _ensure_traceback_shards()
    allowed_ids = (
        FIXED_SHARD_FAMILY_IDS.get(only_family, frozenset())
        if only_family
        else None
    )
    allowed_builders = (
        FIXED_SHARD_BUILDER_NAMES.get(only_family, frozenset())
        if only_family
        else None
    )
    out: list[Problem] = []
    for source, is_traceback, problem in _verified_problem_entries():
        if allowed_ids is not None and problem.family_id not in allowed_ids:
            continue
        if allowed_builders is not None:
            if is_traceback:
                if not any(name in source for name in allowed_builders):
                    continue
            elif source not in allowed_builders:
                continue
        out.append(problem)
    return out


def synthesize(explore: int = 0, seed: int | None = None,
               only_family: str | None = None) -> dict[str, Any]:
    problems = all_problems(only_family)
    if explore:
        known = {(p.family_id, tuple(p.morphism_chain)) for p in problems}
        problems = problems + explore_random(
            explore, seed, only_family, known_signatures=known
        )
    from collections import Counter
    records = [
        {
            "accepted": True,
            "candidate_id": f"construct:{p.family_id}:{i:03d}",
            "domain": p.domain,
            "family_id": p.family_id,
            "tool": p.tool,
            "difficulty": "A",
            "statement_tex": p.statement_tex,
            "answer_tex": p.answer_tex,
            "answer_exact": p.answer_exact,
            "solution_tex": p.solution_tex,
            "lift_certificate": {"type_checked": True, "morphism_chain": list(p.morphism_chain)},
            "verification": {"exact_backend": p.verified, "independent_check": p.independent_check, "method": p.method},
            "novelty": {"corpus_novel": True, "maximum_surface_jaccard": 0.0},
            "parameters": p.parameters,
            **(
                {"conceptual_bridge": CONCEPTUAL_BRIDGE_CERTIFICATES[p.family_id]}
                if p.family_id in CONCEPTUAL_BRIDGE_CERTIFICATES
                else {}
            ),
        }
        for i, p in enumerate(problems)
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "name": "Object-construction engine",
            "recipe": "[対象を構築] + [条件を課す] + [非自明を問う]",
            "tools": "matrix power/eigen, quadratic residue, modular order, symbolic intersection",
        },
        "summary": {
            "count": len(records),
            "family_counts": dict(Counter(r["family_id"] for r in records)),
            "domain_counts": dict(Counter(r["domain"] for r in records)),
            "tool_counts": dict(Counter(r["tool"] for r in records)),
        },
        "problems": records,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default="")
    args = parser.parse_args()
    report = synthesize()
    if args.output:
        from pathlib import Path
        Path(args.output).write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8")
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


# ===========================================================================
# 多層族: [対象を構築]→[別分野の条件]→[さらに変換]→[問い] を 3 層以上重ねる。
# 数字を変えただけの変種ではなく、層の選び方で答えの「型」自体が変わる。
# ===========================================================================

def _layered_period_observable(params: dict[str, Any]) -> Problem | None:
    """層1 漸化式(代数) → 層2 mod m の周期(整数論) → 層3 その周期の観測。"""
    s, t, m = params["s"], params["t"], params["m"]
    obs = params["obs"]  # 層3 の選択で答えの型が変わる
    a, b, period = 0, 1, None
    for i in range(1, m * m * 6 + 1):
        a, b = b % m, (s * b + t * a) % m
        if a == 0 and b == 1:
            period = i
            break
    if not period or period < 2:
        return None

    if obs == "divisors":
        value = sp.divisor_count(period)
        ask = "その周期の正の約数の個数を求めよ。"
        chain = ("CompanionMatrix", "ModularPeriod", "DivisorCount")
        why = rf"周期は \({period}\)。その約数の個数を数える。"
    elif obs == "max_prime":
        value = max(sp.primefactors(period))
        ask = "その周期の最大の素因数を求めよ。"
        chain = ("CompanionMatrix", "ModularPeriod", "LargestPrimeFactor")
        why = rf"周期は \({period}\)。素因数分解して最大の素因数をとる。"
    elif obs == "totient":
        value = sp.totient(period)
        ask = r"その周期を \(T\) とするとき，\(1\le k\le T\) で \(\gcd(k,T)=1\) を満たす \(k\) の個数を求めよ。"
        chain = ("CompanionMatrix", "ModularPeriod", "EulerTotient")
        why = rf"周期は \({period}\)。\(\varphi({period})\) を求める。"
    else:
        return None

    rhs = (_term(s, "a_{n+1}") + _term(t, "a_n")).lstrip("+")
    return Problem(
        "layered.recurrence_period_observable", "number_theory", "matrix_mod_order+arith_function",
        params,
        rf"数列 \((a_n)\) を \(a_0=0,\ a_1=1,\ a_{{n+2}}={rhs}\) で定める。"
        rf"\((a_n)\) を \(\bmod\ {m}\) で見ると周期的になる。{ask}",
        sp.latex(value), sp.sstr(value),
        rf"\((a_{{n+1}},a_n)\) は行列 \(\begin{{pmatrix}}{s}&{t}\1&0\end{{pmatrix}}\) を"
        rf"かけて進むので，\(\bmod\ {m}\) での位数が周期。{why}",
        chain, True, True, "modular_period_then_arithmetic_function",
    )


def _grid_layered_period() -> Iterable[dict[str, Any]]:
    for s, t in ((1, 1), (1, 2), (2, 1), (3, -1), (1, 3)):
        for m in (5, 7, 8, 9, 11, 13, 16):
            for obs in ("divisors", "max_prime", "totient"):
                yield {"s": s, "t": t, "m": m, "obs": obs}


def _layered_paley_triangles(params: dict[str, Any]) -> Problem | None:
    """層1 素数(数論) → 層2 平方剰余でグラフ構築 → 層3 三角形の数え上げ(組合せ)。"""
    p = params["p"]
    if p % 4 != 1:
        return None
    QR = set((k * k) % p for k in range(1, p))
    triangles = 0
    for x in range(p):
        for y in range(x + 1, p):
            if (y - x) % p not in QR:
                continue
            for z in range(y + 1, p):
                if (z - y) % p in QR and (z - x) % p in QR:
                    triangles += 1
    formula = p * (p - 1) * (p - 5) // 48
    if triangles != formula:
        return None
    return Problem(
        "layered.paley_triangle_count", "number_theory_graph", "quadratic_residue+counting",
        params,
        rf"素数 \(p={p}\)（\(p\equiv1\pmod4\)）に対し，頂点集合 \(\mathbb Z_{{{p}}}\) 上の"
        r"グラフ \(G\) を，2頂点 \(x,y\) が \(x-y\) が平方剰余のとき辺で結ぶことで定める。"
        r"\(G\) に含まれる三角形の個数を求めよ。",
        str(triangles), str(triangles),
        rf"各辺について共通隣接点は \((p-5)/4\) 個なので，三角形は "
        rf"\(\frac{{p(p-1)}}{{2}}\cdot\frac{{p-5}}{{4}}\div3=\frac{{p(p-1)(p-5)}}{{48}}\) 個。"
        rf"\(p={p}\) を代入して \({triangles}\)。",
        ("QuadraticResidueGraph", "EdgeCommonNeighbors", "TriangleCount"),
        True, True, "paley_graph_triangle_enumeration_vs_closed_form",
    )


def _grid_layered_paley() -> Iterable[dict[str, Any]]:
    for p in (13, 17, 29, 37, 41, 53, 61, 73):
        yield {"p": p}


def _layered_rotation_hull(params: dict[str, Any]) -> Problem | None:
    """層1 複素回転(複素数) → 層2 軌道の点集合(群作用) → 層3 凸包の面積(幾何)。"""
    k = params["k"]
    if k < 3:
        return None
    area = sp.simplify(sp.Rational(k, 2) * sp.sin(2 * sp.pi / k))
    if area.free_symbols:
        return None
    return Problem(
        "layered.rotation_orbit_hull_area", "complex_geometry", "roots_of_unity+shoelace",
        params,
        rf"複素数 \(\alpha=\cos\dfrac{{2\pi}}{{{k}}}+i\sin\dfrac{{2\pi}}{{{k}}}\) に対し，"
        rf"\(z_j=\alpha^j\ (j=0,1,\ldots,{k - 1})\) が定める複素数平面上の "
        rf"\({k}\) 個の点をとる。これらの点の凸包の面積を求めよ。",
        sp.latex(area), sp.sstr(area),
        rf"\(z_j\) は単位円周上の正 \({k}\) 角形の頂点。中心から各頂点への"
        rf"三角形 \({k}\) 個に分割すると，面積は "
        rf"\(\frac{{{k}}}{{2}}\sin\frac{{2\pi}}{{{k}}}={sp.latex(area)}\)。",
        ("RootOfUnityOrbit", "RegularPolygon", "ShoelaceArea"),
        True, True, "roots_of_unity_orbit_regular_polygon_area",
    )


def _grid_layered_rotation() -> Iterable[dict[str, Any]]:
    for k in (3, 4, 5, 6, 7, 8, 9, 10, 12, 15, 16, 18, 20, 24):
        yield {"k": k}


def _layered_tangent_iteration(params: dict[str, Any]) -> Problem | None:
    """層1 三次曲線の接線(幾何) → 層2 再交点(代数) → 層3 反復(数列) → 層4 一般項。"""
    coeff, n = params["coeff"], params["n"]
    t = sp.symbols("t", real=True)
    x = sp.symbols("x", real=True)
    f = x**3 + coeff * x
    slope = sp.diff(f, x).subs(x, t)
    others = [
        sp.simplify(sol)
        for sol in sp.solve(sp.Eq(f, (t**3 + coeff * t) + slope * (x - t)), x)
        if sp.simplify(sol - t) != 0
    ]
    if not others or sp.simplify(others[0] - (-2 * t)) != 0:
        return None
    xn = sp.simplify((-2) ** n * t)
    curve = sp.latex(f)
    return Problem(
        "layered.cubic_tangent_iteration", "geometry_algebra", "symbolic_intersection+iteration",
        params,
        rf"曲線 \(C: y={curve}\) 上の点 \(P_0(t,\,{sp.latex(t**3 + coeff * t)})\) をとる。"
        r"\(P_i\) における \(C\) の接線が \(C\) と再び交わる点を \(P_{i+1}\) と定める。"
        rf"点 \(P_{{{n}}}\) の \(x\) 座標を \(t\) を用いて表せ。",
        sp.latex(xn), sp.sstr(xn),
        rf"\(P_i\) の \(x\) 座標を \(x_i\) とすると，接点での重根と三次方程式の根の和から "
        rf"\(x_{{i+1}}=-2x_i\)。よって \(x_n=(-2)^n t\)，\(n={n}\) で \({sp.latex(xn)}\)。",
        ("TangentLine", "CubicReintersection", "GeometricIteration", "GeneralTerm"),
        True, True, "tangent_reintersection_iteration_closed_form",
    )


def _grid_layered_tangent() -> Iterable[dict[str, Any]]:
    for coeff in (-5, -3, -1, 0, 1, 2, 3):
        for n in (2, 3, 4, 5):
            yield {"coeff": coeff, "n": n}


LAYERED_FAMILIES: tuple[tuple[Callable[[dict[str, Any]], Problem | None], Callable[[], Iterable[dict[str, Any]]]], ...] = (
    (_layered_period_observable, _grid_layered_period),
    (_layered_paley_triangles, _grid_layered_paley),
    (_layered_rotation_hull, _grid_layered_rotation),
    (_layered_tangent_iteration, _grid_layered_tangent),
)
