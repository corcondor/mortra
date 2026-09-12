"""Rational Cauchy bounds for the existing analytic-germ program grammar.

This adds evaluation, not recognition of a special value. Every returned
interval encloses the value on the branch defined by the series at zero.
SymPy exact rational/polynomial arithmetic is trusted; no floating point is
used in a certificate. Unsupported disks are failures of this bound method,
not evidence of divergence.
"""

from copy import deepcopy
from hashlib import sha256

import sympy as sp

from math_os_prototype.holonomic_route_discovery import coefficients, key, rational, validate

SCHEMA = "mortra.holonomic-certified-evaluation.v1"
M = sp.Symbol("m", nonnegative=True)


class BoundUnavailable(ValueError):
    pass


def _positive_radius(value):
    radius = rational(value)
    if radius <= 0:
        raise ValueError("radius must be positive")
    return radius


def _poly_abs(values, radius):
    return sum((abs(rational(v))*radius**i for i, v in enumerate(values)), sp.S.Zero)


def disk_bound(program, radius, ratio_budget=128):
    """Prove analyticity near |z| <= radius and a uniform modulus bound."""
    validate(program)
    radius = _positive_radius(radius)
    if type(ratio_budget) is not int or not 0 <= ratio_budget <= 256:
        raise ValueError("invalid ratio budget")
    op = program["op"]
    proof = {"rule": op, "radius": str(radius)}
    if op == "hyper":
        a = [abs(rational(v)) for v in program["a"]]
        b = [rational(v) for v in program["b"]]
        if len(a) == len(b)+1:
            if radius >= 1:
                raise BoundUnavailable("balanced hypergeometric disk must have radius < 1")
            rho = (1+radius)/2
        else:
            rho = sp.Rational(1, 2)
        # Nonnegative coefficients in m certify the ratio bound for every n=N+m.
        for start in range(ratio_budget+1):
            n = M+start
            gap = sp.Poly(rho*(n+1)*sp.prod(n+v for v in b)
                          - radius*sp.prod(n+v for v in a), M, domain=sp.QQ)
            if all(c >= 0 for c in gap.all_coeffs()):
                break
        else:
            raise BoundUnavailable("no all-index coefficient-ratio bound within budget")
        c = coefficients(program, start+1)
        finite = sum((abs(c[i])*radius**i for i in range(start)), sp.S.Zero)
        tail = abs(c[start])*radius**start/(1-rho)
        bound = finite+tail
        proof.update({"start": start, "rho": str(rho),
                      "ratio_gap_coefficients_descending": list(map(str, gap.all_coeffs())),
                      "initial_coefficients": list(map(str, c)),
                      "finite_bound": str(finite), "tail_bound": str(tail)})
    elif op == "poly":
        bound = _poly_abs(program["coefficients"], radius)
    elif op == "scale":
        child = disk_bound(program["child"], str(radius), ratio_budget)
        bound = abs(rational(program["factor"]))*rational(child["bound"])
        proof["child"] = child
    elif op in ("mul", "add"):
        left = disk_bound(program["left"], str(radius), ratio_budget)
        right = disk_bound(program["right"], str(radius), ratio_budget)
        a, b = rational(left["bound"]), rational(right["bound"])
        bound = a*b if op == "mul" else a+b
        proof.update({"left": left, "right": right})
    elif op == "diff":
        outer = 2*radius
        child = disk_bound(program["child"], str(outer), ratio_budget)
        bound = rational(child["bound"])/(outer-radius)
        proof.update({"child": child, "outer_radius": str(outer),
                      "method": "Cauchy derivative estimate"})
    else:
        num_upper = _poly_abs(program["numerator"], radius)
        den_lower = 2*abs(rational(program["denominator"][0])) \
            - _poly_abs(program["denominator"], radius)
        if den_lower <= 0:
            raise BoundUnavailable("denominator not separated from zero on disk")
        image_radius = num_upper/den_lower
        child = disk_bound(program["child"], str(image_radius), ratio_budget)
        bound = rational(child["bound"])
        proof.update({"child": child, "numerator_upper": str(num_upper),
                      "denominator_lower": str(den_lower), "image_radius": str(image_radius)})
    proof["bound"] = str(bound)
    return proof


def certify_evaluation(program, point, radius, digits=20, max_terms=384, ratio_budget=128):
    """Enclose F(point) to absolute interval width <= 10**(-digits)."""
    validate(program)
    point, radius = rational(point), _positive_radius(radius)
    if abs(point) >= radius:
        raise ValueError("point must lie strictly inside the certified disk")
    if type(digits) is not int or not 1 <= digits <= 100:
        raise ValueError("invalid accuracy budget")
    if type(max_terms) is not int or not 1 <= max_terms <= 384:
        raise ValueError("invalid coefficient budget")
    proof = disk_bound(program, str(radius), ratio_budget)
    bound = rational(proof["bound"])
    ratio = abs(point)/radius
    tolerance = sp.Rational(1, 10**digits)
    for count in range(1, max_terms+1):
        error = bound*ratio**count/(1-ratio)
        if 2*error <= tolerance:
            break
    else:
        raise BoundUnavailable("Cauchy tail exceeds accuracy at coefficient budget")
    c = coefficients(program, count)
    partial = sum((v*point**i for i, v in enumerate(c)), sp.S.Zero)
    cert = {"schema": SCHEMA, "status": "certified_real_interval", "program": deepcopy(program),
            "point": str(point), "radius": str(radius), "digits": digits,
            "max_terms": max_terms, "ratio_budget": ratio_budget,
            "disk_proof": proof, "terms": count, "coefficients": list(map(str, c)),
            "partial_sum": str(partial), "tail_bound": str(error),
            "lower": str(partial-error), "upper": str(partial+error),
            "width": str(2*error), "tolerance": str(tolerance),
            "method": "Cauchy coefficient bound and geometric tail; exact rational arithmetic",
            "trusted_backend": {"name": "SymPy rational and polynomial arithmetic", "version": sp.__version__},
            "scope": "real rational point in certified disk; branch analytic at zero",
            "global_continuation_proved": False, "exact_special_value_identified": False,
            "novelty_established": False}
    cert["sha256"] = sha256(key(cert).encode()).hexdigest()
    return cert


def replay_evaluation(cert):
    try:
        return cert == certify_evaluation(cert["program"], cert["point"], cert["radius"],
                                          cert["digits"], cert["max_terms"], cert["ratio_budget"])
    except (ValueError, KeyError, TypeError, ZeroDivisionError):
        return False


def choose_evaluation_disk(program, radius_steps=20, ratio_budget=128):
    """Fixed, value-blind policy: first certifiable dyadic disk, then t=R/2."""
    if type(radius_steps) is not int or not 1 <= radius_steps <= 24:
        raise ValueError("invalid radius search budget")
    failures = []
    radii = [sp.Rational(3, 4)]+[sp.Rational(1, 2**i) for i in range(1, radius_steps+1)]
    for radius in radii:
        try:
            disk_bound(program, str(radius), ratio_budget)
            return {"point": str(radius/2), "radius": str(radius), "rejected_disks": failures}
        except BoundUnavailable as exc:
            failures.append({"radius": str(radius), "reason": str(exc)})
    raise BoundUnavailable("no disk certified within fixed radius search")
