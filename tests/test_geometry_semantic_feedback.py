"""Development regressions; their supplied examples are not acquisition evidence."""
from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from math_os_prototype import geometry_contracts as gc
from math_os_prototype import geometry_semantic_dsl as dsl
from math_os_prototype import library_compression as lib
from math_os_prototype.theory_geometry_feedback import GeometryLibrary, SemanticGeometryDomain, acquire, reach_key


ROOT = Path(__file__).resolve().parents[1]
CONFIG = json.loads((ROOT/"configs/theory-geometry-semantic-feedback.json").read_text())


@pytest.fixture(scope="module")
def bank():
    return GeometryLibrary()


def domain(bank, task=None, **kw):
    return SemanticGeometryDomain(task or CONFIG["training"][0], CONFIG["search"], bank, **kw)


def apply(d, state, name, inputs):
    return d.apply(state, SimpleNamespace(family=name, inputs=inputs), (name, d.key(state), inputs))


@pytest.mark.parametrize("family", list(dsl.FRAGMENT.arities))
def test_all_historical_families_have_relational_certificates(bank, family):
    cert = bank.schemas[family]
    assert cert["exact_certificate"]["all_input_assignments_under_P"]
    assert cert["representation_scopes"] == dsl.FRAGMENT.scope
    assert all(all(v == "0" for v in s["existence_residuals"]) for s in cert["exact_certificate"]["steps"])


@pytest.mark.parametrize("name,args", [
    ("midpoint", ("a", "b")), ("mirror", ("a", "b")), ("foot", ("c", "a", "b")),
    ("circle", ("a", "b", "c")), ("orthocenter", ("a", "b", "c")),
    ("reflect", ("c", "a", "b")), ("intersection_ll", ("a", "c", "b", "d"))])
def test_seven_execute_and_independently_replay(bank, name, args):
    d = domain(bank)
    result = apply(d, d.initial(), name, args)
    assert result is not None
    assert d.histories[-1]["replay"]["passed"]
    assert result.value.predicates


def test_predicates_live_and_preconditions_consumed(bank):
    d = domain(bank)
    first = apply(d, d.initial(), "midpoint", ("a", "b")).value
    output = first.history[-1].outputs[-1]
    key = dsl.atom_key("diff", (output, "a"))
    assert key in first.predicates
    second = apply(d, first, "foot", ("c", output, "a")).value
    assert second.history[-1].provenance["used_predicates"][0]["already_in_state"]
    assert any(a.predicate == "perp" for a in second.predicates.values())


def test_degenerate_refused_and_parent_unchanged(bank):
    d = domain(bank)
    state = d.initial()
    before = state.record()
    assert apply(d, state, "foot", ("c", "a", "a")) is None
    assert before == state.record()
    assert not d.histories


def test_zero_direction_is_not_perp(bank):
    d = domain(bank)
    assert d.prove(d.initial(), "perp", ("a", "a", "a", "b"), "test") is None
    with pytest.raises(ValueError, match="unsupported"):
        d.prove(d.initial(), "invented", ("a", "b"), "test")


def test_cyclic_requires_circle_not_collinear():
    objects = {n: {"type": "Point", "coordinates": [str(i), "0"]} for i, n in enumerate("abcd")}
    assert dsl.certify_atom("cyclic", tuple("abcd"), objects, provenance="test") is None


def test_typing_and_numeric_acceptance_refused(bank):
    with pytest.raises(ValueError, match="exact rational"):
        domain(bank, {"points": {"a": [0.0, 0], "b": [1, 1]}})
    with pytest.raises(ValueError, match="Point objects"):
        dsl.certify_atom("diff", ("a", "b"), {"a": {"type": "Line"}, "b": {"type": "Point"}}, provenance="test")


def test_nested_calls_and_shared_arguments_are_not_flattened(bank):
    bank = deepcopy(bank)
    f0, f1 = lib.program_hole(0), lib.program_hole(1)
    template = {"op": "mirror", "args": [f0, {"op": "midpoint", "args": [f0, f1]}]}
    h = dsl.certify_definition(template, bank.archive)
    bank.register(h)
    g_template = {"op": "midpoint", "args": [lib.use_node(h["id"], template, {"f0": f0, "f1": f1}), f1]}
    g = dsl.certify_definition(g_template, bank.archive)
    assert g["parents"] == (h["id"],)
    assert g["generation"] == 2
    assert h["id"] in lib.calls_in(g["body"])
    assert not lib.calls_in(g["primitive_expansion"])
    assert len(g["parameters"]) == 2
    bank.register(g)
    assert dsl.replay_definition(g, bank.archive)
    stored = json.loads(json.dumps(g))
    assert dsl.replay_definition(stored, bank.archive)


def test_archive_tampering_and_free_points_rejected(bank):
    with pytest.raises(ValueError, match="source point"):
        dsl.definition_body({"op": "midpoint", "args": [lib.program_hole(0), gc.point("hand_supplied")]})
    template = {"op": "midpoint", "args": [lib.program_hole(0), lib.program_hole(1)]}
    h = dsl.certify_definition(template, [])
    h["exact_certificate"]["witness"]["local0"] = ["0", "0"]
    with pytest.raises(ValueError, match="mismatch"):
        deepcopy(bank).register(h)


