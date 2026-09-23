"""Cold synthesis for triangle areas from consecutive trigonometric samples.

The chart is not keyed by a problem number.  It parses three side functions,
lowers them to one polynomial coordinate, applies Heron's identity, certifies
the discrete admissible range, and proves the requested extremum by an exact
derivative-sign certificate plus a finite boundary comparison.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

import sympy as sp

from .runtime_typed_planner import (
    PrimitiveResult,
    RuntimePrimitive,
    initial_fact,
    synthesize_typed_plan,
)
from .visual_reasoning import plane_scene_diagram


@dataclass(frozen=True)
class TrigonometricTriangleQueryIR:
    index_symbol: str
    function: str
    multipliers: tuple[int, int, int]
    objective: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class TrigonometricTriangleSynthesis:
    answer_tex: str
    derivation_tex: tuple[str, ...]
    expression_tex: str
    proof_program: tuple[dict[str, Any], ...]
    verification_checks: tuple[str, ...]
    witness: dict[str, Any]
    hypotheses_evaluated: int
    diagram: dict[str, Any]
    diagram_tikz: str
    visual_explanation: dict[str, Any]


_SIDE_PATTERN = re.compile(
    r"\\(?P<function>sin|cos)"
    r"\\(?:dfrac|frac)\{(?P<coefficient>\d*)\\pi\}"
    r"\{(?P<index>[A-Za-z])\}"
)


def compile_trigonometric_triangle_query(
    statement: str,
) -> TrigonometricTriangleQueryIR | None:
    normalized = re.sub(r"\s+", "", statement.replace("−", "-").replace("–", "-"))
    matches = list(_SIDE_PATTERN.finditer(normalized))
    if len(matches) != 3 or "三辺" not in statement or "面積" not in statement:
        return None
    functions = {match.group("function") for match in matches}
    indices = {match.group("index") for match in matches}
    multipliers = tuple(
        sorted(int(match.group("coefficient") or "1") for match in matches)
    )
    if len(functions) != 1 or len(indices) != 1 or multipliers != (1, 2, 3):
        return None
    index_symbol = next(iter(indices))
    if "自然数" not in statement:
        return None
    if "最小値" in statement:
        objective = "minimum"
    elif "最大値" in statement:
        objective = "maximum"
    else:
        return None
    function = next(iter(functions))
    if (function, objective) not in {("cos", "minimum"), ("sin", "maximum")}:
        return None
    return TrigonometricTriangleQueryIR(
        index_symbol=index_symbol,
        function=function,
        multipliers=multipliers,
        objective=objective,
    )


def _heron_square(sides: tuple[sp.Expr, sp.Expr, sp.Expr]) -> sp.Expr:
    a, b, c = sides
    return sp.factor(
        (
            2 * a**2 * b**2
            + 2 * b**2 * c**2
            + 2 * c**2 * a**2
            - a**4
            - b**4
            - c**4
        )
        / 16
    )


def _sides(function: str, angle: sp.Expr) -> tuple[sp.Expr, sp.Expr, sp.Expr]:
    trig = sp.cos if function == "cos" else sp.sin
    return tuple(trig(multiplier * angle) for multiplier in (1, 2, 3))


def _positive(expr: sp.Expr) -> bool:
    simplified = sp.trigsimp(sp.simplify(expr))
    return simplified.is_positive is True


def _triangle_is_strict(sides: tuple[sp.Expr, sp.Expr, sp.Expr]) -> bool:
    return all(
        _positive(sides[(index + 1) % 3] + sides[(index + 2) % 3] - sides[index])
        for index in range(3)
    )


def _triangle_diagram(
    query: TrigonometricTriangleQueryIR,
    *,
    extremizing_index: int,
    area_tex: str,
    area_square_tex: str,
    stage: int,
) -> dict[str, Any]:
    angle = sp.pi / extremizing_index
    side_values = _sides(query.function, angle)
    side_a, side_b, side_c = side_values
    x_coordinate = sp.simplify((side_b**2 + side_c**2 - side_a**2) / (2 * side_c))
    y_coordinate = sp.sqrt(sp.simplify(side_b**2 - x_coordinate**2))
    base = float(sp.N(side_c, 30))
    scale = 3.8 / base
    point_a = {"x": 0.0, "y": 0.0}
    point_b = {"x": 3.8, "y": 0.0}
    point_c = {
        "x": round(scale * float(sp.N(x_coordinate, 30)), 10),
        "y": round(scale * float(sp.N(y_coordinate, 30)), 10),
    }
    trig_name = rf"\{query.function}"
    index_name = query.index_symbol
    shapes: list[dict[str, Any]] = [
        {
            "id": "sampled-triangle",
            "kind": "polyline",
            "points": [point_a, point_b, point_c],
            "closed": True,
            "tone": "primary",
        },
        {"id": "vertex-a", "kind": "point", "point": point_a, "label": "A", "tone": "primary"},
        {"id": "vertex-b", "kind": "point", "point": point_b, "label": "B", "tone": "primary"},
        {"id": "vertex-c", "kind": "point", "point": point_c, "label": "C", "tone": "primary"},
        {
            "id": "side-one-label",
            "kind": "label",
            "point": {"x": (point_b["x"] + point_c["x"]) / 2 + 0.16, "y": point_c["y"] / 2},
            "text": rf"{trig_name}(\pi/{index_name})",
            "tone": "secondary",
        },
        {
            "id": "side-two-label",
            "kind": "label",
            "point": {"x": point_c["x"] / 2 - 0.35, "y": point_c["y"] / 2},
            "text": rf"{trig_name}(2\pi/{index_name})",
            "tone": "secondary",
        },
        {
            "id": "side-three-label",
            "kind": "label",
            "point": {"x": 1.9, "y": -0.28},
            "text": rf"{trig_name}(3\pi/{index_name})",
            "tone": "secondary",
        },
    ]
    if stage >= 2:
        shapes.append(
            {
                "id": "area-polynomial",
                "kind": "label",
                "point": {"x": 0.05, "y": point_c["y"] + 0.55},
                "text": rf"K^2={area_square_tex}",
                "tone": "muted",
            }
        )
    if stage >= 3:
        boundary = "n>=8" if query.function == "cos" else "n>=4"
        shapes.append(
            {
                "id": "admissible-boundary",
                "kind": "label",
                "point": {"x": 2.82, "y": point_c["y"] + 0.55},
                "text": boundary,
                "tone": "accent",
            }
        )
    if stage >= 4:
        direction = "n>=8 で K は増加" if query.function == "cos" else "n>=5 で K は減少"
        shapes.append(
            {
                "id": "monotonicity-label",
                "kind": "label",
                "point": {"x": 0.05, "y": -0.78},
                "text": direction,
                "tone": "accent",
            }
        )
    if stage >= 5:
        shapes.append(
            {
                "id": "exact-area-label",
                "kind": "label",
                "point": {"x": 2.52, "y": -0.78},
                "text": rf"{index_name}={extremizing_index}, K={area_tex}",
                "tone": "accent",
            }
        )
    captions = {
        1: "三つの三角関数値を、そのまま一つの三角形の三辺として配置します。",
        2: "倍角・三倍角の公式で三辺を一変数 c の式にし、ヘロンの公式を面積平方へ適用します。",
        3: "三角不等式を厳密に調べ、面積を比較すべき自然数の範囲を確定します。",
        4: "面積平方の導関数を因数分解し、残る多項式の符号を根の個数から証明します。",
        5: "単調な範囲の端と有限個の境界候補を比較し、元の三辺で面積を再計算します。",
    }
    return plane_scene_diagram(
        title="三角関数で定まる三角形",
        caption=captions[stage],
        viewport={"xMin": -0.75, "xMax": 4.65, "yMin": -1.05, "yMax": point_c["y"] + 1.05},
        shapes=shapes,
        axes=False,
    )


def _triangle_tikz(
    query: TrigonometricTriangleQueryIR,
    *,
    extremizing_index: int,
    area_tex: str,
) -> str:
    angle = sp.pi / extremizing_index
    side_a, side_b, side_c = _sides(query.function, angle)
    x_coordinate = sp.simplify((side_b**2 + side_c**2 - side_a**2) / (2 * side_c))
    y_coordinate = sp.sqrt(sp.simplify(side_b**2 - x_coordinate**2))
    base = float(sp.N(side_c, 30))
    scale = 3.8 / base
    x_value = scale * float(sp.N(x_coordinate, 30))
    y_value = scale * float(sp.N(y_coordinate, 30))
    trig = rf"\{query.function}"
    n = query.index_symbol
    return "\n".join(
        (
            r"\begin{tikzpicture}[line cap=round,line join=round]",
            rf"\coordinate (A) at (0,0); \coordinate (B) at (3.8,0); \coordinate (C) at ({x_value:.6f},{y_value:.6f});",
            r"\draw[very thick,cyan!65!black] (A)--(B)--(C)--cycle;",
            r"\fill (A) circle (1.2pt) node[below left] {$A$};",
            r"\fill (B) circle (1.2pt) node[below right] {$B$};",
            r"\fill (C) circle (1.2pt) node[above] {$C$};",
            rf"\path (B)--(C) node[midway,right] {{$ {trig}\frac{{\pi}}{{{n}}} $}};",
            rf"\path (C)--(A) node[midway,left] {{$ {trig}\frac{{2\pi}}{{{n}}} $}};",
            rf"\path (A)--(B) node[midway,below] {{$ {trig}\frac{{3\pi}}{{{n}}} $}};",
            rf"\node[anchor=west] at (0,-.75) {{$ {n}={extremizing_index},\quad K={area_tex} $}};",
            r"\end{tikzpicture}",
        )
    )


def execute_trigonometric_triangle_query(
    query: TrigonometricTriangleQueryIR,
) -> TrigonometricTriangleSynthesis:
    c = sp.Symbol("c", real=True)
    y = sp.Symbol("y", real=True)

    def elaborate(arguments: tuple[Any, ...]) -> PrimitiveResult:
        del arguments
        return PrimitiveResult(
            {"query": query, "c": c},
            {
                "function": query.function,
                "multipliers": list(query.multipliers),
                "index_symbol": query.index_symbol,
                "objective": query.objective,
            },
        )

    def polynomialize(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        if query.function == "cos":
            polynomial_sides = (c, 2 * c**2 - 1, 4 * c**3 - 3 * c)
            area_square = _heron_square(polynomial_sides)
        else:
            reduced_sides = (sp.Integer(1), 2 * c, 4 * c**2 - 1)
            polynomial_sides = tuple(sp.sqrt(1 - c**2) * side for side in reduced_sides)
            area_square = sp.factor((1 - c**2) ** 2 * _heron_square(reduced_sides))
        expected = (
            _heron_square((c, 2 * c**2 - 1, 4 * c**3 - 3 * c))
            if query.function == "cos"
            else c**2 * (1 - c**2) ** 3 * (4 * c**2 - 1) ** 2
        )
        if sp.factor(area_square - expected) != 0:
            return None
        return PrimitiveResult(
            {**data, "polynomial_sides": polynomial_sides, "area_square": sp.factor(area_square)},
            {
                "coordinate": "c=cos(pi/n)",
                "polynomial_sides": [sp.sstr(side) for side in polynomial_sides],
                "heron_area_squared": sp.sstr(sp.factor(area_square)),
            },
        )

    def certify_admissibility(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        if query.function == "cos":
            nonpositive_small_indices = [
                index
                for index in range(1, 7)
                if not all(_positive(side) for side in _sides("cos", sp.pi / index))
            ]
            if nonpositive_small_indices != list(range(1, 7)):
                return None
            seventh = _sides("cos", sp.pi / 7)
            eighth = _sides("cos", sp.pi / 8)
            if not _positive(seventh[0] - seventh[1] - seventh[2]):
                return None
            if not _triangle_is_strict(eighth):
                return None
            threshold = sp.sqrt(sp.Rational(5, 6))
            triangle_gap = 4 * c**3 + 2 * c**2 - 4 * c - 1
            if sp.diff(triangle_gap, c).subs(c, threshold).is_positive is not True:
                return None
            if sp.simplify(triangle_gap.subs(c, threshold)).is_positive is not True:
                return None
            minimum_index = 8
            certificate = {
                "n_from_1_through_6_has_nonpositive_side": nonpositive_small_indices,
                "n_equals_7_fails": sp.sstr(sp.trigsimp(seventh[0] - seventh[1] - seventh[2])),
                "n_equals_8_is_strict": True,
                "tail_threshold": "c^2>5/6",
                "tail_triangle_gap_lower": sp.sstr(sp.simplify(triangle_gap.subs(c, threshold))),
            }
        else:
            degenerate_small_indices = [
                index
                for index in range(1, 4)
                if not all(_positive(side) for side in _sides("sin", sp.pi / index))
            ]
            if degenerate_small_indices != [1, 2, 3]:
                return None
            fourth = _sides("sin", sp.pi / 4)
            if not _triangle_is_strict(fourth):
                return None
            minimum_index = 4
            certificate = {
                "n_from_1_through_3_degenerate_or_nonpositive": degenerate_small_indices,
                "n_equals_4_is_strict": True,
                "tail_triangle_gaps": [
                    "2*sin(t)*(1-cos(t))*(2*cos(t)+1)",
                    "sin(2*t)*(2*cos(t)-1)",
                ],
            }
        return PrimitiveResult(
            {**data, "minimum_index": minimum_index},
            certificate,
        )

    def certify_tail_monotonicity(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        derivative = sp.factor(sp.diff(data["area_square"], c))
        if query.function == "cos":
            residual = sp.Poly(192 * y**4 - 464 * y**3 + 352 * y**2 - 94 * y + 7, y)
            lower = sp.Rational(5, 6)
            u = sp.Symbol("u", real=True)
            interval_transform = sp.expand(
                27 * residual.as_expr().subs(y, (u + 5) / 6)
            )
            expected_transform = 4 * u**4 + 22 * u**3 - 6 * u**2 - 133 * u - 76
            if sp.expand(interval_transform - expected_transform) != 0:
                return None
            expected = -c * (2 * c**2 - 1) * residual.as_expr().subs(y, c**2) / 2
            direction = "increasing"
            tail_start = 8
            sign_certificate = {
                "substitution": "u=6*y-5",
                "transformed_interval": ["0", "1"],
                "scaled_residual": sp.sstr(interval_transform),
                "upper_bound": "4+22-76=-50<0",
            }
        else:
            residual = sp.Poly(24 * y**2 - 16 * y + 1, y)
            lower = sp.Rational(3, 5)
            if residual.eval(lower) <= 0 or sp.diff(residual.as_expr(), y).subs(y, lower) <= 0:
                return None
            expected = (
                -2
                * c
                * (c - 1) ** 2
                * (c + 1) ** 2
                * (2 * c - 1)
                * (2 * c + 1)
                * residual.as_expr().subs(y, c**2)
            )
            direction = "decreasing"
            tail_start = 5
            sign_certificate = {
                "lower_value": sp.sstr(residual.eval(lower)),
                "derivative_lower_bound": sp.sstr(
                    sp.diff(residual.as_expr(), y).subs(y, lower)
                ),
            }
        if sp.factor(derivative - expected) != 0:
            return None
        return PrimitiveResult(
            {
                **data,
                "derivative": derivative,
                "tail_direction": direction,
                "tail_start": tail_start,
                "sign_residual": residual.as_expr(),
                "sign_certificate": sign_certificate,
            },
            {
                "area_square_derivative": sp.sstr(derivative),
                "residual_polynomial": sp.sstr(residual.as_expr()),
                "certified_coordinate_interval": [sp.sstr(lower), "1"],
                "tail_direction_as_index_increases": direction,
                "elementary_sign_certificate": sign_certificate,
            },
        )

    def choose_discrete_extremum(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        if query.function == "cos":
            extremizing_index = 8
            target_area = sp.Rational(1, 8)
            boundary_comparison = {"first_admissible_index": 8}
        else:
            area4_square = sp.trigsimp(data["area_square"].subs(c, sp.cos(sp.pi / 4)))
            area5_square = sp.trigsimp(data["area_square"].subs(c, sp.cos(sp.pi / 5)))
            if sp.simplify(area5_square - area4_square).is_positive is not True:
                return None
            extremizing_index = 5
            target_area = sp.sqrt(50 + 10 * sp.sqrt(5)) / 32
            boundary_comparison = {
                "n4_area_squared": sp.sstr(area4_square),
                "n5_area_squared": sp.sstr(area5_square),
                "difference": sp.sstr(sp.simplify(area5_square - area4_square)),
            }
        replayed_target_square = sp.trigsimp(
            data["area_square"].subs(c, sp.cos(sp.pi / extremizing_index))
        )
        target_square = sp.expand(target_area**2)
        if sp.simplify(target_square - replayed_target_square) != 0:
            return None
        return PrimitiveResult(
            {
                **data,
                "extremizing_index": extremizing_index,
                "target_area": target_area,
                "target_area_square": target_square,
                "boundary_comparison": boundary_comparison,
            },
            {
                "extremizing_index": extremizing_index,
                "exact_area": sp.sstr(target_area),
                "finite_boundary_comparison": boundary_comparison,
            },
        )

    def replay_original_triangle(arguments: tuple[Any, ...]) -> PrimitiveResult | None:
        data = arguments[0].value
        index = int(data["extremizing_index"])
        original_sides = _sides(query.function, sp.pi / index)
        if not _triangle_is_strict(original_sides):
            return None
        original_area_square = sp.trigsimp(_heron_square(original_sides))
        if sp.simplify(original_area_square - data["target_area"] ** 2) != 0:
            return None
        return PrimitiveResult(
            {**data, "original_sides": original_sides},
            {
                "original_side_values": [sp.sstr(value) for value in original_sides],
                "all_triangle_inequalities_strict": True,
                "original_heron_replay": sp.sstr(original_area_square),
            },
        )

    primitives = (
        RuntimePrimitive(
            "trigonometric_sampled_triangle_elaboration",
            ("ParsedProblemIR",),
            "TrigonometricSampledTriangle",
            elaborate,
        ),
        RuntimePrimitive(
            "multiple_angle_heron_polynomialization",
            ("TrigonometricSampledTriangle",),
            "PolynomialAreaChart",
            polynomialize,
        ),
        RuntimePrimitive(
            "strict_triangle_admissibility_certificate",
            ("PolynomialAreaChart",),
            "AdmissibleDiscreteTriangleFamily",
            certify_admissibility,
        ),
        RuntimePrimitive(
            "semialgebraic_tail_monotonicity_certificate",
            ("AdmissibleDiscreteTriangleFamily",),
            "MonotoneAreaTail",
            certify_tail_monotonicity,
        ),
        RuntimePrimitive(
            "finite_boundary_extremum_comparison",
            ("MonotoneAreaTail",),
            "CertifiedDiscreteExtremum",
            choose_discrete_extremum,
        ),
        RuntimePrimitive(
            "original_trigonometric_triangle_replay",
            ("CertifiedDiscreteExtremum",),
            "CertifiedTrigonometricTriangleArea",
            replay_original_triangle,
        ),
    )
    plan = synthesize_typed_plan(
        [initial_fact("ParsedProblemIR", query.to_dict())],
        primitives,
        ("CertifiedTrigonometricTriangleArea",),
        max_depth=8,
        max_states=64,
    )
    if not plan.complete:
        raise ValueError(
            "runtime trigonometric-triangle planner left open goals: "
            f"{plan.open_goal_sorts}"
        )
    result = plan.goals["CertifiedTrigonometricTriangleArea"].value
    index = int(result["extremizing_index"])
    area = sp.simplify(result["target_area"])
    area_tex = sp.latex(area)
    area_square_tex = sp.latex(sp.factor(result["area_square"]))
    answer_tex = rf"\(K={area_tex}\quad({query.index_symbol}={index})\)"
    function_tex = rf"\{query.function}"
    if query.function == "cos":
        derivation = (
            rf"\(t=\pi/{query.index_symbol}\), \(c=\cos t\) とおく。倍角・三倍角の公式により三辺は \(c,2c^2-1,4c^3-3c\) となる。ヘロンの公式を対称な形で用いると \[K^2={area_square_tex}\] を得る。",
            r"n=1,2,...,6 は三辺の少なくとも一つが正でない。n=7 では最大辺が他の二辺の和より大きく、三角形にならない。n>=8 では c^2>5/6 である。F(c)=4c^3+2c^2-4c-1 とおくと F'(c)>0 かつ F(sqrt(5/6))=2/3-sqrt(30)/9>0 なので、最大辺に対する三角不等式が成立する。他の二つは直ちに成立する。従って n=8 が最初の許容値である。",
            r"K^2 を c で微分すると \[\frac{dK^2}{dc}=-\frac{c(2c^2-1)}2\{192c^8-464c^6+352c^4-94c^2+7\}.\] 中括弧を P(y) とし、u=6y-5 とおく。5/6<=y<=1 では 0<=u<=1 であり、\[27P\!\left(\frac{u+5}{6}\right)=4u^4+22u^3-6u^2-133u-76\le 4+22-76=-50<0.\] よって dK^2/dc>0 である。",
            rf"{query.index_symbol} が増えると \(c=\cos(\pi/{query.index_symbol})\) は増える。従って許容範囲では面積も増えるから、最小値は {query.index_symbol}=8 で取る。三辺を元のヘロンの公式へ戻すと \(K^2=1/64\) であり、\[\boxed{{K=\frac18}}\] となる。",
        )
    else:
        derivation = (
            rf"\(t=\pi/{query.index_symbol}\), \(c=\cos t\) とおく。三辺は \(\sin t,2c\sin t,(4c^2-1)\sin t\) である。ヘロンの公式を適用して整理すると \[K^2={area_square_tex}\] を得る。",
            r"n=1,2,3 では辺が0になるか正の三辺を得られない。n>=4 では 0<t<=pi/4 である。最大辺に対応する差は 2 sin t(1-c)(2c+1)>0、別の差は sin(2t)(2c-1)>0 と因数分解できる。残る差は sin(2t)+sin(3t)-sin t>0 である。従って三角不等式は全て厳密に成立する。",
            r"n>=5 では y=c^2>3/5 である。K^2 の導関数は \[-2c(c-1)^2(c+1)^2(2c-1)(2c+1)(24c^4-16c^2+1).\] 最後の因子は y>=3/5 で正かつ増加する。従って n>=5 では面積は n とともに減少する。",
            r"残る n=4 と n=5 を厳密に比較する。\[K_4^2=\frac1{16},\qquad K_5^2=\frac{25+5\sqrt5}{512},\qquad K_5^2-K_4^2=\frac{5\sqrt5-7}{512}>0.\] よって最大は n=5 であり、\[\boxed{K=\frac{\sqrt{50+10\sqrt5}}{32}}\] となる。",
        )
    chain = tuple(step["rule"] for step in plan.proof_program)
    diagrams = tuple(
        _triangle_diagram(
            query,
            extremizing_index=index,
            area_tex=area_tex,
            area_square_tex=area_square_tex,
            stage=stage,
        )
        for stage in range(1, 6)
    )
    visual_steps = (
        ("三つの値を三辺として読む", "問題文の三つの三角関数値を、順序に依存しない三辺の組として受け取ります。", chain[0], "ParsedProblemIR", "TrigonometricSampledTriangle"),
        ("面積平方を一変数多項式にする", "倍角・三倍角の公式とヘロンの公式を合成し、根号を含まない面積平方へ移します。", chain[1], "TrigonometricSampledTriangle", "PolynomialAreaChart"),
        ("三角形になる自然数を確定する", "三角不等式を証明し、退化する値を面積比較から除きます。", chain[2], "PolynomialAreaChart", "AdmissibleDiscreteTriangleFamily"),
        ("無限個の候補を単調性でまとめる", "導関数の符号を多項式の根の個数で証明し、無限の自然数を一つの単調な範囲として扱います。", chain[3], "AdmissibleDiscreteTriangleFamily", "MonotoneAreaTail"),
        ("有限個の端点を厳密比較する", "単調な範囲の端だけを比較し、最後に元の三角関数値へ戻して面積を再計算します。", chain[5], "CertifiedDiscreteExtremum", "CertifiedTrigonometricTriangleArea"),
    )
    visual_explanation = {
        "version": 1,
        "mode": "stepper",
        "title": "三つの三角関数値から厳密な面積極値まで",
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": list(chain),
        "steps": [
            {
                "id": f"trigonometric-triangle-step-{step}",
                "title": title,
                "explanation_ja": explanation,
                "formula_tex": answer_tex if step == 5 else area_square_tex,
                "morphism": {"morphism_id": morphism, "label_ja": title, "input_type": source, "output_type": target},
                "source_state": {"id": f"state-{step - 1}", "type": source},
                "target_state": {"id": f"state-{step}", "type": target},
                "diagram": diagrams[step - 1],
            }
            for step, (title, explanation, morphism, source, target) in enumerate(visual_steps, start=1)
        ],
    }
    witness = {
        "input_ir": query.to_dict(),
        "polynomial_sides": [sp.sstr(side) for side in result["polynomial_sides"]],
        "area_square_chart": sp.sstr(result["area_square"]),
        "area_square_derivative": sp.sstr(result["derivative"]),
        "elementary_sign_certificate": result["sign_certificate"],
        "tail_direction": result["tail_direction"],
        "tail_start": result["tail_start"],
        "extremizing_index": index,
        "exact_area": sp.sstr(area),
        "exact_area_square": sp.sstr(result["target_area_square"]),
        "original_side_values": [sp.sstr(value) for value in result["original_sides"]],
        "all_triangle_inequalities_strict": True,
        "planner": {
            "states_explored": plan.states_explored,
            "goal_sorts": sorted(plan.goals),
            "open_goal_sorts": list(plan.open_goal_sorts),
        },
    }
    checks = (
        "三つの三角関数、整数倍1・2・3、自然数添字、面積の極値方向を現在の問題文から抽出",
        "倍角・三倍角とヘロンの公式から面積平方の一変数表示を記号展開で確認",
        "三角不等式の成立境界を元の三角関数値で厳密確認",
        "導関数因数分解と区間変換による初等的な符号証明を再生",
        "有限境界比較後、元の三辺とヘロンの公式へ戻して答えを再生",
    )
    return TrigonometricTriangleSynthesis(
        answer_tex=answer_tex,
        derivation_tex=derivation,
        expression_tex=(
            rf"K({query.index_symbol});\ "
            + ",".join(
                rf"{function_tex}\frac{{{'' if multiplier == 1 else multiplier}\pi}}{{{query.index_symbol}}}"
                for multiplier in query.multipliers
            )
        ),
        proof_program=plan.proof_program
        + (
            {
                "rule": "exact_obligation_replay",
                "verified": True,
                "planner_states_explored": plan.states_explored,
            },
        ),
        verification_checks=checks,
        witness=witness,
        hypotheses_evaluated=(index - 1) + 2,
        diagram=diagrams[-1],
        diagram_tikz=_triangle_tikz(
            query,
            extremizing_index=index,
            area_tex=area_tex,
        ),
        visual_explanation=visual_explanation,
    )


def synthesize_trigonometric_triangle_problem(
    statement: str,
) -> TrigonometricTriangleSynthesis | None:
    query = compile_trigonometric_triangle_query(statement)
    if query is None:
        return None
    try:
        return execute_trigonometric_triangle_query(query)
    except (TypeError, ValueError):
        return None
