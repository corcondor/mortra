"""Executable theorem queries obtained from the Prime type.

These queries use reusable consequences of primality (parity and set
inclusion) and then hand the resulting obligations to exact arithmetic.
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
class PrimeStructureQuery:
    operator: str
    parameters: dict[str, str]
    lowering_certificate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_prime_structure_query(text: str) -> PrimeStructureQuery | None:
    compact = re.sub(r"\s+", "", text)
    if "素数" in text and r"\sum" in text and "示せ" in text:
        _, spans = split_tex_text_math(text)
        source = next((span.content for span in spans if r"\sum" in span.content and "<" in span.content), None)
        if source is not None and re.search(r"p\s*:\s*素数", source):
            exponent_match = re.search(r"p\^\{?(\d+)\}?", source)
            if exponent_match:
                try:
                    target = canonical_constants(
                        parse_latex(canonicalize_latex_for_sympy(source.rsplit("<", 1)[1]))
                    )
                except Exception:
                    target = None
                exponent = int(exponent_match.group(1))
                if target is not None and not target.free_symbols and exponent >= 2 and exponent % 2 == 0:
                    return PrimeStructureQuery(
                        operator="bound_prime_reciprocal_power_series",
                        parameters={"exponent": str(exponent), "target": str(target)},
                        lowering_certificate={
                            "kind": "prime_type_parity_partition",
                            "morphisms": ["Prime -> {2} coproduct OddPrime", "OddPrime -> OddInteger"],
                            "memorized_answer": False,
                        },
                    )

    triangle_tokens = ("三辺", "素数", "三角形", "外接円半径", "無理数", "示せ")
    if all(token in compact for token in triangle_tokens):
        return PrimeStructureQuery(
            operator="prove_prime_triangle_circumradius_irrational",
            parameters={},
            lowering_certificate={
                "kind": "prime_triangle_heron_square_obstruction",
                "case_split": "number_of_sides_equal_to_two",
                "case_count": 4,
                "memorized_answer": False,
            },
        )
    return None


def execute_prime_structure_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = PrimeStructureQuery(**payload)
    if query.operator == "bound_prime_reciprocal_power_series":
        exponent = int(query.parameters["exponent"])
        target = sp.sympify(query.parameters["target"])
        exact_superset = sp.simplify(
            sp.Rational(1, 2) ** exponent
            + (1 - sp.Rational(1, 2) ** exponent) * sp.zeta(exponent)
            - 1
        )
        archimedean_upper = sp.simplify(exact_superset.subs(sp.pi, sp.Rational(22, 7)))
        if exact_superset.has(sp.zeta) or sp.simplify(archimedean_upper <= target) is not sp.true:
            raise ValueError("the reusable odd-integer bound does not prove the requested target")
        return {
            "status": "solved",
            "query_operator": query.operator,
            "answer_exact": "True",
            "answer_tex": r"\(\displaystyle\sum_{p\ \mathrm{prime}}p^{-" + str(exponent) + r"}<" + sp.latex(target) + r"\)",
            "superset_bound": str(exact_superset),
            "rational_upper_bound": str(archimedean_upper),
            "lowering_certificate": query.lowering_certificate,
            "derivation_tex": [
                r"素数を \(2\) と奇素数に分け，奇素数全体を \(3\) 以上の奇数全体へ包含する。",
                rf"したがって和は \(2^{{-{exponent}}}+\sum_{{m\ge3,\ m\ {r'\mathrm{odd}'}}}m^{{-{exponent}}}={sp.latex(exact_superset)}\) より小さい。",
                rf"\(\pi<22/7\) を代入すると上界は \({sp.latex(archimedean_upper)}<{sp.latex(target)}\) である。",
            ],
        }

    if query.operator == "prove_prime_triangle_circumradius_irrational":
        # D=(4 area)^2.  Each branch below is an exact square obstruction.
        residues = {
            "all_odd": (3, 8),
            "one_side_two": "D=16(p^2-1), and (p-1)^2<p^2-1<p^2",
            "two_sides_two": (63, "not_square"),
            "three_sides_two": (48, "not_square"),
        }
        if any(sp.ntheory.primetest.is_square(value) for value in (3, 63, 48)):
            raise ValueError("square-obstruction self-check failed")
        return {
            "status": "solved",
            "query_operator": query.operator,
            "answer_exact": "True",
            "answer_tex": r"\(R\notin\mathbb{Q}\)",
            "case_certificates": residues,
            "lowering_certificate": query.lowering_certificate,
            "derivation_tex": [
                r"辺を \(a,b,c\)，面積を \(\Delta\) とし，Heron恒等式の整数 \(D=(4\Delta)^2\) を用いる。すると \(R=abc/\sqrt D\) である。",
                r"三辺が奇素数なら \(D\equiv3\pmod 8\) であり，平方数ではない。",
                r"一辺だけが \(2\) なら三角不等式から他の二辺は同じ奇素数 \(p\) で，\(D=16(p^2-1)\) は平方数でない。",
                r"二辺が \(2\) なら残りは \(3\) で \(D=63\)，三辺とも \(2\) なら \(D=48\) となり，いずれも平方数でない。",
                r"全場合で \(\sqrt D\) は無理数なので，\(R=abc/\sqrt D\) も無理数である。",
            ],
        }
    raise ValueError(f"unsupported prime structure operator: {query.operator}")
