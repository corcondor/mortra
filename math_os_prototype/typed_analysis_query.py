"""Typed, problem-independent lowering for exact analysis queries.

The compiler only accepts source constructs whose complete observation is
present in the input.  It deliberately rejects multi-part statements so that
solving one visible formula can never be reported as solving the whole task.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

import sympy as sp
from sympy.core.relational import Relational
from sympy.parsing.latex import parse_latex

try:
    from math_os_prototype.latex_frontend import split_tex_text_math
except ImportError:
    from latex_frontend import split_tex_text_math


@dataclass(frozen=True)
class TypedAnalysisQuery:
    operator: str
    source_latex: str
    output_sort: str
    lowering_certificate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_typed_analysis_query(text: str) -> TypedAnalysisQuery | None:
    if has_multiple_subproblems(text):
        return None
    _, spans = split_tex_text_math(text)
    parsed_items: list[tuple[str, sp.Basic]] = []
    for span in spans:
        try:
            parsed_items.append((span.content, canonical_constants(parse_latex(span.content))))
        except Exception:
            continue

    operations = [
        (source, expression)
        for source, expression in parsed_items
        if isinstance(expression, (sp.Limit, sp.Integral))
    ]
    if len(operations) == 1:
        source, expression = operations[0]
        operator = "limit" if isinstance(expression, sp.Limit) else "integral"
        lower = text.lower()
        query_markers = {
            "limit": ("極限", "limit", "求めよ", "evaluate", "compute"),
            "integral": ("積分", "integral", "求めよ", "evaluate", "compute"),
        }[operator]
        if not any(marker in lower for marker in query_markers):
            return None
        return TypedAnalysisQuery(
            operator=operator,
            source_latex=source,
            output_sort="ExtendedReal" if operator == "limit" else "Expression",
            lowering_certificate={
                "kind": "latex_calculus_ast",
                "operator": operator,
                "complete_query_count": 1,
                "multipart_rejected": True,
            },
        )

    proof_requested = any(marker in text.lower() for marker in ("示せ", "証明", "prove", "show that"))
    relations: list[tuple[str, Relational]] = []
    for span in spans:
        relation = parse_latex_relation(span.content)
        if relation is not None:
            relations.append((span.content, relation))
    if proof_requested and len(relations) == 1:
        source, relation = relations[0]
        if relation.free_symbols:
            return None
        return TypedAnalysisQuery(
            operator="decide_closed_proposition",
            source_latex=source,
            output_sort="Bool",
            lowering_certificate={
                "kind": "closed_symbolic_proposition",
                "free_symbol_count": 0,
                "complete_query_count": 1,
                "multipart_rejected": True,
            },
        )
    return None


def execute_typed_analysis_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = TypedAnalysisQuery(**payload)
    expression = canonical_constants(parse_latex(query.source_latex))
    if query.operator in {"limit", "integral"}:
        expected_type = sp.Limit if query.operator == "limit" else sp.Integral
        if not isinstance(expression, expected_type):
            raise ValueError(f"source did not reparse as {query.operator}")
        integrand = expression.args[0]
        bound_variables = (
            {expression.args[1]}
            if query.operator == "limit"
            else {limit[0] for limit in expression.limits}
        )
        if not bound_variables or not bound_variables <= integrand.free_symbols:
            raise ValueError("bound variable dependency was lost during LaTeX lowering")
        unresolved_parameters = integrand.free_symbols - bound_variables
        if unresolved_parameters:
            raise ValueError(
                "calculus target contains unresolved parameters: "
                + ", ".join(sorted(str(item) for item in unresolved_parameters))
            )
        result = sp.simplify(expression.doit())
        if result.has(sp.Limit, sp.Integral, sp.Sum, sp.Derivative):
            raise ValueError("exact backend left an unevaluated operation")
        if result in {sp.nan, sp.zoo}:
            raise ValueError("calculus query produced an indeterminate result")
        return {
            "status": "solved",
            "query_operator": query.operator,
            "answer_exact": str(result),
            "source_expression": str(expression),
            "lowering_certificate": query.lowering_certificate,
            "derivation_tex": [
                "LaTeX の演算子・束縛変数・極限点または積分区間を構文木から読み取る。",
                f"構文木に対して厳密演算 \\(\\mathrm{{{query.operator}}}\\) を適用する。",
                "未評価の極限・積分・和・微分が残っていないことを検査する。",
            ],
        }

    if query.operator == "decide_closed_proposition":
        expression = parse_latex_relation(query.source_latex)
        if not isinstance(expression, Relational) or expression.free_symbols:
            raise ValueError("proposition is not closed")
        decision = sp.simplify(expression)
        if decision not in {sp.true, sp.false}:
            raise ValueError("exact symbolic decision did not close the proposition")
        difference = sp.simplify(expression.lhs - expression.rhs)
        if difference.has(sp.Limit, sp.Integral, sp.Sum, sp.Derivative):
            raise ValueError("proposition decision retained an unevaluated operator")
        derivation, proof_certificate = build_closed_proposition_derivation(expression, difference)
        return {
            "status": "solved",
            "query_operator": query.operator,
            "answer_exact": str(bool(decision)),
            "answer_tex": (
                rf"\({sp.latex(expression)}\)"
                if decision is sp.true
                else rf"\(\neg\left({sp.latex(expression)}\right)\)"
            ),
            "relation": str(expression),
            "normalized_difference": str(difference),
            "proof_certificate": proof_certificate,
            "lowering_certificate": query.lowering_certificate,
            "derivation_tex": derivation,
        }
    raise ValueError(f"unsupported typed analysis operator: {query.operator}")


def canonical_constants(expression: sp.Basic) -> sp.Basic:
    replacements = {
        symbol: constant
        for symbol, constant in ((sp.Symbol("e"), sp.E), (sp.Symbol("pi"), sp.pi))
        if symbol in expression.free_symbols
    }
    return expression.xreplace(replacements) if replacements else expression


def parse_latex_relation(source: str) -> Relational | None:
    operators = (
        (r"\leq", sp.Le),
        (r"\le", sp.Le),
        ("<=", sp.Le),
        (r"\geq", sp.Ge),
        (r"\ge", sp.Ge),
        (">=", sp.Ge),
        ("<", sp.Lt),
        (">", sp.Gt),
        ("=", sp.Eq),
    )
    for token, constructor in operators:
        parts = source.split(token)
        if len(parts) != 2 or not all(part.strip() for part in parts):
            continue
        try:
            left = canonical_constants(parse_latex(canonicalize_latex_for_sympy(parts[0])))
            right = canonical_constants(parse_latex(canonicalize_latex_for_sympy(parts[1])))
        except Exception:
            return None
        return constructor(left, right, evaluate=False)
    return None


def canonicalize_latex_for_sympy(source: str) -> str:
    """Add braces required by SymPy without changing the mathematical term."""
    normalized = source.strip()
    previous = None
    while normalized != previous:
        previous = normalized
        normalized = re.sub(
            r"\\sqrt\s*([A-Za-z0-9])",
            lambda match: rf"\sqrt{{{match.group(1)}}}",
            normalized,
        )
    return normalized


def build_closed_proposition_derivation(
    relation: Relational,
    difference: sp.Basic,
) -> tuple[list[str], dict[str, Any]]:
    if isinstance(relation, sp.StrictLessThan) and relation.rhs == sp.E and isinstance(relation.lhs, sp.Pow):
        base, exponent = relation.lhs.args
        if base.is_Rational and base > 1 and sp.simplify(exponent > 0) is sp.true:
            ratio = sp.simplify((base - 1) / (base + 1))
            for degree in range(0, 32):
                partial = 2 * sum(
                    ratio ** (2 * index + 1) / (2 * index + 1)
                    for index in range(degree + 1)
                )
                tail = sp.simplify(
                    2
                    * ratio ** (2 * degree + 3)
                    / ((2 * degree + 3) * (1 - ratio**2))
                )
                upper = sp.simplify(partial + tail)
                if sp.simplify(exponent * upper < 1) is not sp.true:
                    continue
                return (
                    [
                        "両辺が正なので対数を取り，指数と対数の積を評価する。",
                        f"\\(y=({sp.latex(base)}-1)/({sp.latex(base)}+1)={sp.latex(ratio)}\\) とおくと，"
                        " \\(\\log a=2\\sum_{k\\ge0}y^{2k+1}/(2k+1)\\) である。",
                        f"第 \\({degree + 1}\\) 項までと等比級数による剰余評価から "
                        f"\\(\\log {sp.latex(base)}<{sp.latex(upper)}\\) を得る。",
                        f"\\({sp.latex(exponent)}\\cdot {sp.latex(upper)}<1\\) なので，"
                        f"\\({sp.latex(exponent)}\\log {sp.latex(base)}<1\\)。",
                        f"指数関数の単調性より \\({sp.latex(relation.lhs)}<e\\) である。",
                    ],
                    {
                        "kind": "atanh_log_series_upper_bound",
                        "base": str(base),
                        "exponent": str(exponent),
                        "degree": degree,
                        "log_upper_bound": str(upper),
                        "verified_product_bound": str(sp.simplify(exponent * upper < 1)),
                    },
                )
    return (
        [
            "命題中に自由変数がないことを型検査する。",
            f"両辺の差を \\({sp.latex(difference)}\\) に厳密正規化する。",
            "記号的な符号判定で不等号の真偽を確定する。",
        ],
        {"kind": "exact_symbolic_sign", "normalized_difference": str(difference)},
    )


def has_multiple_subproblems(text: str) -> bool:
    markers = re.findall(r"\\item(?:\[[^\]]*\])?|(?<![A-Za-z0-9])\(\s*\d+\s*\)|（\s*\d+\s*）", text)
    return len(markers) >= 2
