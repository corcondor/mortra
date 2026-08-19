"""Small typed formal language for MathOS.

The goal is not to solve problems here. This module compiles TeX-centered
Japanese math text into a fully parenthesized core form and generates a
standard Japanese paraphrase so users can inspect the interpretation.
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

try:
    import sympy as sp
except ImportError:  # pragma: no cover
    sp = None

try:
    from math_os_prototype.structural_parser import StructuralIR, analyze_structure
except ImportError:
    from structural_parser import StructuralIR, analyze_structure


@dataclass
class FormalIR:
    source_text: str
    status: str
    sexpr: str
    standard_japanese: str
    declarations: list[dict[str, str]]
    metas: list[dict[str, str]]
    assumptions: list[str]
    goal: str
    ambiguities: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


TYPE_PRIORITY = {
    "prime": "Prime",
    "positive_integer": "PositiveInteger",
    "nonnegative_integer": "NonnegativeInteger",
    "integer": "Integer",
    "real": "Real",
    "complex": "Complex",
}


def compile_formal_ir(text: str) -> FormalIR:
    structure = analyze_structure(text)
    declarations = infer_declarations(structure)
    assumptions = [safe_relation_to_sexpr(relation) for relation in structure.relations]
    ambiguities = detect_ambiguities(structure)
    warnings: list[str] = []

    query = infer_query(text, structure, declarations)
    sexpr = build_problem_sexpr(declarations, assumptions, query)
    standard = build_standard_japanese(declarations, assumptions, query)

    if query["kind"] == "unknown":
        warnings.append("Could not infer a precise query type from the problem text.")
    status = "type_checked" if not warnings else "needs_review"
    if ambiguities:
        status = "ambiguous"

    return FormalIR(
        source_text=text,
        status=status,
        sexpr=sexpr,
        standard_japanese=standard,
        declarations=declarations,
        metas=query.get("metas", []),
        assumptions=assumptions,
        goal=query.get("goal", ""),
        ambiguities=ambiguities,
        warnings=warnings,
    )


def infer_declarations(structure: StructuralIR) -> list[dict[str, str]]:
    type_by_var = {variable: "Unknown" for variable in structure.variables}
    entity_kinds = {entity.kind for entity in structure.entities}
    operation_kinds = {operation.kind for operation in structure.operations}
    if entity_kinds & {"circle", "square", "triangle", "equilateral_triangle", "line", "curve"} or operation_kinds & {
        "locus",
        "passing_region",
        "envelope",
    }:
        for variable in ("x", "y", "X", "Y"):
            if variable in type_by_var:
                type_by_var[variable] = "Real"
    for constraint in structure.constraints:
        mapped = TYPE_PRIORITY.get(constraint.kind)
        if not mapped:
            continue
        for variable in constraint.variables:
            if variable in type_by_var:
                type_by_var[variable] = merge_type(type_by_var[variable], mapped)
    return [{"name": variable, "type": type_name} for variable, type_name in type_by_var.items()]


def merge_type(current: str, candidate: str) -> str:
    if current == "Unknown":
        return candidate
    order = ["Unknown", "Complex", "Real", "Integer", "NonnegativeInteger", "PositiveInteger", "Prime"]
    return candidate if order.index(candidate) > order.index(current) else current


def infer_query(text: str, structure: StructuralIR, declarations: list[dict[str, str]]) -> dict[str, Any]:
    normalized = structure.normalized_text
    type_by_var = {item["name"]: item["type"] for item in declarations}
    if "すべて求め" in normalized or "all solutions" in normalized.lower() or "all pairs" in normalized.lower():
        variable = choose_query_variable(normalized, declarations, structure)
        var_type = type_by_var.get(variable, "Unknown")
        condition = and_sexpr([safe_relation_to_sexpr(relation) for relation in structure.relations])
        goal = f"(forall (({variable} {var_type})) (iff (member {variable} S) {condition}))"
        return {
            "kind": "exact_set",
            "metas": [{"name": "S", "type": f"(Set {var_type})"}],
            "goal": goal,
        }

    range_variable = detect_range_variable(normalized)
    if range_variable:
        var_type = type_by_var.get(range_variable, "Unknown")
        quantified = [
            item for item in declarations if item["name"] != range_variable
        ]
        condition = and_sexpr([safe_relation_to_sexpr(relation) for relation in structure.relations])
        if quantified:
            condition = f"(exists ({format_decl_list(quantified)}) {condition})"
        goal = f"(forall (({range_variable} {var_type})) (iff (member {range_variable} S) {condition}))"
        return {
            "kind": "existence_range",
            "metas": [{"name": "S", "type": f"(Set {var_type})"}],
            "goal": goal,
        }

    condition_parameter = detect_condition_parameter(normalized, declarations)
    if condition_parameter:
        param_type = type_by_var.get(condition_parameter, "Unknown")
        quantified = [item for item in declarations if item["name"] != condition_parameter]
        condition = and_sexpr([safe_relation_to_sexpr(relation) for relation in structure.relations])
        if quantified:
            condition = f"(forall ({format_decl_list(quantified)}) {condition})"
        goal = f"(forall (({condition_parameter} {param_type})) (iff (member {condition_parameter} S) {condition}))"
        return {
            "kind": "condition_set",
            "metas": [{"name": "S", "type": f"(Set {param_type})"}],
            "goal": goal,
        }

    if "証明" in normalized or "示せ" in normalized or "prove" in normalized.lower():
        predicate_query = detect_predicate_implication(normalized, declarations)
        if predicate_query:
            return predicate_query
        target = safe_relation_to_sexpr(structure.relations[-1]) if structure.relations else "True"
        premises = [safe_relation_to_sexpr(relation) for relation in structure.relations[:-1]]
        goal_body = implication_sexpr(premises, target)
        return {
            "kind": "prove",
            "metas": [],
            "goal": wrap_forall(declarations, goal_body),
        }

    geometry_locus_area_query = detect_geometry_locus_area_query(normalized, structure, declarations)
    if geometry_locus_area_query:
        return geometry_locus_area_query

    region_query = detect_region_query(normalized, structure, declarations)
    if region_query:
        return region_query

    query_expr = detect_value_expression(structure)
    if query_expr:
        expr = expr_to_sexpr(query_expr)
        premises = [safe_relation_to_sexpr(relation) for relation in structure.relations]
        goal_body = implication_sexpr(premises, f"(= a {expr})")
        return {
            "kind": "value",
            "metas": [{"name": "a", "type": "Real"}],
            "goal": wrap_forall(declarations, goal_body),
        }

    return {"kind": "unknown", "metas": [], "goal": ""}


def build_problem_sexpr(
    declarations: list[dict[str, str]],
    assumptions: list[str],
    query: dict[str, Any],
) -> str:
    lines = ["(problem"]
    for declaration in declarations:
        lines.append(f"  (declare {declaration['name']} {declaration['type']})")
    for meta in query.get("metas", []):
        lines.append(f"  (meta {meta['name']} {meta['type']})")
    if assumptions:
        lines.append("  (assume")
        lines.append(indent(and_sexpr(assumptions), 4))
        lines.append("  )")
    if query.get("goal"):
        lines.append("  (goal")
        lines.append(indent(query["goal"], 4))
        lines.append("  )")
    lines.append(")")
    return "\n".join(lines)


def build_standard_japanese(
    declarations: list[dict[str, str]],
    assumptions: list[str],
    query: dict[str, Any],
) -> str:
    decl_text = "、".join(f"{item['name']} は {type_to_ja(item['type'])}" for item in declarations) or "変数宣言なし"
    assumption_text = " かつ ".join(assumptions) if assumptions else "追加条件なし"
    if query["kind"] == "value":
        return f"MathOSの解釈: {decl_text} とし、{assumption_text} のもとで、実数 a が目標式の値に等しくなるような a を求める。"
    if query["kind"] == "exact_set":
        return f"MathOSの解釈: {decl_text} とし、条件 {assumption_text} を満たすすべての対象の集合 S を求める。"
    if query["kind"] == "existence_range":
        return f"MathOSの解釈: {decl_text} とし、条件 {assumption_text} が成立するようなパラメータ全体の集合 S を求める。"
    if query["kind"] == "condition_set":
        return f"MathOSの解釈: {decl_text} とし、条件 {assumption_text} が全称的に成立するようなパラメータ全体の集合 S を求める。"
    if query["kind"] == "region":
        return f"MathOSの解釈: {decl_text} とし、ある媒介変数が存在して条件 {assumption_text} を満たす点全体の領域 R を求める。"
    if query["kind"] == "geometry_locus_area":
        return f"MathOSの解釈: {decl_text} とし、幾何条件 {assumption_text} から定まる重心の軌跡が囲む有界領域の面積 A を求める。"
    if query["kind"] == "prove":
        return f"MathOSの解釈: {decl_text} とし、{assumption_text} から目標命題が従うことを証明する。"
    return f"MathOSの解釈: {decl_text}。問いの型は未確定。"


def detect_value_expression(structure: StructuralIR) -> str | None:
    relation_set = set(structure.relations)
    for expression in reversed(structure.expressions):
        if expression in relation_set:
            continue
        if "," in expression and not any(op in expression for op in "+-*/^"):
            continue
        if re.fullmatch(r"[A-Za-z](?:,[A-Za-z])*", expression):
            continue
        if any(op in expression for op in ("+", "-", "*", "/", "**", "^", "sqrt", "sin", "cos", "tan", "log")):
            return expression
    return None


def detect_range_variable(text: str) -> str | None:
    if "範囲" not in text and "存在範囲" not in text:
        return None
    match = re.search(r"(?:実数|整数|正の整数|非負整数)\s+([A-Za-z])\s+の範囲", text)
    if match:
        return match.group(1)
    match = re.search(r"([A-Za-z])\s+の範囲", text)
    return match.group(1) if match else None


def detect_condition_parameter(text: str, declarations: list[dict[str, str]]) -> str | None:
    if "必要十分条件" not in text and "ための" not in text:
        return None
    match = re.search(r"ための\s*([A-Za-z])", text)
    if match:
        return match.group(1)
    match = re.search(r"実数\s+([A-Za-z])\s+について", text)
    if match:
        return match.group(1)
    if len(declarations) >= 2:
        return declarations[0]["name"]
    return None


def detect_region_query(
    text: str,
    structure: StructuralIR,
    declarations: list[dict[str, str]],
) -> dict[str, Any] | None:
    if not any(marker in text for marker in ("通過領域", "点全体の領域", "領域", "少なくとも一つ")):
        return None
    if not structure.relations:
        return None
    point_vars = [item for item in declarations if item["name"] in {"x", "y"}]
    if len(point_vars) < 2:
        return None
    parameter_decls = [
        item
        for item in declarations
        if item["name"] not in {"x", "y"} and not item["name"].startswith("C_")
    ]
    condition = and_sexpr([safe_relation_to_sexpr(relation) for relation in structure.relations])
    if parameter_decls:
        condition = f"(exists ({format_decl_list(parameter_decls)}) {condition})"
    goal = f"(forall ({format_decl_list(point_vars)}) (iff (member (point x y) R) {condition}))"
    return {
        "kind": "region",
        "metas": [{"name": "R", "type": "Region2"}],
        "goal": goal,
    }


def detect_geometry_locus_area_query(
    text: str,
    structure: StructuralIR,
    declarations: list[dict[str, str]],
) -> dict[str, Any] | None:
    operation_kinds = {operation.kind for operation in structure.operations}
    entity_kinds = {entity.kind for entity in structure.entities}
    if not ("locus" in operation_kinds and "measure" in operation_kinds):
        return None
    if "equilateral_triangle" not in entity_kinds and "重心" not in text:
        return None
    curve_assumptions = [safe_relation_to_sexpr(relation) for relation in structure.relations]
    curve_condition = and_sexpr(curve_assumptions)
    goal = (
        "(= A "
        "(area (bounded_region "
        "(locus (centroid (equilateral_triangle_on_curve curve))))))"
    )
    if curve_condition != "True":
        goal = f"(implies {curve_condition} {goal})"
    return {
        "kind": "geometry_locus_area",
        "metas": [{"name": "A", "type": "Real"}],
        "goal": goal,
    }


def detect_predicate_implication(text: str, declarations: list[dict[str, str]]) -> dict[str, Any] | None:
    if "ならば" not in text:
        return None
    if "偶数" in text:
        match = re.search(r"([A-Za-z](?:\*\*|\^)?2?)\s*が偶数ならば\s*([A-Za-z])\s*も偶数", text)
        if not match:
            return None
        premise_expr = normalize_power_shorthand(match.group(1))
        target_var = match.group(2)
        goal_body = f"(implies (even {expr_to_sexpr(premise_expr)}) (even {target_var}))"
        return {"kind": "prove", "metas": [], "goal": wrap_forall(declarations, goal_body)}
    return None


def normalize_power_shorthand(expr: str) -> str:
    match = re.fullmatch(r"([A-Za-z])2", expr)
    if match:
        return f"{match.group(1)}**2"
    return expr.replace("^", "**")


def choose_query_variable(text: str, declarations: list[dict[str, str]], structure: StructuralIR) -> str:
    match = re.search(r"(?:実数|整数|正の整数|非負整数)\s+([A-Za-z])\s+をすべて", text)
    if match:
        return match.group(1)
    if len(declarations) == 1:
        return declarations[0]["name"]
    relation_vars = []
    for relation in structure.relations:
        relation_vars.extend(re.findall(r"\b[A-Za-z]\b", relation))
    for item in declarations:
        if item["name"] in relation_vars:
            return item["name"]
    return declarations[0]["name"] if declarations else "x"


def wrap_forall(declarations: list[dict[str, str]], body: str) -> str:
    if not declarations:
        return body
    return f"(forall ({format_decl_list(declarations)}) {body})"


def format_decl_list(declarations: list[dict[str, str]]) -> str:
    return " ".join(f"({item['name']} {item['type']})" for item in declarations)


def implication_sexpr(premises: list[str], target: str) -> str:
    if not premises:
        return target
    return f"(implies {and_sexpr(premises)} {target})"


def and_sexpr(items: list[str]) -> str:
    if not items:
        return "True"
    if len(items) == 1:
        return items[0]
    return "(and " + " ".join(items) + ")"


def relation_to_sexpr(relation: str) -> str:
    for op in ("<=", ">=", "!=", "=", "<", ">"):
        if op in relation:
            lhs, rhs = relation.split(op, 1)
            mapped = {"<=": "<=", ">=": ">=", "!=": "not=", "=": "=", "<": "<", ">": ">"}[op]
            return f"({mapped} {expr_to_sexpr(lhs)} {expr_to_sexpr(rhs)})"
    return expr_to_sexpr(relation)


def safe_relation_to_sexpr(relation: str) -> str:
    try:
        return relation_to_sexpr(relation)
    except Exception:
        return normalize_atom(relation)


def expr_to_sexpr(expression: str) -> str:
    if "!" in expression:
        return factorial_to_sexpr(expression)
    if sp is None:
        return normalize_atom(expression)
    try:
        expr = sp.sympify(expression.replace("^", "**"))
    except Exception:
        return normalize_atom(expression)
    return sympy_to_sexpr(expr)


def sympy_to_sexpr(expr: Any) -> str:
    if isinstance(expr, tuple):
        return "(tuple " + " ".join(sympy_to_sexpr(item) for item in expr) + ")"
    if not hasattr(expr, "is_Symbol"):
        return normalize_atom(str(expr))
    if expr.is_Symbol:
        return str(expr)
    if expr.is_Integer:
        try:
            return str(expr)
        except ValueError:
            return f"(integer-with-bit-length {expr.p.bit_length()})"
    if expr.is_Rational:
        return f"(/ {expr.p} {expr.q})"
    if expr.is_Add:
        return "(+ " + " ".join(sympy_to_sexpr(arg) for arg in expr.args) + ")"
    if expr.is_Mul:
        return "(* " + " ".join(sympy_to_sexpr(arg) for arg in expr.args) + ")"
    if expr.is_Pow:
        base, exp = expr.args
        return f"(^ {sympy_to_sexpr(base)} {sympy_to_sexpr(exp)})"
    if expr.is_Function:
        return f"({expr.func.__name__} " + " ".join(sympy_to_sexpr(arg) for arg in expr.args) + ")"
    return str(expr)


def factorial_to_sexpr(expression: str) -> str:
    normalized = expression.replace("^", "**")
    normalized = re.sub(r"([A-Za-z0-9_()]+)!", r"(factorial \1)", normalized)
    if "-" in normalized and not normalized.startswith("-"):
        lhs, rhs = normalized.split("-", 1)
        return f"(- {normalize_atom(lhs)} {normalize_atom(rhs)})"
    if "+" in normalized:
        lhs, rhs = normalized.split("+", 1)
        return f"(+ {normalize_atom(lhs)} {normalize_atom(rhs)})"
    return normalize_atom(normalized)


def detect_ambiguities(structure: StructuralIR) -> list[str]:
    ambiguities: list[str] = []
    text = structure.normalized_text
    if "log" in text and "底" not in text and "base" not in text.lower():
        ambiguities.append("log の底が明示されていません。")
    if "囲まれる領域" in text and "有界" not in text and "どの" not in text:
        ambiguities.append("囲まれる領域の連結成分が複数あり得ます。")
    if any(item["type"] == "Unknown" for item in infer_declarations(structure)):
        ambiguities.append("型が確定していない変数があります。")
    return ambiguities


def type_to_ja(type_name: str) -> str:
    return {
        "Real": "実数",
        "Integer": "整数",
        "PositiveInteger": "正の整数",
        "NonnegativeInteger": "非負整数",
        "Prime": "素数",
        "Complex": "複素数",
        "Unknown": "型未確定の対象",
    }.get(type_name, type_name)


def normalize_atom(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip())


def indent(text: str, spaces: int) -> str:
    prefix = " " * spaces
    return "\n".join(prefix + line for line in text.splitlines())
