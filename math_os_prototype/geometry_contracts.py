"""Certified rational construction DAGs using the existing geometry bridge.

Scope: QQ coefficients, arbitrary real point coordinates, midpoint and foot.
Orthogonality means a zero vector dot product, not two nonzero directed lines.
No numerical diagram, coordinate gauge, or external prover is used.
"""
from __future__ import annotations

from copy import deepcopy
import re
import time

import sympy as sp

from math_os_prototype import library_compression as library
from math_os_prototype.representation_progress import digest
from worker.backend.jgex_exact_constraint_bridge import (
    _JGEXElaborator, _RelationalJGEXElaborator,
    _replay_polynomial_identity_with_flint,
)

ARITIES = {"midpoint": 2, "foot": 3}
SCOPE = {"coefficient_field": "QQ", "models": "real_coordinate_plane",
         "actions": {"midpoint": "bridge_midpoint_v1", "foot": "bridge_foot_v1"},
         "predicates": {"midp": "coordinate_average", "coll": "determinant_zero",
                        "orthogonal": "vector_dot_zero"},
         "branch": "single_valued_rational", "version": 1}


def point(name):
    return {"op": "var", "name": name}


def validate(term, *, fragment=None):
    if not isinstance(term, dict):
        raise ValueError("point term must be a mapping")
    if term.get("op") == "var" and set(term) == {"op", "name"}:
        if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", term["name"]):
            raise ValueError("invalid point parameter")
        return
    arities = ARITIES if fragment is None else fragment.arities
    if (set(term) != {"op", "args"} or term["op"] not in arities
            or len(term["args"]) != arities[term["op"]]):
        raise ValueError("outside the declared rational construction fragment")
    for argument in term["args"]:
        validate(argument, fragment=fragment)


def parameters(term, *, fragment=None):
    validate(term, fragment=fragment)
    if term["op"] == "var":
        return [term["name"]]
    return list(dict.fromkeys(p for a in term["args"] for p in parameters(a, fragment=fragment)))


def dag(term, *, fragment=None):
    """Identical deterministic subterms share one locally bound point."""
    validate(term, fragment=fragment)
    steps, memo = [], {}
    occupied = set(parameters(term, fragment=fragment))
    def visit(node):
        if node["op"] == "var":
            return node["name"]
        key = digest(node)
        if key not in memo:
            inputs = [visit(a) for a in node["args"]]
            index = len(steps)
            name = f"local{index}"
            while name in occupied:
                index += 1
                name = f"local{index}"
            occupied.add(name)
            steps.append({"family": node["op"], "inputs": inputs, "output": name,
                          "term": deepcopy(node)})
            memo[key] = name
        return memo[key]
    output = visit(term)
    return steps, output


def parse(expression, symbols):
    # Saved contracts are data, not an eval channel. Restrict to rational algebra.
    if not re.fullmatch(r"[A-Za-z0-9_+*/(). \-]+", expression):
        raise ValueError("invalid rational expression")
    names = set(re.findall(r"[A-Za-z_][A-Za-z_0-9]*", expression))
    if not names <= set(symbols):
        raise ValueError("undeclared variable in expression")
    value = sp.sympify(expression, locals=symbols)
    if value.has(sp.Float) or not value.is_rational_function(*symbols.values()):
        raise ValueError("exact rational expressions only")
    return value


def factors(expression):
    numerator = sp.cancel(expression).as_numer_denom()[0]
    if numerator == 0:
        raise ValueError("unsatisfiable applicability condition")
    if not numerator.free_symbols:
        return []
    return sorted({str(sp.Poly(f, *sorted(f.free_symbols, key=str), domain=sp.QQ).monic().as_expr())
                   for f, _ in sp.factor_list(numerator)[1]})


def exact_zero(expression):
    numerator = sp.cancel(expression).as_numer_denom()[0]
    replay = _replay_polynomial_identity_with_flint(goal=numerator, multiplier=sp.S.One,
        quotients=(), basis=(), remainder=sp.S.Zero)
    return bool(numerator == 0 if replay is None else replay)


def primitive(elaborator, family, output, inputs, *, fragment=None):
    if fragment is not None:
        return fragment.primitive(elaborator, family, output, inputs)
    if family not in ARITIES or len(inputs) != ARITIES[family]:
        raise ValueError("unsupported primitive")
    getattr(elaborator, "_"+family)((output, *inputs))


def geometric_relations(step):
    y, args = step["output"], step["inputs"]
    if step["family"] == "midpoint":
        return [{"predicate": "midp", "points": [y, *args]}]
    p, a, b = args
    return [{"predicate": "coll", "points": [y, a, b]},
            {"predicate": "orthogonal", "points": [y, p, a, b]}]


def relation_polynomial(elaborator, relation):
    name = relation["predicate"]
    if name not in SCOPE["predicates"]:
        raise ValueError("unverified predicate fragment")
    return elaborator.goal("perp" if name == "orthogonal" else name,
                           tuple(relation["points"]))


