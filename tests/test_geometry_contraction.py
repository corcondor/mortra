from copy import deepcopy
import json
from pathlib import Path
import pytest
import sympy as sp
from math_os_prototype import geometry_contracts as gc
from math_os_prototype.geometry_contraction import compile_summary, replay_summary, infer_interface, source_interfaces
from math_os_prototype.theory_geometry_contraction import ContractionGeometryDomain
from math_os_prototype.theory_geometry_acquisition import RationalGeometryDomain, acquisition, solve, independent_replay
from worker.backend.typed_geometry_stalk import TypedConstructionCandidate, enumerate_typed_candidates, ConstructionFamily


def term(op, *args):
    return {"op": op, "args": [gc.point(a) if isinstance(a, str) else a for a in args]}


def contracted(body, boundary=()):
    h, _ = gc.certify_body(body)
    h["summary"], _ = compile_summary(h, boundary)
    return h


CONFIG = {"seed": 17, "max_states": 60, "max_primitive_operations": 180,
          "wall_seconds": 120, "per_family_limit": 12, "max_input_tuples_per_family": 128}
TASK = {"id": "synthetic-regression", "points": ["a", "b", "p"],
        "goal_polynomials": ["4*ux-2*px-ax-bx", "4*uy-2*py-ay-by"],
        "nonzero": ["(ax-bx)**2+(ay-by)**2"]}


@pytest.mark.parametrize("body", [term("midpoint", "p", term("midpoint", "a", "b")),
    term("midpoint", "p", term("foot", "p", "a", "b")),
    term("foot", "p", "a", term("midpoint", "a", "b")),
    term("foot", "p", "a", term("foot", "b", "a", "c"))])
def test_exact_summary_arbitrary_symbols_and_replay(body):
    h = contracted(body)
    summary = h["summary"]
    assert replay_summary(h, summary)[0]
    private = summary["interface"]["private_locals"]
    for rows in summary["Q"].values():
        assert not any(p+a in e for e in rows for p in private for a in ("x", "y"))
    assert summary["certificate"]["equivalence_under_P"]


@pytest.mark.parametrize("field", ["P", "Q", "R", "interface", "public_witness", "scope", "effect_signature", "certificate"])
def test_summary_tamper_rejected(field):
    h = contracted(term("midpoint", "p", term("midpoint", "a", "b")))
    changed = deepcopy(h["summary"])
    changed[field] = {}
    try:
        ok, _ = replay_summary(h, changed)
    except (ValueError, KeyError):
        ok = False
    assert not ok


def test_interface_promotes_external_references_not_every_local():
    steps = [{"output": "m", "inputs": ["a", "b"]},
             {"output": "k", "inputs": ["m", "p"]},
             {"output": "y", "inputs": ["k", "p"]},
             {"output": "outside", "inputs": ["m", "y"]}]
    interface = infer_interface(steps, ["m", "k", "y"], ["outside", "y"])
    assert interface["boundary_outputs"] == ["m", "y"]
    assert interface["private_locals"] == ["k"]
    assert interface["external_inputs"] == ["a", "b", "p"]
    with pytest.raises(ValueError):
        infer_interface(list(reversed(steps)), ["m", "y"], ["outside"])


def test_hide_and_paid_refinement_preserve_internal_goal():
    h = contracted(term("midpoint", "p", term("midpoint", "a", "b")))
    d = ContractionGeometryDomain(TASK, CONFIG, [h])
    candidate = TypedConstructionCandidate(h["id"], ("p", "a", "b"), ())
    state = d.apply(d.initial(), candidate).value
    assert len(state["points"]) == 4
    assert d.costs["certified_witness_evaluations"] == 1
    assert d.costs["hidden_objects"] == 1
    assert d.costs["primitive_equivalent_operations"] == 2
    calls = list(d.alternatives("refine", state))
    assert len(calls) == 1
    refined = calls[0]().value
    assert len(refined["points"]) == 5
    assert d.costs["primitive_equivalent_operations"] == 4
    assert not list(d.alternatives("refine", refined))
    internal = {**TASK, "goal_polynomials": ["2*ux-ax-bx", "2*uy-ay-by"]}
    test = RationalGeometryDomain(internal, CONFIG)
    assert not test.is_goal(state)
    assert test.is_goal(refined)
    later = d.apply(refined, TypedConstructionCandidate("midpoint", ("v4", "p"), ()))
    assert later is None  # duplicate final output, not an inaccessible private point


