# median-projection-second-circle-intersection-midpoint-equidistant 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; m = midpoint b c; p = foot c a m; q = on_line b c, on_circum a b p; n = midpoint a q ? cong n b n c
```

## Natural-language domain

```text
In an acute triangle $ABC$, let $M$ be the midpoint of $\overline{BC}$. Let $P$ be the foot of the perpendicular from $C$ to $AM$. Suppose that the circumcircle of triangle $ABP$ intersects line $BC$ at two distinct points $B$ and $Q$. Let $N$ be the midpoint of $\overline{AQ}$. Prove that $NB=NC$.
```

- typed atoms: distinct(Q,B), second_intersection(Q,line(B,C),circumcircle(A,B,P))
- statement SHA-256: `5130044a386cca938f379937307bf90757ba7fffb284767efacb8f91245ba502`

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `M` -> `m`
- `N` -> `n`
- `P` -> `p`
- `Q` -> `q`

## 非退化条件

- `u and v are real`
- `v != 0`
- `P is the projection of C on AM`
- `Q is the circle-line intersection distinct from the known root B`

## 未消去条件

- なし

## 証明書

- SHA-256: `fe736acadcdb150cf794f513a9f6f64a8956f3d13917946897a963b13f63f37b`
- 再生恒等式: `9`

# 中線射影・円の第2交点・中点チャート

## 定理

三角形 $ABC$ で $M$ を $BC$ の中点、$P$ を $C$ から$AM$ への垂足とする。円 $(ABP)$ が直線 $BC$ と $B$ 以外で$Q$ に交わり、$N$ が $AQ$ の中点なら、$NB=NC$ である。

## 標準化

B=(-1,0), C=(1,0), M=(0,0), A=(u,v) with v nonzero

## 定義域条件

- `u and v are real`
- `v != 0`
- `P is the projection of C on AM`
- `Q is the circle-line intersection distinct from the known root B`

## 条件の消去

- `v != 0`: The accepted triangle ABC is nondegenerate.
- `u^2+v^2 != 0`: The median line AM has nonzero direction.
- `Q != B`: The natural-language domain explicitly selects the distinct second intersection of line BC with circle ABP.

## 座標

- `A=(u, v)`
- `B=(-1, 0)`
- `C=(1, 0)`
- `M=(0, 0)`
- `P=(u**2/(u**2 + v**2), u*v/(u**2 + v**2))`
- `Q=(-u, 0)`
- `N=(0, v/2)`

## 恒等式再生

- `M_midpoint_BC_x`: `0`
- `M_midpoint_BC_y`: `0`
- `P_on_AM`: `0`
- `CP_perpendicular_AM`: `0`
- `A_B_P_Q_cyclic`: `0`
- `Q_on_BC`: `0`
- `N_midpoint_AQ_x`: `0`
- `N_midpoint_AQ_y`: `0`
- `goal_NB_equals_NC`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `fe736acadcdb150cf794f513a9f6f64a8956f3d13917946897a963b13f63f37b`
