# incircle-diameter-circle-reflection 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; i = incenter a b c; d = foot i b c; o = circumcenter a b c; m1 = midpoint a i; s = on_circle o a, on_circle m1 a; h = orthocenter b i c; q = on_line h s, on_circle m1 a; m2 = midpoint d q; x = mirror i m2 ? cong x i i d
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `H` -> `h`
- `I` -> `i`
- `M1` -> `m1`
- `M2` -> `m2`
- `O` -> `o`
- `Q` -> `q`
- `S` -> `s`
- `X` -> `x`

## 非退化条件

- `p,q != +/-1`
- `p*q != -1 and p*q != 1`
- `W(p,q) != 0`
- `the named second-intersection branches are selected`

## 未消去条件

- なし

## 証明書

- SHA-256: `550c0ab18ef1d9e4834f04e1252828a0960b8adf7b6f510d1fbf9adbfa15bf87`
- 再生恒等式: `24`

# 内接円・直径円・点反転チャート

## 定理

内心 $I$、接点 $D$、直径 $AI$ の円、三角形 $BIC$ の垂心 $H$を用いる所定の構成で、$DQ$ の中点に関する $I$ の対称点 $X$ は内接円上にある。したがって $IX=ID$ である。

## 接線座標による標準化

I=(0,0), incircle: x^2+y^2=1, BC: y=-1; AB and AC are unit-circle tangents with parameters p and q

## 非退化条件

- `p,q != +/-1`
- `p*q != -1 and p*q != 1`
- `W(p,q) != 0`
- `the named second-intersection branches are selected`

## 条件の消去根拠

- `p,q != +/-1`: AB and AC meet the fixed tangent BC at finite vertices B and C; the tangent parameters +/-1 would make either side parallel to or coincident with BC.
- `p*q != -1`: AB and AC meet at the finite vertex A; p*q=-1 makes the two tangents parallel.
- `p*q != 1`: For p*q=1 the second line-circle intersection Q collapses to the existing point I, which reduce_intersection rejects.
- `W(p,q) != 0`: W is the denominator of the nontrivial HS/circle intersection Q; the successful finite JGEX construction excludes W=0.
- `the named second-intersection branches are selected`: The first circle pair already shares A and the line-circle pair already shares S; reduce_intersection rejects existing points and returns the remaining branch.

## 構成点の座標

- `A=(-(p*q - 1)/(p*q + 1), (p + q)/(p*q + 1))`
- `B=(-(p + 1)/(p - 1), -1)`
- `C=(-(q + 1)/(q - 1), -1)`
- `I=(0, 0)`
- `D=(0, -1)`
- `O=(-(p*q - 1)/((p - 1)*(q - 1)), -(p**2*q**2 - 2*p**2*q + p**2 - 2*p*q**2 - 2*p + q**2 - 2*q + 1)/(2*(p - 1)*(q - 1)*(p*q + 1)))`
- `M1=(-(p*q - 1)/(2*(p*q + 1)), (p + q)/(2*(p*q + 1)))`
- `S=(-(p + 1)*(q + 1)*(p*q - 1)/(2*(p**2*q**2 + 1)), -(p**2*q**2 - p**2*q - p*q**2 - 2*p*q - p - q + 1)/(2*(p**2*q**2 + 1)))`
- `H=(0, -2*(p*q + 1)/((p - 1)*(q - 1)))`
- `Q=(-2*(p*q - 1)*(2*p*q - p - q + 2)/(5*p**2*q**2 - 4*p**2*q + p**2 - 4*p*q**2 + 8*p*q - 4*p + q**2 - 4*q + 5), 2*(p*q - 1)**2/(5*p**2*q**2 - 4*p**2*q + p**2 - 4*p*q**2 + 8*p*q - 4*p + q**2 - 4*q + 5))`
- `M2=(-(p*q - 1)*(2*p*q - p - q + 2)/(5*p**2*q**2 - 4*p**2*q + p**2 - 4*p*q**2 + 8*p*q - 4*p + q**2 - 4*q + 5), -(p*q - p - q + 3)*(3*p*q - p - q + 1)/(2*(5*p**2*q**2 - 4*p**2*q + p**2 - 4*p*q**2 + 8*p*q - 4*p + q**2 - 4*q + 5)))`
- `X=(-2*(p*q - 1)*(2*p*q - p - q + 2)/(5*p**2*q**2 - 4*p**2*q + p**2 - 4*p*q**2 + 8*p*q - 4*p + q**2 - 4*q + 5), -(p*q - p - q + 3)*(3*p*q - p - q + 1)/(5*p**2*q**2 - 4*p**2*q + p**2 - 4*p*q**2 + 8*p*q - 4*p + q**2 - 4*q + 5))`

## 証明過程

2本の辺を単位円の接線として表し、外心、2つの円交点、垂心、点対称を順に代入する。最後に $|IX|^2-|ID|^2$ を簡約する。

- `first_tangent_normal_is_unit`: `0`
- `second_tangent_normal_is_unit`: `0`
- `A_on_first_tangent`: `0`
- `B_on_first_tangent`: `0`
- `A_on_second_tangent`: `0`
- `C_on_second_tangent`: `0`
- `BC_tangent_to_unit_incircle`: `0`
- `D_is_foot_from_I_to_BC_x`: `0`
- `D_is_foot_from_I_to_BC_y`: `0`
- `O_is_circumcenter_AB`: `0`
- `O_is_circumcenter_AC`: `0`
- `M1_midpoint_AI_x`: `0`
- `M1_midpoint_AI_y`: `0`
- `S_on_diameter_circle_AI`: `0`
- `S_on_circumcircle`: `0`
- `H_altitude_from_I`: `0`
- `H_altitude_from_B`: `0`
- `Q_on_HS`: `0`
- `Q_on_diameter_circle_AI`: `0`
- `M2_midpoint_DQ_x`: `0`
- `M2_midpoint_DQ_y`: `0`
- `X_reflection_of_I_x`: `0`
- `X_reflection_of_I_y`: `0`
- `goal_IX_equals_ID`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `550c0ab18ef1d9e4834f04e1252828a0960b8adf7b6f510d1fbf9adbfa15bf87`
