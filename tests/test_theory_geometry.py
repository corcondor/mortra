"""Development guards, not autonomous acquisition evidence."""
import os
import pytest

from math_os_prototype.runtime_typed_planner import PrimitiveResult
from math_os_prototype.theory_action_domain import search_action_domain


class CounterDomain:
    sort = "IntegerState"
    families = ("successors",)
    def __init__(self):
        self.expanded = []
    def initial(self): return 0
    def key(self, value): return str(value)
    def is_goal(self, value): return value == 3
    def alternatives(self, family, state):
        self.expanded.append(state)
        for delta in (0, 1):
            yield lambda delta=delta: PrimitiveResult(state+delta, {"parent": state, "delta": delta})


def test_successor_enumeration_reads_new_states():
    domain = CounterDomain()
    plan = search_action_domain(domain, max_depth=4, max_states=20)
    assert plan.complete and domain.expanded == [0, 1, 2]
    assert [s["parent"] for s in plan.proof_program] == [0, 1, 2]


def test_application_budget_counts_duplicates():
    domain = CounterDomain()
    plan = search_action_domain(domain, max_depth=4, max_states=3)
    assert not plan.complete and plan.states_explored == 3


def test_geometry_rejects_injected_auxiliary():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    with pytest.raises(ValueError, match="auxiliary"):
        GeometryDomain({"statement": "a b c = triangle a b c | m = midpoint m a b ? coll a m b"}, {})


def test_geometry_rejects_empty_goal():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    with pytest.raises(ValueError, match="goal"):
        GeometryDomain({"statement": "a b c = triangle a b c"}, {})


def test_false_statement_cannot_get_exact_certificate():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    domain = GeometryDomain({"statement": "a b c = triangle a b c ? perp a b b c"}, {})
    assert not domain.certify(str(domain.formulation))["accepted"]


def test_names_are_normalized_without_goal_information():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    first = GeometryDomain({"statement": "a b c = triangle a b c ? perp a b b c"}, {})
    second = GeometryDomain({"statement": "z y x = triangle z y x ? perp z y y x"}, {})
    assert str(first.formulation) == str(second.formulation)


def test_existing_construction_updates_real_next_inputs_and_replays():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    task = {"statement": "a b c = triangle a b c; h = on_tline h b a c, on_tline h c a b ? perp a h b c"}
    config = {"seed": 17, "closure_steps": 1000, "per_family_limit": 8}
    domain = GeometryDomain(task, config)
    root = domain.initial()
    candidate = domain.candidates("midpoint", root)[0]
    child = domain.apply(root, candidate).value
    output = child["path"][-1]["output"]
    assert len(child["problem"]["points"]) == len(root["problem"]["points"])+1
    assert any(output in c.inputs for c in domain.candidates("foot", child))
    assert domain.key(root) != domain.key(child)
    assert domain.replay(child)["passed"]
    assert any(e["event"] == "enumerate" and e["state_key"] == domain.key(child) for e in domain.events)


def test_similarity_does_not_change_initial_theorem():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    task = {"statement": "a b c = triangle a b c; h = on_tline h b a c, on_tline h c a b ? perp a h b c"}
    config = {"seed": 17, "closure_steps": 1000, "per_family_limit": 8}
    first = GeometryDomain(task, config).initial()
    other = GeometryDomain(task, dict(config, diagram_similarity=[3, 4, -2])).initial()
    assert first["certified"] and other["certified"]
    assert first["certificates"] == other["certificates"]
    assert first["problem"]["points"] != other["problem"]["points"]


