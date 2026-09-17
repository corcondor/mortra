"""Task-independent enumerated producer index for the relational geometry DSL.

Programs of certified primitives over generic inputs ``p0, p1, p2`` are
enumerated bottom-up to a declared depth with observational equivalence at
digest-seeded floating-point instances, and each distinct program is indexed by
the atom patterns over ``v`` and the inputs that vanish at every instance.
Floating point is only a filter: a program is used for a pattern only after
certify_entry decides that pattern exactly in the rational function field over
QQ, with non-vacuity shown by exact execution at digest-derived rational inputs.
No task, goal, witness or solver output is read.
"""
from __future__ import annotations

from collections import Counter
from functools import lru_cache
from hashlib import sha256
from itertools import product
import time

import numpy as np
import sympy as sp

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype.representation_progress import digest

INPUTS = ("p0", "p1", "p2")
PREDICATES = ("coll", "perp", "para", "cong", "cyclic", "midp", "eqangle")
SPEC = {"inputs": list(INPUTS), "predicates": list(PREDICATES), "max_depth": 2, "instances": 8,
        "level_two": "exactly one argument from the previous level, the others inputs",
        "version": 2}


def _instances(count):
    seed = int(sha256(digest(SPEC).encode()).hexdigest()[:8], 16)
    rng = np.random.default_rng(seed)
    return {n: rng.normal(size=(count, 2))*3 for n in INPUTS}


def _float_primitives():
    functions = {}
    for family, contract in rdsl.primitive_contracts().items():
        params = contract["params"]
        symbols = [sp.Symbol(p+a, real=True) for p in params for a in ("x", "y")]
        table = {str(s): s for s in symbols}
        expressions = [gc.parse(e, table) for e in contract["witness"]["y"]]
        functions[family] = (len(params), sp.lambdify(symbols, expressions, "numpy"))
    return functions


def _patterns():
    names = ("v",)+INPUTS
    seen, result = set(), []
    for predicate in PREDICATES:
        arity = rdsl.PREDICATE_ARITIES[predicate]
        for args in product(names, repeat=arity):
            if "v" not in args:
                continue
            key = rdsl.canonical_atom(predicate, args)
            if key not in seen:
                seen.add(key)
                result.append(key)
    return result


def _pattern_function(predicate, args):
    polynomial = rdsl._generic_polynomial(predicate, tuple(args))
    names = list(dict.fromkeys(args))
    symbols = [sp.Symbol(n+a) for n in names for a in ("x", "y")]
    return names, sp.lambdify(symbols, polynomial, "numpy")


def _evaluate_pattern(function, names, points):
    arrays = []
    for n in names:
        arrays.extend((points[n][..., 0], points[n][..., 1]))
    return function(*arrays)


