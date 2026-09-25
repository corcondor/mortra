"""Difficulty and selection diagnostics using only already recorded outcomes."""
from collections import defaultdict
from pathlib import Path
import math
import numpy as np

from .data import read, write, csv_write, source_files, CONFIG, original
from .maths import threshold_audit, response_stats, gaussian_response, resampled_response, max_normal_constant, correlation


def difficulty(source, output):
    out=Path(output)
    _,bundles,audits=source_files(source)
    task_rows=[]; summaries=[]; comparisons=[]
    for key in sorted(bundles):
        b,a=read(bundles[key]),read(audits[key])
        for split in ('selection','holdout'):
            budgets=[r['budget'] for r in a['paired']]
            ev=[r[split] for r in a['paired']]
            tasks=b['archived_final']['tasks'] if split=='selection' else b['holdout_tasks']
            rows=[]
            for j,t in enumerate(tasks):
                vals=[int(e['task_results'][j]['success']) for e in ev]
                row=dict(seed=key[0],game_hash=key[1],split=split,task_id=j,**threshold_audit(vals,budgets))
                rows.append(row); task_rows.append(row)
            d=original.replication.analysis.curve(a['paired'],split)['D']
            avg=lambda k: float(np.mean([r[k] for r in rows]))
            assert abs(d-avg('D_task'))<1e-11
            summaries.append(dict(seed=key[0],game_hash=key[1],split=split,tasks=len(rows),
                monotone_fraction=avg('monotone'),non_monotone_fraction=1-avg('monotone'),
                reversals=sum(r['reversals'] for r in rows),censored_fraction=avg('censored')))
            comparisons.append(dict(seed=key[0],game_hash=key[1],split=split,D_from_curve=d,
                mean_capped_log_threshold=avg('capped_log_threshold'),half_bin_correction=avg('trapezoid_half_bin'),
                nonmonotonicity_penalty=avg('nonmonotonicity_penalty'),
                identity_error=d-(avg('capped_log_threshold')-avg('trapezoid_half_bin')+avg('nonmonotonicity_penalty')),
                true_uncensored_mean='NOT_IDENTIFIED_WITH_RIGHT_CENSORING'))
    csv_write(out/'difficulty_theory/task_thresholds.csv',task_rows)
    csv_write(out/'difficulty_theory/monotonicity_summary.csv',summaries)
    csv_write(out/'difficulty_theory/D_sample_complexity_comparison.csv',comparisons)
    return summaries,comparisons


def selection(source, output):
    out=Path(output)
    paths,_,ap=source_files(source)
    # A frontier world can also occur as an unselected candidate; label this observed subset.
    d_holdout={k:read(p)['holdout_metrics']['D'] for k,p in ap.items()}
    constant=max_normal_constant()
    records=[]; gauss=[]; nonparam=[]; pair_groups=defaultdict(list)
    for path in paths:
        r=read(path); seed,cond=r['seed'],r['condition']
        for g in range(1,11):
            parent=r['frontier'][g-1]; chosen=r['frontier'][g]
            ph=d_holdout[seed,parent['game_hash']]
            pool=[c for c in r['candidates'][1:] if c['generation']==g]
            pairs=[]
            for c in pool:
                y=d_holdout.get((seed,c['game_hash']))
                x=None if c['D'] is None else c['D']-parent['D']
                dy=None if y is None else y-ph
                records.append(dict(level='candidate',seed=seed,condition=cond,generation=g,
                    parent_hash=parent['game_hash'],candidate_hash=c['game_hash'],X=x,Y=dy,
                    eligible=original.outcome_of(c).eligible,selected=c['game_hash']==chosen['game_hash'] and c['candidate']==chosen['candidate'],
                    missing_Y=y is None,coverage='frontier-observed subset, selection-biased'))
                if x is not None and dy is not None:
                    pairs.append((x,dy)); pair_groups[cond,'candidate_observed_subset'].append((x,dy))
            changed=parent['game_hash']!=chosen['game_hash']
            x=chosen['D']-parent['D']; y=d_holdout[seed,chosen['game_hash']]-ph
            records.append(dict(level='selected_transition',seed=seed,condition=cond,generation=g,
                parent_hash=parent['game_hash'],candidate_hash=chosen['game_hash'],X=x,Y=y,changed=changed,
                eligible=original.outcome_of(chosen).eligible,missing_Y=False))
            if changed: pair_groups[cond,'selected_changed'].append((x,y))
            complete=len(pool)==8 and len(pairs)==8
            predicted=gaussian_response(pairs,constant['value']) if complete else None
            gauss.append(dict(seed=seed,condition=cond,generation=g,observed_candidates=len(pairs),total_slots=8,
                Y_observed=y,Y_predicted=predicted,status='MEASURED_APPROXIMATION' if predicted is not None else 'INSUFFICIENT_COMPLETE_POOL',
                assumption='iid bivariate normal; real eligibility, parent option and ties differ'))
            boot=resampled_response(pairs,original.io.derive(seed,cond,g,'selection-bootstrap'),draws=CONFIG['resampling_draws']) if complete else None
            nonparam.append(dict(seed=seed,condition=cond,generation=g,observed_candidates=len(pairs),
                status='MEASURED_EMPIRICAL_POOL' if boot else 'INSUFFICIENT_COMPLETE_POOL',**(boot or {})))
    csv_write(out/'selection_theory/selection_holdout_response.csv',records)
    csv_write(out/'selection_theory/gaussian_response_prediction.csv',gauss)
    csv_write(out/'selection_theory/nonparametric_response.csv',nonparam)
    def prediction_fit(rows):
        rows=[r for r in rows if r['Y_predicted'] is not None]
        error=[r['Y_predicted']-r['Y_observed'] for r in rows]
        return dict(generations=len(rows),
            Pearson=correlation([r['Y_predicted'] for r in rows],[r['Y_observed'] for r in rows]),
            MAE=float(np.mean(np.abs(error))) if error else None,
            signed_bias=float(np.mean(error)) if error else None)
    write(out/'selection_theory/response_summary.json',dict(normal_maximum=constant,
        groups=[dict(condition=c,scope=s,**response_stats(p)) for (c,s),p in pair_groups.items()],
        complete_generation_pools=sum(g['Y_predicted'] is not None for g in gauss),
        prediction_fit=prediction_fit(gauss),
        prediction_fit_by_seed=[dict(seed=s,**prediction_fit([r for r in gauss if r['seed']==s])) for s in original.SEEDS],
        limitation='No holdout evaluation of counterfactuals or unobserved candidates. Missing Y not estimated.'))


