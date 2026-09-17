"""Relational geometry DSL: relation terms, contracts with obligations, certified metarules.

The geometric predicates and their polynomial meaning are unchanged: every atom
is lowered by ``geometry_semantic_dsl.lower`` and its prerequisites come from
``geometry_semantic_dsl.conditions``. This module adds the language that combines
them (docs/research/GEOMETRY-RELATIONAL-DSL-20260917.md):

* relation terms: atom, conjunction, hiding, relation variables;
* primitive operation contracts read from the exact kernel certificates;
* argument symmetries used only after an exact polynomial check;
* instances of the MR-transfer metarule used only after an exact identity
  certificate, replayed by ``geometry_contracts.exact_zero``;
* exact instance execution and a non-vacuity check for guard sets.

Nothing here is task-specific and nothing is accepted numerically.
"""
from __future__ import annotations

from copy import deepcopy
from functools import lru_cache
from hashlib import sha256
from itertools import permutations
import re

import sympy as sp

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_semantic_dsl as dsl
from math_os_prototype.representation_progress import digest

EQUALITY_PREDICATES = {"midp": 3, "coll": 3, "perp": 4, "para": 4, "cyclic": 4, "cong": 4, "eqangle": 8}
NONZERO_PREDICATES = {"diff": 2, "ncoll": 3, "npara": 4}
PREDICATE_ARITIES = {**EQUALITY_PREDICATES, **NONZERO_PREDICATES}
VARIABLE = re.compile(r"[A-Za-z][A-Za-z0-9_]*")


# ---------------------------------------------------------------------------
# Relation terms
# ---------------------------------------------------------------------------

def atom(predicate, *arguments):
    return {"atom": predicate, "args": list(arguments)}


def conj(*parts):
    return {"and": [deepcopy(p) for p in parts]}


def exists(variables, body):
    return {"exists": list(variables), "body": deepcopy(body)}


def rvar(name, *arguments):
    return {"rvar": name, "args": list(arguments)}


def validate_relation(term, relation_arities=None):
    """Check the four relation rules; relation variables need a declared arity."""
    relation_arities = relation_arities or {}
    if not isinstance(term, dict):
        raise ValueError("relation term must be a mapping")
    if set(term) == {"atom", "args"}:
        if term["atom"] not in PREDICATE_ARITIES or len(term["args"]) != PREDICATE_ARITIES[term["atom"]]:
            raise ValueError("unknown predicate or arity")
        _check_variables(term["args"])
    elif set(term) == {"and"}:
        if not isinstance(term["and"], list):
            raise ValueError("conjunction needs a list")
        for part in term["and"]:
            validate_relation(part, relation_arities)
    elif set(term) == {"exists", "body"}:
        _check_variables(term["exists"])
        if len(set(term["exists"])) != len(term["exists"]):
            raise ValueError("repeated hidden variable")
        validate_relation(term["body"], relation_arities)
    elif set(term) == {"rvar", "args"}:
        name = term["rvar"]
        if name not in relation_arities or len(term["args"]) != relation_arities[name]:
            raise ValueError("undeclared relation variable or arity")
        _check_variables(term["args"])
    else:
        raise ValueError("outside the relation grammar")


def _check_variables(names):
    if not isinstance(names, list) or any(not isinstance(n, str) or not VARIABLE.fullmatch(n) for n in names):
        raise ValueError("invalid point variable")


def free_variables(term):
    if "atom" in term or "rvar" in term:
        return set(term["args"])
    if "and" in term:
        return set().union(*(free_variables(p) for p in term["and"]))
    return free_variables(term["body"])-set(term["exists"])


def rename_relation(term, mapping):
    """Capture-avoiding renaming of free point variables."""
    if "atom" in term:
        return atom(term["atom"], *(mapping.get(a, a) for a in term["args"]))
    if "rvar" in term:
        return rvar(term["rvar"], *(mapping.get(a, a) for a in term["args"]))
    if "and" in term:
        return {"and": [rename_relation(p, mapping) for p in term["and"]]}
    bound = list(term["exists"])
    inner = {k: v for k, v in mapping.items() if k not in bound}
    occupied = set(inner.values()) | free_variables(term["body"]) | set(inner)
    fresh = {}
    for name in bound:
        if name in set(inner.values()):
            index = 0
            while f"{name}_{index}" in occupied:
                index += 1
            fresh[name] = f"{name}_{index}"
            occupied.add(fresh[name])
    body = rename_relation(term["body"], {**inner, **fresh})
    return exists([fresh.get(n, n) for n in bound], body)


