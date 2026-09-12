"""Goal-free series-route comparison, with exact formal-series certificates.

SymPy supplies holonomic closure algorithms. Rational coefficient arithmetic,
right-multiple checks and the coefficient-uniqueness bound are replayed here.
No special-value, modularity, novelty or global-continuation claim is made.
"""

from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
import json

import sympy as sp
from sympy.holonomic import DifferentialOperators, HolonomicFunction

X, N = sp.symbols("x n")
RING, D = DifferentialOperators(sp.QQ.old_poly_ring(X), "D")
SCHEMA = "mortra.holonomic-route-equality.v1"


def key(program):
    return json.dumps(program, sort_keys=True, separators=(",", ":"))


def rational(value):
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        raise ValueError("rational inputs must be integer or fraction strings")
    import re
    if not re.fullmatch(r"[+-]?\d+(?:/[1-9]\d*)?", str(value)):
        raise ValueError("not an exact rational")
    return sp.Rational(value)


def polynomial(values):
    if not values:
        raise ValueError("empty polynomial")
    return sum((rational(c)*X**i for i, c in enumerate(values)), sp.S.Zero)


def validate(p, depth=0):
    if depth > 20 or not isinstance(p, dict):
        raise ValueError("invalid or excessively nested program")
    op = p.get("op")
    fields = {"hyper": {"op", "a", "b"}, "poly": {"op", "coefficients"},
              "ode": {"op", "operator", "initial"},
              "diff": {"op", "child"}, "mul": {"op", "left", "right"},
              "add": {"op", "left", "right"},
              "pullback": {"op", "child", "numerator", "denominator"},
              "scale": {"op", "child", "factor"}}
    if op not in fields or set(p) != fields[op]:
        raise ValueError("unknown operation or fields")
    if op == "ode":
        from math_os_prototype.holonomic_ode_source import source_data
        source_data(key(p))
    elif op == "hyper":
        a, b = [rational(v) for v in p["a"]], [rational(v) for v in p["b"]]
        if not a or len(a) > 5 or len(a) > len(b)+1 or len(b) > 4:
            raise ValueError("unsupported hypergeometric order/convergence")
        if any(v <= 0 for v in b):
            raise ValueError("denominator parameters must be positive")
    elif op == "poly":
        polynomial(p["coefficients"])
    elif op in ("mul", "add"):
        validate(p["left"], depth+1)
        validate(p["right"], depth+1)
    else:
        validate(p["child"], depth+1)
        if op == "scale":
            if rational(p["factor"]) == 0:
                raise ValueError("zero scaling is excluded")
        elif op == "pullback":
            num, den = polynomial(p["numerator"]), polynomial(p["denominator"])
            if num == 0 or num.subs(X, 0) != 0 or den.subs(X, 0) == 0:
                raise ValueError("pullback must be nonconstant and analytic with value zero")


def convolution(a, b, size):
    return tuple(sum((a[j]*b[i-j] for j in range(i+1)), sp.S.Zero)
                 for i in range(size))


def coefficients(p, size):
    validate(p)
    return _validated_coefficients(p, size)


def _validated_coefficients(p, size):
    # The public entry validates the entire tree, including every ODE source.
    # Retain the per-call size check: differentiation requests an extra term.
    if not isinstance(size, int) or not 0 <= size <= 512:
        raise ValueError("coefficient budget exceeded")
    return _coefficients(key(p), size)


@lru_cache(maxsize=2048)
def _coefficients(serialized, size):
    if size == 0:
        return ()
    p = json.loads(serialized)
    op = p["op"]
    if op == "ode":
        from math_os_prototype.holonomic_ode_source import source_coefficients
        return source_coefficients(serialized, size)
    if op == "hyper":
        a, b = [rational(v) for v in p["a"]], [rational(v) for v in p["b"]]
        out = [sp.S.One]
        for n in range(size-1):
            out.append(out[-1]*sp.prod(n+v for v in a)/((n+1)*sp.prod(n+v for v in b)))
        return tuple(out)
    if op == "poly":
        return tuple(rational(p["coefficients"][i]) if i < len(p["coefficients"])
                     else sp.S.Zero for i in range(size))
    if op == "diff":
        child = _validated_coefficients(p["child"], size+1)
        return tuple((i+1)*child[i+1] for i in range(size))
    if op == "scale":
        return tuple(rational(p["factor"])*v for v in _validated_coefficients(p["child"], size))
    if op == "mul":
        return convolution(_validated_coefficients(p["left"], size), _validated_coefficients(p["right"], size), size)
    if op == "add":
        return tuple(a+b for a, b in zip(_validated_coefficients(p["left"], size), _validated_coefficients(p["right"], size)))
    num = _validated_coefficients({"op": "poly", "coefficients": p["numerator"]}, size)
    den = _validated_coefficients({"op": "poly", "coefficients": p["denominator"]}, size)
    phi = []
    for i in range(size):
        phi.append((num[i]-sum((den[j]*phi[i-j] for j in range(1, i+1)), sp.S.Zero))/den[0])
    out = [sp.S.Zero]*size
    power = (sp.S.One,)+(sp.S.Zero,)*(size-1)
    for value in _validated_coefficients(p["child"], size):
        out = [u+value*v for u, v in zip(out, power)]
        power = convolution(power, phi, size)
    return tuple(out)


