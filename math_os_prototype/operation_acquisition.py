"""The loop: search, compose what is missing, register it, edit it, re-certify, use it again.

Nothing here is a second reasoner. The search is `runtime_typed_planner` driven
through `operation_contracts.Session`; the bodies are programs in the grammar of
`geometry_relational_edit`, unfolded, spliced and abstracted by that module's
calculus with the contract domain plugged in; the arithmetic is
`algebraic_structures`.

What this module adds is the acquisition step:

    a plan that meets a specification is read back as an executable body;
    the specification is derived from the guarantees the body itself
    established, by exhibiting the witnesses it produced;
    every precondition the body did not discharge internally is carried to the
    composite instead of being dropped;
    the composite is registered with its provenance, parents and generation, and
    the same search picks it up for later goals.
"""
from __future__ import annotations

from math_os_prototype import geometry_relational_edit as edit
from math_os_prototype.operation_contracts import (
    ACQUIRED,
    CANDIDATE,
    Condition,
    Contract,
    Session,
)
from math_os_prototype.representation_progress import digest


class AcquisitionRefused(ValueError):
    """A composite that may not be registered as certified."""


# ---------------------------------------------------------------------------
# Executing a body
# ---------------------------------------------------------------------------

def execute_body(session, body, arguments):
    """Run a body step by step through the contract session.

    A step naming an acquired operation runs that operation's own body, so an
    acquired operation is material: it is stored as a program, not as a closure.
    """
    environment = dict(arguments)
    for step in body["steps"]:
        name = step.get("prim") or step.get("call")
        contract = session.registry.contracts.get(name)
        if contract is None:
            raise AcquisitionRefused(f"unknown operation in body: {name}")
        binding = {param: environment[argument]
                   for (param, _), argument in zip(contract.params, step["args"], strict=True)}
        result = session.apply(contract, binding)
        if result is None:
            return None
        environment[step["out"]] = result.value
    return environment[body["result"]]


# ---------------------------------------------------------------------------
# From a plan to a body
# ---------------------------------------------------------------------------

def body_from_executions(session, required, inputs, result_id, *, since=0):
    """The executions a result and its derivation rest on, written as a body.

    Requirements are closed under two relations: an argument an execution
    consumed, and an execution that discharged one of its preconditions. Nothing
    that the derivation of the guarantee depends on is left out, so re-running the
    body re-establishes exactly what was used.
    """
    producer = {}
    for index, execution in enumerate(session.executions):
        producer.setdefault(execution["objects"]["v"], index)
    input_ids = {}
    for name, (sort, value) in inputs.items():
        input_ids.setdefault(session.registry.object_id(sort, value), name)
    needed, stack = set(), list(required)
    while stack:
        index = stack.pop()
        if index in needed or index < since or index >= len(session.executions):
            continue
        needed.add(index)
        execution = session.executions[index]
        contract = session.registry.contracts[execution["contract"]]
        for parameter, _ in contract.params:
            identity = execution["objects"][parameter]
            if identity in input_ids:
                continue
            if identity in producer:
                stack.append(producer[identity])
        for premise in execution["pre"]:
            earlier = premise["justification"].get("execution")
            if earlier is not None:
                stack.append(earlier)
    names, steps = dict(input_ids), []
    for index in sorted(needed):
        execution = session.executions[index]
        contract = session.registry.contracts[execution["contract"]]
        arguments = []
        for parameter, _ in contract.params:
            identity = execution["objects"][parameter]
            if identity not in names:
                raise AcquisitionRefused(
                    f"{contract.name}: an argument is not reachable from the inputs")
            arguments.append(names[identity])
        out = f"t{len(steps)+1}"
        steps.append({"out": out, "prim": contract.name, "args": arguments})
        # A rule that returns its subject adds a guarantee, not an object: the object
        # keeps the name it already had, and `canonical_names` identifies the two.
        names.setdefault(execution["objects"]["v"], out)
    if result_id not in names:
        raise AcquisitionRefused("the result was not produced by any of the required executions")
    return prune_body(session, {"params": list(inputs), "steps": steps, "result": names[result_id]})


