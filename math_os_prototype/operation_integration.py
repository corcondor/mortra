"""Goals stated as specifications, solved by the ordinary search, and what is acquired from them.

The three integration goals are:

    ker(A) / im(B) under A B = 0   (`homology_of`)     the first integration task
    H_q of a chain complex         (`homology_at`)     built from what the first acquired
    the tangent directions that     (`tangent_quotient`) built from the same acquired operation,
    extra equations remove                              on a problem of a different kind

Only the specifications and the given contracts are supplied. Which sequence of
operations meets a specification is found by the planner; the composite is then
registered as an operation and is available to the goals that follow.
"""
from __future__ import annotations

from collections import Counter

from math_os_prototype import algebraic_operation_domain as dom
from math_os_prototype import geometry_relational_edit as edit
from math_os_prototype.operation_acquisition import (
    AcquisitionRefused,
    acquire,
    body_from_executions,
    derive_specification,
    edit_domain,
    execute_body,
    expand,
    required_executions,
)
from math_os_prototype.operation_contracts import ACQUIRED, Session
from math_os_prototype.runtime_typed_planner import RuntimeSearchProgress

GOAL_SORT = {"homology_of": "Quotient", "homology_at": "Quotient", "tangent_quotient": "Quotient"}


def new_session(*, verify_derivations=False, emit=None, contracts=dom.GIVEN_CONTRACTS):
    return Session(dom.base_registry(contracts), verify_derivations=verify_derivations, emit=emit)


# ---------------------------------------------------------------------------
# Solving a specification
# ---------------------------------------------------------------------------

def search_phases(session):
    """Supplied scheduling, not part of any guarantee.

    While an acquired operation reaches a sort, the given operations that reach
    the same sort are held back: the compressed route is tried first. If that
    finds nothing, everything is offered.
    """
    certified = session.registry.certified_contracts()
    acquired_sorts = {c.result for c in certified if c.provenance == ACQUIRED}
    phases = []
    if acquired_sorts:
        phases.append(("prefer acquired", [c for c in certified
                                           if c.provenance == ACQUIRED or c.result not in acquired_sorts]))
    phases.append(("all operations", certified))
    return phases


def solve_specification(session, specification, inputs, *, max_states=2000, max_depth=8):
    """`inputs` maps each specification parameter (except the result) to (sort, value)."""
    definition = session.registry.definitions[specification]
    bindings = {name: session.registry.object_id(*inputs[name]) for name in inputs}
    goal_sort = GOAL_SORT[specification]
    started = len(session.executions)
    attempts = []
    for label, contracts in search_phases(session):
        progress = RuntimeSearchProgress()
        plan = session.solve(initial=list(inputs.values()), goal_sort=goal_sort,
                             goal_spec=session.specification_goal(definition, bindings, goal_sort),
                             contracts=contracts, max_depth=max_depth, max_states=max_states,
                             progress=progress)
        attempts.append({"phase": label, "states": plan.states_explored, "solved": plan.complete})
        if plan.complete:
            return {"plan": plan, "bindings": bindings, "goal_sort": goal_sort, "progress": progress,
                    "solved": True, "phase": label, "attempts": attempts, "started": started}
    return {"plan": plan, "bindings": bindings, "goal_sort": goal_sort, "progress": progress,
            "solved": False, "phase": None, "attempts": attempts, "started": started}


def acquire_from(session, solution, inputs, *, name, specification, parents=(), note=""):
    """Register the solution as an operation of the same language.

    The body is built from the executions the result and its derivation rest on,
    not merely from the steps that produced the value: a witness the guarantee
    needs is part of the operation.
    """
    plan, goal_sort = solution["plan"], solution["goal_sort"]
    if not solution["solved"]:
        raise AcquisitionRefused(f"{name}: no solution to acquire")
    definition = session.registry.definitions[specification]
    result_id = session.registry.object_id(goal_sort, plan.goals[goal_sort].value)
    derivation = derive_specification(session, definition, solution["bindings"], result_id)
    if derivation is None:
        raise AcquisitionRefused(f"{name}: the specification does not follow from what was established")
    goal_step = plan.goals[goal_sort].certificate_step
    body = body_from_executions(session, required_executions(session, derivation, goal_step), inputs,
                                result_id, since=solution.get("started", 0))
    return acquire(session, name=name, body=body,
                   parameters=[(parameter, inputs[parameter][0]) for parameter in body["params"]],
                   specification=specification, spec_binding={p: p for p in inputs},
                   bindings=solution["bindings"], result_id=result_id,
                   result_sort=goal_sort, parents=parents, note=note)


