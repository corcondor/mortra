"""Exact convergence analysis for self-similar scalar iteration expressions."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

import sympy as sp
from sympy.parsing.latex import parse_latex

try:
    from math_os_prototype.latex_frontend import split_tex_text_math
    from math_os_prototype.typed_analysis_query import canonical_constants, has_multiple_subproblems
except ImportError:
    from latex_frontend import split_tex_text_math
    from typed_analysis_query import canonical_constants, has_multiple_subproblems


@dataclass(frozen=True)
class IterationQuery:
    operator: str
    base: str
    coefficient: str
    seed: str
    lowering_certificate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_iteration_query(text: str) -> IterationQuery | None:
    if has_multiple_subproblems(text) or not any(marker in text for marker in (r"\cdots", r"\ldots", "…")):
        return None
    lower = text.lower()
    if not any(marker in lower for marker in ("値を求め", "evaluate", "value")):
        return None
    _, spans = split_tex_text_math(text)
    candidates: list[tuple[sp.Basic, sp.Basic]] = []
    for span in spans:
        match = re.search(
            r"\\sqrt\s*\{\s*(?P<base>[^{}\s^]+)\s*\^\{\s*(?P<coefficient>.*?)\\sqrt",
            span.content,
            flags=re.DOTALL,
        )
        if not match:
            continue
        repeated = re.findall(
            rf"{re.escape(match.group('base'))}\s*\^\{{\s*{re.escape(match.group('coefficient').strip())}",
            span.content,
        )
        if len(repeated) < 2:
            continue
        try:
            base = canonical_constants(parse_latex(match.group("base").strip()))
            coefficient = canonical_constants(parse_latex(match.group("coefficient").strip()))
        except Exception:
            continue
        if base.free_symbols or coefficient.free_symbols:
            continue
        candidates.append((base, coefficient))
    if len(candidates) != 1:
        return None
    base, coefficient = candidates[0]
    return IterationQuery(
        operator="nested_square_root_power",
        base=str(base),
        coefficient=str(coefficient),
        seed="1",
        lowering_certificate={
            "kind": "self_similar_scalar_iteration",
            "recurrence": "x_(n+1) = sqrt(base**(coefficient*x_n))",
            "repeated_layer_count_min": 2,
            "complete_observation": True,
        },
    )


def execute_iteration_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = IterationQuery(**payload)
    if query.operator != "nested_square_root_power":
        raise ValueError("unsupported iteration query")
    base = sp.sympify(query.base, locals={"E": sp.E, "pi": sp.pi})
    coefficient = sp.sympify(query.coefficient, locals={"E": sp.E, "pi": sp.pi})
    seed = sp.sympify(query.seed)
    if sp.simplify(base > 1) is not sp.true or sp.simplify(coefficient > 0) is not sp.true:
        raise ValueError("convergence theorem requires base > 1 and coefficient > 0")
    rate = sp.simplify(coefficient * sp.log(base) / 2)
    threshold_test = sp.simplify(rate > 1 / sp.E)
    if threshold_test is not sp.true:
        raise ValueError("the current exact theorem does not determine this convergence regime")

    x = sp.symbols("x", positive=True)
    log_ratio = sp.simplify(rate * x - sp.log(x))
    minimizer = sp.simplify(1 / rate)
    minimum = sp.simplify(log_ratio.subs(x, minimizer))
    if sp.simplify(minimum > 0) is not sp.true:
        raise ValueError("failed to prove the iteration map lies above the diagonal")
    return {
        "status": "solved",
        "query_operator": "iteration_convergence",
        "answer_exact": "oo",
        "iteration_map": str(sp.exp(rate * x)),
        "seed": str(seed),
        "rate": str(rate),
        "fixed_point_threshold": "1/E",
        "log_ratio_minimizer": str(minimizer),
        "log_ratio_minimum": str(minimum),
        "lowering_certificate": query.lowering_certificate,
        "derivation_tex": [
            f"有限段を \\(x_0={sp.latex(seed)}\\), \\(x_{{n+1}}=\\exp({sp.latex(rate)}x_n)\\) と表す。",
            f"\\(\\log(F(x)/x)={sp.latex(log_ratio)}\\) は \\(x={sp.latex(minimizer)}\\) で最小となる。",
            f"その最小値は \\({sp.latex(minimum)}>0\\) なので，すべての \\(x>0\\) で \\(F(x)>x\\) である。",
            "反復列は単調増加する。有限極限を持てば固定点になるが固定点は存在しないため，無限大へ発散する。",
        ],
    }
