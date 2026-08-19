"""Typed lowering for finite progression constraints.

The relation is derived from the algebraic definition of a progression.  No
problem statement, numeric answer, or benchmark identifier is stored here.
"""

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
class ProgressionQuery:
    progression: str
    terms: list[str]
    target: str
    output_sort: str
    lowering_certificate: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def compile_progression_query(text: str) -> ProgressionQuery | None:
    lower = text.lower()
    geometric = "等比数列" in text or "geometric progression" in lower
    if not geometric or has_multiple_subproblems(text):
        return None
    _, spans = split_tex_text_math(text)
    triples: list[list[sp.Basic]] = []
    for span in spans:
        parts = split_top_level(span.content, ",")
        if len(parts) != 3:
            continue
        try:
            triples.append([canonical_constants(parse_latex(part)) for part in parts])
        except Exception:
            continue
    if len(triples) != 1:
        return None

    parsed_targets: list[sp.Basic] = []
    for span in spans:
        try:
            parsed_targets.append(canonical_constants(parse_latex(span.content)))
        except Exception:
            continue
    if not parsed_targets:
        return None
    target = parsed_targets[-1]
    terms = triples[0]
    if target not in terms:
        return None
    return ProgressionQuery(
        progression="geometric",
        terms=[str(term) for term in terms],
        target=str(target),
        output_sort="FiniteSet(Real)",
        lowering_certificate={
            "kind": "finite_progression_definition",
            "arity": 3,
            "constraint": "term_2^2 = term_1 * term_3",
            "target_is_declared_term": True,
        },
    )


def execute_progression_query(payload: dict[str, Any]) -> dict[str, Any]:
    query = ProgressionQuery(**payload)
    if query.progression != "geometric" or len(query.terms) != 3:
        raise ValueError("unsupported progression query")
    locals_map = {
        "sin": sp.sin,
        "cos": sp.cos,
        "tan": sp.tan,
        "sqrt": sp.sqrt,
        "pi": sp.pi,
        "E": sp.E,
    }
    terms = [sp.sympify(term, locals=locals_map) for term in query.terms]
    target = sp.sympify(query.target, locals=locals_map)
    relation = sp.together(terms[1] ** 2 - terms[0] * terms[2])
    answer, polynomial, interval = eliminate_single_angle(relation, target)
    return {
        "status": "solved",
        "query_operator": "solve_progression_constraint",
        "answer_exact": str(answer),
        "defining_relation": str(sp.Eq(terms[1] ** 2, terms[0] * terms[2])),
        "elimination_polynomial": str(polynomial),
        "admissible_interval": str(interval),
        "lowering_certificate": query.lowering_certificate,
        "derivation_tex": [
            "3項がこの順で等比数列をなす条件を，中項の二乗＝両端の積として書く。",
            "三角関数を \\(s=\\sin\\theta,\\ c=\\cos\\theta\\) と \\(s^2+c^2=1\\) に落とす。",
            f"補助変数を消去すると \\({sp.latex(polynomial)}=0\\) を得る。",
            f"値域 \\({sp.latex(interval)}\\) 内の解を元の等比条件へ戻し，\\({sp.latex(answer)}\\) だけが残る。",
        ],
    }


def eliminate_single_angle(relation: sp.Basic, target: sp.Basic) -> tuple[sp.Basic, sp.Basic, sp.Set]:
    trig_atoms = list(relation.atoms(sp.sin, sp.cos, sp.tan) | target.atoms(sp.sin, sp.cos, sp.tan))
    angles = {atom.args[0] for atom in trig_atoms if len(atom.args) == 1}
    if len(angles) != 1:
        raise ValueError("progression does not use one common angle")
    angle = next(iter(angles))
    s, c = sp.symbols("s c", real=True)
    replacements = {
        sp.sin(angle): s,
        sp.cos(angle): c,
        sp.tan(angle): s / c,
    }
    algebraic_relation = sp.together(relation.xreplace(replacements))
    numerator, denominator = algebraic_relation.as_numer_denom()
    target_algebraic = target.xreplace(replacements)
    if target_algebraic == c:
        target_symbol, eliminate_symbol = c, s
    elif target_algebraic == s:
        target_symbol, eliminate_symbol = s, c
    else:
        raise ValueError("only sine or cosine observations are currently eliminable")

    polynomial = reduce_even_circle_relation(numerator, eliminate_symbol, target_symbol)
    if polynomial is None:
        polynomial = sp.resultant(numerator, s**2 + c**2 - 1, eliminate_symbol)
    polynomial = sp.Poly(sp.factor(polynomial), target_symbol).sqf_part().as_expr()
    interval = sp.Interval(-1, 1)
    solution_set = sp.solveset(polynomial, target_symbol, domain=interval)
    if not isinstance(solution_set, sp.FiniteSet) or not solution_set:
        raise ValueError("elimination did not produce a finite real answer set")

    valid: list[sp.Basic] = []
    for candidate in solution_set:
        if sp.simplify(denominator.subs(target_symbol, candidate)) == 0:
            continue
        if sp.simplify(polynomial.subs(target_symbol, candidate)) == 0:
            valid.append(candidate)
    if not valid:
        raise ValueError("all elimination candidates violated source constraints")
    answer: sp.Basic = valid[0] if len(valid) == 1 else sp.FiniteSet(*valid)
    return answer, polynomial, interval


def reduce_even_circle_relation(
    expression: sp.Basic,
    eliminate_symbol: sp.Symbol,
    target_symbol: sp.Symbol,
) -> sp.Basic | None:
    polynomial = sp.Poly(sp.expand(expression), eliminate_symbol)
    if any(power[0] % 2 for power, _ in polynomial.terms()):
        return None
    reduced = sp.S.Zero
    for (power,), coefficient in polynomial.terms():
        reduced += coefficient * (1 - target_symbol**2) ** (power // 2)
    return sp.factor(reduced)


def split_top_level(text: str, delimiter: str) -> list[str]:
    parts: list[str] = []
    depth = 0
    start = 0
    pairs = {"{": "}", "(": ")", "[": "]"}
    opens = set(pairs)
    closes = set(pairs.values())
    for index, char in enumerate(text):
        if char in opens:
            depth += 1
        elif char in closes:
            depth = max(0, depth - 1)
        elif char == delimiter and depth == 0:
            parts.append(text[start:index].strip())
            start = index + 1
    parts.append(text[start:].strip())
    return parts
