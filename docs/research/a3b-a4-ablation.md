# A3b と A4 の比較 — Discourse IR は単独では悪化した

## 最初の測定（dev + holdout 97問が混ざった 264 問。手順の誤り）

```
                    certified  wrong  abstained  executed
平文                       0      0        264         0
文字列AST                 14     24        200        58
AST                       15      0        232        31
A3b 本文の指示と条件        66      1        185        78
A4  Discourse IR           9      3        240        23
```

**A4 は A3b より大幅に悪い。** 25.0% → 3.4%。

この測定は holdout を 97 問含んでいた（収集を足した後に走らせたため）。
集計値を見ただけで、問題文も失敗内容も読んでいないが、**手順として誤り**なので、
以後 `paired_comparison.py` は manifest の dev だけを読むよう直した。

## なぜ A4 が悪いのか

```
A3b  executed 78   abstained 185
A4   executed 23   abstained 240
```

A4 は棄権が 55 件多い。原因は二つ。

**1. backend routing が正しく棄却している。**
目標が `Prove` / `FindMaximum` / `Count` / `FindArea` なら、
それぞれ proof / optimization / counting / geometry_region backend が要る。
どれも未実装なので `unsupported_backend` で棄却する。
これは正しい振る舞いだが、**A3b が偶然当てていた問題まで落ちる**。

**2. 目標を一つに決めてしまう。**
A3b は候補を順に試す。A4 は Discourse が決めた一つだけを解く。
Discourse の判断が外れた問題は、そこで終わる。

## 棄権の質は上がっている

A4 の棄権には理由が付く。

```
unsupported_backend:proof             証明の探索器が無い
unsupported_backend:optimization      最大最小の backend が無い
unsupported_backend:counting          数え上げの backend が無い
unsupported_backend:geometry_region   面積・体積・軌跡の backend が無い
no_goal                               目標の語が無い
```

A3b の棄権は `not_reduced` に潰れていて、何が足りないか分からなかった。

**「点は下がったが、何が足りないかが分かるようになった」** が正確な評価。
これを「改善」とは呼ばない。

## A5 — 両方を使う

```
1. Discourse が目標と backend を決め、実装済みならそれで解く
2. 決まらない・未実装なら候補探索へ後退する（本文から得た仮定は捨てない）
3. 後退しても解けず、routing が未実装 backend と言っていたなら、
   「解けない」ではなく「その backend が無い」と記録する
```

routing の棄却の質を保ちながら、A3b が拾っていた問題を落とさない。

## 教訓

**構造を正しくすることと、点が上がることは別。**

A4 は設計としては A3b より正しい（目標が第一級、backend が型で選ばれる、
棄権に理由が付く）。しかし単独では点が下がった。

機能を足して点が下がったなら、下がったと書く。
