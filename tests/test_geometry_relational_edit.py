"""The DSL criterion: acquired operations can be re-edited and generalized inside the same DSL."""
import json
from pathlib import Path

import pytest

from math_os_prototype import geometry_relational_edit as edit

ROOT = Path(__file__).resolve().parents[1]

PARA_PRODUCER = {"params": ["p0", "p1", "p2"],
                 "steps": [{"out": "s0", "prim": "mirror", "args": ["p1", "p0"]},
                           {"out": "s1", "prim": "midpoint", "args": ["s0", "p2"]}], "result": "s1"}
TRANSLATE = {"params": ["p0", "p1", "p2"],
             "steps": [{"out": "m", "prim": "midpoint", "args": ["p0", "p1"]},
                       {"out": "y", "prim": "mirror", "args": ["p2", "m"]}], "result": "y"}


def perpendicular_through(last):
    return {"params": ["p0", "p1", "p2"],
            "steps": [{"out": "s0", "prim": "foot", "args": ["p0", "p1", "p2"]},
                      {"out": "y", "prim": last, "args": ["s0", "p0"]}], "result": "y"}


def test_define_certifies_post_exactly_and_refuses_false_or_hidden_atoms():
    definition = edit.define(PARA_PRODUCER, [("para", ("p0", "v", "p1", "p2"))])
    assert definition["generation"] == 1 and definition["certificates"]
    with pytest.raises(edit.EditRefused):
        edit.define(PARA_PRODUCER, [("perp", ("p0", "v", "p1", "p2"))])
    with pytest.raises(edit.EditRefused):
        edit.define(PARA_PRODUCER, [("coll", ("s0", "v", "p2"))])


def test_vacuous_definition_is_refused():
    body = {"params": ["p0", "p1"], "steps": [{"out": "m", "prim": "midpoint", "args": ["p0", "p1"]},
                                               {"out": "o", "prim": "circle", "args": ["m", "p0", "p1"]}],
            "result": "o"}
    with pytest.raises(edit.EditRefused):
        edit.define(body, [("cong", ("v", "p0", "v", "p1"))])


def test_substitution_inside_a_body_is_accepted_only_when_the_post_recertifies():
    parent = edit.define(TRANSLATE, [("cong", ("p0", "p2", "p1", "v"))])
    same_point = {"params": ["q0", "q1"],
                  "steps": [{"out": "r0", "prim": "mirror", "args": ["q1", "q0"]},
                            {"out": "r1", "prim": "mirror", "args": ["q0", "q1"]},
                            {"out": "r2", "prim": "midpoint", "args": ["r0", "r1"]}], "result": "r2"}
    edited = edit.substitute(parent, "m", same_point)
    assert edited["generation"] == 2 and edited["parents"] == [parent["id"]]
    assert [s["prim"] for s in edited["body"]["steps"]] == ["mirror", "mirror", "midpoint", "mirror"]
    other_point = {"params": ["q0", "q1"], "steps": [{"out": "r", "prim": "mirror", "args": ["q0", "q1"]}],
                   "result": "r"}
    with pytest.raises(edit.EditRefused):
        edit.substitute(parent, "m", other_point)


def test_acquired_operation_is_material_for_later_definitions_and_edits():
    parent = edit.define(PARA_PRODUCER, [("para", ("p0", "v", "p1", "p2"))])
    table = {parent["id"]: parent}
    outer = {"params": ["a", "b", "c"],
             "steps": [{"out": "x", "call": parent["id"], "args": ["a", "b", "c"]},
                       {"out": "z", "prim": "midpoint", "args": ["x", "a"]}], "result": "z"}
    child = edit.define(outer, [("para", ("a", "v", "b", "c"))], table, parents=[parent["id"]])
    assert child["generation"] == 2
    unfolded = edit.unfold(outer, table)
    assert [s["prim"] for s in unfolded["steps"]] == ["mirror", "midpoint", "midpoint"]
    grandchild = edit.substitute(child, "z", {"params": ["q0", "q1"],
                                              "steps": [{"out": "r", "prim": "mirror", "args": ["q0", "q1"]}],
                                              "result": "r"}, table)
    assert grandchild["generation"] == 3
    flat = {"params": ["a", "b", "c", "d"],
            "steps": [{"out": "m1", "prim": "mirror", "args": ["b", "a"]},
                      {"out": "x", "prim": "midpoint", "args": ["m1", "c"]},
                      {"out": "z", "prim": "midpoint", "args": ["x", "d"]}], "result": "z"}
    folded = edit.fold(flat, parent, table)
    assert folded["steps"][0] == {"out": "x", "call": parent["id"], "args": ["a", "b", "c"]}


