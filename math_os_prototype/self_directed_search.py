"""One task in, an answer out, with nothing picked by hand.

The point of this module is to be checkable rather than impressive. A task is
handed in stating only its own contract -- states and start, labels and update,
legality, what is evaluated, what the length counts and what is being counted.
Everything after that is the run's:

    1. the premise is re-proved, not assumed
    2. candidates come off the stated grammar in its fixed order. None is
       supplied, preferred or excluded from outside.
    3. each candidate goes to the closure prover. Its cost is recorded whether
       it survives or not.
    4. each surviving representation goes to the certificate FOR THIS TASK.
       Refusals are kept with their counterexamples, and their cost counts
       towards acquisition too -- a search pays for what it rejected.
    5. candidates spanning the same linear space are collected into one class,
       decided by exact rank, so a reordering of a basis is not counted as a
       second representation
    6. one representative of each class is measured on a small probe of the same
       task, every component separately
    7. the choice is a Pareto frontier over those components. No weighting, no
       total; the tie-break is stated in the record.
    8. the task is answered at lengths the enumeration cannot reach, and checked
       against the enumeration at the lengths it can -- maximum, count attaining
       it, and the whole distribution, not merely the total word count.

What would make this not a search: handing in a candidate, filtering the grammar
towards one, or choosing by anything other than the measurements. `trace` keeps
enough of each step that all three would be visible.
"""
from __future__ import annotations

import sympy as sp

from math_os_prototype import fold_observable_system as observables
from math_os_prototype import fold_tasks
from math_os_prototype import quotient_counting
from math_os_prototype import representation_benchmarks as benchmarks
from math_os_prototype import representation_certificate as certificates
from math_os_prototype import representation_evaluation as E
from math_os_prototype import representation_ledger as ledgers
from math_os_prototype import representation_policy as policy

SCHEMA = "mortra.self-directed-search.v2"

#: stated here rather than decided per run: when two representations are on the
#: same Pareto front, the one the grammar offered first is taken.
TIE_BREAK = (
    "within one Pareto front, and only there: acquisition cost plus the cost of "
    "running the WORKLOAD THE TASK DECLARES -- its own answer lengths -- both "
    "counted in primitive calls, then the earlier candidate in the grammar's "
    "fixed enumeration order. Stated here rather than decided per run.\n"
    "Why this and not the cheaper acquisition: a probe at a small length "
    "measures the wrong thing. An acquisition is paid once and the saving grows "
    "with the length actually asked for, so a tie-break on acquisition alone "
    "would hand every task to the route that learns nothing, whatever the task "
    "goes on to ask. Both sides of the ledger are measured over the same "
    "declared workload instead.\n"
    "This does not reintroduce a weighting across the Pareto components: it is "
    "one quantity in one unit, used only to order candidates that the frontier "
    "has already declared incomparable.")


#: the existing exact route is a candidate too, not only a rung to be measured
#: against. It needs nothing learned and costs nothing to acquire, so if it is
#: not beaten on every component it stays on the first front and the tie-break
#: hands the task to it. A run that chooses it is a correct run.
EXISTING_ROUTE = "existing exact route: merge equal concrete states"


