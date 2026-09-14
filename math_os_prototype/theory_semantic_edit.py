"""Bounded library learning modulo certified finite-model polynomial equations.

Not equality saturation: keep the original corpus and one certified alternative
view, then run the existing anti-unifier on both. Universal arguments are
arbitrary QQ-valued functions on *all* model states, not sampled DSL arguments.
The polynomial prover and linear-system solver are initial infrastructure.
The discovered right-hand sides and equation records are acquired knowledge.
"""
from copy import copy, deepcopy
import time
import sympy as sp

from math_os_prototype import library_compression as lib
from math_os_prototype.theory_domain import term
from math_os_prototype.representation_progress import digest


def immutable_definition(d):
    return {k: d[k] for k in ("index", "id", "template", "signature", "scope", "dependencies")}


def dependencies(vocabulary, nodes):
    """Fingerprint only the referenced immutable definitions and certificates."""
    found = {}
    def walk(t):
        if not isinstance(t, dict):
            if isinstance(t, list):
                for a in t:
                    walk(a)
            return
        if lib.is_call(t):
            d = next(d for d in vocabulary.state["definitions"]
                     if str(d["index"]) == str(t["abstraction"]))
            key = "definition:"+str(d["index"])
            if key not in found:
                found[key] = digest(immutable_definition(d))
                walk(d["template"])
        if t.get("op") == "represented":
            from math_os_prototype.theory_spaces import materialize
            r = materialize(vocabulary.theory.state, t["binding"])
            found["representation:"+t["binding"]] = digest({k: r.get(k) for k in
                ("basis", "action_matrices", "readout", "scope", "system_key", "binding_certificate", "certificate")})
        if t.get("op") == "recurrence":
            p, law = vocabulary.law(t["procedure"])
            found["procedure:"+t["procedure"]] = digest([p["kind"], p["representation"], law])
        for a in t.values():
            walk(a)
    walk(nodes)
    return found


class SymbolicScope:
    def __init__(self, vocabulary, signature):
        if vocabulary.domain.scope["kind"] != "complete_finite_model":
            raise ValueError("no symbolic-argument certificate for this domain")
        if signature["result"] != "scalar" or any(t != "scalar" for t in signature["parameters"].values()):
            raise ValueError("only scalar function parameters are certified here")
        self.v = copy(vocabulary)
        self.v.domain = copy(vocabulary.domain)
        self.v.domain.names = list(vocabulary.domain.names)
        self.binding, self.symbolic, self.reverse = {}, {}, {}
        for i, name in enumerate(signature["parameters"]):
            sensor = "__argument_"+str(i)
            while sensor in self.v.domain.names:
                sensor += "_"
            self.binding[name] = term("var", name=sensor)
            self.reverse[sensor] = {"series_parameter": name}
            self.symbolic[sensor] = tuple(sp.Symbol(f"u{i}_s{j}") for j in range(len(vocabulary.domain.models)))
            self.v.domain.names.append(sensor)
        self.symbols = tuple(s for values in self.symbolic.values() for s in values)
        self.cost = {"symbolic_nodes": 0, "polynomial_identities": 0, "linear_systems": 0,
                     "candidate_relations": 0}
        self.certification_seconds = 0

    def instantiate(self, template):
        with lib.grammar(self.v.accepts):
            return lib.instantiate_term(template, self.binding)

    def values(self, template):
        instance = self.instantiate(template)
        primitive = self.v.primitive(instance,
            charge=lambda k, n: self.cost.__setitem__(k, self.cost.get(k, 0)+n))
        if self.v.domain.type_of(primitive) != "scalar":
            raise ValueError("non-polynomial definition")
        values = self.v.domain.evaluate(primitive, symbolic_sensors=self.symbolic)
        self.cost["symbolic_nodes"] += sum(int(sp.count_ops(x))+1 for x in values)
        return tuple(sp.expand(x) for x in values)

    def key(self, values):
        return tuple(sp.srepr(v) for v in values)

    def equal(self, left, right):
        started = time.perf_counter()
        self.cost["candidate_relations"] += 1
        lvals, rvals = self.values(left), self.values(right)
        residuals = [sp.expand(a-b) for a, b in zip(lvals, rvals)]
        self.cost["polynomial_identities"] += len(residuals)
        # QQ polynomial equality, coefficient by coefficient; no numeric fit.
        passed = all(sp.Poly(r, *self.symbols, domain=sp.QQ).is_zero
                     if self.symbols else r == 0 for r in residuals)
        proof = {"kind": "all_states_symbolic_polynomial_identity", "field": "QQ",
            "scope": deepcopy(self.v.domain.scope), "free_variables": [str(s) for s in self.symbols],
            "quantification": "independent arbitrary QQ value per parameter per declared state",
            "premises": "pure scalar polynomial operations; no legality or history assertion",
            "left": [str(x) for x in lvals], "right": [str(x) for x in rvals],
            "residuals": [str(r) for r in residuals], "passed": passed}
        self.certification_seconds += time.perf_counter()-started
        return passed, proof

    def linear_candidate(self, target, atoms):
        """Solve a QQ linear readout of existing typed atoms, with symbolic args."""
        vectors = [self.values(a) for a in atoms]
        all_vectors = [*vectors, target]
        rows = []
        for state in range(len(target)):
            if self.symbols:
                polys = [sp.Poly(v[state], *self.symbols, domain=sp.QQ) for v in all_vectors]
                support = sorted({m for p in polys for m in p.monoms()})
                rows.extend([[p.coeff_monomial(m) for p in polys] for m in support])
            else:
                rows.append([v[state] for v in all_vectors])
        matrix = sp.Matrix(rows)
        self.cost["linear_systems"] += 1
        try:
            weights, free = matrix[:, :-1].gauss_jordan_solve(matrix[:, -1])
        except ValueError:
            return None
        weights = weights.subs({x: 0 for x in free})
        if matrix[:, :-1]*weights != matrix[:, -1]:
            raise AssertionError("readout residual")
        summands = []
        for weight, atom in zip(weights, atoms):
            if not weight:
                continue
            summands.append(deepcopy(atom) if weight == 1 else term("neg", deepcopy(atom))
                            if weight == -1 else term("mul", term("const", value=str(weight)), deepcopy(atom)))
        out = summands[0] if summands else term("const", value="0")
        for a in summands[1:]:
            out = term("add", out, a)
        self.instantiate(out)  # Do not introduce undeclared arithmetic operations.
        return out