def test_composed_local_proofs_keep_sequential_witness_and_guards():
    f0, f1, f2 = (lib.program_hole(i) for i in range(3))
    template = {"op": "foot", "args": [f2, f0,
                {"op": "midpoint", "args": [f0, f1]}]}
    h = dsl.certify_definition(template, [])
    cert = h["exact_certificate"]["exact_certificate"]
    assert cert["all_input_assignments_under_P"]
    assert h["exact_certificate"]["witness_mode"] == "sequential_local"
    assert any(g["parent_factors"] for g in h["applicability"]["sequential_nonzero_polynomials"])
    assert all(s["residual_scope"] == "current output with independent parent coordinate symbols"
               for s in cert["steps"])
    assert all(all(r == "0" for r in s["existence_residuals"]) for s in cert["steps"])
    # Each witness may refer only to original inputs and earlier bound outputs.
    import sympy as sp
    allowed = {n+axis for n in ("f0", "f1", "f2") for axis in ("x", "y")}
    for local in h["exact_certificate"]["local_auxiliary_variables"]:
        xy = h["exact_certificate"]["witness"][local["name"]]
        assert all({str(s) for s in sp.sympify(v).free_symbols} <= allowed for v in xy)
        allowed.update(local["coordinates"])
    assert dsl.replay_definition(h, [])


def test_recursive_cycle_and_unknown_calls_rejected():
    term = {"op": "use", "abstraction": "x", "arguments": {}}
    with pytest.raises(lib.ExpansionError):
        dsl.expand(term, lib.definition_table({"x": term}))
    with pytest.raises(lib.ExpansionError):
        dsl.expand(term, lib.definition_table({}))


def test_acquired_sequential_guard_refuses_degenerate_intermediate(bank):
    bank = deepcopy(bank)
    f = [lib.program_hole(i) for i in range(4)]
    template = {"op": "foot", "args": [f[0],
                {"op": "midpoint", "args": [f[1], f[2]]}, f[3]]}
    h = dsl.certify_definition(template, [])
    bank.register(h)
    d = domain(bank, {"points": {"a": [0, 2], "b": [0, 0], "c": [2, 0], "d": [1, 0]}}, active=[h["id"]])
    state = d.initial()
    before = state.record()
    assert apply(d, state, h["id"], ("a", "b", "c", "d")) is None
    assert state.record() == before
    assert not d.histories


def test_nested_three_point_constructions_use_local_proofs(bank):
    bank = deepcopy(bank)
    f = [lib.program_hole(i) for i in range(4)]
    h = dsl.certify_definition({"op": "orthocenter", "args": [
        {"op": "circle", "args": f[:3]}, f[0], f[3]]}, [])
    bank.register(h)
    d = domain(bank, active=[h["id"]])
    assert apply(d, d.initial(), h["id"], ("a", "b", "c", "d")) is not None
    assert d.histories[-1]["replay"]["passed"]
    assert d.costs["witness_evaluations"] == 2


def test_generated_call_survives_into_later_learning_input(bank):
    bank = deepcopy(bank)
    template = {"op": "midpoint", "args": [lib.program_hole(0),
                 {"op": "midpoint", "args": [lib.program_hole(1), lib.program_hole(2)]}]}
    h = dsl.certify_definition(template, [])
    bank.register(h)
    d = domain(bank, active=[h["id"]])
    first = apply(d, d.initial(), h["id"], ("a", "b", "c")).value
    result = apply(d, first, "mirror", (first.history[-1].outputs[-1], "d"))
    assert result is not None
    assert h["id"] in lib.calls_in(d.histories[-1]["program"])
    assert not lib.calls_in(d.histories[-1]["primitive_expansion"])
    small = dict(CONFIG["acquisition"], cycle=1, pairs=5)
    original = acquire(d.histories, deepcopy(bank), small)
    flat = acquire(d.histories, deepcopy(bank), small, flatten=True)
    assert any(lib.calls_in(c["program"]) for c in original["corpus"])
    assert not any(lib.calls_in(c["program"]) for c in flat["corpus"])


def test_search_frontier_continues_and_no_goal_hard_gate(bank):
    d = domain(bank)
    d.started -= 10000  # Waiting for another domain is not this search's work.
    d.search(12)
    before = set(d.attempted)
    d.search(12)
    assert before < d.attempted
    assert len(d.attempted) == d.costs["candidate_expansions"]
    assert set(dsl.FRAGMENT.arities) <= {a[0] for a in d.attempted}
    assert not d.solution
    assert d.search_seconds < d.config["wall_seconds"]


def test_reach_normalization_ignores_history_and_names(bank):
    d = domain(bank)
    state = apply(d, d.initial(), "midpoint", ("a", "b")).value
    changed = deepcopy(state)
    changed.history.clear()
    changed.terms.clear()
    changed.predicates.clear()
    changed.objects = {"rename"+str(i): o for i, o in enumerate(changed.objects.values())}
    assert reach_key(state) == reach_key(changed)


def test_solve_has_exact_goal_and_replay(bank):
    d = domain(bank, CONFIG["evaluation"][0], policy="SOLVE")
    result = d.search(30)
    assert result["solved"]
    assert result["solution"]["replay"]["passed"]
    assert len(result["solution"]["goals"]) == 2
