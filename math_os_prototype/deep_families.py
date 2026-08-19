"""深層族 (8層): 族を減らして深くする。東大・数オリ級を狙う。

各族は 8 個の射を連鎖し、途中で構造が何度も変わる。すべて高校数学の道具で
解けるが、到達するまでに何段も踏む必要がある。
"""

from __future__ import annotations

import itertools
import math
from collections import defaultdict
from functools import lru_cache
from typing import Any, Callable, Iterable

import sympy as sp

try:
    from math_os_prototype.construct_engine import Problem, _term
except ImportError:  # pragma: no cover
    from construct_engine import Problem, _term


def _deep_paley_spectrum(params: dict[str, Any]) -> Problem | None:
    """素数→平方剰余→Paleyグラフ→隣接行列→A^3→閉歩道→三角形→トレース(8層)。"""
    p = params["p"]
    if p % 4 != 1:
        return None
    QR = set((k * k) % p for k in range(1, p))
    triangles = p * (p - 1) * (p - 5) // 48
    brute = 0
    for x in range(p):
        for y in range(x + 1, p):
            if (y - x) % p not in QR:
                continue
            for z in range(y + 1, p):
                if (z - y) % p in QR and (z - x) % p in QR:
                    brute += 1
    if brute != triangles:
        return None
    answer = 6 * triangles
    return Problem(
        "deep.paley_spectrum_triangles",
        "number_theory_graph",
        "quadratic_residue+spectral+counting",
        params,
        rf"素数 \(p={p}\)（\(p\equiv1\pmod4\)）に対し，頂点集合 \(\mathbb Z_{{{p}}}\) 上の"
        r"グラフ \(G\) を，2頂点 \(x,y\) が \(x-y\) が平方剰余のとき辺で結ぶことで定める。"
        r"\(G\) の隣接行列を \(A\) とするとき，\(\operatorname{tr}(A^3)\) を求めよ。",
        str(answer),
        str(answer),
        rf"\(\operatorname{{tr}}(A^3)\) は長さ3の閉じた歩道の総数で，三角形1個が6回"
        rf"数えられる。この \(G\) では各辺の共通隣接点が \((p-5)/4\) 個なので三角形は "
        rf"\(\frac{{p(p-1)(p-5)}}{{48}}={triangles}\) 個。よって "
        rf"\(\operatorname{{tr}}(A^3)=6\times{triangles}={answer}\)。",
        (
            "PrimeField", "QuadraticResidueSet", "PaleyGraph", "AdjacencyMatrix",
            "MatrixCube", "ClosedWalkCount", "TriangleCount", "TraceInvariant",
        ),
        True,
        True,
        "adjacency_trace_vs_exhaustive_triangle_count",
    )


def _grid_deep_paley() -> Iterable[dict[str, Any]]:
    for p in (13, 17, 29, 37, 41, 53, 61, 73, 89, 97):
        yield {"p": p}


def _deep_tangent_growth(params: dict[str, Any]) -> Problem | None:
    """三次曲線→接線→再交点→反復→一般項→増大度→対数→極限(8層)。"""
    coeff = params["coeff"]
    x, t, n = sp.symbols("x t n", real=True)
    f = x**3 + coeff * x
    slope = sp.diff(f, x).subs(x, t)
    others = [
        sp.simplify(s)
        for s in sp.solve(sp.Eq(f, (t**3 + coeff * t) + slope * (x - t)), x)
        if sp.simplify(s - t) != 0
    ]
    if not others or sp.simplify(others[0] - (-2 * t)) != 0:
        return None
    limit = sp.log(2)
    return Problem(
        "deep.tangent_iteration_growth",
        "geometry_analysis",
        "symbolic_intersection+iteration+limit",
        params,
        rf"曲線 \(C: y={sp.latex(f)}\) 上に点 "
        rf"\(P_0(t,\,{sp.latex(t**3 + coeff * t)})\)（\(t>0\)）をとる。"
        r"\(P_i\) における \(C\) の接線が \(C\) と再び交わる点を \(P_{i+1}\) と定め，"
        r"\(P_n\) の \(x\) 座標を \(x_n\) とする。"
        r"極限 \(\displaystyle\lim_{n\to\infty}\frac{\log|x_n|}{n}\) を求めよ。",
        sp.latex(limit),
        sp.sstr(limit),
        r"接点で重根をもつことと三次方程式の根の和の関係から \(x_{i+1}=-2x_i\)。"
        r"したがって \(x_n=(-2)^n t\)，\(|x_n|=2^n|t|\)。"
        r"\(\frac{\log|x_n|}{n}=\log 2+\frac{\log|t|}{n}\to\log 2\)。",
        (
            "CubicCurve", "TangentLine", "Reintersection", "RootSumRelation",
            "GeometricIteration", "GeneralTerm", "GrowthRate", "LogarithmicLimit",
        ),
        True,
        True,
        "tangent_iteration_ratio_then_log_limit",
    )


