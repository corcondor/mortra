"""Exact finite-function spaces, with separately certified readout bindings.

Coordinates are rational functions on the declared complete finite model.
Canonicalization is row reduction, not a comparison of names or dimensions.
No panel-history legality or external goal is licensed by these certificates.
"""
from copy import deepcopy
import sympy as sp

from math_os_prototype.theory_domain import linear_readout
from math_os_prototype.representation_progress import digest


def seal(record):
    result = deepcopy(record)
    result["sha256"] = digest(result)
    return result


def checked(record):
    if record.get("sha256") != digest({k: v for k, v in record.items() if k != "sha256"}):
        raise ValueError("certified space/binding content changed")


def canonical_space(domain, acquired):
    system = domain.linear_system()
    xs = system.variables
    old = [sp.sympify(b) for b in acquired["basis"]]
    rows = sp.Matrix([[sp.expand(b).coeff(x) for x in xs] for b in old])
    if any(sp.expand(b-sum(a*x for a, x in zip(row, xs))) != 0
           for b, row in zip(old, rows.tolist())):
        raise ValueError("not a rational finite-function linear encoding")
    reduced, _ = rows.rref()
    reduced = sp.Matrix([row for row in reduced.tolist() if any(row)])
    basis = [sum(a*x for a, x in zip(row, xs)) for row in reduced.tolist()]
    change = sp.Matrix([linear_readout(old, b, xs) for b in basis])
    matrices = {}
    for generator in system.generators:
        old_action = sp.Matrix(acquired["action_matrices"][generator.name])
        transformed = change * old_action * change.inv()
        if transformed * change != change * old_action:
            raise AssertionError("basis-change action correspondence failed")
        # Independent exact transition check on every coordinate, not samples.
        from math_os_prototype.finite_generator_problem_dna import pullback
        if any(sp.expand(pullback(b, generator, xs)-v) != 0
               for b, v in zip(basis, transformed*sp.Matrix(basis))):
            raise AssertionError("canonical action identity failed")
        matrices[generator.name] = [[str(x) for x in row] for row in transformed.tolist()]
    key = {"system_key": domain.key, "scope": domain.scope, "field": "QQ",
           "basis": [str(b) for b in basis], "action_matrices": matrices}
    return seal(dict(key, id="S-"+digest(key)[:16], dimension=len(basis),
                     ambient_dimension=len(xs), omits=acquired["omits"],
                     semantic_type=acquired["semantic_type"],
                     certificate={"method": "rational change of basis and exact action identities",
                                  "all_zero": True},
                     source_basis=acquired["basis"],
                     change_of_basis=[[str(x) for x in row] for row in change.tolist()]))


def readout(domain, space, expression, *, requirements=None):
    checked(space)
    if space["system_key"] != domain.key or space["scope"] != domain.scope or space["field"] != "QQ":
        raise ValueError("action, field or certificate scope mismatch")
    if requirements and any(v not in (None, False, "unrestricted") for v in requirements.values()):
        raise ValueError("readout existence does not certify legality or goal requirements")
    system = domain.linear_system()
    values = domain.evaluate(expression)
    q = sum(v*x for v, x in zip(values, system.variables))
    return linear_readout([sp.sympify(b) for b in space["basis"]], q, system.variables)


def materialize(state, rid):
    binding = state["representations"][rid]
    if "space" not in binding:
        return binding
    space = state["observable_spaces"][binding["space"]]
    checked(space)
    checked(binding["binding_certificate"])
    cert = binding["binding_certificate"]
    if cert["space_sha256"] != space["sha256"] or cert["readout"] != binding["readout"]:
        raise ValueError("binding refers to different space or readout")
    if cert["scope"] != space["scope"] or binding["scope"] != space["scope"] or \
       cert["expression"] != state["concepts"][binding["concept"]]["definition"]:
        raise ValueError("binding expression or scope changed")
    return dict(space, **{k: v for k, v in binding.items() if k not in {"certificate", "sha256"}})


def bind(domain, state, cid, space, coefficients, cycle):
    rid = "R-"+cid[2:]
    certificate = seal({"space_sha256": space["sha256"], "readout": coefficients,
                        "expression": state["concepts"][cid]["definition"],
                        "scope": deepcopy(domain.scope), "identity_verified": True,
                        "task_applicability": "observation only; legality and goal not inferred"})
    return {"id": rid, "concept": cid, "space": space["id"], "readout": coefficients,
            "theorem": "T-closure-"+cid[2:], "born": cycle, "reuse_count": 0,
            "derived_labels": [], "query_count": 0, "dimension": space["dimension"],
            "binding_certificate": certificate, "certificate": certificate,
            "scope": deepcopy(domain.scope), "system_key": domain.key}
