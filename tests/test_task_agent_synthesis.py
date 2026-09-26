"""The automaton learner on a world small enough to check by hand."""
import random

from experiments.task_agent import checkpoint
from experiments.task_agent.synthesis import (GoalSet, LearnedAutomaton, TrueTask, _Partition,
                                              counterexample_loop, disagreement, execute,
                                              labelled_prefixes, material, rpni, sample)

# a line of ten cells; action 0 steps left, action 1 steps right, both clamp at the ends
STATES = [(i,) for i in range(10)]
EDGES = [[max(0, i-1), min(9, i+1)] for i in range(10)]
SEQ = {"op": "SEQ", "goals": [{"kind": "exact", "state": [7]}, {"kind": "exact", "state": [2]},
                              {"kind": "exact", "state": [9]}]}


def line_task(spec=SEQ):
    return TrueTask(STATES, EDGES, checkpoint.TaskAutomaton(spec), 2)


def classifies(hypothesis, labels):
    for prefix, value in labels.items():
        m = hypothesis.initial_memory(prefix[0])
        for s in prefix[1:]:
            m = hypothesis.update(m, s)
        if hypothesis.done(m) != value:
            return False
    return True


def test_true_task_distances_and_labels():
    task = line_task()
    # from 0: right to 7 (7 steps), left to 2 (5), right to 9 (7)
    assert task.optimal_steps(0) == 19
    trace, accepted = task.demonstration(0, random.Random(0))
    assert accepted and len(trace)-1 == 19 and trace[-1] == 9
    # walking straight to 9 passes 2 before 7: not accomplished
    assert task.label(list(range(10))) == (list(range(10)), False)


def test_rpni_is_consistent_with_its_sample():
    task = line_task()
    rows = material(task, [0, 1, 3, 5, 8, 4], "line")
    for negatives in ("none", "random", "near_miss"):
        labels = labelled_prefixes(sample(rows, 6, negatives))
        assert classifies(rpni(labels), labels), negatives


def test_a_failed_merge_leaves_the_partition_unchanged():
    # nodes: 0 root(False) -a-> 1(False) -b-> 2(True); 0 -b-> 3(False)
    h = _Partition([{"a": 1, "b": 3}, {"b": 2}, {}, {}], [False, False, True, False])
    before = (list(h.parent), [dict(c) for c in h.children], list(h.label))
    assert not h.merge(0, 1)                   # would put node 2 (True) with node 3 (False)
    assert (h.parent, h.children, h.label) == before


def test_goal_set_misses_the_order_and_the_counterexample_loop_recovers_it():
    task = line_task()
    rows = material(task, [0], "line")
    goal = GoalSet(sample(rows, 1, "none"))
    assert goal.goals == {9}
    assert execute(task, goal, 0)[0] is False
    hypothesis, rounds, traces = counterexample_loop(task, sample(rows, 1, "random"), 0)
    assert rounds is not None
    accomplished, steps, _ = execute(task, hypothesis, 0)
    assert accomplished and steps == 19
    assert classifies(hypothesis, labelled_prefixes(traces))


def test_equivalence_on_the_world_is_detected():
    task = line_task()
    truth_as_learned = LearnedAutomaton({(0, 7): 1, (1, 2): 2, (2, 9): 3}, {3}, 0, 4)
    assert not disagreement(task, truth_as_learned, range(10))
    order_lost = LearnedAutomaton({(0, 9): 1}, {1}, 0, 2)
    assert disagreement(task, order_lost, [0])
