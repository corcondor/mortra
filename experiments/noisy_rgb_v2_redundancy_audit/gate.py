"""Wait for the unchanged development run; never cancel or relaunch it."""
import argparse
import json
from pathlib import Path
import subprocess
import time

from .artifacts import api,artifact_list,RUN,REPO,EXECUTION


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    for prefix in ('experiments/noisy_rgb_discovery','experiments/noisy_rgb_version_space','experiments/noisy_rgb_predictive_v2'):
        changed=subprocess.check_output(['git','diff','--name-only',EXECUTION,'HEAD','--',prefix],text=True)
        assert not changed, ('Acquisition/evaluation code must remain frozen',changed)
    with (args.output/'wait_log.jsonl').open('x') as log:
        while True:
            run=api(f'repos/{REPO}/actions/runs/{RUN}')
            assert run['head_sha']==EXECUTION
            status={k:run[k] for k in ('id','status','conclusion','head_sha','updated_at')}
            log.write(json.dumps(status)+'\n'); log.flush()
            if run['status']=='completed':
                break
            time.sleep(60)
    artifacts=artifact_list()
    mapping={a['name']:a for a in artifacts}
    cases=[]
    missing=[]
    for seed in range(97027000,97027032):
        for camera in ('base','shifted'):
            name=(f'pv2-full-first-{RUN}' if (seed,camera)==(97027000,'base') else f'pv2-full-{seed}-{camera}-V2-{RUN}')
            if name not in mapping:
                missing.append(dict(seed=seed,camera=camera,artifact=name))
            else:
                cases.append(dict(seed=seed,camera=camera))
    (args.output/'upstream.json').write_text(json.dumps(dict(run=status,artifacts=artifacts,missing=missing),indent=2))
    (args.output/'matrix.json').write_text(json.dumps(dict(include=cases)))
    print(json.dumps(dict(source_completed=True,available_conditions=len(cases),missing=missing,source_conclusion=run['conclusion'])))
    assert cases, 'No frozen data to audit'


if __name__=='__main__':
    main()
