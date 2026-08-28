# incenter-excenter-radical-axis-isogonal-trace 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; i = incenter a b c; ia = excenter a b c; ib = excenter b c a; ic = excenter c a b; o = circumcenter a b c; d = on_circle o a; o1 = circumcenter d i ia; o2 = circumcenter d ib ic; f = on_circle o1 d, on_circle o2 d; e = on_line d f, on_line b c ? eqangle b a a d e a a c
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `I` -> `i`
- `Ia` -> `ia`
- `Ib` -> `ib`
- `Ic` -> `ic`
- `O` -> `o`
- `O1` -> `o1`
- `O2` -> `o2`

## 非退化条件

- `d != f`
- `b*c*r*(c*s-b*t)*(c*s+b*t) != 0`

## 未消去条件

- なし

## 証明書

- SHA-256: `83a5a49da1df738b6e84a15ad092a50a8d3ff9e4ea141889ac0f6a37fa97706b`
- 再生恒等式: `10`

# 重心座標による円・根軸チャート

## 定理

三角形 $ABC$ の外接円上の点を $D=(r:s:t)$ とする。内心を $I$、傍心を $I_a,I_b,I_c$ とすると、円 $(DII_a)$ と $(DI_bI_c)$ の根軸が辺 $BC$ と交わる点は、直線 $AD$ の等角共役線上にある。

## 仮定

- `a*b*c*r != 0`
- `c*s-b*t != 0`
- `c*s+b*t != 0`
- `a^2*s*t+b^2*t*r+c^2*r*s = 0`

## 条件の消去根拠

- `a*b*c*r != 0`: The triangle has nonzero side lengths.  D is a new circumcircle point distinct from B and C; since BC meets the circumcircle only at B,C, D is not on BC and r!=0.
- `c*s-b*t != 0`: This factor is the determinant for the required circumcenter of D,I,Ia; the successful construction excludes zero.
- `c*s+b*t != 0`: This factor is the determinant for the required circumcenter of D,Ib,Ic; the successful construction excludes zero.
- `a^2*s*t+b^2*t*r+c^2*r*s = 0`: This is exactly the barycentric circumcircle equation and follows from the on_circle(O,A) construction of D.
- `D != F and E is finite`: The two circles already share D, so reduce_intersection returns the other point F; the final line intersection rejects D=F and parallel DF,BC.

## 証明過程

### 1. 一般の円

`-a^2*y*z-b^2*z*x-c^2*x*y+(x+y+z)(u*x+v*y+w*z)=0`

### 2. 2円の方程式

- $(DII_a)$: `(a**2*b*t*y*z - a**2*c*s*y*z + b**3*t*x*z + b**2*c*r*x*z + b**2*c*r*y*z + b**2*c*r*z**2 - b**2*c*s*x*z - b**2*c*t*x**2 - b**2*c*t*x*y - b**2*c*t*x*z - b*c**2*r*x*y - b*c**2*r*y**2 - b*c**2*r*y*z + b*c**2*s*x**2 + b*c**2*s*x*y + b*c**2*s*x*z + b*c**2*t*x*y - c**3*s*x*y)/(-b*t + c*s) = 0`
- $(DI_bI_c)$: `-(a**2*b*t*y*z + a**2*c*s*y*z + b**3*t*x*z - b**2*c*r*x*z - b**2*c*r*y*z - b**2*c*r*z**2 + b**2*c*s*x*z + b**2*c*t*x**2 + b**2*c*t*x*y + b**2*c*t*x*z - b*c**2*r*x*y - b*c**2*r*y**2 - b*c**2*r*y*z + b*c**2*s*x**2 + b*c**2*s*x*y + b*c**2*s*x*z + b*c**2*t*x*y + c**3*s*x*y)/(b*t + c*s) = 0`

### 3. 根軸

2式を引くと `2*b*c*(b**2*r*t*z - b**2*t**2*x - c**2*r*s*y + c**2*s**2*x)/((-b*t + c*s)*(b*t + c*s)) = 0` を得る。

### 4. 辺 $BC$ との交点

`E=(0:b^2*t:c^2*s)`

### 5. 等角共役の確認

`b^2*t*z_E-c^2*s*y_E=0`

## 恒等式の再生結果

- `circle1_contains_D_mod_circumcircle`: `0`
- `circle1_contains_I`: `0`
- `circle1_contains_Ia`: `0`
- `circle2_contains_D_mod_circumcircle`: `0`
- `circle2_contains_Ib`: `0`
- `circle2_contains_Ic`: `0`
- `radical_axis_subtraction`: `0`
- `trace_lies_on_radical_axis`: `0`
- `trace_lies_on_BC`: `0`
- `isogonal_trace_identity`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `83a5a49da1df738b6e84a15ad092a50a8d3ff9e4ea141889ac0f6a37fa97706b`
