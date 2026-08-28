# contact-polar-reflection-two-secants-side-return 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; o = circumcenter a b c; i = incenter a b c; d = foot i b c; e = foot i a c; f = foot i a b; h = reflect d e f; m = on_line o i, on_circle o a; t = on_line i o, on_line b c; q = on_line a t, on_circle o a; o1 = circumcenter q m h; y = on_line m a, on_circle o1 q; y1 = reflect y e f ? coll y1 b c
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `H` -> `h`
- `I` -> `i`
- `M` -> `m`
- `O` -> `o`
- `O1` -> `o1`
- `Q` -> `q`
- `T` -> `t`
- `Y` -> `y`
- `Y1` -> `y1`

## 非退化条件

- `ABC is a nondegenerate triangle with circumcenter O and incenter I`
- `D,E,F are the perpendicular contact feet on BC,CA,AB`
- `H is the reflection of D in the defined line EF`
- `T=OI cap BC is finite and Q is the non-A point of AT on (ABC)`
- `M is any defined point of (ABC) for which the circle QMH exists`
- `Y is the non-M point of AM on (QMH), and Y1 is its reflection in EF`

## 未消去条件

- なし

## 証明書

- SHA-256: `c0b41fb469db3c61f089c93fd35012a125e9ed535ff2cd4aba2a9d3cbec8e2df`
- 再生恒等式: `37`

# Contact-polar reflection and secant chart

## Theorem

Let H be the reflection of the BC contact point D in the contact chord EF.  Put T=OI cap BC and let Q be the second intersection of AT with the circumcircle.  For any M on the circumcircle, the circle QMH meets AM again at Y, whose reflection in EF lies on BC.

## Reusable proof

1. Normalize the circumcircle and write the incenter/contact feet rationally.
2. Reflect D in the contact polar EF to obtain H.
3. Use the known root A to eliminate Q from line AT and the unit circle.
4. Solve the circle through Q,M,H by three linear coefficient equations.
5. Use the known root M to eliminate the second intersection Y on AM.
6. Reflect Y in EF; the resulting BC-collinearity determinant is identically zero.

## Exact replay

- `A_on_unit_circumcircle`: `0`
- `B_on_unit_circumcircle`: `0`
- `C_on_unit_circumcircle`: `0`
- `I_equidistant_from_AB_AC`: `0`
- `I_equidistant_from_AB_BC`: `0`
- `D_on_BC`: `0`
- `ID_perpendicular_BC`: `0`
- `E_on_CA`: `0`
- `IE_perpendicular_CA`: `0`
- `F_on_AB`: `0`
- `IF_perpendicular_AB`: `0`
- `DH_midpoint_on_EF`: `0`
- `DH_perpendicular_EF`: `0`
- `T_on_OI`: `0`
- `T_on_BC`: `0`
- `A_is_known_AT_circle_root`: `0`
- `Q_on_AT`: `0`
- `Q_on_unit_circumcircle`: `0`
- `M_on_unit_circumcircle`: `0`
- `Q_on_QMH_circle`: `0`
- `M_on_QMH_circle`: `0`
- `H_on_QMH_circle`: `0`
- `O1_equidistant_Q_M`: `0`
- `O1_equidistant_Q_H`: `0`
- `M_is_known_MA_circle_root`: `0`
- `Y_on_MA`: `0`
- `Y_on_QMH_circle`: `0`
- `YY1_midpoint_on_EF`: `0`
- `YY1_perpendicular_EF`: `0`
- `Y1_on_BC`: `0`
- `exceptional_M_on_unit_circumcircle`: `0`
- `exceptional_Q_on_QMH_circle`: `0`
- `exceptional_M_on_QMH_circle`: `0`
- `exceptional_H_on_QMH_circle`: `0`
- `exceptional_Y_on_MA`: `0`
- `exceptional_Y_on_QMH_circle`: `0`
- `exceptional_Y1_on_BC`: `0`

- all identities replayed: `True`
- all conditions discharged: `True`
- certificate SHA-256: `c0b41fb469db3c61f089c93fd35012a125e9ed535ff2cd4aba2a9d3cbec8e2df`
