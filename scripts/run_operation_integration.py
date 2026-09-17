"""Evidence for the shared operation contract: what was composed, what was acquired, what it cost.

This is an integration record, not a preregistered comparison. It reports what the
run did on stated inputs: which specification was met by composing which given
contracts, what was registered with which provenance and generation, what an
acquired operation cost on later goals with and without it, and every answer
checked against `algebraic_structures` computed independently.

    python scripts/run_operation_integration.py --output reports/operation-integration
"""
from __future__ import annotations

import argparse
from fractions import Fraction
import json
import platform
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from math_os_prototype import algebraic_operation_domain as dom
from math_os_prototype import algebraic_structures as alg
from math_os_prototype import operation_acquisition as acq
from math_os_prototype import operation_contracts as oc
from math_os_prototype import operation_integration as oi

COMPLEXES = {
    "triangle_with_loop": [(0, 1, 2), (0, 3), (1, 3)],
    "two_triangles": [(0, 1), (1, 2), (2, 3), (3, 0), (0, 2, 4), (2, 4, 5)],
    "two_circles": [(0, 1), (1, 2), (2, 0), (3, 4), (4, 5), (5, 3)],
    "tetrahedron_boundary": [(0, 1, 2), (0, 1, 3), (0, 2, 3), (1, 2, 3)],
}
SPHERE = {"variables": ["x", "y", "z"], "polynomials": ["x**2 + y**2 + z**2 - 1"]}
SPHERE_AND_PLANE = {"variables": ["x", "y", "z"], "polynomials": ["x**2 + y**2 + z**2 - 1", "z"]}
ON_SPHERE = (Fraction(1), Fraction(0), Fraction(0))


def complex_of(name):
    return alg.simplicial_chain_complex(alg.closure(COMPLEXES[name]))


def measure(session, specification, inputs, *, max_states):
    before, started = session.counter["total"], time.perf_counter()
    solution = oi.solve_specification(session, specification, inputs, max_states=max_states)
    return solution, {"solved": solution["solved"], "phase": solution["phase"],
                      "states": sum(attempt["states"] for attempt in solution["attempts"]),
                      "operations": session.counter["total"]-before,
                      "seconds": time.perf_counter()-started,
                      "steps": [step["contract"] for step in solution["plan"].proof_program]
                               if solution["solved"] else []}


def first_generation(session, name="triangle_with_loop"):
    """The first integration task: ker(A) / im(B) under A B = 0."""
    complex_ = complex_of(name)
    A, B = complex_.d(1), complex_.d(2)
    session.context.assume("zero_composition",
                           [session.registry.object_id("Map", A), session.registry.object_id("Map", B)],
                           source="task hypothesis A B = 0")
    inputs = {"A": ("Map", A), "B": ("Map", B)}
    solution, record = measure(session, "homology_of", inputs, max_states=800)
    record["reference_betti"] = alg.homology(complex_, 1)["betti"]
    record["dimension"] = solution["plan"].goals["Quotient"].value["dimension"] if solution["solved"] else None
    record["answer_agrees"] = record["dimension"] == record["reference_betti"]
    contract = oi.acquire_from(session, solution, inputs, name="homology_pair", specification="homology_of",
                               note="composed for the first integration task")
    return contract, record


