"""Discover and certify linear dependencies of generated function expressions.

Polynomial features can contain several functions and their derivatives. Their
values need not be algebraic. Finite coefficient fits remain conjectures until
the existing exact differential-operator proof has been replayed.
"""

from copy import deepcopy
from hashlib import sha256
from itertools import combinations_with_replacement

import sympy as sp
from sympy.polys.matrices import DomainMatrix

from math_os_prototype.holonomic_route_discovery import (
    X, coefficients, certify_equal, key, polynomial, rational, replay_certificate, validate,
)

ZERO = {"op": "poly", "coefficients": [0]}
SCHEMA = "mortra.joint-series-relation.v1"


def balanced_sum(programs):
    if not programs:
        return deepcopy(ZERO)
    if len(programs) == 1:
        return deepcopy(programs[0])
    middle = len(programs)//2
    return {"op": "add", "left": balanced_sum(programs[:middle]),
            "right": balanced_sum(programs[middle:])}


def uninterpreted_expression(program):
    """Use no special-function identity: only arithmetic and formal calculus."""
    validate(program)

    def translate(term):
        op = term["op"]
        if op in ("hyper", "ode"):
            return sp.Function("h"+sha256(key(term).encode()).hexdigest())(X)
        if op == "poly":
            return polynomial(term["coefficients"])
        if op == "scale":
            return rational(term["factor"])*translate(term["child"])
        if op == "diff":
            return sp.diff(translate(term["child"]), X)
        if op in ("mul", "add"):
            a, b = translate(term["left"]), translate(term["right"])
            return a*b if op == "mul" else a+b
        return translate(term["child"]).subs(
            X, polynomial(term["numerator"])/polynomial(term["denominator"]))

    return translate(program)


def definition_only(features, terms):
    return sp.cancel(uninterpreted_expression(relation_program(features, terms))) == 0


def make_features(programs, degree_x=2, derivatives=1, product_degree=2):
    if (not 1 <= len(programs) <= 32 or type(degree_x) is not int or not 0 <= degree_x <= 6
            or type(derivatives) is not int or not 0 <= derivatives <= 3
            or type(product_degree) is not int or not 1 <= product_degree <= 2):
        raise ValueError("invalid feature budget")
    if len({key(p) for p in programs}) != len(programs):
        raise ValueError("duplicate input syntax")
    atoms = []
    for origin, program in enumerate(programs):
        validate(program)
        current = deepcopy(program)
        for derivative in range(derivatives+1):
            atoms.append({"program": current, "origin": origin, "derivative": derivative})
            current = {"op": "diff", "child": current}
    features = []
    for degree in range(product_degree+1):
        for factors in combinations_with_replacement(range(len(atoms)), degree):
            if not factors:
                p = {"op": "poly", "coefficients": [1]}
            else:
                p = deepcopy(atoms[factors[0]]["program"])
                for index in factors[1:]:
                    p = {"op": "mul", "left": p, "right": deepcopy(atoms[index]["program"])}
            for power in range(degree_x+1):
                monomial = {"op": "poly", "coefficients": [0]*power+[1]}
                program = p if power == 0 else monomial if not factors else {
                    "op": "mul", "left": monomial, "right": p}
                validate(program)
                features.append({"program": deepcopy(program), "power_x": power,
                    "factors": [{"origin": atoms[i]["origin"], "derivative": atoms[i]["derivative"]} for i in factors]})
    if len(features) > 176:
        raise ValueError("feature count exceeds coefficient budget")
    return features


