"""Connection contracts, not additional training or benchmark examples."""
from collections import Counter
import numpy as np
import pytest

from mortra_predictive_perception.symbol_world import SymbolWorld
from mortra_predictive_perception.world import UNKNOWN
from scripts import integrated_predictive_evaluation as ev
from scripts import evaluate_integrated_predictive_world_model as run


def test_repeated_symbol_is_one_state_not_one_state_per_time():
    world = SymbolWorld((0, 1))
    world.add_episode(("a", "b", "a", "b", "a"), (0, 1, 0, 1))
    world.freeze()
    assert len(world.labels) == len(world.emissions) == 2
    assert world.counts[world.nodes["a"], 0] == Counter({world.nodes["b"]: 2})
    assert world.connection_audit()["training_transitions_checked"] == 4


def test_recombination_differs_from_every_training_prefix():
    world = SymbolWorld((0, 1))
    world.add_episode(("a", "b", "a", "c", "a"), (0, 0, 1, 1))
    world.freeze()
    symbols, actions = ("a", "c", "a", "b", "a"), (1, 1, 0, 0)
    belief = world.begin(symbols[0])
    for t, action in enumerate(actions):
        belief = world.update(belief, action, symbols[t+1])
        assert belief and UNKNOWN not in belief
        assert belief == world.reconstruct(symbols[:t+2], actions[:t+1])


def test_successor_disagreement_retained_not_modal_or_hidden():
    world = SymbolWorld(("a", "b"))
    world.add_episode((10, 20, 10, 30), ("a", "b", "a"))
    world.freeze()
    predicted = world.predict(world.begin(10), "a")
    assert {world.emissions[s] for s in predicted} == {20, 30}
    assert world.connection_audit()["multiple_successor_rows"] == 1
    assert not world.plan(world.begin(10), {s for s in predicted if world.emissions[s] == 20}).actions
    assert world.predict(world.begin(10), "b") == frozenset({UNKNOWN})


def test_reset_and_end_of_recording_do_not_create_new_world_states():
    world = SymbolWorld((0,))
    world.add_episode((1, 2, 1), (0, 0))
    world.add_episode((2, 1), (0,))
    world.freeze()
    assert len(world.initial) == 2
    assert len(world.labels) == 2
    assert world.reconstruct((1, 2, 1, 2, 1), (0, 0, 0, 0)) == world.begin(1)
    with pytest.raises(RuntimeError):
        world.add_episode((1, 2), (0,))


def test_exact_projection_still_audited():
    world = SymbolWorld((0, 1))
    world.add_episode((0, 1, 0, 2, 0), (0, 1, 0, 1))
    world.freeze()
    result = ev.audit_operator(world.labels, [world.actions]*len(world.labels), world.counts,
                               world.certificate["blocks"], world.certificate["rows"])
    assert result["exact_residual"] == "0"
    assert result["observations_preserved"]


def test_fitted_perception_connects_without_manually_supplied_symbols(tmp_path):
    # A fully sampled Markov sensor fixture isolates the connection, not the
    # ability of perception to generalize from a confounded periodic history.
    training = [(np.array([[float(s)], [float((s + (1 if a == 0 else -1)) % 3)]]), [a])
                for _ in range(12) for s in range(3) for a in (0, 1)]
    heldout = [(np.array([[0.], [2.], [0.], [2.], [0.]]), [1, 0, 1, 0])]
    for target in ("absolute", "delta"):
        perception, world, _, symbols, _ = run.fit_new(training, heldout, (0, 1), target, tmp_path)
        assert len(world.labels) == perception.report.generated_symbols == 3
        records, _, _ = ev.memory_records(world, heldout, symbols)
        assert all(r["agrees"] and not r["unknown"] and not r["contradiction"] for r in records)
        assert not {"q", "discount", "goal", "reward", "max_history_depth"} & vars(world).keys()


def test_history_sensitive_perception_is_not_replaced_by_raw_labels(tmp_path):
    actions = [0, 0, 0, 1, 1, 1]*12
    observations = np.array([[0.]] + [[x] for x in [1., 2., 0., 2., 1., 0.]*12])
    training = [(observations, actions)]
    heldout = [(np.array([[0.], [2.], [0.], [2.], [0.]]), [1, 0, 1, 0])]
    for target in ("absolute", "delta"):
        perception, world, _, symbols, _ = run.fit_new(training, heldout, (0, 1), target, tmp_path)
        assert len(world.labels) == perception.report.generated_symbols
        assert len(world.labels) < len(actions)
        before = dict(world.counts)
        records, _, _ = ev.memory_records(world, heldout, symbols)
        assert all(r["agrees"] for r in records)
        assert world.counts == before
        # No guarantee is imposed on this fixture's held-out perception.
        # Training symbols (including any history-dependent ones) define states.
        assert set(world.labels) == {s for seq, _, _ in world.episodes for s in seq}


def test_unknown_is_not_a_false_merge_or_successful_memory_recovery():
    unknown = frozenset({UNKNOWN})
    q = ev.common_partition([unknown, unknown, None, frozenset()], [0, 1, 2, 3])
    assert q["evaluated_occurrences"] == 0
    assert q["false_merge"] is None
    assert q["false_split"] is None
    assert q["predictive_violation"] is None
    records = [{"unknown": True, "contradiction": False, "agrees": True}]*4
    summary = ev.memory_agreement_summary(records)
    assert summary["known_nonempty_agreement"] is None
    assert summary["known_nonempty_steps"] == 0


def test_diagnostic_denominator_keeps_unobserved_cases_visible():
    states = [frozenset({0}), frozenset({0}), frozenset({UNKNOWN}), frozenset({0, 1})]
    quality = ev.common_partition(states, [0, 1, 2, 3])
    assert quality["known_assignment_fraction"] == .5
    assert quality["false_merge"] == 1
    ambiguity, participating = ev.ambiguity_diagnostics([[0]]*4, [0, 1, 2, 3], states)
    assert participating == {0, 1, 2, 3}
    assert ambiguity["same_observation_different_future_pairs"] == 6
    assert ambiguity["evaluated_known_different_future_pairs"] == 1
    assert ambiguity["excluded_uncertain_occurrences"] == 2
    assert ambiguity["collision_pairs"] == 1


def test_training_route_replay_is_reported_separately():
    records = [{"actual_success":True, "actions":[]},
               {"actual_success":True, "actions":[0, 1]},
               {"actual_success":True, "actions":[1, 0]}]
    audit = ev.trace_reuse_audit(records, [(None, [0, 1, 0])])
    assert audit["nonempty_successful_trajectories"] == 2
    assert audit["equal_training_action_prefix"] == 1
    assert audit["not_equal_training_action_prefix"] == 1


def test_paired_metrics_use_identical_history_carrier():
    values = {"OLD":[0, 0, None, 1], "NEW":[frozenset({UNKNOWN}), frozenset({0}), frozenset({0}), frozenset({0})]}
    result = ev.paired_partitions(values,[0, 1, 2, 3])
    for item in result.values():
        assert item["evaluated_occurrences"] == 2
        assert item["paired_evaluable_fraction"] == .5
        assert item["known_assignment_fraction"] == .75
        assert item["true_different_pairs"] == 1
    assert result["OLD"]["false_merge"] == 0
    assert result["NEW"]["false_merge"] == 1
