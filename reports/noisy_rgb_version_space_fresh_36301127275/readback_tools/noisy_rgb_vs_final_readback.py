"""Read-only final consistency checks and descriptive summaries."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import statistics


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--compact', type=Path, required=True)
    p.add_argument('--summary', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    summary = json.loads((args.summary/'summary.json').read_text())
    expected = {(s,c,a) for s in range(97027000,97027032) for c in ('base','shifted') for a in ('H','V')}
    records, source_maps, receipts = {}, [], []
    for f in sorted(args.compact.rglob('result.json')):
        r = json.loads(f.read_text())
        key = (r['seed'],r['camera'],r['arm'])
        assert key not in records
        records[key] = r
        hashes = json.loads((f.parent/'artifact_hashes.json').read_text())
        for local in f.parent.iterdir():
            if local.name in hashes:
                assert hashlib.sha256(local.read_bytes()).hexdigest() == hashes[local.name], local
        source = json.loads((f.parent/'source_snapshot.json').read_text())
        assert source['commit'] == 'cb61cb548f07243250b1ea07ebb0d8ff46bd9dae'
        assert source['thread_env'] == {k:'1' for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}
        source_maps.append(source['files'])
        receipt = json.loads((f.parent/'full_evidence_receipt.json').read_text(encoding='utf-8-sig'))
        assert receipt['artifact_id'] and receipt['artifact_digest']
        receipts.append(receipt)
        assert r['phase'] == 'fresh'
        if not r['status'].startswith('COMPLETED'):
            assert r['heldout'] is None and r['model_audit'] is None and r['control'] is None
    assert set(records) == expected, (expected-records.keys(), records.keys()-expected)
    assert all(s == source_maps[0] for s in source_maps)
    assert summary['expected_runs'] == summary['received_runs'] == 128
    # Preserve experimental implementation errors; do not confuse them with
    # missing/duplicate artifacts or turn them into policy outcomes.
    assert all(e['error'] == 'IMPLEMENTATION_ERROR' for e in summary['errors'])
    aggregate = {}
    metrics = ('acquisition_environment_actions','acquisition_exposure_sets','acquisition_cpu_seconds',
               'acquisition_wall_seconds','peak_memory_bytes','access_histories','nonempty_suffix_count')
    for arm in ('H','V'):
        rows = [r for (_,_,a),r in records.items() if a == arm]
        stats = {}
        for metric in metrics:
            values = [r[metric] for r in rows]
            stats[metric] = dict(mean=statistics.mean(values),median=statistics.median(values),min=min(values),max=max(values),total=sum(values))
        mechanisms = Counter()
        audits = Counter()
        for r in rows:
            mechanisms.update(r.get('mechanisms', {}))
            for k,v in r.get('acquisition_audit',{}).items():
                if isinstance(v,int):
                    audits[k] += v
        aggregate[arm] = dict(conditions=len(rows), statuses=dict(Counter(r['status'] for r in rows)),
            complete_models=sum(r['status'].startswith('COMPLETED') for r in rows),
            complete_heldout=sum((r.get('heldout') or {}).get('cases') == 5000 for r in rows),
            metrics=stats, mechanisms=dict(mechanisms), audit_totals=dict(audits))
    valid_cost_pairs = []
    excluded_cost_pairs = []
    for seed in range(97027000,97027032):
        for camera in ('base','shifted'):
            h, v = records[seed,camera,'H'], records[seed,camera,'V']
            if any(r['status'] == 'IMPLEMENTATION_ERROR' or r.get('postfreeze_error') for r in (h,v)):
                excluded_cost_pairs.append([seed,camera])
            else:
                valid_cost_pairs.append([seed,camera])
    bug_separated_costs = {}
    for metric in metrics[:5]:
        pairs = [(records[s,c,'H'][metric],records[s,c,'V'][metric]) for s,c in valid_cost_pairs]
        bug_separated_costs[metric] = dict(paired=len(pairs), H_mean=statistics.mean(h for h,v in pairs),
            V_mean=statistics.mean(v for h,v in pairs), improve=sum(v<h for h,v in pairs),
            tie=sum(v==h for h,v in pairs), worsen=sum(v>h for h,v in pairs))
    out = dict(status='READBACK_PASSED_WITH_RECORDED_IMPLEMENTATION_ERRORS' if summary['errors'] else 'READBACK_PASSED',
        experimental_errors=summary['errors'], bug_separated_costs=bug_separated_costs,
        excluded_bug_cost_pairs=excluded_cost_pairs,
        run_id=36301127275, exact_sha='cb61cb548f07243250b1ea07ebb0d8ff46bd9dae',
        expected_conditions=64, expected_runs=128, verified_compact_runs=len(records),
        identical_source_maps=True, source_files=source_maps[0], endpoints=summary['endpoints'], arms=aggregate,
        full_artifacts=receipts, notes=[
            'Full original artifacts are retained separately; compact-file hashes were checked against their own original manifests.',
            'Independent exhaustive RGB recomputation was performed on the four development V conditions, not all fresh conditions.',
            'Access histories in H and representative states in V are not the same state-count quantity.',
            'False exclusion is evaluated only where the true predictive class already has a representative.',
            'Unfinished acquisition implies unmeasured heldout accuracy, not zero accuracy.',
            'Two cameras share each world. Counts describe 64 paired conditions, not 64 independent worlds.'
        ])
    with args.output.open('x',encoding='utf-8') as stream:
        json.dump(out,stream,indent=2,allow_nan=False)
    print(json.dumps(dict(status=out['status'],arms=aggregate,endpoints=summary['endpoints']),indent=2))


if __name__ == '__main__':
    main()
