"""The loop: pose, solve, acquire, choose what to study next, and measure what changed.

Everything that reasons is already in the repository. This module only runs the
cycle and keeps the books:

    posing            `geometry_self_posing` builds a construction and hides it;
    screening         the current solver decides how hard a posed task is, so the
                      curriculum can prefer tasks just past the current budget;
    solving           `geometry_relational_search.RelationalSynthesis`, one fresh
                      instance per task, so no answer and no cache crosses tasks;
    acquisition       `geometry_acquisition` certifies a solved construction as a
                      general operation and registers it for later retrieval;
    policy            a policy is data: which families are offered first, how the
                      application and expansion budget is split between the
                      phases, how many library programs a binding may try. A
                      candidate is proposed from the recorded stop reasons and is
                      kept only if it helps on the validation tasks.

What may cross a task boundary is stated explicitly: the library and the policy.
Nothing else does.
"""
from __future__ import annotations

from collections import Counter
from copy import deepcopy
import time

from math_os_prototype import geometry_acquired_library as acqlib
from math_os_prototype import geometry_acquisition as acq
from math_os_prototype import geometry_relational_search as search
from math_os_prototype import geometry_self_posing as posing

START_POLICY = {
    "guaranteed_applications": 40, "guaranteed_expansions": 2000,
    "partial_root_coverage": True, "partial_applications": 16, "partial_expansions": 1000,
    "max_plan_steps": 6, "wall_seconds": 20, "library_programs_per_binding": 2,
    # the enumerated index is written over three named points; an operation acquired
    # from a task whose goals mention more is stored over as many as it needs
    "library_slots": ("p0", "p1", "p2", "p3", "p4"),
}

COST_KEYS = ("applications", "plan_expansions", "polynomial_checks", "predicate_prover_calls",
             "guard_checks", "library_queries", "library_exact_certifications",
             "identity_bindings_excluded", "refuted_before_charge", "duplicate_outputs",
             "distinctness_failures", "goal_replay_failures")


def solve(task, *, library=None, policy=None, applications=40):
    """One task, one fresh solver. The library and the policy are the only things carried in."""
    configuration = dict(START_POLICY, **(policy or {}))
    started = time.perf_counter()
    synthesis = search.RelationalSynthesis(task, configuration,
                                           library=library if (library and library.programs) else None)
    row = synthesis.search(applications)
    row["seconds"] = time.perf_counter()-started
    return row


def measurements(row):
    """The cost of one attempt, separated the way the comparison needs it."""
    costs = row.get("costs", {})
    solution = row.get("solution") or {}
    replay = solution.get("replay") or {}
    return {"solved": bool(row.get("solved")), "stop_reason": row.get("stop_reason"),
            "search_states": costs.get("plan_expansions", 0),
            "primitive_applications": costs.get("applications", 0),
            "primitive_expansion_operations": replay.get("primitive_operations"),
            "checking": costs.get("polynomial_checks", 0)+costs.get("predicate_prover_calls", 0)
                        +costs.get("guard_checks", 0),
            "library_certifications": costs.get("library_exact_certifications", 0),
            "execution_seconds": costs.get("execution_seconds", 0.0),
            "search_seconds": costs.get("search_seconds", 0.0),
            "wall_seconds": row.get("seconds", row.get("wall_seconds", 0.0)),
            "costs": {key: costs.get(key, 0) for key in COST_KEYS}}


def screen(task, *, library=None, policy=None, small=4, medium=24):
    """How hard the task is for the solver as it stands now."""
    tight = dict(policy or {}, wall_seconds=6, guaranteed_applications=small, partial_applications=0,
                 guaranteed_expansions=120, partial_expansions=0, partial_root_coverage=False)
    first = solve(task, library=library, policy=tight, applications=small)
    if first["solved"]:
        return {"class": "easy", "small": measurements(first)}
    second = solve(task, library=library, policy=dict(policy or {}, wall_seconds=12), applications=medium)
    return {"class": "boundary" if second["solved"] else "hard",
            "small": measurements(first), "medium": measurements(second)}


