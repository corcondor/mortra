# equal-angle-cevian-three-radical-axes-return-to-first-cevian-circle 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; p = eqangle3 p b c a c b; p1 = on_line a p, on_line b c; p2 = on_line b p, on_line a c; p3 = on_line c p, on_line a b; o = circumcenter a b c; o2 = circumcenter a p2 p3; x1 = on_circle o a, on_circle o2 a; o3 = circumcenter b p3 p1; x2 = on_circle o b, on_circle o3 b; o4 = circumcenter c p1 p2; x3 = on_circle o c, on_circle o4 c; b1 = on_line a x1, on_line c x3; c1 = on_line a x1, on_line b x2; k = on_line b b1, on_line c c1 ? cyclic k a p2 p3
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `B1` -> `b1`
- `C` -> `c`
- `C1` -> `c1`
- `K` -> `k`
- `O` -> `o`
- `O2` -> `o2`
- `O3` -> `o3`
- `O4` -> `o4`
- `P` -> `p`
- `P1` -> `p1`
- `P2` -> `p2`
- `P3` -> `p3`
- `X1` -> `x1`
- `X2` -> `x2`
- `X3` -> `x3`

## 非退化条件

- `ABC is a nondegenerate triangle and P satisfies the ordered eqangle3 relation`
- `P1=AP intersect BC, P2=BP intersect CA, and P3=CP intersect AB are finite`
- `the parent and three cevian circumcircles are defined`
- `X1,X2,X3 are the official nontrivial common-circle roots`
- `B1=AX1 intersect CX3 and C1=AX1 intersect BX2 are finite`
- `K=BB1 intersect CC1 is finite`

## 未消去条件

- なし

## 証明書

- SHA-256: `00303c2b0605153f0bbdfdcc35a13a81d5c1c48ab25c5f187d116c559cd0efe6`
- 再生恒等式: `28`

# Cevian radical-axes equal-angle chart

## Reusable proof

1. Normalize A=(0,0), B=(1,0), C=(u,v), and write P=(r,s).
2. Construct the three cevian traces by exact line intersection.
3. Subtract each cevian-circle equation from the parent circle.
4. These differences are precisely the three second-intersection carrier lines.
5. Construct B1, C1, and K using only those radical axes.
6. Divide the final circle numerator by the directed-angle numerator.

## Exact replay

- `P1_on_AP`: `0`
- `P1_on_BC`: `0`
- `P2_on_BP`: `0`
- `P2_on_AC`: `0`
- `P3_on_CP`: `0`
- `P3_on_AB`: `0`
- `A_on_parent_circle`: `0`
- `B_on_parent_circle`: `0`
- `C_on_parent_circle`: `0`
- `A_on_cevian_A_circle`: `0`
- `P2_on_cevian_A_circle`: `0`
- `P3_on_cevian_A_circle`: `0`
- `B_on_cevian_B_circle`: `0`
- `P3_on_cevian_B_circle`: `0`
- `P1_on_cevian_B_circle`: `0`
- `C_on_cevian_C_circle`: `0`
- `P1_on_cevian_C_circle`: `0`
- `P2_on_cevian_C_circle`: `0`
- `A_on_axis_A`: `0`
- `B_on_axis_B`: `0`
- `C_on_axis_C`: `0`
- `B1_on_axis_A`: `0`
- `B1_on_axis_C`: `0`
- `C1_on_axis_A`: `0`
- `C1_on_axis_B`: `0`
- `K_on_BB1`: `0`
- `K_on_CC1`: `0`
- `equal_angle_implies_goal_circle_numerator`: `0`

- all identities replayed: `True`
- all conditions discharged: `True`
- certificate SHA-256: `00303c2b0605153f0bbdfdcc35a13a81d5c1c48ab25c5f187d116c559cd0efe6`