def prune_body(session, body):
    """Keep the steps the result depends on, and the steps whose guarantees they need.

    A step that produces nothing the result uses is still kept when a step that is
    kept relies on a condition it establishes: a rule earns its place in a body by
    the precondition it discharges, not by the object it returns.
    """
    alias = canonical_names(session, body)
    resolve = lambda name: alias.get(name, name)
    keep, names_needed, conditions_needed = set(), set(), set()
    for index in range(len(body["steps"])-1, -1, -1):
        step = body["steps"][index]
        contract = session.registry.contracts[step.get("prim") or step.get("call")]
        local = dict(zip(contract.param_names, step["args"], strict=True)) | {"v": step["out"]}
        rename = lambda condition: condition.rename(local).rename(alias)
        produces = {(rename(c).predicate, rename(c).args) for c in contract.post}
        if (resolve(step["out"]) == resolve(body["result"]) or step["out"] in names_needed
                or produces & conditions_needed):
            keep.add(index)
            conditions_needed -= produces
            conditions_needed |= {(rename(c).predicate, rename(c).args) for c in contract.pre}
            names_needed |= {resolve(argument) for argument in step["args"]} | set(step["args"])
    steps = [step for index, step in enumerate(body["steps"]) if index in keep]
    used = {argument for step in steps for argument in step["args"]}
    return {"params": [name for name in body["params"] if name in used], "steps": steps,
            "result": body["result"]}


# ---------------------------------------------------------------------------
# What the body proves, and what it still needs
# ---------------------------------------------------------------------------

def canonical_names(session, body):
    """Names of the same object identified.

    An operation that returns one of its arguments unchanged — a lemma, whose
    content is the guarantee and not a new object — makes its output another name
    for that argument. Conditions are compared modulo these aliases, so a
    guarantee proved about the argument is the same guarantee about the output.
    """
    alias = {}
    for step in body["steps"]:
        contract = session.registry.contracts[step.get("prim") or step.get("call")]
        if contract.returns is not None:
            index = contract.param_names.index(contract.returns)
            argument = step["args"][index]
            alias[step["out"]] = alias.get(argument, argument)
    return alias


def body_conditions(session, body):
    """Walk the body once: what each step needs, and what has been established before it."""
    alias = canonical_names(session, body)
    established, needed = set(), []
    for step in body["steps"]:
        contract = session.registry.contracts[step.get("prim") or step.get("call")]
        names = dict(zip(contract.param_names, step["args"], strict=True))
        names["v"] = step["out"]
        resolve = lambda condition: condition.rename(names).rename(alias)
        for condition in contract.pre:
            renamed = resolve(condition)
            if (renamed.predicate, renamed.args) not in established:
                needed.append(renamed)
        for condition in contract.post:
            renamed = resolve(condition)
            established.add((renamed.predicate, renamed.args))
    return established, needed


def carried_preconditions(session, body, parameters):
    """Preconditions no step of the body established, lifted to the composite.

    A condition discharged against a hypothesis of the task, or by an exact check
    on these concrete objects, is not proven for every input: it becomes a
    precondition of the composite. A condition about an object internal to the
    body cannot be stated at the interface, so the composite is refused instead.
    """
    _, needed = body_conditions(session, body)
    carried, seen = [], set()
    for condition in needed:
        if any(argument not in parameters for argument in condition.args):
            raise AcquisitionRefused(
                f"a precondition about an internal object is neither established nor statable: "
                f"{condition.as_json()}")
        if (condition.predicate, condition.args) not in seen:
            seen.add((condition.predicate, condition.args))
            carried.append(condition)
    return carried


def derive_specification(session, definition, bindings, result_id):
    """Witnesses making the specification true of these objects, with each conjunct's justification."""
    objects = [result_id if p == "v" else bindings[p] for p in definition.params]
    witnesses = session.entails(definition, objects)
    if witnesses is None:
        return None
    conjuncts = []
    for conjunct in definition.body:
        ids = [witnesses[a] for a in conjunct.args]
        conjuncts.append({"condition": conjunct.as_json(), "objects": ids,
                          "justification": session.context.lookup(conjunct.predicate, ids)})
    return {"witnesses": {k: v for k, v in witnesses.items() if k in definition.exists},
            "conjuncts": conjuncts}


# ---------------------------------------------------------------------------
# Acquisition
# ---------------------------------------------------------------------------

def required_executions(session, derivation, goal_step):
    """The executions that established the result and every conjunct of the derivation.

    The result is anchored to the execution the plan actually used, not to whichever
    execution first produced an equal object: an operation is what was done, and two
    routes to the same value are two different operations.
    """
    required = [index for index, execution in enumerate(session.executions) if execution is goal_step]
    for conjunct in derivation["conjuncts"]:
        index = (conjunct["justification"] or {}).get("execution")
        if index is not None:
            required.append(index)
    return required


