"""Drawing programs as data: the language, the interpreter, and what the search builds.

What is guarded here is the line between the geometry, which does not move, and
the execution language, which is new: the primitives and predicates are exactly
the ones the fragment had, `let`/`emit`/`call`/`keep` add no relation and no
construction, and a macro — a body kept so a later search reaches a point sooner
— carries no guarantee and is never mistaken for an acquired operation.
"""
from collections import Counter
from fractions import Fraction

import pytest

from math_os_prototype import geometry_drawing_program as dp
from math_os_prototype import geometry_self_improvement as loop

A, B, C = (Fraction(0), Fraction(0)), (Fraction(4), Fraction(6)), (Fraction(8), Fraction(0))
INPUTS = {"p0": A, "p1": B, "p2": C}

SUBDIVISION = {
    "name": "r", "params": ["p0", "p1", "p2"],
    "body": [{"let": "v1", "op": "midpoint", "args": ["p0", "p1"]},
             {"let": "v2", "op": "midpoint", "args": ["p1", "p2"]},
             {"let": "v3", "op": "midpoint", "args": ["v1", "v2"]}],
    "emit": ["v3"],
    "calls": [{"rule": "r", "args": ["p0", "v1", "v3"]},
              {"rule": "r", "args": ["p2", "v2", "v3"]}]}


def quadratic(t, a=A, b=B, c=C):
    return tuple((1-t)**2*a[i]+2*t*(1-t)*b[i]+t**2*c[i] for i in (0, 1))


# ---------------------------------------------------------------------------
# The geometry did not move
# ---------------------------------------------------------------------------

def test_the_core_is_the_seven_primitives_and_the_ten_predicates():
    core = dp.geometric_core()
    assert sorted(core["primitives"]) == ["circle", "foot", "intersection_ll", "midpoint",
                                          "mirror", "orthocenter", "reflect"]
    assert sorted(core["predicates"]) == ["coll", "cong", "cyclic", "diff", "eqangle", "midp",
                                          "ncoll", "npara", "para", "perp"]


def test_the_language_adds_no_operator_of_its_own():
    table = dp.operators()
    assert set(table) == set(dp.FAMILIES)
    assert all(entry["kind"] == "primitive" for entry in table.values())


# ---------------------------------------------------------------------------
# The language and its interpreter
# ---------------------------------------------------------------------------

def test_a_program_that_does_not_type_is_refused_before_it_runs():
    table = dp.operators()
    for broken in ({"name": "r", "params": ["p0"], "emit": ["nope"], "body": []},
                   {"name": "r", "params": ["p0", "p1"], "emit": ["v"], "calls": [],
                    "body": [{"let": "v", "op": "midpoint", "args": ["p0", "missing"]}]},
                   {"name": "r", "params": ["p0", "p1"], "emit": ["v"], "calls": [],
                    "body": [{"let": "v", "op": "midpoint", "args": ["p0"]}]},
                   {"name": "r", "params": ["p0", "p1"], "emit": ["v"], "calls": [],
                    "body": [{"let": "v", "op": "draw_curve", "args": ["p0", "p1"]}]}):
        with pytest.raises(dp.ProgramRefused):
            dp.validate(broken, table)


def test_the_recursion_is_bounded_and_the_count_follows_the_depth():
    counts = {depth: len(dp.run(SUBDIVISION, INPUTS, depth)[0]) for depth in range(0, 7)}
    assert counts == {0: 0, 1: 1, 2: 3, 3: 7, 4: 15, 5: 31, 6: 63}


def test_the_same_program_draws_a_different_figure_from_different_inputs():
    here, _ = dp.run(SUBDIVISION, INPUTS, 4)
    moved = {"p0": (Fraction(-1), Fraction(1)), "p1": (Fraction(3), Fraction(9)),
             "p2": (Fraction(9), Fraction(-1))}
    there, _ = dp.run(SUBDIVISION, moved, 4)
    assert len(here) == len(there) == 15
    assert {dp.exact(p) for p in here} != {dp.exact(p) for p in there}
    assert dp.exact(quadratic(Fraction(1, 2), *moved.values())) in {dp.exact(p) for p in there}


def test_keep_drops_a_point_when_an_existing_relation_fails():
    program = {"name": "r", "params": ["p0", "p1", "p2"],
               "body": [{"let": "v", "op": "midpoint", "args": ["p0", "p1"]},
                        {"keep": "v", "where": ["coll", ["p0", "p1", "v"]]}],
               "emit": ["v"], "calls": []}
    assert len(dp.run(program, INPUTS, 1)[0]) == 1          # the midpoint is on the line
    refusing = dict(program, body=[program["body"][0],
                                   {"keep": "v", "where": ["perp", ["p0", "p1", "p0", "v"]]}])
    assert dp.run(refusing, INPUTS, 1)[0] == []             # it is not perpendicular to it


# ---------------------------------------------------------------------------
# What the search builds
# ---------------------------------------------------------------------------

def test_the_equality_a_point_level_hole_asks_for_is_not_a_goal_the_relational_search_takes():
    """A construction whose output is this point matches no primitive's guarantee."""
    target = quadratic(Fraction(1, 2))
    task = {"points": {"a": [str(v) for v in A], "b": [str(v) for v in B],
                       "c": [str(v) for v in C], "m": [str(v) for v in target]},
            "goals": [{"predicate": "cong", "points": ["m", "u", "m", "m"]}]}
    row = loop.solve(task, policy=dict(loop.START_POLICY), applications=20)
    assert not row["solved"]
    assert row["costs"].get("applications", 0) == 0         # it never even offered a candidate