def _existing_route_entry(task, probe_length, book):
    """Measure the repository own exact route on the same probe, as a candidate.

    Its objectives are filled in the same shape as a learned representation so
    the Pareto comparison is between comparable things. Its acquisition cost is
    zero, because there is nothing to acquire.
    """
    naive = E.measure(lambda: benchmarks.enumerate_rung(task, probe_length))
    concrete = E.measure(lambda: benchmarks.concrete_merge_rung(task,
                                                                probe_length))
    measurement = {
        "task": task.name,
        "description_gain_bits": 0,
        "state_dimension_reduction": {"before": 12, "after": 12,
                                      "difference": 0, "ratio": 1.0},
        "primitive_elimination": {
            "before": naive["primitive_calls"],
            "after": concrete["primitive_calls"],
            "eliminated": {}, "derivative_calls_before": 0,
            "derivative_calls_after": 0,
            "derivative_request_calls_before": 0,
            "derivative_request_calls_after": 0},
        "search_reduction": {
            "candidates_before": naive["candidates_generated"],
            "candidates_after": concrete["candidates_generated"],
            "nodes_before": naive["search_nodes"],
            "nodes_after": concrete["search_nodes"],
            "rejected_before": naive["rejected_candidates"],
            "rejected_after": concrete["rejected_candidates"],
            "units": "same as the learned rows"},
        "sequential_depth_reduction": {
            "before": probe_length, "after": probe_length, "ratio": 1.0,
            "not_a_success_condition": "recorded, not required"},
        "measured_wall_time": {
            "before": naive["wall_time"], "after": concrete["wall_time"],
            "saved": round(naive["wall_time"] - concrete["wall_time"], 6)},
        "attribution": None, "break_evens": {}, "provenance": None,
        "certificate_scope": {
            "verdict": "exact by construction",
            "admissible": True,
            "checks": [{"name": "exactness", "kind": "proof",
                        "holds": True,
                        "scope": ("merging states that are equal preserves "
                                  "every function of the state, so the "
                                  "conditions of the counting lemma hold with "
                                  "no representation and nothing to check")}]}}
    entry = {
        "id": "existing-exact-route",
        "kind": "existing exact route",
        "representation": {"kind": "existing exact route",
                           "observable": EXISTING_ROUTE,
                           "dimension": 12,
                           "note": ("no representation is learned; the concrete "
                                    "state is merged with itself")},
        "first_seen_cycle": book.cycle,
        "acquisition_cost": {"acquisition_primitive_calls": 0,
                             "acquisition_time": 0.0,
                             "note": "nothing to acquire"},
        "measurements": [measurement],
        "certificates": [{"task": task.name, "admissible": True,
                          "verdict": "exact by construction",
                          "refused_by": [],
                          "checks": measurement["certificate_scope"]["checks"]}],
        "reuse": {"count": 1, "successes": 1, "failures": 0,
                  "heldout_successes": 0, "tasks": [task.name],
                  "last_used_cycle": book.cycle},
        "status": "active", "dormant_since": None, "deleted": False,
        "deletion_policy": "not stored; rebuilt per task because it costs nothing"}
    return entry, {"naive": naive, "concrete": concrete}


def _closure_record(found, premise):
    return {"observable": found["observable"], "basis": found["basis"],
            "action_matrices": found["action_matrices"],
            "dimension": found["dimension"],
            "identity_residuals_all_zero": found["identity_residuals_all_zero"],
            "closure_scope": found["scope"],
            "step_premise": premise}


def _representation_of(record):
    return {"kind": "observation representation",
            "observable": record["observable"], "basis": record["basis"],
            "dimension": record["dimension"],
            "action_matrices": record["action_matrices"],
            "identity": "Phi(T_g(x)) = B_g Phi(x)"}


