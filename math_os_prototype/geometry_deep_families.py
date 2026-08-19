"""10段の射を持つ幾何作問族。

包絡線、双対円錐曲線、発展曲線、直交中心、Minkowski和を、それぞれ
異なる観測量へ送る。閉形式と独立な数値・記号計算が一致した問題だけ返す。
"""

from __future__ import annotations

import math
from typing import Any, Callable, Iterable

import sympy as sp

try:
    from math_os_prototype.construct_engine import Problem
except ImportError:  # pragma: no cover
    from construct_engine import Problem


def _shoelace_area(points: list[tuple[float, float]]) -> float:
    return abs(
        sum(
            x1 * y2 - y1 * x2
            for (x1, y1), (x2, y2) in zip(points, points[1:] + points[:1])
        )
    ) / 2


def _convex_hull(
    points: list[tuple[float, float]],
) -> list[tuple[float, float]]:
    unique = sorted(set(points))
    if len(unique) <= 1:
        return unique

    def cross(
        origin: tuple[float, float],
        left: tuple[float, float],
        right: tuple[float, float],
    ) -> float:
        return (
            (left[0] - origin[0]) * (right[1] - origin[1])
            - (left[1] - origin[1]) * (right[0] - origin[0])
        )

    lower: list[tuple[float, float]] = []
    for point in unique:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], point) <= 1e-10:
            lower.pop()
        lower.append(point)
    upper: list[tuple[float, float]] = []
    for point in reversed(unique):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], point) <= 1e-10:
            upper.pop()
        upper.append(point)
    return lower[:-1] + upper[:-1]


def _geometry_astroid_envelope(params: dict[str, Any]) -> Problem | None:
    a, b = int(params["a"]), int(params["b"])
    if a <= 0 or b <= 0:
        return None

    exact_area = sp.Rational(3, 8) * sp.pi * a * b
    sample_count = 4096
    boundary = [
        (
            a * math.cos(2 * math.pi * index / sample_count) ** 3,
            b * math.sin(2 * math.pi * index / sample_count) ** 3,
        )
        for index in range(sample_count)
    ]
    numeric_area = _shoelace_area(boundary)
    if abs(numeric_area - float(exact_area)) > 2e-5 * float(exact_area):
        return None

    return Problem(
        "ultradeep.geometry_astroid_envelope_area",
        "analytic_geometry",
        "line_envelope+stationarity+numeric_shoelace",
        params,
        rf"\(0<\theta<\frac{{\pi}}{{2}}\) に対し，点 "
        rf"\(A_\theta=({a}\cos\theta,0)\), "
        rf"\(B_\theta=(0,{b}\sin\theta)\) をとる。直線 "
        rf"\(A_\theta B_\theta\) を対称性により全象限へ拡張して得られる"
        r"直線族の包絡線が囲む面積を求めよ。",
        sp.latex(exact_area),
        sp.sstr(exact_area),
        rf"直線族を \(F=\frac{{x}}{{{a}\cos\theta}}+"
        rf"\frac{{y}}{{{b}\sin\theta}}-1=0\) とする。"
        r"\(F=F_\theta=0\) から "
        rf"\(x={a}\cos^3\theta,\ y={b}\sin^3\theta\)。"
        r"したがって包絡線はアステロイドであり，Greenの公式より "
        rf"\(\frac12\oint(x\,dy-y\,dx)={sp.latex(exact_area)}\)。",
        (
            "CircleParameter",
            "AxisEndpointPair",
            "JoiningLine",
            "LineFamily",
            "EnvelopeStationarity",
            "ParameterElimination",
            "AstroidIdentification",
            "ClosedCurveOrientation",
            "GreenAreaMorphism",
            "AreaObservation",
        ),
        True,
        True,
        "symbolic_envelope_conditions_vs_numeric_shoelace",
    )


def _grid_geometry_astroid() -> Iterable[dict[str, Any]]:
    for a in range(2, 9):
        for b in range(2, 9):
            yield {"a": a, "b": b}


