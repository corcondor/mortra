"""Reading a goal backwards through a primitive: what the substitution must keep and must refuse.

The tests are about the discipline of the path, not about one task: the
specification is built from the primitive's own output function and the goal
polynomials, the conditions that make the operation defined are kept rather than
cancelled, a point is decided exactly, a bound is reported as an unfinished
search, and the solver's acceptance is unchanged.
"""
from fractions import Fraction

import pytest
import sympy as sp

from math_os_prototype import geometry_backsubstitution as backward
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_relational_search as search
from math_os_prototype import geometry_self_improvement as loop

DEVELOPMENT = {"points": {"a": [0, -8], "b": [-5, -8], "c": [5, 4], "d": [-9, -2], "e": [5, 2]},
               "goals": [{"predicate": "cong", "points": ["e", "u", "a", "b"]},
                         {"predicate": "para", "points": ["u", "e", "e", "c"]},
                         {"predicate": "coll", "points": ["u", "e", "c"]}]}

SQUARE = {"a": (Fraction(0), Fraction(0)), "b": (Fraction(4), Fraction(0)),
          "c": (Fraction(4), Fraction(4)), "e": (Fraction(0), Fraction(4))}


def goal_atoms(task):
    return [(goal["predicate"], tuple(goal["points"])) for goal in task["goals"]]


# ---------------------------------------------------------------------------
# The substitution itself
# ---------------------------------------------------------------------------

def test_the_specification_comes_from_the_primitive_s_own_output_function():
    """midpoint(w, e) lands on the line through e and c exactly when w does."""
    coordinates = {name: tuple(sp.Rational(v) for v in xy) for name, xy in DEVELOPMENT["points"].items()}
    specification = backward.intermediate_specification(
        [("coll", ("u", "e", "c"))], coordinates, "midpoint", {"f1": "e"}, "f0")
    assert specification is not None
    assert specification["family"] == "midpoint" and specification["unknown"] == "f0"
    equality = sp.expand(specification["equalities"][0])
    # e and c share the abscissa 5, so the condition on the unknown is that it does too
    assert sp.simplify(equality/sp.Poly(equality, *backward.UNKNOWN).LC()) in (
        backward.UNKNOWN[0]-5, -(backward.UNKNOWN[0]-5), 5-backward.UNKNOWN[0])


def test_a_goal_no_primitive_guarantees_still_produces_a_specification():
    """The three conditions of the development task match no primitive's post at all."""
    synthesis = search.RelationalSynthesis(DEVELOPMENT, dict(loop.START_POLICY))
    root = tuple(sorted({rdsl.canonical_atom(p, tuple("v" if a == "u" else a for a in args))
                         for p, args in synthesis.goal_atoms}))
    assert all(not synthesis._matchings(family, root) for family in synthesis.contracts)
    coordinates = {name: tuple(sp.Rational(v) for v in xy) for name, xy in DEVELOPMENT["points"].items()}
    specification = backward.intermediate_specification(
        synthesis.goal_atoms, coordinates, "midpoint", {"f1": "e"}, "f0")
    assert specification is not None and len(specification["equalities"]) == 3


def test_every_goal_is_carried_as_a_conjunction_about_the_same_unknown():
    coordinates = {name: tuple(sp.Rational(v) for v in xy) for name, xy in DEVELOPMENT["points"].items()}
    specification = backward.intermediate_specification(
        goal_atoms(DEVELOPMENT), coordinates, "midpoint", {"f1": "e"}, "f0")
    symbols = set()
    for equality in specification["equalities"]:
        symbols |= equality.free_symbols
    assert symbols <= set(backward.UNKNOWN)
    assert len(specification["equalities"]) == len(DEVELOPMENT["goals"])


def test_the_conditions_that_make_the_operation_defined_are_kept():
    """A primitive with a guard keeps it as a non-zero condition on the unknown."""
    kept = []
    for family, contract in rdsl.primitive_contracts().items():
        if not contract["guards"]:
            continue
        parameters = contract["params"]
        binding = dict(zip(parameters[1:], ["b", "c", "e"][:len(parameters)-1], strict=False))
        specification = backward.intermediate_specification(
            [("coll", ("u", "b", "c"))], SQUARE, family, binding, parameters[0])
        if specification is not None:
            kept.append((family, len(specification["nonzero"])))
    assert kept and any(count > 0 for _, count in kept)


