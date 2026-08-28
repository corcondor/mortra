# incenter-side-midpoint-perpendicular-triangle-radical-axis 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; i = incenter a b c; m1 = midpoint b c; m2 = midpoint a c; m3 = midpoint a b; a1 = on_tline m2 b i, on_tline m3 c i; b1 = on_tline m1 a i, on_tline m3 c i; c1 = on_tline m1 a i, on_tline m2 b i; h = orthocenter a1 b1 c1; m = midpoint i h; o = circumcenter a b c; o1 = circumcenter a1 b1 c1; x = on_circle o a, on_circle o1 a1; y = on_circle o a, on_circle o1 a1 ? coll x y m
```

## 点の役割対応

- `A` -> `a`
- `A1` -> `a1`
- `B` -> `b`
- `B1` -> `b1`
- `C` -> `c`
- `C1` -> `c1`
- `H` -> `h`
- `I` -> `i`
- `M` -> `m`
- `MA` -> `m1`
- `MB` -> `m2`
- `MC` -> `m3`
- `O` -> `o`
- `O1` -> `o1`
- `X` -> `x`
- `Y` -> `y`

## 非退化条件

- `p and q are real`
- `p*q*(p-q)*(1+p*q) != 0`
- `the three midpoint perpendiculars form a nondegenerate triangle`
- `the two circumcircles have two distinct supplied common points X,Y`

## 未消去条件

- なし

## 証明書

- SHA-256: `c40ffcaa9af016741a2614a37eb7d4c63af27a3514a63ac46a6fe3096c34b3bd`
- 再生恒等式: `31`

# 内心・辺中点垂線三角形の根軸チャート

## 定理

三角形 $ABC$ の内心を $I$ とする。辺 $BC,CA,AB$ の中点をそれぞれ $M_A,M_B,M_C$ とし、$M_A,M_B,M_C$ を通って$AI,BI,CI$ に垂直な3直線が作る三角形を $A_1B_1C_1$ とする。その垂心を $H$、$IH$ の中点を $M$ とすると、$M$ は$ABC$ と $A_1B_1C_1$ の外接円の根軸上にある。

## 標準化

I=(0,0), the incircle has radius 1, BC is x=1, and the other two side tangents have half-angle parameters p and q.

## 定義域条件

- `p and q are real`
- `p*q*(p-q)*(1+p*q) != 0`
- `the three midpoint perpendiculars form a nondegenerate triangle`
- `the two circumcircles have two distinct supplied common points X,Y`

## 条件の消去

- `p*q*(p-q)*(1+p*q) != 0`: The JGEX triangle and incenter require three distinct nonparallel side tangents; this is exactly the nonzero factor in the unit-incircle chart.
- `triangle A1B1C1 is nondegenerate`: Its doubled area factors as -p*q*(p-q)*(1+p^2)*(1+q^2) / (4*(1+p*q)^2), hence it is nonzero over the real parameter domain.
- `X and Y are distinct common points of the two circles`: The source constructs two circle intersections and uses them as a line; the JGEX construction domain rejects a collapsed common chord.

## 座標

- `I=(0, 0)`
- `A=(-(p*q - 1)/(p*q + 1), (p + q)/(p*q + 1))`
- `B=(1, q)`
- `C=(1, p)`
- `MA=(1, (p + q)/2)`
- `MB=(1/(p*q + 1), (p**2*q + 2*p + q)/(2*(p*q + 1)))`
- `MC=(1/(p*q + 1), (p*q**2 + p + 2*q)/(2*(p*q + 1)))`
- `A1=((p**2*q**2 + p*q + 2)/(2*(p*q + 1)), (p + q)/(2*(p*q + 1)))`
- `B1=(-(p**2 - p*q - 2)/(2*(p*q + 1)), (p*q**2 + 2*p + q)/(2*(p*q + 1)))`
- `C1=((p*q - q**2 + 2)/(2*(p*q + 1)), (p**2*q + p + 2*q)/(2*(p*q + 1)))`
- `O=(-(p**2*q**2 - p**2 - q**2 - 3)/(4*(p*q + 1)), (p + q)/2)`
- `O1=((p**2*q**2 - p**2 + 2*p*q - q**2 + 3)/(4*(p*q + 1)), (p + q)/(2*(p*q + 1)))`
- `H=((p*q + 3)/(2*(p*q + 1)), (p + q)*(p*q + 2)/(2*(p*q + 1)))`
- `M=((p*q + 3)/(4*(p*q + 1)), (p + q)*(p*q + 2)/(4*(p*q + 1)))`

## 非退化因子

- `triangle_ABC_twice_area`: `2*p*q*(p - q)/(p*q + 1)`
- `line_B_line_C`: `p - q`
- `line_A_line_C`: `-q*(p**2 + 1)/(p*q + 1)`
- `line_A_line_B`: `-p*(q**2 + 1)/(p*q + 1)`
- `triangle_A1B1C1_twice_area`: `-p*q*(p - q)*(p**2 + 1)*(q**2 + 1)/(4*(p*q + 1)**2)`
- `circumcenter_ABC`: `4*p*q*(p - q)/(p*q + 1)`
- `circumcenter_A1B1C1`: `-p*q*(p - q)*(p**2 + 1)*(q**2 + 1)/(2*(p*q + 1)**2)`

## 恒等式再生

- `CA_tangent_normalized`: `0`
- `AB_tangent_normalized`: `0`
- `A_on_CA`: `0`
- `A_on_AB`: `0`
- `B_on_AB`: `0`
- `B_on_BC`: `0`
- `C_on_BC`: `0`
- `C_on_CA`: `0`
- `MA_midpoint_x`: `0`
- `MA_midpoint_y`: `0`
- `MB_midpoint_x`: `0`
- `MB_midpoint_y`: `0`
- `MC_midpoint_x`: `0`
- `MC_midpoint_y`: `0`
- `A1_on_line_B`: `0`
- `A1_on_line_C`: `0`
- `B1_on_line_A`: `0`
- `B1_on_line_C`: `0`
- `C1_on_line_A`: `0`
- `C1_on_line_B`: `0`
- `O_equidistant_A_B`: `0`
- `O_equidistant_A_C`: `0`
- `O1_equidistant_A1_B1`: `0`
- `O1_equidistant_A1_C1`: `0`
- `H_altitude_A1`: `0`
- `H_altitude_B1`: `0`
- `H_altitude_C1`: `0`
- `M_midpoint_IH_x`: `0`
- `M_midpoint_IH_y`: `0`
- `circumradii_equal`: `0`
- `M_equal_circle_powers`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `c40ffcaa9af016741a2614a37eb7d4c63af27a3514a63ac46a6fe3096c34b3bd`
