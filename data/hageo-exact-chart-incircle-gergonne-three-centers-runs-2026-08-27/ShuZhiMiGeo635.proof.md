# incircle-gergonne-three-circumcenters-centroid-axis 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; k = on_line k a d, on_line k b e; o = circumcenter o a b c; x = on_line x a k, on_circle x o a; y = on_line y b k, on_circle y o a; z = on_line z c k, on_circle z o a; oa = circumcenter oa y k z; ob = circumcenter ob z k x; oc = circumcenter oc x k y; m1 m2 m3 g = centroid m1 m2 m3 g oa ob oc ? coll g i k
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `G` -> `g`
- `I` -> `i`
- `K` -> `k`
- `O` -> `o`
- `OA` -> `oa`
- `OB` -> `ob`
- `OC` -> `oc`
- `X` -> `x`
- `Y` -> `y`
- `Z` -> `z`

## 非退化条件

- `ABC is a defined nondegenerate triangle with incenter I`
- `D,E,F are the three defined perpendicular contact feet of I`
- `K is the defined intersection of AD and BE`
- `O is the defined circumcenter of ABC`
- `X,Y,Z are the defined second intersections of AK,BK,CK with (ABC)`
- `OA,OB,OC are the defined circumcenters of YKZ,ZKX,XKY`
- `G is the centroid output associated with OA,OB,OC`

## 未消去条件

- なし

## 証明書

- SHA-256: `7a0a41039baac848422e6458e90f1fc7c24ff6ee24a6167db315b634a61b287d`
- 再生恒等式: `30`

# Incircle-Gergonne three-circumcenter chart

## Theorem

Let K be the Gergonne point of ABC and X,Y,Z the second intersections of AK,BK,CK with (ABC).  If OA,OB,OC are the circumcenters of YKZ,ZKX,XKY, then their centroid G lies on IK.

## Representation changes

- incircle contact triangle -> two rational contact parameters
- Gergonne concurrence -> three exact line determinants
- second circle intersections -> one known-root division each
- three circumcenters -> six linear equal-distance equations
- centroid collinearity -> one scalar-multiple identity

## Replayed identities

- `D_on_unit_incircle`: `0`
- `E_on_unit_incircle`: `0`
- `F_on_unit_incircle`: `0`
- `A_on_tangent_at_E`: `0`
- `A_on_tangent_at_F`: `0`
- `B_on_tangent_at_D`: `0`
- `B_on_tangent_at_F`: `0`
- `C_on_tangent_at_D`: `0`
- `C_on_tangent_at_E`: `0`
- `K_on_AD`: `0`
- `K_on_BE`: `0`
- `K_on_CF_Gergonne_concurrence`: `0`
- `A_on_circumcircle`: `0`
- `B_on_circumcircle`: `0`
- `C_on_circumcircle`: `0`
- `X_on_AK`: `0`
- `X_on_circumcircle`: `0`
- `Y_on_BK`: `0`
- `Y_on_circumcircle`: `0`
- `Z_on_CK`: `0`
- `Z_on_circumcircle`: `0`
- `OA_equidistant_Y_K`: `0`
- `OA_equidistant_Y_Z`: `0`
- `OB_equidistant_Z_K`: `0`
- `OB_equidistant_Z_X`: `0`
- `OC_equidistant_X_K`: `0`
- `OC_equidistant_X_Y`: `0`
- `centroid_scalar_x`: `0`
- `centroid_scalar_y`: `0`
- `G_I_K_collinear`: `0`

- all identities replayed: `True`
- all domain conditions discharged: `True`
- certificate SHA-256: `7a0a41039baac848422e6458e90f1fc7c24ff6ee24a6167db315b634a61b287d`
