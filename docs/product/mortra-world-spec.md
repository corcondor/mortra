# MortraWorld 仕様

## なぜ要るか

これまで成果物は別々に生成していた。図を作る関数、記事を書く関数、
動画を書き出す関数がそれぞれ独立していたので、
「証明を座標から幾何に変えて」と言われたら全部作り直すしかなかった。

世界を一つにして、成果物をその射影にする。

## 型

`lib/mortra/world/world-types.ts`

```ts
MortraWorld = {
  brief         何をしたいか（自然文のまま）
  objects       型付きの数学的対象
  claims        主張と、その強さ
  certificates  どの手段でどこまで確かめたか
  proofGraph    証明の DAG。複数経路を保つ
  routes        表現のあいだを移す射
  artifacts     成果物。すべて semantic ID を参照する
  revisions     何を変えたら何が作り直されたか
}
```

## 主張の強さ

```
proved                 記号的に導出し、恒等式として確かめた
verified_instance      具体値では一致した。一般には未証明
numerically_supported  数値では合うが記号的な確認が無い
conjectured            観測しただけ
unverified             出したが確認が取れていない
rejected               確認して、成り立たないと分かった
unformalized           形式化できていない
unsupported            扱える範囲の外
```

## 整合の検査

`auditWorld()` が次を落とす。

```
artifact_without_meaning     意味を参照しない成果物（＝独立生成になっている）
dangling_reference           存在しない意味を指している
proved_without_certificate   proved と名乗るのに証明書が無い
route_without_invariant      保つ不変量を宣言しない移動（＝射ではなく橋）
```

## 「一つを直したら全部更新」

```
affectedByPolicy(world, {audience: 'highschool'})
  → 描画方針だけ変わる。意味は動かない

affectedByRoute(world, [changedClaim])
  → 証明経路が変わる。証明書と意味グラフの整合は保つ
```

この区別が要点。「高校生向けに」と「幾何的に説明して」は別の操作。

## 既存資産の扱い

大規模な書き換えはしない。次を adapter で包む。

```
app/solve      app/proof      app/robot
components/ScrollSolid        lib/proof-scene.ts
lib/vision/lattice.ts         export/video の書き出し
```
