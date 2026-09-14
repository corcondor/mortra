"""Typed, partial Euclidean constructions, separate from the locus DSL.

Programs use library_compression's existing `use` nodes. Certificates describe
arbitrary real input points with QQ coefficients, not sampled configurations.
The finite search instantiates those contracts at exact rational configurations.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from copy import deepcopy
from itertools import combinations

import sympy as sp

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import library_compression as library
from math_os_prototype.representation_progress import digest


CARRIERS = ("Point", "Line", "Circle")
PREDICATES = {"midp": 3, "coll": 3, "perp": 4, "para": 4,
              "cyclic": 4, "cong": 4, "eqangle": 8,
              "diff": 2, "ncoll": 3, "npara": 4}


@dataclass(frozen=True)
class PredicateAtom:
    predicate: str
    arguments: tuple[str, ...]
    certificate: dict
    argument_type: str = "Point"


@dataclass(frozen=True)
class MorphismCall:
    morphism: str
    binding: dict
    outputs: tuple[str, ...]
    contract: str
    term: dict
    primitive_expansion: dict
    provenance: dict


@dataclass(frozen=True)
class MorphismContract:
    id: str
    parameters: tuple[dict, ...]
    body: dict
    primitive_expansion: dict
    applicability: dict
    effects: tuple[dict, ...]
    exact_certificate: dict
    parents: tuple[str, ...]
    generation: int


@dataclass
class GeometrySemanticState:
    objects: dict
    predicates: dict = field(default_factory=dict)
    terms: dict = field(default_factory=dict)
    history: list = field(default_factory=list)
    registered_morphisms: tuple[str, ...] = ()
    depth: int = 0
    primitive_cost: int = 0

    def record(self):
        return asdict(self)


class EuclideanFragment:
    arities = {"midpoint": 2, "mirror": 2, "foot": 3, "circle": 3,
               "orthocenter": 3, "reflect": 3, "intersection_ll": 4}
    scope = {"coefficient_field": "QQ", "models": "real_coordinate_plane",
             "branch": "single_valued_rational", "version": 2,
             "actions": list(arities),
             "equations": "existing JGEX rational and relational elaborators",
             "predicate_policy": "polynomial equality plus explicit geometric nondegeneracy",
             "circle_operation": "Point^3 -> Point (circumcenter), not a Circle carrier"}

    @staticmethod
    def primitive(elaborator, family, output, inputs):
        if family not in EuclideanFragment.arities or len(inputs) != EuclideanFragment.arities[family]:
            raise ValueError("unsupported exact construction")
        if family == "intersection_ll":
            if isinstance(elaborator, gc._RelationalJGEXElaborator):
                elaborator._on_line((output, *inputs[:2]))
                elaborator._on_line((output, *inputs[2:]))
            else:
                elaborator.coordinates[output] = elaborator._line_intersection(*inputs)
        else:
            name = "circumcenter" if family == "circle" else family
            getattr(elaborator, "_"+name)((output, *inputs))

    @staticmethod
    def relations(step):
        y, a, family = step["output"], step["inputs"], step["family"]
        def row(p, *args):
            return {"predicate": p, "points": list(args)}
        if family == "midpoint":
            return [row("midp", y, *a), row("coll", y, *a), row("cong", y, a[0], y, a[1])]
        if family == "mirror":
            return [row("midp", a[1], a[0], y), row("coll", y, *a)]
        if family == "foot":
            return [row("coll", y, a[1], a[2]), row("perp", a[0], y, a[1], a[2])]
        if family == "circle":
            return [row("cong", y, a[0], y, a[1]), row("cong", y, a[0], y, a[2])]
        if family == "orthocenter":
            return [row("perp", y, a[0], a[1], a[2]), row("perp", y, a[1], a[0], a[2])]
        if family == "reflect":
            return [row("perp", y, a[0], a[1], a[2]),
                    row("cong", y, a[1], a[0], a[1]), row("cong", y, a[2], a[0], a[2])]
        return [row("coll", y, *a[:2]), row("coll", y, *a[2:])]

    @staticmethod
    def relation_polynomial(elaborator, relation):
        # Construction certificates establish the equation; proper-line/circle
        # conditions below are separately required before publishing an atom.
        return gc._JGEXElaborator.goal(elaborator, relation["predicate"], tuple(relation["points"]))


FRAGMENT = EuclideanFragment()


def validate_primitive(term):
    gc.validate(term, fragment=FRAGMENT)


def validate_semantic(term):
    if library.is_call(term):
        if not isinstance(term["abstraction"], str):
            raise ValueError("content-addressed definition ID required")
        for a in term["arguments"].values():
            validate_semantic(a)
    elif isinstance(term, dict) and term.get("op") in FRAGMENT.arities:
        if set(term) != {"op", "args"} or len(term["args"]) != FRAGMENT.arities[term["op"]]:
            raise ValueError("invalid construction arity")
        for a in term["args"]:
            validate_semantic(a)
    else:
        gc.validate(term)


def expand(term, table, stats=None):
    with library.grammar(validate_primitive):
        return library.expand_for_execution(term, table, stats=stats)


def rename_points(term, prefix):
    if isinstance(term, dict) and term.get("op") == "var":
        return gc.point(prefix+term["name"])
    if isinstance(term, dict):
        return {k: rename_points(v, prefix) for k, v in term.items()}
    if isinstance(term, list):
        return [rename_points(v, prefix) for v in term]
    return term


def definition_body(template):
    names = library.holes(template)
    if not names or any(not n.startswith("f") for n in names):
        raise ValueError("Point-valued arguments required")
    body = library.instantiate_term(template, {n: gc.point(n) for n in names})
    validate_semantic(body)
    def free(node):
        if isinstance(node, dict):
            if node.get("op") == "var":
                return {node["name"]}
            return set().union(*(free(v) for v in node.values()))
        if isinstance(node, list):
            return set().union(*(free(v) for v in node))
        return set()
    if free(body) != set(names):
        raise ValueError("unabstracted source point")
    return body


def conditions(predicate, args):
    if predicate in {"perp", "para", "npara"}:
        return [("diff", tuple(args[:2])), ("diff", tuple(args[2:]))]
    if predicate == "eqangle":
        return [("diff", tuple(args[i:i+2])) for i in range(0, 8, 2)]
    if predicate == "cyclic":
        return [("ncoll", tuple(args[:3]))] + [("diff", p) for p in combinations(args, 2)]
    return []


def requirements(family, args):
    if family in {"foot", "reflect"}:
        return [("diff", tuple(args[1:]))]
    if family in {"circle", "orthocenter"}:
        return [("ncoll", tuple(args))]
    if family == "intersection_ll":
        return [("npara", tuple(args))]
    return []


def atom_key(predicate, args):
    return digest([predicate, list(args)])


def lower(elaborator, predicate, args):
    if predicate not in PREDICATES or len(args) != PREDICATES[predicate]:
        raise ValueError("unsupported exact predicate or arity")
    if predicate == "diff":
        return elaborator._distance_squared(*args)
    return gc._JGEXElaborator.goal(elaborator, {"ncoll": "coll", "npara": "para"}.get(predicate, predicate), args)


def certify_atom(predicate, args, objects, *, provenance, known=None, stats=None):
    """Decide an atom at an exact rational state, retaining proper geometry NDGs.

    These are instance certificates. Universal morphism certificates are
    produced by certify_body and never inferred from these finite checks.
    """
    key = atom_key(predicate, args)
    if known is not None and key in known:
        if stats is not None:
            stats["predicate_cache_hits"] += 1
        return known[key]
    if any(n not in objects or objects[n]["type"] != "Point" for n in args):
        raise ValueError("predicate needs declared Point objects")
    prerequisites = []
    for p, a in conditions(predicate, args):
        proof = certify_atom(p, a, objects, provenance=provenance, known=known, stats=stats)
        if proof is None:
            return None
        prerequisites.append(asdict(proof))
    elaborator = gc._JGEXElaborator()
    elaborator.coordinates.update({n: tuple(sp.Rational(v) for v in o["coordinates"])
                                   for n, o in objects.items() if o["type"] == "Point"})
    value = sp.cancel(lower(elaborator, predicate, tuple(args)))
    if stats is not None:
        stats["predicate_prover_calls"] += 1
    holds = value != 0 if predicate in {"diff", "ncoll", "npara"} else gc.exact_zero(value)
    if not holds or any(d == 0 for d in elaborator.denominators):
        return None
    return PredicateAtom(predicate, tuple(args), {
        "method": "exact_rational_instance", "value": str(value),
        "scope": FRAGMENT.scope, "conditions": prerequisites, "source": provenance})


def certify_definition(template, archive):
    table = library.definition_table({h["id"]: h["template"] for h in archive})
    body = definition_body(template)
    stats = {}
    primitive = expand(body, table, stats)
    certificate, costs = gc.certify_body(primitive, fragment=FRAGMENT)
    parents = tuple(sorted(set(library.calls_in(body))))
    generations = {h["id"]: h["generation"] for h in archive}
    generation = 1+max((generations[p] for p in parents), default=0)
    identifier = "geom.semantic."+digest({"template": template, "scope": FRAGMENT.scope})[:20]
    effects = tuple(dict(r, conditions=[{"predicate": p, "points": list(a)}
                                        for p, a in conditions(r["predicate"], r["points"])])
                    for r in certificate["guaranteed_relation"])
    result = asdict(MorphismContract(identifier, tuple(certificate["typed_parameters"]), body,
        primitive, certificate["applicability"], effects, certificate, parents, generation))
    result.update(template=deepcopy(template), acquisition_cost=dict(costs, **stats))
    return result


def replay_definition(h, archive):
    rebuilt = certify_definition(h["template"], archive)
    return all(digest(h.get(k)) == digest(v) for k, v in rebuilt.items() if k != "acquisition_cost")


def support_manifest():
    return {"carriers": CARRIERS, "executable_carrier": "Point",
            "other_carriers": "declared types; no Line/Circle-valued constructors in this fragment",
            "constructions": {n: {"arity": a, "exact": True} for n, a in FRAGMENT.arities.items()},
            "predicates": {n: {"arity": a, "exact": True} for n, a in PREDICATES.items()},
            "eqangle_scope": "directed line angles modulo pi, with four nonzero lines",
            "cyclic_scope": "noncollinear first triple and pairwise distinct points",
            "unsupported_policy": "refuse, never numerical acceptance", "scope": FRAGMENT.scope}
