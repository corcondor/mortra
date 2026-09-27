"""V1/V2 acquisition with serialized, separately evaluated partial checkpoints."""
import argparse
import gzip
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import time
import traceback

import numpy as np
import PIL
import psutil

from experiments.noisy_rgb_discovery.core import calibrate
from experiments.noisy_rgb_discovery.run import CONFIG as OLD_CONFIG,write,save_statistics
from experiments.noisy_rgb_discovery.sensor import Sensor,make_game
from experiments.noisy_rgb_version_space.core import Evidence,CandidateLearner
from experiments.noisy_rgb_version_space.runtime import LIMITS,ResourceLimit,measured_statistics,stage_sensors
from experiments.noisy_rgb_version_space.run import save_input_image
from .core import ProvisionalLearner
from .snapshots import CHECKPOINTS,CheckpointBudget,v1_record,save_checkpoint
from .public_labels import PublicLabels,labelled_game,labelled_stages

ROOT=Path(__file__).parent


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--phase',choices=['development','fresh'],required=True)
    p.add_argument('--seed',type=int,required=True)
    p.add_argument('--camera',choices=['base','shifted'],required=True)
    p.add_argument('--arm',choices=['V1','V2'],required=True)
    p.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    registration=json.loads((ROOT/'launch.json').read_text())
    assert registration['diagnostic_gate_passed']
    assert args.phase==registration['phase'] and args.seed in registration['seeds']
    out=args.output
    out.mkdir(parents=True,exist_ok=False)
    write(out/'config.json',dict(phase=args.phase,seed=args.seed,camera=args.camera,arm=args.arm,
        acquisition_limits=LIMITS,checkpoints=CHECKPOINTS,registration=registration,
        camera_bias=OLD_CONFIG['cameras'][args.camera],statistical_rule='frozen VS1',
        endpoint='confirmed and provisional class coverage / exposures; partial control / exposures'))
    source_files={str(f):hashlib.sha256(f.read_bytes()).hexdigest() for d in (ROOT,ROOT.parent/'noisy_rgb_version_space',ROOT.parent/'noisy_rgb_discovery')
                  for f in d.rglob('*') if f.is_file() and f.suffix in ('.py','.json','.md')}
    write(out/'source_snapshot.json',dict(commit=subprocess.check_output(['git','rev-parse','HEAD'],text=True).strip(),
        files=source_files,command=sys.argv,python=sys.version,numpy=np.__version__,pillow=PIL.__version__,
        platform=platform.platform(),run_id=os.getenv('GITHUB_RUN_ID'),attempt=os.getenv('GITHUB_RUN_ATTEMPT'),
        threads={k:os.getenv(k) for k in ('OPENBLAS_NUM_THREADS','OMP_NUM_THREADS','MKL_NUM_THREADS')}))
    events=gzip.open(out/'events.jsonl.gz','wt',encoding='utf-8',compresslevel=1)
    started,cpu=time.perf_counter(),time.process_time()
    event_count=0
    def emit(row):
        nonlocal event_count
        event_count+=1
        events.write(json.dumps(dict(row,event_index=event_count,elapsed_seconds=time.perf_counter()-started))+'\n')
        if args.arm=='V2' and table is not None:
            table.receive_certificate(row)
    table=None
    stats={}
    threshold=None
    sensors={}
    snapshots=[]
    labels=PublicLabels()
    def freeze(target,actual):
        if table is None:
            return
        directory=out/f'checkpoint_{target}'
        state=table.record() if args.arm=='V2' else v1_record(table)
        if args.arm=='V2':
            state['public_labels']=labels.record()
            state['public_label_schema']={'goal':'observed public boolean','terminal':'API unavailable'}
        metadata=dict(target_exposures=target,actual_exposures=actual,environment_actions=budget.actions,
            threshold=threshold,arm=args.arm,seed=args.seed,camera=args.camera,event_prefix_count=event_count,
            acquisition_cpu_seconds=time.process_time()-cpu,acquisition_wall_seconds=time.perf_counter()-started,
            peak_memory_bytes=getattr(psutil.Process().memory_info(),'peak_wset',psutil.Process().memory_info().rss),
            snapshot_boundary='before atomic RGB batch crossing target; no post-target evidence',
            requested_checkpoint_reached=(isinstance(target,int) and actual>=target-31))
        save_checkpoint(directory,state,stats,metadata)
        snapshots.append(directory.name)
        emit(dict(event='checkpoint_frozen',**metadata))
        print(json.dumps(dict(event='checkpoint_frozen',**metadata)),flush=True)
    budget=CheckpointBudget(freeze,**LIMITS)
    result=dict(phase=args.phase,seed=args.seed,camera=args.camera,arm=args.arm,status='NOT_STARTED')
    game=labelled_game(args.seed) if args.arm=='V2' else make_game(args.seed)
    bias=OLD_CONFIG['cameras'][args.camera]
    try:
        cal=Sensor(game,bias,'calibration-v1',out/'calibration',8,12)
        sensors['calibration']=cal
        threshold,cal_record=calibrate(measured_statistics(cal,budget),cal.port.actions)
        write(out/'calibration.json',cal_record)
        train,stats=(labelled_stages(game,bias,out,'training',budget,labels) if args.arm=='V2'
                     else stage_sensors(game,bias,out,'training',budget))
        sensors.update(train)
        evidence=Evidence(stats,threshold,args.camera,emit,budget.check)
        if args.arm=='V1':
            table=CandidateLearner(evidence,train[8].port.actions,emit,budget.check)
            _,result['status']=table.learn()
        else:
            table=ProvisionalLearner(evidence,train[8].port.actions,lambda h:stats[8].summary(h,0),emit,budget.check,
                                     label_equality=labels.compare)
            table.start()
            while table.step():
                pass
            result['status']='PARTIAL_AGENDA_EXHAUSTED'
    except ResourceLimit as exc:
        result.update(status='INCOMPLETE_RESOURCE_LIMIT',resource_reason=str(exc))
    except Exception:
        result.update(status='IMPLEMENTATION_ERROR',traceback=traceback.format_exc())
    finally:
        if table is not None:
            for target in CHECKPOINTS:
                if target not in budget.saved and budget.exposures>=target:
                    freeze(target,budget.exposures)
                    budget.saved.add(target)
            if not snapshots or json.loads((out/snapshots[-1]/'checkpoint.json').read_text())['actual_exposures']!=budget.exposures:
                freeze('final',budget.exposures)
        for sensor in sensors.values():
            sensor.close()
        if 8 in sensors:
            save_input_image(sensors[8],out,args.seed,args.camera,args.arm)
        events.close()
    result.update(acquisition_exposure_sets=budget.exposures,acquisition_environment_actions=budget.actions,
        acquisition_cpu_seconds=time.process_time()-cpu,acquisition_wall_seconds=time.perf_counter()-started,
        checkpoints=snapshots,event_count=event_count,sensors=[dict(namespace=s.namespace,**s.metrics()) for s in sensors.values()])
    write(out/'acquisition_result.json',result)
    if result['status']!='IMPLEMENTATION_ERROR':
        from .evaluate import evaluate_checkpoint
        evaluations=[]
        for name in snapshots:
            try:
                evaluation=evaluate_checkpoint(out/name,out/(name+'_evaluation'),args.seed,args.camera,args.arm,bias)
                evaluations.append(evaluation)
                print(json.dumps(dict(event='checkpoint_evaluated',checkpoint=name,
                    audit=evaluation['model_audit'],heldout_status=evaluation['heldout']['status'],control=evaluation['control']['status'])),flush=True)
            except Exception:
                result['postfreeze_error']=traceback.format_exc()
                break
        result['evaluations']=evaluations
    result.update(total_cpu_seconds=time.process_time()-cpu,total_wall_seconds=time.perf_counter()-started,
                  peak_memory_bytes=getattr(psutil.Process().memory_info(),'peak_wset',psutil.Process().memory_info().rss))
    write(out/'result.json',result)
    write(out/'artifact_hashes.json',{str(f.relative_to(out)):hashlib.sha256(f.read_bytes()).hexdigest()
                                    for f in out.rglob('*') if f.is_file()})
    print(json.dumps(result),flush=True)
    if result['status']=='IMPLEMENTATION_ERROR' or result.get('postfreeze_error'):
        raise SystemExit(1)


if __name__=='__main__':
    main()
