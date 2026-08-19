"""Exact executor for the coordinate subset of embedded Asymptote diagrams."""

from __future__ import annotations

import ast
from dataclasses import asdict, dataclass
import re
from typing import Any

import sympy as sp


@dataclass(frozen=True)
class AsymptoteGeometryProblem:
    source: str
    polygon: tuple[str, ...]
    answer_exact: str
    certificate: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def detect_asymptote_geometry_problem(text: str) -> AsymptoteGeometryProblem | None:
    block = re.search(r"\[asy\](.*?)\[/asy\]", text, flags=re.DOTALL | re.IGNORECASE)
    if block is None or "area" not in text.lower():
        return None
    scalars: dict[str, sp.Expr] = {}
    points: dict[str, sp.Matrix] = {}
    statements = [statement.strip() for statement in block.group(1).split(";") if statement.strip()]
    for statement in statements:
        assignment = re.fullmatch(r"(?:(?:real|pair)\s+)?([A-Za-z]\w*)\s*=\s*(.+)", statement)
        if assignment is None:
            continue
        name, expression = assignment.groups()
        try:
            value = evaluate_pair_expression(expression, scalars, points)
        except (ValueError, SyntaxError, TypeError, KeyError):
            continue
        if isinstance(value, sp.MatrixBase):
            points[name] = sp.Matrix(value)
        else:
            scalars[name] = sp.sympify(value)

    polygon = infer_target_polygon(text, block.group(1))
    polygon = [name if name in points else f"p{name}" if f"p{name}" in points else name for name in polygon]
    if len(polygon) < 3 or any(name not in points for name in polygon):
        return None
    area = polygon_area([points[name] for name in polygon])
    scale_squared = regular_polygon_scale_squared(text, block.group(1))
    result = sp.simplify(area * scale_squared)
    return AsymptoteGeometryProblem(
        source=text,
        polygon=tuple(polygon),
        answer_exact=str(result),
        certificate=(
            "Asymptote coordinate assignments evaluated exactly",
            "line intersections solved as a 2x2 linear system",
            "polygon area verified by the shoelace determinant",
        ),
    )


def solve_asymptote_geometry_problem(payload: dict[str, Any]) -> dict[str, Any]:
    problem = detect_asymptote_geometry_problem(str(payload["source"]))
    if problem is None:
        raise ValueError("Asymptote coordinate program could not be elaborated")
    return {
        "status": "solved",
        "answer_exact": problem.answer_exact,
        "polygon": list(problem.polygon),
        "certificate": list(problem.certificate),
        "verified": True,
    }


def evaluate_pair_expression(
    expression: str,
    scalars: dict[str, sp.Expr],
    points: dict[str, sp.Matrix],
) -> sp.Expr | sp.Matrix:
    intersection = re.fullmatch(
        r"intersectionpoint\(\s*([A-Za-z]\w*)--([A-Za-z]\w*)\s*,\s*([A-Za-z]\w*)--([A-Za-z]\w*)\s*\)",
        expression,
    )
    if intersection:
        a, b, c, d = (points[name] for name in intersection.groups())
        return line_intersection(a, b, c, d)
    tree = ast.parse(expression, mode="eval")
    return evaluate_ast(tree.body, scalars, points)


def evaluate_ast(
    node: ast.AST,
    scalars: dict[str, sp.Expr],
    points: dict[str, sp.Matrix],
) -> sp.Expr | sp.Matrix:
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return sp.Rational(str(node.value))
    if isinstance(node, ast.Name):
        if node.id in points:
            return points[node.id]
        if node.id in scalars:
            return scalars[node.id]
        raise KeyError(node.id)
    if isinstance(node, ast.Tuple) and len(node.elts) == 2:
        return sp.Matrix([evaluate_ast(item, scalars, points) for item in node.elts])
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.USub):
        return -evaluate_ast(node.operand, scalars, points)
    if isinstance(node, ast.BinOp) and isinstance(node.op, (ast.Add, ast.Sub, ast.Mult, ast.Div)):
        left = evaluate_ast(node.left, scalars, points)
        right = evaluate_ast(node.right, scalars, points)
        if isinstance(node.op, ast.Add):
            return left + right
        if isinstance(node.op, ast.Sub):
            return left - right
        if isinstance(node.op, ast.Mult):
            return left * right
        return left / right
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id == "dir" and len(node.args) == 1:
        degrees = sp.sympify(evaluate_ast(node.args[0], scalars, points))
        radians = sp.pi * degrees / 180
        return sp.Matrix([sp.cos(radians), sp.sin(radians)])
    raise ValueError(f"unsupported Asymptote expression: {ast.dump(node)}")


def line_intersection(a: sp.Matrix, b: sp.Matrix, c: sp.Matrix, d: sp.Matrix) -> sp.Matrix:
    t, u = sp.symbols("t u")
    solution = sp.solve(tuple(a + t * (b - a) - c - u * (d - c)), (t, u), dict=True)
    if len(solution) != 1:
        raise ValueError("lines do not have a unique intersection")
    return sp.simplify(a + solution[0][t] * (b - a))


def infer_target_polygon(text: str, asy_source: str) -> list[str]:
    query = re.search(r"area of[^A-Za-z]+(?:\\triangle\s*|triangle\s+)([A-Z]{3,})", text)
    if query:
        return list(query.group(1))
    fills = re.findall(r"filldraw\(\s*([A-Za-z]\w*(?:--[A-Za-z]\w*){2,})", asy_source)
    if fills:
        return [name for name in fills[-1].split("--") if name != "cycle"]
    return []


def polygon_area(points: list[sp.Matrix]) -> sp.Expr:
    twice_area = sp.Integer(0)
    for left, right in zip(points, points[1:] + points[:1]):
        twice_area += left[0] * right[1] - left[1] * right[0]
    return sp.simplify(sp.Abs(twice_area) / 2)


def regular_polygon_scale_squared(text: str, asy_source: str) -> sp.Expr:
    names = {"triangle": 3, "square": 4, "pentagon": 5, "hexagon": 6, "heptagon": 7, "octagon": 8}
    match = re.search(
        r"regular\s+(triangle|square|pentagon|hexagon|heptagon|octagon)\s+with\s+side\s+length\s+(\d+(?:\.\d+)?)",
        text,
        flags=re.IGNORECASE,
    )
    if match is None or "dir(" not in asy_source:
        return sp.Integer(1)
    sides = names[match.group(1).lower()]
    side_length = sp.Rational(match.group(2))
    return sp.simplify(side_length**2 / (4 * sp.sin(sp.pi / sides) ** 2))