def _geometry_ellipse_tangent_pair(params: dict[str, Any]) -> Problem | None:
    a, b, k = int(params["a"]), int(params["b"]), int(params["k"])
    if not (a > b > 0 and k >= 3):
        return None

    delta = math.pi / k
    scale = 1 / math.cos(delta)
    for index in range(24):
        t = 2 * math.pi * index / 24 + 0.013
        matrix = sp.Matrix(
            [
                [math.cos(t + delta) / a, math.sin(t + delta) / b],
                [math.cos(t - delta) / a, math.sin(t - delta) / b],
            ]
        )
        point = matrix.inv() * sp.ones(2, 1)
        expected = (a * scale * math.cos(t), b * scale * math.sin(t))
        if max(abs(float(point[i]) - expected[i]) for i in range(2)) > 1e-8:
            return None

    rhs = sp.sec(sp.pi / k) ** 2
    return Problem(
        "ultradeep.geometry_ellipse_tangent_pair_locus",
        "projective_geometry",
        "dual_conic+tangent_intersection+linear_system",
        params,
        rf"楕円 \(E:\frac{{x^2}}{{{a * a}}}+\frac{{y^2}}{{{b * b}}}=1\) "
        rf"上の点を \(P(t)=({a}\cos t,{b}\sin t)\) とする。"
        rf"\(P(t+\frac{{\pi}}{{{k}}})\) と "
        rf"\(P(t-\frac{{\pi}}{{{k}}})\) における2本の接線の交点を \(Q(t)\)"
        r"とするとき，\(Q(t)\) の軌跡の方程式を求めよ。",
        rf"\frac{{x^2}}{{{a * a}}}+\frac{{y^2}}{{{b * b}}}"
        rf"={sp.latex(rhs)}",
        sp.sstr(rhs),
        rf"2本の接線の方程式を加減して解くと "
        rf"\(Q(t)=({a}\sec\frac{{\pi}}{{{k}}}\cos t,"
        rf"{b}\sec\frac{{\pi}}{{{k}}}\sin t)\)。よって軌跡は "
        rf"\(\frac{{x^2}}{{{a * a}}}+\frac{{y^2}}{{{b * b}}}"
        rf"={sp.latex(rhs)}\)。",
        (
            "EllipseObject",
            "TrigonometricChart",
            "PairedParameterShift",
            "TangentDualization",
            "DualLinePair",
            "LinearIntersection",
            "TrigonometricDiagonalization",
            "HomothetyRecognition",
            "ConicElimination",
            "LocusEquationObservation",
        ),
        True,
        True,
        "closed_intersection_formula_vs_numeric_two_line_solve",
    )


def _grid_geometry_ellipse_tangent_pair() -> Iterable[dict[str, Any]]:
    for a in range(2, 7):
        for b in range(1, a):
            for k in range(3, 9):
                yield {"a": a, "b": b, "k": k}


def _geometry_parabola_normal_envelope(params: dict[str, Any]) -> Problem | None:
    a = int(params["a"])
    if a <= 0:
        return None

    t, x, y = sp.symbols("t x y")
    family = x + t * y - 2 * a * t - a * t**3
    stationary = sp.diff(family, t)
    resultant = sp.factor(sp.resultant(family, stationary, t))
    implicit = sp.expand(4 * (y - 2 * a) ** 3 - 27 * a * x**2)
    if sp.simplify(resultant - a**2 * implicit) != 0:
        return None
    for value in (-3, -2, -1, 0, 1, 2, 3):
        px = -2 * a * value**3
        py = 2 * a + 3 * a * value**2
        if implicit.subs({x: px, y: py}) != 0:
            return None

    return Problem(
        "ultradeep.geometry_parabola_normal_envelope",
        "differential_geometry",
        "normal_family+resultant+evolute",
        params,
        rf"放物線 \(C:y=\frac{{x^2}}{{{4 * a}}}\) 上の各点で法線を引く。"
        r"この法線族の包絡線の方程式を求めよ。",
        rf"4(y-{2 * a})^3={27 * a}x^2",
        sp.sstr(implicit),
        rf"\(C\) を \(P(t)=({2 * a}t,{a}t^2)\) と表示する。法線族は "
        rf"\(F=x+ty-{2 * a}t-{a}t^3=0\)。"
        r"\(F=F_t=0\) から "
        rf"\(x=-{2 * a}t^3,\ y={2 * a}+{3 * a}t^2\)。"
        rf"消去すると \(4(y-{2 * a})^3={27 * a}x^2\)。",
        (
            "ParabolaObject",
            "TangentVector",
            "NormalDirection",
            "NormalLine",
            "NormalLineFamily",
            "EnvelopeStationarity",
            "StationaryParameterSolve",
            "EvoluteParametrization",
            "ResultantElimination",
            "ImplicitCurveObservation",
        ),
        True,
        True,
        "symbolic_resultant_identity_vs_parametric_substitution",
    )