def acquire_index(*, max_depth=2, stats=None):
    """Enumerate distinct programs and index each by the atom patterns it satisfies at every float instance.

    The index is a proposal structure only. A program is used for a pattern only
    after certify_entry decides that pattern exactly (see ContractIndex.certified).
    """
    stats = stats if stats is not None else Counter()
    started = time.perf_counter()
    count = SPEC["instances"]
    base = _instances(count)
    primitives = _float_primitives()
    scale = max(float(np.abs(v).max()) for v in base.values())
    known = {tuple(np.round(base[n].ravel()/scale, 7)): n for n in INPUTS}
    values = {n: base[n] for n in INPUTS}
    programs, order, previous = {}, [], []
    for depth in range(1, max_depth+1):
        current = []
        for family, (arity, function) in primitives.items():
            if depth == 1:
                bindings = product(INPUTS, repeat=arity)
            else:
                bindings = (rest[:position]+(inner,)+rest[position:] for position in range(arity)
                            for inner in previous for rest in product(INPUTS, repeat=arity-1))
            for args in bindings:
                if rdsl.binding_returns_input(family, args):
                    continue
                arrays = []
                for a in args:
                    arrays.extend((values[a][:, 0], values[a][:, 1]))
                stats["float_evaluations"] += 1
                with np.errstate(all="ignore"):
                    x, y = function(*arrays)
                xy = np.stack([np.broadcast_to(x, (count,)), np.broadcast_to(y, (count,))], axis=1).astype(float)
                if not np.all(np.isfinite(xy)) or np.abs(xy).max() > 1e6:
                    continue
                key = tuple(np.round(xy.ravel()/scale, 7))
                if key in known:
                    continue
                name = f"q{len(programs)}"
                known[key] = name
                programs[name] = {"prim": family, "args": list(args)}
                values[name] = xy
                current.append(name)
                order.append(name)
        previous = current
    patterns = []
    probe = np.random.default_rng(1).normal(size=(count, 2))*3
    stacked = np.stack([values[n] for n in order])
    magnitude = np.maximum(1.0, np.abs(stacked).max(axis=(1, 2)))**4
    membership = {}
    for predicate, args in _patterns():
        names, function = _pattern_function(predicate, args)
        with np.errstate(all="ignore"):
            if np.allclose(_evaluate_pattern(function, names, dict(base, v=probe)), 0, atol=1e-9):
                stats["trivial_patterns"] += 1
                continue
            residual = np.broadcast_to(_evaluate_pattern(function, names, dict(base, v=stacked)), stacked.shape[:2])
        hits = np.nonzero(np.all(np.abs(residual) <= 1e-7*magnitude[:, None], axis=1))[0]
        if len(hits):
            membership[(predicate, args)] = [int(i) for i in hits]
            patterns.append((predicate, args))
    flat = [_flatten(n, programs) for n in order]
    stats["distinct_programs"] = len(flat)
    stats["indexed_patterns"] = len(membership)
    stats["index_seconds"] = time.perf_counter()-started
    return ContractIndex(flat, membership, dict(stats))


class ContractIndex:
    """Programs indexed by float-filtered atom patterns; exact certification on demand, cached."""

    def __init__(self, programs, membership, costs):
        self.programs = programs
        self.membership = {k: set(v) for k, v in membership.items()}
        self.ordered = {k: sorted(v, key=lambda i: (len(programs[i]["steps"]), i)) for k, v in membership.items()}
        self.costs = Counter(costs)
        self.certificates = {}

    def candidates(self, patterns):
        """Program ids satisfying every pattern at the float instances, smallest first."""
        patterns = list(patterns)
        if any(p not in self.membership for p in patterns):
            return []
        first = min(patterns, key=lambda p: len(self.membership[p]))
        return [i for i in self.ordered[first] if all(i in self.membership[p] for p in patterns)]

    def certified(self, index, pattern):
        key = (index, pattern)
        if key not in self.certificates:
            self.costs["exact_certifications"] += 1
            self.certificates[key] = certify_entry(pattern[0], pattern[1], self.programs[index])
            if self.certificates[key] is None:
                self.costs["float_candidates_refused_exactly"] += 1
        return self.certificates[key]

    def digest(self):
        return digest([self.programs, sorted([[k[0], list(k[1]), sorted(v)] for k, v in self.membership.items()])])


def _flatten(name, programs):
    steps, memo = [], {}
    def visit(n):
        if n in INPUTS:
            return n
        if n in memo:
            return memo[n]
        program = programs[n]
        args = [visit(a) for a in program["args"]]
        out = f"s{len(steps)}"
        steps.append({"out": out, "prim": program["prim"], "args": args})
        memo[n] = out
        return out
    result = visit(name)
    return {"params": list(INPUTS), "steps": steps, "result": result}


@lru_cache(maxsize=None)
def _kernel_rational_maps(family):
    """Kernel witness and guard expressions of a primitive as rational functions over QQ."""
    contract = rdsl.primitive_contracts()[family]
    names = [q+a for q in contract["params"] for a in ("x", "y")]
    symbols = {n: sp.Symbol(n, real=True) for n in names}
    field, *_ = sp.field(",".join(names), sp.QQ)
    def convert(expression):
        value = gc.parse(expression, symbols).subs({symbols[n]: sp.Symbol(n) for n in names}, simultaneous=True)
        return field.from_expr(value)
    return (tuple(convert(e) for e in contract["witness"]["y"]), tuple(convert(g) for g in contract["guards"]))


