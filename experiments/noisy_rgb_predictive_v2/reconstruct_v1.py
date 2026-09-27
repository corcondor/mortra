"""Development baseline checkpoints reconstructed from V1; no reacquisition."""
import argparse
import json
from pathlib import Path

from experiments.noisy_rgb_discovery.run import write,CONFIG
from .diagnose_v1 import diagnose
from .snapshots import save_checkpoint,v1_record


def main():
    p=argparse.ArgumentParser()
    p.add_argument('--input',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--checkpoint-only',action='store_true')
    args=p.parse_args()
    folder=next(args.input.rglob('result.json')).parent
    saved=json.loads((folder/'result.json').read_text())
    args.output.mkdir(parents=True,exist_ok=False)
    snapshots=[]
    seen_exposures=set()
    def capture(target,budget,table,statistics):
        if budget['exposures'] in seen_exposures:
            return
        seen_exposures.add(budget['exposures'])
        destination=args.output/f'checkpoint_{target}'
        metadata=dict(target_exposures=target,actual_exposures=budget['exposures'],environment_actions=budget['actions'],
            threshold=table.evidence.threshold,seed=saved['seed'],camera=saved['camera'],arm='V1',
            original_run_id=36301127275,source='READ_ONLY_RECONSTRUCTION_OF_SAVED_V1',
            acquisition_cpu_seconds=saved['acquisition_cpu_seconds'] if target=='final' else None,
            acquisition_wall_seconds=saved['acquisition_wall_seconds'] if target=='final' else None,
            peak_memory_bytes=None,requested_checkpoint_reached=isinstance(target,int) and budget['exposures']>=target-31,
            timing_note='Original prefix CPU/memory were not recorded; diagnostic replay timing is not substituted.')
        save_checkpoint(destination,v1_record(table),statistics,metadata)
        snapshots.append(destination)
    diagnose(folder,args.output/'read_only_diagnosis',capture)
    if args.checkpoint_only:
        write(args.output/'checkpoint_reconstruction.json',dict(passed=True,new_sensor_operations=0,
              checkpoints=[x.name for x in snapshots]))
        return
    from .evaluate import evaluate_checkpoint
    evaluations=[]
    for checkpoint in snapshots:
        evaluations.append(evaluate_checkpoint(checkpoint,args.output/(checkpoint.name+'_evaluation'),
            saved['seed'],saved['camera'],'V1',CONFIG['cameras'][saved['camera']]))
    result=dict(phase='development',arm='V1',seed=saved['seed'],camera=saved['camera'],status=saved['status'],
        acquisition_mode='READ_ONLY_RECONSTRUCTION',original_result=saved,evaluations=evaluations,
        acquisition_exposure_sets=saved['acquisition_exposure_sets'],acquisition_environment_actions=saved['acquisition_environment_actions'],
        acquisition_cpu_seconds=saved['acquisition_cpu_seconds'],acquisition_wall_seconds=saved['acquisition_wall_seconds'],
        peak_memory_bytes=saved['peak_memory_bytes'])
    write(args.output/'result.json',result)


if __name__=='__main__':
    main()
