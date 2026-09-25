"""Descriptive seed-level reporting. No model choices depend on this module."""
from pathlib import Path
import json
import shutil

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

from .protocol import CONFIG, SEEDS, read, write


RANK_METRICS = ['spearman', 'pairwise_accuracy', 'top1_regret', 'top5_recall',
                'positive_precision8', 'eligible_precision8', 'mse']


def macro(frame, by, values):
    return frame.groupby(by, dropna=False)[values].mean().reset_index()


def save_table(frame, path):
    path = Path(path); path.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(path, index=False)


def draw_bar(frame, x, y, path, ylabel, title):
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.bar(frame[x].astype(str), frame[y], color='#287886')
    ax.set_ylabel(ylabel); ax.set_title(title)
    ax.tick_params(axis='x', rotation=60)
    ax.axhline(0, color='#666666', linewidth=.7)
    fig.tight_layout(); fig.savefig(path, dpi=140); plt.close(fig)


def table(frame):
    if frame.empty:
        return '該当する行はありません。'
    cols = list(frame.columns)
    lines = ['| ' + ' | '.join(cols) + ' |', '| ' + ' | '.join(['---']*len(cols)) + ' |']
    for row in frame.itertuples(index=False, name=None):
        cells = ['未定義' if pd.isna(v) else f'{v:.5f}' if isinstance(v, float) else str(v) for v in row]
        lines.append('| ' + ' | '.join(cells) + ' |')
    return '\n'.join(lines)


