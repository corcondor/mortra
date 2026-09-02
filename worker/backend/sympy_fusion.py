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


def parse_pair_map(terms):
    x, y = sp.symbols("x y")
    if not isinstance(terms, list) or not terms or len(terms) > 12:
        raise ValueError("polynomial pair map requires 1 to 12 terms")
    expression = sp.Integer(0)
    depends_on_x = False
    depends_on_y = False
    for term in terms:
        if not isinstance(term, dict):
            raise ValueError("pair-map term must be an object")
        coefficient = term.get("coefficient")
        x_power = term.get("left_power")
        y_power = term.get("right_power")
        if not isinstance(coefficient, int) or coefficient == 0 or abs(coefficient) > 12:
            raise ValueError("pair-map coefficients must be nonzero bounded integers")
        if not isinstance(x_power, int) or not isinstance(y_power, int):
            raise ValueError("pair-map powers must be integers")
        if x_power < 0 or y_power < 0 or x_power > 3 or y_power > 3:
            raise ValueError("pair-map powers exceed the bounded polynomial grammar")
        expression += coefficient * x ** x_power * y ** y_power
        depends_on_x = depends_on_x or x_power > 0
        depends_on_y = depends_on_y or y_power > 0
    expression = sp.expand(expression)
    if not depends_on_x or not depends_on_y:
        raise ValueError("pair map must depend on both parent coordinates")
    return expression


def polynomial_pair_map(left, right, map_expression):
    x, y, z = sp.symbols("x y z")
    f = left.as_expr().subs(left.gens[0], x)
    g = right.as_expr().subs(right.gens[0], y)
    first = sp.resultant(f, sp.expand(z - map_expression), x)
    second = sp.resultant(g, first, y)
    return monic_squarefree(second, z)


def polynomial_pair_map_elimination(left, right, map_expression):
    x, y, z = sp.symbols("x y z")
    f = left.as_expr().subs(left.gens[0], x)
    g = right.as_expr().subs(right.gens[0], y)
    first = sp.expand(sp.resultant(f, sp.expand(z - map_expression), x))
    second = sp.Poly(sp.expand(sp.resultant(g, first, y)), z, domain=sp.QQ).monic()
    derivative_gcd = sp.gcd(second, second.diff()).monic()
    squarefree = second.sqf_part().monic()
    return first, second, derivative_gcd, squarefree


def numeric_pair_map_check(left, right, result, map_expression):
    x, y = sp.symbols("x y")
    left_roots = [complex(root) for root in sp.nroots(left.as_expr(), maxsteps=300)]
    right_roots = [complex(root) for root in sp.nroots(right.as_expr(), maxsteps=300)]
    result_roots = [complex(root) for root in sp.nroots(result.as_expr(), maxsteps=300)]
    evaluator = sp.lambdify((x, y), map_expression, "math")
    expected = [complex(evaluator(a, b)) for a in left_roots for b in right_roots]
    tolerance = 2e-7
    expected_is_covered = all(
        any(abs(value - root) <= tolerance * max(1.0, abs(value)) for root in result_roots)
        for value in expected
    )
    result_has_no_extra_roots = all(
        any(abs(root - value) <= tolerance * max(1.0, abs(root)) for value in expected)
        for root in result_roots
    )
    return expected_is_covered and result_has_no_extra_roots


