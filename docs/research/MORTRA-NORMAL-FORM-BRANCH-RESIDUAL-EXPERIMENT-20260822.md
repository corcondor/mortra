# MORTRA 正規形証明残差・AND/OR 分岐探索実験

実施日: 2026-08-22

## 1. 目的

未解決の型付き幾何義務を単なる述語名の一致で順位付けせず、現在までに得た多項式証明書でどこまで簡約できるかを探索信号にする。特に、FormalGeo 由来の OR 分岐と各分岐内の AND 条件を保ったまま、Newclid/GCLC/Wu/Gröbner 系の中間結果を交換できるかを検証する。

問題番号、数値、問題文の表層パターンによる分岐は追加しない。

## 2. 原理と仮説

現在の仮定から生成されるイデアルを `I`、未解決目標の一つを `g` とする。候補操作後の基底に対する剰余 `NF(g mod I)` が小さくなる操作は、目標を閉じる方向へ進んでいる可能性がある。

証明目標は次の形を保つ。

```text
(g11 AND g12 AND ...) OR (g21 AND g22 AND ...) OR ...
```

異なる OR 分岐の原子を混ぜて進捗を水増ししてはならない。各 AND 分岐を独立に簡約し、最良の整合した一分岐を次の辞書式順位で評価する。

```text
(未証明原子数, 剰余の総項数, 最大次数, 総演算数)
```

実験仮説は「同じ時間予算なら、この順位を使う探索は min-fill 探索より多くの未解決義務を閉じる」である。

## 3. 方法

### 3.1 型付き義務から多項式分岐へ

`construction_block_proof_dag.py` で型付き関係の AND/OR 構造を保持し、座標多項式へ lowering する。一原子でも lowering できない AND 分岐は、条件を勝手に弱めず分岐全体を棄却する。座標化後に同一となる分岐は同値類として統合する。

### 3.2 証明残差

`polynomial_proof_residual.py` に二つのモードを実装した。

1. bounded certified Buchberger: 各基底要素が初期生成元から従う証明 DAG を再生し、イデアル所属を検査する。
2. direct message reduction: 探索途中で交換された厳密な separator 多項式だけを除数にして順序付き多項式除算を行い、`target - sum(q_i g_i) - remainder = 0` を再生する。

2 は完全 Gröbner 基底に対する正規形ではない。剰余ゼロなら当該除算証明を再生できるが、非ゼロは「現在のメッセージでは閉じなかった」という限定的な探索信号にすぎない。これだけで最終解答を採択しない。

### 3.3 探索器への接続

次を実装した。

- local elimination と chordal elimination に `residual_conditioned` 順序を追加
- 実行可能な候補だけを残差評価
- 各厳密消去出力を次段の separator message として累積
- 候補ごとの残差順位、失敗理由、証明書再生結果を trace に保存
- `run_jgex_exact_specialist.py` のプロセス境界を越えて AND/OR 分岐を JSON で搬送
- HAGeo 実験 runner から未解決義務分岐を exact specialist へ供給

### 3.4 比較条件

固定未解決問題2問について、同一問題・同一初期状態・同一 wall-clock 予算で逐次比較した。

- control: `min_fill`
- treatment: `residual_conditioned`

保存された消去証明書はすべて再生検査する。

## 4. 実装中に判明した失敗

最初は候補ごとに bounded Buchberger 基底を再計算した。この方式は `2024PlanetCupp10` で30秒以内に treatment が1ノードも完了せず、候補順位付け自体が探索を停止させた。

そこで、候補作用が実際に生成した separator message に対する増分的な厳密除算へ変更した。また、非実行候補の順位付け、非退化条件を満たさない preview pivot、座標化で重複した OR 分岐を除去した。

この変更は証明の採択条件を弱めていない。完全性を主張しない非ゼロ剰余を探索順序にだけ使う。

## 5. 結果

### 5.1 テスト

関連する単体・統合・プロセス境界テストは **75件すべて成功**した。

確認した主な性質:

- 推移的なイデアル所属の再生
- AND/OR 分岐間の不正な原子混合を禁止
- 非ゼロ剰余を証明済みに昇格しない
- direct message reduction の恒等式再生
- subprocess 経由の分岐保存

