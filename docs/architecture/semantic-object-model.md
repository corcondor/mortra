# Semantic Object Model

`lib/mortra/kernel/semantic-kernel.ts`

## 型

```
SemanticId        同一性。文字列の一致ではなく ID の一致で「同じ物」を判断する
MathSort          分野をまたいで同じ語を使う種別
SemanticObject    id / sort / definition / assumptions / conventions / provenance / payload
TypedRelation     predicate / arguments / status / certificate / provenance
Morphism          source / target / preconditions / transported / preserved /
                  proofObligations / certificate / conventionMap / failureState
Certificate       method / consumedPremises / detail / artifact
Convention        kind / value / rationale
SymbolBinding     name / role / sort / source / confidence
Provenance        source / path / consumed / method / artifact
```

## 射の条件

**保つ不変量を宣言しない移動は射ではない。** 裸の値を渡すだけの橋を射と呼ばない。

`auditKernel()` が落とすもの：

```
proved_without_certificate     proved と名乗るのに証明書が無い
dangling_certificate           存在しない証明書を指している
dangling_argument              存在しない対象を指している
morphism_without_invariant     保つ不変量を宣言していない
sort_arity_mismatch            型の個数が対象の個数と合わない
silent_convention_change       規約が変わるのに対応を書いていない
object_without_provenance      出所が無い
```

## 記号の役割の解決順

```
1  explicit_declaration
2  content_mathml
3  presentation_structure   &af; / &it; / 括弧の隣接
4  text_context
5  standard_dictionary
6  inferred
```

同順位で役割が食い違えば **null を返す（棄権）**。推測で埋めない。

`I(a,n)` が sympy の虚数単位に化けた事故は、3（構造）が 5（辞書）に負けていたのが原因。
