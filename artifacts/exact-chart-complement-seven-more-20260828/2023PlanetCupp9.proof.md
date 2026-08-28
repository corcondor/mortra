# euler-line-circle-bisector-equal-distance 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; o = circumcenter a b c; h = orthocenter a b c; e = on_line o h, on_line a c; f = on_line o h, on_line a b; o1 = circumcenter a h o; k = on_circle o1 a, on_circle o a; l = on_line k h, on_circle o a; m = midpoint b c; p = on_line h m, on_bline e f; q = on_line p l, on_line b c ? cong q h q o
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `E` -> `e`
- `F` -> `f`
- `H` -> `h`
- `K` -> `k`
- `L` -> `l`
- `M` -> `m`
- `O` -> `o`
- `O1` -> `o1`
- `P` -> `p`
- `Q` -> `q`

## 非退化条件

- `u*v != 0`
- `DE(u,v)*DF(u,v)*W(u,v) != 0`
- `all named intersections are nondegenerate`

## 未消去条件

- なし

## 証明書

- SHA-256: `ebbbbf7ac7d7a3c2ac7ccf997725140c778f4b3e3f0e3e8cf787b28942302644`
- 再生恒等式: `21`

# Euler線・2円・垂直二等分線チャート

## 定理

三角形 $ABC$ の外心を $O$、垂心を $H$ とし、以下の構成依存関係で $E,F,K,L,M,P,Q$ を定める。このとき $QH=QO$ である。

## 標準化

B=(-1,0), C=(1,0), A=(u,v)

## 非退化条件

- `u*v != 0`
- `DE(u,v)*DF(u,v)*W(u,v) != 0`
- `all named intersections are nondegenerate`

## 条件の消去根拠

- `u*v != 0`: v!=0 is the triangle determinant.  If u=0 then A,H,O are collinear, so the required circumcenter O1 of AHO does not exist.
- `DE(u,v)*DF(u,v) != 0`: DE and DF are the exact line-line determinants for E=OH intersect AC and F=OH intersect AB; successful JGEX intersections exclude zero.
- `W(u,v) != 0`: W is the common denominator of the nontrivial K/L circle branches; the finite second-intersection constructions exclude W=0.
- `all named intersections are nondegenerate`: K is selected after rejecting the shared existing point A, L after rejecting K, and P,Q are defined by nonparallel line intersections.

## 構成点の座標

- `A=(u, v)`
- `B=(-1, 0)`
- `C=(1, 0)`
- `O=(0, (u**2 + v**2 - 1)/(2*v))`
- `H=(u, -(u - 1)*(u + 1)/v)`
- `E=(u*(u + 1)*(u**2 - 2*u + v**2 + 1)/(3*u**3 - 3*u**2 + 3*u*v**2 - 3*u - v**2 + 3), v*(u - 1)*(u**2 - 2*u + v**2 - 3)/(3*u**3 - 3*u**2 + 3*u*v**2 - 3*u - v**2 + 3))`
- `F=(u*(u - 1)*(u**2 + 2*u + v**2 + 1)/(3*u**3 + 3*u**2 + 3*u*v**2 - 3*u + v**2 - 3), v*(u + 1)*(u**2 + 2*u + v**2 - 3)/(3*u**3 + 3*u**2 + 3*u*v**2 - 3*u + v**2 - 3))`
- `O1=(-(3*u**4 - 6*u**2*v**2 - 6*u**2 - v**4 + 2*v**2 + 3)/(8*u*v**2), -(u**2 - v**2 - 1)/(2*v))`
- `K=(-u*(15*u**4 - 2*u**2*v**2 - 30*u**2 - v**4 - 2*v**2 + 15)/(9*u**4 + 10*u**2*v**2 - 18*u**2 + v**4 - 6*v**2 + 9), (u - 1)*(u + 1)*(3*u**2 - 6*u - v**2 + 3)*(3*u**2 + 6*u - v**2 + 3)/(v*(9*u**4 + 10*u**2*v**2 - 18*u**2 + v**4 - 6*v**2 + 9)))`
- `L=(-u*(3*u**4 + 6*u**2*v**2 - 6*u**2 + 3*v**4 - 10*v**2 + 3)/(9*u**4 + 10*u**2*v**2 - 18*u**2 + v**4 - 6*v**2 + 9), v*(u**2 - 2*u + v**2 - 3)*(u**2 + 2*u + v**2 - 3)/(9*u**4 + 10*u**2*v**2 - 18*u**2 + v**4 - 6*v**2 + 9))`
- `M=(0, 0)`
- `P=(-u*v**2*(u**2 - 2*u + v**2 - 3)*(u**2 + 2*u + v**2 - 3)/((3*u**3 - 3*u**2 + 3*u*v**2 - 3*u - v**2 + 3)*(3*u**3 + 3*u**2 + 3*u*v**2 - 3*u + v**2 - 3)), v*(u - 1)*(u + 1)*(u**2 - 2*u + v**2 - 3)*(u**2 + 2*u + v**2 - 3)/((3*u**3 - 3*u**2 + 3*u*v**2 - 3*u - v**2 + 3)*(3*u**3 + 3*u**2 + 3*u*v**2 - 3*u + v**2 - 3)))`
- `Q=((3*u**4 + 2*u**2*v**2 - 6*u**2 - v**4 + 2*v**2 + 3)/(8*u*v**2), 0)`

## 証明

各座標を元の直線・円・中点・垂直二等分線の条件へ代入し、最後に $|Q-H|^2-|Q-O|^2$ を評価する。

- `O_is_circumcenter_AB`: `0`
- `O_is_circumcenter_AC`: `0`
- `H_altitude_from_A`: `0`
- `H_altitude_from_B`: `0`
- `E_on_OH`: `0`
- `E_on_AC`: `0`
- `F_on_OH`: `0`
- `F_on_AB`: `0`
- `O1_contains_A_and_H`: `0`
- `O1_contains_A_and_O`: `0`
- `K_on_circle_O1A`: `0`
- `K_on_circumcircle`: `0`
- `L_on_KH`: `0`
- `L_on_circumcircle`: `0`
- `M_midpoint_BC_x`: `0`
- `M_midpoint_BC_y`: `0`
- `P_on_HM`: `0`
- `P_on_perpendicular_bisector_EF`: `0`
- `Q_on_PL`: `0`
- `Q_on_BC`: `0`
- `goal_QH_equals_QO`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `ebbbbf7ac7d7a3c2ac7ccf997725140c778f4b3e3f0e3e8cf787b28942302644`
