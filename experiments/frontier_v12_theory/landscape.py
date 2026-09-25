"""Independent mutations of immutable archived parents, never an evolution loop."""
from collections import defaultdict
import gzip
import json
import random
import tempfile
import time
from pathlib import Path

from experiments.game_frontier_v12 import run as old
from .data import CONFIG, read, write, csv_write, file_sha, frozen_sources


def mutation_rng(parent_hash, arm, replicate):
    seed=old.io.derive(parent_hash,arm,replicate,'reward-landscape-v1')
    rng=random.Random(seed)
    rng.choice(old.FAMILIES)  # Preserve the frozen scheduler's consumed family draw.
    return seed,rng


def evaluate_one(parent, arm, replicate, cfg, scratch):
    assert set(parent)=={'parent_id','seed','game_hash','genome','D_parent','context_id','context','generations'}
    assert 'holdout' not in json.dumps(parent).lower()
    before=old.frozen.game_hash(parent['genome'])
    assert before==parent['game_hash']
    mutation_seed,rng=mutation_rng(before,arm,replicate)
    t0=time.process_time()
    result=None; genome=None; error=None
    try:
        genome=old.frozen.mutate(parent['genome'],arm,rng,cfg['max_board'])
    except ValueError as exc:
        error=str(exc)
    else:
        prepared=old.frozen.prepare(genome,cfg,parent['seed'])
        meta=dict(generation=min(parent['generations']),candidate=old.FAMILIES.index(arm)*10+replicate,
                  mutation=arm,parent_hash=before)
        result=old.frozen.train_candidate(genome,prepared,cfg,parent['seed'],meta,scratch)
    assert before==old.frozen.game_hash(parent['genome'])
    outcome=old.outcome_of(result)
    value=old.reward(parent['D_parent'],outcome)
    r=result or {}
    oracle=r.get('oracle',{})
    category=('invalid_zero' if not outcome.valid else 'ineligible_zero' if not outcome.eligible else
              'eligible_harder_positive' if value>0 else 'eligible_easier_negative' if value<0 else 'eligible_equal_zero')
    row=dict(parent_id=parent['parent_id'],parent_hash=before,seed=parent['seed'],generations=parent['generations'],
             context_id=parent['context_id'],primitive=arm,replicate=replicate,mutation_seed=mutation_seed,
             candidate_hash=r.get('game_hash'),valid=outcome.valid,eligible=outcome.eligible,
             oracle_status=oracle.get('status','NOT_RUN_INVALID_MUTATION'),classification=r.get('classification','INVALID_MUTATION'),
             invalid_reason=error or r.get('reason'),D_parent=parent['D_parent'],D_candidate=outcome.D,
             delta_D=None if outcome.D is None else outcome.D-parent['D_parent'],
             B50=r.get('B50'),B80=outcome.B80,B90=outcome.B90,final_learned_success=outcome.final_success,
             full_info_success=outcome.full_info_success,reward=value,reward_category=category,
             reachable_states=oracle.get('reachable_states'),branching_factor=oracle.get('branching_factor'),
             branching_states=oracle.get('branching_states'),rules=len(genome['rules']) if genome else None,
             variables=len(genome['domains']) if genome else None,action_count=genome['actions'] if genome else None,
             evaluation_CPU=time.process_time()-t0,parent_unchanged=True,mutation_attempts=1)
    return row,dict(row=row,genome=genome,evaluation=result)


def run(inputs, output, stage):
    data=read(inputs); cfg=data['evaluator_config']; assert cfg==old.config()
    before=frozen_sources()
    out=Path(output); out.mkdir(parents=True,exist_ok=False)
    parents=data['parents']
    reps=CONFIG['smoke_replicates'] if stage==1 else CONFIG['replicates']
    if stage==1:
        assert data['seed']==2101
        parents=[p for p in parents if set(p['generations']) & set(CONFIG['smoke_generations'])]
        assert len(parents)==3
    write(out/'config.json',dict(**CONFIG,stage=stage,actual_replicates=reps,input_sha=file_sha(inputs)))
    write(out/'source_snapshot.json',dict(frozen=before,head=old.io.git('rev-parse','HEAD'),run=__import__('os').environ.get('GITHUB_RUN_ID')))
    rows=[]; t0=time.perf_counter()
    with (out/'run.log').open('x',encoding='utf-8',buffering=1) as log, gzip.open(out/'records.jsonl.gz','xt',encoding='utf-8') as archive:
        try:
            for p in parents:
                for arm in old.FAMILIES:
                    for rep in range(reps):
                        # Only new candidate scratch files are removed; prior research is never touched.
                        with tempfile.TemporaryDirectory(prefix='candidate-',dir=out) as directory:
                            assert Path(directory).resolve().parent==out.resolve()
                            row,record=evaluate_one(p,arm,rep,cfg,Path(directory))
                        rows.append(row)
                        archive.write(json.dumps(record,sort_keys=True,allow_nan=False)+'\n'); archive.flush()
                        csv_write(out/'counterfactual_candidates.csv',rows)
                        msg=f"{p['parent_id']} {arm} {rep} {row['classification']} reward={row['reward']}"
                        print(msg,flush=True); log.write(msg+'\n')
            assert len(rows)==len(parents)*14*reps and frozen_sources()==before
            write(out/'completed.json',dict(status='COMPLETED',parents=len(parents),replicates=reps,candidates=len(rows),
                parent_updates=0,invalid_retries=0,wall_seconds=time.perf_counter()-t0))
        except BaseException as exc:
            write(out/'incomplete.json',dict(status='RUN_NOT_COMPLETED',completed_candidates=len(rows),reason=repr(exc)))
            raise
