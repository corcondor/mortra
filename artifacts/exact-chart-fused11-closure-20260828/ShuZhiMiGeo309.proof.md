# excentral-contact-triangle-radical-centers-incenter-axis 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; i = incenter a b c; i1 = excenter a b c; i2 = excenter b c a; i3 = excenter c a b; a1 = foot i1 a b; a2 = foot i1 a c; b1 = foot i2 b c; b2 = foot i2 b a; c1 = foot i3 c a; c2 = foot i3 c b; d = on_line b1 b2, on_line c1 c2; e = on_line a1 a2, on_line c1 c2; f = on_line a1 a2, on_line b1 b2; o1 = circumcenter d e f; x1 = on_circle o1 d, on_circle i1 a1; x2 = on_circle o1 d, on_circle i1 a1; y1 = on_circle o1 d, on_circle i2 b1; y2 = on_circle o1 d, on_circle i2 b1; z1 = on_circle o1 d, on_circle i3 c1; z2 = on_circle o1 d, on_circle i3 c1; x = on_line y1 y2, on_line z1 z2; y = on_line x1 x2, on_line z1 z2; z = on_line x1 x2, on_line y1 y2; o2 = circumcenter x y z ? coll i o1 o2
```

## 点の役割対応

- `A` -> `a`
- `A1` -> `a1`
- `A2` -> `a2`
- `B` -> `b`
- `B1` -> `b1`
- `B2` -> `b2`
- `C` -> `c`
- `C1` -> `c1`
- `C2` -> `c2`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `I` -> `i`
- `I1` -> `i1`
- `I2` -> `i2`
- `I3` -> `i3`
- `O1` -> `o1`
- `O2` -> `o2`
- `X` -> `x`
- `Y` -> `y`
- `Z` -> `z`

## 非退化条件

- `ABC is a nondegenerate triangle with incenter I and three excenters`
- `all six excentral contact feet and the contact-line triangle DEF are defined`
- `Omega=(DEF) and all three excircles are defined`
- `each named pair consists of the two common points of Omega and one excircle`
- `the radical centers X,Y,Z and their circumcircle are defined`

## 未消去条件

- なし

## 証明書

- SHA-256: `3c880120f12cf0d46feb9f4f5b1d9e847ea224c1ea791136216d3461a090d3dd`
- 再生恒等式: `43`

# Excentral radical-centers axis chart

## Reusable proof

1. Normalize the incircle to the unit circle.
2. Encode the three sides by rational unit normals.
3. Solve the signed-distance equations for the excenters and feet.
4. Construct DEF and Omega exactly.
5. Replace every circle-intersection pair by its radical axis.
6. Construct X,Y,Z, then replay I,O1,O2 collinear.

## Exact replay

- `normal_a_unit`: `0`
- `normal_b_unit`: `0`
- `normal_c_unit`: `0`
- `A_on_sides_b_c`: `0`
- `B_on_sides_c_a`: `0`
- `C_on_sides_a_b`: `0`
- `A_excenter_signed_distance_ab`: `0`
- `A_excenter_signed_distance_ac`: `0`
- `B_excenter_signed_distance_ba`: `0`
- `B_excenter_signed_distance_bc`: `0`
- `C_excenter_signed_distance_ca`: `0`
- `C_excenter_signed_distance_cb`: `0`
- `A1_on_AB`: `0`
- `A1_foot_direction`: `0`
- `A2_on_AC`: `0`
- `A2_foot_direction`: `0`
- `B1_on_BC`: `0`
- `B1_foot_direction`: `0`
- `B2_on_BA`: `0`
- `B2_foot_direction`: `0`
- `C1_on_CA`: `0`
- `C1_foot_direction`: `0`
- `C2_on_CB`: `0`
- `C2_foot_direction`: `0`
- `D_on_B1B2`: `0`
- `D_on_C1C2`: `0`
- `E_on_A1A2`: `0`
- `E_on_C1C2`: `0`
- `F_on_A1A2`: `0`
- `F_on_B1B2`: `0`
- `D_on_Omega`: `0`
- `E_on_Omega`: `0`
- `F_on_Omega`: `0`
- `X_equal_power_Omega_excircle_B`: `0`
- `X_equal_power_Omega_excircle_C`: `0`
- `Y_equal_power_Omega_excircle_A`: `0`
- `Y_equal_power_Omega_excircle_C`: `0`
- `Z_equal_power_Omega_excircle_A`: `0`
- `Z_equal_power_Omega_excircle_B`: `0`
- `X_on_XYZ_circle`: `0`
- `Y_on_XYZ_circle`: `0`
- `Z_on_XYZ_circle`: `0`
- `I_O1_O2_collinear`: `0`

- all identities replayed: `True`
- all conditions discharged: `True`
- certificate SHA-256: `3c880120f12cf0d46feb9f4f5b1d9e847ea224c1ea791136216d3461a090d3dd`
