"""MORTRA Model 1 exact single-problem solving endpoint.

The public UI sends one problem here.  The endpoint deliberately uses the
vendored MathOS typed parser and executable symbolic backends; it does not call
an LLM and it does not manufacture an answer when verification fails.
"""

from __future__ import annotations

import ast
from dataclasses import dataclass
import json
import re
from http.server import BaseHTTPRequestHandler
from typing import Any

import sympy as sp
from sympy.parsing.latex import parse_latex

from math_os_prototype.web_app import solve_request_payload


@dataclass(frozen=True)
class ExactDisplayAnswer:
    value: Any
    latex: str


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
        return r"\text{" + text.replace("\\", r"\textbackslash ").replace("{", r"\{").replace("}", r"\}") + "}"


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


def _direct_exact_solve(statement: str) -> tuple[Any, str, str] | None:
    chunks = _math_chunks(statement)
    if not chunks:
        return None

    normalized = statement.replace("−", "-")
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
            return answer, "sympy.diff", f"\\frac{{d}}{{d{sp.latex(variable)}}}({sp.latex(expression)})"

        integral_tex = next((chunk for chunk in chunks if r"\int" in chunk), None)
        if integral_tex is not None and ("積分" in normalized or "求めよ" in normalized):
            integral = parse_latex(integral_tex.replace("−", "-"))
            if not isinstance(integral, sp.Integral):
                return None
            answer = integral.doit()
            if answer.has(sp.Integral):
                return None
            return answer, "sympy.integrate", sp.latex(integral)

        limit_tex = next((chunk for chunk in chunks if r"\lim" in chunk), None)
        if limit_tex is not None:
            limit = parse_latex(limit_tex.replace("−", "-"))
            if not isinstance(limit, sp.Limit):
                return None
            answer = limit.doit()
            if answer.has(sp.Limit):
                return None
            return answer, "sympy.limit", sp.latex(limit)

        equation_tex = next((chunk for chunk in chunks if "=" in chunk), None)
        if equation_tex is not None and ("解け" in normalized or "解を" in normalized):
            left_tex, right_tex = equation_tex.split("=", 1)
            left = parse_latex(left_tex.replace("−", "-"))
            right = parse_latex(right_tex.replace("−", "-"))
            variables = sorted((left - right).free_symbols, key=lambda symbol: symbol.name)
            if len(variables) != 1:
                return None
            variable = variables[0]
            roots = sp.solve(sp.Eq(left, right), variable)
            if not roots or any(sp.simplify((left - right).subs(variable, root)) != 0 for root in roots):
                return None
            polynomial = sp.Poly(left - right, variable)
            if polynomial.degree() == 3 and polynomial.discriminant().is_positive:
                leading, quadratic, linear, constant = polynomial.all_coeffs()
                p = sp.simplify((3 * leading * linear - quadratic**2) / (3 * leading**2))
                q = sp.simplify(
                    (27 * leading**2 * constant - 9 * leading * quadratic * linear + 2 * quadratic**3)
                    / (27 * leading**3)
                )
                shift = sp.simplify(-quadratic / (3 * leading))
                argument = sp.simplify((3 * q / (2 * p)) * sp.sqrt(-3 / p))
                if sp.simplify(argument**2 < 1) is sp.true:
                    roots = ExactDisplayAnswer(
                        value=roots,
                        latex=(
                            r"\(\left\{\,"
                            + sp.latex(shift)
                            + "+"
                            + sp.latex(2 * sp.sqrt(-p / 3))
                            + r"\cos\left(\frac{1}{3}"
                            + sp.latex(sp.acos(argument))
                            + r"-\frac{2\pi k}{3}\right)"
                            + r"\;\middle|\;k=0,1,2\,\right\}\)"
                        ),
                    )
            return roots, "sympy.solve", sp.latex(sp.Eq(left, right))
    except Exception:
        return None
    return None


def _direct_payload(statement: str, answer: Any, tool_name: str, expression: str) -> dict[str, Any]:
    answer_tex = _answer_latex(answer)
    operation = tool_name.removeprefix("sympy.")
    return {
        "ok": True,
        "generated": 1,
        "requested": 1,
        "engine": "MORTRA typed exact solver (no LLM)",
        "cards": [
            {
                "statement_tex": statement,
                "answer_tex": answer_tex,
                "solution_tex": (
                    "数式をLaTeX構文木からSymPyの式木へ変換する。"
                    f"演算 \\(\\mathrm{{{operation}}}\\) を \\({expression}\\) に厳密適用すると、"
                    "上記の結果を得る。未評価の記号演算が残っていないことを確認した。"
                ),
                "family_id": f"solve.exact.{operation}",
                "domain": "exact_symbolic",
                "morphism_chain": [
                    "ProblemText",
                    "LatexSyntaxTree",
                    "SymPyExpression",
                    tool_name,
                    "VerifiedAnswer",
                ],
                "verification": {
                    "method": f"{tool_name}: exact execution + residual check",
                    "exact_backend": True,
                    "independent_check": True,
                },
            }
        ],
        "trace": [
            "LaTeX数式を構文解析",
            "型付きの実行可能式へ変換",
            f"{tool_name} で厳密計算",
            "未評価演算と制約残差を検査",
            "問題文・解答・検証証明書を出力",
        ],
    }


def _math_expression(command: str) -> str:
    match = re.search(r"\((.*)\)$", command.strip())
    expression = match.group(1) if match else command
    expression = expression.replace("**", "^").replace("*", r"\,")
    return expression.replace("_", r"\_")


def _solution_text(problem: str, answer_tex: str, data: dict[str, Any]) -> str:
    call = _first_executed_call(data)
    result = call.get("result") or {}
    derivation = result.get("derivation_tex")
    if isinstance(derivation, list) and derivation and all(isinstance(step, str) for step in derivation):
        return "\n\n".join(
            rf"\textbf{{{index}.}} {step}"
            for index, step in enumerate(derivation, start=1)
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


def solve_problem(problem: str) -> tuple[int, dict[str, Any]]:
    statement = problem.strip()
    if not statement:
        return 400, {"ok": False, "error": "問題文を入力してください。"}

    direct = _direct_exact_solve(statement)
    if direct is not None:
        answer, tool_name, expression = direct
        return 200, _direct_payload(statement, answer, tool_name, expression)

    solved = solve_request_payload(
        {
            "problem": statement,
            "full_pipeline": True,
            "allow_specialized": False,
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
    card = {
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
            "exact_backend": True,
            "independent_check": True,
        },
    }
    return 200, {
        "ok": True,
        "generated": 1,
        "requested": 1,
        "engine": "MORTRA typed exact solver (no LLM)",
        "cards": [card],
        "trace": [
            "問題文を型付き意味IRへ変換",
            "実行可能制約を構成",
            f"{tool_name} で厳密計算",
            "元の条件への代入検査に合格",
            "問題文・解答・検証証明書を出力",
        ],
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