def instantiate_relation(term, arguments, bound=frozenset()):
    """Beta-reduce relation variables: arguments maps name -> {"lambda": [v...], "body": R}.

    A closure may mention fixed point names. It is refused if one of them would be
    captured by a hiding binder on the path to the relation variable.
    """
    if "rvar" in term:
        closure = arguments.get(term["rvar"])
        if closure is None:
            return deepcopy(term)
        if len(closure["lambda"]) != len(term["args"]):
            raise ValueError("relation argument arity mismatch")
        if (free_variables(closure["body"])-set(closure["lambda"])) & bound:
            raise ValueError("relation argument would be captured by a hidden variable")
        return rename_relation(closure["body"], dict(zip(closure["lambda"], term["args"], strict=True)))
    if "atom" in term:
        return deepcopy(term)
    if "and" in term:
        return {"and": [instantiate_relation(p, arguments, bound) for p in term["and"]]}
    return exists(term["exists"], instantiate_relation(term["body"], arguments, bound | set(term["exists"])))


def atoms_of(term):
    """Flatten an existential-free, variable-free relation into (predicate, args) tuples."""
    if "atom" in term:
        return ((term["atom"], tuple(term["args"])),)
    if "and" in term:
        return tuple(a for p in term["and"] for a in atoms_of(p))
    raise ValueError("relation contains hiding or relation variables")


# ---------------------------------------------------------------------------
# Exact lowering on generic and on rational coordinates
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _generic_polynomial(predicate, arguments):
    """dsl.lower on symbolic coordinates, expanded instead of factored (same polynomial)."""
    if predicate not in PREDICATE_ARITIES or len(arguments) != PREDICATE_ARITIES[predicate]:
        raise ValueError("unsupported exact predicate or arity")
    elaborator = gc._JGEXElaborator()
    elaborator.coordinates.update({n: (sp.Symbol(n+"x"), sp.Symbol(n+"y")) for n in dict.fromkeys(arguments)})
    if predicate == "diff":
        return sp.expand(elaborator._distance_squared(*arguments))
    channel = {"ncoll": "coll", "npara": "para"}.get(predicate, predicate)
    return gc._JGEXElaborator.goal(elaborator, channel, tuple(arguments), factor_result=False)


def value_at(predicate, arguments, coordinates):
    """Exact value of the lowered predicate at rational coordinates."""
    elaborator = gc._JGEXElaborator()
    elaborator.coordinates.update({n: tuple(sp.Rational(v) for v in coordinates[n]) for n in dict.fromkeys(arguments)})
    return sp.cancel(dsl.lower(elaborator, predicate, tuple(arguments)))


def polynomial_holds(predicate, arguments, coordinates):
    """Relaxed truth: the defining polynomial vanishes (equalities) or not (nonzero predicates)."""
    value = value_at(predicate, arguments, coordinates)
    return value != 0 if predicate in NONZERO_PREDICATES else value == 0


def objects_of(coordinates):
    return {n: {"type": "Point", "coordinates": [str(sp.Rational(v)) for v in xy]} for n, xy in coordinates.items()}


def atom_holds(predicate, arguments, coordinates, stats=None):
    """Strict truth with geometric prerequisites, by the existing certify_atom."""
    return dsl.certify_atom(predicate, tuple(arguments), objects_of(coordinates),
                            provenance="relational_instance", stats=stats) is not None


# ---------------------------------------------------------------------------
# Certified argument symmetries
# ---------------------------------------------------------------------------

def _candidate_generators(predicate):
    n = PREDICATE_ARITIES[predicate]
    swap = lambda i, j: tuple(j if k == i else i if k == j else k for k in range(n))
    if predicate in {"coll", "ncoll", "cyclic", "diff"}:
        return tuple(swap(i, i+1) for i in range(n-1))
    if predicate in {"perp", "para", "cong", "npara"}:
        return (swap(0, 1), swap(2, 3), (2, 3, 0, 1))
    if predicate == "midp":
        return (swap(1, 2),)
    return ()


def _closure(generators, n):
    identity = tuple(range(n))
    group, frontier = {identity}, [identity]
    while frontier:
        current = frontier.pop()
        for g in generators:
            composed = tuple(current[g[k]] for k in range(n))
            if composed not in group:
                group.add(composed)
                frontier.append(composed)
    return tuple(sorted(group))


