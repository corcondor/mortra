# MORTRA: 追加7問の厳密作図チャート閉包

日付: 2026-08-28
対象: HAGeo 409問のうち、既存の認証済み89問を除いた問題
制約: MORTRA内部の外部LLM不使用、期待解答不使用、問題ID分岐不使用

## 目的

既存89問の閉包後も問題を解き続け、停止した問題から再利用可能な最小表現を抽出する。今回は、問題を調べた後に作ったチャートであっても、問題文、構成順序、目標、非退化条件、厳密残差、図を一つの証明書として再生できるところまで実装する。

同時に、次を分離して測る。

1. 観察済み問題を厳密に解けたか
2. 同じチャートが未見問題へ転移したか
3. 量化修復、曖昧一致、期待解答参照で結果を水増ししていないか

## 仮説

個別定理を丸ごと保存する代わりに、次の二つの座標表現を再利用すれば、複数の異なる作図を少ない演算で閉じられる。

- 内接円を単位円に正規化し、辺を接線として表す表現
- 中点、内分、直交射影、既知根を持つ円交点をアフィン演算として表す表現

ただし、対象問題を見てからチャートを実装した段階では、厳密証明は示せても未見汎化は示せない。開発に使った問題を除外した別集団で、転移を独立に測る必要がある。

## 原理

各チャートは次の共通経路を通る。

```text
JGEX + 必要な自然意味
  -> 構成依存順序と目標型の照合
  -> 正規化された厳密座標
  -> 構成点を射として順番に合成
  -> 定義域・非退化条件の消去
  -> 全残差を有理式または代数式として0へ還元
  -> 問題文・証明・図・証明書のSHA-256連鎖
```

問題名はsolverの分岐に使わない。問題名はfixture、監査、成果物の索引にだけ使う。自然文を必要としないチャートは自然文ハッシュへ依存せず、第2交点などJGEXだけでは枝が失われる場合に限って型付き自然意味を要求する。

## 方法

停止問題の構成を直接読み、最終目標から逆向きに必要な恒等式を決めた。その後、構成順序に沿って点を生成し、すべての中間条件と最終目標を同じ厳密体上で再生した。

追加した7チャートは共通ポートフォリオへ登録し、次の三段階で検査した。

1. 対象問題の正例、目標改変、構成改変、役割改変を含む単体試験
2. 認証済み89問を除く320問に対する一括監査
3. 開発時に観察した14問も除く306問に対する未見転移監査

## 結果

### 追加した厳密証明

| 問題 | 再利用可能チャート | 残差 | 証明書SHA-256 |
|---|---|---:|---|
| 2009G6 | `two-euler-midpoints-cross-perpendiculars-orthocenter-line` | 18 | `6ac1d8695cab67dbece2480fed223af44d1ec911e23b28f0d862efc0dc70b4a0` |
| 2021GOWACAp4 | `incenter-side-midpoint-perpendicular-triangle-radical-axis` | 31 | `c40ffcaa9af016741a2614a37eb7d4c63af27a3514a63ac46a6fe3096c34b3bd` |
| 2023IranGOAp4 | `incenter-bisector-orthocenters-midpoint-on-bisector` | 29 | `a862323bab5abc64d5e5efa787a5a550560c5e7372f2389f2259af7336f0f60a` |
| 2021IranGOMp1 | `isosceles-orthocenter-midpoint-trisection-perpendicular` | 11 | `856c0b05c48513df47f661fe372250be9655fe5d63fdd95e26df1dca984f42de` |
| 2023USAMOp1 | `median-projection-second-circle-intersection-midpoint-equidistant` | 9 | `fe736acadcdb150cf794f513a9f6f64a8956f3d13917946897a963b13f63f37b` |
| 2012ARMOg10p2 | `incircle-touchpoint-circumcenter-line-second-root-equals-inradius` | 15 | `a45025b662ef2a56988d52c92d3b00cfd54653180649fcf60442607a96885eee` |
| 2012CGMOp5 | `incircle-two-contacts-bci-circumcenter-equal-angle` | 9 | `cb5b0e585d226be9c286782dd5b41f1d682ab692c27f35d0e67f4792e5800bd2` |

7問で122個の残差がすべて0へ還元された。各問に `.chart-portfolio.json`、`.artifact.json`、`.proof.md`、`.proof-focus.svg` を生成した。

### 全補集合監査

既存認証89問を除いた320問では、今回の7問と以前の開発問題6問を合わせて13件の厳密一致が得られた。

| 指標 | 結果 |
|---|---:|
| 評価問題 | 320 |
| 厳密一致 | 13 |
| 量化修復のみ | 1 |
| 曖昧一致 | 0 |
| 証明書再監査 | 13/13受理 |
| 再生残差 | 244 |
| 証明書拒否 | 0 |

量化修復のみの1問は厳密一致13件へ含めていない。