def solve(task, *, degree=1, max_terms=1, coefficients=(1,),
          candidate_limit=None, dimension_cap=64, certificate_depth=5,
          probe_length=5, verify_lengths=(5, 6, 7), answer_lengths=(10, 12),
          ledger=None, frame_depth=4):
    """Work the task through, and record every decision on the way."""
    trace = {"schema": SCHEMA, "task": task.name,
             "task_contract": {"goal": task.goal, "counted": task.counted,
                               "length_means": task.length_means,
                               "state": task.state_contract,
                               "legality": ("declared vacuous by the task"
                                            if task.legal_always
                                            else "a predicate on the state"),
                               "notes": task.notes},
             "grammar": {"degree": degree, "max_terms": max_terms,
                         "coefficients": list(coefficients),
                         "limit": candidate_limit,
                         "source": "fold_observable_system.candidate_observables",
                         "note": ("the enumeration and its order are the "
                                  "grammar's; nothing is injected or excluded "
                                  "here")},
             "tie_break": TIE_BREAK}
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
        return trace, book
    system = observables.fold_system()

    # 2. candidates, from the grammar
    offered = observables.candidate_observables(
        degree=degree, max_terms=max_terms, coefficients=tuple(coefficients),
        limit=candidate_limit)
    trace["candidates_offered"] = [str(c) for c in offered]

    # 3 and 4. closure, then the certificate for this task. Every candidate
    # costs something whether it survives or not, and all of it is acquisition.
    survivors, refused_closure, refused_certificate = [], [], []
    search_cost = {"wall_time": premise_run["wall_time"],
                   "primitive_calls": premise_run["primitive_calls"],
                   "proof_calls": premise_run["proof_calls"],
                   "peak_memory": premise_run["peak_memory"]}
    for order, candidate in enumerate(offered):
        acquisition = E.measure(lambda: {"value": observables.acquire_closure(
            system, candidate, maximum_dimension=dimension_cap)})
        found = acquisition["value"]
        certificate = None
        if found["closed"]:
            record = _closure_record(found, premise)
            certification = E.measure(lambda: {"value": certificates.certify(
                record, task, depth=certificate_depth, premise=premise)})
            certificate = certification["value"]
        else:
            certification = {"wall_time": 0.0, "primitive_calls": 0,
                             "proof_calls": 0, "peak_memory": 0}
        for key in ("wall_time", "primitive_calls", "proof_calls", "peak_memory"):
            search_cost[key] += acquisition[key] + certification[key]

        if not found["closed"]:
            refused_closure.append({"observable": str(candidate),
                                    "reason": found["reason"], "order": order})
            continue
        if not certificates.admissible(certificate):
            refused_certificate.append({
                "observable": found["observable"],
                "dimension": found["dimension"], "order": order,
                "refused_by": certificate["refused_by"],
                "counterexample": policy._first_counterexample(certificate)})
            book.note_certificate(_representation_of(record), certificate)
            continue
        survivors.append({"order": order, "record": record,
                          "certificate": certificate})

    trace["refused_at_closure"] = refused_closure
    trace["refused_by_certificate"] = refused_certificate
    trace["admitted"] = [s["record"]["observable"] for s in survivors]
    trace["acquisition_cost"] = {
        "acquisition_time": round(search_cost["wall_time"], 6),
        "acquisition_primitive_calls": search_cost["primitive_calls"],
        "acquisition_proof_calls": search_cost["proof_calls"],
        "acquisition_peak_memory": search_cost["peak_memory"],
        "acquisition_search_nodes": len(offered),
        "candidates_enumerated": len(offered),
        "candidates_refused_at_closure": len(refused_closure),
        "candidates_refused_by_certificate": len(refused_certificate),
        "includes": ("the premise, and the closure and certification of EVERY "
                     "candidate, refused ones included. A search pays for what "
                     "it rejects."),
        "excludes": ("the probe measurements below, which are comparison work "
                     "and are reported separately")}
    if not survivors:
        trace["stopped"] = ("no candidate in this grammar both closed and "
                            "preserved what the task needs")
        trace["stopping_point"] = {
            "candidates_enumerated": len(offered),
            "refused_by": sorted({name for row in refused_certificate
                                  for name in row["refused_by"]}),
            "exact": ("this is a statement about this grammar at this degree "
                      "and these coefficients, and about the certificate depth "
                      "used. Widening any of them is a different question")}
        return trace, book

    # 5. candidates that span the same space are one representation
    classes = []
    for survivor in survivors:
        closure = observables.closure_from_record(survivor["record"])
        for group in classes:
            if certificates.same_span(closure, group["closure"])["same"]:
                group["members"].append(survivor["record"]["observable"])
                break
        else:
            classes.append({"closure": closure, "members":
                            [survivor["record"]["observable"]],
                            "representative": survivor})
    trace["span_classes"] = [
        {"representative": group["representative"]["record"]["observable"],
         "dimension": group["representative"]["record"]["dimension"],
         "members": group["members"], "size": len(group["members"])}
        for group in classes]
    trace["span_class_note"] = ("candidates spanning the same linear space are "
                               "one representation, decided by exact rank on "
                               "shared monomial coordinates. Only one member of "
                               "each class is measured.")

    # 6. measure one representative of each class on a probe of the same task
    for group in classes:
        survivor = group["representative"]
        evaluation = benchmarks.fold_search_comparison(
            f"{survivor['record']['observable']}: probe at length {probe_length}",
            survivor["record"], trace["acquisition_cost"], task=task,
            length=probe_length, certificate=survivor["certificate"])
        book.observe(_representation_of(survivor["record"]), evaluation,
                     certificate=survivor["certificate"],
                     acquisition=trace["acquisition_cost"])
    trace["probe_length"] = probe_length

    # 7. the choice, by Pareto front, tie-broken by the stated rule. The
    # existing exact route is entered as a candidate, not merely as something to
    # be measured against: if nothing beats it on every component it stays on
    # the first front, and costing nothing to acquire it then wins the tie.
    existing, existing_runs = _existing_route_entry(task, probe_length, book)
    entries = book.admissible_for(task.name) + [existing]
    chosen = policy.select(entries, task=task.name)
    order_of = {s["record"]["observable"]: s["order"] for s in survivors}
    cost_of = {s["record"]["observable"]:
               trace["acquisition_cost"]["acquisition_primitive_calls"]
               for s in survivors}
    cost_of[EXISTING_ROUTE] = 0
    # the tie-break: what each front-one candidate would cost over the workload
    # this task declares, plus what it cost to acquire. Measured, not assumed.
    workload = {}
    for row in chosen["selected"]:
        if row["front"] != 1:
            continue
        name = row["observable"]
        if name == EXISTING_ROUTE:
            runs = [E.measure(lambda n=n: benchmarks.concrete_merge_rung(task, n))
                    for n in answer_lengths]
            acquisition = 0
        else:
            survivor = next(s for s in survivors
                            if s["record"]["observable"] == name)
            closure = observables.closure_from_record(survivor["record"])
            runs = [E.measure(lambda n=n: benchmarks.represented_rung(
                closure, survivor["certificate"], task, n))
                for n in answer_lengths]
            acquisition = trace["acquisition_cost"]["acquisition_primitive_calls"]
        workload[name] = {
            "acquisition_primitive_calls": acquisition,
            "workload_primitive_calls": sum(r["primitive_calls"] for r in runs),
            "workload_nodes": sum(r["search_nodes"] for r in runs),
            "workload_wall_time": round(sum(r["wall_time"] for r in runs), 6),
            "lengths": list(answer_lengths)}
        workload[name]["total_primitive_calls"] = (
            acquisition + workload[name]["workload_primitive_calls"])
        workload[name]["acquisition_wall_time"] = (
            0.0 if name == EXISTING_ROUTE
            else trace["acquisition_cost"]["acquisition_time"])
        workload[name]["total_wall_time"] = round(
            workload[name]["acquisition_wall_time"]
            + workload[name]["workload_wall_time"], 6)
        workload[name]["primitive_count_note"] = (
            "zero here means the primitives this route uses are not "
            "instrumented, not that it did no work; read workload_nodes"
            if workload[name]["workload_primitive_calls"] == 0 else None)
    by_time = sorted(workload, key=lambda n: workload[n]["total_wall_time"])
    by_nodes = sorted(workload, key=lambda n: workload[n]["workload_nodes"])
    trace["tie_break_workload"] = {
        "lengths": list(answer_lengths),
        "measured": workload,
        "rule": ("acquisition plus workload, in wall time, smallest first; "
                 "then grammar order"),
        "order_by_wall_time": by_time,
        "order_by_workload_nodes": by_nodes,
        "units_disagree": by_time[:1] != by_nodes[:1],
        "units_disagree_note": ("the two units put a different candidate first. "
                                "The stated rule uses wall time; the node order "
                                "is kept here so the disagreement is visible "
                                "rather than settled silently"
                                if by_time[:1] != by_nodes[:1] else None),
        "note": ("only front-one candidates are measured this way; the Pareto "
                 "frontier has already decided which candidates are "
                 "incomparable and this orders those. One measurement each, so "
                 "a small gap is not a ranking -- `scripts/measure_routes.py` "
                 "is where a repeated timing lives")}

    def tie_key(row):
        found = workload.get(row["observable"])
        return (row["front"], row["status"] != "active",
                found["total_wall_time"] if found else 10 ** 12,
                order_of.get(row["observable"], 10 ** 9))

    front_rows = sorted(chosen["selected"], key=tie_key)
    trace["existing_route_candidate"] = {
        "name": EXISTING_ROUTE,
        "probe_length": probe_length,
        "nodes": existing_runs["concrete"]["search_nodes"],
        "wall_time": existing_runs["concrete"]["wall_time"],
        "acquisition_primitive_calls": 0,
        "why_it_competes": ("it is exact with nothing learned, so it is a "
                            "candidate and not only a baseline. A run that "
                            "picks it is a correct run")}
    trace["selection"] = {
        "front_sizes": chosen["front_sizes"],
        "order": chosen["order"], "gate": chosen["gate"],
        "tie_break": TIE_BREAK,
        "offered": [{"observable": row["observable"], "front": row["front"],
                     "dimension": row["dimension"], "status": row["status"],
                     "grammar_order": order_of.get(row["observable"]),
                     "objectives": {k: v for k, v in row["objectives"].items()
                                    if v is not None}}
                    for row in front_rows],
        "not_admissible": chosen["not_admissible"]}
    if not front_rows:
        trace["stopped"] = "nothing was admissible for this task"
        return trace, book
    winner = front_rows[0]
    if winner["observable"] == EXISTING_ROUTE:
        trace["selected"] = {
            "observable": EXISTING_ROUTE, "dimension": 12, "basis": None,
            "readout": None, "front": winner["front"],
            "kind": "existing exact route",
            "why": ("the existing exact route is on the first Pareto front and "
                    "is cheaper over this task own declared workload once "
                    "acquisition is counted, so the stated tie-break gives it "
                    "the task. Nothing learned was needed here."),
            "workload": workload.get(EXISTING_ROUTE)}
        result = answer_with_concrete(task, verify_lengths=verify_lengths,
                                      answer_lengths=answer_lengths)
        trace.update(result)
        trace["learned_alternatives"] = [
            {"observable": row["observable"], "front": row["front"],
             "dimension": row["dimension"]}
            for row in front_rows if row["observable"] != EXISTING_ROUTE][:5]
        trace["ledger_entries"] = len(book.entries)
        return trace, book
    selected = next(s for s in survivors
                    if s["record"]["observable"] == winner["observable"])
    trace["selected"] = {"observable": selected["record"]["observable"],
                         "dimension": selected["record"]["dimension"],
                         "basis": selected["record"]["basis"],
                         "action_matrices": selected["record"]["action_matrices"],
                         "readout": selected["certificate"]["readout"],
                         "front": winner["front"],
                         "why": ("first of the first Pareto front; nothing in "
                                 "the set beats it on every measured component, "
                                 "and over this task own declared workload it "
                                 "is the cheaper of those the frontier left "
                                 "incomparable"),
                         "workload": workload.get(winner["observable"]),
                         "tie_break": TIE_BREAK}

    result = answer_with(selected["record"], selected["certificate"], task,
                         verify_lengths=verify_lengths,
                         answer_lengths=answer_lengths)
    trace.update(result)
    trace["ledger_entries"] = len(book.entries)
    return trace, book