def _ratio_is_nonzero_rational(permuted, original):
    if original == 0:
        return permuted == 0
    ratio = sp.cancel(permuted/original)
    return ratio.is_Rational is True and ratio != 0


@lru_cache(maxsize=None)
def certified_symmetry_group(predicate):
    """Position permutations under which the lowered polynomial changes only by a nonzero rational factor."""
    n = PREDICATE_ARITIES[predicate]
    slots = tuple(f"s{i}" for i in range(n))
    original = _generic_polynomial(predicate, slots)
    def verified(perm):
        return _ratio_is_nonzero_rational(_generic_polynomial(predicate, tuple(slots[perm[k]] for k in range(n))), original)
    if predicate == "eqangle":
        from worker.backend.geometry_proof_hypergraph import _eqangle_argument_orbit
        index = {s: i for i, s in enumerate(slots)}
        candidates = {tuple(index[s] for s in row) for row in _eqangle_argument_orbit(slots)}
        return tuple(sorted(p for p in candidates if verified(p)))
    generators = tuple(g for g in _candidate_generators(predicate) if verified(g))
    return _closure(generators, n)


def canonical_atom(predicate, arguments):
    arguments = tuple(arguments)
    group = certified_symmetry_group(predicate)
    return (predicate, min(tuple(arguments[p[k]] for k in range(len(arguments))) for p in group))


def symmetry_certificate():
    return {p: {"permutations": [list(g) for g in certified_symmetry_group(p)],
                "method": "generic lowered polynomial equal up to a nonzero rational constant"}
            for p in PREDICATE_ARITIES}


# ---------------------------------------------------------------------------
# Primitive contracts from the exact kernel
# ---------------------------------------------------------------------------

@lru_cache(maxsize=None)
def _kernel_schemas():
    from math_os_prototype.theory_geometry_feedback import GeometryLibrary
    return GeometryLibrary().schemas


@lru_cache(maxsize=None)
def primitive_contracts():
    """family -> contract; post and guards are copied from kernel certificates, not written by hand."""
    contracts = {}
    for family, cert in _kernel_schemas().items():
        params = [p["name"] for p in cert["typed_parameters"]]
        output = cert["output"]
        rename = lambda n: "y" if n == output else n
        guards = [factor for g in cert["applicability"].get("sequential_nonzero_polynomials", [])
                  for factor in g["parent_factors"]]
        contracts[family] = {
            "family": family, "params": params, "output": "y",
            "pre": [atom(p, *a) for p, a in dsl.requirements(family, params)],
            "guards": guards,
            "post": [atom(r["predicate"], *map(rename, r["points"])) for r in cert["guaranteed_relation"]],
            "kernel_certificate": cert["id"], "witness": {"y": cert["witness"][output]},
        }
    return contracts


@lru_cache(maxsize=None)
def family_symmetry_group(family):
    """Input permutations that leave a primitive's kernel witness, guard factors and requirements unchanged.

    Used only to avoid executing the same construction twice under a reordered
    binding. Every permutation is checked exactly; none is assumed.
    """
    contract = primitive_contracts()[family]
    params = contract["params"]
    n = len(params)
    symbols = {p+a: sp.Symbol(p+a, real=True) for p in params for a in ("x", "y")}
    witness = [gc.parse(e, symbols) for e in contract["witness"]["y"]]
    guards = {f for g in contract["guards"] for f in gc.factors(gc.parse(g, symbols))}
    requirements = {canonical_atom(r["atom"], tuple(r["args"])) for r in contract["pre"]}
    group = []
    for perm in permutations(range(n)):
        rename = {params[k]: params[perm[k]] for k in range(n)}
        substitution = {symbols[p+a]: symbols[rename[p]+a] for p in params for a in ("x", "y")}
        moved = [sp.cancel(w.subs(substitution, simultaneous=True)-original)
                 for w, original in zip(witness, witness, strict=True)]
        if any(m != 0 for m in moved):
            continue
        moved_guards = {f for g in contract["guards"]
                        for f in gc.factors(gc.parse(g, symbols).subs(substitution, simultaneous=True))}
        moved_requirements = {canonical_atom(r["atom"], tuple(rename[a] for a in r["args"])) for r in contract["pre"]}
        if moved_guards == guards and moved_requirements == requirements:
            group.append(perm)
    return tuple(group)