def _grid_geometry_parabola_normal() -> Iterable[dict[str, Any]]:
    for a in range(1, 31):
        yield {"a": a}


def _geometry_orthocenter_locus(params: dict[str, Any]) -> Problem | None:
    a, b = int(params["a"]), int(params["b"])
    if not (a > b > 0):
        return None

    exact_area = sp.pi * sp.Rational(a**3, b)
    sample_count = 4096
    locus: list[tuple[float, float]] = []
    for index in range(sample_count):
        t = 2 * math.pi * (index + 0.25) / sample_count
        px, py = a * math.cos(t), b * math.sin(t)
        hx = px
        hy = (a * a - px * px) / py
        locus.append((hx, hy))
    numeric_area = _shoelace_area(locus)
    if abs(numeric_area - float(exact_area)) > 2e-5 * float(exact_area):
        return None

    return Problem(
        "ultradeep.geometry_orthocenter_locus_area",
        "euclidean_geometry",
        "orthocenter+linear_image+numeric_shoelace",
        params,
        rf"楕円 \(E:\frac{{x^2}}{{{a * a}}}+\frac{{y^2}}{{{b * b}}}=1\) "
        rf"の長軸の端点を \(A=(-{a},0),B=({a},0)\) とする。"
        r"\(E\) 上を動く点 \(P\ne A,B\) に対し，三角形 \(ABP\) の"
        r"垂心を \(H\) とする。\(H\) の軌跡が囲む面積を求めよ。",
        sp.latex(exact_area),
        sp.sstr(exact_area),
        rf"\(P=({a}\cos t,{b}\sin t)\) とおく。\(AB\) が水平なので"
        rf"垂心の \(x\) 座標は \({a}\cos t\)。もう1本の高さから "
        rf"\(H=({a}\cos t,\frac{{{a * a}}}{{{b}}}\sin t)\)。"
        rf"したがって軌跡は半軸 \({a},\frac{{{a * a}}}{{{b}}}\) の楕円で，"
        rf"面積は \({sp.latex(exact_area)}\)。",
        (
            "EllipseObject",
            "MajorAxisVertexPair",
            "MovingTriangle",
            "AltitudeConstraint",
            "OrthocenterIntersection",
            "CoordinateSolve",
            "LinearImageRecognition",
            "ImageEllipse",
            "DeterminantAreaScaling",
            "AreaObservation",
        ),
        True,
        True,
        "altitude_coordinate_formula_vs_numeric_locus_shoelace",
    )


def _grid_geometry_orthocenter() -> Iterable[dict[str, Any]]:
    for a in range(2, 10):
        for b in range(1, a):
            yield {"a": a, "b": b}


