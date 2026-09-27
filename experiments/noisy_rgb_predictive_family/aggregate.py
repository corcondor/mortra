"""Report all registered development conditions without selecting outcomes."""
import argparse
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess

from .analyze import dump

CHECKPOINTS = (50000,100000,250000,500000)
METRICS = ('provisional_nodes','signature_families','represented_union_classes','confirmed_representatives',
           'exposures_per_represented_class','actions_per_represented_class','probe_count','repeated_probe_count',
           'heldout_unresolved_rate','heldout_wrong_unique_rate','wrong_empirical_merges_active',
           'wrong_empirical_merges_ever','transition_errors','control_success','acquisition_cpu_seconds','peak_memory_bytes')


def csv_write(path, rows):
    fields = list(dict.fromkeys(k for row in rows for k in row))
    with path.open('x', encoding='utf-8', newline='') as f:
        writer = csv.DictWriter(f,fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def assess(a, b):
    matched = bool(a['checkpoint_reached'] and b['checkpoint_reached'])
    benefits = {}
    for metric, sign in (('represented_union_classes',1),('exposures_per_represented_class',-1),
                         ('heldout_unresolved_rate',-1),('confirmed_representatives',1),('control_success',1)):
        x,y = a.get(metric),b.get(metric)
        benefits[metric] = sign*(float(y)-float(x))>0 if x is not None and y is not None else None
    safety_metrics = ('heldout_wrong_unique_rate','wrong_empirical_merges_active',
                      'wrong_empirical_merges_ever','transition_errors')
    safety = {k: (b[k]<=a[k] if a.get(k) is not None and b.get(k) is not None else None)
              for k in safety_metrics}
    if a.get('heldout_cases')!=5000 or b.get('heldout_cases')!=5000:
        safety['heldout_wrong_unique_rate']=None
    verdict = ('UNMATCHED_RESOURCE_CHECKPOINT' if not matched else
               'UNDETERMINED_SAFETY' if any(v is None for v in safety.values()) else
               'SAFETY_WORSENED' if not all(safety.values()) else
               'SPECIFIED_IMPROVEMENT' if any(v is True for v in benefits.values()) else
               'NO_SPECIFIED_IMPROVEMENT')
    return dict(verdict=verdict,benefits=benefits,safety=safety,
                actual_exposure_difference=b['actual_exposures']-a['actual_exposures'],
                identical_actual_exposures=b['actual_exposures']==a['actual_exposures'])


def figures(rows, pairs, out):
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    final = [r for r in rows if r['checkpoint']==500000]
    fig, axes=plt.subplots(1,3,figsize=(13,4))
    for ax,key,title in zip(axes,('provisional_nodes','signature_families','represented_union_classes'),
                            ('Provisional nodes','Exact-signature groups (A: audit only)','Represented true classes')):
        for arm,color in (('A','#167f79'),('B','#bd4a62')):
            data=[r for r in final if r['arm']==arm and r.get(key) is not None]
            ax.scatter([r['seed']-97027000+(.14 if r['camera']=='shifted' else 0) for r in data],
                       [r[key] for r in data],label=arm,s=15,color=color)
        ax.set(title=title,xlabel='Development seed offset')
        ax.legend()
    fig.suptitle('Registered 500k checkpoint; missing checkpoints remain missing')
    fig.tight_layout(); fig.savefig(out/'nodes_families_classes.png',dpi=160); plt.close(fig)
    fig,axes=plt.subplots(1,2,figsize=(10,4))
    for arm,color in (('A','#167f79'),('B','#bd4a62')):
        selected=[r for r in rows if r['seed']==97027000 and r['camera']=='base' and isinstance(r['checkpoint'],int)]
        selected=sorted((r for r in selected if r['arm']==arm),key=lambda r:r['checkpoint'])
        axes[0].plot([r['actual_exposures'] for r in selected],[r['represented_union_classes'] for r in selected],
                     marker='o',label=arm,color=color)
        axes[1].plot([r['actual_exposures'] for r in selected],[r['probe_count'] for r in selected],
                     marker='o',label=arm,color=color)
    axes[0].set(title='97027000 / base: represented classes',xlabel='Actual exposure sets')
    axes[1].set(title='97027000 / base: probe attempts',xlabel='Actual exposure sets')
    for ax in axes: ax.legend()
    fig.tight_layout(); fig.savefig(out/'first_condition_curves.png',dpi=160); plt.close(fig)
    fig,ax=plt.subplots(figsize=(9,4))
    b=[r for r in final if r['arm']=='B']
    x=list(range(len(b)))
    ax.bar(x,[r['pure_families'] for r in b],label='One true class',color='#167f79')
    ax.bar(x,[r['mixed_families'] for r in b],bottom=[r['pure_families'] for r in b],
           label='Multiple true classes',color='#bd4a62')
    ax.set(title='Post-freeze family purity; not learner merge evidence',xlabel='Available seed/camera conditions',ylabel='Families')
    ax.legend(); fig.tight_layout(); fig.savefig(out/'family_truth_redundancy.png',dpi=160); plt.close(fig)


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    conditions={}
    inputs=[]
    for path in sorted(args.input.rglob('comparison.json')):
        record=json.loads(path.read_text())
        key=(record['seed'],record['camera'])
        assert key not in conditions, ('Duplicate condition',key)
        conditions[key]=record
        inputs.append(dict(path=str(path),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    expected={(s,c) for s in range(97027000,97027032) for c in ('base','shifted')}
    assert set(conditions)<=expected
    rows=[]; pairs=[]; details=[]; missing_checkpoints=[]
    for key,condition in sorted(conditions.items()):
        arms={a['arm']:a for a in condition['arms']}
        for arm in arms.values(): rows.extend(arm['rows'])
        indexed={arm:{r['checkpoint']:r for r in record['rows']} for arm,record in arms.items()}
        for checkpoint in CHECKPOINTS:
            if any(checkpoint not in indexed[arm] for arm in ('A','B')):
                missing_checkpoints.append(dict(seed=key[0],camera=key[1],checkpoint=checkpoint,
                    missing_arms=[a for a in ('A','B') if checkpoint not in indexed[a]]))
                continue
            a,b=indexed['A'][checkpoint],indexed['B'][checkpoint]
            decision=assess(a,b)
            pair=dict(seed=key[0],camera=key[1],checkpoint=checkpoint,verdict=decision['verdict'],
                actual_exposures_A=a['actual_exposures'],actual_exposures_B=b['actual_exposures'],
                actual_exposure_difference=decision['actual_exposure_difference'])
            for metric in METRICS:
                pair[metric+'_B_minus_A']=(float(b[metric])-float(a[metric])
                    if a.get(metric) is not None and b.get(metric) is not None else None)
            pairs.append(pair)
            details.append(dict(seed=key[0],camera=key[1],checkpoint=checkpoint,**decision))
    world_rows=[]
    for seed in range(97027000,97027032):
        for checkpoint in CHECKPOINTS:
            subset=[p for p in pairs if p['seed']==seed and p['checkpoint']==checkpoint]
            row=dict(seed=seed,checkpoint=checkpoint,camera_pairs=len(subset))
            for metric in METRICS:
                values=[p[metric+'_B_minus_A'] for p in subset if p[metric+'_B_minus_A'] is not None]
                row[metric+'_B_minus_A']=statistics.mean(values) if len(values)==2 else None
            world_rows.append(row)
    csv_write(args.output/'checkpoint_metrics.csv',rows)
    csv_write(args.output/'paired_conditions.csv',pairs)
    csv_write(args.output/'world_paired_differences.csv',world_rows)
    dump(args.output/'criterion_details.json',details)
    summary=dict(status='COMPLETE' if set(conditions)==expected and not missing_checkpoints else 'INCOMPLETE',
        expected_conditions=64,available_conditions=len(conditions),missing_conditions=sorted(expected-set(conditions)),
        missing_checkpoints=missing_checkpoints,
        checkpoint_verdicts={str(c):dict(Counter(p['verdict'] for p in pairs if p['checkpoint']==c)) for c in CHECKPOINTS},
        A_reused_not_rerun=True,B_new_acquisitions=len(conditions),fresh_worlds=0,
        structural=[dict(seed=k[0],camera=k[1],**v['structural']) for k,v in sorted(conditions.items())],
        conditions=[dict(seed=k[0],camera=k[1],arm=a['arm'],status=a['acquisition_status'],
                         resource_reason=a['acquisition_resource_reason'],total_cpu_seconds=a['total_cpu_seconds'],
                         total_wall_seconds=a['total_wall_seconds'],peak_memory_bytes=a['peak_memory_bytes'])
                    for k,v in sorted(conditions.items()) for a in v['arms']],
        seed_97027000_base=[r for r in rows if r['seed']==97027000 and r['camera']=='base'],
        input_hashes=inputs,github_run=os.getenv('GITHUB_RUN_ID'),
        commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        notes=['Existing development seeds only; no confirmatory fresh claim.',
               'Family membership never licenses state identity or shared SAME certificates.',
               'A CPU is historical; B uses new hosted workers. Timing is descriptive.',
               'Avoided opportunities are schedule choices, not measured counterfactual exposure savings.',
               'Registered targets may differ by an atomic batch; actual resources are retained.',
               'Incomplete heldout observations cannot establish safety non-degradation.',
               'No algorithm adjustment or sensor-program experiment follows automatically.'])
    dump(args.output/'summary.json',summary)
    figures(rows,pairs,args.output)
    dump(args.output/'hashes.json',{str(f.relative_to(args.output)):hashlib.sha256(f.read_bytes()).hexdigest()
                                   for f in args.output.rglob('*') if f.is_file()})
    print(json.dumps(dict(status=summary['status'],available_conditions=len(conditions),
                         checkpoint_verdicts=summary['checkpoint_verdicts'])),flush=True)
    if len(conditions)!=64: raise SystemExit(1)


if __name__=='__main__':
    main()