def answer_with_concrete(task, *, verify_lengths, answer_lengths):
    """Answer with the existing exact route. Same DP, merging on the state."""
    checks = []
    for length in verify_lengths:
        independent = fold_tasks.enumerate_answer(task, length)
        merged = benchmarks.concrete_merge_rung(task, length)
        checks.append({
            "length": length,
            "by_enumeration": independent["answer"],
            "by_representation": merged["value"],
            "answers_agree": independent["answer"] == merged["value"],
            "distributions_agree": (independent["distribution"]
                                    == merged["distribution"]),
            "distribution": independent["distribution"],
            "nodes_enumerating": independent["nodes"],
            "nodes_with_representation": merged["search_nodes"]})
    answers = []
    for length in answer_lengths:
        run = E.measure(lambda: benchmarks.concrete_merge_rung(task, length))
        answers.append({"length": length, "answer": run["value"],
                        "distribution": run["distribution"],
                        "search_nodes": run["search_nodes"],
                        "classes_expanded": run["candidates_generated"],
                        "wall_time": run["wall_time"],
                        "words_this_stands_for": run["value"]["total_words"],
                        "enumerated": False})
    return {"verification": checks, "answers": answers,
            "all_checks_agree": all(c["answers_agree"] and c["distributions_agree"]
                                    for c in checks),
            "scope": ("the answers at the longer lengths were computed by the "
                      "existing exact route and were NOT enumerated. Merging "
                      "equal states needs no certificate: it preserves every "
                      "function of the state by construction.")}