def summarize(source, folds, replay, output):
    out = Path(output); out.mkdir(parents=True, exist_ok=False)
    source, folds, replay = Path(source), Path(folds), Path(replay)
    for name in ('config.json', 'frozen_manifest.json', 'dataset_manifest.json', 'feature_schema.json'):
        shutil.copyfile(source/name, out/name)
    shutil.copytree(source/'data', out/'data')
    shutil.copytree(source/'diagnostics', out/'diagnostics')
    shutil.copytree(replay, out/'offline_replay')
    tables = {}
    for name in ('row_predictions', 'parent_rank_metrics', 'secondary_predictions', 'feature_importance', 'compute'):
        tables[name] = pd.concat([pd.read_csv(p) for p in sorted(folds.glob('*/'+name+'.csv'))], ignore_index=True)
    pred, rank = tables['row_predictions'], tables['parent_rank_metrics']
    assert set(pred.seed.unique()) == set(SEEDS) and len(pred) == 70000
    assert not pred.duplicated(['row_id', 'model', 'feature_set']).any()
    save_table(pred, out/'prediction/row_predictions.csv')
    save_table(rank, out/'prediction/parent_rank_metrics.csv')
    test = rank[rank.split == 'test']
    seed = macro(test, ['seed', 'model', 'feature_set'], RANK_METRICS)
    defined = test.groupby(['seed', 'model', 'feature_set']).spearman.count().rename('spearman_defined_parents').reset_index()
    seed = seed.merge(defined)
    save_table(seed, out/'prediction/seed_metrics.csv')
    comparisons = []
    for kind in CONFIG['models']:
        for left, right in [('M3', 'M1'), ('M3', 'M0'), ('M3', 'M2'), ('M4', 'M3')]:
            a = seed[(seed.model == kind) & (seed.feature_set == left)].set_index('seed')
            b = seed[(seed.model == kind) & (seed.feature_set == right)].set_index('seed')
            for metric in RANK_METRICS:
                d = a[metric]-b[metric]
                for s, value in d.items():
                    comparisons.append(dict(model=kind, comparison=left+'-'+right, seed=s, metric=metric, difference=value))
    compare = pd.DataFrame(comparisons)
    save_table(compare, out/'prediction/feature_set_comparison.csv')
    model_comparison = seed.groupby(['model', 'feature_set'])[RANK_METRICS].agg(['mean', 'median', 'min', 'max'])
    model_comparison.columns = ['_'.join(c) for c in model_comparison.columns]
    save_table(model_comparison.reset_index(), out/'prediction/model_comparison.csv')
    secondary = tables['secondary_predictions']
    diagnostics = []
    for key, rows in secondary.groupby(['seed', 'model', 'feature_set', 'target']):
        finite = rows.dropna(subset=['truth'])
        diagnostics.append(dict(zip(('seed', 'model', 'feature_set', 'target'), key)) |
            dict(n=len(finite), mse=float(np.mean((finite.prediction-finite.truth)**2)),
                 accuracy=float(np.mean((finite.prediction >= .5) == finite.truth)) if key[-1] != 'delta_D' else np.nan))
    save_table(pd.DataFrame(diagnostics), out/'diagnostics/eligibility_prediction.csv')
    save_table(secondary, out/'diagnostics/secondary_row_predictions.csv')
    pred['squared_error'] = (pred.prediction-pred.truth)**2
    pred['absolute_error'] = abs(pred.prediction-pred.truth)
    breakdown = pred.groupby(['seed', 'model', 'feature_set', 'reward_category']).agg(
        rows=('truth', 'size'), mse=('squared_error', 'mean'), mae=('absolute_error', 'mean')).reset_index()
    save_table(breakdown, out/'diagnostics/reward_class_breakdown.csv')
    save_table(tables['feature_importance'], out/'diagnostics/feature_importance.csv')
    save_table(tables['compute'], out/'diagnostics/compute.csv')
    top = pd.read_csv(replay/'top8_results.csv')
    measures = ['mean_reward', 'best_reward', 'positive_rate', 'eligible_rate', 'max_delta_D', 'beats_parent']
    top_seed = macro(top, ['seed', 'policy'], measures)
    save_table(top_seed, out/'offline_replay/seed_top8_results.csv')
    top_all = macro(top_seed, ['policy'], measures)
    paired_top = []
    for kind in CONFIG['models']:
        for s in SEEDS:
            subset = top[(top.seed == s)]
            for comparator in ('Uniform-8', 'Recorded-UCB-snapshot'):
                left = subset[subset.policy == kind+':M3'].set_index('parent_id')
                right = subset[subset.policy == comparator].set_index('parent_id')
                shared = left.index.intersection(right.index)
                for metric in measures:
                    paired_top.append(dict(seed=s, model=kind, comparator=comparator, metric=metric,
                        parents=len(shared), difference=(left.loc[shared, metric]-right.loc[shared, metric]).mean()))
    paired_top = pd.DataFrame(paired_top)
    save_table(paired_top, out/'offline_replay/paired_seed_differences.csv')
    figdir = out/'figures'; figdir.mkdir()
    fig, axes = plt.subplots(1, 2, figsize=(11, 5))
    for ax, kind in zip(axes, CONFIG['models']):
        x = pred[(pred.model == kind) & (pred.feature_set == 'M3')]
        ax.scatter(x.truth, x.prediction, s=3, alpha=.18)
        lo = min(x.truth.min(), x.prediction.min()); hi = max(x.truth.max(), x.prediction.max())
        ax.plot([lo, hi], [lo, hi], color='#444444'); ax.set_title(kind+' M3, LOSO')
        ax.set_xlabel('Archived reward'); ax.set_ylabel('Predicted reward')
    fig.tight_layout(); fig.savefig(figdir/'predicted_vs_true_reward.png', dpi=140); plt.close(fig)
    fig, axes = plt.subplots(1, 2, figsize=(12, 5))
    for ax, kind in zip(axes, CONFIG['models']):
        for fs in CONFIG['feature_sets']:
            rows = seed[(seed.model == kind) & (seed.feature_set == fs)].sort_values('seed')
            ax.plot(rows.seed.astype(str), rows.spearman, marker='o', label=fs)
        ax.set_title(kind+' held-out parent ranking'); ax.set_ylabel('Seed macro Spearman')
        ax.tick_params(axis='x', rotation=45); ax.legend()
    fig.tight_layout(); fig.savefig(figdir/'ranking_by_seed.png', dpi=140); plt.close(fig)
    draw_bar(compare[(compare.comparison == 'M3-M1') & (compare.metric == 'spearman')].assign(
        label=lambda d: d.model+':'+d.seed.astype(str)), 'label', 'difference', figdir/'M1_vs_M3_paired.png',
        'M3 minus M1 Spearman', 'Paired unseen-seed differences')
    draw_bar(top_all, 'policy', 'mean_reward', figdir/'top8_reward_comparison.png', 'Mean true reward of selected 8', 'Seed-macro offline replay')
    head = pd.read_csv(replay/'oracle_headroom.csv')
    draw_bar(macro(head[head.measure == 'mean_reward'], ['seed'], ['headroom']), 'seed', 'headroom',
        figdir/'oracle_headroom.png', 'Oracle minus Uniform mean reward', 'Saved-pool reward headroom')
    recovery = pd.read_csv(replay/'headroom_recovery.csv')
    rec = macro(macro(recovery[recovery.measure == 'mean_reward'], ['seed', 'policy'], ['recovery']), ['policy'], ['recovery'])
    draw_bar(rec, 'policy', 'recovery', figdir/'headroom_recovery.png', 'Headroom recovery, undefined ratios omitted', 'Seed macro of defined parent ratios')
    pools = pd.read_csv(replay/'proposal_pool_size.csv')
    pools_all = macro(macro(pools, ['seed', 'policy', 'pool_size'], ['mean_reward']), ['policy', 'pool_size'], ['mean_reward'])
    fig, ax = plt.subplots(figsize=(9, 5))
    for policy in ('Uniform-8', 'ridge:M1', 'ridge:M3', 'ridge:M4', 'tree:M1', 'tree:M3', 'tree:M4', 'Oracle-top8'):
        rows = pools_all[pools_all.policy == policy].sort_values('pool_size')
        ax.plot(rows.pool_size, rows.mean_reward, marker='o', label=policy)
    ax.set_xlabel('Available cheap candidates'); ax.set_ylabel('Selected-8 mean reward'); ax.legend(fontsize=8)
    fig.tight_layout(); fig.savefig(figdir/'pool_size_vs_reward.png', dpi=140); plt.close(fig)
    draw_bar(top_all, 'policy', 'eligible_rate', figdir/'eligibility_precision.png', 'Eligible fraction among selected 8', 'Eligibility is not the reward objective')
    draw_bar(breakdown.groupby('reward_category').mse.mean().reset_index(), 'reward_category', 'mse',
        figdir/'reward_class_error.png', 'Mean MSE across available seed/model/set cells', 'Reward-category diagnostic')
    imp = tables['feature_importance']; imp = imp[imp.method == 'held_out_group_permutation']
    imp = imp[(imp.model == 'tree') & (imp.feature_set == 'M3')].groupby('feature').value.mean().reset_index()
    draw_bar(imp, 'feature', 'value', figdir/'feature_importance.png', 'Held-out MSE increase', 'Tree M3 grouped permutation diagnostic')
    summary = dict(status='COMPLETED', rows=7000, parents=50, seeds=SEEDS, folds=8,
        expensive_candidate_evaluations=0, new_evolution=0, online_integration=False,
        config=CONFIG, seed_metrics=seed.to_dict('records'), paired_ranking=compare.to_dict('records'),
        top8_seed=top_seed.to_dict('records'), top8_macro=top_all.to_dict('records'),
        paired_top8=paired_top.to_dict('records'), training_and_test_parent_rows=len(rank),
        recorded_UCB_parents=int((top.policy == 'Recorded-UCB-snapshot').sum()),
        terminal_hypothetical_UCB_parents=int((top.policy == 'Terminal-UCB-hypothetical').sum()))
    # pandas NaN is explicitly rendered null, never a fabricated zero.
    summary = json.loads(json.dumps(summary, default=lambda x: x.item()), parse_constant=lambda _: None)
    write(out/'metrics.json', summary)
    comp = compare[(compare.comparison == 'M3-M1') & (compare.metric == 'spearman')]
    training = macro(rank, ['split', 'model', 'feature_set'], ['spearman', 'top1_regret', 'mse'])
    text = '\n\n'.join([
        '# MORTRA Frontier v1.3: Offline Generalization',
        '## 1. 入力\n50 world・7,000候補。親の静的構造、提案前に観測済みの親のselection評価、具体的編集差分、初回登場時点までの履歴を使用しました。M0〜M4、Ridgeと深さ4の木モデルの設定を実行前に固定しました。',
        '## 2. 禁止した入力\n候補の評価結果は教師ラベル専用です。seed・hash・世代番号は集計と分割専用で、特徴には含みません。game holdout artifactはダウンロードもしていません。新規mutation・Player・oracle評価は0回です。',
        '## 3. 未知seedの予測\n独立単位は8 seedです。各seed内でparentを等重み集計しています。Spearman未定義の定数予測・定数報酬は0に置換しません。\n'+table(seed),
        '## 4. ranking能力\nM3−M1の対応差。正値はSpearmanの改善です。後付けのPASS基準は設けません。\n'+table(comp)+ '\n\n学習側と未見側の診断（学習側parentはfold間で再登場します）:\n'+table(training),
        '## 5. offline top-8\n保存済みpoolから8件を選ぶだけで、新規評価・進化はしていません。Uniformの区間は部分集合抽出のばらつきであり、8 seedに関する信頼区間ではありません。\n'+table(top_all),
        '## 6. Oracle headroom\nOracleは真のreward順の上位8件です。reward以外のeligibilityやdelta_Dの最大値を保証するoracleではありません。分母が1e-12以下の回収率は未定義として、絶対差を残しています。\n'+table(macro(head[head.measure == 'mean_reward'], ['seed'], ['uniform', 'oracle', 'headroom'])),
        '## 7. 具体的editの追加価値\nM3−M2が親構造にeditを足した効果、M3−M0がoperator IDのみとの差、M4−M3が過去履歴を加えた差です。特徴群ごとの追加価値とモデル間の差を分離して保存しました。\n'+table(compare[compare.metric == 'spearman'].groupby(['model', 'comparison']).difference.agg(['mean', 'median', 'min', 'max']).reset_index()),
        '## 8. UCBとの比較\nUCB replayは初回の提案直前の確率を固定して8件抽出します。履歴の途中で反実仮想rewardによるUCB更新は行いません。G10-only parentは次回提案が未記録のためTerminal-UCB-hypotheticalとして分離しています。対応比較は同一parentだけで計算しました。\n'+table(paired_top[paired_top.metric == 'mean_reward']),
        '## 9. 負のseedと限界\nM3−M1が負のseedも全件示します。低い予測精度だけからreward noise、表現不足、学習データ不足の因果を一意には決められません。ineligible=0、eligibleで容易化すると負という既存rewardを変更していません。\n'+table(comp[comp.difference < 0]),
        '## 10. onlineへの根拠\n本結果が直接検査したのは保存pool内・未知seedでの静的予測と選抜です。rankingとtop-8の対応差、oracleとの差を合わせて判断する必要があります。online evolutionの改善やゲームの意味理解を示す実験ではありません。全8 foldの終了後停止し、online実装・報酬変更・特徴追加はしていません。',
    ])
    (out/'FINAL_REPORT.ja.md').write_text(text+'\n', encoding='utf-8')
