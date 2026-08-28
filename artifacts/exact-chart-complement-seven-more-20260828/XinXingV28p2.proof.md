# incircle-antipodes-three-circle-axis 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; o = circumcenter a b c; i = incenter a b c; j1 = on_line a i, on_circle o a; j = mirror j1 o; k1 = on_line b i, on_circle o a; k = mirror k1 o; l1 = on_line c i, on_circle o a; l = mirror l1 o; d = foot i b c; e = foot i a c; f = foot i a b; x = on_line j d, on_circle o a; y = on_line k e, on_circle o a; z = on_line l f, on_circle o a; o1 = circumcenter x e f; o2 = circumcenter y f d; o3 = circumcenter z d e; u = on_circle o1 f, on_circle o2 f; v = on_circle o1 e, on_circle o3 e; t = on_line u f, on_line v e ? coll t o i
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
- `J1` -> `j1`
- `K` -> `k`
- `K1` -> `k1`
- `L` -> `l`
- `L1` -> `l1`
- `O` -> `o`
- `O1` -> `o1`
- `O2` -> `o2`
- `O3` -> `o3`
- `T` -> `t`
- `U` -> `u`
- `V` -> `v`
- `X` -> `x`
- `Y` -> `y`
- `Z` -> `z`

## 非退化条件

- `the tangent-coordinate triangle is finite and nondegenerate`
- `all named second-intersection branches are nondegenerate`
- `the three circumcenters and the two defining lines exist`

## 未消去条件

- なし

## 証明書

- SHA-256: `8bbc973426cfc5061671c60d2fd704e9364085b18e211f3279a57151a6d24fea`
- 再生恒等式: `32`

# 内接円・反対点・3円根軸チャート

## 定理

三角形の内心を通る3本の直線から外接円上の点を取り、その反対点と内接円の3接点を用いて3円を構成する。指定された2本の共通弦の交点は内心と外心を結ぶ直線上にある。

## 標準化

I=(0,0), incircle: x^2+y^2=1, BC:y=-1; AB and AC are unit-circle tangents with parameters p and q

## 非退化条件

- `the tangent-coordinate triangle is finite and nondegenerate`
- `all named second-intersection branches are nondegenerate`
- `the three circumcenters and the two defining lines exist`

## 条件の消去根拠

- `the tangent-coordinate triangle is finite and nondegenerate`: The input triangle, circumcenter, and incenter exist; this excludes coincident or parallel side tangents in the normalized unit-incircle chart.
- `all named second-intersection branches are nondegenerate`: J1/K1/L1 share A/B/C with the circumcircle, X/Y/Z share J/K/L, and U/V share F/E.  reduce_intersection rejects each known branch.
- `the three circumcenters and the two defining lines exist`: Successful circumcenter clauses exclude collinear triples; the final line intersection excludes coincident points and parallel lines.

## 構成点の座標

