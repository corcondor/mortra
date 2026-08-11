# Ablation — 何が本当に効いたか

locked test = mathexamtest.jp から収集した 167 問（同一集合・同一 CAS・同一判定）。
`python scripts/ablation.py` で再現。

## 結果

| | 内容 | certified | wrong | abstained | timeout |
|---|---|---:|---:|---:|---:|
| **A0** | 平文のみ | **0** | 0 | 167 | 0 |
| **A1** | + MathML（文字列で復元） | **10** | **12** | 126 | 2 |
| **A2** | + scoped symbol env（AST） | **36** | **1** | 100 | 0 |
| **A3** | + semantic kernel（証明書を要求） | **36** | 1 | 100 | 0 |
| A4 | + shared domain kernels | NOT_IMPLEMENTED | | | |
| A5 | + representation routing | NOT_IMPLEMENTED | | | |
| A6 | + Vision-derived invariants | NOT_IMPLEMENTED | | | |
| A7 | + LiveProof-required structure | NOT_IMPLEMENTED | | | |
| A8 | full system | NOT_IMPLEMENTED | | | |

```
A0   0/167 =  0.0%
A1  10/167 =  6.0%   Δ +10
A2  36/167 = 21.6%   Δ +26
A3  36/167 = 21.6%   Δ  +0
```

## 読み方

**certified の列より wrong の列が重要。**

```
A1  wrong 12   正答 10 に対して誤答 12。誤答のほうが多い
A2  wrong  1
```

6.0% という数字だけ見ていたら気づけない。文字列経由の復元は、
正しく解いた数より間違った数のほうが多かった。木から直接読む経路で 12 → 1。

`timeout` と `parse_failed` も 2/3 → 0/0。正規表現の積み上げが生んでいた不安定さが消えた。

## 一般演算あたりの効き

```
A0→A1  MathML を保持するという一つの変更で  +10 問
A1→A2  AST と役割解決という一つの変更で      +26 問、誤答 12→1
問題別のパッチ                              0 件
```

一つの一般的な変更が 167 問に波及した。例外分岐は足していない。

## A3 が効かなかったこと

**意味核の導入は certified solve rate を上げなかった（Δ +0）。**

効いたのは別の軸だった。

- `proved` の定義が 7 箇所にあったのを一つにし、横断して数えられるようになった
- 規約の食い違いと記号の役割の衝突を、型として検出できるようになった
- `fromProofScene` が proved を返さないので、幾何の結果を過大に数えなくなった

**正答率には効いていない。** その事実をそのまま出す。
今後 A4〜A8 を実装したときに、上がらなければ同じく上がらないと書く。

## 未実装

A4〜A8 は推測値を出さない。実装したら同じ locked test で測り直す。