@lru_cache(maxsize=None)
def _pattern_rational_map(predicate, args):
    polynomial = rdsl._generic_polynomial(predicate, tuple(args))
    names = [n+a for n in dict.fromkeys(args) for a in ("x", "y")]
    field, *_ = sp.field(",".join(names), sp.QQ)
    return names, field.from_expr(polynomial)


TERM_BUDGET = 20000


class CertificationBudgetExceeded(ArithmeticError):
    """Exact certification stopped at the declared size bound: the atom is undecided, never accepted."""


def _check_size(element):
    if len(element.numer)+len(element.denom) > TERM_BUDGET:
        raise CertificationBudgetExceeded(f"rational function exceeds {TERM_BUDGET} terms")
    return element


def _evaluate(element, values, target):
    """Evaluate a rational function (in the generators of its own field) at target field elements."""
    def polynomial(poly):
        total = target.zero
        for monomial, coefficient in poly.terms():
            term = target.from_expr(sp.Rational(coefficient))
            for value, exponent in zip(values, monomial):
                if exponent:
                    term = _check_size(term*value**exponent)
            total = _check_size(total+term)
        return total
    denominator = polynomial(element.denom)
    if denominator == target.zero:
        raise ZeroDivisionError("rational map undefined on the generic inputs")
    return _check_size(polynomial(element.numer)/denominator)


def symbolic_output(program):
    """Exact rational witnesses of every program point in QQ(input coordinates), and substituted guards."""
    names = [p+a for p in program["params"] for a in ("x", "y")]
    target, *generators = sp.field(",".join(names), sp.QQ)
    coordinates = {p: (generators[2*i], generators[2*i+1]) for i, p in enumerate(program["params"])}
    guards = []
    for step in program["steps"]:
        witness, step_guards = _kernel_rational_maps(step["prim"])
        values = [c for arg in step["args"] for c in coordinates[arg]]
        coordinates[step["out"]] = tuple(_evaluate(w, values, target) for w in witness)
        guards.extend(_evaluate(g, values, target) for g in step_guards)
    return target, coordinates, guards


def certify_entry(predicate, args, program, stats=None):
    """Exact decision: the pattern polynomial vanishes identically at the program output.

    Computation is in the rational function field QQ(inputs); a guard that is the
    zero rational function (or an undefined witness) refuses, and non-vacuity is
    shown by exact execution at digest-derived rational inputs.
    """
    started = time.perf_counter()
    if stats is not None:
        stats["exact_certifications"] += 1
    try:
        target, coordinates, guards = symbolic_output(program)
    except ZeroDivisionError:
        return None
    except CertificationBudgetExceeded:
        if stats is not None:
            stats["certification_budget_exceeded"] += 1
        return None
    if any(g == target.zero for g in guards):
        return None
    names, pattern = _pattern_rational_map(predicate, tuple(args))
    values = []
    for name in names:
        point, axis = name[:-1], 0 if name[-1] == "x" else 1
        source = coordinates[program["result"]] if point == "v" else coordinates[point]
        values.append(source[axis])
    try:
        if _evaluate(pattern, values, target) != target.zero:
            return None
    except CertificationBudgetExceeded:
        if stats is not None:
            stats["certification_budget_exceeded"] += 1
        return None
    witness = rdsl.nonvacuity_witness({"steps": program["steps"], "result": [program["result"]]}, list(program["params"]))
    if witness is None:
        return None
    if stats is not None:
        stats["certification_seconds"] = stats.get("certification_seconds", 0)+time.perf_counter()-started
    return {"method": "rational function field QQ(inputs): kernel witnesses substituted into the lowered pattern polynomial",
            "guards_nonzero_as_rational_functions": True, "nonvacuity": witness,
            "concludes": "pattern polynomial vanishes wherever every step executes; prerequisites not concluded"}
