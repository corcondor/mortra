# mixtilinear-two-circumcircles-tangent 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle a b c; i = incenter i a b c; o = circumcenter o a b c; d = foot d i b c; e = on_line e a b, on_tline e i a i; f = on_line f a c, on_tline f i a i; o1 = circumcenter o1 a e f; g = on_circle g o1 a, on_circle g o a; h = on_circle h o1 a, on_line h a i; j = on_tline j g o g, on_line j b c; k = on_line k a j, on_circle k o a; o3 = circumcenter o3 d j k; o4 = circumcenter o4 g i h; t = on_circle t o4 i, on_circle t o3 d ? coll o3 o4 t
```

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `D` -> `d`
- `E` -> `e`
- `F` -> `f`
- `G` -> `g`
- `H` -> `h`
- `I` -> `i`
- `J` -> `j`
- `K` -> `k`
- `O` -> `o`
- `O1` -> `o1`
- `O3` -> `o3`
- `O4` -> `o4`
- `T` -> `t`

## 非退化条件

- `the tangent-coordinate triangle is finite and nondegenerate`
- `all named intersections and circumcenters are nondegenerate`
- `the two final circles have a real common point T as specified`

## 未消去条件

- なし

## 証明書

- SHA-256: `090954c9f2f62dc674311abf3a36988a37d6e742db2d6853b21b9a281755d14b`
- 再生恒等式: `19`

# 混線内接円型構成と2円接触チャート

## 定理

内心・外心・接線から所定の点を構成すると、三角形 $DJK$ と$GIH$ の外接円は接する。したがって両円の共通点と2中心は一直線上にある。

## 標準化

I=(0,0), incircle:x^2+y^2=1, BC:y=-1; AB and AC are unit-circle tangents with parameters p and q

## 非退化条件

- `the tangent-coordinate triangle is finite and nondegenerate`
- `all named intersections and circumcenters are nondegenerate`
- `the two final circles have a real common point T as specified`

## 条件の消去根拠

- `the tangent-coordinate triangle is finite and nondegenerate`: The JGEX triangle and its incenter exist.  In the unit-incircle chart this excludes coincident/parallel side tangents and every base-chart denominator.
- `all named intersections and circumcenters are nondegenerate`: Every denominator in the rational construction is the determinant of the corresponding line intersection, circumcenter, or second-intersection operator; successful JGEX construction excludes its vanishing.
- `the two final circles have a real common point T as specified`: The input constructs T on both real circles.  Their exact tangency discriminant is zero, while Newclid rejects coincident centers, so T is their unique contact point.

## 構成点の座標

- `A=((-p*q + 1)/(p*q + 1), (p + q)/(p*q + 1))`
- `B=((-p - 1)/(p - 1), -1)`
- `C=((-q - 1)/(q - 1), -1)`
- `I=(0, 0)`
- `O=((-p*q + 1)/(p*q - p - q + 1), (-p**2*q**2 + 2*p**2*q - p**2 + 2*p*q**2 + 2*p - q**2 + 2*q - 1)/(2*p**2*q**2 - 2*p**2*q - 2*p*q**2 + 4*p*q - 2*p - 2*q + 2))`
- `D=(0, -1)`
- `E=((-p - q)/(p - q), (-p*q + 1)/(p - q))`
- `F=((p + q)/(p - q), (p*q - 1)/(p - q))`
- `O1=((p**3*q**3 - p**3*q + 3*p**2*q**2 + p**2 - p*q**3 - 3*p*q + q**2 - 1)/(2*p**3*q - 4*p**2*q**2 + 2*p**2 + 2*p*q**3 - 4*p*q + 2*q**2), (-p**3*q**2 + p**3 - p**2*q**3 - 3*p**2*q - 3*p*q**2 - p + q**3 - q)/(2*p**3*q - 4*p**2*q**2 + 2*p**2 + 2*p*q**3 - 4*p*q + 2*q**2))`
- `G=((-p**4*q**4 + p**4*q**3 - p**4*q + p**3*q**4 - 2*p**3*q**3 + 2*p**3*q**2 + p**3 + 2*p**2*q**3 - 2*p**2*q - p*q**4 - 2*p*q**2 + 2*p*q - p + q**3 - q + 1)/(p**4*q**4 - 2*p**4*q**3 + 2*p**4*q**2 - 2*p**3*q**4 + 4*p**3*q**3 - 6*p**3*q**2 + 2*p**2*q**4 - 6*p**2*q**3 + 14*p**2*q**2 - 6*p**2*q + 2*p**2 - 6*p*q**2 + 4*p*q - 2*p + 2*q**2 - 2*q + 1), (-p**4*q**4 + 2*p**4*q**3 - 3*p**4*q**2 + p**4*q + 2*p**3*q**4 - 2*p**3*q**3 + 5*p**3*q**2 - 2*p**3*q + p**3 - 3*p**2*q**4 + 5*p**2*q**3 - 10*p**2*q**2 + 5*p**2*q - 3*p**2 + p*q**4 - 2*p*q**3 + 5*p*q**2 - 2*p*q + 2*p + q**3 - 3*q**2 + 2*q - 1)/(p**4*q**4 - 2*p**4*q**3 + 2*p**4*q**2 - 2*p**3*q**4 + 4*p**3*q**3 - 6*p**3*q**2 + 2*p**2*q**4 - 6*p**2*q**3 + 14*p**2*q**2 - 6*p**2*q + 2*p**2 - 6*p*q**2 + 4*p*q - 2*p + 2*q**2 - 2*q + 1))`
- `H=((p**2*q**2 - 1)/(p**2 - 2*p*q + q**2), (-p**2*q - p*q**2 - p - q)/(p**2 - 2*p*q + q**2))`
- `J=((-p**3*q**3 - p**3*q**2 + p**3*q - p**3 - p**2*q**3 + 3*p**2*q**2 - p**2*q + p**2 + p*q**3 - p*q**2 + 3*p*q - p - q**3 + q**2 - q - 1)/(2*p**3*q**3 - 2*p**3*q**2 + 2*p**3*q - 2*p**2*q**3 - 2*p**2*q**2 - 2*p**2 + 2*p*q**3 + 2*p*q + 2*p - 2*q**2 + 2*q - 2), -1)`
- `K=((-3*p**4*q**4 + p**4*q**2 - 2*p**4*q + 4*p**3*q**3 + 2*p**3*q**2 + 2*p**3 + p**2*q**4 + 2*p**2*q**3 - 2*p**2*q - p**2 - 2*p*q**4 - 2*p*q**2 - 4*p*q + 2*q**3 - q**2 + 3)/(5*p**4*q**4 - 6*p**4*q**3 + 5*p**4*q**2 - 6*p**3*q**4 - 2*p**3*q**3 - 2*p**3*q**2 - 6*p**3*q + 5*p**2*q**4 - 2*p**2*q**3 + 18*p**2*q**2 - 2*p**2*q + 5*p**2 - 6*p*q**3 - 2*p*q**2 - 2*p*q - 6*p + 5*q**2 - 6*q + 5), (-4*p**4*q**4 + 5*p**4*q**3 - 6*p**4*q**2 + p**4*q + 5*p**3*q**4 + 4*p**3*q**3 + 2*p**3*q**2 + 4*p**3*q + p**3 - 6*p**2*q**4 + 2*p**2*q**3 - 16*p**2*q**2 + 2*p**2*q - 6*p**2 + p*q**4 + 4*p*q**3 + 2*p*q**2 + 4*p*q + 5*p + q**3 - 6*q**2 + 5*q - 4)/(5*p**4*q**4 - 6*p**4*q**3 + 5*p**4*q**2 - 6*p**3*q**4 - 2*p**3*q**3 - 2*p**3*q**2 - 6*p**3*q + 5*p**2*q**4 - 2*p**2*q**3 + 18*p**2*q**2 - 2*p**2*q + 5*p**2 - 6*p*q**3 - 2*p*q**2 - 2*p*q - 6*p + 5*q**2 - 6*q + 5))`
- `O3=((-p**3*q**3 - p**3*q**2 + p**3*q - p**3 - p**2*q**3 + 3*p**2*q**2 - p**2*q + p**2 + p*q**3 - p*q**2 + 3*p*q - p - q**3 + q**2 - q - 1)/(4*p**3*q**3 - 4*p**3*q**2 + 4*p**3*q - 4*p**2*q**3 - 4*p**2*q**2 - 4*p**2 + 4*p*q**3 + 4*p*q + 4*p - 4*q**2 + 4*q - 4), (-3*p**2*q**2 + 2*p**2*q - 3*p**2 + 2*p*q**2 + 2*p - 3*q**2 + 2*q - 3)/(4*p**2*q**2 - 4*p**2*q + 4*p**2 - 4*p*q**2 - 4*p + 4*q**2 - 4*q + 4))`
- `O4=((p**3*q**3 - p**3*q**2 + p**3*q - p**3 - p**2*q**3 + p**2*q**2 - p**2*q + p**2 + p*q**3 - p*q**2 + p*q - p - q**3 + q**2 - q + 1)/(2*p**3*q - 4*p**2*q**2 - 2*p**2 + 2*p*q**3 + 4*p*q - 2*q**2), (-p**2*q**2 - p**2 - q**2 - 1)/(2*p**2 - 4*p*q + 2*q**2))`

## 証明過程

すべての構成を $\mathbf{Q}(p,q)$ 上で再生し、2円の半径平方$R_3^2,R_4^2$ と中心間距離平方 $d^2$ に対する接触判別式$(d^2-R_3^2-R_4^2)^2-4R_3^2R_4^2$ を既約化する。

- `E_on_AB`: `0`
- `E_on_perpendicular_through_I`: `0`
- `F_on_AC`: `0`
- `F_on_perpendicular_through_I`: `0`
- `O1_center_AEF_1`: `0`
- `O1_center_AEF_2`: `0`
- `G_on_circle_AEF`: `0`
- `G_on_circumcircle`: `0`
- `H_on_AI`: `0`
- `H_on_circle_AEF`: `0`
- `J_on_BC`: `0`
- `JG_tangent_to_circumcircle`: `0`
- `K_on_AJ`: `0`
- `K_on_circumcircle`: `0`
- `O3_center_DJK_1`: `0`
- `O3_center_DJK_2`: `0`
- `O4_center_GIH_1`: `0`
- `O4_center_GIH_2`: `0`
- `two_circle_tangency_discriminant`: `0`

- 全恒等式再生: `True`
- 未消去条件なし: `True`
- 証明書 SHA-256: `090954c9f2f62dc674311abf3a36988a37d6e742db2d6853b21b9a281755d14b`