def _geometry_minkowski_polygon(params: dict[str, Any]) -> Problem | None:
    n, radius = int(params["n"]), int(params["R"])
    if n < 3 or radius <= 0:
        return None

    polygon = [
        (
            radius * math.cos(2 * math.pi * index / n),
            radius * math.sin(2 * math.pi * index / n),
        )
        for index in range(n)
    ]
    rotated = [
        (
            radius * math.cos(2 * math.pi * index / n + math.pi / n),
            radius * math.sin(2 * math.pi * index / n + math.pi / n),
        )
        for index in range(n)
    ]
    hull = _convex_hull(
        [(x1 + x2, y1 + y2) for x1, y1 in polygon for x2, y2 in rotated]
    )
    numeric_perimeter = sum(
        math.hypot(x2 - x1, y2 - y1)
        for (x1, y1), (x2, y2) in zip(hull, hull[1:] + hull[:1])
    )
    exact_perimeter = 4 * n * radius * sp.sin(sp.pi / n)
    if len(hull) != 2 * n:
        return None
    if abs(numeric_perimeter - float(exact_perimeter)) > 1e-8:
        return None

    return Problem(
        "ultradeep.geometry_regular_polygon_minkowski_perimeter",
        "convex_geometry",
        "minkowski_sum+support_faces+convex_hull",
        params,
        rf"同じ中心・外接円半径 \({radius}\) の正 \({n}\) 角形 \(P,Q\) があり，"
        rf"\(Q\) は \(P\) を中心のまわりに \(\frac{{\pi}}{{{n}}}\) 回転したもの"
        r"とする。Minkowski和 \(P+Q=\{p+q\mid p\in P,q\in Q\}\) の周長を求めよ。",
        sp.latex(exact_perimeter),
        sp.sstr(exact_perimeter),
        rf"両多角形の辺の法線方向は交互に現れるため，\(P+Q\) は正 \({2 * n}\)"
        rf"角形になる。隣接頂点間の距離は \(2\cdot {radius}"
        rf"\sin\frac{{\pi}}{{{n}}}\)。したがって周長は "
        rf"\({2 * n}\cdot2\cdot {radius}\sin\frac{{\pi}}{{{n}}}"
        rf"={sp.latex(exact_perimeter)}\)。",
        (
            "RootOfUnityChart",
            "RegularPolygon",
            "HalfStepRotation",
            "SecondRegularPolygon",
            "MinkowskiAddition",
            "SupportDirectionMerge",
            "VertexSumHull",
            "RegularDoublePolygon",
            "EdgeLengthObservation",
            "PerimeterObservation",
        ),
        True,
        True,
        "regular_polygon_formula_vs_all_vertex_sums_convex_hull",
    )


def _grid_geometry_minkowski() -> Iterable[dict[str, Any]]:
    for n in range(3, 13):
        for radius in range(1, 7):
            yield {"n": n, "R": radius}


def _geometry_triangle_displacement_locus(params: dict[str, Any]) -> Problem | None:
    """A triangle's difference body, surfaced as a moving-vector locus."""
    a, u, v = 4, 1, 3
    triangle = [(0.0, 0.0), (float(a), 0.0), (float(u), float(v))]
    difference_hull = _convex_hull(
        [(qx - px, qy - py) for px, py in triangle for qx, qy in triangle]
    )
    triangle_area = _shoelace_area(triangle)
    locus_area = _shoelace_area(difference_hull)
    if len(difference_hull) != 6 or abs(locus_area - 6 * triangle_area) > 1e-10:
        return None

    return Problem(
        "ultradeep.geometry_triangle_displacement_locus_area",
        "convex_geometry",
        "difference_body+convex_hull+shoelace",
        {"symbolic_area": "S", "verification_triangle": [a, u, v]},
        r"面積が \(S\) である三角形 \(T\) の内部または周上を2点 \(P,Q\) が"
        r"独立に動く。ベクトル \(\overrightarrow{PQ}\) を、その成分を座標とする"
        r"平面上の点とみなすとき、この点の通過領域の面積を \(S\) で表せ。",
        r"6S",
        "6*S",
        r"三角形を \(A=(0,0),B=\mathbf b,C=\mathbf c\) とおく。変位全体は "
        r"\(T-T=\{Q-P\mid P,Q\in T\}\) であり、その頂点は "
        r"\(\pm\mathbf b,\pm\mathbf c,\pm(\mathbf b-\mathbf c)\) の6点である。"
        r"この中心対称六角形を3本の対角線で分けるか靴紐公式を用いると、"
        r"面積は \(6[ABC]=6S\) となる。",
        (
            "TriangleConfiguration",
            "IndependentPointPair",
            "DisplacementMap",
            "DifferenceBody",
            "VertexDifferenceSet",
            "ConvexHull",
            "CentralSymmetry",
            "HexagonRecognition",
            "AffineNormalization",
            "AreaObservation",
        ),
        True,
        True,
        "symbolic_difference_body_identity_vs_numeric_convex_hull",
    )


def _grid_geometry_triangle_displacement() -> Iterable[dict[str, Any]]:
    yield {"symbolic": True}


