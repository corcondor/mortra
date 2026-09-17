"""Edit, abstract and re-register operations inside the relational geometry DSL.

An operation definition is data in the same grammar as every program:

    {"id", "params": [{"name", "sort": "Point" | "Op" | "Rel", ...}],
     "body": {"params": [...], "steps": [{"out", "prim"|"call"|"ovar", "args"}], "result": name},
     "post": [atoms over params and "v" (the result)], "certificates": {...},
     "parents": [ids], "generation": g}

Every edit re-derives exact certificates for the declared post atoms by
substituting kernel witnesses (geometry_relational_library.certify_entry), and
shows non-vacuity by exact execution. Nothing is accepted on a numeric check.
Higher-order parameters are instantiated only when the certificates the body
relies on replay with the argument substituted.
"""
from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Callable

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_relational_library as lib
from math_os_prototype import geometry_semantic_dsl as dsl
from math_os_prototype.representation_progress import digest


class EditRefused(ValueError):
    pass


# ---------------------------------------------------------------------------
# The domain a program is written in
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class EditDomain:
    """What the calculus needs to know about a language: arities, sorts, and how a
    definition is accepted. The grammar, the hygiene rules, unfolding, folding,
    splicing and anti-unification are the same for every domain.

    `register` is the acceptance gate. For the relational geometry language it is
    `define`, which re-derives an exact certificate for every declared post atom.
    A domain that certifies elsewhere (the contract layer derives a composite's
    guarantee from the guarantees of its steps) supplies its own gate; a domain
    with no gate at all cannot register definitions.
    """

    name: str
    id_prefix: str
    param_sort: Callable[[str], str]
    arity: Callable[[str], int]
    has_primitive: Callable[[str], bool]
    instantiated_post: Callable[[str], list] | None = None
    register: Callable[..., dict] | None = None


def _geometry_arity(prim):
    return len(rdsl.primitive_contracts()[prim]["params"])


def _geometry_register(body, post, table=None, *, parents=(), generation=None, domain=None):
    return define(body, post, table, parents=parents, generation=generation)


GEOMETRY = EditDomain(
    name="relational-geometry",
    id_prefix="rel.",
    param_sort=lambda name: "Point",
    arity=_geometry_arity,
    has_primitive=lambda prim: prim in rdsl.primitive_contracts(),
    instantiated_post=lambda prim: _instantiated_post(prim),
    register=_geometry_register,
)


# ---------------------------------------------------------------------------
# Definitions, unfolding and folding
# ---------------------------------------------------------------------------

def validate_program(program, table=None, *, domain=GEOMETRY):
    """Name hygiene: parameters and step outputs are distinct identifiers; every argument is bound earlier."""
    table = table or {}
    params = program.get("params")
    if not isinstance(params, list) or len(set(params)) != len(params):
        raise EditRefused("parameters must be distinct")
    bound = set()
    for name in params:
        if not isinstance(name, str) or not rdsl.VARIABLE.fullmatch(name):
            raise EditRefused("invalid parameter name")
        bound.add(name)
    for step in program["steps"]:
        kinds = [k for k in ("prim", "call", "ovar") if k in step]
        if len(kinds) != 1:
            raise EditRefused("a step has exactly one of prim, call, ovar")
        if not isinstance(step["out"], str) or not rdsl.VARIABLE.fullmatch(step["out"]) or step["out"] in bound:
            raise EditRefused("step outputs must be fresh identifiers")
        if any(a not in bound for a in step["args"]):
            raise EditRefused("unbound argument")
        if "prim" in step:
            if not domain.has_primitive(step["prim"]):
                raise EditRefused("unknown primitive")
            if len(step["args"]) != domain.arity(step["prim"]):
                raise EditRefused("primitive arity mismatch")
        if "call" in step and step["call"] not in table:
            raise EditRefused("unknown callee")
        bound.add(step["out"])
    if program["result"] not in bound-set(params):
        raise EditRefused("result must be a step output")


