"""Exact formal germs defined by an ODE, not by a special-function name.

Geometric origin and analytic convergence require separate source certificates.
The leading coefficient recurrence fixes all coefficients after its last
nonnegative integer root; initial values must satisfy every earlier equation.
"""
from functools import lru_cache
from hashlib import sha256
import json
from pathlib import Path

import sympy as sp

from math_os_prototype.ordinary_period_germ import coefficient_recurrence, exact_germ_coefficients


@lru_cache(maxsize=128)
def source_data(serialized):
    from math_os_prototype.holonomic_route_discovery import rational
    p = json.loads(serialized)
    if set(p) != {"op", "operator", "initial"} or p["op"] != "ode":
        raise ValueError("invalid ODE germ fields")
    rows, initial = p["operator"], p["initial"]
    if (not isinstance(rows, list) or not 2 <= len(rows) <= 21 or
            not isinstance(initial, list) or not 1 <= len(initial) <= 512 or
            any(not isinstance(row, list) or not 1 <= len(row) <= 1025 for row in rows)):
        raise ValueError("ODE source size budget exceeded")
    x = sp.Symbol("x")
    polys = tuple(sp.Add(*(rational(c)*x**j for j, c in enumerate(row))) for row in rows)
    if not polys[-1]:
        raise ValueError("ODE leading coefficient is zero")
    values = tuple(rational(v) for v in initial)
    recurrence = coefficient_recurrence({"variable": "x", "operator_coefficients_ascending": polys})
    if recurrence["initial_count"] > len(values):
        raise ValueError("ODE source lacks uniqueness-determining initial coefficients")
    exact_germ_coefficients(recurrence, values, len(values))
    return polys, values, recurrence


def source_coefficients(serialized, size, *, fast=False):
    polys, initial, recurrence = source_data(serialized)
    if fast:
        return exact_germ_coefficients(recurrence, initial, size)
    values = list(initial[:size])
    lag_polynomials = recurrence["lag_polynomials"]
    for n in range(len(values), size):
        residual = sum((poly.eval(n)*values[n-lag]
                        for lag, poly in lag_polynomials.items() if 0 < lag <= n), sp.S.Zero)
        values.append(-residual/lag_polynomials[0].eval(n))
    return tuple(values)


def source_corpus(programs, provenance):
    if not isinstance(programs, list) or not 1 <= len(programs) <= 32:
        raise ValueError("ODE source corpus must contain 1..32 objects")
    for p in programs:
        source_data(json.dumps(p, sort_keys=True, separators=(",", ":")))
    encoded = [json.dumps(p, sort_keys=True) for p in programs]
    if len(set(encoded)) != len(encoded):
        raise ValueError("duplicate ODE source")
    payload = {"schema": "mortra.ode-source-corpus.v1", "programs": programs,
               "provenance": provenance,
               "scope": "formal ODE germs; geometric and analytic claims depend on attached source audits"}
    payload["sha256"] = sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    return payload


def replay_corpus(data):
    expected = source_corpus(data["programs"], data["provenance"])
    if expected != data:
        raise ValueError("ODE source corpus changed")
    for name, checksum in data["provenance"].get("files", {}).items():
        if sha256(Path(name).read_bytes()).hexdigest() != checksum:
            raise ValueError("ODE source provenance file changed")
    return expected


def load_corpus(path):
    from math_os_prototype.shared_json import read
    return replay_corpus(read(path))
