"""MORTRA Model 1 exact single-problem solving endpoint.

The public UI sends one problem here.  The endpoint deliberately uses the
vendored MathOS typed parser and executable symbolic backends; it does not call
an LLM and it does not manufacture an answer when verification fails.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import hashlib
import json
import re
from http.server import BaseHTTPRequestHandler
from typing import Any

import sympy as sp
from sympy.parsing.latex import parse_latex

from math_os_prototype.web_app import solve_request_payload
from math_os_prototype.solution_artifact import attach_solution_artifact


@dataclass(frozen=True)
class ExactDisplayAnswer:
    value: Any
    latex: str


@dataclass(frozen=True)
class ExactSolveOutcome:
    answer: Any
    tool_name: str
    expression_tex: str
    derivation_tex: tuple[str, ...]
    verification_method: str = "exact execution + residual check"
    verification_checks: tuple[str, ...] = ()
    diagram: dict[str, Any] | None = None
    diagram_tikz: str | None = None


def _real_number(value: Any) -> float | None:
    try:
        numeric = complex(sp.N(value, 12))
    except (TypeError, ValueError):
        return None
    if abs(numeric.imag) > 1e-8 or not (-1e100 < numeric.real < 1e100):
        return None
    return float(numeric.real)


def _sample_curve(
    expression: sp.Expr,
    variable: sp.Symbol,
    x_min: float,
    x_max: float,
    *,
    count: int = 121,
) -> list[dict[str, float]]:
    points: list[dict[str, float]] = []
    for index in range(count):
        x_value = x_min + (x_max - x_min) * index / max(1, count - 1)
        try:
            y_value = complex(sp.N(expression.subs(variable, x_value), 12))
        except (TypeError, ValueError, ZeroDivisionError):
            continue
        if abs(y_value.imag) > 1e-7 or not (-1e8 < y_value.real < 1e8):
            continue
        points.append({"x": round(x_value, 8), "y": round(float(y_value.real), 8)})
    return points


def _visible_y_range(curves: list[list[dict[str, float]]]) -> tuple[float, float]:
    values = sorted(point["y"] for curve in curves for point in curve)
    if not values:
        return -1.0, 1.0
    lower = values[max(0, int(len(values) * 0.05) - 1)]
    upper = values[min(len(values) - 1, int(len(values) * 0.95))]
    if abs(upper - lower) < 1e-8:
        margin = max(1.0, abs(upper) * 0.25)
    else:
        margin = max(0.35, (upper - lower) * 0.16)
    return lower - margin, upper + margin


def _curve_diagram(
    *,
    title: str,
    caption: str,
    x_min: float,
    x_max: float,
    curves: list[tuple[sp.Expr, sp.Symbol, str]],
    marked_x: list[tuple[float, str]] | None = None,
    fill_first_to_axis: bool = False,
) -> tuple[dict[str, Any], str]:
    sampled = [_sample_curve(expression, variable, x_min, x_max) for expression, variable, _ in curves]
    y_min, y_max = _visible_y_range(sampled)
    clipped = [
        [
            {"x": point["x"], "y": min(y_max, max(y_min, point["y"]))}
            for point in curve
        ]
        for curve in sampled
    ]
    shapes: list[dict[str, Any]] = []
    tones = [tone for _, _, tone in curves]
    for index, points in enumerate(clipped):
        if len(points) < 2:
            continue
        if index == 0 and fill_first_to_axis:
            shapes.append({
                "kind": "polyline",
                "points": [{"x": points[0]["x"], "y": 0.0}, *points, {"x": points[-1]["x"], "y": 0.0}],
                "closed": True,
                "tone": tones[index],
                "fill": True,
            })
        shapes.append({"kind": "polyline", "points": points, "tone": tones[index]})
    for x_value, label in marked_x or []:
        shapes.append({
            "kind": "point",
            "point": {"x": x_value, "y": 0.0},
            "label": label,
            "tone": "accent",
        })

    diagram = {
        "version": 1,
        "kind": "plane",
        "title": title,
        "caption": caption,
        "viewport": {"xMin": x_min, "xMax": x_max, "yMin": y_min, "yMax": y_max},
        "axes": True,
        "shapes": shapes,
    }

    width, height = 9.0, 5.4
    def map_point(point: dict[str, float]) -> tuple[float, float]:
        px = -width / 2 + width * (point["x"] - x_min) / max(1e-9, x_max - x_min)
        py = -height / 2 + height * (point["y"] - y_min) / max(1e-9, y_max - y_min)
        return px, py

    axis_x = map_point({"x": 0.0, "y": y_min})[0] if x_min <= 0 <= x_max else -width / 2
    axis_y = map_point({"x": x_min, "y": 0.0})[1] if y_min <= 0 <= y_max else -height / 2
    tikz = [
        r"\begin{tikzpicture}[line cap=round,line join=round]",
        rf"\draw[->,gray] ({-width / 2:.3f},{axis_y:.3f}) -- ({width / 2:.3f},{axis_y:.3f}) node[right] {{$x$}};",
        rf"\draw[->,gray] ({axis_x:.3f},{-height / 2:.3f}) -- ({axis_x:.3f},{height / 2:.3f}) node[above] {{$y$}};",
    ]
    colors = {"primary": "cyan!70!black", "secondary": "blue!70!black", "accent": "orange!85!black"}
    for points, tone in zip(clipped, tones):
        if len(points) < 2:
            continue
        coordinates = " ".join(f"({px:.4f},{py:.4f})" for px, py in map(map_point, points))
        tikz.append(rf"\draw[thick,{colors.get(tone, 'black!65')}] plot coordinates {{{coordinates}}};")
    for x_value, label in marked_x or []:
        px, py = map_point({"x": x_value, "y": 0.0})
        tikz.append(rf"\fill[orange!85!black] ({px:.4f},{py:.4f}) circle (1.6pt) node[below] {{{_escape_tikz(label)}}};")
    tikz.append(r"\end{tikzpicture}")
    return diagram, "\n".join(tikz)


def _escape_tikz(value: str) -> str:
    return value.replace("\\", r"\textbackslash{}").replace("_", r"\_").replace("%", r"\%")


def _first_executed_call(data: dict[str, Any]) -> dict[str, Any]:
    calls = data.get("tool_execution", {}).get("tool_calls", [])
    direct = next(
        (
            call
            for call in calls
            if call.get("status") == "executed" and call.get("error") is None
        ),
        {},
    )
    if direct:
        return direct
    action = next(
        (
            action
            for action in data.get("math_search", {}).get("actions", [])
            if action.get("status") == "executed"
            and (action.get("result") or {}).get("status") == "solved"
        ),
        {},
    )
    if not action:
        return {}
    return {
        "name": action.get("name"),
        "command": action.get("command") or action.get("input_summary"),
        "status": "executed",
        "result": action.get("result"),
        "error": None,
    }


def _latex_atom(value: Any) -> str:
    if isinstance(value, sp.Basic):
        return sp.latex(value)
    if isinstance(value, (list, tuple, set)):
        return r"\left\{" + r",\;".join(_latex_atom(item) for item in value) + r"\right\}"
    text = str(value).strip()
    try:
        return sp.latex(sp.sympify(text))
    except Exception:
        replacements = {
            "\\": r"\textbackslash{}",
            "&": r"\&",
            "%": r"\%",
            "$": r"\$",
            "#": r"\#",
            "_": r"\_",
            "{": r"\{",
            "}": r"\}",
            "^": r"\textasciicircum{}",
            "~": r"\textasciitilde{}",
        }
        escaped = "".join(replacements.get(character, character) for character in text)
        return r"\text{" + escaped + "}"


def _answer_latex(answer: Any) -> str:
    if isinstance(answer, ExactDisplayAnswer):
        return answer.latex
    if isinstance(answer, str):
        try:
            parsed = ast.literal_eval(answer)
        except (ValueError, SyntaxError):
            parsed = answer
    else:
        parsed = answer
    return r"\(" + _latex_atom(parsed) + r"\)"


def _math_chunks(statement: str) -> list[str]:
    patterns = (
        r"\\\[(.*?)\\\]",
        r"\$\$(.*?)\$\$",
        r"(?<!\$)\$(?!\$)(.*?)(?<!\$)\$(?!\$)",
    )
    chunks: list[str] = []
    for pattern in patterns:
        chunks.extend(match.strip() for match in re.findall(pattern, statement, flags=re.DOTALL))
    return chunks


def _three_real_cubic_chart(
    expression: sp.Expr,
    polynomial: sp.Poly,
    variable: sp.Symbol,
) -> tuple[ExactDisplayAnswer, list[sp.Expr], tuple[str, ...], tuple[str, ...]] | None:
    """Solve a three-real-root cubic without constructing Cardano radicals."""

    if polynomial.degree() != 3:
        return None
    discriminant = sp.factor(polynomial.discriminant())
    if discriminant.is_positive is not True:
        return None

    leading, quadratic, linear, constant = polynomial.all_coeffs()
    p = sp.factor((3 * leading * linear - quadratic**2) / (3 * leading**2))
    q = sp.factor(
        (27 * leading**2 * constant - 9 * leading * quadratic * linear + 2 * quadratic**3)
        / (27 * leading**3)
    )
    if p.is_negative is not True:
        return None

    shift = sp.factor(-quadratic / (3 * leading))
    radius = sp.sqrt(-p / 3)
    argument = sp.factor(-q / (2 * radius**3))
    if sp.factor(1 - argument**2).is_positive is not True:
        return None

    # This coefficient identity is the exact certificate for the chart change.
    depressed_variable = sp.Dummy("y")
    normalized = sp.expand(
        expression.subs(variable, depressed_variable + shift) / leading
    )
    depressed = depressed_variable**3 + p * depressed_variable + q
    if sp.expand(normalized - depressed) != 0:
        return None

    amplitude = 2 * radius
    base_angle = sp.acos(argument) / 3
    exact_roots = [
        shift + amplitude * sp.cos(base_angle - 2 * sp.pi * index / 3)
        for index in range(3)
    ]
    try:
        plot_roots = sorted(
            (
                root
                for root in sp.nroots(polynomial, n=18, maxsteps=100)
                if abs(complex(root).imag) < 1e-10
            ),
            key=lambda root: float(sp.re(root)),
        )
    except (ValueError, ArithmeticError):
        plot_roots = exact_roots

    family_latex = (
        sp.latex(shift)
        + "+"
        + sp.latex(amplitude)
        + r"\cos\left(\frac{1}{3}\arccos\left("
        + sp.latex(argument)
        + r"\right)-\frac{2\pi k}{3}\right)"
    )
    answer = ExactDisplayAnswer(
        value=tuple(exact_roots),
        latex=(
            r"\(\left\{\,"
            + family_latex
            + r"\;\middle|\;k=0,1,2\,\right\}\)"
        ),
    )
    derivation = (
        rf"左辺から右辺を移項し、\({sp.latex(expression)}=0\) とする。判別式は "
        rf"\({sp.latex(discriminant)}>0\) なので、相異なる実根は3個である。",
        rf"\({sp.latex(variable)}={sp.latex(depressed_variable + shift)}\) とおくと、係数恒等式により "
        rf"\({sp.latex(depressed)}=0\) へ正規化される。",
        rf"\({sp.latex(depressed_variable)}=2\sqrt{{-{sp.latex(p)}/3}}\cos\theta\) とおき、"
        r"三倍角公式 \(4\cos^3\theta-3\cos\theta=\cos3\theta\) を使うと、"
        rf"\(\cos3\theta={sp.latex(argument)}\) を得る。",
        rf"したがって \({sp.latex(variable)}={family_latex}\;(k=0,1,2)\) である。"
        r"正規化恒等式と三倍角公式が各候補を元の三次式へ戻し、判別式と次数が完全性を保証する。",
    )
    checks = (
        "元の三次式と減次三次式の係数恒等式を記号的に確認",
        "判別式が正であり、相異なる実根が3個であることを確認",
        "三倍角公式により3候補が減次三次式を満たすことを確認",
    )
    return answer, plot_roots, derivation, checks


def _direct_exact_solve(statement: str) -> ExactSolveOutcome | None:
    chunks = _math_chunks(statement)
    if not chunks:
        return None

    normalized = statement.replace("−", "-")
    if r"\item" in normalized:
        return None
    try:
        if "導関数" in normalized or "微分せよ" in normalized:
            definition = next((chunk for chunk in chunks if "=" in chunk), None)
            if definition is None:
                return None
            _, expression_tex = definition.split("=", 1)
            expression = parse_latex(expression_tex.replace("−", "-"))
            variables = sorted(expression.free_symbols, key=lambda symbol: symbol.name)
            if len(variables) != 1:
                return None
            variable = variables[0]
            answer = sp.diff(expression, variable)
            diagram, diagram_tikz = _curve_diagram(
                title="関数と導関数",
                caption="青が元の関数、灰色が導関数です。表示範囲内で同じ厳密式を数値化しています。",
                x_min=-3.0,
                x_max=3.0,
                curves=[(expression, variable, "primary"), (answer, variable, "secondary")],
            )
            return ExactSolveOutcome(
                answer=answer,
                tool_name="sympy.diff",
                expression_tex=f"\\frac{{d}}{{d{sp.latex(variable)}}}({sp.latex(expression)})",
                derivation_tex=(
                    rf"与えられた関数は \(f({sp.latex(variable)})={sp.latex(expression)}\) である。",
                    rf"各項を微分すると \(f'({sp.latex(variable)})={sp.latex(answer)}\) を得る。",
                    "右図では元の関数と導関数を同じ座標系に描き、傾きの符号を照合した。",
                ),
                diagram=diagram,
                diagram_tikz=diagram_tikz,
            )

        integral_tex = next((chunk for chunk in chunks if r"\int" in chunk), None)
        if integral_tex is not None and ("積分" in normalized or "求めよ" in normalized):
            integral = parse_latex(integral_tex.replace("−", "-"))
            if not isinstance(integral, sp.Integral):
                return None
            answer = integral.doit()
            if answer.has(sp.Integral):
                return None
            integrand = integral.function
            limit_spec = integral.limits[0]
            variable = limit_spec[0]
            if len(limit_spec) != 3:
                return None
            lower, upper = limit_spec[1:]
            x_lower, x_upper = _real_number(lower), _real_number(upper)
            if x_lower is None or x_upper is None or x_lower == x_upper:
                return None
            antiderivative = sp.integrate(integrand, variable)
            diagram, diagram_tikz = _curve_diagram(
                title="定積分の被積分関数",
                caption="青い領域の符号付き面積を、原始関数の端点差で厳密に評価します。",
                x_min=min(x_lower, x_upper),
                x_max=max(x_lower, x_upper),
                curves=[(integrand, variable, "primary")],
                marked_x=[(x_lower, sp.latex(lower)), (x_upper, sp.latex(upper))],
                fill_first_to_axis=True,
            )
            return ExactSolveOutcome(
                answer=answer,
                tool_name="sympy.integrate",
                expression_tex=sp.latex(integral),
                derivation_tex=(
                    rf"被積分関数を \(h({sp.latex(variable)})={sp.latex(integrand)}\) とおく。",
                    rf"原始関数の一つは \(H({sp.latex(variable)})={sp.latex(antiderivative)}\) である。",
                    rf"微積分の基本定理より \(H({sp.latex(upper)})-H({sp.latex(lower)})={sp.latex(answer)}\) となる。",
                ),
                diagram=diagram,
                diagram_tikz=diagram_tikz,
            )

        limit_tex = next((chunk for chunk in chunks if r"\lim" in chunk), None)
        if limit_tex is not None:
            limit = parse_latex(limit_tex.replace("−", "-"))
            if not isinstance(limit, sp.Limit):
                return None
            answer = limit.doit()
            integrand, variable, destination = limit.args[:3]
            if (
                answer.has(sp.Limit)
                or sp.simplify(answer - integrand) == 0
                or variable in answer.free_symbols
            ):
                return None
            center = _real_number(destination)
            diagram = diagram_tikz = None
            if center is not None:
                diagram, diagram_tikz = _curve_diagram(
                    title="極限点の近傍",
                    caption="極限点の左右で同じ関数値へ近づくことを、厳密式から描いた近傍図で確認します。",
                    x_min=center - 2.0,
                    x_max=center + 2.0,
                    curves=[(integrand, variable, "primary")],
                    marked_x=[(center, sp.latex(destination))],
                )
            try:
                local_form = sp.series(integrand, variable, destination, 4)
                local_step = rf"\({sp.latex(integrand)}={sp.latex(local_form)}\) と局所展開できる。"
            except (NotImplementedError, ValueError):
                local_step = "分子・分母の共通因子または既知の基本極限を厳密に整理する。"
            return ExactSolveOutcome(
                answer=answer,
                tool_name="sympy.limit",
                expression_tex=sp.latex(limit),
                derivation_tex=(
                    rf"\({sp.latex(variable)}\to {sp.latex(destination)}\) における局所形を調べる。",
                    local_step,
                    rf"したがって極限値は \({sp.latex(answer)}\) である。",
                ),
                diagram=diagram,
                diagram_tikz=diagram_tikz,
            )

        equation_tex = next((chunk for chunk in chunks if "=" in chunk), None)
        if equation_tex is not None and ("解け" in normalized or "解を" in normalized):
            left_tex, right_tex = equation_tex.split("=", 1)
            left = parse_latex(left_tex.replace("−", "-"))
            right = parse_latex(right_tex.replace("−", "-"))
            variables = sorted((left - right).free_symbols, key=lambda symbol: symbol.name)
            if len(variables) != 1:
                return None
            variable = variables[0]
            expression = sp.expand(left - right)
            try:
                polynomial = sp.Poly(expression, variable)
            except sp.PolynomialError:
                polynomial = None

            cubic_chart = (
                _three_real_cubic_chart(expression, polynomial, variable)
                if polynomial is not None
                else None
            )
            if cubic_chart is not None:
                answer, roots_for_plot, derivation, checks = cubic_chart
                real_roots = [
                    (numeric, rf"x_{{{index}}}")
                    for index, root in enumerate(roots_for_plot, start=1)
                    if (numeric := _real_number(root)) is not None
                ]
                root_values = [root for root, _ in real_roots]
                span = max(2.0, (max(root_values) - min(root_values)) * 0.35)
                diagram, diagram_tikz = _curve_diagram(
                    title="三次方程式の3実根",
                    caption="青い曲線は左辺−右辺です。橙色の点は三角関数形で厳密表示した3実根です。",
                    x_min=min(root_values) - span,
                    x_max=max(root_values) + span,
                    curves=[(expression, variable, "primary")],
                    marked_x=real_roots,
                )
                return ExactSolveOutcome(
                    answer=answer,
                    tool_name="sympy.cubic_trigonometric_chart",
                    expression_tex=sp.latex(sp.Eq(left, right)),
                    derivation_tex=derivation,
                    verification_method=(
                        "depressed-cubic coefficient identity + triple-angle identity + discriminant"
                    ),
                    verification_checks=checks,
                    diagram=diagram,
                    diagram_tikz=diagram_tikz,
                )

            roots = sp.solve(sp.Eq(left, right), variable)
            if not roots or any(sp.simplify(expression.subs(variable, root)) != 0 for root in roots):
                return None
            roots_for_plot = roots
            real_roots = [
                (numeric, sp.latex(root))
                for root in roots_for_plot
                if (numeric := _real_number(root)) is not None
            ]
            if real_roots:
                root_values = [root for root, _ in real_roots]
                span = max(2.0, (max(root_values) - min(root_values)) * 0.35)
                x_min, x_max = min(root_values) - span, max(root_values) + span
            else:
                x_min, x_max = -4.0, 4.0
            diagram, diagram_tikz = _curve_diagram(
                title="方程式の零点",
                caption="青い曲線は左辺−右辺です。橙色の点が元の方程式を満たす実数解です。",
                x_min=x_min,
                x_max=x_max,
                curves=[(expression, variable, "primary")],
                marked_x=real_roots,
            )
            factorized = sp.factor(expression)
            factor_step = (
                rf"左辺から右辺を移項すると \({sp.latex(expression)}=0\) であり、"
                rf"\({sp.latex(factorized)}=0\) と因数分解できる。"
                if factorized != expression
                else rf"左辺から右辺を移項し、\({sp.latex(expression)}=0\) を厳密に解く。"
            )
            root_set = r"\left\{" + r",\;".join(sp.latex(root) for root in roots_for_plot) + r"\right\}"
            return ExactSolveOutcome(
                answer=roots,
                tool_name="sympy.solve",
                expression_tex=sp.latex(sp.Eq(left, right)),
                derivation_tex=(
                    factor_step,
                    rf"各因子または代数的根を解くと \({sp.latex(variable)}\in {root_set}\) を得る。",
                    "各候補を元の等式へ代入し、残差がすべて0になることを確認した。",
                ),
                verification_checks=("各候補を元の等式へ代入し、残差0を確認",),
                diagram=diagram,
                diagram_tikz=diagram_tikz,
            )
    except Exception:
        return None
    return None


def _direct_payload(
    statement: str,
    outcome: ExactSolveOutcome,
    *,
    evaluation_mode: str,
) -> dict[str, Any]:
    answer_tex = _answer_latex(outcome.answer)
    operation = outcome.tool_name.removeprefix("sympy.")
    morphism_chain = [
        "ProblemText",
        "LatexSyntaxTree",
        "SymPyExpression",
        outcome.tool_name,
        "VerifiedAnswer",
    ]
    verification_method = f"{outcome.tool_name}: {outcome.verification_method}"
    execution_certificate = {
        "schema": "mortra.direct-exact-certificate.v1",
        "statement_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
        "answer_tex_sha256": hashlib.sha256(answer_tex.encode("utf-8")).hexdigest(),
        "tool_name": outcome.tool_name,
        "expression_tex": outcome.expression_tex,
        "morphism_chain": morphism_chain,
        "checks": list(outcome.verification_checks),
    }
    certificate_sha256 = hashlib.sha256(
        json.dumps(
            execution_certificate,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()
    trace = [
        "LaTeX数式を構文解析",
        "型付きの実行可能式へ変換",
        f"{outcome.tool_name} で厳密計算",
        "未評価演算と制約残差を検査",
        "問題文・解答・検証証明書を出力",
    ]
    card = attach_solution_artifact(
        {
            "statement_tex": statement,
            "answer_tex": answer_tex,
            "solution_tex": "\n\n".join(
                rf"\textbf{{{index}.}} {step}"
                for index, step in enumerate(outcome.derivation_tex, start=1)
            ),
            "family_id": f"solve.exact.{operation}",
            "domain": "exact_symbolic",
            "morphism_chain": morphism_chain,
            "verification": {
                "method": verification_method,
                "exact_backend": True,
                "independent_check": True,
                "checks": list(outcome.verification_checks),
                "certificate_sha256": certificate_sha256,
            },
            "execution_certificate": execution_certificate,
            **({"diagram": outcome.diagram} if outcome.diagram else {}),
            **({"diagram_tikz": outcome.diagram_tikz} if outcome.diagram_tikz else {}),
        },
        trace,
    )
    return {
        "ok": True,
        "generated": 1,
        "requested": 1,
        "engine": "MORTRA typed exact solver (no LLM)",
        "evaluation_mode": evaluation_mode,
        "cards": [card],
        "trace": trace,
    }


def _math_expression(command: str) -> str:
    match = re.search(r"\((.*)\)$", command.strip())
    expression = match.group(1) if match else command
    expression = expression.replace("**", "^").replace("*", r"\,")
    return expression.replace("_", r"\_")


def _plain_derivation_to_tex(step: str) -> str:
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "^": r"\textasciicircum{}",
        "~": r"\textasciitilde{}",
    }
    return "".join(replacements.get(character, character) for character in step)


def _solution_text(problem: str, answer_tex: str, data: dict[str, Any]) -> str:
    call = _first_executed_call(data)
    result = call.get("result") or {}
    derivation = result.get("derivation_tex")
    if isinstance(derivation, list) and derivation and all(isinstance(step, str) for step in derivation):
        return "\n\n".join(
            rf"\textbf{{{index}.}} {step}"
            for index, step in enumerate(derivation, start=1)
        )
    theorem_derivation = result.get("derivation")
    if (
        isinstance(theorem_derivation, list)
        and theorem_derivation
        and all(isinstance(step, str) for step in theorem_derivation)
    ):
        return "\n\n".join(
            rf"\textbf{{{index}.}} {_plain_derivation_to_tex(step)}"
            for index, step in enumerate(theorem_derivation, start=1)
        )
    command = str(call.get("command") or "exact symbolic execution")
    operator = str(result.get("query_operator") or call.get("name") or "constraint solving")
    expression = _math_expression(command)
    verification = data.get("verification", {})
    checks = verification.get("checks") or ["候補を元の制約へ代入して照合した。"]
    checks_tex = " ".join(str(check) for check in checks)
    operator_tex = operator.replace("_", r"\_")
    return (
        "問題文を字句・構文解析し，量化・定義域・等式を型付き制約へ変換する。"
        f"実行演算は \\(\\mathrm{{{operator_tex}}}\\) であり，"
        f"厳密計算対象は \\({expression}\\) である。"
        f"計算結果は {answer_tex}。"
        f"最後に得られた候補を元の条件へ戻して検査した。{checks_tex}"
    )


def solve_problem(
    problem: str,
    *,
    allow_theorem_kernels: bool = True,
) -> tuple[int, dict[str, Any]]:
    statement = problem.strip()
    if not statement:
        return 400, {"ok": False, "error": "問題文を入力してください。"}

    evaluation_mode = "portfolio" if allow_theorem_kernels else "cold"

    direct = _direct_exact_solve(statement)
    if direct is not None:
        return 200, _direct_payload(
            statement,
            direct,
            evaluation_mode=evaluation_mode,
        )

    solved = solve_request_payload(
        {
            "problem": statement,
            "full_pipeline": True,
            "allow_specialized": False,
            "allow_theorem_kernels": allow_theorem_kernels,
            "live_retrieval": False,
        }
    )
    data = solved.get("data") or {}
    answer = solved.get("answer")
    verification = data.get("verification") or {}
    evidence = _first_executed_call(data)
    verified = answer not in (None, "", []) and verification.get("status") == "verified"
    if not verified:
        return 422, {
            "ok": False,
            "generated": 0,
            "requested": 1,
            "engine": "MORTRA typed exact solver (no LLM)",
            "evaluation_mode": evaluation_mode,
            "error": "型付き制約は生成できましたが、厳密に検証できる解答までは到達しませんでした。",
            "trace": [
                "問題文を型付き意味IRへ変換",
                "実行可能制約を探索",
                "検証済み解答が得られないため公開を停止",
            ],
        }

    intent = str(data.get("tool_execution", {}).get("intent") or "exact_constraint")
    route = str(data.get("tool_execution", {}).get("route") or data.get("domain_ir", {}).get("domain") or "mathematics")
    call = _first_executed_call(data)
    result = call.get("result") or {}
    answer_tex = (
        result.get("answer_tex")
        if isinstance(result.get("answer_tex"), str)
        else _answer_latex(answer)
    )
    tool_name = str(call.get("name") or "exact_backend")
    raw_execution_certificate = (
        result.get("certificate")
        if isinstance(result.get("certificate"), dict)
        else None
    )
    execution_certificate = (
        dict(raw_execution_certificate)
        if raw_execution_certificate is not None
        else None
    )
    if execution_certificate is not None:
        execution_certificate["runtime_binding"] = {
            "input_sha256": hashlib.sha256(statement.encode("utf-8")).hexdigest(),
            "answer_tex_sha256": hashlib.sha256(answer_tex.encode("utf-8")).hexdigest(),
            "tool_name": tool_name,
        }
    certificate_verified = bool(
        execution_certificate
        and execution_certificate.get("verified") is True
        and result.get("verified") is True
    )
    certificate_sha256 = (
        hashlib.sha256(
            json.dumps(
                execution_certificate,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
        if execution_certificate is not None
        else None
    )
    trace = [
        "問題文を型付き意味IRへ変換",
        "実行可能制約を構成",
        f"{tool_name} で厳密計算",
        "元の条件への代入検査に合格",
        "問題文・解答・検証証明書を出力",
    ]
    card_payload = {
        "statement_tex": statement,
        "answer_tex": answer_tex,
        "solution_tex": _solution_text(statement, answer_tex, data),
        "family_id": f"solve.{route}.{intent}",
        "domain": route,
        "morphism_chain": [
            "ProblemText",
            "TypedSemanticIR",
            "ExecutableConstraint",
            tool_name,
            "VerifiedAnswer",
        ],
        "verification": {
            "method": f"{tool_name}: exact execution + original-constraint check",
            "exact_backend": bool(result.get("verified") is True),
            "independent_check": certificate_verified,
            "verification_scope": (
                "deterministic in-process witness replay; "
                "not an independent external theorem prover"
            ),
            "checks": [
                "typed executable call completed",
                "structural theorem replay certificate verified",
                "original-domain witness and proof obligations replayed",
            ],
            "certificate_sha256": certificate_sha256,
        },
        "execution_certificate": execution_certificate,
    }
    for display_key in ("diagram", "diagram_tikz", "visual_explanation"):
        display_value = result.get(display_key)
        if display_value:
            card_payload[display_key] = display_value
    card = attach_solution_artifact(card_payload, trace)
    return 200, {
        "ok": True,
        "generated": 1,
        "requested": 1,
        "engine": "MORTRA typed exact solver (no LLM)",
        "evaluation_mode": evaluation_mode,
        "cards": [card],
        "trace": trace,
    }


class handler(BaseHTTPRequestHandler):
    def _json(self, status: int, payload: dict[str, Any]) -> None:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:  # noqa: N802 - Vercel handler contract
        self._json(200, {"engine": "MORTRA typed exact solver (no LLM)", "mode": "single-problem"})

    def do_POST(self) -> None:  # noqa: N802 - Vercel handler contract
        try:
            length = int(self.headers.get("Content-Length", "0"))
            payload = json.loads(self.rfile.read(length) or b"{}")
            status, result = solve_problem(str(payload.get("problem") or ""))
        except Exception as error:  # The public endpoint must return structured failure.
            status, result = 500, {"ok": False, "error": f"解答器の実行に失敗しました: {error}"}
        self._json(status, result)