def answer_with(record, certificate, task, *, verify_lengths, answer_lengths):
    """Answer the task with one admitted representation, and check where possible."""
    closure = observables.closure_from_record(record)
    checks = []
    for length in verify_lengths:
        independent = fold_tasks.enumerate_answer(task, length)
        represented = benchmarks.represented_rung(closure, certificate, task,
                                                  length)
        checks.append({
            "length": length,
            "by_enumeration": independent["answer"],
            "by_representation": represented["value"],
            "answers_agree": independent["answer"] == represented["value"],
            "distributions_agree": (independent["distribution"]
                                    == represented["distribution"]),
            "distribution": independent["distribution"],
            "nodes_enumerating": independent["nodes"],
            "nodes_with_representation": represented["search_nodes"]})
    answers = []
    for length in answer_lengths:
        run = E.measure(lambda: benchmarks.represented_rung(
            closure, certificate, task, length))
        answers.append({"length": length, "answer": run["value"],
                        "distribution": run["distribution"],
                        "search_nodes": run["search_nodes"],
                        "classes_expanded": run["candidates_generated"],
                        "wall_time": run["wall_time"],
                        "words_this_stands_for": run["value"]["total_words"],
                        "enumerated": False})
    return {"verification": checks,
            "answers": answers,
            "all_checks_agree": all(c["answers_agree"] and c["distributions_agree"]
                                    for c in checks),
            "scope": ("the answers at the longer lengths were computed by the "
                      "certified DP and were NOT enumerated. They rest on the "
                      "certificate, whose own domain and depth are recorded in "
                      "it.")}