@lru_cache(maxsize=None)
def _returns_input_pattern(family, pattern):
    contract = primitive_contracts()[family]
    params = contract["params"]
    representative = {p: params[pattern[i]] for i, p in enumerate(params)}
    symbols = {p+a: sp.Symbol(p+a, real=True) for p in params for a in ("x", "y")}
    substitution = {symbols[p+a]: symbols[representative[p]+a] for p in params for a in ("x", "y")}
    witness = [sp.cancel(gc.parse(e, symbols).subs(substitution, simultaneous=True)) for e in contract["witness"]["y"]]
    if any(w.has(sp.zoo, sp.nan) for w in witness):
        return True
    for p in set(representative.values()):
        if all(sp.cancel(w-symbols[p+a]) == 0 for w, a in zip(witness, ("x", "y"), strict=True)):
            return True
    return False


def binding_returns_input(family, arguments):
    """True when the repeated-argument pattern makes the exact witness equal an input (or undefined) identically.

    Such a step cannot create a new point for any input coordinates, so it is
    excluded before an application is charged. Decided by exact substitution.
    """
    first = {}
    pattern = tuple(first.setdefault(a, i) for i, a in enumerate(arguments))
    if len(set(arguments)) == len(arguments):
        return False
    return _returns_input_pattern(family, pattern)


def canonical_step(family, arguments):
    group = family_symmetry_group(family)
    arguments = tuple(arguments)
    return (family, min(tuple(arguments[p[k]] for k in range(len(arguments))) for p in group))


# ---------------------------------------------------------------------------
# Exact instance execution
# ---------------------------------------------------------------------------

def execute_primitive(family, inputs, coordinates, stats=None):
    """Execute one certified primitive at exact rational coordinates.

    Mirrors the refusals of SemanticGeometryDomain.apply for primitives:
    requirement atoms, kernel guards, undefined witnesses. Returns (xy, None)
    or (None, reason). Duplicate outputs are decided by the caller.
    """
    contract = primitive_contracts()[family]
    if len(inputs) != len(contract["params"]):
        return None, "arity"
    mapping = dict(zip(contract["params"], inputs, strict=True))
    for requirement in contract["pre"]:
        args = [mapping[a] for a in requirement["args"]]
        if not atom_holds(requirement["atom"], args, coordinates, stats):
            return None, "unproved_applicability:"+requirement["atom"]
    symbols = {n+a: sp.Symbol(n+a, real=True) for n in contract["params"] for a in ("x", "y")}
    replacement = {symbols[n+a]: sp.Rational(coordinates[v][i])
                   for n, v in mapping.items() for i, a in enumerate(("x", "y"))}
    for guard in contract["guards"]:
        if stats is not None:
            stats["guard_checks"] += 1
        if sp.cancel(gc.parse(guard, symbols).subs(replacement, simultaneous=True)) == 0:
            return None, "unproved_applicability:contract_nonzero"
    elaborator = gc._JGEXElaborator()
    elaborator.coordinates.update({n: tuple(sp.Rational(v) for v in coordinates[n]) for n in inputs})
    dsl.FRAGMENT.primitive(elaborator, family, "__out", list(inputs))
    if any(sp.cancel(d) == 0 for d in elaborator.denominators):
        return None, "primitive_degeneracy"
    xy = tuple(sp.cancel(v) for v in elaborator.coordinates["__out"])
    if any(not v.is_Rational for v in xy):
        return None, "undefined_exact_witness"
    return xy, None


def replay_program(program, inputs):
    """Re-execute a program from input coordinates only; returns output coordinates by name."""
    coordinates = {n: tuple(sp.Rational(v) for v in xy) for n, xy in inputs.items()}
    for step in program["steps"]:
        xy, reason = execute_primitive(step["prim"], step["args"], coordinates)
        if xy is None:
            raise ValueError("replay refused: "+reason)
        coordinates[step["out"]] = xy
    return coordinates


# ---------------------------------------------------------------------------
# Composition calculus over primitive programs
# ---------------------------------------------------------------------------

