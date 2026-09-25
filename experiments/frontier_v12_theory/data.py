"""Verify official artifacts before producing holdout-free counterfactual inputs."""
import csv
import hashlib
import json
import os
from pathlib import Path
import statistics
import subprocess
from collections import defaultdict
from dataclasses import asdict

from experiments.game_frontier_v12 import run as original
from experiments.game_frontier_v12.proposal import ContextualUCB
from .maths import max_normal_constant

HEAD = 'c060d5c9549eaae913bd7b9555ad2289ff96ff8c'
RUN = '36107649938'
SEEDS = original.SEEDS
ROOT = original.io.ROOT
CONFIG = dict(protocol='reward-landscape-v1', source_run=RUN, source_commit=HEAD,
              smoke_generations=[0,5,10], smoke_replicates=5, replicates=10,
              parent_scope='all unique (seed, adaptive frontier hash, context), G0 through G10',
              mutation_seed="derive(parent_hash, primitive, replicate, 'reward-landscape-v1')",
              consumed_family_draw=True, parent_update=False, selection=False, holdout_candidate_evaluation=False,
              calibration='all recorded pre-slot probabilities; G10 post-run hypothetical reported separately',
              ties='average ranks, uniform top-1 ties, expected top-3 overlap under independent uniform ties',
              snr_epsilon=float(__import__('numpy').finfo(float).eps),
              variance='within-arm sample variance ddof=1; between-arm population variance ddof=0',
              response='m=8 normal approximation; complete pools only for predictions/resampling; missing Y not imputed',
              resampling_draws=10000, seed_cluster_bootstrap_draws=10000,
              fixed_field_scope='all saved unique frontier worlds, selection and holdout full-information tasks',
              exact_solve='sparse LU of I-.9K; no replacement of frozen solver or policy',
              resource='original oracle and dense-K guards; interruptions are RUN_NOT_COMPLETED, never task FAIL',
              repetition='no outcome-based retries or replicate adjustment',
              gate='saved metrics/source equality then correctness smoke only, never performance',
              hypothesis_test=None, stop='after Stage 2 artifacts; no tuning')


def read(p):
    p = Path(p).resolve()
    return json.loads(Path('\\\\?\\'+str(p) if os.name=='nt' else p).read_text(encoding='utf-8'))


def file_sha(p):
    p=Path(p).resolve()
    return hashlib.sha256(Path('\\\\?\\'+str(p) if os.name=='nt' else p).read_bytes()).hexdigest()


def write(p, obj):
    original.io.write_json(p, obj)


def csv_write(p, rows, fields=None):
    rows=list(rows)
    p=Path(p); p.parent.mkdir(parents=True,exist_ok=True)
    if fields is None:
        fields=list(dict.fromkeys(k for r in rows for k in r)) or ['status']
    with p.open('w',encoding='utf-8',newline='') as f:
        w=csv.DictWriter(f,fieldnames=fields); w.writeheader()
        w.writerows({k:json.dumps(v,sort_keys=True) if isinstance(v,(list,dict,tuple)) else v for k,v in r.items()} for r in rows)


def frozen_sources():
    prov=original.provenance()
    all_hashes={**prov['source_hashes_lf'],**prov['v12_source_hashes_lf']}
    for name, sha in all_hashes.items():
        expected=subprocess.check_output(['git','show',f'{HEAD}:{name}'],cwd=ROOT)
        assert hashlib.sha256(expected.replace(b'\r\n',b'\n')).hexdigest()==sha, name
    return all_hashes


def source_files(source, require_evolution=True):
    source=Path(source)
    results=list((source/'evolution').rglob('results.json'))
    assert len(results)==32 or not require_evolution
    bundles={}; audits={}
    manifest=read(source/'frozen/manifest.json')
    assert manifest['evolution_run']==RUN and manifest['evolution_head']==HEAD
    for c in manifest['cases']:
        p=source/'frozen/cases'/c['file']
        assert file_sha(p)==c['bundle_sha256']
        b=read(p)
        paths=list((source/'holdout').rglob(c['file']))
        assert len(paths)==1,(c['file'],paths)
        a=read(paths[0])
        assert a['source_bundle_sha256']==c['bundle_sha256'] and a['all_selection_checkpoints_reproduced']
        assert original.holdout.digest(b['holdout_tasks'])==c['holdout_tasks_sha256']
        assert not set(map(original.holdout.pair,b['holdout_tasks'])) & {(tuple(u),tuple(v)) for u,v in b['excluded_pairs']}
        bundles[c['seed'],c['game_hash']]=p
        audits[c['seed'],c['game_hash']]=paths[0]
    return results,bundles,audits


