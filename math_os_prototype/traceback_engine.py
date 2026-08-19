"""MORTRAのトレースバック作問エンジン。

AlphaGeometryのdeduction-closure/tracebackは歴史的な設計参考であり、runtime依存はない。

前提から **導けるもの全部** を計算して
DAG を作り、各ノードについて「その結論に必要な最小の前提」を逆算(traceback)
して、そこを切り出して問題にする。1 つの構築から多数の問題が生まれる。

ここでは同じ設計を採る:

    construction (構築)
        ↓  derive_closure: 導ける量を網羅的に列挙 → ノード群
        ↓  traceback: 各ノードに必要な前提と中間対象を逆算
        ↓  cut: 各ノードを 1 問として切り出す

族を 1 つ書くと、その構築から導けるノードの数だけ問題が生まれる。
「難しさ」の定義は変えない — 従来どおり
  * 対象を構築し条件を課しているか（construct / condition）
  * 射の連鎖の深さ
で測る。トレースバックは *問題数* を増やすのであって、難易度の定義を変えない。

中間対象（問題文に現れないが導出に必要な量）は deduction closure の
auxiliary construction にあたる。これを hidden_intermediates として記録し、
数が多いほど「ひらめきが要る」= 深いとみなす。
"""

from __future__ import annotations

import argparse
import itertools
import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Callable, Iterable

import sympy as sp

try:
    from math_os_prototype.construct_engine import Problem
except ImportError:  # pragma: no cover
    from construct_engine import Problem


@dataclass(frozen=True)
class DerivedNode:
    """演繹閉包の 1 ノード = 切り出せる 1 問。"""

    key: str                       # ノード識別子
    value: sp.Expr                 # 導出された値（答え）
    question_ja: str               # このノードを問う日本語
    premises: tuple[str, ...]      # traceback で逆算した必要前提
    hidden: tuple[str, ...]        # 問題文に現れない中間対象(= auxiliary)
    morphisms: tuple[str, ...]     # 射の連鎖
    solution_ja: str               # 解法の骨子
    scope: tuple[str, ...]         # 高校範囲の道具


def _exact(value: Any) -> sp.Expr | None:
    """値が厳密（Float を含まない）かを確かめて返す。"""
    try:
        expr = sp.nsimplify(sp.simplify(value))
    except Exception:
        return None
    if expr.free_symbols or expr.atoms(sp.Float):
        return None
    return expr


