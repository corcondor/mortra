"""Certify definition-only equalities without special-function identities."""
from copy import deepcopy
from hashlib import sha256
import json

import sympy as sp

from math_os_prototype.holonomic_joint_relations import uninterpreted_expression
from math_os_prototype.holonomic_route_discovery import X, polynomial, validate


def normalized_maps(program):
    validate(program)

    def normalize(term):
        result = {name: normalize(value) if isinstance(value, dict) else deepcopy(value)
                  for name, value in term.items()}
        if result["op"] == "pullback":
            ratio = sp.cancel(polynomial(result["numerator"]) / polynomial(result["denominator"]))
            numerator, denominator = sp.fraction(ratio)
            result["numerator"] = list(map(str, reversed(sp.Poly(numerator, X).all_coeffs())))
            result["denominator"] = list(map(str, reversed(sp.Poly(denominator, X).all_coeffs())))
        return result

    return normalize(program)


def certify_definition_equal(left, right):
    a, b = normalized_maps(left), normalized_maps(right)
    if sp.cancel(uninterpreted_expression(a) - uninterpreted_expression(b)) != 0:
        return None
    payload = {"schema": "mortra.definition-only-series-equality.v1",
               "status": "definition_only_equality", "left": deepcopy(left), "right": deepcopy(right),
               "normalized_left": a, "normalized_right": b,
               "scope": "rational arithmetic and formal calculus; hypergeometric atoms uninterpreted"}
    payload["sha256"] = sha256(json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
    return payload


def replay_definition_certificate(certificate):
    try:
        reconstructed = certify_definition_equal(certificate["left"], certificate["right"])
        return reconstructed is not None and reconstructed == certificate
    except (ValueError, KeyError, TypeError):
        return False