def register(source, output):
    out=Path(output); out.mkdir(parents=True,exist_ok=False)
    hashes=frozen_sources()
    results,bundles,audits=source_files(source)
    metrics=read(Path(source)/'summary/metrics.json')
    assert metrics['head']==HEAD and metrics['run']==RUN
    seen=set(); starts=defaultdict(set); parent_rows=[]; parents=defaultdict(dict); aggregates=defaultdict(list)
    for path in results:
        r=read(path)
        key=(r['seed'],r['condition']); assert key not in seen; seen.add(key)
        assert r['config']==original.config() and r['provenance']['git_head']==HEAD
        original.validate_run(r)
        starts[r['seed']].add(r['frontier'][0]['game_hash'])
        for g,p in enumerate(r['frontier']):
            a=read(audits[r['seed'],p['game_hash']])
            for k in ('D','B50','B80','B90','final_success'):
                assert p[k]==a['selection_metrics'][k],(key,g,k)
            for row in a['paired']:
                for split in ('selection','holdout'):
                    e=row[split]
                    assert e['successes']==sum(t['success'] for t in e['task_results'])
            if r['condition']!='adaptive': continue
            b=read(bundles[r['seed'],p['game_hash']])
            ctx=original.context_of(b['genome'],p)
            actual=[h for h in r['mutation_history'] if h['generation']==g+1]
            if actual:
                assert all(h['parent_hash']==p['game_hash'] and h['decision']['context']==asdict(ctx) for h in actual)
                decisions=[h['decision'] for h in actual]
            else:
                model=ContextualUCB(13); model.tables=r['proposal_posterior']
                decisions=[model.decision(ctx,11)]
            pid=f"{r['seed']}_{p['game_hash']}"
            entry=parents[r['seed']].setdefault(pid,dict(parent_id=pid,seed=r['seed'],game_hash=p['game_hash'],
                genome=b['genome'],D_parent=p['D'],context_id=ctx.key(),context=asdict(ctx),occurrences=[]))
            assert entry['D_parent']==p['D'] and entry['context_id']==ctx.key()
            occurrence=dict(generation=g,actual_proposals=bool(actual),decisions=decisions,
                selected_primitives=[h['mutation'] for h in actual if h['selected']],
                candidate_rewards=[h['reward'] for h in actual],
                D_selection=p['D'],D_holdout=a['holdout_metrics']['D'],B80=p['B80'],
                learned_success=p['final_success'],full_info_success=p['full_info']['success_rate'],
                ucb_after=actual[-1]['posterior_after'] if actual else r['proposal_posterior'])
            entry['occurrences'].append(occurrence)
            parent_rows.append(dict(parent_id=pid,seed=r['seed'],game_hash=p['game_hash'],
                context_id=ctx.key(),**occurrence))
        final=read(audits[r['seed'],r['frontier'][-1]['game_hash']])
        aggregates[r['condition']].append(dict(final_holdout_D_mean=final['holdout_metrics']['D'],
            final_holdout_success_macro=final['holdout_metrics']['final_success'],
            final_selection_D_mean=r['frontier'][-1]['D'],
            valid_rate=statistics.mean(h['outcome']['valid'] for h in r['mutation_history']),
            eligible_rate=statistics.mean(h['outcome']['eligible'] for h in r['mutation_history'])))
    assert seen=={(s,c) for s in SEEDS for c in original.CONDITIONS}
    assert all(len(h)==1 for h in starts.values()) and len(parent_rows)==88
    # Recalculate primary published aggregates, not merely their presence.
    for cond in original.CONDITIONS:
        checks={k:statistics.mean(v[k] for v in aggregates[cond]) for k in aggregates[cond][0]}
        for k,v in checks.items(): assert abs(v-metrics['conditions'][cond][k])<1e-12,(cond,k)
    assert len(bundles)==193 and sum(len(read(b)['holdout_tasks']) for b in bundles.values())==95580
    for seed,items in parents.items():
        # Holdout values stay in the audit manifest, not in candidate-evaluation inputs.
        clean=[{k:v for k,v in p.items() if k!='occurrences'} | {'generations':[o['generation'] for o in p['occurrences']]} for p in items.values()]
        assert 'holdout' not in json.dumps(clean).lower()
        write(out/'inputs'/f'{seed}.json',dict(seed=seed,parents=clean,evaluator_config=original.config()))
        write(out/'restored'/f'{seed}.json',list(items.values()))
    csv_write(out/'parent_manifest.csv',parent_rows)
    write(out/'config.json',CONFIG)
    write(out/'normal_maximum.json',max_normal_constant())
    write(out/'frozen_manifest.json',dict(status='SOURCE_AND_SAVED_VALUES_VERIFIED',source_run=RUN,source_head=HEAD,
        source_hashes=hashes,audit_head=original.io.git('rev-parse','HEAD'),
        audit_source_hashes={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_text(encoding='utf-8').encode()).hexdigest()
            for p in [*sorted((ROOT/'experiments/frontier_v12_theory').glob('*.py')),ROOT/'scripts/audit_frontier_v12_theory.py',
                ROOT/'scripts/download_frontier_v12_audit_sources.py',ROOT/'tests/test_frontier_v12_theory.py',
                ROOT/'.github/workflows/frontier-v12-theory-reward-landscape.yml',ROOT/'docs/research/FRONTIER-V12-THEORY-AUDIT-20260925.md']},
        unique_parents=sum(len(p) for p in parents.values()),frontier_occurrences=88,
        input_hashes={str(p.relative_to(out)):file_sha(p) for p in (out/'inputs').glob('*.json')},
        original_summary_sha=file_sha(Path(source)/'summary/metrics.json'),
        original_manifest_sha=file_sha(Path(source)/'frozen/manifest.json')))
    print('SOURCE_AND_SAVED_VALUES_VERIFIED',sum(len(p) for p in parents.values()),flush=True)
