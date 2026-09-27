import argparse
import csv
import hashlib
import json
from pathlib import Path

from experiments.noisy_rgb_discovery.run import write


def aggregate(root, output, phase):
    files = sorted(root.rglob('result.json'))
    records = {}
    for f in files:
        row = json.loads(f.read_text())
        key = (row['seed'], row['camera'], row['arm'])
        if key in records:
            raise AssertionError(('duplicate acquisition key', key))
        records[key] = row
    seeds = [95027004, 95027005] if phase == 'development' else list(range(97027000, 97027032))
    expected = {(s, c, a) for s in seeds for c in ('base', 'shifted') for a in ('H', 'V')}
    output.mkdir(parents=True, exist_ok=False)
    errors = []
    for key in sorted(expected-records.keys()):
        errors.append(dict(key=key, error='MISSING_RUN; infrastructure/not_completed, not policy failure'))
    for key, row in records.items():
        if key not in expected:
            errors.append(dict(key=key, error='UNEXPECTED_RUN'))
        if row['status'] == 'IMPLEMENTATION_ERROR' or row.get('postfreeze_error'):
            errors.append(dict(key=key, error='IMPLEMENTATION_ERROR', traceback=row.get('traceback', row.get('postfreeze_error'))))
        if phase == 'development' and row['arm'] == 'H' and not row.get('old_reproduction', {}).get('passed'):
            errors.append(dict(key=key, error='OLD_REPRODUCTION_MISMATCH', details=row.get('old_reproduction')))
        if row['arm'] == 'V':
            m = row.get('mechanisms', {})
            if phase == 'development':
                if not m.get('UNRESOLVED_comparisons', 0):
                    errors.append(dict(key=key, error='NO_UNRESOLVED_COMPARISON_EVIDENCE'))
                if not m.get('probe_depth_1', 0):
                    errors.append(dict(key=key, error='NO_ACTIVE_PROBE_RECORDED'))
                if not all(any(s['namespace'] == ns and s['queries'] > 0 for s in row.get('acquisition_sensors', []))
                           for ns in ('vs-training-16-v1', 'vs-training-32-v1')):
                    errors.append(dict(key=key, error='NO_ACTUAL_RESAMPLING'))
    rows, endpoints = [], {}
    directions = dict(completed=1, wrong_unique=-1, unresolved=-1, transition_error=-1, actions=-1)
    for seed in seeds:
        for camera in ('base', 'shifted'):
            row = dict(seed=seed, camera=camera)
            values = {}
            for arm in ('H', 'V'):
                r = records.get((seed, camera, arm), {})
                completed = r.get('status', '').startswith('COMPLETED')
                h, a = r.get('heldout') or {}, r.get('model_audit') or {}
                v = dict(completed=int(completed) if r else None,
                    wrong_unique=h.get('wrong_unique_rate'), unresolved=h.get('unresolved_rate'),
                    transition_error=a.get('predictive_transition_error'), actions=r.get('acquisition_environment_actions'))
                values[arm] = v
                row.update({arm+'_'+k: value for k, value in v.items()})
                row.update({arm+'_'+k: r.get(k) for k in ('status', 'access_histories', 'nonempty_suffix_count',
                    'acquisition_exposure_sets', 'acquisition_cpu_seconds', 'acquisition_wall_seconds', 'peak_memory_bytes')})
                row[arm+'_learned_states'] = a.get('learned_states')
                row[arm+'_control_success'] = (r.get('control') or {}).get('control_success')
            for metric, direction in directions.items():
                h, v = values['H'][metric], values['V'][metric]
                if h is None or v is None:
                    row[metric+'_comparison'] = 'NOT_PAIRED_EVALUABLE'
                    continue
                d = v-h
                label = 'tie' if d == 0 else ('improve' if direction*d > 0 else 'worsen')
                row[metric+'_comparison'] = label
                endpoint = endpoints.setdefault(metric, dict(paired=0, improve=0, tie=0, worsen=0, H=[], V=[]))
                endpoint['paired'] += 1
                endpoint[label] += 1
                endpoint['H'].append(h)
                endpoint['V'].append(v)
            rows.append(row)
    for endpoint in endpoints.values():
        for arm in ('H', 'V'):
            endpoint[arm+'_mean'] = sum(endpoint[arm])/len(endpoint[arm])
    summary = dict(phase=phase, expected_runs=len(expected), received_runs=len(records),
        expected_world_camera_conditions=len(seeds)*2, completion_by_arm={
            a: sum(r['status'].startswith('COMPLETED') for (_, _, b), r in records.items() if b == a) for a in ('H', 'V')},
        development_gate_passed=(phase == 'development' and not errors), errors=errors, endpoints=endpoints,
        accuracy_rule='incomplete is null; each paired metric has its own explicit denominator',
        independence='paired world-camera description; two cameras share each world',
        source_artifacts={str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest() for f in files})
    write(output/'summary.json', summary)
    write(output/'all_results.json', list(records.values()))
    with (output/'paired_conditions.csv').open('x', newline='', encoding='utf-8') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(json.dumps(summary, indent=2))
    return summary


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--input', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--phase', choices=['development', 'fresh'], required=True)
    args = p.parse_args()
    result = aggregate(args.input, args.output, args.phase)
    if result['errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