def build_pool(seed, count, *, depth, goal_count=2, library=None, policy=None, exclude=(),
               classes=("boundary", "hard", "easy"), attempts=1500, screen_tasks=True,
               require_multistep=False):
    """Pose tasks and label them by how hard they are for the current solver."""
    batch = posing.pose_many(seed, count, depth=depth, goal_count=goal_count, attempts=attempts,
                             exclude=exclude, require_multistep=require_multistep)
    pool = []
    for record in batch["posed"]:
        entry = dict(record)
        if screen_tasks:
            entry["screen"] = screen(record["task"], library=library, policy=policy)
            entry["difficulty"] = entry["screen"]["class"]
        else:
            entry["difficulty"] = "unscreened"
        if entry["difficulty"] in classes:
            pool.append(entry)
    return {"seed": seed, "requested": count, "pool": pool, "rejections": batch["rejections"],
            "difficulty_counts": dict(Counter(entry["difficulty"] for entry in pool))}


def curriculum(pool, *, easy=2, boundary=8, hard=2, prefer_composition=True):
    """A mixture, not only the tasks that already work and not only the impossible ones.

    Tasks that no single primitive can meet are taken first: they are the ones
    where an operation has to be composed, and so the ones where keeping an
    operation can pay later.
    """
    wanted = {"easy": easy, "boundary": boundary, "hard": hard}
    ordered = sorted(pool, key=lambda entry: (0 if (prefer_composition and not entry.get("one_step_reachable"))
                                              else 1))
    chosen, taken = [], Counter()
    for entry in ordered:
        kind = entry["difficulty"]
        if taken[kind] < wanted.get(kind, 0):
            taken[kind] += 1
            chosen.append(entry)
    return chosen


# ---------------------------------------------------------------------------
# A learning stage
# ---------------------------------------------------------------------------

def learn_stage(entries, *, library, policy, applications=40, table=None):
    """Solve each task, certify what can be certified, record why the rest could not."""
    rows, acquisitions, failures = [], [], Counter()
    started = time.perf_counter()
    acquisition_seconds = 0.0
    for entry in entries:
        task = entry["task"]
        row = solve(task, library=library, policy=policy, applications=applications)
        record = {"signature": entry["signature"], "difficulty": entry.get("difficulty"),
                  "hidden_families": entry["hidden"]["families"], "measurements": measurements(row)}
        if row["solved"]:
            record["solution_families"] = [step["prim"] for step in _families(row["solution"])]
            began = time.perf_counter()
            result = acq.acquire(row["solution"], task, table=table)
            if result["acquired"]:
                registration = acq.register(library, result, source={
                    "signature": entry["signature"], "difficulty": entry.get("difficulty"),
                    "goals": [[g["predicate"], list(g["points"])] for g in task["goals"]]})
                record["acquisition"] = {"acquired": True, **registration,
                                         "body": result["body"], "declared": result["declared"]}
                if registration.get("registered"):
                    acquisitions.append(record["acquisition"])
                else:
                    failures["registration_"+registration["reason"][:40]] += 1
            else:
                record["acquisition"] = {"acquired": False, "reason": result["reason"]}
                failures["acquisition_"+result["reason"][:60]] += 1
            acquisition_seconds += time.perf_counter()-began
        else:
            failures["unsolved_"+str(row["stop_reason"])] += 1
        rows.append(record)
    return {"rows": rows, "acquisitions": acquisitions, "failures": dict(failures),
            "seconds": time.perf_counter()-started, "acquisition_seconds": acquisition_seconds,
            "solved": sum(1 for r in rows if r["measurements"]["solved"]), "tasks": len(rows)}


def _families(solution):
    from math_os_prototype import geometry_contracts as gc
    from math_os_prototype import geometry_semantic_dsl as dsl
    term = solution.get("term")
    if not isinstance(term, dict) or term.get("op") == "var":
        return []
    try:
        steps, _ = gc.dag(term, fragment=dsl.FRAGMENT)
    except (ValueError, KeyError):
        return []
    return [{"prim": step["family"]} for step in steps]


