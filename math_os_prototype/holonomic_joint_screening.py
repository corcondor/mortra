"""Screen joint conjectures against replayed knowledge and rational multiples."""

from hashlib import sha256
import sympy as sp

from math_os_prototype.holonomic_joint_relations import relation_program, uninterpreted_expression
from math_os_prototype.holonomic_route_discovery import X


def opaque_polynomial(expression):
    expression = sp.cancel(expression)
    opaque = expression.atoms(sp.Function, sp.Derivative, sp.Subs)
    replacements = {a: sp.Symbol("u"+sha256(str(a).encode()).hexdigest()) for a in opaque}
    return expression.xreplace(replacements)


def rational_multiple_key(expression):
    encoded = opaque_polynomial(expression)
    if encoded == 0:
        return "zero"
    variables = sorted(encoded.free_symbols-{X}, key=str)
    if not variables:
        return "nonzero_rational_function"
    return str(sp.Poly(encoded, *variables, domain=sp.QQ.frac_field(X)).monic().as_expr())


def screen(features, terms, library):
    residual = relation_program(features, terms)
    reduced, trace = library.reduce(residual)
    if not library.replay(trace):
        raise ValueError("prior knowledge failed replay")
    canonical = rational_multiple_key(uninterpreted_expression(reduced))
    return {"status": "known_relation" if canonical == "zero" else "requires_proof",
            "rewrite": trace, "rational_multiple_key": canonical,
            "scope": "known rewrites and arithmetic only; not a novelty certificate"}
