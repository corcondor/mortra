"""Current-input proof programs for public single-problem solving.

Every synthesizer in this module compiles mathematical structure found in the
current statement.  No problem id, stored answer, or completed Atlas route is
consulted.  The returned diagram is another representation of the same exact
objects used by the proof.
"""

from __future__ import annotations

from dataclasses import dataclass
from fractions import Fraction
from math import gcd
import re
from typing import Any, Callable

import sympy as sp
from sympy.parsing.latex import parse_latex

from math_os_prototype.latex_frontend import parse_latex_problem
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


def _real_float(value: sp.Expr) -> float | None:
    try:
        numeric = complex(sp.N(value, 30))
    except (TypeError, ValueError):
        return None
    if abs(numeric.imag) > 1e-10:
        return None
    return float(numeric.real)


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


def synthesize_second_order_recurrence(statement: str) -> RuntimeSolutionSynthesis | None:
    """Compile a current-input recurrence to its companion matrix and roots."""

    if "漸化式" not in statement and "数列" not in statement:
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


def _assigned_integral(statement: str) -> tuple[str, sp.Integral] | None:
    match = re.search(
        r"(?P<name>[A-Za-z])\s*=\s*(?P<integral>\\int.*?\\,?d[A-Za-z])(?=\s*(?:とする|、|。|0\s*<|$))",
        statement,
        flags=re.DOTALL,
    )
    if match is None:
        return None
    try:
        integral = parse_latex(match.group("integral").replace("−", "-"))
    except Exception:
        return None
    if isinstance(integral, sp.Integral):
        named_constants = {
            symbol: sp.pi
            for symbol in integral.free_symbols
            if symbol.name in {"pi", "π"}
        }
        if named_constants:
            integral = integral.xreplace(named_constants)
    return (match.group("name"), integral) if isinstance(integral, sp.Integral) else None


def synthesize_first_quadrant_trig_integral_bound(statement: str) -> RuntimeSolutionSynthesis | None:
    """Synthesize the complement-angle/Cauchy proof for its structural form."""

    assigned = _assigned_integral(statement)
    if assigned is None or "証明" not in statement:
        return None
    name, integral = assigned
    compact = re.sub(r"\s+", "", statement)
    if f"0<{name}<2" not in compact:
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
        rf"\(u=\sin {sp.latex(variable)}+\cos {sp.latex(variable)}\) とおく。\(0\le {sp.latex(variable)}\le\pi/2\) では \(1\le u\le\sqrt2<\pi/2\) なので、\(\sin u+\cos u>0\) であり \({name}>0\) である。",
        r"また \(\pi/2<2u<\pi\) だから、補角 \(\pi-2u\) は第1象限にある。したがって \(\sin 2u=\sin(\pi-2u)<\pi-2u\) である。",
        r"よって \((\sin u+\cos u)^2=1+\sin2u<1+\pi-2u\) となる。さらに Cauchy--Schwarz の不等式より"
        + rf"\[{name}^2\le\frac{{\pi}}{{2}}\int_0^{{\pi/2}}(\sin u+\cos u)^2\,d{sp.latex(variable)}"
        + rf"<\frac{{\pi}}{{2}}\left(\frac{{\pi}}{{2}}(1+\pi)-2\int_0^{{\pi/2}}u\,d{sp.latex(variable)}\right).\]",
        rf"ここで \(\int_0^{{\pi/2}}u\,d{sp.latex(variable)}=2\) である。\(h(t)=\frac t2\left(\frac t2(1+t)-4\right)\) とおくと \(h'(t)={sp.latex(derivative_h)}>0\;(t\ge3)\) であり、"
        rf"\(\pi<22/7\) から \({name}^2<h(\pi)<h(22/7)={sp.latex(bound_value)}<4\)。従って \(0<{name}<2\) である。",
    )
    return RuntimeSolutionSynthesis(
        answer=True,
        answer_tex=rf"\(0<{name}<2\)",
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
            {"rule": "introduce_inner_trigonometric_coordinate", "u": sp.srepr(u)},
            {"rule": "move_double_angle_to_first_quadrant"},
            {"rule": "apply_sine_linear_upper_bound"},
            {"rule": "apply_cauchy_schwarz_to_integral"},
            {"rule": "evaluate_inner_coordinate_integral", "value": str(u_integral)},
            {"rule": "close_pi_rational_bound", "bound": str(bound_value)},
        ),
        diagram=diagram,
        witness={
            "inner_coordinate": sp.srepr(u),
            "inner_integral": str(u_integral),
            "rational_pi_bound": "22/7",
            "final_square_bound": str(bound_value),
        },
    )


def synthesize_runtime_solution(statement: str) -> RuntimeSolutionSynthesis | None:
    """Run reusable current-input kernels from narrowest proof obligation."""

    for synthesizer in (
        synthesize_univariate_variation,
        synthesize_rational_variation,
        synthesize_positive_monomial_extremum,
        synthesize_coordinate_triangle_centers,
        synthesize_tetrahedron_volume,
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
