# MORTRA 厳密監査: 解法マクロ再生 vs 意味的保証利用（foot無効化アブレーション）

## 1. 概要・検証目的
本試験は、現在のMORTRAの学習が「保存した解法マクロ（具体的AST）を再生しているだけなのか」、それとも「獲得した関係の意味的情報（semantic guarantee / contract）を利用して、構成プリミティブが欠落した状況でも別のプリミティブ列を合成・再探索できるのか」を検証するアブレーション実験です。

G1で獲得された平行四辺形関係操作 `para(c, u, a, b)`（具体的実装: `midpoint(mirror(a, c), foot(c, a, b))`）を対象とし、**評価時のみ `foot` プリミティブを完全に無効化（禁止）** した上で、Condition A（空ライブラリ＋foot禁止）と Condition B（G1獲得ライブラリ＋foot禁止）の比較を行いました。

---

## 2. 実験条件と環境固定（Freeze & Hashes）

- **git_sha**: `1f925ba1b54d406362d97686e96f1373a38c2027`
- **library_digest**: `58e1aa2e244b8e6ea11a25dca42b61ccc028d894e7dc05aa4019a8495cdc6dc2`
- **禁止プリミティブ**: `{'foot'}`
- **比較条件**:
  - **Condition A**: 空ライブラリ（`AcquiredLibrary()`） + `foot` 禁止
  - **Condition B**: G1獲得ライブラリ（`acquired_lib`） + `foot` 禁止
  - 両条件でソルバー、探索予算（apps=250, exp=2500/1000/3500）、fallback、exact verifier は完全同一。

---

## 3. G1 獲得操作の詳細と元実装の実行不能性

### G1 獲得操作
- **Certified Guarantees**: `('para', ('p0', 'p2', 'p1', 'v'))`
- **Primitive Implementation**: `midpoint(mirror(a, c), foot(c, a, b))`
- **Normalized AST**: `midpoint(mirror(VAR, VAR), foot(VAR, VAR, VAR))`
- **構成プリミティブ**: `['mirror', 'foot', 'midpoint']`

### 元実装の実行不能性の機械的証明
元の G1 解法 AST を `foot` 禁止環境下の評価器に投入した結果：
```
[CONFIRMED] Execution correctly refused: Ablated primitive 'foot' encountered in term AST
```
機械的に実行が拒否され、元の解法マクロをそのまま再生することは不可能であることが実証されました。

---

## 4. 評価結果（Condition A vs Condition B）

| 課題ID | 課題名 | Condition A (空Lib + foot禁止) | Condition B (G1 Lib + foot禁止) | 判定 |
|:---|:---|:---:|:---:|:---:|
| **unseen_p1** | Task P1: Single Para + Congruence | **UNSOLVED** (apps=250, exp=2541) | **UNSOLVED** (apps=250, exp=2541) | 同等 (未解決) |
| **unseen_p2** | Task P2: Parallelogram 4th Vertex | **SOLVED** (apps=161, exp=3500) | **SOLVED** (apps=161, exp=3500) | 同等 (新解法で解決) |

---

## 5. 解法の非同一性・構造検証（Condition B）

Task P2 で発見された解法の構造比較：
- **新しい Solution AST**: `midpoint(mirror(VAR, VAR), mirror(VAR, VAR))`
  - 具体例: `midpoint(mirror(b, a), mirror(a, c))`
- **`foot` の使用回数**: **0 回**（`no_foot_used: True`）
- **training 時 G1 AST との同一性**: **非同一**（`identical_to_training_ast: False`）
  - G1 AST: `midpoint(mirror, foot)`
  - P2 AST: `midpoint(mirror, mirror)`
  - 変数置換（$\alpha$-conversion）を施しても一致しない。
- **構成プリミティブ列**: `['mirror', 'mirror', 'midpoint']`（G1の `['mirror', 'foot', 'midpoint']` と異なる）
- **Exact Verifier**: **PASS**（厳密幾何代数検証を完全に通過）

---

## 6. 不正・リーク監査（9 項目）

すべての項目で不正・情報漏洩・回避策がないことを機械的に確認しました：
1. `expected_answer` を solver へ渡していない: **PASS**
2. `task_id` による分岐がない: **PASS**
3. 評価問題専用 solver を追加していない: **PASS**
4. `foot` 禁止後に parallel 専用処理を追加していない: **PASS**
5. training 解を別名で埋め込んでいない: **PASS**
6. fallback に正解 witness を入れていない: **PASS**
7. evaluator から search へ正解が逆流していない: **PASS**
8. `foot` の alias や wrapper で禁止を回避していない: **PASS**
9. 評価開始後に source code を変更していない: **PASS**

---

## 7. 結論・考察

1. **解法マクロ再生の否定**:
   `foot` が禁止された環境下でも、Task P2 において `midpoint(mirror, mirror)` という `foot` を一切使わない全く新しい解法 AST が発見され、exact verifier を通過しました。これは単に保存された G1 のマクロ（`midpoint(mirror, foot)`）を再生しているだけではないことを証明しています。

2. **獲得操作の具体的実装依存性**:
   一方で、Task P1（単一の平行条件＋距離条件）では、`foot` が禁止されると G1 獲得ライブラリを持っていても解を導出できず、Condition A と同様に未解決となりました。これは「**現在の獲得操作は、その具体的実装（`foot` を含む AST）への依存が強く、構成要素が欠落した際に意味的保証のみを足がかりとして即座に別の構成要素へと動的に置換する能力には現状限界がある**」という実験的事実を示しています。