def polynomial_pair_map_response(left, right, terms):
    map_expression = parse_pair_map(terms)
    first, elimination, derivative_gcd, result = polynomial_pair_map_elimination(
        left, right, map_expression
    )
    if not numeric_pair_map_check(left, right, result, map_expression):
        raise ValueError("independent numerical polynomial-pair-map check failed")
    left_perturbed = polynomial_pair_map(perturb(left), right, map_expression)
    right_perturbed = polynomial_pair_map(left, perturb(right), map_expression)
    if left_perturbed == result or right_perturbed == result:
        raise ValueError("parent perturbation did not change the polynomial-pair-map result")
    return {
        "left": latex_polynomial(left.monic()),
        "right": latex_polynomial(right.monic()),
        "result": latex_polynomial(result),
        "left_sympy": sp.sstr(left.monic().as_expr()),
        "right_sympy": sp.sstr(right.monic().as_expr()),
        "result_sympy": sp.sstr(result.as_expr()),
        "map": sp.latex(map_expression),
        "map_sympy": sp.sstr(map_expression),
        "map_terms": terms,
        "first_resultant": sp.latex(first),
        "elimination_result": sp.latex(elimination.as_expr(), order="lex"),
        "elimination_gcd": sp.latex(derivative_gcd.as_expr(), order="lex"),
        "degree_left": left.degree(),
        "degree_right": right.degree(),
        "degree_result": result.degree(),
        "exact": True,
        "numeric_check": True,
        "ablation": True,
    }


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
    expected_is_covered = all(
        any(abs(value - root) <= tolerance * max(1.0, abs(value)) for root in result_roots)
        for value in expected
    )
    result_has_no_extra_roots = all(
        any(abs(root - value) <= tolerance * max(1.0, abs(root)) for value in expected)
        for root in result_roots
    )
    return expected_is_covered and result_has_no_extra_roots


def perturb(polynomial):
    variable = polynomial.gens[0]
    return sp.Poly(polynomial.as_expr() + 1, variable, domain=sp.QQ)


def latex_polynomial(polynomial):
    return sp.latex(polynomial.as_expr(), order="lex")


def polynomial_invariant(polynomial, invariant):
    monic = polynomial.monic()
    degree = monic.degree()
    coefficients = monic.all_coeffs()
    if invariant == "trace":
        value = -coefficients[1]
        perturbation = monic.as_expr() + monic.gens[0] ** (degree - 1)
    elif invariant == "norm":
        value = (-1) ** degree * coefficients[-1]
        perturbation = monic.as_expr() + 1
    else:
        raise ValueError(f"unsupported invariant: {invariant}")

    roots = [complex(root) for root in sp.nroots(monic.as_expr(), maxsteps=200)]
    observed = sum(roots) if invariant == "trace" else sp.prod(roots)
    expected = complex(sp.N(value, 30))
    tolerance = 1e-7 * max(1.0, abs(expected))
    if abs(complex(observed) - expected) > tolerance:
        raise ValueError(f"independent numerical {invariant} check failed")

    return {
        "polynomial": latex_polynomial(monic),
        "polynomial_sympy": sp.sstr(monic.as_expr()),
        "degree": degree,
        "invariant": invariant,
        "value": sp.latex(value),
        "value_sympy": sp.sstr(value),
        "coefficient_formula": (
            "-a_(n-1)/a_n" if invariant == "trace" else "(-1)^n*a_0/a_n"
        ),
        "numeric_check": True,
        "exact": True,
        "ablation_polynomial_sympy": sp.sstr(sp.expand(perturbation)),
    }


def parse_rational_map(source: str):
    expression = parse_expr(source, transformations=TRANSFORMS, evaluate=True)
    symbols = sorted(expression.free_symbols, key=lambda symbol: symbol.name)
    if len(symbols) != 1:
        raise ValueError("rational map must have exactly one variable")
    variable = symbols[0]
    numerator, denominator = sp.fraction(sp.cancel(sp.together(expression)))
    numerator_polynomial = sp.Poly(numerator, variable, domain=sp.QQ)
    denominator_polynomial = sp.Poly(denominator, variable, domain=sp.QQ)
    if numerator_polynomial.degree() > 1 or denominator_polynomial.degree() > 1:
        raise ValueError("map is not fractional linear")
    a = numerator_polynomial.coeff_monomial(variable)
    b = numerator_polynomial.coeff_monomial(1)
    c = denominator_polynomial.coeff_monomial(variable)
    d = denominator_polynomial.coeff_monomial(1)
    determinant = sp.expand(a * d - b * c)
    if determinant == 0:
        raise ValueError("fractional-linear matrix is singular")
    return expression, variable, numerator_polynomial, denominator_polynomial, determinant


