# midpoint-bisector-two-circles-equal-power 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
k b c = triangle; b1 = mirror b k; c1 = mirror c k; a = on_line b1 c1, angle_bisector b k c; m = midpoint b c; n = midpoint c a; p = midpoint a b; e = on_line m n, on_line b k; f = on_line m p, on_line c k; h = foot a b c; o1 = circumcenter a k h; o2 = circumcenter h e f; l = on_circle o1 a, on_circle o2 h; x = on_line m k, on_line e f ? coll x h l
```

## 点の役割対応

- `A` -> `a`
- `B` -> `c`
- `B1` -> `c1`
- `C` -> `b`
- `C1` -> `b1`
- `E` -> `f`
- `F` -> `e`
- `H` -> `h`
- `K` -> `k`
- `L` -> `l`
- `M` -> `m`
- `N` -> `p`
- `O1` -> `o1`
- `O2` -> `o2`
- `P` -> `n`
- `X` -> `x`

## 非退化条件

- `K,B,C form the supplied nondegenerate triangle`
- `A is the intersection of the reflected-BC carrier and the internal angle bisector at K`
- `M,N,P are the three supplied side midpoints`
- `E,F,X and the altitude foot H are defined by the displayed carrier lines`
- `the circumcircles (AKH) and (HEF) are nondegenerate and distinct`
- `L is the common point of those circles distinct from H`

## 未消去条件

- なし

## 量化監査

- 元の一出力交点節は2つの交点から分岐を選ばないため、そのままでは自然文の存在命題と同値ではない。
- 修復後: `exists l: on_circle(o1) and on_circle(o2) and l != h and coll(x,h,l)`
- 自然文の存在命題: `proved`
- 元入力の任意交点版: `not proved`
- この量化修復は凍結ベンチマーク得点へ加算しない。

## 証明書

- SHA-256: `78187f5e265cb3497488be438ba6b49c827e32df432d5f6b1e4294f5370ee213`
- 再生恒等式: `24`

# Midpoint-bisector equal-power chart

## Theorem

In the midpoint-net construction described below, let H be the altitude foot, let L be the second common point of (AKH) and (HEF), and let X=MK intersect EF.  Then X,H,L are collinear.

## Representation changes

- midpoint net -> two affine line intersections E,F
- angle bisector -> a symmetric two-ray coordinate chart
- Pappus/Desargues block -> A,E,F collinear and BF || CE || AK
- Apollonius/symmedian block -> one exact equality of powers
- two common circle points -> the radical axis HL

## Replayed identities

- `half_angle_direction_is_unit`: `0`
- `A_on_reflected_BC_line`: `0`
- `A_on_normalized_angle_bisector`: `0`
- `M_is_midpoint_BC_x`: `0`
- `M_is_midpoint_BC_y`: `0`
- `N_is_midpoint_CA_x`: `0`
- `N_is_midpoint_CA_y`: `0`
- `P_is_midpoint_AB_x`: `0`
- `P_is_midpoint_AB_y`: `0`
- `E_on_MN`: `0`
- `E_on_BK`: `0`
- `F_on_MP`: `0`
- `F_on_CK`: `0`
- `Pappus_AEF_collinear`: `0`
- `Desargues_BF_parallel_AK`: `0`
- `Desargues_CE_parallel_AK`: `0`
- `Z_on_EF`: `0`
- `Z_on_BC`: `0`
- `ZK_perpendicular_AK`: `0`
- `H_on_BC`: `0`
- `AH_perpendicular_BC`: `0`
- `X_on_MK`: `0`
- `X_on_EF`: `0`
- `equal_circle_powers`: `0`

- all identities replayed: `True`
- all domain conditions discharged: `True`
- certificate SHA-256: `78187f5e265cb3497488be438ba6b49c827e32df432d5f6b1e4294f5370ee213`