def test_boundary_public_output_and_no_false_totality_after_cancellation():
    body = term("midpoint", "p", term("foot", "a", "a", "b"))
    h = contracted(body, ["local0"])
    assert not h["summary"]["interface"]["private_locals"]
    assert h["summary"]["P"]["input_nonzero_polynomials"]
    d = ContractionGeometryDomain(TASK, CONFIG, [h])
    assert d.apply(d.initial(), TypedConstructionCandidate(h["id"], ("p", "a", "a"), ())) is None


def test_precondition_before_ranking_and_limit_and_unchanged_legacy():
    audit = {}
    seen = []
    rows = enumerate_typed_candidates(points=["a", "b"], graph={}, goal_multiplicity={},
        families=[ConstructionFamily("F", 2, "ordered", allow_repeated_inputs=True)],
        per_family_limit=1, audit=audit, binding_precondition=lambda f, a: seen.append(a) or a == ("b", "a"))
    assert len(seen) == 4 and rows[0].inputs == ("b", "a")
    assert audit["precondition_filtered"] == 3
    h = contracted(term("midpoint", "p", term("foot", "p", "a", "b")))
    d = ContractionGeometryDomain(TASK, CONFIG, [h])
    rows = d.candidates(h["id"], d.initial())
    assert d.costs["precondition_filtered"] > 0
    assert d.costs["candidate_expansions"] == 0
    assert all(r.inputs[1] != r.inputs[2] for r in rows)
    count = d.costs["precondition_prover_calls"]
    d.candidates(h["id"], d.initial())
    assert d.costs["precondition_prover_calls"] == count


def test_normal_solver_hiding_independent_replay():
    h = contracted(term("midpoint", "p", term("midpoint", "a", "b")))
    r = solve(TASK, CONFIG, [h], mode="summarized", domain_class=ContractionGeometryDomain)
    assert r["solved"] and independent_replay(r)["passed"]


def test_sources_from_existing_learner_not_expected_definition():
    training = [{"solved": True, "independent_replay": {"passed": True}, "task_sha256": str(i),
                 "proof": {"term": term("midpoint", p, term("midpoint", a, b))}}
                for i, (p, a, b) in enumerate([("p", "a", "b"), ("q", "c", "d")])]
    learned = acquisition(training, {"pairs": 100, "max_parameters": 4, "min_steps": 2, "max_steps": 4, "capacity": 4})
    assert learned["active"]
    for h in learned["active"]:
        boundary, evidence = source_interfaces(h, learned["corpus"])
        assert evidence
        assert compile_summary(h, boundary)[0]["certificate"]["equivalence_under_P"]


def test_frozen_cohort_has_only_specs_not_witnesses():
    config = json.loads(Path("configs/theory-geometry-morphism-contraction.json").read_text())
    assert len(config["protocol"]["seeds"]) > 1
    for t in config["training"]+config["evaluation"]:
        assert set(t) == {"id", "points", "goal_polynomials", "nonzero"}
    assert len(config["evaluation"]) == 8


def test_prefilter_never_discards_a_binding_admitted_by_old_contract():
    h = contracted(term("midpoint", "p", term("foot", "p", "a", "b")))
    d = ContractionGeometryDomain(TASK, CONFIG, [h])
    d.candidates(h["id"], d.initial())
    old = RationalGeometryDomain(TASK, {**CONFIG, "max_primitive_operations": 1000}, [h])
    rejected = [e for e in d.events if e["event"] == "precondition_filter"]
    assert rejected
    for event in rejected:
        assert old.apply(old.initial(), TypedConstructionCandidate(h["id"], tuple(event["inputs"]), ())) is None


def test_source_subdag_shared_internal_point_becomes_boundary():
    shared = term("midpoint", "a", "b")
    body = term("midpoint", "p", shared)
    full = term("midpoint", shared, body)
    h, _ = gc.certify_body(body)
    h["source_proof_traces"] = [{"source_proof": "proof", "matches": [{"path": [1],
        "binding": {n: gc.point(n) for n in ("p", "a", "b")}}]}]
    boundary, evidence = source_interfaces(h, [{"source_proof": "proof", "program": full}])
    assert boundary == ["local0", "local1"]  # Both feed the outside consumer.
    summary, _ = compile_summary(h, boundary)
    assert summary["interface"]["public_outputs"] == ["local0", "local1"]