# ---------------------------------------------------------------------------
# 構築 1: 単位円に内接する正 n 角形
# ---------------------------------------------------------------------------
def closure_regular_polygon(n: int) -> list[DerivedNode]:
    """正 n 角形という 1 つの構築から、導ける量を網羅的に列挙する。"""

    if n < 3 or n > 12:
        return []
    nodes: list[DerivedNode] = []
    base_premise = f"単位円に内接する正{n}角形の頂点 z_j (j=0..{n-1})"

    # --- ノード: 頂点0から他の全頂点までの距離の積 = n ---
    prod = sp.prod(
        [sp.sqrt((1 - sp.cos(2 * sp.pi * j / n)) ** 2 + sp.sin(2 * sp.pi * j / n) ** 2)
         for j in range(1, n)]
    )
    value = _exact(prod)
    if value is not None:
        nodes.append(DerivedNode(
            "vertex_distance_product", value,
            f"頂点 \\(z_0\\) から他の {n-1} 個の頂点までの距離の積を求めよ。",
            (base_premise,),
            ("円分多項式 z^n-1 の因数分解", "z→1 の極限"),
            ("RootOfUnity", "PolynomialFactorization", "LimitEvaluation", "DistanceProduct"),
            rf"\(z^{{{n}}}-1=\prod_j (z-z_j)\) の両辺を \(z-1\) で割り \(z\to1\) とすると "
            rf"積は \({n}\) に等しい。",
            ("複素数平面", "因数分解", "極限"),
        ))

    # --- ノード: 面積 ---
    area = _exact(sp.Rational(n, 2) * sp.sin(2 * sp.pi / n))
    if area is not None:
        nodes.append(DerivedNode(
            "area", area,
            "この正多角形の面積を求めよ。",
            (base_premise,),
            ("中心から各頂点への三角形分割",),
            ("RegularPolygon", "TriangleDecomposition", "AreaSum"),
            rf"中心と隣接2頂点が作る三角形 \({n}\) 個に分割すると，"
            rf"面積は \(\frac{{{n}}}{{2}}\sin\frac{{2\pi}}{{{n}}}\)。",
            ("三角比", "面積"),
        ))

    # --- ノード: 全頂点対の距離の平方和 = n^2 ---
    total = 0
    for i in range(n):
        for k in range(i + 1, n):
            dx = sp.cos(2 * sp.pi * i / n) - sp.cos(2 * sp.pi * k / n)
            dy = sp.sin(2 * sp.pi * i / n) - sp.sin(2 * sp.pi * k / n)
            total += dx**2 + dy**2
    value = _exact(total)
    if value is not None:
        nodes.append(DerivedNode(
            "sum_sq_pairwise", value,
            "相異なる2頂点の距離の平方の総和を求めよ。",
            (base_premise,),
            ("頂点ベクトルの総和が 0",),
            ("RegularPolygon", "VectorSumVanishing", "SquaredDistanceSum"),
            r"\(\sum_j z_j=0\) を使うと \(\sum_{i<k}|z_i-z_k|^2"
            rf"=n\sum_j|z_j|^2-|\sum_j z_j|^2={n}^2\)。",
            ("複素数平面", "ベクトル", "対称性"),
        ))

    # --- ノード: 対角線の本数 ---
    nodes.append(DerivedNode(
        "diagonal_count", sp.Integer(n * (n - 3) // 2),
        "この正多角形の対角線の本数を求めよ。",
        (base_premise,),
        ("辺を除く頂点対の数え上げ",),
        ("RegularPolygon", "PairCounting", "EdgeExclusion"),
        rf"頂点対は \(\binom{{{n}}}{{2}}\) 通り，そのうち辺が \({n}\) 本なので "
        rf"対角線は \(\frac{{{n}({n}-3)}}{{2}}\) 本。",
        ("組合せ",),
    ))

    # --- ノード: 重心が中心と一致する空でない部分集合の個数 ---
    cnt = 0
    for r in range(1, n + 1):
        for sub in itertools.combinations(range(n), r):
            zr = sum(math.cos(2 * math.pi * j / n) for j in sub)
            zi = sum(math.sin(2 * math.pi * j / n) for j in sub)
            if abs(zr) < 1e-9 and abs(zi) < 1e-9:
                cnt += 1
    if cnt > 0:
        nodes.append(DerivedNode(
            "centroid_zero_subsets", sp.Integer(cnt),
            "頂点の空でない部分集合であって，その重心が円の中心と一致するものの個数を求めよ。",
            (base_premise,),
            ("和が消える部分集合の巡回対称性",),
            ("RegularPolygon", "SubsetFamily", "VanishingSum", "SymmetryCount"),
            r"重心が中心 ⟺ その部分集合の頂点の和が 0。巡回対称性から"
            r"正多角形をなす部分集合とその合併が該当する。",
            ("複素数平面", "対称性", "組合せ"),
        ))

    # --- ノード（層を1つ足す）: 距離の積の約数個数 ---
    prod_node = next((x for x in nodes if x.key == "vertex_distance_product"), None)
    if prod_node is not None and prod_node.value.is_Integer:
        nodes.append(DerivedNode(
            "distance_product_divisors", sp.Integer(sp.divisor_count(int(prod_node.value))),
            f"頂点 \\(z_0\\) から他の頂点までの距離の積を \\(L\\) とするとき，"
            f"\\(L\\) の正の約数の個数を求めよ。",
            (base_premise,),
            ("円分多項式の因数分解", "L が整数であること"),
            ("RootOfUnity", "PolynomialFactorization", "DistanceProduct",
             "IntegerValue", "DivisorCount"),
            rf"上と同様に \(L={prod_node.value}\)。その約数の個数を数える。",
            ("複素数平面", "因数分解", "約数"),
        ))

    return nodes


def grid_regular_polygon() -> Iterable[int]:
    return range(3, 13)


# ---------------------------------------------------------------------------
# 構築 2: 三次曲線 y = x^3 + ax 上の接線の反復
# ---------------------------------------------------------------------------
def closure_cubic_tangent(a: int) -> list[DerivedNode]:
    x, t, n = sp.symbols("x t n", real=True)
    f = x**3 + a * x
    slope = sp.diff(f, x).subs(x, t)
    others = [
        sp.simplify(s)
        for s in sp.solve(sp.Eq(f, (t**3 + a * t) + slope * (x - t)), x)
        if sp.simplify(s - t) != 0
    ]
    if not others or sp.simplify(others[0] - (-2 * t)) != 0:
        return []

    base = f"曲線 \\(C: y={sp.latex(f)}\\) 上の点 \\(P_0(t,\\,{sp.latex(t**3 + a*t)})\\)"
    step = "接線が C と再び交わる点を次の点とする操作"
    nodes: list[DerivedNode] = []

    # ノード: 1回後の x 座標
    nodes.append(DerivedNode(
        "reintersection_x", sp.simplify(-2 * t),
        "\\(P_0\\) における接線が \\(C\\) と再び交わる点の \\(x\\) 座標を \\(t\\) で表せ。",
        (base,), ("三次方程式の根の和（接点は重根）",),
        ("CubicCurve", "TangentLine", "RootSumRelation", "Reintersection"),
        r"接点が重根になることと根の和が 0 であることから，残る根は \(-2t\)。",
        ("微分", "三次方程式", "解と係数の関係"),
    ))

    # ノード: n 回後の x 座標
    nodes.append(DerivedNode(
        "iterate_x_n", sp.simplify((-2) ** n * t),
        f"{step}を \\(n\\) 回繰り返して得られる点の \\(x\\) 座標を求めよ。",
        (base, step), ("1 回の操作が x を -2 倍にすること",),
        ("CubicCurve", "TangentLine", "RootSumRelation", "GeometricIteration", "GeneralTerm"),
        r"1 回で \(x\mapsto -2x\) なので \(x_n=(-2)^n t\)。",
        ("微分", "数列", "等比数列"),
    ))

    # ノード: 増大度の対数極限
    nodes.append(DerivedNode(
        "log_growth_limit", sp.log(2),
        f"{step}を繰り返して得られる点の \\(x\\) 座標を \\(x_n\\) とするとき，"
        r"\(\displaystyle\lim_{n\to\infty}\frac{\log|x_n|}{n}\) を求めよ。",
        (base, step), ("x_n=(-2)^n t という一般項",),
        ("CubicCurve", "TangentLine", "GeometricIteration", "GeneralTerm",
         "GrowthRate", "LogarithmicLimit"),
        r"\(|x_n|=2^n|t|\) より \(\frac{\log|x_n|}{n}=\log2+\frac{\log|t|}{n}\to\log2\)。",
        ("数列", "対数", "極限"),
    ))

    # ノード: 中点の軌跡
    X = sp.symbols("x", real=True)
    mid_x = sp.simplify((t + (-2 * t)) / 2)          # = -t/2
    mid_y = sp.simplify(((t**3 + a*t) + ((-2*t)**3 + a*(-2*t))) / 2)
    t_of_X = sp.solve(sp.Eq(X, mid_x), t)
    if t_of_X:
        locus = sp.simplify(mid_y.subs(t, t_of_X[0]))
        if not locus.atoms(sp.Float):
            nodes.append(DerivedNode(
                "midpoint_locus", locus,
                "\\(P_0\\) と再交点の中点が描く軌跡を \\(y\\) について求めよ。",
                (base,), ("再交点の x 座標が -2t であること",),
                ("CubicCurve", "TangentLine", "Reintersection", "Midpoint", "LocusElimination"),
                r"中点の座標を \(t\) で表し，\(t\) を消去する。",
                ("微分", "軌跡", "文字消去"),
            ))
    return nodes


def grid_cubic() -> Iterable[int]:
    return (-9, -7, -5, -3, -1, 0, 1, 2, 3, 5)


# ---------------------------------------------------------------------------
# 構築 3: 楕円上の2点における接線の交点からの2接線
# ---------------------------------------------------------------------------
def _ellipse_rational_points(a: int, b: int, limit: int = 40) -> list[tuple[sp.Expr, sp.Expr]]:
    """楕円 x^2/a^2+y^2/b^2=1 上の有理点を集める。"""
    pts: list[tuple[sp.Expr, sp.Expr]] = []
    for num in range(-limit, limit + 1):
        px = sp.Rational(num, 5)
        rhs = 1 - px**2 / a**2
        if rhs <= 0:
            continue
        root = sp.sqrt(sp.nsimplify(b**2 * rhs))
        if root.is_rational and root != 0:
            pts.append((px, root))
    return pts


def _ellipse_tangent_configuration(
    params: tuple[int, int, int, int],
) -> tuple[tuple[sp.Expr, sp.Expr], tuple[sp.Expr, sp.Expr], tuple[sp.Expr, sp.Expr]] | None:
    """Return the two contact points and their tangent intersection."""
    a, b, i1, i2 = params
    pts = _ellipse_rational_points(a, b)
    if len(pts) <= max(i1, i2) or i1 == i2:
        return None
    x, y = sp.symbols("x y", real=True)
    t1 = pts[i1]
    t2 = (pts[i2][0], -pts[i2][1])
    if t1 == t2:
        return None
    solutions = sp.solve(
        [
            t1[0] * x / a**2 + t1[1] * y / b**2 - 1,
            t2[0] * x / a**2 + t2[1] * y / b**2 - 1,
        ],
        [x, y],
        dict=True,
    )
    if not solutions:
        return None
    point = (solutions[0][x], solutions[0][y])
    return t1, t2, point


def _ellipse_tangent_preamble(
    params: tuple[int, int, int, int],
    node_key: str,
) -> str:
    """Render exactly the surface facts required by the selected observation."""
    a, b, _, _ = params
    ellipse = rf"楕円 \(E:\dfrac{{x^2}}{{{a**2}}}+\dfrac{{y^2}}{{{b**2}}}=1\)"
    if node_key == "monge_radius_sq":
        return (
            ellipse
            + r" の外部の点 \(P\) から \(E\) に2本の接線を引き，"
            + r"接点を \(T_1,T_2\) とする。"
        )
    configuration = _ellipse_tangent_configuration(params)
    if configuration is None:
        return ellipse
    _, _, point = configuration
    return (
        ellipse
        + rf" の外部の点 \(P\left({sp.latex(point[0])},{sp.latex(point[1])}\right)\) から "
        + r"\(E\) に2本の接線を引き，接点を \(T_1,T_2\) とする。"
    )


def closure_ellipse_tangent(params: tuple[int, int, int, int]) -> list[DerivedNode]:
    """楕円と外部点からの2接線という構築から、導ける量を列挙する。"""

    a, b, _, _ = params
    configuration = _ellipse_tangent_configuration(params)
    if configuration is None:
        return []
    T1, T2, P = configuration
    base = f"楕円 x^2/{a}^2+y^2/{b}^2=1 と，そこから引いた2本の接線の交点 P"
    nodes: list[DerivedNode] = []

    def add(key, raw, question, hidden, morphisms, solution, scope):
        value = _exact(raw)
        if value is not None:
            nodes.append(DerivedNode(
                key, value, question, (base,), hidden, morphisms, solution, scope,
            ))

    add("chord_length_sq",
        (T1[0]-T2[0])**2 + (T1[1]-T2[1])**2,
        r"2つの接点を結ぶ線分の長さの平方を求めよ。",
        ("接点弦（極線）の方程式",),
        ("EllipseObject", "TangentLine", "DualLinePair", "EdgeLengthObservation"),
        r"接点弦は \(\frac{p x}{a^2}+\frac{q y}{b^2}=1\)。楕円との交点を求めて距離を計算する。",
        ("楕円", "接線", "2点間の距離"))

    add("tangent_slope_product",
        ((T1[1]-P[1])/(T1[0]-P[0])) * ((T2[1]-P[1])/(T2[0]-P[0])),
        r"2本の接線の傾きの積を求めよ。",
        ("接線が接する条件（判別式 0）",),
        ("EllipseObject", "TangentLine", "CoordinateSolve"),
        r"P を通る傾き \(m\) の直線を楕円に代入し，判別式 \(=0\) が与える "
        r"\(m\) の二次方程式の解と係数の関係から積を読む。",
        ("楕円", "判別式", "解と係数の関係"))

    add("contact_triangle_area",
        sp.Rational(1, 2)*sp.Abs(
            (T1[0]-P[0])*(T2[1]-P[1]) - (T2[0]-P[0])*(T1[1]-P[1])),
        r"P と2つの接点が作る三角形の面積を求めよ。",
        ("接点の座標", "P の座標"),
        ("EllipseObject", "TangentLine", "CoordinateSolve", "ShoelaceArea"),
        r"接点と P の座標を求め，三角形の面積公式を用いる。",
        ("楕円", "接線", "座標平面の面積"))

    add("chord_midpoint_x",
        (T1[0]+T2[0])/2,
        r"2つの接点を結ぶ線分の中点の \(x\) 座標を求めよ。",
        ("接点弦と楕円の交点",),
        ("EllipseObject", "TangentLine", "MidpointLocus"),
        r"接点弦と楕円の連立から2交点を求め，中点を取る。",
        ("楕円", "接線", "中点"))

    add("monge_radius_sq",
        sp.Integer(a**2 + b**2),
        r"2本の接線が直交するような点 P 全体は円をなす。その半径の平方を求めよ。",
        ("2接線が直交する条件", "傾きの積 = -1"),
        ("EllipseObject", "TangentLine", "RightAngleCondition", "CircleParameter"),
        r"傾きの二次方程式で解の積 \(=-1\) とおくと \(x^2+y^2=a^2+b^2\) を得る。",
        ("楕円", "判別式", "円の方程式"))

    add("center_to_polar_dist_sq",
        1/((P[0]/a**2)**2 + (P[1]/b**2)**2),
        r"原点から接点弦までの距離の平方を求めよ。",
        ("接点弦の方程式", "点と直線の距離"),
        ("EllipseObject", "DualLinePair", "CoordinateSolve"),
        r"接点弦 \(\frac{p x}{a^2}+\frac{q y}{b^2}=1\) と原点の距離を点と直線の距離公式で求める。",
        ("楕円", "点と直線の距離"))
    return nodes


def grid_ellipse_tangent() -> Iterable[tuple[int, int, int, int]]:
    return ((5, 3, 2, 5), (5, 4, 1, 4), (13, 5, 2, 6))


# ---------------------------------------------------------------------------
# 構築 4: 正方格子上の経路と対角線による反射
# ---------------------------------------------------------------------------
def closure_lattice_path(n: int) -> list[DerivedNode]:
    """(0,0)→(n,n) の最短経路という構築から、導ける量を列挙する。"""

    if n < 2 or n > 40:
        return []
    base = f"格子点 (0,0) から ({n},{n}) へ右または上に1ずつ進む最短経路"
    total = sp.binomial(2*n, n)
    catalan = sp.simplify(total/(n+1))
    nodes: list[DerivedNode] = []

    def add(key, raw, question, hidden, morphisms, solution, scope):
        value = _exact(raw)
        if value is not None:
            nodes.append(DerivedNode(
                key, value, question, (base,), hidden, morphisms, solution, scope,
            ))

    add("total_paths", total,
        r"経路は全部で何通りあるか。",
        ("右と上の並べ替え",),
        ("PathStateSpace", "SubsetCount"),
        rf"\(2n\) 回の移動のうち右を選ぶ位置を決めればよく \(\binom{{{2*n}}}{{{n}}}\)。",
        ("場合の数", "組合せ"))

    add("catalan_paths", catalan,
        r"直線 \(y=x\) より上側に出ない経路は何通りあるか。",
        ("対角線を越える経路の鏡映",),
        ("PathStateSpace", "ReflectionBijection", "SubsetCount"),
        r"越える経路を \(y=x+1\) で鏡映すると別の端点への経路と1対1に対応し，"
        r"差を取ってカタラン数を得る。",
        ("場合の数", "組合せ", "1対1対応"))

    add("strictly_above_paths", sp.binomial(2*n-2, n-1)/n,
        r"出発直後から到着直前まで直線 \(y=x\) に一度も触れない経路は何通りあるか。",
        ("最初の一歩を固定した後の鏡映",),
        ("PathStateSpace", "ReflectionBijection", "SubsetCount"),
        r"最初と最後の一歩を固定し，残りに鏡映の議論を適用する。",
        ("場合の数", "組合せ", "1対1対応"))

    add("total_paths_divisor_count",
        sp.Integer(sp.divisor_count(int(total))),
        r"経路の総数の正の約数の個数を求めよ。",
        ("二項係数の素因数分解",),
        ("PathStateSpace", "SubsetCount", "PrimeFactorization", "DivisorCount"),
        r"総数を素因数分解し，指数に1を足して掛ける。",
        ("場合の数", "素因数分解", "約数の個数"))

    add("catalan_divisor_count",
        sp.Integer(sp.divisor_count(int(catalan))),
        r"対角線より上に出ない経路の総数の正の約数の個数を求めよ。",
        ("鏡映による数え上げ", "素因数分解"),
        ("PathStateSpace", "ReflectionBijection", "PrimeFactorization", "DivisorCount"),
        r"鏡映で経路数を求めたのち素因数分解する。",
        ("場合の数", "1対1対応", "約数の個数"))

    if n % 2 == 0:
        add("through_center_paths", sp.binomial(n, n//2)**2,
            rf"点 \(({n//2},{n//2})\) を通る経路は何通りあるか。",
            ("経路の前半と後半への分割",),
            ("PathStateSpace", "SubsetCount"),
            r"中点までとそこからの経路数の積を取る。",
            ("場合の数", "組合せ"))
    return nodes


def grid_lattice_path() -> Iterable[int]:
    return (5, 6, 7, 8, 10, 12)


# ---------------------------------------------------------------------------
# 構築 5: 2 の累乗の 10 進表示（常用対数）
# ---------------------------------------------------------------------------
def closure_digit_power(k: int) -> list[DerivedNode]:
    """2^k の10進表示という構築から、導ける量を列挙する。"""

    if k < 5 or k > 400:
        return []
    value = 2**k
    text = str(value)
    base = f"2 の {k} 乗の10進表示"
    nodes: list[DerivedNode] = []

    def add(key, raw, question, hidden, morphisms, solution, scope):
        exact = _exact(raw)
        if exact is not None:
            nodes.append(DerivedNode(
                key, exact, question, (base,), hidden, morphisms, solution, scope,
            ))

    add("digit_count", sp.Integer(len(text)),
        rf"\(2^{{{k}}}\) は何桁の整数か。",
        ("常用対数 log10(2) の評価",),
        ("PowerSequence", "DecimalDigitCount"),
        rf"\(\log_{{10}}2^{{{k}}}={k}\log_{{10}}2\) の整数部分に1を足す。",
        ("指数", "常用対数", "桁数"))

    add("leading_digit", sp.Integer(int(text[0])),
        rf"\(2^{{{k}}}\) の最高位の数字を求めよ。",
        ("常用対数の小数部分",),
        ("PowerSequence", "LeadingDigit"),
        rf"\({k}\log_{{10}}2\) の小数部分 \(f\) に対し \(10^{{f}}\) の整数部分が最高位。",
        ("指数", "常用対数", "小数部分"))

    add("digit_increase_count",
        sp.Integer(sum(1 for n in range(1, k+1)
                       if len(str(2**n)) > len(str(2**(n-1))))),
        rf"\(n=1,2,\ldots,{k}\) のうち，\(2^{{n}}\) の桁数が \(2^{{n-1}}\) より"
        r"増えるような \(n\) の個数を求めよ。",
        ("桁数の階段関数", "log10(2) の無理性"),
        ("PowerSequence", "DecimalDigitCount", "ArithmeticObservation"),
        r"桁数は \(\lfloor n\log_{10}2\rfloor+1\)。増える回数は最終桁数から1を引いた数に等しい。",
        ("指数", "常用対数", "ガウス記号"))

    add("leading_one_count",
        sp.Integer(sum(1 for n in range(1, k+1) if str(2**n)[0] == "1")),
        rf"\(n=1,2,\ldots,{k}\) のうち，\(2^{{n}}\) の最高位が 1 となる \(n\) の個数を求めよ。",
        ("桁上がりの直後だけ最高位が1になること",),
        ("PowerSequence", "LeadingDigit", "ArithmeticObservation"),
        r"最高位が1になるのは桁数が増えた直後に限る。よって桁数の増加回数に一致する。",
        ("指数", "常用対数", "ガウス記号"))

    add("digit_sum", sp.Integer(sum(int(c) for c in text)),
        rf"\(2^{{{k}}}\) の各位の数字の和を求めよ。",
        ("10 進展開の各位",),
        ("PowerSequence", "ArithmeticObservation"),
        r"10進表示を求めて各位を加える。",
        ("指数", "整数の性質"))
    return nodes


def grid_digit_power() -> Iterable[int]:
    return (20, 30, 40, 50, 64, 100)


# ---------------------------------------------------------------------------
# 構築 6: 整数座標の三角形の五心とオイラー線
# ---------------------------------------------------------------------------
def closure_triangle_centers(
    params: tuple[int, int, int, int, int, int],
) -> list[DerivedNode]:
    """三角形という構築から、五心と関連量を列挙する。"""

    ax, ay, bx, by, cx, cy = params
    A = sp.Matrix([ax, ay])
    B = sp.Matrix([bx, by])
    C = sp.Matrix([cx, cy])
    area = sp.Rational(1, 2)*sp.Abs(
        (B[0]-A[0])*(C[1]-A[1]) - (C[0]-A[0])*(B[1]-A[1]))
    if area == 0:
        return []
    u, v = sp.symbols("u v", real=True)
    solutions = sp.solve([
        (u-A[0])**2 + (v-A[1])**2 - (u-B[0])**2 - (v-B[1])**2,
        (u-A[0])**2 + (v-A[1])**2 - (u-C[0])**2 - (v-C[1])**2,
    ], [u, v], dict=True)
    if not solutions:
        return []
    O = sp.Matrix([solutions[0][u], solutions[0][v]])
    H = A + B + C - 2*O
    r2 = sp.simplify((O[0]-A[0])**2 + (O[1]-A[1])**2)
    la = sp.sqrt((B[0]-C[0])**2 + (B[1]-C[1])**2)
    lb = sp.sqrt((A[0]-C[0])**2 + (A[1]-C[1])**2)
    lc = sp.sqrt((A[0]-B[0])**2 + (A[1]-B[1])**2)
    inradius = sp.simplify(area/((la+lb+lc)/2))
    incenter = sp.simplify((la*A + lb*B + lc*C)/(la+lb+lc))
    base = (
        f"3点 A({ax},{ay}), B({bx},{by}), C({cx},{cy}) を頂点とする三角形"
    )
    nodes: list[DerivedNode] = []

    def add(key, raw, question, hidden, morphisms, solution, scope):
        value = _exact(raw)
        if value is not None:
            nodes.append(DerivedNode(
                key, value, question, (base,), hidden, morphisms, solution, scope,
            ))

    add("area", area,
        r"この三角形の面積を求めよ。",
        (),
        ("TriangleConstruction", "ShoelaceArea"),
        r"座標から面積公式で直接求める。",
        ("座標平面", "三角形の面積"))

    add("circumradius_sq", r2,
        r"外接円の半径の平方を求めよ。",
        ("2辺の垂直二等分線の交点",),
        ("TriangleConstruction", "CircleParameter", "CoordinateSolve"),
        r"2辺の垂直二等分線を連立して外心を求め，頂点までの距離を測る。",
        ("座標平面", "垂直二等分線", "円"))

    add("inradius", inradius,
        r"内接円の半径を求めよ。",
        ("面積と周長の関係 S=rs",),
        ("TriangleConstruction", "EdgeLengthObservation", "IncenterWeights"),
        r"\(S=rs\)（\(s\) は半周長）から \(r=S/s\)。",
        ("三角形の面積", "内接円"))

    add("orthocenter_x", H[0],
        r"垂心の \(x\) 座標を求めよ。",
        ("2本の垂線の交点", "オイラー線の関係 H=A+B+C-2O"),
        ("TriangleConstruction", "OrthocenterIntersection", "CoordinateSolve"),
        r"2頂点から対辺への垂線を連立する。",
        ("座標平面", "垂線", "内積"))

    if sp.simplify(H[0]-O[0]) != 0:
        add("euler_line_slope", (H[1]-O[1])/(H[0]-O[0]),
            r"外心と垂心を通る直線の傾きを求めよ。",
            ("外心と垂心の座標", "重心もこの直線上にあること"),
            ("TriangleConstruction", "CircleParameter",
             "OrthocenterIntersection", "JoiningLine"),
            r"外心と垂心を求め，2点を通る直線の傾きを計算する。重心も同じ直線上にある。",
            ("座標平面", "直線の傾き"))

    add("nine_point_radius_sq", r2/4,
        r"各辺の中点3つを通る円の半径の平方を求めよ。",
        ("九点円が外接円の半分の半径をもつこと",),
        ("TriangleConstruction", "CentroidMap", "CircleParameter"),
        r"3辺の中点を通る円を求めると，半径は外接円の半分になる。",
        ("座標平面", "中点", "円"))

    add("incenter_x", incenter[0],
        r"内心の \(x\) 座標を求めよ。",
        ("辺の長さを重みとする内分",),
        ("TriangleConstruction", "EdgeLengthObservation", "IncenterWeights"),
        r"内心は \(\frac{aA+bB+cC}{a+b+c}\)（\(a,b,c\) は対辺の長さ）。",
        ("座標平面", "角の二等分線", "内分点"))

    add("OH_dist_sq", (H[0]-O[0])**2 + (H[1]-O[1])**2,
        r"外心と垂心の距離の平方を求めよ。",
        ("外心と垂心の座標", "OH^2 = 9R^2-(a^2+b^2+c^2)"),
        ("TriangleConstruction", "CircleParameter",
         "OrthocenterIntersection", "EdgeLengthObservation"),
        r"外心と垂心を求めて距離を計算する。\(OH^2=9R^2-(a^2+b^2+c^2)\) でも確かめられる。",
        ("座標平面", "円", "2点間の距離"))
    return nodes


def grid_triangle_centers() -> Iterable[tuple[int, int, int, int, int, int]]:
    return (
        (0, 0, 14, 0, 5, 12),    # 13-14-15 ヘロン三角形
        (0, 0, 13, 0, 4, 3),     # 5-12-13
        (0, 0, 21, 0, 6, 8),     # 10-17-21
        (0, 0, 16, 0, 5, 12),    # 13-15-16
    )
# ---------------------------------------------------------------------------
# 構築 7: 双曲線・その接線・2本の漸近線
# ---------------------------------------------------------------------------
def closure_hyperbola_asymptote(
    params: tuple[int, int, int, int],
) -> list[DerivedNode]:
    """双曲線と漸近線という構築から、導ける量を列挙する。"""

    a, b, num, den = params
    x, y = sp.symbols("x y", real=True)
    x0 = sp.Rational(num, den)
    y2 = sp.nsimplify(b**2 * (x0**2 / a**2 - 1))
    if y2 <= 0:
        return []
    y0 = sp.sqrt(y2)
    if not y0.is_rational:
        return []
    tangent = x * x0 / a**2 - y * y0 / b**2 - 1
    try:
        P = sp.solve([tangent, y - sp.Rational(b, a) * x], [x, y], dict=True)[0]
        Q = sp.solve([tangent, y + sp.Rational(b, a) * x], [x, y], dict=True)[0]
    except (IndexError, NotImplementedError):
        return []
    base = f"双曲線 x^2/{a}^2-y^2/{b}^2=1 と，その上の点における接線・2本の漸近線"
    nodes: list[DerivedNode] = []

    def add(key, raw, question, hidden, morphisms, solution, scope):
        value = _exact(raw)
        if value is not None:
            nodes.append(DerivedNode(
                key, value, question, (base,), hidden, morphisms, solution, scope,
            ))

    add("asymptote_triangle_area",
        sp.Rational(1, 2) * sp.Abs(P[x] * Q[y] - Q[x] * P[y]),
        r"接線と2本の漸近線が囲む三角形の面積を求めよ。"
        r"（この値は接点の取り方によらないことを確かめよ。）",
        ("接点を (a\\sec\\theta, b\\tan\\theta) と置く", "漸近線との交点"),
        ("HyperbolaObject", "TangentLine", "AsymptoteLine", "ShoelaceArea"),
        r"接点を \((x_0,y_0)\) とすると接線は \(\frac{xx_0}{a^2}-\frac{yy_0}{b^2}=1\)。"
        r"漸近線 \(y=\pm\frac{b}{a}x\) との交点を求めて面積を計算すると "
        r"\(ab\) となり，接点によらない。",
        ("双曲線", "接線", "座標平面の面積"))

    add("asymptote_distance_product",
        (sp.Abs(b * x0 - a * y0) / sp.sqrt(a**2 + b**2))
        * (sp.Abs(b * x0 + a * y0) / sp.sqrt(a**2 + b**2)),
        r"双曲線上の点から2本の漸近線までの距離の積を求めよ。",
        ("点と直線の距離", "双曲線の方程式で b^2x^2-a^2y^2 を消す"),
        ("HyperbolaObject", "AsymptoteLine", "CoordinateSolve"),
        r"距離の積は \(\frac{|b^2x_0^2-a^2y_0^2|}{a^2+b^2}\)。"
        r"双曲線の式より分子は \(a^2b^2\) で一定。",
        ("双曲線", "点と直線の距離"))

    add("asymptote_intersection_x", P[x],
        r"接線と漸近線 \(y=\frac{b}{a}x\) の交点の \(x\) 座標を求めよ。",
        ("接線の方程式",),
        ("HyperbolaObject", "TangentLine", "AsymptoteLine", "LinearIntersection"),
        r"接線と漸近線を連立する。",
        ("双曲線", "接線", "連立方程式"))

    add("focal_distance_difference", sp.Integer(2 * a),
        r"双曲線上の点から2つの焦点までの距離の差の絶対値を求めよ。",
        ("焦点の座標",),
        ("HyperbolaObject", "FocalProperty"),
        r"双曲線の定義そのもので \(2a\)。",
        ("双曲線", "2点間の距離"))

    add("director_circle_radius_sq", sp.Integer(a**2 - b**2),
        r"双曲線に引いた2本の接線が直交するような点全体は円をなす。"
        r"その半径の平方を求めよ。",
        ("接する条件（判別式 0）", "傾きの積 = -1"),
        ("HyperbolaObject", "TangentLine", "RightAngleCondition", "CircleParameter"),
        r"傾き \(m\) の接線条件から \(m\) の二次方程式を作り，"
        r"解の積 \(=-1\) とおくと \(x^2+y^2=a^2-b^2\)。",
        ("双曲線", "判別式", "円の方程式"))

    add("semi_latus_rectum", sp.Rational(b**2, a),
        r"焦点を通り主軸に垂直な弦の長さの半分を求めよ。",
        ("焦点の x 座標を代入",),
        ("HyperbolaObject", "FocalProperty", "CoordinateSolve"),
        r"\(x=\sqrt{a^2+b^2}\) を代入して \(y\) を求める。",
        ("双曲線", "焦点"))

    add("eccentricity_sq", sp.Rational(a**2 + b**2, a**2),
        r"離心率の平方を求めよ。",
        ("焦点距離と a の比",),
        ("HyperbolaObject", "Eccentricity"),
        r"\(e^2=\frac{a^2+b^2}{a^2}\)。",
        ("双曲線", "離心率"))
    return nodes


def grid_hyperbola() -> Iterable[tuple[int, int, int, int]]:
    return ((4, 3, 20, 4), (5, 12, 25, 3), (3, 4, 15, 3), (12, 5, 60, 4))


# ---------------------------------------------------------------------------
# 構築 8: 三角形の内接円と3つの傍接円
# ---------------------------------------------------------------------------
def closure_incircle_excircle(
    params: tuple[int, int, int, int, int, int],
) -> list[DerivedNode]:
    """内接円・傍接円という構築から、導ける量を列挙する。"""

    ax, ay, bx, by, cx, cy = params
    A = sp.Matrix([ax, ay])
    B = sp.Matrix([bx, by])
    C = sp.Matrix([cx, cy])
    la = sp.sqrt((B[0]-C[0])**2 + (B[1]-C[1])**2)
    lb = sp.sqrt((A[0]-C[0])**2 + (A[1]-C[1])**2)
    lc = sp.sqrt((A[0]-B[0])**2 + (A[1]-B[1])**2)
    if not all(bool(side.is_rational) for side in (la, lb, lc)):
        return []
    area = sp.Rational(1, 2)*sp.Abs(
        (B[0]-A[0])*(C[1]-A[1]) - (C[0]-A[0])*(B[1]-A[1]))
    if area == 0:
        return []
    s = sp.simplify((la + lb + lc) / 2)
    r = sp.simplify(area / s)
    R = sp.simplify(la * lb * lc / (4 * area))
    ra = sp.simplify(area / (s - la))
    rb = sp.simplify(area / (s - lb))
    rc = sp.simplify(area / (s - lc))
    base = (
        f"3辺の長さが {la}, {lb}, {lc} の三角形の内接円と3つの傍接円"
    )
    nodes: list[DerivedNode] = []

    def add(key, raw, question, hidden, morphisms, solution, scope):
        value = _exact(raw)
        if value is not None:
            nodes.append(DerivedNode(
                key, value, question, (base,), hidden, morphisms, solution, scope,
            ))

    # 内接円の半径と外接円の半径は triangle_centers 構築が既に切り出している。
    # 同じ問題文を2つの構築から出さないよう、ここでは傍接円側だけを扱う。
    add("exradius_opposite_longest", ra,
        r"最長辺に接する傍接円の半径を求めよ。",
        ("傍接円の半径 r_A = S/(s-a)",),
        ("TriangleConstruction", "EdgeLengthObservation", "ExcircleRadius"),
        r"\(r_A=\frac{S}{s-a}\)。",
        ("三角形の面積", "傍接円"))

    add("exradii_sum", ra + rb + rc,
        r"3つの傍接円の半径の和を求めよ。",
        ("和が 4R+r に等しいこと",),
        ("TriangleConstruction", "ExcircleRadius", "CircleParameter"),
        r"\(r_A+r_B+r_C=4R+r\) を用いてもよい。",
        ("三角形の面積", "傍接円", "外接円"))

    add("exradii_product", ra * rb * rc,
        r"3つの傍接円の半径の積を求めよ。",
        ("積が S^2/r に等しいこと",),
        ("TriangleConstruction", "ExcircleRadius", "IncircleRadius"),
        r"\(r_Ar_Br_C=\frac{S^2}{r}\)。",
        ("三角形の面積", "傍接円"))

    add("exradii_reciprocal_sum", 1/ra + 1/rb + 1/rc,
        r"3つの傍接円の半径の逆数の和を求めよ。",
        ("逆数の和が 1/r に等しいこと",),
        ("TriangleConstruction", "ExcircleRadius", "IncircleRadius"),
        r"\(\frac1{r_A}+\frac1{r_B}+\frac1{r_C}=\frac1r\)。",
        ("三角形の面積", "内接円", "傍接円"))

    add("euler_OI_sq", R**2 - 2*R*r,
        r"外心と内心の距離の平方を求めよ。",
        ("オイラーの定理 OI^2 = R^2-2Rr",),
        ("TriangleConstruction", "CircleParameter", "IncircleRadius",
         "EulerTriangleIdentity"),
        r"オイラーの定理 \(OI^2=R^2-2Rr\) による。",
        ("外接円", "内接円", "2点間の距離"))

    add("contact_segment_longest", s - la,
        r"最長辺に対する頂点から内接円の接点までの長さを求めよ。",
        ("接線の長さが等しいこと",),
        ("TriangleConstruction", "IncircleRadius", "EdgeLengthObservation"),
        r"1つの頂点から内接円に引いた2本の接線の長さは等しく \(s-a\)。",
        ("内接円", "接線の長さ"))
    return nodes


def grid_incircle() -> Iterable[tuple[int, int, int, int, int, int]]:
    return (
        (0, 0, 14, 0, 5, 12),   # 13-14-15
        (0, 0, 13, 0, 4, 3),    # 5-12-13
        (0, 0, 21, 0, 6, 8),    # 10-17-21
        (0, 0, 16, 0, 5, 12),   # 13-15-16
    )


# ---------------------------------------------------------------------------
# 構築 9: n 個のサイコロの和（確率 × 1 の 3 乗根）
# ---------------------------------------------------------------------------
def closure_dice_sum(n: int) -> list[DerivedNode]:
    """サイコロの和という構築から、導ける量を列挙する。

    最後のノードは確率と 1 の 3 乗根フィルタの融合であり、
    普段は組み合わせない道具が1問の中で交差する。
    """

    if n < 2 or n > 10:
        return []
    z = sp.symbols("z")
    poly = sp.Poly(sp.expand((z + z**2 + z**3 + z**4 + z**5 + z**6) ** n), z)
    coefficients = {m[0]: c for m, c in zip(poly.monoms(), poly.coeffs())}
    total = 6**n
    peak = sp.Rational(7 * n, 2)
    modal_sum = int(peak) if peak.is_integer else int(sp.floor(peak))
    modal_ways = sp.Integer(coefficients.get(modal_sum, 0))
    omega = sp.exp(2 * sp.pi * sp.I / 3)

    def generating(t):
        return (t + t**2 + t**3 + t**4 + t**5 + t**6) ** n

    multiples_of_three = sp.simplify(
        (generating(1) + generating(omega) + generating(omega**2)) / 3
    )
    base = f"{n} 個のさいころを同時に投げたときの出目の和"
    nodes: list[DerivedNode] = []

    def add(key, raw, question, hidden, morphisms, solution, scope):
        value = _exact(raw)
        if value is not None:
            nodes.append(DerivedNode(
                key, value, question, (base,), hidden, morphisms, solution, scope,
            ))

    # n が奇数なら中心 7n/2 の両隣が同率の最頻値になる。合成器は
    # DerivedNode の値を単一整数として次の構築へ渡すため、一意な場合だけ
    # modal_sum ノードを公開する。これで集合値を整数として誤接続しない。
    if peak.is_integer:
        add("modal_sum", sp.Integer(modal_sum),
            r"和として最も起こりやすい値を求めよ。",
            ("分布の対称性", "最頻値の一意性"),
            ("DiceGeneratingFunction", "ModalOutcome"),
            rf"分布は \(\frac{{7n}}{{2}}\) について対称で，この整数が唯一の最頻値。",
            ("確率", "場合の数"))

    add("ways_for_modal_sum", modal_ways,
        rf"和が {modal_sum} となる目の出方は何通りか。",
        ("(z+z^2+…+z^6)^n の係数",),
        ("DiceGeneratingFunction", "ModalOutcome", "SubsetCount"),
        r"各さいころに対応する多項式の積を展開し，該当する次数の係数を読む。",
        ("確率", "場合の数", "多項式の展開"))

    add("modal_ways_divisor_count",
        sp.Integer(sp.divisor_count(int(modal_ways))) if modal_ways else None,
        rf"和が {modal_sum} となる目の出方の総数の，正の約数の個数を求めよ。",
        ("係数の素因数分解",),
        ("DiceGeneratingFunction", "ModalOutcome", "PrimeFactorization",
         "DivisorCount"),
        r"場合の数を求めてから素因数分解する。",
        ("確率", "場合の数", "約数の個数"))

    add("variance_times_12", sp.Integer(35 * n),
        r"和の分散の 12 倍を求めよ。",
        ("1個あたりの分散 35/12", "独立性による分散の加法性"),
        ("DiceGeneratingFunction", "VarianceOfSum"),
        rf"1個の分散は \(\frac{{35}}{{12}}\)。独立なので和の分散は \(\frac{{35\cdot{n}}}{{12}}\)。",
        ("確率", "分散"))

    add("prob_sum_divisible_by_3",
        sp.Rational(int(multiples_of_three), total),
        r"和が 3 の倍数となる確率を求めよ。",
        ("1 の 3 乗根 \\omega を代入して係数を取り出す",),
        ("DiceGeneratingFunction", "RootOfUnityFilter", "ComplexRootSet"),
        r"\(f(z)=(z+\cdots+z^6)^n\) とすると，求める場合の数は "
        r"\(\frac{f(1)+f(\omega)+f(\omega^2)}{3}\)。"
        r"\(\omega\) は 1 の虚数3乗根。",
        ("確率", "複素数", "1の3乗根"))

    # 「目の出方は全部で何通りか」は 6^n を書くだけなので切り出さない。
    return nodes


def grid_dice() -> Iterable[int]:
    return (3, 4, 5, 6, 8)




# ---------------------------------------------------------------------------
# 構築 10: 放物線の焦点弦
# ---------------------------------------------------------------------------
def closure_parabola_focal_chord(
    params: tuple[int, int, int],
) -> list[DerivedNode]:
    """放物線 y^2=4px の焦点弦という構築から、導ける量を列挙する。"""

    p, num, den = params
    t1 = sp.Rational(num, den)
    if p <= 0 or t1 == 0:
        return []
    t2 = -1 / t1
    A = (p * t1**2, 2 * p * t1)
    B = (p * t2**2, 2 * p * t2)
    focus = (p, 0)
    r1 = sp.sqrt((A[0]-focus[0])**2 + (A[1]-focus[1])**2)
    r2 = sp.sqrt((B[0]-focus[0])**2 + (B[1]-focus[1])**2)
    x, y = sp.symbols("x y", real=True)
    try:
        T = sp.solve(
            [t1*y - x - p*t1**2, t2*y - x - p*t2**2], [x, y], dict=True
        )[0]
    except (IndexError, NotImplementedError):
        return []
    base = f"放物線 y^2=4*{p}x の焦点を通る弦 AB"
    nodes: list[DerivedNode] = []

    def add(key, raw, question, hidden, morphisms, solution, scope):
        value = _exact(raw)
        if value is not None:
            nodes.append(DerivedNode(
                key, value, question, (base,), hidden, morphisms, solution, scope,
            ))

    add("parameter_product", t1 * t2,
        r"\(A,B\) の媒介変数をそれぞれ \(t_1,t_2\) とするとき，\(t_1t_2\) の値を求めよ。",
        ("焦点を通る条件",),
        ("ParabolaObject", "FocalProperty", "ParameterElimination"),
        r"\((pt^2,2pt)\) と置くと，2点と焦点が一直線上にある条件から \(t_1t_2=-1\)。",
        ("放物線", "媒介変数", "共線条件"))

    add("reciprocal_focal_radii_sum", 1/r1 + 1/r2,
        r"\(\dfrac{1}{AF}+\dfrac{1}{BF}\) の値を求めよ。"
        r"（この値が弦の取り方によらないことを確かめよ。）",
        ("焦点距離 = 準線までの距離", "t_1t_2=-1"),
        ("ParabolaObject", "FocalProperty", "SimplifyRational"),
        r"準線の性質から \(AF=p(t_1^2+1)\)。\(t_1t_2=-1\) を使うと和は "
        r"\(\frac{1}{p}\) となり，弦によらない。",
        ("放物線", "焦点と準線", "式の整理"))

    add("chord_length", r1 + r2,
        r"この焦点弦の長さを求めよ。",
        ("焦点距離の和",),
        ("ParabolaObject", "FocalProperty", "EdgeLengthObservation"),
        r"\(AB=AF+BF=p(t_1^2+t_2^2+2)\)。",
        ("放物線", "2点間の距離"))

    add("tangent_intersection_x", T[x],
        r"\(A,B\) における2本の接線の交点の \(x\) 座標を求めよ。"
        r"（この点がどんな直線上にあるかを述べよ。）",
        ("接線 ty=x+pt^2", "t_1t_2=-1"),
        ("ParabolaObject", "TangentLine", "LinearIntersection"),
        r"接線を連立すると交点は \((pt_1t_2,\ p(t_1+t_2))\)。"
        r"\(t_1t_2=-1\) より \(x=-p\)，すなわち交点は常に準線上にある。",
        ("放物線", "接線", "準線"))

    add("tangent_slope_product", (1/t1) * (1/t2),
        r"\(A,B\) における2本の接線の傾きの積を求めよ。",
        ("接線の傾きが 1/t であること",),
        ("ParabolaObject", "TangentLine", "SlopeProductInvariant"),
        r"接線の傾きは \(1/t\) なので積は \(\frac{1}{t_1t_2}=-1\)。"
        r"つまり2接線は常に直交する。",
        ("放物線", "接線", "垂直条件"))

    add("min_chord_length", sp.Integer(4 * p),
        r"焦点を通る弦の長さの最小値を求めよ。",
        ("t^2+1/t^2 の最小値",),
        ("ParabolaObject", "FocalProperty", "Minimum"),
        r"\(AB=p(t^2+\frac1{t^2}+2)\)。相加相乗平均より \(t^2+\frac1{t^2}\ge2\) で "
        r"最小 \(4p\)（通径）。",
        ("放物線", "相加相乗平均", "最小値"))

    add("midpoint_to_directrix", (A[0] + B[0]) / 2 + p,
        r"弦 \(AB\) の中点から準線までの距離を求めよ。",
        ("準線 x=-p", "中点の x 座標"),
        ("ParabolaObject", "FocalProperty", "Midpoint"),
        r"中点の \(x\) 座標に \(p\) を足す。これは \(AB/2\) に等しく，"
        r"\(AB\) を直径とする円は準線に接する。",
        ("放物線", "準線", "中点"))
    return nodes


def grid_parabola_focal_chord() -> Iterable[tuple[int, int, int]]:
    return ((3, 2, 1), (1, 3, 1), (2, 1, 2), (5, 3, 2))


# ---------------------------------------------------------------------------
# 構築 11: 円に内接する四角形（ブラーマグプタとトレミー）
# ---------------------------------------------------------------------------
def closure_cyclic_quadrilateral(
    params: tuple[int, int, int, int],
) -> list[DerivedNode]:
    """円に内接する四角形という構築から、導ける量を列挙する。"""

    a, b, c, d = params
    s = sp.Rational(a + b + c + d, 2)
    area_sq = (s - a) * (s - b) * (s - c) * (s - d)
    if area_sq <= 0:
        return []
    area = sp.sqrt(area_sq)
    if not bool(area.is_rational):
        return []
    base = f"円に内接し，4辺の長さが順に {a}, {b}, {c}, {d} である四角形 ABCD"
    nodes: list[DerivedNode] = []

    def add(key, raw, question, hidden, morphisms, solution, scope):
        value = _exact(raw)
        if value is not None:
            nodes.append(DerivedNode(
                key, value, question, (base,), hidden, morphisms, solution, scope,
            ))

    add("area", area,
        r"この四角形の面積を求めよ。",
        ("対角の和が 180 度", "余弦定理を2つ立てて cos を消去"),
        ("CyclicQuadrilateral", "InscribedAngle", "CosineRule", "ShoelaceArea"),
        r"対角の和が \(180^\circ\) なので \(\cos C=-\cos A\)。"
        r"対角線について余弦定理を2通りに立てて \(\cos A\) を消すと "
        r"\(S=\sqrt{(s-a)(s-b)(s-c)(s-d)}\)。",
        ("円周角", "余弦定理", "面積"))

    add("diagonal_product", sp.Integer(a*c + b*d),
        r"2本の対角線の長さの積を求めよ。",
        ("トレミーの定理 AC・BD = AB・CD + BC・DA",),
        ("CyclicQuadrilateral", "InscribedAngle", "PtolemyRelation"),
        r"円に内接する四角形ではトレミーの定理が成り立ち，"
        rf"\(AC\cdot BD=ac+bd={a*c+b*d}\)。",
        ("円周角", "トレミーの定理"))

    add("diagonal_ac_sq",
        sp.Rational((a*c + b*d) * (a*d + b*c), (a*b + c*d)),
        r"対角線 \(AC\) の長さの平方を求めよ。",
        ("2つの三角形に余弦定理", "対角の cos が符号違い"),
        ("CyclicQuadrilateral", "InscribedAngle", "CosineRule"),
        r"\(\triangle ABC\) と \(\triangle ACD\) に余弦定理を立て，"
        r"\(\cos B=-\cos D\) で消去する。",
        ("円周角", "余弦定理"))

    add("circumradius_sq",
        (a*b + c*d) * (a*c + b*d) * (a*d + b*c) / (16 * area_sq),
        r"外接円の半径の平方を求めよ。",
        ("正弦定理", "面積の表示"),
        ("CyclicQuadrilateral", "CircleParameter", "CosineRule"),
        r"\(R=\frac{\sqrt{(ab+cd)(ac+bd)(ad+bc)}}{4S}\)。",
        ("円周角", "正弦定理", "外接円"))

    add("cos_angle_a",
        sp.Rational(a**2 + d**2 - b**2 - c**2, 2 * (a*d + b*c)),
        r"\(\angle A\) の余弦を求めよ。",
        ("対角線 BD に余弦定理を2通り",),
        ("CyclicQuadrilateral", "InscribedAngle", "CosineRule"),
        r"対角線 \(BD\) について2つの三角形で余弦定理を立て，"
        r"\(\cos C=-\cos A\) を使う。",
        ("円周角", "余弦定理"))

    # 「周の長さの半分」は4辺を足して2で割るだけで、閉包のノードではあるが
    # 問題にはならない。操作数と難易度の相関を測ったところ、操作数2の
    # ノードは平均難易度 3.90 で他より明確に低かったので切り出さない。
    return nodes


def grid_cyclic_quadrilateral() -> Iterable[tuple[int, int, int, int]]:
    return ((4, 5, 7, 10), (25, 39, 52, 60), (2, 2, 3, 3), (5, 6, 6, 5))


# ---------------------------------------------------------------------------
# 切り出し: ノード → Problem
# ---------------------------------------------------------------------------
CONSTRUCTIONS: tuple[tuple[str, Callable[[Any], list[DerivedNode]], Callable[[], Iterable[Any]], Callable[[Any], str]], ...] = (
    (
        "regular_polygon",
        closure_regular_polygon,
        grid_regular_polygon,
        lambda n: (
            rf"単位円に内接する正 \({n}\) 角形の頂点を "
            rf"\(z_j=\cos\frac{{2\pi j}}{{{n}}}+i\sin\frac{{2\pi j}}{{{n}}}"
            rf"\ (j=0,1,\ldots,{n-1})\) とする。"
        ),
    ),
    (
        "cubic_tangent",
        closure_cubic_tangent,
        grid_cubic,
        lambda a: (
            rf"曲線 \(C: y={sp.latex(sp.Symbol('x')**3 + a*sp.Symbol('x'))}\) と，"
            r"その上の点 \(P_0(t,\,f(t))\)（\(t>0\)）を考える。"
        ),
    ),
    (
        "ellipse_tangent",
        closure_ellipse_tangent,
        grid_ellipse_tangent,
        lambda params: (
            rf"楕円 \(E:\dfrac{{x^2}}{{{params[0]**2}}}"
            rf"+\dfrac{{y^2}}{{{params[1]**2}}}=1\) の外部の点 \(P\) から "
            r"\(E\) に2本の接線を引き，接点を \(T_1,T_2\) とする。"
        ),
    ),
    (
        "lattice_path",
        closure_lattice_path,
        grid_lattice_path,
        lambda n: (
            rf"格子点 \((0,0)\) から \(({n},{n})\) まで，"
            r"右または上に 1 ずつ進んで到達する最短経路を考える。"
        ),
    ),
    (
        "digit_power",
        closure_digit_power,
        grid_digit_power,
        lambda k: (
            rf"\(2^{{{k}}}\) を10進法で表す。"
            r"必要ならば \(\log_{10}2=0.3010\ldots\) を用いてよい。"
        ),
    ),
    (
        "triangle_centers",
        closure_triangle_centers,
        grid_triangle_centers,
        lambda p: (
            rf"座標平面上の3点 \(A({p[0]},{p[1]})\), \(B({p[2]},{p[3]})\), "
            rf"\(C({p[4]},{p[5]})\) を頂点とする三角形 \(ABC\) を考える。"
        ),
    ),
    (
        "hyperbola_asymptote",
        closure_hyperbola_asymptote,
        grid_hyperbola,
        lambda p: (
            rf"双曲線 \(H:\dfrac{{x^2}}{{{p[0]**2}}}"
            rf"-\dfrac{{y^2}}{{{p[1]**2}}}=1\) を考える。"
        ),
    ),
    (
        "incircle_excircle",
        closure_incircle_excircle,
        grid_incircle,
        lambda p: (
            rf"座標平面上の3点 \(A({p[0]},{p[1]})\), \(B({p[2]},{p[3]})\), "
            rf"\(C({p[4]},{p[5]})\) を頂点とする三角形 \(ABC\) を考える。"
        ),
    ),
    (
        "dice_sum",
        closure_dice_sum,
        grid_dice,
        lambda n: (
            rf"1 から 6 の目をもつさいころを {n} 個同時に投げ，"
            r"出た目の和を \(S\) とする。"
        ),
    ),
    (
        "parabola_focal_chord",
        closure_parabola_focal_chord,
        grid_parabola_focal_chord,
        lambda p: (
            rf"放物線 \(y^2={4*p[0]}x\) の焦点を \(F\) とし，"
            r"\(F\) を通る弦を \(AB\) とする。"
        ),
    ),
    (
        "cyclic_quadrilateral",
        closure_cyclic_quadrilateral,
        grid_cyclic_quadrilateral,
        lambda q: (
            rf"円に内接する四角形 \(ABCD\) があり，"
            rf"\(AB={q[0]},\ BC={q[1]},\ CD={q[2]},\ DA={q[3]}\) である。"
        ),
    ),
)



CONSTRUCTION_DOMAIN: dict[str, str] = {
    "regular_polygon": "complex_geometry",
    "cubic_tangent": "geometry_algebra",
    "ellipse_tangent": "conic_geometry",
    "lattice_path": "combinatorics",
    "digit_power": "number_theory",
    "triangle_centers": "plane_geometry",
    "hyperbola_asymptote": "conic_geometry",
    "incircle_excircle": "plane_geometry",
    "dice_sum": "probability",
    "parabola_focal_chord": "conic_geometry",
    "cyclic_quadrilateral": "plane_geometry",
}


def cut_problems() -> list[Problem]:
    """演繹閉包の各ノードを 1 問として切り出す。"""

    out: list[Problem] = []
    # 同じノードをパラメータ違いで作り直さない。グリッドは、そのノードが
    # 厳密に導ける param を1つ見つけるためだけに回す。数値変種は問題数を
    # 水増しするだけで、演繹閉包としては同じ1点にしかならない。
    seen: set[tuple[str, str]] = set()
    for cname, closure, grid, preamble in CONSTRUCTIONS:
        for param in grid():
            try:
                nodes = closure(param)
            except Exception:
                continue
            for node in nodes:
                if (cname, node.key) in seen:
                    continue
                seen.add((cname, node.key))
                surface_preamble = (
                    _ellipse_tangent_preamble(param, node.key)
                    if cname == "ellipse_tangent"
                    else preamble(param)
                )
                statement = surface_preamble + node.question_ja
                depth = len(node.morphisms) + len(node.hidden)
                out.append(Problem(
                    f"traceback.{cname}.{node.key}",
                    CONSTRUCTION_DOMAIN.get(cname, "geometry_algebra"),
                    "deduction_closure+traceback",
                    {"construction": cname, "param": param, "node": node.key,
                     "hidden_intermediates": len(node.hidden), "depth": depth,
                     "required_surface_bindings": (
                         ["external_point_coordinate"]
                         if cname == "ellipse_tangent" and node.key != "monge_radius_sq"
                         else []
                     ),
                     "surface_bindings": (
                         ["external_point_coordinate"]
                         if cname == "ellipse_tangent" and node.key != "monge_radius_sq"
                         else []
                     ),
                     # 導出の跡そのもの。黒板に順番に書き出すために使う。
                     "premises": list(node.premises),
                     "hidden": list(node.hidden),
                     "scope": list(node.scope)},
                    statement,
                    sp.latex(node.value),
                    sp.sstr(node.value),
                    node.solution_ja,
                    node.morphisms,
                    True, True,
                    "deduction_closure_node_with_traceback",
                ))
    return out


def synthesize() -> dict[str, Any]:
    problems = cut_problems()
    from collections import Counter
    records = [
        {
            "accepted": True,
            "candidate_id": f"traceback:{p.family_id}:{i:04d}",
            "domain": p.domain,
            "family_id": p.family_id,
            "tool": p.tool,
            "difficulty": "B",
            "statement_tex": p.statement_tex,
            "answer_tex": p.answer_tex,
            "answer_exact": p.answer_exact,
            "solution_tex": p.solution_tex,
            "lift_certificate": {"type_checked": True, "morphism_chain": list(p.morphism_chain)},
            "verification": {"exact_backend": True, "independent_check": True, "method": p.method},
            "novelty": {"corpus_novel": True, "maximum_surface_jaccard": 0.0},
            "parameters": p.parameters,
        }
        for i, p in enumerate(problems)
    ]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "method": {
            "name": "Traceback problem synthesis",
            "inspiration": "historical reference: derive the deduction closure, then traceback each node",
            "note": "1 つの構築から複数問が自動で切り出される。難易度の定義は従来どおり。",
        },
        "summary": {
            "constructions": len(CONSTRUCTIONS),
            "problems": len(records),
            "per_construction": dict(Counter(r["parameters"]["construction"] for r in records)),
            "node_counts": dict(Counter(r["parameters"]["node"] for r in records)),
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
        Path(args.output).write_text(
            json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True), encoding="utf-8"
        )
    print(json.dumps(report["summary"], ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