### 5.2 固定未解決問題

| 問題 | 予算/arm | control local/separator | treatment local/separator | treatment残差 | 追加正答 |
|---|---:|---:|---:|---:|---:|
| 2024PlanetCupp10 | 20秒 | 6 / 4 | 6 / 1 | `(1,8,2,23)`、全段同一 | 0 |
| 2016G6 | 25秒 | 9 / 2 | 6 / 0 | `(1,4,2,7)`、全段同一 | 0 |

両 arm とも right-censored timeout で未解決だった。treatment の保存済み証明書は両問とも exact replay に成功したが、未解決義務を閉じず、残差も一度も減少しなかった。

## 6. 考察

### 6.1 確立したこと

- 型付き AND/OR 義務を壊さずに worker まで運び、多項式残差として探索器へ戻す経路は動作する。
- 消去エージェントの出力を再生可能な多項式メッセージとして交換できる。
- 問題固有の解法や数値を追加せず、探索制御を差し替えられる。

### 6.2 支持されなかったこと

現在の実座標 chart と separator message だけで作った剰余が、固定未解決2問の有効候補を識別するという仮説は支持されなかった。残差が平坦なので、探索深度を増やしても同じ chart 内では候補選択の情報が増えない。

treatment は chordal 段階で複数候補を厳密評価する費用を負い、同時間内の separator node 数も減った。したがって、現方式をそのまま全探索へ広げる根拠はない。

### 6.3 次のボトルネック

不足は主に探索順序ではなく、同じ幾何関係を異なる計算表現へ移す atlas と、残差から補助構成を合成する閉ループである。

優先する chart は次の通り。

1. `lequation` と `perp` を結ぶ偏極・内積・二次形式 chart
2. incidence/affine 条件を結ぶ行列・rank・determinant・Cramer chart
3. 円・角・相似を結ぶ複素座標 chart
4. 距離・面積・辺比を結ぶ三角関数・正弦定理・余弦定理・Heron chart

その後、各 OR 分岐の未解決剰余を postcondition とし、型検査可能な補助点・補助線候補を有限合成する CEGIS を接続する。候補は剰余を実際に減らし、かつ証明書を再生できた場合だけ昇格させる。

## 7. 結論

正規形証明残差の配線と厳密な分岐保持は実装できた。しかし固定未解決2問では **追加正答0** であり、現在の残差だけでは正答率向上を示せない。

この実験は「もっと深く探索すればよい」という仮説を支持せず、次の得点差が表現 chart の選択と残差駆動の補助構成合成にあることを示した。ここを実装・ablation して初めて、正答率への因果効果を測れる。

## 8. 再現方法

```powershell
$researchSources = $env:MORTRA_RESEARCH_SOURCES
$env:PATH="$researchSources\Newclid\.venv\Scripts;$researchSources\boost_1_88_0\lib64-msvc-14.3;$env:PATH"
python -B -m pytest worker/backend/test_polynomial_proof_residual.py worker/backend/test_polynomial_obligation_alignment.py worker/backend/test_local_polynomial_elimination.py worker/backend/test_chordal_buchberger_elimination.py worker/backend/test_construction_block_proof_dag.py worker/backend/test_polynomial_relation_reelaborator.py worker/backend/test_bounded_macaulay_membership.py scripts/test_run_jgex_exact_specialist.py scripts/test_experiment_hageo_passk.py -q
```

最終比較 artifact:

- `data/normal-form-branch-residual-executable-2024planet-2026-08-22.json`
- `data/normal-form-branch-residual-executable-2016g6-2026-08-22.json`

初期の計算量失敗を含む診断 artifact:

- `data/normal-form-branch-residual-2024planet-2026-08-22.json`
- `data/normal-form-branch-residual-incremental-2024planet-2026-08-22.json`
- `data/normal-form-branch-residual-shortlist-2024planet-2026-08-22.json`
- `data/normal-form-branch-residual-diagnostic-2024planet-2026-08-22.json`
- `data/normal-form-branch-residual-direct-2024planet-2026-08-22.json`
