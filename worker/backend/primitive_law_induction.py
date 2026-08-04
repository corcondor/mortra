"""CEGIS-style induction of executable laws between two algebraic parents.

The candidate language contains typed polynomial expressions, not finished
problem templates.  Candidates are deduplicated semantically, eliminated
exactly, checked numerically, and tested by perturbing either parent.
"""

import json
import sys

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


TRANSFORMS = standard_transformations + (convert_xor, implicit_multiplication_application)


def parse_polynomial(source: str, name: str):
    expression = parse_expr(source, transformations=TRANSFORMS, evaluate=True)
    symbols = sorted(expression.free_symbols, key=lambda symbol: symbol.name)
    if len(symbols) != 1:
        raise ValueError(f"{name} must contain exactly one variable")
    polynomial = sp.Poly(sp.together(expression), symbols[0], domain=sp.QQ)
    if polynomial.degree() < 1:
        raise ValueError(f"{name} must have positive degree")
    return polynomial


def candidate_expressions(max_depth: int, max_candidates: int):
    x, y = sp.symbols("x y")
    levels = [{x, y}]
    accepted = []
    seen = {sp.srepr(x), sp.srepr(y)}
    numeric_points = [(2, 3), (-2, 5), (3, -1), (5, 2)]
    signatures = set()
    for depth in range(1, max(2, max_depth + 1)):
        prior = set().union(*levels)
        generated = set()
        for left in prior:
            for right in prior:
                for expression in (left + right, left - right, left * right):
                    expression = sp.expand(expression)
                    if not expression.has(x) or not expression.has(y):
                        continue
                    if sp.Poly(expression, x, y).total_degree() > max_depth + 1:
                        continue
                    key = sp.srepr(expression)
                    if key in seen:
                        continue
                    seen.add(key)
                    signature = tuple(sp.expand(expression).subs({x: a, y: b}) for a, b in numeric_points)
                    if signature in signatures:
                        continue
                    signatures.add(signature)
                    generated.add(expression)
        if not generated:
            break
        ordered = sorted(generated, key=lambda item: (sp.count_ops(item), len(str(item)), str(item)))
        levels.append(set(ordered[: max_candidates * 4]))
        accepted.extend(ordered)
        if len(accepted) >= max_candidates * 8:
            break
    return accepted


def monic_squarefree(expression, variable):
    polynomial = sp.Poly(sp.expand(expression), variable, domain=sp.QQ)
    if polynomial.is_zero or polynomial.degree() < 1:
        raise ValueError("elimination produced no finite nonconstant observable")
    return polynomial.sqf_part().monic()


def eliminate(left, right, observable):
    x, y, z = sp.symbols("x y z")
    f = left.as_expr().subs(left.gens[0], x)
    g = right.as_expr().subs(right.gens[0], y)
    inner = sp.resultant(g, z - observable, y)
    return monic_squarefree(sp.resultant(f, inner, x), z)


def numeric_check(left, right, result, observable):
    x, y, z = sp.symbols("x y z")
    left_roots = [complex(value) for value in sp.nroots(left.as_expr(), maxsteps=200)]
    right_roots = [complex(value) for value in sp.nroots(right.as_expr(), maxsteps=200)]
    result_expression = result.as_expr().subs(result.gens[0], z)
    tolerance = 1e-6
    for a in left_roots:
        for b in right_roots:
            value = complex(observable.subs({x: a, y: b}))
            residual = abs(complex(result_expression.subs(z, value)))
            if residual > tolerance * max(1.0, abs(value)) ** max(1, result.degree()):
                return False
    return True


def perturb(polynomial, amount):
    return sp.Poly(polynomial.as_expr() + amount, polynomial.gens[0], domain=sp.QQ)


def main():
    request = json.load(sys.stdin)
    left = parse_polynomial(request["left"], "left")
    right = parse_polynomial(request["right"], "right")
    max_depth = max(1, min(int(request.get("max_depth", 3)), 4))
    max_candidates = max(1, min(int(request.get("max_candidates", 4)), 12))
    offset = max(0, int(request.get("offset", 0)))
    expressions = candidate_expressions(max_depth, max_candidates + offset + 8)
    x, y = sp.symbols("x y")
    registered_seed_laws = {
        sp.srepr(sp.expand(expression))
        for expression in (x + y, x - y, y - x, x * y)
    }
    expressions = [
        expression for expression in expressions
        if sp.srepr(sp.expand(expression)) not in registered_seed_laws
    ]
    tested = rejected_elimination = rejected_numeric = rejected_ablation = rejected_duplicate = 0
    results = []
    result_normal_forms = set()
    for observable in expressions[offset:]:
        if len(results) >= max_candidates:
            break
        tested += 1
        try:
            result = eliminate(left, right, observable)
        except Exception:
            rejected_elimination += 1
            continue
        if not numeric_check(left, right, result, observable):
            rejected_numeric += 1
            continue
        result_key = sp.srepr(result.as_expr())
        if result_key in result_normal_forms:
            rejected_duplicate += 1
            continue
        try:
            left_changed = eliminate(perturb(left, 1), right, observable)
            right_changed = eliminate(left, perturb(right, 1), observable)
        except Exception:
            rejected_ablation += 1
            continue
        if left_changed == result or right_changed == result:
            rejected_ablation += 1
            continue
        result_normal_forms.add(result_key)
        results.append({
            "expression": sp.sstr(observable),
            "expression_tex": sp.latex(observable),
            "result": sp.latex(result.as_expr(), order="lex"),
            "degree_result": result.degree(),
            "operations": int(sp.count_ops(observable)),
            "exact": True,
            "numeric_check": True,
            "left_ablation": True,
            "right_ablation": True,
        })
    json.dump({
        "left": sp.latex(left.monic().as_expr(), order="lex"),
        "right": sp.latex(right.monic().as_expr(), order="lex"),
        "candidates": results,
        "telemetry": {
            "enumerated": len(expressions),
            "tested": tested,
            "rejected_elimination": rejected_elimination,
            "rejected_numeric": rejected_numeric,
            "rejected_ablation": rejected_ablation,
            "rejected_duplicate": rejected_duplicate,
            "certified": len(results),
        },
    }, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        json.dump({"error": f"{type(error).__name__}: {error}"}, sys.stdout, ensure_ascii=False)
        sys.exit(2)
