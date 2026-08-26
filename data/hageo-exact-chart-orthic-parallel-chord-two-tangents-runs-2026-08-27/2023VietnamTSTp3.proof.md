# orthic-parallel-chord-two-tangents-collinearity 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle a b c; o = circumcenter o a b c; e = foot e b a c; f = foot f c a b; h = on_line h b e, on_line h c f; m = midpoint m a h; k = foot k h e f; p = on_circle p o a; q = on_circle q o a, on_pline q p b c; o1 = circumcenter o1 c q e; o2 = circumcenter o2 b p f; x = on_tline x e o1 e, on_tline x f o2 f ? coll x m k
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `E` -> `e`
- `F` -> `f`
- `H` -> `h`
- `K` -> `k`
- `M` -> `m`
- `O` -> `o`
- `O1` -> `o1`
- `O2` -> `o2`
- `P` -> `p`
- `Q` -> `q`
- `X` -> `x`

## 非退化条件

- `ABC is a defined nondegenerate triangle with circumcenter O`
- `E,F are the defined feet from B,C and H is their altitude intersection`
- `M is the midpoint of AH and K is the defined foot from H to EF`
- `P,Q are defined points of (ABC) with PQ parallel to BC`
- `O1,O2 are the defined circumcenters of CQE and BPF`
- `X is the defined intersection of the tangents at E and F`

## 未消去条件

- なし

## 証明書

- SHA-256: `fde31ec4d2f576dfb59f1d5543edf9b2e625fbc482ff131b3df27602650d217e`
- 再生恒等式: `23`

# Orthic parallel-chord two-tangent chart

## Theorem

In triangle ABC let E,F be the feet from B,C, H the orthocenter, M the midpoint of AH, and K the projection of H on EF.  A chord PQ of (ABC) is parallel to BC.  The tangent at E to (CQE) and the tangent at F to (BPF) meet at X.  Then X,M,K are collinear.

## Replayed identities

- `E_on_AC`: `0`
- `BE_perpendicular_AC`: `0`
- `F_on_AB`: `0`
- `CF_perpendicular_AB`: `0`
- `H_on_BE`: `0`
- `H_on_CF`: `0`
- `M_midpoint_x`: `0`
- `M_midpoint_y`: `0`
- `K_on_EF`: `0`
- `HK_perpendicular_EF`: `0`
- `A_on_circumcircle`: `0`
- `B_on_circumcircle`: `0`
- `C_on_circumcircle`: `0`
- `P_on_circumcircle`: `0`
- `Q_on_circumcircle`: `0`
- `PQ_parallel_BC`: `0`
- `O1_equidistant_C_Q`: `0`
- `O1_equidistant_C_E`: `0`
- `O2_equidistant_B_P`: `0`
- `O2_equidistant_B_F`: `0`
- `X_on_tangent_at_E`: `0`
- `X_on_tangent_at_F`: `0`
- `X_M_K_collinear`: `0`

- all identities replayed: `True`
- all domain conditions discharged: `True`
- certificate SHA-256: `fde31ec4d2f576dfb59f1d5543edf9b2e625fbc482ff131b3df27602650d217e`
