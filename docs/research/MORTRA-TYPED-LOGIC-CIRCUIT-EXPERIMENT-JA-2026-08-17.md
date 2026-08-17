# MORTRA 型付き論理回路実験

日付: 2026-08-17

## 要旨

MORTRAの厳密な証明器を論理回路として保ち、連続値を真偽判定ではなく探索順序にだけ使えるかを検証した。結論は限定付きで肯定的だった。型付きground atomを保持したAND-OR証明回路とtop-1 proof provenanceを用いると、未見ラベル・未見数値からなる4領域400正例を、最短証明長と同じ通信予算で400件すべて再生できた。対応する400反例では誤受理0、不要な証明書送信0だった。

ただし、これは自然文の形式化や定理の自動発明を含むend-to-end数学ベンチマークではない。全ground rule applicationを先に列挙した後の、証明経路選択と証明書交換だけを測った実験である。

## 原理

```mermaid
flowchart LR
    A["型付きground atom"] --> B["AND: 一規則の全前提"]
    B --> C["OR: 同じ結論への代替証明"]
    C --> D["連続需要 / 将来のADMM・NN"]
    D --> E["top-k来歴で試行順を選択"]
    E --> F["native certificate replay"]
    F -->|"検証成功のみ"| G["証明済みgoal"]
    F -->|"失敗"| H["棄却・再探索"]
    D -.->|"真偽には不使用"| F
```

### 1. 真理層と制御層を分離する

ground atom `a` の真偽を `x_a in {0, 1}` とする。Horn規則の一適用をgate `g` とし、その前提集合を `P_g`、結論を `c_g` とする。

```text
x_g = AND { x_p | p in P_g }
x_c = given(c) OR OR { x_g | c_g = c }
```

この離散回路だけが真理を決める。連続値 `d(a) in [0,1]` は、どのgateを先に試すかを決める需要であり、命題を真にしない。

### 2. 型と引数を捨てない

`divides(5,80)` と `divides(12,80)` は同じ述語だが、異なる命題である。述語名だけへの縮約は高速でも不健全であるため、回路のnodeは完全なground atomとする。型検査は各証明書の結論に対して行う。

### 3. ORでは証明枝の一貫性を保つ

gateの構造コストを

```text
C(g) = 1 + sum { minimum_cost(p) | p in P_g }
```

とし、OR候補上の制御分布を

```text
pi(g | c) proportional to exp(-C(g) / temperature)
```

とする。全候補へ需要を流すsoft-all方式は、等コストの証明を混ぜる可能性がある。そこでScallopのtop-k proof provenanceに対応する制限を加え、既定では最小コストの1枝だけへ需要を流す。AND gateでは選んだ枝の全前提へ需要を戻す。

### 4. NNを入れない理由と入れられる場所

Deep Differentiable Logic Gate Networksは16個のBoolean gateから連続緩和で演算を学ぶ。一方、MORTRAのHorn規則ではAND/ORの意味は既知であり、ここを学習すると厳密性を弱める。したがって本実験は「論理回路NNそのもの」ではなく、論理回路NN・LNN・TensorLog・Scallopから、微分可能な制御面と離散的な真理面の分離だけを抽出した非学習baselineである。

将来学習させる対象は、真理値ではなく `pi(g | c)` の優先度パラメータに限定する。最終結果は常にnative verifierで再生する。

## 文献と実装監査

| 系統 | 採用した要素 | 今回採用しなかった要素 |
|---|---|---|
| Logical Neural Networks | 論理式に対応するnode、上下方向推論、矛盾を隠さない設計 | 実数真理値による最終判定 |
| Neural Logic Machines | 引数付き述語をarity別tensorとして保持する発想 | neural predicate induction |
| Differentiable ILP / TensorLog | forward chainingの計算グラフ化 | 全groundingを学習で重み付けする部分 |
| Scallop | proof provenance、top-k証明近似 | 確率的provenanceを真理値として扱うこと |
| Differentiable Logic Gate Networks | 離散回路と連続緩和の役割分離 | AND/OR演算自体の学習 |
| SATNet | 最適化を制御面に使い、離散制約を保つ発想 | SDP/MAXSAT層の導入 |
| Sheaf-ADMM | 局所agent間の合意変数を探索配分に使う構想 | 今回はADMM更新をgate demandへ未接続 |

確認した公式実装の固定commit:

- IBM LNN: `0dc20bfc1b4ee4d0d3696d40f15db94890d18c55`
- difflogic: `469702c01ff0bfac9cdc6a395134252e11a56bd8`
- Scallop: `668bfb6d45ce302fd4ffa7f29916baf3c7ce36ef`
- SakanaAI sheaf-admm: `1e2b5d648361802234348b0b1a7fb3a222128e7d`

## 仮説

1. **H1 型付き回路仮説**: 述語だけ、または目標との表層的な引数重複より、完全ground atom上のAND-OR回路が限られた通信予算で高い証明完了率を持つ。
2. **H2 健全性仮説**: 連続需要が誤っても、native certificate replayを真理層に置けば反例を受理しない。
3. **H3 汎化仮説**: 制御が問題ID・数値・entity labelを使わなければ、entity renamingと未見数値で同じ回路構造と結果を保つ。
4. **H4 来歴一貫性仮説**: tight budgetではsoft-allよりtop-1 provenanceの方が、異なるOR枝の前提混合を防ぐ。

## 方法

### 対象

- 幾何関係閉包 100件
- 整数の整除閉包 100件
- 集合の包含閉包 100件
- 任意長の到達可能性 100件
- 各正例から、同じ述語・同じ型で引数だけを替えたmatched negativeを1件生成

