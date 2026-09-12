"""Uniform formal-series proofs over positive rational parameter domains.

Closure is computed over a rational-function coefficient field by SymPy.
Polynomial annihilators extend across removable parameter singularities because
the source series coefficients are regular on the declared positive domain.
Coefficient uniqueness is checked uniformly, not by parameter sampling.
"""
from copy import deepcopy

import sympy as sp
from sympy.holonomic import DifferentialOperators, HolonomicFunction

from math_os_prototype.holonomic_route_discovery import X, N, right_remainder
from math_os_prototype.holonomic_parametric_learning import (
    names, symbolic, instantiate,
)
from math_os_prototype.holonomic_route_discovery import validate
from math_os_prototype.holonomic_relation_reuse import digest

SCHEMA = "mortra.uniform-parameter-ode.v1"


def uniform_bound(coeffs, parameters, max_initial=16):
    """A sufficient polynomial positivity certificate for all n >= B."""
    terms = [(j, power[0], value) for j, c in enumerate(coeffs)
             for power, value in sp.Poly(c, X).terms() if value != 0]
    if not terms:
        raise ValueError("zero operator")
    shift = min(k-j for j, k, _ in terms)
    leading = sp.expand(sum(value*sp.prod(N-i for i in range(j))
                            for j, k, value in terms if k-j == shift))
    m = sp.Symbol("m", nonnegative=True)
    for bound in range(max(0, -shift), max_initial+1):
        translated = sp.Poly(leading.subs(N, m+bound), m, *parameters, domain=sp.QQ)
        values = translated.coeffs()
        if translated.is_zero or not (all(c > 0 for c in values) or all(c < 0 for c in values)):
            continue
        # m may be zero, whereas all parameters are strictly positive.
        if not any(powers[0] == 0 for powers, _ in translated.terms()):
            continue
        return {"coefficient_shift": shift, "leading_polynomial": str(leading),
                "required_initial_coefficients": bound,
                "shifted_polynomial": str(translated.as_expr()),
                "reason": "all nonzero coefficients have one sign; a term independent of m survives at m=0"}
    raise ValueError("no uniform nonvanishing certificate within initial-coefficient budget")


