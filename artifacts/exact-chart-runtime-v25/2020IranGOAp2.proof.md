# major-arc-homothety-right-circle-tangent 適用証明

## 判定

- 構成依存関係と目標を照合した。
- 座標チャート上の全恒等式を厳密再生した。
- 判定: `proved`（構成の定義域条件まで消去済み）。
- 問題確認後に実装したチャートなので、凍結未見得点には遡及加算しない。

## 入力問題

```text
a b c = triangle; i = incenter a b c; o = circumcenter a b c; n = on_bline b c, on_circle o a; m = midpoint b c; p = mirror a m; q = mirror a n; r = foot a q i; o1 = circumcenter p q r; t = foot o1 a i ? cong o1 p o1 t
```

## Natural-language domain

```text
Let triangle ABC be an acute-angled triangle with incenter I. Suppose that N is the midpoint of the arc BAC of the circumcircle of triangle ABC, and P is chosen so that ABPC is a parallelogram. Let Q be the reflection of A over N and R the projection of A onto QI. Show that AI is tangent to the circumcircle of triangle PQR.
```

- typed atoms: acute(A,B,C), arc_midpoint_through(N,B,A,C)
- statement SHA-256: `cf15b6b8fa714e0eb7fdd2db3c35e52a94f38c3c7a486cbf08927e6edecabbf4`

## 点の役割対応

- `A` -> `a`
- `B` -> `b`
- `C` -> `c`
- `I` -> `i`
- `M` -> `m`
- `N` -> `n`
- `O` -> `o`
- `O1` -> `o1`
- `P` -> `p`
- `Q` -> `q`
- `R` -> `r`
- `T` -> `t`

## 非退化条件

- `ABC is acute`
- `N is the midpoint of the B-to-C circumcircle arc through A`
- `all reflected and projected points are finite and nondegenerate`

## 未消去条件

- なし

## 証明書

- SHA-256: `14fce866da10724217a145f52c199e0e50c860400d1559d0d5321f6c71a24045`
- 再生恒等式: `42`

# Major-arc homothety / tangent-circle chart

## Theorem

For the typed construction in the chart, the incenter axis is tangent to the circumcircle of the reflected parallelogram/projection triangle.

## Reusable proof

1. The ratio-1/2 homothety about A sends P,Q,R to M,N,U.
2. If S is the midpoint of AI, then U is the foot from A to SN.
3. The right-triangle similarity gives SU*SN=SA^2=SI^2.
4. For the antipodal arc midpoint D, DM*DN=DB^2=DI^2.
5. Hence the circles IUN and IMN are both tangent to AI at I.
6. Uniqueness gives I,M,N,U concyclic; homothety returns the goal.

## Domain and branch certificate

- `acute_branch`: Choose 0<beta<pi/4<alpha<pi/2 and alpha+beta>pi/2; then A=(cos 2alpha,sin 2alpha), B=(cos 2beta,sin 2beta), C=(cos 2beta,-sin 2beta) form an acute nondegenerate triangle.
- `rational_parameter_domain`: p=tan(alpha/2), q=tan(beta/2) satisfy 0<q<sqrt(2)-1<p<1 and p+q>1-pq.
- `arc_branch`: N=(-1,0) lies on the B-to-C arc containing A; D=(1,0) is its antipodal midpoint on AI.  The typed natural atom selects N.
- `denominators`: 1+p^2, 1+q^2 and cos(alpha) are positive.  |SN|^2>0 because S lies inside ABC while N lies on its circumcircle.
- `incenter_branch`: The equal-distance residuals plus 0<q<p<1 place I inside ABC, selecting the internal rather than an excentral branch.
- `tangency_uniqueness`: A circle tangent to AI at I has center on the perpendicular at I; requiring it to pass through N fixes that center uniquely.

## Exact replay

- `A_on_unit_circumcircle`: `0`
- `B_on_unit_circumcircle`: `0`
- `C_on_unit_circumcircle`: `0`
- `N_on_unit_circumcircle`: `0`
- `N_on_perpendicular_bisector_BC`: `0`
- `D_antipodal_to_N_x`: `0`
- `D_antipodal_to_N_y`: `0`
- `I_on_AD`: `0`
- `I_equidistant_from_AB_BC_squared`: `0`
- `I_equidistant_from_AC_BC_squared`: `0`
- `M_midpoint_BC_x`: `0`
- `M_midpoint_BC_y`: `0`
- `P_parallelogram_x`: `0`
- `P_parallelogram_y`: `0`
- `Q_reflection_in_N_x`: `0`
- `Q_reflection_in_N_y`: `0`
- `S_midpoint_AI_x`: `0`
- `S_midpoint_AI_y`: `0`
- `AN_perpendicular_AS`: `0`
- `U_on_SN`: `0`
- `AU_perpendicular_SN`: `0`
- `SU_times_SN_equals_SA_squared`: `0`
- `SI_squared_equals_SA_squared`: `0`
- `R_on_QI`: `0`
- `AR_perpendicular_QI`: `0`
- `P_maps_to_M_x`: `0`
- `P_maps_to_M_y`: `0`
- `Q_maps_to_N_x`: `0`
- `Q_maps_to_N_y`: `0`
- `R_maps_to_U_x`: `0`
- `R_maps_to_U_y`: `0`
- `DM_times_DN_equals_DB_squared`: `0`
- `DI_squared_equals_DB_squared`: `0`
- `small_circle_M_equals_I`: `0`
- `small_circle_N_equals_I`: `0`
- `small_circle_U_equals_I`: `0`
- `small_radius_at_I_perpendicular_AI`: `0`
- `O1_equidistant_P_Q`: `0`
- `O1_equidistant_P_R`: `0`
- `tangent_foot_on_AI`: `0`
- `O1_foot_perpendicular_AI`: `0`
- `goal_O1P_equals_O1T_squared`: `0`

- all identities replayed: `True`
- all conditions discharged: `True`
- certificate SHA-256: `14fce866da10724217a145f52c199e0e50c860400d1559d0d5321f6c71a24045`
