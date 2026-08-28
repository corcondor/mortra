# incenter-bisector-orthocenters-midpoint-on-bisector 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; e = on_line a c, angle_bisector a b c; f = on_line a b, angle_bisector a c b; i = incenter a b c; d = foot i b c; m = orthocenter a i f; n = orthocenter a i e; p = on_line e m, on_line f n; x = midpoint b c; y = on_line a d, on_tline x i p; m_xy = midpoint x y ? coll m_xy a i
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `I` -> `i`
- `K` -> `m_xy`
- `M` -> `m`
- `N` -> `n`
- `P` -> `p`
- `X` -> `x`
- `Y` -> `y`

## 非退化条件

- `p and q are real`
- `p*q*(p-q)*(1+p*q) != 0`
- `all line intersections, feet, and orthocenters in the source are defined`

## 未消去条件

- なし

## 証明書

- SHA-256: `a862323bab5abc64d5e5efa787a5a550560c5e7372f2389f2259af7336f0f60a`
- 再生恒等式: `29`

# 内心・二等分線・垂心対の中点チャート

## 定理

三角形 $ABC$ の内心を $I$ とし、$E=BI\cap AC$, $F=CI\cap AB$、$D$ を $I$ から $BC$ への垂足とする。$M,N$ を三角形 $AIF,AIE$ の垂心、$P=EM\cap FN$、$X$ を $BC$ の中点とする。$Y\in AD$ かつ $XY\perp IP$ とすると、$XY$ の中点は $AI$ 上にある。

## 標準化

I=(0,0), the incircle has radius 1, BC is x=1, and CA,AB use the rational tangent half-angle parameters p,q.

## 定義域条件

- `p and q are real`
- `p*q*(p-q)*(1+p*q) != 0`
- `all line intersections, feet, and orthocenters in the source are defined`

## 条件の消去

- `p*q*(p-q)*(1+p*q) != 0`: The nondegenerate JGEX triangle with an incenter has three distinct nonparallel side tangents in this unit-incircle chart.
- `E,F,M,N,P,Y are uniquely defined`: Each source construction is an accepted line intersection, orthocenter, foot, or perpendicular-line intersection; its displayed determinant is nonzero.
- `p+q != 0 and the two cevian denominators are nonzero`: These are factors of the accepted P, E, and F constructions and are therefore discharged by the JGEX construction domain.

## 座標

- `I=(0, 0)`
- `A=(-(p*q - 1)/(p*q + 1), (p + q)/(p*q + 1))`
- `B=(1, q)`
- `C=(1, p)`
- `D=(1, 0)`
- `E=(-(p**2 + 1)/(p**2 - 2*p*q - 1), -q*(p**2 + 1)/(p**2 - 2*p*q - 1))`
- `F=((q**2 + 1)/(2*p*q - q**2 + 1), p*(q**2 + 1)/(2*p*q - q**2 + 1))`
- `M=(-(p**2 + 1)*(q - 1)*(q + 1)/((p*q + 1)*(2*p*q - q**2 + 1)), 2*q*(p**2 + 1)/((p*q + 1)*(2*p*q - q**2 + 1)))`
- `N=((p - 1)*(p + 1)*(q**2 + 1)/((p*q + 1)*(p**2 - 2*p*q - 1)), -2*p*(q**2 + 1)/((p*q + 1)*(p**2 - 2*p*q - 1)))`
- `P=(1/(p*q + 1), p*q*(p*q + 3)/((p + q)*(p*q + 1)))`
- `X=(1, (p + q)/2)`
- `Y=(-(p**2*q**2 + 2*p*q - 1)/(p*q + 1), (p + q)*(p*q + 3)/(2*(p*q + 1)))`
- `K=(-(p*q - 1)*(p*q + 2)/(2*(p*q + 1)), (p + q)*(p*q + 2)/(2*(p*q + 1)))`

## 非退化因子

- `triangle_ABC_twice_area`: `2*p*q*(p - q)/(p*q + 1)`
- `E_intersection`: `-q*(p**2 - 2*p*q - 1)/(p*q + 1)`
- `F_intersection`: `p*(2*p*q - q**2 + 1)/(p*q + 1)`
- `P_intersection`: `-(p - q)*(p + q)**2*(p**2 + 1)**2*(q**2 + 1)**2/((p*q + 1)*(p**2 - 2*p*q - 1)**2*(2*p*q - q**2 + 1)**2)`
- `Y_intersection`: `-p*q/(p*q + 1)`

## 恒等式再生

- `CA_tangent_normalized`: `0`
- `AB_tangent_normalized`: `0`
- `A_on_CA`: `0`
- `A_on_AB`: `0`
- `B_on_AB`: `0`
- `B_on_BC`: `0`
- `C_on_BC`: `0`
- `C_on_CA`: `0`
- `E_on_AC`: `0`
- `E_on_BI`: `0`
- `F_on_AB`: `0`
- `F_on_CI`: `0`
- `D_on_BC`: `0`
- `ID_perpendicular_BC`: `0`
- `M_altitude_A`: `0`
- `M_altitude_I`: `0`
- `M_altitude_F`: `0`
- `N_altitude_A`: `0`
- `N_altitude_I`: `0`
- `N_altitude_E`: `0`
- `P_on_EM`: `0`
- `P_on_FN`: `0`
- `X_midpoint_BC_x`: `0`
- `X_midpoint_BC_y`: `0`
- `Y_on_AD`: `0`
- `XY_perpendicular_IP`: `0`
- `K_midpoint_XY_x`: `0`
- `K_midpoint_XY_y`: `0`
- `goal_K_on_AI`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `a862323bab5abc64d5e5efa787a5a550560c5e7372f2389f2259af7336f0f60a`