# ---- using a saved representation, without acquiring anything -------------

def solve_from_store(task, book, *, verify_lengths=(), answer_lengths=(12,)):
    """Answer a task from a representation already in the ledger.

    Nothing is enumerated, no closure is acquired and no candidate is offered:
    the basis and the matrices are read back out of the stored entry and used.
    The certificate stored with the entry is what licenses it, and if none of
    the stored entries carries an admitting certificate for this task, that is
    the answer.
    """
    entries = book.admissible_for(task.name)
    if not entries:
        return {"schema": SCHEMA, "task": task.name, "reused": False,
                "reason": ("no stored representation carries a certificate "
                           "admitting it for this task"),
                "stored_entries": len(book.entries)}
    entry = entries[0]
    representation = entry["representation"]
    certificate = policy.certificate_for(entry, task.name)
    record = {"observable": representation["observable"],
              "basis": representation["basis"],
              "action_matrices": representation["action_matrices"],
              "dimension": representation["dimension"],
              "identity_residuals_all_zero": True,
              "closure_scope": "read from the ledger"}
    measured = E.measure(lambda: {"value": answer_with(
        record, certificate, task, verify_lengths=verify_lengths,
        answer_lengths=answer_lengths)})
    result = measured["value"]
    return {"schema": SCHEMA, "task": task.name, "reused": True,
            "from_entry": entry["id"],
            "observable": representation["observable"],
            "dimension": representation["dimension"],
            "certificate_verdict": certificate.get("verdict"),
            "acquired_again": False,
            "cost": {"wall_time": measured["wall_time"],
                     "primitive_calls": measured["primitive_calls"],
                     "proof_calls": measured["proof_calls"]},
            "verification": result["verification"],
            "answers": result["answers"],
            "all_checks_agree": result["all_checks_agree"],
            "sense": ("the basis and the action matrices came out of the stored "
                      "entry. No closure prover ran, no candidate was "
                      "enumerated, and the acquisition cost of this call is "
                      "whatever the figures above say -- not the original "
                      "acquisition, which was paid once.")}