def normalize_vector(vector):
    denominator = sp.ilcm(*[int(c.q) for c in vector]) if len(vector) > 1 else int(vector[0].q)
    values = [int(c*denominator) for c in vector]
    common = sp.igcd(*values) if len(values) > 1 else abs(values[0])
    if not common:
        raise ValueError("zero relation vector")
    values = [v//int(common) for v in values]
    if next(v for v in values if v) < 0:
        values = [-v for v in values]
    return values


def guess_relations(features, holdout=16, coefficient_backend="reference"):
    from math_os_prototype.research_events import measured
    if not 1 <= len(features) <= 176 or type(holdout) is not int or not 1 <= holdout <= 32:
        raise ValueError("invalid guessing budget")
    if coefficient_backend not in ("reference", "flint"):
        raise ValueError("unknown exact coefficient backend")
    provider = coefficients
    if coefficient_backend == "flint":
        from math_os_prototype.holonomic_fast_coefficients import coefficients as provider
    training = max(16, 2*len(features))
    size = training+holdout
    with measured("joint_series", "relation_coefficients", features=len(features), coefficients=size):
        columns = [provider(f["program"], size) for f in features]
    with measured("joint_series", "relation_matrix", rows=training, columns=len(features)):
        matrix = sp.Matrix([[column[n] for column in columns] for n in range(training)])
    with measured("joint_series", "relation_nullspace"):
        if coefficient_backend == "flint":
            from math_os_prototype.exact_rational_nullspace import nullspace_rows
            nullspace = nullspace_rows(matrix)
        else:
            nullspace = DomainMatrix.from_Matrix(matrix).to_field().nullspace().to_Matrix()
    candidates, rejected = [], []
    for row in nullspace.tolist():
        vector = normalize_vector(row)
        terms = [{"feature": i, "coefficient": str(c)} for i, c in enumerate(vector) if c]
        first = next((n for n in range(training, size)
                      if sum((c*columns[i][n] for i, c in enumerate(vector) if c), sp.S.Zero) != 0), None)
        if first is not None:
            rejected.append({"terms": terms, "first_heldout_mismatch": first})
            continue
        origins = sorted({a["origin"] for t in terms for a in features[t["feature"]]["factors"]})
        candidates.append({"terms": terms, "origins": origins, "term_count": len(terms),
            "coefficient_height_bits": max(abs(int(t["coefficient"])).bit_length() for t in terms),
            "status": "finite_coefficient_fit_only"})
    candidates.sort(key=lambda c: (len(c["origins"]) < 2, c["term_count"], c["coefficient_height_bits"], key(c["terms"])))
    return {"training_coefficients": training, "heldout_coefficients": holdout,
            "feature_count": len(features), "nullity": nullspace.rows,
            "candidates": candidates, "rejected": rejected, "infinite_identity_proved": False}


def relation_program(features, terms):
    if not terms or len(terms) > len(features):
        raise ValueError("invalid relation support")
    programs, used = [], set()
    for term in terms:
        if set(term) != {"feature", "coefficient"}:
            raise ValueError("unexpected relation field")
        index, c = term["feature"], rational(term["coefficient"])
        if type(index) is not int or not 0 <= index < len(features) or index in used or c == 0:
            raise ValueError("invalid relation term")
        used.add(index)
        p = deepcopy(features[index]["program"])
        programs.append(p if c == 1 else {"op": "scale", "factor": str(c), "child": p})
    result = balanced_sum(programs)
    validate(result)
    return result


def _wrap_certificate(features, terms, proof, proof_backend):
    cert = {"schema": SCHEMA, "status": "exact_joint_series_relation",
            "features_sha256": sha256(key(features).encode()).hexdigest(),
            "terms": deepcopy(terms), "proof": proof,
            "scope": "formal identity at zero; special values require a separate analytic domain",
            "novelty_established": False}
    if proof_backend != "closure":
        cert["proof_backend"] = proof_backend
    cert["sha256"] = sha256(key(cert).encode()).hexdigest()
    return cert


def certify_relation(features, terms, proof_backend="closure"):
    residual = relation_program(features, terms)
    if proof_backend == "closure":
        proof = certify_equal(residual, ZERO)
        success = "exact_formal_series_equality"
    elif proof_backend == "shared_module":
        from math_os_prototype.holonomic_shared_module import certify_equal_shared, SharedModuleBudget
        try:
            proof = certify_equal_shared(residual, ZERO)
        except SharedModuleBudget as exc:
            proof = {"status": "shared_module_budget", "reason": str(exc)}
        success = "exact_shared_module_equality"
    else:
        raise ValueError("unknown relation proof backend")
    if proof["status"] != success:
        return {"status": proof["status"], "proof_attempt": proof}
    return _wrap_certificate(features, terms, proof, proof_backend)


def replay_relation(cert, features):
    try:
        if cert.get("proof_backend") == "shared_module":
            from math_os_prototype.holonomic_shared_module import replay_shared_certificate
            if cert != _wrap_certificate(features, cert["terms"], cert["proof"], "shared_module"):
                return False
            return (cert["proof"]["left"] == relation_program(features, cert["terms"])
                    and cert["proof"]["right"] == ZERO and replay_shared_certificate(cert["proof"]))
        if cert != certify_relation(features, cert["terms"]):
            return False
        return replay_certificate(cert["proof"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        return False
