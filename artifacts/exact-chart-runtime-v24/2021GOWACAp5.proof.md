# second-lemoine-harmonic-pascal-incenter-altitude 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; d = foot a b c; o = circumcenter a b c; m m1 m2 g = centroid m m1 m2 g a b c; k = on_aline k a c b a g, on_aline k b a c b g; d1 = mirror d m; d2 = on_line b c, on_aline d2 a b c a d1; p = on_tline k a o, on_line a d2; x = on_line b c, on_tline k b o; y = on_line b c, on_tline k c o; i = incenter p x y ? coll i a d
```

## Natural-language domain

```text
Let $ABC$ be an acute triangle with altitude $\overline{AD}$, circumcenter $O$, and symmedian point $K$. Let $D_1$, $D_2$ be points on segment $\overline{BC}$ such that $BD = CD_1$ and $\angle BAD_2 = \angle CAD_1$. The line through $K$ perpendicular to $\overline{AO}$ meets $\overline{AD_2}$ at $P$, and the lines through $K$ perpendicular to $\overline{BO}$, $\overline{CO}$ meet $\overline{BC}$ at $X$, $Y$. Prove that the incenter $I$ of $\triangle PXY$ lies on $\overline{AD}$.
```

- typed atoms: acute(A,B,C), between(D1,B,C), between(D2,B,C)
- statement SHA-256: `0ae4d2dff38b5bf1a40bb0a9d794e615adb95a7298c960b543ec1c6691f6572c`

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `D1` -> `d1`
- `D2` -> `d2`
- `G` -> `g`
- `I` -> `i`
- `K` -> `k`
- `M` -> `m`
- `O` -> `o`
- `P` -> `p`
- `X` -> `x`
- `Y` -> `y`

## 非退化条件

- `ABC is acute and oriented with B=(0,0), C=(1,0), A=(u,v), v>0`
- `D is the altitude foot from A and O is the circumcenter of ABC`
- `M is the midpoint of BC and G is the centroid of ABC`
- `K is the intersection of the two displayed symmedian angle lines`
- `D1 is the reflection of D in M and D2 is the selected point on BC`
- `P,X,Y are the three displayed perpendicular-line intersections`
- `I is the internal incenter of the nondegenerate triangle PXY`

## 未消去条件

- なし

## 証明書

- SHA-256: `b01b47e337b024bfededd0db6a031ee6b74c39daead5106c1d3247f7c4a90cde`
- 再生恒等式: `41`

# Second Lemoine circle / harmonic incenter chart

## Theorem

In the acute-triangle construction described by the chart, the incenter of PXY lies on the altitude AD.

## Representation changes

- two directed-angle loci -> the symmedian point K
- three perpendicular projections -> the second Lemoine circle
- harmonic bundle / power identity -> cyclic quadrilateral PKXY
- cyclic angles -> internal bisectors XW and YV
- Pascal's point at infinity -> the altitude direction AD

## Domain and branch signs

- `acute_coordinate_domain`: acute(B), acute(C), acute(A) give u>0, 1-u>0, t=u^2-u+v^2>0; orientation gives v>0
- `denominators`: h=1+t>0 and 3u^2-3u+v^2+1>=(u-1/2)^2+1/4+v^2>0
- `D1_D2_on_segment`: D1_x=1-u is in (0,1); D2_x=u*s/q is in (0,1) because q-u*s=(1-u)((1-u)^2+v^2)>0
- `triangle_PXY_nondegenerate`: X_x-Y_x=t/h>0 and P_y=2uv(1-u)/h>0
- `XW_internal_branch`: cross(XP,XW)=uv(1-u)s/h^2>0 and cross(XW,XY)=uvt/h^2>0
- `YV_internal_branch`: cross(YP,YV)=-uv(1-u)((1-u)^2+v^2)/h^2<0 and cross(YV,YX)=-v(1-u)t/h^2<0

## Replayed identities

- `D_on_BC`: `0`
- `AD_perpendicular_BC`: `0`
- `O_equidistant_A_B`: `0`
- `O_equidistant_A_C`: `0`
- `M_midpoint_BC_x`: `0`
- `M_midpoint_BC_y`: `0`
- `G_centroid_x`: `0`
- `G_centroid_y`: `0`
- `K_first_symmedian_angle_line`: `0`
- `K_second_symmedian_angle_line`: `0`
- `D1_reflection_x`: `0`
- `D1_reflection_y`: `0`
- `D2_on_BC`: `0`
- `D2_isogonal_angle_line`: `0`
- `P_on_AD2`: `0`
- `KP_perpendicular_AO`: `0`
- `X_on_BC`: `0`
- `KX_perpendicular_BO`: `0`
- `Y_on_BC`: `0`
- `KY_perpendicular_CO`: `0`
- `X1_on_KX`: `0`
- `X1_on_AB`: `0`
- `Y1_on_KY`: `0`
- `Y1_on_AC`: `0`
- `W_on_KP`: `0`
- `W_on_AB`: `0`
- `V_on_KP`: `0`
- `V_on_AC`: `0`
- `KY_equals_KX`: `0`
- `KX1_equals_KX`: `0`
- `KY1_equals_KX`: `0`
- `KW_equals_KX`: `0`
- `KV_equals_KX`: `0`
- `harmonic_power_equivalent_PKXY_cyclic`: `0`
- `XW_angle_bisector_squared`: `0`
- `YV_angle_bisector_squared`: `0`
- `I_on_XW`: `0`
- `I_on_YV`: `0`
- `Pascal_X1Y_parallel_AD`: `0`
- `Pascal_Y1X_parallel_AD`: `0`
- `I_on_altitude_AD`: `0`

- all identities replayed: `True`
- all domain conditions discharged: `True`
- certificate SHA-256: `b01b47e337b024bfededd0db6a031ee6b74c39daead5106c1d3247f7c4a90cde`