def test_a_requirement_of_seven_points_pins_the_subdivision_rule():
    targets = [quadratic(Fraction(k, 8)) for k in (1, 2, 3, 4, 5, 6, 7)]
    result = dp.synthesise_rule(targets, INPUTS, levels=2, node_budget=4000, depth=3)
    assert result["solved"], result.get("reason")
    program = result["program"]
    assert len(program["calls"]) == 2
    assert all(statement["op"] == "midpoint" for statement in program["body"])
    check = dp.check(program, INPUTS, 3, {"must_contain": targets})
    assert check["passed"], check


def test_a_weaker_requirement_admits_a_shorter_program():
    """Three points do not pin the rule, and the search is free to return the cheapest."""
    targets = [quadratic(Fraction(1, 2)), quadratic(Fraction(1, 4)), quadratic(Fraction(3, 4))]
    result = dp.synthesise_rule(targets, INPUTS, levels=2, node_budget=4000, depth=3)
    assert result["solved"]
    assert dp.check(result["program"], INPUTS, 3, {"must_contain": targets})["passed"]


def test_the_search_stops_at_the_first_body_whose_recursion_closes():
    targets = [quadratic(Fraction(k, 8)) for k in (1, 2, 3, 4, 5, 6, 7)]
    counter = Counter()
    result = dp.synthesise_rule(targets, INPUTS, levels=2, node_budget=4000, depth=3,
                                counter=counter)
    assert result["solved"]
    assert result["nodes_to_success"] < 4000                # it did not spend the whole budget


# ---------------------------------------------------------------------------
# Macros are not acquired operations
# ---------------------------------------------------------------------------

def test_a_macro_reaches_in_one_step_what_its_body_reached_in_three():
    macro = dp.macro_from(SUBDIVISION)
    assert macro is not None and macro["primitive_steps"] == 3
    table = dp.operators(macros=[macro])
    coordinates = {name: dp.exact(value) for name, value in INPUTS.items()}
    xy, reason = dp.apply_operator(macro["name"], ["p0", "p1", "p2"], coordinates, table, Counter())
    assert reason is None
    assert dp.exact(xy) == dp.exact(quadratic(Fraction(1, 2)))


def test_a_macro_carries_no_guarantee_and_says_so():
    macro = dp.macro_from(SUBDIVISION)
    assert macro["guarantees"] is None
    assert "not a certified operation" in macro["note"]
    table = dp.operators(macros=[macro])
    assert table[macro["name"]]["kind"] == "macro"
    assert all(entry["kind"] != "acquired" for entry in table.values())


def test_the_same_body_always_gets_the_same_macro_name():
    assert dp.macro_from(SUBDIVISION)["name"] == dp.macro_from(dict(SUBDIVISION))["name"]


# ---------------------------------------------------------------------------
# The geometric core does not need Newclid
# ---------------------------------------------------------------------------

def test_no_module_of_the_geometry_path_imports_newclid_at_import_time():
    """A top-level newclid import anywhere in the chain makes the core need it to load."""
    import re
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    offenders = []
    for name in ("math_os_prototype/geometry_drawing_program.py",
                 "math_os_prototype/geometry_ink.py",
                 "math_os_prototype/geometry_shadow_design.py",
                 "math_os_prototype/geometry_relational_dsl.py",
                 "math_os_prototype/geometry_semantic_dsl.py",
                 "math_os_prototype/geometry_contracts.py",
                 "math_os_prototype/geometry_relational_library.py",
                 "worker/backend/jgex_exact_constraint_bridge.py",
                 "worker/backend/jgex_legacy_normalizer.py",
                 "worker/backend/jgex_gclc_translator.py"):
        text = (root/name).read_text(encoding="utf-8")
        if re.search(r"^(from|import) newclid", text, flags=re.M):
            offenders.append(name)
    assert not offenders, f"these import newclid at module level: {offenders}"


def test_the_whole_path_runs_with_newclid_made_unimportable():
    """Blocked in a separate process, so the check cannot be hidden by an earlier import."""
    import subprocess
    import sys
    from pathlib import Path

    root = Path(__file__).resolve().parents[1]
    program = (
        "import builtins, sys\n"
        "real = builtins.__import__\n"
        "def guard(name, *a, **k):\n"
        "    if name == 'newclid' or name.startswith('newclid.'):\n"
        "        raise ImportError('blocked: '+name)\n"
        "    return real(name, *a, **k)\n"
        "builtins.__import__ = guard\n"
        f"sys.path.insert(0, {str(root)!r})\n"
        "from fractions import Fraction as F\n"
        "from math_os_prototype import geometry_drawing_program as dp\n"
        "from math_os_prototype import geometry_ink as ink\n"
        "a, b, c = (F(0), F(0)), (F(4), F(6)), (F(8), F(0))\n"
        "def q(t):\n"
        "    return tuple((1-t)**2*a[i]+2*t*(1-t)*b[i]+t**2*c[i] for i in (0, 1))\n"
        "targets = [q(F(k, 8)) for k in (1, 2, 3, 4, 5, 6, 7)]\n"
        "r = dp.synthesise_rule(targets, {'p0': a, 'p1': b, 'p2': c}, levels=2,\n"
        "                       node_budget=4000, depth=3)\n"
        "assert r['solved'], r.get('reason')\n"
        "assert dp.check(r['program'], {'p0': a, 'p1': b, 'p2': c}, 3,\n"
        "                {'must_contain': targets})['passed']\n"
        "assert ink.occluded((F(3), F(0)), (F(0), F(0)), (F(1), F(-1)), (F(1), F(1)))[0]\n"
        "print('ok')\n")
    finished = subprocess.run([sys.executable, "-c", program], capture_output=True, text=True,
                              cwd=root, timeout=600)
    assert finished.returncode == 0, finished.stderr[-2000:]
    assert "ok" in finished.stdout
