# X 上の 6 投稿に含まれる研究と MORTRA の理論的整合性

- 調査日: 2026-09-03
- 対象: ユーザー指定の X 投稿 6 件
- 調査範囲: 投稿本文、論文本文、著者の公式ブログ、公開実装、ライセンス
- 判断基準: 数学的意味、再現可能性、MORTRA のどの層に効くか、誤受理を生まないか、最小表現で汎化するか

## 結論

直接の優先順位は次の通りである。

| 順位 | 研究 | MORTRA への価値 | 採用位置 |
|---:|---|---:|---|
| 1 | Harness-of-Harness | 5/5 | 再開可能な長時間研究、独立 QA、証拠付き状態遷移 |
| 2 | GEPA / optimize_anything / omni | 4.5/5 | 表現チャート・探索方策・説明方策の外側最適化 |
| 3 | Looped Transformers | 4/5 | 少数の型付き操作を反復する固定実行器の理論モデル |
| 4 | DLCM / ConceptMoE | 4/5（入力層）、2/5（証明層） | 自然文・長いログの適応的圧縮候補 |
| 5 | Optimal Transport / FGW | 3/5 | 大きさの異なる証明 DAG・問題構造の検索と対応付け |
| 6 | TimesFM-3 | 2/5 | 実験時間、失敗率、資源需要の予測。数学推論には直接効かない |

最も重要な結論は、これらを一つの学習器へ混ぜないことである。MORTRA の厳密検証を真理判定面として固定し、その外側だけを学習・圧縮・進化させる。

```text
自然文・図
  -> 適応的分節（DLCM / ConceptMoE は候補だけを出す）
  -> 型付き意味解析（MORTRA）
  -> 類似構造検索（FGW は候補順位だけを出す）
  -> 表現・構成・探索方策の進化（GEPA / omni）
  -> 少数操作の反復実行（Looped interpreter）
  -> 厳密検証・証明再生・hash 照合（MORTRA。変更不可）

外側全体の反復と再開、独立 QA（Harness-of-Harness）
運用時系列の予測（TimesFM-3。判定権なし）
```

## 1. 投稿と一次資料の対応

6 投稿が 6 論文に一対一対応しているわけではない。

