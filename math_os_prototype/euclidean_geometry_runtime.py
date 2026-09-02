"""Typed current-input proofs for elementary Euclidean geometry.

The finite grammar in this module only identifies mathematical relations.  A
successful parse is compiled into a symbolic proof with fresh variables; no
problem identifier, stored answer, or numerical sampling is used to establish
the theorem.  Numerical coordinates are introduced afterwards solely to draw
the same verified construction in the public interface.
"""

from __future__ import annotations

from dataclasses import dataclass
import re
from typing import Any

import sympy as sp

from math_os_prototype.visual_reasoning import plane_scene_diagram


_POINT = r"[A-Z](?:[_']?[A-Za-z0-9]+)?"


@dataclass(frozen=True)
class LineReflectionRelation:
    source: str
    axis: tuple[str, str]
    result: str
    opposite_vertex: str


@dataclass(frozen=True)
class OrthocenterReflectionIR:
    vertices: tuple[str, str, str]
    orthocenter: str
    reflections: tuple[LineReflectionRelation, ...]
    goal: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "vertices": list(self.vertices),
            "orthocenter": self.orthocenter,
            "reflections": [
                {
                    "source": relation.source,
                    "axis": list(relation.axis),
                    "result": relation.result,
                    "opposite_vertex": relation.opposite_vertex,
                }
                for relation in self.reflections
            ],
            "goal": self.goal,
        }


@dataclass(frozen=True)
class EuclideanGeometryRuntimeProof:
    answer: Any
    answer_tex: str
    tool_name: str
    expression_tex: str
    derivation_tex: tuple[str, ...]
    verification_checks: tuple[str, ...]
    proof_program: tuple[dict[str, Any], ...]
    diagram: dict[str, Any]
    visual_explanation: dict[str, Any]
    witness: dict[str, Any]


def _normalize_statement(statement: str) -> str:
    value = re.sub(r"\\text\s*\{([^{}]*)\}", r"\1", statement)
    replacements = {
        "\\triangle": "三角形",
        "△": "三角形",
        "（": "(",
        "）": ")",
        "，": ",",
        "；": ";",
        "：": ":",
        "−": "-",
    }
    for source, target in replacements.items():
        value = value.replace(source, target)
    return re.sub(r"\s+", " ", value).strip()


