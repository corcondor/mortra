"""Exact semantics adapters for target-free theory exploration.

The adapters supply definitions, not conjectures. Finite truth tables certify
only the declared complete model; differential polynomials use the existing
universal identity prover. No sample agreement licenses rewriting.
"""
from __future__ import annotations

from itertools import islice, product
from copy import deepcopy
from functools import lru_cache
import re
import sympy as sp

from math_os_prototype import abstraction_correspondence as ring
from math_os_prototype.finite_generator_problem_dna import (
    FiniteGeneratorSystem, LinearGenerator, discover_action_observable_basis,
    discover_linear_observation_recurrence)
from math_os_prototype.representation_progress import digest


@lru_cache(maxsize=512, typed=True)
def _parsed_literal(value):
    return sp.sympify(value)


def parse_literal(value):
    """Memoize immutable JSON literals, not model observations or equations."""
    numeric = type(value) is int or (type(value) is str and
        re.fullmatch(r"[+-]?[0-9]+(?:/[+-]?[0-9]+)?", value) is not None)
    return _parsed_literal(value) if numeric else sp.sympify(value)


def size(term):
    return 1 + sum(size(c) for c in term.get("args", []))


def term(op, *args, **fields):
    return dict(op=op, args=list(args), **fields)


def recurrence_value(law, n):
    """Initial generic interpreter; the certified parameters are acquired data."""
    if type(n) is not int or n < 0 or not law.get("certificate_passed"):
        raise ValueError("certified recurrence and nonnegative integer required")
    values = [sp.Rational(v) for v in law["initial_values"]]
    weights = [sp.Rational(v) for v in law["coefficients"]]
    order = law["order"]
    if len(weights) != order or len(values) < order:
        raise ValueError("invalid recurrence dimensions")
    if order == 0:
        return sp.S.Zero
    while len(values) <= n:
        values.append(sum(w*v for w, v in zip(weights, values[-order:])))
    return values[n]


def linear_readout(basis, expression, variables):
    polys = [sp.Poly(p, *variables, domain=sp.QQ) for p in [*basis, expression]]
    support = sorted({m for p in polys for m in p.monoms()})
    columns = [sp.Matrix([p.coeff_monomial(m) for m in support]) for p in polys]
    matrix, target = sp.Matrix.hstack(*columns[:-1]), columns[-1]
    if matrix.rank() != matrix.row_join(target).rank():
        return None
    solution, parameters = matrix.gauss_jordan_solve(target)
    solution = solution.subs({p: 0 for p in parameters})
    assert matrix * solution == target
    return [str(x) for x in solution]


