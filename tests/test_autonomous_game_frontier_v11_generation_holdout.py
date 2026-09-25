import copy
import inspect

import pytest

from experiments.game_frontier_v11_generation_holdout import audit


def test_protocol_frozen_and_distinct_from_prior():
    assert audit.CONFIG["checkpoints"] == audit.previous.CONFIG["checkpoints"]
    assert audit.CONFIG["horizon"] == audit.previous.CONFIG["horizon"]
    assert audit.TASK_SEED_ROOT != audit.previous.TASK_SEED_ROOT
    assert audit.CONFIG["q"] == .90 and audit.CONFIG["cutoff"] == 1e-7
    assert len(audit.previous.verified_sources()) == 18


def test_retained_generations_share_case():
    a = {"game_hash": "a", "tasks": [1]}
    b = {"game_hash": "b", "tasks": [2]}
    groups = audit.group_frontier([copy.deepcopy(a) for _ in range(4)] + [copy.deepcopy(b) for _ in range(7)])
    assert groups["a"]["generations"] == [0, 1, 2, 3]
    assert groups["b"]["generations"] == list(range(4, 11))
    conflicting = [copy.deepcopy(a) for _ in range(11)]
    conflicting[4]["tasks"] = [3]
    with pytest.raises(AssertionError, match="conflicting"):
        audit.group_frontier(conflicting)


def test_rational_direction_no_rounding_tolerance():
    assert audit.sign_delta("1/3", "2/6") == "tie"
    assert audit.sign_delta("10/3", "11/3") == "increase"
    assert audit.sign_delta("10/3", "9/3") == "decrease"
    assert audit.sign_delta(None, "10/3") == "unmeasured"


@pytest.mark.parametrize("learned,full,expected", [
    (.8, .8, "LEARNED_SUCCESS"), (.79, .8, "EXPLORATION_LIMITED"),
    (.9, .79, "REASONER_LIMITED"), (.7, .7, "REASONER_LIMITED"),
    (None, None, "NO_UNUSED_TASKS")])
def test_classification(learned, full, expected):
    assert audit.classification(learned, full) == expected


def evaluation(bits):
    return {"task_results": [{"success": b, "actual_actions": 4} for b in bits]}


def test_task_matched_capacity_decomposition():
    full = evaluation([True, False, True, False])
    learned = evaluation([True, True, False, False])
    assert audit.contingency(learned, full) == {
        "both_success": 1, "learned_failure_full_success": 1,
        "learned_success_full_failure": 1, "both_failure": 1}
    paired = [{"budget": 1, "holdout": evaluation([False] * 4)},
              {"budget": 2, "holdout": learned},
              {"budget": 4, "holdout": evaluation([True, False, True, False])}]
    total = audit.curve(paired, "holdout")
    yes = audit.curve(paired, "holdout", [0, 2])
    no = audit.curve(paired, "holdout", [1, 3])
    assert total["D"] == (yes["D"] + no["D"]) / 2
    assert total["B50"] == 2 and total["B80"] is None
    assert yes["B80"] == 4
    assert audit.curve(paired, "holdout", []) is None


def test_prior_holdout_and_selection_both_excluded():
    states = [(i,) for i in range(7)]
    graph = states, [[min(i + 1, 6)] for i in range(7)], {s: i for i, s in enumerate(states)}
    tasks, _ = audit.previous.sample_holdout(graph, set(), 500, 17)
    blocked = set(map(audit.previous.pair, tasks[:2])) | set(map(audit.previous.pair, tasks[2:4]))
    fresh, pop = audit.previous.sample_holdout(graph, blocked, 500, audit.TASK_SEED_ROOT)
    assert len(fresh) == 2 and pop["exhaustive"]
    assert not blocked & set(map(audit.previous.pair, fresh))


def test_no_mutation_generation_selection_or_player_implementation():
    source = inspect.getsource(audit)
    for forbidden in ("generate(", "mutate(", "choose(", "class StructuralLearner", "def solve_fixed_field", "def run_fixed_field_policy"):
        assert forbidden not in source
    assert "previous.paired_learning(b, emit)" in source