def _primitive_program(body, table, *, domain=GEOMETRY):
    """Unfold every call (recursively) into primitive steps.

    Fresh local names start with an underscore, which no validated parameter or
    step name can, so unfolding cannot capture a parameter.
    """
    validate_program(body, table, domain=domain)
    steps, counter = [], [0]
    def fresh():
        counter[0] += 1
        return f"_u{counter[0]}"
    def inline(program, binding):
        local = dict(binding)
        for step in program["steps"]:
            args = [local.get(a, a) for a in step["args"]]
            if "prim" in step:
                out = fresh()
                steps.append({"out": out, "prim": step["prim"], "args": args})
                local[step["out"]] = out
            elif "call" in step:
                callee = table[step["call"]]
                validate_program(callee["body"], table, domain=domain)
                names = [p["name"] for p in callee["params"]]
                if len(names) != len(args):
                    raise EditRefused("call arity mismatch")
                local[step["out"]] = inline(callee["body"], dict(zip(callee["body"]["params"], args, strict=True)))
            else:
                raise EditRefused("unbound operation variable")
        return local[program["result"]]
    result = inline(body, {p: p for p in body["params"]})
    return {"params": list(body["params"]), "steps": steps, "result": result}


def unfold(body, table, *, domain=GEOMETRY):
    return _primitive_program(body, table, domain=domain)


def define(body, post, table=None, *, parents=(), generation=None):
    """Register an operation after exact certification of every declared post atom."""
    table = table or {}
    if any(not (isinstance(p, (list, tuple)) and p[0] in rdsl.EQUALITY_PREDICATES) for p in post):
        raise EditRefused("post atoms must be equality predicates over params and v")
    primitive = unfold(body, table)
    certificates = {}
    for predicate, args in post:
        if not set(args) <= set(body["params"]) | {"v"} or "v" not in args:
            raise EditRefused("post atom mentions a hidden local")
        certificate = lib.certify_entry(predicate, tuple(args), primitive)
        if certificate is None:
            raise EditRefused(f"post atom not certified: {predicate}{tuple(args)}")
        certificates[digest([predicate, list(args)])] = certificate
    if rdsl.nonvacuity_witness({"steps": primitive["steps"], "result": [primitive["result"]]},
                               list(primitive["params"])) is None:
        raise EditRefused("non-vacuity not shown")
    if generation is None:
        generation = 1+max((table[p]["generation"] for p in parents if p in table), default=0)
    definition = {"params": [{"name": p, "sort": "Point"} for p in body["params"]], "body": deepcopy(body),
                  "post": [[p, list(a)] for p, a in post], "certificates": certificates,
                  "parents": list(parents), "generation": generation,
                  "primitive_steps": len(primitive["steps"])}
    definition["id"] = "rel."+digest({k: definition[k] for k in ("params", "body", "post")})[:20]
    return definition


def call_step(definition, out, args):
    return {"out": out, "call": definition["id"], "args": list(args)}


def fold(body, definition, table, *, domain=GEOMETRY):
    """Replace one occurrence of a definition's body by a call, checked by identical unfolding."""
    pattern = definition["body"]
    for start in range(len(body["steps"])-len(pattern["steps"])+1):
        window = body["steps"][start:start+len(pattern["steps"])]
        mapping, ok = {}, True
        for mine, theirs in zip(window, pattern["steps"], strict=True):
            if mine.get("prim") != theirs.get("prim") or mine.get("call") != theirs.get("call"):
                ok = False
                break
            for a, b in zip(mine["args"], theirs["args"], strict=True):
                if mapping.setdefault(b, a) != a:
                    ok = False
            mapping[theirs["out"]] = mine["out"]
        if not ok:
            continue
        internal = {s["out"] for s in window[:-1]}
        used_later = {a for s in body["steps"][start+len(window):] for a in s["args"]} | {body["result"]}
        if internal & used_later:
            continue
        args = [mapping[p] for p in pattern["params"]]
        steps = body["steps"][:start]+[call_step(definition, window[-1]["out"], args)]+body["steps"][start+len(window):]
        folded = {"params": body["params"], "steps": steps, "result": body["result"]}
        if (_expansion_key(unfold(folded, table | {definition["id"]: definition}, domain=domain))
                == _expansion_key(unfold(body, table, domain=domain))):
            return folded
    raise EditRefused("definition body does not occur")