class ParameterSeries:
    def __init__(self, template):
        if not isinstance(template, dict) or set(template) != {"left", "right"}:
            raise ValueError("invalid relation template")
        self.symbols = {v: sp.Symbol(v, positive=True) for v in sorted(names(template))}
        if not 1 <= len(self.symbols) <= 3:
            raise ValueError("parameter budget is one to three")
        for p in template.values():
            validate(instantiate(p, {v: 1 for v in self.symbols}))
            self.check(p)
        self.parameters = tuple(self.symbols.values())
        self.ring, self.d = DifferentialOperators(
            sp.QQ.frac_field(*self.parameters).old_poly_ring(X), "D")

    def scalar(self, value):
        return symbolic(value, self.symbols)

    def polynomial(self, values):
        return sum((self.scalar(c)*X**i for i, c in enumerate(values)), sp.S.Zero)

    def check(self, p, depth=0):
        if depth > 8:
            raise ValueError("parameter proof depth budget exceeded")
        op = p["op"]
        if op == "hyper":
            if any(self.scalar(v).is_positive is not True for v in p["a"]+p["b"]):
                raise ValueError("uniform hypergeometric coefficients require positive parameters")
        elif op in {"mul", "add"}:
            self.check(p["left"], depth+1)
            self.check(p["right"], depth+1)
        elif op in {"diff", "scale", "pullback"}:
            self.check(p["child"], depth+1)
            if op == "pullback":
                num, den = self.polynomial(p["numerator"]), self.polynomial(p["denominator"])
                if num.subs(X, 0) != 0 or den.subs(X, 0).is_zero is not False:
                    raise ValueError("substitution is not uniformly defined at zero")

    def coefficients(self, p, size):
        if size == 0:
            return ()
        op = p["op"]
        if op == "hyper":
            a, b = [self.scalar(v) for v in p["a"]], [self.scalar(v) for v in p["b"]]
            out = [sp.S.One]
            for n in range(size-1):
                out.append(sp.cancel(out[-1]*sp.prod(n+v for v in a)/((n+1)*sp.prod(n+v for v in b))))
            return tuple(out)
        if op == "poly":
            return tuple(self.scalar(p["coefficients"][i]) if i < len(p["coefficients"])
                         else sp.S.Zero for i in range(size))
        if op == "diff":
            child = self.coefficients(p["child"], size+1)
            return tuple((i+1)*child[i+1] for i in range(size))
        if op == "scale":
            return tuple(self.scalar(p["factor"])*v for v in self.coefficients(p["child"], size))
        if op in {"mul", "add"}:
            a, b = self.coefficients(p["left"], size), self.coefficients(p["right"], size)
            if op == "add":
                return tuple(sp.cancel(u+v) for u, v in zip(a, b))
            return tuple(sp.cancel(sum(a[j]*b[i-j] for j in range(i+1))) for i in range(size))
        phi = sp.series(self.polynomial(p["numerator"])/self.polynomial(p["denominator"]),
                        X, 0, size).removeO()
        out, power = sp.S.Zero, sp.S.One
        for c in self.coefficients(p["child"], size):
            out += c*power
            power = sp.Poly(sp.expand(power*phi), X)
            power = sum(v*X**monomial[0] for monomial, v in power.terms() if monomial[0] < size)
        return tuple(sp.cancel(sp.expand(out).coeff(X, i)) for i in range(size))

    def operator_coefficients(self, h):
        base = h.annihilator.parent.base
        out = [base.to_sympy(c) for c in h.annihilator.listofpoly]
        denominator = sp.lcm([sp.denom(sp.cancel(c)) for c in out])
        out = [sp.expand(sp.cancel(c*denominator)) for c in out]
        while len(out) > 1 and out[-1] == 0:
            out.pop()
        if not any(out):
            raise ValueError("zero operator")
        if len(out) > 9:
            raise ValueError("parameter operator order budget exceeded")
        # Only remove rational content; keep all parameter factors for the guard.
        all_coeffs = [v for c in out for v in sp.Poly(c, X, *self.parameters, domain=sp.QQ).coeffs()]
        content = sp.gcd_list(all_coeffs)
        return tuple(sp.expand(c/content) for c in out)

    def from_coeffs(self, values):
        return HolonomicFunction(sum((c*self.d**i for i, c in enumerate(values)), 0*self.d), X)

    def annihilator(self, p):
        op, d = p["op"], self.d
        if op == "hyper":
            theta = X*d
            left, right = theta, 1+0*d
            for b in p["b"]:
                left *= theta+self.scalar(b)-1
            for a in p["a"]:
                right *= theta+self.scalar(a)
            h = HolonomicFunction(left-X*right, X)
        elif op == "poly":
            f = self.polynomial(p["coefficients"])
            h = self.from_coeffs((1,)) if f == 0 else self.from_coeffs((-sp.diff(f, X), f))
        elif op in {"mul", "add"}:
            a, b = self.annihilator(p["left"]), self.annihilator(p["right"])
            h = a*b if op == "mul" else a+b
        elif op == "diff":
            h = self.annihilator(p["child"]).diff()
        elif op == "scale":
            h = self.annihilator(p["child"])
        else:
            h = self.annihilator(p["child"]).composition(
                self.polynomial(p["numerator"])/self.polynomial(p["denominator"]))
        return self.from_coeffs(self.operator_coefficients(h))


def certify_parameter_ode(template):
    series = ParameterSeries(template)
    # Cheap exact refutation before symbolic closure, never an acceptance test.
    for i, (a, b) in enumerate(zip(series.coefficients(template["left"], 4),
                                  series.coefficients(template["right"], 4))):
        if sp.cancel(a-b) != 0:
            return {"status": "not_a_symbolic_identity", "first_mismatch": i,
                    "residual": str(sp.cancel(a-b))}
    l, r = series.annihilator(template["left"]), series.annihilator(template["right"])
    lc, rc = series.operator_coefficients(l), series.operator_coefficients(r)
    common = series.operator_coefficients(l+r)
    if any(right_remainder(common, lc)) or any(right_remainder(common, rc)):
        raise ValueError("parameter common operator failed right-division replay")
    bound = uniform_bound(common, series.parameters)
    count = bound["required_initial_coefficients"]
    a, b = series.coefficients(template["left"], count), series.coefficients(template["right"], count)
    if any(sp.cancel(u-v) != 0 for u, v in zip(a, b)):
        return {"status": "not_a_symbolic_identity", "diagnostic": "required initial coefficients differ"}
    result = {"schema": SCHEMA, "status": "exact_parametric_coefficient_identity",
              "template": deepcopy(template),
              "guards": {v: "positive rational" for v in series.symbols},
              "left_operator": list(map(str, lc)), "right_operator": list(map(str, rc)),
              "common_operator": list(map(str, common)), "uniqueness": bound,
              "initial_coefficients": [str(sp.cancel(v)) for v in a],
              "proof": "polynomial annihilator and uniform coefficient induction on positive parameters",
              "scope": "Q[[x]] at zero; no endpoint or special-value claim", "backend": sp.__version__}
    result["sha256"] = digest(result)
    return result
