"""Development guards, not autonomous acquisition evidence."""
import pytest

from math_os_prototype.runtime_typed_planner import PrimitiveResult
from math_os_prototype.theory_action_domain import search_action_domain


class CounterDomain:
    sort = "IntegerState"
    families = ("successors",)
    def __init__(self):
        self.expanded = []
    def initial(self): return 0
    def key(self, value): return str(value)
    def is_goal(self, value): return value == 3
    def alternatives(self, family, state):
        self.expanded.append(state)
        for delta in (0, 1):
            yield lambda delta=delta: PrimitiveResult(state+delta, {"parent": state, "delta": delta})


def test_successor_enumeration_reads_new_states():
    domain = CounterDomain()
    plan = search_action_domain(domain, max_depth=4, max_states=20)
    assert plan.complete and domain.expanded == [0, 1, 2]
    assert [s["parent"] for s in plan.proof_program] == [0, 1, 2]


def test_application_budget_counts_duplicates():
    domain = CounterDomain()
    plan = search_action_domain(domain, max_depth=4, max_states=3)
    assert not plan.complete and plan.states_explored == 3


def test_geometry_rejects_injected_auxiliary():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    with pytest.raises(ValueError, match="auxiliary"):
        GeometryDomain({"statement": "a b c = triangle a b c | m = midpoint m a b ? coll a m b"}, {})


def test_geometry_rejects_empty_goal():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    with pytest.raises(ValueError, match="goal"):
        GeometryDomain({"statement": "a b c = triangle a b c"}, {})


def test_false_statement_cannot_get_exact_certificate():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    domain = GeometryDomain({"statement": "a b c = triangle a b c ? perp a b b c"}, {})
    assert not domain.certify(str(domain.formulation))["accepted"]


def test_names_are_normalized_without_goal_information():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    first = GeometryDomain({"statement": "a b c = triangle a b c ? perp a b b c"}, {})
    second = GeometryDomain({"statement": "z y x = triangle z y x ? perp z y y x"}, {})
    assert str(first.formulation) == str(second.formulation)


def test_existing_construction_updates_real_next_inputs_and_replays():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    task = {"statement": "a b c = triangle a b c; h = on_tline h b a c, on_tline h c a b ? perp a h b c"}
    config = {"seed": 17, "closure_steps": 1000, "per_family_limit": 8}
    domain = GeometryDomain(task, config)
    root = domain.initial()
    candidate = domain.candidates("midpoint", root)[0]
    child = domain.apply(root, candidate).value
    output = child["path"][-1]["output"]
    assert len(child["problem"]["points"]) == len(root["problem"]["points"])+1
    assert any(output in c.inputs for c in domain.candidates("foot", child))
    assert domain.key(root) != domain.key(child)
    assert domain.replay(child)["passed"]
    assert any(e["event"] == "enumerate" and e["state_key"] == domain.key(child) for e in domain.events)


def test_similarity_does_not_change_initial_theorem():
    pytest.importorskip("newclid")
    from math_os_prototype.theory_geometry import GeometryDomain
    task = {"statement": "a b c = triangle a b c; h = on_tline h b a c, on_tline h c a b ? perp a h b c"}
    config = {"seed": 17, "closure_steps": 1000, "per_family_limit": 8}
    first = GeometryDomain(task, config).initial()
    other = GeometryDomain(task, dict(config, diagram_similarity=[3, 4, -2])).initial()
    assert first["certified"] and other["certified"]
    assert first["certificates"] == other["certificates"]
    assert first["problem"]["points"] != other["problem"]["points"]