def _expansion_key(program):
    """Canonical structure of a primitive program, independent of local names."""
    names = {p: p for p in program["params"]}
    rendered = []
    for step in program["steps"]:
        names[step["out"]] = f"#{len(rendered)}"
        rendered.append([step["prim"], [names[a] for a in step["args"]]])
    return digest([rendered, names[program["result"]]])


# ---------------------------------------------------------------------------
# Substitution inside a body (R2)
# ---------------------------------------------------------------------------

def splice_step(body, step_out, replacement):
    """Replace the step producing `step_out` by `replacement`, a program over that step's inputs.

    Pure rewriting: names stay hygienic and the interface arity is checked. Whether
    the result may be registered is the domain's decision, not this function's.
    """
    index = next((i for i, s in enumerate(body["steps"]) if s["out"] == step_out), None)
    if index is None:
        raise EditRefused("no such step")
    target = body["steps"][index]
    if len(replacement["params"]) != len(target["args"]):
        raise EditRefused("replacement interface arity mismatch")
    binding = dict(zip(replacement["params"], target["args"], strict=True))
    occupied = {s["out"] for s in body["steps"]} | set(body["params"])
    renamed, local = [], {}
    for step in replacement["steps"]:
        out = step_out if step["out"] == replacement["result"] else _fresh(step["out"], occupied)
        occupied.add(out)
        local[step["out"]] = out
        renamed.append({**{k: v for k, v in step.items() if k not in {"out", "args"}}, "out": out,
                        "args": [binding.get(a, local.get(a, a)) for a in step["args"]]})
    if replacement["result"] not in local:
        raise EditRefused("replacement result must be a step")
    return {"params": body["params"], "steps": body["steps"][:index]+renamed+body["steps"][index+1:],
            "result": body["result"]}


def substitute(definition, step_out, replacement, table=None, *, domain=GEOMETRY):
    """Replace the step producing `step_out` by `replacement` (a program over that step's inputs).

    Accepted only if every post atom of the definition re-certifies on the edited
    body and non-vacuity still holds. The result is a new generation.
    """
    table = table or {}
    edited = splice_step(definition["body"], step_out, replacement)
    if domain.register is None:
        raise EditRefused("domain cannot register definitions")
    return domain.register(edited, [tuple([p, tuple(a)]) for p, a in definition["post"]], table,
                           parents=[definition["id"]], generation=definition["generation"]+1, domain=domain)


def _fresh(name, occupied):
    index = 0
    while f"{name}_{index}" in occupied:
        index += 1
    return f"{name}_{index}"


# ---------------------------------------------------------------------------
# Abstraction to operation and relation parameters (R2), instantiation by replay
# ---------------------------------------------------------------------------

