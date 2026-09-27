"""Post-hoc replay of saved partial-table grouping, without environment queries."""
from collections import Counter
import gzip
import json
from pathlib import Path
import zipfile

import numpy as np

BASE = Path(__file__).parent/'completed'


def get(z, suffix):
    names = [n for n in z.namelist() if n.endswith(suffix)]
    assert len(names) == 1, (suffix, names)
    return z.read(names[0])


def main():
    artifacts = json.loads((BASE/'artifacts.json').read_text())['artifacts']
    reports = []
    for artifact in artifacts:
        if artifact['name'].startswith('noisy-rgb-tests-'):
            continue
        with zipfile.ZipFile(BASE/'original_artifacts'/f"{artifact['id']}.zip") as z:
            result = json.loads(get(z, '/result.json'))
            if result['status'] != 'RUN_NOT_COMPLETED':
                continue
            partial = json.loads(get(z, '/partial_table.json'))
            calibration = json.loads(get(z, '/calibration.json'))
            config = json.loads(get(z, '/config.json'))
            assert partial['E'] == [[]], 'This audit is specifically for empty-suffix closure.'
            words = [tuple(w) for w in partial['S']]
            index = json.loads(get(z, '/statistics_index.json'))
            data = np.frombuffer(gzip.decompress(get(z, '/statistics.bin.gz')), dtype='<f4').reshape(len(index), 2, -1)
            lookup = {(tuple(h), rep): i for i, (h, rep) in enumerate(index)}
            summaries = data[[lookup[(w, 0)] for w in words]]
            mean = summaries[:, 0]
            var = summaries[:, 1]/config['batch']
            threshold = calibration['threshold']
            groups = []
            zmat = np.zeros((len(words), len(words)), dtype=np.float32)
            counts = Counter()
            additions = []
            witness = None
            for i, word in enumerate(words):
                if i:
                    scores = np.sqrt(np.mean((mean[:i]-mean[i])**2/(var[:i]+var[i]+config['noise_floor']**2), axis=1))
                    zmat[i, :i] = zmat[:i, i] = scores
                matches = [j for j, g in enumerate(groups) if np.all(zmat[i, g] <= threshold)]
                if i:
                    kind = 'no_matching_group' if not matches else 'multiple_matching_groups' if len(matches)>1 else 'one_matching_group'
                    counts[kind] += 1
                    additions.append(dict(index=i, history=word, reason=kind, matches=matches))
                    if len(matches)>1 and witness is None:
                        for a in groups[matches[0]]:
                            for b in groups[matches[1]]:
                                if zmat[a, b] > threshold:
                                    witness = dict(a=words[a], bridge=word, b=words[b], threshold=threshold,
                                        z_a_bridge=float(zmat[a, i]), z_bridge_b=float(zmat[i, b]), z_a_b=float(zmat[a, b]))
                                    break
                            if witness:
                                break
                if matches:
                    groups[matches[0]].append(i)
                else:
                    groups.append([i])
            report = dict(seed=result['seed'], camera=result['camera'], status=result['status'],
                          access_histories=len(words), learned_suffixes=partial['E'],
                          suffix_events=len(partial['events']), final_provisional_groups=len(groups),
                          addition_reasons=dict(counts), nontransitivity_witness=witness,
                          environment_actions_in_this_audit=0)
            reports.append(report)
            with (BASE/f"closure_additions_{result['seed']}_{result['camera']}.json").open('x') as stream:
                json.dump(additions, stream)
            print(json.dumps(report), flush=True)
    with (BASE/'closure_diagnosis.json').open('x') as stream:
        json.dump(reports, stream, indent=2)


if __name__ == '__main__':
    main()
