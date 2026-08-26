# three-circumcenters-radical-axis-reflection-isogonal 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle a b c; p = free p; o = circumcenter o a b c; o1 = circumcenter o1 a p b; o2 = circumcenter o2 b p c; o3 = circumcenter o3 c p a; o_g = circumcenter o_g o1 o2 o3; x = on_circle x o a, on_circle x o_g o1; y = on_circle y o a, on_circle y o_g o1; q = reflect q p x y ? eqangle a b a p a q a c
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `O` -> `o`
- `O1` -> `o1`
- `O2` -> `o2`
- `O3` -> `o3`
- `OG` -> `o_g`
- `P` -> `p`
- `Q` -> `q`
- `X` -> `x`
- `Y` -> `y`

## 非退化条件

- `ABC is a defined nondegenerate triangle with circumcenter O`
- `P is a defined point distinct from the required circumcenter triples`
- `O1,O2,O3 are the defined circumcenters of APB,BPC,CPA`
- `OG is the defined circumcenter of O1O2O3`
- `X and Y are the two defined common points of (ABC) and (O1O2O3)`
- `Q is the reflection of P in the defined line XY`

## 未消去条件

- なし

## 証明書

- SHA-256: `cb3a76184864f6f644a48258b1208e052b21e2cc9b183215b7d181f80ae8cd37`
- 再生恒等式: `18`

# Three-circumcenter radical-reflection chart

## Theorem

Let O1,O2,O3 be the circumcenters of APB, BPC, CPA.  The circle through O1,O2,O3 meets (ABC) in X,Y.  If Q is the reflection of P in XY, then AP and AQ are isogonal in angle BAC.

## Representation changes

- three circumcenters -> six linear equal-distance equations
- their circumcircle -> one Hermitian circle equation
- the common chord XY -> subtraction of the two circle equations
- reflection in XY -> one rational complex expression
- isogonality at A -> reality of one cross-ratio product

## Replayed identities

- `A_on_normalized_circumcircle`: `0`
- `B_on_normalized_circumcircle`: `0`
- `C_on_normalized_circumcircle`: `0`
- `O1_equidistant_A_P`: `0`
- `O1_equidistant_A_B`: `0`
- `O2_equidistant_B_P`: `0`
- `O2_equidistant_B_C`: `0`
- `O3_equidistant_C_P`: `0`
- `O3_equidistant_C_A`: `0`
- `O1_on_three_center_circle`: `0`
- `O2_on_three_center_circle`: `0`
- `O3_on_three_center_circle`: `0`
- `three_center_circle_has_conjugate_coefficients`: `0`
- `three_center_circle_has_real_constant`: `0`
- `circle_subtraction_is_radical_axis`: `0`
- `reflection_midpoint_lies_on_radical_axis`: `0`
- `reflection_segment_is_normal_to_axis`: `0`
- `isogonal_cross_ratio_is_real`: `0`

- all identities replayed: `True`
- all domain conditions discharged: `True`
- certificate SHA-256: `cb3a76184864f6f644a48258b1208e052b21e2cc9b183215b7d181f80ae8cd37`