def contract_record(session, contract):
    entry = contract.as_json()
    entry.pop("run", None)
    if contract.body is not None:
        expansion = acq.expand(session.registry, contract.body)
        entry["expansion"] = expansion
        entry["expansion_is_given_only"] = all(
            session.registry.contracts[step["prim"]].provenance == oc.GIVEN for step in expansion["steps"])
    return entry


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    parser.add_argument("--max-states", type=int, default=9000)
    arguments = parser.parse_args()
    output = Path(arguments.output)
    output.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    report = {"environment": {
        "sha": subprocess.run(["git", "rev-parse", "HEAD"], cwd=ROOT, capture_output=True, text=True).stdout.strip(),
        "python": sys.version, "platform": platform.platform()}}

    session = oi.new_session(verify_derivations=True)
    generation_one, first = first_generation(session)
    report["first_integration_task"] = first
    report["given_contracts"] = [c.name for c in session.registry.by_provenance(oc.GIVEN)]
    report["given_specifications"] = {name: definition.as_json()
                                      for name, definition in session.registry.definitions.items()}

    # Later goals: the same specifications, solved with and without what was acquired.
    later = []
    for label, specification, inputs in [
            ("homology of two_triangles at 1", "homology_at",
             {"C": ("Complex", complex_of("two_triangles")), "q": ("Degree", 1)}),
            ("homology of two_circles at 1", "homology_at",
             {"C": ("Complex", complex_of("two_circles")), "q": ("Degree", 1)}),
            ("homology of tetrahedron_boundary at 2", "homology_at",
             {"C": ("Complex", complex_of("tetrahedron_boundary")), "q": ("Degree", 2)}),
            ("tangent directions removed by z = 0 on the sphere", "tangent_quotient",
             {"S": ("System", SPHERE), "T": ("System", SPHERE_AND_PLANE), "p": ("Point", ON_SPHERE)})]:
        reuse_session = oi.new_session(verify_derivations=True)
        first_generation(reuse_session)
        solution, with_acquired = measure(reuse_session, specification, inputs, max_states=arguments.max_states)
        bare = oi.new_session(verify_derivations=True)
        _, given_only = measure(bare, specification, inputs, max_states=arguments.max_states)
        entry = {"goal": label, "specification": specification,
                 "with_acquired": with_acquired, "given_operations_only": given_only,
                 "used_the_acquired_operation": "homology_pair" in with_acquired["steps"]}
        if solution["solved"]:
            value = solution["plan"].goals["Quotient"].value
            if specification == "homology_at":
                reference = alg.homology(inputs["C"][1], int(inputs["q"][1]))["betti"]
            else:
                outer = alg.tangent_space(dom.system_callables(SPHERE), ON_SPHERE)["dimension"]
                inner = alg.tangent_space(dom.system_callables(SPHERE_AND_PLANE), ON_SPHERE)["dimension"]
                reference = outer-inner
            entry["dimension"] = value["dimension"]
            entry["reference"] = reference
            entry["answer_agrees"] = value["dimension"] == reference
        later.append(entry)
    report["later_goals"] = later

    # The second generation, on two kinds of problem, and an edit of one of them.
    second = []
    for name, specification, inputs in [
            ("homology_at_degree", "homology_at",
             {"C": ("Complex", complex_of("two_triangles")), "q": ("Degree", 1)}),
            ("tangent_gap", "tangent_quotient",
             {"S": ("System", SPHERE), "T": ("System", SPHERE_AND_PLANE), "p": ("Point", ON_SPHERE)})]:
        solution, record = measure(session, specification, inputs, max_states=arguments.max_states)
        if not solution["solved"]:
            second.append({"name": name, "acquired": False, "search": record})
            continue
        contract = oi.acquire_from(session, solution, inputs, name=name, specification=specification,
                                   parents=["homology_pair"], note="built on the acquired quotient operation")
        second.append({"name": name, "acquired": True, "search": record,
                       "contract": contract_record(session, contract)})
    report["second_generation"] = second

    edits = {}
    acquired_second = next((entry for entry in second if entry.get("acquired")
                            and entry["name"] == "homology_at_degree"), None)
    if acquired_second is not None:
        contract = session.registry.contracts["homology_at_degree"]
        step = next(s for s in contract.body["steps"] if s["prim"] == "differential")
        higher = oi.abstract_step(session, contract, step["out"])
        edits["abstraction"] = {"step": step["out"], "parameter": higher["params"][-1]}
        refused = None
        try:
            oi.instantiate(session, higher, {"op0": "compose_maps"})
        except Exception as error:                       # recorded, never silently ignored
            refused = repr(error)
        edits["refused_instantiation"] = refused
        definition = oi.instantiate(session, higher, {"op0": "differential"})
        inputs = {"C": ("Complex", complex_of("two_circles")), "q": ("Degree", 1)}
        reacquired = oi.reacquire(session, definition, inputs, name="homology_at_degree_reedited",
                                  specification="homology_at", parents=["homology_at_degree"])
        edits["reacquired"] = contract_record(session, reacquired)
        edits["same_expansion_as_parent"] = (acq.expand(session.registry, reacquired.body)
                                             == acq.expand(session.registry, contract.body))
    report["edits"] = edits

    # Provenance: a candidate is executed but never promoted.
    candidate_body = {"params": ["A"], "steps": [{"out": "t1", "prim": "kernel_basis", "args": ["A"]}],
                      "result": "t1"}
    candidate = acq.acquire_candidate(session, name="guessed_image", body=candidate_body,
                                      parameters=[("A", "Map")],
                                      post=[oc.Condition.of("image_of", "A", "v")], result_sort="Basis")
    nilpotent = alg.SparseMatrix.from_rows([[0, 1], [0, 0]])
    applied = session.apply(candidate, {"A": nilpotent})
    report["provenance"] = {
        "given": [c.name for c in session.registry.by_provenance(oc.GIVEN)],
        "acquired": [{"name": c.name, "generation": c.generation, "parents": list(c.parents)}
                     for c in session.registry.by_provenance(oc.ACQUIRED)],
        "candidate": [c.name for c in session.registry.by_provenance(oc.CANDIDATE)],
        "candidate_guarantee_status": [entry["status"] for entry in applied.certificate_step["post"]]
                                      if applied else None,
        "candidate_in_certified_vocabulary": candidate in session.registry.certified_contracts(),
        "candidate_guarantee_entered_the_context":
            session.context.lookup("image_of", [session.registry.object_id("Map", nilpotent),
                                                applied.certificate_step["objects"]["v"]]) is not None
            if applied else None,
        "candidate_refused_where_it_does_not_hold":
            session.apply(candidate, {"A": complex_of("two_triangles").d(1)}) is None}

    derived = [entry for execution in session.executions for entry in execution["post"]
               if entry["justification"].get("kind") == "derivation"]
    report["supplied_rules_audited"] = {
        "derived_guarantees": len(derived),
        "all_also_checked_exactly": all(entry["justification"]["verified_exactly"] for entry in derived),
        "rules": [c.name for c in session.registry.by_provenance(oc.GIVEN) if c.derivation]}
    report["acquired_contracts"] = [contract_record(session, c)
                                    for c in session.registry.by_provenance(oc.ACQUIRED)]
    report["first_generation_contract"] = contract_record(session, generation_one)
    report["cost"] = dict(session.counter)
    report["total_seconds"] = time.perf_counter()-started
    report["claims_not_made"] = [
        "the lemmas, the specifications, the sorts and the primitive contracts are supplied by a person",
        "the scheduling that offers rules first and acquired operations before the given ones they "
        "were composed from is supplied search machinery, not a result",
        "an acquired guarantee is derived from the guarantees of its steps; it is not a proof that the "
        "operation is correct for inputs outside its stated preconditions",
        "the measurements compare two runs of this search on these inputs, and are not a claim about "
        "searches in general",
        "no preregistered evaluation is affected by this layer; the frozen configurations, runners and "
        "results are untouched"]
    (output/"result.json").write_text(json.dumps(report, indent=1, default=str)+"\n", encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("first_integration_task", "later_goals", "provenance",
                                             "supplied_rules_audited")}, indent=1, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
