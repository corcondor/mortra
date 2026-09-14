"""Artificial completeness/regression checks, not autonomous discoveries."""
from copy import deepcopy
from itertools import product
import json

import pytest

from worker.backend.typed_geometry_stalk import (
    ConstructionFamily, DEFAULT_POINT_FAMILIES, _family_inputs,
    iter_complete_typed_candidates,
)
from math_os_prototype.runtime_typed_planner import (
    RuntimePrimitive, PrimitiveResult, initial_fact, synthesize_typed_plan,
)
from math_os_prototype.theory_geometry_feedback import GeometryLibrary, SemanticGeometryDomain
from math_os_prototype.theory_geometry_selection import SelectionDomain


@pytest.mark.parametrize("family", DEFAULT_POINT_FAMILIES)
def test_all_declared_symmetry_tuples_are_present(family):
    points = tuple("abcde")
    rows = list(iter_complete_typed_candidates(points=points, graph={},
        goal_multiplicity={}, generated_points=set(), family=family))
    assert {r.inputs for r in rows} == set(_family_inputs(points, family))
    assert len(rows) > 3
    assert len(rows) == len({r.inputs for r in rows})


def test_acquired_arguments_past_128_and_non_core_points_are_not_lost():
    points = tuple("abcdefgh")
    family = ConstructionFamily("arbitrary", 5, "ordered", allow_repeated_inputs=True)
    rows = iter_complete_typed_candidates(points=points, graph={}, goal_multiplicity={},
        generated_points=set(), family=family)
    actual = {r.inputs for r in rows}
    assert actual == set(product(points, repeat=5))
    assert len(actual) == 32768


@pytest.fixture(scope="module")
def bank():
    return GeometryLibrary()


SEARCH = {"seed": 17, "max_depth": 50, "wall_seconds": 60,
    "max_primitive_operations": 2000, "max_candidate_checks": 10000,
    "ranking_window": 4, "trace_predicates": True,
    # Obsolete values must not become membership restrictions in complete mode.
    "per_family_limit": 3, "max_input_tuples": 128}
TASK = {"points": {"a": [0, 0], "b": [4, 0], "c": [1, 3], "d": [3, 2], "e": [7, 8]}}


def test_normal_domain_emits_beyond_former_prefix_and_records_predicates(bank):
    events = []
    d = SemanticGeometryDomain(TASK, SEARCH, bank, emit=events.append)
    rows = list(d.candidate_rows("midpoint", d.initial()))
    assert len(rows) == 10
    result = d.apply(d.initial(), rows[-1], ("midpoint", d.key(d.initial()), rows[-1].inputs))
    assert result is not None
    assert any(e["event"] == "predicate_check" for e in events)
    assert any(e["event"] == "candidate_stream_exhausted" for e in events)


def test_global_budget_is_reported_not_treated_as_no_more_candidates(bank):
    d = SemanticGeometryDomain(TASK, dict(SEARCH, max_candidate_checks=5), bank)
    assert len(list(d.candidate_rows("midpoint", d.initial()))) == 5
    assert d.stop_reason == "candidate_check_budget"


@pytest.mark.parametrize("guided", [False, True])
def test_all_selection_pages_eventually_execute(guided, bank, monkeypatch):
    task = dict(TASK, goals=[{"predicate": "cong", "points": ["u", "a", "u", "b"]}])
    d = SelectionDomain(task, SEARCH, bank, guided=guided)
    seen = []
    monkeypatch.setattr(d, "apply", lambda state, row, attempt: seen.append(row.inputs))
    for offer in d.alternatives("midpoint", d.initial()):
        offer()
    assert len(seen) == 10
    assert set(seen) == set(_family_inputs(tuple(TASK["points"]), DEFAULT_POINT_FAMILIES[0]))
    assert [r["offset"] for r in d.proposal_audit] == [0, 4, 8]
    assert [r["count"] for r in d.proposal_audit] == [4, 4, 2]


@pytest.mark.parametrize("guided", [False, True])
def test_child_state_can_expand_before_parent_stream_exhaustion(guided):
    trace = []
    def offers(args):
        value = args[0].value
        for i in range(1000):
            def invoke(value=value, i=i):
                trace.append((value, i))
                return PrimitiveResult(value+1, {"step": i}) if i == 0 and value < 2 else None
            yield invoke
    primitive = RuntimePrimitive("next", ("X",), "X", lambda _: None, alternatives=offers)
    plan = synthesize_typed_plan([initial_fact("X", 0)], [primitive], ["X"],
        goal_predicates={"X": lambda f: f.value == 2}, max_states=10,
        fair=True, fair_state_streams=True, rank_fair_rounds=guided)
    assert plan.complete
    assert (1, 0) in trace
    assert len(trace) < 10
    assert (0, 999) not in trace


def test_continuation_does_not_reexecute_completed_calls(bank):
    events = []
    d = SemanticGeometryDomain(TASK, SEARCH, deepcopy(bank), emit=events.append)
    d.search(3)
    before = {h["id"] for h in d.histories}
    d.search(6)
    assert before < {h["id"] for h in d.histories}
    assert len(d.histories) == len({h["id"] for h in d.histories})


def test_audit_keeps_failed_predicate_requests_and_reasons(tmp_path):
    from math_os_prototype.geometry_execution_audit import aggregate_geometry_events
    log = tmp_path/"events.jsonl"
    rows = [
        {"event": "predicate_check", "cohort": "regression", "arm": "D",
         "predicate": "perp", "source": "goal", "passed": False},
        {"event": "candidate_scan", "cohort": "regression", "arm": "D",
         "family": "foot", "ordinal": 130, "disposition": "eligible"},
        {"event": "refusal", "cohort": "regression", "arm": "D",
         "family": "foot", "reason": "duplicate_output_point"}]
    log.write_text("".join(json.dumps(r)+"\n" for r in rows))
    result = aggregate_geometry_events(log)
    assert result["predicate_requests"]["regression:D"]["perp:goal:False"] == 1
    assert result["families"]["regression:D"]["foot"]["largest_scan_ordinal"] == 130
    assert result["predicate_request_coverage"] == "recorded"


def test_pipeline_passes_only_its_new_archive_to_selection(tmp_path, monkeypatch):
    from math_os_prototype import theory_geometry_selection as selection
    from math_os_prototype import theory_geometry_feedback as feedback
    captured = {}
    config = {"acquisition_config": "configs/theory-geometry-semantic-feedback-eight-cycles.json",
        "selection_config": "configs/theory-geometry-selection-factorial.json",
        "search_overrides": {"candidate_enumeration": "complete"}}
    def acquire(c, out):
        assert "per_family_limit" not in c["search"]
        (out/"C-archive.json").write_text('[{"test_marker": "current-run-only"}]')
        (out/"frozen-plan.json").write_text(json.dumps(c))
        (out/"events.jsonl").touch()
        return {"execution_completed": True}
    def compare(c, out, *, frozen_inputs):
        captured["definitions"] = frozen_inputs[0]
        assert c["source_archive"]["kind"] == "current_normal_run_acquisition"
        assert "max_input_tuples" not in c["search"]
        (out/"events.jsonl").touch()
        return {"execution_completed": True}
    monkeypatch.setattr(feedback, "run_semantic_feedback", acquire)
    monkeypatch.setattr(selection, "run_selection_factorial", compare)
    result = selection.run_complete_revalidation(config, tmp_path)
    assert result["execution_completed"] and not result["old_library_loaded"]
    assert captured["definitions"] == [{"test_marker": "current-run-only"}]