@pytest.mark.skipif(os.environ.get("MORTRA_EXTERNAL_GEOMETRY") != "1", reason="external comparison job only")
def test_external_yuclid_backend_still_requires_exact_certificate():
    pytest.importorskip("py_yuclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    task = {"statement": "a b c = triangle a b c; h = on_tline h b a c, on_tline h c a b ? perp a h b c"}
    config = {"seed": 17, "deduction_backend": "yuclid", "ar_profile": "standard",
              "closure_timeout_seconds": 10, "per_family_limit": 8}
    domain = GeometryDomain(task, config)
    root = domain.initial()
    assert root["deduction_proved"] and root["certified"]
    assert root["certificates"][0]["obligation"]["remainder"] == "0"
    assert domain.replay(root)["passed"]
    false_state = dict(root, statement="p0 p1 p2 = triangle p0 p1 p2 ? perp p0 p1 p1 p2",
                       certificates=[], certified=False)
    assert not domain.certify_solved(false_state)["certified"]


def test_generic_affine_elimination_exports_conditions_and_replays():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    task = {"statement": "a b c = triangle a b c; d = on_line d a b; e = on_line e a c, on_pline e d b c ? eqratio a d a b a e a c"}
    domain = GeometryDomain(task, {})
    from worker.backend.jgex_exact_constraint_bridge import lower_jgex_to_exact_obligation
    proof = lower_jgex_to_exact_obligation(str(domain.formulation),
        enable_affine_local_lemmas=True, enable_structural_lemmas=False)
    assert proof.exact_replay
    lemmas = proof.local_lemma_certificates
    assert lemmas and all(l.replayed and l.nonzero_condition for l in lemmas)
    cached = domain.certify(str(domain.formulation))
    assert domain.certify(str(domain.formulation)) == cached
    assert domain.costs["exact_prover_calls"] == 1
    assert domain.costs["exact_certificate_cache_hits"] == 1


def test_internal_closure_never_imports_external_deduction(monkeypatch):
    import builtins
    original = builtins.__import__
    def checked(name, *args, **kwargs):
        if name.startswith(("py_yuclid", "newclid.api", "newclid.deductors", "newclid.agent")):
            raise AssertionError("external deduction attempted: "+name)
        return original(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", checked)
    from math_os_prototype.theory_geometry import GeometryDomain
    task = {"statement": "a b c = triangle a b c; m = midpoint m a b ? coll a m b"}
    config = {"seed": 17, "closure_steps": 1000, "per_family_limit": 8}
    domain = GeometryDomain(task, config)
    root = domain.initial()
    assert root["certified"] and root["deduction_mode"].startswith("MORTRA")
    assert domain.costs["exact_prover_calls"] > 0
    assert root["relation_certificates"]
    assert domain.replay(root)["passed"]


def test_exact_closure_keeps_only_certified_relations_and_does_not_claim_saturation():
    from math_os_prototype.theory_geometry import GeometryDomain
    domain = GeometryDomain({"statement": "a b c = triangle a b c; m = midpoint m a b ? coll a m b"},
        {"seed": 17, "closure_steps": 1000, "per_family_limit": 16})
    state = domain.initial()
    checks = [e for e in domain.events if e["event"] == "exact_relation_check"]
    assert any(e["accepted"] for e in checks)
    assert any(not e["accepted"] for e in checks)
    for check in checks:
        assert (check["relation"] in state["relations"]) == check["accepted"]
        if check["accepted"]:
            assert check["certificate"]["obligation"]["exact_replay"]
            assert not check["additional_conditions"]
    assert not state["closure_exhausted"]


def test_no_float_false_goal_and_local_candidate_bound():
    from math_os_prototype.theory_geometry import GeometryDomain
    domain = GeometryDomain({"statement": "a b c = triangle a b c ? perp a b b c"},
        {"seed": 17, "closure_steps": 1000, "per_family_limit": 8})
    # Avoid Newclid's numeric-goal construction filter for this false-goal guard.
    assert not domain.certify(str(domain.formulation))["accepted"]
    state = {"problem": {"points": [{"name": f"p{i}"} for i in range(100)]},
             "relations": [], "path": []}
    candidates = domain.relation_candidates(state, 8)
    assert len(candidates) <= 8
    assert all(set(r.split()[1:]) <= {"p0", "p1", "p2"} for r in candidates)


def test_native_rules_feed_exact_certificates_and_backward_compiler():
    from math_os_prototype.theory_geometry import GeometryDomain
    domain = GeometryDomain({"statement": "a b c = triangle a b c; m = midpoint m a b ? cong a m b m"},
        {"seed": 17, "closure_steps": 1000, "per_family_limit": 8})
    state = domain.initial()
    domain.candidates("midpoint", state)
    assert domain.costs["native_rule_relations_certified"] > 0
    trace = next(e for e in domain.events if e["event"] == "native_backward_compilation")
    assert trace["certified_relations_used"]
    assert set(trace["certified_relations_used"]) <= set(state["relation_certificates"])
    previous = domain.costs["native_backward_compilation_seconds"]
    domain.candidates("foot", state)
    assert domain.costs["native_backward_compilation_seconds"] == previous
    registry = next(e for e in domain.events if e["event"] == "native_registry")
    assert registry["external_deductor"] is False
    assert registry["rule_count"] == len(domain.native_theorems)


def test_backward_compiler_retains_witnesses_without_assuming_open_requirements():
    from math_os_prototype.theory_geometry import GeometryDomain
    domain = GeometryDomain({"statement": "a b c = triangle a b c; h = on_tline h b a c, on_tline h c a b ? perp a h b c"},
        {"seed": 17, "closure_steps": 1000, "per_family_limit": 8})
    root = domain.initial()
    rows = domain.native_candidates(root)
    assert rows and any(c.open_requirements for c in rows)
    trace = next(e for e in domain.events if e["event"] == "native_backward_compilation")
    assert any(o["unbound_variables"] for o in trace["obligations"])
    domain.candidates("foot", root)
    enumeration = domain.events[-1]
    assert not set(enumeration["native_contract_candidates"]) & {c.key for c in rows if not c.executable}


def test_contract_generated_candidate_is_executed_and_recorded(monkeypatch):
    """Artificial compilation fixture; not autonomous-run evidence."""
    from math_os_prototype.theory_geometry import GeometryDomain
    from worker.backend.geometry_proof_hypergraph import Atom, BackwardObligation
    import worker.backend.geometry_proof_hypergraph as hypergraph
    domain = GeometryDomain({"statement": "a b c = triangle a b c; h = on_tline h b a c, on_tline h c a b ? perp a h b c"},
        {"seed": 17, "closure_steps": 1000, "per_family_limit": 8})
    root = domain.initial()
    obligation = BackwardObligation(theorem="development fixture", goal=domain.native_goal,
        matched_premises=(), open_premises=(Atom("midp", ("?M", "p0", "p1")),),
        substitution=(), unbound_variables=("?M",))
    monkeypatch.setattr(hypergraph, "synthesize_backward_obligations", lambda *a, **k: (obligation,))
    rows = domain.native_candidates(root)
    assert any(c.family == "midpoint" and c.executable for c in rows)
    candidate = domain.candidates("midpoint", root)[0]
    child = domain.apply(root, candidate).value
    assert child["path"][-1]["native_contract_selected"]
    assert child["path"][-1]["native_plan_certificates"]
    assert domain.costs["native_contract_applications"] == 1


@pytest.mark.parametrize("extension,accepted", [
    ("m = midpoint m p0 p1", True),
    ("m = free m", False),
    ("m = foot m p2 p0 p1", False),
    ("m = on_line m p0 p1, on_circle m p0 p2", False),
])
def test_conservative_extension_guards(extension, accepted):
    from math_os_prototype.theory_geometry import GeometryDomain
    domain = GeometryDomain({"statement": "a b c = triangle a b c ? perp a b b c"}, {})
    source = str(domain.formulation)
    setup, goal = source.split("?")
    augmented = setup.strip()+"; "+extension+" ? "+goal
    certificate = domain.certify_extension(source, augmented)
    assert certificate["accepted"] is accepted
    assert domain.certify_extension(source, augmented) == certificate
    assert domain.costs["extension_cache_hits"] == 1
    if accepted:
        assert certificate["all_residuals_zero"] and certificate["point_witnesses"]
    else:
        assert certificate["refusal_reason"]


def test_extension_cannot_change_goal_or_source():
    from math_os_prototype.theory_geometry import GeometryDomain
    domain = GeometryDomain({"statement": "a b c = triangle a b c ? perp a b b c"}, {})
    source = str(domain.formulation)
    altered = source.replace("? perp p0 p1 p1 p2", "? cong p0 p1 p0 p1")
    assert not domain.certify_extension(source, altered)["accepted"]
    assert not domain.certify_extension(source, source.replace("triangle", "r_triangle"))["accepted"]


def test_failed_original_proof_does_not_block_certified_extension(monkeypatch):
    """Mock only proof availability, not extension semantics or final answer."""
    from math_os_prototype.theory_geometry import GeometryDomain
    domain = GeometryDomain({"statement": "a b c = triangle a b c ? cong a b a b"}, {})
    source = str(domain.formulation)
    setup, goal = source.split("?")
    augmented = setup.strip()+"; m = midpoint m p0 p1 ? "+goal
    original_certify = domain.certify
    def certify(statement):
        return {"accepted": False, "statement": statement} if statement == source else original_certify(statement)
    monkeypatch.setattr(domain, "certify", certify)
    state = {"statement": augmented, "deduction_proved": True, "certificates": [], "certified": False}
    domain.certify_solved(state)
    assert state["certified"]
    assert state["extension_certificate"]["accepted"]
    assert state["certification_route"] == "augmented_exact_with_conservative_extension"


@pytest.mark.parametrize("poison", ["unknown", "floating", "irrational"])
def test_extension_rejects_undeclared_or_nonrational_witness(monkeypatch, poison):
    import sympy as sp
    import worker.backend.jgex_exact_constraint_bridge as bridge
    from math_os_prototype.theory_geometry import GeometryDomain
    domain = GeometryDomain({"statement": "a b c = triangle a b c ? cong a b a b"}, {})
    source = str(domain.formulation)
    setup, goal = source.split("?")
    augmented = setup.strip()+"; m = midpoint m p0 p1 ? "+goal
    prepare = bridge._prepare_exact_system
    def poisoned(statement, **kwargs):
        result = prepare(statement, **kwargs)
        if statement == augmented:
            result[0].coordinates["m"] = ({"unknown": sp.Symbol("injected"),
                "floating": sp.Float(0.5), "irrational": sp.sqrt(2)}[poison], sp.S.Zero)
        return result
    monkeypatch.setattr(bridge, "_prepare_exact_system", poisoned)
    assert not domain.certify_extension(source, augmented)["accepted"]


@pytest.mark.parametrize("error_name", ["CoercionFailed", "PolynomialError"])
def test_unsupported_polynomial_domain_is_recorded_not_proved(monkeypatch, error_name):
    import sympy.polys.polyerrors as errors
    import worker.backend.jgex_exact_constraint_bridge as bridge
    from math_os_prototype.theory_geometry import GeometryDomain
    domain = GeometryDomain({"statement": "a b c = triangle a b c ? cong a b a b"}, {})
    def unsupported(*args, **kwargs):
        raise getattr(errors, error_name)("outside declared coefficient domain")
    monkeypatch.setattr(bridge, "lower_jgex_to_exact_obligation", unsupported)
    first = domain.certify(str(domain.formulation))
    assert not first["accepted"] and first["unsupported"].startswith(error_name)
    assert domain.certify(str(domain.formulation)) == first
    assert domain.costs["unsupported_exact_checks"] == 1
    assert domain.costs["exact_prover_calls"] == 1
    assert domain.events[-1]["event"] == "exact_check_completed"
    assert domain.events[-1]["accepted"] is False


def test_actions_complex_similarity_obligation_is_refused():
    """Regression from failed run 34836669023; never normal-run input."""
    from math_os_prototype.theory_geometry import GeometryDomain
    statement = ("a b c = triangle a b c; d = on_line d a b; "
        "e = on_pline e d b c, on_line e a c; "
        "f = on_line f c d, on_line f b e; "
        "g = on_line g a f, on_line g b c; o = circle o b c a ? simtri a b c a d e")
    domain = GeometryDomain({"statement": statement}, {})
    certificate = domain.certify(str(domain.formulation))
    assert not certificate["accepted"]
    assert certificate["unsupported"].startswith("CoercionFailed")
