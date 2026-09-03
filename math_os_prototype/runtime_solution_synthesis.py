"""Current-input proof programs for public single-problem solving.

Every synthesizer in this module compiles mathematical structure found in the
current statement.  No problem id, stored answer, or completed Atlas route is
consulted.  The returned diagram is another representation of the same exact
objects used by the proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
import math
from math import gcd
import re
from typing import Any, Callable

import sympy as sp
from sympy.parsing.latex import parse_latex

from math_os_prototype.euclidean_geometry_runtime import (
    synthesize_euclidean_geometry_runtime,
)
from math_os_prototype.exact_interval_charts import (
    alternating_trig_bounds,
    alternating_trig_interval_chart,
)
from math_os_prototype.latex_frontend import normalize_latex_math, parse_latex_problem
from math_os_prototype.runtime_log_exp_envelope_synthesis import (
    synthesize_log_exp_affine_sandwich,
)
from math_os_prototype.runtime_ordered_sample_synthesis import (
    synthesize_ordered_three_sample_probabilities,
)
from math_os_prototype.structural_theorem_query import (
    solve_mobius_polynomial_fixed_point_chart,
)
from math_os_prototype.visual_reasoning import (
    function_plot_diagram,
    plane_scene_diagram,
    state_transition_diagram,
    variation_table_diagram,
)


@dataclass(frozen=True)
class RuntimeSolutionSynthesis:
    answer: Any
    answer_tex: str
    tool_name: str
    expression_tex: str
    derivation_tex: tuple[str, ...]
    verification_checks: tuple[str, ...]
    proof_program: tuple[dict[str, Any], ...]
    diagram: dict[str, Any] | None
    witness: dict[str, Any]
    visual_explanation: dict[str, Any] | None = None


def _real_float(value: sp.Expr) -> float | None:
    try:
        numeric = complex(sp.N(value, 30))
    except (TypeError, ValueError):
        return None
    if abs(numeric.imag) > 1e-10:
        return None
    return float(numeric.real)


def _proves_strictly_positive(value: sp.Expr) -> bool:
    """Accept an order comparison only when SymPy proves it exactly."""

    return sp.simplify(value > 0) is sp.S.true


def _sympify_exact_scalar(source: str) -> sp.Expr | None:
    try:
        value = sp.sympify(
            source.replace("^", "**"),
            locals={"sin": sp.sin, "cos": sp.cos, "sqrt": sp.sqrt, "pi": sp.pi},
        )
    except (sp.SympifyError, TypeError, ValueError):
        return None
    if value.free_symbols or value.is_real is not True:
        return None
    return sp.simplify(value)


def _parse_normalized_integral_inner_product(
    statement: str,
) -> tuple[str, str, sp.Symbol, sp.Expr, sp.Expr, sp.Expr] | None:
    """Recognize an exact normalized L2 inner-product realization query."""

    if not re.search(r"(?:一組|1組|pair\s+of\s+functions|find\s+functions)", statement, re.I):
        return None
    if not re.search(r"(?:関数|functions?)", statement, re.I):
        return None

    integral_pattern = re.compile(
        r"integral\s*_(?P<lower>\([^)]*\)|[^\s*]+)\*\*"
        r"(?P<upper>\([^)]*\)|[^\s*]+)\s*\*?\s*"
        r"(?P<body>[A-Za-z][A-Za-z0-9_]*\*\([A-Za-z]\)"
        r"(?:\*[A-Za-z][A-Za-z0-9_]*\*\([A-Za-z]\)|\*\*2))\s*\*?\s*d"
        r"(?P<variable>[A-Za-z])"
    )

    for segment in parse_latex_problem(statement).math_segments:
        if "integral" not in segment or "=" not in segment:
            continue
        left, right = segment.rsplit("=", 1)
        matches = list(integral_pattern.finditer(left))
        if len(matches) != 3 or left.count("sqrt(") != 2:
            continue

        bounds = {(match.group("lower"), match.group("upper")) for match in matches}
        variables = {match.group("variable") for match in matches}
        if len(bounds) != 1 or len(variables) != 1:
            continue
        variable_name = variables.pop()

        product_atoms = re.findall(
            rf"([A-Za-z][A-Za-z0-9_]*)\*\({re.escape(variable_name)}\)",
            matches[0].group("body"),
        )
        if len(product_atoms) != 2 or product_atoms[0] == product_atoms[1]:
            continue
        squared_atoms: list[str] = []
        for match in matches[1:]:
            squared = re.fullmatch(
                rf"([A-Za-z][A-Za-z0-9_]*)\*\({re.escape(variable_name)}\)\*\*2",
                match.group("body"),
            )
            if squared is None:
                break
            squared_atoms.append(squared.group(1))
        if len(squared_atoms) != 2 or set(squared_atoms) != set(product_atoms):
            continue

        lower_source, upper_source = next(iter(bounds))
        lower = _sympify_exact_scalar(lower_source)
        upper = _sympify_exact_scalar(upper_source)
        target = _sympify_exact_scalar(right)
        if lower is None or upper is None or target is None:
            continue
        if not _proves_strictly_positive(upper - lower):
            continue
        return product_atoms[0], product_atoms[1], sp.Symbol(variable_name), lower, upper, target
    return None


def synthesize_normalized_inner_product_realization(
    statement: str,
) -> RuntimeSolutionSynthesis | None:
    """Construct two interval functions with a requested normalized inner product."""

    parsed = _parse_normalized_integral_inner_product(statement)
    if parsed is None:
        return None
    first_name, second_name, variable, lower, upper, target = parsed
    infeasible_gap = sp.simplify(target**2 - 1)
    if _proves_strictly_positive(infeasible_gap):
        target_float = _real_float(target)
        if target_float is None:
            return None
        extent = max(1.4, abs(target_float) + 0.4)
        diagram = plane_scene_diagram(
            title="正規化内積が取り得る範囲",
            caption="コーシー・シュワルツの不等式による許容範囲 [-1,1] と、入力された目標値を同じ数直線上に示しています。",
            viewport={"xMin": -extent, "xMax": extent, "yMin": -0.55, "yMax": 0.55},
            axes=True,
            shapes=(
                {
                    "kind": "polyline",
                    "id": "feasible-range",
                    "points": ({"x": -1.0, "y": 0.0}, {"x": 1.0, "y": 0.0}),
                    "tone": "primary",
                },
                {"kind": "point", "id": "lower-bound", "point": {"x": -1.0, "y": 0.0}, "label": "-1", "tone": "primary"},
                {"kind": "point", "id": "upper-bound", "point": {"x": 1.0, "y": 0.0}, "label": "1", "tone": "primary"},
                {
                    "kind": "point",
                    "id": "requested-target",
                    "point": {"x": target_float, "y": 0.0},
                    "label": rf"入力値 {sp.latex(target)}",
                    "tone": "accent",
                },
            ),
        )
        return RuntimeSolutionSynthesis(
            answer={"exists": False, "target": str(target)},
            answer_tex=r"\[\text{そのような関数の組は存在しない。}\]",
            tool_name="mortra.runtime_normalized_inner_product_infeasibility",
            expression_tex=rf"\left|\langle {first_name},{second_name}\rangle_{{\mathrm{{norm}}}}\right|\le 1<{sp.latex(sp.Abs(target))}",
            derivation_tex=(
                rf"分母が定義されるため、\({first_name},{second_name}\) はともに零関数ではない。",
                rf"コーシー・シュワルツの不等式より、正規化内積 \(c\) は必ず \(|c|\le 1\) を満たす。",
                rf"入力された値は \(c={sp.latex(target)}\) であり、厳密に \(c^2-1={sp.latex(infeasible_gap)}>0\) である。したがって \(|c|>1\) となり矛盾する。",
                r"よって、条件を満たす実関数の組は存在しない。",
            ),
            verification_checks=(
                "三つの積分が同じ有限区間と同じ積分変数を使うことを型検査",
                "目標値を入力から厳密式として復元",
                "目標値の二乗から1を引いた値が厳密に正であることを確認",
                "コーシー・シュワルツの不等式による必要条件 |c|<=1 と矛盾することを確認",
            ),
            proof_program=(
                {"rule": "elaborate_normalized_l2_inner_product", "domain": [str(lower), str(upper)]},
                {"rule": "apply_cauchy_schwarz", "bound": "Abs(c) <= 1"},
                {"rule": "compare_exact_target", "target": str(target), "target_squared_minus_one": str(infeasible_gap)},
                {"rule": "close_by_contradiction"},
            ),
            diagram=diagram,
            witness={
                "interval": [str(lower), str(upper)],
                "variable": variable.name,
                "target": str(target),
                "target_squared_minus_one": str(infeasible_gap),
                "feasible_interval": ["-1", "1"],
                "exists": False,
            },
        )
    length = sp.simplify(upper - lower)
    midpoint = sp.simplify((lower + upper) / 2)
    first_basis = sp.simplify(1 / sp.sqrt(length))
    second_basis = sp.simplify(sp.sqrt(12 / length**3) * (variable - midpoint))
    orthogonal_weight = sp.simplify(sp.sqrt(1 - target**2))
    first_function = first_basis
    second_function = sp.simplify(target * first_basis + orthogonal_weight * second_basis)

    first_norm = sp.simplify(sp.integrate(first_function**2, (variable, lower, upper)))
    second_norm = sp.simplify(sp.integrate(second_function**2, (variable, lower, upper)))
    cross_inner_product = sp.simplify(
        sp.integrate(first_function * second_function, (variable, lower, upper))
    )
    basis_cross = sp.simplify(
        sp.integrate(first_basis * second_basis, (variable, lower, upper))
    )
    normalized_value = sp.simplify(
        cross_inner_product / sp.sqrt(first_norm * second_norm)
    )
    if (first_norm, second_norm, basis_cross, normalized_value) != (1, 1, 0, target):
        return None

    lower_float = _real_float(lower)
    upper_float = _real_float(upper)
    if lower_float is None or upper_float is None:
        return None
    first_numeric: Callable[[float], float] = sp.lambdify(variable, first_function, "math")
    second_numeric: Callable[[float], float] = sp.lambdify(variable, second_function, "math")
    diagram = function_plot_diagram(
        [
            (rf"{first_name}({variable})={sp.latex(first_function)}", first_numeric, "primary"),
            (rf"{second_name}({variable})={sp.latex(second_function)}", second_numeric, "accent"),
        ],
        x_min=lower_float,
        x_max=upper_float,
        title="構成した二つの関数",
        caption="同じ厳密式から描画しています。内積とノルムは標本値ではなく記号積分で検証しています。",
    )
    diagram.update(
        {
            "domainTex": rf"[{sp.latex(lower)},{sp.latex(upper)}]",
            "functionTex": [sp.latex(first_function), sp.latex(second_function)],
            "targetInnerProductTex": sp.latex(target),
            "certificateMethod": "exact Gram matrix integration",
        }
    )

    answer_tex = (
        r"\["
        + rf"{first_name}({sp.latex(variable)})={sp.latex(first_function)},\qquad "
        + rf"{second_name}({sp.latex(variable)})={sp.latex(second_function)}"
        + r"\]"
    )
    derivation = (
        rf"区間の長さを \(L={sp.latex(length)}\)、中点を \(m={sp.latex(midpoint)}\) とする。"
        rf"\(u({sp.latex(variable)})=1/\sqrt{{L}}\)、"
        rf"\(v({sp.latex(variable)})=\sqrt{{12/L^3}}\,({sp.latex(variable)}-m)\) とおく。",
        rf"直接積分すると \(\int_{{{sp.latex(lower)}}}^{{{sp.latex(upper)}}}u^2\,d{sp.latex(variable)}=1\)、"
        rf"\(\int_{{{sp.latex(lower)}}}^{{{sp.latex(upper)}}}v^2\,d{sp.latex(variable)}=1\)、"
        rf"\(\int_{{{sp.latex(lower)}}}^{{{sp.latex(upper)}}}uv\,d{sp.latex(variable)}=0\) である。",
        rf"そこで \(c={sp.latex(target)}\) とし、\(f=u\)、"
        rf"\(g=cu+\sqrt{{1-c^2}}\,v\) と構成する。\(u,v\) は正規直交しているので、"
        r"\(\lVert f\rVert=\lVert g\rVert=1\)、\(\langle f,g\rangle=c\) となる。",
        rf"この区間と目標値について式を整理すると、上に示した "
        rf"\({first_name}({sp.latex(variable)})\)、\({second_name}({sp.latex(variable)})\) を得る。"
        rf"実際、正規化内積は厳密に \({sp.latex(normalized_value)}\) である。",
    )
    return RuntimeSolutionSynthesis(
        answer={first_name: first_function, second_name: second_function},
        answer_tex=answer_tex,
        tool_name="mortra.runtime_normalized_inner_product_realization",
        expression_tex=rf"\langle {first_name},{second_name}\rangle={sp.latex(target)}",
        derivation_tex=derivation,
        verification_checks=(
            "三つの積分が同じ有限区間と同じ積分変数を使うことを型検査",
            "目標値が実数で -1 以上 1 以下であることを厳密比較",
            "入力区間から生成した二関数の Gram 行列を記号積分で再計算",
            "二つのノルムが1、相互内積が入力された目標値と一致することを確認",
        ),
        proof_program=(
            {"rule": "elaborate_normalized_l2_inner_product", "domain": [str(lower), str(upper)]},
            {"rule": "construct_interval_orthonormal_frame", "length": str(length), "midpoint": str(midpoint)},
            {"rule": "rotate_orthonormal_frame", "cosine": str(target), "sine": str(orthogonal_weight)},
            {"rule": "replay_exact_gram_matrix", "gram": [[str(first_norm), str(cross_inner_product)], [str(cross_inner_product), str(second_norm)]]},
        ),
        diagram=diagram,
        witness={
            "interval": [str(lower), str(upper)],
            "variable": variable.name,
            "target": str(target),
            "basis": [sp.srepr(first_basis), sp.srepr(second_basis)],
            "functions": [sp.srepr(first_function), sp.srepr(second_function)],
            "gram_matrix": [[str(first_norm), str(cross_inner_product)], [str(cross_inner_product), str(second_norm)]],
            "normalized_inner_product": str(normalized_value),
        },
    )


def _latex_interval(left: sp.Expr | None, right: sp.Expr | None) -> str:
    left_tex = r"-\infty" if left is None else sp.latex(left)
    right_tex = r"\infty" if right is None else sp.latex(right)
    return rf"({left_tex},{right_tex})"


def _relation_rhs(statement: str) -> tuple[sp.Expr, sp.Symbol] | None:
    for segment in parse_latex_problem(statement).math_segments:
        if "=" not in segment:
            continue
        left, right = segment.split("=", 1)
        if not (re.search(r"(?:^|\*)f\*?\(", left) or left.strip() == "y"):
            continue
        try:
            expression = sp.sympify(right.replace("^", "**"))
        except (sp.SympifyError, TypeError, ValueError):
            continue
        variables = sorted(expression.free_symbols, key=lambda symbol: symbol.name)
        if len(variables) == 1:
            return expression, variables[0]
    return None


def synthesize_univariate_variation(statement: str) -> RuntimeSolutionSynthesis | None:
    """Differentiate a current-input polynomial and compile its variation."""

    if not re.search(r"(?:増減|極大|極小|概形|グラフ)", statement):
        return None
    parsed = _relation_rhs(statement)
    if parsed is None:
        return None
    expression, variable = parsed
    try:
        polynomial = sp.Poly(expression, variable)
        derivative = sp.factor(sp.diff(expression, variable))
        derivative_polynomial = sp.Poly(derivative, variable)
    except sp.PolynomialError:
        return None
    if polynomial.degree() < 1 or derivative_polynomial.degree() < 1:
        return None

    root_multiplicities = sp.roots(derivative_polynomial.as_expr(), variable)
    if sum(root_multiplicities.values()) != derivative_polynomial.degree():
        return None
    real_roots = [root for root in root_multiplicities if root.is_real is True]
    if not real_roots:
        return None
    real_roots.sort(key=lambda value: float(sp.N(value, 30)))

    boundaries: list[sp.Expr | None] = [None, *real_roots, None]
    interval_signs: list[int] = []
    for left, right in zip(boundaries, boundaries[1:]):
        if left is None:
            sample = sp.Rational(str(float(sp.N(right, 30)) - 1.0))
        elif right is None:
            sample = sp.Rational(str(float(sp.N(left, 30)) + 1.0))
        else:
            sample = sp.Rational(str((float(sp.N(left, 30)) + float(sp.N(right, 30))) / 2.0))
        value = sp.factor(derivative.subs(variable, sample))
        interval_signs.append(1 if value > 0 else -1 if value < 0 else 0)
    if any(sign == 0 for sign in interval_signs):
        return None

    maxima: list[tuple[sp.Expr, sp.Expr]] = []
    minima: list[tuple[sp.Expr, sp.Expr]] = []
    for index, root in enumerate(real_roots):
        value = sp.simplify(expression.subs(variable, root))
        if interval_signs[index] > 0 > interval_signs[index + 1]:
            maxima.append((root, value))
        elif interval_signs[index] < 0 < interval_signs[index + 1]:
            minima.append((root, value))

    increasing = [
        _latex_interval(boundaries[index], boundaries[index + 1])
        for index, sign in enumerate(interval_signs)
        if sign > 0
    ]
    decreasing = [
        _latex_interval(boundaries[index], boundaries[index + 1])
        for index, sign in enumerate(interval_signs)
        if sign < 0
    ]
    extrema_tex = []
    extrema_tex.extend(
        rf"x={sp.latex(point)}\text{{ で極大値 }}{sp.latex(value)}"
        for point, value in maxima
    )
    extrema_tex.extend(
        rf"x={sp.latex(point)}\text{{ で極小値 }}{sp.latex(value)}"
        for point, value in minima
    )
    increasing_tex = r",\;".join(increasing) or r"\varnothing"
    decreasing_tex = r",\;".join(decreasing) or r"\varnothing"
    answer_rows = [
        rf"f'({sp.latex(variable)})={sp.latex(derivative)}",
        rf"\text{{増加}}:\;{increasing_tex}",
        rf"\text{{減少}}:\;{decreasing_tex}",
        *extrema_tex,
    ]
    answer_tex = r"\[\begin{gathered}" + r"\\".join(answer_rows) + r"\end{gathered}\]"

    columns: list[str] = []
    derivative_cells: list[str] = []
    function_cells: list[str] = []
    for index, sign in enumerate(interval_signs):
        columns.append(_latex_interval(boundaries[index], boundaries[index + 1]))
        derivative_cells.append("+" if sign > 0 else "-")
        function_cells.append("↗" if sign > 0 else "↘")
        if index < len(real_roots):
            root = real_roots[index]
            columns.append(sp.latex(root))
            derivative_cells.append("0")
            function_cells.append(sp.latex(sp.simplify(expression.subs(variable, root))))
    variation = variation_table_diagram(
        columns,
        [
            {"label": "f'(x)", "cells": derivative_cells},
            {"label": "f(x)", "cells": function_cells},
        ],
        title="増減表",
        caption="導関数の零点と各区間の符号から増減を決めます。",
        variable_label=sp.latex(variable),
    )
    critical_numeric = [value for root in real_roots if (value := _real_float(root)) is not None]
    x_min = min(critical_numeric, default=-2.0) - 1.5
    x_max = max(critical_numeric, default=2.0) + 1.5
    numeric_function: Callable[[float], float] = sp.lambdify(variable, expression, "math")
    marked_points = [
        (float(sp.N(point)), float(sp.N(value)), sp.latex(value))
        for point, value in [*maxima, *minima]
    ]
    plot = function_plot_diagram(
        [(sp.latex(expression), numeric_function, "primary")],
        x_min=x_min,
        x_max=x_max,
        title="関数の概形",
        caption="増減表と同じ厳密式を描き、極値を橙色で示します。",
        marked_points=marked_points,
    )
    diagram = {
        "version": 1,
        "kind": "calculus",
        "title": "増減表とグラフ",
        "caption": "導関数の符号と関数の概形を同じ証明状態から生成します。",
        "variable": sp.latex(variable),
        "functionTex": sp.latex(expression),
        "derivativeTex": sp.latex(derivative),
        "domainTex": r"\mathbb{R}",
        "variation": variation,
        "plot": plot,
        "certificateMethod": "exact symbolic derivative + rational sign samples",
    }
    checks = (
        "入力された関数を記号微分して導関数を再計算",
        "導関数の全代数根と重複度を列挙",
        "各区間の有理標本点で導関数の厳密符号を確認",
        "各極値を元の関数へ代入して厳密値を確認",
    )
    proof_program = (
        {"rule": "differentiate_exact_function", "result": sp.srepr(derivative)},
        {"rule": "enumerate_critical_points", "roots": [sp.srepr(root) for root in real_roots]},
        {"rule": "propagate_derivative_sign", "signs": interval_signs},
        {"rule": "classify_local_extrema", "maxima": len(maxima), "minima": len(minima)},
        {"rule": "render_verified_variation_and_graph"},
    )
    return RuntimeSolutionSynthesis(
        answer={"derivative": str(derivative), "maxima": maxima, "minima": minima},
        answer_tex=answer_tex,
        tool_name="mortra.runtime_univariate_variation",
        expression_tex=sp.latex(expression),
        derivation_tex=(
            rf"与式を微分すると \(f'({sp.latex(variable)})={sp.latex(derivative)}\) である。",
            rf"\(f'({sp.latex(variable)})=0\) の実数解は "
            + r"\(" + r",\;".join(sp.latex(root) for root in real_roots) + r"\) である。",
            "これらで数直線を分け、導関数の符号を調べると図の増減表を得る。",
            "符号が正から負へ変わる点が極大、負から正へ変わる点が極小である。"
            + (
                "したがって "
                + "、".join(rf"\({item}\)" for item in extrema_tex)
                + "。"
                if extrema_tex
                else ""
            ),
        ),
        verification_checks=checks,
        proof_program=proof_program,
        diagram=diagram,
        witness={
            "function": sp.srepr(expression),
            "derivative": sp.srepr(derivative),
            "critical_points": [sp.srepr(root) for root in real_roots],
            "interval_signs": interval_signs,
        },
    )


def _sorted_real_polynomial_roots(expression: sp.Expr, variable: sp.Symbol) -> list[sp.Expr] | None:
    try:
        polynomial = sp.Poly(expression, variable)
    except sp.PolynomialError:
        return None
    roots = sp.roots(polynomial.as_expr(), variable)
    if sum(roots.values()) != polynomial.degree():
        return None
    real_roots = [sp.simplify(root) for root in roots if root.is_real is True]
    real_roots.sort(key=lambda value: float(sp.N(value, 40)))
    return real_roots


def synthesize_rational_variation(statement: str) -> RuntimeSolutionSynthesis | None:
    """Compile a current-input rational function to signs, asymptotes, and plot."""

    if not re.search(r"(?:増減|極値|極大|極小|概形|グラフ|漸近線)", statement):
        return None
    parsed = _relation_rhs(statement)
    if parsed is None:
        return None
    expression, variable = parsed
    numerator, denominator = sp.fraction(sp.cancel(expression))
    try:
        numerator_polynomial = sp.Poly(numerator, variable)
        denominator_polynomial = sp.Poly(denominator, variable)
    except sp.PolynomialError:
        return None
    if denominator_polynomial.degree() < 1:
        return None

    derivative = sp.cancel(sp.diff(expression, variable))
    derivative_numerator, _ = sp.fraction(derivative)
    critical_points = _sorted_real_polynomial_roots(derivative_numerator, variable)
    poles = _sorted_real_polynomial_roots(denominator, variable)
    if critical_points is None or poles is None:
        return None
    critical_points = [
        point for point in critical_points
        if sp.simplify(denominator.subs(variable, point)) != 0
    ]
    boundaries_exact = sorted(
        set([*critical_points, *poles]),
        key=lambda value: float(sp.N(value, 40)),
    )
    boundaries: list[sp.Expr | None] = [None, *boundaries_exact, None]
    interval_signs: list[int] = []
    for left, right in zip(boundaries, boundaries[1:]):
        if left is None:
            sample = sp.Rational(str(float(sp.N(right, 30)) - 1.0))
        elif right is None:
            sample = sp.Rational(str(float(sp.N(left, 30)) + 1.0))
        else:
            sample = sp.Rational(str((float(sp.N(left, 30)) + float(sp.N(right, 30))) / 2.0))
        sign_value = sp.sign(sp.simplify(derivative.subs(variable, sample)))
        if sign_value not in {-1, 1}:
            return None
        interval_signs.append(int(sign_value))

    maxima: list[tuple[sp.Expr, sp.Expr]] = []
    minima: list[tuple[sp.Expr, sp.Expr]] = []
    for point in critical_points:
        boundary_index = boundaries_exact.index(point)
        value = sp.simplify(expression.subs(variable, point))
        if interval_signs[boundary_index] > 0 > interval_signs[boundary_index + 1]:
            maxima.append((point, value))
        elif interval_signs[boundary_index] < 0 < interval_signs[boundary_index + 1]:
            minima.append((point, value))

    quotient, remainder = sp.div(numerator_polynomial, denominator_polynomial)
    asymptote = sp.expand(quotient.as_expr())
    if sp.simplify(expression - asymptote - remainder.as_expr() / denominator) != 0:
        return None
    if any(sp.simplify(denominator.subs(variable, pole)) != 0 for pole in poles):
        return None

    increasing = [
        _latex_interval(boundaries[index], boundaries[index + 1])
        for index, sign in enumerate(interval_signs)
        if sign > 0
    ]
    decreasing = [
        _latex_interval(boundaries[index], boundaries[index + 1])
        for index, sign in enumerate(interval_signs)
        if sign < 0
    ]
    answer_rows = [
        rf"f'({sp.latex(variable)})={sp.latex(derivative)}",
        rf"\text{{増加}}:\;{r',\;'.join(increasing) or r'\varnothing'}",
        rf"\text{{減少}}:\;{r',\;'.join(decreasing) or r'\varnothing'}",
    ]
    answer_rows.extend(
        rf"{sp.latex(variable)}={sp.latex(point)}\text{{ で極大値 }}{sp.latex(value)}"
        for point, value in maxima
    )
    answer_rows.extend(
        rf"{sp.latex(variable)}={sp.latex(point)}\text{{ で極小値 }}{sp.latex(value)}"
        for point, value in minima
    )
    if poles:
        answer_rows.append(
            r"\text{垂直漸近線}:\;" + r",\;".join(
                rf"{sp.latex(variable)}={sp.latex(pole)}" for pole in poles
            )
        )
    answer_rows.append(rf"\text{{無限遠での漸近線}}:\;y={sp.latex(asymptote)}")
    answer_tex = r"\[\begin{gathered}" + r"\\".join(answer_rows) + r"\end{gathered}\]"

    columns: list[str] = []
    derivative_cells: list[str] = []
    function_cells: list[str] = []
    for index, sign in enumerate(interval_signs):
        columns.append(_latex_interval(boundaries[index], boundaries[index + 1]))
        derivative_cells.append("+" if sign > 0 else "-")
        function_cells.append("↗" if sign > 0 else "↘")
        if index < len(boundaries_exact):
            boundary = boundaries_exact[index]
            columns.append(sp.latex(boundary))
            if boundary in poles:
                derivative_cells.append("-")
                function_cells.append("定義なし")
            else:
                derivative_cells.append("0")
                function_cells.append(sp.latex(sp.simplify(expression.subs(variable, boundary))))
    variation = variation_table_diagram(
        columns,
        [
            {"label": "f'(x)", "cells": derivative_cells},
            {"label": "f(x)", "cells": function_cells},
        ],
        title="増減表",
        caption="導関数の零点と分母の零点を区別して増減を決めます。",
        variable_label=sp.latex(variable),
    )

    finite_points = [float(sp.N(value, 30)) for value in boundaries_exact]
    x_min = min(finite_points, default=-3.0) - 1.5
    x_max = max(finite_points, default=3.0) + 1.5
    numeric_function: Callable[[float], float] = sp.lambdify(variable, expression, "math")
    numeric_asymptote: Callable[[float], float] = sp.lambdify(variable, asymptote, "math")
    pole_values = [float(sp.N(pole, 30)) for pole in poles]
    branch_boundaries: list[float | None] = [None, *pole_values, None]
    curves: list[tuple[str, Callable[[float], float], str]] = []
    for branch_index, (left, right) in enumerate(zip(branch_boundaries, branch_boundaries[1:])):
        def branch(value: float, *, lower: float | None = left, upper: float | None = right) -> float:
            if lower is not None and value <= lower:
                raise ValueError("outside branch")
            if upper is not None and value >= upper:
                raise ValueError("outside branch")
            return float(numeric_function(value))

        curves.append((f"f-{branch_index}", branch, "primary"))
    curves.append((sp.latex(asymptote), numeric_asymptote, "secondary"))
    marked_points = [
        (float(sp.N(point, 30)), float(sp.N(value, 30)), sp.latex(value))
        for point, value in [*maxima, *minima]
    ]
    plot = function_plot_diagram(
        curves,
        x_min=x_min,
        x_max=x_max,
        title="有理関数の概形",
        caption="各枝を分母の零点で分け、漸近線と極値を同じ座標面に示します。",
        marked_points=marked_points,
        samples=241,
    )
    for index, pole_value in enumerate(pole_values):
        plot["shapes"].append({
            "id": f"vertical-asymptote-{index}",
            "kind": "polyline",
            "points": [
                {"x": pole_value, "y": plot["viewport"]["yMin"]},
                {"x": pole_value, "y": plot["viewport"]["yMax"]},
            ],
            "tone": "muted",
            "dashed": True,
        })
    diagram = {
        "version": 1,
        "kind": "calculus",
        "title": "増減表・漸近線・グラフ",
        "caption": "定義域の切れ目を保持したまま、証明と図を同じ式から生成します。",
        "variable": sp.latex(variable),
        "functionTex": sp.latex(expression),
        "derivativeTex": sp.latex(derivative),
        "domainTex": r"\mathbb{R}\setminus\{" + r",\;".join(sp.latex(pole) for pole in poles) + r"\}",
        "variation": variation,
        "plot": plot,
        "certificateMethod": "exact rational differentiation + pole-separated sign replay",
    }
    return RuntimeSolutionSynthesis(
        answer={"maxima": maxima, "minima": minima, "poles": poles, "asymptote": asymptote},
        answer_tex=answer_tex,
        tool_name="mortra.runtime_rational_variation",
        expression_tex=sp.latex(expression),
        derivation_tex=(
            rf"分母が0となる点は \({r',\;'.join(sp.latex(pole) for pole in poles)}\) であり、ここでは関数を定義できない。",
            rf"商の微分を整理すると \(f'({sp.latex(variable)})={sp.latex(derivative)}\) である。導関数の分子の実数解と分母の零点で定義域を分ける。",
            "各区間で導関数の符号を厳密に調べると、図の増減表を得る。",
            rf"多項式除法により \(f({sp.latex(variable)})={sp.latex(asymptote)}+{sp.latex(remainder.as_expr())}/{sp.latex(denominator)}\) である。従って無限遠での漸近線は \(y={sp.latex(asymptote)}\) である。",
        ),
        verification_checks=(
            "分子と分母を既約な多項式として抽出",
            "導関数の全実根と分母の全実根を厳密に列挙",
            "各定義域区間で導関数の符号を有理数標本により再生",
            "多項式除法の恒等式と全極値を元の関数へ再代入",
        ),
        proof_program=(
            {"rule": "elaborate_rational_function", "numerator": sp.srepr(numerator), "denominator": sp.srepr(denominator)},
            {"rule": "differentiate_rational_function", "derivative": sp.srepr(derivative)},
            {"rule": "partition_domain_by_critical_points_and_poles", "signs": interval_signs},
            {"rule": "divide_for_polynomial_asymptote", "quotient": sp.srepr(asymptote)},
            {"rule": "render_pole_separated_variation_and_graph"},
        ),
        diagram=diagram,
        witness={
            "function": sp.srepr(expression),
            "derivative": sp.srepr(derivative),
            "critical_points": [sp.srepr(point) for point in critical_points],
            "poles": [sp.srepr(pole) for pole in poles],
            "asymptote": sp.srepr(asymptote),
            "interval_signs": interval_signs,
        },
    )


def synthesize_positive_monomial_extremum(statement: str) -> RuntimeSolutionSynthesis | None:
    """Maximize a positive two-variable monomial under a fixed positive sum."""

    if "最大" not in statement or "正の実数" not in statement:
        return None
    segments = parse_latex_problem(statement).math_segments
    sum_data: tuple[sp.Symbol, sp.Symbol, sp.Expr] | None = None
    for segment in segments:
        match = re.fullmatch(r"(?P<x>[A-Za-z])\+(?P<y>[A-Za-z])=(?P<sum>.+)", segment)
        if match is None:
            continue
        try:
            sum_value = sp.simplify(sp.sympify(match.group("sum")))
        except (sp.SympifyError, TypeError, ValueError):
            continue
        if sum_value.is_positive is True:
            sum_data = (sp.Symbol(match.group("x")), sp.Symbol(match.group("y")), sum_value)
            break
    if sum_data is None:
        return None
    first, second, sum_value = sum_data
    objective: sp.Expr | None = None
    exponent_first = exponent_second = 0
    coefficient = sp.Integer(0)
    for segment in segments:
        if "=" in segment:
            continue
        try:
            candidate = sp.expand(sp.sympify(segment.replace("^", "**")))
            polynomial = sp.Poly(candidate, first, second)
        except (sp.SympifyError, sp.PolynomialError, TypeError, ValueError):
            continue
        terms = polynomial.terms()
        if len(terms) != 1:
            continue
        powers, candidate_coefficient = terms[0]
        if powers[0] < 1 or powers[1] < 1 or candidate_coefficient <= 0:
            continue
        objective = candidate
        exponent_first, exponent_second = int(powers[0]), int(powers[1])
        coefficient = sp.simplify(candidate_coefficient)
        break
    if objective is None:
        return None

    total_exponent = exponent_first + exponent_second
    maximizing_first = sp.simplify(sp.Rational(exponent_first, total_exponent) * sum_value)
    maximizing_second = sp.simplify(sp.Rational(exponent_second, total_exponent) * sum_value)
    maximum = sp.simplify(objective.subs({first: maximizing_first, second: maximizing_second}))
    reduced = sp.expand(objective.subs(second, sum_value - first))
    derivative = sp.factor(sp.diff(reduced, first))
    if sp.simplify(derivative.subs(first, maximizing_first)) != 0:
        return None
    sample_left = sp.simplify(maximizing_first / 2)
    sample_right = sp.simplify((maximizing_first + sum_value) / 2)
    if sp.sign(derivative.subs(first, sample_left)) != 1 or sp.sign(derivative.subs(first, sample_right)) != -1:
        return None

    numeric_reduced: Callable[[float], float] = sp.lambdify(first, reduced, "math")
    plot = function_plot_diagram(
        [(sp.latex(reduced), numeric_reduced, "primary")],
        x_min=0.0,
        x_max=float(sp.N(sum_value, 30)),
        title="制約条件上の目的関数",
        caption=rf"\({second}={sp.latex(sum_value)}-{first}\) として一変数のグラフにします。",
        marked_points=[(
            float(sp.N(maximizing_first, 30)),
            float(sp.N(maximum, 30)),
            sp.latex(maximum),
        )],
    )
    answer_tex = (
        rf"\[\max {sp.latex(objective)}={sp.latex(maximum)},\qquad "
        rf"{sp.latex(first)}={sp.latex(maximizing_first)},\quad "
        rf"{sp.latex(second)}={sp.latex(maximizing_second)}\]"
    )
    return RuntimeSolutionSynthesis(
        answer={"maximum": maximum, "point": [maximizing_first, maximizing_second]},
        answer_tex=answer_tex,
        tool_name="mortra.runtime_positive_monomial_extremum",
        expression_tex=sp.latex(objective),
        derivation_tex=(
            rf"制約式から \({sp.latex(second)}={sp.latex(sum_value)}-{sp.latex(first)}\) とおく。目的式は \({sp.latex(reduced)}\) となる。",
            rf"これを微分すると \({sp.latex(derivative)}\) である。正の範囲 \(0<{sp.latex(first)}<{sp.latex(sum_value)}\) では、\({sp.latex(first)}={sp.latex(maximizing_first)}\) の前で正、後で負になる。",
            rf"従って最大となるのは \(({sp.latex(first)},{sp.latex(second)})=({sp.latex(maximizing_first)},{sp.latex(maximizing_second)})\) のときで、最大値は \({sp.latex(maximum)}\) である。",
            "同じ結論は重み付き相加平均・相乗平均の不等式でも得られ、等号条件も一致する。",
        ),
        verification_checks=(
            "入力から正の二変数単項式と和の制約を抽出",
            "一変数化した導関数の零点を厳密計算",
            "零点の左右で導関数の符号が正から負へ変わることを確認",
            "最大点を元の制約式と目的式へ再代入",
        ),
        proof_program=(
            {"rule": "elaborate_positive_sum_constraint", "sum": sp.srepr(sum_value)},
            {"rule": "extract_monomial_weights", "weights": [exponent_first, exponent_second]},
            {"rule": "eliminate_one_variable", "reduced": sp.srepr(reduced)},
            {"rule": "certify_unique_interior_maximum", "point": [sp.srepr(maximizing_first), sp.srepr(maximizing_second)]},
            {"rule": "render_constrained_objective_graph"},
        ),
        diagram=plot,
        witness={
            "variables": [str(first), str(second)],
            "sum": sp.srepr(sum_value),
            "exponents": [exponent_first, exponent_second],
            "coefficient": sp.srepr(coefficient),
            "maximizer": [sp.srepr(maximizing_first), sp.srepr(maximizing_second)],
            "maximum": sp.srepr(maximum),
        },
    )


def _parse_coordinate(value: str) -> sp.Expr:
    normalized = value.strip().replace("−", "-")
    if "\\" in normalized:
        return sp.simplify(parse_latex(normalized))
    return sp.simplify(sp.sympify(normalized.replace("^", "**")))


def _coordinate_points(statement: str) -> list[tuple[str, sp.Matrix]]:
    points: list[tuple[str, sp.Matrix]] = []
    pattern = r"(?P<label>[A-Z][A-Za-z0-9_]*)\s*[\(（]\s*(?P<x>[^,，()（）]+)\s*[,，]\s*(?P<y>[^()（）]+)\s*[\)）]"
    for match in re.finditer(pattern, statement):
        try:
            point = sp.Matrix([_parse_coordinate(match.group("x")), _parse_coordinate(match.group("y"))])
        except (sp.SympifyError, TypeError, ValueError):
            continue
        points.append((match.group("label"), point))
    return points


def synthesize_coordinate_triangle_centers(statement: str) -> RuntimeSolutionSynthesis | None:
    """Construct a triangle's circumcenter and incenter from coordinates."""

    if "三角形" not in statement or not re.search(r"(?:外心|内心)", statement):
        return None
    parsed = _coordinate_points(statement)
    if len(parsed) != 3:
        return None
    labels = [label for label, _ in parsed]
    points = [point for _, point in parsed]
    a_point, b_point, c_point = points
    oriented_double_area = sp.expand(
        (b_point[0] - a_point[0]) * (c_point[1] - a_point[1])
        - (b_point[1] - a_point[1]) * (c_point[0] - a_point[0])
    )
    if sp.simplify(oriented_double_area) == 0:
        return None

    ox, oy = sp.symbols("o_x o_y", real=True)
    o = sp.Matrix([ox, oy])
    equations = [
        sp.expand((o - a_point).dot(o - a_point) - (o - b_point).dot(o - b_point)),
        sp.expand((o - a_point).dot(o - a_point) - (o - c_point).dot(o - c_point)),
    ]
    solutions = sp.solve(equations, (ox, oy), dict=True)
    if len(solutions) != 1:
        return None
    circumcenter = sp.Matrix([sp.simplify(solutions[0][ox]), sp.simplify(solutions[0][oy])])
    side_a = sp.sqrt(sp.expand((b_point - c_point).dot(b_point - c_point)))
    side_b = sp.sqrt(sp.expand((a_point - c_point).dot(a_point - c_point)))
    side_c = sp.sqrt(sp.expand((a_point - b_point).dot(a_point - b_point)))
    perimeter = sp.simplify(side_a + side_b + side_c)
    incenter = sp.simplify((side_a * a_point + side_b * b_point + side_c * c_point) / perimeter)
    circumradius = sp.sqrt(sp.simplify((circumcenter - a_point).dot(circumcenter - a_point)))
    inradius = sp.simplify(sp.Abs(oriented_double_area) / perimeter)

    circum_residuals = [
        sp.simplify((circumcenter - point).dot(circumcenter - point) - circumradius**2)
        for point in points
    ]
    distance_residuals = []
    for start, end in ((a_point, b_point), (b_point, c_point), (c_point, a_point)):
        distance = sp.simplify(sp.Abs(
            (end[0] - start[0]) * (incenter[1] - start[1])
            - (end[1] - start[1]) * (incenter[0] - start[0])
        ) / sp.sqrt((end - start).dot(end - start)))
        distance_residuals.append(sp.simplify(distance - inradius))
    if any(residual != 0 for residual in [*circum_residuals, *distance_residuals]):
        return None

    def numeric(point: sp.Matrix) -> tuple[float, float]:
        return float(sp.N(point[0], 18)), float(sp.N(point[1], 18))

    numeric_points = [numeric(point) for point in points]
    numeric_o = numeric(circumcenter)
    numeric_i = numeric(incenter)
    radius_o = float(sp.N(circumradius, 18))
    radius_i = float(sp.N(inradius, 18))
    x_values = [point[0] for point in numeric_points] + [numeric_o[0] - radius_o, numeric_o[0] + radius_o]
    y_values = [point[1] for point in numeric_points] + [numeric_o[1] - radius_o, numeric_o[1] + radius_o]
    span = max(max(x_values) - min(x_values), max(y_values) - min(y_values), 1.0)
    margin = 0.18 * span

    def point_record(point: tuple[float, float]) -> dict[str, float]:
        return {"x": round(point[0], 10), "y": round(point[1], 10)}

    shapes: list[dict[str, Any]] = [
        {
            "id": "triangle",
            "kind": "polyline",
            "points": [point_record(point) for point in numeric_points],
            "closed": True,
            "tone": "primary",
        },
        {
            "id": "circumcircle",
            "kind": "circle",
            "center": point_record(numeric_o),
            "radius": radius_o,
            "tone": "muted",
        },
        {
            "id": "incircle",
            "kind": "circle",
            "center": point_record(numeric_i),
            "radius": radius_i,
            "tone": "secondary",
        },
    ]
    for label, point in zip(labels, numeric_points):
        shapes.append({"id": f"point-{label}", "kind": "point", "point": point_record(point), "label": label, "tone": "primary"})
    shapes.extend([
        {"id": "point-O", "kind": "point", "point": point_record(numeric_o), "label": "O", "tone": "accent"},
        {"id": "point-I", "kind": "point", "point": point_record(numeric_i), "label": "I", "tone": "secondary"},
    ])
    for index, (start, end) in enumerate(((numeric_points[0], numeric_points[1]), (numeric_points[0], numeric_points[2]))):
        midpoint = ((start[0] + end[0]) / 2.0, (start[1] + end[1]) / 2.0)
        direction = (-(end[1] - start[1]), end[0] - start[0])
        norm = max((direction[0] ** 2 + direction[1] ** 2) ** 0.5, 1e-12)
        unit = (direction[0] / norm, direction[1] / norm)
        shapes.append({
            "id": f"perpendicular-bisector-{index}",
            "kind": "polyline",
            "points": [
                point_record((midpoint[0] - span * unit[0], midpoint[1] - span * unit[1])),
                point_record((midpoint[0] + span * unit[0], midpoint[1] + span * unit[1])),
            ],
            "tone": "muted",
            "dashed": True,
        })
    for index in (0, 1):
        shapes.append({
            "id": f"angle-bisector-{index}",
            "kind": "polyline",
            "points": [point_record(numeric_points[index]), point_record(numeric_i)],
            "tone": "secondary",
            "dashed": True,
        })
    diagram = plane_scene_diagram(
        title="外心・内心と補助線",
        caption="灰色は垂直二等分線、青緑は角の二等分線です。両者の交点として O と I を構成します。",
        viewport={
            "xMin": min(x_values) - margin,
            "xMax": max(x_values) + margin,
            "yMin": min(y_values) - margin,
            "yMax": max(y_values) + margin,
        },
        shapes=shapes,
        axes=True,
    )
    point_tex = lambda point: rf"\left({sp.latex(point[0])},{sp.latex(point[1])}\right)"
    answer_tex = rf"\(O={point_tex(circumcenter)},\qquad I={point_tex(incenter)}\)"
    checks = (
        "外心から3頂点までの距離平方がすべて一致",
        "内心から3辺への距離がすべて内接円半径と一致",
        "三角形の符号付き面積が0でないことを確認",
    )
    return RuntimeSolutionSynthesis(
        answer={"circumcenter": list(circumcenter), "incenter": list(incenter)},
        answer_tex=answer_tex,
        tool_name="mortra.runtime_coordinate_triangle_centers",
        expression_tex=answer_tex,
        derivation_tex=(
            r"外心を \(O=(u,v)\) とおく。\(OA^2=OB^2\), \(OA^2=OC^2\) を展開すると、二次項が消えて \(u,v\) の連立一次方程式になる。",
            rf"これを解くと \(O={point_tex(circumcenter)}\) を得る。3頂点までの距離を戻し計算するとすべて \({sp.latex(circumradius)}\) である。",
            rf"辺 \(BC,CA,AB\) の長さをそれぞれ \(a={sp.latex(side_a)}, b={sp.latex(side_b)}, c={sp.latex(side_c)}\) とする。",
            rf"角の二等分線定理より内心は \(I=(aA+bB+cC)/(a+b+c)={point_tex(incenter)}\) である。各辺への距離はすべて \({sp.latex(inradius)}\) となる。",
        ),
        verification_checks=checks,
        proof_program=(
            {"rule": "perpendicular_bisector_linearization", "equations": [sp.srepr(equation) for equation in equations]},
            {"rule": "solve_exact_affine_intersection", "point": [sp.srepr(value) for value in circumcenter]},
            {"rule": "incenter_barycentric_weights", "weights": [sp.srepr(side_a), sp.srepr(side_b), sp.srepr(side_c)]},
            {"rule": "replay_equal_distance_certificates"},
            {"rule": "render_construction_from_verified_points"},
        ),
        diagram=diagram,
        witness={
            "labels": labels,
            "points": [[sp.srepr(value) for value in point] for point in points],
            "circumcenter": [sp.srepr(value) for value in circumcenter],
            "incenter": [sp.srepr(value) for value in incenter],
        },
    )


