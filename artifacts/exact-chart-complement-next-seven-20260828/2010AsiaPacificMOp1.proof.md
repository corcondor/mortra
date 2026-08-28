# circumcenter-secondary-circle-diameter-parallelogram 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; o = circumcenter a b c; o1 = circumcenter o b c; p = on_line a b, on_circle o1 o; q = on_line a c, on_circle o1 o; n = mirror o o1 ? para a p n q
```

## Natural-language domain

```text
Let $ABC$ be a triangle with $\angle BAC \neq 90^{\circ}.$ Let $O$ be the circumcenter of the triangle $ABC$ and $\Gamma$ be the circumcircle of the triangle $BOC.$ Suppose that $\Gamma$ intersects the line segment $AB$ at $P$ different from $B$, and the line segment $AC$ at $Q$ different from $C.$ Let $ON$ be the diameter of the circle $\Gamma.$ Prove that the quadrilateral $APNQ$ is a parallelogram.
```

- typed atoms: distinct(P,B), distinct(Q,C)
- statement SHA-256: `4da655c3c5bd3dd4239bbc17c5eedf6595468c7fd0e7672b9bb8b46599cd22b1`

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `N` -> `n`
- `O` -> `o`
- `O1` -> `o1`
- `P` -> `p`
- `Q` -> `q`

## 非退化条件

- `s,t are real`
- `s,t,0 are pairwise distinct`
- `angle BAC != 90 degrees`
- `P is the intersection of AB with circle BOC distinct from B`
- `Q is the intersection of AC with circle BOC distinct from C`
- `N is the antipode of O on circle BOC`

## 未消去条件

- なし

## 証明書

- SHA-256: `6b2cece6cb1e424e5e296892f7672426bcfc07951518f33a66b97ced2a53922e`
- 再生恒等式: `14`

# 外心・第2交点・直径平行四辺形チャート

## 定理

三角形 $ABC$ の外心を $O$ とし、円 $(BOC)$ が $AB,AC$と $B,C$ 以外で $P,Q$ に交わる。円 $(BOC)$ の $O$ の対蹠点を $N$ とすると、$A+N=P+Q$、したがって四角形$APNQ$ は平行四辺形である。

## 標準化

O=(0,0), B=(1,0), and A,C use rational unit-circle parameters s,t; the circle through B,O,C has center O1=(1/2,t/2)

## 定義域条件

- `s,t are real`
- `s,t,0 are pairwise distinct`
- `angle BAC != 90 degrees`
- `P is the intersection of AB with circle BOC distinct from B`
- `Q is the intersection of AC with circle BOC distinct from C`
- `N is the antipode of O on circle BOC`

## 条件の消去

- `1+s^2 != 0 and 1+t^2 != 0`: Both denominators are positive over R.
- `s,t,0 are pairwise distinct`: The accepted triangle ABC is nondegenerate.
- `C != -B`: The stated condition angle BAC != 90 degrees makes circle BOC nondegenerate.
- `P != B and Q != C`: The natural-language domain explicitly chooses the other two circle-line intersections.

## 座標

- `A=(-(s - 1)*(s + 1)/(s**2 + 1), 2*s/(s**2 + 1))`
- `B=(1, 0)`
- `C=(-(t - 1)*(t + 1)/(t**2 + 1), 2*t/(t**2 + 1))`
- `O=(0, 0)`
- `O1=(1/2, t/2)`
- `P=(-(s*t - 1)/(s**2 + 1), (s + t)/(s**2 + 1))`
- `Q=((s*t + 1)/(s**2 + 1), s*(s*t + 1)/(s**2 + 1))`
- `N=(1, t)`

## 恒等式再生

- `OA_equals_OB`: `0`
- `OB_equals_OC`: `0`
- `O1O_equals_O1B`: `0`
- `O1O_equals_O1C`: `0`
- `P_on_AB`: `0`
- `P_on_gamma`: `0`
- `Q_on_AC`: `0`
- `Q_on_gamma`: `0`
- `N_mirror_O_about_O1_x`: `0`
- `N_mirror_O_about_O1_y`: `0`
- `strong_parallelogram_identity_x`: `0`
- `strong_parallelogram_identity_y`: `0`
- `goal_AP_parallel_NQ`: `0`
- `second_side_PN_parallel_AQ`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `6b2cece6cb1e424e5e296892f7672426bcfc07951518f33a66b97ced2a53922e`
