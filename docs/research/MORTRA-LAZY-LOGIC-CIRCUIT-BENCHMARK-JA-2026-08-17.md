# MORTRA goal-directed lazy論理回路と実ベンチ実験

日付: 2026-08-17

## 要旨

前実験の型付きAND-OR証明回路は400/400を証明再生できたが、全ground rule applicationを先に列挙していた。本実験では、目標から逆向きに必要な型付き項だけを展開するSLD型lazy compilerを実装した。

未見4領域400正例・400 matched negativeでは、全列挙と同じ400/400正例再生・400/400反例棄却を維持し、規則/fact照合を85.08%、生成gateを94.39%削減した。正例compile実時間は31.40秒から3.50秒へ減った。ただし到達可能性だけでは1.17秒から1.36秒へ悪化した。

実問題では、IMO-AG-30未解決13問から抽出した独立JGEX関係義務20件を20/20再生し、照合を75.65%、gateを86.42%削減した。公式Yuclid全30問とGCLC/exact二重証明も再実行したが、グローバルスコアは17/30、厳格portfolioは19/30で導入前と同じだった。したがって「探索量削減だけで数学的被覆も増える」という仮説は支持されなかった。

## 原理

### 1. goal-directed compilation

全列挙は、既知fact集合 `F` と全規則 `R` に対して、適用可能なground規則を飽和まで生成する。lazy compilerはground goal `g` から始め、次だけを展開する。

```text
Solve(g, F):
  1. g とunifyする fact があれば終了
  2. conclusion(r) と g をunifyできる規則 r のみ選ぶ
  3. premises(r) を新しい局所目標として再帰的に解く
  4. 完成した枝だけをground AND-OR gateへ変換する
```

変数はfactまたは他の前提が拘束するまで保持する。全entityの直積を事前生成しない。

### 2. 探索順序

前提の選択順位は次の構造量だけで決める。

1. 拘束済み引数の数
2. 現在のfactとunifyできるか
3. 同じ結論述語への未固定再帰が少ないか
4. 前提数

問題ID、数値、定理名の意味、既知解答はscoreに使わない。定理名は同順位時の決定的整列にだけ使う。

### 3. 反復深化と証明DAG共有

深さ優先だけでは再帰規則が深い誤枝へ入るため、規則適用数0,1,2,...の反復深化を行う。また、変数代入後に同じ前提が二つ現れた場合は

```text
P AND P = P
```

として共有する。これによりproof treeではなくproof DAGの最短コストと一致させる。

### 4. 健全性境界

lazy compilerが作るのは候補gateである。採用条件は前実験と同じで、各agent固有のnative certificate payloadを復元し、元agentの`verify`で最初から再生できることとする。lazy探索だけで真理を宣言しない。

## 仮説

1. **H1 保存仮説**: 同じ深さ予算なら、lazy compilerは全列挙と同じ正例をnative replayできる。
2. **H2 縮約仮説**: goalと無関係なgroundingを避けるため、照合数とgate数が減る。
3. **H3 健全性仮説**: matched negativeの誤受理は増えない。
4. **H4 実証明書仮説**: 合成RuleClosureだけでなく、JGEXの独立証明書payloadも壊さず再生できる。
5. **H5 正答率仮説**: 探索量削減だけでIMO-AG-30のグローバル正答数も増える。

## 方法

### 実験A: 未見4領域

- 幾何関係閉包100件
- 整数整除閉包100件
- 集合包含閉包100件
- 任意長到達可能性100件
- 各正例に同型matched negativeを1件
- seed 110000以降
- 学習なし、LLMなし
- 正例の全列挙最短proof DAG長を、両方式の共通深さ予算とした

変更変数は`exhaustive_forward`と`goal_directed_lazy`のcompilerだけで、規則、型、verifier、証明書実行器は同一である。

### 実験B: 実JGEX局所関係義務

- 固定母集団: 公式Yuclidが未解決だったIMO-AG-30の13問
- dataset auxiliary clausesは非表示
- setupから抽出したJGEX relation certificateの全結論20件
- 既存coordinator、全列挙回路、lazy回路を比較
- `on_aline / cc_tangent / external_homothety`等の証明書SHA-256とnative payloadを保持

### 実験C: グローバルベンチ再実行

1. 公式Yuclid executableでIMO-AG-30原問題30問を同一command、all-AR、30秒制限で再実行。
2. 追加厳格成功2問 `2008_p1a / 2012_p5` をGCLC Wu/Gröbnerと独立exact backendで再実行。
3. GCLC証明、exact証明、型付き目標一致の三条件を満たす場合だけportfolioへ追加。

## 結果

### A. 未見4領域

| 指標 | 全列挙 | lazy | 変化 |
|---|---:|---:|---:|
| 正例native replay | 400/400 | 400/400 | 維持 |
| matched negative棄却 | 400/400 | 400/400 | 維持 |
| 規則/fact照合 | 75,546 | 11,271 | **85.08%減** |
| 生成gate | 22,135 | 1,242 | **94.39%減** |
| 正例compile時間 | 31.396秒 | 3.503秒 | **88.84%減** |

