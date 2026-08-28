# cyclic-cevian-reflection-second-roots-parallel 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; o = circumcenter a b c; p = on_circle o a; d = on_line a p, on_line b c; m = midpoint b c; t = mirror d m; o1 = circumcenter p d t; g = on_line a t, on_circle o1 p; o2 = circumcenter a g p; e = on_line a b, on_circle o2 a; f = on_line a c, on_circle o2 a; q = on_line e f, on_line g p ? para a q b c
```

## Natural-language domain

```text
Let $ABC$ be a triangle and $P$ be a point on its circumcircle. Lines $AP$ and $BC$ intersect at $D$ and point $T$ is the reflection of $D$ over the midpoint of $\overline{BC}$. Let $AT$ meet the circumcircle of $\triangle PDT$ again at $G$. The circumcircle of $\triangle AGP$ meets $AB$ and $AC$ again at $E$ and $F$ respectively. Lines $EF$ and $GP$ intersect at $Q$. Prove that $AQ \parallel BC$.
```

- typed atoms: distinct(G,T), distinct(E,A), distinct(F,A)
- statement SHA-256: `ccd58e7ae8aee452fc5f40e6552d051b9d0a7c283e7bc9b502a445c1d6668f3c`

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `G` -> `g`
- `M` -> `m`
- `O` -> `o`
- `O1` -> `o1`
- `O2` -> `o2`
- `P` -> `p`
- `Q` -> `q`
- `T` -> `t`

## 非退化条件

- `u,v,r are real`
- `v != 0`
- `P is the non-A intersection of AD with circle ABC`
- `T is the reflection of D about the midpoint of BC`
- `G is the intersection of AT and circle PDT distinct from T`
- `E,F are the intersections of AB,AC and circle AGP distinct from A`
- `Q=EF intersect GP is finite`

## 未消去条件

- なし

## 証明書

- SHA-256: `b0dbc1e21ac1c92f64f727b3df7d0fec4cb63ed431fb4d8084bbbeadc89e058d`
- 再生恒等式: `22`

# 円内接セバ線・中点反射・第2交点平行チャート

## 定理

$P$ を $ABC$ の外接円上、$D=AP\cap BC$ とし、$T$ を $BC$ の中点に関する $D$ の反射とする。$G$ を $AT$ と円 $(PDT)$ の第2交点、$E,F$ を円 $(AGP)$ と $AB,AC$ の第2交点、$Q=EF\cap GP$ とすると、$AQ\parallel BC$。

## 標準化

A=(0,0), B=(1,0), C=(u,v), D=B+r(C-B); all three second intersections are eliminated through known-root products

## 定義域条件

- `u,v,r are real`
- `v != 0`
- `P is the non-A intersection of AD with circle ABC`
- `T is the reflection of D about the midpoint of BC`
- `G is the intersection of AT and circle PDT distinct from T`
- `E,F are the intersections of AB,AC and circle AGP distinct from A`
- `Q=EF intersect GP is finite`

## 条件の消去

- `v != 0`: The accepted triangle ABC is nondegenerate.
- `u^2+v^2 != 0`: Side AC is nonzero.
- `|D|^2 != 0`: The accepted intersection D is distinct from A.
- `|T|^2 != 0`: The accepted line AT is defined.
- `u^2+v^2-1 != 0`: The accepted finite intersection Q exists.
- `G != T; E != A; F != A`: The natural statement explicitly selects the second intersections.

## 座標

- `A=(0, 0)`
- `B=(1, 0)`
- `C=(u, v)`
- `D=(r*u - r + 1, r*v)`
- `M=((u + 1)/2, v/2)`
- `T=(-r*u + r + u, -v*(r - 1))`
- `P=((r*u - r + 1)*(r*u**2 + r*v**2 - r + 1)/(r**2*u**2 - 2*r**2*u + r**2*v**2 + r**2 + 2*r*u - 2*r + 1), r*v*(r*u**2 + r*v**2 - r + 1)/(r**2*u**2 - 2*r**2*u + r**2*v**2 + r**2 + 2*r*u - 2*r + 1))`
- `G=(-(r*u - r - u)*(r*u**2 + r*v**2 - r + 1)/(r**2*u**2 - 2*r**2*u + r**2*v**2 + r**2 - 2*r*u**2 + 2*r*u - 2*r*v**2 + u**2 + v**2), -v*(r - 1)*(r*u**2 + r*v**2 - r + 1)/(r**2*u**2 - 2*r**2*u + r**2*v**2 + r**2 - 2*r*u**2 + 2*r*u - 2*r*v**2 + u**2 + v**2))`
- `E=(r*u**2 + r*v**2 - r + 1, 0)`
- `F=(u*(r*u**2 + r*v**2 - r + 1)/(u**2 + v**2), v*(r*u**2 + r*v**2 - r + 1)/(u**2 + v**2))`
- `Q=((u - 1)*(r*u**2 + r*v**2 - r + 1)/(u**2 + v**2 - 1), v*(r*u**2 + r*v**2 - r + 1)/(u**2 + v**2 - 1))`

## 恒等式再生

- `A_on_circle_ABC`: `0`
- `B_on_circle_ABC`: `0`
- `C_on_circle_ABC`: `0`
- `P_on_circle_ABC`: `0`
- `D_on_AP`: `0`
- `D_on_BC`: `0`
- `M_is_midpoint_BC`: `0`
- `T_is_reflection_of_D_about_M`: `0`
- `G_on_AT`: `0`
- `directed_power_AP_AD`: `0`
- `directed_power_AG_AT`: `0`
- `PDTG_concyclic_by_power_converse`: `0`
- `A_on_circle_AGP`: `0`
- `G_on_circle_AGP`: `0`
- `P_on_circle_AGP`: `0`
- `E_on_circle_AGP`: `0`
- `F_on_circle_AGP`: `0`
- `E_on_AB`: `0`
- `F_on_AC`: `0`
- `Q_on_EF`: `0`
- `Q_on_GP`: `0`
- `goal_AQ_parallel_BC`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `b0dbc1e21ac1c92f64f727b3df7d0fec4cb63ed431fb4d8084bbbeadc89e058d`