def compose(program, *, pre=(), lemmas=None):
    """Derive pre/post/obligations for a primitive program.

    A step requirement is discharged when an atom equal modulo certified
    symmetries is in the context; otherwise it becomes an open obligation.
    Requirements refuted syntactically (a nonzero predicate on repeated
    arguments whose polynomial is identically zero) refuse the composition.
    Kernel guards stay as sequential obligations; they are decided exactly at an
    instance or by the non-vacuity check, never assumed.
    """
    contracts = primitive_contracts()
    context = {canonical_atom(p, a) for p, a in (atoms_of(conj(*pre)) if pre else ())}
    obligations, post, refuted = [], [], []
    for index, step in enumerate(program["steps"]):
        contract = contracts[step["prim"]]
        mapping = dict(zip(contract["params"], step["args"], strict=True), y=step["out"])
        for requirement in contract["pre"]:
            args = tuple(mapping[a] for a in requirement["args"])
            if _generic_polynomial(requirement["atom"], args) == 0:
                refuted.append({"step": index, "condition": atom(requirement["atom"], *args)})
                continue
            key = canonical_atom(requirement["atom"], args)
            justification = {"kind": "context"} if key in context else None
            obligations.append({"step": index, "condition": atom(requirement["atom"], *args),
                                "status": "discharged" if justification else "open",
                                "justification": justification})
        for guard in contract["guards"]:
            obligations.append({"step": index, "condition": {"nonzero": guard, "binding": mapping},
                                "status": "open", "justification": None})
        for relation in contract["post"]:
            args = tuple(mapping[a] for a in relation["args"])
            context.add(canonical_atom(relation["atom"], args))
            post.append(atom(relation["atom"], *args))
    locals_ = [s["out"] for s in program["steps"] if s["out"] not in program["result"]]
    body = conj(*post)
    return {"pre": [deepcopy(p) for p in pre], "post": exists(locals_, body) if locals_ else body,
            "obligations": obligations, "refuted": refuted,
            "existence": "refused" if refuted else "open"}


def _sample_coordinates(seed_material, names, index):
    stream = sha256(f"{seed_material}:{index}".encode()).digest()
    while len(stream) < 4*len(names):
        stream += sha256(stream).digest()
    values = [int.from_bytes(stream[2*i:2*i+2], "big") % 195-97 for i in range(2*len(names))]
    return {n: (sp.Integer(values[2*i]), sp.Integer(values[2*i+1])) for i, n in enumerate(names)}


def nonvacuity_witness(program, params, *, samples=8):
    """Exhibit rational inputs at which every step executes; None if none of the samples does.

    A successful exact execution shows every guard polynomial is not identically
    zero on the free input space, hence the domain is dense. Samples come from the
    program digest, not from any task. Failure is "not shown", not "vacuous".
    """
    material = digest(program)
    for index in range(samples):
        coordinates = _sample_coordinates(material, params, index)
        if len({coordinates[n] for n in params}) != len(params):
            continue
        try:
            values = replay_program(program, coordinates)
        except ValueError:
            continue
        outputs = [values[s["out"]] for s in program["steps"]]
        if len(set(outputs)) != len(outputs) or set(outputs) & {coordinates[n] for n in params}:
            continue
        return {"sample": index, "inputs": {n: [str(v) for v in xy] for n, xy in coordinates.items()},
                "method": "exact execution at digest-derived rational inputs"}
    return None


# ---------------------------------------------------------------------------
# MR-transfer:  alpha(y) <- alpha(x1) & alpha(x2) & S(y, x1, x2) & diff(x1, x2)
# ---------------------------------------------------------------------------

def _pattern(arguments, distinguished):
    """Abstract non-distinguished point names to slot names, preserving sharing."""
    slots, pattern = {}, []
    for a in arguments:
        if a == distinguished:
            pattern.append("v")
        else:
            slots.setdefault(a, f"k{len(slots)}")
            pattern.append(slots[a])
    return tuple(pattern), slots


@lru_cache(maxsize=None)
def transfer_shapes():
    """S shapes read from primitive posts: atoms relating y to two distinct inputs, affine in y.

    Returns {(predicate, roles): certificate} where roles place "y", "x1", "x2".
    The parametrization y = x0 + t*d is certified exactly: S vanishes identically
    on it, S is affine in y, and |grad_y S|^2 is a nonzero rational multiple of
    |x1 - x2|^2, so under diff(x1, x2) the line is the whole solution set.
    """
    shapes = {}
    for contract in primitive_contracts().values():
        inputs = set(contract["params"])
        for relation in contract["post"]:
            args = relation["args"]
            if "y" not in args or len(set(args)) != 3 or not set(args)-{"y"} <= inputs:
                continue
            others = [a for a in dict.fromkeys(args) if a != "y"]
            roles = tuple("y" if a == "y" else ("x1" if a == others[0] else "x2") for a in args)
            key = canonical_atom(relation["atom"], roles)
            if key in shapes:
                continue
            certificate = _certify_shape(relation["atom"], roles)
            if certificate is not None:
                shapes[key] = certificate
    return shapes