def _geometry_polygon_disk_sweep(params: dict[str, Any]) -> Problem | None:
    """Steiner's polygon formula, surfaced as a disk passage region."""
    width, height, radius = 3.0, 2.0, 1.0
    polygon = [(0.0, 0.0), (width, 0.0), (width, height), (0.0, height)]
    samples = 1024
    circle = [
        (radius * math.cos(2 * math.pi * index / samples),
         radius * math.sin(2 * math.pi * index / samples))
        for index in range(samples)
    ]
    hull = _convex_hull(
        [(px + cx, py + cy) for px, py in polygon for cx, cy in circle]
    )
    numeric_area = _shoelace_area(hull)
    expected = width * height + radius * 2 * (width + height) + math.pi * radius**2
    if abs(numeric_area - expected) > 3e-5:
        return None

    return Problem(
        "ultradeep.geometry_convex_polygon_disk_sweep_area",
        "convex_geometry",
        "minkowski_sum+parallel_body+numeric_hull",
        {"symbolic": ["A", "L", "r"], "verification_rectangle": [3, 2, 1]},
        r"面積 \(A\)、周長 \(L\) の凸多角形 \(P\) 上を、半径 \(r\) の円板の"
        r"中心が自由に動く。この円板が通過する領域の面積を \(A,L,r\) で表せ。",
        r"A+rL+\pi r^2",
        "A + r*L + pi*r**2",
        r"通過領域は多角形 \(P\) と半径 \(r\) の円板とのMinkowski和である。"
        r"元の \(P\) に加え、各辺の外側に面積 \(r\ell_i\) の長方形ができる。"
        r"各頂点にできる扇形の中心角の和は \(2\pi\) なので、その面積の和は"
        r"\(\pi r^2\)。したがって \(A+r\sum_i\ell_i+\pi r^2"
        r"=A+rL+\pi r^2\) である。",
        (
            "ConvexPolygon",
            "MovingCenter",
            "DiskTranslation",
            "PassageUnion",
            "MinkowskiAddition",
            "ParallelBody",
            "EdgeStripDecomposition",
            "ExteriorAngleSum",
            "SectorAreaMerge",
            "AreaObservation",
        ),
        True,
        True,
        "polygon_parallel_body_decomposition_vs_sampled_minkowski_hull",
    )


def _grid_geometry_polygon_disk_sweep() -> Iterable[dict[str, Any]]:
    yield {"symbolic": True}


def _geometry_tetrahedron_displacement_locus(
    params: dict[str, Any],
) -> Problem | None:
    """The three-dimensional difference body of a tetrahedron."""
    try:
        import numpy as np
        from scipy.spatial import ConvexHull
    except ImportError:  # pragma: no cover - CI installs scipy
        return None

    vertices = np.array(
        [
            [0.0, 0.0, 0.0],
            [1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0],
            [0.0, 0.0, 1.0],
        ]
    )
    differences = np.array([q - p for p in vertices for q in vertices])
    locus_volume = float(ConvexHull(differences).volume)
    tetrahedron_volume = 1.0 / 6.0
    if abs(locus_volume / tetrahedron_volume - 20.0) > 1e-9:
        return None

    return Problem(
        "ultradeep.spatial_tetrahedron_displacement_locus_volume",
        "euclidean_geometry",
        "difference_body+orthant_decomposition+numeric_convex_hull_3d",
        {"symbolic_volume": "V", "verification_simplex": "unit"},
        r"体積が \(V\) である四面体 \(T\) の内部または表面を2点 \(P,Q\) が"
        r"独立に動く。ベクトル \(\overrightarrow{PQ}\) の3成分を空間内の点の"
        r"座標とみなすとき、この点の通過領域の体積を \(V\) で表せ。",
        r"20V",
        "20*V",
        r"アフィン変換で \(T=\{(x,y,z)\mid x,y,z\ge0,\ x+y+z\le1\}\) "
        r"としてよい。変位 \(u=Q-P\) 全体は、正の成分の和と負の成分の"
        r"絶対値の和がともに1以下となる領域である。符号が正の座標を \(k\) 個"
        r"指定した部分の体積は \(1/(k!(3-k)!)\)。したがって全体の体積は "
        r"\(\sum_{k=0}^3\binom3k/(k!(3-k)!)=10/3\)。標準四面体の体積は"
        r" \(1/6\) なので比は20であり、一般の四面体でもアフィン変換で"
        r"同じ比が保たれる。よって答は \(20V\)。",
        (
            "TetrahedronConfiguration",
            "IndependentPointPair",
            "SpatialDisplacementMap",
            "ThreeDimensionalDifferenceBody",
            "AffineSimplexNormalization",
            "CoordinateSignPartition",
            "PositiveNegativeMassConstraints",
            "OrthantSimplexDecomposition",
            "BinomialVolumeMerge",
            "AffineVolumeScaling",
            "VolumeObservation",
        ),
        True,
        True,
        "orthant_simplex_volume_identity_vs_scipy_convex_hull_3d",
    )


