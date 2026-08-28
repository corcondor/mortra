# isosceles-orthocenter-midpoint-trisection-perpendicular 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = iso_triangle; h = orthocenter a b c; e = midpoint a c; d f = trisegment d f c b ? perp b e h d
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `H` -> `h`

## 非退化条件

- `t is real and t != 0`
- `H is the orthocenter and D,F are the ordered trisection points of CB`

## 未消去条件

- なし

## 証明書

- SHA-256: `856c0b05c48513df47f661fe372250be9655fe5d63fdd95e26df1dca984f42de`
- 再生恒等式: `11`

# 二等辺三角形・垂心・三等分点の直交チャート

## 定理

$AB=AC$ の三角形 $ABC$ で、$H$ を垂心、$E$ を $AC$ の中点とする。$D,F$ が $CB$ をこの順に三等分するとき、$BE\perp HD$ である。

## 標準化

B=(-1,0), C=(1,0), A=(0,t) with t nonzero

## 定義域条件

- `t is real and t != 0`
- `H is the orthocenter and D,F are the ordered trisection points of CB`

## 条件の消去

- `t != 0`: The accepted isosceles triangle is nondegenerate; its normalized height therefore does not vanish.
- `D and F are ordered trisection points of CB`: JGEX trisegment returns the first and second internal trisection points in the declared endpoint order.

## 座標

- `A=(0, t)`
- `B=(-1, 0)`
- `C=(1, 0)`
- `H=(0, 1/t)`
- `E=(1/2, t/2)`
- `D=(1/3, 0)`
- `F=(-1/3, 0)`

## 恒等式再生

- `isosceles_AB_AC`: `0`
- `H_altitude_A`: `0`
- `H_altitude_B`: `0`
- `H_altitude_C`: `0`
- `E_midpoint_AC_x`: `0`
- `E_midpoint_AC_y`: `0`
- `D_first_trisection_x`: `0`
- `D_first_trisection_y`: `0`
- `F_second_trisection_x`: `0`
- `F_second_trisection_y`: `0`
- `goal_BE_perpendicular_HD`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `856c0b05c48513df47f661fe372250be9655fe5d63fdd95e26df1dca984f42de`
