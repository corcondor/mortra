# MORTRA と Kimi K3・体系的数学推論研究の比較

実施日: 2026-08-22

## 1. 目的

Kimi K3を含む最新の推論アーキテクチャと、MORTRAが必要とする数学知識表現・形式推論・局所協調の研究を比較し、模倣すべき機構と採用すべきでない部分を分離する。

## 2. Kimi K3の構造

Kimi K3は2.8T総パラメータ、104B活性パラメータ、93層、1M token contextのnative multimodal MoEである。

- sequence方向: 3層のKimi Delta Attentionと1層のGated MLAを反復し、効率的な局所・再帰混合と周期的な大域相互作用を両立する。
- depth方向: Block Attention Residualsが過去のblock表現を選択的に参照する。K3は8 blockに分割する。
- width方向: Stable LatentMoEが896 routed expertsからtokenごとに16 expertを選び、2 shared expertsを併用する。
- multimodal: MoonViT-V2の視覚特徴を共通embeddingへ写す。
- long horizon: partial rollout、永続KV cache、再開可能sandboxにより長いtrajectoryを中断・再開する。
- post-training: general、agent、codingの3領域とlow/high/maxの3 effortからなる9 expert policyをMulti-Teacher On-Policy Distillationで統合する。

公式報告値はMathVision 94.3、Python併用97.8、GPQA Diamond 93.5である。ただし、これは確率的生成モデルの評価であり、native証明書再生率ではない。

## 3. 関連研究との比較

| 研究 | 中心原理 | MORTRAへ直接移せる部分 | 移せない・未証明の部分 |
|---|---|---|---|
| Kimi K3 | hybrid attention、AttnRes、sparse MoE、persistent rollout | 局所/大域schedule、block残差、疎agent routing、探索再開 | 2.8T重み、自然言語RL、確率的正答を真理判定に使うこと |
| C-RASP分解理論 | 長さ一般化を語彙数でなく遷移の合成代数で特徴化 | 射列の合成代数、長さheld-out、状態分離の評価 | 文字列言語の定理を証明hypergraphへそのまま適用すること |
| OpenMath / MMT | symbolの意味、theory graph、viewによる体系間写像 | 有限語彙、型、chart間の可逆view、証明書交換規約 | それ自体による補助構成探索 |
| Sheaf-ADMM | 局所状態全体でなく隣接射影だけを合意させる | agentごとの局所chartと共有境界、残差による協調 | Sudoku等の連続潜在空間での結果を形式証明へ外挿すること |
| HAGeo | 数値incidence gateと有限補助構成探索 | LLMなしの補助構成列挙、CPU上の探索、Pass@K評価 | full code非公開部分の完全再現 |
| Hilbert-Geo | 3Dを含む統一predicate言語、Parse2Reason、theorem bank | solid geometry IR、図と本文の共通CDL | neural parserの重み、公開予定コードの未確認部分 |
| LEAP / Goedel-Prover-V2 | subgoal分解、verifier feedback、自己修正、段階的合成 | proof obligation分割、compiler feedback、curriculum | LLMによるblueprint生成とproof sampling |
| 9.2M theorem search | theorem単位の大規模検索 | 既知定理の候補取得、出典付きretrieval | 検索結果を証明済みと扱うこと |

## 4. MORTRAの現在地

MORTRAには型付きproof DAG、表現chart、CEGIS、Newclid/GCLC/Wu/Gröbner、native certificate replay、MMT/Sheafの部分適応がある。したがってK3のMoEをそのまま再実装する必要はない。

固定未解決3問に対する直近実験では、構成エラーは7から0へ減ったが、実問題でchart経由となった候補は0、native残差改善は0/3、追加正答は0/3だった。現在の本質的断絶は次である。

```text
ground typed obligation
  -> executable chart goal
  -> backend certificate / residual
  -> re-elaborated typed relation
```

この往復が閉じる前にroutingを高度化しても、実行不能な候補の順番を変えるだけである。

## 5. MORTRAへ採用するK3原理

### 5.1 Hybrid proof propagation

各agent内で局所閉包を複数回行い、一定間隔でのみglobal certificate reconciliationを行う。K3の3:1比は初期仮説にすぎず、MORTRAでは未解決義務数と通信費から比率を適応させる。

### 5.2 Block proof residual

各探索blockの出力全文ではなく、未解決typed obligation、証明済みcertificate hash、非退化条件をblock summaryとして保持する。過去blockは必要な型が単一化するときだけ参照する。

### 5.3 Latent typed expert routing

共通の完全proof stateはshared pathに保持し、各agentへはMMT viewで必要最小限のprojectionだけを渡す。routingは問題IDや文型でなく、precondition単一化、期待残差減少、native closure実績、費用で決める。

### 5.4 Quantile load balancing

特定agentの過剰発火を防ぐため、expertごとの実行待ち時間と有効closure率からrouting biasを補正する。正答率ではなく負荷分散の機構として評価する。

### 5.5 Persistent proof trajectories

timeoutを失敗終端にせず、frontier、certificate、sandbox stateを保存して再開する。UIの未回答問題と長時間探索を分離する。

K3のMulti-Teacher Distillationは採用しない。代わりに、検証済みtrajectoryから問題文や数値ではなく最小morphism chain、必要なside condition、chart選択条件だけを抽出するcertificate distillationを用いる。

## 6. 次の因果実験

同じfrozen未解決集合に対して、次を逐次ablationする。

1. 現行系。
2. ground obligationの双方向chart bridge。
3. block proof residual。
4. local/global hybrid scheduler。
5. latent typed expert routingとload balancing。
6. persistent trajectory resume。

測定値は追加正答、native replay率、chart発火率、残差減少、verifier呼出数、wall time、peak memory、agent負荷分散、長いmorphism chainでのLiftCertificate保持率とする。

最初の採否条件は、双方向bridge単体がchart発火率を0から増やし、少なくとも一つのground obligationをnative certificateへ変換することである。これを満たさなければ、K3型scheduler実験へ進まない。

## 7. 結論

Kimi K3はMORTRAの代替ではなく、探索制御アーキテクチャの参考である。K3の最も有用な知見は、情報流をsequence、depth、widthの三方向に分け、局所処理、大域同期、疎routing、永続状態を共同設計した点にある。

数学の体系化にはC-RASPだけでもK3だけでも足りない。MORTRAの核は、OpenMath/MMTによる意味とview、C-RASP型の合成代数評価、Sheaf型の局所合意、HAGeo/LEAP型の探索・検証を、native certificate replayの上で統合する構成になる。

## 8. 一次資料

- Kimi K3 technical report: https://arxiv.org/abs/2607.24653
- Kimi K3 official repository: https://github.com/MoonshotAI/Kimi-K3
- C-RASP algebraic decomposition: https://arxiv.org/abs/2608.13433
- Sheaf-ADMM paper and code: https://arxiv.org/abs/2605.31005 , https://github.com/SakanaAI/sheaf-admm
- HAGeo: https://arxiv.org/abs/2512.00097
- Hilbert-Geo: https://arxiv.org/abs/2605.16385
- LEAP: https://arxiv.org/abs/2606.03303
- Goedel-Prover-V2: https://arxiv.org/abs/2508.03613
- Semantic theorem search: https://arxiv.org/abs/2602.05216
- MMT: https://arxiv.org/abs/1105.0548
- OpenMath Content Dictionaries: https://openmath.org/cd/