合計は400正例 + 400反例である。学習は行わず、seed 70000以降のラベルと数値を使用した。

### 比較条件

1. `predicate`: 述語名だけで優先度を決める。
2. `current`: 目標一致、目標との引数重複、述語一致による従来型heuristic。
3. `circuit_soft`: 型付きAND-OR回路だが、全OR枝へsoftmax需要を流す。
4. `circuit`: 型付きAND-OR回路 + top-1 proof provenance。

各roundで送れる証明書は1件、round数はその正例の最短証明に必要なgate数と同じに固定した。成功条件は、選択した証明書列を元agentのverifierで最初から再生し、goalへ到達することである。

### 反暗記条件

- 問題ID分岐なし
- 数値定数分岐なし
- theorem名を学習featureとして使用しない
- entity labelをfeatureとして使用しない
- 学習なし
- entity renaming testあり
- matched negativeあり

## 結果

| 制御 | 正例成功 | 証明再生 | 反例誤受理 | 反例への送信 |
|---|---:|---:|---:|---:|
| predicate | 11/400 | 11/400 | 0/400 | 1241 |
| current | 152/400 | 152/400 | 0/400 | 1241 |
| circuit_soft | 399/400 | 399/400 | 0/400 | 0 |
| circuit top-1 | **400/400** | **400/400** | **0/400** | **0** |

領域別のtop-1結果は、幾何100/100、整数100/100、集合100/100、到達可能性100/100だった。最大証明長7、平均証明長3.1025、平均gate数55.2825、最大gate数88、平均ground rule match数189.0425だった。

述語名だけに潰した抽象判定は400反例すべてを「証明可能」と誤判定した。最終verifierを残したため実際の誤受理は0だったが、述語だけの状態表現を探索や証明の本体にできないことが分かる。

### PDCAで観測した1件の失敗

初回soft-all実験は399/400だった。整数例 `5 divides 80` に、`60+20` と `240-160` の等コスト証明があった。需要を0.5ずつ両枝へ流したため、3手の予算で双方の前提を混ぜ、どちらも完成しなかった。

これは個別の整数規則ではなくOR gateの一般的な来歴問題である。top-1 provenanceを導入すると、`gcd-right -> gcd-left -> divisor-difference` の一枝に揃い、400/400へ改善した。soft-allの399/400はablationとして最終結果に残した。

## 考察

### 支持されたこと

- 完全ground atomを保つ型付き回路は、述語や単純な引数重複より強い探索信号になる。
- 連続値を制御面に限定し、最終判定を厳密な証明書再生にすれば、探索器の誤差と論理的健全性を分離できる。
- 学習なしでも、証明DAGの構造だけで未見ラベル・未見数値へ転移した。
- ORの局所確率を独立に選ぶだけでは不十分で、証明全体の来歴を一貫させる必要がある。

### まだ支持されていないこと

- MATH、MathVision、IMO-AG-30で正答率が上がること。
- 自然文や画像から正しいground atomを生成できること。
- 未知の定理や補助構成を発明できること。
- 論理回路NNを学習した方が、非学習の最短コスト制御より良いこと。
- Sheaf-ADMMによる自己組織化がgate選択に寄与すること。

### 計算量上の限界

今回のcompilerはforward chainingで到達可能なground rule applicationを先に全列挙する。したがって回路実行時の通信削減は確認できても、compile costを含むend-to-end高速化は示していない。対象数とarityが増えるとgroundingが支配的になる。次段では、TensorLogのgoal-directed compilationとScallopのtop-k provenanceを組み合わせ、必要な部分だけをlazy groundingする必要がある。

## 結論

MORTRAで採るべき構造は「論理回路NNを真理判定器にする」ことではない。

```text
型付き離散AND-OR証明回路
        +
連続値/ADMMによる探索制御
        +
native verifierによる証明書再生
```

である。今回、第一段として型付き回路と連続需要を分離し、top-1来歴を含む非学習baselineを実装した。400正例/400反例の限定実験では仮説H1-H4を支持したが、外部ベンチマークへの効果は未検証である。

次の反証実験は、(1) lazy backward grounding、(2) top-kを固定せず局所特徴から小規模に学習するcontroller、(3) 同じ回路上のSheaf-ADMM consensus、(4) Newclid/GCLCの実証明義務への接続、の順で行う。評価はcompile時間・展開gate数・証明成功率・誤受理率・native replay率を同時に測る。

## 再現

```powershell
python -B -m unittest worker.backend.test_typed_logic_circuit -v
python -B scripts/experiment_typed_logic_circuit.py `
  --episodes-per-domain 100 `
  --reachability-episodes 100 `
  --distractors 12 `
  --seed-start 70000 `
  --output data/typed-logic-circuit-heldout-2026-08-17.json
```

実装:

- `worker/backend/typed_logic_circuit.py`
- `worker/backend/test_typed_logic_circuit.py`
- `scripts/experiment_typed_logic_circuit.py`
- `data/typed-logic-circuit-heldout-2026-08-17.json`

## 一次資料

- Riegel et al., Logical Neural Networks, arXiv:2006.13155
- Dong et al., Neural Logic Machines, arXiv:1904.11694
- Evans and Grefenstette, Learning Explanatory Rules from Noisy Data, JAIR 2018
- Cohen et al., TensorLog, arXiv:1605.06523
- Huang et al., Scallop, NeurIPS 2021
- Petersen et al., Deep Differentiable Logic Gate Networks, NeurIPS 2022
- Wang et al., SATNet, ICML 2019
- Badreddine et al., Logic Tensor Networks, arXiv:2012.13635
- Sakana AI, Self-Organization of Multi-Agent Systems via Sheaf Theory, arXiv:2605.31005
