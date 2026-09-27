"""Fail closed before development acquisition; emit the complete fixed matrix."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess

BASE='cb61cb548f07243250b1ea07ebb0d8ff46bd9dae'


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    root=Path(__file__).parent
    registration=json.loads((root/'launch.json').read_text())
    report=Path('reports/noisy_rgb_predictive_v2_diagnosis_36308147477/diagnosis_summary.json')
    rows=json.loads(report.read_text(encoding='utf-8-sig'))
    assert len(rows)==len({(r['seed'],r['camera']) for r in rows})==64
    assert {(r['seed'],r['camera']) for r in rows}=={(s,c) for s in range(97027000,97027032) for c in ('base','shifted')}
    assert all(r['passed'] and r['new_sensor_operations']==0 for r in rows)
    paths=subprocess.check_output(['git','ls-tree','-r','--name-only',BASE,'experiments/noisy_rgb_discovery','experiments/noisy_rgb_version_space'],text=True).splitlines()
    paths.append('scripts/evaluate_autonomous_game_design_loop.py')
    hashes={}
    for name in paths:
        if not name.endswith(('.py','.json','.md')):
            continue
        expected=subprocess.check_output(['git','rev-parse',BASE+':'+name],text=True).strip()
        actual=subprocess.check_output(['git','hash-object',name],text=True).strip()
        assert actual==expected, ('Frozen source changed',name)
        hashes[name]=dict(git_blob=actual,working_bytes_sha256=hashlib.sha256(Path(name).read_bytes()).hexdigest())
    result=dict(passed=True,old_source_unchanged=True,frozen_source=hashes,
                diagnostic_summary_sha256=hashlib.sha256(report.read_bytes()).hexdigest(),registration=registration)
    (args.output/'gate.json').write_text(json.dumps(result,indent=2))
    first=registration['first_condition']
    cases=[dict(seed=s,camera=c,arm=a) for s in registration['seeds'] for c in registration['cameras'] for a in registration['arms']]
    assert first in cases and len(cases)==len({tuple(x.values()) for x in cases})
    (args.output/'matrix.json').write_text(json.dumps(dict(include=[x for x in cases if x!=first])))
    (args.output/'first.json').write_text(json.dumps(first))
    print(json.dumps(dict(passed=True,cases=len(cases),diagnostic_run=registration['diagnostic_run_id'])))


if __name__=='__main__':
    main()