def discover(v, definition):
    start = time.perf_counter()
    record = {"definition": definition["id"], "cycle": v.theory.state["cycle"],
              "status": "unsupported", "relations": []}
    scope = None
    try:
        scope = SymbolicScope(v, definition["signature"])
        left = definition["template"]
        target = scope.values(left)
        atoms = [{"series_parameter": name} for name in definition["signature"]["parameters"]]
        atoms += v.domain.seeds()
        candidates = list(atoms)
        # Also retain non-shortest shared contexts and previously acquired bodies.
        from math_os_prototype.holonomic_relation_reuse import occurrences
        candidates += [t for _, t in occurrences(left) if isinstance(t, dict) and "op" in t and not lib.is_call(t)]
        for old in v.state["definitions"]:
            if old["index"] >= definition["index"] or old["signature"] != definition["signature"]:
                continue
            candidates.append(old["template"])
        linear = scope.linear_candidate(target, atoms)
        if linear is not None:
            candidates.append(linear)
        seen = {digest(left)}
        for right in candidates:
            key = digest(right)
            if key in seen:
                continue
            seen.add(key)
            try:
                passed, proof = scope.equal(left, right)
            except (ValueError, KeyError, TypeError):
                continue
            if not passed:
                continue
            relation = {"definition_index": definition["index"], "definition": definition["id"],
                "left": deepcopy(left), "right": deepcopy(right),
                "signature": deepcopy(definition["signature"]), "scope": deepcopy(v.domain.scope),
                "proof": proof, "cycle": v.theory.state["cycle"],
                "kind": "projection" if lib.is_hole(right) else "equivalent_implementation"}
            call = {"op": lib.USE, "abstraction": definition["index"],
                    "arguments": {n: {"series_parameter": n} for n in definition["signature"]["parameters"]}}
            relation["dependencies"] = dependencies(v, [call, right])
            relation["id"] = "E-"+digest(relation)[:16]
            relation["sha256"] = digest(relation)
            record["relations"].append(relation)
        record["status"] = "certified" if record["relations"] else "no_relation_in_bounded_candidates"
    except (ValueError, KeyError, TypeError) as exc:
        record["reason"] = str(exc)
    record["costs"] = scope.cost if scope else {}
    record["seconds"] = time.perf_counter()-start
    record["certification_seconds"] = scope.certification_seconds if scope else 0
    record["discovery_seconds"] = record["seconds"]-record["certification_seconds"]
    return record


def validate(v, relation):
    if relation["scope"] != v.domain.scope or not relation["proof"]["passed"]:
        raise ValueError("semantic equation scope mismatch")
    if digest({k: x for k, x in relation.items() if k != "sha256"}) != relation["sha256"]:
        raise ValueError("semantic equation seal mismatch")
    d = next(d for d in v.state["definitions"] if d["index"] == relation["definition_index"])
    call = {"op": lib.USE, "abstraction": d["index"], "arguments": {}}
    if (relation["left"] != d["template"] or relation["signature"] != d["signature"] or
            dependencies(v, [call, relation["right"]]) != relation["dependencies"]):
        raise ValueError("semantic equation dependencies changed")


def rewrite(v, program, *, counter=None, charge=None, relation_ids=None):
    """Cost-decreasing choice at each concrete call; originals stay immutable."""
    counter = counter if counter is not None else {}
    proofs = []
    relations = [r for r in v.state.get("semantic_relations", []) if relation_ids is None or r["id"] in relation_ids]
    v.accepts(program, counter=counter)
    def visit(t):
        if not isinstance(t, dict):
            return t
        if lib.is_call(t):
            node = dict(t, arguments={k: visit(a) for k, a in t["arguments"].items()})
            if not relations:
                return node
            best, score = node, v.execution_estimate(node, counter=counter, charge=charge)
            proof = None
            for r in relations:
                counter["rewrite_matching_checks"] = counter.get("rewrite_matching_checks", 0)+1
                if charge:
                    charge("rewrite_matching_checks", 1)
                if str(r["definition_index"]) != str(node["abstraction"]):
                    continue
                validate(v, r)
                with lib.grammar(v.accepts):
                    candidate = lib.instantiate_term(r["right"], node["arguments"])
                if v.accepts(candidate) != v.accepts(node):
                    raise ValueError("rewrite changes type")
                value = v.execution_estimate(candidate, counter=counter, charge=charge)
                if value < score:
                    best, score, proof = candidate, value, r["id"]
            if proof:
                proofs.append(proof)
                counter["semantic_rewrites"] = counter.get("semantic_rewrites", 0)+1
            return best
        return dict(t, args=[visit(a) for a in t.get("args", [])])
    return visit(program), proofs
