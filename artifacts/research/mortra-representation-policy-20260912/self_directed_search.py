"""One task in, an answer out, with nothing hand-picked in between.

The point of this module is to be checkable rather than impressive. A task is
handed in stating only what it needs -- its transition, the quantity it reads,
its goal and which words it may use. Everything after that is the system's:

    1. the premise is re-proved, not assumed
    2. candidate observables come off the stated grammar, in its fixed order.
       No candidate is supplied, preferred or excluded from outside.
    3. each candidate is put to the closure prover. Most are refused there.
    4. each surviving representation is put to the certificate for THIS task.
       Refusals are kept, with their counterexamples.
    5. each admitted representation is measured on a small probe of the task,
       every component separately
    6. the selection is a Pareto frontier over those components. No weighting,
       no total, and a representation is never dropped for losing on one
       component alone.
    7. the task is answered with the selected representation at lengths the
       enumeration cannot reach, and checked against the enumeration at the
       lengths it can.

What would make this not a search: handing in a candidate, filtering the grammar
towards one, or choosing between representations by anything other than the
measurements. `trace` records enough of each step that all three are visible if
they happen.
"""
from __future__ import annotations

import sympy as sp

from math_os_prototype import fold_observable_system as observables
from math_os_prototype import fold_tasks
from math_os_prototype import representation_benchmarks as benchmarks
from math_os_prototype import representation_certificate as certificates
from math_os_prototype import representation_evaluation as E
from math_os_prototype import representation_ledger as ledgers
from math_os_prototype import representation_policy as policy

SCHEMA = "mortra.self-directed-search.v1"


def _closure_record(found, premise):
    return {"observable": found["observable"], "basis": found["basis"],
            "action_matrices": found["action_matrices"],
            "dimension": found["dimension"],
            "identity_residuals_all_zero": found["identity_residuals_all_zero"],
            "closure_scope": found["scope"],
            "step_premise": premise}


def solve(task, *, degree=1, max_terms=1, coefficients=(1,),
          candidate_limit=None, dimension_cap=64, certificate_depth=5,
          probe_length=6, verify_lengths=(5, 6, 7), answer_lengths=(10, 12),
          ledger=None, frame_depth=4):
    """Work the task through, and record every decision on the way."""
    trace = {"schema": SCHEMA, "task": task.name, "goal": task.goal,
             "grammar": {"degree": degree, "max_terms": max_terms,
                         "coefficients": list(coefficients),
                         "limit": candidate_limit,
                         "source": "fold_observable_system.candidate_observables",
                         "note": ("the enumeration and its order are the "
                                  "grammar's; nothing is injected or excluded "
                                  "here")}}
    book = ledger if ledger is not None else ledgers.Ledger()

    # 1. the premise
    premise_run = E.measure(lambda: {"value": observables.verify_step(
        observables.fold_system(), depth=frame_depth)})
    premise = premise_run["value"]
    trace["premise"] = {"exact": premise["exact"],
                        "identities_checked": premise["identities_checked"],
                        "frames_checked": premise["frames_checked"],
                        "centre": premise["centre"], "scope": premise["scope"],
                        "cost": {"wall_time": premise_run["wall_time"],
                                 "primitive_calls": premise_run["primitive_calls"]}}
    if not premise["exact"]:
        trace["stopped"] = "the one-step correspondence is not exact"
        return trace
    system = observables.fold_system()

    # 2. candidates, from the grammar
    offered = observables.candidate_observables(
        degree=degree, max_terms=max_terms, coefficients=tuple(coefficients),
        limit=candidate_limit)
    trace["candidates_offered"] = [str(c) for c in offered]

    # 3 and 4. closure, then the certificate for this task
    considered, refused_closure, refused_certificate = [], [], []
    for candidate in offered:
        acquisition = E.measure(lambda: {"value": observables.acquire_closure(
            system, candidate, maximum_dimension=dimension_cap)})
        found = acquisition["value"]
        if not found["closed"]:
            refused_closure.append({"observable": str(candidate),
                                    "reason": found["reason"]})
            continue
        record = _closure_record(found, premise)
        certificate = certificates.certify(record, task, depth=certificate_depth,
                                           premise=premise)
        cost = {"acquisition_time": acquisition["wall_time"],
                "acquisition_primitive_calls": acquisition["primitive_calls"],
                "acquisition_proof_calls": acquisition["proof_calls"],
                "acquisition_peak_memory": acquisition["peak_memory"],
                "acquisition_search_nodes": len(trace["candidates_offered"]),
                "acquisition_search_note": ("candidates enumerated from the "
                                            "grammar up to this point")}
        if not certificates.admissible(certificate):
            refused_certificate.append({
                "observable": found["observable"],
                "dimension": found["dimension"],
                "refused_by": certificate["refused_by"],
                "counterexample": policy._first_counterexample(certificate)})
            book.note_certificate(
                {"kind": "observation representation",
                 "observable": found["observable"], "basis": found["basis"],
                 "dimension": found["dimension"],
                 "action_matrices": found["action_matrices"],
                 "identity": "Phi(T_g(x)) = B_g Phi(x)"}, certificate)
            continue
        considered.append((record, certificate, cost))

    trace["refused_at_closure"] = refused_closure
    trace["refused_by_certificate"] = refused_certificate
    trace["admitted"] = [r["observable"] for r, _, _ in considered]
    if not considered:
        trace["stopped"] = ("no candidate in this grammar both closed and "
                            "preserved what the task needs")
        return trace

    # 5. measure each admitted representation on a probe of the same task
    for record, certificate, cost in considered:
        evaluation = benchmarks.fold_search_comparison(
            f"{record['observable']}: probe at length {probe_length}",
            record, cost, task=task, length=probe_length,
            certificate=certificate)
        book.observe({"kind": "observation representation",
                      "observable": record["observable"],
                      "basis": record["basis"],
                      "dimension": record["dimension"],
                      "action_matrices": record["action_matrices"],
                      "identity": "Phi(T_g(x)) = B_g Phi(x)"},
                     evaluation, certificate=certificate, acquisition=cost)
    trace["probe_length"] = probe_length

    # 6. the choice, by Pareto front
    entries = book.admissible_for(task.name)
    chosen = policy.select(entries, task=task.name)
    trace["selection"] = {
        "front_sizes": chosen["front_sizes"],
        "order": chosen["order"], "gate": chosen["gate"],
        "offered": [{"observable": row["observable"], "front": row["front"],
                     "dimension": row["dimension"], "status": row["status"],
                     "objectives": {k: v for k, v in row["objectives"].items()
                                    if v is not None}}
                    for row in chosen["selected"]],
        "not_admissible": chosen["not_admissible"]}
    if not chosen["selected"]:
        trace["stopped"] = "nothing was admissible for this task"
        return trace
    winner = chosen["selected"][0]
    selected = next(r for r, _, _ in considered
                    if r["observable"] == winner["observable"])
    trace["selected"] = {"observable": selected["observable"],
                         "dimension": selected["dimension"],
                         "basis": selected["basis"],
                         "front": winner["front"],
                         "why": ("first of the first Pareto front; nothing in "
                                 "the set beats it on every measured component")}

    closure = observables.closure_from_record(selected)

    # 7. answer, and check where checking is possible
    checks = []
    for length in verify_lengths:
        independent = fold_tasks.answer_by_enumeration(task, length)
        represented = benchmarks.represented_search_run(closure, task, length)
        checks.append({"length": length, "by_enumeration": independent,
                       "by_representation": represented["value"],
                       "agree": independent == represented["value"],
                       "words_enumerated": len(task.alphabet) ** length,
                       "nodes_with_representation": represented["search_nodes"]})
    answers = []
    for length in answer_lengths:
        run = E.measure(lambda: benchmarks.represented_search_run(
            closure, task, length))
        answers.append({"length": length, "answer": run["value"],
                        "search_nodes": run["search_nodes"],
                        "candidates_expanded": run["candidates_generated"],
                        "wall_time": run["wall_time"],
                        "words_this_stands_for": len(task.alphabet) ** length,
                        "enumeration_would_have_taken":
                            f"{len(task.alphabet) ** length} words x {length} "
                            "fold steps"})
    trace["verification"] = checks
    trace["answers"] = answers
    trace["all_checks_agree"] = all(c["agree"] for c in checks)
    trace["ledger_entries"] = len(book.entries)
    trace["scope"] = ("the answers at the longer lengths are not enumerated and "
                      "not checked against enumeration; they rest on the "
                      "certificate, whose own scope is stated in it")
    return trace, book


