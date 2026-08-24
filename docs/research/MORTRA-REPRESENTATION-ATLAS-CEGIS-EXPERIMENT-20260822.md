# MORTRA 表現Atlas・残差駆動補助構成CEGIS実験

実施日: 2026-08-22

## 1. 目的

未解決の幾何義務を一つの座標多項式表現に固定せず、同じ数学的関係を内積・二次形式・行列式へ移してから、未解決残差を減らす補助構成を有限合成する。問題ID、数値、問題文、既知の補助点を探索規則へ入れず、固定未解決問題で追加正答への因果効果を測る。

## 2. 原理

### 2.1 表現chart

- 計量chart: `perp`、`cong`、線分長方程式を平方距離の係数ベクトルへ移す。偏極恒等式で内積と二次形式を往復する。
- アフィンchart: `coll`、`para`、incidenceを2次元のbracket、行列式、rank条件へ移す。
- 変換は文字列置換ではない。正規化ベクトルの比例を検査し、Cartesian多項式へ戻した差が厳密に0となる場合だけ同値証明書を発行する。

### 2.2 残差駆動CEGIS

証明目標はOR分岐を混ぜず、各AND分岐を独立に扱う。候補構成のpostconditionが一つの整合した分岐の残差を減らす場合だけ検証へ送り、Newclid/GCLC/Wu/Gröbnerなどの外部証明書を再生できた場合だけ昇格する。

構成の存在条件はpostconditionではない。`diff(a,a)`、重複点を含む`ncoll`、退化線分を含む`npara/nperp`は静的に反証する。真偽不明の条件はopen obligationとして保持し、実行候補へ入れない。

## 3. 情報理論・代数的言語理論との関係

Stanford Stats 311の情報理論は、次の測定設計に利用できる。

```text
typed obligation --encoder/chart--> backend representation
                 --channel/bridge--> certificate
                 --decoder/replay--> typed theorem
```

chartの情報保持率、bridgeによる識別可能性の縮約、残差の減少量、候補集合のmetric entropyを測れる。ただしMORTRAの主な誤りは確率的な通信雑音ではなく、意味の欠落、部分関数、未証明の非退化条件である。したがって通信路符号化と同一視せず、測定原理として使う。

arXiv:2608.13433のC-RASP分解理論から採用する中心原則は「有限語彙だけでは長さ一般化せず、遷移の合成代数が決める」である。MORTRAでは射名の有限性ではなく、型付き合成、対称性、証明書付きchart往復、長いproof traceでの状態分離を測る必要がある。同論文の定理は文字列認識用であり、幾何証明ハイパーグラフへ直接適用したとは主張しない。

## 4. 実装

- `worker/backend/geometry_representation_atlas.py`
  - 計量・アフィンchart
  - 正規形署名のcache
  - exact Cartesian replay
- `worker/backend/typed_construction_contracts.py`
  - 型付き穴から構成contractを逆単一化
  - 一貫したAND分岐置換
  - side-conditionの証明済み/open/矛盾分類
- `worker/backend/typed_construction_cegis.py`
  - 残差順位、反例oracle、exact verifier gate
  - 未証明・矛盾要件を高価な検証前に停止
- `scripts/experiment_newclid_construction_stalk.py`
  - production候補列へ接続
  - 実行可能候補だけをNewclidへ渡す
  - 棄却理由と証明書hashをtraceへ保存

## 5. 方法

固定未解決3問を同じ`depth=1 / branch=4 / beam=4 / seed=0`で比較した。

- control: 通常の型付き構成列挙
- treatment: 表現Atlas + contract逆合成 + requirement gate
- 真理面: native Yuclid replayのみ
- 外部LLM: 不使用

指標は追加正答、構成エラー、最小native AR残差、chart経由候補、矛盾棄却数である。エラー実行の`residual=0`は進捗として数えない。

## 6. 結果

関連単体・統合テストは **130件すべて成功**した。

| 問題 | control error | treatment error | 最小残差 control→treatment | 追加正答 |
|---|---:|---:|---:|---:|
| 2000USATSTp2 | 1 | 0 | `2 → 2` | 0 |
| 2016G6 | 3 | 0 | `2 → 2` | 0 |
| 2024PlanetCupp10 | 3 | 0 | `2 → 2` | 0 |

集計:

- 構成エラー: `7 → 0`
- 静的に反証したcontractインスタンス: 2,395
- retained planの未証明条件付き候補: 18
- runtime全候補の未証明条件付き候補: 76
- 実問題でchart経由となった候補: 0
- native残差改善: 0/3
- 追加正答: 0/3

## 7. 考察

要件ゲートには因果効果があった。以前は見かけ上の残差減少を優先して`intersection_pp(a,m,n,a,e,f)`のような`diff(a,a)`を要求する不可能な候補を実行していた。修正後は3問すべてで構成エラーが消えた。

一方、得点仮説は支持されなかった。固定3問のopen obligationはgroundな`lequation`または直接の`perp/para`が中心で、型付き穴を持つ計量chart候補へ到達しなかった。chartの単体往復は厳密でも、proof-stateからchartを選択し、groundな代数義務をWu/Gröbnerへ送り、得た補題を幾何関係へ戻す経路が閉じていない。

これは解法暗記の不足ではない。必要なのは、有限語彙の追加ではなく次の合成である。

1. ground relationをchartごとの実行可能goalへloweringする。
2. backendの証明残差を型付き関係へre-elaborateする。
3. postconditionが現在のopen obligationと単一化する補助構成だけを生成する。
4. 長いtraceでも同じ型付き遷移代数が状態を分離するかheld-outで測る。

## 8. 結論

表現chart、残差駆動CEGIS、要件証明ゲートは実装され、健全性と実行安定性は改善した。しかし固定未解決3問では追加正答0であり、正答率向上は実証されていない。

次の実装対象は、groundな内積・行列・複素座標・三角関数chartをbackend goalとして実行し、その証明書を元の型付き幾何関係へ戻す双方向bridgeである。有限語彙だけでなく、長い射合成を保つ遷移代数として評価する。

## 9. 再現

集計artifact:

- `data/representation-atlas-cegis-summary-2026-08-22.json`

主要arm:

- `data/representation-atlas-typed-control-2000usatstp2-2026-08-22.json`
- `data/representation-atlas-typed-treatment-v2-2000usatstp2-2026-08-22.json`
- `data/representation-atlas-typed-control-2016g6-2026-08-22.json`
- `data/representation-atlas-typed-treatment-2016g6-2026-08-22.json`
- `data/representation-atlas-typed-control-2024planetcup-p10-2026-08-22.json`
- `data/representation-atlas-typed-treatment-2024planetcup-p10-2026-08-22.json`

一次資料:

- Stanford Stats 311 lecture notes: https://web.stanford.edu/class/stats311/lecture-notes.pdf
- Algebraic Decomposition Theory for Transformer Length Generalization: https://arxiv.org/abs/2608.13433
- 公式実装: https://github.com/bveseli/state-tracking-crasp
