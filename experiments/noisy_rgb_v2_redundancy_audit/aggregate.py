import argparse
from collections import Counter
import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np


def latest(row):
    return max(row['checkpoints'],key=lambda a:(a['checkpoint']['actual_exposures'],a['checkpoint']['target_exposures']=='final'))


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--development-summary',type=Path)
    args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    rows=[json.loads(f.read_text()) for f in args.input.rglob('summary.json')]
    rows=[r for r in rows if r.get('mode')=='POST_FREEZE_READ_ONLY']
    expected={(s,c) for s in range(97027000,97027032) for c in ('base','shifted')}
    assert len(rows)==len({(r['seed'],r['camera']) for r in rows})
    assert all((r['seed'],r['camera']) in expected for r in rows)
    worlds={}
    for r in rows:
        key=r['seed']
        if key in worlds:
            assert worlds[key]['depth_ceiling']==r['depth_ceiling']
        else:
            worlds[key]=r
    node_flags,pair_flags,joint,dstar=Counter(),Counter(),Counter(),Counter()
    totals=Counter()
    records=[]
    for r in rows:
        a=latest(r)
        node_flags.update(a['node_flags']); pair_flags.update(a['pair_summary']); joint.update(a['joint_node_blockers'])
        for k in ('provisional_count','within_true_class_redundant_histories','provisional_in_unrepresented_classes',
                  'provisional_in_represented_classes','probe_progress_entries_cleared_by_promotion'):
            totals[k]+=a[k]
        for cp in r['checkpoints']:
            records.append(dict(seed=r['seed'],camera=r['camera'],target=cp['checkpoint']['target_exposures'],
                exposures=cp['checkpoint']['actual_exposures'],q2=r['depth_ceiling']['q2'],q_infinity=r['depth_ceiling']['q_infinity'],
                provisional=cp['provisional_count'],confirmed=cp['confirmed_representatives'],
                provisional_true_classes=cp['represented_provisional_classes'],
                confirmed_true_classes=cp['represented_confirmed_classes'],union_true_classes=cp['represented_union_classes'],
                redundant_same_class_histories=cp['within_true_class_redundant_histories'],
                unrepresented_class_histories=cp['provisional_in_unrepresented_classes'],
                candidate_buckets=cp['candidate_buckets']['bucket_count'],outcome_buckets=cp['outcome_buckets']['bucket_count'],
                literal_buckets=cp['literal_certificate_buckets']['bucket_count'],
                any_unmeasured=cp['node_flags'].get('any_NOT_COMPARED',0),any_measured_unresolved=cp['node_flags'].get('any_measured_UNRESOLVED',0),
                own_outgoing_incomplete=cp['node_flags'].get('own_outgoing_incomplete',0),
                correct_match_blocked_by_other=cp['node_flags'].get('some_correct_match_passes_but_other_candidate_blocks',0),
                noise_only_pairs=cp['pair_summary'].get('same_class_statistical_rule_only_blocker_pairs',0)))
    for r in worlds.values():
        dstar.update(r['depth_ceiling']['d_star_histogram'])
    first=next((r for r in rows if (r['seed'],r['camera'])==(97027000,'base')),None)
    first_record=dict(depth_ceiling=first['depth_ceiling'],latest=latest(first)) if first else None
    if first_record and args.development_summary and args.development_summary.exists():
        development=json.loads(args.development_summary.read_text())
        baseline=next((r for r in development['results'] if (r['seed'],r['camera'],r['arm'])==(97027000,'base','V1')),None)
        if baseline and baseline.get('evaluations'):
            first_record['saved_V1_latest']=max(baseline['evaluations'],key=lambda e:(e['checkpoint']['actual_exposures'],e['checkpoint']['target_exposures']=='final'))
    summary=dict(status='COMPLETE' if len(rows)==64 else 'INCOMPLETE',conditions=len(rows),expected_conditions=64,
        missing=[list(k) for k in sorted(expected-{(r['seed'],r['camera']) for r in rows})],worlds=len(worlds),
        q2_equals_q_infinity_worlds=sum(r['depth_ceiling']['q2']==r['depth_ceiling']['q_infinity'] for r in worlds.values()),
        world_depth_ceilings={str(s):r['depth_ceiling'] for s,r in sorted(worlds.items())},
        distinguishing_depth_histogram_by_world=dict(dstar),latest_snapshot_totals=dict(totals),
        latest_node_flags=dict(node_flags),latest_pair_summary=dict(pair_flags),latest_joint_blockers=dict(joint),
        first_condition=first_record,new_sensor_calls=sum(r['new_sensor_calls'] for r in rows),
        new_exposures=0,learner_updates=0,
        offline_pure_transition_evaluations=sum(r['offline_pure_transition_evaluations'] for r in rows),
        note='Clean-output structural depths, not exact noisy-distribution equivalence. Diagnostic flags overlap. No new design or fresh run.',
        source_run=36309862254)
    (args.output/'summary.json').write_text(json.dumps(summary,indent=2))
    if records:
        with (args.output/'checkpoint_diagnostics.csv').open('w',newline='') as stream:
            w=csv.DictWriter(stream,fieldnames=list(records[0])); w.writeheader(); w.writerows(records)
    if worlds:
        fig,ax=plt.subplots(figsize=(8,5))
        for seed,r in sorted(worlds.items()):
            ax.plot(range(7),r['depth_ceiling']['q_by_depth'],alpha=.35,color='#167568')
        ax.set(xlabel='Offline distinguishing depth',ylabel='Clean-output + public-label classes',title=f'Structural ceilings: {len(worlds)} worlds')
        ax.axvline(2,color='#bf453e',linestyle='--',label='Frozen learner probe depth 2'); ax.legend()
        fig.tight_layout(); fig.savefig(args.output/'depth_ceiling.png',dpi=160); plt.close(fig)
    if rows:
        fig,axes=plt.subplots(1,2,figsize=(12,5))
        ordered=sorted(rows,key=lambda r:(r['seed'],r['camera']))
        axes[0].bar(range(len(rows)),[latest(r)['provisional_count'] for r in ordered],color='#be544b',label='Provisional histories')
        axes[0].bar(range(len(rows)),[latest(r)['represented_provisional_classes'] for r in ordered],color='#147d72',label='Distinct true classes touched')
        axes[0].set(xlabel='Seed-camera condition (seed order, base then shifted)',ylabel='Count',title=f'Latest snapshots: {len(rows)}/64 conditions'); axes[0].legend(fontsize=8)
        if first:
            sizes=sorted([c['provisional_count'] for c in latest(first)['provisional_per_true_class']],reverse=True)
            axes[1].bar(range(len(sizes)),sizes,color='#465dab')
            axes[1].set(xlabel='True class ranked by history count',ylabel='Provisional histories',title='97027000/base only')
        fig.tight_layout(); fig.savefig(args.output/'provisional_redundancy.png',dpi=160); plt.close(fig)
        fields=[('any_NOT_COMPARED','Unmeasured test'),('any_measured_UNRESOLVED','Measured unresolved'),
                ('own_outgoing_incomplete','Outgoing actions incomplete'),('any_missing_public_label','Public label missing'),
                ('some_correct_match_passes_but_other_candidate_blocks','Correct match blocked by other candidate'),
                ('all_candidates_eligible_but_not_committed','Eligible but not committed')]
        fig,ax=plt.subplots(figsize=(10,5))
        ax.barh([label for key,label in fields],[node_flags[key] for key,label in fields],color='#40698e')
        ax.set(xlabel='Provisional histories (overlapping flags)',title='Recorded merge blockers, latest snapshots')
        ax.invert_yaxis(); fig.tight_layout(); fig.savefig(args.output/'merge_blockers.png',dpi=160); plt.close(fig)
        suffixes=Counter()
        for r in rows:
            for word,c in latest(r)['suffix_outcomes'].items():
                suffixes[word]+=c.get('same_true_class_UNRESOLVED',0)
        values=np.array([[suffixes[str((a,b))] for b in range(5)] for a in range(5)])
        fig,ax=plt.subplots(figsize=(6,5)); im=ax.imshow(values,cmap='YlOrRd')
        for a in range(5):
            for b in range(5): ax.text(b,a,str(values[a,b]),ha='center',va='center',fontsize=8)
        ax.set(xlabel='Second opaque action ID',ylabel='First opaque action ID',title='Same-true-class measured UNRESOLVED pairs')
        fig.colorbar(im,ax=ax); fig.tight_layout(); fig.savefig(args.output/'suffix_unresolved.png',dpi=160); plt.close(fig)
    print(json.dumps({k:v for k,v in summary.items() if k not in ('first_condition','world_depth_ceilings','latest_joint_blockers')},indent=2))
    if summary['missing']:
        raise SystemExit(1)


if __name__=='__main__':
    main()
