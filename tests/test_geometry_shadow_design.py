"""A wanted shadow, handed to the search that already exists.

The checks here are about the two things that were added — the translation of a
wanted shadow into relations, and the handling of a requirement that names more
than one unknown — and about the boundary between what the fragment can certify
and what only holds at the instance.
"""
from fractions import Fraction

import pytest

from math_os_prototype import geometry_ink as ink
from math_os_prototype import geometry_self_improvement as loop
from math_os_prototype import geometry_shadow_design as design


def point(x, y):
    return (str(Fraction(x)), str(Fraction(y)))


DEVELOPMENT = {
    "name": "development", "light": "l", "placement": ("k1", "k2"),
    "points": {"l": point(0, "3/2"), "k1": point(1, 0), "k2": point(1, 1),
               "w1": point(3, 0), "w2": point(3, 1),
               "s": point(3, "3/5"), "t": point(3, "12/5")},
    "wanted": [{"name": "A", "kind": "occluder_end", "target": "s"},
               {"name": "B", "kind": "occluder_end", "target": "t"}],
    "verify": [{"kind": "shadow_interval", "light": "l", "occluder": ["A", "B"],
                "receiving": ["w1", "w2"], "target": ["s", "t"]},
               {"kind": "on_line", "point": "A", "line": ["k1", "k2"]},
               {"kind": "between", "point": "A", "from": "l", "to": "s"}],
    "unknowns_named": ["A", "B"]}


# ---------------------------------------------------------------------------
# The translation
# ---------------------------------------------------------------------------

def test_the_translation_is_one_rule_and_keeps_the_order_condition_apart():
    unknowns = design.requirement_relations(DEVELOPMENT)
    assert [u["name"] for u in unknowns] == ["A", "B"]
    for unknown, target in zip(unknowns, ("s", "t"), strict=True):
        predicates = {(g["predicate"], tuple(g["points"])) for g in unknown["goals"]}
        assert ("coll", ("k1", "k2", unknown["name"])) in predicates
        assert ("coll", ("l", target, unknown["name"])) in predicates
        assert unknown["ordering"] == ("strictly_between", unknown["name"], "l", target)


def test_the_order_condition_is_not_one_of_the_goals():
    """An inequality is not a relation this fragment states, so it must not be smuggled in."""
    for unknown in design.requirement_relations(DEVELOPMENT):
        assert all(goal["predicate"] in ("coll", "cong", "midp", "para", "perp")
                   for goal in unknown["goals"])


# ---------------------------------------------------------------------------
# Where the existing search stops
# ---------------------------------------------------------------------------

def test_one_unknown_cannot_carry_both_ends_of_a_wanted_shadow():
    collapsed = {"points": DEVELOPMENT["points"],
                 "goals": [{"predicate": "coll", "points": ["k1", "k2", "u"]},
                           {"predicate": "coll", "points": ["l", "s", "u"]},
                           {"predicate": "coll", "points": ["l", "t", "u"]}]}
    row = loop.solve(collapsed, policy=dict(loop.START_POLICY), applications=25)
    assert not row["solved"]


def test_a_given_point_named_like_the_solvers_unknown_is_refused():
    requirement = dict(DEVELOPMENT)
    requirement["points"] = dict(DEVELOPMENT["points"], u=point(9, 9))
    with pytest.raises(ValueError, match="named"):
        design.solve_system(requirement, applications=10)


# ---------------------------------------------------------------------------
# The connection
# ---------------------------------------------------------------------------

def test_the_requirement_is_solved_and_the_answer_meets_every_published_condition():
    result = design.solve_system(DEVELOPMENT, applications=40)
    assert result["solved"], result.get("stop_reason")
    assert result["points"] == {"A": ["1", "6/5"], "B": ["1", "9/5"]}
    program = design.program_of(DEVELOPMENT, result)
    produced, reason = design.run_program(program, DEVELOPMENT["points"])
    assert reason is None
    assert produced["A"] == (Fraction(1), Fraction(6, 5))
    verification = design.check_requirement(DEVELOPMENT, produced)
    assert verification["passed"], verification


