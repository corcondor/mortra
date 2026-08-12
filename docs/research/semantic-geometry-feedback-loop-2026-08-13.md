# Semantic Geometry Feedback Loop v1

日付: 2026-08-13

## 仮説

同じ型付き幾何状態を空間的に観測し、候補関係を独立検証してReasonerへ戻すと、
表現を後付けの表示にせず証明探索へ利用できる。

## 実装

```text
Fact / exact coordinate state
  -> bounded spatial inspection
  -> perp / para / cong / coll / midp candidates
  -> safe exact-rational polynomial identity
  -> one-candidate proof ablation
  -> relevant certified seed only
  -> forwardChain
  -> proof DAG
  -> synchronized Proof Scene Beat
```

座標の由来を分離する。

- `given_exact`: 座標そのものが数学的入力。厳密恒等式が0なら証明事実として使用可能。
- `constructed_witness`: 条件を満たす一つの見本。候補は予想として保存するが証明へ入れない。

8点以下は点対を完全観測し、それより大きい状態は前提・目標に現れる線分だけを観測する。
候補総数にも上限を置く。認証候補を全投入せず、1件ずつ追加したときに証明が初めて閉じるかを
測り、証明寄与のある最小候補だけを選択する。

## 実測

正例6件、負例2件。直接目標の座標検証を禁止し、中間命題が証明を開くかだけを測った。

| 指標 | 結果 |
|---|---:|
| baseline proof rate | 0/6 |
| visual feedback proof rate | 6/6 |
| expected intermediate recall | 6/6 |
| proposal precision after exact verification | 92.6% |
| proof-opening candidates | 8 |
| selected reasoning seeds | 6 |
| selected seed precision | 100% |
| negative false acceptance | 0/2 |
| mean augmented proof steps | 2.0 |

テストはunit、constructed-witness negative、near-relation negative、平行移動・回転・拡大の
metamorphic、座標counterfactual、Proof Scene provenanceの6件。

## Artifact

- `data/visual-reasoning-loop-experiment.json`
- `data/visual-reasoning-demo.json`
- `/proof?p=visual-loop`

## 4軸への寄与

| 軸 | このsliceで実装・観測したこと | 状態 |
|---|---|---|
| Reasoning | 厳密座標から認証した中間命題をreasonerへ戻し、6/6で証明を開いた | REPRODUCED（限定条件） |
| Discovery | 図の空間関係から未明示の補助関係を列挙し、反実仮想で寄与を選別した | PROTOTYPE |
| Generation | 証明DAGを生成可能だが、このsliceでは新規問題生成を評価していない | PROTOTYPE / 未測定 |
| Mathematical Experience | 認証された発見と証明を同じProof Sceneで再生する | PROTOTYPE |

## 最小プロダクト仮説

- 想定利用者: 大学受験・数オリの幾何を学ぶ人、解答を作る人。
- 痛み: 静的PDFや通常の解説では「どの補助関係を、なぜ見つけたか」が消える。
- 代替: 紙の解答、解説動画、一般チャットAI。
- 優位性仮説: 表示する補助関係が証明器で認証され、証明DAGのどこを開いたかまで追える。
- 最小slice: `/proof?p=visual-loop` で、発見した中間命題から結論までを一つのsceneとして再生する。
- 継続利用仮説: 複数解法比較、途中状態scrub、誤答時の反例表示があれば再訪理由になる。
- 支払意思・配布経路: 未測定。既存の作問コミュニティと短い実演動画で検証する。
- 次の行動指標: scene完走率、途中状態の再生回数、理解度pre/post、共有率、再訪率。

## 限界と反証条件

これは厳密座標が与えられた小規模な座標幾何での成功であり、一般の数オリ幾何性能ではない。
constructed witnessに見える関係を普遍命題へ昇格できない。円・接線・共円、補助点・補助円の
構成証明書、複数候補を必要とする探索、未見自然文corpusは未実装。

次の反証実験では、未見幾何を固定し、baselineとvisual loopでproof rate、candidate precision、
false proof、補助構成recall、proof lengthを比較する。改善が無い、またはfalse proofが増えるなら、
visual reasoning aid仮説はその範囲では棄却する。
