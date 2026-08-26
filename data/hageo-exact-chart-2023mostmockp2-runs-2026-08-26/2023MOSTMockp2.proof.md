# positive-similarity-six-circumcenters-concurrency 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a1 a3 a5 = triangle a1 a3 a5; a4 = free a4; a6 = free a6; a2 = on_aline a2 a4 a6 a5 a1 a3, on_aline a2 a6 a4 a5 a3 a1; x1 = on_line x1 a1 a3, on_line x1 a2 a6; x2 = on_line x2 a1 a3, on_line x2 a2 a4; x3 = on_line x3 a2 a4, on_line x3 a3 a5; x4 = on_line x4 a3 a5, on_line x4 a4 a6; x5 = on_line x5 a1 a5, on_line x5 a6 a4; x6 = on_line x6 a1 a5, on_line x6 a2 a6; o1 = circumcenter o1 a1 x1 a2; o2 = circumcenter o2 a2 x2 a3; o3 = circumcenter o3 a3 x3 a4; o4 = circumcenter o4 a4 x4 a5; o5 = circumcenter o5 a5 x5 a6; o6 = circumcenter o6 a6 x6 a1; k = on_line k o1 o4, on_line k o2 o5 ? coll k o3 o6
```

## 点の役割対応

- `A1` -> `a1`
- `A2` -> `a2`
- `A3` -> `a3`
- `A4` -> `a4`
- `A5` -> `a5`
- `A6` -> `a6`
- `K` -> `k`
- `O1` -> `o1`
- `O2` -> `o2`
- `O3` -> `o3`
- `O4` -> `o4`
- `O5` -> `o5`
- `O6` -> `o6`
- `X1` -> `x1`
- `X2` -> `x2`
- `X3` -> `x3`
- `X4` -> `x4`
- `X5` -> `x5`
- `X6` -> `x6`

## 非退化条件

- `A1,A3,A5 form a noncollinear triangle`
- `the direct similarity from A1,A3,A5 to A4,A6,A2 has nonzero scale`
- `the six carrier-line intersections Xi are finite and uniquely defined`
- `the six triples Ai,Xi,Ai+1 are noncollinear`
- `O1O4 and O2O5 have a unique finite intersection K`

## 未消去条件

- なし

## 証明書

- SHA-256: `ef03877e3cba7b06dbd890060754633c18db1737e35258c04fa9184d8741dced`
- 再生恒等式: `23`

# Positive-similarity six-circumcenter chart

## Theorem

Let A1A3A5 and A4A6A2 be directly similar.  Put Xi at the intersection of AiAi+2 and Ai+1Ai-1 (indices modulo six), and let Oi be the circumcenter of AiXiAi+1.  Then O1O4, O2O5, and O3O6 are concurrent whenever the constructions are defined.

## Representation change

- A direct similarity is represented by one complex multiplication matrix.
- Lines and intersections are exterior products in homogeneous coordinates.
- A circumcenter is recovered from the signed minors of its circle equation.
- Concurrency is the determinant of the three homogeneous line vectors.

## Replayed identities

- `direct_similarity_A1_to_A4_x`: `0`
- `direct_similarity_A1_to_A4_y`: `0`
- `direct_similarity_A3_to_A6_x`: `0`
- `direct_similarity_A3_to_A6_y`: `0`
- `direct_similarity_A5_to_A2_x`: `0`
- `direct_similarity_A5_to_A2_y`: `0`
- `generic_circle_to_circumcenter_bridge`: `0`
- `circle_minor_annihilates_row_1`: `0`
- `circle_minor_annihilates_row_2`: `0`
- `circle_minor_annihilates_row_3`: `0`
- `X1_on_first_carrier`: `0`
- `X1_on_second_carrier`: `0`
- `X2_on_first_carrier`: `0`
- `X2_on_second_carrier`: `0`
- `X3_on_first_carrier`: `0`
- `X3_on_second_carrier`: `0`
- `X4_on_first_carrier`: `0`
- `X4_on_second_carrier`: `0`
- `X5_on_first_carrier`: `0`
- `X5_on_second_carrier`: `0`
- `X6_on_first_carrier`: `0`
- `X6_on_second_carrier`: `0`
- `three_opposite_circumcenter_lines_concurrent`: `0`

- determinant expression operations: `2676`
- symbolic trace SHA-256: `ebf3d6266e65028cbe5e28d37d795e7622693f53763799d7fc01695660b8ee22`
- all identities replayed: `True`
- all domain conditions discharged: `True`
- certificate SHA-256: `ef03877e3cba7b06dbd890060754633c18db1737e35258c04fa9184d8741dced`