def operator_coefficients(h):
    base = h.annihilator.parent.base
    out = [base.to_sympy(c) if isinstance(c, base.dtype) else sp.sympify(c)
           for c in h.annihilator.listofpoly]
    while len(out) > 1 and out[-1] == 0:
        out.pop()
    if all(c == 0 for c in out):
        raise ValueError("zero operator cannot certify an identity")
    divisor = sp.Poly(sp.gcd_list(out), X, domain=sp.QQ).monic().as_expr()
    out = [sp.cancel(c/divisor) for c in out]
    leading = sp.Poly(out[-1], X, domain=sp.QQ).LC()
    return tuple(sp.expand(c/leading) for c in out)


def function_from_operator(coeffs):
    operator = sum((c*D**i for i, c in enumerate(coeffs)), 0*D)
    return HolonomicFunction(operator, X)


def annihilator(p):
    validate(p)
    return function_from_operator(_annihilator(key(p)))


@lru_cache(maxsize=1024)
def _annihilator(serialized):
    p = json.loads(serialized)
    op = p["op"]
    if op == "ode":
        from math_os_prototype.holonomic_ode_source import source_data
        h = function_from_operator(source_data(serialized)[0])
    elif op == "hyper":
        theta = X*D
        lhs = theta
        for b in p["b"]:
            lhs *= theta+rational(b)-1
        rhs = 1+0*D
        for a in p["a"]:
            rhs *= theta+rational(a)
        h = HolonomicFunction(lhs-X*rhs, X)
    elif op == "poly":
        f = polynomial(p["coefficients"])
        h = function_from_operator((1,)) if f == 0 else function_from_operator((-sp.diff(f, X), f))
    elif op == "mul":
        h = annihilator(p["left"])*annihilator(p["right"])
    elif op == "add":
        h = annihilator(p["left"])+annihilator(p["right"])
    elif op == "diff":
        h = annihilator(p["child"]).diff()
    elif op == "scale":
        h = annihilator(p["child"])
    else:
        # SymPy 1.14 composition mutates coefficient storage; use a fresh child.
        h = annihilator(p["child"]).composition(polynomial(p["numerator"])/polynomial(p["denominator"]))
    return operator_coefficients(h)


def right_remainder(dividend, divisor):
    """Ore right division, with D*f = f*D + f'."""
    out = list(dividend)
    degree = len(divisor)-1
    for top in range(len(out)-1, degree-1, -1):
        factor = sp.cancel(out[top]/divisor[-1])
        shift = top-degree
        for i, value in enumerate(divisor):
            for j in range(shift+1):
                k = i+shift-j
                out[k] = sp.cancel(out[k]-factor*sp.binomial(shift, j)*sp.diff(value, X, j))
    return tuple(out)


def uniqueness_bound(coeffs):
    terms = [(j, power[0], value) for j, c in enumerate(coeffs)
             for power, value in sp.Poly(c, X, domain=sp.QQ).terms() if value != 0]
    if not terms:
        raise ValueError("zero operator")
    shift = min(k-j for j, k, value in terms)
    leading = sp.Poly(sum(value*sp.prod(N-i for i in range(j))
                         for j, k, value in terms if k-j == shift), N, domain=sp.QQ)
    if leading.is_zero:
        raise ValueError("missing coefficient recurrence")
    # ground_roots finds ALL rational roots over QQ; integer roots are among them.
    roots = sorted(int(r) for r in leading.ground_roots() if r.is_Integer and r >= 0)
    count = max([0, -shift]+[r+1 for r in roots])
    return {"coefficient_shift": shift, "leading_polynomial": str(leading.as_expr()),
            "nonnegative_integer_roots": roots, "required_initial_coefficients": count}


def certify_equal(left, right, max_initial=128):
    l, r = annihilator(left), annihilator(right)
    lc, rc = operator_coefficients(l), operator_coefficients(r)
    common = operator_coefficients(l+r)
    if any(right_remainder(common, lc)) or any(right_remainder(common, rc)):
        raise ValueError("common annihilator failed exact right-multiple replay")
    bound = uniqueness_bound(common)
    count = bound["required_initial_coefficients"]
    if count > max_initial:
        return {"status": "initial_coefficient_budget", "bound": bound}
    initial_l, initial_r = coefficients(left, count), coefficients(right, count)
    if initial_l != initial_r:
        return {"status": "refuted", "first_mismatch": next(i for i in range(count) if initial_l[i] != initial_r[i])}
    cert = {"schema": SCHEMA, "status": "exact_formal_series_equality", "left": deepcopy(left),
            "right": deepcopy(right), "left_operator": list(map(str, lc)),
            "right_operator": list(map(str, rc)), "common_operator": list(map(str, common)),
            "uniqueness": bound, "initial_coefficients": list(map(str, initial_l)),
            "trusted_backend": {"name": "SymPy holonomic", "version": sp.__version__},
            "scope": "Q[[x]] at zero; analytic germs only; no continuation/special-value claim",
            "special_value_proved": False, "novelty_established": False}
    cert["sha256"] = sha256(key(cert).encode()).hexdigest()
    return cert


def replay_certificate(cert):
    try:
        return cert == certify_equal(cert["left"], cert["right"])
    except (ValueError, KeyError, TypeError, ZeroDivisionError):
        return False
