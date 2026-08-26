# incircle-contact-circle-pencil-midpoint-radical-axis 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; i = incenter a b c; d = foot i b c; e = foot i a c; f = foot i a b; k = foot d e f; o1 = circumcenter a i b; c1 = on_circle o1 a, on_circle i d; c2 = on_circle o1 a, on_circle i d; o2 = circumcenter a i c; b1 = on_circle o2 a, on_circle i d; b2 = on_circle o2 a, on_circle i d; o3 = circumcenter b b1 b2; o4 = circumcenter c c1 c2; p1 = on_circle o3 b, on_circle o4 c; p2 = on_circle o3 b, on_circle o4 c; m = midpoint d k ? coll m p1 p2
```

## 点の役割対応

- `A` -> `a`
- `B` -> `c`
- `B1` -> `c1`
- `B2` -> `c2`
- `C` -> `b`
- `C1` -> `b1`
- `C2` -> `b2`
- `D` -> `d`
- `E` -> `f`
- `F` -> `e`
- `I` -> `i`
- `K` -> `k`
- `M` -> `m`
- `OAB` -> `o2`
- `OAC` -> `o1`
- `OB` -> `o4`
- `OC` -> `o3`
- `P1` -> `p1`
- `P2` -> `p2`

## 非退化条件

- `ABC is a defined nondegenerate triangle with incenter I`
- `D,E,F are the three defined perpendicular contact projections from I`
- `K is the defined projection of D onto EF and M is the midpoint of DK`
- `the AIB and AIC circumcircles meet the incircle in the displayed pairs`
- `the two target circumcircles through B and C are defined`
- `P1 and P2 are the two displayed common points of the target circles`

## 未消去条件

- なし

## 証明書

- SHA-256: `9af628159cba1714545645950dc531cb26fdbe3e87cf228bca3798cc15d8773c`
- 再生恒等式: `22`

# Incircle-contact circle-pencil midpoint chart

## Theorem

Let D,E,F be the contact points of the incircle of triangle ABC. Let K be the projection of D onto EF and M the midpoint of DK. The circle through B and the common chord of (AIC) with the incircle, and the analogous circle through C from (AIB), have equal power at M.

## Representation changes

- contact triangle -> three tangent-line intersections
- circle-circle intersections -> a linear common-chord equation
- three-point circle -> incircle plus a multiple of that chord
- midpoint collinearity -> equality of two circle powers

## Replayed identities

- `D_on_normalized_incircle`: `0`
- `E_on_normalized_incircle`: `0`
- `F_on_normalized_incircle`: `0`
- `A_on_tangent_at_E`: `0`
- `A_on_tangent_at_F`: `0`
- `B_on_tangent_at_F`: `0`
- `B_on_tangent_at_D`: `0`
- `C_on_tangent_at_D`: `0`
- `C_on_tangent_at_E`: `0`
- `K_on_EF`: `0`
- `DK_perpendicular_EF`: `0`
- `M_midpoint_DK_x`: `0`
- `M_midpoint_DK_y`: `0`
- `A_on_circle_AIC`: `0`
- `C_on_circle_AIC`: `0`
- `A_on_circle_AIB`: `0`
- `B_on_circle_AIB`: `0`
- `circle_subtraction_gives_common_chord`: `0`
- `B_closes_first_circle_pencil`: `0`
- `C_closes_second_circle_pencil`: `0`
- `M_has_equal_power_to_both_pencil_circles`: `0`
- `circle_pencil_preserves_common_chord`: `0`

- all identities replayed: `True`
- all domain conditions discharged: `True`
- certificate SHA-256: `9af628159cba1714545645950dc531cb26fdbe3e87cf228bca3798cc15d8773c`
