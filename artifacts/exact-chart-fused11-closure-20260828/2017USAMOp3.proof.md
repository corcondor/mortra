# incenter-nine-point-power-chain-midpoint-on-circumcircle 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; o = circumcenter a b c; i = incenter a b c; d = on_line a i, on_line b c; m = on_line a i, on_circle o a; k = on_dia m d, on_circle o a; s = on_line m k, on_line b c; n = midpoint i s; o1 = circumcenter k i d; o2 = circumcenter m a n; l = on_circle o1 k, on_circle o2 m; p = midpoint i l ? cyclic a b c p
```

## Natural-language domain

```text
Let $ABC$ be a scalene triangle with circumcircle $\Omega$ and incenter $I$. Ray $AI$ meets $\overline{BC}$ at $D$ and meets $\Omega$ again at $M$; the circle with diameter $\overline{DM}$ cuts $\Omega$ again at $K$. Lines $MK$ and $BC$ meet at $S$, and $N$ is the midpoint of $\overline{IS}$. The circumcircles of $\triangle KID$ and $\triangle MAN$ intersect at points $L_1$ and $L_2$. Prove that $\Omega$ passes through the midpoint of either $\overline{IL_1}$ or $\overline{IL_2}$.
```

- typed atoms: circle_intersection_pair(L1,L2,circumcircle(K,I,D),circumcircle(M,A,N)), exists_midpoint_on_circumcircle(I,L1,L2,A,B,C)
- statement SHA-256: `432dba7f07b42bb761951d6c62d1648077223bce5c50673b4ffc227c046ca6b4`

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `I` -> `i`
- `K` -> `k`
- `L_star` -> `exists_intersection(o1,o2)`
- `M` -> `m`
- `N` -> `n`
- `Omega_center` -> `o`
- `S` -> `s`
- `T_star` -> `midpoint(i,L_star)`
- `circle_KID_center` -> `o1`
- `circle_MAN_center` -> `o2`
- `raw_intersection_branch` -> `l`
- `raw_midpoint_branch` -> `p`

## 非退化条件

- `the source constructions are finite and nondegenerate`
- `the natural statement quantifies over both circle intersections`

## 未消去条件

- なし

## 証明書

- SHA-256: `122db1143ca7a9f7b9702e8f5168c4222186f2c23c2f081146801538d3236f03`
- 再生恒等式: `49`

# Incenter / nine-point / power-chain midpoint chart

## Reusable proof

1. Let X be antipodal to M and let I_A be the A-excenter.
2. The construction makes S the orthocenter of triangle DMX.
3. A radical-center identity makes I the orthocenter of triangle XSI_A.
4. Its altitude foot L lies on the nine-point circle MAN.
5. XD*XK=XW*XM=XA*XS=XI*XL, so K,D,I,L are concyclic.
6. For T=midpoint(I,L), TM is parallel to LI_A and TX is perpendicular to LI_A.
7. Thus angle MTX is right; since XM is a diameter, T lies on the original circle.

## Exact replay

- `A_on_Omega`: `0`
- `B_on_Omega`: `0`
- `C_on_Omega`: `0`
- `M_on_Omega`: `0`
- `X_on_Omega`: `0`
- `XM_is_diameter_x`: `0`
- `XM_is_diameter_y`: `0`
- `I_on_AM`: `0`
- `D_on_AI`: `0`
- `D_on_BC`: `0`
- `K_on_DX`: `0`
- `K_on_Omega`: `0`
- `K_on_diameter_DM_circle`: `0`
- `S_on_MK`: `0`
- `S_on_BC`: `0`
- `N_midpoint_IS_x`: `0`
- `N_midpoint_IS_y`: `0`
- `IA_reflection_of_I_in_M_x`: `0`
- `IA_reflection_of_I_in_M_y`: `0`
- `MI_equals_MB_squared`: `0`
- `MI_equals_MC_squared`: `0`
- `MI_equals_MIA_squared`: `0`
- `S_orthocenter_DMX_DS_perp_MX`: `0`
- `S_orthocenter_DMX_MS_perp_DX`: `0`
- `S_orthocenter_DMX_XS_perp_DM`: `0`
- `I_orthocenter_XSIA_XI_perp_SIA`: `0`
- `I_orthocenter_XSIA_SI_perp_XIA`: `0`
- `I_orthocenter_XSIA_IAI_perp_XS`: `0`
- `L_on_SIA`: `0`
- `XL_perp_SIA`: `0`
- `X_I_L_collinear`: `0`
- `M_midpoint_I_IA_x`: `0`
- `M_midpoint_I_IA_y`: `0`
- `A_is_altitude_foot_from_IA_on_XS`: `0`
- `A_on_XS`: `0`
- `power_X_DK_equals_X_WM`: `0`
- `power_X_WM_equals_X_AS`: `0`
- `power_X_AS_equals_X_IL`: `0`
- `L_on_circle_KID`: `0`
- `T_midpoint_IL_x`: `0`
- `T_midpoint_IL_y`: `0`
- `TM_parallel_LIA`: `0`
- `TX_perpendicular_LIA`: `0`
- `goal_T_on_Omega`: `0`
- `kernel_I_is_orthocenter`: `0`
- `kernel_L_is_altitude_foot`: `0`
- `kernel_MANL_is_nine_point_circle`: `0`
- `kernel_TM_parallel_LJ`: `0`
- `kernel_TX_perpendicular_TM`: `0`

- all identities replayed: `True`
- all conditions discharged: `True`
- certificate SHA-256: `122db1143ca7a9f7b9702e8f5168c4222186f2c23c2f081146801538d3236f03`
