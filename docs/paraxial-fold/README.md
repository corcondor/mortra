# MORTRA 近軸光学系 作用素Fold獲得および幾何・波動光学構造再利用 評価報告書

## 1. 概要・実験目的
本実験は、MORTRAが近軸光学系（Paraxial Optical System）において、長い光学要素列を逐次処理する代わりに、**再利用可能な中間表現／Fold（作用素合成）を獲得し、その単一のコンパクト作用素表現を幾何光学（光線伝搬）と波動光学（ガウスビームの複素 $q$ パラメータ伝搬）の双方へ再利用できるか**を実証・評価したものです。

評価問題側から「ABCD行列へ変換せよ」「2×2行列を使え」とは一切指示せず、またガウスビームの複素一次分数変換公式 $q' = (A q + B)/(C q + D)$ も問題解法としてハードコードしていません。幾何光学側で獲得された $\mathrm{SL}(2, \mathbb{R})$ 作用素が、波動光学側において射影直線上の群準同型（Möbius 変換）としてそのまま再利用される構造を検証しました。

---

## 2. 総合評価サマリー（Conditions A vs B）

- **Condition A (Baseline / Untrained)**: 初期状態。獲得したFold/libraryなし。逐次伝搬のみ。
- **Condition B (Trained / Acquired Fold)**: Training後。幾何光学で獲得したFold/libraryあり。
- **実行原則**: 同一ソルバー・同一プリミティブ・同一探索予算・同一検証基準。

| 課題名 | 要素数 | 評価次元 | Condition A (apps / size) | Condition B (apps / size) | 探索短縮比 | 計算残差 (Residual) | 構造再利用 | 判定 |
|:---|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|
| **unseen_multi_relay_10** | 10 | 1. 幾何光学 (Ray) | 10 apps / size 10 | 2 apps / size 1 | **5.0x** (apps) / **10x** (size) | $1.39 \times 10^{-17}$ | — | ✅ PASS |
| | 10 | 2. 波動光学 (Beam $q$) | 10 apps / size 10 | 1 apps / size 1 | **10.0x** (apps) / **10x** (size) | $9.81 \times 10^{-18}$ | 幾何Foldを完全再利用 | ✅ PASS |
| **unseen_periodic_cavity_17** | 17 | 1. 幾何光学 (Ray) | 17 apps / size 17 | 2 apps / size 1 | **8.5x** (apps) / **17x** (size) | $3.47 \times 10^{-17}$ | — | ✅ PASS |
| | 17 | 2. 波動光学 (Beam $q$) | 17 apps / size 17 | 1 apps / size 1 | **17.0x** (apps) / **17x** (size) | $3.93 \times 10^{-17}$ | 幾何Foldを完全再利用 | ✅ PASS |

---

## 3. 評価項目別の詳細検証結果

### A. 答えが正しいか（Correctness）
- **判定**: **完全一致（残差 $< 4 \times 10^{-17}$）**
- **検証内容**:
  - `unseen_multi_relay_10`:
    - 幾何光線: 逐次解 $(x, \theta) = (2.954444\times 10^{-3}, -8.503333\times 10^{-2})$ に対し、Fold解の残差は $1.39\times 10^{-17}$。
    - ガウスビーム: 逐次解 $q = -4.064778\times 10^{-2} + 2.151309\times 10^{-2}i$（ウエスト $w = 129.0\,\mu\text{m}$）に対し、Fold解の残差は $9.81\times 10^{-18}$。
  - `unseen_periodic_cavity_17`:
    - 幾何光線: 逐次解 $(x, \theta) = (6.103994\times 10^{-3}, 3.427905\times 10^{-2})$ に対し、残差 $3.47\times 10^{-17}$。
    - ガウスビーム: 逐次解 $q = 1.072491\times 10^{-1} + 6.407026\times 10^{-2}i$（ウエスト $w = 203.1\,\mu\text{m}$）に対し、残差 $3.93\times 10^{-17}$。