# ---------------------------------------------------------------------------
# Generalising an acquired operation inside the same calculus
# ---------------------------------------------------------------------------

def abstract_step(session, contract, step_out, parameter="op0"):
    """Lift the operation at one step of an acquired body to an operation parameter.

    The parameter's interface is that step's guarantees, written over the step's
    own inputs and output: any operation offering at least that interface may be
    instantiated in its place.
    """
    body = contract.body
    step = next((s for s in body["steps"] if s["out"] == step_out), None)
    if step is None:
        raise AcquisitionRefused("no such step")
    inner = session.registry.contracts[step.get("prim") or step.get("call")]
    index = {p: i for i, (p, _) in enumerate(inner.params)}
    interface = [[condition.predicate,
                  ["o" if a == "v" else f"i{index[a]}" for a in condition.args]]
                 for condition in inner.post if all(a == "v" or a in index for a in condition.args)]
    steps = [{"out": s["out"], "ovar": parameter, "args": list(s["args"])} if s["out"] == step_out
             else dict(s) for s in body["steps"]]
    higher = {"params": [{"name": p, "sort": "Object"} for p in body["params"]]
                        +[{"name": parameter, "sort": "Op", "inputs": len(step["args"]), "outputs": 1,
                           "interface": interface, "witnesses": [inner.name]}],
              "body": {"params": list(body["params"]), "steps": steps, "result": body["result"]},
              "post": [[c.predicate, list(c.args)] for c in contract.post],
              "parents": [contract.name], "generation": contract.generation,
              "id": f"op.ho.{contract.name}.{step_out}"}
    return higher


def instantiate(session, higher, arguments):
    """Instantiate the operation parameters, by the repository's edit calculus."""
    return edit.instantiate_operation(higher, arguments, {}, domain=edit_domain(session.registry))


def reacquire(session, definition, inputs, *, name, specification, parents=(), note=""):
    """Re-certify an edited body: execute it, derive the specification again, register it.

    An edit is accepted only through the same gate as an acquisition. Nothing is
    carried over from the operation that was edited.
    """
    body = definition["body"]
    arguments = {parameter: value for parameter, (_, value) in inputs.items()}
    value = execute_body(session, body, {p: arguments[p] for p in body["params"]})
    if value is None:
        raise AcquisitionRefused(f"{name}: the edited body does not apply to these inputs")
    goal_sort = GOAL_SORT[specification]
    return acquire(session, name=name, body=body,
                   parameters=[(parameter, inputs[parameter][0]) for parameter in body["params"]],
                   specification=specification, spec_binding={p: p for p in inputs},
                   bindings={p: session.registry.object_id(*inputs[p]) for p in inputs},
                   result_id=session.registry.object_id(goal_sort, value),
                   result_sort=goal_sort, parents=parents, note=note)


# ---------------------------------------------------------------------------
# Reporting how a run went
# ---------------------------------------------------------------------------

def discharge_summary(session, start=0):
    kinds = Counter()
    for execution in session.executions[start:]:
        for premise in execution["pre"]:
            kinds[premise["justification"]["kind"]] += 1
        for guarantee in execution["post"]:
            kinds["guarantee:"+guarantee["justification"]["kind"]] += 1
    return dict(kinds)


def solution_record(session, solution, *, before_cost, before_executions):
    plan = solution["plan"]
    return {"solved": solution["solved"], "states_explored": plan.states_explored,
            "applications": solution["progress"].applications_completed,
            "operations": session.counter["total"]-before_cost,
            "steps": [step["contract"] for step in plan.proof_program],
            "discharge": discharge_summary(session, before_executions)}


def expansion_of(session, contract):
    """The acquired operation written out in given contracts only."""
    return expand(session.registry, contract.body)


def replay(session, contract, arguments):
    """Execute an acquired operation from its stored body."""
    return execute_body(session, contract.body, arguments)