def abstract_operation(first, second, *, domain=GEOMETRY):
    """Anti-unify two definitions with the same step skeleton.

    Positions where the primitive family differs become one Op parameter each.
    The parameter interface is the set of post atoms (over the step's inputs and
    output) certified for both families; the abstraction's post keeps the atoms
    certified in both definitions. At least one fixed step must remain.
    """
    a, b = first["body"], second["body"]
    if len(a["steps"]) != len(b["steps"]) or a["params"] != b["params"] or a["result"] != b["result"]:
        raise EditRefused("different skeletons")
    steps, parameters, fixed = [], [], 0
    for left, right in zip(a["steps"], b["steps"], strict=True):
        if left["out"] != right["out"] or left["args"] != right["args"]:
            raise EditRefused("different sharing structure")
        if all(left.get(k) == right.get(k) for k in ("prim", "call", "ovar")):
            steps.append(deepcopy(left))
            fixed += 1
            continue
        if "prim" not in left or "prim" not in right:
            raise EditRefused("only primitive positions are lifted")
        if domain.arity(left["prim"]) != domain.arity(right["prim"]):
            raise EditRefused("operation arity differs")
        if domain.instantiated_post is None:
            raise EditRefused("domain publishes no operation interface")
        interface = sorted(set(domain.instantiated_post(left["prim"]))
                           & set(domain.instantiated_post(right["prim"])))
        name = f"op{len(parameters)}"
        parameters.append({"name": name, "sort": "Op", "inputs": len(left["args"]), "outputs": 1,
                           "interface": [[i[0], list(i[1])] for i in interface],
                           "witnesses": [left["prim"], right["prim"]]})
        steps.append({"out": left["out"], "ovar": name, "args": list(left["args"])})
    if not parameters:
        raise EditRefused("nothing differs: no parameter to abstract")
    if not fixed:
        raise EditRefused("a bare hole is not an abstraction")
    post = sorted({tuple([p, tuple(x)]) for p, x in first["post"]} & {tuple([p, tuple(x)]) for p, x in second["post"]})
    if not post:
        raise EditRefused("no shared certified post atom")
    definition = {"params": [{"name": p, "sort": domain.param_sort(p)} for p in a["params"]]+parameters,
                  "body": {"params": a["params"], "steps": steps, "result": a["result"]},
                  "post": [[p, list(x)] for p, x in post], "parents": [first["id"], second["id"]],
                  "generation": 1+max(first["generation"], second["generation"]),
                  "applicability": "an Op argument's certified post must include the interface, "
                                   "and every post atom must re-certify on the instantiated body"}
    definition["id"] = domain.id_prefix+"ho."+digest({k: definition[k] for k in ("params", "body", "post")})[:20]
    return definition


def _instantiated_post(family):
    contract = rdsl.primitive_contracts()[family]
    return [rdsl.canonical_atom(r["atom"], tuple(f"i{contract['params'].index(x)}" if x in contract["params"] else "o"
                                               for x in r["args"])) for r in contract["post"]]


def instantiate_operation(higher, arguments, table=None, *, domain=GEOMETRY):
    """Instantiate Op parameters; applicability is decided by interface inclusion and re-certification."""
    body = deepcopy(higher["body"])
    for parameter in higher["params"]:
        if parameter["sort"] != "Op":
            continue
        family = arguments.get(parameter["name"])
        if family is None or not domain.has_primitive(family):
            raise EditRefused("Op argument must be a certified primitive")
        if domain.arity(family) != parameter["inputs"]:
            raise EditRefused("Op argument arity mismatch")
        if domain.instantiated_post is None:
            raise EditRefused("domain publishes no operation interface")
        provided = set(domain.instantiated_post(family))
        if not {tuple([p, tuple(x)]) for p, x in parameter["interface"]} <= provided:
            raise EditRefused("Op argument does not provide the interface")
        for step in body["steps"]:
            if step.get("ovar") == parameter["name"]:
                del step["ovar"]
                step["prim"] = family
    if domain.register is None:
        raise EditRefused("domain cannot register definitions")
    return domain.register(body, [tuple([p, tuple(a)]) for p, a in higher["post"]], table,
                           parents=[higher["id"]], generation=higher["generation"]+1, domain=domain)


