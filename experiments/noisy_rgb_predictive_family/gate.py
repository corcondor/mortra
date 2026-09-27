"""Source integrity and availability gate; never rerun A."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import time

from experiments.noisy_rgb_v2_redundancy_audit.artifacts import api, artifact_list, RUN, EXECUTION

PROTECTED = ('experiments/noisy_rgb_predictive_v2', 'experiments/noisy_rgb_version_space',
             'experiments/noisy_rgb_discovery', 'scripts/evaluate_autonomous_game_design_loop.py')


def verify_sources():
    difference = subprocess.check_output(['git', 'diff', EXECUTION, '--', *PROTECTED], text=True)
    assert not difference, 'Frozen acquisition/evaluation source differs'
    return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
            for directory in PROTECTED for p in
            ([Path(directory)] if Path(directory).is_file() else Path(directory).rglob('*.py'))}


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    args.output.mkdir(parents=True, exist_ok=False)
    hashes = verify_sources()
    while True:
        run = api(f'repos/corcondor/mortra/actions/runs/{RUN}')
        assert run['head_sha'] == EXECUTION
        print(json.dumps(dict(source_run=RUN, status=run['status'], conclusion=run['conclusion'])), flush=True)
        if run['status'] == 'completed':
            break
        time.sleep(60)
    artifacts = artifact_list()
    names = {a['name']: a for a in artifacts if not a['expired']}
    matrix = []
    sources = []
    for seed in range(97027000, 97027032):
        for camera in ('base', 'shifted'):
            name = (f'pv2-full-first-{RUN}' if (seed, camera) == (97027000, 'base') else
                    f'pv2-full-{seed}-{camera}-V2-{RUN}')
            assert name in names, ('Saved A artifact unavailable; do not substitute/rerun', name)
            matrix.append(dict(seed=seed, camera=camera))
            sources.append({k: names[name][k] for k in ('id', 'name', 'digest', 'size_in_bytes')})
    record = dict(commit=subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip(),
                  source_run=run, sources=sources, frozen_file_sha256=hashes,
                  acquisition_A_rerun=False, cases=len(matrix))
    (args.output/'preflight.json').write_text(json.dumps(record, indent=2), encoding='utf-8')
    (args.output/'matrix.json').write_text(json.dumps(dict(include=matrix)), encoding='utf-8')


if __name__ == '__main__':
    main()