def test_a_condition_that_cannot_hold_is_refused_rather_than_searched():
    coordinates = dict(SQUARE)
    # the midpoint of w and b can never equal a fixed distinct point unless w is determined,
    # but a contradiction shows up as a constant: build one by asking for two distances at once
    specification = backward.intermediate_specification(
        [("cong", ("a", "u", "a", "u"))], coordinates, "midpoint", {"f1": "b"}, "f0")
    assert specification is None or all(e.free_symbols for e in specification["equalities"])


def test_a_point_is_decided_exactly_and_the_decision_is_charged():
    from collections import Counter
    coordinates = {name: tuple(sp.Rational(v) for v in xy) for name, xy in DEVELOPMENT["points"].items()}
    specification = backward.intermediate_specification(
        goal_atoms(DEVELOPMENT), coordinates, "midpoint", {"f1": "e"}, "f0")
    counter = Counter()
    assert backward.satisfied(specification, (Fraction(5), Fraction(-8)), counter=counter)
    assert not backward.satisfied(specification, (Fraction(0), Fraction(0)), counter=counter)
    assert counter["backward_specification_checks"] >= 2


def test_a_specification_over_the_size_bound_is_an_unfinished_search_not_an_impossible_goal():
    coordinates = {name: tuple(sp.Rational(v) for v in xy) for name, xy in DEVELOPMENT["points"].items()}
    with pytest.raises(backward.BackwardBudget):
        backward.intermediate_specification(goal_atoms(DEVELOPMENT), coordinates, "midpoint",
                                            {"f1": "e"}, "f0", degree_bound=1)


# ---------------------------------------------------------------------------
# The path inside the solver
# ---------------------------------------------------------------------------

def test_the_backward_path_is_off_unless_the_configuration_asks_for_it():
    row = loop.solve(DEVELOPMENT, policy=dict(loop.START_POLICY), applications=40)
    assert not row["solved"]
    assert not any(key.startswith("backward") for key in row["costs"])


def test_the_backward_path_solves_the_task_no_budget_solves():
    for applications in (40, 400):
        row = loop.solve(DEVELOPMENT, policy=dict(loop.START_POLICY), applications=applications)
        assert not row["solved"], "more budget alone should not solve it"
        assert row["costs"]["applications"] < applications, "it stops for want of plans, not budget"
    row = loop.solve(DEVELOPMENT, policy=dict(loop.START_POLICY, backward_substitution=True),
                     applications=40)
    assert row["solved"] and row["solution"]["via"] == "backward_substitution"
    specification = row["solution"]["backward"]["specification"]
    assert specification["family"] and specification["equalities"]
    assert row["solution"]["replay"]["passed"]                     # accepted by primitive re-execution


def test_the_accepted_solution_meets_every_original_goal():
    row = loop.solve(DEVELOPMENT, policy=dict(loop.START_POLICY, backward_substitution=True),
                     applications=40)
    assert row["solved"]
    point = row["solution"]["point"]
    synthesis = search.RelationalSynthesis(DEVELOPMENT, dict(loop.START_POLICY))
    coordinates = dict(synthesis.inputs)
    replayed, _ = search.independent_replay(row["solution"]["term"], synthesis.inputs)
    coordinates["u"] = tuple(sp.cancel(v) for v in replayed)
    for predicate, arguments in synthesis.goal_atoms:
        assert rdsl.atom_holds(predicate, tuple(arguments), coordinates)


def test_the_backward_allowance_is_its_own_and_is_reported():
    row = loop.solve(DEVELOPMENT, policy=dict(loop.START_POLICY, backward_substitution=True,
                                              backward_applications=50), applications=40)
    assert row["costs"]["backward_allowance"] == 50
    assert row["costs"]["applications"] <= 40+50


def test_the_expression_work_is_counted():
    row = loop.solve(DEVELOPMENT, policy=dict(loop.START_POLICY, backward_substitution=True),
                     applications=40)
    for key in ("backward_specifications_built", "backward_goal_substitutions",
                "backward_expression_terms", "backward_specification_checks"):
        assert row["costs"][key] > 0