def _extract_triangle(text: str) -> tuple[str, str, str] | None:
    patterns = (
        r"(?:(?:鋭角|鈍角|直角)\s*)?三角形\s*([A-Z])\s*([A-Z])\s*([A-Z])",
        r"(?:acute\s+|obtuse\s+|right\s+)?triangle\s+([A-Z])\s*([A-Z])\s*([A-Z])",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is not None:
            vertices = tuple(value.upper() for value in match.groups())
            if len(set(vertices)) == 3:
                return vertices  # type: ignore[return-value]
    return None


def _extract_orthocenter(
    text: str,
    vertices: tuple[str, str, str],
) -> str | None:
    triangle = r"\s*".join(re.escape(vertex) for vertex in vertices)
    patterns = (
        rf"(?:三角形\s*{triangle}\s*の\s*)?垂心\s*を\s*({_POINT})\s*と(?:する|し|おく|置く)",
        rf"({_POINT})\s*を\s*(?:三角形\s*{triangle}\s*の\s*)?垂心\s*と(?:する|し|おく|置く)",
        rf"({_POINT})\s+is\s+(?:the\s+)?orthocenter\s+of\s+(?:triangle\s+)?{triangle}",
        rf"(?:the\s+)?orthocenter\s+of\s+(?:triangle\s+)?{triangle}\s+is\s+({_POINT})",
    )
    for pattern in patterns:
        match = re.search(pattern, text, re.IGNORECASE)
        if match is not None:
            return match.group(1).upper()
    return None


def _triangle_sides(
    vertices: tuple[str, str, str],
) -> tuple[tuple[str, str], ...]:
    a, b, c = vertices
    return ((b, c), (c, a), (a, b))


def _axis_key(axis: tuple[str, str]) -> frozenset[str]:
    return frozenset(point.upper() for point in axis)


def _opposite_vertex(
    vertices: tuple[str, str, str],
    axis: tuple[str, str],
) -> str | None:
    remaining = [vertex for vertex in vertices if vertex not in _axis_key(axis)]
    return remaining[0] if len(remaining) == 1 else None


def _default_reflection_label(source: str, opposite: str) -> str:
    return f"{source}_{opposite}"


def _extract_named_reflections(
    text: str,
    vertices: tuple[str, str, str],
    source: str,
) -> list[LineReflectionRelation]:
    relations: list[LineReflectionRelation] = []
    patterns = (
        rf"(?:直線|線分|辺)?\s*([A-Z])\s*([A-Z])\s*に関(?:する|して)\s*(?:点\s*)?{re.escape(source)}\s*(?:の|と)\s*対称(?:な)?(?:点|な点)?\s*を\s*({_POINT})",
        rf"(?:点\s*)?{re.escape(source)}\s*を\s*(?:直線|線分|辺)?\s*([A-Z])\s*([A-Z])\s*に関(?:して|する)\s*対称(?:移動)?(?:した|させた)?(?:点)?\s*を\s*({_POINT})",
        rf"({_POINT})\s+is\s+the\s+reflection\s+of\s+{re.escape(source)}\s+(?:across|in|about)\s+(?:side|line)?\s*([A-Z])\s*([A-Z])",
    )
    side_keys = {_axis_key(side) for side in _triangle_sides(vertices)}
    for pattern_index, pattern in enumerate(patterns):
        for match in re.finditer(pattern, text, re.IGNORECASE):
            groups = tuple(value.upper() for value in match.groups())
            if pattern_index == 2:
                result, left, right = groups
            else:
                left, right, result = groups
            axis = (left, right)
            opposite = _opposite_vertex(vertices, axis)
            if opposite is None or _axis_key(axis) not in side_keys:
                continue
            relations.append(LineReflectionRelation(source, axis, result, opposite))
    return relations


def _extract_plural_reflections(
    text: str,
    vertices: tuple[str, str, str],
    source: str,
) -> list[LineReflectionRelation]:
    sides = _triangle_sides(vertices)
    side_keys = {_axis_key(side): side for side in sides}
    if re.search(
        rf"{re.escape(source)}\s*を\s*(?:三角形\s*[A-Z]\s*[A-Z]\s*[A-Z]\s*の\s*)?(?:三つの|3つの|各)辺\s*に関(?:して|する).{{0,24}}?(?:対称|折り返)",
        text,
        re.IGNORECASE,
    ):
        axes = list(sides)
    else:
        match = re.search(
            rf"{re.escape(source)}\s*を\s*(?P<axes>[^。.!?]{{1,90}}?)\s*に関(?:して|する)\s*(?:それぞれ\s*)?(?:対称(?:移動)?|折り返)",
            text,
            re.IGNORECASE,
        )
        if match is None:
            return []
        axes = []
        for left, right in re.findall(
            r"(?:直線|線分|辺)?\s*([A-Z])\s*([A-Z])",
            match.group("axes"),
            re.IGNORECASE,
        ):
            key = _axis_key((left, right))
            if key in side_keys and side_keys[key] not in axes:
                axes.append(side_keys[key])

    relations = []
    for axis in axes:
        opposite = _opposite_vertex(vertices, axis)
        if opposite is None:
            continue
        relations.append(
            LineReflectionRelation(
                source=source,
                axis=axis,
                result=_default_reflection_label(source, opposite),
                opposite_vertex=opposite,
            )
        )
    return relations


def parse_orthocenter_reflection_circumcircle(
    statement: str,
) -> OrthocenterReflectionIR | None:
    """Elaborate orthocenter reflections without using a stored theorem route."""

    text = _normalize_statement(statement)
    vertices = _extract_triangle(text)
    if vertices is None:
        return None
    orthocenter = _extract_orthocenter(text, vertices)
    if orthocenter is None:
        return None
    if re.search(r"(?:外接円|circumcircle)", text, re.IGNORECASE) is None:
        return None
    if re.search(r"(?:証明|示せ|prove|show)", text, re.IGNORECASE) is None:
        return None

    named = _extract_named_reflections(text, vertices, orthocenter)
    plural = _extract_plural_reflections(text, vertices, orthocenter)
    by_axis: dict[frozenset[str], LineReflectionRelation] = {}
    for relation in [*plural, *named]:
        by_axis[_axis_key(relation.axis)] = relation
    reflections = tuple(
        by_axis[_axis_key(side)]
        for side in _triangle_sides(vertices)
        if _axis_key(side) in by_axis
    )
    if not reflections:
        return None

    stated_count = re.search(r"([123三一二])\s*(?:個|つ|点)", text)
    if stated_count is not None:
        count_table = {"1": 1, "一": 1, "2": 2, "二": 2, "3": 3, "三": 3}
        expected = count_table.get(stated_count.group(1))
        if expected is not None and expected != len(reflections):
            return None
    return OrthocenterReflectionIR(
        vertices=vertices,
        orthocenter=orthocenter,
        reflections=reflections,
        goal="each_reflection_on_triangle_circumcircle",
    )


def _reflect_across_line_exact(
    point: sp.Matrix,
    start: sp.Matrix,
    end: sp.Matrix,
) -> tuple[sp.Matrix, sp.Matrix]:
    direction = end - start
    norm_squared = sp.expand(direction.dot(direction))
    if norm_squared == 0:
        raise ValueError("a reflection axis needs two distinct points")
    foot = sp.simplify(start + direction * ((point - start).dot(direction) / norm_squared))
    reflected = sp.simplify(2 * foot - point)
    return reflected, foot


def _numeric_point(point: sp.Matrix) -> dict[str, float]:
    return {
        "x": round(float(sp.N(point[0], 18)), 10),
        "y": round(float(sp.N(point[1], 18)), 10),
    }


def _diagram_frames(
    ir: OrthocenterReflectionIR,
    point_coordinates: dict[str, sp.Matrix],
    orthocenter: sp.Matrix,
    circumcenter: sp.Matrix,
    circumradius: sp.Expr,
    reflected: dict[str, sp.Matrix],
    feet: dict[str, sp.Matrix],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    a, b, c = ir.vertices
    triangle_points = [point_coordinates[a], point_coordinates[b], point_coordinates[c]]
    triangle_shape = {
        "id": "triangle",
        "kind": "polyline",
        "points": [_numeric_point(point) for point in triangle_points],
        "closed": True,
        "tone": "primary",
    }
    vertex_shapes = [
        {
            "id": f"point-{label}",
            "kind": "point",
            "point": _numeric_point(point_coordinates[label]),
            "label": label,
            "tone": "primary",
        }
        for label in ir.vertices
    ]
    altitude_shapes = []
    for opposite, side in zip(ir.vertices, _triangle_sides(ir.vertices)):
        foot = feet[f"altitude-{opposite}"]
        altitude_shapes.append(
            {
                "id": f"altitude-{opposite}",
                "kind": "polyline",
                "points": [_numeric_point(point_coordinates[opposite]), _numeric_point(foot)],
                "tone": "muted",
                "dashed": True,
            }
        )
    orthocenter_shape = {
        "id": f"point-{ir.orthocenter}",
        "kind": "point",
        "point": _numeric_point(orthocenter),
        "label": ir.orthocenter,
        "tone": "accent",
    }
    reflection_segments = []
    reflection_points = []
    for relation in ir.reflections:
        reflection_segments.append(
            {
                "id": f"reflection-segment-{relation.opposite_vertex}",
                "kind": "polyline",
                "points": [
                    _numeric_point(orthocenter),
                    _numeric_point(reflected[relation.result]),
                ],
                "tone": "secondary",
                "dashed": True,
            }
        )
        reflection_points.append(
            {
                "id": f"point-{relation.result}",
                "kind": "point",
                "point": _numeric_point(reflected[relation.result]),
                "label": relation.result,
                "tone": "secondary",
            }
        )
    circle_shape = {
        "id": "circumcircle",
        "kind": "circle",
        "center": _numeric_point(circumcenter),
        "radius": round(float(sp.N(circumradius, 18)), 10),
        "tone": "accent",
    }

    all_points = [*triangle_points, orthocenter, *reflected.values()]
    radius = float(sp.N(circumradius, 18))
    center_numeric = _numeric_point(circumcenter)
    x_values = [float(sp.N(point[0], 18)) for point in all_points]
    y_values = [float(sp.N(point[1], 18)) for point in all_points]
    x_values.extend((center_numeric["x"] - radius, center_numeric["x"] + radius))
    y_values.extend((center_numeric["y"] - radius, center_numeric["y"] + radius))
    span = max(max(x_values) - min(x_values), max(y_values) - min(y_values), 1.0)
    margin = 0.16 * span
    viewport = {
        "xMin": min(x_values) - margin,
        "xMax": max(x_values) + margin,
        "yMin": min(y_values) - margin,
        "yMax": max(y_values) + margin,
    }

    def scene(title: str, caption: str, shapes: list[dict[str, Any]]) -> dict[str, Any]:
        return plane_scene_diagram(
            title=title,
            caption=caption,
            viewport=viewport,
            shapes=shapes,
            axes=False,
        )

    frame1 = scene(
        "三角形を固定する",
        "頂点と三辺を読み取り、以後の構成が参照する三角形を固定します。",
        [triangle_shape, *vertex_shapes],
    )
    frame2 = scene(
        "垂心を構成する",
        "三本の破線は各頂点から対辺への垂線です。その交点が垂心です。",
        [triangle_shape, *altitude_shapes, *vertex_shapes, orthocenter_shape],
    )
    frame3 = scene(
        "三辺に関して反射する",
        "垂心と各反射点を結ぶ破線は、対応する辺に垂直で、その辺によって二等分されます。",
        [
            triangle_shape,
            *altitude_shapes,
            *reflection_segments,
            *vertex_shapes,
            orthocenter_shape,
            *reflection_points,
        ],
    )
    frame4 = scene(
        "外接円との一致を確認する",
        "外接円を重ねると、三つの反射点がすべて円周上にあります。表示座標でも各円方程式の残差は厳密に0です。",
        [
            circle_shape,
            triangle_shape,
            *altitude_shapes,
            *reflection_segments,
            *vertex_shapes,
            orthocenter_shape,
            *reflection_points,
        ],
    )
    return frame4, [frame1, frame2, frame3, frame4]


def _visual_explanation(
    ir: OrthocenterReflectionIR,
    frames: list[dict[str, Any]],
) -> dict[str, Any]:
    a, b, c = ir.vertices
    steps = (
        (
            "geometry.statement.elaborate_triangle.v1",
            "三角形と三辺を読み取る",
            "問題文の頂点、辺、垂心、反射という役割を区別します。",
            rf"\triangle {a}{b}{c}",
            "ProblemText",
            "TypedTriangle",
        ),
        (
            "geometry.orthocenter.from_altitudes.v1",
            "垂線の交点として垂心を作る",
            "垂心という名称を、各頂点から対辺への垂直関係へ展開します。",
            rf"{a}{ir.orthocenter}\perp {b}{c},\quad {b}{ir.orthocenter}\perp {c}{a}",
            "TypedTriangle",
            "TriangleWithOrthocenter",
        ),
        (
            "geometry.line_reflection.construct.v1",
            "各辺に関して垂心を反射する",
            "反射点との中点が辺上にあり、垂心と反射点を結ぶ線が辺に垂直になるように構成します。",
            r",\quad ".join(
                rf"{relation.result}=s_{{{relation.axis[0]}{relation.axis[1]}}}({ir.orthocenter})"
                for relation in ir.reflections
            ),
            "TriangleWithOrthocenter",
            "TriangleWithReflections",
        ),
        (
            "geometry.circumcircle.polynomial_replay.v1",
            "円方程式へ代入して認証する",
            "任意の一辺を座標軸へ移した記号計算を再生し、三辺すべてに同じ証明を適用します。",
            r"u^2+h^2-u-(h-v)h=u^2-u+vh=0",
            "TriangleWithReflections",
            "VerifiedConcyclicity",
        ),
    )
    visual_steps = []
    for index, (morphism_id, title, explanation, formula, source_type, target_type) in enumerate(steps):
        visual_steps.append(
            {
                "id": f"orthocenter-reflection-step-{index + 1}",
                "title": title,
                "explanation_ja": explanation,
                "formula_tex": rf"\({formula}\)",
                "morphism": {
                    "morphism_id": morphism_id,
                    "label_ja": title,
                    "input_type": source_type,
                    "output_type": target_type,
                },
                "source_state": {"id": f"geometry-state-{index}", "type": source_type},
                "target_state": {"id": f"geometry-state-{index + 1}", "type": target_type},
                "evidence": {"verified": True},
                "diagram": frames[index],
            }
        )
    return {
        "version": 1,
        "mode": "stepper",
        "title": "証明と作図を一手ずつ見る",
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": [step[0] for step in steps],
        "steps": visual_steps,
    }


def prove_orthocenter_reflections_on_circumcircle(
    ir: OrthocenterReflectionIR,
) -> EuclideanGeometryRuntimeProof:
    """Prove the parsed theorem by one side-generic polynomial identity."""

    u = sp.symbols("u", real=True)
    v = sp.symbols("v", real=True, nonzero=True)
    h = sp.cancel(u * (1 - u) / v)
    circle_y_coefficient = sp.cancel(h - v)
    altitude_residual = sp.cancel(u * (1 - u) - v * h)
    vertex_residual = sp.cancel(u**2 + v**2 - u + circle_y_coefficient * v)
    reflected_residual = sp.cancel(
        u**2 + h**2 - u - circle_y_coefficient * h
    )
    if any(value != 0 for value in (altitude_residual, vertex_residual, reflected_residual)):
        raise AssertionError("the generic reflection proof did not close")

    a, b, c = ir.vertices
    point_coordinates = {
        a: sp.Matrix([sp.Rational(2, 5), sp.Rational(4, 5)]),
        b: sp.Matrix([0, 0]),
        c: sp.Matrix([1, 0]),
    }
    ax, ay = sp.symbols("h_x h_y", real=True)
    candidate_h = sp.Matrix([ax, ay])
    altitude_equations = (
        sp.expand((candidate_h - point_coordinates[a]).dot(point_coordinates[c] - point_coordinates[b])),
        sp.expand((candidate_h - point_coordinates[b]).dot(point_coordinates[c] - point_coordinates[a])),
    )
    h_solution = sp.solve(altitude_equations, (ax, ay), dict=True)
    if len(h_solution) != 1:
        raise AssertionError("the display triangle did not determine one orthocenter")
    orthocenter = sp.Matrix([h_solution[0][ax], h_solution[0][ay]])

    ox, oy = sp.symbols("o_x o_y", real=True)
    candidate_o = sp.Matrix([ox, oy])
    circle_equations = (
        sp.expand((candidate_o - point_coordinates[a]).dot(candidate_o - point_coordinates[a])
                  - (candidate_o - point_coordinates[b]).dot(candidate_o - point_coordinates[b])),
        sp.expand((candidate_o - point_coordinates[a]).dot(candidate_o - point_coordinates[a])
                  - (candidate_o - point_coordinates[c]).dot(candidate_o - point_coordinates[c])),
    )
    o_solution = sp.solve(circle_equations, (ox, oy), dict=True)
    if len(o_solution) != 1:
        raise AssertionError("the display triangle did not determine one circumcenter")
    circumcenter = sp.Matrix([o_solution[0][ox], o_solution[0][oy]])
    circumradius_squared = sp.simplify(
        (circumcenter - point_coordinates[a]).dot(circumcenter - point_coordinates[a])
    )
    circumradius = sp.sqrt(circumradius_squared)

    reflected: dict[str, sp.Matrix] = {}
    feet: dict[str, sp.Matrix] = {}
    diagram_circle_residuals: dict[str, sp.Expr] = {}
    reflection_residuals: dict[str, dict[str, sp.Expr]] = {}
    for relation in ir.reflections:
        start = point_coordinates[relation.axis[0]]
        end = point_coordinates[relation.axis[1]]
        reflected_point, foot = _reflect_across_line_exact(orthocenter, start, end)
        reflected[relation.result] = reflected_point
        feet[f"reflection-{relation.opposite_vertex}"] = foot
        direction = end - start
        midpoint = sp.simplify((orthocenter + reflected_point) / 2)
        reflection_residuals[relation.result] = {
            "midpoint_on_axis": sp.simplify(
                (midpoint[0] - start[0]) * direction[1]
                - (midpoint[1] - start[1]) * direction[0]
            ),
            "connector_perpendicular_to_axis": sp.simplify(
                (reflected_point - orthocenter).dot(direction)
            ),
        }
        diagram_circle_residuals[relation.result] = sp.simplify(
            (reflected_point - circumcenter).dot(reflected_point - circumcenter)
            - circumradius_squared
        )

    for opposite, side in zip(ir.vertices, _triangle_sides(ir.vertices)):
        _, altitude_foot = _reflect_across_line_exact(point_coordinates[opposite], point_coordinates[side[0]], point_coordinates[side[1]])
        feet[f"altitude-{opposite}"] = sp.simplify((point_coordinates[opposite] + altitude_foot) / 2)

    exact_residuals = [
        *diagram_circle_residuals.values(),
        *(value for record in reflection_residuals.values() for value in record.values()),
    ]
    if any(sp.simplify(value) != 0 for value in exact_residuals):
        raise AssertionError("the reflected display points failed exact replay")

    diagram, frames = _diagram_frames(
        ir,
        point_coordinates,
        orthocenter,
        circumcenter,
        circumradius,
        reflected,
        feet,
    )
    visual_explanation = _visual_explanation(ir, frames)
    result_labels = [relation.result for relation in ir.reflections]
    result_tex = ",".join(result_labels)
    axis_tex = ",".join("".join(relation.axis) for relation in ir.reflections)
    answer_tex = (
        rf"\({result_tex}\) はそれぞれ辺 \({axis_tex}\) に関する \({ir.orthocenter}\) の反射点であり、"
        rf"すべて三角形 \({a}{b}{c}\) の外接円上にある。"
    )
    return EuclideanGeometryRuntimeProof(
        answer={"points_on_circumcircle": result_labels},
        answer_tex=answer_tex,
        tool_name="mortra.runtime_orthocenter_line_reflection_circumcircle",
        expression_tex=rf"{result_tex}\in\odot {a}{b}{c}",
        derivation_tex=(
            rf"三辺のうち任意の一辺を選ぶ。頂点の名前を一時的に付け替え、その辺を \({b}{c}\)、向かいの頂点を \({a}\) とする。平行移動・回転・相似拡大によって \({b}=(0,0),\ {c}=(1,0),\ {a}=(u,v)\;(v\ne0)\) とおいてよい。これらの変換は垂直、反射、円周上という関係を保つ。",
            rf"垂心を \({ir.orthocenter}=(u,h)\) とおく。\({a}{ir.orthocenter}\perp {b}{c}\) から第1座標は \(u\) である。また \({b}{ir.orthocenter}\perp {a}{c}\) から \(u(1-u)-vh=0\) となるので、\(h=\dfrac{{u(1-u)}}v\) である。",
            rf"三角形 \({a}{b}{c}\) の外接円は \[x^2+y^2-x+(h-v)y=0\] と表せる。実際、\({b},{c}\) を代入すると0であり、\({a}\) を代入した残差は \(u^2+v^2-u+(h-v)v=0\) である。",
            rf"\({ir.orthocenter}\) を \({b}{c}\) に関して反射した点は \((u,-h)\) である。円の左辺へ代入すると \[u^2+h^2-u-(h-v)h=u^2-u+vh=0\] となる。従って、この反射点は外接円上にある。",
            "選んだ辺には何の制限もない。同じ証明を残りの二辺にも適用すると、三つの反射点はすべて同じ外接円上にある。",
        ),
        verification_checks=(
            "入力から三角形、垂心、反射元、反射軸、外接円所属の結論を型付き関係として抽出",
            "任意の一辺を正規化した座標で、二本の高度から垂心座標を記号的に導出",
            "三頂点が外接円方程式を満たすことを恒等式として確認",
            "反射点を外接円方程式へ代入した残差が恒等的に0であることを確認",
            "表示用の三つの反射点について、反射条件と円方程式を独立した有理数座標で再計算",
        ),
        proof_program=(
            {"rule": "elaborate_typed_euclidean_relations", "ir": ir.to_dict()},
            {"rule": "normalize_arbitrary_side_by_similarity", "coordinates": {b: ["0", "0"], c: ["1", "0"], a: ["u", "v"]}},
            {"rule": "solve_orthocenter_from_perpendicular_incidence", "orthocenter": ["u", sp.srepr(h)]},
            {"rule": "construct_line_reflection", "reflection": ["u", sp.srepr(-h)]},
            {"rule": "derive_circumcircle_polynomial", "equation": sp.srepr(sp.Symbol("x")**2 + sp.Symbol("y")**2 - sp.Symbol("x") + circle_y_coefficient * sp.Symbol("y"))},
            {"rule": "replay_zero_polynomial_residual", "residual": sp.srepr(reflected_residual)},
            {"rule": "transport_certificate_to_each_triangle_side", "axes": [list(relation.axis) for relation in ir.reflections]},
            {"rule": "render_verified_construction_sequence", "steps": 4},
        ),
        diagram=diagram,
        visual_explanation=visual_explanation,
        witness={
            "typed_ir": ir.to_dict(),
            "generic_side_certificate": {
                "orthocenter_height": sp.srepr(h),
                "circle_y_coefficient": sp.srepr(circle_y_coefficient),
                "altitude_residual": sp.srepr(altitude_residual),
                "opposite_vertex_circle_residual": sp.srepr(vertex_residual),
                "reflected_point_circle_residual": sp.srepr(reflected_residual),
            },
            "display_coordinates": {
                **{label: [sp.srepr(value) for value in point] for label, point in point_coordinates.items()},
                ir.orthocenter: [sp.srepr(value) for value in orthocenter],
                **{label: [sp.srepr(value) for value in point] for label, point in reflected.items()},
            },
            "display_reflection_residuals": {
                label: {name: sp.srepr(value) for name, value in record.items()}
                for label, record in reflection_residuals.items()
            },
            "display_circle_residuals": {
                label: sp.srepr(value) for label, value in diagram_circle_residuals.items()
            },
        },
    )


def synthesize_euclidean_geometry_runtime(
    statement: str,
) -> EuclideanGeometryRuntimeProof | None:
    ir = parse_orthocenter_reflection_circumcircle(statement)
    if ir is None:
        return None
    return prove_orthocenter_reflections_on_circumcircle(ir)


__all__ = [
    "EuclideanGeometryRuntimeProof",
    "LineReflectionRelation",
    "OrthocenterReflectionIR",
    "parse_orthocenter_reflection_circumcircle",
    "prove_orthocenter_reflections_on_circumcircle",
    "synthesize_euclidean_geometry_runtime",
]
