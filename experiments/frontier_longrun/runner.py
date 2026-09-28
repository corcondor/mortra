"""Colab infrastructure, not a new learner or a Minecraft implementation.

Raw environment states are retained by the harness. The learner receives only
random opaque observation labels and the outcomes of its executed actions.
This is a fully observed control, not a noisy-RGB perception experiment.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path
import platform
import random
import subprocess
import sys
import time
import uuid

import numpy as np
import psutil
import scipy
from PIL import Image

from experiments.game_frontier_v1.frozen import StructuralLearner
from experiments.game_frontier_v1.world import OpaqueMap
from experiments.game_frontier_v11 import designer
from experiments.game_frontier_v11.world import Engine
from experiments.noisy_rgb_discovery.reference.physics3d import PhysicsArena3D
from experiments.task_agent.pretraining import METHODS, TaskBlindSelector

ROOT = Path(__file__).resolve().parents[2]
CHECKPOINTS = (2048, 8192, 32768, 131072)
SOURCES = (
    'scripts/evaluate_cross_domain_generalization.py',
    'experiments/game_frontier_v1/frozen.py',
    'experiments/game_frontier_v1/world.py',
    'experiments/game_frontier_v11/world.py',
    'experiments/game_frontier_v11/designer.py',
    'experiments/noisy_rgb_discovery/reference/physics3d.py',
    'experiments/task_agent/pretraining.py',
    'experiments/task_agent/core.py',
    'experiments/task_agent/exploration.py',
    'experiments/task_agent/virtual_frontier.py',
    'experiments/frontier_longrun/runner.py',
    'experiments/frontier_longrun/PROTOCOL.md',
    'experiments/frontier_longrun/build_notebook.py',
    'tests/test_frontier_longrun.py',
)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def digest(value):
    return hashlib.sha256(canonical(value)).hexdigest()


def read(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_new(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('xb') as stream:
        stream.write(canonical(value))
        stream.flush()
        os.fsync(stream.fileno())
    if read(path) != json.loads(canonical(value)):
        raise RuntimeError(f'write/read-back mismatch: {path}')


def seal(path, value):
    """Immutable record with a digest of its payload."""
    write_new(path, {'sha256': digest(value), 'payload': value})


def unseal(path):
    value = read(path)
    if digest(value['payload']) != value['sha256']:
        raise RuntimeError(f'checksum mismatch: {path}')
    return value['payload']


def versions():
    return {'python': platform.python_version(), 'numpy': np.__version__,
            'scipy': scipy.__version__, 'psutil': psutil.__version__,
            'platform': platform.platform()}


def source_record():
    if subprocess.call(['git', 'diff', '--quiet', 'HEAD'], cwd=ROOT):
        raise RuntimeError('tracked source has uncommitted edits')
    return {'sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT, text=True).strip(),
            'files': {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in SOURCES}}


def learner_data(learner):
    return {'num_actions': learner.num_actions, 'id_to_state': learner.id_to_state,
            'state_to_id': list(learner.state_to_id.items()),
            'node_visits': list(learner.node_visits.items()),
            'action_visits': list(learner.action_visits.items()),
            'counts': [[k, list(v.items())] for k, v in learner.counts.items()],
            'dest_map': list(learner.dest_map.items())}


def restore_learner(data):
    learner = StructuralLearner(data['num_actions'])
    learner.id_to_state = [tuple(s) for s in data['id_to_state']]
    learner.state_to_id = {tuple(s): i for s, i in data['state_to_id']}
    learner.node_visits = dict(data['node_visits'])
    learner.action_visits = {tuple(k): v for k, v in data['action_visits']}
    learner.counts = {tuple(k): dict(v) for k, v in data['counts']}
    learner.dest_map = {tuple(k): v for k, v in data['dest_map']}
    assert digest(learner_data(learner)) == digest(data)
    return learner


def tuples(value):
    return tuple(map(tuples, value)) if isinstance(value, list) else value


class World:
    def __init__(self, spec):
        self.spec = spec
        if spec['kind'] == 'program':
            self.engine = Engine(spec['genome'])
            self.initial = self.engine.initial
        else:
            self.engine = PhysicsArena3D(spec['seed'])
            if digest(self.engine.spec()) != digest(spec['environment']):
                raise RuntimeError('3D environment changed')
            self.initial = self.engine.start_raw
        self.num_actions = self.engine.num_actions
        self.opaque = OpaqueMap(spec['seed'] + 1000000)
        self.step_calls = 0

    def observe(self, raw):
        return (self.opaque.encode(tuple(raw)),)

    def step(self, state, action):
        self.step_calls += 1
        if self.spec['kind'] == 'program':
            return self.engine.step(state, action)
        return self.engine.raw_step(state, action)

    def observation_state(self):
        return {'rng': self.opaque.rng.getstate(), 'states': list(self.opaque.states.items())}

    def restore_observations(self, data):
        self.opaque.rng.setstate(tuples(data['rng']))
        self.opaque.states = {tuple(raw): token for raw, token in data['states']}
        self.opaque.labels = set(self.opaque.states.values())
        assert len(self.opaque.labels) == len(self.opaque.states)


def registration(program_seeds=range(98028000, 98028032), physics_seeds=range(98028100, 98028108)):
    worlds = []
    for seed in program_seeds:
        rng = random.Random(seed)
        genome = designer.generate(rng)
        edits = []
        # Fixed random generation, not performance-guided invention or filtering.
        for index in range(32):
            family = rng.choice(designer.FAMILIES)
            try:
                genome = designer.mutate(genome, family, rng, 32)
                edits.append({'index': index, 'family': family, 'accepted_syntax': True})
            except ValueError as exc:
                edits.append({'index': index, 'family': family, 'accepted_syntax': False, 'reason': str(exc)})
        while genome['domains'][0] < 32:
            genome = designer.mutate(genome, 'board', rng, 32)
            edits.append({'family': 'board', 'reason': 'fixed 32x32 scale, not learned choice'})
        worlds.append({'id': f'program_{seed}', 'kind': 'program', 'seed': seed,
                       'genome': genome, 'generation_log': edits})
    for seed in physics_seeds:
        worlds.append({'id': f'physics3d_{seed}', 'kind': 'physics3d', 'seed': seed,
                       'environment': PhysicsArena3D(seed).spec()})
    return {'protocol': 'frontier-longrun-development-v1', 'worlds': worlds,
            'methods': list(METHODS), 'checkpoints': list(CHECKPOINTS),
            'q': .9, 'source': 1, 'task_aware': False, 'task_source': False,
            'observation': 'fully-observed random opaque labels; NOT noisy RGB',
            'oracle_calls': 0, 'selection': 'none', 'world_replacement': False,
            'claim': 'long-run structure acquisition, not Minecraft or autonomous game construction',
            'source': source_record(), 'versions': versions()}


class Session:
    def __init__(self, spec, method, folder, registration_hash):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=True)
        self.world = World(spec)
        self.method, self.registration_hash = method, registration_hash
        self.selector = TaskBlindSelector(method)
        self.learner = StructuralLearner(self.world.num_actions)
        self.raw = self.world.initial
        self.state = self.world.observe(self.raw)
        self.learner.get_or_add_id(self.state)
        self.steps = 0
        self.cpu = self.wall = 0.0
        self.peak_rss = 0
        self.snapshots = []
        self.journal_tip = '0' * 64
        self.replayed = 0
        self._restore()

    def checkpoint_payload(self):
        return {'registration': self.registration_hash, 'method': self.method,
                'world': self.world.spec['id'], 'steps': self.steps,
                'learner': learner_data(self.learner), 'raw_state': self.raw,
                'observation': self.state, 'observation_state': self.world.observation_state(),
                'cpu_seconds': self.cpu, 'wall_seconds': self.wall,
                'peak_sampled_rss_bytes': self.peak_rss, 'journal_tip': self.journal_tip}

    def checkpoint(self):
        if sum(self.learner.action_visits.values()) != self.steps:
            raise RuntimeError('learner action count mismatch')
        path = self.folder / f'checkpoint_{self.steps:09d}.json'
        data = self.checkpoint_payload()
        if path.exists():
            if digest(unseal(path)) != digest(data):
                raise RuntimeError('existing checkpoint differs')
        else:
            seal(path, data)
        if self.steps in CHECKPOINTS and self.world.spec['kind'] == 'physics3d':
            picture = self.folder / f'observed_state_{self.steps:09d}.png'
            if not picture.exists():
                views = self.world.engine.render_views(self.raw)
                with picture.open('xb') as stream:
                    Image.fromarray(np.concatenate(views, axis=1)).save(stream, format='PNG')
                seal(self.folder / f'observed_state_{self.steps:09d}_metadata.json', {
                    'step': self.steps, 'world': self.world.spec['id'], 'method': self.method,
                    'raw_state': self.raw, 'sha256': hashlib.sha256(picture.read_bytes()).hexdigest(),
                    'meaning': 'rendered recorded state for inspection; RGB not supplied to learner'})
        return path

    def _restore(self):
        checkpoints = sorted(self.folder.glob('checkpoint_*.json'))
        if checkpoints:
            data = unseal(checkpoints[-1])
            if (data['registration'], data['method'], data['world']) != (
                    self.registration_hash, self.method, self.world.spec['id']):
                raise RuntimeError('checkpoint belongs to another run')
            self.learner = restore_learner(data['learner'])
            self.world.restore_observations(data['observation_state'])
            self.steps, self.raw, self.state = data['steps'], tuple(data['raw_state']), tuple(data['observation'])
            self.cpu, self.wall = data['cpu_seconds'], data['wall_seconds']
            self.peak_rss, self.journal_tip = data['peak_sampled_rss_bytes'], data['journal_tip']
        # A journal row is a committed observation. Recovery never steps the world.
        snapshot_step, snapshot_tip = self.steps, self.journal_tip
        last_journal_step = 0
        for row in journal_rows(self.folder):
            step = row['step']
            last_journal_step = step
            if step == snapshot_step and digest(row) != snapshot_tip:
                raise RuntimeError('checkpoint/journal tip mismatch')
            if step <= self.steps:
                continue
            if step != self.steps + 1 or row['previous'] != self.journal_tip:
                raise RuntimeError('action journal gap or hash chain mismatch')
            choice, _ = self.selector.choose(self.learner, self.state)
            if choice.action != row['action'] or list(self.state) != row['observation']:
                raise RuntimeError('recovery differs from recorded policy')
            nxt = tuple(row['next_raw'])
            observation = self.world.observe(nxt)
            if list(observation) != row['next_observation']:
                raise RuntimeError('recovery observation mapping differs')
            self._record(row, nxt, observation)
            self.replayed += 1
        if last_journal_step < snapshot_step:
            raise RuntimeError('checkpoint has missing action journal')

    def _record(self, row, nxt, observation):
        u = self.learner.state_to_id[self.state]
        v = self.learner.get_or_add_id(observation)
        self.learner.record_transition(u, row['action'], v)
        self.steps += 1
        self.raw, self.state = nxt, observation
        self.cpu += row['cpu_seconds']
        self.wall += row['wall_seconds']
        self.peak_rss = max(self.peak_rss, row['rss_bytes'])
        self.journal_tip = digest(row)

    def advance(self, target, *, deadline=float('inf'), min_available_bytes=0):
        if self.steps >= target:
            return True
        path = self.folder / f'journal_{self.steps + 1:09d}_{uuid.uuid4().hex}.jsonl'
        with path.open('xb') as journal:
            return self._advance(target, journal, deadline, min_available_bytes)

    def _advance(self, target, journal, deadline, min_available_bytes):
        while self.steps < target:
            if time.monotonic() >= deadline or psutil.virtual_memory().available < min_available_bytes:
                self.checkpoint()
                return False
            cpu0, wall0 = time.process_time(), time.perf_counter()
            decision, telemetry = self.selector.choose(self.learner, self.state)
            action = int(decision.action)
            if not 0 <= action < self.world.num_actions:
                raise RuntimeError('illegal action')
            nxt = self.world.step(self.raw, action)
            observation = self.world.observe(nxt)
            row = {'step': self.steps + 1, 'previous': self.journal_tip,
                   'observation': self.state, 'action': action, 'next_observation': observation,
                   'raw_state': self.raw, 'next_raw': nxt,
                   'cpu_seconds': time.process_time() - cpu0,
                   'wall_seconds': time.perf_counter() - wall0,
                   'rss_bytes': psutil.Process().memory_info().rss,
                   'scores': telemetry.get('generic_scores'),
                   'virtual_frontier': telemetry.get('virtual_field_decision'),
                   'field_residual': telemetry.get('field_residual')}
            # Persist actual observation before changing the learner. A damaged
            # write is an infrastructure interruption, never a policy failure.
            journal.write(canonical({'sha256': digest(row), 'payload': row}) + b'\n')
            journal.flush()
            os.fsync(journal.fileno())
            self._record(row, nxt, observation)
            if self.steps % 512 == 0:
                self.checkpoint()
                print(json.dumps({'checkpoint': self.steps, 'world': self.world.spec['id'],
                                  'method': self.method, 'known_states': len(self.learner.id_to_state),
                                  'tried_state_actions': len(self.learner.counts),
                                  'cpu_seconds': self.cpu}), flush=True)
        self.checkpoint()
        return True


def journal_rows(folder):
    expected, previous = 1, '0' * 64
    for path in sorted(Path(folder).glob('journal_*.jsonl')):
        with path.open('rb') as stream:
            for line in stream:
                if not line.endswith(b'\n'):
                    raise RuntimeError(f'incomplete journal write; preserve and audit: {path}')
                record = json.loads(line)
                row = record['payload']
                if digest(row) != record['sha256'] or row['step'] != expected or row['previous'] != previous:
                    raise RuntimeError(f'journal checksum, duplicate or gap: {path}')
                yield row
                expected, previous = expected + 1, digest(row)


def summarize(root, reg):
    rows = []
    for spec in reg['worlds']:
        for method in reg['methods']:
            folder = root / spec['id'] / method
            for budget in reg['checkpoints']:
                path = folder / f'checkpoint_{budget:09d}.json'
                if not path.exists():
                    continue
                data = unseal(path)
                rows.append({'world': spec['id'], 'kind': spec['kind'], 'seed': spec['seed'],
                             'method': method, 'budget': budget,
                             'known_states': len(data['learner']['id_to_state']),
                             'tried_state_actions': len(data['learner']['counts']),
                             'cpu_seconds': data['cpu_seconds'],
                             'wall_seconds_excluding_persistence': data['wall_seconds'],
                             'peak_sampled_process_rss_bytes': data['peak_sampled_rss_bytes']})
    stamp = uuid.uuid4().hex
    expected = len(reg['worlds']) * len(reg['methods']) * len(reg['checkpoints'])
    by_key = {(r['world'], r['method'], r['budget']): r for r in rows}
    paired = []
    for spec in reg['worlds']:
        for budget in reg['checkpoints']:
            main_row = by_key.get((spec['id'], 'virtual_frontier', budget))
            for baseline in ('structural', 'frontier_t0'):
                base_row = by_key.get((spec['id'], baseline, budget))
                if main_row is not None and base_row is not None:
                    paired.append({'world': spec['id'], 'budget': budget, 'baseline': baseline,
                                   'known_states_difference': main_row['known_states'] - base_row['known_states'],
                                   'tried_state_actions_difference': main_row['tried_state_actions'] - base_row['tried_state_actions'],
                                   'cpu_seconds_difference': main_row['cpu_seconds'] - base_row['cpu_seconds']})
    result = {'status': 'COMPLETE' if len(rows) == expected else 'INCOMPLETE',
              'checkpoint_count': len(rows), 'expected_checkpoints': expected, 'rows': rows,
              'paired_differences': paired,
              'noisy_rgb_claim': False, 'minecraft_claim': False, 'policy_success_claim': False}
    seal(root / f'summary_{stamp}.json', result)
    if rows:
        with (root / f'summary_{stamp}.csv').open('x', newline='') as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', required=True, type=Path)
    parser.add_argument('--session-hours', type=float, default=6)
    parser.add_argument('--min-free-gib', type=float, default=1)
    args = parser.parse_args(argv)
    if args.session_hours <= 0 or args.min_free_gib < 0:
        parser.error('session-hours must be positive and min-free-gib nonnegative')
    root = args.root.resolve()
    root.mkdir(parents=True, exist_ok=True)
    reg_path = root / 'registration.json'
    if not reg_path.exists():
        seal(reg_path, registration())
    reg = unseal(reg_path)
    runtime = versions()
    if reg['source'] != source_record() or any(reg['versions'][k] != runtime[k] for k in (
            'python', 'numpy', 'scipy', 'psutil')):
        raise RuntimeError('source or numerical runtime changed; refusing silent continuation')
    attempt = uuid.uuid4().hex
    seal(root / f'attempt_{attempt}_start.json', {
        'runtime': versions(), 'cpu_count': os.cpu_count(),
        'ram_bytes': psutil.virtual_memory().total, 'session_hours': args.session_hours,
        'parallel_workers': 1, 'method_order': reg['methods'],
        'timing': 'shared Colab worker, fixed order; not a rigorous speed benchmark',
        'argv': sys.argv, 'started_unix': time.time()})
    deadline = time.monotonic() + args.session_hours * 3600
    invocation_start = time.monotonic()
    try:
        for budget in reg['checkpoints']:
            for spec in reg['worlds']:
                for method in reg['methods']:
                    folder = root / spec['id'] / method
                    if (folder / f'checkpoint_{budget:09d}.json').exists():
                        unseal(folder / f'checkpoint_{budget:09d}.json')
                        continue
                    session = Session(spec, method, folder, digest(reg))
                    complete = session.advance(budget, deadline=deadline,
                                               min_available_bytes=int(args.min_free_gib * 2**30))
                    print(json.dumps({'world': spec['id'], 'method': method,
                                      'steps': session.steps, 'states': len(session.learner.id_to_state),
                                      'resume_replayed_without_world_steps': session.replayed}), flush=True)
                    del session
                    if not complete:
                        summary = summarize(root, reg)
                        print(json.dumps({k: summary[k] for k in ('status', 'checkpoint_count', 'expected_checkpoints')}), flush=True)
                        return
    except BaseException as exc:
        seal(root / f'attempt_{attempt}_interruption.json',
             {'type': type(exc).__name__, 'reason': str(exc), 'policy_failure': False})
        raise
    finally:
        summarize(root, reg)
        seal(root / f'attempt_{attempt}_end.json', {
            'invocation_wall_seconds_including_io_and_recovery': time.monotonic() - invocation_start,
            'ended_unix': time.time(), 'policy_failure': False})
    print('COMPLETE: all registered acquisition checkpoints saved', flush=True)


if __name__ == '__main__':
    main()
