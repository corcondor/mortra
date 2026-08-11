# Domain Kernel の契約

同じ数学 kernel を solver 用・Vision 用・design 用に重複実装しない。
一つの canonical kernel と binding layer にする。

## 現在の実装

| kernel | 実体 | 利用先 |
|---|---|---|
| **Lattice** | `lib/vision/lattice.ts` | solver（未接続）/ Vision / Design |
| **GroupAction** | `lib/mortra/vision/ornament.ts` の `closePointGroup` | Vision / Design |
| **Expression / MathML** | `worker/backend/mathml_ast.py` + `solve_from_ast.py` | solver / LiveProof |
| **Geometry** | `worker/backend/geometry_natural_formalizer.py` + `lib/proof-scene.ts` | solver / LiveProof |

## 監査で確認したこと

```
grep -rln "closePointGroup|matMul"     → ornament.ts と design-world.ts のみ
                                          design-world は ornament を import している
grep -rln "minimalVectors|thetaSeries" → lattice.ts と design-world.ts のみ
                                          design-world は lattice を import している
```

**群と格子の重複実装は無い。** design 側は import で共有している。

## 残っている分断

**Lattice kernel が solver に接続されていない。**
`worker/src/generalization-kernel.ts` の射のアトラスには `Lattice` ソートが無く、
`lib/vision/lattice.ts` は TypeScript 側にしかない。
入試の整数格子問題・二次形式問題へ届いていない。

これが A4（shared domain kernels）の中身になる。

## 契約

各 domain kernel は次を提供する。Three.js / SVG / canvas は触らない。

```
domain object     型を持つ数学的対象
typed operations  対象の上の操作
invariants        操作が保つもの
conventions       規約（暗黙にしない）
certificates      検証の手段と結果
failure states    できないときに何が足りないか
```

描画は Visual IR より下の層の仕事。
