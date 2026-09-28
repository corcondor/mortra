import json
import time

import pytest

from experiments.frontier_longrun.runner import (
    Session, World, canonical, digest, journal_rows, learner_data, registration,
    main, seal, source_record, unseal, versions,
)
from experiments.task_agent.pretraining import METHODS, train_snapshots_with_policy


def small_spec():
    return {'id': 'test_ring', 'kind': 'program', 'seed': 7, 'genome': {
        'version': 'finite-program-v1.1', 'domains': [12, 12], 'actions': 3,
        'initial': [1, 1], 'walls': [], 'rules': [
            {'action': 0, 'guard': [], 'assign': [{'var': 0, 'op': 'add_mod', 'value': 1}]},
            {'action': 1, 'guard': [], 'assign': [{'var': 1, 'op': 'add_mod', 'value': 1}]},
            {'action': 2, 'guard': [], 'assign': [{'var': 0, 'op': 'add_mod', 'value': -1}]},
        ]}}


class ObservationWorld:
    def __init__(self, spec):
        self.world = World(spec)
        self.initial = self.world.observe(self.world.initial)
        self.num_actions = self.world.num_actions
        self.reverse = {self.initial: self.world.initial}

    def step(self, observation, action):
        nxt = self.world.step(self.reverse[observation], action)
        obs = self.world.observe(nxt)
        self.reverse[obs] = nxt
        return obs


@pytest.mark.parametrize('method', METHODS)
def test_exact_original_prefix_and_resumed_prefix(method, tmp_path):
    world = ObservationWorld(small_spec())
    trace = []
    original = train_snapshots_with_policy(world, method, (12, 24), trace_sink=trace.append)
    session = Session(small_spec(), method, tmp_path, 'test')
    assert session.advance(12)
    assert digest(learner_data(original.snapshots[12])) == digest(learner_data(session.learner))
    resumed = Session(small_spec(), method, tmp_path, 'test')
    assert resumed.world.step_calls == 0
    assert resumed.advance(24)
    assert resumed.world.step_calls == 12
    assert digest(learner_data(original.snapshots[24])) == digest(learner_data(resumed.learner))
    saved = list(journal_rows(tmp_path))
    assert [r['action'] for r in trace] == [r['action'] for r in saved]
    assert [list(r['state']) for r in trace] == [r['observation'] for r in saved]


@pytest.mark.parametrize('method', METHODS)
def test_committed_observation_recovers_without_environment_operation(method, tmp_path, monkeypatch):
    session = Session(small_spec(), method, tmp_path, 'test')
    assert session.advance(8)
    def fail_after_journal(*args):
        raise RuntimeError('simulated crash after durable observation')

    monkeypatch.setattr(session, '_record', fail_after_journal)
    with pytest.raises(RuntimeError, match='simulated crash'):
        session.advance(9)
    assert session.world.step_calls == 9
    recovered = Session(small_spec(), method, tmp_path, 'test')
    assert recovered.steps == 9
    assert recovered.replayed == 1
    assert recovered.world.step_calls == 0
    reference = train_snapshots_with_policy(ObservationWorld(small_spec()), method, (9,))
    assert digest(learner_data(recovered.learner)) == digest(learner_data(reference.snapshots[9]))


def test_checksum_and_no_overwrite(tmp_path):
    path = tmp_path / 'x.json'
    seal(path, {'x': 1})
    with pytest.raises(FileExistsError):
        seal(path, {'x': 2})
    data = json.loads(path.read_text())
    data['payload']['x'] = 2
    path.write_bytes(canonical(data))
    with pytest.raises(RuntimeError, match='checksum'):
        unseal(path)


def test_resource_pause_is_no_action_and_resumable(tmp_path):
    session = Session(small_spec(), 'virtual_frontier', tmp_path, 'test')
    assert not session.advance(10, deadline=time.monotonic() - 1)
    assert session.steps == session.world.step_calls == 0
    resumed = Session(small_spec(), 'virtual_frontier', tmp_path, 'test')
    assert resumed.advance(2)


def test_registration_reproducible_no_oracle_or_policy_calls(monkeypatch):
    from experiments.game_frontier_v11 import world
    from experiments.task_agent.pretraining import TaskBlindSelector

    def forbidden(*args, **kwargs):
        raise AssertionError('oracle or policy used to construct benchmark')

    monkeypatch.setattr(world, 'oracle', forbidden)
    monkeypatch.setattr(TaskBlindSelector, 'choose', forbidden)
    a = registration([98028000], [98028100])
    b = registration([98028000], [98028100])
    assert digest(a) == digest(b)
    assert a['worlds'][0]['genome']['domains'][:2] == [32, 32]
    assert a['worlds'][1]['environment']['size'] == [7, 7, 3]


def test_corrupt_or_partial_journal_is_not_silently_replayed(tmp_path):
    session = Session(small_spec(), 'virtual_frontier', tmp_path, 'test')
    session.advance(2)
    path = next(tmp_path.glob('journal_*'))
    with path.open('ab') as stream:
        stream.write(b'{"incomplete":')
    with pytest.raises(RuntimeError, match='incomplete journal'):
        Session(small_spec(), 'virtual_frontier', tmp_path, 'test')


def test_wrong_registration_rejected(tmp_path):
    session = Session(small_spec(), 'virtual_frontier', tmp_path, 'first')
    session.advance(2)
    with pytest.raises(RuntimeError, match='another run'):
        Session(small_spec(), 'virtual_frontier', tmp_path, 'second')


def test_physics_adapter_uses_only_executed_steps(tmp_path, monkeypatch):
    spec = registration([], [98028100])['worlds'][0]
    session = Session(spec, 'virtual_frontier', tmp_path, 'test')
    monkeypatch.setattr(session.world.engine, 'raw_goal', lambda *_: pytest.fail('goal queried'))
    session.advance(12)
    assert session.world.step_calls == 12
    assert sum(session.learner.action_visits.values()) == 12
    assert all(len(state) == 1 and state[0].startswith('state_') for state in session.learner.id_to_state)


def test_full_command_small_fixture_and_reentry_skip_complete(tmp_path):
    reg = {'worlds': [small_spec()], 'methods': list(METHODS), 'checkpoints': [2, 4],
           'source': source_record(), 'versions': versions()}
    seal(tmp_path / 'registration.json', reg)
    main(['--root', str(tmp_path), '--session-hours', '1', '--min-free-gib', '0'])
    before = {str(p): p.read_bytes() for p in tmp_path.glob('test_ring/*/journal_*')}
    main(['--root', str(tmp_path), '--session-hours', '1', '--min-free-gib', '0'])
    after = {str(p): p.read_bytes() for p in tmp_path.glob('test_ring/*/journal_*')}
    assert before == after
    for path in tmp_path.glob('summary_*.json'):
        summary = unseal(path)
        assert summary['status'] == 'COMPLETE'
        assert summary['checkpoint_count'] == 6
        assert len(summary['paired_differences']) == 4