def _grid_geometry_tetrahedron_displacement() -> Iterable[dict[str, Any]]:
    yield {"symbolic": True}


def _cube_section_area(t: float) -> float:
    """Area of [0,1]^3 cut by x+y+z=t, computed from edge intersections."""
    cube = [
        (float(x), float(y), float(z))
        for x in (0, 1)
        for y in (0, 1)
        for z in (0, 1)
    ]
    points: list[tuple[float, float, float]] = []
    for left_index, left in enumerate(cube):
        for right in cube[left_index + 1:]:
            if sum(a != b for a, b in zip(left, right)) != 1:
                continue
            left_level, right_level = sum(left), sum(right)
            if (left_level - t) * (right_level - t) > 0:
                continue
            if abs(right_level - left_level) < 1e-12:
                continue
            ratio = (t - left_level) / (right_level - left_level)
            if -1e-12 <= ratio <= 1 + 1e-12:
                points.append(tuple(a + ratio * (b - a) for a, b in zip(left, right)))
    unique = list(dict.fromkeys(tuple(round(value, 12) for value in p) for p in points))
    u = (1 / math.sqrt(2), -1 / math.sqrt(2), 0.0)
    v = (1 / math.sqrt(6), 1 / math.sqrt(6), -2 / math.sqrt(6))
    projected = [
        (
            sum(point[index] * u[index] for index in range(3)),
            sum(point[index] * v[index] for index in range(3)),
        )
        for point in unique
    ]
    return _shoelace_area(_convex_hull(projected)) if len(projected) >= 3 else 0.0


def _geometry_cube_diagonal_section_maximum(
    params: dict[str, Any],
) -> Problem | None:
    sample_levels = [index / 100 for index in range(1, 300)]
    sampled_areas = [_cube_section_area(level) for level in sample_levels]
    maximum_index = max(range(len(sampled_areas)), key=sampled_areas.__getitem__)
    if abs(sample_levels[maximum_index] - 1.5) > 1e-12:
        return None
    if abs(sampled_areas[maximum_index] - 3 * math.sqrt(3) / 4) > 1e-9:
        return None

    return Problem(
        "ultradeep.spatial_cube_diagonal_section_maximum",
        "euclidean_geometry",
        "slice_volume_derivative+inclusion_exclusion+numeric_section_hull",
        {"symbolic_side": "a", "verification_side": 1},
        r"一辺 \(a\) の立方体を、3辺を座標軸に平行になるように "
        r"\(0\le x,y,z\le a\) と置く。平面 \(x+y+z=t\) で切った断面の"
        r"面積が最大となる \(t\) と、その最大面積を求めよ。",
        r"t=\frac{3a}{2},\qquad \frac{3\sqrt3}{4}a^2",
        "t=3*a/2; area=3*sqrt(3)*a**2/4",
        r"\(F(t)\) を立方体内で \(x+y+z\le t\) を満たす部分の体積とする。"
        r"断面に垂直な移動距離は \(dt/\sqrt3\) なので断面積は "
        r"\(\sqrt3F'(t)\)。対称性から \(0\le t\le3a/2\) だけ見ればよい。"
        r"\(0\le t\le a\) では \(F=t^3/6\)、\(a\le t\le3a/2\) では"
        r"包除原理により \(F=\{t^3-3(t-a)^3\}/6\)。後者の断面積は "
        r"\(\frac{\sqrt3}{2}\{t^2-3(t-a)^2\}\) で、\(t=3a/2\) まで"
        r"増加する。よって中央の正六角形断面で最大値 "
        r"\(3\sqrt3a^2/4\) をとる。",
        (
            "CubeConfiguration",
            "BodyDiagonalDirection",
            "ParallelPlaneFamily",
            "SublevelSolid",
            "SliceVolumeCorrespondence",
            "CoordinateSimplexVolume",
            "ThreeCornerExclusion",
            "InclusionExclusion",
            "PiecewiseQuadraticSectionArea",
            "CentralSymmetryReduction",
            "ExtremumObservation",
        ),
        True,
        True,
        "inclusion_exclusion_derivative_vs_edge_intersection_polygon_area",
    )