def abstract_relation(programs):
    """Lift the hole specs of solved transfer programs to Rel parameters.

    Each item is {"family", "specs": [spec_of_input_0, ...]} where a spec is a
    single atom over "v" and named points, recorded by the planner. The result
    is an operation schema whose Rel parameters stand for those specs; its post
    concludes each parameter at the output under MR-transfer.
    """
    families = {p["family"] for p in programs}
    if len(families) != 1:
        raise EditRefused("different families")
    family = families.pop()
    shapes = rdsl.transfer_shapes()
    contract = rdsl.primitive_contracts()[family]
    layout = [tuple(i for i, s in enumerate(p["specs"]) if s is not None) for p in programs]
    if len(set(layout)) != 1 or not layout[0]:
        raise EditRefused("different parameter layout")
    positions = layout[0]
    if all(p["specs"] == programs[0]["specs"] for p in programs):
        raise EditRefused("identical specs: nothing to abstract")
    pairs = []
    for relation in contract["post"]:
        args = relation["args"]
        others = [a for a in dict.fromkeys(args) if a != "y"]
        if "y" in args and len(set(args)) == 3 and len(others) == 2:
            roles = tuple("y" if a == "y" else ("x1" if a == others[0] else "x2") for a in args)
            if rdsl.canonical_atom(relation["atom"], roles) in shapes:
                pairs.append(tuple(contract["params"].index(o) for o in others))
    if not pairs:
        raise EditRefused("family publishes no certified transfer shape")
    parameters = []
    for k, (i, j) in enumerate(pairs):
        if i not in positions or j not in positions:
            continue
        if any(rdsl.canonical_atom(*p["specs"][i]) != rdsl.canonical_atom(*p["specs"][j]) for p in programs):
            continue
        parameters.append({"name": f"rho{k}", "sort": "Rel", "arity": 1, "inputs": [i, j],
                           "applicability": "MR-transfer certificate replays for the argument relation"})
    if not parameters:
        raise EditRefused("no transferable parameter positions")
    schema = {"family": family, "params": parameters, "parents": [digest(p) for p in programs],
              "pre": "rho(x_i) & rho(x_j) & diff(x_i, x_j) for each Rel parameter",
              "post": "rho(v) for each Rel parameter"}
    schema["id"] = "rel.rho."+digest(schema)[:20]
    return schema


def instantiate_relation_schema(schema, relations):
    """Decide applicability of a Rel-parameter schema for concrete relations by certificate replay."""
    (shape,) = rdsl.transfer_shapes()
    decided = {}
    for parameter in schema["params"]:
        predicate, args = relations[parameter["name"]]
        certificate = rdsl.certify_transfer(predicate, tuple(args), "v", shape)
        if certificate is None:
            raise EditRefused(f"transfer certificate does not replay for {predicate}{tuple(args)}")
        decided[parameter["name"]] = certificate
    return {"schema": schema["id"], "family": schema["family"], "certificates": decided}


# ---------------------------------------------------------------------------
# Existing archive conversion (E1)
# ---------------------------------------------------------------------------

def convert_archive_definition(h):
    """Convert a stored MorphismContract and re-certify its effects that are expressible over its interface.

    An effect whose exact certification is refused or stops at the declared size
    bound is recorded under `undecided`; it is never kept as a post atom.
    """
    steps, output = gc.dag(h["primitive_expansion"], fragment=dsl.FRAGMENT)
    params = [p["name"] for p in h["parameters"]]
    body = {"params": params, "steps": [{"out": s["output"], "prim": s["family"], "args": list(s["inputs"])}
                                        for s in steps], "result": output}
    primitive = unfold(body, {})
    post, undecided = [], []
    for effect in h["effects"]:
        points = ["v" if p == output else p for p in effect["points"]]
        if set(points) <= set(params) | {"v"} and "v" in points:
            if lib.certify_entry(effect["predicate"], tuple(points), primitive) is None:
                undecided.append([effect["predicate"], points])
            else:
                post.append((effect["predicate"], tuple(points)))
    definition = define(body, post)
    definition["undecided_interface_effects"] = undecided
    definition["source_archive_id"] = h["id"]
    return definition
