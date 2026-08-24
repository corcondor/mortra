# MORTRA: 型付き関係セパレータと局所消去証明書の実験

実施日: 2026-08-21

## 1. 目的

幾何の型付き関係を最初から一個の巨大な座標多項式へ潰すと、局所的な関係まで
高次数・多変数の消去問題へ巻き込まれる。本実験では、関係型を保ったままgoal近傍の
前提を選び、低次数の局所消去証明書として交換することで、次の二仮説を検証する。

- H1: 変数数と入力多項式の複雑さを、恒等式を再生可能なまま削減できる。
- H2: その削減が固定未見問題の終端証明数または打切り率を改善する。

H1とH2は別々に判定する。中間表現が小さくなっただけでは正解に数えない。

## 2. 原理と根拠

仮定を多項式集合 `F={f_1,...,f_m}`、goalを `g` とする。最終判定は従来どおり、
非退化条件を明示した飽和イデアルについて `g` の所属証明を再生できる場合だけ成功とする。

局所消去では、変数 `x` を含む二式 `a*x+b=0`, `c*x+d=0` から

```text
h = c*(a*x+b) - a*(c*x+d) = c*b - a*d
```

を作る。`h` が元の二式のイデアルに属することは右辺の係数を含む恒等式で検査できる。
各段についてこの恒等式の残差が厳密に0になる場合だけ、次の局所agentへ渡す。

また、幾何表現に対して次の意味保存変換を行う。

1. `circle(o,a,b,c)` を、中心 `o` からの半径相等 `cong(o,a,o,b)` などへ下げる。
2. 同じ中心円成分から従う巨大な `cyclic` 行列式を重複前提として除く。
3. 定数倍だけ異なる多項式を同一視し、述語名が異なっても同じ式なら一個にする。
4. goal変数との共有、項数、変数数で有限個の前提を選ぶ。
5. bounded MacaulayとBuchberger DAGの両方で、最終所属証明を再生する。

これは問題文型や解法名の暗記ではない。選択器は問題ID、期待解、数値テンプレートを
参照せず、型付き関係、変数依存、項数、厳密恒等式だけを使う。

## 3. 実装

- `worker/backend/typed_relation_separator.py`
  - 型付き境界前提の選択
  - 円から半径合同への意味保存lowering
  - 自明関係と多項式同値関係の除去
  - 非退化条件を現在の多項式環へ閉じるring safety
  - bounded Macaulay / Buchberger DAG / 局所投影の証明書統合
- `worker/backend/bounded_macaulay_membership.py`
  - 有理数体上の有限次数イデアル所属証明と厳密再生
- `worker/backend/local_polynomial_elimination.py`
  - min-fill順の局所線形消去と各段のideal-membership witness
- `worker/backend/jgex_exact_constraint_bridge.py`
  - 一回の座標elaborationから複数の型付き義務を厳密専門器へ渡す
- `scripts/experiment_hageo_passk.py`
  - 上記全ソースを再現性manifestへ追加

局所投影は明示指定時だけ有効である。固定未見ablationで打切りが悪化したため、
製品既定値は `enable_local_projection=False` とした。

## 4. 方法

固定済みの未見5問を使った。

```text
2007CMOp4
2016CTSTp5
2016G6
2024PlanetCupp10
2025KoeraFinalRoundp3
```

- 外部LLM: 不使用
- dataset補助節: 不使用
- 問題IDによる探索分岐: 不使用
- 期待解: 不使用
- 各問 `N=1, K=1`, seed 0
- 最終成功条件: 厳密証明書の再生
- exact specialist上限: 30秒

対照は型付きセパレータなし、処置1はring-safeな直接セパレータ、処置2は局所投影を
有効にしたセパレータである。最後に現行既定値を逐次実行し、並列資源競合と内部打切りを
区別した。

## 5. 結果

| 条件 | 正解 | 完全観測 | 右打切り | 実行エラー | 壁時計 |
|---|---:|---:|---:|---:|---:|
| 対照 | 0/5 | 5 | 0 | 0 | 44.36秒 |
| ring-safe直接セパレータ | 0/5 | 4 | 1 | 0 | 96.23秒 |
| 局所投影あり | 0/5 | 2 | 3 | 0 | 102.32秒 |
| 現行既定・逐次診断 | 0/5 | 3 | 2 | 0 | 278.81秒 |

逐次診断はスケジューリング条件が異なるため、得点の因果比較には使わない。
内部の30秒上限に由来する右打切りが残ることを確認するための診断である。

### 5.1 `2016G6` の局所結果

- 選択前提: 8個
- 選択前提の最大項数: 8項
- 変数: 21から11へ削減
- 局所消去: 8段
- 恒等式を厳密再生できた段: 8/8
- 残った多項式: 4個
- 終端goal: 未証明

以前は同じ近傍で385項の `cyclic` 行列式が選ばれた。円の中心・半径構造と
多項式同値商を使うことで、その式を直接入力せずに済んだ。

### 5.2 実装不具合の修復

多項式同値商の初期版では、飽和因子が現在の多項式環にない変数を含み、
`variables omitted from ring` が2問で発生した。飽和因子をactive ringへ閉じることで、
同じ2問は実行エラーではなく、正しく `open` またはtimeoutとして記録されるようになった。

## 6. 考察

H1は支持された。型付き関係を利用すると、巨大な行列式を避け、変数を21から11へ減らし、
消去8段をすべて厳密に再生できた。

H2は支持されなかった。正解は0/5のままで、局所投影は打切りを増やした。投影後に残る
多項式の一部が高密度化し、終端goalへ必要な中間命題そのものも生成されなかったためである。
消去幅を広げるだけでは、欠けている補助構成や中間補題は得られない。

したがって局所投影を既定経路へ採用しない。証明書付きの選択肢として残すが、次の探索は
現在のgoal残差と単一化する事後条件を持つ中間補題・補助構成の型合成へ向ける。

## 7. 結論と次の実験

型付き関係セパレータは表現圧縮と実行安全性を改善したが、固定未見5問の得点は改善しなかった。
よって「CASへ渡す前の縮約不足」だけがボトルネックという仮説は棄却する。

次の反証可能な実験は、未解決goal `g` と現在の前提イデアル `I` から残差 `r` を取り、
次を満たす型付き中間命題 `l` を有限合成することである。

```text
I proves l          and          I union {l} proves g
```

候補 `l` は既存の関係語彙と型付き穴から合成し、問題ID・解答・表層文型を使わない。
固定未見集合で、追加正解、残差減少、候補当たり検証時間のいずれも改善しなければ棄却する。

## 8. 再現物

- 対照: `data/typed-separator-control-frozen5-2026-08-21.json`
- ring-safe処置: `data/typed-separator-ring-closed-treatment-frozen5-2026-08-21.json`
- 局所投影処置: `data/typed-separator-local-projection-treatment-frozen5-2026-08-21.json`
- 現行逐次診断: `data/typed-separator-final-sequential-frozen5-2026-08-21.json`
- 固定問題: `data/hageo-contract-low-witness-frozen5-2026-08-21.txt`

回帰テストは次で40件すべて成功した。

```powershell
python -m pytest worker/backend/test_typed_relation_separator.py `
  worker/backend/test_bounded_macaulay_membership.py `
  scripts/test_run_jgex_exact_specialist.py `
  scripts/test_hageo_passk_internal.py `
  scripts/test_experiment_hageo_passk.py `
  scripts/test_benchmark_hageo_passk_cohort.py -q
```