def acquire(session, *, name, body, parameters, specification, spec_binding, bindings, result_id,
            result_sort, parents=(), note=""):
    """Register a composite as a contract in the same language, with its derivation.

    `spec_binding` maps the specification's parameter names to this operation's
    parameter names. Refused when the specification does not follow from the
    guarantees the body established: such an operation may only be kept as a
    candidate.
    """
    definition = session.registry.definitions[specification]
    derivation = derive_specification(session, definition, bindings, result_id)
    if derivation is None:
        raise AcquisitionRefused(f"{name}: the specification does not follow from the body's guarantees")
    names = [p for p, _ in parameters]
    carried = carried_preconditions(session, body, names)
    post = Condition(definition.predicate, tuple(spec_binding.get(p, p) for p in definition.params))
    generation = 1+max((session.registry.contracts[p].generation for p in parents
                        if p in session.registry.contracts), default=0)

    def run(binding, counter, body=body):
        return execute_body(session, body, binding)

    contract = Contract(
        name=name, params=tuple(parameters), result=result_sort, pre=tuple(carried), post=(post,),
        run=run, provenance=ACQUIRED, body=body, parents=tuple(parents), generation=generation,
        derivation={"kind": "composition", "specification": specification,
                    "rule": "witnesses produced by the body prove the specification; "
                            "undischarged preconditions are carried to the interface",
                    "witnesses": derivation["witnesses"], "conjuncts": derivation["conjuncts"],
                    "body_digest": digest(body)[:20]},
        note=note)
    session.registry.add(contract)
    return contract


def acquire_candidate(session, *, name, body, parameters, post, result_sort, parents=(), note=""):
    """Keep an operation whose guarantee was only observed on the instances run so far."""
    def run(binding, counter, body=body):
        return execute_body(session, body, binding)

    contract = Contract(
        name=name, params=tuple(parameters), result=result_sort, post=tuple(post), run=run,
        provenance=CANDIDATE, body=body, parents=tuple(parents),
        generation=1+max((session.registry.contracts[p].generation for p in parents
                          if p in session.registry.contracts), default=0),
        note=note or "observed on the instances run so far, not derived")
    session.registry.add(contract)
    return contract


# ---------------------------------------------------------------------------
# The contract domain of the edit calculus
# ---------------------------------------------------------------------------

def edit_domain(registry):
    """Arities, sorts and operation interfaces read off the contracts themselves."""

    def instantiated_post(name):
        contract = registry.contracts[name]
        index = {p: i for i, (p, _) in enumerate(contract.params)}
        return [(condition.predicate,
                 tuple("o" if a == "v" else f"i{index[a]}" for a in condition.args))
                for condition in contract.post if all(a == "v" or a in index for a in condition.args)]

    def register(body, post, table=None, *, parents=(), generation=None, domain=None):
        """The calculus may rewrite; only the contract layer may certify.

        The definition comes back marked as pending, and `acquire` turns it into a
        contract after deriving the specification from an execution of this body.
        """
        edit.validate_program(body, table or {}, domain=domain)
        definition = {"params": [{"name": p, "sort": "Object"} for p in body["params"]],
                      "body": body, "post": [[p, list(a)] for p, a in post],
                      "parents": list(parents), "generation": generation,
                      "certification": "pending: the contract layer derives the guarantee"}
        definition["id"] = domain.id_prefix+digest({k: definition[k] for k in ("params", "body", "post")})[:20]
        return definition

    return edit.EditDomain(
        name="operation-contracts", id_prefix="op.",
        param_sort=lambda name: "Object",
        arity=lambda prim: len(registry.contracts[prim].params),
        has_primitive=lambda prim: prim in registry.contracts,
        instantiated_post=instantiated_post,
        register=register)


def expand(registry, body):
    """Unfold acquired calls into steps of given contracts, by the repository's edit calculus."""
    table, rewritten = {}, {"params": list(body["params"]), "steps": [], "result": body["result"]}
    for name, contract in registry.contracts.items():
        if contract.body is not None:
            table[name] = {"params": [{"name": p} for p, _ in contract.params],
                           "body": _as_call_body(registry, contract.body)}
    for step in body["steps"]:
        rewritten["steps"].append(_as_call_step(registry, step))
    return edit.unfold(rewritten, table, domain=edit_domain(registry))


def _as_call_step(registry, step):
    name = step.get("prim") or step.get("call")
    if registry.contracts[name].body is not None:
        return {"out": step["out"], "call": name, "args": list(step["args"])}
    return {"out": step["out"], "prim": name, "args": list(step["args"])}


def _as_call_body(registry, body):
    return {"params": list(body["params"]), "result": body["result"],
            "steps": [_as_call_step(registry, step) for step in body["steps"]]}
