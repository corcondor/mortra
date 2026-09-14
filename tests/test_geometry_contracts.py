from copy import deepcopy
import json
from pathlib import Path

import pytest
import sympy as sp

from math_os_prototype import geometry_contracts as g
from math_os_prototype import library_compression as library
from math_os_prototype.theory_geometry_acquisition import RationalGeometryDomain, task_identity, solve, independent_replay, acquisition


def term(op, *args):
    return {"op": op, "args": [g.point(a) if isinstance(a, str) else a for a in args]}


@pytest.mark.parametrize("body", [
    term("midpoint", "a", "b"), term("foot", "p", "a", "b"),
    term("midpoint", term("foot", "p", "a", "b"), "p"),
    term("foot", "p", "a", term("midpoint", "a", "b")),
    term("foot", "p", "a", term("foot", "b", "a", "c")),
])
def test_contract_all_real_assignments_and_transfer(body):
    h, _ = g.certify_body(body)
    assert g.replay_contract(h)[0]
    assert h["exact_certificate"]["all_input_assignments_under_P"]
    assert h["guaranteed_relation"]
    assert all(e == "0" for s in h["exact_certificate"]["steps"] for e in s["existence_residuals"])


@pytest.mark.parametrize("field", ["applicability", "witness", "construction_relation", "representation_scopes", "branch_conditions", "dependency_graph"])
def test_modified_contract_rejected(field):
    h, _ = g.certify_body(term("foot", "p", "a", "b"))
    h[field] = {}
    assert not g.replay_contract(h)[0]


def test_sharing_and_antiunification():
    common = term("midpoint", "a", "b")
    body = term("foot", common, "a", common)
    steps, _ = g.dag(body)
    assert len(steps) == 2
    assert steps[-1]["inputs"][0] == steps[-1]["inputs"][2]
    with library.grammar(g.validate):
        template, _ = library.generalise(term("midpoint", "a", term("midpoint", "a", "b")),
                                         term("midpoint", "c", term("midpoint", "c", "d")))
        abstract = g.body_from_template(template)
    assert abstract["args"][0] == abstract["args"][1]["args"][0]


def test_degenerate_composition_and_scope_rejected():
    with pytest.raises(ValueError):
        g.certify_body(term("foot", "p", "a", "a"))
    with pytest.raises(ValueError):
        g.certify_body(term("circle", "a", "b", "c"))
    with pytest.raises(ValueError):
        g.dag(term("midpoint", "local0", "b"))


def test_guard_not_removed_by_coordinate_cancellation():
    h, _ = g.certify_body(term("foot", "a", "a", "b"))
    assert h["nondegeneracy_conditions"]
    assert list(h["witness"].values())[-1] == ["ax", "ay"]


def test_unproved_guard_and_renamed_task():
    task = {"id": "x", "points": ["a", "b"], "goal_polynomials": ["2*ux-ax-bx", "2*uy-ay-by"]}
    domain = RationalGeometryDomain(task, {"seed": 0, "wall_seconds": 30})
    with pytest.raises(ValueError, match="unproved_applicability"):
        domain.require_guards([domain.symbols["ax"]-domain.symbols["bx"]])
    assert task_identity(task) == task_identity({**task, "id": "renamed"})


def test_goal_synthesis_independent_replay_and_tamper():
    task = {"id": "unit", "points": ["a", "b"], "goal_polynomials": ["2*ux-ax-bx", "2*uy-ay-by"]}
    config = {"seed": 17, "wall_seconds": 30, "max_states": 10, "max_primitive_operations": 30, "per_family_limit": 12}
    result = solve(task, config)
    assert result["solved"]
    assert independent_replay(result)["passed"]
    result["proof"]["term"] = g.point("a")
    assert not independent_replay(result)["passed"]


def test_frozen_plan_contains_conditions_not_programs():
    plan = json.loads(Path("configs/theory-geometry-contract-acquisition.json").read_text())
    assert not {task_identity(t) for t in plan["training"]} & {task_identity(t) for t in plan["evaluation"]}
    assert all(set(t) == {"id", "points", "goal_polynomials", "nonzero"} for t in plan["training"]+plan["evaluation"])


def test_existing_library_protocol_and_source_bindings():
    # Artificial records test the adapter only; they are not normal-run evidence.
    training = [{"solved": True, "independent_replay": {"passed": True},
                 "proof": {"term": term("midpoint", a, term("midpoint", a, b))},
                 "task_sha256": str(i)} for i, (a, b) in enumerate([("a", "b"), ("c", "d")])]
    learned = acquisition(training, {"pairs": 100, "max_parameters": 6, "min_steps": 2, "max_steps": 3, "capacity": 4})
    assert learned["active"]
    for h in learned["active"]:
        assert g.replay_contract(h)[0]
        assert all(s["matches"] for s in h["source_proof_traces"])


def test_acquired_registry_allows_argument_aliases_and_checks_real_guard():
    from worker.backend.typed_geometry_stalk import _family_inputs
    body = term("midpoint", "q", term("foot", "p", "a", "b"))
    h, cost = g.certify_body(body)
    assert cost["prover_calls"] > cost["primitive_schema_steps"]
    task = {"points": ["a", "b", "p"], "goal_polynomials": ["ux-ax"],
            "nonzero": ["(ax-bx)**2+(ay-by)**2"]}
    config = {"seed": 0, "wall_seconds": 60, "max_primitive_operations": 20}
    domain = RationalGeometryDomain(task, config, [h])
    assert ("a", "p", "a", "b") in list(_family_inputs(task["points"], domain.registry[h["id"]]))
    from worker.backend.typed_geometry_stalk import TypedConstructionCandidate
    assert domain.apply(domain.initial(), TypedConstructionCandidate(h["id"], ("a", "p", "a", "b"), ())) is not None
    assert domain.apply(domain.initial(), TypedConstructionCandidate(h["id"], ("a", "p", "a", "a"), ())) is None
    assert domain.events[-1]["event"] == "reject"
