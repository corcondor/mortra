# MORTRA goal-conditioned補助構成実験

日付: 2026-08-22

## 目的

HAGeo固定未解決問題に対し、ゴールから逆算した型付き未解決義務を補助構成探索へ渡すことで、候補のnative Yuclid証明が増えるかを測る。問題ID、期待解答、外部LLM、dataset既知補助点は使わない。

## 原理と仮説

既知事実の前向き閉包を `F`、ゴールから得たAND/OR型付き義務を `B`、補助構成候補を `C` とする。必要条件は、候補追加後の前向き証明片が同じAND枝の義務と型付き単一化することである。

```text
candidate postconditions -> F(C) -> typed meet with B -> native Yuclid replay
```

仮説は「`B` に条件づけた候補順序が、無条件順序より厳密な義務被覆とnative正答を増やす」である。支持点の重なりや数値incidenceは探索信号に限り、証明受理には使わない。

## 方法

### truth plane

- 正答: native Yuclidが返した証明のみ。
- timeout: 誤答でなくright-censoredとして記録。
- 部分proof DAG、支持重なり、数値incidence: 候補順位だけに使用。
- 問題固有の数値・問題ID・表層文型分岐: 追加しない。

### 実装した資源境界

1. Yuclid subprocessへ候補単位のtimeoutを追加した。
2. proof DAG、candidate forward cone、双方向queueへ壁時計予算を追加した。
3. 各構成族の入力tuple列挙数を制限し、切り捨てた族をartifactへ保存した。
4. 各batch後にatomic progress checkpointを保存した。
5. 時間切れ直前に生成済みの有効なopen枝を捨てず、探索証拠として保持した。
6. 外側で作成済みのproof DAGを双方向探索で再利用した。
7. 全候補の直接postconditionを先に照合し、その後の定理展開だけを公平に時間配分した。

これらは探索スケジューラの変更であり、native証明の受理条件は変更していない。

## 結果

### 固定3問

| 問題 | 条件 | 評価候補 | native正答 | goal-touch | 厳密被覆増分 |
|---|---:|---:|---:|---:|---:|
| `2008CTSTp4` | 1段 | 81 | 0 | 0 | 0 |
| `2022CHNSouthEastMOg11p6` | 1段 | 90 | 0 | 0 | 0 |
| 同上 | 2段 control | 257 | 0 | 0 | 0 |
| 同上 | 2段 treatment | 257 | 0 | 0 | 0 |
| `2002CTSTp25` | 1段、root-first | 8 native replay | 0 | 0 | 0 |

2022 treatmentでは支持重なり増分が最大32まで増えたが、厳密な原子被覆増分、goal-touch、native正答はいずれも0だった。HAGeo数値incidenceのcontrol/treatmentでも追加正答は0だった。

`2002CTSTp25`の最終実験では、38構成族から76候補を残し、8本のopen枝に対して全候補の直接postconditionを照合した。その後41候補、299 cone statesまで定理展開し、上位8候補をnative replayした。エラー0、right-censored 0、追加正答0だった。

### 接続不良の修正過程

| 段階 | open枝 | forward task | 観測 |
|---|---:|---:|---|
| 再コンパイル版 | 0 | 0 | 後向きDAGだけで5秒を消費 |
| DAG再利用、枝未保持 | 0 | 0 | 時間切れ層の部分枝を廃棄 |
| 部分枝保持 | 4 | 1 | 前向き経路が初めて発火 |
| 公平配分 | 8 | 19 | 最初の候補による予算独占を除去 |
| root-first + 展開 | 8 | 41 | 全76候補の直接照合後に展開 |

### 成果物

- `data/goal-conditioned-2008ctst-native-dag-increment-n1-2026-08-22.json`
- `data/goal-conditioned-2022-native-dag-support-n1-2026-08-22.json`
- `data/goal-conditioned-2022-native-dag-increment-control-n2-2026-08-22.json`
- `data/goal-conditioned-2022-native-dag-increment-treatment-n2-2026-08-22.json`
- `data/goal-conditioned-2022-hageo-incidence-control-n1-2026-08-22.json`
- `data/goal-conditioned-2022-hageo-incidence-treatment-n1-2026-08-22.json`
- `data/goal-conditioned-2002ctst-root-plus-expansion-n1-2026-08-22.json`

関連テストは82件成功した。現在の監査済みcapability unionは別実験の `53/89 = 59.55%` であり、本実験による追加正答は0なので加算しない。

## 考察

仮説は現構成族では支持されなかった。候補順位、探索深さ、通信、支持重なりを改善しても、候補のpostconditionが未解決義務へ型付き単一化しなければ正答は増えない。

3問共通で `goal_deduction_count == 0` である。2022の支持重なり32は、支持集合の近さが証明到達性の代理にならない反例である。2002ではopen枝が要求する `simtri` と中間 `eqangle` に対し、既存構成族の直接・1段導出が厳密meetを作れなかった。

したがって現在の主因は「探索量不足」ではなく、次の往復が閉じていないことである。

```text
ground typed obligation
-> executable construction specification
-> candidate postconditions
-> backend certificate / residual
-> re-elaborated typed relation
```

## 結論

停止・予算独占・proof DAG再計算・部分枝廃棄という工学的欠陥は修正できた。一方、固定未解決3問の追加正答は0であり、正答改善を主張しない。

次の実験対象は、open AND枝の原子を仕様として、実行可能な補助構成項を逆合成する機構である。まず `simtri`、穴を含む `eqangle`、`cyclic` を対象に、生成したpostconditionが義務へ単一化し、native replayで新しいgoal-touchを生む場合だけ構成語彙へ昇格する。評価は同じ固定3問のcontrol/treatmentで行う。