def _grid_deep_tangent() -> Iterable[dict[str, Any]]:
    for coeff in (-9, -7, -5, -3, -1, 0, 1, 2, 3, 5):
        yield {"coeff": coeff}


def _deep_rotation_divisors(params: dict[str, Any]) -> Problem | None:
    """1の冪根→正n角形→頂点間距離→全積(=n)→約数個数(8層)。"""
    n_val = params["n"]
    if n_val < 3:
        return None
    prod = 1.0
    for j in range(1, n_val):
        d = abs(
            complex(1, 0)
            - complex(math.cos(2 * math.pi * j / n_val), math.sin(2 * math.pi * j / n_val))
        )
        prod *= d
    if abs(prod - n_val) > 1e-6:
        return None
    answer = sp.divisor_count(n_val)
    return Problem(
        "deep.rotation_diagonal_product_divisors",
        "complex_geometry",
        "roots_of_unity+product+divisor_function",
        params,
        rf"単位円に内接する正 \({n_val}\) 角形の頂点を "
        rf"\(z_j=\cos\frac{{2\pi j}}{{{n_val}}}+i\sin\frac{{2\pi j}}{{{n_val}}}"
        rf"\ (j=0,1,\ldots,{n_val - 1})\) とする。頂点 \(z_0\) から他の "
        rf"\({n_val - 1}\) 個の頂点までの距離の積を \(L\) とするとき，"
        r"\(L\) の正の約数の個数を求めよ。",
        str(answer),
        str(answer),
        rf"\(z^{{{n_val}}}-1=\prod_{{j=0}}^{{{n_val - 1}}}(z-z_j)\) の両辺を \(z-1\) で"
        rf"割り \(z\to1\) とすると \(\prod_{{j=1}}^{{{n_val - 1}}}(1-z_j)={n_val}\)。"
        rf"絶対値をとって \(L={n_val}\)。よって約数の個数は \({answer}\)。",
        (
            "RootOfUnity", "RegularPolygon", "VertexDistances", "PolynomialFactorization",
            "LimitEvaluation", "DistanceProduct", "IntegerValue", "DivisorCount",
        ),
        True,
        True,
        "cyclotomic_product_identity_plus_numeric_check",
    )


def _grid_deep_rotation() -> Iterable[dict[str, Any]]:
    for n in range(3, 40):
        yield {"n": n}


