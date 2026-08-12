# 目標と条件の抽出

## 目標は「最後の式」でも「未知変数」でもない

これまで「最後の非関係式」を目標にしていた。外れたらその問題は落ちる。
本文が何を求めているかを読んでいなかった。

`GoalNode` を第一級にした。

```
operator          17種
formula_index     式が目標のとき、その添字
symbolic_target   式でない目標。Area(三角形:formula_3) など
confidence
span              本文のどこから来たか
```

## 演算子

```
ComputeValue  SolveEquation  FindAll  FindRange
FindMaximum  FindMinimum  Count  Prove  ShowInequality
FindLocus  FindArea  FindVolume  FindProbability
EvaluateLimit  EvaluateIntegral  ExpressInTerms  Construct
```

**長い表現を先に見る。** `範囲を求めよ` が `求めよ` に食われないようにしている。
これは検査に入れてある。

## 式でない目標

```
三角形ABCの面積を求めよ  →  Area(三角形:formula_k)
点Pの軌跡を求めよ        →  Locus(...)
整数nをすべて求めよ      →  FindAll + formula_k
```

印字式を探しに行かない。**無理に sympy の式へ押し込まない。**

## 条件

変数名は本文には出ない。式の中にある。`⟦式⟧` の位置で対応づける。

```
⟦式⟧ を自然数とする       →  Sort.NATURAL   →  x > 0
⟦式⟧ は3以上             →  lower=3, lower_open=False
⟦式⟧ は0より大きく1より小さい →  lower=0 open, upper=1 open
三角形 ⟦式⟧ において       →  Sort.TRIANGLE
数列 ⟦式⟧                →  Sort.SEQUENCE
```

連鎖を分解しすぎない。`0<t<1` は一つの `IntervalConstraint` として持つ。
開閉（`以上` と `より大きい`）を保持する。これは counterfactual 検査に入れてある。

## 印字済みの条件を二重に入れない

`0 < t < 1` が MathML に不等式として入っている場合、それは既に relations にある。
日本語で書かれたものだけを text から取る。

## 語ごとの if 文を書かない

`(語 → 型)` と `(語 → 演算子)` の表から作る。
表に足すことはあっても、問題ごとの分岐は作らない。

## 検査

`tests/discourse/test_discourse.py` 42/42。

各項目に positive / metamorphic / counterfactual / negative を付けてある。

```
metamorphic     語順を変えても同じ IR
                「自然数nは3以上」と「nは3以上の自然数」
counterfactual  以上 → より大きい で開閉が変わる
                最大値 → 最小値 で演算子が変わる
negative        目標の語が無ければ no_goal_detected
```

counterfactual が無いと、単語を見ているだけの実装が満点を取れてしまう。
