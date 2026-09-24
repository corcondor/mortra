"""Codex-authored development tests, NOT the missing handoff package tests."""
import hashlib
from pathlib import Path

import numpy as np
import pytest

from mortra_predictive_perception.adapters import ResponseSymbolizer, load_legacy_visual, readonly_episode
from mortra_predictive_perception.core import PredictiveMDLSymbolizer, UnknownActionResponse
from mortra_predictive_perception.evaluation import partition_quality
from mortra_predictive_perception.pipeline import fit_integrated, perception_metrics
from mortra_predictive_perception.world import ObservedWorld, UNKNOWN


ROOT = Path(__file__).resolve().parents[1]


def samples():
    return [([np.array([float(t), float(t % 2)]) for t in range(6)], [0, 1, 0, 1, 0]),
            ([np.array([float(-t), float(t % 3)]) for t in range(5)], [1, 0, 1, 0])]


def test_delta_adapter_is_reference_not_reimplementation():
    ref, adapter = PredictiveMDLSymbolizer([0, 1]), ResponseSymbolizer([0, 1])
    for obs, acts in samples():
        ref.add_episode(obs, acts)
        adapter.add_episode(obs, acts)
    assert ref.fit() == adapter.fit()
    assert ref.export_tree() == adapter.export_tree()
    for obs, acts in samples():
        for t in range(len(obs)):
            assert ref.encode_history(obs[:t + 1], acts[:t]) == adapter.encode_history(obs[:t + 1], acts[:t])


def test_absolute_adapter_changes_only_target():
    a, b = ResponseSymbolizer([0, 1], "absolute"), ResponseSymbolizer([0, 1], "delta")
    for obs, acts in samples():
        a.add_episode(obs, acts)
        b.add_episode(obs, acts)
    xa, va, ya, aa, sa, ma, da, ha = a._build_training_arrays()
    xb, vb, yb, ab, sb, mb, db, hb = b._build_training_arrays()
    np.testing.assert_array_equal(xa, xb)
    np.testing.assert_array_equal(va, vb)
    np.testing.assert_array_equal(aa, ab)
    assert (sa, ma, da, ha) == (sb, mb, db, hb)
    for i, (episode, t) in enumerate(ma):
        np.testing.assert_array_equal(ya[i], a.episodes[episode].observations[t + 1])
        np.testing.assert_array_equal(yb[i], a.episodes[episode].observations[t + 1] - a.episodes[episode].observations[t])


def test_shared_raw_arrays_cannot_be_modified():
    source = np.array([1.0, 2.0])
    obs, actions = readonly_episode([source, source + 1], ["opaque"])
    source[0] = -100
    assert obs[0][0] == 1
    assert actions == ("opaque",)
    with pytest.raises(ValueError):
        obs[0][0] = 4


def test_legacy_definition_loader_does_not_touch_log():
    source = ROOT / "scripts/evaluate_visual_state_construction.py"
    log = ROOT / "reports/visual_state_construction/run.log"
    before = log.read_bytes() if log.exists() else None
    legacy = load_legacy_visual(source)
    assert legacy.source_sha256 == hashlib.sha256(source.read_bytes()).hexdigest()
    assert legacy.VisualStateConstructor.map_observation_to_cluster.__code__.co_filename == str(source)
    after = log.read_bytes() if log.exists() else None
    assert before == after


def test_reference_unknown_action_response_remains_unknown():
    model = ResponseSymbolizer([0, 1])
    model.add_episode([[0.0], [1.0], [2.0]], [0, 0])
    model.fit()
    with pytest.raises(UnknownActionResponse):
        model.predict_response(model.encode_history([[0.0]], []), 1)


def test_reference_all_available_lags_are_candidates():
    model = ResponseSymbolizer([0, 1])
    for obs, acts in samples():
        model.add_episode(obs, acts)
    model.fit()
    assert max(s.lag for s in model.feature_specs) == 5
    assert not model._feature_valid[0, 2:].any()
    assert np.isfinite(model._feature_matrix).all()


def chain():
    model = ObservedWorld([0, 1])
    model.add_episode(["start", "middle", "goal"], [0, 1])
    return model.freeze()


def test_observed_action_congruence_is_exact():
    model = chain()
    assert model.certificate["eps_action"] == 0
    assert model.certificate["eps_K"] == 0
    assert "unobserved" in model.certificate["scope"]


