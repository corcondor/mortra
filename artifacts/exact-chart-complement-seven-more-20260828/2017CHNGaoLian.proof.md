# isosceles-two-circle-intersection-perpendicular 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = iso_triangle; i = incenter a b c; o3 = on_bline b i; p = on_circle a b, on_circle o3 b; q = on_circle i b, on_circle o3 b; r = on_line p i, on_line b q ? perp b r c r
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `I` -> `i`
- `O3` -> `o3`
- `P` -> `p`
- `Q` -> `q`
- `R` -> `r`

## 非退化条件

- `0 < t < 1`
- `v is real`
- `P and Q are the B-distinct circle intersections`
- `R is the defined intersection of PI and BQ`

## 未消去条件

- なし

## 証明書

- SHA-256: `84d4c57f803946e9ba3977abb27bce11d7521d9df10230a6fec97ada1396a4a3`
- 再生恒等式: `19`

# 等腰三角形・2円交点・直交チャート

## 定理

二等辺三角形 $ABC$ の内心を $I$ とする。点 $O_3$ は $BI$ の垂直二等分線上にあり、$P$ は中心 $A,O_3$ の2円の $B$ でない交点、$Q$ は中心 $I,O_3$ の2円の $B$ でない交点とする。$R=PI\cap BQ$ とおけば、$BR\perp CR$ である。

## 標準化

B=(-1,0), C=(1,0), I=(0,t), A=(0,2t/(1-t^2)), O3=((t^2-1-2tv)/2,v)

## 構成の定義域

- `0 < t < 1`
- `v is real`
- `P and Q are the B-distinct circle intersections`
- `R is the defined intersection of PI and BQ`

## 条件の消去

- `0 < t < 1`: t is the normalized inradius.  A genuine isosceles triangle has positive inradius smaller than the half-base.
- `A != O3`: If A=O3, the perpendicular-bisector condition gives AB=AI; the replayed identity AI^2=t^2 AB^2 contradicts 0<t<1.
- `P != B, hence t != v`: JGEX reduce_intersection rejects every intersection already present; P is therefore the second circle intersection.  The replayed lambda_P factorization then gives t!=v.
- `Q != B, hence t != 2v`: The same official second-intersection rule applies to Q; the lambda_Q factorization gives t!=2v.
- `det(PI,BQ) != 0`: D_P is a positive squared center distance up to positive factors, and det*D_P=2(t-2v)(t^2+1)^3.

## 座標

- `A=(0, -2*t/((t - 1)*(t + 1)))`
- `B=(-1, 0)`
- `C=(1, 0)`
- `I=(0, t)`
- `O3=((t**2 - 2*t*v - 1)/2, v)`
- `P=(-(t**2 + 1)*(t**2 - 2*t*v - 2*t + 2*v - 1)*(t**2 - 2*t*v + 2*t - 2*v - 1)/(t**6 - 4*t**5*v + 4*t**4*v**2 - 5*t**4 + 16*t**3*v - 8*t**2*v**2 + 11*t**2 - 12*t*v + 4*v**2 + 1), -4*(t - 1)*(t + 1)*(t - v)*(t**2 - 2*t*v - 1)/(t**6 - 4*t**5*v + 4*t**4*v**2 - 5*t**4 + 16*t**3*v - 8*t**2*v**2 + 11*t**2 - 12*t*v + 4*v**2 + 1))`
- `Q=((3*t**2 - 8*t*v + 4*v**2 - 1)/(t**2 - 4*t*v + 4*v**2 + 1), 2*(t - 2*v)*(t**2 - 2*t*v - 1)/(t**2 - 4*t*v + 4*v**2 + 1))`
- `R=(-(t**2 - 2*t*v - 2*t + 2*v - 1)*(t**2 - 2*t*v + 2*t - 2*v - 1)/((t**2 + 1)*(t**2 - 4*t*v + 4*v**2 + 1)), 4*(t - v)*(t**2 - 2*t*v - 1)/((t**2 + 1)*(t**2 - 4*t*v + 4*v**2 + 1)))`

## 恒等式再生

- `isosceles_AB_equals_AC`: `0`
- `I_equal_distance_from_AB`: `0`
- `I_equal_distance_from_AC`: `0`
- `AI_squared_equals_t_squared_AB_squared`: `0`
- `O3_on_perpendicular_bisector_BI`: `0`
- `P_on_circle_center_A`: `0`
- `P_on_circle_center_O3`: `0`
- `Q_on_circle_center_I`: `0`
- `Q_on_circle_center_O3`: `0`
- `R_on_PI`: `0`
- `R_on_BQ`: `0`
- `bridge_BQ_perpendicular_IO3`: `0`
- `bridge_CR_parallel_IO3`: `0`
- `goal_BR_perpendicular_CR`: `0`
- `delta_P_factorization`: `0`
- `delta_Q_factorization`: `0`
- `lambda_P_factorization`: `0`
- `lambda_Q_factorization`: `0`
- `line_determinant_factorization`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `84d4c57f803946e9ba3977abb27bce11d7521d9df10230a6fec97ada1396a4a3`