### 開発問題除外監査

現在のチャートを作る際に内容を観察した14問を除外し、残る306問を再評価した。

| 指標 | 結果 |
|---|---:|
| 評価問題 | 306 |
| 厳密一致 | 0 |
| 量化修復のみ | 0 |
| 曖昧一致 | 0 |
| near attemptを持つ問題 | 7 |

したがって、今回の結果は7問の新しい厳密証明であるが、未見問題への追加正答はまだ0である。

### 回帰

新規7チャート、共通ポートフォリオ、一括監査、成果物生成の重点回帰は43件すべて成功した。全チャート回帰の結果は同日の実行記録へ併記する。

同期MORTRAプロセスにも同じ介入を返し、すでに11/11閉包済みの固定集団を再評価した。新規正答0のため介入の得点採用は拒否されたが、回帰0、曖昧一致0、証明書欠損0を確認した。既に満点の集団で新規得点が出ないことを、効果があったようには扱っていない。

この再評価で、証明済み問題にも `stop_obligation` が表示される状態記録の不整合を発見した。停止義務は未証明問題だけへ付けるよう修正し、証明済み・未証明の両分岐を回帰試験へ追加した。

## 考察

### 何が再利用されたか

単位内接円と接線の表現は、次の4問で共通して使えた。

- 2021GOWACAp4
- 2023IranGOAp4
- 2012ARMOg10p2
- 2012CGMOp5

この表現では、三角形の辺、接点、内心、角の二等分線、垂線、円の第2交点を同じ少数の代数演算へ落とせる。

アフィンな中点・比・射影・既知根消去は、次の3問で使えた。

- 2009G6
- 2021IranGOMp1
- 2023USAMOp1

これにより、Euler中点、三等分点、直交射影、第2円交点を、問題ごとに別の数値解法として持たずに記述できた。

### 何がまだ足りないか

開発問題を除外すると306問で追加正答0だった。原因は証明の厳密性ではなく、構造照合の被覆が狭いことである。現在のチャートは、同じ正規化表現を共有していても、構成DAGと目標型がほぼ同じ場合にしか発火しない。

次に必要なのはチャート数を無差別に増やすことではない。near attempt 7問について、どの構成射または双方向変換が1本不足しているかを型付き差分として抽出し、一つの追加で複数問を閉じられる場合だけ昇格する必要がある。

### 解法暗記との境界

問題ID・期待解答による分岐はない。しかし7チャートは対象問題を見てから作ったため、評価上はposthocである。この点を隠して未見正答率へ加算すると解法暗記との区別がつかなくなる。

厳密証明と未見汎化を別に報告したことで、次の二つを同時に保持できる。

- MORTRAが対象7問を実際に証明し、図と証明書を生成できること
- 現時点で、その改善が別の未見問題へ転移した証拠はないこと

## 結論

処理を止めずに7問を追加で厳密閉包した。13件の統合証明書は244残差を再生して全件受理され、新規チャートを含む重点回帰43件も成功した。

一方、開発問題を除外した306問で厳密転移は0だった。今回の成果は厳密な問題解決と再利用表現の実装であり、未見汎化の得点上昇ではない。この境界を固定した上で、次はnear attempt 7問の型付き差分から、複数問題に効く最小の構成射を抽出する。

## 再現

```text
python scripts/audit_exact_chart_transfer.py \
  --excluded-union data/hageo-certified-capability-union-fused11-closure-2026-08-28.json \
  --dataset data/hageo-409-jgex-2026-08-18.txt \
  --natural-dataset data/hageo-409-natural-language-2026-08-26.json \
  --output data/hageo-409-exact-chart-complement-seven-more-2026-08-28.json

python scripts/audit_exact_chart_transfer.py \
  --excluded-union data/hageo-certified-capability-union-fused11-closure-2026-08-28.json \
  --development-problems data/exact-chart-observed-development-problems-2026-08-28.txt \
  --dataset data/hageo-409-jgex-2026-08-18.txt \
  --natural-dataset data/hageo-409-natural-language-2026-08-26.json \
  --output data/hageo-409-exact-chart-source-excluded-seven-more-2026-08-28.json

python scripts/audit_exact_chart_transfer_artifacts.py \
  --transfer-report data/hageo-409-exact-chart-complement-seven-more-2026-08-28.json \
  --artifact-dir artifacts/exact-chart-complement-seven-more-20260828 \
  --output data/hageo-409-exact-chart-complement-seven-more-artifact-audit-2026-08-28.json
```

## 成果物

```text
data/hageo-409-exact-chart-complement-seven-more-2026-08-28.json
data/hageo-409-exact-chart-source-excluded-seven-more-2026-08-28.json
data/hageo-409-exact-chart-complement-seven-more-artifact-audit-2026-08-28.json
artifacts/exact-chart-complement-seven-more-20260828/
```
