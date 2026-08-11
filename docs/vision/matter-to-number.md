# Matter to Number

MORTRA Vision の最初の縦貫デモ。

## 流れ

```
FCC 結晶
  ↓  dual
逆格子 BCC
  ↓  millerPlane
Miller 面 / 回折
  ↓  automorphisms
Aut(Λ)  位数 48
  ↓  rootSystem
A₃ ルート系  12本
  ↓  cartan
Dynkin 図 / ウェイト格子
  ↓  thetaSeries
Θ(q) = 1 + 12q² + 6q⁴ + 24q⁶ + …
  ↓
整数の表現数
```

最後に `It was the same lattice all along.`

## 数値はすべて出ている

`npx tsx scripts/verify-lattice.mts` で確認済み。

```
配位数        SC 6 / FCC 12 / BCC 8
充填率        π/6 / π/(3√2) / π√3/8
双対          FCC ↔ BCC、SC は自己双対
Miller 面間隔  a/√(h²+k²+l²)
Aut の位数     いずれも 48
ルート系       FCC の最近接12本 = A₃、Cartan [[2,-1,-1],[-1,2,0],[-1,0,2]]
テータ級数     D₃ の既知係数と全一致
```

## 守る規則

- **別々の動画を連結しない。** 一つの semantic ID を追跡する
- 同じベクトルが、各 view で意味を変えて再解釈される
- 式・図・説明が同期する
- スクロール／時間軸が数理操作に対応する。戻すと数学の状態も戻る
- domain kernel から生成する。ハードコードしたシーンだけにしない

## 残り

数値は揃っている。残っているのは Visual IR と Timeline の実装。
`lib/mortra/vision/visual-ir.ts` に型はあるので、
`lattice.ts` から `VisualScene` を作る adapter を書けば繋がる。
