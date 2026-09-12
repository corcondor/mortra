"""Bounded competence on a declared evaluation set, and the gate for controller changes.

The primitive morphism closure is fixed. Adding a rewrite rule does not add
expressivity: every normal form was already reachable. What changes is the
number of rewrite steps the controller actually takes, so the measured quantity
is search effort, inside a declared budget, under a declared strategy.

What the cost is
    The number of steps the library's own fixed reduction strategy performs.
    It is not the length of the shortest rewrite path, and a change that leaves
    the shortest path untouched can still change this number.

What acceptance proves
    Only this: on the declared evaluation set D = stored tasks + the proposed
    task, every task solved before is still solved and no cheaper, and the
    proposed task moves from unsolved to solved. Nothing is claimed about tasks
    outside D, so this is not monotone growth of R_B(A) over all tasks.

What acceptance does not prove
    That an added rule is mathematically sound. Rules must be certified before
    they reach the library; passing this gate is not a substitute for that.

The evaluation set, the reach criterion and the budget are fixed across an
update and recorded in the receipt, because a verdict computed against a moving
judge would mean nothing.
"""
from __future__ import annotations

from math_os_prototype.representation_progress import digest

SCHEMA = "mortra.bounded-competence.v2"
STRATEGY = "library-fixed greedy reduction; not a shortest-rewrite-path metric"
CRITERIA = ("final_output", "first_arrival")
SCOPE = ("steps taken by the library's fixed reduction strategy at one budget, "
         "on one declared evaluation set; not shortest-path length, not monotone "
         "growth of the solvable set outside that evaluation set")


def library_digest(library):
    """Identify a controller by what it can rewrite, not by its object identity.

    A library that carries its own replayed digest supplies it. Otherwise the
    rule set is digested here. Private state is never read, because an identity
    outside the library's own contract would let two controllers share a name.
    """
    recorded = getattr(library, "sha256", None)
    if isinstance(recorded, str) and len(recorded) == 64:
        return recorded
    rules = getattr(library, "rules", None)
    if rules is None:
        raise ValueError("a controller must expose a digest or its rewrite rules")
    return digest({"schema": SCHEMA, "rules": rules})


def task_digest(tasks, budget, criterion):
    """The judge: which tasks, at what budget, under which reach criterion."""
    return digest({"schema": SCHEMA, "budget": budget, "criterion": criterion,
                   "tasks": [{"id": t["id"], "program": t["program"], "target": t["target"]}
                             for t in tasks]})


def _checked(task, budget, criterion):
    if type(budget) is not int or budget < 1:
        raise ValueError("a budget must be a positive exact integer")
    if criterion not in CRITERIA:
        raise ValueError(f"the reach criterion must be one of {CRITERIA}")
    if not isinstance(task, dict) or "program" not in task or "target" not in task:
        raise ValueError("a task must declare a program and the target form")


def cost(library, task, budget, criterion="final_output"):
    """C_A(task) under the library's fixed strategy, with the reach rule declared.

    final_output   the run stops on its own within the budget and its output is
                   the target; the cost is the number of steps it took.
    first_arrival  the target appears after some prefix of the same run; the
                   cost is the length of the shortest such prefix. Prefixes are
                   taken from the one fixed strategy, so this is still not a
                   shortest-rewrite-path length.

    The trace is replayed before any count is believed, so an unreplayable trace
    is an error rather than a large cost.
    """
    _checked(task, budget, criterion)

    def run(limit):
        output, trace = library.reduce(task["program"], max_steps=limit)
        if not library.replay(trace):
            raise ValueError("a cost may not be recorded from an unreplayed trace")
        steps = len(trace["steps"])
        if steps > limit:
            raise ValueError("a reduction may not exceed its own budget")
        return output, trace, steps

    if criterion == "final_output":
        output, trace, steps = run(budget)
        solved = output == task["target"] and not trace["budget_exhausted"]
        return {"steps": steps, "solved": solved, "budget": budget,
                "criterion": criterion, "strategy": STRATEGY}

    # first_arrival: walk prefixes of the same run until the target shows up.
    for limit in range(0, budget + 1):
        output, _, steps = run(limit) if limit else (task["program"], None, 0)
        if output == task["target"]:
            return {"steps": steps, "solved": True, "budget": budget,
                    "criterion": criterion, "strategy": STRATEGY}
    return {"steps": budget, "solved": False, "budget": budget,
            "criterion": criterion, "strategy": STRATEGY}


