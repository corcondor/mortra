"""One operation contract shared by every reasoner in this repository.

A contract carries exactly six things:

    type          each parameter and the result have a sort; sorts are the
                  planner's types (`runtime_typed_planner`), so maps, complexes
                  and quotients travel in the same search as points;
    object id     every value has a canonical identity inside its sort, so a
                  condition is a statement about objects, not about variables;
    preconditions conditions that must hold before the operation applies;
    guarantees    conditions that hold of the result afterwards;
    proof         how each guarantee was established, and how each precondition
                  was discharged (context, inheritance, or an exact check);
    cost          every check and every computation charges the shared counter.

Nothing here searches. Contracts compile to `RuntimePrimitive`s and the existing
typed planner does the searching; contracts compile to DSL bodies and the
existing edit calculus does the editing. The only new thing is the record that
lets the two speak about the same objects.

Provenance is kept apart and never collapsed:

    given       written by a person (or read off an exact kernel certificate);
    acquired    composed during a run and certified by derivation from the
                guarantees of its steps, with every undischarged precondition
                carried to the composite;
    candidate   observed to hold on the instances run so far and not derived.
                A candidate may be executed, but its guarantees are recorded
                with status "instance" and may never discharge another
                operation's precondition.
"""
from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Any, Callable

from math_os_prototype.algebraic_structures import OperationCounter
from math_os_prototype.representation_progress import digest
from math_os_prototype.runtime_typed_planner import (
    PrimitiveResult,
    RuntimePrimitive,
    initial_fact,
    synthesize_typed_plan,
)

GIVEN = "given"
ACQUIRED = "acquired"
CANDIDATE = "candidate"
PROVENANCE = (GIVEN, ACQUIRED, CANDIDATE)


class ContractRefused(ValueError):
    """A contract, a registration or a discharge that must not be accepted."""


class ContractViolation(AssertionError):
    """A guarantee failed its exact check after the operation ran: a defect, not a dead end."""


# ---------------------------------------------------------------------------
# Types and object identity
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Sort:
    """A type together with the canonical identity of its objects."""

    name: str
    key: Callable[[Any], str]

    def object_id(self, value):
        return f"{self.name}.{self.key(value)}"


@dataclass(frozen=True)
class Condition:
    """A proposition `predicate(arg, ...)` over parameter names (and "v" for the result)."""

    predicate: str
    args: tuple[str, ...]

    @staticmethod
    def of(predicate, *args):
        return Condition(predicate, tuple(args))

    def rename(self, mapping):
        return Condition(self.predicate, tuple(mapping.get(a, a) for a in self.args))

    def as_json(self):
        return [self.predicate, list(self.args)]


@dataclass(frozen=True)
class Predicate:
    """An exactly decidable relation between objects, with its own cost."""

    name: str
    sorts: tuple[str, ...]
    check: Callable[..., bool]
    statement: str = ""

    @property
    def arity(self):
        return len(self.sorts)


@dataclass(frozen=True)
class Definition:
    """A specification: `predicate(params) := exists witnesses. conjunct & ...`.

    A specification says what is wanted; it never says by which operations. It is
    what a goal is stated in, and what an acquired operation's guarantee is
    derived from: exhibiting witnesses among the objects a body already produced,
    with every conjunct already established, is a proof of the specification by
    introduction of the existential witnesses.
    """

    predicate: str
    params: tuple[str, ...]
    sorts: tuple[str, ...]
    exists: tuple[str, ...]
    body: tuple[Condition, ...]

    def as_json(self):
        return {"predicate": self.predicate, "params": list(self.params), "sorts": list(self.sorts),
                "exists": list(self.exists), "body": [c.as_json() for c in self.body]}


