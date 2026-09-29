import hashlib
import json

import numpy as np
import pytest

from experiments.noisy_rgb_discovery.core import Statistics, calibrate, learner, model_record, predict_from_rgb
from experiments.noisy_rgb_discovery.sensor import RGBPort, Sensor, make_game
from experiments.noisy_rgb_discovery.source import EXPECTED, ROOT, table_class


def toy_sample(history, replicate):
    visible = bit = 0
    for a in history:
        if a == 0:
            bit = 1-bit
        elif a == 1:
            visible = bit
        elif a == 2:
            visible = 1-visible
    seed = int.from_bytes(hashlib.sha256(json.dumps([history, replicate]).encode()).digest()[:8], 'little')
    rng = np.random.default_rng(seed)
    return np.clip(40+visible*170+rng.integers(-3, 4, size=(8, 4, 2, 2, 3)), 0, 255).astype(np.uint8)


def toy_statistics():
    return Statistics(RGBPort(tuple(range(5)), toy_sample))


def fit_toy(memoize=True):
    calibration = toy_statistics()
    threshold, _ = calibrate(calibration, calibration.port.actions)
    stats = toy_statistics()
    emitted = []
    table = learner(stats, stats.port.actions, threshold, emitted.append, memoize=memoize)
    assert table.E == [()] and table.S == [()]
    model, rounds = table.learn()
    return stats, table, model, rounds


def test_reference_hashes():
    for name, expected in EXPECTED.items():
        assert hashlib.sha256((ROOT/name).read_bytes()).hexdigest() == expected


def test_no_goal_or_state_api(tmp_path):
    game = make_game(95027004)
    with pytest.raises(AssertionError):
        game.raw_goal(game.start_raw)
    with pytest.raises(AssertionError):
        game.get_initial_state()
    sensor = Sensor(game, (0, 0), 'unit', tmp_path/'sensor')
    try:
        assert set(sensor.port.__dataclass_fields__) == {'actions', 'sample'}
        raw = sensor.port.sample((3, 0), 0)
        assert raw.shape == (8, 4, 12, 12, 3)
        assert sensor.actions == 2 and sensor.exposures == 8
    finally:
        sensor.close()


def test_replicates_differ_and_replay_counts(tmp_path):
    sensor = Sensor(make_game(95027004), (.32, -.24), 'unit', tmp_path/'sensor')
    try:
        a = sensor.sample((0, 1), 0)
        b = sensor.sample((0, 1), 1)
        assert not np.array_equal(a, b)
        assert sensor.metrics()['environment_actions'] == 4
    finally:
        sensor.close()


def test_success_compatibility_is_constant_not_sensor_output():
    stats = toy_statistics()
    x = stats.summary(())
    assert x.goal is False
    assert set(x.__dataclass_fields__) == {'mean', 'var', 'n'}
    with pytest.raises(AttributeError):
        x.goal = True


def test_calibration_repeats_same_histories_only():
    stats = toy_statistics()
    t, report = calibrate(stats, stats.port.actions)
    assert len(report['histories']) == 100
    assert t == max(report['scores'])*1.18
    assert all((tuple(h), 0) in stats.cache and (tuple(h), 1) in stats.cache for h in report['histories'])


def test_suffix_is_discovered_with_recorded_witness():
    stats, table, model, rounds = fit_toy()
    assert len(model['reps']) == 4
    assert len(table.E) > 1
    assert not rounds[-1]['counterexample']
    for event in table.events:
        assert event['suffix'] not in event['prior_E']
        assert event['previous_suffix'] in event['prior_E']
        assert max(event['prior_scores']) <= event['threshold'] < event['witness_score']
    assert not any(model['goal'].values())


def test_memoization_preserves_decisions_and_model():
    s1, t1, m1, l1 = fit_toy(True)
    s2, t2, m2, l2 = fit_toy(False)
    assert model_record(m1, t1.E) == model_record(m2, t2.E)
    assert t1.events == t2.events
    assert l1 == l2
    assert list(s1.cache) == list(s2.cache)


def test_adapter_matches_unmodified_reference_table():
    stats, table, model, rounds = fit_toy()
    fresh = toy_statistics()
    reference = table_class(fresh.port.actions)(fresh, table.T)
    other, log = reference.learn()
    assert model_record(model, table.E) == model_record(other, reference.E)
    assert rounds == log


def test_empty_suffix_cannot_resolve_hidden_bit():
    stats, table, model, _ = fit_toy()
    proto = [[stats.summary(h+e) for e in table.E] for h in model['reps']]
    validation = toy_statistics()
    full = predict_from_rgb(validation, (0,), table.E, proto, table.T)
    passive = predict_from_rgb(validation, (0,), [()], [[p[0]] for p in proto], table.T)
    assert full['predicted'] is not None
    assert passive['predicted'] is None and len(passive['candidates']) == 2


def test_evaluation_truth_not_imported_by_core():
    from experiments.noisy_rgb_discovery import core
    assert not hasattr(core, 'truth')
    assert not hasattr(core, 'make_game')


def test_shrinking_floor_matches_20260928_schedule_and_preserves_legacy_default():
    # The legacy path remains byte-for-byte semantic default at n=32.
    x = np.zeros((32, 1, 1, 1, 1), dtype=np.uint8)
    y = np.full((32, 1, 1, 1, 1), 2, dtype=np.uint8)
    port = RGBPort((0,), lambda history, rep: x if rep == 0 else y)
    fixed = Statistics(port)
    shrinking = Statistics(port, floor_mode='shrinking')
    a, b = fixed.summary((), 0), fixed.summary((), 1)
    assert fixed.effective_noise_floor(a, b) == pytest.approx(.01)
    a2, b2 = shrinking.summary((), 0), shrinking.summary((), 1)
    assert shrinking.effective_noise_floor(a2, b2) == pytest.approx(.01)
    assert fixed.z(a, b) == pytest.approx(shrinking.z(a2, b2))

    e512 = type(a)(a.mean, a.var, 512)
    assert shrinking.effective_noise_floor(e512, e512) == pytest.approx(.01*(32/512)**.25)


def test_exact_clean_zero_variance_is_not_a_calibration_error():
    same = np.zeros((8, 1, 1, 1, 1), dtype=np.uint8)
    other = np.full((8, 1, 1, 1, 1), 255, dtype=np.uint8)
    stats = Statistics(RGBPort((0,), lambda h, rep: same if rep == 0 else other), noise_floor=0.)
    a = stats.summary((), 0)
    b = stats.summary((), 1)
    assert stats.z(a, a) == 0.0
    assert np.isinf(stats.z(a, b))
