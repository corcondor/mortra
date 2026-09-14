"""Artificial development fixtures, not normal-run acquisition evidence."""
from copy import deepcopy
import pytest

from math_os_prototype import geometry_semantic_dsl as dsl, library_compression as lib
from math_os_prototype import theory_geometry_selection as selection
from math_os_prototype.runtime_typed_planner import (
    RuntimePrimitive, RankedAlternative, initial_fact, synthesize_typed_plan)
from math_os_prototype.theory_geometry_feedback import GeometryLibrary, SemanticGeometryDomain


TASK = {"points": {"a": [0, 0], "b": [4, 0], "c": [1, 3], "d": [3, 2]},
        "goals": [{"predicate": "perp", "points": ["a", "u", "b", "c"]}]}
SEARCH = {"seed": 4, "max_depth": 100, "per_family_limit": 3, "max_input_tuples": 128,
          "max_primitive_operations": 1000, "wall_seconds": 60}


@pytest.fixture(scope="module")
def bank():
    return GeometryLibrary()


@pytest.fixture(scope="module")
def extended(bank):
    result = deepcopy(bank)
    f = [lib.program_hole(i) for i in range(3)]
    h = dsl.certify_definition({"op": "midpoint", "args": [f[0], {"op": "midpoint", "args": f[1:]}]}, [])
    result.register(h)
    return result


@pytest.mark.parametrize("enabled", [False, True])
@pytest.mark.parametrize("family", tuple(dsl.FRAGMENT.arities))
def test_same_state_candidate_set_is_unchanged(extended, enabled, family):
    active = [h["id"] for h in extended.archive] if enabled else []
    plain = selection.SelectionDomain(TASK, SEARCH, extended, active=active)
    guided = selection.SelectionDomain(TASK, SEARCH, extended, active=active, guided=True)
    p = plain.proposals(family, plain.initial())
    q = guided.proposals(family, guided.initial())
    assert sorted((r.family, r.inputs) for r, *_ in p) == sorted((r.family, r.inputs) for r, *_ in q)
    assert selection.compare_memberships(plain.proposal_audit, guided.proposal_audit)["mismatches"] == 0


def test_acquired_family_candidate_set_is_unchanged(extended):
    h = extended.archive[0]["id"]
    plain = selection.SelectionDomain(TASK, SEARCH, extended, active=[h])
    guided = selection.SelectionDomain(TASK, SEARCH, extended, active=[h], guided=True)
    a = plain.proposals(h, plain.initial())
    b = guided.proposals(h, guided.initial())
    assert sorted(r.inputs for r, *_ in a) == sorted(r.inputs for r, *_ in b)
    assert a and b


def test_alignment_uses_bound_arguments_and_preserves_state(bank):
    d = selection.SelectionDomain(TASK, SEARCH, bank, guided=True)
    before = d.initial().record()
    assert d.alignment("foot", ("a", "b", "c")).direct_match_count == 1
    assert d.alignment("foot", ("b", "a", "c")).direct_match_count == 0
    assert before == d.initial().record()
    # An unrelated constructor remains offered, with unchanged certification.
    assert d.proposals("circle", d.initial())


def test_unguided_matches_existing_normal_search(bank):
    old = SemanticGeometryDomain(TASK, SEARCH, bank, policy="SOLVE").search(14)
    new = selection.SelectionDomain(TASK, SEARCH, bank).search(14)
    assert old["solved"] == new["solved"]
    assert old["reach"] == new["reach"]
    assert old["costs"]["candidate_expansions"] == new["costs"]["candidate_expansions"]
    assert new["costs"].get("selection_alignment_calls", 0) == 0


@pytest.mark.parametrize("guided", [False, True])
def test_solution_keeps_replay_and_construction_dag(bank, guided):
    task = dict(TASK, goals=[{"predicate": "midp", "points": ["u", "a", "b"]}])
    result = selection.SelectionDomain(task, SEARCH, bank, guided=guided).search(14)
    assert result["solved"]
    assert result["solution"]["replay"]["passed"]
    assert result["solution"]["construction_ancestors"]
    assert result["construction_proof_dag"]