領域別照合削減率:

- 幾何: 95.35%
- 整数: 71.27%
- 到達可能性: 62.75%
- 集合: 95.27%

到達可能性の実時間は全列挙1.174秒、lazy 1.357秒で15.6%悪化した。Python再帰・unification・反復深化の固定費が、規則数の少ない領域では削減分を上回った。

### PDCA: 396/400から400/400

初回は整数4件を落とした。`divides(d,a) AND divides(d,a)`を別々の証明として数え、最短DAG2 gateをproof tree 3 gateへ膨らませていたことが原因だった。AND冪等性による共通部分式除去を実装し、個別の整数規則を追加せず400/400へ修復した。

### B. 実JGEX局所義務

| 指標 | 既存 | 全列挙回路 | lazy回路 |
|---|---:|---:|---:|
| native replay | 20/20 | 20/20 | 20/20 |
| matched negative棄却 | - | - | 20/20 |
| 照合 | - | 423 | 103 |
| gate | - | 162 | 22 |
| compile時間 | - | 0.01424秒 | 0.01477秒 |

実問題でも構造量は減ったが、対象が小さいためwall time改善はなかった。

### C. グローバルスコア

| ベンチ | 結果 |
|---|---:|
| Yuclid IMO-AG-30原問題 | 17/30 = 56.67% |
| 公式easy reformulation込み | 18/30 = 60.00% |
| GCLC + exact厳格portfolio | 19/30 = 63.33% |
| lazy回路導入後の厳格portfolio | **19/30 = 63.33%** |

`2008_p1a`と`2012_p5`は今回もGCLC証明、独立exact証明、型一致をすべて通過した。lazy回路による新しいグローバル正解は0件だった。

## 考察

### 支持された仮説

- H1: 400/400と実義務20/20を維持した。
- H2: 照合とgateを大幅に削減した。
- H3: 合計420 matched negativeをすべて棄却した。
- H4: JGEX固有payloadを元verifierへ戻して20/20再生した。

### 棄却された仮説

- H5: グローバルIMOスコアは19/30のままだった。

理由は、lazy compilerが「既に存在する規則・証明書のどれを展開するか」を改善しても、未解決13問に必要な新しい補助構成や中間補題を追加しないためである。探索制御と数学的被覆は別の変数である。

### 科学的含意

今回の結果は失敗を含めて重要である。論理回路化は計算資源を削減し、後段の補助構成探索へ予算を回す基盤になるが、それ自体は theorem invention ではない。正答率を上げる次の実験では、Yuclid/GCLCの未解決goalを回路のopen obligationとして戻し、局所agentが次を生成・検証する必要がある。

1. 既存factから作れる中間関係候補
2. GCLC/Wu消去を小さくする局所補題
3. Newclidへ戻せる補助構成
4. 追加後にのみ閉じる証明回路

## 結論

goal-directed lazy論理回路は、MORTRAの厳密性と正例被覆を維持しながら、不要なgroundingを大きく減らした。これはスケールの前提条件として有効である。一方、IMO-AG-30の正答率は上がらず、scheduler改善だけでは数学的発明を代替できないことも明らかになった。

次の本質的実験は、未解決goalから逆向きに不足predicateを抽出し、Newclid、GCLC、Wu局所消去、JGEX relation stalkが中間証明義務を反復交換する閉ループである。評価は19/30を超えるか、native replayを保つか、同一時間予算で比較する。

## 再現

```powershell
python -B -m unittest worker.backend.test_typed_logic_circuit -v

python -B scripts/experiment_lazy_logic_circuit.py `
  --episodes-per-domain 100 --reachability-episodes 100 `
  --distractors 12 --seed-start 110000 `
  --output data/lazy-logic-circuit-heldout-2026-08-17.json

C:/Users/81808/.cache/mortra-research-sources/Newclid/.venv/Scripts/python.exe `
  -B scripts/benchmark_lazy_jgex_relation_circuit.py `
  --output data/lazy-jgex-relation-benchmark-2026-08-17.json
```

公式Yuclid再現では次のruntime pathを使用した。

```text
C:/Users/81808/.cache/mortra-research-sources/boost_1_88_dlls/app/lib64-msvc-14.3
```

## 成果物

- `worker/backend/typed_logic_circuit.py`
- `worker/backend/jgex_local_relation_stalk.py`
- `scripts/experiment_lazy_logic_circuit.py`
- `scripts/benchmark_lazy_jgex_relation_circuit.py`
- `data/lazy-logic-circuit-heldout-2026-08-17.json`
- `data/lazy-jgex-relation-benchmark-2026-08-17.json`
- `data/yuclid-imo-ag-30-lazy-circuit-control-2026-08-17.json`
- `data/real-symbolic-coordination-lazy-circuit-control-2026-08-17.json`