def competence(library, tasks, budget, criterion="final_output"):
    """The cost of every task in one table, keyed by task id.

    Duplicate ids are refused: a regression check that silently dropped a task
    would let a controller change hide a slowdown.
    """
    ids = [t["id"] for t in tasks]
    if len(ids) != len(set(ids)):
        raise ValueError("a competence table needs distinct task ids")
    entries = [dict(cost(library, t, budget, criterion), id=t["id"]) for t in tasks]
    table = {"schema": SCHEMA, "controller": library_digest(library),
             "budget": budget, "criterion": criterion, "strategy": STRATEGY,
             "entries": entries, "scope": SCOPE}
    table["sha256"] = digest(table)
    return table


def solved_ids(table):
    """The ids solved inside the budget, on the tasks this table covers."""
    return {e["id"] for e in table["entries"] if e["solved"]}


def acceptance(before_library, after_library, new_task, tasks, budget,
               criterion="final_output"):
    """The gate, as a receipt, on the evaluation set D = tasks + new_task.

    Admitted only when all three hold:
      the proposed task is unsolved by the old controller,
      the proposed task is solved by the new controller,
      no stored task became unsolved or more expensive.
    """
    if any(t["id"] == new_task["id"] for t in tasks):
        raise ValueError("the proposed task is already stored")
    _checked(new_task, budget, criterion)

    evaluation = list(tasks) + [new_task]
    before = competence(before_library, evaluation, budget, criterion)
    after = competence(after_library, evaluation, budget, criterion)
    prior = {e["id"]: e for e in before["entries"]}
    later = {e["id"]: e for e in after["entries"]}

    regressions = [{"id": t["id"], "before": prior[t["id"]]["steps"],
                    "after": later[t["id"]]["steps"]}
                   for t in tasks
                   if later[t["id"]]["steps"] > prior[t["id"]]["steps"]
                   or (prior[t["id"]]["solved"] and not later[t["id"]]["solved"])]

    conditions = {"proposed_task_unsolved_before": not prior[new_task["id"]]["solved"],
                  "proposed_task_solved_after": later[new_task["id"]]["solved"],
                  "no_stored_task_regressed": not regressions}
    evidence = {"schema": SCHEMA, "budget": budget, "criterion": criterion,
                "strategy": STRATEGY,
                "new_task_id": new_task["id"],
                "evaluation_set": sorted(t["id"] for t in evaluation),
                "judge": task_digest(evaluation, budget, criterion),
                "before_controller": before["controller"],
                "after_controller": after["controller"],
                "before_table_sha256": before["sha256"],
                "after_table_sha256": after["sha256"],
                "before_new_task": prior[new_task["id"]]["steps"],
                "after_new_task": later[new_task["id"]]["steps"],
                "regressions": regressions,
                "conditions": conditions,
                "accepted": all(conditions.values()),
                "solved_before": sorted(solved_ids(before)),
                "solved_after": sorted(solved_ids(after)),
                "proves": ("stored tasks retained and the proposed task added, "
                           "on the recorded evaluation set only"),
                "scope": SCOPE}
    evidence["sha256"] = digest(evidence)
    return evidence


def validate_acceptance(evidence):
    """Refuse a decision that its own numbers do not support."""
    if not isinstance(evidence, dict) or evidence.get("schema") != SCHEMA:
        raise ValueError("an acceptance receipt must declare its schema")
    stored = dict(evidence)
    recorded = stored.pop("sha256", None)
    if recorded != digest(stored):
        raise ValueError("acceptance receipt digest does not match its contents")
    if evidence["criterion"] not in CRITERIA:
        raise ValueError("an acceptance receipt must declare a known reach criterion")
    if evidence["accepted"] != all(evidence["conditions"].values()):
        raise ValueError("acceptance verdict does not follow from its own conditions")
    if evidence["accepted"]:
        before, after = set(evidence["solved_before"]), set(evidence["solved_after"])
        if not before < after or evidence["new_task_id"] in before:
            raise ValueError("an accepted change must retain the solved tasks and add the "
                             "proposed one, inside the recorded evaluation set")
        if not set(evidence["evaluation_set"]) >= after:
            raise ValueError("solved tasks must lie inside the recorded evaluation set")
    return evidence["accepted"]


def replay_acceptance(evidence, before_library, after_library, new_task, tasks):
    """Recompute the whole decision from the two controllers and the fixed judge."""
    validate_acceptance(evidence)
    fresh = acceptance(before_library, after_library, new_task, tasks,
                       evidence["budget"], evidence["criterion"])
    if fresh != evidence:
        raise ValueError("acceptance receipt failed replay against the supplied controllers")
    return fresh["accepted"]
