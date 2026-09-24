from __future__ import annotations

from collections import Counter, defaultdict
import itertools

import pytest

from future_refinement_core import (
    FutureRefinementCore,
    Relation,
    UNKNOWN,
    certified_congruence_quotient,
    pair_relation_on_empirical_model,
)
from exact_moore_oracle import MooreMachine, partition_refinement


def _same_partition(block_ids, oracle_blocks, n):
    oracle_id = {}
    for i, block in enumerate(oracle_blocks):
        for s in block:
            oracle_id[s] = i
    for s in range(n):
        for t in range(n):
            if (block_ids[s] == block_ids[t]) != (oracle_id[s] == oracle_id[t]):
                return False
    return True


def test_unbounded_history_can_select_depth_beyond_six():
    core = FutureRefinementCore(actions=("advance", "choose"))

    # The only distinguishing observation is eight actions in the past.
    for cue, outcome in (("cue0", "good"), ("cue1", "bad")):
        core.begin(cue)
        for _ in range(8):
            core.observe("advance", "same")
        core.observe("choose", outcome)

    summary = core.summary()
    assert summary["has_fixed_history_cap"] is False
    assert summary["max_selected_history_depth"] >= 8
    assert any(e.action == "choose" and e.depth >= 8 for e in core.split_events)


def test_multistep_counterexample_propagates_backward():
    core = FutureRefinementCore(actions=("enter", "a", "b"))

    # Immediate transition x --a--> m looks identical.
    # Only one further action b reveals y vs z.
    for cue, outcome in (("cue0", "y"), ("cue1", "z")):
        core.begin(cue)
        core.observe("enter", "x")
        core.observe("a", "m")
        core.observe("b", outcome)

    actions = [e.action for e in core.split_events]

    # First the downstream m-state must split on b, then that changed successor
    # structure must create a counterexample one step upstream at x on a.
    assert "b" in actions
    assert "a" in actions
    assert actions.index("b") < actions.index("a")


def test_identical_observable_history_with_two_successors_is_not_forced_split():
    core = FutureRefinementCore(actions=("a",))

    core.begin("x")
    core.observe("a", "y")

    core.begin("x")
    core.observe("a", "z")

    summary = core.summary()
    assert summary["unresolved_counterexamples"]
    assert "identical observable history" in summary["unresolved_counterexamples"][0]["reason"]


def test_missing_action_rows_are_unknown_and_do_not_merge():
    labels = ["x", "x", "y"]
    actions = (0, 1)
    counts = defaultdict(Counter)

    # States 0 and 1 look identical on observed action 0, but action 1 was never
    # tried.  They must remain separate.
    counts[0, 0][2] += 1
    counts[1, 0][2] += 1
    counts[2, 0][2] += 1
    counts[2, 1][2] += 1

    q = certified_congruence_quotient(labels, actions, counts)
    assert q["blocks"][0] != q["blocks"][1]

    rel = pair_relation_on_empirical_model(labels, actions, counts, 0, 1)
    assert rel.relation == Relation.UNKNOWN


def test_fully_observed_equivalent_states_merge_exactly():
    labels = ["x", "x", "y"]
    actions = (0, 1)
    counts = defaultdict(Counter)

    for s in (0, 1):
        counts[s, 0][s] += 1
        counts[s, 1][2] += 1
    counts[2, 0][2] += 1
    counts[2, 1][2] += 1

    q = certified_congruence_quotient(labels, actions, counts)
    assert q["blocks"][0] == q["blocks"][1]
    assert q["blocks"][0] != q["blocks"][2]
    assert q["eps_action"] == 0.0

    rel = pair_relation_on_empirical_model(labels, actions, counts, 0, 1)
    assert rel.relation == Relation.EQUIVALENT


def test_observed_distinguishing_word_returns_different():
    labels = ["x", "x", "m", "m", "y", "z"]
    actions = ("a",)
    counts = defaultdict(Counter)
    counts[0, "a"][2] += 1
    counts[1, "a"][3] += 1
    counts[2, "a"][4] += 1
    counts[3, "a"][5] += 1
    counts[4, "a"][4] += 1
    counts[5, "a"][5] += 1

    rel = pair_relation_on_empirical_model(labels, actions, counts, 0, 1)
    assert rel.relation == Relation.DIFFERENT
    assert rel.distinguishing_word == ("a", "a")


def test_core_has_no_goal_reward_q_discount_or_fixed_max_depth():
    core = FutureRefinementCore(actions=(0, 1))
    attrs = set(vars(core))
    assert "goal" not in attrs
    assert "reward" not in attrs
    assert "q" not in attrs
    assert "discount" not in attrs
    assert "max_depth" not in attrs
    assert "max_history_depth" not in attrs


def test_complete_deterministic_quotient_matches_exact_oracle_for_all_5832_small_machines():
    """
    Exhaustive validation on all:
        3 states, 2 actions, 2 outputs
    labelled deterministic Moore machines.

    2^3 * 3^(3*2) = 5832.
    """
    states = (0, 1, 2)
    actions = (0, 1)
    checked = 0

    for outputs in itertools.product((0, 1), repeat=3):
        labels = list(outputs)
        O = dict(zip(states, outputs))

        for dests in itertools.product(states, repeat=6):
            T = {}
            counts = defaultdict(Counter)
            k = 0
            for s in states:
                for a in actions:
                    d = dests[k]
                    k += 1
                    T[s, a] = d
                    counts[s, a][d] += 1

            machine = MooreMachine(states, actions, O, T)
            oracle = partition_refinement(machine)
            learned = certified_congruence_quotient(labels, actions, counts)

            assert _same_partition(learned["blocks"], oracle, 3)
            assert learned["eps_action"] == 0.0
            checked += 1

    assert checked == 5832


def test_recursive_belief_equals_full_history_reconstruction():
    core = FutureRefinementCore(actions=(0, 1))

    # Build a tiny learned model with both observations and a missing row.
    core.begin("A")
    core.observe(0, "B")
    core.observe(1, "A")

    core.begin("A")
    core.observe(1, "A")

    observations = ["A", "B", "A"]
    actions = [0, 1]

    belief = core.begin_belief(observations[0])
    for a, o in zip(actions, observations[1:]):
        belief = core.update_belief(belief, a, o)

    assert belief == core.reconstruct_belief(observations, actions)


def test_missing_transition_propagates_explicit_unknown():
    core = FutureRefinementCore(actions=(0, 1))
    core.begin("A")
    core.observe(0, "B")

    belief = core.begin_belief("A")
    updated = core.update_belief(belief, 1, "A")

    assert UNKNOWN in updated


def test_shortest_unresolved_experiment_is_not_a_scored_heuristic():
    labels = ["x", "x", "y"]
    actions = (0, 1)
    counts = defaultdict(Counter)
    counts[0, 0][2] += 1
    counts[1, 0][2] += 1
    counts[2, 0][2] += 1
    counts[2, 1][2] += 1

    # Build a core object only to exercise the exact BFS experiment selector.
    core = FutureRefinementCore(actions)
    core.leaf_keys = [("s", 0), ("s", 1), ("s", 2)]
    core.mapping = [0, 1, 2]
    core.nodes = []
    from future_refinement_core import HistoryNode
    core.nodes = [
        HistoryNode(None, None, "x", 0),
        HistoryNode(None, None, "x", 0),
        HistoryNode(None, None, "y", 0),
    ]
    core.leaf_counts = counts
    core.model = certified_congruence_quotient(labels, actions, counts)

    assert core.shortest_unresolved_experiment(0, 1) == (1,)