def context_diagnostics(source, output):
    paths,_,_=source_files(source)
    rows=[]; snapshots=[]; zero_rank=[]
    for path in paths:
        if path.parent.name!='adaptive': continue
        r=read(path); groups=defaultdict(list); past=defaultdict(lambda:defaultdict(list))
        for h in r['mutation_history']:
            groups[h['decision']['context_key']].append(h)
            d=h['decision']; observed=[v for v in d['mean_rewards'].values() if v is not None]
            gap=max(observed)-min(observed) if observed else 0.
            n=sum(d['counts'].values())
            ps=past[d['context_key']]
            zeros=[arm for arm,vs in ps.items() if vs and all(not v['outcome']['eligible'] for v in vs)]
            negative=[arm for arm,vs in ps.items() if vs and np.mean([v['reward'] for v in vs])<0 and any(v['outcome']['eligible'] for v in vs)]
            pairs=[(i,j) for i in zeros for j in negative if i!=j]
            zero_rank.append(dict(seed=r['seed'],generation=h['generation'],slot=h['candidate'],context=d['context_key'],
                pure_ineligible_zero_vs_negative_exploitation_pairs=len(pairs),
                also_higher_actual_ucb_pairs=sum(d['ucb'][i]>d['ucb'][j] for i,j in pairs),
                proposed_pure_ineligible_zero_arm=h['mutation'] in zeros,
                at_least_one_negative_eligible_arm=bool(negative)))
            for arm,na in d['counts'].items():
                bonus=math.sqrt(2*math.log(max(1,n))/na) if na else None
                snapshots.append(dict(seed=r['seed'],generation=h['generation'],slot=h['candidate'],context=d['context_key'],
                    primitive=arm,context_trials=n,trials=na,mean_reward=d['mean_rewards'][arm],ucb=d['ucb'][arm],
                    bonus_normalized=bonus,between_arm_gap_raw=gap,between_arm_gap_normalized=gap/26,
                    bonus_to_gap=bonus/(gap/26) if bonus is not None and gap>0 else None,
                    gap_status='ZERO_OR_UNOBSERVED' if gap==0 else 'MEASURED'))
            ps[h['mutation']].append(h)
        for ctx,hs in groups.items():
            for arm in original.FAMILIES:
                vals=[h['reward'] for h in hs if h['mutation']==arm]
                rows.append(dict(seed=r['seed'],context_id=ctx,visits=len(hs),operators_observed=len({h['mutation'] for h in hs}),
                    primitive=arm,trials=len(vals),effective_sample_size_unweighted=len(vals),
                    ESS_caveat='count only; dependent parents mean independent-information ESS unidentified',
                    reward_mean=float(np.mean(vals)) if vals else None,
                    reward_variance=float(np.var(vals,ddof=1)) if len(vals)>1 else None))
    csv_write(Path(output)/'reward_landscape/context_summary.csv',rows)
    csv_write(Path(output)/'reward_landscape/ucb_bonus_history.csv',snapshots)
    csv_write(Path(output)/'reward_landscape/actual_ucb_zero_over_negative.csv',zero_rank)


def run(source, output):
    out=Path(output); out.mkdir(parents=True,exist_ok=False)
    difficulty(source,out); selection(source,out); context_diagnostics(source,out)
    write(out/'completed.json',dict(status='COMPLETED',new_experience=0,new_holdout=0))