def certify_body(body, *, fragment=None):
    """Derive input guards, a rational witness, and triangular uniqueness.

    Existence is substitution in the *relational* bridge's equations.
    Uniqueness follows stepwise from a nonzero 2x2 coefficient determinant.
    Thus a relation true at the witness holds for all C-models under P.
    """
    started = time.perf_counter()
    identity_checks = 0
    def check(expression):
        nonlocal identity_checks
        identity_checks += 1
        return exact_zero(expression)
    steps, output = dag(body, fragment=fragment)
    if not steps:
        raise ValueError("not a construction")
    names = parameters(body, fragment=fragment)
    explicit, relational = _JGEXElaborator(), _RelationalJGEXElaborator()
    coords = {n: tuple(sp.Symbol(n+axis, real=True) for axis in ("x", "y")) for n in names}
    explicit.coordinates.update(coords)
    relational.coordinates.update(coords)
    guards, geometry_guards, witnesses, equations, proofs, relations = set(), [], {}, [], [], []
    substitution = {}
    for step in steps:
        family, y, args = step["family"], step["output"], step["inputs"]
        e0, d0 = len(relational.equations), len(explicit.denominators)
        primitive(explicit, family, y, args, fragment=fragment)
        primitive(relational, family, y, args, fragment=fragment)
        value = tuple(sp.cancel(v) for v in explicit.coordinates[y])
        if any(v.has(sp.zoo, sp.nan, sp.oo) for v in value):
            raise ValueError("undefined witness")
        block = relational.equations[e0:]
        local = relational.coordinates[y]
        matrix = sp.Matrix(block).jacobian(local)
        if len(block) != 2 or any(v.free_symbols & set(local) for v in matrix):
            raise ValueError("construction is not triangular linear in its output")
        determinant = matrix.det().subs(substitution, simultaneous=True)
        step_guards = set(factors(determinant))
        for denominator in explicit.denominators[d0:]:
            step_guards.update(factors(denominator))
        for v in value:
            step_guards.update(factors(v.as_numer_denom()[1]))
        inherited = set(guards)
        if fragment is not None:
            geometry_guards.append({"predicate": "polynomial_nonzero",
                                    "points": args, "input_factors": sorted(step_guards)})
        elif family == "foot":
            a, b = args[1:]
            delta = relational._sub(relational.coordinates[b], relational.coordinates[a])
            raw_guard = relational._dot(delta, delta)
            pulled = raw_guard.subs(substitution, simultaneous=True)
            pn, pd = sp.cancel(pulled).as_numer_denom()
            pulled_guards = set(factors(pn)) | set(factors(pd))
            if pulled_guards | inherited != step_guards | inherited:
                raise ValueError("geometry/polynomial applicability mismatch")
            geometry_guards.append({"predicate": "distinct", "points": [a, b],
                                    "pullback": str(sp.cancel(pulled)),
                                    "input_factors": sorted(step_guards)})
        elif not step_guards <= inherited:
            raise ValueError("unexpected guard on total midpoint")
        guards.update(step_guards)
        substitution.update(zip(local, value))
        checks = [str(sp.cancel(e.subs(substitution, simultaneous=True))) for e in block]
        if not all(check(sp.sympify(e)) for e in checks):
            raise ValueError("relational witness replay failed")
        current_relations = geometric_relations(step) if fragment is None else fragment.relations(step)
        lower = relation_polynomial if fragment is None else fragment.relation_polynomial
        for relation in current_relations:
            residual = lower(relational, relation)
            if not check(residual.subs(substitution, simultaneous=True)):
                raise ValueError("guaranteed relation replay failed")
        # Coordinate midpoint equations are equivalent to a sum of their
        # squares only over the declared real field. Other rows are +/- C rows.
        transfer = []
        for relation in current_relations:
            poly = lower(relational, relation)
            reference = sum(e*e for e in block) if family == "midpoint" else None
            if fragment is not None:
                # The rational witness is the unique output under the recorded
                # determinants. Effects follow by substitution in that witness.
                ok = check(poly.subs(substitution, simultaneous=True))
            elif reference is not None:
                ok = check(poly-reference)
            else:
                ok = any(check(poly-sign*e) for e in block for sign in (1, -1))
            if not ok:
                raise ValueError("geometry relation and construction equations differ")
            transfer.append({"relation": relation, "polynomial": str(poly), "replayed": ok})
        witnesses[y] = [str(v) for v in value]
        equations.extend(map(str, block))
        relations.extend(current_relations)
        proofs.append({"output": y, "linear_output_matrix": [[str(v) for v in row] for row in matrix.tolist()],
                       "determinant_pullback": str(sp.cancel(determinant)),
                       "required_nonzero": sorted(step_guards), "existence_residuals": checks,
                       "transfer": transfer})
    semantic = {"version": 1, "typed_parameters": [{"name": n, "type": "Point"} for n in names],
        "local_auxiliary_variables": [{"name": s["output"], "type": "Point",
            "coordinates": list(map(str, relational.coordinates[s["output"]]))} for s in steps],
        "body": body, "composition": steps, "output": output,
        "applicability": {"input_nonzero_polynomials": sorted(guards), "geometry_pullbacks": geometry_guards},
        "construction_relation": {"geometry": relations, "polynomials": equations},
        "guaranteed_relation": relations, "nondegeneracy_conditions": sorted(guards),
        "branch_conditions": [], "representation_scopes": SCOPE if fragment is None else fragment.scope,
        "witness": witnesses, "dependency_graph": {s["output"]: s["inputs"] for s in steps},
        "exact_certificate": {"method": "rational_witness_and_triangular_linear_uniqueness",
            "steps": proofs, "existence": True, "guarantee": True,
            "contract_transfer": True, "all_input_assignments_under_P": True}}
    semantic["id"] = "geom."+digest(semantic)[:20]
    return semantic, {"certification_seconds": time.perf_counter()-started,
                      "primitive_schema_steps": len(steps), "prover_calls": identity_checks}


def replay_contract(contract):
    rebuilt, costs = certify_body(contract["body"])
    fields = set(rebuilt)
    return ({k: contract.get(k) for k in fields} == rebuilt), costs


def body_from_template(template):
    holes = library.holes(template)
    if any(not n.startswith("f") for n in holes):
        raise ValueError("point-valued parameters required")
    body = library.instantiate_term(template, {n: point(n) for n in holes})
    validate(body)
    if set(parameters(body)) != set(holes):
        raise ValueError("unabstracted source points in definition")
    return body
