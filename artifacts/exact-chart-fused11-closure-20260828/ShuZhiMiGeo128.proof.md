# miquel-cevian-three-target-circles-coaxial 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; p = free; d = on_line a p, on_line b c; e = on_line b p, on_line a c; f = on_line c p, on_line a b; o1 = circumcenter a e f; o2 = circumcenter b d f; q = on_circle o1 a, on_circle o2 b; r = on_line p q; j = on_line a r, on_circle o1 a; k = on_line b r, on_circle o2 b; o3 = circumcenter c d e; l = on_line c r, on_circle o3 c; oa = circumcenter a j d; ob = circumcenter b k e; t = on_circle oa a, on_circle ob b ? cyclic t c l f
```

## Natural-language domain

```text
For point $P$ in $\triangle ABC$ with Cevian triangle $DEF$ and Miquel point $Q$ of $DEF$, take $R\in PQ$ with $AR\cap\odot(AEF)=J$, $BR\cap\odot(BFD)=K$, $CR\cap\odot(CDE)=L$. Prove $\odot(AJD)$, $\odot(BKE)$, $\odot(CLF)$ are coaxial.
```

- typed atoms: miquel_point(Q,D,E,F)
- statement SHA-256: `501eda8c6d0c9e4821b802feae4d238385413b277e8767069a55b3abcdcf3adc`

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `J` -> `j`
- `K` -> `k`
- `L` -> `l`
- `O1` -> `o1`
- `O2` -> `o2`
- `O3` -> `o3`
- `OA` -> `oa`
- `OB` -> `ob`
- `P` -> `p`
- `Q` -> `q`
- `R` -> `r`
- `T` -> `t`

## 非退化条件

- `ABC is nondegenerate and P has a defined cevian triangle DEF`
- `Q is the non-F Miquel point of DEF`
- `R is any point on PQ`
- `J,K,L are the nontrivial second intersections on AR,BR,CR`
- `the three target circles are defined`

## 未消去条件

- なし

## 証明書

- SHA-256: `bbae333ed91ab522160f1d5cb890bd5b29ea603cb16b0fa337cb2c5a41ca1beb`
- 再生恒等式: `31`

# Miquel--cevian coaxial chart

## Reusable proof

1. Normalize A=(0,0), B=(1,0), C=(u,v), P=(p,q).
2. Construct the cevian triangle and its three base circles.
3. Eliminate the known common root F to obtain the Miquel point Q.
4. For R on PQ, represent each target circle as a base circle plus its common-chord line.
5. Cross-normalize the three equations; their radical axes are proportional.
6. Hence every common point of (AJD) and (BKE) lies on (CLF).

## Exact replay

- `D_on_AP`: `0`
- `D_on_BC`: `0`
- `E_on_BP`: `0`
- `E_on_AC`: `0`
- `F_on_CP`: `0`
- `F_on_AB`: `0`
- `A_on_AEF`: `0`
- `E_on_AEF`: `0`
- `F_on_AEF`: `0`
- `B_on_BDF`: `0`
- `D_on_BDF`: `0`
- `F_on_BDF`: `0`
- `C_on_CDE`: `0`
- `D_on_CDE`: `0`
- `E_on_CDE`: `0`
- `Q_on_AEF`: `0`
- `Q_on_BDF`: `0`
- `Q_on_CDE_Miquel_closure`: `0`
- `R_on_PQ`: `0`
- `A_on_AJD`: `0`
- `D_on_AJD`: `0`
- `B_on_BKE`: `0`
- `E_on_BKE`: `0`
- `C_on_CLF`: `0`
- `F_on_CLF`: `0`
- `AJD_BKE_CLF_coaxial_1`: `0`
- `AJD_BKE_CLF_coaxial_2`: `0`
- `AJD_BKE_CLF_coaxial_3`: `0`
- `exceptional_R_equals_Q_coaxial_1`: `0`
- `exceptional_R_equals_Q_coaxial_2`: `0`
- `exceptional_R_equals_Q_coaxial_3`: `0`

- all identities replayed: `True`
- all conditions discharged: `True`
- certificate SHA-256: `bbae333ed91ab522160f1d5cb890bd5b29ea603cb16b0fa337cb2c5a41ca1beb`
