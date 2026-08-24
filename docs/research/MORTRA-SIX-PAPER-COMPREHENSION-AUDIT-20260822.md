# MORTRA 6論文理解・再現境界監査

日付: 2026-08-22

## 目的

C-RASP、OpenMath/MMT、Sheaf-ADMM、HAGeo、Hilbert-Geo、LEAPについて、
論文名や着想をMORTRAの部品へ対応づけるだけでなく、次の5段階を分離して監査する。

1. 論文の定理・アルゴリズム・前提条件を説明できる。
2. 公開された公式コードまたは公式成果物を確認した。
3. 公式評価条件を再現した。
4. MORTRAへ意味を保って接続した。
5. 接続が固定未見問題の追加正答を生んだ。

この区別をしない「統合済み」「再現済み」という表現は使わない。

## 結論

6件を一つの統合系として再現した状態ではない。現在の正確な分類は次の通りである。

| 資料 | 理論理解 | 公式コード確認 | 公式評価再現 | MORTRA実装 | 追加正答の因果効果 |
|---|---|---|---|---|---|
| C-RASP | 定理と判定対象を確認 | 判定器の履歴を確認 | READMEの3例のみ | 一般proof探索へ未接続 | なし |
| OpenMath/MMT | 語彙・theory viewの役割を確認 | 公式CD/MMTを確認 | 対象外 | 独立した小部分実装 | なし |
| Sheaf-ADMM | restrictionとADMMを確認 | JAX/Flax実装を確認 | 論文タスク未再現 | 記号証明書へ独立適応 | なし |
| HAGeo | N-round/K-trajectoryを確認 | full code未公開 | 未再現 | 独立再構成 | 既存unionは増えたが本統合の増分0 |
| Hilbert-Geo | CDL/SGREを確認 | 公式GDL・探索器を確認 | 未実行 | 型語彙の一部だけ適応 | なし |
| LEAP | OR/AND分解と二重gateを確認 | 公開物は解答中心 | agent runtime未再現 | LLMなしの独立適応 | 固定5問で0 |

したがって、以前の「6論文統合」は、正確には**6資料由来の独立部品を接続した実験**である。
公式方式を同一条件で再現し、相互補完による追加正答を示した実験ではない。

## 一次資料から確認した内容

### 1. C-RASP分解理論

定理の対象は文字列言語である。正規言語 `L` に対し、構文モノイド `M(L)` が
整数加法群を用いる型付きwreath-product closureへ属するかを判定する。
公式判定器は正規表現からオートマトン、構文モノイド、derived categoryを構成する。

MORTRAのproof DAGは、そのままでは文字列言語でも構文モノイドでもない。
次が未定義である。

```text
MORTRA proof-state transition system
  -> regular language / finite abstraction
  -> syntactic monoid
  -> C-RASP membership
```

この写像と保存定理がないため、C-RASPから「MORTRAの目標到達性を多項式時間で
事前判定できる」とは結論できない。現状で再現したのは公式READMEの正規表現3例だけである。

### 2. OpenMath / MMT

OpenMath Content Dictionaryは、記号の名前、説明、規則を共有する意味辞書である。
MMTは、基礎論に依存しないtheory graphとmorphism/viewを管理するmodule systemである。

MORTRAの`mortra_geometry_content_dictionary.py`と`mmt_exact_coordination.py`は、
URI、signature、symbol mapping、push/pullを実行する独立部分実装である。
Scala版MMTを埋め込んだものでも、MMTが補助構成を探索するものでもない。
確認できた効果は誤った型・arityの証明書交換を拒否することに限られる。

### 3. Sheaf-ADMM

公式方式では各agentが局所状態を持ち、隣接agent間でrestriction mapによる射影だけを
一致させる。局所最適化、sheaf diffusion、双対更新を含むADMMをunrollし、
encoder、decoder、restriction mapをend-to-endで学習する。

MORTRAは証明書の局所配送と線形ADMM型の予算・信用調整へ独立適応している。
公式の学習目的、latent state、論文タスクは再現していない。

合成frozen 60件では全方式60/60、送信はstrict 2,461件、learned sheaf 276件だった。
しかしlearned global blackboardは282件で、sheaf固有差は6件、95% CIは0を含む。
実幾何の追加正答は0である。通信削減と正答増を混同しない。

### 4. HAGeo

論文の核は、初期DDARが失敗した後、最大`N=6`段の補助構成を`K`軌道試すことである。
各段で現在の数値配置から非自明なincidenceを生む候補を列挙し、候補を選んでDDARを再実行する。
論文はIMO-30で28/30、HAGeo-409では計算量を増やすと70.2%を報告する。

MORTRAにも、型付き構成族と入力tupleの列挙、Newclid上での点生成、数値incidence評価、
native replayがある。これは着想に沿う独立再構成である。ただし次は一致しない。

- 公式full codeは未公開で、候補分布と細部を照合できない。
- 論文の高速DDAR実装を再現していない。
- 論文と同じ`K`、benchmark、計算環境ではない。
- MORTRAは論文外の構成族、型gate、proof-DAG順位を混在させている。

現在の認証済み能力集合は53/89である。これはHAGeo-409の公式スコアではなく、
異なる証明器・実験から得た証明書の集合和である。

### 5. Hilbert-Geo

公式実装にはCDL predicate GDL、theorem GDL、forward/backward search、代数計算がある。
論文は120述語・220定理の統一2D/3D表現を説明し、公式コードにはそれに対応する
大規模JSONとSGRE実行系がある。自然文・画像からCDLへのparse段階はMLLMを使う。

