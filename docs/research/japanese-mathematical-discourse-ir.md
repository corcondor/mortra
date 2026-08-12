# 日本語数学談話 IR

`worker/semantics/discourse_ir.py` / `worker/semantics/problem_ir.py`

## なぜ要るか

167問中 **78問（47%）には印字された等式が一本も無い**。条件は日本語の側にある。

これまでの実装は式の並びだけを見て「最後の非関係式」を目標にしていた。
本文が何を宣言し、何を仮定し、何を求めているかを読んでいなかった。

```
本文 + 順序付きMathML
  ↓
Mathematical Discourse IR
  ↓
Typed Problem IR
  ↓
backend（目標の演算子と制約の型で選ぶ）
```

**日本語本文を直接 CAS へ渡さない。** 必ずこの経路を通す。

## 式の位置を失わない

収集器が `<math>` を `⟦式⟧` に置き換えているので、
本文中の `⟦式⟧` の個数と式の添字が一対一に対応する。

```
DocumentBlock = TEXT | FORMULA(formula_index) | SUBPROBLEM
```

## 談話ノード

```
ObjectDeclaration    三角形ABCにおいて / 数列 a_n / 関数 f
DomainDeclaration    n を自然数とする / x は実数
IntervalConstraint   n は3以上 / t は0より大きく1より小さい
StructuralCondition  AB=AC / ∠A=60° / 点Pは円O上（未実装）
GoalNode             何をどう求めているか
```

**語ごとの if 文を並べない。** (語 → 型 → 成分数) の表から作る。

## 目標を第一級にする

目標は「最後の式」でも「未知変数」でもない。

```
ComputeValue / SolveEquation / FindAll / FindRange
FindMaximum / FindMinimum / Count / Prove / ShowInequality
FindLocus / FindArea / FindVolume / FindProbability
EvaluateLimit / EvaluateIntegral / ExpressInTerms / Construct
```

式でない目標は、印字式を探さずに構築する。

```
三角形ABCの面積を求めよ   →  Area(三角形:formula_k)
点Pの軌跡を求めよ         →  Locus(...)
```

**無理に sympy の式へ押し込まない。**

長い表現を先に見る。`範囲を求めよ` が `求めよ` に食われないようにしている。

## backend routing

```
ComputeValue / SolveEquation / ExpressInTerms / 極限 / 積分  → cas
FindRange                                                  → inequality
FindAll                                                    → solution_set   未実装
FindMaximum / FindMinimum                                  → optimization   未実装
Count                                                      → counting       未実装
Prove / ShowInequality                                     → proof          未実装
FindLocus / FindArea / FindVolume                          → geometry_region 未実装
FindProbability                                            → probability    未実装
```

未実装の backend は `unsupported_backend` として正しく棄却する。
**全部を sympy へ押し込まない。**

## テスト

`tests/discourse/test_discourse.py` — 42/42

```
positive        宣言・範囲・目標演算子16種
metamorphic     語順 / とする↔とおく / 求めよ↔求めなさい / 示せ↔証明せよ / 句読点
counterfactual  自然数↔実数 / 3以上↔4以上 / 以上↔より大きい（開閉）/
                最大↔最小 / 面積↔体積 / 求めよ↔示せ / 三角形↔四面体
negative        目標語なし→no_goal_detected / 目標過多→ambiguous_goal /
                空文字・式なしで落ちない
```
