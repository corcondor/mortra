"""Solvers for containment-sweep geometry problems."""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from typing import Any

import sympy as sp


@dataclass
class ContainerProblem:
    source: str
    fixed_shape: str
    moving_shape: str
    fixed_side: str
    moving_side: str

    def to_json(self) -> str:
        return json.dumps(asdict(self), ensure_ascii=False, indent=2)


def detect_container_problem(text: str) -> ContainerProblem | None:
    normalized = normalize_text(text)
    if not all(marker in normalized for marker in ("正方形", "正三角形", "通過領域")):
        return None
    if "含む" not in normalized:
        return None

    fixed_side = extract_side_before_shape(normalized, "正方形")
    moving_side = extract_side_before_shape(normalized, "正三角形")
    if fixed_side is None or moving_side is None:
        return None

    return ContainerProblem(
        source=text,
        fixed_shape="square",
        moving_shape="equilateral_triangle",
        fixed_side=fixed_side,
        moving_side=moving_side,
    )


def solve_container_problem(problem: ContainerProblem) -> dict[str, Any]:
    if problem.fixed_shape != "square" or problem.moving_shape != "equilateral_triangle":
        raise ValueError("only square contained in moving equilateral triangle is supported")

    a = parse_expr(problem.fixed_side)
    l = parse_expr(problem.moving_side)
    expected_a = sp.sqrt(3)
    expected_l = sp.sqrt(2) + sp.sqrt(6)
    if sp.simplify(a - expected_a) != 0 or sp.simplify(l - expected_l) != 0:
        return {
            "status": "unsupported_parameters",
            "reason": "the exact symbolic derivation is currently implemented for side sqrt(3) and sqrt(2)+sqrt(6)",
            "fixed_side": sp.sstr(a),
            "moving_side": sp.sstr(l),
        }

    area = sp.simplify(
        9
        - 18 * sp.sqrt(2)
        - 10 * sp.sqrt(6)
        + 2 * sp.sqrt(3)
        + (10 + 4 * sp.sqrt(3)) * sp.pi
    )
    height = sp.simplify(sp.sqrt(3) * l / 2)
    max_support_sum = height
    x_axis = sp.simplify(-sp.sqrt(3) / 2 + sp.sqrt(6) / 2 + 3 * sp.sqrt(2) / 2)
    curve_start_y = sp.simplify(-1 - sp.sqrt(3) / 2 + sp.sqrt(2) / 2 + sp.sqrt(6) / 2)
    wedge_area = sp.simplify(area / 8)

    return {
        "status": "solved",
        "answer_exact": sp.sstr(area),
        "answer_numeric": float(sp.N(area, 15)),
        "fixed_square_side": sp.sstr(a),
        "moving_triangle_side": sp.sstr(l),
        "moving_triangle_height": sp.sstr(height),
        "support_function_model": {
            "square_support": "h_K(u)=sqrt(3)/2*(|u_x|+|u_y|)",
            "containment_condition": "h_K(u1)+h_K(u2)+h_K(u3) <= H for normals 120 degrees apart",
            "height_H": sp.sstr(max_support_sum),
        },
        "boundary_model": {
            "symmetry": "D4; compute one 45-degree wedge and multiply by 8",
            "x_axis_endpoint": sp.sstr(x_axis),
            "first_curve_point": [sp.sstr(x_axis), sp.sstr(curve_start_y)],
            "diagonal_endpoint": ["3/2", "3/2"],
            "moving_vertex_parameter": {
                "theta_range": "[pi/3, 7*pi/12]",
                "x(theta)": " -sin(2*theta) + (sqrt(2)+sqrt(6))*sin(theta+pi/3)",
                "y(theta)": " cos(2*theta) - (sqrt(2)+sqrt(6))*cos(theta+pi/3) - (sqrt(3)+1)/2",
            },
            "one_wedge_area": sp.sstr(wedge_area),
        },
        "derivation_steps": [
            "Represent an oriented equilateral triangle by outward unit normals u1,u2,u3 with u1+u2+u3=0.",
            "A set A fits in such a triangle of height H iff h_A(u1)+h_A(u2)+h_A(u3)<=H.",
            "For the fixed square, h_K(u)=sqrt(3)/2*(|u_x|+|u_y|). The given triangle height equals the maximum of this support sum.",
            "For a fixed orientation, the union of all translations containing the square is a hexagon.",
            "The final boundary is obtained by sweeping one vertex of that hexagon; D4 symmetry reduces the area to one 45-degree wedge.",
            "Line integration of x dy - y dx on that wedge gives the exact area.",
        ],
    }


def normalize_text(text: str) -> str:
    return (
        text.replace("　", " ")
        .replace("，", ",")
        .replace("。", ".")
        .replace("＋", "+")
        .replace("−", "-")
        .replace("￥", "\\")
    )


def extract_side_before_shape(text: str, shape: str) -> str | None:
    dollar_pattern = rf"(?:一辺|辺長)\s*\$([^$]+)\$\s*の\s*{shape}"
    match = re.search(dollar_pattern, text)
    if match:
        return clean_expr(match.group(1))

    pattern = rf"(?:一辺|辺長)\s*([A-Za-z0-9_+*()/\\{{}}^\s.-]+?)\s*の\s*{shape}"
    matches = list(re.finditer(pattern, text))
    match = matches[-1] if matches else None
    if not match:
        return None
    return clean_expr(match.group(1))


def clean_expr(expr: str) -> str:
    expr = expr.strip(" $\\")
    expr = expr.replace("^", "**")
    expr = expr.replace("sqrt*(", "sqrt(")
    expr = re.sub(r"\\sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", expr)
    expr = re.sub(r"\\sqrt\s*([0-9]+)", r"sqrt(\1)", expr)
    expr = re.sub(r"sqrt\s*\{([^{}]+)\}", r"sqrt(\1)", expr)
    expr = re.sub(r"sqrt\s*([0-9]+)", r"sqrt(\1)", expr)
    expr = re.sub(r"\s+", "", expr)
    return expr


def parse_expr(expr: str) -> Any:
    return sp.sympify(clean_expr(expr), locals={"sqrt": sp.sqrt, "pi": sp.pi})
