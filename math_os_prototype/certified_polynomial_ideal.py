"""Ideal membership with explicit multipliers, checked without Groebner search."""

import sympy as sp
from sympy.polys import lex
from sympy.polys.distributedmodules import (
    sdm_from_vector, sdm_to_vector, sdm_groebner, sdm_nf_buchberger,
)

from math_os_prototype.holonomic_route_discovery import X, rational

SCHEMA = "mortra.polynomial-ideal-witness.v1"


def _poly(expression, variables, parameter):
    if not variables or len(set(variables)) != len(variables) or parameter in variables:
        raise ValueError("distinct polynomial variables and parameter required")
    expression = sp.sympify(expression)
    if expression.has(sp.Float):
        raise ValueError("exact coefficients required")
    return sp.Poly(expression, *variables, domain=sp.QQ.frac_field(parameter))


def encode(expression, variables, parameter=X):
    rows = []
    for powers, coefficient in _poly(expression, variables, parameter).terms():
        if coefficient == 0:
            continue
        numerator, denominator = sp.fraction(sp.cancel(coefficient))
        rows.append({"powers": list(powers), "numerator": list(map(str,
            reversed(sp.Poly(numerator, parameter, domain=sp.QQ).all_coeffs()))),
            "denominator": list(map(str,
            reversed(sp.Poly(denominator, parameter, domain=sp.QQ).all_coeffs())))})
    return rows


def decode(rows, variables, parameter=X):
    if not isinstance(rows, list) or len(rows) > 20000:
        raise ValueError("invalid witness size")
    expression, seen = sp.S.Zero, set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != {"powers", "numerator", "denominator"}:
            raise ValueError("invalid witness term")
        powers = row["powers"]
        if (not isinstance(powers, list) or len(powers) != len(variables)
                or any(type(p) is not int or not 0 <= p <= 512 for p in powers)
                or tuple(powers) in seen):
            raise ValueError("invalid monomial")
        seen.add(tuple(powers))
        coefficients = []
        for name in ("numerator", "denominator"):
            values = row[name]
            if not isinstance(values, list) or not 1 <= len(values) <= 512:
                raise ValueError("invalid rational-function coefficient")
            coefficients.append(sum((rational(v)*parameter**i for i, v in enumerate(values)), sp.S.Zero))
        numerator, denominator = coefficients
        if denominator == 0:
            raise ValueError("zero witness denominator")
        expression += numerator/denominator*sp.prod(v**p for v, p in zip(variables, powers))
    return _poly(expression, variables, parameter).as_expr()


def verify_witness(certificate, equations, target, variables, parameter=X):
    """Check a polynomial identity only; the equations need separate proofs."""
    try:
        if set(certificate) != {"schema", "equations", "target", "multipliers"}:
            return False
        if certificate["schema"] != SCHEMA:
            return False
        if certificate["equations"] != [encode(p, variables, parameter) for p in equations]:
            return False
        if certificate["target"] != encode(target, variables, parameter):
            return False
        if len(certificate["multipliers"]) != len(equations):
            return False
        multipliers = [decode(q, variables, parameter) for q in certificate["multipliers"]]
        residual = target-sum((q*p for q, p in zip(multipliers, equations)), sp.S.Zero)
        return _poly(residual, variables, parameter).is_zero
    except (KeyError, TypeError, ValueError, ZeroDivisionError, sp.PolynomialError, sp.CoercionFailed):
        return False


class PolynomialIdeal:
    def __init__(self, equations, variables, parameter=X):
        self.variables, self.parameter = tuple(variables), parameter
        self.equations = [_poly(p, variables, parameter).as_expr() for p in equations]
        self.field = sp.QQ.frac_field(parameter)
        self.basis, self.transition = [], []
        if not equations:
            return
        generators = [sdm_from_vector([p], lex, self.field, gens=self.variables) for p in self.equations]
        basis, transition = sdm_groebner(generators, sdm_nf_buchberger, lex, self.field, extended=True)
        self.basis = [sdm_to_vector(p, self.variables, self.field, n=1)[0] for p in basis]
        self.transition = [sdm_to_vector(p, self.variables, self.field, n=len(equations)) for p in transition]
        for p, row in zip(self.basis, self.transition):
            residual = p-sum((a*b for a, b in zip(row, self.equations)), sp.S.Zero)
            if not _poly(residual, variables, parameter).is_zero:
                raise ValueError("basis transition does not reproduce its original equations")

    def witness(self, target):
        target = _poly(target, self.variables, self.parameter).as_expr()
        if self.basis:
            quotients, remainder = sp.reduced(target, self.basis, *self.variables, domain=self.field)
        else:
            quotients, remainder = [], target
        if remainder != 0:
            return None
        multipliers = [sp.cancel(sum((q*row[i] for q, row in zip(quotients, self.transition)), sp.S.Zero))
                       for i in range(len(self.equations))]
        certificate = {"schema": SCHEMA,
            "equations": [encode(p, self.variables, self.parameter) for p in self.equations],
            "target": encode(target, self.variables, self.parameter),
            "multipliers": [encode(q, self.variables, self.parameter) for q in multipliers]}
        if not verify_witness(certificate, self.equations, target, self.variables, self.parameter):
            raise ValueError("ideal membership witness failed its independent identity check")
        return certificate