# ---------------------------------------------------------------------------
# Contracts
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Contract:
    name: str
    params: tuple[tuple[str, str], ...]          # (parameter name, sort name)
    result: str                                   # sort name
    pre: tuple[Condition, ...] = ()
    post: tuple[Condition, ...] = ()
    run: Callable[..., Any] | None = None         # (binding, counter) -> value or None
    provenance: str = GIVEN
    body: dict | None = None                      # executable DSL body for composites
    parents: tuple[str, ...] = ()
    generation: int = 0
    derivation: dict | None = None                # how the guarantees were derived
    returns: str | None = None                    # the parameter returned unchanged, if any
    note: str = ""

    @property
    def param_names(self):
        return tuple(name for name, _ in self.params)

    @property
    def source_sorts(self):
        return tuple(sort for _, sort in self.params)

    def identity(self):
        return digest({"name": self.name, "params": [list(p) for p in self.params], "result": self.result,
                       "pre": [c.as_json() for c in self.pre], "post": [c.as_json() for c in self.post],
                       "body": self.body})[:20]

    def as_json(self):
        return {"name": self.name, "id": self.identity(), "params": [list(p) for p in self.params],
                "result": self.result, "pre": [c.as_json() for c in self.pre],
                "post": [c.as_json() for c in self.post], "returns": self.returns,
                "provenance": self.provenance,
                "generation": self.generation, "parents": list(self.parents),
                "body": self.body, "derivation": self.derivation, "note": self.note}


# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

class Registry:
    """Sorts, predicates and contracts. Provenance decides what a contract may be used for."""

    def __init__(self, sorts=(), predicates=(), contracts=(), definitions=()):
        self.sorts = {s.name: s for s in sorts}
        self.predicates = {p.name: p for p in predicates}
        self.definitions = {d.predicate: d for d in definitions}
        self.contracts = {}
        self.order = []
        for contract in contracts:
            self.add(contract)

    # -- registration -------------------------------------------------------
    def add(self, contract):
        if contract.name in self.contracts:
            raise ContractRefused(f"contract already registered: {contract.name}")
        if contract.provenance not in PROVENANCE:
            raise ContractRefused(f"unknown provenance: {contract.provenance}")
        for name, sort in contract.params:
            if sort not in self.sorts:
                raise ContractRefused(f"{contract.name}: unknown parameter sort {sort}")
        if contract.result not in self.sorts:
            raise ContractRefused(f"{contract.name}: unknown result sort {contract.result}")
        for condition in contract.pre+contract.post:
            self._check_condition(contract, condition)
        if contract.run is None and contract.body is None:
            raise ContractRefused(f"{contract.name}: neither an implementation nor a body")
        self.contracts[contract.name] = contract
        self.order.append(contract.name)
        return contract

    def condition_sorts(self, predicate):
        """The sorts a condition relates, whether it is decided directly or defined."""
        if predicate in self.predicates:
            return self.predicates[predicate].sorts
        if predicate in self.definitions:
            return self.definitions[predicate].sorts
        return None

    def _check_condition(self, contract, condition):
        expected_sorts = self.condition_sorts(condition.predicate)
        if expected_sorts is None:
            raise ContractRefused(f"{contract.name}: unknown predicate {condition.predicate}")
        if len(condition.args) != len(expected_sorts):
            raise ContractRefused(f"{contract.name}: {condition.predicate} arity")
        sorts = dict(contract.params) | {"v": contract.result}
        for argument, expected in zip(condition.args, expected_sorts, strict=True):
            if argument not in sorts:
                raise ContractRefused(f"{contract.name}: condition mentions unknown name {argument}")
            if sorts[argument] != expected:
                raise ContractRefused(f"{contract.name}: {condition.predicate} expects {expected} at {argument}")

    # -- lookups ------------------------------------------------------------
    def by_provenance(self, *provenance):
        return [self.contracts[n] for n in self.order if self.contracts[n].provenance in provenance]

    def object_id(self, sort, value):
        return self.sorts[sort].object_id(value)

    def certified_contracts(self):
        """Contracts whose guarantees may discharge another operation's precondition."""
        return [c for c in self.by_provenance(GIVEN, ACQUIRED)]


# ---------------------------------------------------------------------------
# Proof context: what is known about objects
# ---------------------------------------------------------------------------

