from types import SimpleNamespace

from experiments.continual_tools.core import ProgramLibrary, SAME, DIFFERENT, UNRESOLVED
from experiments.noisy_rgb_predictive_signature.adapter import PredictiveGraphAdapter


def belief(*candidates, resolved=None, new=True):
    return SimpleNamespace(candidates=tuple(candidates), resolved_state=resolved,
                           new_state_possible=new)


def test_nested_program_reuse_preserves_exact_primitive_trace():
    lib = ProgramLibrary(4)
    first = lib.register([0, 1, 2], guard=0, expected_states=[1, 2, 3], source="ep1")
    second = lib.register([0, 1, 2, 3], guard=0, expected_states=[1, 2, 3, 0], source="ep2")
    assert lib.flatten_token(first) == (0, 1, 2)
    assert lib.flatten_token(second) == (0, 1, 2, 3)
    assert first in lib.definitions[second]


def test_unresolved_tool_observation_is_not_a_counterexample():
    lib = ProgramLibrary(2)
    token = lib.register([0, 1], guard=0, expected_states=[1, 2], source="ep1")
    running = lib.begin(token, belief(0, resolved=0, new=False))
    assert running.next_action() == 0
    result = running.observe(belief(1, 7, resolved=None, new=True))
    assert result.status == UNRESOLVED
    assert lib.records[token]["status"] == "candidate"
    assert not any(e["event"] == "tool_counterexample" for e in lib.events)


def test_confirmed_different_revokes_but_keeps_program_code():
    lib = ProgramLibrary(2)
    token = lib.register([0], guard=0, expected_states=[1], source="ep1")
    running = lib.begin(token, belief(0, resolved=0, new=False))
    result = running.observe(belief(2, resolved=2, new=False))
    assert result.status == DIFFERENT
    assert lib.records[token]["status"] == "refuted"
    assert lib.flatten_token(token) == (0,)
    assert any(e["event"] == "tool_counterexample" for e in lib.events)


def test_quotient_law_is_scoped_and_does_not_rewrite_primitive_trace():
    # action 0 maps every state to 0, so the learned one-action tool is idempotent
    # on this complete finite quotient.
    model = {
        "reps": [(), (1,)],
        "trans": {(0, 0): 0, (1, 0): 0},
    }
    graph = PredictiveGraphAdapter(model, 1)
    lib = ProgramLibrary(1)
    token = lib.register([0], guard=0, expected_states=[0], source="ep1")
    relations = lib.discover_quotient_relations(graph)
    assert any(r["kind"] == "idempotent" and r["status"] == SAME for r in relations)
    assert all(r["scope"] == "current_complete_predictive_quotient" for r in relations)
    assert lib.flatten_token(token) == (0,)