def test_the_answer_is_a_program_that_runs_again_from_the_inputs_alone():
    result = design.solve_system(DEVELOPMENT, applications=40)
    program = design.program_of(DEVELOPMENT, result)
    assert set(program["outputs"]) == {"A", "B"}
    assert all(step["prim"] in ("intersection_ll", "midpoint", "mirror", "foot", "circle",
                                "orthocenter", "reflect") for step in program["steps"])
    again, _ = design.run_program(program, DEVELOPMENT["points"])
    once, _ = design.run_program(program, DEVELOPMENT["points"])
    assert again == once


def test_a_later_unknown_may_depend_on_an_earlier_one():
    """The far end of the interval is itself constructed, and the second end needs it."""
    requirement = {
        "name": "indirect", "light": "l", "placement": ("k1", "k2"),
        "points": {"l": point(0, "3/2"), "k1": point(1, 0), "k2": point(1, 1),
                   "w1": point(3, 0), "w2": point(3, 1),
                   "s": point(3, "3/5"), "m": point(3, "3/2")},
        "wanted": [{"name": "A", "kind": "occluder_end", "target": "s"},
                   {"name": "T", "kind": "relation",
                    "goals": [{"predicate": "midp", "points": ["m", "s", "T"]},
                              {"predicate": "coll", "points": ["w1", "w2", "T"]}]},
                   {"name": "B", "kind": "occluder_end", "target": "T"}],
        "verify": [{"kind": "shadow_interval", "light": "l", "occluder": ["A", "B"],
                    "receiving": ["w1", "w2"], "target": ["s", "T"]}],
        "unknowns_named": ["A", "T", "B"]}
    result = design.solve_system(requirement, applications=40)
    assert result["solved"], result.get("stop_reason")
    program = design.program_of(requirement, result)
    assert program["primitive_steps"] == 3
    produced, reason = design.run_program(program, requirement["points"])
    assert reason is None and produced["T"] == (Fraction(3), Fraction(12, 5))
    assert design.check_requirement(requirement, produced)["passed"]


def test_the_order_condition_refuses_a_placement_line_met_only_beyond_the_screen():
    """The relations are satisfiable there; the arrangement is not. The order catches it."""
    requirement = dict(DEVELOPMENT)
    requirement["points"] = dict(DEVELOPMENT["points"], k1=point(1, 0), k2=point(2, 1))
    result = design.solve_system(requirement, applications=40)
    assert not result["solved"]
    assert result["stop_reason"] == "the order condition failed on the instance"
    assert result["stopped_at"] == "B"


def test_the_light_can_be_the_unknown_instead():
    requirement = {
        "name": "find the light", "light": "L", "placement": ("k1", "k2"),
        "points": {"a": point(1, "6/5"), "b": point(1, "9/5"), "k1": point(1, 0), "k2": point(1, 1),
                   "w1": point(3, 0), "w2": point(3, 1),
                   "s": point(3, "3/5"), "t": point(3, "12/5")},
        "wanted": [{"name": "L", "kind": "light", "rays": [("a", "s"), ("b", "t")]}],
        "verify": [{"kind": "shadow_interval", "light": "L", "occluder": ["a", "b"],
                    "receiving": ["w1", "w2"], "target": ["s", "t"]}],
        "unknowns_named": ["L"]}
    result = design.solve_system(requirement, applications=40)
    assert result["solved"]
    assert result["points"]["L"] == ["0", "3/2"]


# ---------------------------------------------------------------------------
# The answer against the drawing
# ---------------------------------------------------------------------------

def test_the_shadow_the_answer_casts_is_the_one_that_was_asked_for():
    result = design.solve_system(DEVELOPMENT, applications=40)
    program = design.program_of(DEVELOPMENT, result)
    produced, _ = design.run_program(program, DEVELOPMENT["points"])
    light = (Fraction(0), Fraction(3, 2))
    a, b = produced["A"], produced["B"]
    # a point of the wanted interval is in shadow, a point just outside it is not
    assert ink.occluded((Fraction(3), Fraction(3, 2)), light, a, b)[0]
    assert ink.occluded((Fraction(3), Fraction(3, 5)), light, a, b)[0]      # the end itself
    assert not ink.occluded((Fraction(3), Fraction(1, 2)), light, a, b)[0]  # just short of it
    assert not ink.occluded((Fraction(3), Fraction(5, 2)), light, a, b)[0]  # just past it