@dataclass
class ProofContext:
    """Conditions known to hold of concrete objects, each with its justification."""

    known: dict = field(default_factory=dict)

    @staticmethod
    def _slot(predicate, object_ids):
        return (predicate, tuple(object_ids))

    # A condition checked in passing while discharging a precondition is the weakest
    # evidence: it holds of these objects and of nothing else. A guarantee of an
    # operation, or a rule's derivation, says why it holds, and can be reproduced by
    # re-running that operation. Better evidence replaces weaker evidence for the
    # same condition; evidence of the same strength is kept as first recorded.
    STRENGTH = {"checked": 0, "context": 1, "instance": 0, "checked_guarantee": 2, "derivation": 2}

    def assume(self, predicate, object_ids, *, source="hypothesis"):
        self.record(predicate, object_ids, {"kind": "context", "source": source})

    def record(self, predicate, object_ids, justification):
        slot = self._slot(predicate, object_ids)
        known = self.known.get(slot)
        if known is None or self.STRENGTH.get(justification["kind"], 0) > self.STRENGTH.get(known["kind"], 0):
            self.known[slot] = justification

    def lookup(self, predicate, object_ids):
        return self.known.get(self._slot(predicate, object_ids))

    def as_json(self):
        return [{"predicate": p, "objects": list(o), "justification": j} for (p, o), j in self.known.items()]


# ---------------------------------------------------------------------------
# Execution of one contract: preconditions, computation, guarantees, cost
# ---------------------------------------------------------------------------