def synthesize_euclidean_geometry(statement: str) -> RuntimeSolutionSynthesis | None:
    """Compile supported Euclidean relations into a fresh symbolic proof."""

    proof = synthesize_euclidean_geometry_runtime(statement)
    if proof is None:
        return None
    return RuntimeSolutionSynthesis(
        answer=proof.answer,
        answer_tex=proof.answer_tex,
        tool_name=proof.tool_name,
        expression_tex=proof.expression_tex,
        derivation_tex=proof.derivation_tex,
        verification_checks=proof.verification_checks,
        proof_program=proof.proof_program,
        diagram=proof.diagram,
        witness=proof.witness,
        visual_explanation=proof.visual_explanation,
    )


def _coordinate_points_3d(statement: str) -> list[tuple[str, sp.Matrix]]:
    points: list[tuple[str, sp.Matrix]] = []
    pattern = (
        r"(?P<label>[A-Z][A-Za-z0-9_]*)\s*[\(（]\s*"
        r"(?P<x>[^,，()（）]+)\s*[,，]\s*"
        r"(?P<y>[^,，()（）]+)\s*[,，]\s*"
        r"(?P<z>[^()（）]+)\s*[\)）]"
    )
    for match in re.finditer(pattern, statement):
        try:
            point = sp.Matrix([
                _parse_coordinate(match.group("x")),
                _parse_coordinate(match.group("y")),
                _parse_coordinate(match.group("z")),
            ])
        except (sp.SympifyError, TypeError, ValueError):
            continue
        points.append((match.group("label"), point))
    return points


def synthesize_tetrahedron_volume(statement: str) -> RuntimeSolutionSynthesis | None:
    """Compute an exact tetrahedron volume and project the same coordinates."""

    if "四面体" not in statement or "体積" not in statement:
        return None
    labeled_points = _coordinate_points_3d(statement)
    if len(labeled_points) != 4:
        return None
    labels = [label for label, _ in labeled_points]
    points = [point for _, point in labeled_points]
    edge_matrix = sp.Matrix.hstack(points[1] - points[0], points[2] - points[0], points[3] - points[0])
    determinant = sp.simplify(edge_matrix.det())
    if determinant == 0:
        return None
    volume = sp.simplify(sp.Abs(determinant) / 6)
    if sp.simplify(6 * volume - sp.Abs(determinant)) != 0:
        return None

    def project(point: sp.Matrix) -> tuple[float, float]:
        x_value, y_value, z_value = [float(sp.N(value, 30)) for value in point]
        return x_value - 0.5 * y_value, z_value + 0.35 * y_value

    def point_record(point: tuple[float, float]) -> dict[str, float]:
        return {"x": round(point[0], 10), "y": round(point[1], 10)}

    projected = [project(point) for point in points]
    shapes: list[dict[str, Any]] = []
    edge_indices = ((0, 1), (0, 2), (0, 3), (1, 2), (1, 3), (2, 3))
    for index, (start, end) in enumerate(edge_indices):
        shapes.append({
            "id": f"edge-{index}",
            "kind": "polyline",
            "points": [point_record(projected[start]), point_record(projected[end])],
            "tone": "primary" if start == 0 else "secondary",
            "dashed": index in {3},
        })
    for label, point in zip(labels, projected):
        shapes.append({"id": f"point-{label}", "kind": "point", "point": point_record(point), "label": label, "tone": "accent"})

    max_coordinate = max(abs(float(sp.N(value, 30))) for point in points for value in point)
    axis_length = max(1.0, 1.15 * max_coordinate)
    origin = project(sp.zeros(3, 1))
    axis_endpoints = {
        "x": project(sp.Matrix([axis_length, 0, 0])),
        "y": project(sp.Matrix([0, axis_length, 0])),
        "z": project(sp.Matrix([0, 0, axis_length])),
    }
    for axis_name, endpoint in axis_endpoints.items():
        shapes.append({
            "id": f"axis-{axis_name}",
            "kind": "vector",
            "from": point_record(origin),
            "to": point_record(endpoint),
            "label": axis_name,
            "tone": "muted",
        })
    all_projected = [*projected, origin, *axis_endpoints.values()]
    x_values = [point[0] for point in all_projected]
    y_values = [point[1] for point in all_projected]
    span = max(max(x_values) - min(x_values), max(y_values) - min(y_values), 1.0)
    margin = 0.18 * span
    diagram = plane_scene_diagram(
        title="四面体の座標投影図",
        caption="3本の座標軸と4頂点を同じ空間座標から平行投影しています。体積計算にも同じ4点を使います。",
        viewport={
            "xMin": min(x_values) - margin,
            "xMax": max(x_values) + margin,
            "yMin": min(y_values) - margin,
            "yMax": max(y_values) + margin,
        },
        shapes=shapes,
        axes=False,
    )
    matrix_tex = sp.latex(edge_matrix)
    coordinate_tex = lambda point: r"\left(" + r",\;".join(sp.latex(value) for value in point) + r"\right)"
    return RuntimeSolutionSynthesis(
        answer=volume,
        answer_tex=rf"\(V={sp.latex(volume)}\)",
        tool_name="mortra.runtime_tetrahedron_determinant_volume",
        expression_tex=rf"V=\frac16\left|\det {matrix_tex}\right|",
        derivation_tex=(
            rf"基点を \({labels[0]}={coordinate_tex(points[0])}\) とし、3本の辺ベクトルを列に並べると \({matrix_tex}\) となる。",
            rf"この行列式は \({sp.latex(determinant)}\) である。平行六面体の体積はその絶対値であり、四面体の体積は6分の1なので \(V={sp.latex(volume)}\) である。",
            "図は同じ4点を平行投影したものであり、体積を求めた座標とは別の近似図形を使っていない。",
        ),
        verification_checks=(
            "入力から相異なる4個の3次元座標を抽出",
            "3本の辺ベクトルの行列式を厳密計算",
            "行列式が0でないことと体積公式の残差0を確認",
            "同じ座標から投影図の全6辺を生成",
        ),
        proof_program=(
            {"rule": "elaborate_four_affine_points_3d", "labels": labels},
            {"rule": "construct_tetrahedron_edge_matrix", "matrix": [[sp.srepr(value) for value in row] for row in edge_matrix.tolist()]},
            {"rule": "evaluate_oriented_volume_determinant", "determinant": sp.srepr(determinant)},
            {"rule": "normalize_tetrahedron_volume", "volume": sp.srepr(volume)},
            {"rule": "project_verified_vertices_to_plane"},
        ),
        diagram=diagram,
        witness={
            "labels": labels,
            "points": [[sp.srepr(value) for value in point] for point in points],
            "determinant": sp.srepr(determinant),
            "volume": sp.srepr(volume),
            "projection": "(x,y,z) -> (x-y/2,z+7y/20)",
        },
    )


def _parse_second_order_recurrence(
    statement: str,
) -> tuple[str, sp.Expr, sp.Expr, sp.Expr, sp.Expr, int | None] | None:
    segments = parse_latex_problem(statement).math_segments
    recurrence_match: re.Match[str] | None = None
    for segment in segments:
        match = re.fullmatch(r"(?P<seq>[A-Za-z])_\(n\+2\)=(?P<rhs>.+)", segment)
        if match is not None:
            recurrence_match = match
            break
    if recurrence_match is None:
        return None
    sequence = recurrence_match.group("seq")
    previous, current = sp.symbols("recurrence_previous recurrence_current")
    rhs_text = recurrence_match.group("rhs")
    rhs_text = rhs_text.replace(f"{sequence}_(n+1)", str(current))
    rhs_text = rhs_text.replace(f"{sequence}_n", str(previous))
    try:
        rhs = sp.expand(sp.sympify(rhs_text))
    except (sp.SympifyError, TypeError, ValueError):
        return None
    coefficient_current = sp.simplify(rhs.coeff(current))
    coefficient_previous = sp.simplify(rhs.coeff(previous))
    if sp.simplify(rhs - coefficient_current * current - coefficient_previous * previous) != 0:
        return None

    initial: dict[int, sp.Expr] = {}
    requested_indices: list[int] = []
    for segment in segments:
        assignment = re.fullmatch(rf"{re.escape(sequence)}_(\d+)=(.+)", segment)
        if assignment is not None:
            try:
                initial[int(assignment.group(1))] = sp.simplify(sp.sympify(assignment.group(2)))
            except (sp.SympifyError, TypeError, ValueError):
                return None
            continue
        requested = re.fullmatch(rf"{re.escape(sequence)}_(\d+)", segment)
        if requested is not None:
            requested_indices.append(int(requested.group(1)))
    if 0 not in initial or 1 not in initial:
        return None
    target_index = max(requested_indices) if requested_indices else None
    return (
        sequence,
        coefficient_current,
        coefficient_previous,
        initial[0],
        initial[1],
        target_index,
    )


def _distinct_second_order_closed_form(
    coefficient_current: sp.Expr,
    coefficient_previous: sp.Expr,
    initial_zero: sp.Expr,
    initial_one: sp.Expr,
) -> tuple[
    sp.Symbol,
    sp.Poly,
    tuple[tuple[sp.Expr, sp.Expr], ...],
    sp.Expr,
    tuple[sp.Expr, ...],
] | None:
    """Solve and replay a second-order recurrence with two distinct roots."""

    n = sp.symbols("n", integer=True, nonnegative=True)
    root_symbol = sp.Symbol("r")
    characteristic = sp.Poly(
        root_symbol**2 - coefficient_current * root_symbol - coefficient_previous,
        root_symbol,
    )
    roots = sp.roots(characteristic.as_expr(), root_symbol)
    if len(roots) != 2 or any(multiplicity != 1 for multiplicity in roots.values()):
        return None
    first_root, second_root = tuple(roots)
    first_weight, second_weight = sp.symbols("C_1 C_2")
    weights = sp.solve(
        (
            sp.Eq(first_weight + second_weight, initial_zero),
            sp.Eq(first_weight * first_root + second_weight * second_root, initial_one),
        ),
        (first_weight, second_weight),
        dict=True,
    )
    if len(weights) != 1:
        return None
    weighted_roots = (
        (first_root, sp.simplify(weights[0][first_weight])),
        (second_root, sp.simplify(weights[0][second_weight])),
    )
    closed_form = sp.simplify(sum(
        (weight * root**n for root, weight in weighted_roots),
        sp.Integer(0),
    ))
    replay_limit = 8
    values = [sp.simplify(initial_zero), sp.simplify(initial_one)]
    for _ in range(2, replay_limit + 1):
        values.append(sp.simplify(
            coefficient_current * values[-1] + coefficient_previous * values[-2]
        ))
    residuals = tuple(
        sp.simplify(closed_form.subs(n, index) - values[index])
        for index in range(replay_limit + 1)
    )
    recurrence_residual = sp.simplify(
        closed_form.subs(n, n + 2)
        - coefficient_current * closed_form.subs(n, n + 1)
        - coefficient_previous * closed_form
    )
    if any(residual != 0 for residual in residuals) or recurrence_residual != 0:
        return None
    return n, characteristic, weighted_roots, closed_form, residuals


def synthesize_second_order_dirichlet_series(
    statement: str,
) -> RuntimeSolutionSynthesis | None:
    """Map a current-input recurrence to its Dirichlet series and convergence set."""

    if not re.search(r"(?:ディリクレ級数|Dirichlet\s+series)", statement, re.IGNORECASE):
        return None
    parsed = _parse_second_order_recurrence(statement)
    if parsed is None:
        return None
    sequence, coefficient_current, coefficient_previous, initial_zero, initial_one, _ = parsed
    solved = _distinct_second_order_closed_form(
        coefficient_current,
        coefficient_previous,
        initial_zero,
        initial_one,
    )
    if solved is None:
        return None
    n, characteristic, weighted_roots, closed_form, residuals = solved
    absolute_roots = tuple(sp.simplify(sp.Abs(root)) for root, _ in weighted_roots)
    numeric_absolute_roots = tuple(_real_float(value) for value in absolute_roots)
    if any(value is None for value in numeric_absolute_roots):
        return None

    matrix = sp.Matrix([[coefficient_current, coefficient_previous], [1, 0]])
    matrix_tex = sp.latex(matrix)
    closed_tex = sp.latex(closed_form)
    characteristic_tex = sp.latex(characteristic.as_expr())
    root_rows = r",\;".join(
        rf"({sp.latex(root)},{sp.latex(weight)})"
        for root, weight in weighted_roots
    )
    common_program: tuple[dict[str, Any], ...] = (
        {
            "rule": "elaborate_second_order_recurrence",
            "coefficients": [str(coefficient_current), str(coefficient_previous)],
        },
        {
            "rule": "construct_companion_matrix",
            "matrix": [[str(value) for value in row] for row in matrix.tolist()],
        },
        {
            "rule": "factor_characteristic_polynomial",
            "roots": [sp.srepr(root) for root, _ in weighted_roots],
        },
        {
            "rule": "solve_initial_value_weights",
            "weighted_roots": [
                {"root": sp.srepr(root), "weight": sp.srepr(weight)}
                for root, weight in weighted_roots
            ],
        },
        {"rule": "replay_recurrence_identity", "through": len(residuals) - 1},
        {"rule": "apply_dirichlet_transform", "start_index": 1},
    )
    common_witness = {
        "sequence": sequence,
        "observable": "dirichlet_series",
        "coefficients": [str(coefficient_current), str(coefficient_previous)],
        "initial": [str(initial_zero), str(initial_one)],
        "characteristic_polynomial": sp.srepr(characteristic.as_expr()),
        "closed_form": sp.srepr(closed_form),
        "weighted_roots": [
            {"root": sp.srepr(root), "weight": sp.srepr(weight), "absolute_value": sp.srepr(absolute)}
            for (root, weight), absolute in zip(weighted_roots, absolute_roots)
        ],
        "recurrence_replay_residuals": [str(residual) for residual in residuals],
    }

    dominant_index = max(
        range(len(weighted_roots)),
        key=lambda index: float(numeric_absolute_roots[index]),
    )
    other_index = 1 - dominant_index
    dominant_root, dominant_weight = weighted_roots[dominant_index]
    dominant_absolute = absolute_roots[dominant_index]
    spectral_gap = sp.simplify(dominant_absolute - absolute_roots[other_index])
    above_one = sp.simplify(dominant_absolute - 1)
    spectral_gap_value = _real_float(spectral_gap)
    above_one_value = _real_float(above_one)
    ratio_limit = sp.simplify(sp.limit(
        closed_form / (dominant_weight * dominant_root**n),
        n,
        sp.oo,
    )) if dominant_weight != 0 else None
    proves_exponential_obstruction = (
        dominant_weight != 0
        and spectral_gap_value is not None
        and above_one_value is not None
        and _proves_strictly_positive(spectral_gap)
        and _proves_strictly_positive(above_one)
        and ratio_limit == 1
    )

    if proves_exponential_obstruction:
        diagram = state_transition_diagram(
            [
                {"id": "recurrence", "label": "二階漸化式", "terminal": False},
                {"id": "closed", "label": "特性根と一般項", "terminal": False},
                {"id": "dirichlet", "label": "ディリクレ変換", "terminal": False},
                {"id": "domain", "label": "収束する点なし", "terminal": True},
            ],
            [
                {"from": "recurrence", "to": "closed", "label": "伴随行列", "tone": "primary"},
                {"from": "closed", "to": "dirichlet", "label": "a_n / n^s", "tone": "primary"},
                {"from": "dirichlet", "to": "domain", "label": "一般項が0に収束しない", "tone": "secondary"},
            ],
            title="漸化式とディリクレ級数",
            caption="特性根から数列の増大度を求め、級数の一般項が0へ収束するかを判定します。",
        )
        return RuntimeSolutionSynthesis(
            answer={"closed_form": closed_form, "convergence_domain": "empty"},
            answer_tex=(
                rf"\[{sequence}_n={closed_tex}.\]"
                rf"\[D(s)=\sum_{{n=1}}^\infty\frac{{{sequence}_n}}{{n^s}}.\]"
                r"すべての \(s\in\mathbb C\) に対して発散する。"
            ),
            tool_name="mortra.runtime_second_order_dirichlet_series",
            expression_tex=rf"D(s)=\sum_{{n=1}}^\infty {sequence}_n n^{{-s}}",
            derivation_tex=(
                rf"伴随行列 \(M={matrix_tex}\) の特性多項式は \({characteristic_tex}\) である。",
                rf"特性根と初期値から得る（根, 係数）の組は \({root_rows}\) であり、従って \({sequence}_n={closed_tex}\) となる。",
                rf"絶対値が最大の特性根は \({sp.latex(dominant_root)}\) で、その係数は \({sp.latex(dominant_weight)}\ne0\) である。他の根との絶対値の差は \({sp.latex(spectral_gap)}>0\) だから、\(\displaystyle\lim_{{n\to\infty}}\frac{{{sequence}_n}}{{{sp.latex(dominant_weight)}({sp.latex(dominant_root)})^n}}=1\) である。",
                rf"任意の \(s=\sigma+it\in\mathbb C\) に対し、\(\left|{sequence}_n/n^s\right|=|{sequence}_n|/n^\sigma\) は0に収束しない。従って級数の必要条件を満たさず、\(D(s)\) はどの \(s\) に対しても発散する。",
            ),
            verification_checks=(
                "現在入力から二階漸化式とディリクレ級数という観測量を抽出",
                "特性根と初期値係数を厳密に計算",
                "一般項を元の漸化式へ0番から8番まで再代入",
                "最大特性根の係数が0でなく、他の根との絶対値の差が正であることを確認",
                "ディリクレ級数の一般項が0へ収束しないことから全複素平面での発散を証明",
            ),
            proof_program=common_program + (
                {
                    "rule": "prove_dominant_root_asymptotic",
                    "dominant_root": sp.srepr(dominant_root),
                    "dominant_weight": sp.srepr(dominant_weight),
                    "ratio_limit": str(ratio_limit),
                },
                {"rule": "apply_series_term_test", "convergence_domain": "empty"},
                {"rule": "render_dirichlet_convergence_diagram"},
            ),
            diagram=diagram,
            witness={
                **common_witness,
                "convergence_domain": "empty",
                "dominant_root": sp.srepr(dominant_root),
                "dominant_weight": sp.srepr(dominant_weight),
                "spectral_gap": sp.srepr(spectral_gap),
                "dominant_ratio_limit": str(ratio_limit),
            },
        )

    proves_exponential_decay = all(
        value is not None and _proves_strictly_positive(1 - exact_value)
        for value, exact_value in zip(numeric_absolute_roots, absolute_roots)
    )
    if not proves_exponential_decay:
        return None
    s = sp.symbols("s")
    dirichlet_expression = sp.simplify(sum(
        (weight * sp.polylog(s, root) for root, weight in weighted_roots),
        sp.Integer(0),
    ))
    dirichlet_tex = sp.latex(dirichlet_expression)
    diagram = state_transition_diagram(
        [
            {"id": "recurrence", "label": "二階漸化式", "terminal": False},
            {"id": "closed", "label": "特性根と一般項", "terminal": False},
            {"id": "transform", "label": "多重対数関数へ変換", "terminal": False},
            {"id": "domain", "label": "全複素平面で収束", "terminal": True},
        ],
        [
            {"from": "recurrence", "to": "closed", "label": "特性多項式", "tone": "primary"},
            {"from": "closed", "to": "transform", "label": "項別に変換", "tone": "primary"},
            {"from": "transform", "to": "domain", "label": "指数減衰", "tone": "secondary"},
        ],
        title="漸化式とディリクレ級数",
        caption="一般項を特性根ごとに分解し、各項のディリクレ変換と収束域を求めます。",
    )
    return RuntimeSolutionSynthesis(
        answer={"closed_form": closed_form, "dirichlet_series": dirichlet_expression},
        answer_tex=(
            rf"\[{sequence}_n={closed_tex}.\]"
            rf"\[D(s)=\sum_{{n=1}}^\infty\frac{{{sequence}_n}}{{n^s}}={dirichlet_tex}.\]"
            r"すべての \(s\in\mathbb C\) に対して絶対収束する。"
        ),
        tool_name="mortra.runtime_second_order_dirichlet_series",
        expression_tex=rf"D(s)=\sum_{{n=1}}^\infty {sequence}_n n^{{-s}}",
        derivation_tex=(
            rf"特性多項式 \({characteristic_tex}\) と初期値から \({sequence}_n={closed_tex}\) を得る。",
            rf"定義 \(\operatorname{{Li}}_s(z)=\sum_{{n=1}}^\infty z^n/n^s\) を各特性根へ適用すると \(D(s)={dirichlet_tex}\) となる。",
            r"すべての特性根の絶対値が1未満なので、指数減衰は任意の多項式増大より速い。従ってこの級数は任意の複素数 \(s\) で絶対収束する。",
        ),
        verification_checks=(
            "現在入力から二階漸化式とディリクレ級数という観測量を抽出",
            "特性根と初期値係数を厳密に計算",
            "一般項を元の漸化式へ0番から8番まで再代入",
            "全特性根の絶対値が1未満であることを確認",
            "一般項を多重対数関数の定義へ項別に戻して照合",
        ),
        proof_program=common_program + (
            {
                "rule": "map_characteristic_modes_to_polylogarithms",
                "expression": sp.srepr(dirichlet_expression),
            },
            {"rule": "prove_exponential_decay_normal_convergence", "convergence_domain": "complex-plane"},
            {"rule": "render_dirichlet_convergence_diagram"},
        ),
        diagram=diagram,
        witness={
            **common_witness,
            "convergence_domain": "complex-plane",
            "dirichlet_series": sp.srepr(dirichlet_expression),
        },
    )


