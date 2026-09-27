"""Descriptive checkpoint curves; missing checkpoints remain missing."""
import argparse
from collections import Counter
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    registration=json.loads((Path(__file__).parent/'launch.json').read_text())
    expected={(s,c,a) for s in registration['seeds'] for c in registration['cameras'] for a in registration['arms']}
    found={}
    rows=[]
    for f in args.input.rglob('result.json'):
        r=json.loads(f.read_text())
        if 'phase' not in r or 'arm' not in r or 'seed' not in r:
            continue
        key=(r['seed'],r['camera'],r['arm'])
        assert key in expected and key not in found, ('Duplicate or unregistered result',key)
        found[key]=r
        for e in r.get('evaluations',[]):
            cp,a,h,c=e['checkpoint'],e['model_audit'],e['heldout'],e['control']
            rows.append(dict(seed=key[0],camera=key[1],arm=key[2],target=cp['target_exposures'],
                exposures=cp['actual_exposures'],actions=cp['environment_actions'],
                confirmed=a['confirmed_representative_count'],provisional=a['provisional_node_count'],
                confirmed_classes=a['represented_confirmed_true_classes'],provisional_classes=a['represented_provisional_true_classes'],
                union_classes=a['represented_union_true_classes'],true_classes=a['true_predictive_classes'],
                known_transitions=a['known_transitions'],transition_error=a['transition_prediction_error'],
                heldout_cases=h.get('cases',0),heldout_status=h['status'],
                candidate_coverage=h['candidate_coverage_rate'],candidate_coverage_partial=h['candidate_coverage_partial_rate'],
                wrong_unique=h['wrong_unique_rate'],unresolved=h['unresolved_rate'],
                candidate_size=h['mean_candidate_set_size'],control_status=c['status'],control_success=c['success'],
                acquisition_cpu=cp.get('acquisition_cpu_seconds'),heldout_cpu=h['cpu_seconds'],control_cpu=c['cpu_seconds'],
                peak_memory_bytes=cp.get('peak_memory_bytes')))
    result=dict(phase=registration['phase'],expected_conditions=len(expected),received_conditions=len(found),
        missing=[list(k) for k in sorted(expected-set(found))],
        status='AGGREGATION_COMPLETE' if set(found)==expected else 'INCOMPLETE',
        acquisition_statuses={arm:dict(Counter(r['status'] for k,r in found.items() if k[2]==arm)) for arm in ('V1','V2')},
        implementation_errors=[list(k) for k,r in found.items() if r['status']=='IMPLEMENTATION_ERROR' or r.get('postfreeze_error')],
        note='Resource-limited acquisitions are incomplete; provisional histories are not confirmed states; missing checkpoints not filled.',
        results=list(found.values()))
    (args.output/'summary.json').write_text(json.dumps(result,indent=2))
    if rows:
        with (args.output/'checkpoints.csv').open('w',newline='') as stream:
            writer=csv.DictWriter(stream,fieldnames=list(rows[0]))
            writer.writeheader(); writer.writerows(rows)
        for field,title in [('confirmed_classes','Confirmed represented true classes'),('union_classes','Confirmed + provisional true-class coverage'),('control_success','Partial control success')]:
            fig,ax=plt.subplots(figsize=(8,5))
            for arm,color in [('V1','#596877'),('V2','#14866d')]:
                for s,c in sorted({(r['seed'],r['camera']) for r in rows if r['arm']==arm}):
                    values=sorted([r for r in rows if (r['arm'],r['seed'],r['camera'])==(arm,s,c)],key=lambda r:r['exposures'])
                    ax.plot([r['exposures'] for r in values],[r[field] for r in values],color=color,alpha=.12)
                for target in (50000,100000,250000,500000):
                    values=[r for r in rows if r['arm']==arm and r['target']==target]
                    if values:
                        ax.scatter([target],[sum(r[field] for r in values)/len(values)],color=color,s=45,
                                   label=f'{arm} n={len(values)} at {target:,}')
            ax.set(xlabel='Acquisition exposure sets (actual checkpoint)',ylabel=title,title=registration['phase']+': '+title)
            ax.legend(fontsize=7,loc='best'); fig.tight_layout()
            fig.savefig(args.output/(field+'.png'),dpi=160); plt.close(fig)
    print(json.dumps({k:v for k,v in result.items() if k!='results'},indent=2))
    if result['missing'] or result['implementation_errors']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