class Session:
    """Executes contracts, keeps the proof context, and charges one shared counter."""

    def __init__(self, registry, *, counter=None, context=None, emit=None, verify_derivations=False):
        self.registry = registry
        self.counter = counter if counter is not None else OperationCounter()
        self.context = context if context is not None else ProofContext()
        self.emit = emit
        # When true, a guarantee that a contract establishes by derivation is also
        # decided exactly. Tests run this way; it costs the recomputation that the
        # derivation exists to avoid, so measured runs report which mode they used.
        self.verify_derivations = verify_derivations
        self.executions = []

    # -- helpers ------------------------------------------------------------
    def object_ids(self, contract, binding, value=None):
        sorts = dict(contract.params)
        ids = {name: self.registry.object_id(sorts[name], binding[name]) for name in binding}
        if value is not None:
            ids["v"] = self.registry.object_id(contract.result, value)
        return ids

    def _values(self, condition, binding, value=None):
        environment = dict(binding)
        if value is not None:
            environment["v"] = value
        return [environment[a] for a in condition.args]

    def check(self, condition, binding, value=None):
        """Decision of a condition, charged to the shared counter.

        A condition with its own decision procedure is decided exactly. A condition
        that is only defined is decided by its definition: witnesses among what has
        been established.
        """
        self.counter.charge("condition_check")
        predicate = self.registry.predicates.get(condition.predicate)
        if predicate is not None:
            return bool(predicate.check(*self._values(condition, binding, value), counter=self.counter))
        definition = self.registry.definitions.get(condition.predicate)
        if definition is None:
            raise ContractRefused(f"unknown predicate {condition.predicate}")
        sorts = dict(zip(condition.args, definition.sorts, strict=True))
        environment = dict(binding) | ({"v": value} if value is not None else {})
        objects = [self.registry.object_id(sorts[a], environment[a]) for a in condition.args]
        return self.entails(definition, objects) is not None

    # -- discharge of preconditions ----------------------------------------
    def discharge(self, contract, condition, binding, ids):
        """Context first, then inheritance, then an exact check. Never assumed."""
        objects = [ids[a] for a in condition.args]
        known = self.context.lookup(condition.predicate, objects)
        if known is not None:
            self.counter.charge("precondition_inherited")
            return {"condition": condition.as_json(), "objects": objects,
                    "status": "discharged", "justification": dict(known)}
        if self.check(condition, binding):
            justification = {"kind": "checked", "by": contract.name, "execution": len(self.executions)}
            self.context.record(condition.predicate, objects, justification)
            return {"condition": condition.as_json(), "objects": objects,
                    "status": "discharged", "justification": justification}
        return None

    # -- one application ----------------------------------------------------
    def apply(self, contract, binding):
        """Run one contract. Returns a PrimitiveResult, or None when it does not apply."""
        before = self.counter["total"]
        ids = self.object_ids(contract, binding)
        discharged = []
        for condition in contract.pre:
            record = self.discharge(contract, condition, binding, ids)
            if record is None:
                self.counter.charge("precondition_refused")
                return None
            discharged.append(record)
        value = contract.run(binding, self.counter) if contract.run is not None else None
        if value is None:
            return None
        ids = self.object_ids(contract, binding, value)
        derived = contract.derivation is not None and contract.provenance != CANDIDATE
        guarantees = []
        for condition in contract.post:
            objects = [ids[a] for a in condition.args]
            if not derived or self.verify_derivations:
                if not self.check(condition, binding, value):
                    if contract.provenance == CANDIDATE:
                        return None
                    raise ContractViolation(f"{contract.name} did not establish {condition.as_json()}")
            if contract.provenance == CANDIDATE:
                status, justification = "instance", {"kind": "instance", "by": contract.name}
            else:
                status = "certified"
                justification = {"kind": "derivation" if derived else "checked_guarantee",
                                 "by": contract.name, "provenance": contract.provenance,
                                 "rule": (contract.derivation or {}).get("rule", ""),
                                 "verified_exactly": bool(not derived or self.verify_derivations),
                                 "execution": len(self.executions)}
                self.context.record(condition.predicate, objects, justification)
            guarantees.append({"condition": condition.as_json(), "objects": objects,
                               "status": status, "justification": justification})
        cost = self.counter["total"]-before
        step = {"contract": contract.name, "contract_id": contract.identity(),
                "provenance": contract.provenance, "generation": contract.generation,
                "objects": ids, "pre": discharged, "post": guarantees, "cost": cost}
        self.executions.append(step)
        if self.emit is not None:
            self.emit("apply", step)
        return PrimitiveResult(value=value, certificate_step=step)

    # -- planner interface --------------------------------------------------
    def runtime_primitive(self, contract):
        def execute(facts, contract=contract):
            binding = {name: fact.value for (name, _), fact in zip(contract.params, facts, strict=True)}
            return self.apply(contract, binding)
        return RuntimePrimitive(name=contract.name, source_sorts=contract.source_sorts,
                                target_sort=contract.result, execute=execute)

    def runtime_primitives(self, contracts=None):
        """Supplied scheduling, not part of any guarantee.

        An operation that returns one of its arguments adds a guarantee and no new
        object, so it is offered first: a precondition that a rule can discharge is
        then discharged instead of recomputed. Acquired operations come before the
        given ones they were composed from.
        """
        contracts = self.registry.certified_contracts() if contracts is None else contracts
        def priority(contract):
            return (0 if contract.returns is not None else 1,
                    0 if contract.provenance == ACQUIRED else 1)
        return tuple(self.runtime_primitive(c) for c in sorted(contracts, key=priority))

    def value_key(self):
        return lambda sort, value: self.registry.object_id(sort, value)

    # -- derivation from what has been established --------------------------
    def entails(self, definition, objects, *, depth=3):
        """Witnesses that make a specification true of these objects, or None.

        The search runs over the proof context — what has been established — and
        never over what could be recomputed. A conjunct that is itself a defined
        specification is unfolded, so a goal can be met either by an operation
        that concludes it directly or by the operations its definition names.
        Candidate guarantees are not in the context, so they can never make a
        specification come out true.
        """
        self.counter.charge("derivation_search")
        start = dict(zip(definition.params, objects, strict=True))
        fresh = [0]

        def solve(conjuncts, assignment, level):
            if not conjuncts:
                return dict(assignment)
            condition, rest = conjuncts[0], conjuncts[1:]
            for (predicate, ids), _ in list(self.context.known.items()):
                if predicate != condition.predicate or len(ids) != len(condition.args):
                    continue
                trial, ok = dict(assignment), True
                for name, object_id in zip(condition.args, ids, strict=True):
                    if trial.setdefault(name, object_id) != object_id:
                        ok = False
                        break
                if not ok:
                    continue
                found = solve(rest, trial, level)
                if found is not None:
                    return found
            inner = self.registry.definitions.get(condition.predicate)
            if inner is not None and level > 0 and all(a in assignment for a in condition.args):
                fresh[0] += 1
                rename = dict(zip(inner.params, condition.args, strict=True))
                rename |= {name: f"{name}#{fresh[0]}" for name in inner.exists}
                self.counter.charge("definition_unfolded")
                found = solve([c.rename(rename) for c in inner.body]+rest, assignment, level-1)
                if found is not None:
                    return found
            return None

        return solve(list(definition.body), start, depth)

    def specification_goal(self, definition, bindings, goal_sort, result_param="v"):
        """A goal stated as a specification: the fact must satisfy it under the established guarantees."""
        def holds(fact):
            objects = [self.registry.object_id(goal_sort, fact.value) if p == result_param else bindings[p]
                       for p in definition.params]
            return self.entails(definition, objects) is not None
        return holds

    # -- goals --------------------------------------------------------------
    def goal_predicate(self, condition, objects):
        """A goal is a specification: the fact's own guarantees must state `condition` of `objects`."""
        wanted = (condition.predicate, tuple(objects))
        def holds(fact):
            step = fact.certificate_step
            if step is None:
                return False
            for entry in step["post"]:
                if entry["status"] != "certified":
                    continue
                if (entry["condition"][0], tuple(entry["objects"])) == wanted:
                    return True
            return False
        return holds

    def solve(self, *, initial, goal_sort, goal_condition=None, goal_objects=None, goal_spec=None,
              contracts=None, max_depth=8, max_states=400, progress=None):
        """Ordinary typed search over the registry; the planner is the one in the repository.

        A goal is a specification, not a route: `goal_spec` decides from a fact's
        own certified guarantees whether it is what was asked for.
        """
        facts = [initial_fact(sort, value) for sort, value in initial]
        for sort, value in initial:
            self.registry.object_id(sort, value)
        predicates = None
        if goal_spec is not None:
            predicates = {goal_sort: goal_spec}
        elif goal_condition is not None:
            predicates = {goal_sort: self.goal_predicate(goal_condition, goal_objects)}
        plan = synthesize_typed_plan(
            facts, self.runtime_primitives(contracts), [goal_sort],
            max_depth=max_depth, max_states=max_states,
            goal_predicates=predicates, value_key=self.value_key(), progress=progress)
        return plan


