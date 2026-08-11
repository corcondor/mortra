# MORTRA Vision アーキテクチャ

## 3D レンダラではない

```
通常の viewer     座標・メッシュ・色・カメラ・アニメーション を持つ。数学的意味は知らない
domain kernel     意味対象・定義・型付き操作・不変量・規約・証明書・失敗状態 を持つ
```

**画像はデータ本体ではない。数学対象がデータ本体。**

## 層

```
Domain IR              数学・物理の対象（格子・三角形・力学系・テンソル）
  ↓
Certified Transport    表現間の意味保存射。不変量と証明義務を持つ
  ↓
Visual IR              表示の意味。Three.js / SVG を知らない
  ↓
Presentation Timeline  focus / enter / update / exit / camera / formula / narration
  ↓
Renderer               ここで初めて Three.js や canvas が出る
```

**domain が Three.js を直接触るとこの分離が壊れる。** domain は Visual IR までを作る。

## 実装

| 層 | ファイル |
|---|---|
| Domain IR（格子） | `lib/vision/lattice.ts` |
| Domain IR（証明） | `lib/proof-scene.ts` |
| Visual IR / Timeline | `lib/mortra/vision/visual-ir.ts` |
| World / Artifact | `lib/mortra/world/world-types.ts` |
| Renderer | `app/proof/page.tsx`, `app/robot/page.tsx`, `components/ScrollSolid.tsx` |

## domain の優先順位

1. **Geometry / Proof** — LiveProof の主戦場
2. **Crystallography（Lattice Core）** — 視覚的に一番映える。実装済み
3. **Mechanics** — ばね・振り子・剛体・波。一般に一瞬で伝わる
4. **Tensor / Lie / Group** — 研究としてのブランド

**教育可視化ツールにはしない。** 目的は意味論 → 対話的視覚表現の一般化で、
教育に使えるのはその結果。
