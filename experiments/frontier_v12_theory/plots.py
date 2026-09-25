"""Plots use measured artifacts; absent candidate holdout data remain absent."""
from collections import Counter,defaultdict
import math
from pathlib import Path
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from .summary import read_csv


def render(out):
    out=Path(out);figdir=out/'figures';figdir.mkdir(exist_ok=False)
    def save(fig,name):
        fig.tight_layout();fig.savefig(figdir/(name+'.png'),dpi=140);plt.close(fig)
    def scatter(rows,x,y,name,title,xlabel=None,ylabel=None):
        fig,ax=plt.subplots(figsize=(9,5))
        valid=[r for r in rows if r.get(x) is not None and r.get(y) is not None]
        if valid:ax.scatter([r[x] for r in valid],[r[y] for r in valid],s=12,alpha=.5)
        else:ax.text(.5,.5,'Not estimable: missing complete candidate holdout pools',ha='center',transform=ax.transAxes,wrap=True)
        ax.set(title=title,xlabel=xlabel or x,ylabel=ylabel or y);save(fig,name)
    cal=read_csv(out/'reward_landscape/adaptive_vs_uniform_expected_reward.csv')
    actual=[r for r in cal if r['actual_proposal']]
    scatter(actual,'rho_UCB','Delta_E','ucb_vs_true_reward','Observed pre-slot UCB calibration against 10-replicate estimates')
    fig,ax=plt.subplots(figsize=(10,5));seeds=sorted({r['seed'] for r in actual})
    ax.boxplot([[r['Delta_E'] for r in actual if r['seed']==s] for s in seeds],tick_labels=seeds)
    ax.axhline(0,color='black',lw=1);ax.set(title='Expected reward advantage: Adaptive minus Uniform',xlabel='Seed',ylabel='Delta E (dependent proposal snapshots)')
    save(fig,'adaptive_vs_uniform_expected_reward')
    fig,ax=plt.subplots(figsize=(10,5))
    for s in seeds:
        vals=defaultdict(list)
        for r in actual:
            if r['seed']==s:vals[r['generation']].append(r['R1'])
        ax.plot(sorted(vals),[np.mean(vals[g]) for g in sorted(vals)],label=str(s),marker='.')
    ax.legend(ncol=4);ax.set(title='Top-1 regret against estimated best primitive',xlabel='Parent generation',ylabel='Tie-averaged regret');save(fig,'proposal_regret_by_generation')
    snr=read_csv(out/'reward_landscape/signal_noise.csv')
    scatter(snr,'V_noise','V_signal','reward_signal_vs_noise','Within-operator noise vs between-operator estimated signal')
    stability=read_csv(out/'reward_landscape/operator_stability.csv')
    ids=sorted({r['parent_i'] for r in stability}|{r['parent_j'] for r in stability});idx={k:i for i,k in enumerate(ids)}
    mat=np.full((len(ids),len(ids)),np.nan)
    for r in stability:
        if r['Spearman'] is not None:mat[idx[r['parent_i']],idx[r['parent_j']]]=mat[idx[r['parent_j']],idx[r['parent_i']]]=r['Spearman']
    fig,ax=plt.subplots(figsize=(8,7));im=ax.imshow(mat,vmin=-1,vmax=1,cmap='coolwarm');fig.colorbar(im,ax=ax)
    ax.set(title='Distinct-parent operator reward rank correlation',xlabel='Parent index (seed, hash order)',ylabel='Parent index');save(fig,'operator_stability_matrix')
    contexts=read_csv(out/'reward_landscape/context_summary.csv');groups=defaultdict(list)
    for r in contexts:groups[f"{r['seed']}:{r['context_id']}"].append(r['trials'])
    fig,ax=plt.subplots(figsize=(12,6));ax.boxplot(list(groups.values()),tick_labels=list(groups));ax.tick_params(axis='x',rotation=60)
    ax.set(title='Actual v1.2 trials per primitive within each context',ylabel='Trials per primitive');save(fig,'context_sample_counts')
    bonus=read_csv(out/'reward_landscape/ucb_bonus_history.csv')
    scatter(bonus,'between_arm_gap_normalized','bonus_normalized','ucb_bonus_vs_reward_gap','UCB bonus vs observed normalized mean-reward gap')
    d=read_csv(out/'difficulty_theory/D_sample_complexity_comparison.csv')
    scatter(d,'mean_capped_log_threshold','D_from_curve','D_vs_mean_log_sample_complexity','Recorded D vs capped first-success log budget')
    pred=read_csv(out/'selection_theory/gaussian_response_prediction.csv')
    scatter(pred,'Y_predicted','Y_observed','selection_predicted_vs_observed','Normal max-8 selection response; complete pools only')
    paths=read_csv(out/'fixed_field_theory/task_path_attenuation.csv')
    fig,ax=plt.subplots(figsize=(10,5))
    for ok,label,color in ((True,'Full-info task success','#168265'),(False,'Full-info task failure','#b44e4e')):
        vals=[r['log_A_path']/math.log(10) for r in paths if r['success']==ok]
        if vals:ax.hist(vals,bins=50,alpha=.55,label=label,color=color)
    ax.axvline(-7,color='black',ls='--');ax.set(title='Single shortest-path contribution (not the total field)',xlabel='log10 path contribution',ylabel='Task count (not independent worlds)');ax.legend();save(fig,'path_attenuation_vs_success')
    res=read_csv(out/'fixed_field_theory/resolvent_diagnostics.csv')
    fig,ax=plt.subplots(figsize=(10,5))
    for ok,label in ((True,'Success'),(False,'Failure')):
        vals=[math.log10(max(r['start_psi_frozen'],np.finfo(float).tiny)) for r in res if r['success']==ok]
        if vals:ax.hist(vals,bins=50,alpha=.55,label=label)
    ax.axvline(-7,color='black',ls='--');ax.set(title='Frozen solver start field and unchanged cutoff',xlabel='log10 psi(start)',ylabel='Task count');ax.legend();save(fig,'psi_start_vs_cutoff')
    diag=read_csv(out/'fixed_field_theory/reasoner_failure_diagnostics.csv')
    counts=Counter(r['category'] for r in diag if not r['success'])
    fig,ax=plt.subplots(figsize=(10,5));ax.bar(list(counts),list(counts.values()),color='#b65a51');ax.tick_params(axis='x',rotation=20)
    ax.set(title='Full-information failure diagnostics',ylabel='Task count');save(fig,'reasoner_failure_categories')
