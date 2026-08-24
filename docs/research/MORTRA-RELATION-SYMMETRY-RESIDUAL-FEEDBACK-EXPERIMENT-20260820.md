# MORTRA 関係対称性・証明残差フィードバック実験 2026-08-20

## 原理

補助構成探索を深くしても正答が増えない原因を、次の三層へ分解した。

1. **意味層**: 同じ幾何関係の同値な引数順序を同一視できるか。
2. **探索層**: 候補を追加した後の未解決証明義務を次ラウンドへ戻せるか。
3. **評価層**: 探索前に閉じたnative証明を外側のshard集約が保持するか。

検証した仮説は次の通りである。

- H1: `eqangle` / `eqratio` の正しい対称群を型付き単一化へ入れると、問題別規則を
  追加せず、HAGeo-409の目標から定理グラフへ入れる割合が上がる。
- H2: 各ラウンドのYuclid証明残差を次ラウンドのrelation demandへ戻すと、固定残差の
  反復より追加正答または証明残差改善が生じる。
- H3: baselineで既に証明済みの問題は探索軌道が0本でも正答として保存すべきである。

## 一次資料と公開コードの監査

| 系統 | 参照した一次成果物 | 取り入れた原理 | MORTRAでの扱い |
|---|---|---|---|
| AlphaGeometry | Nature論文、公式実装 | 補助構成を外生項として提案しDD+ARで検証 | 既存の有限構成文法とnative verifier |
| HAGeo | arXiv論文、公式リポジトリ `2217d813...` | N-round / K-trajectory、数値incidence gate | 独立再構成。full code未公開なので完全再現とは呼ばない |
| Newclid | 公式リポジトリ `ac655073...` | DD/AR、native proof JSON | Yuclidを真偽判定に直接使用 |
| FormalGeo | 公式リポジトリ `e7d90421...` | goalをAND/OR subgoalへ分解する後向き探索 | open proof obligationの設計根拠 |
| GenesisGeo | 公式リポジトリ `89f33599...` | 述語対称性、reverse construction、依存追跡、必要性再検査 | Apache-2.0実装の意味を照合し、関係対称群を独立実装 |
| TongGeometry | Nature Machine Intelligence論文 | construction sequenceとproof sequenceの依存差から必要補助点を抽出 | 次段の補助構成必要性判定の設計根拠 |
| MMT | theory view / morphism論文 | 異なる形式体系間の型付き写像 | 今回は候補順位に使わず、表現射の設計根拠のみ |

FormalGeoとTongGeometryの公開コードはGPL系であるため、本実装へコードをコピーして
いない。GenesisGeoはApache-2.0であるが、ここでもファイルの移植ではなく、公開された
述語対称性を数学的に再実装した。

## 方法

### 1. 証明残差の閉ループ化

同一の候補生成、typed-atom順位、数値incidence gate、Yuclid検証を使う二条件を作った。

- `residual-static`: 最初のopen relation demandを全ラウンドで固定。
- `residual-feedback`: 選択候補のnative証明残差を次ラウンドへ戻す。

各ラウンドに次を記録する。

- `relation_demands_in`
- `relation_demands_observed`
- `relation_demands_next`
- `residual_feedback_applied`
- 候補別native proof residual

### 2. 関係対称性

`eqangle(A,B,C,D,E,F,G,H)` を4本の無向直線の角度関係とみなし、次の生成元の有限閉包を
単一化へ導入した。

- 各線分の端点交換
- 左右の角の同時反転
- 二つの角の交換
- 有向角の転置恒等式

同じ群を `eqratio` にも適用した。また6引数になっていた旧
`equal-angle-transitivity` を8引数へ修正し、8引数の
`equal-ratio-transitivity` を追加した。

### 3. 評価集約

内側の実験は `baseline_solved=true` なら探索を行わず、attempt数は0になる。旧外側集約は
attemptだけを見て `solved=false` に上書きしていた。shard自体のnative solvedを論理和へ
入れ、baseline proof JSONとSHA-256も保存するよう修正した。

### 4. 評価規約

- 外部LLM不使用。
- 問題ID分岐、期待解、dataset auxiliary clauses不使用。
- 真偽はYuclid native proofだけで決める。
- timeoutは誤答でなくright-censoredとする。
- 関係対称性の修正に使った問題群は、修正後の未見held-outとは呼ばない。

## 結果

### A. HAGeo-409全目標の定理入口

`scripts/audit_geometry_goal_symmetry_coverage.py` で409問すべてを監査した。

