"""The port, the optimal field, and the equivalences the speed-ups rely on.

Every claim the checkpoint, online and noisy runs make rests on one of these:
that the port reproduces the registered run, that the linear field is not a
shortest-path field (a four-state world shows it), that the optimal field on
the same product graph is, and that the sparse planner, the cached planner and
the one-search policy decide exactly what the delivered code decides.
"""
import copy
import csv
from functools import lru_cache

import pytest

from experiments.game_frontier_v11.world import game_hash
from experiments.task_agent import ExactState, ProductPlanner, SequenceTask, TaskConditionedPolicy
from experiments.task_agent import checkpoint, noisy, online_eval


@lru_cache(maxsize=None)
def trained(seed):
    parent, engine = checkpoint.load_world(None, seed)
    snapshots = checkpoint.train_snapshots(engine)
    tasks = checkpoint.generate_basic_tasks(snapshots[8192], 120000+seed)
    tasks += checkpoint.generate_branch_tasks(snapshots[8192], 220000+seed)
    return parent, engine, snapshots, tasks


def registered(name):
    with open(checkpoint.REGISTERED/name, encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


# ---------------------------------------------------------------------------
# The port reproduces the registered run
# ---------------------------------------------------------------------------

def test_the_committed_worlds_are_the_registered_ones():
    rows = {int(r["seed"]): r for r in registered("task_agent_worlds.csv")}
    for seed in checkpoint.SEEDS:
        parent, engine = checkpoint.load_world(None, seed)
        assert game_hash(parent["genome"]) == parent["game_hash"] == rows[seed]["game_hash"]


@pytest.mark.parametrize("seed", [2303, 2808])
def test_the_canonical_learner_learns_exactly_the_registered_number_of_states(seed):
    _, _, snapshots, _ = trained(seed)
    row = {int(r["seed"]): r for r in registered("task_agent_worlds.csv")}[seed]
    for budget in checkpoint.BUDGETS:
        assert len(snapshots[budget].i2s) == int(row[f"learned_states_{budget}"])


def test_one_world_reproduces_every_registered_row():
    records, specs, worlds, _, _ = checkpoint.run(
        None, seeds=(2303,), methods=("static_source", "dynamic_source", "product_compiler"),
        log=lambda *_: None)
    comparison = checkpoint.compare(checkpoint.REGISTERED, records, specs, worlds)
    assert comparison["worlds"]["differences"] == []
    assert comparison["task_specs"]["difference_count"] == 0
    assert comparison["results"]["compared"] == 46*4*3
    assert comparison["results"]["difference_count"] == 0


# ---------------------------------------------------------------------------
# The linear field is not a shortest-path field
# ---------------------------------------------------------------------------

WORLD = {("s",): {0: ("a",), 1: ("b",)},
         ("a",): {0: ("g",), 1: ("x1",), 2: ("x2",), 3: ("x3",)},
         ("b",): {0: ("c",)}, ("c",): {0: ("g",)}, ("g",): {0: ("g",)},
         ("x1",): {0: ("x1",)}, ("x2",): {0: ("x2",)}, ("x3",): {0: ("x3",)}}


def four_state_learner():
    learner = checkpoint.Learner(4)
    for state in WORLD:
        learner.add(state)
    for state, row in WORLD.items():
        for action, nxt in row.items():
            learner.rec(learner.s2i[state], action, learner.s2i[nxt])
    return learner


class FourStateEngine:
    num_actions = 4

    def step(self, state, action):
        return WORLD[state].get(action, state)


def test_the_delivered_planner_takes_the_three_step_route_when_two_steps_exist():
    """a is one step from g but three of its four actions lead nowhere; b is two clean steps."""
    learner = four_state_learner()
    task = SequenceTask([ExactState(("g",))])
    action = ProductPlanner().choose_action(learner.core, task, ("s",), task.initial_memory)
    assert action == 1                                   # towards b: psi(b) = 8.1 > psi(a) = 2.25


def test_the_optimal_field_on_the_same_graph_takes_the_two_step_route():
    learner = four_state_learner()
    automaton = checkpoint.TaskAutomaton({"op": "SEQ", "goals": [{"kind": "exact", "state": ["g"]}]})
    linear = checkpoint.execute_product_policy(learner, FourStateEngine(), automaton, ("s",),
                                               value="linear")
    optimal = checkpoint.execute_product_policy(learner, FourStateEngine(), automaton, ("s",),
                                                value="optimal")
    assert linear[:2] == (True, 3)
    assert optimal[:2] == (True, 2)
    assert checkpoint.product_shortest_path(learner, automaton, ("s",)) == 2


def test_on_an_archived_world_the_optimal_field_is_always_a_shortest_path():
    _, engine, snapshots, tasks = trained(2303)
    learner = snapshots[8192]
    for task_type, start, spec in tasks:
        automaton = checkpoint.TaskAutomaton(spec)
        success, steps, _ = checkpoint.execute_product_policy(learner, engine, automaton, start,
                                                              value="optimal")
        assert success and steps == checkpoint.product_shortest_path(learner, automaton, start)


# ---------------------------------------------------------------------------
# The speed-ups decide what the delivered code decides
# ---------------------------------------------------------------------------

def test_the_sparse_planner_builds_the_same_model_and_picks_the_same_action():
    _, _, snapshots, tasks = trained(2303)
    for budget in (512, 8192):
        core = snapshots[budget].core
        for task_id in (0, 1, 2, 36):
            _, start, spec = tasks[task_id]
            if tuple(start) not in core.state_to_id:
                continue
            task = online_eval.task_from_spec(spec)
            verdict = online_eval.planners_agree(core, task, tuple(start), task.initial_memory)
            assert verdict["same_graph"] and verdict["same_reachability"]
            assert verdict["same_field"] and verdict["same_action"]


def test_the_one_search_policy_makes_the_delivered_policys_decisions():
    parent, engine, snapshots, tasks = trained(2303)
    _, start, spec = tasks[1]
    task = online_eval.task_from_spec(spec)
    learner = copy.deepcopy(snapshots[512].core)
    delivered = TaskConditionedPolicy(online_eval.SparseProductPlanner())
    fast = online_eval.FastTaskConditionedPolicy(online_eval.CachingSparsePlanner())
    env = online_eval.WorldEnv(engine)
    state = env.reset(tuple(start))
    memory = task.advance(task.initial_memory, state)
    learner.get_or_add_id(state)
    for _ in range(80):
        one = delivered.choose(learner, state, task, memory)
        two = fast.choose(learner, state, task, memory)
        assert (one.action, one.target_frontier, one.reason) == \
            (two.action, two.target_frontier, two.reason)
        u = learner.get_or_add_id(state)
        nxt = env.step(one.action)
        learner.record_transition(u, one.action, learner.get_or_add_id(nxt))
        state = nxt
        memory = task.advance(memory, state)


@pytest.mark.parametrize("threshold", [1, 0])
def test_the_one_search_policy_agrees_where_exploration_actually_happens(threshold):
    """World 2505, task 3: no accepting path at 512, so the policy is really consulted."""
    parent, engine, snapshots, tasks = trained(2505)
    _, start, spec = tasks[3]
    task = online_eval.task_from_spec(spec)
    assert checkpoint.product_shortest_path(snapshots[512], checkpoint.TaskAutomaton(spec),
                                            start) is None
    learner = copy.deepcopy(snapshots[512].core)
    delivered = TaskConditionedPolicy(online_eval.SparseProductPlanner(),
                                      low_count_threshold=threshold)
    fast = online_eval.FastTaskConditionedPolicy(online_eval.CachingSparsePlanner(),
                                                 low_count_threshold=threshold)
    env = online_eval.WorldEnv(engine)
    state = env.reset(tuple(start))
    memory = task.advance(task.initial_memory, state)
    learner.get_or_add_id(state)
    for _ in range(80):
        one = delivered.choose(learner, state, task, memory)
        two = fast.choose(learner, state, task, memory)
        assert (one.action, one.target_frontier, one.reason) == \
            (two.action, two.target_frontier, two.reason)
        u = learner.get_or_add_id(state)
        nxt = env.step(one.action)
        learner.record_transition(u, one.action, learner.get_or_add_id(nxt))
        state = nxt
        memory = task.advance(memory, state)


def test_the_optimal_method_no_longer_solves_for_psi_and_still_agrees():
    _, engine, snapshots, tasks = trained(2303)
    learner = snapshots[8192]
    _, start, spec = tasks[0]
    automaton = checkpoint.TaskAutomaton(spec)
    assert checkpoint.build_product_model(learner, automaton, start, solve=False)["psi"] is None
    with_psi = checkpoint.build_product_model(learner, automaton, start)
    without = checkpoint.build_product_model(learner, automaton, start, solve=False)
    assert (checkpoint.optimal_field(with_psi) == checkpoint.optimal_field(without)).all()


# ---------------------------------------------------------------------------
# Exact evaluation under slip
# ---------------------------------------------------------------------------

def test_exact_evaluation_matches_the_geometric_law():
    """Two states; action 0 reaches g, action 1 stays. Each step succeeds with p = 1 - e/2."""
    from experiments.task_agent import exact_slip

    states = [("s",), ("g",)]
    edges = [[1, 0], [1, 1]]
    automaton = checkpoint.TaskAutomaton({"op": "SEQ", "goals": [{"kind": "exact", "state": ["g"]}]})
    index, order = exact_slip.true_product(states, edges, automaton, ("s",), 2)
    actions = [0 if not automaton.done(m) else -1 for (_, m) in order]
    for slip in (0.0, 0.1, 0.5):
        p = 1-slip/2
        horizon = 40
        expected = sum(t*p*(1-p)**(t-1) for t in range(1, horizon+1))+horizon*(1-p)**horizon
        got = exact_slip.evaluate(order, index, edges, automaton, states, actions, slip, 2,
                                  horizon=horizon)
        assert got["p_success"] == pytest.approx(1-(1-p)**horizon, abs=1e-12)
        assert got["expected_cost"] == pytest.approx(expected, abs=1e-9)
        ssp = exact_slip.ssp_policy(order, index, edges, automaton, states, slip, 2)
        assert ssp[0] == 0


def test_exact_evaluation_at_slip_zero_reproduces_the_checkpoint():
    from experiments.task_agent import exact_slip

    parent, engine, snapshots, tasks = trained(2303)
    states, edges, ids = exact_slip.true_graph(engine, [t[1] for t in tasks])
    learner = noisy.train(noisy.SlipEngine(parent["genome"], 0.0, "train:2303:0.0"), 8192)
    for task_id, (task_type, start, spec) in enumerate(tasks[:12]):
        rows = {r["planner"]: r for r in exact_slip.task_rows(
            2303, 0.0, task_id, task_type, start, spec, learner, states, edges, ids,
            engine.num_actions)}
        automaton = checkpoint.TaskAutomaton(spec)
        base = checkpoint.execute_product_policy(snapshots[8192], engine, automaton, start,
                                                 value="linear")
        best = checkpoint.execute_product_policy(snapshots[8192], engine, automaton, start,
                                                 value="optimal")
        assert rows["linear"]["p_success"] == 1.0 and rows["linear"]["expected_cost"] == base[1]
        assert rows["shortest"]["expected_cost"] == best[1]
        assert rows["shortest_oracle"]["expected_cost"] == rows["ssp_optimal"]["expected_cost"]


# ---------------------------------------------------------------------------
# The slipping world
# ---------------------------------------------------------------------------

def test_slip_is_reproducible_and_actually_slips():
    parent, _ = checkpoint.load_world(None, 2303)
    first = noisy.SlipEngine(parent["genome"], 0.5, "seed")
    second = noisy.SlipEngine(parent["genome"], 0.5, "seed")
    state = first.initial
    trace_one = [first.step(state, 0) for _ in range(50)]
    trace_two = [second.step(state, 0) for _ in range(50)]
    assert trace_one == trace_two
    exact = checkpoint.Engine(parent["genome"]).step(state, 0)
    assert any(s != exact for s in trace_one)


def test_at_slip_zero_every_noisy_planner_reproduces_the_checkpoint():
    parent, engine, snapshots, tasks = trained(2303)
    learner = noisy.train(noisy.SlipEngine(parent["genome"], 0.0, "x"), 8192)
    assert len(learner.i2s) == len(snapshots[8192].i2s)
    for task_type, start, spec in tasks:
        automaton = checkpoint.TaskAutomaton(spec)
        base = checkpoint.execute_product_policy(snapshots[8192], engine, automaton, start,
                                                 value="linear")
        best = checkpoint.execute_product_policy(snapshots[8192], engine, automaton, start,
                                                 value="optimal")
        for method, reference in (("linear", base), ("linear_empirical", base),
                                  ("shortest", best), ("expected", best)):
            got = noisy.run_episode(learner, noisy.SlipEngine(parent["genome"], 0.0, "y"),
                                    automaton, start, method)
            assert (got["success"], got["steps"]) == reference[:2], (method, task_type)
