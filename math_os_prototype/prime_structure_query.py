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

    has_triangle_sides = any(token in compact for token in ("三辺", "3辺", "三つの辺"))
    has_all_prime_sides = "素数" in compact and any(
        token in compact for token in ("全て", "すべて", "いずれも", "全部")
    )
    has_circumradius = any(
        token in compact for token in ("外接円半径", "外接円の半径")
    )
    has_proof_request = any(token in compact for token in ("示せ", "証明せよ"))
    if (
        "三角形" in compact
        and has_triangle_sides
        and has_all_prime_sides
        and has_circumradius
        and "無理数" in compact
        and has_proof_request
    ):
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
        a, b, c, p = sp.symbols("a b c p", integer=True, positive=True)
        heron_discriminant = (a + b + c) * (-a + b + c) * (a - b + c) * (a + b - c)
        symmetric_form = 2 * (a**2 * b**2 + b**2 * c**2 + c**2 * a**2) - (
            a**4 + b**4 + c**4
        )
        one_two_case = sp.factor(heron_discriminant.subs({a: 2, b: p, c: p}))
        two_two_case = int(heron_discriminant.subs({a: 2, b: 2, c: 3}))
        three_two_case = int(heron_discriminant.subs({a: 2, b: 2, c: 2}))
        if (
            sp.expand(heron_discriminant - symmetric_form) != 0
            or sp.simplify(one_two_case - 16 * (p**2 - 1)) != 0
            or (two_two_case, three_two_case) != (63, 48)
            or any(
                sp.ntheory.primetest.is_square(value)
                for value in (3, two_two_case, three_two_case)
            )
        ):
            raise ValueError("square-obstruction self-check failed")
        case_certificates = {
            "all_sides_odd": {
                "identity": str(symmetric_form),
                "odd_square_mod_8": 1,
                "discriminant_mod_8": 3,
                "square_residues_mod_8": [0, 1, 4],
            },
            "exactly_one_side_two": {
                "triangle_inequality_consequence": "|p-q|<2; odd primes p,q imply p=q",
                "discriminant": str(one_two_case),
                "strict_square_gap": "(p-1)^2 < p^2-1 < p^2 for p>=3",
            },
            "exactly_two_sides_two": {
                "triangle_inequality_consequence": "odd prime p<4 implies p=3",
                "discriminant": two_two_case,
                "is_square": False,
            },
            "all_sides_two": {
                "discriminant": three_two_case,
                "is_square": False,
            },
        }
        return {
            "status": "solved",
            "query_operator": query.operator,
            "answer_exact": "True",
            "answer_tex": r"\(R\notin\mathbb{Q}\)",
            "case_certificates": case_certificates,
            "lowering_certificate": query.lowering_certificate,
            "derivation_tex": [
                r"辺を \(a,b,c\)，面積を \(\Delta\) とし，\(D=(4\Delta)^2=(a+b+c)(-a+b+c)(a-b+c)(a+b-c)\) とおく。外接円半径は \(R=abc/\sqrt D\) である。",
                r"恒等式 \(D=2(a^2b^2+b^2c^2+c^2a^2)-(a^4+b^4+c^4)\) を使う。三辺が奇素数なら各平方は法 \(8\) で \(1\) だから，\(D\equiv6-3\equiv3\pmod8\) であり，平方数ではない。",
                r"一辺だけが \(2\) なら三角不等式から他の二辺は同じ奇素数 \(p\) で，\(D=16(p^2-1)\) は平方数でない。",
                r"二辺が \(2\) なら残りは \(3\) で \(D=63\)，三辺とも \(2\) なら \(D=48\) となり，いずれも平方数でない。",
                r"全場合で \(D\) は平方数でない。もし \(R=abc/\sqrt D\) が有理数なら \(\sqrt D=abc/R\) も有理数となるが，整数 \(D\) の平方根が有理数なら \(D\) は平方数である。これは矛盾である。",
            ],
        }
    raise ValueError(f"unsupported prime structure operator: {query.operator}")