def test_unknown_action_is_not_a_self_loop_or_imputed_successor():
    model = chain()
    b = model.begin("start")
    assert model.predict(b, 1) == frozenset({UNKNOWN})
    assert model.update(b, 1, "unseen symbol") == frozenset({UNKNOWN})
    target = {s for s, o in model.emissions.items() if o == "goal"}
    assert model.plan(frozenset({UNKNOWN}), target).guaranteed_steps is None


def test_recursive_belief_matches_independent_full_history_replay():
    model = ObservedWorld([0, 1])
    episodes = [(["s", "x", "g"], [0, 1]), (["s", "y", "g"], [0, 1]),
                (["s", "y", "y"], [0, 0])]
    for symbols, actions in episodes:
        model.add_episode(symbols, actions)
    model.freeze()
    for symbols, actions in episodes:
        b = model.begin(symbols[0])
        for t, (a, symbol) in enumerate(zip(actions, symbols[1:]), 1):
            b = model.update(b, a, symbol)
            assert b == model.reconstruct(symbols[:t + 1], actions[:t])
            assert b


def test_observed_contradiction_is_not_silently_replaced():
    model = chain()
    assert not model.update(model.begin("start"), 0, "unexpected")


def test_guaranteed_distance_is_attractor_entry_rank():
    model = chain()
    goals = {s for s, o in model.emissions.items() if o == "goal"}
    plan = model.plan(model.begin("start"), goals)
    assert plan.status == "GUARANTEED"
    assert plan.guaranteed_steps == 2
    assert plan.actions == (0,)


def test_every_possible_outcome_must_win():
    model = ObservedWorld([0])
    model.add_episode(["s", "g"], [0])
    model.add_episode(["s", "dead"], [0])
    model.freeze()
    goals = {s for s, o in model.emissions.items() if o == "g"}
    assert model.plan(model.begin("s"), goals).guaranteed_steps is None


def test_unknown_is_not_declared_identified():
    model = chain()
    assert model.identify(frozenset({UNKNOWN})).status == "NOT IDENTIFIABLE UNDER CURRENT MODEL/DATA"


def test_frozen_model_rejects_in_place_new_experience():
    with pytest.raises(RuntimeError):
        chain().add_episode(["a", "b"], [0])


def test_common_evaluator_ignores_arbitrary_partition_names():
    result = partition_quality([5, 9, 5], ["a", "b", "a"])
    assert result["exact_partition_equality"]
    assert result["partition_agreement"] == 1


def test_common_evaluator_distinguishes_overmerge_and_oversplit():
    merge = partition_quality([0, 0, 0], [0, 1, 0])
    split = partition_quality([0, 1, 2], [0, 1, 0])
    assert merge["over_merge_pairs"] == 2
    assert merge["over_split_pairs"] == 0
    assert split["over_merge_pairs"] == 0
    assert split["over_split_pairs"] == 1
    assert merge["predictive_violation_pairs"] == merge["over_merge_pairs"]


def test_empty_comparison_has_no_fake_accuracy():
    result = partition_quality([], [])
    assert result["partition_agreement"] is None
    assert result["exact_partition_equality"] is None


def test_raw_to_symbols_to_belief_pipeline_is_connected():
    model = fit_integrated(samples(), [0, 1])
    assert model.world.episodes
    assert model.world.certificate["eps_action"] == 0
    for obs, acts in samples():
        records = model.memory_audit(obs, acts)
        assert len(records) == len(obs)
        assert all(r["agrees"] and not r["model_contradiction"] for r in records)


def test_heldout_prediction_does_not_retrain_perception():
    import copy
    model = fit_integrated(samples(), [0, 1], "absolute")
    before = copy.deepcopy(model.perception.export_tree())
    heldout = [([np.array([3.0, 0.0]), np.array([4.0, 0.0])], [0])]
    metrics = perception_metrics(model.perception, heldout)
    assert metrics["predicted_transitions"] + metrics["unpredicted_transitions"] == 1
    assert model.perception.export_tree() == before
    assert len(model.perception.episodes) == 2


def test_new_pipeline_never_calls_old_fixed_field(monkeypatch):
    from scripts import evaluate_adaptive_refinement as old
    def forbidden(*args, **kwargs):
        raise AssertionError("OLD fixed-field was called by NEW")
    monkeypatch.setattr(old.base, "solve_fixed_field", forbidden)
    model = fit_integrated(samples(), [0, 1])
    model.world.plan(model.world.begin(model.training_symbols[0][0]), set())


def test_empty_belief_is_not_vacuous_identification():
    assert chain().identify(frozenset()).status == "MODEL CONTRADICTION"
