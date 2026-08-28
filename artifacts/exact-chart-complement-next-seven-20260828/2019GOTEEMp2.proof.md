# orthic-transversals-midpoint-right-angle 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; d = foot a b c; e = foot b a c; f = foot c a b; p = on_line d e, on_tline a a b; q = on_line d f, on_tline a a c; t = on_line p q, on_line b c; m = midpoint b c ? perp m a a t
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `M` -> `m`
- `P` -> `p`
- `Q` -> `q`
- `T` -> `t`

## 非退化条件

- `b,u,v are real`
- `b*v != 0`
- `D,E,F are the three altitude feet`
- `P=DE intersect the perpendicular to AB through A`
- `Q=DF intersect the perpendicular to AC through A`
- `T=PQ intersect BC is finite`

## 未消去条件

- なし

## 証明書

- SHA-256: `fba33b43a53bd5352a6ea07609824f0882751533c28612c31578ff15b1eab9a5`
- 再生恒等式: `14`

# 垂足三角形・二直交線・中点直角チャート

## 定理

三角形 $ABC$ の垂足を $D,E,F$ とする。$P=DE\cap (A\text{ を通り }AB\text{ に垂直な直線})$、$Q=DF\cap(A\text{ を通り }AC\text{ に垂直な直線})$、$T=PQ\cap BC$ とし、$M$ を $BC$ の中点とすると、$AM\perp AT$。

## 標準化

A=(0,0), B=(b,0), C=(u,v); all later points are eliminated from their incidence and perpendicularity constraints

## 定義域条件

- `b,u,v are real`
- `b*v != 0`
- `D,E,F are the three altitude feet`
- `P=DE intersect the perpendicular to AB through A`
- `Q=DF intersect the perpendicular to AC through A`
- `T=PQ intersect BC is finite`

## 条件の消去

- `b*v != 0`: The accepted triangle ABC is nondegenerate.
- `u^2+v^2 != 0`: Side AC of the accepted triangle is nonzero.
- `(u-b)^2+v^2 != 0`: Side BC of the accepted triangle is nonzero.
- `u^2-v^2-b*u != 0`: The accepted construction defines finite P.
- `u^2(u-b)+v^2(u+b) != 0`: The accepted construction defines finite Q.
- `u^2+v^2-b^2 != 0`: The accepted construction defines finite T.

## 座標

- `A=(0, 0)`
- `B=(b, 0)`
- `C=(u, v)`
- `D=(b*v**2/(b**2 - 2*b*u + u**2 + v**2), -b*v*(-b + u)/(b**2 - 2*b*u + u**2 + v**2))`
- `E=(b*u**2/(u**2 + v**2), b*u*v/(u**2 + v**2))`
- `F=(u, 0)`
- `P=(0, -b*u*v/(-b*u + u**2 - v**2))`
- `Q=(b*u*v**2/(-b*u**2 + b*v**2 + u**3 + u*v**2), -b*u**2*v/(-b*u**2 + b*v**2 + u**3 + u*v**2))`
- `T=(b*v**2/(-b**2 + u**2 + v**2), -b*v*(b + u)/(-b**2 + u**2 + v**2))`
- `M=((b + u)/2, v/2)`

## 恒等式再生

- `D_on_BC`: `0`
- `AD_perpendicular_BC`: `0`
- `E_on_AC`: `0`
- `BE_perpendicular_AC`: `0`
- `F_on_AB`: `0`
- `CF_perpendicular_AB`: `0`
- `P_on_DE`: `0`
- `AP_perpendicular_AB`: `0`
- `Q_on_DF`: `0`
- `AQ_perpendicular_AC`: `0`
- `T_on_PQ`: `0`
- `T_on_BC`: `0`
- `M_is_midpoint_BC`: `0`
- `goal_AM_perpendicular_AT`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `fba33b43a53bd5352a6ea07609824f0882751533c28612c31578ff15b1eab9a5`