- `A=((-p*q + 1)/(p*q + 1), (p + q)/(p*q + 1))`
- `B=((-p - 1)/(p - 1), -1)`
- `C=((-q - 1)/(q - 1), -1)`
- `I=(0, 0)`
- `O=((-p*q + 1)/(p*q - p - q + 1), (-p**2*q**2 + 2*p**2*q - p**2 + 2*p*q**2 + 2*p - q**2 + 2*q - 1)/(2*p**2*q**2 - 2*p**2*q - 2*p*q**2 + 4*p*q - 2*p - 2*q + 2))`
- `D=(0, -1)`
- `E=((-q**2 + 1)/(q**2 + 1), 2*q/(q**2 + 1))`
- `F=((-p**2 + 1)/(p**2 + 1), 2*p/(p**2 + 1))`
- `J1=((-p*q + 1)/(p*q - p - q + 1), (p + q)/(p*q - p - q + 1))`
- `J=((-p*q + 1)/(p*q - p - q + 1), (-p**2*q**2 + p**2*q - p**2 + p*q**2 + p - q**2 + q - 1)/(p**2*q**2 - p**2*q - p*q**2 + 2*p*q - p - q + 1))`
- `K1=((-p*q**2 - p - q**2 - 1)/(2*p*q**2 - 2*p*q + 2*q - 2), (-p*q**2 - p + q**2 + 1)/(2*p*q**2 - 2*p*q + 2*q - 2))`
- `K=((-3*p**2*q**2 + p**2 - q**2 + 3)/(2*p**2*q**2 - 2*p**2*q - 2*p*q**2 + 4*p*q - 2*p - 2*q + 2), (-p**2*q**2 + 4*p**2*q - p**2 + 2*p*q**2 + 2*p - q**2 + 4*q - 1)/(2*p**2*q**2 - 2*p**2*q - 2*p*q**2 + 4*p*q - 2*p - 2*q + 2))`
- `L1=((-p**2*q - p**2 - q - 1)/(2*p**2*q - 2*p*q + 2*p - 2), (-p**2*q + p**2 - q + 1)/(2*p**2*q - 2*p*q + 2*p - 2))`
- `L=((-3*p**2*q**2 - p**2 + q**2 + 3)/(2*p**2*q**2 - 2*p**2*q - 2*p*q**2 + 4*p*q - 2*p - 2*q + 2), (-p**2*q**2 + 2*p**2*q - p**2 + 4*p*q**2 + 4*p - q**2 + 2*q - 1)/(2*p**2*q**2 - 2*p**2*q - 2*p*q**2 + 4*p*q - 2*p - 2*q + 2))`
- `X=((-p**4*q**4 - p**4*q**3 - p**3*q**4 - 2*p**3*q**3 - p**3*q**2 - p**2*q**3 + p**2*q + p*q**2 + 2*p*q + p + q + 1)/(p**4*q**4 + p**4 - 4*p**3*q + 4*p**2*q**2 - 4*p*q**3 + q**4 + 1), (-p**4*q**4 - p**4*q**2 - p**4*q - p**4 + 2*p**3*q**3 + p**3*q**2 + 2*p**3*q - p**3 - p**2*q**4 + p**2*q**3 + p**2*q - p**2 - p*q**4 + 2*p*q**3 + p*q**2 + 2*p*q - q**4 - q**3 - q**2 - 1)/(p**4*q**4 + p**4 - 4*p**3*q + 4*p**2*q**2 - 4*p*q**3 + q**4 + 1))`
- `Y=((-p**4*q**4 - 3*p**4*q**3 - 3*p**4*q**2 + p**4*q + 2*p**4 + p**3*q**4 + 6*p**3*q**3 + 2*p**3*q**2 - 2*p**3*q + p**3 - 5*p**2*q**4 - 4*p**2*q**3 + 4*p**2*q + 5*p**2 - p*q**4 + 2*p*q**3 - 2*p*q**2 - 6*p*q - p - 2*q**4 - q**3 + 3*q**2 + 3*q + 1)/(p**4*q**4 + 2*p**4*q**3 + 2*p**4*q**2 - 2*p**4*q + p**4 - 4*p**3*q**3 + 8*p**3*q**2 + 4*p**3*q + 6*p**2*q**4 - 4*p**2*q**2 + 6*p**2 + 4*p*q**3 + 8*p*q**2 - 4*p*q + q**4 - 2*q**3 + 2*q**2 + 2*q + 1), (p**4*q**3 + 3*p**4*q**2 + 5*p**4*q - p**4 + p**3*q**4 + 4*p**3*q**3 - 4*p**3*q**2 + 4*p**3*q + 3*p**3 - 3*p**2*q**4 + 2*p**2*q**3 + 2*p**2*q**2 + 2*p**2*q - 3*p**2 + 3*p*q**4 + 4*p*q**3 - 4*p*q**2 + 4*p*q + p - q**4 + 5*q**3 + 3*q**2 + q)/(p**4*q**4 + 2*p**4*q**3 + 2*p**4*q**2 - 2*p**4*q + p**4 - 4*p**3*q**3 + 8*p**3*q**2 + 4*p**3*q + 6*p**2*q**4 - 4*p**2*q**2 + 6*p**2 + 4*p*q**3 + 8*p*q**2 - 4*p*q + q**4 - 2*q**3 + 2*q**2 + 2*q + 1))`
- `Z=((-p**4*q**4 + p**4*q**3 - 5*p**4*q**2 - p**4*q - 2*p**4 - 3*p**3*q**4 + 6*p**3*q**3 - 4*p**3*q**2 + 2*p**3*q - p**3 - 3*p**2*q**4 + 2*p**2*q**3 - 2*p**2*q + 3*p**2 + p*q**4 - 2*p*q**3 + 4*p*q**2 - 6*p*q + 3*p + 2*q**4 + q**3 + 5*q**2 - q + 1)/(p**4*q**4 + 6*p**4*q**2 + p**4 + 2*p**3*q**4 - 4*p**3*q**3 + 4*p**3*q - 2*p**3 + 2*p**2*q**4 + 8*p**2*q**3 - 4*p**2*q**2 + 8*p**2*q + 2*p**2 - 2*p*q**4 + 4*p*q**3 - 4*p*q + 2*p + q**4 + 6*q**2 + 1), (p**4*q**3 - 3*p**4*q**2 + 3*p**4*q - p**4 + p**3*q**4 + 4*p**3*q**3 + 2*p**3*q**2 + 4*p**3*q + 5*p**3 + 3*p**2*q**4 - 4*p**2*q**3 + 2*p**2*q**2 - 4*p**2*q + 3*p**2 + 5*p*q**4 + 4*p*q**3 + 2*p*q**2 + 4*p*q + p - q**4 + 3*q**3 - 3*q**2 + q)/(p**4*q**4 + 6*p**4*q**2 + p**4 + 2*p**3*q**4 - 4*p**3*q**3 + 4*p**3*q - 2*p**3 + 2*p**2*q**4 + 8*p**2*q**3 - 4*p**2*q**2 + 8*p**2*q + 2*p**2 - 2*p*q**4 + 4*p*q**3 - 4*p*q + 2*p + q**4 + 6*q**2 + 1))`
- `O1=((p**4*q**4 + p**4*q**3 + 2*p**4*q**2 + p**3*q**4 - 2*p**3*q**3 + p**3*q**2 + 2*p**2*q**4 + p**2*q**3 - p**2*q - 2*p**2 - p*q**2 + 2*p*q - p - 2*q**2 - q - 1)/(2*p**4*q + 2*p**4 - 2*p**3*q**2 - 8*p**3*q + 2*p**3 - 2*p**2*q**3 + 12*p**2*q**2 - 2*p**2*q + 2*p*q**4 - 8*p*q**3 - 2*p*q**2 + 2*q**4 + 2*q**3), (-p**4*q**3 - p**4*q**2 - 2*p**4*q - p**3*q**4 - 2*p**3*q**3 - p**3*q**2 - 2*p**3*q - 2*p**3 - p**2*q**4 - p**2*q**3 - 4*p**2*q**2 - p**2*q - p**2 - 2*p*q**4 - 2*p*q**3 - p*q**2 - 2*p*q - p - 2*q**3 - q**2 - q)/(2*p**4*q + 2*p**4 - 2*p**3*q**2 - 8*p**3*q + 2*p**3 - 2*p**2*q**3 + 12*p**2*q**2 - 2*p**2*q + 2*p*q**4 - 8*p*q**3 - 2*p*q**2 + 2*q**4 + 2*q**3))`
- `O2=((p**3*q**2 + p**3*q + 2*p**3 - 3*p**2*q - p**2 + p*q**2 + 3*p*q - 2*q**2 - q - 1)/(2*p**3*q + 2*p**3 + 2*p**2*q**2 - 2*p**2*q + 4*p**2 + 4*p*q**2 - 2*p*q + 2*p + 2*q**2 + 2*q), (p**4*q**2 + p**4*q + 2*p**4 - p**3*q**2 - 4*p**3*q - 3*p**3 + p**2*q**2 + 6*p**2*q + p**2 - 3*p*q**2 - 4*p*q - p + 2*q**2 + q + 1)/(2*p**4*q + 2*p**4 + 2*p**3*q**2 + 6*p**3 + 6*p**2*q**2 - 4*p**2*q + 6*p**2 + 6*p*q**2 + 2*p + 2*q**2 + 2*q))`
- `O3=((p**2*q**3 + p**2*q - 2*p**2 + p*q**3 - 3*p*q**2 + 3*p*q - p + 2*q**3 - q**2 - 1)/(2*p**2*q**2 + 4*p**2*q + 2*p**2 + 2*p*q**3 - 2*p*q**2 - 2*p*q + 2*p + 2*q**3 + 4*q**2 + 2*q), (p**2*q**4 - p**2*q**3 + p**2*q**2 - 3*p**2*q + 2*p**2 + p*q**4 - 4*p*q**3 + 6*p*q**2 - 4*p*q + p + 2*q**4 - 3*q**3 + q**2 - q + 1)/(2*p**2*q**3 + 6*p**2*q**2 + 6*p**2*q + 2*p**2 + 2*p*q**4 - 4*p*q**2 + 2*p + 2*q**4 + 6*q**3 + 6*q**2 + 2*q))`
- `U=((2*p**6*q**2 + 4*p**6*q - 8*p**5*q**2 + 4*p**5*q + 4*p**5 - 2*p**4*q**4 + 12*p**4*q**3 + 2*p**4*q**2 + 2*p**4 - 8*p**3*q**4 - 4*p**3*q**3 + 4*p**3*q + 8*p**3 - 2*p**2*q**4 - 2*p**2*q**2 - 12*p**2*q + 2*p**2 - 4*p*q**4 - 4*p*q**3 + 8*p*q**2 - 4*q**3 - 2*q**2)/(p**6*q**3 - p**6*q**2 + 2*p**6 + p**5*q**4 + 9*p**5*q**2 - 10*p**5*q + 5*p**4*q**4 - 8*p**4*q**3 + 17*p**4*q**2 + 15*p**4*q + p**4 + 7*p**3*q**4 + 2*p**3*q**3 - 18*p**3*q**2 + 2*p**3*q + 7*p**3 + p**2*q**4 + 15*p**2*q**3 + 17*p**2*q**2 - 8*p**2*q + 5*p**2 - 10*p*q**3 + 9*p*q**2 + p + 2*q**4 - q**2 + q), (p**6*q**4 + 3*p**6*q**2 - 2*p**6*q - 2*p**6 + 2*p**5*q**4 + 2*p**5*q**3 + 4*p**5*q**2 + 14*p**5*q - 2*p**5 + 6*p**4*q**3 - 11*p**4*q**2 + 4*p**4*q + p**4 + 8*p**3*q**3 + 8*p**3*q**2 + 8*p**3*q + p**2*q**4 + 4*p**2*q**3 - 11*p**2*q**2 + 6*p**2*q - 2*p*q**4 + 14*p*q**3 + 4*p*q**2 + 2*p*q + 2*p - 2*q**4 - 2*q**3 + 3*q**2 + 1)/(p**6*q**3 - p**6*q**2 + 2*p**6 + p**5*q**4 + 9*p**5*q**2 - 10*p**5*q + 5*p**4*q**4 - 8*p**4*q**3 + 17*p**4*q**2 + 15*p**4*q + p**4 + 7*p**3*q**4 + 2*p**3*q**3 - 18*p**3*q**2 + 2*p**3*q + 7*p**3 + p**2*q**4 + 15*p**2*q**3 + 17*p**2*q**2 - 8*p**2*q + 5*p**2 - 10*p*q**3 + 9*p*q**2 + p + 2*q**4 - q**2 + q))`
- `V=((-2*p**4*q**4 - 8*p**4*q**3 - 2*p**4*q**2 - 4*p**4*q + 12*p**3*q**4 - 4*p**3*q**3 - 4*p**3*q - 4*p**3 + 2*p**2*q**6 - 8*p**2*q**5 + 2*p**2*q**4 - 2*p**2*q**2 + 8*p**2*q - 2*p**2 + 4*p*q**6 + 4*p*q**5 + 4*p*q**3 - 12*p*q**2 + 4*q**5 + 2*q**4 + 8*q**3 + 2*q**2)/(p**4*q**5 + 5*p**4*q**4 + 7*p**4*q**3 + p**4*q**2 + 2*p**4 + p**3*q**6 - 8*p**3*q**4 + 2*p**3*q**3 + 15*p**3*q**2 - 10*p**3*q - p**2*q**6 + 9*p**2*q**5 + 17*p**2*q**4 - 18*p**2*q**3 + 17*p**2*q**2 + 9*p**2*q - p**2 - 10*p*q**5 + 15*p*q**4 + 2*p*q**3 - 8*p*q**2 + p + 2*q**6 + q**4 + 7*q**3 + 5*q**2 + q), (p**4*q**6 + 2*p**4*q**5 + p**4*q**2 - 2*p**4*q - 2*p**4 + 2*p**3*q**5 + 6*p**3*q**4 + 8*p**3*q**3 + 4*p**3*q**2 + 14*p**3*q - 2*p**3 + 3*p**2*q**6 + 4*p**2*q**5 - 11*p**2*q**4 + 8*p**2*q**3 - 11*p**2*q**2 + 4*p**2*q + 3*p**2 - 2*p*q**6 + 14*p*q**5 + 4*p*q**4 + 8*p*q**3 + 6*p*q**2 + 2*p*q - 2*q**6 - 2*q**5 + q**4 + 2*q + 1)/(p**4*q**5 + 5*p**4*q**4 + 7*p**4*q**3 + p**4*q**2 + 2*p**4 + p**3*q**6 - 8*p**3*q**4 + 2*p**3*q**3 + 15*p**3*q**2 - 10*p**3*q - p**2*q**6 + 9*p**2*q**5 + 17*p**2*q**4 - 18*p**2*q**3 + 17*p**2*q**2 + 9*p**2*q - p**2 - 10*p*q**5 + 15*p*q**4 + 2*p*q**3 - 8*p*q**2 + p + 2*q**6 + q**4 + 7*q**3 + 5*q**2 + q))`
- `T=((-2*p**2*q**2 + 2)/(2*p**2*q**2 - p**2*q + p**2 - p*q**2 + 2*p*q - p + q**2 - q + 2), (-p**2*q**2 + 2*p**2*q - p**2 + 2*p*q**2 + 2*p - q**2 + 2*q - 1)/(2*p**2*q**2 - p**2*q + p**2 - p*q**2 + 2*p*q - p + q**2 - q + 2))`