# ---------------------------------------------------------------------------
# Policy proposals: data, derived from what went wrong
# ---------------------------------------------------------------------------

def propose_policies(rows, current):
    """Candidate policies, each justified by a recorded stop reason or a recorded success."""
    stops = Counter(row["measurements"]["stop_reason"] for row in rows)
    families = Counter(family for row in rows for family in row.get("solution_families", []))
    candidates = []
    if stops.get("plan_expansion_budget", 0):
        candidates.append(("more expansions, fewer applications per phase",
                           dict(current, guaranteed_expansions=int(current["guaranteed_expansions"]*2),
                                partial_expansions=int(current["partial_expansions"]*2))))
    if stops.get("application_budget", 0):
        candidates.append(("more applications in the guaranteed phase",
                           dict(current, guaranteed_applications=current["guaranteed_applications"]+16,
                                partial_applications=max(0, current["partial_applications"]-8))))
    if stops.get("plans_exhausted", 0) or stops.get("directed_phases_complete", 0):
        candidates.append(("deeper plans",
                           dict(current, max_plan_steps=current["max_plan_steps"]+2)))
    if families:
        order = [family for family, _ in families.most_common()]
        candidates.append(("offer the families that solved training tasks first",
                           dict(current, family_order=order)))
        candidates.append(("that order, with more library programs per binding",
                           dict(current, family_order=order,
                                library_programs_per_binding=current["library_programs_per_binding"]+2)))
    return candidates


def choose_policy(candidates, validation, *, library, applications=40, current=None):
    """Keep a candidate only if it helps on tasks that are not the final evaluation."""
    trials = []
    baseline = evaluate(validation, library=library, policy=current, applications=applications)
    trials.append({"policy": "current", "description": "the policy in force", "summary": baseline["summary"]})
    best, best_key = (current, None), _policy_key(baseline["summary"])
    for description, candidate in candidates:
        result = evaluate(validation, library=library, policy=candidate, applications=applications)
        trials.append({"policy": description, "summary": result["summary"],
                       "changed": {k: v for k, v in candidate.items() if current is None or current.get(k) != v}})
        key = _policy_key(result["summary"])
        if key > best_key:
            best, best_key = (candidate, description), key
    return {"policy": best[0], "chosen": best[1], "trials": trials}


def _policy_key(summary):
    return (summary["solved"], -summary["total_search_states"], -summary["total_wall_seconds"])


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate(entries, *, library=None, policy=None, applications=40, note=""):
    """Run a set of tasks under one library and one policy, and total the costs."""
    rows = []
    for entry in entries:
        row = solve(entry["task"], library=library, policy=policy, applications=applications)
        measured = measurements(row)
        used = acq.used_acquired_operation(row["solution"], library) if (row["solved"] and library) else []
        rows.append({"signature": entry["signature"], "difficulty": entry.get("difficulty"),
                     "probe": entry.get("probe"), "measurements": measured,
                     "used_acquired_operations": used,
                     "solution_families": [step["prim"] for step in _families(row["solution"] or {})],
                     "hidden_families": entry["hidden"]["families"],
                     "solution_point": (row["solution"] or {}).get("point")})
    summary = {"note": note, "tasks": len(rows), "solved": sum(1 for r in rows if r["measurements"]["solved"]),
               "total_search_states": sum(r["measurements"]["search_states"] for r in rows),
               "total_applications": sum(r["measurements"]["primitive_applications"] for r in rows),
               "total_checking": sum(r["measurements"]["checking"] for r in rows),
               "total_library_certifications": sum(r["measurements"]["library_certifications"] for r in rows),
               "total_wall_seconds": sum(r["measurements"]["wall_seconds"] for r in rows),
               "solved_with_an_acquired_operation": sum(1 for r in rows if r["used_acquired_operations"]),
               "primitive_expansion_operations": sum(r["measurements"]["primitive_expansion_operations"] or 0
                                                     for r in rows),
               "stop_reasons": dict(Counter(r["measurements"]["stop_reason"] for r in rows))}
    return {"rows": rows, "summary": summary}