def _certify_shape(predicate, roles):
    polynomial = _generic_polynomial(predicate, roles)
    yx, yy = sp.Symbol("yx"), sp.Symbol("yy")
    if sp.Poly(polynomial, yx, yy).total_degree() != 1:
        return None
    c1, c2 = sp.expand(sp.diff(polynomial, yx)), sp.expand(sp.diff(polynomial, yy))
    distance = sp.expand((sp.Symbol("x1x")-sp.Symbol("x2x"))**2+(sp.Symbol("x1y")-sp.Symbol("x2y"))**2)
    if not _ratio_is_nonzero_rational(sp.expand(c1**2+c2**2), distance):
        return None
    t = sp.Symbol("t")
    for base in ("x1", "x2"):
        origin = (sp.Symbol(base+"x"), sp.Symbol(base+"y"))
        if sp.expand(polynomial.subs({yx: origin[0], yy: origin[1]}, simultaneous=True)) == 0:
            point = (origin[0]-t*c2, origin[1]+t*c1)
            if gc.exact_zero(polynomial.subs({yx: point[0], yy: point[1]}, simultaneous=True)):
                return {"predicate": predicate, "roles": list(roles), "origin": base,
                        "parametrization": [str(point[0]), str(point[1])],
                        "gradient_norm_ratio": str(sp.cancel(sp.expand(c1**2+c2**2)/distance))}
    return None


@lru_cache(maxsize=None)
def _certify_transfer_pattern(predicate, pattern, shape_key):
    shape = transfer_shapes()[shape_key]
    t = sp.Symbol("t")
    names = sorted({s for s in pattern if s != "v"})
    def lowered(point):
        return _generic_polynomial(predicate, tuple(point if s == "v" else s for s in pattern))
    target = lowered("y")
    parametrized = sp.expand(target.subs({sp.Symbol("yx"): sp.sympify(shape["parametrization"][0]),
                                          sp.Symbol("yy"): sp.sympify(shape["parametrization"][1])},
                                         simultaneous=True))
    left, right = lowered("x1"), lowered("x2")
    p0, p1, q0, q1 = sp.symbols("p0 p1 q0 q1")
    residual = sp.expand(parametrized-(p0+p1*t)*left-(q0+q1*t)*right)
    generators = sorted(residual.free_symbols-{p0, p1, q0, q1}, key=str)
    if not generators:
        equations = [residual]
    else:
        equations = sp.Poly(residual, *generators).coeffs()
    solutions = sp.linsolve(equations, [p0, p1, q0, q1])
    if not solutions:
        return None
    (solution,) = tuple(solutions)
    solution = [s.subs({p0: 0, p1: 0, q0: 0, q1: 0}) for s in solution]
    if any(not s.is_Rational for s in solution):
        return None
    l1, l2 = solution[0]+solution[1]*t, solution[2]+solution[3]*t
    if not gc.exact_zero(parametrized-l1*left-l2*right):
        return None
    return {"metarule": "MR-transfer", "relation": {"predicate": predicate, "pattern": list(pattern),
            "slots": names}, "shape": shape, "multipliers": [str(l1), str(l2)],
            "identity": "alpha(x(t)) - l1*alpha(x1) - l2*alpha(x2) == 0",
            "concludes": "polynomial equation of alpha(y); prerequisites of alpha(y) are not concluded",
            "premises": ["alpha(x1)", "alpha(x2)", "S(y,x1,x2)", "diff(x1,x2)"]}


def certify_transfer(predicate, arguments, distinguished, shape_key, stats=None):
    """Certificate that the spec atom predicate(arguments) in `distinguished` transfers along S, or None."""
    if distinguished not in arguments or shape_key not in transfer_shapes():
        return None
    pattern, _ = _pattern(arguments, distinguished)
    if stats is not None:
        stats["transfer_certification_requests"] += 1
    return _certify_transfer_pattern(predicate, pattern, shape_key)
