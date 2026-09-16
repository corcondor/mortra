"""Artificial development fixtures; not autonomous-run evidence."""
from copy import deepcopy

import pytest

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_semantic_dsl as dsl
from math_os_prototype.geometry_proof_dsl import search_exact_proof
from math_os_prototype.geometry_symbolic_dsl import (
    SymbolicDSLDomain, compile_call, instantiate_call,
)
from math_os_prototype.theory_geometry_feedback import GeometryLibrary
from worker.backend.typed_geometry_stalk import TypedConstructionCandidate


TASK = {"statement": "a b c = triangle a b c; m = midpoint m a b ? cong a m b m"}
CONFIG = {"seed": 17, "closure_steps": 0, "per_family_limit": 4,
          "proof_dsl": True, "proof_dsl_budget": 64, "max_depth": 4}


@pytest.fixture(scope="module")
def bank():
    return GeometryLibrary()


def test_existing_exact_prover_selected_by_typed_dsl():
    result = search_exact_proof(TASK["statement"])
    assert result["accepted"]
    assert result["obligation"]["exact_replay"]
    assert result["obligation"]["remainder"] == "0"
    assert [s["operation"] for s in result["proof_program"]] == ["explicit_chart", "certify"]
    assert result["proof_dsl_costs"]["exact_prover_calls"] >= 1


def test_no_numeric_true_false_goal_escape():
    result = search_exact_proof("a b c = triangle a b c ? perp a b b c", budget=32)
    assert not result["accepted"]
    assert result["proof_attempts"] and all(not r["accepted"] for r in result["proof_attempts"])


def test_solver_can_compose_request_modifiers_not_only_choose_fixed_route(monkeypatch):
    import worker.backend.jgex_exact_constraint_bridge as bridge
    from dataclasses import dataclass
    @dataclass
    class Certificate:
        exact_replay: bool
        remainder: str
        vacuous_unit_ideal: bool = False
        untransported_nonzero_conditions: tuple = ()
        certificate_sha256: str = "development fixture only"
    def prover(statement, **options):
        okay = options["representation"] == "goal_local_relational" and options["enable_affine_local_lemmas"]
        return Certificate(okay, "0" if okay else "1")
    monkeypatch.setattr(bridge, "lower_jgex_to_exact_obligation", prover)
    result = search_exact_proof(TASK["statement"], budget=512)
    assert result["accepted"]
    assert {s["operation"] for s in result["proof_program"]} >= {
        "relational_chart", "goal_slice", "local_elimination", "affine", "certify"}


def test_refuse_injected_proof_options():
    with pytest.raises(ValueError, match="injected"):
        search_exact_proof(TASK["statement"], backend_limits={"representation": "explicit"})


def test_alpha_renaming_preserves_sharing(bank):
    sub = {"op": "midpoint", "args": [gc.point("a"), gc.point("b")]}
    term = {"op": "mirror", "args": [sub, sub]}
    clauses, output, primitive, points = compile_call(term, bank.table, {"a", "b", "aux3", "local0"})
    assert len(clauses) == 2
    assert len(set(n for n, _ in points)) == 2
    assert not {n for n, _ in points} & {"a", "b", "aux3", "local0"}
    assert clauses[-1].split()[-1] == clauses[-1].split()[-2]


def acquired_bank(bank):
    bank = deepcopy(bank)
    template = {"op": "mirror", "args": [
        {"op": "midpoint", "args": [{"series_parameter": "f0"}, {"series_parameter": "f1"}]},
        {"series_parameter": "f0"}]}
    h = dsl.certify_definition(template, bank.archive)
    bank.register(h)
    return bank, h


def test_acquired_call_executes_in_symbolic_state_and_returns_to_learning(bank):
    bank, h = acquired_bank(bank)
    domain = SymbolicDSLDomain(TASK, CONFIG, bank, active=[h["id"]], discover=True)
    root = domain.initial()
    row = TypedConstructionCandidate(h["id"], ("p0", "p2"), ())
    result = domain.apply(root, row)
    assert result is not None
    state = result.value
    assert state["certified"]
    assert len(state["problem"]["points"]) == len(root["problem"]["points"])+2
    assert domain.histories[-1]["program"]["op"] == "use"
    assert domain.histories[-1]["acquired_calls"] == [h["id"]]
    assert domain.histories[-1]["replay"]["passed"]
    assert domain.histories[-1]["compilation_certificate"]["identity_checks"] == 4
    assert domain.costs["primitive_equivalent_operations"] == 2
    assert domain.costs["acquired_applications"] == 1
    assert any(state["path"][-1]["output"] in c.inputs
               for c in domain.candidates("midpoint", state))


def test_complete_binding_stream_not_old_per_family_limit(bank):
    domain = SymbolicDSLDomain(TASK, dict(CONFIG, per_family_limit=1), bank)
    root = domain.initial()
    candidates = list(domain.candidates("midpoint", root))
    assert len({c.inputs for c in candidates}) == 6


