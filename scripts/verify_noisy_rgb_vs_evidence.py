"""Independent post-run checks; reads archives without changing the learner."""
import argparse
from collections import Counter
import gzip
import hashlib
import json
from pathlib import Path
import zipfile

import numpy as np


class DirectoryArchive:
    def __init__(self, directory):
        self.directory = Path(directory)
    def __enter__(self):
        return self
    def __exit__(self, *args):
        pass
    def namelist(self):
        return [p.relative_to(self.directory).as_posix() for p in self.directory.rglob('*') if p.is_file()]
    def read(self, name):
        return (self.directory/name).read_bytes()
    def open(self, name):
        return (self.directory/name).open('rb')


def verify(archive):
    with (DirectoryArchive(archive) if archive.is_dir() else zipfile.ZipFile(archive)) as z:
        root = next(n[:-len('result.json')] for n in z.namelist() if n.endswith('/result.json'))
        def read(name):
            return z.read(root+name)
        result = json.loads(read('result.json'))
        hashes = json.loads(read('artifact_hashes.json'))
        for name, expected in hashes.items():
            assert hashlib.sha256(read(name)).hexdigest() == expected, name
        scores = {}
        statistics = {}
        sensors = result['acquisition_sensors']
        image_count = 0
        for sensor in sensors:
            namespace = sensor['namespace']
            if namespace == 'calibration-v1':
                folder, n = 'calibration', 8
            elif namespace == 'training-v1':
                n = 8
                folder = 'training' if result['arm'] == 'H' else 'training_8'
            else:
                n = int(namespace.split('-')[-2])
                folder = 'training_'+str(n)
            means = {}
            metadata = gzip.decompress(read(folder+'/queries.jsonl.gz')).splitlines()
            with z.open(root+folder+'/raw.rgb.gz') as raw, gzip.GzipFile(fileobj=raw) as stream:
                for line in metadata:
                    row = json.loads(line)
                    rgb = np.frombuffer(stream.read(int(np.prod(row['shape']))), np.uint8).reshape(row['shape'])
                    assert len(rgb) == n
                    for exposure, expected in zip(rgb, row['raw_hashes']):
                        assert hashlib.sha256(exposure.tobytes()).hexdigest() == expected
                    image_count += len(rgb)
                    x = rgb.reshape(len(rgb), -1).astype(np.float32)/255.
                    means[tuple(row['history']), row['replicate']] = (x.mean(0), x.var(0, ddof=1), len(x))
                assert not stream.read(1)
            if namespace == 'calibration-v1':
                calibration = json.loads(read('calibration.json'))
                cal_scores = []
                for history in calibration['histories']:
                    a, b = means[tuple(history), 0], means[tuple(history), 1]
                    cal_scores.append(float(np.sqrt(np.mean((a[0]-b[0])**2/(a[1]/a[2]+b[1]/b[2]+.01**2)))))
                assert cal_scores == calibration['scores']
                assert max(cal_scores)*1.18 == calibration['threshold']
                continue
            keys = json.loads(read(f'statistics_{n}/statistics_index.json'))
            dim = 4*12*12*3
            saved = np.frombuffer(gzip.decompress(read(f'statistics_{n}/statistics.bin.gz')), '<f4').reshape(-1, 2, dim)
            assert len(keys) == len(means) == len(saved)
            for key, value in zip(keys, saved):
                h, rep = tuple(key[0]), key[1]
                m, v, _ = means[h, rep]
                assert np.array_equal(value[0], m) and np.array_equal(value[1], v)
            statistics[n] = means
        counts = Counter()
        certificates = {}
        reps = [()]
        suffixes = [()]
        memberships = {}
        for line in gzip.decompress(read('events.jsonl.gz')).splitlines():
            r = json.loads(line)
            counts[r['event']] += 1
            if r['event'] == 'comparison':
                assert result['arm'] == 'V'
                h, k = map(tuple, r['pair'])
                values = []
                for n in (8, 16, 32):
                    if n > r['stage']:
                        break
                    for rep in (0, 1):
                        a, b = statistics[n][h, rep], statistics[n][k, rep]
                        den = a[1]/a[2]+b[1]/b[2]+.01**2
                        values.append(float(np.sqrt(np.mean((a[0]-b[0])**2/den))))
                assert values == r['scores']
                lo, hi = min(values), max(values)
                outcome = 'UNRESOLVED'
                if r['stage'] == 32:
                    if hi+(hi-lo) < r['threshold']:
                        outcome = 'SAME'
                    elif max(0., lo-(hi-lo)) > r['threshold']:
                        outcome = 'DIFFERENT'
                assert outcome == r['result']
                certificates[r['id']] = r
            elif r['event'] == 'state_added':
                assert r['reason'] == 'all_representatives_confirmed_different_32'
                assert r['state'] == len(reps)
                assert len(r['evidence']) == len(reps)
                assert {x['q'] for x in r['evidence']} == set(range(len(reps)))
                for item in r['evidence']:
                    c = certificates[item['certificate']]
                    assert c['stage'] == 32 and c['result'] == 'DIFFERENT'
                    words = sorted([tuple(r['history'])+tuple(item['suffix']), reps[item['q']]+tuple(item['suffix'])])
                    assert words == list(map(tuple, c['pair']))
                reps.append(tuple(r['history']))
            elif r['event'] == 'candidate_set':
                assert r['representative_count'] == len(reps)
                assert set(r['candidates']) | {x['q'] for x in r['exclusions']} == set(range(len(reps)))
                assert not (set(r['candidates']) & {x['q'] for x in r['exclusions']})
                for item in r['exclusions']:
                    c = certificates[item['certificate']]
                    assert c['result'] == 'DIFFERENT' and c['stage'] == 32
                memberships[tuple(r['history'])] = r
            elif r['event'] == 'suffix_added':
                assert tuple(r['suffix']) not in suffixes and 0 < len(r['suffix']) <= 2
                c = certificates[r['certificate']]
                assert c['result'] == 'DIFFERENT' and c['stage'] == 32
                words = sorted([tuple(r['history_a'])+tuple(r['suffix']), tuple(r['history_b'])+tuple(r['suffix'])])
                assert words == list(map(tuple, c['pair']))
                assert 'DIFFERENT' not in r['previous_results']
                suffixes.append(tuple(r['suffix']))
            elif r['event'] == 'active_probe':
                options = [(float(s), tuple(e)) for s, e in r['candidate_scores']]
                assert min(options) == (r['score'], tuple(r['selected']))
            elif r['event'] == 'unresolved':
                assert len(r['candidates']) > 1
                assert all(0 < len(e) <= 2 for e in r['tested_probes'])
        if result['arm'] == 'V':
            table = json.loads(read('partial_table.json'))
            assert reps == list(map(tuple, table['S']))
            assert suffixes == list(map(tuple, table['E']))
        digest = None
        if archive.is_file():
            with archive.open('rb') as stream:
                digest = hashlib.file_digest(stream, 'sha256').hexdigest()
        return dict(archive=str(archive), archive_sha256=digest,
                    seed=result['seed'], camera=result['camera'], arm=result['arm'],
                    passed=True, saved_file_hashes=len(hashes), recomputed_exposure_sets=image_count,
                    recomputed_statistics=sum(map(len, statistics.values())), event_counts=dict(counts),
                    certificates_recomputed=len(certificates), numpy=np.__version__)


def main():
    p = argparse.ArgumentParser()
    p.add_argument('archives', type=Path, nargs='+')
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    records = []
    for archive in args.archives:
        row = verify(archive)
        records.append(row)
        print(json.dumps(row), flush=True)
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(records, stream, indent=2)


if __name__ == '__main__':
    main()
