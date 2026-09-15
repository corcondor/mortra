"""Synthetic audit-unit tests, not autonomous acquisition evidence."""
from collections import Counter

from math_os_prototype import geometry_contracts as gc
from scripts.diagnose_geometry_failure_location import (
    complete_grammar_probe, goal_proofs, initial, input_state_count, replay, signature, term,
)


def test_signatures_keep_asymmetric_roles():
    xy = [["0", "0"], ["1", "0"], ["0", "1"], ["2", "2"]]
    assert signature("mirror", xy[:2]) != signature("mirror", xy[1::-1])
    assert signature("foot", xy[:3]) == signature("foot", [xy[0], xy[2], xy[1]])
    assert signature("foot", xy[:3]) != signature("foot", [xy[1], xy[0], xy[2]])


def test_line_pair_signature_only_changes_orientation_and_pair_order():
    xy = [["0", "0"], ["1", "0"], ["0", "1"], ["2", "2"]]
    assert signature("intersection_ll", xy) == signature("intersection_ll", xy[::-1])
    assert signature("intersection_ll", xy) != signature("intersection_ll", [xy[0], xy[2], xy[1], xy[3]])


def test_exact_replay_and_goal_conditions():
    task = {"points": {"a": [0, 0], "b": [2, 0]},
            "goals": [{"predicate": "cong", "points": ["u", "a", "u", "b"]}]}
    from math_os_prototype.geometry_semantic_dsl import FRAGMENT
    steps, out = gc.dag(term(["midpoint", "a", "b"]), fragment=FRAGMENT)
    rows, objects, error = replay(steps, initial(task)["objects"], Counter())
    assert error is None and rows[0]["coordinates"] == ["1", "0"]
    assert all(goal_proofs(task, objects, out, Counter()))


def test_degenerate_primitive_is_not_mislabeled_as_valid():
    task = {"points": {"a": [0, 0], "b": [1, 0]}, "goals": []}
    rows, _, error = replay([{"family": "foot", "inputs": ["a", "b", "b"], "output": "v"}],
                            initial(task)["objects"], Counter())
    assert rows == [] and error == "primitive_precondition_refused"


def test_individual_reach_is_not_copresence():
    a = initial({"points": {"a": [0, 0]}, "goals": []})
    b = initial({"points": {"b": [1, 0]}, "goals": []})
    assert input_state_count({"a": a, "b": b}, [["0", "0"], ["1", "0"]]) == []


def test_probe_uses_declared_complete_grammar():
    task = {"points": {"a": [0, 0], "b": [2, 0]}, "goals": []}
    step = {"family": "midpoint", "input_coordinates": [["0", "0"], ["2", "0"]]}
    assert complete_grammar_probe(initial(task), task, step)["exists"]
