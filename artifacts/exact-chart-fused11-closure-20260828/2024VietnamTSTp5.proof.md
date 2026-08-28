# incircle-contact-chord-circumtangents-isogonal-trace 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; i = incenter a b c; d = foot i b c; e = foot i a c; f = foot i a b; o = circumcenter a b c; m = on_line e f, on_circle o a; s = on_tline m o m, on_tline a o a; t = on_tline b o b, on_tline c o c; j = on_line t i, on_line o a ? eqangle a s s j i s s t
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `I` -> `i`
- `J` -> `j`
- `M` -> `m`
- `O` -> `o`
- `S` -> `s`
- `T` -> `t`

## 非退化条件

- `ABC is a nondegenerate triangle and I is its incenter`
- `D,E,F are the perpendicular feet of I on BC,CA,AB`
- `O is the circumcenter and M is a defined common point of EF and (O)`
- `the tangent pairs at M,A and B,C have finite intersections S,T`
- `the lines TI and OA have a finite intersection J`

## 未消去条件

- なし

## 証明書

- SHA-256: `de3428739823e63c65aca9b509ea139cf37e2aa7775781d2c96192558a67579c`
- 再生恒等式: `26`

# Incircle contact-chord tangent-isogonality chart

## Theorem

Let the incircle of ABC touch CA and AB at E and F.  Let M be either point of EF on the circumcircle.  The tangents at A,M meet at S and the tangents at B,C meet at T.  If J=TI cap OA, then angle ASJ=angle IST modulo pi.

## Reusable proof

1. EF is the polar of A with respect to the incircle.
2. Normalize the circumcircle to the unit circle and use rational half-angle coordinates.
3. Tangent intersections and J are linear rational constructions in that chart.
4. The directed-angle numerator factors through the polar-incidence numerator.
5. M lies on EF, so that incidence factor is zero; hence the angle equality follows.

## Exact replay

- `A_on_unit_circumcircle`: `0`
- `B_on_unit_circumcircle`: `0`
- `C_on_unit_circumcircle`: `0`
- `M_on_unit_circumcircle`: `0`
- `I_equidistant_from_AB_AC`: `0`
- `I_equidistant_from_AB_BC`: `0`
- `D_on_BC`: `0`
- `ID_perpendicular_BC`: `0`
- `E_on_CA`: `0`
- `IE_perpendicular_CA`: `0`
- `F_on_AB`: `0`
- `IF_perpendicular_AB`: `0`
- `ID_squared_is_inradius_squared`: `0`
- `IE_squared_is_inradius_squared`: `0`
- `IF_squared_is_inradius_squared`: `0`
- `E_on_contact_polar_of_A`: `0`
- `F_on_contact_polar_of_A`: `0`
- `EF_perpendicular_AI`: `0`
- `EF_line_equals_contact_polar`: `0`
- `S_on_tangent_at_M`: `0`
- `S_on_tangent_at_A`: `0`
- `T_on_tangent_at_B`: `0`
- `T_on_tangent_at_C`: `0`
- `J_on_TI`: `0`
- `J_on_OA`: `0`
- `directed_angle_numerator_factors_through_EF`: `0`

- all identities replayed: `True`
- all conditions discharged: `True`
- certificate SHA-256: `de3428739823e63c65aca9b509ea139cf37e2aa7775781d2c96192558a67579c`