def render(trace):
    """The run as a page, close to the order it happened in."""
    if isinstance(trace, tuple):
        trace = trace[0]
    lines = [f"task   : {trace['task']}", f"goal   : {trace['goal']}", ""]
    premise = trace.get("premise", {})
    lines.append(f"premise: exact={premise.get('exact')} "
                 f"identities={premise.get('identities_checked')} "
                 f"frames={premise.get('frames_checked')}")
    lines.append(f"grammar: {trace['grammar']['degree']} degree, "
                 f"{trace['grammar']['max_terms']} term(s) -> "
                 f"{len(trace['candidates_offered'])} candidates offered")
    lines.append(f"         {trace['candidates_offered']}")
    lines.append("")
    lines.append(f"refused at closure    : {len(trace.get('refused_at_closure', []))}")
    for row in trace.get("refused_at_closure", [])[:6]:
        lines.append(f"    {row['observable']}: {row['reason'][:70]}")
    lines.append(f"refused by certificate: {len(trace.get('refused_by_certificate', []))}")
    for row in trace.get("refused_by_certificate", [])[:8]:
        lines.append(f"    {row['observable']} (dim {row['dimension']}): "
                     f"refused by {row['refused_by']}")
    lines.append(f"admitted              : {trace.get('admitted')}")
    lines.append("")
    if "selection" in trace:
        lines.append(f"Pareto fronts: {trace['selection']['front_sizes']}")
        for row in trace["selection"]["offered"]:
            lines.append(f"    front {row['front']}  {row['observable']} "
                         f"(dim {row['dimension']}): {row['objectives']}")
        lines.append("")
    if "selected" in trace:
        lines.append(f"selected: {trace['selected']['observable']} "
                     f"dim {trace['selected']['dimension']}")
        lines.append(f"          basis {trace['selected']['basis']}")
        lines.append(f"          {trace['selected']['why']}")
        lines.append("")
    for check in trace.get("verification", []):
        lines.append(f"length {check['length']:>2}  enumeration "
                     f"{check['by_enumeration']}  ->  agrees "
                     f"{check['agree']}  (nodes with representation "
                     f"{check['nodes_with_representation']})")
    lines.append("")
    for answer in trace.get("answers", []):
        lines.append(f"length {answer['length']:>2}  answer {answer['answer']}")
        lines.append(f"           {answer['search_nodes']} nodes, "
                     f"{answer['candidates_expanded']} classes, "
                     f"{answer['wall_time']}s, standing for "
                     f"{answer['words_this_stands_for']} words")
    if "stopped" in trace:
        lines.append(f"stopped: {trace['stopped']}")
    lines.append("")
    lines.append(f"scope: {trace.get('scope', '')}")
    return "\n".join(lines)