def test_operation_parameter_abstraction_and_instantiation_by_replay():
    first = edit.define(perpendicular_through("midpoint"), [("perp", ("p0", "v", "p1", "p2"))])
    second = edit.define(perpendicular_through("mirror"), [("perp", ("p0", "v", "p1", "p2"))])
    higher = edit.abstract_operation(first, second)
    (op,) = [p for p in higher["params"] if p["sort"] == "Op"]
    assert op["interface"] == [["coll", ["i0", "i1", "o"]]]
    for family in ("midpoint", "mirror"):
        assert edit.instantiate_operation(higher, {op["name"]: family})["generation"] == higher["generation"]+1
    with pytest.raises(edit.EditRefused):
        edit.instantiate_operation(higher, {op["name"]: "foot"})
    with pytest.raises(edit.EditRefused):
        edit.abstract_operation(first, first)


def test_relation_parameter_schema_applicability_by_certificate_replay():
    programs = [{"family": "intersection_ll", "specs": [("coll", ("v", "a", "b")), ("coll", ("v", "a", "b")),
                                                         ("cong", ("v", "c", "v", "d")), ("cong", ("v", "c", "v", "d"))]},
                {"family": "intersection_ll", "specs": [("coll", ("v", "a", "c")), ("coll", ("v", "a", "c")),
                                                         ("perp", ("b", "v", "c", "d")), ("perp", ("b", "v", "c", "d"))]}]
    schema = edit.abstract_relation(programs)
    names = [p["name"] for p in schema["params"]]
    assert {p["sort"] for p in schema["params"]} == {"Rel"} and len(names) == 2
    decided = edit.instantiate_relation_schema(schema, {names[0]: ("para", ("v", "a", "b", "c")),
                                                        names[1]: ("cong", ("v", "a", "v", "d"))})
    assert set(decided["certificates"]) == set(names)
    with pytest.raises(edit.EditRefused):
        edit.instantiate_relation_schema(schema, {names[0]: ("cyclic", ("v", "a", "b", "c")),
                                                  names[1]: ("coll", ("v", "a", "b"))})


def test_existing_archive_converts_and_recertifies():
    from math_os_prototype.theory_geometry_selection import read_inputs
    config = json.loads((ROOT/"configs/theory-geometry-failure-location.json").read_text())
    if not (ROOT/config["source_archive"]["path"]).exists():
        pytest.skip("frozen archive not present in this checkout")
    definitions, _, _ = read_inputs(config["source_archive"], ROOT)
    converted = [edit.convert_archive_definition(h) for h in definitions]
    assert len(converted) == 16
    assert all(len(d["certificates"]) == len(d["post"]) for d in converted)


def test_unfolding_cannot_capture_a_parameter_named_like_a_local():
    body = {"params": ["u1", "a", "b"],
            "steps": [{"out": "s0", "prim": "midpoint", "args": ["a", "b"]},
                      {"out": "s1", "prim": "midpoint", "args": ["u1", "a"]}], "result": "s1"}
    with pytest.raises(edit.EditRefused):
        edit.define(body, [("coll", ("v", "a", "b"))])
    with pytest.raises(edit.EditRefused):
        edit.define({"params": ["a", "b"], "steps": [{"out": "a", "prim": "midpoint", "args": ["a", "b"]}],
                     "result": "a"}, [])
