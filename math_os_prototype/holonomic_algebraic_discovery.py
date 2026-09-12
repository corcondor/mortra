"""Guess polynomial relations, prove them, then isolate specialized values.

No target identity, special constant, or known-function table is used here.
The finite coefficient fit is explicitly not a proof. SymPy holonomic closure,
exact linear algebra and polynomial factor/root counting are trusted backends.
"""

from copy import deepcopy
from hashlib import sha256

import sympy as sp
from sympy.polys.matrices import DomainMatrix

from math_os_prototype.holonomic_route_discovery import (
    X, annihilator, coefficients, convolution, function_from_operator, key,
    operator_coefficients, rational, right_remainder, uniqueness_bound, validate,
)
from math_os_prototype.holonomic_certified_evaluation import replay_evaluation

Y = sp.Symbol("y")
SCHEMA = "mortra.holonomic-algebraic-relation.v1"
VALUE_SCHEMA = "mortra.certified-algebraic-value.v1"


def primitive(poly):
    result = poly.clear_denoms(convert=True)[1].primitive()[1]
    return -result if result.LC() < 0 else result


def encode_polynomial(poly):
    p = primitive(sp.Poly(poly, X, Y, domain=sp.QQ))
    return [[i, j, str(c)] for (i, j), c in p.terms()]


def decode_polynomial(terms):
    if not isinstance(terms, list) or not 1 <= len(terms) <= 256:
        raise ValueError("invalid polynomial support")
    expression = sp.S.Zero
    seen = set()
    for term in terms:
        if not isinstance(term, list) or len(term) != 3:
            raise ValueError("invalid polynomial term")
        i, j, c = term
        if type(i) is not int or type(j) is not int or not 0 <= i <= 32 or not 0 <= j <= 8:
            raise ValueError("polynomial degree budget exceeded")
        if (i, j) in seen:
            raise ValueError("duplicate polynomial term")
        seen.add((i, j))
        expression += rational(c)*X**i*Y**j
    poly = sp.Poly(expression, X, Y, domain=sp.QQ)
    if poly.is_zero or poly.degree(Y) < 1:
        raise ValueError("relation must be nonzero and depend on the function")
    return poly


def _powers(program, size, degree):
    base = coefficients(program, size)
    result = [(sp.S.One,)+(sp.S.Zero,)*(size-1)]
    for _ in range(degree):
        result.append(convolution(result[-1], base, size))
    return result


def residual_coefficients(program, terms, size):
    poly = decode_polynomial(terms)
    powers = _powers(program, size, poly.degree(Y))
    return tuple(sum((c*powers[j][n-i] for (i, j), c in poly.terms() if i <= n), sp.S.Zero)
                 for n in range(size))


def guess_relations(program, degree_x=6, degree_y=6, holdout=16):
    validate(program)
    if (type(degree_x) is not int or type(degree_y) is not int
            or not 0 <= degree_x <= 12 or not 1 <= degree_y <= 8
            or type(holdout) is not int or not 1 <= holdout <= 64):
        raise ValueError("invalid guessing budget")
    support = [(i, j) for j in range(degree_y+1) for i in range(degree_x+1)]
    training = max(16, 2*len(support))
    size = training+holdout
    if size > 384:
        raise ValueError("coefficient budget exceeded")
    powers = _powers(program, size, degree_y)
    matrix = DomainMatrix.from_Matrix(sp.Matrix([
        [powers[j][n-i] if n >= i else sp.S.Zero for i, j in support]
        for n in range(training)])).to_field()
    nullspace = matrix.nullspace().to_Matrix()
    candidates, seen, rejected = [], set(), []
    for row in nullspace.tolist():
        expression = sum((c*X**i*Y**j for c, (i, j) in zip(row, support)), sp.S.Zero)
        poly = primitive(sp.Poly(expression, X, Y, domain=sp.QQ))
        # Multiples are not independent discoveries. Keep the factors that fit.
        for factor, multiplicity in poly.factor_list()[1]:
            if factor.degree(Y) < 1:
                continue
            terms = encode_polynomial(factor)
            if key(terms) in seen:
                continue
            seen.add(key(terms))
            residual = residual_coefficients(program, terms, size)
            first = next((n for n, c in enumerate(residual) if c != 0), None)
            if first is not None:
                rejected.append({"polynomial": terms, "first_coefficient_mismatch": first})
                continue
            candidates.append({"polynomial": terms, "status": "finite_coefficient_fit_only",
                               "degree_x": factor.degree(X), "degree_y": factor.degree(Y),
                               "term_count": len(terms),
                               "coefficient_height_bits": max(abs(int(c)).bit_length() for _, _, c in terms)})
    candidates.sort(key=lambda c: (c["term_count"], c["coefficient_height_bits"], c["degree_y"],
                                   c["degree_x"], key(c["polynomial"])))
    return {"training_coefficients": training, "heldout_coefficients": holdout,
            "max_degree_x": degree_x, "max_degree_y": degree_y, "support": support,
            "nullity": nullspace.rows, "program_prefix": list(map(str, coefficients(program, size))),
            "candidates": candidates, "rejected_factors": rejected,
            "infinite_identity_proved": False}


