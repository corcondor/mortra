# 統合 Semantic Kernel

2026-08-12。実行して得た結果のみ。再現コマンドを各節に書く。

## 監査で見つかった分断

`proved` の定義が **7 箇所**にあり、それぞれ別の列挙だった。

| 場所 | 列挙 |
|---|---|
| `lib/mortra/world/world-types.ts` | proved / verified_instance / numerically_supported / … |
| `worker/src/alphageometry2-executor.ts` | proved / unproved / unformalized / unavailable / error |
| `worker/src/exact-linear-invariant.ts` | proved / underdetermined / inconsistent / blocked |
| `worker/src/generalization-kernel.ts` | proved / open |
| `worker/backend/cas_solver.py` | proved / verified_instance / numerically_supported / unverified |
| `worker/src/benchmark-bridge.ts` | certified / unproved |
| `lib/proof-scene.ts` | 数値検証のみ（状態語彙なし） |

**同じ語が別の意味を持っていたので、証明済みを横断して数えられなかった。**

射の型も 2 つあった（`MorphismSchema` と `VerifiedDomainMorphism`）。

## 唯一の定義にした

`lib/mortra/kernel/semantic-kernel.ts`

```
KnowledgeStatus
  proved / verified_instance / numerically_supported
  stable_under_perturbation / conjectured
  unverified / disproved / rejected / unformalized / unsupported

VerificationMethod
  symbolic_identity / exact_substitution / groebner_reduction
  interval_arithmetic / smt / ddar / forward_chaining
  numeric_sampling / property_test / group_closure
  orbit_membership / symmetry_verification
```

**LLM の自己申告は列挙に入れない。**

## 規約と記号の役割を第一級にした

今回の二つの事故は、どちらも暗黙だったことが原因。

- **scale error** — テータの指数の規約（|x|² か |x|²/2 か）が型に無かった
- **`I` の衝突** — 記号の役割（虚数単位か関数か）が型に無かった

```
Convention      reciprocal_lattice / root_normalization / theta_exponent /
                coordinate_frame / unit / orientation / branch_selection / symbol_role

SymbolBinding   role + source の優先順位
                explicit_declaration > content_mathml > presentation_structure
                > text_context > standard_dictionary > inferred
                同順位で食い違えば棄権する
```

`conventionsAgree()` が食い違いを検出し、`auditKernel()` が
**規約が変わるのに対応を書いていない射**（silent_convention_change）を落とす。

## アダプタ

既存はそのまま動かし、出てきた物を核の語彙へ写す。大きな書き換えはしない。

```
fromCasVerdict / fromLinearStatus / fromGeometryStatus / fromProofScene
bindLattice / bindDualMorphism / bindRootSystemMorphism
bindWallpaperGroup / bindOrbitMorphism
```

**`fromProofScene` は proved を返さない。** 前向き推論＋座標検証は
`verified_instance` であって記号的証明ではない。ここを混ぜていた。

## 測った結果

```
npx tsx scripts/kernel-integration.mts   18/18
npx tsx scripts/slice-b-revision.mts     13/13
```

核の中身：対象 32 / 関係 21 / 射 12 / 証明書 21。
射はすべて保つ不変量を宣言している（宣言しない移動は `auditKernel` が落とす）。

## 効果の測定

`docs/research/generalization-ablation.md` を参照。

**A3（意味核の導入）で certified solve rate は動かなかった（Δ +0）。**
分断の解消は横断集計と誤りの検出には効いたが、正答率には効いていない。
その事実を書く。
