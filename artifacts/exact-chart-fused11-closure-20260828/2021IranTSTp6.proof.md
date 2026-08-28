# euler-line-equal-angle-two-circle-radical-axis-is-altitude 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; o = circumcenter a b c; h = orthocenter a b c; d = on_line o h; e = on_line b d, on_line a c; f = on_line c d, on_line a b; x = on_line a d, eqangle3 x e f a b c; o1 = circumcenter c x f; o2 = circumcenter b x e; p = on_circle o1 c, on_circle o2 b; q = on_line x p, on_line e f ? coll q a h
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `H` -> `h`
- `O` -> `o`
- `O1` -> `o1`
- `O2` -> `o2`
- `P` -> `p`
- `Q` -> `q`
- `X` -> `x`

## 非退化条件

- `ABC is a nondegenerate triangle with circumcenter O and orthocenter H`
- `D lies on the Euler line OH`
- `E=BD intersect AC and F=CD intersect AB are defined`
- `X lies on AD and angle(EXF)=angle(BAC) modulo pi`
- `P is the second common point of (CXF) and (BXE)`
- `Q=XP intersect EF is defined`

## 未消去条件

- なし

## 証明書

- SHA-256: `2eeab57e459bf781f37371e0ef040a7c69171de8de5528b75dd6b9e8ee4e108f`
- 再生恒等式: `20`

# Euler-line equal-angle radical-altitude chart

## Reusable proof

1. Normalize A=(0,0), B=(1,0), C=(u,v).
2. Parameterize D on the Euler line and X on AD.
3. Construct E and F by exact line intersections.
4. Subtract the equations of (CXF) and (BXE) to obtain XP.
5. Intersect that radical axis with EF to obtain Q.
6. The altitude residual is a polynomial multiple of the angle residual.

## Exact replay

- `O_equidistant_A_B`: `0`
- `O_equidistant_A_C`: `0`
- `AH_perpendicular_BC`: `0`
- `CH_perpendicular_AB`: `0`
- `D_on_OH`: `0`
- `E_on_BD`: `0`
- `E_on_AC`: `0`
- `F_on_CD`: `0`
- `F_on_AB`: `0`
- `X_on_AD`: `0`
- `C_on_first_circle`: `0`
- `X_on_first_circle`: `0`
- `F_on_first_circle`: `0`
- `B_on_second_circle`: `0`
- `X_on_second_circle`: `0`
- `E_on_second_circle`: `0`
- `X_on_radical_axis`: `0`
- `Q_on_EF`: `0`
- `Q_on_radical_axis`: `0`
- `equal_angle_implies_altitude_numerator`: `0`

- all identities replayed: `True`
- all conditions discharged: `True`
- certificate SHA-256: `2eeab57e459bf781f37371e0ef040a7c69171de8de5528b75dd6b9e8ee4e108f`