def test_scope_strengthening_refused_before_numeric_execution(bank, monkeypatch):
    domain = SymbolicDSLDomain(TASK, CONFIG, bank)
    root = domain.initial()
    import newclid.jgex.to_newclid as numerical
    monkeypatch.setattr(numerical, "add_clause_to_problem", lambda *a, **k: pytest.fail("guard bypass"))
    # p3 is the midpoint of p0,p1, so these three are provably collinear.
    result = domain.apply(root, TypedConstructionCandidate("circle", ("p0", "p1", "p3"), ()))
    assert result is None
    assert domain.costs["extension_refusals"] == 1
    assert not domain.histories


def test_archive_inactive_removes_only_search_roots(bank):
    bank, h = acquired_bank(bank)
    active = SymbolicDSLDomain(TASK, CONFIG, bank, active=[h["id"]])
    inactive = SymbolicDSLDomain(TASK, CONFIG, bank)
    assert h["id"] in active.families and h["id"] not in inactive.families
    assert active.bank.archive == inactive.bank.archive


def test_registration_rejects_tampered_certificate(bank):
    bank, h = acquired_bank(bank)
    fresh = GeometryLibrary()
    h = deepcopy(h)
    h["exact_certificate"]["witness"] = {}
    with pytest.raises(ValueError, match="certificate mismatch"):
        fresh.register(h)


def test_original_gauge_nonzero_is_available_to_extension_verifier(bank):
    domain = SymbolicDSLDomain(TASK, CONFIG, bank)
    source = str(domain.formulation)
    setup, goal = source.split("?", 1)
    augmented = setup.strip()+"; z = foot z p2 p0 p1 ? "+goal
    certificate = domain.certify_extension(source, augmented)
    assert certificate["accepted"]
    assert certificate["all_residuals_zero"]


def test_intersection_alias_uses_existing_exact_locus_elaboration(bank):
    term = {"op": "intersection_ll", "args": [gc.point(n) for n in "abcd"]}
    clauses, _, _, _ = compile_call(term, bank.table, set("abcd"))
    assert "intersection_ll" not in clauses[0]
    assert clauses[0].count("on_line") == 2


def test_task_constructions_remain_visible_as_dsl_terms(bank):
    domain = SymbolicDSLDomain(TASK, CONFIG, bank)
    root = domain.initial()
    assert root["terms"]["p3"]["op"] == "midpoint"
    assert not bank.archive


def test_later_cycle_retains_frontier_and_does_not_reexecute_old_candidates(bank):
    domain = SymbolicDSLDomain(TASK, CONFIG, bank, discover=True)
    domain.search(8)
    first = set(domain.attempted)
    facts = {f.id for f in domain.facts}
    domain.search(8)
    assert first < domain.attempted
    assert facts <= {f.id for f in domain.facts}
    assert domain.costs["morphism_applications"] == len(domain.attempted)


def test_parameter_closure_preserves_shared_source_point_and_existing_hole():
    from math_os_prototype import library_compression as library
    template = {"op": "mirror", "args": [
        {"op": "midpoint", "args": [gc.point("a"), library.program_hole(0)]}, gc.point("a")]}
    closed, bindings = dsl.close_point_parameters(template, limit=2)
    assert bindings == {"a": library.program_hole(1)}
    assert closed["args"][0]["args"][0] == closed["args"][1]
    restored = library.instantiate_term(closed, {"f0": gc.point("b"), "f1": gc.point("a")})
    expected = library.instantiate_term(template, {"f0": gc.point("b")})
    assert restored == expected
    assert dsl.certify_definition(closed, [])["parameters"]


def test_parameter_closure_respects_budget_and_definition_references():
    from math_os_prototype import library_compression as library
    template = {"op": library.USE, "abstraction": "existing.definition",
                "arguments": {"f0": gc.point("a"), "f1": gc.point("b")}}
    with pytest.raises(ValueError, match="budget"):
        dsl.close_point_parameters(template, limit=1)
    closed, bindings = dsl.close_point_parameters(template, limit=2)
    assert closed["abstraction"] == "existing.definition"
    assert bindings["a"] != bindings["b"]


def test_existing_point_return_does_not_require_fresh_numeric_construction(bank, monkeypatch):
    bank, h = acquired_bank(bank)
    domain = SymbolicDSLDomain(TASK, CONFIG, bank, active=[h["id"]], discover=True)
    root = domain.initial()
    import newclid.jgex.to_newclid as numerical
    monkeypatch.setattr(numerical, "add_clause_to_problem", lambda *a, **k: pytest.fail("duplicate construction"))
    result = domain.apply(root, TypedConstructionCandidate(h["id"], ("p0", "p0"), ()))
    assert result is not None
    assert result.value["problem"] == root["problem"]
    history = domain.histories[-1]
    assert history["program"]["op"] == "use"
    assert history["execution"]["outputs"][-1][0] == "p0"
    assert history["unabridged_extension"]["accepted"]
    assert len(history["point_aliasing"]["aliases"]) == 2
    assert domain.costs["primitive_equivalent_operations"] == 2
    assert domain.costs["numeric_construction_calls"] == 0
    assert domain.costs["acquired_successful_executions"] == 1