def rational_map_orbit(map_source: str, polynomial):
    expression, source_variable, numerator, denominator, determinant = parse_rational_map(map_source)
    x, z = sp.symbols("x z")
    orbit = polynomial.monic()
    orbit_expression = orbit.as_expr().subs(orbit.gens[0], x)
    numerator_expression = numerator.as_expr().subs(source_variable, x)
    denominator_expression = denominator.as_expr().subs(source_variable, x)
    denominator_polynomial = sp.Poly(denominator_expression, x, domain=sp.QQ)
    if sp.gcd(sp.Poly(orbit_expression, x, domain=sp.QQ), denominator_polynomial).degree() > 0:
        raise ValueError("rational map has a pole on the algebraic orbit")
    elimination = sp.resultant(
        orbit_expression,
        sp.expand(denominator_expression * z - numerator_expression),
        x,
    )
    result = monic_squarefree(elimination, z)

    orbit_roots = [complex(root) for root in sp.nroots(orbit.as_expr(), maxsteps=200)]
    expected = []
    for root in orbit_roots:
        numerator_value = complex(sp.N(numerator.as_expr().subs(source_variable, root), 30))
        denominator_value = complex(sp.N(denominator.as_expr().subs(source_variable, root), 30))
        if abs(denominator_value) <= 1e-10:
            raise ValueError("numerical pole encountered on the algebraic orbit")
        expected.append(numerator_value / denominator_value)
    observed = [complex(root) for root in sp.nroots(result.as_expr(), maxsteps=200)]
    tolerance = 1e-7
    expected_is_covered = all(
        any(abs(value - root) <= tolerance * max(1.0, abs(value)) for root in observed)
        for value in expected
    )
    result_has_no_extra_roots = all(
        any(abs(root - value) <= tolerance * max(1.0, abs(root)) for value in expected)
        for root in observed
    )
    if not expected_is_covered or not result_has_no_extra_roots:
        raise ValueError("independent numerical rational-map orbit check failed")

    return {
        "map": sp.latex(expression),
        "map_sympy": sp.sstr(expression),
        "numerator_sympy": sp.sstr(numerator.as_expr()),
        "denominator_sympy": sp.sstr(denominator.as_expr()),
        "orbit_polynomial": latex_polynomial(orbit),
        "orbit_polynomial_sympy": sp.sstr(orbit.as_expr()),
        "result": latex_polynomial(result),
        "result_sympy": sp.sstr(result.as_expr()),
        "determinant": sp.latex(determinant),
        "determinant_sympy": sp.sstr(determinant),
        "degree_orbit": orbit.degree(),
        "degree_result": result.degree(),
        "exact": True,
        "numeric_check": True,
        "map_ablation_sympy": sp.sstr(sp.cancel(expression + 1)),
    }


def main():
    request = json.load(sys.stdin)
    if request.get("request") == "invariant":
        polynomial = parse_polynomial(request["polynomial"])
        json.dump(
            polynomial_invariant(polynomial, request["invariant"]),
            sys.stdout,
            ensure_ascii=False,
        )
        return
    if request.get("request") == "rational_map_orbit":
        polynomial = parse_polynomial(request["polynomial"])
        json.dump(
            rational_map_orbit(request["map"], polynomial),
            sys.stdout,
            ensure_ascii=False,
        )
        return
    if request.get("request") == "polynomial_pair_map":
        left = parse_polynomial(request["left"])
        right = parse_polynomial(request["right"])
        json.dump(
            polynomial_pair_map_response(left, right, request["map_terms"]),
            sys.stdout,
            ensure_ascii=False,
        )
        return

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
        "left_sympy": sp.sstr(left.monic().as_expr()),
        "right_sympy": sp.sstr(right.monic().as_expr()),
        "result_sympy": sp.sstr(result.as_expr()),
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
