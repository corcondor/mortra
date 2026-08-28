# arc-midpoint-reflected-bisector-two-circle-cyclicity 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; o = circumcenter a b c; i = incenter a b c; e = on_line a c, angle_bisector c b a; f = on_line a b, angle_bisector b c a; k = on_line a i, on_line e f; t = on_circle o a, on_bline b c; m = midpoint b c; x = on_line a m, on_circle o a; o1 = circumcenter a e f; s = on_circle o1 a, on_circle o a; s1 = reflect s a i; o2 = circumcenter a s1 k; j = on_line a x, on_circle o2 a ? cyclic t j i x
```

## Natural-language domain

```text
Given a triangle $ABC$ with circumcircle $\Gamma$. Points $E$ and $F$ are the foot of angle bisectors of $B$ and $C$, $I$ is incenter and $K$ is the intersection of $AI$ and $EF$. Suppose that $T$ be the midpoint of arc $BAC$. Circle $\Gamma$ intersects the $A$-median and circumcircle of $AEF$ for the second time at $X$ and $S$. Let $S'$ be the reflection of $S$ across $AI$ and $J$ be the second intersection of circumcircle of $AS'K$ and $AX$. Prove that quadrilateral $TJIX$ is cyclic.
```

- typed atoms: arc_midpoint_through(T,B,A,C)
- statement SHA-256: `df3bbe857a77c82bb3963c87bb51d0faf0b95d452c1b34741bd10b2622062a37`

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `E` -> `e`
- `F` -> `f`
- `I` -> `i`
- `J` -> `j`
- `K` -> `k`
- `M` -> `m`
- `O` -> `o`
- `O1` -> `o1`
- `O2` -> `o2`
- `S` -> `s`
- `S1` -> `s1`
- `T` -> `t`
- `X` -> `x`

## 非退化条件

- `ABC is a nondegenerate triangle with circumcenter O and incenter I`
- `E=BI cap AC, F=CI cap AB, and K=AI cap EF are finite`
- `T is the midpoint of the BC arc containing A`
- `X is the non-A point of AM on (ABC)`
- `S is the non-A common point of (AEF) and (ABC)`
- `S' is the reflection of S in AI and (AS'K) is defined`
- `J is the non-A point of AX on (AS'K)`

## 未消去条件

- なし

## 証明書

- SHA-256: `35bb2e4e8a9c3a0ecaf8484c50f5493490f6db14a6c52ff677b32f5b9aeb747c`
- 再生恒等式: `34`

# Arc-midpoint reflected-bisector cyclic chart

## Reusable proof

1. Normalize the parent circumcircle and its incenter rationally.
2. Build E,F,K by exact carrier-line intersections.
3. Use the natural arc atom to select T and the known root A to obtain X.
4. Subtract the equations of (AEF) and (ABC); use A to obtain S.
5. Reflect S in AI and solve the circle (AS'K).
6. Use A again to obtain J; the TJIX circle residual is zero.

## Exact replay

- `A_on_parent_circle`: `0`
- `B_on_parent_circle`: `0`
- `C_on_parent_circle`: `0`
- `I_equidistant_AB_AC`: `0`
- `I_equidistant_AB_BC`: `0`
- `E_on_AC`: `0`
- `B_I_E_collinear`: `0`
- `F_on_AB`: `0`
- `C_I_F_collinear`: `0`
- `K_on_AI`: `0`
- `K_on_EF`: `0`
- `T_on_parent_circle`: `0`
- `T_on_BC_perpendicular_bisector`: `0`
- `M_midpoint_BC_x`: `0`
- `M_midpoint_BC_y`: `0`
- `X_on_AM`: `0`
- `X_on_parent_circle`: `0`
- `A_on_AEF_circle`: `0`
- `E_on_AEF_circle`: `0`
- `F_on_AEF_circle`: `0`
- `A_on_radical_axis`: `0`
- `S_on_parent_circle`: `0`
- `S_on_AEF_circle`: `0`
- `SS1_midpoint_on_AI`: `0`
- `SS1_perpendicular_AI`: `0`
- `A_on_AS1K_circle`: `0`
- `S1_on_AS1K_circle`: `0`
- `K_on_AS1K_circle`: `0`
- `J_on_AX`: `0`
- `J_on_AS1K_circle`: `0`
- `T_on_TJIX_circle`: `0`
- `J_on_TJIX_circle`: `0`
- `I_on_TJIX_circle`: `0`
- `X_on_TJIX_circle`: `0`

- all identities replayed: `True`
- all conditions discharged: `True`
- certificate SHA-256: `35bb2e4e8a9c3a0ecaf8484c50f5493490f6db14a6c52ff677b32f5b9aeb747c`