class Domain:
    def __init__(self, spec, *, primitive_exclusions=()):
        spec = deepcopy(spec)
        self.spec = spec
        self.kind = spec["kind"]
        self.key = digest(spec)
        self.actions = {}
        self.sensors = {}
        self.premise = None
        if self.kind == "differential_ring":
            if set(spec) != {"kind", "variables", "operations"}:
                raise ValueError("ring signature accepts only variables and operations")
            self.names = list(spec["variables"])
            if not self.names or len(set(self.names)) != len(self.names):
                raise ValueError("distinct nonempty variable signature required")
            if any(not n.isidentifier() or "__d" in n for n in self.names):
                raise ValueError("invalid variable name")
            self.scope = {"kind": "universal_differential_polynomial_identity",
                          "field": "QQ", "domain": self.key,
                          "laws": ring.DERIVATION_LAW}
        elif self.kind == "fold_frames":
            if set(spec) != {"kind", "operations"}:
                raise ValueError("fold signature contains no target observable")
            from math_os_prototype.fold_observable_system import reachable_frames
            from math_os_prototype.rigid_fold_problem_discovery import (
                FOLD_GENERATORS, apply_fold_generator)
            frames = sorted(reachable_frames())
            index = {f: i for i, f in enumerate(frames)}
            for g in FOLD_GENERATORS:
                self.actions[g.symbol] = [index[apply_fold_generator(f, (0, 0, 0), g)[0]]
                                          for f in frames]
            self.sensors = {f"F{i+1}{j+1}": [f[i][j] for f in frames]
                            for i in range(3) for j in range(3)}
            self.models = [[list(row) for row in f] for f in frames]
            self.premise = {"source": "rigid_fold_problem_discovery.apply_fold_generator",
                            "frames": self.models, "closed": True,
                            "omits": ["centre", "panels", "collision", "legality"]}
            self._finite()
        elif self.kind == "finite_table":
            if set(spec) != {"kind", "states", "actions", "sensors", "operations"}:
                raise ValueError("finite signature contains only exact model definitions")
            self.models = spec["states"]
            self.actions = spec["actions"]
            self.sensors = spec["sensors"]
            self._finite()
        else:
            raise ValueError(f"unsupported domain {self.kind!r}")
        allowed = {"add", "mul", "neg", "eq", "and", "not"}
        allowed |= {"diff"} if self.kind == "differential_ring" else {"pull"}
        self.operations = list(spec["operations"])
        if not self.operations or set(self.operations) - allowed:
            raise ValueError("operation outside the exact typed fragment")
        self.primitive_exclusions = frozenset(primitive_exclusions)
        removable = allowed | {"var", "const"} | {"pull:"+g for g in self.actions}
        if self.primitive_exclusions-removable:
            raise ValueError("unknown excluded primitive")
        if self.primitive_exclusions:
            self.key = digest([spec, sorted(self.primitive_exclusions)])
            self.scope = dict(self.scope, domain=self.key, excluded_primitives=sorted(self.primitive_exclusions))
            self.operations = [o for o in self.operations if o not in self.primitive_exclusions]
            self.actions = {g: a for g, a in self.actions.items()
                            if "pull" not in self.primitive_exclusions and "pull:"+g not in self.primitive_exclusions}

    def _finite(self):
        n = len(self.models)
        if not 1 <= n <= 64 or not self.actions or not self.sensors:
            raise ValueError("finite model needs 1..64 states, actions and sensors")
        if len({digest(x) for x in self.models}) != n:
            raise ValueError("duplicate states")
        for targets in self.actions.values():
            if len(targets) != n or any(type(x) is not int or not 0 <= x < n for x in targets):
                raise ValueError("action is not total on the declared finite scope")
        for values in self.sensors.values():
            if len(values) != n or any(sp.sympify(v).is_Rational is not True for v in values):
                raise ValueError("sensor needs one exact rational per state")
        self.names = list(self.sensors)
        self.scope = {"kind": "complete_finite_model", "domain": self.key,
                      "field": "QQ", "states": n, "legality": "not represented"}

    def seeds(self):
        return [p for p in ([term("var", name=n) for n in self.names] + [term("const", value="0"),
                                                               term("const", value="1")]) if p["op"] not in self.primitive_exclusions]

    def parse_literal(self, value):
        return parse_literal(value) if getattr(self, "syntax_cache_enabled", True) else sp.sympify(value)

    def type_of(self, t):
        op, args = t["op"], t.get("args", [])
        arities = {"var": 0, "const": 0, "neg": 1, "diff": 1, "pull": 1,
                   "not": 1, "add": 2, "mul": 2, "eq": 2, "and": 2}
        if op not in arities or len(args) != arities[op]:
            raise ValueError("invalid typed term")
        if op in self.primitive_exclusions:
            raise ValueError("excluded primitive")
        if op not in {"var", "const"} and op not in self.operations:
            raise ValueError("undeclared operation")
        if op == "var" and t["name"] not in self.names:
            raise ValueError("undeclared sensor")
        if op == "const" and self.parse_literal(t["value"]).is_Rational is not True:
            raise ValueError("inexact constant")
        if op == "pull" and t["label"] not in self.actions:
            raise ValueError("undeclared action")
        required = "predicate" if op in {"not", "and"} else "scalar"
        if any(self.type_of(a) != required for a in args):
            raise ValueError("ill-typed operation")
        return "predicate" if op in {"eq", "and", "not"} else "scalar"

    def compose(self, parent, others, *, type_of=None):
        type_of = type_of or self.type_of
        ptype = type_of(parent)
        for op in self.operations:
            if op in {"neg", "diff"} and ptype == "scalar":
                yield term(op, parent)
            elif op == "pull" and ptype == "scalar":
                for label in self.actions:
                    yield term(op, parent, label=label)
            elif op == "not" and ptype == "predicate":
                yield term(op, parent)
            elif op in {"add", "mul", "eq", "and"}:
                needed = "predicate" if op == "and" else "scalar"
                if ptype == needed:
                    for other in others:
                        if type_of(other) == needed:
                            yield term(op, parent, other)
                            yield term(op, other, parent)

    def program(self, t):
        op, a = t["op"], t["args"]
        if op == "var":
            return ring.slot(t["name"])
        if op == "const":
            return {"op": "poly", "coefficients": [t["value"]]}
        if op in {"add", "mul"}:
            return {"op": op, "left": self.program(a[0]), "right": self.program(a[1])}
        if op == "neg":
            return {"op": "scale", "factor": "-1", "child": self.program(a[0])}
        if op == "diff":
            return {"op": "diff", "child": self.program(a[0])}
        raise ValueError("not a differential scalar term")

    def evaluate(self, t, counter=None, *, charge=None, symbolic_sensors=None):
        """Count actual syntax operations, including repeated subexpressions."""
        self.type_of(t)
        if symbolic_sensors is not None:
            if self.kind == "differential_ring" or self.type_of(t) != "scalar":
                raise ValueError("symbolic finite-model evaluation supports scalar polynomials only")
            if set(symbolic_sensors) - set(self.names) or any(
                    len(v) != len(self.models) for v in symbolic_sensors.values()):
                raise ValueError("symbolic sensor scope mismatch")
        if charge is not None:
            if self.kind == "differential_ring":
                charge("symbolic_ast_nodes", size(t))
            else:
                charge("model_node_evaluations", size(t)*len(self.models))
        if counter is not None:
            counter["semantic_nodes"] = counter.get("semantic_nodes", 0) + size(t)
        if self.kind == "differential_ring":
            if self.type_of(t) == "scalar":
                return sp.expand(ring.differential_expression(self.program(t)))
            if t["op"] == "eq":
                return sp.Eq(self.evaluate(t["args"][0]), self.evaluate(t["args"][1]))
            args = [self.evaluate(a) for a in t["args"]]
            return sp.Not(args[0]) if t["op"] == "not" else sp.And(*args)
        def ev(node):
            op, a = node["op"], node["args"]
            if op == "var":
                if symbolic_sensors is not None and node["name"] in symbolic_sensors:
                    return tuple(symbolic_sensors[node["name"]])
                return tuple(sp.Rational(str(v)) for v in self.sensors[node["name"]])
            if op == "const":
                return (sp.Rational(node["value"]),) * len(self.models)
            values = [ev(x) for x in a]
            if op == "pull":
                return tuple(values[0][i] for i in self.actions[node["label"]])
            if op == "neg":
                return tuple(-x for x in values[0])
            if op == "not":
                return tuple(not x for x in values[0])
            fn = {"add": lambda x, y: x+y, "mul": lambda x, y: x*y,
                  "eq": lambda x, y: x == y, "and": lambda x, y: bool(x and y)}[op]
            return tuple(fn(x, y) for x, y in zip(*values))
        return ev(t)

    def semantic_key(self, value):
        if isinstance(value, tuple):
            return digest([str(x) for x in value])
        return sp.srepr(value)

    def probe(self, t):
        value = self.evaluate(t)
        if self.kind != "differential_ring":
            return str(value[:2])
        return str([value.subs({s: v for s in value.free_symbols}) for v in (0, 1)])

    def settle(self, left, right, kind="equality"):
        """A cheap probe proposes; this independent complete check settles."""
        if self.type_of(left) != self.type_of(right):
            raise ValueError("conjecture type mismatch")
        if self.kind == "differential_ring":
            if kind != "equality" or self.type_of(left) != "scalar":
                return {"status": "unknown", "reason": "no universal logical prover"}
            proof = ring.prove_identity(self.program(left), self.program(right))
            if proof["proved"]:
                return {"status": "proved", "certificate": proof, "scope": self.scope}
            residual = self.evaluate(left) - self.evaluate(right)
            symbols = sorted(residual.free_symbols, key=str)
            # A jet assignment extends to rational polynomials via Taylor coefficients.
            for values in islice(product(range(3), repeat=len(symbols)), 4096):
                assignment = dict(zip(symbols, values))
                if residual.subs(assignment) != 0:
                    return {"status": "disproved", "counterexample": {
                        "jets_at_zero": {str(s): v for s, v in assignment.items()},
                        "left": str(self.evaluate(left).subs(assignment)),
                        "right": str(self.evaluate(right).subs(assignment)),
                        "model": "QQ[x], jets realized by sum a_k*x**k/k!"}}
            return {"status": "unknown", "reason": "counterexample budget exhausted"}
        lvals, rvals = self.evaluate(left), self.evaluate(right)
        truth = [(not x or y) if kind == "implication" else x == y
                 for x, y in zip(lvals, rvals)]
        if all(truth):
            return {"status": "proved", "scope": self.scope, "certificate": {
                "method": "complete finite enumeration", "checks": len(truth),
                "left": [str(x) for x in lvals], "right": [str(x) for x in rvals]}}
        i = truth.index(False)
        return {"status": "disproved", "counterexample": {
            "state_index": i, "state": self.models[i], "left": str(lvals[i]),
            "right": str(rvals[i])}}

    def linear_system(self):
        if not self.actions:
            return None
        n = len(self.models)
        generators = []
        for label, targets in self.actions.items():
            rows = [[0]*n for _ in range(n)]
            for source, target in enumerate(targets):
                rows[target][source] = 1
            generators.append(LinearGenerator.from_rows(label, rows))
        return FiniteGeneratorSystem(self.key, tuple(f"s{i}" for i in range(n)),
                                     tuple(generators), (1,) + (0,)*(n-1))

    def acquire(self, t, dimension_cap):
        system = self.linear_system()
        values = self.evaluate(t)
        expression = sum(v*x for v, x in zip(values, system.variables))
        found = discover_action_observable_basis(system, [expression],
                                                 maximum_dimension=dimension_cap)
        basis = found["basis"]
        readout = linear_readout(basis, expression, system.variables)
        assert readout is not None and found["certificate_passed"]
        return {"basis": [str(b) for b in basis], "readout": readout,
                "action_matrices": {g: [[str(x) for x in row] for row in m.tolist()]
                                    for g, m in zip(found["generator_names"], found["action_matrices"])},
                "dimension": len(basis), "ambient_dimension": len(values),
                "certificate": {"method": "discover_action_observable_basis",
                                "residuals": [[str(x) for x in r] for r in found["identity_residuals"]],
                                "all_zero": all(all(x == 0 for x in r) for r in found["identity_residuals"])},
            "scope": deepcopy(self.scope), "system_key": self.key,
                "omits": ["collision", "legality"], "semantic_type": "functions on declared finite states"}

    def recurrence(self, representation, label):
        if representation["system_key"] != self.key or representation["scope"] != self.scope:
            raise ValueError("representation outside certificate scope")
        system = self.linear_system()
        basis = [sp.sympify(x) for x in representation["basis"]]
        initial = sp.Matrix([b.subs(dict(zip(system.variables, system.seed))) for b in basis])
        matrix = sp.Matrix(representation["action_matrices"][label])
        readout = sp.Matrix([representation["readout"]])
        found = discover_linear_observation_recurrence(matrix, initial, readout)
        result = found.to_dict()
        result.update(label=label, scope={"kind": "all_repeats", "initial_state_index": 0,
                                         "domain": self.key, "parent": self.scope})
        return result
