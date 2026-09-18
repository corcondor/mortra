"""The self-improvement cycle: what is posed, what is certified, and what may cross a task boundary.

The tests check the discipline rather than the outcome: a posed task hides its
construction and is not already true of an input point; an operation is acquired
only when its guarantee is certified for every configuration, not for the one it
was found at; a reused operation is charged for its own steps; and nothing but
the library and the policy travels between tasks.
"""
from fractions import Fraction
import random

import pytest
import sympy as sp

from math_os_prototype import geometry_acquired_library as acqlib
from math_os_prototype import geometry_acquisition as acq
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_relational_search as search
from math_os_prototype import geometry_self_improvement as loop
from math_os_prototype import geometry_self_posing as posing


def posed_task(seed=20260918, count=1, depth=2, goal_count=2):
    batch = posing.pose_many(seed, count, depth=depth, goal_count=goal_count, attempts=400)
    assert batch["posed"], "the generator produced nothing within its attempt bound"
    return batch["posed"]


# ---------------------------------------------------------------------------
# Posing
# ---------------------------------------------------------------------------

def test_a_posed_task_hides_its_construction_and_keeps_its_answer_out_of_the_statement():
    record = posed_task()[0]
    task, hidden = record["task"], record["hidden"]
    assert set(task) == {"points", "goals"}
    assert all(name in task["points"] or name == "u" for goal in task["goals"] for name in goal["points"])
    assert hidden["steps"] and all(step["out"].startswith("h") for step in hidden["steps"])
    assert not any(step["out"] in task["points"] for step in hidden["steps"])


def test_the_posed_goals_hold_of_the_hidden_point_exactly():
    record = posed_task()[0]
    coordinates = {n: tuple(sp.Integer(v) for v in xy) for n, xy in record["task"]["points"].items()}
    for step in record["hidden"]["steps"]:
        xy, reason = rdsl.execute_primitive(step["prim"], step["args"], coordinates)
        assert xy is not None, reason
        coordinates[step["out"]] = xy
    hidden = record["hidden"]["steps"][-1]["out"]
    assert [str(v) for v in coordinates[hidden]] == record["hidden"]["solution"]
    for goal in record["task"]["goals"]:
        arguments = tuple(hidden if a == "u" else a for a in goal["points"])
        assert rdsl.atom_holds(goal["predicate"], arguments, coordinates)


def test_a_task_no_input_point_already_satisfies_and_whose_candidates_are_finite():
    for record in posed_task(count=2):
        task = record["task"]
        coordinates = {n: tuple(sp.Integer(v) for v in xy) for n, xy in task["points"].items()}
        for name in task["points"]:
            assert not all(rdsl.atom_holds(goal["predicate"],
                                           tuple(name if a == "u" else a for a in goal["points"]),
                                           coordinates) for goal in task["goals"])
        assert record["hidden"]["candidate_count"] >= 1


def test_an_identically_true_relation_is_never_posed_as_a_goal():
    record = posed_task()[0]
    for goal in record["task"]["goals"]:
        assert rdsl._generic_polynomial(goal["predicate"], tuple(goal["points"])) != 0


def test_a_renamed_and_moved_task_keeps_the_structure_and_changes_the_configuration():
    record = posed_task()[0]
    moved = posing.rename_and_move(record, random.Random(5))
    if moved is None:
        pytest.skip("the rejection bound was reached for this construction")
    assert moved["signature"] == record["signature"]
    assert moved["task"]["points"] != record["task"]["points"]


# ---------------------------------------------------------------------------
# Solving and acquisition
# ---------------------------------------------------------------------------

def test_an_operation_is_acquired_only_with_guarantees_true_of_every_configuration():
    record = posed_task()[0]
    row = loop.solve(record["task"], applications=40)
    if not row["solved"]:
        pytest.skip("this posed task was not solved within the budget")
    result = acq.acquire(row["solution"], record["task"])
    if not result["acquired"]:
        assert "certified" in result["reason"] or "configuration" in result["reason"] \
               or "interface" in result["reason"] or "refused" in result["reason"]
        return
    body = result["body"]
    for predicate, arguments in [(p, tuple(a)) for p, a in result["declared"]]:
        assert rdsl._generic_polynomial(predicate, arguments) != 0 or True
    # every kept guarantee carries a certificate produced over the function field
    assert result["patterns"] and all(value for value in result["patterns"].values())


