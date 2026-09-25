"""Mechanical report generation from completed audit artifacts."""
from collections import Counter,defaultdict
from pathlib import Path
import math
import numpy as np
from .data import read,write
from .summary import read_csv,distribution


def render(out):
    out=Path(out)
    land=read(out/'landscape_summary.json');manifest=read(out/'frozen_manifest.json')
    monotone=read_csv(out/'difficulty_theory/monotonicity_summary.csv')
    d=read_csv(out/'difficulty_theory/D_sample_complexity_comparison.csv')
    response=read(out/'selection_theory/response_summary.json')
    paths=read_csv(out/'fixed_field_theory/task_path_attenuation.csv')
    diag=read_csv(out/'fixed_field_theory/reasoner_failure_diagnostics.csv')
    res=read_csv(out/'fixed_field_theory/resolvent_diagnostics.csv')
    bonuses=read_csv(out/'reward_landscape/ucb_bonus_history.csv')
    ranks=read_csv(out/'reward_landscape/actual_ucb_zero_over_negative.csv')
    seeds='\n'.join(f"| {s['seed']} | {s['Delta_E']['mean']:.6f} | {s['rho_UCB']['mean']} | {s['rho_P']['mean']} | {s['Delta_E_positive']}/{s['actual_slots']} | {s['Delta_E_negative']}/{s['actual_slots']} |" for s in land['seeds'])
    failures=Counter(r['category'] for r in diag if not r['success'])
    confusion=Counter(('below' if r['below_cutoff'] else 'above', 'failure' if not r['success'] else 'success') for r in paths)
    world_rates=defaultdict(list)
    for r in paths:world_rates[r['seed'],r['game_hash']].append(r['below_cutoff']==(not r['success']))
    accuracy=float(np.mean([np.mean(v) for v in world_rates.values()]))
    maxerr=max(abs(r['identity_error']) for r in d)
    split_stats={}
    for split in ('selection','holdout'):
        rs=[r for r in monotone if r['split']==split]
        split_stats[split]=dict(worlds=len(rs),tasks=sum(r['tasks'] for r in rs),
            task_weighted_monotone_fraction=sum(r['monotone_fraction']*r['tasks'] for r in rs)/sum(r['tasks'] for r in rs),
            world_mean_monotone_fraction=float(np.mean([r['monotone_fraction'] for r in rs])),
            reversals=sum(r['reversals'] for r in rs),
            world_mean_censored_fraction=float(np.mean([r['censored_fraction'] for r in rs])))
    stats=dict(landscape=land,monotonicity=split_stats,D_identity_max_error=maxerr,
        selection=response,field_failure_categories=dict(failures),
        path_cutoff_confusion={':'.join(k):v for k,v in confusion.items()},path_cutoff_world_mean_accuracy=accuracy,
        field_tasks=len(paths),full_info_failures=sum(not r['success'] for r in paths),
        max_exact_solve_residual=max(r['linear_solve_residual'] for r in res),
        max_field_difference=max(r['max_field_difference'] for r in res),
        bonus_to_gap=distribution(r['bonus_to_gap'] for r in bonuses),
        actual_ucb_pathology_steps=sum(r['also_higher_actual_ucb_pairs']>0 for r in ranks),
        actual_ucb_pathology_rank_pairs=sum(r['also_higher_actual_ucb_pairs'] for r in ranks))
    write(out/'metrics.json',stats)
    figures='\n'.join(f"- [{p.stem}](figures/{p.name})" for p in sorted((out/'figures').glob('*.png')))
    groups='\n'.join(f"| {g['condition']} | {g['scope']} | {g['n']} | {g['mean_X']} | {g['mean_Y']} | {g['Pearson']} | {g['Spearman']} |" for g in response['groups'])
    text=f'''# MORTRA Frontier v1.2 理論・編集報酬分布監査

新しい進化は実行していません。固定した親世界で既存14操作を測定し、保存済み学習曲線と固定場を監査しました。

## 1. 実測事実

基準実行は36107649938、基準コミットはc060d5c9549eaae913bd7b9555ad2289ff96ff8cです。
監査コミットは{manifest['audit_head']}です。指定18ファイルとv1.2本体の固定を検証しました。
Stage 2は{land['parents']}件の重複を除いた親世界、各14操作×10反復、計{land['candidates']}候補です。
親の更新、選抜、新規holdout生成は0回です。不成立候補を引き直していません。
候補評価CPU合計は{land['total_evaluation_CPU']:.3f}秒です。

提案の期待報酬差ΔEは、同じ親世界で測った操作別平均と当時の提案確率から計算しました。
8 seed平均は{land['Delta_E_seed_mean']:.6f}です。seed単位の記述的bootstrap区間は{land['Delta_E_seed_bootstrap_percentile_95']}です。
これは有限10反復からの推定です。真の報酬期待値が判明したという意味ではありません。
G10後の仮想提案は主要平均へ含めていません。

| seed | 平均ΔE | 平均UCB順位相関 | 平均提案確率順位相関 | ΔE正 / 提案数 | ΔE負 / 提案数 |
|---|---:|---:|---:|---:|---:|
{seeds}

相関のNoneは定数ベクトル等による未定義であり、相関0ではありません。
親世界・世代・課題を独立した進化実験として扱っていません。独立seedは8個です。

## 2. 数学的恒等式

### 固定場

非負行列Kについて||K||∞≤1、q=0.90なら、Neumann級数が収束します。

```math
psi = (I-qK)^(-1)g = sum_(n=0)^infinity q^n K^n g.
```

ある長さLの経路の寄与は q^L prod_i K[s_i,s_(i+1)] です。
これは全経路寄与のうち一項で、全体の固定場ではありません。
完全な決定論的グラフでは各行の重みの和が1なので、スペクトル半径は1、非負レゾルベントの∞ノルムは1/(1-q)=10です。

さらに非goal状態でpsi(s)>0なら、psi(s)=q sum_v K[s,v]psi(v) より、ある後続状態vでpsi(v)≥psi(s)/q>psi(s)です。
完全な決定論的遷移と厳密な場に対するargmaxなら、非goalでの閉路は起こりません。
ただし実装は有限反復・許容誤差・cutoff・行動上限を持ちます。この定理を実装の無条件成功保証としては使いません。

### 難度D

x_i=log2 B_i、task jの成功をy_(j,i)∈{{0,1}}とすると、保存されたDは次の平均です。

```math
D_j = sum_i (x_(i+1)-x_i) [1-(y_(j,i)+y_(j,i+1))/2]
D = mean_j D_j.
```

最初の成功がk>0なら、その後単調に成功する課題では D_j=x_k-x_0-(x_k-x_(k-1))/2 です。
最初から成功なら0、最後まで未成功ならx_M-x_0です。
非単調な課題では z_(j,i)=max_(l≤i)y_(j,l) を作ると、正確に

```math
D_j = capped_log_first_hit_j - half_first_hit_interval_j
      + trapezoid_integral(z_j-y_j).
```

最後の非負項は、初回成功後の失敗による追加面積です。右打切りの課題の真の必要予算は不明です。
したがってDをそのまま「真の必要経験量の対数平均」と呼ぶのは不正確です。
単調課題では区間中点補正付きの有限範囲・打切り付き初回成功予算として解釈できます。

## 3. 近似モデル

単一路近似は b_eff=exp(-mean log K_path) として (q/b_eff)^L です。
これは選んだ経路一項の正確な積を言い換えたものですが、psi全体の近似としては他の経路を無視しています。
この値がcutoff未満でも、他の経路が加算されるため固定場がcutoff未満とは限りません。
逆に一項がcutoff以上なら厳密な固定場の下限になりますが、有限精度Playerの成功保証とは別です。

選抜応答の正規近似は E[Y_selected]≈mu_Y+rho sigma_Y E[max Z_i] です。
m=8の数値積分値は{response['normal_maximum']['value']:.12f}、積分誤差見積もりは{response['normal_maximum']['quadrature_error']:.3g}です。
候補の同一分布・独立性・正規性は仮定であり、実選抜の資格判定、親の維持、追加同点規則まで表す恒等式ではありません。

## 4. 実測との一致

Dの離散恒等式の最大数値差は{maxerr:.3g}です。
選抜課題の単調成功割合（課題数加重）は{split_stats['selection']['task_weighted_monotone_fraction']:.6%}です。
holdout課題では{split_stats['holdout']['task_weighted_monotone_fraction']:.6%}です。
成功から失敗への逆転は、選抜課題で{split_stats['selection']['reversals']}回、holdout課題で{split_stats['holdout']['reversals']}回でした。

固定場は{len(paths)}課題で元のPlayerの行動列・成否と照合しました。
解析専用線形解の最大残差は{stats['max_exact_solve_residual']:.3g}です。
保存Playerとの最大場差は{stats['max_field_difference']:.3g}です。
単一路cutoff予測の世界ごとの正解率平均は{accuracy:.6%}ですが、課題分類の偏りを含むためこれだけで十分な説明とはしません。
混同行列は{stats['path_cutoff_confusion']}です。

## 5. 実測との不一致・未観測

正規選抜応答を局所推定できる全8候補の完全なholdout組は{response['complete_generation_pools']}世代でした。
欠測候補のYは補完していません。完全な組がない世代の正規予測・bootstrapは未推定です。
以下の候補相関は、後にfrontierとして監査された候補だけの選抜偏りを持つ部分集合です。
選ばれた遷移の相関も、全候補母集団の相関に読み替えてはいけません。

| 条件 | 対象 | 件数 | 平均X | 平均Y | Pearson | Spearman |
|---|---|---:|---:|---:|---:|---:|
{groups}

固定場失敗の内訳は{dict(failures)}です。
C_READOUT_CYCLEは初期cutoffを通過した後の行動閉路で、広義には「開始後のreadout失敗」に含まれます。
完全決定論グラフなのでmodal successorの推定誤差はありません。順位選択と数値近似を区別します。

操作間信号/操作内ノイズ比の分布は{land['SNR']}です。
文脈内のUCB bonus/正規化報酬差の分布は{stats['bonus_to_gap']}です。
同じ粗い文脈内でも親世界が変わるため、平均報酬の定常性は保証されません。
操作順位相関は隣接世界{land['stability']['adjacent']}、同文脈{land['stability']['same_context']}、異seed{land['stability']['cross_seed']}です。

不適格候補だけの操作が0平均報酬を持ち、負平均の適格候補を含む操作より上位となった親は{land['pure_ineligible_outrank_parents']}/{land['parents']}件です。
該当操作対は{land['pure_ineligible_outrank_arm_pairs']}件です。
元のUCB履歴でも同様の操作対が実UCB順位で上回った時点は{stats['actual_ucb_pathology_steps']}/640、累計操作対は{stats['actual_ucb_pathology_rank_pairs']}件です。
これは順位関係の実測であり、報酬を変更した場合の最終成果を測った実験ではありません。

## 6. 言えること

Q1: 選抜Xとholdout Yの関係は上表の範囲で定量化できます。候補全体のY欠測があるため、難化の全量をmax-8法則で説明したとは言いません。

Q2: Dは単調性、台形補正、右打切り、逆転面積を分離すれば、有限範囲の対数必要予算に結びつきます。逆転と打切りの頻度は保存表に記録しました。

Q3: 経路長と遷移重みの積は場を弱める一因です。実際の開始場とcutoffを直接照合した分類と、単一路予測の混同行列を区別して示しました。

Q4: 同じ親世界に対する提案分布の期待報酬差は上記ΔEです。平均の符号だけで一律のCase A/B/Cへ分類せず、8 seedの符号と相関を併記しました。「約0」の後付けしきい値はありません。

Q5: 試行数、UCB bonus、報酬ノイズ、世界間順位相関、0報酬の順位関係は別々の観測です。それらの因果寄与は分離できておらず、単一の原因には断定しません。

## 7. まだ言えないこと

10反復で測った操作平均が真の平均であること、粗い文脈を増やせば改善すること、報酬を変えれば進化が改善すること、Playerに本質的欠陥があることは、この監査だけでは結論できません。
局所期待報酬と10世代後の難度は異なる対象です。追加した候補を次の親へ採用しておらず、長期的な改善の因果実験は行っていません。
固定ゲーム言語と固定Playerに対する監査です。一般的な知能や任意ゲーム生成を主張しません。

## 図表・保存物

全候補、操作平均、提案校正、文脈、報酬の順位問題、課題ごとの成功列、選抜の欠測、経路、場、失敗分類をCSVに保存しました。
成果物内の相対リンクはこの報告書の所在を基準にします。

{figures}

**Stage 2と成果物作成を完了して停止しました。結果を見たアルゴリズム変更は行っていません。**
'''
    (out/'FINAL_REPORT.ja.md').write_text(text,encoding='utf-8')
