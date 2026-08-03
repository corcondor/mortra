import json
import re
import sys

import sympy as sp
from sympy.parsing.sympy_parser import (
    convert_xor,
    implicit_multiplication_application,
    parse_expr,
    standard_transformations,
)


TRANSFORMS = standard_transformations + (convert_xor, implicit_multiplication_application)


def parse_polynomial(source: str):
    expression = parse_expr(source, transformations=TRANSFORMS, evaluate=True)
    symbols = sorted(expression.free_symbols, key=lambda symbol: symbol.name)
    if not symbols:
        raise ValueError("polynomial has no variable")
    variable = symbols[0]
    if len(symbols) != 1:
        raise ValueError("polynomial must be univariate after elaboration")
    polynomial = sp.Poly(sp.together(expression), variable, domain=sp.QQ)
    if polynomial.degree() < 1:
        raise ValueError("polynomial degree must be positive")
    return polynomial


def monic_squarefree(expression, variable):
    polynomial = sp.Poly(sp.expand(expression), variable, domain=sp.QQ)
    squarefree = polynomial.sqf_part()
    return squarefree.monic()


def root_composition(left, right, operation):
    x, z = sp.symbols("x z")
    f = left.as_expr().subs(left.gens[0], x)
    g = right.as_expr()
    y = right.gens[0]
    if operation == "sum":
        transformed = g.subs(y, z - x)
    elif operation == "difference":
        transformed = g.subs(y, x - z)
    elif operation == "product":
        transformed = sp.expand(x ** right.degree() * g.subs(y, z / x))
    else:
        raise ValueError(f"unsupported operation: {operation}")
    return monic_squarefree(sp.resultant(f, transformed, x), z)


def numeric_check(left, right, result, operation):
    left_roots = [complex(root) for root in sp.nroots(left.as_expr(), maxsteps=200)]
    right_roots = [complex(root) for root in sp.nroots(right.as_expr(), maxsteps=200)]
    result_roots = [complex(root) for root in sp.nroots(result.as_expr(), maxsteps=200)]
    if operation == "sum":
        expected = [a + b for a in left_roots for b in right_roots]
    elif operation == "difference":
        expected = [a - b for a in left_roots for b in right_roots]
    else:
        expected = [a * b for a in left_roots for b in right_roots]
    tolerance = 1e-7
    return all(any(abs(value - root) <= tolerance * max(1.0, abs(value)) for root in result_roots) for value in expected)


def perturb(polynomial):
    variable = polynomial.gens[0]
    return sp.Poly(polynomial.as_expr() + 1, variable, domain=sp.QQ)


def latex_polynomial(polynomial):
    return sp.latex(polynomial.as_expr(), order="lex")


def main():
    request = json.load(sys.stdin)
    left = parse_polynomial(request["left"])
    right = parse_polynomial(request["right"])
    operation = request["operation"]
    result = root_composition(left, right, operation)
    if not numeric_check(left, right, result, operation):
        raise ValueError("independent numerical root check failed")
    left_perturbed = root_composition(perturb(left), right, operation)
    right_perturbed = root_composition(left, perturb(right), operation)
    ablation = left_perturbed != result and right_perturbed != result
    if not ablation:
        raise ValueError("parent perturbation did not change the construction")
    response = {
        "left": latex_polynomial(left.monic()),
        "right": latex_polynomial(right.monic()),
        "result": latex_polynomial(result),
        "degree_left": left.degree(),
        "degree_right": right.degree(),
        "degree_result": result.degree(),
        "operation": operation,
        "exact": True,
        "numeric_check": True,
        "ablation": True,
    }
    json.dump(response, sys.stdout, ensure_ascii=False)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        json.dump({"error": f"{type(error).__name__}: {error}"}, sys.stdout, ensure_ascii=False)
        sys.exit(2)
