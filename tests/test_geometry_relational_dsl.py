"""Soundness and language tests for the relational geometry DSL."""
import pytest
import sympy as sp

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_relational_dsl as rdsl
from math_os_prototype import geometry_semantic_dsl as dsl
from math_os_prototype.geometry_relational_search import RelationalSynthesis, independent_replay

POINTS = {"a": [0, 1], "b": [8, 2], "c": [2, 8], "d": [7, 5]}


def coords(points):
    return {n: tuple(sp.Rational(v) for v in xy) for n, xy in points.items()}


def test_relation_terms_validate_rename_and_beta_reduce():
    term = rdsl.exists(["z"], rdsl.conj(rdsl.atom("coll", "x", "z", "y"), rdsl.rvar("R", "z")))
    rdsl.validate_relation(term, {"R": 1})
    with pytest.raises(ValueError):
        rdsl.validate_relation(term)
    assert rdsl.free_variables(term) == {"x", "y"}
    renamed = rdsl.rename_relation(term, {"x": "z"})
    assert rdsl.free_variables(renamed) == {"z", "y"}
    assert renamed["exists"] != ["z"]
    reduced = rdsl.instantiate_relation(term, {"R": {"lambda": ["p"], "body": rdsl.atom("cong", "p", "a", "p", "b")}})
    assert rdsl.free_variables(reduced) == {"x", "y", "a", "b"}
    with pytest.raises(ValueError):
        rdsl.instantiate_relation(term, {"R": {"lambda": ["p"], "body": rdsl.atom("coll", "p", "z", "a")}})


def test_symmetries_are_certified_not_assumed():
    assert len(rdsl.certified_symmetry_group("coll")) == 6
    assert len(rdsl.certified_symmetry_group("perp")) == 8
    assert (0, 2, 1) in rdsl.certified_symmetry_group("midp")
    assert (1, 0, 2) not in rdsl.certified_symmetry_group("midp")
    assert rdsl.canonical_atom("perp", ("b", "a", "d", "c")) == rdsl.canonical_atom("perp", ("c", "d", "a", "b"))


@pytest.mark.parametrize("predicate,args,expected", [
    ("coll", ("v", "a", "b"), True),
    ("perp", ("v", "a", "b", "c"), True),
    ("perp", ("a", "v", "b", "c"), True),
    ("para", ("v", "a", "b", "c"), True),
    ("cong", ("v", "a", "v", "b"), True),
    ("cong", ("v", "a", "b", "c"), False),
    ("midp", ("v", "a", "b"), False),
    ("perp", ("v", "a", "v", "b"), False),
])
def test_transfer_metarule_certifies_exactly_the_affine_loci(predicate, args, expected):
    (shape,) = rdsl.transfer_shapes()
    certificate = rdsl.certify_transfer(predicate, args, "v", shape)
    assert (certificate is not None) == expected
    if certificate:
        t = sp.Symbol("t")
        assert set(certificate["multipliers"]) == {"t + 1", "-t"}


def test_vacuous_composition_is_not_shown_nonvacuous_although_kernel_certifies_it():
    body = {"op": "circle", "args": [{"op": "midpoint", "args": [gc.point("f0"), gc.point("f1")]},
                                     gc.point("f0"), gc.point("f1")]}
    certificate, _ = gc.certify_body(body, fragment=dsl.FRAGMENT)
    assert certificate["exact_certificate"]["existence"] is True   # defect recorded at 10213b0
    program = {"steps": [{"out": "m", "prim": "midpoint", "args": ["f0", "f1"]},
                         {"out": "o", "prim": "circle", "args": ["m", "f0", "f1"]}], "result": ["o"]}
    assert rdsl.nonvacuity_witness(program, ["f0", "f1"]) is None
    program["steps"][1]["args"] = ["m", "f0", "f2"]
    assert rdsl.nonvacuity_witness(program, ["f0", "f1", "f2"]) is not None


def test_composition_keeps_open_obligations_and_refutes_repeated_arguments():
    program = {"steps": [{"out": "y", "prim": "foot", "args": ["p", "a", "a"]}], "result": ["y"]}
    assert rdsl.compose(program)["refuted"]
    program = {"steps": [{"out": "y", "prim": "foot", "args": ["p", "a", "b"]}], "result": ["y"]}
    open_result = rdsl.compose(program)
    assert any(o["status"] == "open" and o["condition"].get("atom") == "diff" for o in open_result["obligations"])
    closed = rdsl.compose(program, pre=[rdsl.atom("diff", "b", "a")])
    assert any(o["status"] == "discharged" for o in closed["obligations"])
    assert all(o["status"] == "open" for o in closed["obligations"] if "nonzero" in o["condition"])


def test_identity_bindings_are_excluded_exactly():
    assert rdsl.binding_returns_input("foot", ["b", "b", "d"])
    assert rdsl.binding_returns_input("intersection_ll", ["a", "b", "a", "c"])
    assert not rdsl.binding_returns_input("midpoint", ["a", "b"])
    assert rdsl.family_symmetry_group("midpoint") == ((0, 1), (1, 0))


def test_execution_refuses_degenerate_primitives():
    xy, reason = rdsl.execute_primitive("foot", ["a", "b", "b"], coords(POINTS))
    assert xy is None and reason.startswith("unproved_applicability")
    xy, reason = rdsl.execute_primitive("intersection_ll", ["a", "b", "c", "d"], coords(POINTS))
    assert reason is None and xy == (sp.Rational(328, 29), sp.Rational(70, 29))


def solve(goals, points=POINTS, **kwargs):
    task = {"points": points, "goals": [{"predicate": p, "points": list(a)} for p, a in goals]}
    return RelationalSynthesis(task, {"max_plan_expansions": 2000, "wall_seconds": 120}, **kwargs).search(112)


def test_synthesis_solves_line_and_bisector_by_certified_transfer_and_replays():
    row = solve([("coll", "uab"), ("cong", "ucud")])
    assert row["solved"] and row["solution"]["replay"]["passed"]
    xy, _ = independent_replay(row["solution"]["term"], coords(POINTS))
    local = dict(coords(POINTS), u=xy)
    assert rdsl.atom_holds("coll", ("u", "a", "b"), local) and rdsl.atom_holds("cong", ("u", "c", "u", "d"), local)
    assert not solve([("coll", "uab"), ("cong", "ucud")], transfer=False)["solved"]


def test_input_points_and_unsatisfiable_goals_are_never_accepted():
    row = solve([("coll", "uab"), ("cong", "uaua")])
    assert not row["solved"] or row["solution"]["point"] not in POINTS
    row = solve([("midp", "uab"), ("midp", "uac")])
    assert not row["solved"]


def test_library_program_with_an_unused_input_leaves_no_unreachable_hole():
    program = {"params": ["p0", "p1", "p2"], "steps": [{"out": "s0", "prim": "midpoint", "args": ["p0", "p1"]}],
               "result": "s0"}
    task = {"points": POINTS, "goals": [{"predicate": "midp", "points": ["u", "a", "b"]}]}
    synthesis = RelationalSynthesis(task, {"wall_seconds": 60})
    plan = synthesis._insert_program(synthesis._root_plan(), 0, program, {"p0": "a", "p1": "b"})
    assert synthesis._holes(plan[0]) == []
    synthesis._execute(plan, 112)
    assert synthesis.solution is not None and synthesis.costs["applications"] == 1