| 条件 | 定理グラフへ入れた目標 | 率 |
|---|---:|---:|
| 旧位置一致 | 389 / 409 | 95.11% |
| 関係対称群 | 408 / 409 | 99.76% |
| 普遍推移射を含む現行核 | 409 / 409 | 100.00% |

対称性だけで回復した内訳は `eqangle` 15問、`eqratio` 4問である。最後の1問は任意形の
`eqratio` で、普遍的な等比推移律により入口を得た。この数値は正答率ではなく、
**後向き探索を開始できる意味被覆率**である。

### B. 残差フィードバック

既知の多段問題 `2005CTSTp11b` では、固定側と閉ループ側の候補経路は変わったが、
`N=3, K=1` では両方未解決だった。固定5問でも修正前・修正後とも追加正答は0だった。

関係対称性で回復した20問のうち、静的条件で完走し未解決だった5問を固定して比較した。

- `residual-static`: 0 / 5
- `residual-feedback`: 0 / 5
- 経路差: 0 / 5
- terminal AR rank差: 全5問で0
- residual support差: 全5問で0

従って、この予算と現在の一段obligation抽出ではH2を支持しない。閉ループを製品既定には
しない。

### C. 集約修正と20問診断

関係対称性で回復した20問を `N=3, K=1` で実行した。

- native baseline正答: 5
- 完走未解決: 5
- right-censored: 10
- execution error: 0
- 観測済み10問に対する正答率: 5 / 10 = 50%
- 全20問に対する保守的下限: 5 / 20 = 25%
- 探索による追加正答: 0

集約修正前は、このbaseline正答5問のうち少なくとも実行中に確認した4問が外側で
`right_censored_timeout` と誤分類された。修正後は5問すべて `solved` としてnative証明書を
持つ。既存の「残り52問」実験には `baseline_solved` shardが0件だったため、監査済み
primary score `51/89 = 57.30%` 自体は今回の修正では増えない。

## 考察

低得点の原因は一つではなかった。

1. **意味の欠落**: 等角・等比の引数対称性がなく、既存18本の等角定理を適用できなかった。
2. **型の不整合**: 6引数の等角推移律が8引数のNewclid表現と接続していなかった。
3. **閉ループの断絶**: 新しい残差を計算しても次ラウンドへ戻していなかった。
4. **評価の過小集計**: baseline solvedをattempt 0のため失敗扱いしていた。
5. **計算コスト**: 候補ごとに完全Yuclid閉包を再計算し、重い角度問題では1軌道が数分に
   達した。

1, 2, 4は普遍的な修正として反映できた。3は配線できたが得点効果がなく、既定採用を
棄却した。残る主要因は、現在のobligationが一段・最大24件で、TongGeometryが使う
construction/proof dependency gapや、GenesisGeoの必要性再検査まで到達していないことで
ある。候補追加後に完全閉包を作り直すため、増分状態再利用も必要である。

## 結論

公開論文と公式コードから再利用可能な原理を特定し、MORTRAへ実装し、409問監査とnative
証明実験まで行った。定理入口の意味被覆率は `389/409` から `409/409` へ改善し、baseline
正答を失う集約バグも修正した。一方、残差フィードバックは固定5問で追加正答0だったため、
正答率改善器としては未成立である。

次の実験は、未解決goalを一段の関係リストへ平坦化せず、construction sequenceとproof
sequenceの依存差を有限OR proof DAGとして保持し、必要性再検査を通った補助構成だけを
増分Yuclidへ渡すことである。

## 再現成果物

- `worker/backend/geometry_proof_hypergraph.py`
- `worker/backend/hageo_search_control.py`
- `scripts/experiment_hageo_passk.py`
- `scripts/benchmark_hageo_passk_sharded.py`
- `scripts/audit_geometry_goal_symmetry_coverage.py`
- `data/hageo409-goal-symmetry-coverage-final-2026-08-20.json`
- `data/residual-static-symmetry-diagnostic20-v2-n3-k1-f1-2026-08-20.json`
- `data/residual-feedback-symmetry-observed5-n3-k1-f1-2026-08-20.json`

## 一次資料

- AlphaGeometry: <https://www.nature.com/articles/s41586-023-06747-5>
- HAGeo: <https://arxiv.org/abs/2512.00097>
- Newclid: <https://github.com/LMCRC/Newclid>
- FormalGeo: <https://github.com/FormalGeo/FormalGeo>
- GenesisGeo: <https://github.com/ZJUVAI/GenesisGeo>
- TongGeometry: <https://doi.org/10.1038/s42256-025-01164-x>
- MMT exchange format: <https://kwarc.info/people/frabe/Research/RK_keappa_08.pdf>
