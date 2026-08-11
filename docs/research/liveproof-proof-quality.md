# LiveProof が証明表現の品質要件になる

`python scripts/slice_a_liveproof.py`

## 縦貫は通った

```
MathML → AST → scoped symbols → 制約 → 検証つき解答 → 依存グラフ → 同期した段
```

```
LiveProof が作れた   36/167 = 21.6%
段の総数             127
proof-diagram 同期率  36/127 = 28.3%
証明書つきの段        36/127
```

## 作れなかった理由 — これが品質要件になる

```
129  式の飛躍が説明できない   unexplained_algebraic_jump
 59  前提の依存が辿れない     missing_premise_dependency
  2  対象が不透明で図に写せない opaque_object
```

**LiveProof を作ろうとすると、証明表現に足りないものが具体的な名前で出てくる。**
「解けなかった」ではなく「前提の依存が辿れない」まで分かる。

## 未達（正直に）

同期率 28.3% は低い。段の大半が「与」で、図に写せる関係が結論の1段しかない。
さらに出てくる答えに自明な言い換えが混ざる。

```
例  α = a₁     （前提 a₁ = α をそのまま返しただけ）
```

`is_trivial()` は `p_n = p_n` 型は弾くが、**別名への言い換えは弾けていない**。
次の作業。

## 分類の意味

証明の各段が持つべきもの（仕様 §7）を、作れない理由の側から定義できた。

```
claim / premises / certificate / consumedSemanticIds
focusObjects / visualActions / formulaActions / narration / camera
```

このうち `premises` と `consumedSemanticIds` が欠けると 59 件が落ちる。
**LiveProof の開発が proof DAG の要件を決めている。**