def test_ranking_does_not_bypass_failed_independent_replay(bank, monkeypatch):
    d = selection.SelectionDomain(TASK, SEARCH, bank, guided=True)
    monkeypatch.setattr(d, "replay", lambda *a: {"passed": False, "residuals": ["1", "0"]})
    assert not d.search(8)["solved"]
    assert not d.histories


def test_ranked_fair_rounds_keep_every_offer_and_periodic_original_order():
    trace = []
    def primitive(name, priority):
        def offers(args):
            for i in range(5):
                yield RankedAlternative(lambda i=i: trace.append((name, i)), (priority,))
        return RuntimePrimitive(name, ("X",), "X", lambda args: None, alternatives=offers)
    synthesize_typed_plan([initial_fact("X", 0)], [primitive("a", 2), primitive("b", 0), primitive("c", 1)],
        ["X"], goal_predicates={"X": lambda _: False}, max_states=100,
        fair=True, rank_fair_rounds=True, original_order_every=4)
    assert len(trace) == 15
    assert trace[:3] == [("b", 0), ("c", 0), ("a", 0)]
    assert trace[9:12] == [("a", 3), ("b", 3), ("c", 3)]
    assert set(trace) == {(n, i) for n in "abc" for i in range(5)}


def test_invalid_ranked_schedule_refused():
    with pytest.raises(ValueError, match="fair"):
        synthesize_typed_plan([], [], [], rank_fair_rounds=True)


def test_frozen_instance_generation_is_reproducible_and_goal_preserving():
    a = selection.transferred_instances([TASK]*2, 23, [-9, 9])
    assert a == selection.transferred_instances([TASK]*2, 23, [-9, 9])
    assert all(t["goals"] == TASK["goals"] for t in a)
    assert a[0]["points"] != a[1]["points"]
    with pytest.raises(ValueError, match="premises"):
        selection.transferred_instances([dict(TASK, predicates=[{}])], 23, [-9, 9])


def test_membership_audit_detects_missing_candidate():
    a = [{"state": "s", "family": "f", "set_sha256": "one"}]
    b = [{"state": "s", "family": "f", "set_sha256": "two"}]
    assert selection.compare_memberships(a, b) == {"common_state_families": 1, "mismatches": 1}


def test_factorial_contrast_does_not_confuse_main_policy_effect():
    def row(solved):
        return {"solved": solved, "task_sha256": "x", "costs": {}, "total_task_seconds": 1,
                "solution": {"acquired_calls": []} if solved else None}
    results = {k: [row(s)] for k, s in zip("ABCD", (False, True, False, True))}
    assert selection.factorial(results)["interaction_D_minus_C_minus_B_plus_A"]["solved"] == 0


def test_small_fixed_library_factorial_runs_without_acquisition(tmp_path, monkeypatch, extended):
    task = dict(TASK, goals=[{"predicate": "midp", "points": ["u", "a", "b"]}])
    monkeypatch.setattr(selection, "read_inputs", lambda *a: (deepcopy(extended.archive),
        {"training": [], "evaluation": [task]}, 0))
    config = {"source_archive": {}, "protocol": {
        "holdout_seed": 31, "holdout_coordinate_range": [-9, 9], "fair_original_round_every": 4,
        "conditions": {"A": [False, False], "B": [False, True], "C": [True, False], "D": [True, True]}},
        "search": SEARCH, "applications": 14, "diagnostic": {"enabled": False}}
    result = selection.run_selection_factorial(config, tmp_path)
    assert result["execution_completed"] and result["library_unchanged"]
    assert result["reacquisitions"] == 0
    assert result["candidate_membership_mismatches"] == 0
    assert all(result["summary"]["transfer"]["arms"][k]["solved"] == 1 for k in "ABCD")