def _grid_geometry_cube_diagonal_section() -> Iterable[dict[str, Any]]:
    yield {"symbolic": True}


def _geometry_cube_ball_sweep(params: dict[str, Any]) -> Problem | None:
    try:
        import numpy as np
        from scipy.spatial import ConvexHull
    except ImportError:  # pragma: no cover - CI installs scipy
        return None

    samples = 4096
    sphere = []
    golden_angle = math.pi * (3 - math.sqrt(5))
    for index in range(samples):
        z = 1 - 2 * (index + 0.5) / samples
        radius = math.sqrt(max(0.0, 1 - z * z))
        angle = index * golden_angle
        sphere.append((radius * math.cos(angle), radius * math.sin(angle), z))
    cube = [(x, y, z) for x in (0.0, 1.0) for y in (0.0, 1.0) for z in (0.0, 1.0)]
    sums = np.array(
        [[x + u, y + v, z + w] for x, y, z in cube for u, v, w in sphere]
    )
    numeric_volume = float(ConvexHull(sums).volume)
    exact_unit_volume = 7 + 13 * math.pi / 3
    if abs(numeric_volume - exact_unit_volume) > 0.02:
        return None

    return Problem(
        "ultradeep.spatial_cube_ball_sweep_volume",
        "convex_geometry",
        "spatial_minkowski_sum+boundary_strata+sampled_convex_hull_3d",
        {"symbolic": ["a", "r"], "verification": [1, 1]},
        r"一辺 \(a\) の立方体の内部または表面を、半径 \(r\) の球の中心が"
        r"自由に動く。この球が通過する空間領域の体積を求めよ。",
        r"a^3+6a^2r+3\pi ar^2+\frac{4\pi}{3}r^3",
        "a**3 + 6*a**2*r + 3*pi*a*r**2 + 4*pi*r**3/3",
        r"通過領域は立方体と半径 \(r\) の球とのMinkowski和である。元の"
        r"立方体に、6面から生じる厚さ \(r\) の角柱、12辺から生じる"
        r"四分円柱、8頂点から生じる球の八分体を加える。それぞれの体積は"
        r" \(a^3,6a^2r,12\cdot\frac14\pi r^2a,"
        r"8\cdot\frac18\frac43\pi r^3\)。合計して答を得る。",
        (
            "CubeConfiguration",
            "MovingSphereCenter",
            "SpatialPassageUnion",
            "ThreeDimensionalMinkowskiAddition",
            "FaceEdgeVertexStratification",
            "FacePrismContribution",
            "QuarterCylinderEdgeContribution",
            "SphericalOctantVertexContribution",
            "DisjointBoundaryLayerMerge",
            "VolumeObservation",
        ),
        True,
        True,
        "boundary_stratum_decomposition_vs_sampled_sphere_minkowski_hull",
    )


def _grid_geometry_cube_ball_sweep() -> Iterable[dict[str, Any]]:
    yield {"symbolic": True}


GEOMETRY_DEEP_FAMILIES: tuple[
    tuple[
        Callable[[dict[str, Any]], Problem | None],
        Callable[[], Iterable[dict[str, Any]]],
    ],
    ...,
] = (
    (_geometry_astroid_envelope, _grid_geometry_astroid),
    (_geometry_ellipse_tangent_pair, _grid_geometry_ellipse_tangent_pair),
    (_geometry_parabola_normal_envelope, _grid_geometry_parabola_normal),
    (_geometry_orthocenter_locus, _grid_geometry_orthocenter),
    (_geometry_minkowski_polygon, _grid_geometry_minkowski),
    (_geometry_triangle_displacement_locus, _grid_geometry_triangle_displacement),
    (_geometry_polygon_disk_sweep, _grid_geometry_polygon_disk_sweep),
    (_geometry_tetrahedron_displacement_locus, _grid_geometry_tetrahedron_displacement),
    (_geometry_cube_diagonal_section_maximum, _grid_geometry_cube_diagonal_section),
    (_geometry_cube_ball_sweep, _grid_geometry_cube_ball_sweep),
)
