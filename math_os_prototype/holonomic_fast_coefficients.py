"""Exact polynomial arithmetic for long analytic-germ compositions.

FLINT accelerates truncated products. This is not a numerical approximation:
every coefficient is rational, and the original implementation remains an
independent reference used by the proof replay.
"""

from functools import lru_cache
import json

from flint import fmpq, fmpq_poly
import sympy as sp

from math_os_prototype.holonomic_route_discovery import key, rational, validate


def _q(value):
    return fmpq(str(rational(value)))


def coefficients(program, size):
    validate(program)
    if type(size) is not int or not 0 <= size <= 512:
        raise ValueError("coefficient budget exceeded")
    result = _series(key(program), size)
    return tuple(sp.Rational(str(result[i])) for i in range(size))


@lru_cache(maxsize=1024)
def _series(serialized, size):
    if not 0 <= size <= 512:
        raise ValueError("coefficient budget exceeded")
    if size == 0:
        return fmpq_poly()
    p = json.loads(serialized)
    op = p["op"]
    if op == "ode":
        from math_os_prototype.holonomic_ode_source import source_coefficients
        return fmpq_poly(source_coefficients(serialized, size, fast=True))
    if op == "poly":
        return fmpq_poly([_q(c) for c in p["coefficients"][:size]])
    if op == "hyper":
        a, b = [_q(v) for v in p["a"]], [_q(v) for v in p["b"]]
        values = [fmpq(1)]
        for n in range(size-1):
            value = values[-1]/(n+1)
            for parameter in a:
                value *= n+parameter
            for parameter in b:
                value /= n+parameter
            values.append(value)
        return fmpq_poly(values)
    if op == "diff":
        return _series(key(p["child"]), size+1).derivative().truncate(size)
    if op == "scale":
        return (_series(key(p["child"]), size)*_q(p["factor"])).truncate(size)
    if op in ("mul", "add"):
        a, b = _series(key(p["left"]), size), _series(key(p["right"]), size)
        return (a*b if op == "mul" else a+b).truncate(size)
    numerator = fmpq_poly([_q(v) for v in p["numerator"][:size]])
    denominator = [_q(v) for v in p["denominator"]]
    inverse = [1/denominator[0]]
    for n in range(1, size):
        inverse.append(-sum((denominator[j]*inverse[n-j]
                            for j in range(1, min(n+1, len(denominator)))), fmpq(0))/denominator[0])
    phi = (numerator*fmpq_poly(inverse)).truncate(size)
    child = _series(key(p["child"]), size)
    result = fmpq_poly()
    for n in range(size-1, -1, -1):
        result = (result*phi+child[n]).truncate(size)
    return result
