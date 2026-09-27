"""Reconstruct the frozen table using recorded statistics, with zero RGB queries."""
import gzip
import json
from pathlib import Path
import sys
import time
import zipfile

import numpy as np

REPO = Path('C:/Users/81808/.openclaw/workspace/mortra-v2-online-feedback-20260928')
sys.path.insert(0, str(REPO))
from experiments.noisy_rgb_discovery.core import Emission, Statistics, learner

BASE = Path(__file__).parent/'completed'


def get(z, suffix):
    names = [n for n in z.namelist() if n.endswith(suffix)]
    assert len(names) == 1
    return z.read(names[0])


class NoNewSamples:
    def sample(self, *args):
        raise AssertionError('Replay requested an unsaved RGB observation')


def main():
    artifacts = json.loads((BASE/'artifacts.json').read_text())['artifacts']
    reports = []
    for artifact in artifacts:
        if artifact['name'].startswith('noisy-rgb-tests-'):
            continue
        with zipfile.ZipFile(BASE/'original_artifacts'/f"{artifact['id']}.zip") as z:
            start = time.perf_counter()
            result = json.loads(get(z, '/result.json'))
            partial = json.loads(get(z, '/partial_table.json'))
            config = json.loads(get(z, '/config.json'))
            calibration = json.loads(get(z, '/calibration.json'))
            index = json.loads(get(z, '/statistics_index.json'))
            data = np.frombuffer(gzip.decompress(get(z, '/statistics.bin.gz')), dtype='<f4').reshape(len(index), 2, -1)
            stats = Statistics(NoNewSamples(), config['noise_floor'])
            stats.cache = {(tuple(w), rep): Emission(data[i, 0], data[i, 1], config['batch'])
                           for i, (w, rep) in enumerate(index)}
            events = []
            table = learner(stats, tuple(range(5)), calibration['threshold'], events.append)
            try:
                table.learn(max_rounds=config['reference_max_rounds'], depth=config['reference_conformance_depth'])
                error = None
            except RuntimeError as exc:
                error = repr(exc)
            assert error == result['error']
            assert [list(w) for w in table.S] == partial['S']
            assert [list(w) for w in table.E] == partial['E']
            assert table.events == partial['events']
            saved = [json.loads(line) for line in get(z, '/events.jsonl').splitlines()]
            saved = [e for e in saved if e['event'] == 'access_added']
            actual = [e for e in events if e['event'] == 'access_added']
            assert len(saved) == len(actual)
            for a, b in zip(saved, actual):
                for key in ('history', 'access_count', 'suffix_count'):
                    assert json.loads(json.dumps(a[key])) == json.loads(json.dumps(b[key]))
            assert stats.query_count == stats.query_actions == stats.exposures == 0
            report = dict(seed=result['seed'], camera=result['camera'], status='PASS',
                          exact_access_sequence=True, exact_suffix_sequence=True, exact_exception=True,
                          access_events=len(actual), environment_actions=0,
                          wall_seconds=time.perf_counter()-start)
            print(json.dumps(report), flush=True)
            reports.append(report)
    with (BASE/'table_replay.json').open('x') as stream:
        json.dump(reports, stream, indent=2)


if __name__ == '__main__':
    main()