## 証明過程

直線と円の第2交点、外心、2円の第2交点、直線交点を順に$\mathbf{Q}(p,q)$ 上で計算する。各構成条件を再代入し、最後に$\det(T-I,O-I)$ を既約化する。

- `A_on_first_tangent`: `0`
- `B_on_first_tangent`: `0`
- `A_on_second_tangent`: `0`
- `C_on_second_tangent`: `0`
- `J1_on_AI`: `0`
- `J1_on_circumcircle`: `0`
- `J_is_antipode`: `0`
- `K1_on_BI`: `0`
- `K1_on_circumcircle`: `0`
- `K_is_antipode`: `0`
- `L1_on_CI`: `0`
- `L1_on_circumcircle`: `0`
- `L_is_antipode`: `0`
- `X_on_JD`: `0`
- `X_on_circumcircle`: `0`
- `Y_on_KE`: `0`
- `Y_on_circumcircle`: `0`
- `Z_on_LF`: `0`
- `Z_on_circumcircle`: `0`
- `O1_center_XEF_1`: `0`
- `O1_center_XEF_2`: `0`
- `O2_center_YFD_1`: `0`
- `O2_center_YFD_2`: `0`
- `O3_center_ZDE_1`: `0`
- `O3_center_ZDE_2`: `0`
- `U_on_circle_XEF`: `0`
- `U_on_circle_YFD`: `0`
- `V_on_circle_XEF`: `0`
- `V_on_circle_ZDE`: `0`
- `T_on_UF`: `0`
- `T_on_VE`: `0`
- `goal_I_O_T_collinear`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `8bbc973426cfc5061671c60d2fd704e9364085b18e211f3279a57151a6d24fea`