### B. Foldにより探索が短くなったか（Search Reduction）
- **判定**: **大幅短縮達成**
- **検証内容**:
  - **プリミティブ適用回数（Primitive Applications）**:
    - 幾何光学（初回Fold生成時）: $N \to 2$（Fold生成 1回 + 適用 1回）。
    - 波動光学（獲得作用素再利用時）: $N \to 1$（すでに獲得されたコンパクト作用素を1回適用するのみ）。
    - 17素子の光学系では、逐次適用の $17 \to 1$（**17倍の効率化**）を達成。
  - **計画展開数（Plan Expansions）**:
    - 逐次では光学列の長さ $N$ に応じて $N$ 回のステップ展開が必要だったのに対し、Fold適用時はわずか $1$ 回の展開で終了。

### C. compact representationを実際に獲得したか（Compact Representation）
- **判定**: **獲得確認**
- **検証内容**:
  - **表現サイズの変化**:
    - Fold前: $N$ 個の要素（パラメータ数 $2N \sim 4N$）のシーケンス。
    - Fold後: 単一の $2 \times 2$ シンプレクティック行列（パラメータ数 4、サイズ $1$）。
  - **獲得された作用素**:
    - `unseen_multi_relay_10`:
      $$M = \begin{pmatrix} 0.555556 & 0.0883333 \\ -16.6667 & -0.850000 \end{pmatrix}, \quad \det(M) = 1.000000$$
    - `unseen_periodic_cavity_17`:
      $$M = \begin{pmatrix} 1.19409 & 0.0667676 \\ 6.37817 & 1.19409 \end{pmatrix}, \quad \det(M) = 1.000000$$
    - 厳密に行列式 $\det(M) = 1$（光学的不変量・シンプレクティック性）が保持されていることを確認。

### D. 幾何光学で獲得した表現が波動光学でも再利用されたか（Cross-Domain Reuse）
- **判定**: **完全再利用確認**
- **検証内容**:
  - 幾何光学側で ray propagation を解く過程で獲得・キャッシュされたコンパクト作用素 $M$ を、波動光学側の Gaussian beam propagation において**同一の作用素オブジェクトとして直接再利用**。
  - 波動光学側での解法探索において、光学列の再Foldを行うことなく、`apply_compact_beam(compact, beam_0)` の **1ステップ（apps=1）** で即座に最終 $q$ パラメータを算出。
  - 線形写像の積と一次分数変換（Möbius 変換）の合成が成す群準同型 $\mathrm{SL}(2, \mathbb{C}) \to \mathrm{PGL}(2, \mathbb{C})$ により、数学的厳密性を保ったまま領域横断（幾何 $\to$ 波動）の転移が成功。

### E. 未見の長い光学列でも再利用できたか（Generalization to Unseen Long Trains）
- **判定**: **未見 10素子・17素子ともに一般化成功**
- **検証内容**:
  - Training では 3素子および 5素子の比較的短い光学列で Fold 機構を獲得。
  - 評価時には、構造が全く異なる未見の 10素子（非対称多段リレー系）および 17素子（共焦点周期キャビティ系）を提示。
  - MORTRAは未見の長い光学系に対しても、獲得された Fold メタ作用素を正しく適用し、即座に $O(1)$ のコンパクト作用素へと畳み込んで幾何・波動の両方で解を導出。

---

## 4. 成果物・生データリンク

- **生データ JSON**: [`paraxial_fold_eval_results.json`](./paraxial_fold_eval_results.json)
- **実行ログ**: [`run_paraxial_fold_eval.log`](./run_paraxial_fold_eval.log)
- **コアエンジン**: [`operator_fold_engine.py`](../../math_os_prototype/operator_fold_engine.py)
- **ドメイン定義**: [`paraxial_optics_domain.py`](../../math_os_prototype/paraxial_optics_domain.py)
- **評価スクリプト**: [`run_paraxial_fold_eval.py`](../../scripts/run_paraxial_fold_eval.py)