def render(trace):
    """The run as a page, close to the order it happened in."""
    if isinstance(trace, tuple):
        trace = trace[0]
    lines = [f"task   : {trace['task']}"]
    contract = trace.get("task_contract", {})
    lines.append(f"goal   : {contract.get('goal')}")
    lines.append(f"counts : {contract.get('counted')}")
    lines.append(f"state  : {contract.get('state')}")
    lines.append(f"legal  : {contract.get('legality')}")
    lines.append("")
    premise = trace.get("premise", {})
    lines.append(f"premise: exact={premise.get('exact')} "
                 f"{premise.get('identities_checked')} identities over "
                 f"{premise.get('frames_checked')} frames")
    lines.append(f"grammar: degree {trace['grammar']['degree']}, "
                 f"{trace['grammar']['max_terms']} term(s) -> "
                 f"{len(trace['candidates_offered'])} candidates")
    lines.append("")
    lines.append(f"refused at closure    : {len(trace.get('refused_at_closure', []))}")
    for row in trace.get("refused_at_closure", [])[:4]:
        lines.append(f"    {row['observable']}: {row['reason'][:66]}")
    lines.append(f"refused by certificate: {len(trace.get('refused_by_certificate', []))}")
    for row in trace.get("refused_by_certificate", [])[:6]:
        lines.append(f"    {row['observable']:<14s} dim {row['dimension']:<3} "
                     f"refused by {row['refused_by']}")
    lines.append(f"admitted              : {len(trace.get('admitted', []))}")
    cost = trace.get("acquisition_cost", {})
    if cost:
        lines.append(f"acquisition cost      : "
                     f"{cost.get('acquisition_primitive_calls')} primitive calls, "
                     f"{cost.get('acquisition_time')}s over "
                     f"{cost.get('candidates_enumerated')} candidates "
                     f"(rejected ones included)")
    lines.append("")
    for row in trace.get("span_classes", []):
        if row["size"] > 1:
            lines.append(f"span class {row['representative']} (dim "
                         f"{row['dimension']}) also spanned by {row['size'] - 1} "
                         f"other candidate(s)")
    if trace.get("span_classes"):
        lines.append(f"{len(trace['span_classes'])} distinct spaces among "
                     f"{len(trace.get('admitted', []))} admitted candidates")
        lines.append("")
    if "selection" in trace:
        lines.append(f"Pareto fronts: {trace['selection']['front_sizes']}")
        for row in trace["selection"]["offered"][:6]:
            lines.append(f"    front {row['front']}  {row['observable']:<14s} "
                         f"dim {row['dimension']}: {row['objectives']}")
        lines.append("")
    if "selected" in trace:
        lines.append(f"selected: {trace['selected']['observable']} "
                     f"dim {trace['selected']['dimension']}")
        if trace["selected"].get("basis"):
            lines.append(f"          basis   {trace['selected']['basis']}")
            lines.append(f"          readout qbar(z) = "
                         f"{trace['selected']['readout']} . z")
        for name, found in (trace.get("tie_break_workload", {})
                            .get("measured", {}).items()):
            lines.append(f"          workload n={found['lengths']}: "
                         f"{name[:32]:<32s} "
                         f"{found['acquisition_wall_time']:.2f}s acquire + "
                         f"{found['workload_wall_time']:.2f}s run = "
                         f"{found['total_wall_time']:.2f}s   "
                         f"({found['workload_nodes']} nodes)")
        disagree = trace.get("tie_break_workload", {})
        if disagree.get("units_disagree"):
            lines.append(f"          units disagree: by time "
                         f"{disagree['order_by_wall_time'][0][:30]}, by nodes "
                         f"{disagree['order_by_workload_nodes'][0][:30]}")
        for row in trace.get("learned_alternatives", [])[:3]:
            lines.append(f"          learned alternative on front "
                         f"{row['front']}: {row['observable']} dim "
                         f"{row['dimension']}")
        lines.append(f"          {trace['selected']['why']}")
        lines.append("")
    for check in trace.get("verification", []):
        lines.append(f"length {check['length']:>2}  enumeration "
                     f"v_max={check['by_enumeration']['v_max']} "
                     f"count={check['by_enumeration']['count_max']} "
                     f"words={check['by_enumeration']['total_words']}")
        lines.append(f"            representation agrees "
                     f"{check['answers_agree']}, distribution agrees "
                     f"{check['distributions_agree']}  "
                     f"({check['nodes_enumerating']} nodes -> "
                     f"{check['nodes_with_representation']})")
    if trace.get("answers"):
        lines.append("")
    for answer in trace.get("answers", []):
        lines.append(f"length {answer['length']:>2}  v_max="
                     f"{answer['answer']['v_max']} "
                     f"count={answer['answer']['count_max']} "
                     f"words={answer['answer']['total_words']}")
        lines.append(f"            {answer['search_nodes']} nodes, "
                     f"{answer['classes_expanded']} classes, "
                     f"{answer['wall_time']}s, not enumerated")
    if "stopped" in trace:
        lines.append("")
        lines.append(f"stopped: {trace['stopped']}")
        for key, value in trace.get("stopping_point", {}).items():
            lines.append(f"    {key}: {value}")
    lines.append("")
    lines.append(f"scope: {trace.get('scope', '')}")
    return "\n".join(lines)