def _term_programs(program, poly):
    powers = [{"op": "poly", "coefficients": [1]}, deepcopy(program)]
    for _ in range(2, poly.degree(Y)+1):
        powers.append({"op": "mul", "left": powers[-1], "right": deepcopy(program)})
    result = []
    for degree in range(poly.degree(Y)+1):
        q = sp.Poly(poly.as_expr().coeff(Y, degree), X, domain=sp.QQ)
        if q.is_zero:
            continue
        weight = {"op": "poly", "coefficients": [str(q.nth(i)) for i in range(q.degree()+1)]}
        term = weight if degree == 0 else {"op": "mul", "left": weight, "right": powers[degree]}
        validate(term)
        result.append(term)
    return result


def certify_relation(program, terms, max_initial=128, max_order=32):
    validate(program)
    if (type(max_initial) is not int or not 1 <= max_initial <= 384
            or type(max_order) is not int or not 1 <= max_order <= 64):
        raise ValueError("invalid proof budget")
    poly = primitive(decode_polynomial(terms))
    components = _term_programs(program, poly)
    operators, common = [], None
    for term in components:
        operator = operator_coefficients(annihilator(term))
        if len(operator)-1 > max_order:
            return {"status": "operator_order_budget"}
        operators.append(operator)
        common = operator if common is None else operator_coefficients(
            function_from_operator(common)+function_from_operator(operator))
        if len(common)-1 > max_order:
            return {"status": "operator_order_budget"}
    if any(any(right_remainder(common, op)) for op in operators):
        raise ValueError("polynomial residual operator failed right-multiple check")
    bound = uniqueness_bound(common)
    count = bound["required_initial_coefficients"]
    if count > max_initial:
        return {"status": "initial_coefficient_budget", "bound": bound}
    initial = residual_coefficients(program, encode_polynomial(poly), count) if count else ()
    first = next((i for i, c in enumerate(initial) if c != 0), None)
    if first is not None:
        return {"status": "refuted", "first_coefficient_mismatch": first, "value": str(initial[first])}
    cert = {"schema": SCHEMA, "status": "exact_formal_algebraic_relation", "program": deepcopy(program),
            "polynomial": encode_polynomial(poly), "component_programs": components,
            "component_operators": [list(map(str, op)) for op in operators],
            "common_operator": list(map(str, common)), "uniqueness": bound,
            "initial_residual_coefficients": list(map(str, initial)),
            "max_initial": max_initial, "max_order": max_order,
            "trusted_backend": {"name": "SymPy holonomic closure and exact arithmetic", "version": sp.__version__},
            "scope": "P(x,F(x))=0 in Q[[x]]; analytic extension only on a separately certified connected domain",
            "novelty_established": False}
    cert["sha256"] = sha256(key(cert).encode()).hexdigest()
    return cert


def replay_relation(cert):
    try:
        return cert == certify_relation(cert["program"], cert["polynomial"], cert["max_initial"], cert["max_order"])
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        return False


def certify_algebraic_value(relation, evaluation):
    if not replay_relation(relation) or not replay_evaluation(evaluation):
        raise ValueError("unverified relation or numerical enclosure")
    if relation["program"] != evaluation["program"]:
        raise ValueError("function mismatch between relation and enclosure")
    point = rational(evaluation["point"])
    poly = sp.Poly(decode_polynomial(relation["polynomial"]).as_expr().subs(X, point), Y, domain=sp.QQ)
    if poly.is_zero or poly.degree() < 1:
        return {"status": "degenerate_specialization"}
    poly = primitive(poly.sqf_part())
    lower, upper = rational(evaluation["lower"]), rational(evaluation["upper"])
    count = int(poly.count_roots(lower, upper))
    if count != 1:
        return {"status": "root_not_isolated", "root_count": count}
    factors = [primitive(f) for f, _ in poly.factor_list()[1] if f.count_roots(lower, upper) == 1]
    if len(factors) != 1:
        raise ValueError("irreducible factor selection failed")
    minimal = factors[0]
    cert = {"schema": VALUE_SCHEMA, "status": "exact_real_algebraic_value",
            "relation_sha256": relation["sha256"], "evaluation_sha256": evaluation["sha256"],
            "point": str(point), "specialized_polynomial_descending": list(map(str, poly.all_coeffs())),
            "minimal_polynomial_descending": list(map(str, minimal.all_coeffs())),
            "isolating_interval": [str(lower), str(upper)], "roots_in_interval": count,
            "degree": minimal.degree(),
            "rational_value": str(-minimal.nth(0)/minimal.nth(1)) if minimal.degree() == 1 else None,
            "proof": "analytic identity on certified disk, exact specialization, factorization and real root count",
            "trusted_backend": {"name": "SymPy exact polynomial factorization and real root counting", "version": sp.__version__},
            "new_identity_claimed": False}
    cert["sha256"] = sha256(key(cert).encode()).hexdigest()
    return cert


def replay_algebraic_value(cert, relation, evaluation):
    try:
        return cert == certify_algebraic_value(relation, evaluation)
    except (KeyError, ValueError, TypeError, ZeroDivisionError):
        return False