# ---------------------------------------------------------------------------
# Reading a plan back as an executable DSL body
# ---------------------------------------------------------------------------

def plan_body(plan, goal_sort, initial_names):
    """The proof DAG of a plan as a body in the edit calculus grammar.

    `initial_names[i]` names the i-th initial fact. Steps are the applications
    that the goal depends on, in dependency order; the body is executable by
    `operation_acquisition.execute_body` and unfoldable to primitive steps by
    the existing edit calculus.
    """
    goal = plan.goals.get(goal_sort)
    if goal is None:
        return None
    by_id = {fact.id: fact for fact in plan.facts}
    names, steps, counter = {}, [], [0]
    for fact, name in zip([f for f in plan.facts if f.certificate_step is None], initial_names, strict=False):
        names[fact.id] = name

    def visit(fact):
        if fact.id in names:
            return names[fact.id]
        for dependency in fact.dependencies:
            visit(by_id[dependency])
        counter[0] += 1
        out = f"t{counter[0]}"
        names[fact.id] = out
        steps.append({"out": out, "prim": fact.certificate_step["contract"],
                      "args": [names[d] for d in fact.dependencies]})
        return out

    result = visit(goal)
    used = [names[f.id] for f in plan.facts if f.certificate_step is None and f.id in names]
    return {"params": [n for n in initial_names if n in used], "steps": steps, "result": result}