| X 投稿 | 実際の一次資料 | 種別 |
|---|---|---|
| [DAIR.AI](https://x.com/dair_ai/status/2095172426925801608) | [Harness-of-Harness](https://arxiv.org/abs/2609.01481) | arXiv 論文 |
| [Daily Dose of Data Science](https://x.com/DailyDoseOfDS_/status/2095081810032251060) | [GEPA](https://arxiv.org/abs/2507.19457)、[optimize_anything](https://arxiv.org/abs/2605.19633)、AutoResearch、Meta-Harness、[omni 実験](https://gepa-ai.github.io/gepa/blog/2026/07/22/optimize-anything-omni/) | 複数研究の紹介 |
| [Probability and Statistics](https://x.com/probnstat/status/2094426968502456644) | 最適輸送の概念説明。理論参照として [Fused Gromov-Wasserstein](https://proceedings.mlr.press/v97/titouan19a.html) を使用 | 投稿自体に論文リンクなし |
| [Google Research](https://x.com/GoogleResearch/status/2094483372718580066) | [TimesFM-3 公式ブログ](https://www.research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/) と [実装](https://github.com/google-research/timesfm) | 公式ブログ。専用論文は未公開 |
| [Beta Tomorrow](https://x.com/BetaTomorrow/status/2095020835497255369) | [Looped Transformers as Programmable Computers](https://arxiv.org/abs/2301.13196) | 2023 年の論文を再紹介 |
| [Ge Zhang](https://x.com/GeZhang86038849/status/2095021856638271747) | [DLCM](https://arxiv.org/abs/2512.24617)、[ConceptMoE](https://arxiv.org/abs/2601.21420) | 2 論文 |

以下では、投稿の要約ではなく一次資料の主張を評価する。

## 2. Harness-of-Harness

### 理論と方法

Harness-of-Harness（HoH）は、新しい数学推論器ではなく、既存の coding agent を反復運用する上位プロトコルである。各反復を planner、developer、独立 QA に分離し、前回の成果物 `A_t` だけでなく、その判断根拠・テスト・未解決事項を含む evidence `E_t` を次回へ渡す。

重要な設計は次の 4 点である。

1. planner は一回の変更を小さく、しかし局所的に完結する範囲へ制限する。
2. developer は前回成果物を warm-start し、一人だけが書き込む。
3. QA は凍結された候補を独立に評価し、実装中の自己評価と分離する。
4. 次の反復は成果物と証拠の組 `(A_t, E_t)` から始まり、失敗理由を再推測しない。

### 実験結果

[論文](https://arxiv.org/abs/2609.01481)の 3 反復比較では、Codex + GPT-5.5 の GameCraft-Bench が `49.58 -> 71.52`、FrontierSWE dominance が `44% -> 71%`、ProgramBench pass rate が `60.41 -> 66.50` となった。OpenCode + DeepSeek-V4-Pro と Pi + MiniMax-M3 でも全体的な改善を報告している。

同論文の ablation では、計画更新、証拠フィードバック、warm-start のいずれを外しても最終性能が落ちる。したがって「同じ agent を何回も呼ぶ」ことではなく、反復間に何を保存し、誰が何を検証するかが主要因である。

### 再現性上の注意

[公式リポジトリ](https://github.com/Flesymeb/HarnessOfHarness)を確認した時点では README、図、動画が中心で、HoH-lite のコードは `Coming soon` である。したがって論文のプロトコルは参照できるが、実装をそのまま移植して同じ数値を再現する段階ではない。

### MORTRA との整合性

整合性は非常に高い。ただし効くのは数学 kernel ではなく研究運用である。

- MORTRA の `artifact + certificate + failure obligation` を HoH の `(A_t, E_t)` に対応させる。
- 実装 agent と proof replay agent を分ける。
- QA は候補を読み取り専用で受け取り、期待解答や探索内部状態を見ない。
- failure obligation が再現できない変更は次の反復へ進めない。

HoH を採用しても幾何の新しい定理は増えない。一方、長時間実験が途中で目的を失う、同じ誤診を繰り返す、証拠なしで得点を更新する、という運用上の失敗を直接減らせる。

## 3. GEPA、optimize_anything、omni

### GEPA の構造

[GEPA](https://arxiv.org/abs/2507.19457)は、軌跡・tool output・評価者の自然言語 feedback を読み、候補 prompt を変異・交叉させる。単一の平均点だけを追わず、各訓練例のどれかで最良な候補を Pareto 集合へ残す点が重要である。

候補 `p` の評価を問題ごとのベクトル

```text
s(p) = (s_1(p), ..., s_n(p))
```

として持ち、少なくとも一つの成分で優越する候補を保存する。これは、ある問題群にだけ効くチャートを平均点で早期消去しないための quality-diversity 機構と読める。

Qwen3-8B の 6 タスク集計では baseline `45.23`、GRPO `48.91`、GEPA `54.85`。GEPA 系の平均 rollout 数は `3,936`、GRPO は `24,000` である。GPT-4.1 Mini では baseline `53.03` に対し GEPA `65.22`、merge あり `66.36` を報告している。

[公式実装](https://github.com/gepa-ai/gepa)には state 保存、評価 cache、Pareto frontier、candidate selector、停止条件、validation/test 分離、複数 optimizer engine が実装され、今回の資料群の中では最も直接再利用しやすい。

### optimize_anything への一般化

[optimize_anything](https://arxiv.org/abs/2605.19633)は、prompt に限らず「文字列化でき、評価関数を持つ artifact」へ同じ探索を一般化する。評価器は scalar score だけでなく、修正に使える `side_info` を返す。

報告例は ARC-AGI `32.5% -> 89.5%`、AIME `46.67% -> 60.00%`、CUDA kernel の 87% が PyTorch と同等以上、円充填 `2.63598` である。特に side information は scalar のみより速く、最終値も高い。ただし論文自身が、構造的に独立な circle-packing 群では multi-task 化が悪化した例を示す。`single=2.6360`、`MT7=2.6313`、`MT11=2.5973` である。

この反例は MORTRA に重要である。問題を「同じ文章分野」だから共有してはいけない。次のいずれかが一致する問題だけで知識を共有すべきである。

- 型付き question algebra の正規形
- 必要な表現チャートの入出力型
- 証明義務の形と不変量
- 許可された verifier の種類

### omni の位置づけ

[omni の記事](https://gepa-ai.github.io/gepa/blog/2026/07/22/optimize-anything-omni/)は査読論文ではなく実験報告である。GEPA、AutoResearch、Meta-Harness を少量ずつ走らせ、初期成績の良い optimizer へ残り予算を配る portfolio 法を試している。Frontier-CS 10 タスク、同一モデル・20 ドル予算で、単独法の最高 `55.4` に対し omni の最高設定 `63.2` を報告する。

これは「一つの万能探索規則」を増やすより、性質の違う少数の探索作用を共通予算下で合成する発想であり、MORTRA の最小生成元という方針と整合する。ただし 10 タスクのブログ実験なので、MORTRA の凍結問題群で独立に検証する必要がある。

### MORTRA に入れる範囲

GEPA 系が変更してよいもの:

- 表現チャートの選択順
- 補助構成候補の生成方策
- 探索予算配分
- 証明・図・解説の表現方策
- 問題生成 artifact

変更してはいけないもの:

- 定理の意味
- verifier の受理条件
- certificate hash の計算
- held-out 問題の内容
- 正解ラベル

評価ベクトルは少なくとも `厳密正答、証明再生、誤受理、使用 primitive 数、未見構造での再利用、図と文章の整合、計算費用` を分離して持つべきである。単一 score にすると、短いが誤った証明や、問題固有の巨大規則が勝つ余地がある。

## 4. 最適輸送と Fused Gromov-Wasserstein

指定投稿は、Wasserstein 距離、entropic regularization、Sinkhorn、network alignment の概念説明であり、特定論文の紹介ではない。そのため、MORTRA との比較には構造付き対象を直接扱う [Fused Gromov-Wasserstein (FGW)](https://proceedings.mlr.press/v97/titouan19a.html) を基準にする。

通常の最適輸送は、共通の特徴空間上の点の移送費用を最小化する。Gromov-Wasserstein は各対象内部の距離関係を比較するため、ノード数や座標系が異なるグラフにも使える。FGW はノード特徴とグラフ構造を同時に使う。

MORTRA では次の用途に適する。

- ノード数の異なる proof DAG 間の対応候補
- 未解決義務と過去の補題グラフの soft matching
- 問題文の表層語彙が違うが構造が近い問題の retrieval
- chart 候補の `top-k` 順位付け

一方、transport plan は一般に soft かつ近似的であり、型付き射でも意味同値の証明でもない。entropic regularization は計算を速くするが、対応はさらに拡散する。したがって FGW は候補を提案できるだけで、証明書や変換規則として受理してはいけない。

## 5. TimesFM-3

### 内容

この投稿の一次資料は論文ではなく、2026-08-31 公開の [Google Research 公式ブログ](https://www.research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/) と [公式実装](https://github.com/google-research/timesfm)である。

TimesFM-3 は 330M parameter、1 兆超の time points で事前学習され、32 時点を一 patch とする。系列ごとの正規化後、2 次元格子上で次を交互に行う。

1. 同一系列の時間方向には causal attention。
2. 同一時点の系列間には full variate attention。

未来既知 covariate には lookahead token を使い、Contiguous Patch Masking により horizon 全体を一回で出力する。公式ブログは GIFT-Eval、FEV-Bench、TIME の事前学習済みモデル比較で最高の平均順位を報告するが、現時点では専用論文による査読結果ではない。

### MORTRA への用途

数学構造を増やす研究ではないため、問題を解く kernel へはほぼ効かない。使うなら次の多変量運用予測である。

- 問題族、chart、backend 別の実行時間
- memory、候補数、閉包サイズ、timeout の同時推移
- worker backlog と完了時刻
- failure class の発生確率

これは長時間実験の予定と資源配分には使えるが、「この chart が正答を生んだ」という因果効果は証明しない。

さらに、source code は Apache-2.0 だが、[TimesFM-3 の重みは non-commercial / non-production license](https://huggingface.co/google/timesfm-3.0-pytorch/blob/main/LICENSE)である。mortra.ai の製品経路へ重みを直接組み込むべきではない。

## 6. Looped Transformers as Programmable Computers

### 理論

[論文](https://arxiv.org/abs/2301.13196)は、入力を instruction と memory を持つ punchcard として与え、同じ transformer block を繰り返し適用する。手で構成した 13 層未満の重みによって SUBLEQ 型の一命令計算機、電卓、線形代数、backpropagation を実行できることを構成的に示す。

重要なのは「transformer が自然にこの計算を学習した」という結果ではない。Q/K/V と feed-forward の重みをアルゴリズムに合わせて明示設計した存在構成である。[公式コード](https://github.com/jysohn1108/Looped-Transformer)も各 building block の重み行列を直接定義している。また簡略化のため instruction と memory を分離した実装では、list 処理の program size が list 長に比例する制約を README が明記する。

### MORTRA との整合性

MORTRA が現在持つ少数の task primitive を固定し、長い合成だけを loop 回数で表す理論モデルとして有用である。

```text
state_{t+1} = Step(program_t, memory_t, typed_obligations_t)
```

ここで `Step` の種類を問題ごとに増やさず、既存の `transport / pair / map / fold / equalizer / preimage / period / extremum / boundary / eliminate / normalize / contract` の反復で計算する。新しい問題へ対応するとき、必要なのが新 primitive なのか、既存 primitive の長い合成なのかを切り分けられる。

ただし neural transformer を導入する必然性はない。まず deterministic な型付き interpreter として実装し、合成長一般化を測る方が MORTRA の証明再生と一致する。論文は自然文から program を得る問題も、数学的意味の正しさも解決していない。

## 7. DLCM と ConceptMoE

### 共通原理

両者は token ごとに同じ計算量を与える代わりに、隣接表現の cosine similarity などから境界を決め、可変長の concept へ圧縮して重い推論を行う。MORTRA の「意味単位で縮約する」という考えに近いが、ここでいう concept は潜在ベクトルであり、型付き数学対象ではない。

### DLCM

[DLCM](https://arxiv.org/abs/2512.24617)は encoder、動的境界分割・pooling、concept transformer、token decoder からなる。圧縮率 `R` と token-level / concept-level capacity を含む scaling law、異種階層向けの decoupled µP を提案する。matched inference FLOPs、`R=4` で 12 zero-shot benchmark の平均が `41.23 -> 43.92`（+2.69）と報告される。

ただし BoolQ `-1.47`、RACE `-0.72`、MMLU `-0.30`、CMMLU `-0.24` の退行もある。細かな否定、含意、事実境界は圧縮で失われうる。確認時点で論文から公式再現コードへの明確なリンクは見つからなかった。

### ConceptMoE

[ConceptMoE](https://arxiv.org/abs/2601.21420)は動的 chunking と MoE を組み合わせ、圧縮で余った計算を concept model の expert・looped layer へ再配分する。continual training の表では overall `40.9 -> 46.4`、math `38.1 -> 50.3`、from-scratch math `52.8`。効率設定では prefill 最大 `175.1%`、decoding 最大 `117.1%` の speedup を報告する。

一方、`R=4` は `R=2` より reasoning と math を大きく悪化させ、細粒度の visual localization、chart text、image Q&A に退行がある。最大圧縮ではなく、意味境界を壊さない圧縮率が必要だという結果である。[公式リポジトリ](https://github.com/ZihaoHuang-notabot/ConceptMoE)は確認時点で demo と画像を中心とする小規模公開であり、大規模学習の完全再現 package ではない。

### MORTRA に入れる条件

利用可能なのは候補分節だけである。

```text
latent segment proposal
  -> 数式・量化子・条件・図形参照を含む span を復元
  -> MORTRA の型付き parser で再 elaboration
  -> round-trip が一致した segment だけ採用
```

次の境界をまたぐ圧縮は禁止すべきである。

- 定義と結論
- 仮定と否定条件
- 量化子の scope
- 添字・指数・根号
- 証明 step と certificate edge
- 図中の点・線・面の参照

この制約下では、DLCM / ConceptMoE は自然文やログを短くする front-end であり、MORTRA の Content Dictionary や型付き chart の代替ではない。

## 8. 統合理論

MORTRA の層を次の 5 層へ明確に分けると、各研究を矛盾なく配置できる。

### L0: 真理判定面

- formal verifier
- certificate replay
- hash / artifact identity
- false-accept injection test

ここは不変とする。学習器、LLM、最適輸送、時系列予測へ受理権限を渡さない。

### L1: 型付き意味・実行面

- semantic object
- typed morphism
- task algebra normal form
- fixed looped interpreter

Looped Transformer 論文の「少数命令 + 反復」を、neural weight ではなく deterministic interpreter として使う。

### L2: 候補生成・検索面

- GEPA / optimize_anything による chart・探索方策の進化
- omni による optimizer portfolio
- FGW による proof DAG / problem graph の類似候補検索
- DLCM / ConceptMoE による入力分節候補

この層の出力はすべて未証明候補である。

### L3: 長時間研究面

- HoH の planner / developer / independent QA
- `(artifact, evidence, unresolved obligations)` の永続化
- bounded increment
- 再開と rollback

### L4: 観測・予測面

- TimesFM-3 型の多変量時系列予測
- 実行時間、queue、memory、failure の予測

この分離により、「近い」「圧縮できた」「改善しそう」と「数学的に正しい」を混同しない。

## 9. 反証可能な実験計画

### E1. HoH 型 evidence loop

仮説: 同一 token / wall-time 予算でも、成果物だけでなく evidence と未解決義務を保存し、独立 QA を置くと、再開後の重複作業と再発 defect が減り、厳密正答が増える。

- Control: 現行 worker の単一 loop
- Treatment: planner / implementer / frozen proof-replay QA
- 固定条件: 同じ問題、同じ verifier、同じ総予算
- 指標: 追加厳密正答、proof replay 率、再発 failure 数、重複候補数、時間、token
- 反証: 正答増なし、または同予算で control より悪化

### E2. GEPA / omni による chart 方策最適化

仮説: scalar score だけでなく、型付き失敗義務を side information として返すと、既存 primitive の合成だけで未見問題への追加正答が増える。

- Artifact: chart 選択・構成候補・budget 配分を記述する policy
- 評価器: 凍結 verifier
- Candidate sharing: task algebra fingerprint が適合する問題間だけ
- 比較: heuristic / GEPA / AutoResearch / Meta-Harness / omni
- 指標: held-out 厳密正答、primitive 追加数、平均 proof length、false accept
- 反証: training 改善のみで held-out 改善なし、または問題固有規則が増える

### E3. 12 primitive の looped interpreter

仮説: 問題固有 operation を増やさず、12 primitive の反復で、学習・単体検証より長い未見 task composition を実行できる。

- 短い合成長 `1..8` で型・意味・逆変換を検証
- 未見合成長 `9..64` で実行
- 既知問題の解答暗記を避け、生成した task graph を使う
- 指標: exact execution、round-trip、composition-depth generalization、必要 primitive 数
- 反証: 長さとともに exactness が崩れる、または問題固有 primitive が必要

### E4. 適応的意味圧縮

仮説: 数学的境界を hard constraint にした動的分節は、固定 chunk より短くしつつ型付き意味を保持する。

- 比較: no compression / fixed / cosine-dynamic
- 圧縮率: `R=1.5, 2, 4`
- 指標: OCR 文字一致、数式 AST 一致、型付き parse recall、round-trip、最終厳密正答、時間
- 反証: 一文字でも条件・添字を失う、または正答率が悪化

### E5. FGW proof-DAG retrieval

仮説: 表層 embedding より FGW の feature + structure 対応の方が、未解決義務に有効な既存 chart を top-k へ多く含める。

- 比較: lexical / embedding / GW / FGW
- 指標: useful-chart recall@k、追加厳密正答、検索時間
- 制約: FGW 対応自体は証明 step にしない
- 反証: recall と最終正答の双方で baseline を超えない

### E6. TimesFM による運用予測

仮説: 十分な実行履歴が蓄積した後、多変量予測で timeout と完了時刻の calibration が改善する。

- 入力: chart、backend、候補数、閉包、memory、CPU/GPU、過去時間
- 出力: completion time quantile、timeout probability
- 判断: scheduler のみ。数学的受理には使わない
- 留保: 商用利用可能な重みか自前モデルで実験する

## 10. 実装判断

### 今すぐ採用する

1. HoH の `(artifact, evidence, unresolved obligations)` 永続状態と独立 QA。
2. GEPA 実装の state、evaluation cache、Pareto、sealed test の考え方。
3. task algebra fingerprint による関連問題だけの cross-task transfer。
4. 12 primitive の deterministic looped interpreter。

### 小規模 pilot の後に判断する

1. FGW による proof-DAG retrieval。
2. cosine boundary による自然文・長大ログの分節。
3. optimizer portfolio。

### 現時点では導入しない

1. TimesFM-3 重みの製品組み込み。ライセンスが不適合。
2. 潜在 concept を型付き数学対象として扱うこと。
3. transport plan を proof morphism として扱うこと。
4. optimizer に verifier や正解ラベルを書き換えさせること。
5. HoH の数値を再現済みとして主張すること。公開コードが未提供。

## 11. 総評

今回の資料群は MORTRA の新しい数学法則を直接与えるものではない。しかし、MORTRA が目指す「少数の再利用可能な射を、長い合成・検証・反復によって一般化する」ための計算機構をかなりよく補完する。

最も理論的に整合する統合は次である。

```text
HoH       = 研究過程の圏外状態と独立検証
GEPA      = 射列・探索方策を進化させる候補生成
Looped    = 少数の生成作用を任意長で反復する実行器
DLCM/MoE  = 表層列から意味候補への可変長縮約
FGW       = 異なる大きさの構造間の近似対応
TimesFM   = 運用状態の時間発展予測
MORTRA    = 型、意味、証明、図、問題生成を閉じる真理判定面
```

したがって、今回の結果から表現 primitive を大量追加する理由はない。先に、既存 primitive を反復実行する共通 interpreter、証拠を失わない長時間 loop、型付き失敗義務を使う外側探索を実装し、凍結未見問題で追加正答が出るかを測るべきである。

## 一次資料

- [Harness-of-Harness paper](https://arxiv.org/abs/2609.01481) / [repository](https://github.com/Flesymeb/HarnessOfHarness)
- [GEPA paper](https://arxiv.org/abs/2507.19457) / [repository](https://github.com/gepa-ai/gepa)
- [optimize_anything paper](https://arxiv.org/abs/2605.19633)
- [optimize_anything omni experiment](https://gepa-ai.github.io/gepa/blog/2026/07/22/optimize-anything-omni/)
- [Fused Gromov-Wasserstein paper](https://proceedings.mlr.press/v97/titouan19a.html)
- [TimesFM-3 official blog](https://www.research.google/blog/timesfm-3-a-zero-shot-foundation-model-for-multivariate-forecasting/) / [repository](https://github.com/google-research/timesfm) / [weight license](https://huggingface.co/google/timesfm-3.0-pytorch/blob/main/LICENSE)
- [Looped Transformers paper](https://arxiv.org/abs/2301.13196) / [repository](https://github.com/jysohn1108/Looped-Transformer)
- [DLCM paper](https://arxiv.org/abs/2512.24617)
- [ConceptMoE paper](https://arxiv.org/abs/2601.21420) / [repository](https://github.com/ZihaoHuang-notabot/ConceptMoE)
