"""Construct witnesses for normalized inner-product constraints.

The lowering is stated in Hilbert-space terms: choose two explicit
orthonormal functions on the parsed interval, then synthesize a vector with
the requested inner product.  No source answer or problem identifier is used.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import re
from typing import Any

import sympy as sp
from sympy.parsing.latex import parse_latex

try:
    from math_os_prototype.latex_frontend import split_tex_text_math
    from math_os_prototype.typed_analysis_query import canonical_constants, canonicalize_latex_for_sympy
except ImportError:
    from latex_frontend import split_tex_text_math
    from typed_analysis_query import canonical_constants, canonicalize_latex_for_sympy


@dataclass(frozen=True)
class HilbertWitnessQuery:
    lower: str
    upper: str
    target_correlation: str
    variable: str
    lowering_certificate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_hilbert_witness_query(text: str) -> HilbertWitnessQuery | None:
    if not any(marker in text for marker in ("一組求めよ", "一組を求めよ", "find a pair")):
        return None
    _, spans = split_tex_text_math(text)
    source = next(
        (
            span.content
            for span in spans
            if span.content.count(r"\int") >= 3
            and "=" in span.content
            and "f(x)" in span.content.replace(" ", "")
            and "g(x)" in span.content.replace(" ", "")
        ),
        None,
    )
    if source is None:
        return None
    compact = source.replace(" ", "")
    if not all(token in compact for token in ("f(x)g(x)", "f(x)^2", "g(x)^2")):
        return None
    bounds = re.findall(r"\\int_\{([^{}]+)\}\^\{([^{}]+)\}", source)
    if len(bounds) < 3 or len(set(bounds)) != 1:
        return None
    lower_tex, upper_tex = bounds[0]
    try:
        lower = canonical_constants(parse_latex(canonicalize_latex_for_sympy(lower_tex)))
        upper = canonical_constants(parse_latex(canonicalize_latex_for_sympy(upper_tex)))
        target = canonical_constants(
            parse_latex(canonicalize_latex_for_sympy(source.rsplit("=", 1)[1]))
        )
    except Exception:
        return None
    length = sp.simplify(upper - lower)
    if length.free_symbols or sp.simplify(length > 0) is not sp.true:
        return None
    if target.free_symbols or target.is_real is not True:
        return None
    if sp.simplify(1 - target**2 > 0) is not sp.true:
        return None
    return HilbertWitnessQuery(
        lower=str(lower),
        upper=str(upper),
        target_correlation=str(target),
        variable="x",
        lowering_certificate={
            "kind": "normalized_inner_product_witness",
            "space": f"L2([{lower},{upper}])",
            "basis_size": 2,
            "construction": "orthonormal_pair_rotation",
            "memorized_answer": False,
        },
    )


def execute_hilbert_witness_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = HilbertWitnessQuery(**payload)
    x = sp.Symbol(query.variable, real=True)
    lower = sp.sympify(query.lower)
    upper = sp.sympify(query.upper)
    target = sp.sympify(query.target_correlation)
    length = sp.simplify(upper - lower)
    midpoint = sp.simplify((lower + upper) / 2)
    first = sp.simplify(1 / sp.sqrt(length))
    second_basis = sp.simplify(sp.sqrt(12 / length**3) * (x - midpoint))
    second = sp.simplify(target * first + sp.sqrt(1 - target**2) * second_basis)

    inner = sp.simplify(sp.integrate(first * second, (x, lower, upper)))
    first_norm = sp.simplify(sp.integrate(first**2, (x, lower, upper)))
    second_norm = sp.simplify(sp.integrate(second**2, (x, lower, upper)))
    correlation = sp.simplify(inner / sp.sqrt(first_norm * second_norm))
    if first_norm != 1 or second_norm != 1 or sp.simplify(correlation - target) != 0:
        raise ValueError("constructed Hilbert-space witness failed exact verification")

    return {
        "status": "solved",
        "query_operator": "construct_normalized_inner_product_witness",
        "answer_exact": str([first, second]),
        "answer_tex": rf"\(f(x)={sp.latex(first)},\quad g(x)={sp.latex(second)}\)",
        "target_correlation": str(target),
        "verification": {
            "first_norm_squared": str(first_norm),
            "second_norm_squared": str(second_norm),
            "inner_product": str(inner),
            "normalized_inner_product": str(correlation),
        },
        "lowering_certificate": query.lowering_certificate,
        "derivation_tex": [
            rf"区間長を \(L={sp.latex(length)}\)，中点を \(m={sp.latex(midpoint)}\) とする。",
            rf"\(e_1={sp.latex(first)}\)，\(e_2={sp.latex(second_basis)}\) は \(L^2\) 内で正規直交する。",
            rf"\(f=e_1\)，\(g={sp.latex(target)}e_1+\sqrt{{1-{sp.latex(target)}^2}}e_2\) と構成する。",
            rf"直接積分により \(\|f\|^2=\|g\|^2=1\)，\(\langle f,g\rangle={sp.latex(target)}\) を確認した。",
        ],
    }