def _deep_recurrence_qr(params: dict[str, Any]) -> Problem | None:
    """漸化式→随伴行列→mod p の位数→周期→素因数→オイラーの規準→ルジャンドル記号(8層)。"""
    s, t, p = params["s"], params["t"], params["p"]
    if not sp.isprime(p):
        return None
    a, b, period = 0, 1, None
    for i in range(1, p * p * 6 + 1):
        a, b = b % p, (s * b + t * a) % p
        if a == 0 and b == 1:
            period = i
            break
    if not period or period < 2:
        return None
    q = max(sp.primefactors(period))
    if q % p == 0:
        return None
    answer = 1 if pow(q % p, (p - 1) // 2, p) == 1 else -1
    rhs = (_term(s, "a_{n+1}") + _term(t, "a_n")).lstrip("+")
    return Problem(
        "deep.recurrence_period_quadratic_character",
        "number_theory",
        "matrix_mod_order+legendre_symbol",
        params,
        rf"数列 \((a_n)\) を \(a_0=0,\ a_1=1,\ a_{{n+2}}={rhs}\) で定める。"
        rf"\((a_n)\) を \(\bmod\ {p}\) で見たときの最小周期を \(T\) とし，"
        rf"\(T\) の最大の素因数を \(q\) とする。ルジャンドル記号 "
        rf"\(\left(\dfrac{{q}}{{{p}}}\right)\) の値を求めよ。",
        str(answer),
        str(answer),
        rf"\((a_{{n+1}},a_n)\) は随伴行列 "
        rf"\(\begin{{pmatrix}}{s}&{t}\\1&0\end{{pmatrix}}\) を掛けて進むので，"
        rf"\(\bmod\ {p}\) でのこの行列の位数が周期 \(T={period}\)。"
        rf"その最大素因数は \(q={q}\)。オイラーの規準 "
        rf"\(q^{{({p}-1)/2}}\equiv{answer}\pmod{{{p}}}\) より "
        rf"\(\left(\frac{{{q}}}{{{p}}}\right)={answer}\)。",
        (
            "LinearRecurrence", "CompanionMatrix", "ModularReduction",
            "MultiplicativeOrder", "MinimalPeriod", "PrimeFactorization",
            "EulerCriterion", "LegendreSymbol",
        ),
        True,
        True,
        "modular_period_then_euler_criterion",
    )


def _grid_deep_recurrence() -> Iterable[dict[str, Any]]:
    for s, t in ((1, 1), (1, 2), (2, 1), (3, -1), (1, 3)):
        for p in (7, 11, 13, 17, 19, 23, 29, 31):
            yield {"s": s, "t": t, "p": p}


def _deep_centroid_subsets(params: dict[str, Any]) -> Problem | None:
    """正n角形→部分集合→重心→中心一致→巡回対称→個数(8層)。"""
    n_val = params["n"]
    if n_val < 3 or n_val > 12:
        return None
    count = 0
    for r in range(1, n_val + 1):
        for subset in itertools.combinations(range(n_val), r):
            zr = sum(math.cos(2 * math.pi * j / n_val) for j in subset)
            zi = sum(math.sin(2 * math.pi * j / n_val) for j in subset)
            if abs(zr) < 1e-9 and abs(zi) < 1e-9:
                count += 1
    if count == 0:
        return None
    return Problem(
        "deep.polygon_subset_centroid",
        "complex_geometry",
        "roots_of_unity+subset_enumeration",
        params,
        rf"単位円に内接する正 \({n_val}\) 角形の頂点を "
        rf"\(z_j=\cos\frac{{2\pi j}}{{{n_val}}}+i\sin\frac{{2\pi j}}{{{n_val}}}"
        rf"\ (j=0,1,\ldots,{n_val - 1})\) とする。空でない部分集合 \(S\) であって，"
        r"\(S\) に属する頂点の重心が円の中心と一致するものの個数を求めよ。",
        str(count),
        str(count),
        rf"重心が中心であることは \(\sum_{{j\in S}}z_j=0\) と同値。\(z_j\) は1の "
        rf"\({n_val}\) 乗根なので，和が消える部分集合を数えればよい。"
        r"巡回対称性から，正多角形をなす頂点集合とその合併が条件を満たす。",
        (
            "RootOfUnity", "RegularPolygon", "SubsetFamily", "CentroidMap",
            "VanishingSum", "CyclotomicRelation", "SymmetryReduction", "SubsetCount",
        ),
        True,
        True,
        "exhaustive_subset_vanishing_sum_count",
    )


def _grid_deep_centroid() -> Iterable[dict[str, Any]]:
    for n in range(3, 13):
        yield {"n": n}


def _factor_data(value: int) -> tuple[dict[int, int], int]:
    factors = {int(p): int(e) for p, e in sp.factorint(value).items()}
    divisors = math.prod(exponent + 1 for exponent in factors.values())
    return factors, divisors


def _factor_tex(factors: dict[int, int]) -> str:
    return r"\cdot ".join(
        str(prime) if exponent == 1 else rf"{prime}^{{{exponent}}}"
        for prime, exponent in sorted(factors.items())
    )


def _paley_adjacency(p: int) -> sp.Matrix:
    residues = {(k * k) % p for k in range(1, p)}
    adjacency = sp.zeros(p)
    for i in range(p):
        for j in range(i + 1, p):
            if (j - i) % p in residues:
                adjacency[i, j] = adjacency[j, i] = 1
    return adjacency


def _ultradeep_paley_tree_divisors(params: dict[str, Any]) -> Problem | None:
    """Paleyグラフのスペクトルから全域木を数え、その約数関数まで送る(12射)。"""
    p = int(params["p"])
    if p % 4 != 1 or not sp.isprime(p):
        return None
    half = (p - 1) // 2
    quarter = (p - 1) // 4
    tree_count = p ** ((p - 3) // 2) * quarter**half
    factors: defaultdict[int, int] = defaultdict(int)
    factors[p] += (p - 3) // 2
    for prime, exponent in sp.factorint(quarter).items():
        factors[int(prime)] += int(exponent) * half
    divisor_count = math.prod(exponent + 1 for exponent in factors.values())

    adjacency = _paley_adjacency(p)
    degree = (p - 1) // 2
    laplacian = sp.diag(*([degree] * p)) - adjacency
    independent_tree_count = int(laplacian[1:, 1:].det())
    if independent_tree_count != tree_count:
        return None

    factor_tex = _factor_tex(dict(factors))
    return Problem(
        "ultradeep.paley_spanning_tree_divisor_count",
        "spectral_graph_number_theory",
        "paley_spectrum+matrix_tree+exact_determinant",
        params,
        rf"素数 \(p={p}\) に対し，頂点集合 \(\mathbb Z_{{{p}}}\) 上で，"
        r"\(x-y\) が平方剰余であるときに \(x,y\) を結んで得られる Paley グラフを "
        r"\(G\) とする。\(G\) の全域木の個数を \(\tau\) とするとき，"
        r"\(\tau\) の正の約数の個数を求めよ。",
        str(divisor_count),
        str(divisor_count),
        rf"Paley グラフの隣接行列の非自明固有値は "
        rf"\(\frac{{-1\pm\sqrt{{{p}}}}}2\)（各重複度 \({half}\)）。"
        rf"次数 \({degree}\) のラプラシアンの非零固有値の積を Kirchhoff の定理で"
        rf"\({p}\) で割ると "
        rf"\(\tau={p}^{{{(p - 3) // 2}}}\left(\frac{{{p}-1}}4\right)^{{{half}}}"
        rf"={factor_tex}\)。したがって約数の個数は \({divisor_count}\)。",
        (
            "PrimeField",
            "QuadraticResidueSet",
            "PaleyGraph",
            "AdjacencyMatrix",
            "AdjacencySpectrum",
            "LaplacianTransform",
            "LaplacianSpectrum",
            "NonzeroEigenvalueProduct",
            "MatrixTreeTheorem",
            "SpanningTreeCount",
            "PrimeFactorization",
            "DivisorCount",
        ),
        True,
        True,
        "spectral_tree_formula_vs_exact_laplacian_cofactor",
    )


def _grid_ultradeep_paley_tree() -> Iterable[dict[str, Any]]:
    for p in (5, 13, 17, 29, 37):
        yield {"p": p}


def _ultradeep_paley_four_cycle_divisors(
    params: dict[str, Any],
) -> Problem | None:
    """共通隣接点から4-cycleを二重計数し、約数関数まで送る(10射)。"""
    p = int(params["p"])
    if p % 4 != 1 or not sp.isprime(p):
        return None
    degree = (p - 1) // 2
    adjacent_common = (p - 5) // 4
    nonadjacent_common = (p - 1) // 4
    pair_count = p * (p - 1) // 4
    cycles = (
        pair_count
        * (
            math.comb(adjacent_common, 2)
            + math.comb(nonadjacent_common, 2)
        )
        // 2
    )
    if cycles <= 0:
        return None

    adjacency = _paley_adjacency(p)
    squared = adjacency * adjacency
    trace_four = sum(
        int(squared[i, j]) ** 2 for i in range(p) for j in range(p)
    )
    trace_cycles = (
        trace_four
        - 2 * pair_count
        - 4 * p * math.comb(degree, 2)
    ) // 8
    if trace_cycles != cycles:
        return None
    factors, divisor_count = _factor_data(cycles)

    return Problem(
        "ultradeep.paley_four_cycle_divisor_count",
        "graph_combinatorics_number_theory",
        "strongly_regular_graph+trace_four+factorization",
        params,
        rf"素数 \(p={p}\) に対し，頂点集合 \(\mathbb Z_{{{p}}}\) 上で，"
        r"\(x-y\) が平方剰余であるときに \(x,y\) を結んで得られる Paley グラフを "
        r"\(G\) とする。\(G\) に含まれる単純な長さ4の閉路の個数を \(C\) とする。"
        r"\(C\) の正の約数の個数を求めよ。",
        str(divisor_count),
        str(divisor_count),
        rf"隣接2頂点の共通隣接点は \({adjacent_common}\) 個，非隣接2頂点では "
        rf"\({nonadjacent_common}\) 個。向かい合う頂点対で二重計数すると "
        rf"\(C={cycles}\)。\(C={_factor_tex(factors)}\) なので，"
        rf"正の約数は \({divisor_count}\) 個。",
        (
            "PrimeField",
            "QuadraticResidueSet",
            "PaleyGraph",
            "StronglyRegularParameters",
            "CommonNeighborRelation",
            "OppositeVertexPairing",
            "FourCycleDoubleCount",
            "CycleCount",
            "PrimeFactorization",
            "DivisorCount",
        ),
        True,
        True,
        "common_neighbor_double_count_vs_adjacency_trace_four",
    )


def _grid_ultradeep_paley_four_cycles() -> Iterable[dict[str, Any]]:
    for p in (13, 17, 29, 37, 41):
        yield {"p": p}


def _ultradeep_cyclotomic_norm_divisors(
    params: dict[str, Any],
) -> Problem | None:
    """原始根まで絞った距離積を円分ノルムに移し、約数関数まで送る(11射)。"""
    n_val, a = int(params["n"]), int(params["a"])
    if n_val < 3 or a <= 1:
        return None
    x = sp.symbols("x")
    cyclotomic = sp.Poly(sp.cyclotomic_poly(n_val, x), x)
    norm = abs(int(cyclotomic.eval(a)))
    if norm <= 1:
        return None

    numeric_product = 1.0
    primitive_indices = [
        j for j in range(1, n_val + 1) if math.gcd(j, n_val) == 1
    ]
    for j in primitive_indices:
        root = complex(
            math.cos(2 * math.pi * j / n_val),
            math.sin(2 * math.pi * j / n_val),
        )
        numeric_product *= abs(a - root)
    if abs(numeric_product - norm) > 1e-7 * max(1, norm):
        return None
    factors, divisor_count = _factor_data(norm)

    return Problem(
        "ultradeep.cyclotomic_distance_norm_divisor_count",
        "complex_algebra_number_theory",
        "cyclotomic_polynomial+algebraic_norm+numeric_product",
        params,
        rf"\(\zeta_j=\cos\frac{{2\pi j}}{{{n_val}}}+i\sin\frac{{2\pi j}}{{{n_val}}}\) "
        rf"とし，\(1\le j\le {n_val}\) かつ \(\gcd(j,{n_val})=1\) を満たす \(j\) "
        rf"について \(L=\prod |{a}-\zeta_j|\) と定める。\(L\) が整数であることを示し，"
        r"\(L\) の正の約数の個数を求めよ。",
        str(divisor_count),
        str(divisor_count),
        rf"積に現れるのは原始 \({n_val}\) 乗根だから，"
        rf"\(\prod({a}-\zeta_j)=\Phi_{{{n_val}}}({a})={norm}\)。共役が対になるので"
        rf"絶対値の積も \(L={norm}\)。\(L={_factor_tex(factors)}\) より，"
        rf"正の約数は \({divisor_count}\) 個。",
        (
            "RootOfUnity",
            "CoprimeIndexFilter",
            "PrimitiveRootSet",
            "DistanceMultiset",
            "DistanceProduct",
            "CyclotomicPolynomial",
            "PolynomialEvaluation",
            "AlgebraicNorm",
            "IntegerInvariant",
            "PrimeFactorization",
            "DivisorCount",
        ),
        True,
        True,
        "cyclotomic_evaluation_vs_numeric_primitive_root_product",
    )


def _grid_ultradeep_cyclotomic_norm() -> Iterable[dict[str, Any]]:
    for n_val in (5, 7, 8, 9, 10, 12, 14, 15, 16, 18, 20, 24, 30):
        for a in (2, 3, 4):
            yield {"n": n_val, "a": a}


@lru_cache(maxsize=None)
def _gambler_moments(n_val: int) -> tuple[tuple[sp.Rational, ...], tuple[sp.Rational, ...]]:
    size = n_val - 1
    operator = sp.zeros(size)
    for row in range(size):
        operator[row, row] = 1
        if row > 0:
            operator[row, row - 1] = -sp.Rational(1, 2)
        if row + 1 < size:
            operator[row, row + 1] = -sp.Rational(1, 2)
    first = operator.LUsolve(sp.ones(size, 1))
    second_rhs = sp.zeros(size, 1)
    for row in range(size):
        left = first[row - 1] if row > 0 else 0
        right = first[row + 1] if row + 1 < size else 0
        second_rhs[row] = 1 + left + right
    second = operator.LUsolve(second_rhs)
    return tuple(first), tuple(second)


def _ultradeep_gambler_variance_divisors(
    params: dict[str, Any],
) -> Problem | None:
    """吸収時間の一・二次モーメントから分散を作り約数関数まで送る(12射)。"""
    n_val, start = int(params["N"]), int(params["k"])
    if not (1 <= start < n_val):
        return None
    variance = (
        start
        * (n_val - start)
        * (n_val * n_val - 2 - 2 * start * (n_val - start))
        // 3
    )
    if variance <= 0:
        return None

    first, second = _gambler_moments(n_val)
    independent = sp.simplify(second[start - 1] - first[start - 1] ** 2)
    if independent != variance:
        return None
    factors, divisor_count = _factor_data(variance)

    return Problem(
        "ultradeep.gambler_absorption_variance_divisor_count",
        "probability_linear_algebra_number_theory",
        "absorbing_markov_moments+linear_system+factorization",
        params,
        rf"点 \(0,1,\ldots,{n_val}\) 上を動く対称ランダムウォークを考える。"
        rf"初期位置は \({start}\) で，各時刻に確率 \(\frac12\) ずつで左右に1動き，"
        rf"\(0\) または \({n_val}\) に着いたら停止する。停止時刻を \(T\) とするとき，"
        r"\(\operatorname{Var}(T)\) の正の約数の個数を求めよ。",
        str(divisor_count),
        str(divisor_count),
        rf"一次モーメントの差分方程式から \(E[T]={start}({n_val}-{start})\)。"
        rf"二次モーメントにも条件付けして解くと "
        rf"\(\operatorname{{Var}}(T)=\frac{{{start}({n_val}-{start})"
        rf"({n_val}^2-2-2\cdot {start}({n_val}-{start}))}}{{3}}={variance}\)。"
        rf"\({variance}={_factor_tex(factors)}\) より約数は \({divisor_count}\) 個。",
        (
            "PathStateSpace",
            "AbsorbingBoundary",
            "SymmetricRandomWalk",
            "HittingTime",
            "FirstMomentConditioning",
            "FirstMomentLinearSystem",
            "SecondMomentConditioning",
            "SecondMomentLinearSystem",
            "VarianceTransform",
            "IntegerInvariant",
            "PrimeFactorization",
            "DivisorCount",
        ),
        True,
        True,
        "closed_variance_formula_vs_exact_two_moment_linear_system",
    )


def _grid_ultradeep_gambler_variance() -> Iterable[dict[str, Any]]:
    for n_val in range(4, 15):
        for start in range(1, n_val // 2 + 1):
            yield {"N": n_val, "k": start}


def _ultradeep_cubic_triangle_divisors(
    params: dict[str, Any],
) -> Problem | None:
    """三次根を放物線へ移し、面積・判別式・整数論を合成する(11射)。"""
    a, t_val = int(params["a"]), int(params["t"])
    x = sp.symbols("x", real=True)
    polynomial = x**3 - 3 * a * a * x + t_val
    discriminant = int(sp.discriminant(polynomial, x))
    normalized = discriminant // 27
    if discriminant <= 0 or discriminant % 27 != 0 or normalized <= 1:
        return None

    roots = sorted(
        (complex(value) for value in sp.nroots(polynomial)),
        key=lambda value: value.real,
    )
    if any(abs(value.imag) > 1e-9 for value in roots):
        return None
    real_roots = [value.real for value in roots]
    r1, r2, r3 = real_roots
    twice_area = abs(
        (r2 - r1) * (r3 * r3 - r1 * r1)
        - (r3 - r1) * (r2 * r2 - r1 * r1)
    )
    numeric_normalized = twice_area * twice_area / 27
    if abs(numeric_normalized - normalized) > 1e-6 * normalized:
        return None
    factors, divisor_count = _factor_data(normalized)

    return Problem(
        "ultradeep.cubic_root_triangle_discriminant_divisor_count",
        "algebraic_geometry_number_theory",
        "cubic_discriminant+vandermonde_area+numeric_roots",
        params,
        rf"方程式 \(x^3-{3 * a * a}x+({t_val})=0\) の3実根を "
        r"\(\alpha,\beta,\gamma\) とする。放物線 \(y=x^2\) 上の3点 "
        r"\((\alpha,\alpha^2),(\beta,\beta^2),(\gamma,\gamma^2)\) が作る"
        r"三角形の面積を \(S\) とし，\(M=\frac{4S^2}{27}\) と定める。"
        r"\(M\) が整数であることを示し，\(M\) の正の約数の個数を求めよ。",
        str(divisor_count),
        str(divisor_count),
        rf"Vandermonde 行列式から \(4S^2\) は三次式の判別式に等しい。"
        rf"判別式は \(27(4\cdot {a}^6-({t_val})^2)=27\cdot {normalized}\) "
        rf"だから \(M={normalized}={_factor_tex(factors)}\)。したがって"
        rf"正の約数は \({divisor_count}\) 個。",
        (
            "CubicPolynomial",
            "ThreeRealRootSet",
            "ParabolaEmbedding",
            "TriangleConstruction",
            "VandermondeDeterminant",
            "AreaSquare",
            "PolynomialDiscriminant",
            "IntegerNormalization",
            "PrimeFactorization",
            "DivisorCount",
            "ArithmeticObservation",
        ),
        True,
        True,
        "symbolic_discriminant_identity_vs_numeric_root_triangle_area",
    )


def _grid_ultradeep_cubic_triangle() -> Iterable[dict[str, Any]]:
    for a in (2, 3, 4):
        for t_val in (-a**3, -(a * a), -1, 0, 1, a * a, a**3):
            yield {"a": a, "t": t_val}


DEEP_FAMILIES: tuple[
    tuple[Callable[[dict[str, Any]], "Problem | None"], Callable[[], Iterable[dict[str, Any]]]], ...
] = (
    (_deep_paley_spectrum, _grid_deep_paley),
    (_deep_tangent_growth, _grid_deep_tangent),
    (_deep_rotation_divisors, _grid_deep_rotation),
    (_deep_recurrence_qr, _grid_deep_recurrence),
    (_deep_centroid_subsets, _grid_deep_centroid),
    (_ultradeep_paley_tree_divisors, _grid_ultradeep_paley_tree),
    (_ultradeep_paley_four_cycle_divisors, _grid_ultradeep_paley_four_cycles),
    (_ultradeep_cyclotomic_norm_divisors, _grid_ultradeep_cyclotomic_norm),
    (_ultradeep_gambler_variance_divisors, _grid_ultradeep_gambler_variance),
    (_ultradeep_cubic_triangle_divisors, _grid_ultradeep_cubic_triangle),
)