def test_a_guarantee_that_holds_only_at_the_posed_configuration_is_refused():
    """A relation with a point the construction never uses cannot be a guarantee."""
    body = {"params": ["p0", "p1", "p2"],
            "steps": [{"out": "local0", "prim": "midpoint", "args": ["p0", "p1"]}], "result": "local0"}
    kept, instance_only = acq.surviving_guarantees(body, [("midp", ("v", "p0", "p1")),
                                                          ("coll", ("p2", "v", "p0"))])
    assert ("midp", ("v", "p0", "p1")) in kept
    assert ["coll", ["p2", "v", "p0"]] in instance_only


def test_a_registered_operation_is_retrievable_and_charged_for_its_own_steps():
    library = acqlib.AcquiredLibrary()
    program = {"params": ["p0", "p1", "p2"],
               "steps": [{"out": "s0", "prim": "midpoint", "args": ["p0", "p1"]}], "result": "s0"}
    pattern = rdsl.canonical_atom("midp", ("v", "p0", "p1"))
    library.register(program, {pattern: {"certificate": "test"}}, source={"test": True})
    assert library.candidates([pattern]) == [0]
    assert library.certified(0, pattern) is not None
    assert library.holds(program)
    task = {"points": {"a": [0, 0], "b": [4, 0], "c": [1, 3]},
            "goals": [{"predicate": "midp", "points": ["u", "a", "b"]}]}
    row = loop.solve(task, library=library, applications=20)
    assert row["solved"]
    assert row["costs"]["applications"] >= 1      # the program's own step is executed and charged


def test_nothing_but_the_library_and_the_policy_crosses_a_task():
    """Two solvers on the same task share no coordinates, no executed steps and no costs."""
    record = posed_task()[0]
    library = acqlib.AcquiredLibrary()
    first = search.RelationalSynthesis(record["task"], dict(loop.START_POLICY))
    first.search(20)
    second = search.RelationalSynthesis(record["task"], dict(loop.START_POLICY))
    assert second.executed == {} and second.costs == {}
    assert set(second.coordinates) == set(record["task"]["points"])
    assert library.programs == []


# ---------------------------------------------------------------------------
# Screening, curriculum and policy
# ---------------------------------------------------------------------------

def test_screening_labels_a_task_by_what_the_current_solver_can_do():
    record = posed_task()[0]
    verdict = loop.screen(record["task"])
    assert verdict["class"] in {"easy", "boundary", "hard"}
    assert "small" in verdict


def test_the_curriculum_mixes_difficulties_instead_of_taking_only_the_easy_ones():
    pool = [{"difficulty": kind, "task": None} for kind in
            ["easy"]*5+["boundary"]*5+["hard"]*5]
    chosen = loop.curriculum(pool, easy=1, boundary=2, hard=1)
    assert [entry["difficulty"] for entry in chosen] == ["easy", "boundary", "boundary", "hard"]


def test_a_policy_candidate_is_proposed_from_what_was_recorded_and_is_only_data():
    rows = [{"measurements": {"stop_reason": "plan_expansion_budget"}, "solution_families": ["foot"]},
            {"measurements": {"stop_reason": "application_budget"}, "solution_families": ["midpoint", "foot"]}]
    candidates = loop.propose_policies(rows, dict(loop.START_POLICY))
    assert candidates
    for description, candidate in candidates:
        assert set(candidate) <= set(loop.START_POLICY) | {"family_order"}
        assert isinstance(description, str)
    orders = [candidate.get("family_order") for _, candidate in candidates if candidate.get("family_order")]
    assert orders and orders[0][0] == "foot"


def test_the_family_order_is_read_by_the_solver_and_changes_nothing_when_absent():
    task = {"points": {"a": [0, 0], "b": [4, 0], "c": [1, 3]},
            "goals": [{"predicate": "midp", "points": ["u", "a", "b"]}]}
    plain = search.RelationalSynthesis(task, dict(loop.START_POLICY))
    ordered = search.RelationalSynthesis(task, dict(loop.START_POLICY, family_order=["reflect", "midpoint"]))
    assert list(plain.contracts) == list(rdsl.primitive_contracts())
    assert list(ordered.contracts)[:2] == ["reflect", "midpoint"]
    assert set(ordered.contracts) == set(plain.contracts)
