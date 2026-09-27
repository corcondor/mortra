"""Audit frozen snapshots after the entire upstream development run ends."""
import argparse
import gzip
import hashlib
import json
from pathlib import Path
import platform
import subprocess
import sys
import time

from .artifacts import RUN,EXECUTION
from .quotient import analyze_table,partitions
from .truth_table import static_table
from .redundancy import EventPrefix,checkpoint_audit


def write(path,value):
    with path.open('x',encoding='utf-8') as stream:
        json.dump(value,stream,indent=2,allow_nan=False)


def audit_condition(input_root,output):
    download=json.loads((input_root/'download_manifest.json').read_text())
    assert download['upstream']['status']=='completed' and download['upstream']['id']==RUN
    assert download['upstream']['head_sha']==EXECUTION and download['all_selected_member_hashes_verified']
    folder=next(p.parent for p in input_root.glob('*/source_snapshot.json'))
    source=json.loads((folder/'source_snapshot.json').read_text())
    assert source['commit']==EXECUTION
    for name,entry in download['members'].items():
        assert hashlib.sha256((input_root/name).read_bytes()).hexdigest()==entry['sha256']
    output.mkdir(parents=True,exist_ok=False)
    result=json.loads((folder/'result.json').read_text())
    seed,camera=result['seed'],result['camera']
    start,cpu=time.perf_counter(),time.process_time()
    table=static_table(seed)
    outputs=list(zip(table['observations'],table['public_goal']))
    structural,layers,pairs=analyze_table(table['transitions'],outputs)
    structural['q_infinity_original_RGB_only']=len(set(partitions(table['transitions'],table['observations'])[-1]))
    structural['scope']=table['scope']
    write(output/'truth_table.json',table)
    write(output/'depth_ceiling.json',structural)
    with gzip.open(output/'minimum_distinguishing_depths.jsonl.gz','wt',encoding='utf-8') as stream:
        for row in pairs:
            stream.write(json.dumps(row)+'\n')
    checkpoints=[]
    for f in folder.glob('checkpoint_*/checkpoint.json'):
        meta=json.loads(f.read_text())
        checkpoints.append((meta['event_prefix_count'],f.parent,meta))
    checkpoints.sort(key=lambda x:(x[0],x[2]['actual_exposures']))
    prefix=EventPrefix()
    summaries=[]
    def process(checkpoint,meta):
        saved=json.loads((checkpoint/'state.json').read_text())
        keys={n:{(tuple(h),j) for h,j in json.loads((checkpoint/f'statistics_{n}'/'statistics_index.json').read_text())}
              for n in (8,16,32)}
        destination=output/checkpoint.name
        destination.mkdir()
        with gzip.open(destination/'provisional_nodes.jsonl.gz','wt',encoding='utf-8') as nodes, \
             gzip.open(destination/'merge_gate_pairs.jsonl.gz','wt',encoding='utf-8') as pairs_out:
            audit=checkpoint_audit(saved,meta,prefix,table,layers,keys,
                lambda row:nodes.write(json.dumps(row)+'\n'),lambda row:pairs_out.write(json.dumps(row)+'\n'))
        # Reconcile cardinalities without comparing arbitrary truth-class IDs.
        old=next((e for e in result.get('evaluations',[]) if e['checkpoint']['event_prefix_count']==meta['event_prefix_count']),None)
        if old is not None:
            a=old['model_audit']
            assert audit['provisional_count']==a['provisional_node_count']
            assert audit['confirmed_representatives']==a['confirmed_representative_count']
            assert structural['q_infinity_original_RGB_only']==a['true_predictive_classes']
            audit['original_evaluation']=dict(model_audit=a,heldout=old['heldout'],control=old['control'])
        write(destination/'audit.json',audit)
        summaries.append(audit)
        print(json.dumps(dict(event='checkpoint_audited',seed=seed,camera=camera,checkpoint=checkpoint.name,
                              provisional=audit['provisional_count'],q2=structural['q2'],q_infinity=structural['q_infinity'])),flush=True)
    pointer=0
    with gzip.open(folder/'events.jsonl.gz','rt',encoding='utf-8') as stream:
        for line in stream:
            row=json.loads(line)
            while pointer<len(checkpoints) and row['event_index']>checkpoints[pointer][0]:
                _,checkpoint,meta=checkpoints[pointer]
                process(checkpoint,meta); pointer+=1
            prefix.accept(row)
    while pointer<len(checkpoints):
        _,checkpoint,meta=checkpoints[pointer]
        process(checkpoint,meta); pointer+=1
    final=dict(seed=seed,camera=camera,source_run=RUN,source_execution=EXECUTION,
               mode='POST_FREEZE_READ_ONLY',depth_ceiling=structural,checkpoints=summaries,
               new_sensor_calls=0,new_exposures=0,interactive_environment_actions=0,learner_updates=0,
               offline_pure_transition_evaluations=table['offline_pure_transition_evaluations'],
               cpu_seconds=time.process_time()-cpu,wall_seconds=time.perf_counter()-start,
               download_manifest=download,
               claims=['Structural Q2 uses deterministic clean four-view outputs and public goal labels.',
                       'It is not an exact noisy-distribution quotient or a finite-sample statistical guarantee.',
                       'Unmeasured and measured UNRESOLVED evidence are kept separate.',
                       'No V2.1, new seed, changed threshold, deeper learner probe or sensor program is executed.'])
    write(output/'summary.json',final)
    write(output/'audit_source.json',dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        python=sys.version,platform=platform.platform(),command=sys.argv,
        files={str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in Path(__file__).parent.glob('*.py')}))
    write(output/'hashes.json',{str(p.relative_to(output)):hashlib.sha256(p.read_bytes()).hexdigest()
                              for p in output.rglob('*') if p.is_file()})


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    audit_condition(args.input,args.output)


if __name__=='__main__':
    main()
