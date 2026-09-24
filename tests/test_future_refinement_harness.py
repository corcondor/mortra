"""Evaluator checks, separate from the unmodified supplied core tests."""
from collections import Counter, defaultdict
from types import SimpleNamespace

from scripts.evaluate_future_refinement_small_ab import (
    CONFIG, coded_machine, independent_residual, partition_metrics, record_episode,
    verify_sources,
)
from exact_moore_oracle import MooreMachine


def test_provided_and_old_hashes():
    assert len(verify_sources()) >= 10


def test_partition_labels_do_not_matter():
    m = partition_metrics([5, 5, 9], [0, 0, 1])
    assert m["exact_partition_agreement"]
    assert m["false_merge_pairs"] == m["false_split_pairs"] == 0


def test_false_merge_has_inequivalent_pair_denominator():
    m = partition_metrics([0, 0, 0], [0, 1, 1])
    assert m["false_merge"] == 1
    assert m["false_split"] == 0
    assert m["false_merge_pairs"] == 2


def test_false_split_has_equivalent_pair_denominator():
    m = partition_metrics([0, 1, 2], [0, 0, 0])
    assert m["false_merge"] is None
    assert m["false_split"] == 1
    assert m["false_split_pairs"] == 3


def test_empty_pair_denominator_not_invented():
    assert partition_metrics([0], [0])["pair_denominator"] == 0


def test_collector_separates_hidden_data():
    machine = MooreMachine((0, 1), ("a",), {0: "x", 1: "y"}, {(0, "a"): 1, (1, "a"): 1})
    coded = coded_machine(machine)
    episode, hidden = record_episode(coded, 0, [0])
    assert set(episode) == {"observations", "actions"}
    assert hidden == [0, 1]
    assert episode == {"observations": [0, 1], "actions": [0]}


def test_independent_residual_rejects_wrong_merge():
    counts = defaultdict(Counter, {(0, 0): Counter({0: 1}), (1, 0): Counter({2: 1})})
    model = SimpleNamespace(leaf_counts=counts, leaf_keys=[0, 1, 2], actions=[0], model={"blocks": [0, 0, 1]})
    assert independent_residual(model, "NEW") == 2


def test_independent_residual_preserves_missing_rows():
    model = SimpleNamespace(leaf_counts={}, leaf_keys=[0, 1], actions=[0], model={"blocks": [0, 1]})
    assert independent_residual(model, "NEW") == 0
    assert model.leaf_counts == {}


def test_no_history_cap_or_seed_selection():
    assert CONFIG["history_cap_new"] is None
    assert CONFIG["stage2_seeds"] == [201, 302, 403]
    assert CONFIG["random_seeds"] == list(range(961000, 961010))