MORTRAが実装したのは、`Point2/Point3`等のsortと少数の共有幾何述語である。
公式predicate/theorem bankとSGREをMORTRA runtimeへ移植した状態ではない。
したがってHilbert-Geo由来の得点改善はまだ測っていない。

### 6. LEAP

LEAPは単なるAND/OR DAGではない。LLMがinformal proofとLean sketchを生成し、
Lean compilerが「親goalが子lemma群から証明できる」ことを検査する。さらに別のLLM reviewerが、
子goalが本当に容易で有望かを判定する。DAG memoizationも使う。

公開リポジトリで確認できるのは論文と生成済みLean解答が中心で、完全なagent runtimeではない。
MORTRAの`typed_open_proof_dag.py`はLLMを使わない独立適応であり、LEAP再現ではない。
固定5問で枝を除外したが追加正答0だった。

## Claude/Codexの既存分析に対する訂正

### `goal_deduction_count`は原因ではなく成功結果に近い

`YuclidVerification.solved`はnative出力の`status == solved`、
`goal_deduction_count`は同じ出力の`deductions_for_goal`の件数である。
したがって「解けた6問では正、未解決46問では0」という完全分離は、
ゴール証明が出たかを別の字段で再確認した結果であり、失敗原因の同定ではない。

この観測から次は導けない。

- 64軌道の外にもゴールへ触れる候補が存在しない。
- 現在の構成語彙では原理的に到達不能である。
- 候補選択や計算予算は原因ではない。
- C-RASP型の事前判定がそのまま使える。

未解決側の閉包が大きいことは「大量に無関係な演繹をした」証拠にはなるが、
必要な補助構成が候補集合に無いことの証明ではない。

### 現在のreachability gapも必要条件診断に留まる

`probe_yuclid_reachability_gap.py`は後向きに生成した複数のAND/OR義務を
`goals + demands`へ平坦化している。代替枝を保った到達可能性判定ではない。
またpredicateとsortが一致する`signature_only`は、引数単一化や構成可能性を保証しない。

現時点で確実に言えるのは次だけである。

1. 既存方策の64軌道では46問を解けなかった。
2. 固定3問のgoal-conditioned順位付けは追加正答0だった。
3. 既存候補のpostconditionは、観測したopen枝へ厳密meetを作らなかった。
4. これが語彙不足、候補生成不足、枝抽出不良、予算不足のどれかは未分離である。

## なぜ6資料を読んでも追加正答0だったか

多くの導入部品が、存在する経路を安全に運ぶ、並べる、分割する機構だったためである。

| 機構 | 改善するもの | 新しい到達経路を供給するか |
|---|---|---|
| OpenMath/MMT | 型付き意味保存 | しない |
| Sheaf-ADMM適応 | 局所通信 | しない |
| LEAP型DAG | 分解と再訪除去 | 子goal生成器が無ければしない |
| C-RASP | 対象言語の表現可能性判定 | 現proof探索への写像が無い |
| Hilbert-Geo一部語彙 | sort誤りの拒否 | theorem bank未接続なので限定的 |
| HAGeo再構成 | 補助点候補 | 供給するが公式規模・分布の再現未完了 |

現在の得点差を埋める本命は、通信やrankingをさらに重ねることではなく、
open OR枝ごとに実行可能な補助構成を生成し、そのpostconditionをnative closureへ戻す閉ループである。

## 次の実験

### 実験A: ORを保つ到達性診断

1. 後向きproof DAGを枝ごとに保持する。
2. 各AND枝について、既知exact atom、数値guard、未充足exact atomを記録する。
3. 候補構成のpostconditionを枝へ単一化する。
4. 1候補で閉じる枝、2候補合成で閉じる枝、現在のgrammarでは閉じない枝を分ける。

評価はpredicate signatureの有無ではなく、枝単位のexact typed unificationとnative replayで行う。

### 実験B: HAGeo忠実度ablation

同一問題、同一`N/K`、同一seed、同一Newclidで次を比較する。

- random構成族・入力tuple
- 数値incidence heuristic
- goal-conditioned heuristic
- 両者の混合

各候補の列挙母数、採択理由、作図成功、DDAR成功、時間切れを保存する。
公式規模へ上げる前に小規模で効果方向を確認し、効果が正なら`K`を段階的に増やす。

### 実験C: Hilbert-Geo solver-only接続

MLLM parserを使わず、公式formal CDLを入力として公式predicate/theorem GDLと
forward/backward SGREを実行する。MORTRAの同じformal inputとのunionを測る。
これにより自然言語parse性能と定理bank/solver性能を分離できる。

### 採用条件

- 期待解答・問題ID・外部LLMを探索に使わない。
- control/treatmentで同一問題・同一計算予算を使う。
- native証明書を再生できた追加正答だけを数える。
- 既存53/89へ加える前に、証明artifactとhashを固定する。
- 追加正答0なら、効かなかった機構として記録し既定経路へ入れない。

## 再検証

既存6論文統合文書の回帰コマンドを2026-08-22に再実行し、`99 passed`を確認した。
これは部品の回帰が無いことを示すが、論文再現や追加正答を示すものではない。

## 一次資料

- C-RASP: https://arxiv.org/abs/2608.13433
- OpenMath Content Dictionaries: https://openmath.org/cd/
- MMT: https://arxiv.org/abs/1105.0548
- Sheaf-ADMM: https://pub.sakana.ai/sheaf-admm/
- HAGeo: https://arxiv.org/abs/2512.00097
- Hilbert-Geo: https://arxiv.org/abs/2605.16385
- LEAP: https://arxiv.org/abs/2606.03303
