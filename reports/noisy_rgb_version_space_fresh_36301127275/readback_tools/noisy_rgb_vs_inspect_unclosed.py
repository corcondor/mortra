"""Inspect a SAVED table only. No sampler, environment or acquisition rerun."""
import argparse
import gzip
import json
from pathlib import Path
import sys

import numpy as np


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--repo', type=Path, required=True)
    p.add_argument('--saved', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    sys.path.insert(0, str(args.repo))
    from experiments.noisy_rgb_discovery.core import Emission, Statistics
    from experiments.noisy_rgb_discovery.source import table_class
    saved = args.saved
    keys = json.loads((saved/'statistics_8/statistics_index.json').read_text())
    raw = np.frombuffer(gzip.decompress((saved/'statistics_8/statistics.bin.gz').read_bytes()), '<f4').reshape(-1,2,1728)
    assert len(keys) == len(raw)
    cache = {(tuple(h),rep): Emission(x[0],x[1],8) for (h,rep),x in zip(keys,raw)}
    class FrozenStatistics(Statistics):
        def __init__(self):
            super().__init__(None)
        def summary(self, history, rep=0):
            return cache[tuple(history),rep]
    partial = json.loads((saved/'partial_table.json').read_text())
    threshold = json.loads((saved/'calibration.json').read_text())['threshold']
    table = table_class(tuple(range(5)))(FrozenStatistics(), threshold)
    table.S, table.E = [tuple(s) for s in partial['S']], [tuple(e) for e in partial['E']]
    groups = table.groups()
    ambiguous = []
    for q, group in enumerate(groups):
        h = group[0]
        for a in range(5):
            t = h+(a,)
            candidates = [i for i,g in enumerate(groups) if all(table.row_same(t,r) for r in g)]
            if len(candidates) != 1:
                ambiguous.append(dict(representative=q, history=h, action=a, extension=t,
                    extension_already_in_S=t in table.S, candidates=candidates))
    assert ambiguous
    record = dict(mode='READ_ONLY_SAVED_STATISTICS; no environment construction, sampling, learning or rerun',
        seed=97027025, camera='shifted', arm='H', threshold=threshold,
        access_histories=len(table.S), provisional_groups=len(groups), suffixes=table.E,
        unclosed_representative_extensions=ambiguous,
        reason='Frozen close_consistent only adds a nonunique extension when it is not already in S. An existing ambiguous extension can therefore survive return; machine then raises.',
        original_traceback=json.loads((saved/'result.json').read_text())['traceback'])
    with args.output.open('x', encoding='utf-8') as stream:
        json.dump(record,stream,indent=2)
    print(json.dumps(record,indent=2))


if __name__ == '__main__':
    main()