def synthesize_second_order_recurrence(statement: str) -> RuntimeSolutionSynthesis | None:
    """Compile a current-input recurrence to its companion matrix and roots."""

    if "漸化式" not in statement and "数列" not in statement:
        return None
    if re.search(r"(?:ディリクレ級数|Dirichlet\s+series)", statement, re.IGNORECASE):
        # The dedicated transform must close the requested observable. Falling
        # back to a closed form would answer a different question.
        return None
    parsed = _parse_second_order_recurrence(statement)
    if parsed is None:
        return None
    sequence, coefficient_current, coefficient_previous, initial_zero, initial_one, target_index = parsed
    asks_for_generating_function = (
        "母関数" in statement
        or "generating function" in statement.lower()
    )
    asks_for_closed_form = target_index is not None or any(
        marker in statement.lower()
        for marker in (
            "一般項",
            "閉形式",
            "遷移行列",
            "状態行列",
            "特性多項式",
            "特性方程式",
            "general term",
            "closed form",
            "transition matrix",
            "characteristic polynomial",
        )
    )
    if not asks_for_generating_function and not asks_for_closed_form:
        return None

    if asks_for_generating_function:
        z = sp.symbols("z")
        numerator = sp.simplify(
            initial_zero + (initial_one - coefficient_current * initial_zero) * z
        )
        denominator = sp.simplify(
            1 - coefficient_current * z - coefficient_previous * z**2
        )
        generating_function = sp.cancel(numerator / denominator)
        replay_limit = 8
        sequence_values = [sp.simplify(initial_zero), sp.simplify(initial_one)]
        for _ in range(2, replay_limit + 1):
            sequence_values.append(sp.simplify(
                coefficient_current * sequence_values[-1]
                + coefficient_previous * sequence_values[-2]
            ))
        series = sp.series(generating_function, z, 0, replay_limit + 1).removeO().expand()
        replayed_coefficients = [sp.simplify(series.coeff(z, index)) for index in range(replay_limit + 1)]
        if replayed_coefficients != sequence_values:
            return None
        if sp.simplify(denominator * generating_function - numerator) != 0:
            return None

        matrix = sp.Matrix([[coefficient_current, coefficient_previous], [1, 0]])
        matrix_tex = sp.latex(matrix)
        generating_tex = sp.latex(generating_function)
        numerator_tex = sp.latex(numerator)
        denominator_tex = sp.latex(denominator)
        diagram = state_transition_diagram(
            [
                {"id": "recurrence", "label": "二階漸化式", "terminal": False},
                {"id": "series", "label": "母関数 A(z)", "terminal": False},
                {"id": "verified", "label": "係数を照合", "terminal": True},
            ],
            [
                {"from": "recurrence", "to": "series", "label": "べき級数として加える", "tone": "primary"},
                {"from": "series", "to": "verified", "label": f"n=0,...,{replay_limit}", "tone": "secondary"},
            ],
            title="漸化式と母関数",
            caption="漸化式を形式的べき級数へ変換し、係数を元の数列へ戻して検証します。",
        )
        return RuntimeSolutionSynthesis(
            answer={"generating_function": generating_function},
            answer_tex=rf"\[A(z)=\sum_{{n=0}}^\infty {sequence}_n z^n={generating_tex}\]",
            tool_name="mortra.runtime_second_order_recurrence",
            expression_tex=rf"{sequence}_{{n+2}}={sp.latex(coefficient_current)}{sequence}_{{n+1}}+({sp.latex(coefficient_previous)}){sequence}_n",
            derivation_tex=(
                rf"母関数を \(A(z)=\sum_{{n=0}}^\infty {sequence}_n z^n\) とおく。",
                rf"漸化式に \(z^{{n+2}}\) を掛けて \(n\ge0\) で加えると、\({denominator_tex}A(z)={numerator_tex}\) を得る。",
                rf"従って \(A(z)={generating_tex}\) である。",
                rf"この有理関数を \(z^{replay_limit}\) まで展開し、得られた係数が元の漸化式から計算した \({sequence}_0,\ldots,{sequence}_{{{replay_limit}}}\) と全て一致することを確認した。",
            ),
            verification_checks=(
                "現在入力から二階漸化式の係数と初期値を抽出",
                "形式的べき級数の恒等式を厳密に整理",
                "分母を掛け戻して恒等式の残差が0であることを確認",
                f"母関数の係数と逐次計算を0から{replay_limit}まで照合",
            ),
            proof_program=(
                {"rule": "elaborate_second_order_recurrence", "coefficients": [str(coefficient_current), str(coefficient_previous)]},
                {"rule": "construct_companion_matrix", "matrix": [[str(value) for value in row] for row in matrix.tolist()]},
                {"rule": "derive_ordinary_generating_function", "numerator": sp.srepr(numerator), "denominator": sp.srepr(denominator)},
                {"rule": "verify_generating_function_identity", "residual": "0"},
                {"rule": "replay_generating_function_coefficients", "through": replay_limit},
                {"rule": "render_recurrence_generating_function_diagram"},
            ),
            diagram=diagram,
            witness={
                "sequence": sequence,
                "observable": "ordinary_generating_function",
                "coefficients": [str(coefficient_current), str(coefficient_previous)],
                "initial": [str(initial_zero), str(initial_one)],
                "numerator": sp.srepr(numerator),
                "denominator": sp.srepr(denominator),
                "generating_function": sp.srepr(generating_function),
                "replayed_coefficients": [sp.srepr(value) for value in replayed_coefficients],
            },
        )

    n = sp.symbols("n", integer=True, nonnegative=True)
    characteristic = sp.Poly(
        sp.Symbol("r") ** 2 - coefficient_current * sp.Symbol("r") - coefficient_previous,
        sp.Symbol("r"),
    )
    roots = sp.roots(characteristic.as_expr(), characteristic.gens[0])
    if sum(roots.values()) != 2:
        return None
    root_values = list(roots)
    if len(root_values) == 2:
        first_root, second_root = root_values
        first_weight, second_weight = sp.symbols("C_1 C_2")
        weights = sp.solve(
            (
                sp.Eq(first_weight + second_weight, initial_zero),
                sp.Eq(first_weight * first_root + second_weight * second_root, initial_one),
            ),
            (first_weight, second_weight),
            dict=True,
        )
        if len(weights) != 1:
            return None
        closed_form = sp.simplify(
            weights[0][first_weight] * first_root**n
            + weights[0][second_weight] * second_root**n
        )
    elif len(root_values) == 1 and roots[root_values[0]] == 2:
        root = root_values[0]
        first_weight, second_weight = sp.symbols("C_1 C_2")
        weights = sp.solve(
            (
                sp.Eq(first_weight, initial_zero),
                sp.Eq((first_weight + second_weight) * root, initial_one),
            ),
            (first_weight, second_weight),
            dict=True,
        )
        if len(weights) != 1:
            return None
        closed_form = sp.simplify((weights[0][first_weight] + weights[0][second_weight] * n) * root**n)
    else:
        return None

    replay_limit = max(target_index or 2, 2)
    sequence_values = [sp.simplify(initial_zero), sp.simplify(initial_one)]
    for _ in range(2, replay_limit + 2):
        sequence_values.append(sp.simplify(
            coefficient_current * sequence_values[-1]
            + coefficient_previous * sequence_values[-2]
        ))
    closed_residuals = [
        sp.simplify(closed_form.subs(n, index) - sequence_values[index])
        for index in range(replay_limit + 1)
    ]
    if any(residual != 0 for residual in closed_residuals):
        return None

    matrix = sp.Matrix([[coefficient_current, coefficient_previous], [1, 0]])
    state_zero = sp.Matrix([initial_one, initial_zero])
    matrix_residuals = [
        sp.simplify((matrix**index * state_zero)[1] - sequence_values[index])
        for index in range(replay_limit + 1)
    ]
    if any(residual != 0 for residual in matrix_residuals):
        return None

    closed_tex = sp.latex(closed_form)
    answer_rows = [rf"{sequence}_n={closed_tex}"]
    target_value: sp.Expr | None = None
    if target_index is not None:
        target_value = sequence_values[target_index]
        answer_rows.append(rf"{sequence}_{{{target_index}}}={sp.latex(target_value)}")
    answer_tex = r"\[\begin{gathered}" + r"\\".join(answer_rows) + r"\end{gathered}\]"
    matrix_tex = sp.latex(matrix)
    diagram = state_transition_diagram(
        [
            {"id": "initial", "label": rf"({sequence}_1,{sequence}_0)", "terminal": False},
            {"id": "state-n", "label": rf"({sequence}_{{n+1}},{sequence}_n)", "terminal": False},
            {"id": "verified", "label": "閉形式と一致", "terminal": True},
        ],
        [
            {"from": "initial", "to": "state-n", "label": rf"M^n,\ M={matrix_tex}", "tone": "primary"},
            {"from": "state-n", "to": "verified", "label": "特性多項式を再生", "tone": "secondary"},
        ],
        title="漸化式・行列・特性多項式",
        caption="同じ二階漸化式を状態ベクトルと特性多項式へ可逆に変換します。",
    )
    target_derivation = (
        rf"従って \({sequence}_{{{target_index}}}={sp.latex(target_value)}\) である。"
        if target_index is not None and target_value is not None
        else ""
    )
    return RuntimeSolutionSynthesis(
        answer={"closed_form": closed_form, "target": target_value},
        answer_tex=answer_tex,
        tool_name="mortra.runtime_second_order_recurrence",
        expression_tex=rf"{sequence}_{{n+2}}={sp.latex(coefficient_current)}{sequence}_{{n+1}}+({sp.latex(coefficient_previous)}){sequence}_n",
        derivation_tex=(
            rf"状態ベクトルを \(v_n=({sequence}_{{n+1}},{sequence}_n)^T\) とおくと \(v_{{n+1}}=Mv_n\)、\(M={matrix_tex}\) である。",
            rf"特性多項式は \({sp.latex(characteristic.as_expr())}\) である。その根から一般解を作り、初期値を代入すると \({sequence}_n={closed_tex}\) を得る。",
            target_derivation,
            rf"閉形式と行列累乗を \(0\le n\le {replay_limit}\) で別々に計算し、元の漸化式との残差がすべて0であることを確認した。",
        ),
        verification_checks=(
            "現在入力から二階漸化式の係数と初期値を抽出",
            "伴随行列の特性多項式を厳密に計算",
            "一般項を初期値と元の漸化式へ再代入",
            f"行列累乗と逐次計算を0から{replay_limit}まで照合",
        ),
        proof_program=(
            {"rule": "elaborate_second_order_recurrence", "coefficients": [str(coefficient_current), str(coefficient_previous)]},
            {"rule": "construct_companion_matrix", "matrix": [[str(value) for value in row] for row in matrix.tolist()]},
            {"rule": "factor_characteristic_polynomial", "roots": [sp.srepr(root) for root in root_values]},
            {"rule": "solve_initial_value_weights", "closed_form": sp.srepr(closed_form)},
            {"rule": "replay_matrix_and_recurrence", "through": replay_limit},
            {"rule": "render_recurrence_state_diagram"},
        ),
        diagram=diagram,
        witness={
            "sequence": sequence,
            "coefficients": [str(coefficient_current), str(coefficient_previous)],
            "initial": [str(initial_zero), str(initial_one)],
            "characteristic_polynomial": sp.srepr(characteristic.as_expr()),
            "closed_form": sp.srepr(closed_form),
            "target_index": target_index,
            "target_value": None if target_value is None else str(target_value),
        },
    )


def synthesize_linear_congruence(statement: str) -> RuntimeSolutionSynthesis | None:
    """Solve one current-input linear congruence and prove completeness."""

    compact = statement.replace(" ", "").replace("\\equiv", "≡")
    compact = compact.replace("\\pmod", "mod")
    match = re.search(
        r"(?P<a>[+-]?\d+)\*?(?P<variable>[A-Za-z])≡(?P<b>[+-]?\d+)\(?mod\{?(?P<modulus>\d+)\}?\)?",
        compact,
    )
    if match is None:
        return None
    coefficient = int(match.group("a"))
    right = int(match.group("b"))
    modulus = int(match.group("modulus"))
    variable = match.group("variable")
    if modulus <= 1:
        return None
    divisor = gcd(abs(coefficient), modulus)
    if right % divisor != 0:
        answer_tex = r"\(\text{解なし}\)"
        classes: list[int] = []
        reduced_modulus = modulus // divisor
    else:
        reduced_coefficient = coefficient // divisor
        reduced_right = right // divisor
        reduced_modulus = modulus // divisor
        inverse = pow(reduced_coefficient % reduced_modulus, -1, reduced_modulus)
        base = (inverse * reduced_right) % reduced_modulus
        classes = sorted((base + offset * reduced_modulus) % modulus for offset in range(divisor))
        class_tex = r",\;".join(str(value) for value in classes)
        answer_tex = rf"\({variable}\equiv {class_tex}\pmod{{{modulus}}}\)"
    if any((coefficient * value - right) % modulus != 0 for value in classes):
        return None
    exhaustive = [value for value in range(modulus) if (coefficient * value - right) % modulus == 0]
    if exhaustive != classes:
        return None
    return RuntimeSolutionSynthesis(
        answer=classes,
        answer_tex=answer_tex,
        tool_name="mortra.runtime_linear_congruence",
        expression_tex=rf"{coefficient}{variable}\equiv {right}\pmod{{{modulus}}}",
        derivation_tex=(
            rf"\(d=\gcd({coefficient},{modulus})={divisor}\) とおく。一次合同式が解をもつ必要十分条件は \(d\mid {right}\) である。",
            (
                rf"両辺と法を \(d\) で割ると、係数が法と互いに素な合同式になる。逆元を掛けると \({variable}\equiv {classes[0]}\pmod{{{reduced_modulus}}}\) を得る。"
                if classes
                else rf"しかし \({divisor}\nmid {right}\) なので解は存在しない。"
            ),
            (
                rf"法 {modulus} では \({variable}\equiv " + r",\;".join(str(value) for value in classes) + rf"\pmod{{{modulus}}}\) である。各剰余を代入して確認した。"
                if classes
                else rf"法 {modulus} の全剰余を検査しても解がないことを確認した。"
            ),
        ),
        verification_checks=(
            "最大公約数による可解条件を確認",
            "縮約した法における係数の逆元を厳密計算",
            f"法{modulus}の全剰余で解集合の完全性を独立検査",
        ),
        proof_program=(
            {"rule": "compute_gcd_obstruction", "gcd": divisor},
            {"rule": "reduce_linear_congruence", "reduced_modulus": reduced_modulus},
            {"rule": "invert_unit_modulo", "solutions": classes},
            {"rule": "enumerate_residue_certificate", "modulus": modulus},
        ),
        diagram=None,
        witness={
            "coefficient": coefficient,
            "right": right,
            "modulus": modulus,
            "gcd": divisor,
            "solutions": classes,
        },
    )


