"""Post-experiment summaries, never fed back to generation or proposals."""
from collections import Counter, defaultdict
import csv
import json
import math
from pathlib import Path
import numpy as np

from .data import read, write, csv_write, original, CONFIG
from .maths import calibration, correlation


def read_csv(path):
    def parse(v):
        if v=='': return None
        if v in ('True','False'): return v=='True'
        try: return json.loads(v)
        except (ValueError,TypeError): return v
    with Path(path).open(encoding='utf-8',newline='') as f:
        return [{k:parse(v) for k,v in r.items()} for r in csv.DictReader(f)]


def distribution(vals):
    vals=[float(v) for v in vals if v is not None and math.isfinite(v)]
    return dict(n=len(vals),mean=float(np.mean(vals)) if vals else None,
                median=float(np.median(vals)) if vals else None,min=min(vals) if vals else None,max=max(vals) if vals else None)


def landscape(registration, inputs, output, smoke=False):
    out=Path(output); out.mkdir(parents=True,exist_ok=False)
    paths=list(Path(inputs).rglob('counterfactual_candidates.csv'))
    rows=[r for p in paths for r in read_csv(p)]
    grouped=defaultdict(list)
    for r in rows: grouped[r['parent_id'],r['primitive']].append(r)
    pids=sorted({r['parent_id'] for r in rows})
    reps=5 if smoke else 10
    assert len(rows)==len(pids)*14*reps
    arm_rows=[];vectors={};variance={};snrs=[];pathology=[]
    for pid in pids:
        means=[];variances=[];summaries=[]
        for arm in original.FAMILIES:
            rs=grouped[pid,arm]
            assert sorted(r['replicate'] for r in rs)==list(range(reps))
            assert all(r['parent_unchanged'] and r['mutation_attempts']==1 for r in rs)
            rewards=np.array([r['reward'] for r in rs])
            elig=[r['reward'] for r in rs if r['eligible']]
            item=dict(parent_id=pid,seed=rs[0]['seed'],parent_hash=rs[0]['parent_hash'],context_id=rs[0]['context_id'],
                primitive=arm,replicates=reps,mu=float(rewards.mean()),variance=float(rewards.var(ddof=1)),
                valid_rate=float(np.mean([r['valid'] for r in rs])),eligible_rate=float(np.mean([r['eligible'] for r in rs])),
                positive_reward_rate=float(np.mean(rewards>0)),zero_reward_rate=float(np.mean(rewards==0)),
                negative_reward_rate=float(np.mean(rewards<0)),eligible_conditional_mean=float(np.mean(elig)) if elig else None,
                ineligible_zero_rate=float(np.mean([not r['eligible'] for r in rs])))
            arm_rows.append(item);summaries.append(item);means.append(item['mu']);variances.append(item['variance'])
        vectors[pid]=np.array(means);variance[pid]=np.array(variances)
        signal=float(np.var(means));noise=float(np.mean(variances))
        snrs.append(dict(parent_id=pid,seed=rs[0]['seed'],context_id=rs[0]['context_id'],V_signal=signal,V_noise=noise,
            SNR=signal/(noise+CONFIG['snr_epsilon']),between_variance_minus_sampling_noise=signal-(1-1/len(means))*noise/reps,
            best_primitives=[a for a,m in zip(original.FAMILIES,means) if m==max(means)]))
        all_rs=[r for arm in original.FAMILIES for r in grouped[pid,arm]]
        counts=Counter(r['reward_category'] for r in all_rs)
        reversal_pairs=[]
        for a in summaries:
            for b in summaries:
                if a['primitive']==b['primitive']:continue
                if a['eligible_rate']==0 and b['eligible_rate']>0 and b['mu']<0 and a['mu']>b['mu']:
                    reversal_pairs.append([a['primitive'],b['primitive']])
        pathology.append(dict(parent_id=pid,seed=rs[0]['seed'],context_id=rs[0]['context_id'],samples=len(all_rs),
            P_zero=sum(r['reward']==0 for r in all_rs)/len(all_rs),P_negative=sum(r['reward']<0 for r in all_rs)/len(all_rs),
            P_positive=sum(r['reward']>0 for r in all_rs)/len(all_rs),categories=dict(counts),
            pure_ineligible_arm_outranks_negative_mean_eligible_arm=len(reversal_pairs),arm_pairs=reversal_pairs,
            zero_ineligible_vs_negative_eligible_candidate_pairs=sum(not r['eligible'] for r in all_rs)*sum(r['eligible'] and r['reward']<0 for r in all_rs)))
    parents={}
    for p in Path(registration).glob('restored/*.json'):
        parents.update({r['parent_id']:r for r in read(p)})
    assert set(pids)<=set(parents)
    if not smoke:
        assert set(pids)==set(parents), 'Incomplete Stage 2 parent coverage'
        assert {parents[p]['seed'] for p in pids}==set(original.SEEDS)
    cal=[]
    for pid in pids:
        p=parents[pid]; mu=vectors[pid]
        for occurrence in p['occurrences']:
            for slot,d in enumerate(occurrence['decisions']):
                prob=[d['probabilities'][a] for a in original.FAMILIES]
                c=calibration(mu,prob,[d['ucb'][a] for a in original.FAMILIES])
                cal.append(dict(parent_id=pid,seed=p['seed'],generation=occurrence['generation'],slot=slot,
                    actual_proposal=occurrence['actual_proposals'],context_id=p['context_id'],**c,
                    Delta_E_MC_SE_approx=float(np.sqrt(np.sum((np.array(prob)-1/14)**2*variance[pid]/reps)))))
    stability=[]
    for i,pid in enumerate(pids):
        p=parents[pid]
        for qid in pids[i+1:]:
            q=parents[qid]
            pg=[x['generation'] for x in p['occurrences']];qg=[x['generation'] for x in q['occurrences']]
            adjacent=p['seed']==q['seed'] and any(abs(a-b)==1 for a in pg for b in qg)
            distant=p['seed']==q['seed'] and any(abs(a-b)>1 for a in pg for b in qg)
            stability.append(dict(parent_i=pid,parent_j=qid,seed_i=p['seed'],seed_j=q['seed'],same_seed=p['seed']==q['seed'],
                same_context=p['context_id']==q['context_id'],adjacent=adjacent,distant=distant,
                Pearson=correlation(vectors[pid],vectors[qid]),Spearman=correlation(vectors[pid],vectors[qid],True)))
    seed_summary=[]
    for seed in sorted({r['seed'] for r in cal}):
        cs=[r for r in cal if r['seed']==seed and r['actual_proposal']]
        seed_summary.append(dict(seed=seed,actual_slots=len(cs),**{k:distribution(r[k] for r in cs) for k in ('Delta_E','rho_UCB','rho_P','R1')},
                                 Delta_E_positive=sum(r['Delta_E']>0 for r in cs),Delta_E_negative=sum(r['Delta_E']<0 for r in cs),Delta_E_zero=sum(r['Delta_E']==0 for r in cs)))
    seed_means=[r['Delta_E']['mean'] for r in seed_summary]
    rng=np.random.default_rng(original.io.derive('reward-landscape-v1','seed-bootstrap'))
    draws=np.mean(rng.choice(seed_means,size=(CONFIG['seed_cluster_bootstrap_draws'],len(seed_means))),axis=1)
    summary=dict(status='COMPLETED',parents=len(pids),candidates=len(rows),replicates=reps,seeds=seed_summary,
        Delta_E_seed_mean=float(np.mean(seed_means)),Delta_E_seed_bootstrap_percentile_95=list(map(float,np.quantile(draws,[.025,.975]))),
        bootstrap_caveat='8 independent seed clusters, conditional on finite replicate estimates; not thousands of independent proposals',
        SNR=distribution(s['SNR'] for s in snrs),
        stability={name:distribution(s['Spearman'] for s in stability if pred(s)) for name,pred in
            [('adjacent',lambda s:s['adjacent']),('distant',lambda s:s['distant']),('same_context',lambda s:s['same_context']),
             ('different_context',lambda s:not s['same_context']),('cross_seed',lambda s:not s['same_seed'])]},
        pure_ineligible_outrank_parents=sum(p['pure_ineligible_arm_outranks_negative_mean_eligible_arm']>0 for p in pathology),
        pure_ineligible_outrank_arm_pairs=sum(p['pure_ineligible_arm_outranks_negative_mean_eligible_arm'] for p in pathology),
        total_evaluation_CPU=sum(r['evaluation_CPU'] for r in rows))
    csv_write(out/'reward_landscape/counterfactual_candidates.csv',rows)
    csv_write(out/'reward_landscape/operator_summary.csv',arm_rows)
    csv_write(out/'reward_landscape/adaptive_vs_uniform_expected_reward.csv',cal)
    csv_write(out/'reward_landscape/operator_stability.csv',stability)
    csv_write(out/'reward_landscape/reward_pathology.csv',pathology)
    contexts=defaultdict(list)
    for row in rows: contexts[row['context_id']].append(row)
    csv_write(out/'reward_landscape/counterfactual_context_rewards.csv',[
        dict(context_id=context,parents=len({r['parent_id'] for r in rs}),seeds=len({r['seed'] for r in rs}),
            candidates=len(rs),P_zero=float(np.mean([r['reward']==0 for r in rs])),
            P_negative=float(np.mean([r['reward']<0 for r in rs])),P_positive=float(np.mean([r['reward']>0 for r in rs])),
            categories=dict(Counter(r['reward_category'] for r in rs))) for context,rs in sorted(contexts.items())])
    csv_write(out/'reward_landscape/signal_noise.csv',snrs)
    write(out/'landscape_summary.json',summary)
    return summary


def combine(registration, landscape_dir, saved_dir, field_dir, output):
    import shutil
    out=Path(output)
    summary=landscape(registration,landscape_dir,out)
    for sub in ('difficulty_theory','selection_theory','reward_landscape'):
        for p in (Path(saved_dir)/sub).glob('*'):
            dst=out/sub/p.name;assert not dst.exists();dst.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,dst)
    for name in ('task_path_attenuation','reasoner_failure_diagnostics','resolvent_diagnostics'):
        rows=[r for p in Path(field_dir).rglob(name+'.csv') for r in read_csv(p)]
        assert len(rows)==114880,len(rows)  # 193*100 selection + 95,580 holdout tasks.
        csv_write(out/'fixed_field_theory'/(name+'.csv'),rows)
    for name in ('config.json','frozen_manifest.json','parent_manifest.csv'):
        shutil.copy2(Path(registration)/name,out/name)
    from .plots import render
    render(out)
    from .report import render as report
    report(out)
    write(out/'completed.json',dict(status='COMPLETED',new_evolution=0,algorithm_changes=0,**{'parents':summary['parents']}))
