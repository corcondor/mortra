"""Read completed immutable artifacts; never change or restart the experiment."""
import gzip
import hashlib
import io
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import numpy as np

REPO = Path('C:/Users/81808/.openclaw/workspace/mortra-v2-online-feedback-20260928')
sys.path.insert(0, str(REPO))
from experiments.v2_online_feedback.prepare import download, write

RUN = 36293621710
OUTPUT = Path(__file__).parent / 'completed'


def api(route):
    return json.loads(subprocess.check_output(['gh', 'api', route], text=True, encoding='utf-8'))


def entry(archive, suffix):
    found = [n for n in archive.namelist() if n.endswith(suffix)]
    assert len(found) == 1, (suffix, found)
    return found[0]


def read(archive, suffix):
    return json.loads(archive.read(entry(archive, suffix)))


def audit_raw(archive, phase):
    paths = [n for n in archive.namelist() if n.endswith(f'/{phase}/queries.jsonl.gz')]
    if not paths:
        return None
    queries = actions = exposures = duplicate = 0
    hashes = set()
    summaries = {}
    with archive.open(paths[0]) as qz, archive.open(entry(archive, f'/{phase}/raw.rgb.gz')) as rz:
        with gzip.GzipFile(fileobj=qz) as qstream, gzip.GzipFile(fileobj=rz) as rstream:
            for line in qstream:
                row = json.loads(line)
                assert row['query'] == queries
                nbytes = int(np.prod(row['shape']))
                data = rstream.read(nbytes)
                assert len(data) == nbytes
                x = np.frombuffer(data, dtype=np.uint8).reshape(row['shape'])
                for image, expected in zip(x, row['raw_hashes']):
                    h = hashlib.sha256(image.tobytes()).hexdigest()
                    assert h == expected
                    duplicate += h in hashes
                    hashes.add(h)
                if phase == 'training':
                    normalized = x.reshape(len(x), -1).astype(np.float32)/255.
                    summaries[(tuple(row['history']), row['replicate'])] = np.stack([
                        normalized.mean(0), normalized.var(0, ddof=1)])
                queries += 1
                actions += len(row['history'])
                exposures += len(x)
            assert rstream.read(1) == b''
    result = dict(queries=queries, environment_actions=actions, exposures=exposures,
                  exact_duplicate_exposures=duplicate, raw_hash_verification='PASS')
    if phase == 'training':
        index_names = [n for n in archive.namelist() if n.endswith('/statistics_index.json')]
        if index_names:
            index = json.loads(archive.read(index_names[0]))
            with archive.open(entry(archive, '/statistics.bin.gz')) as z:
                with gzip.GzipFile(fileobj=z) as stream:
                    for history, rep in index:
                        expected = summaries[(tuple(history), rep)]
                        actual = np.frombuffer(stream.read(expected.nbytes), dtype='<f4').reshape(expected.shape)
                        assert np.array_equal(actual, expected)
                    assert stream.read(1) == b''
            result['summary_recomputation'] = dict(status='PASS', summaries=len(index))
    return result


def main():
    run = api(f'repos/corcondor/mortra/actions/runs/{RUN}')
    assert run['status'] == 'completed'
    OUTPUT.mkdir(exist_ok=False)
    artifacts = api(f'repos/corcondor/mortra/actions/runs/{RUN}/artifacts?per_page=100')
    write(OUTPUT/'github_run.json', run)
    write(OUTPUT/'artifacts.json', artifacts)
    write(OUTPUT/'jobs.json', api(f'repos/corcondor/mortra/actions/runs/{RUN}/jobs?per_page=100'))
    reports = []
    for artifact in artifacts['artifacts']:
        path = OUTPUT/'original_artifacts'/f"{artifact['id']}.zip"
        download(artifact, path)
        print('downloaded and digest verified', artifact['name'], flush=True)
        with zipfile.ZipFile(path) as archive:
            destination = OUTPUT/'extracted'/artifact['name']
            for name in archive.namelist():
                if name.endswith('/') or name.endswith(('/raw.rgb.gz', '/statistics.bin.gz')):
                    continue
                target = destination/name
                assert target.resolve().is_relative_to(destination.resolve())
                target.parent.mkdir(parents=True, exist_ok=True)
                with target.open('xb') as stream:
                    stream.write(archive.read(name))
            if artifact['name'].startswith('noisy-rgb-tests-'):
                continue
            result = read(archive, '/result.json')
            source = read(archive, '/source_snapshot.json')
            assert source['commit'] == run['head_sha']
            checks = {p: audit_raw(archive, p) for p in ('calibration', 'training', 'heldout')}
            for acquisition in result['acquisition_sensors']:
                phase = acquisition['namespace'].split('-')[0]
                for field in ('queries', 'environment_actions', 'exposures', 'exact_duplicate_exposures'):
                    assert checks[phase][field] == acquisition[field]
            if 'heldout' in result:
                for field in ('queries', 'environment_actions', 'exposures', 'exact_duplicate_exposures'):
                    assert checks['heldout'][field] == result['heldout']['sensor'][field]
                with gzip.GzipFile(fileobj=io.BytesIO(archive.read(entry(archive, '/heldout_cases.jsonl.gz')))) as stream:
                    rows = [json.loads(line) for line in stream]
                assert len(rows) == 5000 and len({(r['episode'],r['step']) for r in rows}) == 5000
                for label in ('adaptive_suffixes', 'empty_suffix_readout'):
                    expected = result['heldout'][label]
                    assert sum(r[label]['correct'] for r in rows) == expected['correct']
                    assert sum(r[label]['predicted'] is None for r in rows) == expected['unresolved']
                checks['heldout_counts'] = 'PASS'
            reports.append(dict(result=result, checks=checks, artifact=artifact['name']))
            print(json.dumps(dict(seed=result['seed'], camera=result['camera'], status=result['status'], checks=checks)), flush=True)
    write(OUTPUT/'verified_results.json', reports)


if __name__ == '__main__':
    main()