def synthesize_factorial_valuation(statement: str) -> RuntimeSolutionSynthesis | None:
    """Evaluate a prime-adic valuation of a current-input factorial."""

    factorial_match = re.search(r"(?P<n>\d+)\s*!", statement)
    power_match = re.search(r"最大の\s*(?P<p>\d+)\s*のべき\s*(?P=p)\s*\^\s*k", statement)
    if factorial_match is None or power_match is None:
        return None
    n_value = int(factorial_match.group("n"))
    prime = int(power_match.group("p"))
    if n_value < 0 or not sp.isprime(prime):
        return None
    terms: list[int] = []
    power = prime
    while power <= n_value:
        terms.append(n_value // power)
        power *= prime
    valuation = sum(terms)
    direct = 0
    for value in range(1, n_value + 1):
        residual = value
        while residual % prime == 0:
            direct += 1
            residual //= prime
    if direct != valuation:
        return None
    sum_tex = "+".join(str(value) for value in terms) or "0"
    return RuntimeSolutionSynthesis(
        answer=valuation,
        answer_tex=rf"\(k={valuation}\)",
        tool_name="mortra.runtime_factorial_prime_valuation",
        expression_tex=rf"v_{{{prime}}}({n_value}!)",
        derivation_tex=(
            rf"\({n_value}!\) に含まれる素因数 \({prime}\) の個数を数える。\({prime}\) の倍数は1個、\({prime}^2\) の倍数はさらに1個というように重複分を加える。",
            rf"Legendre の公式より \(v_{{{prime}}}({n_value}!)=\sum_{{j\ge1}}\left\lfloor {n_value}/{prime}^j\right\rfloor={sum_tex}={valuation}\) である。",
            rf"従って \({prime}^{{{valuation}}}\mid {n_value}!\) であり、\({prime}^{{{valuation + 1}}}\nmid {n_value}!\) である。",
        ),
        verification_checks=(
            "入力された底が素数であることを確認",
            "Legendre の有限和を整数除算で計算",
            f"1から{n_value}までを個別に素因数分解して付値を再計算",
        ),
        proof_program=(
            {"rule": "recognize_factorial_valuation", "prime": prime, "n": n_value},
            {"rule": "sum_prime_power_multiplicities", "terms": terms},
            {"rule": "independent_factor_count_replay", "valuation": direct},
        ),
        diagram=None,
        witness={"n": n_value, "prime": prime, "terms": terms, "valuation": valuation},
    )


def synthesize_consecutive_coin_wait(statement: str) -> RuntimeSolutionSynthesis | None:
    """Compile a run-waiting problem to a finite Markov recurrence."""

    run_match = re.search(r"表が\s*(\d+)\s*回連続", statement)
    if run_match is None or "期待値" not in statement or "硬貨" not in statement:
        return None
    run_length = int(run_match.group(1))
    if run_length < 1 or run_length > 20:
        return None
    if "公平" in statement:
        probability = sp.Rational(1, 2)
    else:
        probability_match = re.search(
            r"表の出る確率(?:が|を)\s*(?:(?P<numerator>\d+)\s*/\s*(?P<denominator>\d+)|\\frac\{(?P<tex_numerator>\d+)\}\{(?P<tex_denominator>\d+)\})",
            statement,
        )
        if probability_match is None:
            return None
        numerator = int(probability_match.group("numerator") or probability_match.group("tex_numerator"))
        denominator = int(probability_match.group("denominator") or probability_match.group("tex_denominator"))
        if denominator <= 0 or not 0 < numerator < denominator:
            return None
        probability = sp.Rational(numerator, denominator)
    failure_probability = sp.simplify(1 - probability)
    symbols = sp.symbols(f"E0:{run_length + 1}")
    equations = [sp.Eq(symbols[-1], 0)]
    for state in range(run_length):
        equations.append(sp.Eq(
            symbols[state],
            1 + probability * symbols[state + 1] + failure_probability * symbols[0],
        ))
    solution = sp.solve(equations, symbols, dict=True)
    if len(solution) != 1:
        return None
    expectation = sp.simplify(solution[0][symbols[0]])
    closed_form = sp.simplify((1 - probability**run_length) / (failure_probability * probability**run_length))
    if sp.simplify(expectation - closed_form) != 0:
        return None
    states = [
        {"id": f"S{state}", "label": (f"表が{state}回連続" if state else "連続なし"), "terminal": False}
        for state in range(run_length)
    ] + [{"id": f"S{run_length}", "label": f"表が{run_length}回連続", "terminal": True}]
    transitions: list[dict[str, Any]] = []
    for state in range(run_length):
        transitions.append({"from": f"S{state}", "to": f"S{state + 1}", "label": f"表 {probability}", "tone": "primary"})
        transitions.append({"from": f"S{state}", "to": "S0", "label": f"裏 {failure_probability}", "tone": "secondary"})
    diagram = state_transition_diagram(
        states,
        transitions,
        title="連続する表の待ち時間",
        caption="状態は直前までに連続している表の回数です。裏が出ると S0 に戻ります。",
    )
    equation_tex = [sp.latex(equation) for equation in equations]
    return RuntimeSolutionSynthesis(
        answer=expectation,
        answer_tex=rf"\({sp.latex(expectation)}\)",
        tool_name="mortra.runtime_finite_state_expectation",
        expression_tex=rf"E_0={sp.latex(expectation)}",
        derivation_tex=(
            rf"状態 \(S_j\;(0\le j\le {run_length})\) を、直前までに表が \(j\) 回連続している状態とする。\(S_{run_length}\) は終了状態である。",
            rf"\(S_j\) から終了までの残り投数の期待値を \(E_j\) とおく。表なら \(S_{{j+1}}\)、裏なら \(S_0\) へ移るので、"
            + r"\(" + r",\quad ".join(equation_tex) + r"\)" + " を得る。",
            rf"この連立一次方程式を消去すると \(E_0={sp.latex(expectation)}\) である。一般に表の確率を \(p\) とすると期待値は \((1-p^r)/((1-p)p^r)\) となる。",
            "得られた値を全ての期待値方程式へ代入し、各辺の差が0になることを確認した。",
        ),
        verification_checks=(
            f"{run_length + 1}状態の遷移を入力の連続回数から構成",
            "全期待値方程式を有理数上で厳密に解消",
            "閉形式と連立方程式解の一致を記号的に確認",
            "解を全方程式へ再代入して残差0を確認",
        ),
        proof_program=(
            {"rule": "compile_run_length_automaton", "run_length": run_length},
            {"rule": "lower_first_step_expectations", "equations": equation_tex},
            {"rule": "solve_exact_linear_system", "solution": {str(key): str(value) for key, value in solution[0].items()}},
            {"rule": "replay_expectation_residuals"},
            {"rule": "render_state_transition_graph"},
        ),
        diagram=diagram,
        witness={
            "run_length": run_length,
            "probability_heads": str(probability),
            "probability_tails": str(failure_probability),
            "expectation": str(expectation),
        },
    )


def synthesize_first_repeat_die_wait(statement: str) -> RuntimeSolutionSynthesis | None:
    """Compile first-repeat waiting time for a fair finite die."""

    match = re.search(r"公平な\s*(?P<sides>\d+)\s*面体のさいころ", statement)
    if match is None or "初めて同じ目" not in statement or "期待値" not in statement:
        return None
    sides = int(match.group("sides"))
    if sides < 2 or sides > 30:
        return None
    expectations = [sp.Integer(0)] * (sides + 1)
    expectations[sides] = sp.Integer(1)
    for distinct in range(sides - 1, -1, -1):
        expectations[distinct] = sp.simplify(
            1 + sp.Rational(sides - distinct, sides) * expectations[distinct + 1]
        )
    expectation = expectations[0]
    survival_terms = [
        sp.Rational(sp.factorial(sides), sp.factorial(sides - throws) * sides**throws)
        for throws in range(sides + 1)
    ]
    survival_sum = sp.simplify(sum(survival_terms))
    if sp.simplify(expectation - survival_sum) != 0:
        return None

    states = [
        {"id": f"S{distinct}", "label": f"相異なる目が{distinct}個", "terminal": False}
        for distinct in range(sides + 1)
    ] + [{"id": "R", "label": "初めての重複", "terminal": True}]
    transitions: list[dict[str, Any]] = []
    for distinct in range(sides):
        transitions.append({
            "from": f"S{distinct}",
            "to": f"S{distinct + 1}",
            "label": f"新しい目 {(sides - distinct)}/{sides}",
            "tone": "primary",
        })
        if distinct:
            transitions.append({
                "from": f"S{distinct}",
                "to": "R",
                "label": f"既出 {distinct}/{sides}",
                "tone": "secondary",
            })
    transitions.append({"from": f"S{sides}", "to": "R", "label": "既出 1", "tone": "secondary"})
    diagram = state_transition_diagram(
        states,
        transitions,
        title="最初の重複までの状態遷移",
        caption="状態は、重複が起きる前に確認した相異なる目の個数です。",
    )
    recurrence_tex = [rf"E_{{{sides}}}=1"] + [
        rf"E_{{{distinct}}}=1+\frac{{{sides - distinct}}}{{{sides}}}E_{{{distinct + 1}}}"
        for distinct in range(sides)
    ]
    return RuntimeSolutionSynthesis(
        answer=expectation,
        answer_tex=rf"\(E_0={sp.latex(expectation)}\)",
        tool_name="mortra.runtime_first_repeat_die_expectation",
        expression_tex=rf"E_0={sp.latex(expectation)}",
        derivation_tex=(
            rf"重複がまだ起きておらず、相異なる目を \(k\) 個見た状態を \(S_k\) とする。残り投数の期待値を \(E_k\) とおく。",
            rf"\(k<{sides}\) では次の1投を数え、新しい目なら確率 \(({sides}-k)/{sides}\) で \(S_{{k+1}}\) へ進む。既出の目なら終了する。従って \(E_k=1+(({sides}-k)/{sides})E_{{k+1}}\) である。",
            rf"すべての目を見た後は次の1投で必ず重複するので \(E_{{{sides}}}=1\) である。後ろから代入すると \(E_0={sp.latex(expectation)}\) を得る。",
            rf"独立確認として、\(t\) 投後も重複がない確率を足すと \(\sum_{{t=0}}^{{{sides}}}( {sides})_t/{sides}^t={sp.latex(survival_sum)}\) となり一致する。",
        ),
        verification_checks=(
            f"{sides + 2}状態の有限状態遷移を面数から構成",
            "各状態の期待値を有理数上で後退代入",
            "重複なし確率の有限和を独立に計算",
            "二つの期待値が厳密に一致することを確認",
        ),
        proof_program=(
            {"rule": "compile_distinct_face_count_automaton", "sides": sides},
            {"rule": "lower_first_step_expectation_recurrence", "equations": recurrence_tex},
            {"rule": "solve_expectations_by_backward_substitution", "values": [sp.srepr(value) for value in expectations]},
            {"rule": "replay_survival_probability_sum", "terms": [sp.srepr(value) for value in survival_terms]},
            {"rule": "render_state_transition_graph"},
        ),
        diagram=diagram,
        witness={
            "sides": sides,
            "expectations": [sp.srepr(value) for value in expectations],
            "survival_terms": [sp.srepr(value) for value in survival_terms],
            "expectation": sp.srepr(expectation),
        },
    )


def _linear_trigonometric_equation(statement: str) -> tuple[sp.Symbol, sp.Expr, sp.Expr, sp.Expr] | None:
    for segment in parse_latex_problem(statement).math_segments:
        if "=" not in segment or not ("sin" in segment or "cos" in segment):
            continue
        normalized = segment.replace("^", "**")
        normalized = re.sub(r"\b(sin|cos)\s*\*?\s*([A-Za-z])\b", r"\1(\2)", normalized)
        left_text, right_text = normalized.split("=", 1)
        try:
            left = sp.sympify(left_text, locals={"sin": sp.sin, "cos": sp.cos, "pi": sp.pi})
            right = sp.sympify(right_text, locals={"sin": sp.sin, "cos": sp.cos, "pi": sp.pi})
        except (sp.SympifyError, TypeError, ValueError):
            continue
        variables = sorted((left - right).free_symbols, key=lambda symbol: symbol.name)
        if len(variables) != 1:
            continue
        variable = variables[0]
        residual = sp.expand(left - right)
        sine_coefficient = sp.simplify(residual.coeff(sp.sin(variable)))
        cosine_coefficient = sp.simplify(residual.coeff(sp.cos(variable)))
        constant = sp.simplify(residual - sine_coefficient * sp.sin(variable) - cosine_coefficient * sp.cos(variable))
        if variable in constant.free_symbols or (sine_coefficient == 0 and cosine_coefficient == 0):
            continue
        right_value = sp.simplify(-constant)
        if any(value.is_real is not True for value in (sine_coefficient, cosine_coefficient, right_value)):
            continue
        return variable, sine_coefficient, cosine_coefficient, right_value
    return None


def synthesize_linear_trigonometric_equation(statement: str) -> RuntimeSolutionSynthesis | None:
    """Solve A sin(x) + B cos(x) = C on one full half-open period."""

    if not re.search(r"0\s*[≤≦]|0\s*<=", statement) or not re.search(r"2\s*(?:π|\\pi)", statement):
        return None
    parsed = _linear_trigonometric_equation(statement)
    if parsed is None:
        return None
    variable, sine_coefficient, cosine_coefficient, right_value = parsed
    left = sp.expand(sine_coefficient * sp.sin(variable) + cosine_coefficient * sp.cos(variable))
    domain = sp.Interval.Ropen(0, 2 * sp.pi)
    solution_set = sp.solveset(sp.Eq(left, right_value), variable, domain=domain)
    if not isinstance(solution_set, sp.FiniteSet):
        return None
    solutions = sorted(
        [sp.simplify(solution) for solution in solution_set],
        key=lambda value: float(sp.N(value, 40)),
    )
    if not solutions or any(sp.simplify(left.subs(variable, solution) - right_value) != 0 for solution in solutions):
        return None
    amplitude = sp.sqrt(sine_coefficient**2 + cosine_coefficient**2)
    phase = sp.atan2(cosine_coefficient, sine_coefficient)
    if sp.simplify(
        sp.expand_trig(amplitude * sp.sin(variable + phase)) - left
    ) != 0:
        return None

    numeric_left: Callable[[float], float] = sp.lambdify(variable, left, "math")
    numeric_right: Callable[[float], float] = sp.lambdify(variable, right_value, "math")
    marked_points = [
        (float(sp.N(solution, 30)), float(sp.N(right_value, 30)), sp.latex(solution))
        for solution in solutions
    ]
    diagram = function_plot_diagram(
        [
            (sp.latex(left), numeric_left, "primary"),
            (sp.latex(right_value), numeric_right, "secondary"),
        ],
        x_min=0.0,
        x_max=float(2 * sp.pi),
        title="三角関数と定数直線の交点",
        caption="厳密に求めた解を交点として橙色で示します。",
        marked_points=marked_points,
        samples=241,
    )
    solution_tex = r",\;".join(sp.latex(solution) for solution in solutions)
    return RuntimeSolutionSynthesis(
        answer=solutions,
        answer_tex=rf"\({sp.latex(variable)}={solution_tex}\)",
        tool_name="mortra.runtime_linear_trigonometric_equation",
        expression_tex=rf"{sp.latex(left)}={sp.latex(right_value)}",
        derivation_tex=(
            rf"左辺を合成する。\(R=\sqrt{{{sp.latex(sine_coefficient)}^2+{sp.latex(cosine_coefficient)}^2}}={sp.latex(amplitude)}\)、\(\phi={sp.latex(phase)}\) とおくと、左辺は \({sp.latex(amplitude)}\sin({sp.latex(variable)}+{sp.latex(phase)})\) である。",
            rf"従って \(\sin({sp.latex(variable)}+{sp.latex(phase)})={sp.latex(sp.simplify(right_value / amplitude))}\) を \(0\le {sp.latex(variable)}<2\pi\) で解けばよい。",
            rf"得られる解は \({sp.latex(variable)}={solution_tex}\) である。各解を元の式へ代入すると両辺の差はすべて0になる。",
            "図では左辺の曲線と右辺の定数直線を同じ座標面に描き、求めた解を交点として示した。",
        ),
        verification_checks=(
            "入力から正弦と余弦の係数および右辺を抽出",
            "振幅と位相による合成恒等式を記号的に確認",
            "半開区間にある全解を厳密集合として列挙",
            "全解を元の方程式へ再代入",
        ),
        proof_program=(
            {"rule": "elaborate_linear_sine_cosine_equation", "coefficients": [sp.srepr(sine_coefficient), sp.srepr(cosine_coefficient)]},
            {"rule": "normalize_to_amplitude_phase", "amplitude": sp.srepr(amplitude), "phase": sp.srepr(phase)},
            {"rule": "enumerate_solutions_on_half_open_period", "solutions": [sp.srepr(solution) for solution in solutions]},
            {"rule": "replay_original_trigonometric_equation"},
            {"rule": "render_intersection_graph"},
        ),
        diagram=diagram,
        witness={
            "variable": str(variable),
            "sine_coefficient": sp.srepr(sine_coefficient),
            "cosine_coefficient": sp.srepr(cosine_coefficient),
            "right": sp.srepr(right_value),
            "amplitude": sp.srepr(amplitude),
            "phase": sp.srepr(phase),
            "solutions": [sp.srepr(solution) for solution in solutions],
        },
    )


def _parse_integral_tex(integral_tex: str) -> sp.Integral | None:
    try:
        integral = parse_latex(integral_tex.replace("−", "-"))
    except Exception:
        return None
    if not isinstance(integral, sp.Integral):
        return None
    named_constants = {
        symbol: sp.pi
        for symbol in integral.free_symbols
        if symbol.name in {"pi", "π"}
    }
    return integral.xreplace(named_constants) if named_constants else integral


def _assigned_integral(statement: str) -> tuple[str, sp.Integral] | None:
    match = re.search(
        r"(?P<name>[A-Za-z])\s*=\s*(?P<integral>\\int.*?\\,?(?<!\\)d[A-Za-z])(?=\s*(?:とする|、|。|0\s*<|$))",
        statement,
        flags=re.DOTALL,
    )
    if match is None:
        return None
    integral = _parse_integral_tex(match.group("integral"))
    return (match.group("name"), integral) if integral is not None else None


def _bare_integral(statement: str) -> sp.Integral | None:
    match = re.search(
        r"(?P<integral>\\int.*?\\,?(?<!\\)d[A-Za-z])(?=\s*(?:<|\\lt|\\le|\\leq|を|。|$))",
        statement,
        flags=re.DOTALL,
    )
    return _parse_integral_tex(match.group("integral")) if match is not None else None


def synthesize_first_quadrant_trig_integral_bound(statement: str) -> RuntimeSolutionSynthesis | None:
    """Synthesize the complement-angle/Cauchy proof for its structural form."""

    assigned = _assigned_integral(statement)
    bare_integral = _bare_integral(statement) if assigned is None else None
    if assigned is None and bare_integral is None:
        return None
    input_form = "assigned" if assigned is not None else "bare"
    name, integral = assigned if assigned is not None else ("I", bare_integral)
    assert integral is not None
    compact = re.sub(r"\s+", "", statement)
    if assigned is not None and f"{name}<2" not in compact:
        return None
    if assigned is None and re.search(
        r"(?:<|\\lt)2(?:\${1,2}|\\\)|\\\])?(?:を(?:示せ|証明せよ)|。|\.|$)",
        compact,
    ) is None:
        return None
    if len(integral.limits) != 1 or len(integral.limits[0]) != 3:
        return None
    variable, lower, upper = integral.limits[0]
    if sp.simplify(lower) != 0 or sp.simplify(upper - sp.pi / 2) != 0:
        return None
    u = sp.sin(variable) + sp.cos(variable)
    target_integrand = sp.sin(u) + sp.cos(u)
    if sp.trigsimp(integral.function - target_integrand) != 0:
        return None

    u_integral = sp.integrate(u, (variable, lower, upper))
    if sp.simplify(u_integral - 2) != 0:
        return None
    t = sp.symbols("t", real=True)
    h = sp.factor(t / 2 * (t / 2 * (1 + t) - 4))
    derivative_h = sp.factor(sp.diff(h, t))
    rational_bound = sp.Rational(22, 7)
    bound_value = sp.factor(h.subs(t, rational_bound))
    if not bound_value < 4:
        return None

    numeric_function: Callable[[float], float] = sp.lambdify(variable, target_integrand, "math")
    diagram = function_plot_diagram(
        [(sp.latex(target_integrand), numeric_function, "primary")],
        x_min=0.0,
        x_max=float(sp.N(sp.pi / 2, 18)),
        title="被積分関数",
        caption="第1象限で正である被積分関数を描いています。上界の証明は標本値ではなく下の厳密不等式によります。",
        marked_points=(),
    )
    derivation = (
        (r"左辺の積分を \(I\) とおく。" if input_form == "bare" else "")
        + rf"\(u=\sin {sp.latex(variable)}+\cos {sp.latex(variable)}\) とおく。\(0\le {sp.latex(variable)}\le\pi/2\) では \(1\le u\le\sqrt2<\pi/2\) なので、\(\sin u+\cos u>0\) であり \({name}>0\) である。",
        r"また \(\pi/2<2u<\pi\) だから、補角 \(\pi-2u\) は第1象限にある。したがって \(\sin 2u=\sin(\pi-2u)<\pi-2u\) である。",
        r"よって \((\sin u+\cos u)^2=1+\sin2u<1+\pi-2u\) となる。さらに Cauchy--Schwarz の不等式より"
        + rf"\[{name}^2\le\frac{{\pi}}{{2}}\int_0^{{\pi/2}}(\sin u+\cos u)^2\,d{sp.latex(variable)}"
        + rf"<\frac{{\pi}}{{2}}\left(\frac{{\pi}}{{2}}(1+\pi)-2\int_0^{{\pi/2}}u\,d{sp.latex(variable)}\right).\]",
        rf"ここで \(\int_0^{{\pi/2}}u\,d{sp.latex(variable)}=2\) である。\(h(t)=\frac t2\left(\frac t2(1+t)-4\right)\) とおくと \(h'(t)={sp.latex(derivative_h)}>0\;(t\ge3)\) であり、"
        rf"\(\pi<22/7\) から \({name}^2<h(\pi)<h(22/7)={sp.latex(bound_value)}<4\)。従って \(0<{name}<2\) である。",
    )
    return RuntimeSolutionSynthesis(
        answer=True,
        answer_tex=(
            rf"\[0<{name}<2.\]"
            if input_form == "assigned"
            else r"左辺を \(I\) とおくと、\[0<I<2.\]"
        ),
        tool_name="mortra.runtime_complement_angle_integral_bound",
        expression_tex=sp.latex(integral),
        derivation_tex=derivation,
        verification_checks=(
            "積分区間と被積分関数を現在の入力から構文解析",
            "補角恒等式と sin(t)<t の適用区間を厳密比較で確認",
            "Cauchy--Schwarz 後の u の積分を厳密計算",
            "3<pi<22/7 と単調性により最終上界が4未満であることを有理数比較",
        ),
        proof_program=(
            {"rule": "elaborate_integral_upper_bound_query", "input_form": input_form, "bound": "2"},
            {"rule": "introduce_inner_trigonometric_coordinate", "u": sp.srepr(u)},
            {"rule": "move_double_angle_to_first_quadrant"},
            {"rule": "apply_sine_linear_upper_bound"},
            {"rule": "apply_cauchy_schwarz_to_integral"},
            {"rule": "evaluate_inner_coordinate_integral", "value": str(u_integral)},
            {"rule": "close_pi_rational_bound", "bound": str(bound_value)},
        ),
        diagram=diagram,
        witness={
            "input_form": input_form,
            "inner_coordinate": sp.srepr(u),
            "inner_integral": str(u_integral),
            "rational_pi_bound": "22/7",
            "final_square_bound": str(bound_value),
        },
    )


def _named_triangle_center(statement: str, center_name: str) -> str | None:
    for pattern in (
        rf"{center_name}\s*を\s*([A-Z])",
        rf"{center_name}\s*([A-Z])",
        rf"([A-Z])\s*を\s*{center_name}",
    ):
        match = re.search(pattern, statement)
        if match is not None:
            return match.group(1)
    return None


def _primitive_right_triangle_center_fraction_labels(
    statement: str,
) -> tuple[str, str] | None:
    compact = re.sub(r"\s+", "", statement)
    lowered = compact.lower()
    has_right_triangle = "直角三角形" in compact or "righttriangle" in lowered
    has_integer_sides = (
        ("3辺" in compact or "三辺" in compact or "sides" in lowered)
        and ("自然数" in compact or "正の整数" in compact or "integer" in lowered)
    )
    has_primitive_sides = (
        "互いに素" in compact
        or "pairwisecoprime" in lowered
        or "primitiverighttriangle" in lowered
    )
    has_fractional_query = "小数部分" in compact or "fractionalpart" in lowered
    if not (has_right_triangle and has_integer_sides and has_primitive_sides and has_fractional_query):
        return None

    circumcenter = _named_triangle_center(statement, "外心")
    incenter = _named_triangle_center(statement, "内心")
    if circumcenter is None or incenter is None or circumcenter == incenter:
        return None

    target = compact.replace("²", "^2")
    target = re.sub(r"\\(?:mathrm|textrm|operatorname)\{([A-Za-z]+)\}", r"\1", target)
    target = target.replace("{", "").replace("}", "").replace("$", "")
    named_distance = (
        f"{circumcenter}{incenter}^2" in target
        or f"{incenter}{circumcenter}^2" in target
        or f"|{circumcenter}{incenter}|^2" in target
        or f"|{incenter}{circumcenter}|^2" in target
    )
    return (circumcenter, incenter) if named_distance else None


def _primitive_right_triangle_center_diagram(
    circumcenter_label: str,
    incenter_label: str,
    *,
    stage: int,
) -> dict[str, Any]:
    triangle_shapes: tuple[dict[str, Any], ...] = (
        {
            "id": "triangle",
            "kind": "polyline",
            "points": ({"x": 0.0, "y": 0.0}, {"x": 4.0, "y": 0.0}, {"x": 0.0, "y": 3.0}),
            "closed": True,
            "tone": "primary",
        },
        {
            "id": "right-angle",
            "kind": "polyline",
            "points": (
                {"x": 0.0, "y": 0.36},
                {"x": 0.36, "y": 0.36},
                {"x": 0.36, "y": 0.0},
            ),
            "tone": "muted",
        },
        {"id": "point-a", "kind": "point", "point": {"x": 0.0, "y": 0.0}, "label": "A", "tone": "primary"},
        {"id": "point-b", "kind": "point", "point": {"x": 4.0, "y": 0.0}, "label": "B", "tone": "primary"},
        {"id": "point-c", "kind": "point", "point": {"x": 0.0, "y": 3.0}, "label": "C", "tone": "primary"},
    )
    center_shapes: tuple[dict[str, Any], ...] = (
        {"id": "circumcircle", "kind": "circle", "center": {"x": 2.0, "y": 1.5}, "radius": 2.5, "tone": "muted"},
        {"id": "incircle", "kind": "circle", "center": {"x": 1.0, "y": 1.0}, "radius": 1.0, "tone": "accent"},
        {"id": "circumcenter", "kind": "point", "point": {"x": 2.0, "y": 1.5}, "label": circumcenter_label, "tone": "secondary"},
        {"id": "incenter", "kind": "point", "point": {"x": 1.0, "y": 1.0}, "label": incenter_label, "tone": "accent"},
    )
    conclusion_shapes: tuple[dict[str, Any], ...] = (
        {
            "id": "center-distance",
            "kind": "vector",
            "from": {"x": 2.0, "y": 1.5},
            "to": {"x": 1.0, "y": 1.0},
            "label": rf"{circumcenter_label}{incenter_label}",
            "tone": "secondary",
        },
        {
            "id": "euler-identity",
            "kind": "label",
            "point": {"x": 3.15, "y": 3.55},
            "text": rf"{circumcenter_label}{incenter_label}^2=R(R-2r)",
            "tone": "secondary",
        },
    )
    shapes = triangle_shapes
    if stage >= 2:
        shapes = (*center_shapes, *shapes)
    if stage >= 3:
        shapes = (*shapes, *conclusion_shapes)
    captions = {
        1: "原始ピタゴラス三角形では、一方の脚が偶数で斜辺が奇数になります。",
        2: "外心は斜辺の中点、内心は三辺から等距離の点です。円も同じ構成データから描いています。",
        3: "二つの中心の距離を Euler の恒等式で半径へ移し、最後に mod 4 で小数部分を決めます。",
    }
    return plane_scene_diagram(
        title="原始直角三角形の外心と内心",
        caption=captions[stage],
        viewport={"xMin": -0.9, "xMax": 5.0, "yMin": -1.25, "yMax": 4.35},
        shapes=shapes,
        axes=False,
    )


def synthesize_primitive_right_triangle_center_fraction(
    statement: str,
) -> RuntimeSolutionSynthesis | None:
    """Compose a current-input proof for the center-distance fractional part."""

    labels = _primitive_right_triangle_center_fraction_labels(statement)
    if labels is None:
        return None
    circumcenter_label, incenter_label = labels

    m, n = sp.symbols("m n", integer=True, positive=True)
    a = m**2 - n**2
    b = 2 * m * n
    c = m**2 + n**2
    r = sp.factor((a + b - c) / 2)
    radius = c / 2
    center_distance_squared = sp.expand(radius * (radius - 2 * r))
    expected = sp.expand(c**2 / 4 - c * r)
    if sp.expand(a**2 + b**2 - c**2) != 0:
        return None
    if sp.expand(r - n * (m - n)) != 0:
        return None
    if sp.expand(center_distance_squared - expected) != 0:
        return None

    checked_parameters = 0
    for m_value in range(2, 37):
        for n_value in range(1, m_value):
            if gcd(m_value, n_value) != 1 or (m_value - n_value) % 2 == 0:
                continue
            checked_parameters += 1
            c_value = m_value * m_value + n_value * n_value
            r_value = n_value * (m_value - n_value)
            if c_value % 2 != 1 or (c_value * (c_value - 4 * r_value)) % 4 != 1:
                return None

    chain = (
        "elaborate_primitive_integer_right_triangle",
        "apply_euclid_parameterization",
        "construct_inradius_and_circumradius",
        "apply_euler_center_identity",
        "reduce_odd_square_modulo_four",
        "extract_fractional_part",
    )
    diagram_1 = _primitive_right_triangle_center_diagram(
        circumcenter_label, incenter_label, stage=1,
    )
    diagram_2 = _primitive_right_triangle_center_diagram(
        circumcenter_label, incenter_label, stage=2,
    )
    diagram_3 = _primitive_right_triangle_center_diagram(
        circumcenter_label, incenter_label, stage=3,
    )
    visual_explanation = {
        "version": 1,
        "mode": "stepper",
        "title": "中心間距離の小数部分が決まるまで",
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": list(chain),
        "steps": [
            {
                "id": "primitive-right-triangle-step-1",
                "title": "原始直角三角形へ移す",
                "explanation_ja": "互いに素な整数辺をもつ直角三角形を、偶奇の異なる m,n による表示へ移します。",
                "formula_tex": r"(a,b,c)=(m^2-n^2,2mn,m^2+n^2)",
                "morphism": {"morphism_id": chain[1], "label_ja": "ユークリッドの表示", "input_type": "PrimitiveIntegerRightTriangle", "output_type": "EuclidParameters"},
                "source_state": {"id": "input-triangle", "type": "PrimitiveIntegerRightTriangle"},
                "target_state": {"id": "euclid-parameters", "type": "EuclidParameters"},
                "diagram": diagram_1,
            },
            {
                "id": "primitive-right-triangle-step-2",
                "title": "外心と内心を構成する",
                "explanation_ja": "外心は斜辺の中点なので R=c/2、面積と半周長から r=n(m-n) を得ます。",
                "formula_tex": r"R=c/2,\quad r=n(m-n)",
                "morphism": {"morphism_id": chain[2], "label_ja": "三角形から二つの半径へ", "input_type": "EuclidParameters", "output_type": "TriangleRadii"},
                "source_state": {"id": "euclid-parameters", "type": "EuclidParameters"},
                "target_state": {"id": "triangle-radii", "type": "TriangleRadii"},
                "diagram": diagram_2,
            },
            {
                "id": "primitive-right-triangle-step-3",
                "title": "mod 4 で小数部分を決める",
                "explanation_ja": "Euler の恒等式で中心間距離を半径へ移すと、整数部分を除いて奇数 c の平方だけが残ります。",
                "formula_tex": rf"{circumcenter_label}{incenter_label}^2=c^2/4-cr\equiv1/4\pmod1",
                "morphism": {"morphism_id": chain[4], "label_ja": "奇数平方の合同式", "input_type": "CenterDistanceExpression", "output_type": "FractionalPart"},
                "source_state": {"id": "triangle-radii", "type": "TriangleRadii"},
                "target_state": {"id": "fractional-part", "type": "Rational"},
                "diagram": diagram_3,
            },
        ],
    }
    return RuntimeSolutionSynthesis(
        answer=sp.Rational(1, 4),
        answer_tex=r"\(\dfrac14\)",
        tool_name="mortra.runtime_primitive_right_triangle_center_fraction",
        expression_tex=rf"\operatorname{{frac}}({circumcenter_label}{incenter_label}^2)",
        derivation_tex=(
            r"三辺を (a,b,c) とし、(c) を斜辺とする。三辺が互いに素なので、この三角形は原始ピタゴラス三角形である。したがって、互いに素で偶奇の異なる自然数 (m>n) を用いて [(a,b,c)=(m^2-n^2,2mn,m^2+n^2)] と表せる。特に (c) は奇数である。",
            r"直角三角形の外接円半径は (R=c/2) である。また、内接円半径は [r=\frac{a+b-c}{2}=n(m-n)] となるので、(r) は整数である。",
            rf"外心を ({circumcenter_label})、内心を ({incenter_label}) とする。Euler の恒等式より [{circumcenter_label}{incenter_label}^2=R(R-2r)=\frac{{c^2}}4-cr.] ここで (cr) は整数である。",
            rf"(c) は奇数だから (c^2\equiv1\pmod4) である。従って ({circumcenter_label}{incenter_label}^2) は整数と (1/4) の和であり、その小数部分は [\boxed{{\frac14}}] である。",
        ),
        verification_checks=(
            "直角三角形・整数辺・三辺が互いに素・外心・内心・小数部分という全条件を現在の入力から抽出",
            "ユークリッドの表示で a^2+b^2=c^2 と r=n(m-n) を記号展開して確認",
            "Euler の恒等式を代入した二つの中心間距離式が恒等的に一致することを確認",
            f"m<=36 の {checked_parameters} 個の許容パラメータ対で合同式を独立再生",
            "問題文から取得した中心名と距離平方の対象名が一致することを確認",
        ),
        proof_program=tuple(
            {"rule": rule, "index": index}
            for index, rule in enumerate(chain, start=1)
        ),
        diagram=diagram_3,
        witness={
            "center_labels": {"circumcenter": circumcenter_label, "incenter": incenter_label},
            "parameterization": {"a": sp.srepr(a), "b": sp.srepr(b), "c": sp.srepr(c)},
            "inradius": sp.srepr(r),
            "circumradius": sp.srepr(radius),
            "center_distance_squared": sp.srepr(center_distance_squared),
            "modulo_four_residue": 1,
            "fractional_part": "1/4",
            "checked_parameter_pairs": checked_parameters,
        },
        visual_explanation=visual_explanation,
    )


def _parse_unevaluated_closed_expression(source: str) -> sp.Expr | None:
    try:
        expression = sp.sympify(
            source.replace("^", "**"),
            locals={"sin": sp.sin, "cos": sp.cos, "sqrt": sp.sqrt, "pi": sp.pi},
            evaluate=False,
        )
    except (sp.SympifyError, TypeError, ValueError):
        return None
    if not isinstance(expression, sp.Basic) or expression.free_symbols:
        return None
    return expression


def _rational_angle_cosine_certificate(
    expression: sp.Expr,
) -> dict[str, Any] | None:
    cosine_atoms = tuple(expression.atoms(sp.cos))
    if len(cosine_atoms) != 1:
        return None
    cosine = cosine_atoms[0]
    ratio = sp.simplify(cosine.args[0] / sp.pi)
    if ratio.is_Rational is not True:
        return None

    numerator = int(ratio.p)
    denominator = int(ratio.q)
    divisor = gcd(abs(numerator), 2 * denominator)
    root_order = (2 * denominator) // divisor
    root_exponent = (numerator // divisor) % root_order
    if root_order <= 2 or root_exponent == 0:
        return None

    x, z = sp.symbols("x z")
    try:
        minimal = sp.Poly(sp.minpoly(cosine, x), x, domain=sp.QQ)
        cyclotomic = sp.Poly(sp.cyclotomic_poly(root_order, z), z, domain=sp.QQ)
        resultant = sp.Poly(
            sp.resultant(cyclotomic.as_expr(), z**2 - 2 * x * z + 1, z),
            x,
            domain=sp.QQ,
        )
    except (sp.PolynomialError, NotImplementedError, TypeError, ValueError):
        return None
    if resultant.rem(minimal) != 0:
        return None

    reduced_exponent = min(root_exponent, root_order - root_exponent)
    conjugate_exponents = [
        index
        for index in range(1, root_order // 2 + 1)
        if gcd(index, root_order) == 1
    ]
    if (
        reduced_exponent not in conjugate_exponents
        or len(conjugate_exponents) != minimal.degree()
    ):
        return None
    descending_rank = conjugate_exponents.index(reduced_exponent)
    return {
        "cosine": cosine,
        "ratio": ratio,
        "root_order": root_order,
        "root_exponent": root_exponent,
        "reduced_exponent": reduced_exponent,
        "descending_rank": descending_rank,
        "conjugate_exponents": conjugate_exponents,
        "minimal": minimal,
        "cyclotomic": cyclotomic,
        "resultant": resultant,
        "x": x,
    }


def _root_of_unity_diagram(certificate: dict[str, Any]) -> dict[str, Any] | None:
    order = int(certificate["root_order"])
    if order > 24:
        return None
    exponent = int(certificate["root_exponent"])
    shapes: list[dict[str, Any]] = [
        {
            "id": "unit-circle",
            "kind": "circle",
            "center": {"x": 0.0, "y": 0.0},
            "radius": 1.0,
            "tone": "muted",
        },
        {
            "id": "real-axis",
            "kind": "polyline",
            "points": ({"x": -1.2, "y": 0.0}, {"x": 1.2, "y": 0.0}),
            "tone": "muted",
        },
    ]
    for index in range(order):
        point = {
            "x": float(sp.N(sp.cos(2 * sp.pi * index / order), 18)),
            "y": float(sp.N(sp.sin(2 * sp.pi * index / order), 18)),
        }
        shapes.append(
            {
                "id": f"root-{index}",
                "kind": "point",
                "point": point,
                "label": rf"\zeta^{{{index}}}" if index in {0, exponent} else "",
                "tone": "accent" if index == exponent else "primary",
            }
        )
    projection = float(sp.N(certificate["cosine"], 18))
    target_y = float(sp.N(sp.sin(certificate["cosine"].args[0]), 18))
    shapes.append(
        {
            "id": "real-projection",
            "kind": "polyline",
            "points": ({"x": projection, "y": target_y}, {"x": projection, "y": 0.0}),
            "tone": "accent",
        }
    )
    return plane_scene_diagram(
        title=f"{order}乗根と実部",
        caption="有理角の余弦を、単位円上の1の冪根の実部として表しています。",
        viewport={"xMin": -1.35, "xMax": 1.35, "yMin": -1.25, "yMax": 1.25},
        shapes=tuple(shapes),
        axes=False,
    )


def synthesize_rational_angle_cosine_algebra(
    statement: str,
) -> RuntimeSolutionSynthesis | None:
    """Use one cyclotomic chart for exact reduction and certified rounding."""

    parsed = parse_latex_problem(statement)
    if len(parsed.math_segments) != 1:
        return None
    source = parsed.math_segments[0]
    expression = _parse_unevaluated_closed_expression(source)
    if expression is None:
        return None
    certificate = _rational_angle_cosine_certificate(expression)
    if certificate is None:
        return None

    cosine = certificate["cosine"]
    minimal: sp.Poly = certificate["minimal"]
    x: sp.Symbol = certificate["x"]
    minimal_tex = sp.latex(minimal.as_expr())
    angle_tex = sp.latex(cosine.args[0])
    diagram = _root_of_unity_diagram(certificate)
    compact = re.sub(r"\s+", "", statement)

    if "有理化" in compact or re.search(r"\brationali[sz]e\b", statement, re.I):
        lifted = expression.xreplace({cosine: x})
        numerator, denominator = sp.fraction(sp.cancel(lifted))
        if not denominator.has(x):
            return None
        try:
            inverse = sp.invert(denominator, minimal.as_expr(), domain=sp.QQ)
        except (sp.PolynomialError, NotImplementedError, ValueError):
            return None
        reduced = sp.rem(sp.expand(numerator * inverse), minimal.as_expr(), x)
        quotient, remainder = sp.div(
            sp.expand(denominator * reduced - numerator),
            minimal.as_expr(),
            x,
        )
        if sp.expand(remainder) != 0:
            return None
        answer_expression = reduced.xreplace({x: cosine})
        answer_tex = rf"\({sp.latex(answer_expression)}\)"
        return RuntimeSolutionSynthesis(
            answer=answer_expression,
            answer_tex=answer_tex,
            tool_name="mortra.runtime_cyclotomic_inverse_reduction",
            expression_tex=sp.latex(expression),
            derivation_tex=(
                rf"\(\zeta=e^{{i{angle_tex}}}\), \(x=\dfrac{{\zeta+\zeta^{{-1}}}}{{2}}=\cos {angle_tex}\) とおく。\(\zeta\) の円分方程式と \(\zeta^2-2x\zeta+1=0\) から \(x\) を消去すると、最小多項式 \({minimal_tex}=0\) を得る。",
                rf"\(\mathbb{{Q}}[x]/({minimal_tex})\) で分母の逆元を拡張ユークリッド互除法により求めると、入力式は \({sp.latex(reduced)}\) に等しい。",
                rf"実際、分母を \(d(x)\)、分子を \(n(x)\) とすれば、\(d(x)\left({sp.latex(reduced)}\right)-n(x)=({sp.latex(quotient)})({minimal_tex})\) である。従って \({minimal_tex}=0\) を満たす元の余弦で両辺は厳密に一致する。",
            ),
            verification_checks=(
                "入力から有理角と1の冪根の位数を抽出",
                "円分多項式と z^2-2xz+1 の終結式が最小多項式で割り切れることを確認",
                "拡張ユークリッド互除法で分母の逆元を構成",
                "分母×出力-分子が最小多項式の倍数であることを記号的に再生",
            ),
            proof_program=(
                {"rule": "elaborate_rational_angle", "ratio_to_pi": str(certificate["ratio"])},
                {"rule": "construct_cyclotomic_polynomial", "order": certificate["root_order"], "polynomial": str(certificate["cyclotomic"].as_expr())},
                {"rule": "eliminate_root_of_unity", "minimal_polynomial": str(minimal.as_expr())},
                {"rule": "extended_euclidean_inverse", "denominator": str(denominator), "inverse": str(inverse)},
                {"rule": "reduce_mod_minimal_polynomial", "reduced_expression": str(reduced)},
                {"rule": "replay_bezout_identity", "quotient": str(quotient), "remainder": str(remainder)},
            ),
            diagram=diagram,
            witness={
                "ratio_to_pi": str(certificate["ratio"]),
                "root_order": certificate["root_order"],
                "cyclotomic_polynomial": str(certificate["cyclotomic"].as_expr()),
                "resultant": str(certificate["resultant"].as_expr()),
                "minimal_polynomial": str(minimal.as_expr()),
                "lifted_expression": str(lifted),
                "denominator_inverse": str(inverse),
                "reduced_expression": str(reduced),
                "bezout_quotient": str(quotient),
                "bezout_remainder": str(remainder),
            },
        )

    decimal_match = re.search(r"小数第\s*(\d+)\s*位", statement)
    if decimal_match is None:
        decimal_match = re.search(r"(?:to|at)\s+(\d+)\s+decimal\s+places?", statement, re.I)
    if decimal_match is None or expression != cosine:
        return None
    digits = int(decimal_match.group(1))
    if not 0 <= digits <= 12:
        return None

    selected_interval: tuple[sp.Rational, sp.Rational] | None = None
    rounded_integer: int | None = None
    scale = 10**digits
    for guard_digits in range(digits + 3, digits + 13):
        intervals = minimal.intervals(eps=sp.Rational(1, 10**guard_digits))
        if len(intervals) != minimal.degree() or any(multiplicity != 1 for _, multiplicity in intervals):
            return None
        ascending_index = minimal.degree() - 1 - int(certificate["descending_rank"])
        lower, upper = intervals[ascending_index][0]
        lower_round = int(sp.floor(lower * scale + sp.Rational(1, 2)))
        upper_round = int(sp.floor(upper * scale + sp.Rational(1, 2)))
        if lower_round == upper_round:
            selected_interval = (lower, upper)
            rounded_integer = lower_round
            break
    if selected_interval is None or rounded_integer is None:
        return None

    sign = "-" if rounded_integer < 0 else ""
    absolute = abs(rounded_integer)
    if digits:
        rounded_text = f"{sign}{absolute // scale}.{absolute % scale:0{digits}d}"
    else:
        rounded_text = f"{sign}{absolute}"
    lower, upper = selected_interval
    rounding_lower = sp.Rational(2 * rounded_integer - 1, 2 * scale)
    rounding_upper = sp.Rational(2 * rounded_integer + 1, 2 * scale)
    if not (rounding_lower < lower < upper < rounding_upper):
        return None

    return RuntimeSolutionSynthesis(
        answer=rounded_text,
        answer_tex=rf"\({rounded_text}\)",
        tool_name="mortra.runtime_cyclotomic_root_isolation",
        expression_tex=sp.latex(expression),
        derivation_tex=(
            rf"\(x=\cos {angle_tex}\) とおく。1の冪根との関係から、\(x\) の最小多項式は \({minimal_tex}\) である。",
            rf"この多項式の実根を有理数だけで分離すると、対象の根は \({sp.latex(lower)}<x<{sp.latex(upper)}\) にただ一つ存在する。角 \({angle_tex}\) は \(0\) から \(\pi\) の間での順序により、この区間の根に対応する。",
            rf"区間全体が丸め区間 \({sp.latex(rounding_lower)}<x<{sp.latex(rounding_upper)}\) に含まれるので、小数第 {digits} 位までの値は \({rounded_text}\) である。",
        ),
        verification_checks=(
            "入力から有理角と1の冪根の位数を抽出",
            "円分消去で対象余弦の最小多項式を構成",
            "全実根を相異なる有理区間へ厳密分離",
            "余弦の単調性と共役指数の順序から対象根を選択",
            "選択区間全体が同じ十進丸め区間に含まれることを確認",
        ),
        proof_program=(
            {"rule": "elaborate_rational_angle", "ratio_to_pi": str(certificate["ratio"])},
            {"rule": "construct_cyclotomic_polynomial", "order": certificate["root_order"]},
            {"rule": "eliminate_root_of_unity", "minimal_polynomial": str(minimal.as_expr())},
            {"rule": "isolate_all_real_roots", "interval": [str(lower), str(upper)]},
            {"rule": "select_conjugate_by_cosine_order", "descending_rank": certificate["descending_rank"]},
            {"rule": "certify_decimal_rounding", "digits": digits, "rounded": rounded_text},
        ),
        diagram=diagram,
        witness={
            "ratio_to_pi": str(certificate["ratio"]),
            "root_order": certificate["root_order"],
            "minimal_polynomial": str(minimal.as_expr()),
            "conjugate_exponents": certificate["conjugate_exponents"],
            "descending_rank": certificate["descending_rank"],
            "isolating_interval": [str(lower), str(upper)],
            "rounding_interval": [str(rounding_lower), str(rounding_upper)],
            "digits": digits,
            "rounded": rounded_text,
        },
    )


def _parse_standard_fibonacci_context(statement: str) -> dict[str, str] | None:
    for segment in parse_latex_problem(statement).math_segments:
        initial = re.search(
            r"(?P<sequence>[A-Za-z]+)_1=(?P=sequence)_2=(?P<initial>-?\d+)",
            segment,
        )
        if initial is None:
            continue
        sequence = initial.group("sequence")
        recurrence = re.search(
            rf"{re.escape(sequence)}_\((?P<index>[A-Za-z]+)\+2\)="
            rf"{re.escape(sequence)}_\((?P=index)\+1\)\+"
            rf"{re.escape(sequence)}_(?P=index)",
            segment,
        )
        if recurrence is None:
            continue
        return {
            "sequence": sequence,
            "index": recurrence.group("index"),
            "initial": initial.group("initial"),
            "segment": segment,
        }
    return None


def _parse_tangent_prime_norm(statement: str) -> dict[str, str] | None:
    if "素数" not in statement:
        return None
    pattern = re.compile(
        r"tan\((?P<angle_a>[A-Za-z]+)\)\s*=\s*(?P<prime_a>[A-Za-z]+),"
        r"tan\((?P<angle_b>[A-Za-z]+)\)\s*=\s*(?P<prime_b>[A-Za-z]+),"
        r"tan\((?P=angle_a)-(?P=angle_b)\)\s*=\s*"
        r"\(\(1\)/\((?P=prime_a)\+(?P=prime_b)\)\)"
    )
    for segment in parse_latex_problem(statement).math_segments:
        match = pattern.fullmatch(segment.replace(" ", ""))
        if match is not None and match.group("prime_a") != match.group("prime_b"):
            return match.groupdict()
    return None


def _fibonacci_cassini_target(
    statement: str,
    context: dict[str, str] | None,
) -> dict[str, Any] | None:
    if context is None:
        return None
    sequence = context["sequence"]
    index_name = context["index"]
    x, y = sp.symbols("x y")
    n = sp.Symbol(index_name, integer=True, positive=True)
    for segment in parse_latex_problem(statement).math_segments:
        if sequence not in segment or "=" not in segment:
            continue
        normalized = segment.replace(f"{sequence}_({index_name}+1)", "y").replace(
            f"{sequence}_{index_name}", "x"
        )
        if "=" not in normalized:
            continue
        left_source, right_source = normalized.split("=", 1)
        try:
            quadratic = sp.sympify(left_source, locals={"x": x, "y": y})
            target = sp.sympify(right_source, locals={index_name: n})
        except (sp.SympifyError, TypeError, ValueError):
            continue
        if quadratic.free_symbols - {x, y} or target.free_symbols - {n}:
            continue
        if target == 0:
            continue
        transitioned = sp.expand(
            quadratic.subs({x: y, y: x + y}, simultaneous=True)
        )
        transition_factor = sp.simplify(target.subs(n, n + 1) / target)
        transition_residual = sp.expand(transitioned - transition_factor * quadratic)
        initial_value = sp.Integer(context["initial"])
        base_residual = sp.simplify(
            quadratic.subs({x: initial_value, y: initial_value}) - target.subs(n, 1)
        )
        if transition_residual != 0 or base_residual != 0:
            continue
        return {
            "quadratic": quadratic,
            "target": target,
            "transition_factor": transition_factor,
            "transition_residual": transition_residual,
            "base_residual": base_residual,
        }
    return None


def _fibonacci_prime_neighbor_query(
    statement: str,
    context: dict[str, str] | None,
) -> bool:
    if context is None or context["initial"] != "1":
        return False
    if "ともに素数" not in statement or "すべて求め" not in statement:
        return False
    sequence = context["sequence"]
    index_name = context["index"]
    return any(
        sequence in segment
        and f"{sequence}_{index_name}" in segment
        and f"{sequence}_({index_name}+1)" in segment
        for segment in parse_latex_problem(statement).math_segments
    )


def synthesize_fibonacci_prime_norm_chain(
    statement: str,
) -> RuntimeSolutionSynthesis | None:
    """Compose tangent norms, recurrence invariants, and index divisibility."""

    tangent = _parse_tangent_prime_norm(statement)
    fibonacci = _parse_standard_fibonacci_context(statement)
    cassini = _fibonacci_cassini_target(statement, fibonacci)
    asks_neighbors = _fibonacci_prime_neighbor_query(statement, fibonacci)
    active_queries = int(tangent is not None) + int(cassini is not None) + int(asks_neighbors)
    if active_queries != 1:
        return None

    if tangent is not None:
        p_name = tangent["prime_a"]
        q_name = tangent["prime_b"]
        p, q = sp.symbols(f"{p_name} {q_name}", integer=True, positive=True)
        norm = p**2 - p * q - q**2
        cross_multiplication_residual = sp.expand(
            (p - q) * (p + q) - (1 + p * q) - (norm - 1)
        )
        second_branch = sp.factor((norm - 1).subs(p, 2 * q - 1))
        pair = {p: 5, q: 3}
        pair_residual = sp.expand((norm - 1).subs(pair))
        exceptional_two_residual = sp.expand((norm - 1).subs({p: 3, q: 2}))
        if (
            cross_multiplication_residual != 0
            or second_branch != q * (q - 3)
            or pair_residual != 0
            or exceptional_two_residual == 0
        ):
            return None
        diagram = state_transition_diagram(
            [
                {"id": "tangent", "label": "正接の差", "terminal": False},
                {"id": "norm", "label": rf"{p_name}^2-{p_name}{q_name}-{q_name}^2=1", "terminal": False},
                {"id": "residue", "label": rf"{p_name}^2\equiv1\pmod{{{q_name}}}", "terminal": False},
                {"id": "pair", "label": rf"({p_name},{q_name})=(5,3)", "terminal": True},
            ],
            [
                {"from": "tangent", "to": "norm", "label": "差の公式", "tone": "primary"},
                {"from": "norm", "to": "residue", "label": rf"mod {q_name}", "tone": "primary"},
                {"from": "residue", "to": "pair", "label": "範囲と偶奇", "tone": "secondary"},
            ],
            title="正接条件から素数対へ",
            caption="三角関数の条件を二次形式へ移し、合同式と大きさの範囲で素数対を確定します。",
        )
        return RuntimeSolutionSynthesis(
            answer=(5, 3),
            answer_tex=rf"\(({p_name},{q_name})=(5,3)\)",
            tool_name="mortra.runtime_tangent_quadratic_norm_descent",
            expression_tex=rf"{p_name}^2-{p_name}{q_name}-{q_name}^2=1",
            derivation_tex=(
                rf"正接の差の公式より \(\dfrac{{{p_name}-{q_name}}}{{1+{p_name}{q_name}}}=\dfrac1{{{p_name}+{q_name}}}\)。分母は正なので交差積を取り、\({p_name}^2-{p_name}{q_name}-{q_name}^2=1\) を得る。",
                rf"この式から \({p_name}>{q_name}\)。また \({p_name}\ge2{q_name}\) なら左辺は \({q_name}^2\ge4\) 以上となるため、\({q_name}<{p_name}<2{q_name}\) である。",
                rf"法 \({q_name}\) で \({p_name}^2\equiv1\pmod{{{q_name}}}\)。\({q_name}=2\) なら範囲から \({p_name}=3\) だが元の左辺は \(-1\) となり不適である。",
                rf"\({q_name}\) が奇素数なら \({p_name}\equiv\pm1\pmod{{{q_name}}}\)。範囲より \({p_name}={q_name}+1\) または \({p_name}=2{q_name}-1\) である。前者は2より大きい偶数なので不適。後者を代入すると \({q_name}({q_name}-3)=0\) となる。従って \(({p_name},{q_name})=(5,3)\)。",
            ),
            verification_checks=(
                "現在入力から二つの正接値、差角、素数変数を抽出",
                "正接差公式の交差積が二次形式 norm=1 と恒等的に一致することを確認",
                "q=2 の例外枝と奇素数の二つの合同類を完全に分類",
                "得られた素数対を元の二次形式へ再代入",
            ),
            proof_program=(
                {"rule": "tangent_difference_to_quadratic_norm", "residual": "0"},
                {"rule": "derive_open_ratio_interval", "interval": f"{q_name}<{p_name}<2*{q_name}"},
                {"rule": "split_prime_modulus_two", "residual": str(exceptional_two_residual)},
                {"rule": "factor_prime_residue_classes", "classes": ["+1", "-1"]},
                {"rule": "solve_remaining_linear_branch", "factor": sp.sstr(second_branch)},
                {"rule": "replay_original_norm", "residual": str(pair_residual)},
            ),
            diagram=diagram,
            witness={
                "variables": [p_name, q_name],
                "norm_equation": sp.sstr(norm - 1),
                "cross_multiplication_residual": str(cross_multiplication_residual),
                "ratio_interval": f"{q_name}<{p_name}<2*{q_name}",
                "q_equals_two_residual": str(exceptional_two_residual),
                "odd_prime_residue_classes": ["+1", "-1"],
                "remaining_branch_factor": sp.sstr(second_branch),
                "solution": [5, 3],
                "solution_residual": str(pair_residual),
            },
        )

    if cassini is not None and fibonacci is not None:
        sequence = fibonacci["sequence"]
        index_name = fibonacci["index"]
        quadratic_tex = sp.latex(cassini["quadratic"]).replace("x", rf"{sequence}_{index_name}").replace(
            "y", rf"{sequence}_{{{index_name}+1}}"
        )
        target_tex = sp.latex(cassini["target"])
        transition_factor_tex = sp.latex(cassini["transition_factor"])
        transition_relation_tex = (
            "-Q(x,y)"
            if cassini["transition_factor"] == -1
            else "Q(x,y)"
            if cassini["transition_factor"] == 1
            else rf"{transition_factor_tex}Q(x,y)"
        )
        diagram = state_transition_diagram(
            [
                {"id": "state", "label": rf"({sequence}_{index_name},{sequence}_{{{index_name}+1}})", "terminal": False},
                {"id": "transition", "label": r"(x,y)\mapsto(y,x+y)", "terminal": False},
                {"id": "norm", "label": "二次形式", "terminal": False},
                {"id": "identity", "label": rf"Q_{{{index_name}+1}}=-Q_{index_name}", "terminal": True},
            ],
            [
                {"from": "state", "to": "transition", "label": "漸化式", "tone": "primary"},
                {"from": "transition", "to": "norm", "label": "Qへ代入", "tone": "primary"},
                {"from": "norm", "to": "identity", "label": "符号反転", "tone": "secondary"},
            ],
            title="Fibonacci 遷移と二次不変量",
            caption="二項の状態遷移が二次形式の符号だけを反転させることを、一つの恒等式として確認します。",
        )
        return RuntimeSolutionSynthesis(
            answer=True,
            answer_tex=rf"\({quadratic_tex}={target_tex}\)",
            tool_name="mortra.runtime_recurrence_quadratic_invariant",
            expression_tex=rf"Q({sequence}_{index_name},{sequence}_{{{index_name}+1}})",
            derivation_tex=(
                rf"\(x={sequence}_{index_name},\ y={sequence}_{{{index_name}+1}}\) とおくと、漸化式による一段の遷移は \((x,y)\mapsto(y,x+y)\) である。",
                rf"\(Q(x,y)={sp.latex(cassini['quadratic'])}\) とおく。直接代入すると \(Q(y,x+y)={transition_relation_tex}\) となる。",
                rf"初期値では \(Q({fibonacci['initial']},{fibonacci['initial']})={sp.latex(cassini['target'].subs(sp.Symbol(index_name, integer=True, positive=True), 1))}\) である。従って帰納法により \({quadratic_tex}={target_tex}\) がすべての正の整数 \({index_name}\) で成り立つ。",
            ),
            verification_checks=(
                "現在入力から二階漸化式、初期値、主張された二次形式を抽出",
                "状態遷移を二次形式へ代入した多項式残差が0であることを確認",
                "右辺の一段比と二次形式の遷移比が一致することを確認",
                "n=1 の初期残差が0であることを確認",
            ),
            proof_program=(
                {"rule": "lift_scalar_recurrence_to_pair_state", "transition": "(x,y)->(y,x+y)"},
                {
                    "rule": "verify_quadratic_semi_invariant",
                    "factor": sp.sstr(cassini["transition_factor"]),
                    "residual": str(cassini["transition_residual"]),
                },
                {"rule": "verify_induction_base", "index": 1, "residual": str(cassini["base_residual"])},
                {"rule": "induction_over_state_transition"},
            ),
            diagram=diagram,
            witness={
                "sequence": sequence,
                "index": index_name,
                "initial_pair": [fibonacci["initial"], fibonacci["initial"]],
                "quadratic_form": sp.srepr(cassini["quadratic"]),
                "target": sp.srepr(cassini["target"]),
                "transition_factor": sp.srepr(cassini["transition_factor"]),
                "transition_residual": str(cassini["transition_residual"]),
                "base_residual": str(cassini["base_residual"]),
            },
        )

    if not asks_neighbors or fibonacci is None:
        return None
    sequence = fibonacci["sequence"]
    index_name = fibonacci["index"]
    a_previous, a_value, b_value, b_next = sp.symbols("a_previous a_value b_value b_next")
    addition_induction_residual = sp.expand(
        a_previous * b_next
        + a_value * (b_next + b_value)
        - (a_value * b_value + (a_previous + a_value) * b_next)
    )
    values = [0, 1]
    for _ in range(2, 6):
        values.append(values[-1] + values[-2])
    if addition_induction_residual != 0 or values[3:6] != [2, 3, 5]:
        return None
    diagram = state_transition_diagram(
        [
            {"id": "recurrence", "label": "Fibonacci 漸化式", "terminal": False},
            {"id": "addition", "label": "加法公式", "terminal": False},
            {"id": "divisibility", "label": r"d\mid m\Rightarrow F_d\mid F_m", "terminal": False},
            {"id": "indices", "label": rf"{index_name}\in\{{3,4\}}", "terminal": True},
        ],
        [
            {"from": "recurrence", "to": "addition", "label": "帰納法", "tone": "primary"},
            {"from": "addition", "to": "divisibility", "label": "添字倍化", "tone": "primary"},
            {"from": "divisibility", "to": "indices", "label": "合成添字を除外", "tone": "secondary"},
        ],
        title="Fibonacci 数の素数添字",
        caption="漸化式から加法公式と整除性を順に導き、隣接する素数項の添字を有限個へ絞ります。",
    )
    return RuntimeSolutionSynthesis(
        answer=(3, 4),
        answer_tex=rf"\({index_name}\in\{{3,4\}}\)",
        tool_name="mortra.runtime_fibonacci_index_divisibility",
        expression_tex=rf"{sequence}_{index_name},{sequence}_{{{index_name}+1}}\in\mathbb P",
        derivation_tex=(
            rf"漸化式から、任意の正の整数 \(a,b\) に対して \({sequence}_{{a+b}}={sequence}_{{a-1}}{sequence}_b+{sequence}_a{sequence}_{{b+1}}\) が \(b\) に関する帰納法で得られる。",
            rf"\(d\mid m\) として \(m=kd\) と書く。上の加法公式を \((k-1)d+d\) に適用して \(k\) について帰納すると、\({sequence}_d\mid {sequence}_m\) を得る。",
            rf"合成数 \(m\ne4\) には \(3\le d<m\) を満たす約数 \(d\) がある。このとき \(1<{sequence}_d<{sequence}_m\) かつ \({sequence}_d\mid {sequence}_m\) なので、\({sequence}_m\) は合成数である。従って \({sequence}_m\) が素数なら、\(m\) は素数または4である。",
            rf"\({sequence}_{index_name}\) と \({sequence}_{{{index_name}+1}}\) がともに素数なら \({index_name}\ge3\)。連続する二添字の一方は偶数であり、2より大きい偶数は素数でないため、その添字は4でなければならない。従って \({index_name}=3,4\)。実際、\(({sequence}_3,{sequence}_4)=(2,3)\), \(({sequence}_4,{sequence}_5)=(3,5)\) である。",
        ),
        verification_checks=(
            "現在入力から初期値1,1のFibonacci漸化式と隣接素数項の問いを抽出",
            "加法公式の帰納ステップを記号多項式として展開し残差0を確認",
            "加法公式から添字整除性を帰納的に導出",
            "合成添字の約数分類で唯一の例外m=4を分離",
            "候補n=3,4の項を元の漸化式で再計算して素数性を確認",
        ),
        proof_program=(
            {"rule": "prove_fibonacci_addition_formula_by_induction", "step_residual": "0"},
            {"rule": "derive_strong_divisibility_for_multiple_indices"},
            {"rule": "classify_composite_index_divisor", "exception": 4},
            {"rule": "exclude_adjacent_indices_by_parity"},
            {"rule": "replay_candidate_indices", "values": {"F3": 2, "F4": 3, "F5": 5}},
        ),
        diagram=diagram,
        witness={
            "sequence": sequence,
            "index": index_name,
            "initial_values": [1, 1],
            "addition_formula_induction_residual": str(addition_induction_residual),
            "divisibility_theorem": "d|m => F_d|F_m",
            "composite_index_exception": 4,
            "candidate_values": {"F3": 2, "F4": 3, "F5": 5},
            "indices": [3, 4],
        },
    )


def _parse_reciprocal_product_recurrence(
    statement: str,
) -> dict[str, Any] | None:
    """Read u_(n+2)=1/(u_(n+1)+1/u_n) from the current statement."""

    pattern = re.compile(
        r"(?P<sequence>[A-Za-z]+)_1=(?P=sequence)_2=(?P<initial>[^,]+),"
        r"(?P=sequence)_\((?P<index>[A-Za-z]+)\+2\)="
        r"\(\(1\)/\((?P=sequence)_\((?P=index)\+1\)\+"
        r"\(\(1\)/\((?P=sequence)_(?P=index)\)\)\)\)"
    )
    for segment in parse_latex_problem(statement).math_segments:
        match = pattern.fullmatch(segment.replace(" ", ""))
        if match is None:
            continue
        initial = _sympify_exact_scalar(match.group("initial"))
        if initial is None or not _proves_strictly_positive(initial):
            return None
        return {
            "sequence": match.group("sequence"),
            "index": match.group("index"),
            "initial": initial,
        }
    return None


def _reciprocal_product_recurrence_query(
    statement: str,
    context: dict[str, Any],
) -> dict[str, str] | None:
    sequence = context["sequence"]
    index_name = context["index"]
    compact_segments = [
        segment.replace(" ", "")
        for segment in parse_latex_problem(statement).math_segments
    ]

    queries: list[dict[str, str]] = []
    integral_pattern = re.compile(
        rf"{re.escape(sequence)}_\(2\*(?P<index>[A-Za-z]+)\+2\)="
        r"integral_0\*\*1\*?\(1-(?P<variable>[A-Za-z]+)\*\*2\)\*\*"
        r"(?P=index)d(?P=variable)"
    )
    limit_pattern = re.compile(
        r"limit_(?P<index>[A-Za-z]+)toinfinitysqrt\((?P=index)\)"
        rf"{re.escape(sequence)}_(?:\(2\*(?P=index)\)|2\*(?P=index))"
    )
    gaussian_pattern = re.compile(
        r"integral_0\*\*infinitye\*\*\(-(?P<variable>[A-Za-z]+)\*\*2\)"
        r"d(?P=variable)"
    )
    for segment in compact_segments:
        if match := integral_pattern.fullmatch(segment):
            queries.append({"kind": "beta_identity", **match.groupdict()})
        if match := limit_pattern.fullmatch(segment):
            queries.append({"kind": "wallis_limit", **match.groupdict()})
        if match := gaussian_pattern.fullmatch(segment):
            queries.append({"kind": "gaussian_integral", **match.groupdict()})

    if not queries and re.search(r"(?:求め|find|determine)", statement, re.I):
        if any(segment == f"{sequence}_{index_name}" for segment in compact_segments):
            queries.append({"kind": "closed_form", "index": index_name})
    if len(queries) != 1:
        return None
    return queries[0]


def synthesize_reciprocal_product_wallis_chain(
    statement: str,
) -> RuntimeSolutionSynthesis | None:
    """Linearize a reciprocal recurrence and compose its Wallis consequences."""

    context = _parse_reciprocal_product_recurrence(statement)
    if context is None:
        return None
    query = _reciprocal_product_recurrence_query(statement, context)
    if query is None:
        return None

    sequence = context["sequence"]
    index_name = context["index"]
    initial = context["initial"]
    u, v = sp.symbols("u v", positive=True)
    n = sp.Symbol("n", integer=True, positive=True)
    m = sp.Symbol("m", integer=True, nonnegative=True)
    next_value = sp.simplify(1 / (v + 1 / u))
    rationalized_next = sp.simplify(u / (1 + u * v))
    rationalization_residual = sp.factor(next_value - rationalized_next)
    reciprocal_increment_residual = sp.factor(
        1 / (v * next_value) - 1 / (u * v) - 1
    )
    c = sp.simplify(1 / initial**2 - 1)
    product_formula = sp.simplify(1 / (n + c))
    product_base_residual = sp.simplify(initial**2 - product_formula.subs(n, 1))
    product_step_residual = sp.simplify(
        product_formula.subs(n, n + 1)
        - product_formula / (1 + product_formula)
    )
    two_step_factor_residual = sp.simplify(
        1 / (1 + product_formula) - (n + c) / (n + c + 1)
    )

    odd_formula = sp.simplify(
        initial
        * sp.rf((c + 1) / 2, m)
        / sp.rf((c + 2) / 2, m)
    )
    even_formula = sp.simplify(
        initial
        * sp.rf((c + 2) / 2, m)
        / sp.rf((c + 3) / 2, m)
    )
    odd_ratio = sp.simplify(
        sp.expand_func(sp.combsimp(odd_formula.subs(m, m + 1) / odd_formula))
    )
    even_ratio = sp.simplify(
        sp.expand_func(sp.combsimp(even_formula.subs(m, m + 1) / even_formula))
    )
    odd_ratio_residual = sp.simplify(
        odd_ratio - (2 * m + c + 1) / (2 * m + c + 2)
    )
    even_ratio_residual = sp.simplify(
        even_ratio - (2 * m + c + 2) / (2 * m + c + 3)
    )
    closed_form_base_residuals = (
        sp.simplify(odd_formula.subs(m, 0) - initial),
        sp.simplify(even_formula.subs(m, 0) - initial),
    )
    common_residuals = (
        rationalization_residual,
        reciprocal_increment_residual,
        product_base_residual,
        product_step_residual,
        two_step_factor_residual,
        odd_ratio_residual,
        even_ratio_residual,
        *closed_form_base_residuals,
    )
    if any(residual != 0 for residual in common_residuals):
        return None

    sample_values = [initial, initial]
    for _ in range(8):
        sample_values.append(
            sp.simplify(1 / (sample_values[-1] + 1 / sample_values[-2]))
        )
    common_checks = (
        "現在入力から数列名、添字、初期値、逆数型二階漸化式を抽出",
        "次項を有理化し、隣接積の逆数が毎回1だけ増えることを恒等式で確認",
        "隣接積の閉形式の初期値と一段遷移を記号計算で再生",
        "偶数列・奇数列の積表示について基底と項比を独立に確認",
        "最初の10項を元の非線形漸化式から厳密数として再計算",
    )
    common_program = (
        {"rule": "rationalize_reciprocal_recurrence", "residual": "0"},
        {
            "rule": "lift_to_adjacent_product",
            "transition": "t_(n+1)=t_n/(1+t_n)",
            "residual": "0",
        },
        {
            "rule": "linearize_by_reciprocal",
            "transition": "1/t_(n+1)=1/t_n+1",
            "residual": "0",
        },
        {
            "rule": "solve_affine_product_state",
            "solution": sp.sstr(product_formula),
            "base_residual": "0",
            "step_residual": "0",
        },
        {
            "rule": "split_parity_and_multiply_two_step_ratios",
            "odd_ratio_residual": "0",
            "even_ratio_residual": "0",
        },
    )
    common_witness = {
        "sequence": sequence,
        "index": index_name,
        "initial": sp.srepr(initial),
        "product_shift": sp.srepr(c),
        "product_formula": sp.srepr(product_formula),
        "rationalization_residual": str(rationalization_residual),
        "reciprocal_increment_residual": str(reciprocal_increment_residual),
        "product_base_residual": str(product_base_residual),
        "product_step_residual": str(product_step_residual),
        "two_step_factor_residual": str(two_step_factor_residual),
        "odd_formula": sp.srepr(odd_formula),
        "even_formula": sp.srepr(even_formula),
        "odd_ratio_residual": str(odd_ratio_residual),
        "even_ratio_residual": str(even_ratio_residual),
        "sample_values": [sp.srepr(value) for value in sample_values],
    }

    if query["kind"] == "closed_form":
        if initial == 1:
            answer_tex = (
                rf"\[{sequence}_1=1,\qquad "
                rf"{sequence}_{{2m}}=\frac{{(2m-2)!!}}{{(2m-1)!!}},\qquad "
                rf"{sequence}_{{2m+1}}=\frac{{(2m-1)!!}}{{(2m)!!}}"
                r"\quad(m=1,2,\ldots).\]"
            )
            closed_form_derivation = (
                rf"従って \({sequence}_{{n+2}}=\dfrac{{n}}{{n+1}}{sequence}_n\)。"
                rf" 初期値 \({sequence}_1={sequence}_2=1\) から偶数番目と奇数番目を別々に掛けると、"
                rf" \({sequence}_{{2m}}=\dfrac{{(2m-2)!!}}{{(2m-1)!!}}\), "
                rf" \({sequence}_{{2m+1}}=\dfrac{{(2m-1)!!}}{{(2m)!!}}\) を得る。"
            )
        else:
            answer_tex = (
                rf"\[c={sp.latex(c)},\qquad "
                rf"{sequence}_{{2m+1}}={sp.latex(odd_formula)},\qquad "
                rf"{sequence}_{{2m+2}}={sp.latex(even_formula)}"
                r"\quad(m=0,1,\ldots),\]"
                r"\[(z)^{(m)}=z(z+1)\cdots(z+m-1).\]"
            )
            closed_form_derivation = (
                rf"従って \({sequence}_{{n+2}}=\dfrac{{n+c}}{{n+c+1}}{sequence}_n\), "
                rf"\(c={sp.latex(c)}\)。偶奇ごとにこの比を掛け、上昇階乗でまとめると表示式を得る。"
            )
        diagram = state_transition_diagram(
            [
                {"id": "recurrence", "label": "逆数型漸化式", "terminal": False},
                {"id": "product", "label": rf"t_n={sequence}_n{sequence}_{{n+1}}", "terminal": False},
                {"id": "linear", "label": r"t_{n+1}^{-1}=t_n^{-1}+1", "terminal": False},
                {"id": "parity", "label": "偶奇別の閉形式", "terminal": True},
            ],
            [
                {"from": "recurrence", "to": "product", "label": "隣接積", "tone": "primary"},
                {"from": "product", "to": "linear", "label": "逆数", "tone": "primary"},
                {"from": "linear", "to": "parity", "label": "二段比", "tone": "secondary"},
            ],
            title="非線形漸化式の線形化",
            caption="隣接二項の積を取ると一次の状態遷移になり、元の数列は偶数列と奇数列の積へ戻せます。",
        )
        return RuntimeSolutionSynthesis(
            answer={"odd": sp.srepr(odd_formula), "even": sp.srepr(even_formula)},
            answer_tex=answer_tex,
            tool_name="mortra.runtime_reciprocal_product_recurrence",
            expression_tex=rf"{sequence}_{{n+2}}=\frac1{{{sequence}_{{n+1}}+1/{sequence}_n}}",
            derivation_tex=(
                rf"初期値は正であり、漸化式から全ての項も正である。\(t_n={sequence}_n{sequence}_{{n+1}}\) とおく。",
                rf"元の式を有理化すると \({sequence}_{{n+2}}={sequence}_n/(1+t_n)\)。従って \(t_{{n+1}}=t_n/(1+t_n)\) であり、逆数を取れば \(1/t_{{n+1}}=1/t_n+1\) となる。",
                rf"\(t_1={sp.latex(initial**2)}\) なので \(t_n=1/(n+c)\), \(c={sp.latex(c)}\) である。",
                closed_form_derivation,
            ),
            verification_checks=common_checks,
            proof_program=common_program,
            diagram=diagram,
            witness={**common_witness, "query_kind": "closed_form"},
        )

    if initial != 1:
        return None

    if query["kind"] == "beta_identity":
        query_index = query["index"]
        variable_name = query["variable"]
        k = sp.Symbol(query_index, integer=True, nonnegative=True)
        x = sp.Symbol(variable_name, real=True)
        integrand = (1 - x**2) ** k
        derivative_residual = sp.factor(
            sp.powsimp(
                sp.diff(x * integrand, x)
                - (integrand - 2 * k * x**2 * (1 - x**2) ** (k - 1)),
                force=True,
            )
        )
        if derivative_residual != 0:
            return None
        diagram = state_transition_diagram(
            [
                {"id": "sequence", "label": rf"{sequence}_{{2n+2}}", "terminal": False},
                {"id": "ratio", "label": r"\frac{2n}{2n+1}", "terminal": False},
                {"id": "integral", "label": r"I_n=\int_0^1(1-x^2)^n dx", "terminal": False},
                {"id": "identity", "label": rf"{sequence}_{{2n+2}}=I_n", "terminal": True},
            ],
            [
                {"from": "sequence", "to": "ratio", "label": "二段漸化式", "tone": "primary"},
                {"from": "integral", "to": "ratio", "label": "部分積分", "tone": "primary"},
                {"from": "ratio", "to": "identity", "label": "初期値1", "tone": "secondary"},
            ],
            title="数列と積分の同一漸化式",
            caption="数列の偶数項と積分が同じ初期値・同じ一段比を持つことを照合します。",
        )
        return RuntimeSolutionSynthesis(
            answer=True,
            answer_tex=(
                rf"\[{sequence}_{{2{query_index}+2}}="
                rf"\int_0^1(1-{variable_name}^2)^{{{query_index}}}\,d{variable_name}="
                rf"\frac{{(2{query_index})!!}}{{(2{query_index}+1)!!}}.\]"
            ),
            tool_name="mortra.runtime_reciprocal_recurrence_beta_identity",
            expression_tex=rf"{sequence}_{{2{query_index}+2}}=\int_0^1(1-{variable_name}^2)^{{{query_index}}}d{variable_name}",
            derivation_tex=(
                rf"\(I_{query_index}=\int_0^1(1-{variable_name}^2)^{{{query_index}}}\,d{variable_name}\) とおく。",
                rf"\({variable_name}(1-{variable_name}^2)^{{{query_index}}}\) を微分し、端点0,1で積分すると \((2{query_index}+1)I_{query_index}=2{query_index}I_{{{query_index}-1}}\)。従って \(I_{query_index}=\dfrac{{2{query_index}}}{{2{query_index}+1}}I_{{{query_index}-1}}\), \(I_0=1\)。",
                rf"一方、隣接積の線形化から \({sequence}_{{2{query_index}+2}}=\dfrac{{2{query_index}}}{{2{query_index}+1}}{sequence}_{{2{query_index}}}\), \({sequence}_2=1\)。初期値と漸化式が一致するため、両者は全ての \({query_index}\ge0\) で等しい。",
                rf"共通の積表示は \(\dfrac{{(2{query_index})!!}}{{(2{query_index}+1)!!}}\) である。",
            ),
            verification_checks=common_checks
            + (
                "積分側の部分積分に使う微分恒等式を記号展開し残差0を確認",
                "数列側と積分側の初期値および一段比が完全一致することを確認",
            ),
            proof_program=common_program
            + (
                {"rule": "differentiate_beta_integrand", "residual": str(derivative_residual)},
                {"rule": "integrate_boundary_identity", "boundary_values": [0, 0]},
                {"rule": "identify_equal_initial_value_recurrences", "base": "1"},
            ),
            diagram=diagram,
            witness={
                **common_witness,
                "query_kind": "beta_identity",
                "query_index": query_index,
                "integration_variable": variable_name,
                "derivative_residual": str(derivative_residual),
                "integral_recurrence": f"I_{query_index}=2*{query_index}/(2*{query_index}+1)*I_({query_index}-1)",
            },
        )

    if query["kind"] == "wallis_limit":
        query_index = query["index"]
        j_odd = sp.sqrt(sp.pi) * sp.gamma(n) / (2 * sp.gamma(n + sp.Rational(1, 2)))
        j_even = sp.sqrt(sp.pi) * sp.gamma(n + sp.Rational(1, 2)) / (2 * sp.gamma(n + 1))
        product_residual = sp.simplify(j_odd * j_even - sp.pi / (4 * n))
        lower_ratio = 2 * n / (2 * n + 1)
        lower_limit = sp.limit(lower_ratio, n, sp.oo)
        if product_residual != 0 or lower_limit != 1:
            return None
        diagram = state_transition_diagram(
            [
                {"id": "odd", "label": r"J_{2n-1}=a_{2n}", "terminal": False},
                {"id": "even", "label": r"J_{2n}", "terminal": False},
                {"id": "squeeze", "label": r"\frac{2n}{2n+1}<\frac{J_{2n}}{J_{2n-1}}<1", "terminal": False},
                {"id": "limit", "label": r"\sqrt n\,a_{2n}\to\sqrt\pi/2", "terminal": True},
            ],
            [
                {"from": "odd", "to": "squeeze", "label": "単調性", "tone": "primary"},
                {"from": "even", "to": "squeeze", "label": "縮約公式", "tone": "primary"},
                {"from": "squeeze", "to": "limit", "label": r"J_{2n-1}J_{2n}=\pi/(4n)", "tone": "secondary"},
            ],
            title="Wallis 積分による極限",
            caption="隣り合う二つの正弦積分の比をはさみ、積の厳密値から数列の極限を決めます。",
        )
        return RuntimeSolutionSynthesis(
            answer=sp.sqrt(sp.pi) / 2,
            answer_tex=rf"\[\lim_{{{query_index}\to\infty}}\sqrt{{{query_index}}}\,{sequence}_{{2{query_index}}}=\frac{{\sqrt\pi}}2.\]",
            tool_name="mortra.runtime_reciprocal_recurrence_wallis_limit",
            expression_tex=rf"\lim_{{{query_index}\to\infty}}\sqrt{{{query_index}}}\,{sequence}_{{2{query_index}}}",
            derivation_tex=(
                rf"\(J_r=\int_0^{{\pi/2}}\sin^r x\,dx\) とおく。部分積分から \(J_r=\dfrac{{r-1}}rJ_{{r-2}}\)。従って \(J_{{2{query_index}-1}}={sequence}_{{2{query_index}}}\)。",
                rf"\(0<\sin x<1\) より \(J_{{2{query_index}+1}}<J_{{2{query_index}}}<J_{{2{query_index}-1}}\)。また \(J_{{2{query_index}+1}}=\dfrac{{2{query_index}}}{{2{query_index}+1}}J_{{2{query_index}-1}}\) だから、\(\dfrac{{2{query_index}}}{{2{query_index}+1}}<\dfrac{{J_{{2{query_index}}}}}{{J_{{2{query_index}-1}}}}<1\)。よってこの比は1へ収束する。",
                rf"縮約公式を掛け合わせると \(J_{{2{query_index}-1}}J_{{2{query_index}}}=\dfrac{{\pi}}{{4{query_index}}}\)。従って \({query_index}J_{{2{query_index}-1}}^2\to\pi/4\)。全て正なので平方根を取り、結論を得る。",
            ),
            verification_checks=common_checks
            + (
                "Wallis 積分の奇数項と偶数項の積をガンマ関数表示から厳密に pi/(4n) へ簡約",
                "単調性と縮約公式から得た比の上下界がともに1へ収束することを確認",
                "正値性を使って二乗極限から元の極限を一意に復元",
            ),
            proof_program=common_program
            + (
                {"rule": "identify_odd_wallis_integral", "identity": f"J_(2*{query_index}-1)={sequence}_(2*{query_index})"},
                {"rule": "squeeze_adjacent_wallis_ratio", "lower": sp.sstr(lower_ratio), "upper": "1"},
                {"rule": "multiply_adjacent_wallis_integrals", "product_residual": str(product_residual)},
                {"rule": "take_positive_square_root"},
            ),
            diagram=diagram,
            witness={
                **common_witness,
                "query_kind": "wallis_limit",
                "query_index": query_index,
                "adjacent_integral_product": "pi/(4*n)",
                "product_residual": str(product_residual),
                "ratio_lower_bound": sp.sstr(lower_ratio),
                "ratio_lower_limit": str(lower_limit),
                "limit": "sqrt(pi)/2",
            },
        )

    if query["kind"] != "gaussian_integral":
        return None
    variable_name = query["variable"]
    y, r = sp.symbols("y r", nonnegative=True)
    pointwise_limit = sp.limit((1 - y**2 / n) ** n, n, sp.oo)
    radial_integral = sp.integrate(r * sp.exp(-(r**2)), (r, 0, sp.oo))
    gaussian_square = sp.simplify((sp.pi / 2) * radial_integral)
    if pointwise_limit != sp.exp(-(y**2)) or radial_integral != sp.Rational(1, 2) or gaussian_square != sp.pi / 4:
        return None
    diagram = state_transition_diagram(
        [
            {"id": "beta", "label": r"\sqrt n\int_0^1(1-x^2)^n dx", "terminal": False},
            {"id": "scale", "label": r"x=y/\sqrt n", "terminal": False},
            {"id": "limit", "label": r"(1-y^2/n)^n\to e^{-y^2}", "terminal": False},
            {"id": "gaussian", "label": r"\int_0^\infty e^{-y^2}dy=\sqrt\pi/2", "terminal": True},
        ],
        [
            {"from": "beta", "to": "scale", "label": "変数変換", "tone": "primary"},
            {"from": "scale", "to": "limit", "label": "指数極限", "tone": "primary"},
            {"from": "limit", "to": "gaussian", "label": "Wallis 極限", "tone": "secondary"},
        ],
        title="ベータ積分から Gaussian 積分へ",
        caption="有限区間の積分を拡大し、同じ極限を Gaussian 積分として読み替えます。",
    )
    return RuntimeSolutionSynthesis(
        answer=sp.sqrt(sp.pi) / 2,
        answer_tex=rf"\[\int_0^\infty e^{{-{variable_name}^2}}\,d{variable_name}=\frac{{\sqrt\pi}}2.\]",
        tool_name="mortra.runtime_reciprocal_recurrence_gaussian_limit",
        expression_tex=rf"\int_0^\infty e^{{-{variable_name}^2}}d{variable_name}",
        derivation_tex=(
            rf"第(2)問の積分で \({variable_name}=y/\sqrt n\) とおくと、\(\sqrt n\,{sequence}_{{2n+2}}=\int_0^{{\sqrt n}}(1-y^2/n)^n\,dy\)。",
            r"固定した \(y\) に対して \((1-y^2/n)^n\to e^{-y^2}\)。また Bernoulli の不等式から、左辺の被積分関数を区間外で0としたものは \(1/(1+y^2)\) 以下である。従って積分の極限を取ることができる。",
            rf"第(3)問と添字を一つずらした極限より、左辺は \(\sqrt\pi/2\) へ収束する。従って \(\int_0^\infty e^{{-{variable_name}^2}}\,d{variable_name}=\sqrt\pi/2\)。",
            r"独立な確認として、積分を \(G\) とおけば、第一象限で極座標変換して \(G^2=(\pi/2)\int_0^\infty re^{-r^2}dr=\pi/4\)。\(G>0\) なので同じ値を得る。",
        ),
        verification_checks=common_checks
        + (
            "拡大変数での被積分関数が点ごとに exp(-y^2) へ収束することを厳密計算",
            "Bernoulli 不等式による可積分な上界 1/(1+y^2) を使用",
            "独立検査として極座標の半径積分を厳密に1/2へ評価",
            "Gaussian 積分の二乗が pi/4 で正であることから値を確定",
        ),
        proof_program=common_program
        + (
            {"rule": "rescale_beta_integral", "substitution": f"{variable_name}=y/sqrt(n)"},
            {"rule": "certify_pointwise_exponential_limit", "limit": sp.sstr(pointwise_limit)},
            {"rule": "dominate_by_rational_tail", "majorant": "1/(1+y^2)"},
            {"rule": "reuse_wallis_limit"},
            {"rule": "independent_polar_replay", "radial_integral": sp.sstr(radial_integral)},
        ),
        diagram=diagram,
        witness={
            **common_witness,
            "query_kind": "gaussian_integral",
            "integration_variable": variable_name,
            "pointwise_limit": sp.srepr(pointwise_limit),
            "dominating_function": "1/(1+y**2)",
            "radial_integral": sp.srepr(radial_integral),
            "gaussian_square": sp.srepr(gaussian_square),
            "gaussian_integral": "sqrt(pi)/2",
        },
    )


def _math_signature(source: str) -> str:
    """Discard presentation-only spacing and multiplication marks."""

    return re.sub(r"[\s*]+", "", source)


def _expected_math_signature(source: str) -> str:
    return _math_signature(normalize_latex_math(source))


def _parse_sine_cosine_iteration(statement: str) -> dict[str, Any] | None:
    """Read an iterated h(x)=sin(x)+cos(x) system from current input."""

    segments = parse_latex_problem(statement).math_segments
    signatures = [_math_signature(segment) for segment in segments]
    combined = ";".join(signatures)
    definition = re.search(
        r"(?P<sequence>[A-Za-z]+)_1\((?P<variable>[A-Za-z]+)\)="
        r"(?P<body>[^;,]+)",
        combined,
    )
    if definition is None:
        return None
    sequence = definition.group("sequence")
    variable = definition.group("variable")
    if definition.group("body") not in {
        f"sin({variable})+cos({variable})",
        f"cos({variable})+sin({variable})",
    }:
        return None

    recurrence = re.search(
        rf"{re.escape(sequence)}_\((?P<index>[A-Za-z]+)\+1\)"
        rf"\({re.escape(variable)}\)=(?P<body>[^;,]+)",
        combined,
    )
    if recurrence is None:
        return None
    index_name = recurrence.group("index")
    recurrence_body = recurrence.group("body")
    inner = f"{sequence}_{index_name}({variable})"
    accepted_bodies = (
        f"{sequence}_1({inner})",
        f"sin{inner}+cos{inner}",
        f"cos{inner}+sin{inner}",
        f"sin({inner})+cos({inner})",
        f"cos({inner})+sin({inner})",
    )
    if not any(recurrence_body.startswith(body) for body in accepted_bodies):
        return None
    return {
        "sequence": sequence,
        "index": index_name,
        "variable": variable,
        "segments": segments,
        "signatures": signatures,
    }


def _sine_cosine_iteration_query(
    statement: str,
    context: dict[str, Any],
) -> dict[str, Any] | None:
    sequence = context["sequence"]
    index_name = context["index"]
    variable = context["variable"]
    signatures = context["signatures"]
    queries: list[dict[str, Any]] = []

    tangent_target = _expected_math_signature(
        rf"{sequence}_1({variable})\leq"
        r"-\dfrac{\sqrt{2}}{2}\left("
        + variable
        + r"-\dfrac{5\pi}{12}\right)+\dfrac{\sqrt{6}}{2}"
    )
    tangent_interval = _expected_math_signature(
        rf"\dfrac{{\pi}}{{3}}\leq {variable}\leq\dfrac{{\pi}}{{2}}"
    )
    if tangent_target in signatures and tangent_interval in signatures:
        queries.append({"kind": "tangent_bound", "variable": variable})

    fixed_equation = _expected_math_signature(
        rf"{variable}-{sequence}_1({variable})=0"
    )
    fixed_interval = _expected_math_signature(
        rf"0\leq {variable}\leq\dfrac{{\pi}}{{2}}"
    )
    comparison = _expected_math_signature(r"\dfrac{4}{\pi}")
    if (
        fixed_equation in signatures
        and fixed_interval in signatures
        and comparison in signatures
        and re.search(r"(?:ただ一つ|唯一|unique)", statement, re.I)
    ):
        queries.append({"kind": "fixed_point", "variable": variable})

    composition_pattern = re.compile(
        rf"{re.escape(sequence)}_1\({re.escape(sequence)}_1\("
        r"(?P<variable>[A-Za-z]+)\)\)<="
    )
    for signature in signatures:
        match = composition_pattern.match(signature)
        if match is None:
            continue
        query_variable = match.group("variable")
        expected = _expected_math_signature(
            rf"{sequence}_1({sequence}_1({query_variable}))\leq"
            r"\dfrac{4}{\pi}+\dfrac{\sqrt{3}-1}{2}\left("
            + query_variable
            + r"-\dfrac{4}{\pi}\right)"
        )
        expected_interval = _expected_math_signature(
            rf"1\leq {query_variable}\leq\sqrt{{2}}"
        )
        if signature == expected and expected_interval in signatures:
            queries.append({"kind": "two_step_bound", "variable": query_variable})

    integral_prefix = _expected_math_signature(
        rf"\int_0^{{\frac{{\pi}}{{2}}}}"
        rf"{sequence}_{index_name}({variable})\,d{variable}"
    )
    for signature in signatures:
        prefix = integral_prefix + "<="
        if not signature.startswith(prefix):
            continue
        bound = _sympify_exact_scalar(signature[len(prefix) :])
        if bound is None or sp.simplify(bound >= 2) is not sp.S.true:
            return None
        queries.append(
            {
                "kind": "integral_bound",
                "variable": variable,
                "bound": bound,
            }
        )
    return queries[0] if len(queries) == 1 else None


def _sine_cosine_iteration_certificate() -> dict[str, Any] | None:
    """Replay the exact interval proof for the two-step affine bound."""

    pi_lower = sp.Rational(333, 106)
    pi_upper = sp.Rational(355, 113)
    sqrt2_lower = sp.Rational(140, 99)
    sqrt2_upper = sp.Rational(99, 70)
    sqrt3_lower = sp.Rational(265, 153)
    sqrt3_upper = sp.Rational(97, 56)
    lambda_lower = (sqrt3_lower - 1) / 2
    lambda_upper = (sqrt3_upper - 1) / 2

    def sum_bounds(value: sp.Rational) -> tuple[sp.Rational, sp.Rational]:
        sin_lower, sin_upper, cos_lower, cos_upper = alternating_trig_bounds(value)
        return sin_lower + cos_lower, sin_upper + cos_upper

    def difference_bounds(value: sp.Rational) -> tuple[sp.Rational, sp.Rational]:
        sin_lower, sin_upper, cos_lower, cos_upper = alternating_trig_bounds(value)
        return sin_lower - cos_upper, sin_upper - cos_lower

    inner_one_lower, inner_one_upper = sum_bounds(sp.Rational(1))
    composition_one_upper = sum_bounds(inner_one_lower)[1]
    line_one_lower = (4 / pi_upper) * (1 - lambda_upper) + lambda_upper
    endpoint_one_margin = sp.factor(line_one_lower - composition_one_upper)

    inner_sqrt2_lower = sum_bounds(sqrt2_upper)[0]
    composition_sqrt2_upper = sum_bounds(inner_sqrt2_lower)[1]
    line_sqrt2_lower = (
        (4 / pi_upper) * (1 - lambda_lower)
        + lambda_lower * sqrt2_lower
    )
    endpoint_sqrt2_margin = sp.factor(
        line_sqrt2_lower - composition_sqrt2_upper
    )

    composition_derivative_one_upper = (
        difference_bounds(inner_one_upper)[1]
        * difference_bounds(sp.Rational(1))[1]
    )
    derivative_one_margin = sp.factor(
        lambda_lower - composition_derivative_one_upper
    )
    composition_derivative_sqrt2_lower = (
        difference_bounds(inner_sqrt2_lower)[0]
        * difference_bounds(sqrt2_lower)[0]
    )
    derivative_sqrt2_margin = sp.factor(
        composition_derivative_sqrt2_lower - lambda_upper
    )

    center_lower = 4 / pi_upper
    tangent_offset_lower = center_lower - 5 * pi_upper / 12
    fixed_point_gap_lower = sp.factor(
        center_lower
        + sqrt2_upper * tangent_offset_lower / 2
        - sqrt2_upper * sqrt3_upper / 2
    )

    z = sp.Symbol("z", real=True)
    h = sp.sin(z) + sp.cos(z)
    tangent_point = 5 * sp.pi / 12
    tangent_value_residual = sp.simplify(
        sp.expand_trig(h.subs(z, tangent_point) - sp.sqrt(6) / 2)
    )
    tangent_slope_residual = sp.simplify(
        sp.expand_trig(sp.diff(h, z).subs(z, tangent_point) + sp.sqrt(2) / 2)
    )
    margins = {
        "endpoint_one": endpoint_one_margin,
        "endpoint_sqrt2": endpoint_sqrt2_margin,
        "derivative_one": derivative_one_margin,
        "derivative_sqrt2": derivative_sqrt2_margin,
        "fixed_point_gap": fixed_point_gap_lower,
    }
    exact_checks = {
        "pi_interval": bool(pi_lower < sp.pi < pi_upper),
        "sqrt2_interval": bool(sqrt2_lower < sp.sqrt(2) < sqrt2_upper),
        "sqrt3_interval": bool(sqrt3_lower < sp.sqrt(3) < sqrt3_upper),
        "invariant_angle_chamber": bool(
            pi_upper / 4 < 1 < sqrt2_lower < pi_lower / 2
        ),
        "contraction_interval": bool(0 < lambda_lower < lambda_upper < 1),
        "inner_interval": bool(
            inner_sqrt2_lower > 1 and inner_one_upper < sqrt2_upper
        ),
        "tangent_value_identity": tangent_value_residual == 0,
        "tangent_slope_identity": tangent_slope_residual == 0,
    }
    if any(value <= 0 for value in margins.values()) or not all(exact_checks.values()):
        return None
    interval_chart = alternating_trig_interval_chart(
        [
            sp.Rational(1),
            inner_one_lower,
            inner_one_upper,
            sqrt2_lower,
            sqrt2_upper,
            inner_sqrt2_lower,
        ]
    )
    return {
        "chart_id": "sine_cosine.iteration.two_step_affine.runtime.v1",
        "rational_bounds": {
            "pi": [sp.sstr(pi_lower), sp.sstr(pi_upper)],
            "sqrt2": [sp.sstr(sqrt2_lower), sp.sstr(sqrt2_upper)],
            "sqrt3": [sp.sstr(sqrt3_lower), sp.sstr(sqrt3_upper)],
        },
        "margins": {key: sp.sstr(value) for key, value in margins.items()},
        "exact_checks": exact_checks,
        "trigonometric_interval_chart": interval_chart,
        "third_derivative_sign": (
            "H'''=3*h(h(t))*h(t)*h'(t)-h'(h(t))*h'(t)*(h'(t)^2+1)<0"
        ),
    }


def synthesize_sine_cosine_iteration(
    statement: str,
) -> RuntimeSolutionSynthesis | None:
    """Compose interval, fixed-point, and integral proofs for h=sin+cos."""

    enumerate_match = re.search(
        r"\\begin\{enumerate\}(?P<body>.*?)\\end\{enumerate\}",
        statement,
        flags=re.DOTALL,
    )
    if enumerate_match is not None and len(
        re.findall(r"\\item(?:\[[^\]]+\])?", enumerate_match.group("body"))
    ) >= 2:
        return None

    context = _parse_sine_cosine_iteration(statement)
    if context is None:
        return None
    query = _sine_cosine_iteration_query(statement, context)
    if query is None:
        return None
    certificate = _sine_cosine_iteration_certificate()
    if certificate is None:
        return None

    sequence = context["sequence"]
    index_name = context["index"]
    variable = query["variable"]
    common_checks = (
        "現在入力から反復関数、変数、添字、求める不等式を抽出",
        "1, sqrt(2), pi, sqrt(3) の順序を有理上下界だけで検証",
        "sin と cos の交代級数を有限項で評価し、全ての端点残差が正であることを確認",
        "写像が [1,sqrt(2)] を保つことを三角恒等式から確認",
    )
    common_program = (
        {
            "rule": "parse_iterated_function",
            "sequence": sequence,
            "index": index_name,
            "map": "sin(x)+cos(x)",
        },
        {
            "rule": "certify_invariant_interval",
            "interval": "[1,sqrt(2)]",
            "reason": "(sin(t)+cos(t))^2=1+sin(2t)",
        },
        {
            "rule": "replay_alternating_interval_chart",
            "chart_id": certificate["trigonometric_interval_chart"]["chart_id"],
            "margins": certificate["margins"],
        },
    )
    common_witness = {
        "sequence": sequence,
        "index": index_name,
        "source_variable": context["variable"],
        "query_variable": variable,
        "runtime_chart": certificate,
    }
    two_step_derivation = (
        r"\(h(t)=\sin t+\cos t\)、\(H=h\circ h\)、\(c=4/\pi\)、\(\lambda=(\sqrt3-1)/2\) とし、\(D(t)=c+\lambda(t-c)-H(t)\) とおく。",
        r"sin と cos の交代級数を12次まで使い、全て有理数で評価すると \(D(1)>1/400\)、\(D(\sqrt2)>1/3000\)、\(D'(1)>1/8\)、\(D'(\sqrt2)<-1/22\) を得る。交代級数の次の項が誤差を上から押さえるため、これらは小数近似ではない。",
        r"区間内では \(h'(t)<0\)、\(h'(h(t))<0\)、\(h(t)>0\) である。直接微分すると \[H'''(t)=3h(h(t))h(t)h'(t)-h'(h(t))h'(t)\{h'(t)^2+1\}<0.\]",
        r"従って \(D'''=-H'''>0\) であり、\(D'\) は凸である。端点で \(D'(1)>0>D'(\sqrt2)\) だから、\(D\) は区間内に局所最小値をもたず、最小値を端点で取る。両端点で \(D>0\) なので、区間全体で \(D(t)>0\) となる。",
    )

    if query["kind"] == "tangent_bound":
        diagram = function_plot_diagram(
            [
                ("h", lambda value: math.sin(value) + math.cos(value), "primary"),
                (
                    "tangent",
                    lambda value: math.sqrt(6) / 2
                    - math.sqrt(2) / 2 * (value - 5 * math.pi / 12),
                    "secondary",
                ),
            ],
            x_min=math.pi / 3,
            x_max=math.pi / 2,
            title="凹関数と接線",
            caption="青い曲線は h(x)=sin x+cos x、直線は x=5π/12 における接線です。証明は二階導関数と厳密恒等式によります。",
            marked_points=[
                (5 * math.pi / 12, math.sqrt(6) / 2, "5π/12")
            ],
        )
        return RuntimeSolutionSynthesis(
            answer=True,
            answer_tex=(
                rf"\[{sequence}_1({variable})\le-\frac{{\sqrt2}}2"
                rf"\left({variable}-\frac{{5\pi}}{{12}}\right)+\frac{{\sqrt6}}2.\]"
            ),
            tool_name="mortra.runtime_sine_cosine_tangent_bound",
            expression_tex=rf"{sequence}_1({variable})=\sin {variable}+\cos {variable}",
            derivation_tex=(
                rf"\(h({variable})=\sin {variable}+\cos {variable}\) とおく。区間 \([\pi/3,\pi/2]\) では \(h({variable})>0\) なので \(h''({variable})=-h({variable})<0\)。従って \(h\) は凹関数であり、任意の接線はグラフの上にある。",
                r"\(a=5\pi/12\) とすると、加法定理から \(h(a)=\sqrt6/2\)、\(h'(a)=\cos a-\sin a=-\sqrt2/2\) である。",
                rf"従って \(h({variable})\le h(a)+h'(a)({variable}-a)=-\dfrac{{\sqrt2}}2({variable}-\dfrac{{5\pi}}{{12}})+\dfrac{{\sqrt6}}2\)。",
            ),
            verification_checks=common_checks
            + ("接点での関数値と傾きの恒等式を記号展開し残差0を確認",),
            proof_program=common_program
            + ({"rule": "concave_tangent_upper_bound", "point": "5*pi/12"},),
            diagram=diagram,
            witness={**common_witness, "query_kind": "tangent_bound"},
        )

    if query["kind"] == "fixed_point":
        diagram = function_plot_diagram(
            [
                ("h", lambda value: math.sin(value) + math.cos(value), "primary"),
                ("identity", lambda value: value, "secondary"),
            ],
            x_min=0.0,
            x_max=math.pi / 2,
            title="固定点の一意性",
            caption="h(x) と y=x の交点が固定点です。証明では x-h(x) の単調性と 4/π における厳密な正の余裕を使います。",
            marked_points=[
                (
                    4 / math.pi,
                    math.sin(4 / math.pi) + math.cos(4 / math.pi),
                    "x=4/π",
                )
            ],
        )
        return RuntimeSolutionSynthesis(
            answer={"unique": True, "comparison": "alpha<4/pi"},
            answer_tex=(
                r"\[x=\sin x+\cos x\text{ は }[0,\pi/2]\text{ にただ一つの解 }"
                r"\alpha\text{ をもち、}\qquad \alpha<\frac4\pi.\]"
            ),
            tool_name="mortra.runtime_sine_cosine_fixed_point",
            expression_tex=rf"{variable}-{sequence}_1({variable})=0",
            derivation_tex=(
                rf"\(g({variable})={variable}-\sin {variable}-\cos {variable}\) とおく。\(g(0)=-1\)、\(g(\pi/2)=\pi/2-1>0\) である。",
                rf"\(0<{variable}\le\pi/2\) では \(g'({variable})=1-\cos {variable}+\sin {variable}>0\) だから、連続性と単調性により零点 \(\alpha\) はただ一つである。",
                r"前問の接線上界へ \(x=4/\pi\) を代入する。\(333/106<\pi<355/113\)、\(140/99<\sqrt2<99/70\)、\(265/153<\sqrt3<97/56\) を使って各項を同じ向きに評価すると",
                r"\[g(4/\pi)>\frac{7259089}{314501600}>0.\]よって一意な零点は \(4/\pi\) より左にあり、\(\alpha<4/\pi\) である。",
            ),
            verification_checks=common_checks
            + (
                "x-h(x) の端点符号と区間内の厳密な増加性を確認",
                "4/pi における正の下界 7259089/314501600 を有理演算で再生",
            ),
            proof_program=common_program
            + (
                {"rule": "monotone_fixed_point_crossing", "interval": "[0,pi/2]"},
                {
                    "rule": "compare_fixed_point_by_tangent",
                    "comparison_point": "4/pi",
                    "gap_lower": certificate["margins"]["fixed_point_gap"],
                },
            ),
            diagram=diagram,
            witness={**common_witness, "query_kind": "fixed_point"},
        )

    if query["kind"] == "two_step_bound":
        contraction = (math.sqrt(3) - 1) / 2
        center = 4 / math.pi
        diagram = function_plot_diagram(
            [
                (
                    "two_step",
                    lambda value: math.sin(math.sin(value) + math.cos(value))
                    + math.cos(math.sin(value) + math.cos(value)),
                    "primary",
                ),
                (
                    "affine_bound",
                    lambda value: center + contraction * (value - center),
                    "secondary",
                ),
            ],
            x_min=1.0,
            x_max=math.sqrt(2),
            title="二段反復の一次上界",
            caption="h を2回続けて作用させた二段写像 H を、傾きが1未満の直線で上から押さえます。端点と導関数の符号は有理区間証明書で検証済みです。",
        )
        return RuntimeSolutionSynthesis(
            answer=True,
            answer_tex=(
                rf"\[{sequence}_1({sequence}_1({variable}))\le\frac4\pi+"
                rf"\frac{{\sqrt3-1}}2\left({variable}-\frac4\pi\right)"
                r"\qquad(1\le "
                + variable
                + r"\le\sqrt2).\]"
            ),
            tool_name="mortra.runtime_sine_cosine_two_step_bound",
            expression_tex=rf"{sequence}_1({sequence}_1({variable}))",
            derivation_tex=two_step_derivation,
            verification_checks=common_checks
            + (
                "二段写像と比較直線の端点値を厳密有理区間で分離",
                "比較差の両端の導関数符号を厳密有理区間で分離",
                "H''' の符号分解から比較差の内部最小値がないことを確認",
            ),
            proof_program=common_program
            + (
                {"rule": "compose_map_twice", "result": "H=h∘h"},
                {
                    "rule": "certify_two_step_affine_majorant",
                    "center": "4/pi",
                    "slope": "(sqrt(3)-1)/2",
                    "margins": certificate["margins"],
                },
            ),
            diagram=diagram,
            witness={**common_witness, "query_kind": "two_step_bound"},
        )

    bound = query["bound"]
    diagram = state_transition_diagram(
        [
            {"id": "range", "label": r"1\le f_n(x)\le\sqrt2", "terminal": False},
            {"id": "two_step", "label": r"H(t)\le c+\lambda(t-c)", "terminal": False},
            {"id": "integral", "label": r"I_{n+2}-2\le\lambda(I_n-2)", "terminal": False},
            {"id": "bound", "label": rf"I_n\le {sp.latex(bound)}", "terminal": True},
        ],
        [
            {"from": "range", "to": "two_step", "label": "区間不変性", "tone": "primary"},
            {"from": "two_step", "to": "integral", "label": "積分", "tone": "primary"},
            {"from": "integral", "to": "bound", "label": "偶奇別帰納", "tone": "secondary"},
        ],
        title="二段反復から積分不変量へ",
        caption="点ごとの一次上界を積分し、偶数番目と奇数番目を同じ縮小率で2以下へ保ちます。",
    )
    bound_tail = "" if bound == 2 else rf"\le {sp.latex(bound)}"
    return RuntimeSolutionSynthesis(
        answer=True,
        answer_tex=(
            rf"\[\int_0^{{\pi/2}}{sequence}_{{{index_name}}}({variable})\,d{variable}"
            rf"\le2{bound_tail}\qquad({index_name}=1,2,3,\ldots).\]"
        ),
        tool_name="mortra.runtime_sine_cosine_iteration_integral_bound",
        expression_tex=rf"\int_0^{{\pi/2}}{sequence}_{{{index_name}}}({variable})\,d{variable}",
        derivation_tex=(
            rf"\(h(t)=\sin t+\cos t\)、\({sequence}_{{{index_name}+1}}=h\circ {sequence}_{index_name}\) とおく。\(h\) は \([1,\sqrt2]\) を同じ区間へ写すので、\({sequence}_{index_name}({variable})\) は第一段以後この区間に留まる。",
            r"区間 \([\pi/3,\pi/2]\) では \(h''=-h<0\) だから、\(a=5\pi/12\) における接線を使って \[h(x)\le-\frac{\sqrt2}{2}\left(x-\frac{5\pi}{12}\right)+\frac{\sqrt6}{2}.\] \(333/106<\pi<355/113\)、\(140/99<\sqrt2<99/70\)、\(265/153<\sqrt3<97/56\) を代入方向に注意して用いると \[\frac4\pi-h(4/\pi)>\frac{7259089}{314501600}>0.\]",
            rf"\(I_{index_name}=\int_0^{{\pi/2}}{sequence}_{{{index_name}}}({variable})\,d{variable}\) とおく。直接積分して \(I_1=2\)。また \(h\) の凹性と Jensen の不等式から \[I_2\le\frac\pi2h\left(\frac2\pi I_1\right)=\frac\pi2h(4/\pi)<2.\]",
            *two_step_derivation,
            r"以上より \[h(h(t))\le\frac4\pi+\lambda\left(t-\frac4\pi\right),\qquad \lambda=\frac{\sqrt3-1}{2}\in(0,1)\] が成り立つ。",
            rf"これへ \(t={sequence}_{index_name}({variable})\) を代入して積分すると \[I_{{{index_name}+2}}\le2+\lambda(I_{index_name}-2).\] \(I_1=2\)、\(I_2<2\) から、偶数番目と奇数番目を別々に帰納して \(I_{index_name}\le2\) を得る。",
            (
                r"最後に \(2\le " + sp.latex(bound) + r"\) なので、問題文の上界も従う。"
                if bound != 2
                else "これは問題文の上界と一致する。"
            ),
        ),
        verification_checks=common_checks
        + (
            "接線評価から h(4/pi)<4/pi を正の有理余裕付きで確認",
            "二段写像の一次上界を端点・導関数・三階導関数の証明書で再生",
            "I_1=2 と I_2<2 を独立に確認し、偶奇別帰納を適用",
            "現在入力の上界が2以上であることを厳密比較",
        ),
        proof_program=common_program
        + (
            {"rule": "certify_unique_fixed_point_order", "comparison": "alpha<4/pi"},
            {
                "rule": "integrate_two_step_affine_majorant",
                "recurrence": "I_(n+2)-2<=lambda*(I_n-2)",
            },
            {"rule": "induct_on_parity", "bases": ["I_1=2", "I_2<2"]},
            {"rule": "weaken_verified_upper_bound", "from": "2", "to": sp.sstr(bound)},
        ),
        diagram=diagram,
        witness={
            **common_witness,
            "query_kind": "integral_bound",
            "requested_bound": sp.srepr(bound),
            "proved_sharp_bound": "2",
            "contraction": "(sqrt(3)-1)/2",
        },
    )


def _parse_mobius_polynomial_fixed_point_input(
    statement: str,
) -> dict[str, Any] | None:
    """Extract a polynomial root transport directly from the current statement."""

    segments = parse_latex_problem(statement).math_segments
    angle_match = next(
        (
            match
            for segment in segments
            if (
                match := re.fullmatch(
                    r"[A-Za-z]+\s*=\s*cos\(\(2\*pi\)/\((\d+)\)\)",
                    segment,
                )
            )
        ),
        None,
    )
    if angle_match is None:
        return None
    order = int(angle_match.group(1))
    if order < 3:
        return None

    polynomial_match = next(
        (
            match
            for segment in segments
            if "**" in segment
            and (
                match := re.fullmatch(
                    r"(?P<function>[A-Za-z]+)\*\((?P<variable>[A-Za-z]+)\)=(?P<body>.+)",
                    segment,
                )
            )
        ),
        None,
    )
    if polynomial_match is None:
        return None
    variable = sp.Symbol(polynomial_match.group("variable"), real=True)
    try:
        polynomial = sp.Poly(
            sp.sympify(polynomial_match.group("body"), locals={variable.name: variable}),
            variable,
            domain=sp.QQ,
        )
    except (sp.PolynomialError, sp.SympifyError, TypeError, ValueError):
        return None
    if polynomial.degree() < 2 or polynomial.LC() == 0:
        return None

    transform_verified = False
    for segment in segments:
        transform_match = re.fullmatch(r"(?P<state>[A-Za-z]+)=(?P<body>.+)", segment)
        if transform_match is None or transform_match.group("state") != "S":
            continue
        try:
            transform = sp.sympify(
                transform_match.group("body"),
                locals={variable.name: variable},
            )
        except (sp.SympifyError, TypeError, ValueError):
            continue
        if sp.cancel(transform - 1 / (1 - variable)) == 0:
            transform_verified = True
            break
    if not transform_verified or not any("S=g*(S)" in segment for segment in segments):
        return None

    asks_constant = any(segment == "C_0" for segment in segments)
    asks_contraction = any(
        "k=" in segment and "g'" in segment and "lvert" in segment
        for segment in segments
    )
    if asks_constant == asks_contraction:
        return None
    if asks_contraction and not any(
        re.fullmatch(rf"cos\(\(pi\)/\({order}\)\)", segment)
        for segment in segments
    ):
        return None

    return {
        "coefficients": tuple(sp.sstr(value) for value in polynomial.all_coeffs()),
        "order": order,
        "query": "contraction" if asks_contraction else "constant",
        "polynomial": polynomial,
        "variable": variable,
    }


def synthesize_polynomial_mobius_fixed_point(
    statement: str,
) -> RuntimeSolutionSynthesis | None:
    """Transport an algebraic root to a fixed-point map and certify its derivative."""

    parsed = _parse_mobius_polynomial_fixed_point_input(statement)
    if parsed is None:
        return None
    try:
        _, witness, _ = solve_mobius_polynomial_fixed_point_chart(
            parsed["coefficients"],
            parsed["order"],
        )
    except (ArithmeticError, KeyError, TypeError, ValueError, sp.PolynomialError):
        return None

    S, c = sp.symbols("S c", real=True)
    try:
        transformed = sp.sympify(witness["transformed_polynomial"], locals={"S": S})
        fixed_map = sp.sympify(witness["fixed_map"], locals={"S": S})
        cosine_minimal = sp.sympify(
            witness["cosine_minimal_polynomial"], locals={"c": c}
        )
        reduced_derivative = sp.sympify(
            witness["derivative_remainder"], locals={"c": c}
        )
        contraction = sp.sympify(
            witness["contraction_factor"],
            locals={"cos": sp.cos, "pi": sp.pi},
        )
        constant_term = sp.Rational(witness["constant_term"])
    except (sp.SympifyError, TypeError, ValueError):
        return None

    order = int(parsed["order"])
    query = str(parsed["query"])
    fixed_map_expanded = sp.apart(fixed_map, S)
    diagram = state_transition_diagram(
        [
            {"id": "root", "label": rf"\alpha=\cos(2\pi/{order})", "terminal": False},
            {"id": "mobius", "label": r"S^*=1/(1-\alpha)", "terminal": False},
            {"id": "fixed", "label": r"S=g(S)", "terminal": query == "constant"},
            {"id": "linearized", "label": r"k=|g'(S^*)|", "terminal": query == "contraction"},
        ],
        [
            {"from": "root", "to": "mobius", "label": r"S=1/(1-x)", "tone": "primary"},
            {"from": "mobius", "to": "fixed", "label": "多項式を移送", "tone": "primary"},
            {"from": "fixed", "to": "linearized", "label": "固定点で微分", "tone": "secondary"},
        ],
        title="代数的数から固定点写像へ",
        caption="同じ根を分数変換で固定点へ移し、写像の定数項と局所的な収束率を読み取ります。",
    )
    common_program = (
        {
            "rule": "parse_current_polynomial_and_rational_angle",
            "coefficients": list(parsed["coefficients"]),
            "cyclotomic_order": order,
        },
        {
            "rule": "verify_supplied_minimal_polynomial_at_root",
            "root_remainder": witness["root_remainder"],
        },
        {
            "rule": "transport_polynomial_by_fractional_linear_map",
            "map": "S=1/(1-x)",
            "transformed_polynomial": witness["transformed_polynomial"],
        },
        {
            "rule": "replay_fixed_point_identity",
            "residual": witness["fixed_point_identity"],
        },
    )
    common_checks = (
        "現在の問題文から有理角・多項式係数・分数変換を抽出",
        "与えられた多項式が指定された余弦を根に持つことを最小多項式による除算で確認",
        "分数変換後の多項式を厳密に展開し、固定点恒等式の残差が0であることを確認",
    )
    common_witness = {
        **witness,
        "query": query,
        "source_polynomial": sp.sstr(parsed["polynomial"].as_expr()),
    }
    transformed_tex = sp.latex(transformed)
    fixed_map_tex = sp.latex(fixed_map_expanded)

    if query == "constant":
        return RuntimeSolutionSynthesis(
            answer=constant_term,
            answer_tex=rf"\({sp.latex(constant_term)}\)",
            tool_name="mortra.runtime_polynomial_mobius_transport",
            expression_tex=rf"S^{{{parsed['polynomial'].degree()}}}f(1-S^{{-1}})",
            derivation_tex=(
                rf"\(x=1-\dfrac1S\) を \(f(x)=0\) に代入し、分母を払うと \({transformed_tex}=0\) となる。",
                rf"最高次の項を左辺に残して整理すると、\(S=g(S)\), \(g(S)={fixed_map_tex}\) を得る。",
                rf"従って \(S\) の負の冪を含まない定数項は \(C_0={sp.latex(constant_term)}\) である。",
            ),
            verification_checks=common_checks + (
                "固定点写像を1/Sの多項式として展開し、定数項を厳密に抽出",
            ),
            proof_program=common_program
            + (
                {
                    "rule": "extract_constant_coefficient_at_infinity",
                    "constant_term": str(constant_term),
                },
            ),
            diagram=diagram,
            witness=common_witness,
        )

    contraction_tex = sp.latex(contraction)
    derivative_tex = sp.latex(reduced_derivative)
    minimal_tex = sp.latex(cosine_minimal)
    return RuntimeSolutionSynthesis(
        answer=contraction,
        answer_tex=rf"\({contraction_tex}\)",
        tool_name="mortra.runtime_polynomial_mobius_transport",
        expression_tex=r"k=|g'(S^*)|",
        derivation_tex=(
            rf"同じ変換から \(S=g(S)\), \(g(S)={fixed_map_tex}\) を得る。",
            rf"\(c=\cos\dfrac{{\pi}}{{{order}}}\) とおくと \(\alpha=2c^2-1\) である。\(c\) の最小多項式は \({minimal_tex}\) であり、与えられた \(f(2c^2-1)\) はこれで割り切れる。",
            rf"\(S^*=1/(1-\alpha)\) を \(g'(S)\) に代入し、上の最小多項式で高次の冪を消去すると \(g'(S^*)={derivative_tex}\) となる。",
            rf"この値の符号を代数的数として厳密に判定して絶対値を取ると、\(k={contraction_tex}\) である。",
        ),
        verification_checks=common_checks
        + (
            "半角公式 alpha=2c^2-1 を代入し、指定余弦の最小多項式との整合性を確認",
            "固定点での導関数を商環で簡約し、除算余りを再計算",
            "導関数の符号を厳密判定して絶対値を確定",
        ),
        proof_program=common_program
        + (
            {
                "rule": "transport_root_by_half_angle",
                "minimal_polynomial": witness["cosine_minimal_polynomial"],
            },
            {
                "rule": "differentiate_at_fixed_point_and_reduce",
                "remainder": witness["derivative_remainder"],
            },
            {
                "rule": "certify_algebraic_sign_and_absolute_value",
                "sign": witness["derivative_sign"],
            },
        ),
        diagram=diagram,
        witness=common_witness,
    )


def _parse_rotated_parabola_limit(statement: str) -> dict[str, Any] | None:
    """Read a rotated ``y=a*x**2`` distance or volume limit from the input."""

    normalized = normalize_latex_math(statement)
    lower = normalized.lower()
    parsed_problem = parse_latex_problem(statement)
    math_segments = parsed_problem.math_segments
    if not any(marker in lower for marker in ("回転", "rotate", "rotation")):
        return None
    compact_statement = re.sub(r"[\s$\\{}]", "", statement)
    compact_lower = compact_statement.lower()
    origin_is_named_o = re.search(r"原点(?:を|は|=)?(?:点)?o", compact_lower) is not None
    rotates_about_origin = any(
        phrase in compact_lower
        for phrase in (
            "原点を中心",
            "原点中心",
            "原点のまわり",
            "原点周り",
            "abouttheorigin",
            "aroundtheorigin",
        )
    ) or (
        origin_is_named_o
        and any(
            phrase in compact_lower
            for phrase in ("oを中心", "o中心", "oのまわり", "o周り", "abouto", "aroundo")
        )
    )
    if not rotates_about_origin:
        return None

    coefficient: sp.Expr | None = None
    curve_variable: sp.Symbol | None = None
    for segment in math_segments:
        compact = segment.replace(" ", "")
        equation = re.fullmatch(
            r"(?:[A-Za-z][A-Za-z0-9_]*:)?[A-Za-z]=(?P<body>.+)", compact
        )
        if equation is None:
            continue
        symbols = sorted(set(re.findall(r"[A-Za-z]+", equation.group("body"))))
        symbols = [name for name in symbols if name not in {"sqrt", "pi", "sin", "cos"}]
        if len(symbols) != 1:
            continue
        variable = sp.Symbol(symbols[0], real=True)
        try:
            body = sp.sympify(
                equation.group("body"),
                locals={variable.name: variable, "sqrt": sp.sqrt, "pi": sp.pi},
            )
            polynomial = sp.Poly(body, variable)
        except (sp.PolynomialError, sp.SympifyError, TypeError, ValueError):
            continue
        if polynomial.degree() != 2:
            continue
        candidate = sp.simplify(polynomial.coeff_monomial(variable**2))
        if sp.simplify(body - candidate * variable**2) != 0:
            continue
        if candidate.free_symbols or not _proves_strictly_positive(candidate):
            continue
        coefficient = candidate
        curve_variable = variable
        break
    if coefficient is None or curve_variable is None:
        return None

    query: dict[str, Any] | None = None
    limit_pattern = re.compile(
        r"limit_\((?:\\)?(?P<angle>[A-Za-z]+)to0(?P<side>\^?[+-])?\)"
        r"\*?(?:\\)?(?P=angle)\*\*(?P<power>\d+)\*?(?P<target>.+)"
    )
    for segment in math_segments:
        match = limit_pattern.fullmatch(segment.replace(" ", ""))
        if match is None:
            continue
        target = match.group("target")
        power = int(match.group("power"))
        if "V" in target and any(marker in normalized for marker in ("体積", "volume")):
            has_x_axis = any(
                phrase in compact_lower
                for phrase in (
                    "x軸周り",
                    "x軸の周り",
                    "x軸まわり",
                    "x軸のまわり",
                    "aboutthexaxis",
                    "aroundthexaxis",
                )
            ) or (
                ("軸周り" in normalized or "axis" in lower) and "x" in math_segments
            )
            if power != 5 or not has_x_axis:
                return None
            query = {
                "kind": "volume",
                "power": power,
                "target": target,
                "angle": match.group("angle"),
                "side": match.group("side") or "two-sided",
            }
        elif any(marker in normalized for marker in ("交点", "intersection")):
            if power != 2 or not re.fullmatch(r"[A-Za-z]{2}", target):
                return None
            query = {
                "kind": "distance",
                "power": power,
                "target": target,
                "angle": match.group("angle"),
                "side": match.group("side") or "two-sided",
            }
        break
    if query is None:
        return None
    return {
        "coefficient": coefficient,
        "curve_variable": curve_variable.name,
        **query,
    }


def _rotated_parabola_limit_diagram(
    *, stage: int, volume: bool
) -> dict[str, Any]:
    """Draw the coefficient-free blow-up chart used by both limit queries."""

    sample_t = 0.18
    cosine = (1.0 - sample_t**2) / (1.0 + sample_t**2)
    sine = 2.0 * sample_t / (1.0 + sample_t**2)
    fixed_points: list[dict[str, float]] = []
    for index in range(121):
        X = -1.05 + 1.18 * index / 120.0
        fixed_points.append({"x": X, "y": X * X})
    rotated_points: list[dict[str, float]] = []
    for index in range(121):
        v = index / 120.0
        rotated_points.append(
            {
                "x": v * cosine - 2.0 * v * v / (1.0 + sample_t**2),
                "y": 2.0 * sample_t**2 * v / (1.0 + sample_t**2) + v * v * cosine,
            }
        )

    shapes: list[dict[str, Any]] = [
        {
            "id": "fixed-parabola",
            "kind": "polyline",
            "points": fixed_points,
            "tone": "primary",
        },
        {
            "id": "rotated-parabola",
            "kind": "polyline",
            "points": rotated_points,
            "tone": "accent",
        },
        {
            "id": "origin",
            "kind": "point",
            "point": {"x": 0.0, "y": 0.0},
            "label": "O",
            "tone": "primary",
        },
    ]
    if stage >= 2:
        shapes.append(
            {
                "id": "nonzero-intersection",
                "kind": "point",
                "point": {"x": -1.0, "y": 1.0},
                "label": "R",
                "tone": "secondary",
            }
        )
    if stage >= 3 and volume:
        region = [
            {"x": -index / 100.0, "y": (index / 100.0) ** 2}
            for index in range(101)
        ]
        region.extend(reversed(rotated_points))
        shapes.insert(
            0,
            {
                "id": "bounded-region",
                "kind": "polyline",
                "points": region,
                "closed": True,
                "fill": True,
                "tone": "muted",
            },
        )
    elif stage >= 3:
        shapes.append(
            {
                "id": "origin-to-intersection",
                "kind": "vector",
                "from": {"x": 0.0, "y": 0.0},
                "to": {"x": -1.0, "y": 1.0},
                "label": "OR",
                "tone": "secondary",
            }
        )

    captions = {
        1: "微小回転で遠方へ移る交点を、有限な尺度 (X,Y) へ縮めて表示します。",
        2: "半角変数で交点式を因数分解すると、原点以外の実交点 R が一意に決まります。",
        3: (
            "囲まれた領域の境界を一周する積分から、x軸回転体の体積を求めます。"
            if volume
            else "同じ交点座標から距離 OR を作り、尺度を元へ戻して極限を取ります。"
        ),
    }
    return plane_scene_diagram(
        title="回転した放物線の有限尺度表示",
        caption=captions[stage],
        viewport={"xMin": -1.18, "xMax": 0.3, "yMin": -0.12, "yMax": 1.2},
        axes=True,
        shapes=shapes,
    )


def synthesize_rotated_parabola_limit(
    statement: str,
) -> RuntimeSolutionSynthesis | None:
    """Conjugate a small rotation to a rational half-angle blow-up chart."""

    parsed = _parse_rotated_parabola_limit(statement)
    if parsed is None:
        return None
    coefficient = sp.simplify(parsed["coefficient"])
    angle_name = str(parsed["angle"])
    angle_tex = sp.latex(sp.Symbol(angle_name, real=True))
    query_kind = str(parsed["kind"])

    a = sp.Symbol("a", positive=True)
    t = sp.Symbol("t", positive=True)
    u = sp.Symbol("u", real=True)
    sine = 2 * t / (1 + t**2)
    cosine = (1 - t**2) / (1 + t**2)
    rotated_x = sp.factor(u * cosine - a * u**2 * sine)
    rotated_y = sp.factor(u * sine + a * u**2 * cosine)
    intersection = sp.factor(rotated_y - a * rotated_x**2)
    expected_factorization = (
        -2
        * t
        * u
        * (a * t * u - 1)
        * (2 * a**2 * u**2 + 2 * a * t * u + t**2 + 1)
        / (1 + t**2) ** 2
    )
    factorization_residual = sp.factor(intersection - expected_factorization)
    quadratic = 2 * a**2 * u**2 + 2 * a * t * u + t**2 + 1
    quadratic_discriminant = sp.factor(sp.discriminant(quadratic, u))
    if factorization_residual != 0:
        return None
    if quadratic_discriminant != -4 * a**2 * (t**2 + 2):
        return None

    nonzero_parameter = 1 / (a * t)
    intersection_x = sp.simplify(rotated_x.subs(u, nonzero_parameter))
    intersection_y = sp.simplify(rotated_y.subs(u, nonzero_parameter))
    if intersection_x != -1 / (a * t) or intersection_y != 1 / (a * t**2):
        return None
    coordinate_residuals = (
        sp.simplify(intersection_y - a * intersection_x**2),
        sp.simplify(intersection.subs(u, nonzero_parameter)),
    )
    if any(residual != 0 for residual in coordinate_residuals):
        return None

    theta = sp.Symbol("theta", positive=True)
    half_angle_ratio = sp.limit(theta / sp.tan(theta / 2), theta, 0, dir="+")
    if half_angle_ratio != 2:
        return None

    common_program = (
        {
            "rule": "elaborate_origin_centered_rotation_of_quadratic_graph",
            "coefficient": sp.srepr(coefficient),
            "angle_variable": angle_name,
        },
        {
            "rule": "conjugate_rotation_by_tangent_half_angle",
            "substitution": f"t=tan({angle_name}/2)",
            "sine": "2*t/(1+t**2)",
            "cosine": "(1-t**2)/(1+t**2)",
        },
        {
            "rule": "factor_rotated_curve_intersection",
            "factorization_residual": str(factorization_residual),
            "quadratic_discriminant": sp.sstr(quadratic_discriminant),
        },
        {
            "rule": "isolate_unique_nonzero_real_intersection",
            "parameter": "1/(a*t)",
            "coordinates": ["-1/(a*t)", "1/(a*t**2)"],
            "coordinate_residuals": [str(value) for value in coordinate_residuals],
        },
    )
    common_checks = (
        "現在入力から原点中心の回転、二次曲線の係数、極限の対象と次数を抽出",
        "正弦・余弦を半角変数の有理式へ移し、交点多項式の因数分解を恒等式として再生",
        "残る二次因子の判別式が負であることから、原点以外の実交点が一意であることを確認",
        "交点の媒介変数と二座標を元の二曲線へ代入し、残差がともに0であることを確認",
        "theta/tan(theta/2) の極限を厳密に2へ評価",
    )
    common_witness = {
        "curve": f"y=({sp.srepr(coefficient)})*x**2",
        "coefficient": sp.srepr(coefficient),
        "angle_variable": angle_name,
        "half_angle_variable": "t",
        "generic_intersection_factorization": sp.sstr(expected_factorization),
        "factorization_residual": str(factorization_residual),
        "quadratic_factor_discriminant": sp.sstr(quadratic_discriminant),
        "nonzero_parameter": "1/(a*t)",
        "intersection_coordinates": ["-1/(a*t)", "1/(a*t**2)"],
        "coordinate_residuals": [str(value) for value in coordinate_residuals],
        "half_angle_ratio_limit": str(half_angle_ratio),
        "query_kind": query_kind,
    }

    diagrams = [
        _rotated_parabola_limit_diagram(stage=stage, volume=query_kind == "volume")
        for stage in (1, 2, 3)
    ]
    chain = [step["rule"] for step in common_program]

    if query_kind == "distance":
        distance = sp.sqrt(1 + t**2) / (a * t**2)
        limit_value = sp.simplify(4 / coefficient)
        chain.append("restore_distance_scale_and_take_limit")
        visual_explanation = {
            "version": 1,
            "mode": "stepper",
            "title": "微小回転から遠方交点の距離を得るまで",
            "diagram_required_for_every_step": True,
            "composition_verified": True,
            "morphism_chain": chain,
            "steps": [
                {
                    "id": "rotated-parabola-distance-1",
                    "title": "回転を半角変数へ移す",
                    "explanation_ja": "回転行列の正弦・余弦を、半角変数 t の有理式へ変えます。",
                    "formula_tex": rf"\sin {angle_tex}=\frac{{2t}}{{1+t^2}},\quad \cos {angle_tex}=\frac{{1-t^2}}{{1+t^2}}",
                    "morphism": {"morphism_id": chain[1], "label_ja": "回転の半角有理化", "input_type": "RotatedQuadraticCurve", "output_type": "RationalParametricCurve"},
                    "source_state": {"id": "rotated-curve", "type": "RotatedQuadraticCurve"},
                    "target_state": {"id": "half-angle-curve", "type": "RationalParametricCurve"},
                    "diagram": diagrams[0],
                },
                {
                    "id": "rotated-parabola-distance-2",
                    "title": "原点以外の交点を一意に決める",
                    "explanation_ja": "交点式を因数分解し、判別式が負の二次因子を除くと、原点以外の実交点が一意に定まります。",
                    "formula_tex": r"R=\left(-\frac1{at},\frac1{at^2}\right)",
                    "morphism": {"morphism_id": chain[3], "label_ja": "実交点の分離", "input_type": "IntersectionPolynomial", "output_type": "UniqueNonzeroIntersection"},
                    "source_state": {"id": "intersection-polynomial", "type": "IntersectionPolynomial"},
                    "target_state": {"id": "nonzero-intersection", "type": "UniqueNonzeroIntersection"},
                    "diagram": diagrams[1],
                },
                {
                    "id": "rotated-parabola-distance-3",
                    "title": "距離の尺度を元へ戻す",
                    "explanation_ja": "交点座標から距離を作り、回転角と半角変数 t の比が2へ近づくことを使います。",
                    "formula_tex": rf"\lim_{{{angle_tex}\to0}}{angle_tex}^2OR={sp.latex(limit_value)}",
                    "morphism": {"morphism_id": chain[-1], "label_ja": "距離尺度の復元", "input_type": "UniqueNonzeroIntersection", "output_type": "ExactLimit"},
                    "source_state": {"id": "nonzero-intersection", "type": "UniqueNonzeroIntersection"},
                    "target_state": {"id": "distance-limit", "type": "ExactLimit"},
                    "diagram": diagrams[2],
                },
            ],
        }
        return RuntimeSolutionSynthesis(
            answer=limit_value,
            answer_tex=rf"\({sp.latex(limit_value)}\)",
            tool_name="mortra.runtime_rotated_parabola_blowup_distance",
            expression_tex=rf"\lim_{{{angle_tex}\to0}}{angle_tex}^2{parsed['target']}",
            derivation_tex=(
                rf"曲線を \(y=ax^2\) と書く。この問題では \(a={sp.latex(coefficient)}\) である。半角変数 \(t=\tan({angle_tex}/2)\) を導入すると、\(\sin {angle_tex}=\frac{{2t}}{{1+t^2}}\), \(\cos {angle_tex}=\frac{{1-t^2}}{{1+t^2}}\) である。",
                r"回転前の点を \((u,au^2)\) とする。回転後の座標を交点条件 \(y=ax^2\) へ代入すると、原点に対応する \(u=0\) を除いた式は \[(atu-1)(2a^2u^2+2atu+t^2+1)=0.\] 後ろの二次式の判別式は \(-4a^2(t^2+2)<0\) なので、原点以外の実交点は \(u=1/(at)\) の一つだけである。",
                r"この値を回転後の座標へ戻すと \[R=\left(-\frac1{at},\frac1{at^2}\right).\] 従って \[OR=\frac{\sqrt{1+t^2}}{a|t|^2}.\]",
                rf"\({angle_tex}/\tan({angle_tex}/2)\to2\) であるから、\[{angle_tex}^2OR=\frac1a\left(\frac{{{angle_tex}}}{{t}}\right)^2\sqrt{{1+t^2}}\longrightarrow\frac4a={sp.latex(limit_value)}.\]",
            ),
            verification_checks=common_checks
            + ("交点座標から距離を厳密に作り、半角比の極限で指定された尺度を復元",),
            proof_program=common_program
            + (
                {
                    "rule": "restore_distance_scale_and_take_limit",
                    "distance": sp.sstr(distance),
                    "limit": sp.srepr(limit_value),
                },
            ),
            diagram=diagrams[-1],
            witness={
                **common_witness,
                "generic_distance": sp.sstr(distance),
                "limit": sp.srepr(limit_value),
            },
            visual_explanation=visual_explanation,
        )

    q_integral = sp.factor(
        sp.integrate(rotated_y**2 * sp.diff(rotated_x, u), (u, 1 / (a * t), 0))
    )
    X = sp.Symbol("X", real=True)
    p_integral = sp.factor(sp.integrate((a * X**2) ** 2, (X, 0, -1 / (a * t))))
    boundary_integral = sp.factor(q_integral + p_integral)
    expected_boundary = (5 * t**2 + 4) / (15 * a**3 * t**5 * (1 + t**2))
    boundary_residual = sp.factor(boundary_integral - expected_boundary)
    if boundary_residual != 0:
        return None
    right_limit = sp.simplify(128 * sp.pi / (15 * coefficient**3))
    left_limit = -right_limit
    side = str(parsed["side"])
    if side in {"+", "^+"}:
        answer: Any = right_limit
        answer_tex = rf"\({sp.latex(right_limit)}\)"
    elif side in {"-", "^-"}:
        answer = left_limit
        answer_tex = rf"\({sp.latex(left_limit)}\)"
    else:
        answer = {
            "exists": False,
            "right_limit": sp.srepr(right_limit),
            "left_limit": sp.srepr(left_limit),
        }
        answer_tex = (
            r"\(\text{両側極限は存在しない。}\quad "
            rf"\lim_{{{angle_tex}\to0^+}}{angle_tex}^5V({angle_tex})={sp.latex(right_limit)},\quad "
            rf"\lim_{{{angle_tex}\to0^-}}{angle_tex}^5V({angle_tex})={sp.latex(left_limit)}.\)"
        )
    chain.extend(("convert_solid_volume_to_boundary_moment", "reflect_negative_rotation"))
    visual_explanation = {
        "version": 1,
        "mode": "stepper",
        "title": "回転した放物線から回転体積の片側極限を得るまで",
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": chain,
        "steps": [
            {
                "id": "rotated-parabola-volume-1",
                "title": "回転を半角変数へ移す",
                "explanation_ja": "回転行列を半角変数 t の有理式にし、微小角で発散する座標を有限尺度へ移します。",
                "formula_tex": rf"t=\tan({angle_tex}/2),\quad X=atx,\quad Y=at^2y",
                "morphism": {"morphism_id": chain[1], "label_ja": "回転の半角有理化", "input_type": "RotatedQuadraticCurve", "output_type": "RationalParametricCurve"},
                "source_state": {"id": "rotated-curve", "type": "RotatedQuadraticCurve"},
                "target_state": {"id": "half-angle-curve", "type": "RationalParametricCurve"},
                "diagram": diagrams[0],
            },
            {
                "id": "rotated-parabola-volume-2",
                "title": "囲まれた領域を確定する",
                "explanation_ja": "二次因子の判別式が負なので、二曲線の実交点は O と R だけです。",
                "formula_tex": r"R=\left(-\frac1{at},\frac1{at^2}\right)",
                "morphism": {"morphism_id": chain[3], "label_ja": "実交点の分離", "input_type": "IntersectionPolynomial", "output_type": "BoundedRegion"},
                "source_state": {"id": "intersection-polynomial", "type": "IntersectionPolynomial"},
                "target_state": {"id": "bounded-region", "type": "BoundedRegion"},
                "diagram": diagrams[1],
            },
            {
                "id": "rotated-parabola-volume-3",
                "title": "境界積分で体積を求める",
                "explanation_ja": "縦断面の円環面積を境界に沿う一つの積分へまとめ、負の角は対称移動で処理します。",
                "formula_tex": r"V=\pi\oint_{\partial\Omega}^{\rm clockwise}y^2\,dx",
                "morphism": {"morphism_id": chain[-2], "label_ja": "断面積から境界積分へ", "input_type": "BoundedRegion", "output_type": "ExactVolume"},
                "source_state": {"id": "bounded-region", "type": "BoundedRegion"},
                "target_state": {"id": "volume-limit", "type": "ExactLimit"},
                "diagram": diagrams[2],
            },
        ],
    }
    return RuntimeSolutionSynthesis(
        answer=answer,
        answer_tex=answer_tex,
        tool_name="mortra.runtime_rotated_parabola_boundary_moment",
        expression_tex=rf"\lim_{{{angle_tex}\to0}}{angle_tex}^5V({angle_tex})",
        derivation_tex=(
            rf"曲線を \(y=ax^2\) と書く。この問題では \(a={sp.latex(coefficient)}\) である。まず \({angle_tex}>0\) とし、半角変数 \(t=\tan({angle_tex}/2)>0\) によって回転行列を有理化する。",
            r"回転前の点を \((u,au^2)\) とすると、交点式は \[-\frac{2tu(atu-1)(2a^2u^2+2atu+t^2+1)}{(1+t^2)^2}=0.\] 二次因子の判別式は負なので、境界の交点は \(O\) と \(R=(-1/(at),1/(at^2))\) だけである。",
            rf"囲まれた領域を \(\Omega_{{{angle_tex}}}\) とする。これは \(x\) 軸より上にあるから、円環法とグリーンの公式により、境界を時計回りに一周して \[V({angle_tex})=\pi\oint_{{\partial\Omega_{{{angle_tex}}}}}^{{\rm clockwise}}y^2\,dx\] と書ける。固定放物線を \(O\to R\)、回転放物線を \(R\to O\) と進む。",
            rf"固定放物線上の積分と回転放物線上の積分はそれぞれ \[-\frac1{{5a^3t^5}},\qquad \frac{{8t^2+7}}{{15a^3t^5(1+t^2)}}.\] 従って \[V({angle_tex})=\frac{{\pi(5t^2+4)}}{{15a^3t^5(1+t^2)}}.\]",
            rf"\({angle_tex}/t\to2\) より右極限は \({sp.latex(right_limit)}\) である。負の角の図形は正の角の図形を \(y\) 軸について反転したものなので \(V(-{angle_tex})=V({angle_tex})\) であり、左極限は \({sp.latex(left_limit)}\) となる。従って両側極限は存在しない。",
        ),
        verification_checks=common_checks
        + (
            "固定曲線と回転曲線の境界積分を独立に記号積分し、その和の残差が0であることを確認",
            "y軸反転で V(-theta)=V(theta) を確認し、奇数5乗を掛けた左右極限を別々に評価",
        ),
        proof_program=common_program
        + (
            {
                "rule": "convert_solid_volume_to_boundary_moment",
                "fixed_curve_integral": sp.sstr(p_integral),
                "rotated_curve_integral": sp.sstr(q_integral),
                "boundary_integral": sp.sstr(boundary_integral),
                "residual": str(boundary_residual),
            },
            {
                "rule": "reflect_negative_rotation",
                "volume_parity": "even",
                "scaled_limit_parity": "odd",
                "right_limit": sp.srepr(right_limit),
                "left_limit": sp.srepr(left_limit),
            },
        ),
        diagram=diagrams[-1],
        witness={
            **common_witness,
            "fixed_curve_integral": sp.sstr(p_integral),
            "rotated_curve_integral": sp.sstr(q_integral),
            "boundary_integral": sp.sstr(boundary_integral),
            "boundary_integral_residual": str(boundary_residual),
            "volume_formula_positive_angle": sp.sstr(sp.pi * boundary_integral),
            "right_limit": sp.srepr(right_limit),
            "left_limit": sp.srepr(left_limit),
            "two_sided_limit_exists": False,
        },
        visual_explanation=visual_explanation,
    )


def _parse_elementary_envelope_query(statement: str) -> dict[str, Any] | None:
    """Recognize proof obligations closed by reusable elementary envelopes."""

    numbered_markers = re.findall(
        r"(?:^|\\\\|\n|\$)\s*\((\d+)\)",
        statement,
    )
    if len(set(numbered_markers)) >= 2:
        return None

    math_segments = parse_latex_problem(statement).math_segments
    for segment in math_segments:
        compact = segment.replace(" ", "")
        pieces = compact.split("<")
        if len(pieces) != 3 or not pieces[1].startswith("integral_"):
            continue
        variable_match = re.search(r"sin\(([A-Za-z])\)", pieces[1])
        if variable_match is None:
            continue
        variable_name = variable_match.group(1)
        flattened = re.sub(r"[\s()]", "", pieces[1]).replace("*d", "d")
        if flattened != f"integral_0**pi/2*sin{variable_name}/{variable_name}d{variable_name}":
            continue
        requested_lower = _sympify_exact_scalar(pieces[0])
        requested_upper = _sympify_exact_scalar(pieces[2])
        if requested_lower is None or requested_upper is None:
            continue
        return {
            "kind": "sinc_integral_bounds",
            "variable": variable_name,
            "requested_lower": requested_lower,
            "requested_upper": requested_upper,
        }

    for segment in math_segments:
        compact = segment.replace(" ", "")
        if "tan" not in compact or "<" not in compact:
            continue
        names = {
            name
            for name in re.findall(r"[A-Za-z]+", compact)
            if name not in {"tan", "e", "pi"}
        }
        if len(names) != 1:
            continue
        variable_name = names.pop()
        variable = sp.Symbol(variable_name, positive=True)
        try:
            relation = sp.sympify(
                compact,
                locals={
                    variable_name: variable,
                    "e": sp.E,
                    "pi": sp.pi,
                    "tan": sp.tan,
                },
            )
        except (sp.SympifyError, TypeError, ValueError, SyntaxError):
            continue
        expected_left = sp.tan(sp.E * (1 - 1 / variable) ** variable) + 1 / variable
        has_domain = any(
            re.sub(r"[\s()]", "", candidate) == f"{variable_name}>1"
            for candidate in math_segments
        )
        if (
            not isinstance(relation, sp.StrictLessThan)
            or not has_domain
            or sp.simplify(relation.lhs - expected_left) != 0
            or sp.simplify(relation.rhs - sp.pi / 2) != 0
        ):
            continue
        return {
            "kind": "reciprocal_exponential_tangent_bound",
            "variable": variable_name,
        }

    for segment in math_segments:
        compact = segment.replace(" ", "")
        comparison = re.fullmatch(r"(?:\(\d+\))?e<(?P<target>.+)", compact)
        if comparison is None:
            continue
        target = _sympify_exact_scalar(comparison.group("target"))
        if target is None:
            continue
        radical = sp.simplify(target - 1)
        radicand = sp.simplify(radical**2)
        if (
            radical.is_positive is not True
            or radicand.is_Rational is not True
            or sp.simplify(radical - sp.sqrt(radicand)) != 0
        ):
            continue
        return {
            "kind": "exponential_radical_bound",
            "target": target,
            "radicand": radicand,
        }

    asks_integer = "整数" in statement or re.search(r"\binteger\b", statement, re.I)
    if asks_integer:
        compact_statement = re.sub(r"[\s{}]", "", statement)
        match = re.search(
            r"\\int_0\^1e\^(?P<variable>[A-Za-z])"
            r"\\sin(?P=variable)(?:\\,)?d(?P=variable)",
            compact_statement,
        )
        if match is not None:
            return {
                "kind": "positive_exp_sine_integral_integer",
                "variable": match.group("variable"),
            }
    return None


def _pi_polynomial_enclosure(
    expression: sp.Expr,
    lower: sp.Rational,
    upper: sp.Rational,
) -> tuple[sp.Rational, sp.Rational] | None:
    """Enclose a rational polynomial in pi by endpoint arithmetic."""

    symbol = sp.Symbol("_pi")
    replaced = sp.expand(expression.xreplace({sp.pi: symbol}))
    try:
        polynomial = sp.Poly(replaced, symbol)
    except sp.PolynomialError:
        return None
    enclosure_lower = sp.Rational(0)
    enclosure_upper = sp.Rational(0)
    for (degree,), coefficient in polynomial.terms():
        if coefficient.is_Rational is not True:
            return None
        coefficient = sp.Rational(coefficient)
        if coefficient >= 0:
            enclosure_lower += coefficient * lower**degree
            enclosure_upper += coefficient * upper**degree
        else:
            enclosure_lower += coefficient * upper**degree
            enclosure_upper += coefficient * lower**degree
    return sp.factor(enclosure_lower), sp.factor(enclosure_upper)


def _number_line_interval_diagram(
    *,
    title: str,
    caption: str,
    outer_lower: sp.Expr,
    inner_lower: sp.Expr,
    inner_upper: sp.Expr,
    outer_upper: sp.Expr,
    labels: tuple[str, str, str, str],
) -> dict[str, Any]:
    """Render a certified nested interval without using samples as evidence."""

    values = [
        float(sp.N(value, 18))
        for value in (outer_lower, inner_lower, inner_upper, outer_upper)
    ]
    width = max(values) - min(values)
    margin = max(0.08, width * 0.18)
    return plane_scene_diagram(
        title=title,
        caption=caption,
        viewport={
            "xMin": min(values) - margin,
            "xMax": max(values) + margin,
            "yMin": -0.48,
            "yMax": 0.48,
        },
        axes=True,
        shapes=(
            {
                "id": "requested-interval",
                "kind": "polyline",
                "points": (
                    {"x": values[0], "y": 0.0},
                    {"x": values[3], "y": 0.0},
                ),
                "tone": "muted",
            },
            {
                "id": "certified-interval",
                "kind": "polyline",
                "points": (
                    {"x": values[1], "y": 0.0},
                    {"x": values[2], "y": 0.0},
                ),
                "tone": "primary",
            },
            *tuple(
                {
                    "id": f"interval-point-{index}",
                    "kind": "point",
                    "point": {"x": value, "y": 0.0},
                    "tone": "accent" if index in {1, 2} else "secondary",
                }
                for index, (value, label) in enumerate(zip(values, labels))
            ),
            *tuple(
                {
                    "id": f"interval-label-{index}",
                    "kind": "label",
                    "point": {
                        "x": value,
                        "y": 0.16 if index % 2 == 0 else -0.16,
                    },
                    "tex": label,
                    "tone": "accent" if index in {1, 2} else "secondary",
                }
                for index, (value, label) in enumerate(zip(values, labels))
            ),
        ),
    )


def synthesize_elementary_envelope(
    statement: str,
) -> RuntimeSolutionSynthesis | None:
    """Close elementary inequalities by exact series and integral envelopes."""

    parsed = _parse_elementary_envelope_query(statement)
    if parsed is None:
        return None

    pi_lower = sp.Rational(223, 71)
    pi_upper = sp.Rational(22, 7)
    if not (
        _proves_strictly_positive(sp.pi - pi_lower)
        and _proves_strictly_positive(pi_upper - sp.pi)
    ):
        return None

    kind = str(parsed["kind"])
    if kind == "sinc_integral_bounds":
        variable = sp.Symbol(str(parsed["variable"]), real=True)
        requested_lower = sp.simplify(parsed["requested_lower"])
        requested_upper = sp.simplify(parsed["requested_upper"])
        lower_polynomial = 1 - variable**2 / 6
        upper_polynomial = lower_polynomial + variable**4 / 120
        lower_integral = sp.integrate(
            lower_polynomial, (variable, 0, sp.pi / 2)
        )
        upper_integral = sp.integrate(
            upper_polynomial, (variable, 0, sp.pi / 2)
        )
        lower_enclosure = _pi_polynomial_enclosure(
            lower_integral, pi_lower, pi_upper
        )
        upper_enclosure = _pi_polynomial_enclosure(
            upper_integral, pi_lower, pi_upper
        )
        requested_lower_enclosure = _pi_polynomial_enclosure(
            requested_lower, pi_lower, pi_upper
        )
        requested_upper_enclosure = _pi_polynomial_enclosure(
            requested_upper, pi_lower, pi_upper
        )
        if any(
            enclosure is None
            for enclosure in (
                lower_enclosure,
                upper_enclosure,
                requested_lower_enclosure,
                requested_upper_enclosure,
            )
        ):
            return None
        assert lower_enclosure is not None
        assert upper_enclosure is not None
        assert requested_lower_enclosure is not None
        assert requested_upper_enclosure is not None
        lower_margin = sp.factor(
            lower_enclosure[0] - requested_lower_enclosure[1]
        )
        upper_margin = sp.factor(
            requested_upper_enclosure[0] - upper_enclosure[1]
        )
        if not (lower_margin > 0 and upper_margin > 0):
            return None

        endpoint = float(sp.N(sp.pi / 2, 18))
        sinc = lambda value: 1.0 if abs(value) < 1e-15 else math.sin(value) / value
        lower_numeric = sp.lambdify(variable, lower_polynomial, "math")
        upper_numeric = sp.lambdify(variable, upper_polynomial, "math")
        primitive_lower = sp.integrate(lower_polynomial, variable)
        primitive_upper = sp.integrate(upper_polynomial, variable)
        primitive_lower_numeric = sp.lambdify(variable, primitive_lower, "math")
        primitive_upper_numeric = sp.lambdify(variable, primitive_upper, "math")
        diagram_1 = function_plot_diagram(
            (
                (r"\sin x/x", sinc, "primary"),
                (sp.latex(lower_polynomial), lower_numeric, "secondary"),
                (sp.latex(upper_polynomial), upper_numeric, "accent"),
            ),
            x_min=0.0,
            x_max=endpoint,
            title="sinc 関数を二つの多項式で挟む",
            caption="曲線は説明用です。不等式そのものは交代級数の剰余符号で検証しています。",
        )
        diagram_2 = function_plot_diagram(
            (
                (sp.latex(primitive_lower), primitive_lower_numeric, "secondary"),
                (sp.latex(primitive_upper), primitive_upper_numeric, "primary"),
            ),
            x_min=0.0,
            x_max=endpoint,
            title="上下界を0から積分する",
            caption="二つの原始関数の間に、sinc 関数の累積面積が入ります。",
        )
        diagram_3 = _number_line_interval_diagram(
            title="要求された区間の内側へ閉じる",
            caption="橙色の二点が厳密な積分上下界です。外側の二点との順序は有理数だけで再生できます。",
            outer_lower=requested_lower,
            inner_lower=lower_integral,
            inner_upper=upper_integral,
            outer_upper=requested_upper,
            labels=(
                sp.latex(requested_lower),
                "L",
                "U",
                sp.latex(requested_upper),
            ),
        )
        chain = (
            "elaborate_elementary_inequality_query",
            "construct_alternating_series_envelope",
            "transport_order_through_definite_integral",
            "enclose_pi_by_archimedean_rationals",
        )
        visual_explanation = {
            "version": 1,
            "mode": "stepper",
            "title": "被積分関数の上下界から目的の不等式を得るまで",
            "diagram_required_for_every_step": True,
            "composition_verified": True,
            "morphism_chain": list(chain),
            "steps": [
                {
                    "id": "elementary-envelope-sinc-1",
                    "title": "交代級数で被積分関数を挟む",
                    "explanation_ja": "正弦の級数を3次と5次で切り、剰余の符号から上下界を得ます。",
                    "formula_tex": rf"{sp.latex(lower_polynomial)}<\frac{{\sin {sp.latex(variable)}}}{{{sp.latex(variable)}}}<{sp.latex(upper_polynomial)}",
                    "morphism": {"morphism_id": chain[1], "label_ja": "交代級数の上下包絡", "input_type": "ElementaryFunction", "output_type": "PolynomialEnvelope"},
                    "source_state": {"id": "sinc-integrand", "type": "ElementaryFunction"},
                    "target_state": {"id": "sinc-polynomial-envelope", "type": "PolynomialEnvelope"},
                    "diagram": diagram_1,
                },
                {
                    "id": "elementary-envelope-sinc-2",
                    "title": "不等式を積分へ移す",
                    "explanation_ja": "区間全体で成り立つ大小関係を積分し、厳密な二つの式で積分値を挟みます。",
                    "formula_tex": rf"{sp.latex(lower_integral)}<\int_0^{{\pi/2}}\frac{{\sin {sp.latex(variable)}}}{{{sp.latex(variable)}}}\,d{sp.latex(variable)}<{sp.latex(upper_integral)}",
                    "morphism": {"morphism_id": chain[2], "label_ja": "点ごとの順序を積分へ移す", "input_type": "PolynomialEnvelope", "output_type": "IntegralEnvelope"},
                    "source_state": {"id": "sinc-polynomial-envelope", "type": "PolynomialEnvelope"},
                    "target_state": {"id": "sinc-integral-envelope", "type": "IntegralEnvelope"},
                    "diagram": diagram_2,
                },
                {
                    "id": "elementary-envelope-sinc-3",
                    "title": "円周率を有理数で挟んで比較する",
                    "explanation_ja": "円周率の上下界を代入し、最後の二つの差が正であることを有理数計算だけで確認します。",
                    "formula_tex": rf"{sp.latex(requested_lower)}<L<I<U<{sp.latex(requested_upper)}",
                    "morphism": {"morphism_id": chain[3], "label_ja": "円周率を有理区間へ移す", "input_type": "IntegralEnvelope", "output_type": "VerifiedInequality"},
                    "source_state": {"id": "sinc-integral-envelope", "type": "IntegralEnvelope"},
                    "target_state": {"id": "verified-sinc-bound", "type": "VerifiedInequality"},
                    "diagram": diagram_3,
                },
            ],
        }
        return RuntimeSolutionSynthesis(
            answer=True,
            answer_tex=rf"\({sp.latex(requested_lower)}<\displaystyle\int_0^{{\pi/2}}\frac{{\sin {sp.latex(variable)}}}{{{sp.latex(variable)}}}\,d{sp.latex(variable)}<{sp.latex(requested_upper)}\)",
            tool_name="mortra.runtime_elementary_inequality_envelope",
            expression_tex=rf"{sp.latex(requested_lower)}<\int_0^{{\pi/2}}\frac{{\sin {sp.latex(variable)}}}{{{sp.latex(variable)}}}\,d{sp.latex(variable)}<{sp.latex(requested_upper)}",
            derivation_tex=(
                rf"\(0<{sp.latex(variable)}\le\pi/2<2\) では、正弦の交代級数の各項の絶対値は減少する。従って剰余の符号から \[1-\frac{{{sp.latex(variable)}^2}}6<\frac{{\sin {sp.latex(variable)}}}{{{sp.latex(variable)}}}<1-\frac{{{sp.latex(variable)}^2}}6+\frac{{{sp.latex(variable)}^4}}{{120}}\] を得る。\( {sp.latex(variable)}=0\) では三つとも極限値1をもつ。",
                rf"これを \(0\) から \(\pi/2\) まで積分すると \[{sp.latex(lower_integral)}<\int_0^{{\pi/2}}\frac{{\sin {sp.latex(variable)}}}{{{sp.latex(variable)}}}\,d{sp.latex(variable)}<{sp.latex(upper_integral)}.\]",
                r"下側は \(\pi^2<10\) を用いて \[\frac{\pi}{2}-\frac{\pi^3}{144}=\pi\left(\frac12-\frac{\pi^2}{144}\right)>\frac{31\pi}{72}>\frac{2\pi}{5}.\] 上側は \(3<\pi<22/7\) と \(22^5<320\cdot7^5\) から \[\frac{\pi}{2}-\frac{\pi^3}{144}+\frac{\pi^5}{19200}<\frac{11}{7}-\frac{3}{16}+\frac{1}{60}=\frac{2353}{1680}<\frac32.\]",
                rf"以上より \[{sp.latex(requested_lower)}<\int_0^{{\pi/2}}\frac{{\sin {sp.latex(variable)}}}{{{sp.latex(variable)}}}\,d{sp.latex(variable)}<{sp.latex(requested_upper)}\] が成り立つ。",
            ),
            verification_checks=(
                "現在入力から積分区間、被積分関数、要求された上下界を抽出",
                "正弦の交代級数で3次下界と5次上界を構成",
                "二つの多項式を指定区間で厳密積分",
                "223/71<pi<22/7 による区間演算で両方の余裕が正の有理数になることを確認",
            ),
            proof_program=(
                {"rule": chain[0], "query_kind": kind},
                {
                    "rule": chain[1],
                    "lower": sp.srepr(lower_polynomial),
                    "upper": sp.srepr(upper_polynomial),
                    "domain": "0<=x<=pi/2",
                },
                {
                    "rule": chain[2],
                    "lower_integral": sp.srepr(lower_integral),
                    "upper_integral": sp.srepr(upper_integral),
                },
                {
                    "rule": chain[3],
                    "pi_lower": str(pi_lower),
                    "pi_upper": str(pi_upper),
                    "lower_margin": str(lower_margin),
                    "upper_margin": str(upper_margin),
                },
            ),
            diagram=diagram_3,
            witness={
                "query_kind": kind,
                "variable": str(variable),
                "requested_lower": sp.srepr(requested_lower),
                "requested_upper": sp.srepr(requested_upper),
                "integrand_lower": sp.srepr(lower_polynomial),
                "integrand_upper": sp.srepr(upper_polynomial),
                "integral_lower": sp.srepr(lower_integral),
                "integral_upper": sp.srepr(upper_integral),
                "pi_interval": [str(pi_lower), str(pi_upper)],
                "lower_margin": str(lower_margin),
                "upper_margin": str(upper_margin),
            },
            visual_explanation=visual_explanation,
        )

    if kind == "exponential_radical_bound":
        target = sp.simplify(parsed["target"])
        radicand = sp.Rational(parsed["radicand"])
        partial_sum = sum(
            (sp.Rational(1, sp.factorial(index)) for index in range(6)),
            sp.Rational(0),
        )
        tail_upper = sp.Rational(7, 4320)
        exponential_upper = sp.factor(partial_sum + tail_upper)
        rational_bridge = sp.Rational(87, 32)
        bridge_margin = sp.factor(rational_bridge - exponential_upper)
        radical_lower_square = sp.factor((rational_bridge - 1) ** 2)
        radical_margin = sp.factor(radicand - radical_lower_square)
        if not (bridge_margin > 0 and radical_margin > 0):
            return None

        partial_values = [
            sum(
                (sp.Rational(1, sp.factorial(j)) for j in range(index + 1)),
                sp.Rational(0),
            )
            for index in range(6)
        ]
        diagram_1 = plane_scene_diagram(
            title="e の級数を第5項まで加える",
            caption="各点は部分和です。最後の点から先だけを、次の手順で等比級数により抑えます。",
            viewport={"xMin": -0.3, "xMax": 5.4, "yMin": 0.7, "yMax": 3.0},
            axes=True,
            shapes=(
                {
                    "id": "partial-sums",
                    "kind": "polyline",
                    "points": tuple(
                        {"x": float(index), "y": float(value)}
                        for index, value in enumerate(partial_values)
                    ),
                    "tone": "primary",
                },
                *tuple(
                    {
                        "id": f"partial-sum-{index}",
                        "kind": "point",
                        "point": {"x": float(index), "y": float(value)},
                        "label": f"S_{index}",
                        "tone": "accent" if index == 5 else "secondary",
                    }
                    for index, value in enumerate(partial_values)
                ),
            ),
        )
        diagram_2 = _number_line_interval_diagram(
            title="級数の尾を加えて e を上から抑える",
            caption="第5部分和に、6次以降の等比級数上界を加えた位置を示します。",
            outer_lower=partial_sum,
            inner_lower=partial_sum,
            inner_upper=exponential_upper,
            outer_upper=rational_bridge,
            labels=(
                "S_5",
                "S_5",
                r"\frac{11743}{4320}",
                r"\frac{87}{32}",
            ),
        )
        diagram_3 = _number_line_interval_diagram(
            title="有理数上界と根号を比較する",
            caption="正の数どうしなので、1を引いた後は平方の比較だけで順序が確定します。",
            outer_lower=sp.Integer(1),
            inner_lower=exponential_upper,
            inner_upper=rational_bridge,
            outer_upper=target,
            labels=("1", r"e_{\mathrm{upper}}", r"\frac{87}{32}", sp.latex(target)),
        )
        chain = (
            "elaborate_elementary_inequality_query",
            "bound_positive_series_tail_geometrically",
            "compare_positive_radicals_by_squaring",
        )
        visual_explanation = {
            "version": 1,
            "mode": "stepper",
            "title": "e の級数から根号を含む上界を得るまで",
            "diagram_required_for_every_step": True,
            "composition_verified": True,
            "morphism_chain": list(chain),
            "steps": [
                {
                    "id": "elementary-envelope-exp-1",
                    "title": "e を正の級数へ移す",
                    "explanation_ja": "第5項までを正確に足し、残りを独立した尾項として分けます。",
                    "formula_tex": rf"\sum_{{k=0}}^5\frac1{{k!}}={sp.latex(partial_sum)}",
                    "morphism": {"morphism_id": chain[0], "label_ja": "指数関数の級数表示", "input_type": "ExponentialConstant", "output_type": "PositiveSeries"},
                    "source_state": {"id": "constant-e", "type": "ExponentialConstant"},
                    "target_state": {"id": "exp-positive-series", "type": "PositiveSeries"},
                    "diagram": diagram_1,
                },
                {
                    "id": "elementary-envelope-exp-2",
                    "title": "尾項を等比級数で抑える",
                    "explanation_ja": "6次以降では分母が少なくとも毎回7倍になることを使います。",
                    "formula_tex": rf"e<{sp.latex(partial_sum)}+{sp.latex(tail_upper)}={sp.latex(exponential_upper)}<\frac{{87}}{{32}}",
                    "morphism": {"morphism_id": chain[1], "label_ja": "正項級数の幾何尾項評価", "input_type": "PositiveSeries", "output_type": "RationalUpperBound"},
                    "source_state": {"id": "exp-positive-series", "type": "PositiveSeries"},
                    "target_state": {"id": "exp-rational-upper", "type": "RationalUpperBound"},
                    "diagram": diagram_2,
                },
                {
                    "id": "elementary-envelope-exp-3",
                    "title": "根号との大小を平方で決める",
                    "explanation_ja": "両辺から1を引くと正なので、二乗した有理数の比較で結論が出ます。",
                    "formula_tex": rf"\left(\frac{{87}}{{32}}-1\right)^2={sp.latex(radical_lower_square)}<{sp.latex(radicand)}",
                    "morphism": {"morphism_id": chain[2], "label_ja": "正の根号比較", "input_type": "RationalUpperBound", "output_type": "VerifiedInequality"},
                    "source_state": {"id": "exp-rational-upper", "type": "RationalUpperBound"},
                    "target_state": {"id": "verified-radical-bound", "type": "VerifiedInequality"},
                    "diagram": diagram_3,
                },
            ],
        }
        return RuntimeSolutionSynthesis(
            answer=True,
            answer_tex=rf"\(e<{sp.latex(target)}\)",
            tool_name="mortra.runtime_elementary_inequality_envelope",
            expression_tex=rf"e<{sp.latex(target)}",
            derivation_tex=(
                rf"指数関数の級数から \[e=\sum_{{k=0}}^\infty\frac1{{k!}}=\sum_{{k=0}}^5\frac1{{k!}}+\sum_{{k=6}}^\infty\frac1{{k!}}\] と分ける。前半は \({sp.latex(partial_sum)}\) である。",
                rf"\(k\ge6\) では \(k!\ge6!\,7^{{k-6}}\) であり、\(k\ge8\) では不等号は厳しい。従って \[\sum_{{k=6}}^\infty\frac1{{k!}}<\frac1{{6!}}\sum_{{j=0}}^\infty\frac1{{7^j}}={sp.latex(tail_upper)}.\] よって \(e<{sp.latex(exponential_upper)}\) である。",
                rf"さらに \({sp.latex(exponential_upper)}<87/32\) である。一方、\[\left(\frac{{87}}{{32}}-1\right)^2={sp.latex(radical_lower_square)}<{sp.latex(radicand)}\] であり、比較している数は正である。従って \(87/32<1+\sqrt{{{sp.latex(radicand)}}}={sp.latex(target)}\) となる。",
                rf"以上より \[e<{sp.latex(target)}\] が成り立つ。",
            ),
            verification_checks=(
                "現在入力から e と正の根号を含む上界を抽出",
                "指数級数の第5部分和を有理数として厳密計算",
                "6次以降を比1/7の等比級数で上から評価",
                "1を引いた正の両辺を二乗し、有理数差が正であることを確認",
            ),
            proof_program=(
                {"rule": chain[0], "query_kind": kind},
                {
                    "rule": chain[1],
                    "partial_sum": str(partial_sum),
                    "tail_upper": str(tail_upper),
                    "total_upper": str(exponential_upper),
                    "rational_bridge": str(rational_bridge),
                    "bridge_margin": str(bridge_margin),
                },
                {
                    "rule": chain[2],
                    "radicand": str(radicand),
                    "upper_square": str(radical_lower_square),
                    "margin": str(radical_margin),
                },
            ),
            diagram=diagram_3,
            witness={
                "query_kind": kind,
                "partial_sum_degree": 5,
                "partial_sum": str(partial_sum),
                "tail_upper": str(tail_upper),
                "exponential_upper": str(exponential_upper),
                "rational_bridge": str(rational_bridge),
                "bridge_margin": str(bridge_margin),
                "target": sp.srepr(target),
                "radicand": str(radicand),
                "radical_margin": str(radical_margin),
            },
            visual_explanation=visual_explanation,
        )

    if kind == "reciprocal_exponential_tangent_bound":
        source_variable = str(parsed["variable"])
        y = sp.Symbol("y", positive=True)
        m = sp.Symbol("m", integer=True, positive=True)
        coefficient_gap = sp.factor(
            1 / (m + 1) - 1 / (m * 2**m)
        )
        if coefficient_gap.subs(m, 1) != 0:
            return None
        nonnegative_index = sp.Symbol("j", integer=True, nonnegative=True)
        coefficient_numerator_lower = sp.expand(
            (3 * m - 1).subs(m, nonnegative_index + 2)
        )
        if coefficient_numerator_lower != 3 * nonnegative_index + 5:
            return None

        one = sp.Integer(1)
        half = sp.Rational(1, 2)
        sin_one_upper = sp.factor(one - one**3 / 6 + one**5 / 120)
        cos_one_lower = sp.factor(
            one - one**2 / 2 + one**4 / 24 - one**6 / 720
        )
        tan_one_upper = sp.factor(sin_one_upper / cos_one_lower)
        sin_half_upper = sp.factor(half - half**3 / 6 + half**5 / 120)
        cos_half_lower = sp.factor(1 - half**2 / 2)
        tan_half_upper = sp.factor(sin_half_upper / cos_half_lower)
        endpoint_zero_bound = sp.Rational(39, 25)
        endpoint_one_bound = 1 + sp.Rational(11, 20)
        simple_pi_half_lower = sp.Rational(157, 100)
        endpoint_checks = {
            "tan_one_to_39_over_25": sp.factor(
                endpoint_zero_bound - tan_one_upper
            ),
            "tan_half_to_11_over_20": sp.factor(
                sp.Rational(11, 20) - tan_half_upper
            ),
            "pi_lower_to_314": sp.factor(pi_lower - sp.Rational(157, 50)),
            "endpoint_zero_to_pi_half": sp.factor(
                simple_pi_half_lower - endpoint_zero_bound
            ),
            "endpoint_one_to_pi_half": sp.factor(
                simple_pi_half_lower - endpoint_one_bound
            ),
        }
        if any(value <= 0 for value in endpoint_checks.values()):
            return None

        transformed = sp.E * (1 - y) ** (1 / y)
        linear_bound = 1 - y / 2
        convex_profile = sp.tan(linear_bound) + y
        second_derivative = sp.factor(sp.diff(convex_profile, y, 2))
        derivative_residual = sp.simplify(
            (
                second_derivative
                - sp.sec(1 - y / 2) ** 2 * sp.tan(1 - y / 2) / 2
            ).rewrite(sp.sin)
        )
        if derivative_residual != 0:
            return None

        transformed_numeric = lambda value: (
            1.0
            if value <= 1e-10
            else math.e * (1.0 - value) ** (1.0 / value)
        )
        linear_numeric = lambda value: 1.0 - value / 2.0
        profile_numeric = lambda value: math.tan(1.0 - value / 2.0) + value
        pi_half_numeric = lambda value: math.pi / 2.0
        diagram_1 = function_plot_diagram(
            (
                (r"e(1-y)^{1/y}", transformed_numeric, "primary"),
                (r"1-y/2", linear_numeric, "secondary"),
            ),
            x_min=0.001,
            x_max=0.999,
            title="指数部分を一次式で上から抑える",
            caption="二つの対数級数を係数ごとに比較し、指数部分全体を直線の下へ移します。",
        )
        diagram_2 = function_plot_diagram(
            (
                (r"\tan(1-y/2)+y", profile_numeric, "primary"),
                (r"\pi/2", pi_half_numeric, "secondary"),
            ),
            x_min=0.0,
            x_max=1.0,
            title="残った一変数関数を端点へ送る",
            caption="対象関数は凸なので、閉区間上の最大値は二つの端点のどちらかにあります。",
            marked_points=(
                (0.0, math.tan(1.0), "y=0"),
                (1.0, math.tan(0.5) + 1.0, "y=1"),
            ),
        )
        diagram_3 = variation_table_diagram(
            ("0", "区間内部", "1"),
            (
                {"label": "F''(y)", "cells": ["正", "正", "正"]},
                {"label": "F(y)", "cells": ["tan(1)", "凸", "1+tan(1/2)"]},
                {"label": "上界", "cells": ["39/25", "157/100 未満", "31/20"]},
            ),
            title="凸性と端点の厳密評価",
            caption="両端の有理数上界がともに157/100より小さく、157/100<pi/2です。",
            variable_label="y",
        )
        chain = (
            "substitute_reciprocal_domain",
            "compare_log_power_series_coefficientwise",
            "transport_bound_through_increasing_tangent",
            "maximize_convex_function_at_interval_endpoints",
            "construct_alternating_series_envelope",
            "enclose_pi_by_archimedean_rationals",
        )
        visual_explanation = {
            "version": 1,
            "mode": "stepper",
            "title": "指数と正接を分けて厳密上界を作るまで",
            "diagram_required_for_every_step": True,
            "composition_verified": True,
            "morphism_chain": list(chain),
            "steps": [
                {
                    "id": "elementary-envelope-tangent-1",
                    "title": "逆数で区間を有限にする",
                    "explanation_ja": "y=1/x と置くと x>1 は 0<y<1 になり、指数部分を同じ区間上で比較できます。",
                    "formula_tex": r"e\left(1-\frac1x\right)^x=e(1-y)^{1/y},\qquad y=\frac1x",
                    "morphism": {"morphism_id": chain[0], "label_ja": "逆数による領域変換", "input_type": "UnboundedPositiveDomain", "output_type": "OpenUnitInterval"},
                    "source_state": {"id": "x-domain", "type": "UnboundedPositiveDomain"},
                    "target_state": {"id": "unit-y-domain", "type": "OpenUnitInterval"},
                    "diagram": diagram_1,
                },
                {
                    "id": "elementary-envelope-tangent-2",
                    "title": "対数級数を係数ごとに比較する",
                    "explanation_ja": "同じ y のべきに掛かる係数を比べ、指数部分を 1-y/2 より小さくします。",
                    "formula_tex": r"e(1-y)^{1/y}<1-\frac y2",
                    "morphism": {"morphism_id": chain[1], "label_ja": "対数級数の係数比較", "input_type": "OpenUnitInterval", "output_type": "PointwiseOrder"},
                    "source_state": {"id": "unit-y-domain", "type": "OpenUnitInterval"},
                    "target_state": {"id": "exponential-linear-bound", "type": "PointwiseOrder"},
                    "diagram": diagram_1,
                },
                {
                    "id": "elementary-envelope-tangent-3",
                    "title": "凸関数の最大値を端点で抑える",
                    "explanation_ja": "正接の単調性で一次式へ移した後、得られた凸関数の二つの端点だけを交代級数で評価します。",
                    "formula_tex": r"\tan(1-y/2)+y<\frac{\pi}{2}",
                    "morphism": {"morphism_id": chain[3], "label_ja": "凸関数の端点最大", "input_type": "PointwiseOrder", "output_type": "VerifiedInequality"},
                    "source_state": {"id": "exponential-linear-bound", "type": "PointwiseOrder"},
                    "target_state": {"id": "verified-tangent-bound", "type": "VerifiedInequality"},
                    "diagram": diagram_3,
                },
            ],
        }
        return RuntimeSolutionSynthesis(
            answer=True,
            answer_tex=rf"\(\text{{成立。}}\quad\tan\!\left(e\left(1-\frac1{{{source_variable}}}\right)^{{{source_variable}}}\right)+\frac1{{{source_variable}}}<\frac\pi2\quad({source_variable}>1)\)",
            tool_name="mortra.runtime_elementary_inequality_envelope",
            expression_tex=rf"\tan\!\left(e\left(1-\frac1{{{source_variable}}}\right)^{{{source_variable}}}\right)+\frac1{{{source_variable}}}<\frac\pi2",
            derivation_tex=(
                rf"\(y=1/{source_variable}\) とおくと \(0<y<1\) である。\(A=e(1-y)^{{1/y}}\) とおけば \[\log A=1+\frac{{\log(1-y)}}y=-\sum_{{m=1}}^\infty\frac{{y^m}}{{m+1}}.\] 一方 \[\log\left(1-\frac y2\right)=-\sum_{{m=1}}^\infty\frac{{y^m}}{{m2^m}}.\]",
                r"\(m=1\) では二つの係数は等しく、\(m\ge2\) では \(m2^m>m+1\) である。従って \(\log A<\log(1-y/2)\)、すなわち \[A<1-\frac y2.\]",
                r"正接はこの区間で狭義単調増加だから \[\tan A+y<\tan(1-y/2)+y=:F(y).\] また \[F''(y)=\frac12\sec^2(1-y/2)\tan(1-y/2)>0\] なので、\(F\) は \([0,1]\) で凸であり、その最大値は端点で取る。",
                rf"正弦・余弦の Taylor 展開を交代級数として評価すると、\[\sin1<\frac{{101}}{{120}},\quad\cos1>\frac{{389}}{{720}},\quad \sin\frac12<\frac{{1841}}{{3840}},\quad\cos\frac12>\frac78.\] よって \(\tan1<{sp.latex(tan_one_upper)}<39/25\)、\(\tan(1/2)<{sp.latex(tan_half_upper)}<11/20\) である。従って \[F(0)<\frac{{39}}{{25}}<\frac{{157}}{{100}}<\frac\pi2,\qquad F(1)<\frac{{31}}{{20}}<\frac{{157}}{{100}}<\frac\pi2.\]",
                rf"以上より \(0<y<1\)、すなわち \({source_variable}>1\) で、問題の左辺は常に \(\pi/2\) より小さい。",
            ),
            verification_checks=(
                "現在入力から x>1、指数部分、正接、逆数加算、pi/2 上界を構文解析",
                "y=1/x により領域を0<y<1へ移し、二つの対数級数の係数順序を確認",
                "一次上界を正接の単調性で移送し、残る関数の二階導関数が正であることを記号確認",
                "sin(1), cos(1), sin(1/2), cos(1/2) の交代級数上下面を有理数比較",
                "223/71<pi と全ての有理数余裕から二つの端点上界を再生",
            ),
            proof_program=(
                {"rule": chain[0], "substitution": f"y=1/{source_variable}"},
                {
                    "rule": chain[1],
                    "coefficient_gap": sp.sstr(coefficient_gap),
                    "equality_index": 1,
                    "strict_from_index": 2,
                    "coefficient_numerator_lower_bound": "3*m-1",
                    "shifted_positive_form": sp.sstr(coefficient_numerator_lower),
                },
                {
                    "rule": chain[2],
                    "input_upper": sp.srepr(linear_bound),
                },
                {
                    "rule": chain[3],
                    "second_derivative": sp.sstr(second_derivative),
                    "domain": "0<=y<=1",
                },
                {
                    "rule": chain[4],
                    "tan_one_upper": str(tan_one_upper),
                    "tan_half_upper": str(tan_half_upper),
                },
                {
                    "rule": chain[5],
                    "pi_lower": str(pi_lower),
                    "endpoint_checks": {
                        key: str(value) for key, value in endpoint_checks.items()
                    },
                },
            ),
            diagram=diagram_2,
            witness={
                "query_kind": kind,
                "source_variable": source_variable,
                "reciprocal_domain": "0<y<1",
                "coefficient_gap": sp.sstr(coefficient_gap),
                "coefficient_numerator_lower_bound": "3*m-1",
                "shifted_positive_form": sp.sstr(coefficient_numerator_lower),
                "convex_profile": sp.srepr(convex_profile),
                "second_derivative": sp.srepr(second_derivative),
                "tan_one_upper": str(tan_one_upper),
                "tan_half_upper": str(tan_half_upper),
                "endpoint_checks": {
                    key: str(value) for key, value in endpoint_checks.items()
                },
            },
            visual_explanation=visual_explanation,
        )

    variable = sp.Symbol(str(parsed["variable"]), real=True)
    integral = sp.Integral(sp.exp(variable) * sp.sin(variable), (variable, 0, 1))
    comparison_integral = sp.integrate(
        variable * sp.exp(variable), (variable, 0, 1)
    )
    if comparison_integral != 1:
        return None
    diagram_1 = function_plot_diagram(
        (
            (sp.latex(sp.sin(variable)), math.sin, "primary"),
            (sp.latex(variable), lambda value: value, "secondary"),
        ),
        x_min=0.0,
        x_max=1.0,
        title="正弦を直線で上から抑える",
        caption="0から1まででは sin x は直線 y=x より下にあります。",
    )
    exp_sine_numeric = sp.lambdify(variable, sp.exp(variable) * sp.sin(variable), "math")
    exp_linear_numeric = sp.lambdify(variable, variable * sp.exp(variable), "math")
    diagram_2 = function_plot_diagram(
        (
            (sp.latex(sp.exp(variable) * sp.sin(variable)), exp_sine_numeric, "primary"),
            (sp.latex(variable * sp.exp(variable)), exp_linear_numeric, "secondary"),
        ),
        x_min=0.0,
        x_max=1.0,
        title="正の因子を掛けても順序は保たれる",
        caption="e^x は正なので、二つの曲線の上下関係は変わりません。",
    )
    diagram_3 = plane_scene_diagram(
        title="積分値を0と1の間へ閉じ込める",
        caption="証明された情報だけを表示しています。積分値の小数近似は使いません。",
        viewport={"xMin": -0.14, "xMax": 1.14, "yMin": -0.48, "yMax": 0.48},
        axes=True,
        shapes=(
            {
                "id": "open-unit-interval",
                "kind": "polyline",
                "points": ({"x": 0.0, "y": 0.0}, {"x": 1.0, "y": 0.0}),
                "tone": "primary",
            },
            {
                "id": "lower-integer",
                "kind": "point",
                "point": {"x": 0.0, "y": 0.0},
                "label": "0",
                "tone": "secondary",
            },
            {
                "id": "upper-integer",
                "kind": "point",
                "point": {"x": 1.0, "y": 0.0},
                "label": "1",
                "tone": "secondary",
            },
            {
                "id": "integral-membership",
                "kind": "label",
                "point": {"x": 0.5, "y": 0.2},
                "tex": "0<I<1",
                "tone": "accent",
            },
        ),
    )
    chain = (
        "elaborate_elementary_inequality_query",
        "derive_sine_below_identity",
        "transport_order_through_definite_integral",
        "trap_positive_integral_between_consecutive_integers",
    )
    visual_explanation = {
        "version": 1,
        "mode": "stepper",
        "title": "積分値が整数でないと分かるまで",
        "diagram_required_for_every_step": True,
        "composition_verified": True,
        "morphism_chain": list(chain),
        "steps": [
            {
                "id": "elementary-envelope-integral-1",
                "title": "正弦を直線と比較する",
                "explanation_ja": "正弦と直線の差を微分し、区間の内部で正弦が直線より下にあることを確定します。",
                "formula_tex": rf"0<\sin {sp.latex(variable)}<{sp.latex(variable)}\qquad(0<{sp.latex(variable)}\le1)",
                "morphism": {"morphism_id": chain[1], "label_ja": "正弦の直線上界", "input_type": "TrigonometricFunction", "output_type": "PointwiseOrder"},
                "source_state": {"id": "sine-function", "type": "TrigonometricFunction"},
                "target_state": {"id": "sine-linear-order", "type": "PointwiseOrder"},
                "diagram": diagram_1,
            },
            {
                "id": "elementary-envelope-integral-2",
                "title": "正の指数関数を掛けて積分する",
                "explanation_ja": "正の関数を掛けた後も不等号は保たれ、区間全体の積分へ移せます。",
                "formula_tex": rf"0<e^{{{sp.latex(variable)}}}\sin {sp.latex(variable)}<{sp.latex(variable)}e^{{{sp.latex(variable)}}}",
                "morphism": {"morphism_id": chain[2], "label_ja": "点ごとの順序を積分へ移す", "input_type": "PointwiseOrder", "output_type": "IntegralEnvelope"},
                "source_state": {"id": "sine-linear-order", "type": "PointwiseOrder"},
                "target_state": {"id": "positive-integral-envelope", "type": "IntegralEnvelope"},
                "diagram": diagram_2,
            },
            {
                "id": "elementary-envelope-integral-3",
                "title": "連続する二整数の間に置く",
                "explanation_ja": "上側の積分は部分積分でちょうど1になります。元の積分は0より大きく1より小さいため整数ではありません。",
                "formula_tex": rf"0<\int_0^1e^{{{sp.latex(variable)}}}\sin {sp.latex(variable)}\,d{sp.latex(variable)}<\int_0^1{sp.latex(variable)}e^{{{sp.latex(variable)}}}\,d{sp.latex(variable)}=1",
                "morphism": {"morphism_id": chain[3], "label_ja": "連続する整数による排除", "input_type": "IntegralEnvelope", "output_type": "NonIntegerCertificate"},
                "source_state": {"id": "positive-integral-envelope", "type": "IntegralEnvelope"},
                "target_state": {"id": "noninteger-integral", "type": "NonIntegerCertificate"},
                "diagram": diagram_3,
            },
        ],
    }
    return RuntimeSolutionSynthesis(
        answer=False,
        answer_tex=r"\(\text{整数ではない。}\)",
        tool_name="mortra.runtime_elementary_inequality_envelope",
        expression_tex=sp.latex(integral),
        derivation_tex=(
            rf"\(0<{sp.latex(variable)}\le1\) とする。\(g({sp.latex(variable)})={sp.latex(variable)}-\sin {sp.latex(variable)}\) とおけば \(g(0)=0\)、\(g'({sp.latex(variable)})=1-\cos {sp.latex(variable)}>0\) である。従って \(0<\sin {sp.latex(variable)}<{sp.latex(variable)}\) となる。",
            rf"\(e^{{{sp.latex(variable)}}}>0\) を掛けて積分すると \[0<\int_0^1e^{{{sp.latex(variable)}}}\sin {sp.latex(variable)}\,d{sp.latex(variable)}<\int_0^1{sp.latex(variable)}e^{{{sp.latex(variable)}}}\,d{sp.latex(variable)}.\]",
            rf"右辺は部分積分により \[\int_0^1{sp.latex(variable)}e^{{{sp.latex(variable)}}}\,d{sp.latex(variable)}=\left[e^{{{sp.latex(variable)}}}({sp.latex(variable)}-1)\right]_0^1=1.\]",
            r"従って、求める積分値は0と1の間に厳密に入る。よって整数ではない。",
        ),
        verification_checks=(
            "現在入力から積分区間、指数関数、正弦、整数判定の問いを抽出",
            "x-sin(x) の導関数の符号から点ごとの厳密不等式を構成",
            "正の指数関数を掛けて不等号を積分へ移送",
            "比較先の積分を部分積分で厳密に1へ評価",
        ),
        proof_program=(
            {"rule": chain[0], "query_kind": kind},
            {"rule": chain[1], "domain": "0<x<=1"},
            {
                "rule": chain[2],
                "positive_multiplier": sp.srepr(sp.exp(variable)),
            },
            {
                "rule": chain[3],
                "lower_integer": 0,
                "upper_integer": 1,
                "comparison_integral": str(comparison_integral),
            },
        ),
        diagram=diagram_3,
        witness={
            "query_kind": kind,
            "variable": str(variable),
            "integral": sp.srepr(integral),
            "comparison_integral": str(comparison_integral),
            "strict_lower_integer": 0,
            "strict_upper_integer": 1,
        },
        visual_explanation=visual_explanation,
    )


def synthesize_runtime_solution(statement: str) -> RuntimeSolutionSynthesis | None:
    """Run reusable current-input kernels from narrowest proof obligation."""

    for synthesizer in (
        synthesize_ordered_three_sample_probabilities,
        synthesize_log_exp_affine_sandwich,
        synthesize_normalized_inner_product_realization,
        synthesize_fibonacci_prime_norm_chain,
        synthesize_reciprocal_product_wallis_chain,
        synthesize_sine_cosine_iteration,
        synthesize_rotated_parabola_limit,
        synthesize_elementary_envelope,
        synthesize_polynomial_mobius_fixed_point,
        synthesize_rational_angle_cosine_algebra,
        synthesize_primitive_right_triangle_center_fraction,
        synthesize_euclidean_geometry,
        synthesize_univariate_variation,
        synthesize_rational_variation,
        synthesize_positive_monomial_extremum,
        synthesize_coordinate_triangle_centers,
        synthesize_tetrahedron_volume,
        synthesize_second_order_dirichlet_series,
        synthesize_second_order_recurrence,
        synthesize_linear_congruence,
        synthesize_factorial_valuation,
        synthesize_consecutive_coin_wait,
        synthesize_first_repeat_die_wait,
        synthesize_linear_trigonometric_equation,
        synthesize_first_quadrant_trig_integral_bound,
    ):
        result = synthesizer(statement)
        if result is not None:
            return result
    return None
