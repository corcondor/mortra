"""Geometry DSL for envelope, passing-region, and locus problems."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

try:
    from math_os_prototype.tool_adapters import ToolRegistry
except ImportError:  # Allows direct script execution from this folder.
    from tool_adapters import ToolRegistry

try:
    import sympy as sp
except ImportError:  # pragma: no cover - useful for planning-only environments.
    sp = None


TASK_ALIASES = {
    "envelope": "envelope",
    "包絡線": "envelope",
    "region": "region",
    "passing_region": "region",
    "pass_region": "region",
    "通過領域": "region",
    "locus": "locus",
    "軌跡": "locus",
}


KNOWN_FUNCTIONS = {
    "sin": getattr(sp, "sin", None),
    "cos": getattr(sp, "cos", None),
    "tan": getattr(sp, "tan", None),
    "exp": getattr(sp, "exp", None),
    "log": getattr(sp, "log", None),
    "sqrt": getattr(sp, "sqrt", None),
}


@dataclass
class ParamDomain:
    kind: str
    lower: str | None = None
    upper: str | None = None
    lower_closed: bool = True
    upper_closed: bool = True

    def label(self) -> str:
        if self.kind == "real":
            return "R"
        left = "[" if self.lower_closed else "("
        right = "]" if self.upper_closed else ")"
        return f"{left}{self.lower},{self.upper}{right}"


@dataclass
class GeometryProblem:
    task: str
    equations: dict[str, str]
    parameter: str
    domain: ParamDomain
    source: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def parse_geometry_dsl(source: str) -> GeometryProblem:
    statements = split_statements(source)
    task: str | None = None
    equations: dict[str, str] = {}
    parameter = "t"
    domain = ParamDomain("real")

    for statement in statements:
        lower = statement.lower()
        if lower in TASK_ALIASES:
            task = TASK_ALIASES[lower]
            continue
        if lower.startswith("task "):
            task_name = statement[5:].strip()
            task = TASK_ALIASES.get(task_name.lower(), task_name.lower())
            continue
        if lower.startswith("goal "):
            task_name = statement[5:].strip()
            task = TASK_ALIASES.get(task_name.lower(), task_name.lower())
            continue
        if lower.startswith("param "):
            parameter, domain = parse_param_statement(statement[6:].strip())
            continue
        if lower.startswith("family "):
            lhs, rhs = parse_equation(statement[7:].strip())
            equations[lhs] = rhs
            continue
        if re.match(r"^[a-zA-Z_]\w*\s*=", statement):
            lhs, rhs = parse_equation(statement)
            equations[lhs] = rhs
            continue

        raise ValueError(f"unrecognized Geometry DSL statement: {statement!r}")

    if task is None:
        if "x" in equations and "y" in equations:
            task = "locus"
        elif "y" in equations:
            task = "envelope"
        else:
            raise ValueError("Geometry DSL needs a task, for example: task envelope")

    if task not in {"envelope", "region", "locus"}:
        raise ValueError(f"unsupported Geometry DSL task: {task}")
    if not equations:
        raise ValueError("Geometry DSL needs at least one equation, for example: family y = t*x - t^2")

    return GeometryProblem(task, equations, parameter, domain, source)


def inspect_geometry_dsl(source: str) -> dict[str, Any]:
    problem = parse_geometry_dsl(source)
    return {
        "problem": asdict(problem),
        "command": command_for_problem(problem),
        "executable": True,
    }


def run_geometry_dsl(source: str, external_tools: bool = False) -> dict[str, Any]:
    problem = parse_geometry_dsl(source)
    if problem.task == "envelope":
        result = solve_envelope(problem)
    elif problem.task == "region":
        result = solve_region(problem)
    elif problem.task == "locus":
        result = solve_locus(problem)
    else:  # pragma: no cover - guarded in parser.
        raise ValueError(f"unsupported task: {problem.task}")
    tool_results = ToolRegistry().geometry_tool_results(
        problem,
        result,
        external_tools=external_tools,
    )
    return {"problem": asdict(problem), "result": result, "tool_results": tool_results}


def solve_envelope(problem: GeometryProblem) -> dict[str, Any]:
    require_sympy()
    if "y" not in problem.equations:
        raise ValueError("envelope currently expects a family y = f(x, t)")

    symbols = make_symbols(problem)
    t = symbols[problem.parameter]
    x = symbols.setdefault("x", sp.symbols("x"))
    y = symbols.setdefault("y", sp.symbols("y"))
    expr = sympify_expr(problem.equations["y"], symbols)
    relation = y - expr
    stationary = sp.diff(relation, t)
    resultant = sp.factor(sp.resultant(relation, stationary, t))
    return {
        "method": "resultant(F, dF/dparam)",
        "F": str(relation),
        "stationary": str(stationary),
        "envelope_relation": str(resultant),
        "readable": f"{resultant} = 0",
        "tool_next": "Lean can verify the eliminated relation after assumptions are formalized.",
    }


def solve_locus(problem: GeometryProblem) -> dict[str, Any]:
    require_sympy()
    if "x" not in problem.equations or "y" not in problem.equations:
        raise ValueError("locus expects both x = f(t) and y = g(t)")

    symbols = make_symbols(problem)
    t = symbols[problem.parameter]
    x = symbols.setdefault("x", sp.symbols("x"))
    y = symbols.setdefault("y", sp.symbols("y"))
    x_expr = sympify_expr(problem.equations["x"], symbols)
    y_expr = sympify_expr(problem.equations["y"], symbols)
    f_x = sp.together(x - x_expr).as_numer_denom()[0]
    f_y = sp.together(y - y_expr).as_numer_denom()[0]
    resultant = sp.factor(sp.resultant(f_x, f_y, t))
    return {
        "method": "resultant(x-f(t), y-g(t))",
        "relations": [str(f_x), str(f_y)],
        "locus_relation": str(resultant),
        "readable": f"{resultant} = 0",
    }


def solve_region(problem: GeometryProblem) -> dict[str, Any]:
    require_sympy()
    if "y" not in problem.equations:
        raise ValueError("region currently expects a family y = f(x, t)")

    symbols = make_symbols(problem)
    t = symbols[problem.parameter]
    y = symbols.setdefault("y", sp.symbols("y"))
    expr = sympify_expr(problem.equations["y"], symbols)
    existential = f"exists {problem.parameter} in {problem.domain.label()}: y = {sp.sstr(expr)}"

    if problem.domain.kind == "real":
        closed_form = derive_real_quadratic_range(expr, t, y)
        return {
            "method": "quantifier_elimination_for_real_parameter",
            "existential": existential,
            "closed_form": closed_form,
        }

    interval_reduction = derive_interval_candidate_bounds(expr, t, problem.domain)
    return {
        "method": "finite_candidate_reduction_for_bounded_parameter",
        "existential": existential,
        "candidate_bounds": interval_reduction,
        "next_tool": "Mathematica Reduce can turn these candidates into a piecewise inequality.",
    }


def derive_real_quadratic_range(expr: Any, param: Any, y_symbol: Any) -> dict[str, Any]:
    poly = sp.Poly(sp.expand(expr), param)
    degree = poly.degree()
    if degree == 0:
        value = sp.sstr(sp.factor(expr))
        return {"type": "constant", "relation": f"y = {value}"}
    if degree == 1:
        slope = poly.coeff_monomial(param)
        if slope.is_zero:
            value = sp.sstr(sp.factor(poly.coeff_monomial(1)))
            return {"type": "constant", "relation": f"y = {value}"}
        return {
            "type": "linear_real_parameter",
            "relation": "all real y if the parameter coefficient is nonzero",
            "coefficient": sp.sstr(slope),
        }
    if degree != 2:
        return {
            "type": "unsupported",
            "reason": f"real-parameter region supports degree <= 2 for now; got degree {degree}",
        }

    a = poly.coeff_monomial(param**2)
    b = poly.coeff_monomial(param)
    c = poly.coeff_monomial(1)
    vertex_value = sp.factor(c - b**2 / (4 * a))
    vertex_param = sp.factor(-b / (2 * a))
    if is_negative(a):
        inequality = sp.Le(y_symbol, vertex_value)
        sense = "upper_bound"
    elif is_positive(a):
        inequality = sp.Ge(y_symbol, vertex_value)
        sense = "lower_bound"
    else:
        return {
            "type": "quadratic_range",
            "reason": "quadratic coefficient sign is symbolic; need assumptions or CAS Reduce",
            "a": sp.sstr(a),
            "vertex_param": sp.sstr(vertex_param),
            "vertex_value": sp.sstr(vertex_value),
        }

    return {
        "type": "quadratic_range",
        "sense": sense,
        "a": sp.sstr(a),
        "vertex_param": sp.sstr(vertex_param),
        "vertex_value": sp.sstr(vertex_value),
        "inequality": sp.sstr(inequality),
    }


def derive_interval_candidate_bounds(expr: Any, param: Any, domain: ParamDomain) -> dict[str, Any]:
    lower = sympify_scalar(domain.lower)
    upper = sympify_scalar(domain.upper)
    derivative = sp.diff(expr, param)
    critical_points = sp.solve(derivative, param)
    candidates = [
        {"where": f"{param}={sp.sstr(lower)}", "value": sp.sstr(sp.factor(expr.subs(param, lower)))},
        {"where": f"{param}={sp.sstr(upper)}", "value": sp.sstr(sp.factor(expr.subs(param, upper)))},
    ]
    for point in critical_points:
        candidates.append(
            {
                "where": f"{param}={sp.sstr(point)}",
                "condition": f"{sp.sstr(lower)} <= {sp.sstr(point)} <= {sp.sstr(upper)}",
                "value": sp.sstr(sp.factor(expr.subs(param, point))),
            }
        )
    return {
        "template": "min(candidate values) <= y <= max(candidate values)",
        "derivative": sp.sstr(derivative),
        "candidates": candidates,
    }


def command_for_problem(problem: GeometryProblem) -> str:
    if problem.task == "envelope":
        return f"Envelope[{problem.equations}, param={problem.parameter}] via resultant(F,dF/dparam)"
    if problem.task == "region":
        return f"Exists[{problem.parameter} in {problem.domain.label()}, y={problem.equations.get('y')}]"
    return f"Eliminate[{problem.equations}, param={problem.parameter}]"


def split_statements(source: str) -> list[str]:
    cleaned = []
    for line in source.splitlines():
        cleaned.append(line.split("#", 1)[0])
    return [part.strip() for part in ";".join(cleaned).split(";") if part.strip()]


def parse_param_statement(statement: str) -> tuple[str, ParamDomain]:
    match = re.match(r"([a-zA-Z_]\w*)(?:\s+in\s+(.+))?$", statement.strip(), re.IGNORECASE)
    if not match:
        raise ValueError(f"invalid param statement: {statement!r}")
    parameter = match.group(1)
    domain_text = match.group(2)
    return parameter, parse_domain(domain_text)


def parse_domain(domain_text: str | None) -> ParamDomain:
    if not domain_text:
        return ParamDomain("real")
    text = domain_text.strip()
    if text in {"R", "Real", "Reals", "real", "reals", "ℝ"}:
        return ParamDomain("real")
    match = re.match(r"([\[(])\s*([^,]+)\s*,\s*([^\])\)]+)\s*([\])])$", text)
    if not match:
        raise ValueError(f"unsupported parameter domain: {domain_text!r}")
    return ParamDomain(
        "interval",
        lower=match.group(2).strip(),
        upper=match.group(3).strip(),
        lower_closed=match.group(1) == "[",
        upper_closed=match.group(4) == "]",
    )


def parse_equation(statement: str) -> tuple[str, str]:
    if "=" not in statement:
        raise ValueError(f"expected equation: {statement!r}")
    lhs, rhs = statement.split("=", 1)
    lhs = lhs.strip()
    rhs = normalize_math_text(rhs.strip())
    if not re.match(r"^[a-zA-Z_]\w*$", lhs):
        raise ValueError(f"left hand side must be a symbol, got: {lhs!r}")
    return lhs, rhs


def normalize_math_text(text: str) -> str:
    normalized = (
        text.replace("^", "**")
        .replace("＋", "+")
        .replace("−", "-")
        .replace("×", "*")
        .replace("・", "*")
    )
    normalized = re.sub(r"(?<=\d)(?=[a-zA-Z_])", "*", normalized)
    normalized = re.sub(r"(?<=[a-zA-Z_])(?=\d)", "*", normalized)
    return normalized


def make_symbols(problem: GeometryProblem) -> dict[str, Any]:
    require_sympy()
    names = {"x", "y", problem.parameter}
    for lhs, rhs in problem.equations.items():
        names.add(lhs)
        for token in re.findall(r"[a-zA-Z_]\w*", rhs):
            if token not in KNOWN_FUNCTIONS:
                names.add(token)
    symbols = {name: sp.symbols(name) for name in sorted(names)}
    for name, fn in KNOWN_FUNCTIONS.items():
        if fn is not None:
            symbols[name] = fn
    return symbols


def sympify_expr(expr: str, symbols: dict[str, Any]) -> Any:
    require_sympy()
    return sp.sympify(normalize_math_text(expr), locals=symbols)


def sympify_scalar(value: str | None) -> Any:
    require_sympy()
    if value is None:
        raise ValueError("interval domain needs both lower and upper bounds")
    text = normalize_math_text(value).replace("inf", "oo")
    return sp.sympify(text)


def is_positive(expr: Any) -> bool:
    return bool(expr.is_positive) or bool(expr.is_number and expr > 0)


def is_negative(expr: Any) -> bool:
    return bool(expr.is_negative) or bool(expr.is_number and expr < 0)


def require_sympy() -> None:
    if sp is None:
        raise RuntimeError("SymPy is not installed.")
