# HAGeo current rerun: unresolved dossiers

## 判定規約

- `completed_unsolved` は不正解ではなく、今回の有限探索で証明書が閉じなかったことだけを表す。
- `right_censored_timeout` は時間打切りであり、数学的な失敗判定には使わない。
- 原因名は推測せず、実際の補助構成、証明DAG、未充足前提だけを記録する。

## 集計

- 未証明 dossier: 32問
- 探索完了・証明書なし: 31問
- 時間打切り: 1問

## 2011G3

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 52.799111399999674
- 入力: `352a7df3ad0cde902c198780b52f69bb8f82f0a72265b61c14223a932fc11f2b`

```text
a b c d = quadrangle a b c d; m1 = midpoint m1 a b; m2 = midpoint m2 c d; e = on_circle e m1 a, on_circle e m2 c; f = on_circle f m1 a, on_circle f m2 c; e1 = foot e1 e a b; e2 = foot e2 e b c; e3 = foot e3 e c d; o1 = circumcenter o1 e1 e2 e3; f1 = foot f1 f c d; f2 = foot f2 f d a; f3 = foot f3 f a b; o2 = circumcenter o2 f1 f2 f3; k1 = on_circle k1 o1 e1, on_circle k1 o2 f1; k2 = on_circle k2 o1 e1, on_circle k2 o2 f1; m = midpoint m e f ? coll k1 k2 m
```

### 観測上位 1

- 構成経路: `nsquare(m,e)->g -> nsquare(m,f)->h`
- 全演繹: 12480
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k1,k2,k1,m)`
  - `para(k1,k2,k2,m)`
  - `midp(m,?A,?B)`
  - `circle(m,?A,?B,k1)`
  - `cyclic(?A,?B,k1,k2)`
  - `cong(?A,?B,k1,k2)`
  - `para(k1,m,k2,m)`
  - `midp(k2,?A,?B)`
  - `circle(k2,?A,?B,k1)`
  - `cyclic(?A,?B,k1,m)`
  - `cong(?A,?B,k1,m)`
  - `midp(m,k1,k2)`

### 観測上位 2

- 構成経路: `intersection_cc(m,e,m1)->g -> intersection_cc(m,e,m2)->h`
- 全演繹: 12288
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k1,k2,k1,m)`
  - `para(k1,k2,k2,m)`
  - `midp(m,?A,?B)`
  - `circle(m,?A,?B,k1)`
  - `cyclic(?A,?B,k1,k2)`
  - `cong(?A,?B,k1,k2)`
  - `para(k1,m,k2,m)`
  - `midp(k2,?A,?B)`
  - `circle(k2,?A,?B,k1)`
  - `cyclic(?A,?B,k1,m)`
  - `cong(?A,?B,k1,m)`
  - `midp(m,k1,k2)`

### 観測上位 3

- 構成経路: `nsquare(m,e)->g -> intersection_cc(m,e,m1)->h`
- 全演繹: 11846
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k1,k2,k1,m)`
  - `para(k1,k2,k2,m)`
  - `midp(m,?A,?B)`
  - `circle(m,?A,?B,k1)`
  - `cyclic(?A,?B,k1,k2)`
  - `cong(?A,?B,k1,k2)`
  - `para(k1,m,k2,m)`
  - `midp(k2,?A,?B)`
  - `circle(k2,?A,?B,k1)`
  - `cyclic(?A,?B,k1,m)`
  - `cong(?A,?B,k1,m)`
  - `midp(m,k1,k2)`

## 2011G5

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 37.26670990000093
- 入力: `7f5a70aa73dedd5c517c7105806e303e36ed71ddc040d336949486401145533f`

```text
a b c = triangle a b c; i = incenter i a b c; o = circumcenter o a b c; d = on_line d a i, on_circle d o a; e = on_line e b i, on_circle e o b; f = on_line f d e, on_line f a c; g = on_line g d e, on_line g b c; p = on_pline p f a d, on_pline p g b e; k = on_tline k a o a, on_tline k b o b; x = on_line x a e, on_line x b d ? coll k p x
```

### 観測上位 1

- 構成経路: `midpoint(a,c)->h -> foot(k,o,h)->j`
- 全演繹: 10668
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k,p,k,x)`
  - `para(k,p,p,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,k)`
  - `cyclic(?A,?B,k,p)`
  - `cong(?A,?B,k,p)`
  - `para(k,x,p,x)`
  - `midp(p,?A,?B)`
  - `circle(p,?A,?B,k)`
  - `cyclic(?A,?B,k,x)`
  - `cong(?A,?B,k,x)`
  - `midp(x,k,p)`

### 観測上位 2

- 構成経路: `midpoint(a,c)->h -> midpoint(b,c)->j`
- 全演繹: 9948
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k,p,k,x)`
  - `para(k,p,p,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,k)`
  - `cyclic(?A,?B,k,p)`
  - `cong(?A,?B,k,p)`
  - `para(k,x,p,x)`
  - `midp(p,?A,?B)`
  - `circle(p,?A,?B,k)`
  - `cyclic(?A,?B,k,x)`
  - `cong(?A,?B,k,x)`
  - `midp(x,k,p)`

### 観測上位 3

- 構成経路: `midpoint(a,c)->h -> excenter(k,a,h)->j`
- 全演繹: 8944
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k,p,k,x)`
  - `para(k,p,p,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,k)`
  - `cyclic(?A,?B,k,p)`
  - `cong(?A,?B,k,p)`
  - `para(k,x,p,x)`
  - `midp(p,?A,?B)`
  - `circle(p,?A,?B,k)`
  - `cyclic(?A,?B,k,x)`
  - `cong(?A,?B,k,x)`
  - `midp(x,k,p)`

## 2014CHNGaoLian

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 111
- 経過秒: 3.321678599999359
- 入力: `6c5de38d6fcf4cf26d85a2212f71f976ade226e254fd38685209903f4c92e7ca`

```text
a b c = triangle a b c; o = circumcenter o a b c; d = on_tline d b o b, on_circle d b c; e = on_tline e c o c, on_circle e c b; f = on_line f a b, on_line f d e; g = on_line g a c, on_line g d e; m = on_line m c f, on_line m b d; n = on_line n c e, on_line n b g ? cong a m a n
```

### 観測上位 1

- 構成経路: `intersection_cc(a,b,o)->h -> intersection_cc(a,n,h)->i`
- 全演繹: 2903
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `circle(a,m,n,?C)`
  - `circle(a,n,m,?C)`
  - `circle(a,?A,m,n)`
  - `circle(a,?A,n,m)`
  - `perp(?C,n,m,n)`
  - `midp(a,m,?C)`
  - `perp(?C,m,m,n)`
  - `midp(a,n,?C)`
  - `contri(a,m,?C,a,n,?R)`
  - `contri(a,m,?C,n,a,?R)`
  - `contri(m,a,?C,a,n,?R)`
  - `contri(m,a,?C,n,a,?R)`

### 観測上位 2

- 構成経路: `intersection_cc(a,b,o)->h -> psquare(a,h)->i`
- 全演繹: 2991
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `circle(a,m,n,?C)`
  - `circle(a,n,m,?C)`
  - `circle(a,?A,m,n)`
  - `circle(a,?A,n,m)`
  - `perp(?C,n,m,n)`
  - `midp(a,m,?C)`
  - `perp(?C,m,m,n)`
  - `midp(a,n,?C)`
  - `contri(a,m,?C,a,n,?R)`
  - `contri(a,m,?C,n,a,?R)`
  - `contri(m,a,?C,a,n,?R)`
  - `contri(m,a,?C,n,a,?R)`

### 観測上位 3

- 構成経路: `intersection_cc(a,b,o)->h -> on_circle(a,h)->i`
- 全演繹: 2862
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `circle(a,m,n,?C)`
  - `circle(a,n,m,?C)`
  - `circle(a,?A,m,n)`
  - `circle(a,?A,n,m)`
  - `perp(?C,n,m,n)`
  - `midp(a,m,?C)`
  - `perp(?C,m,m,n)`
  - `midp(a,n,?C)`
  - `contri(a,m,?C,a,n,?R)`
  - `contri(a,m,?C,n,a,?R)`
  - `contri(m,a,?C,a,n,?R)`
  - `contri(m,a,?C,n,a,?R)`

## 2015CTSTp9

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 81.01529339999979
- 入力: `18ec1e5a166809f7b113b976d1ace02431e8e8f716c75b6a72e056bed8cbb5d1`

```text
a b c = triangle a b c; o = circumcenter o a b c; d d1 d2 g = centroid d d1 d2 g a b c; e = on_circle e d b, on_tline e a b c; f = on_line f e g, on_line f o d; k = on_line k b c, on_pline k f o b; l = on_line l b c, on_pline l f o c; m = on_line m a b, on_tline m k b c; n = on_line n a c, on_tline n l b c; o1 = on_bline o1 b c, on_tline o1 b o b; o2 = circumcenter o2 a m n; t = on_circle t o1 b, on_circle t o2 a ? coll o1 o2 t
```

### 観測上位 1

- 構成経路: `orthocenter(o1,b,c)->h -> orthocenter(o1,b,l)->i`
- 全演繹: 24768
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o1,o2,o1,t)`
  - `para(o1,o2,o2,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,o1)`
  - `cyclic(?A,?B,o1,o2)`
  - `cong(?A,?B,o1,o2)`
  - `para(o1,t,o2,t)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,o1)`
  - `cyclic(?A,?B,o1,t)`
  - `cong(?A,?B,o1,t)`
  - `midp(t,o1,o2)`

### 観測上位 2

- 構成経路: `circle(o1,b,c)->h -> orthocenter(o1,b,h)->i`
- 全演繹: 20126
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o1,o2,o1,t)`
  - `para(o1,o2,o2,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,o1)`
  - `cyclic(?A,?B,o1,o2)`
  - `cong(?A,?B,o1,o2)`
  - `para(o1,t,o2,t)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,o1)`
  - `cyclic(?A,?B,o1,t)`
  - `cong(?A,?B,o1,t)`
  - `midp(t,o1,o2)`

### 観測上位 3

- 構成経路: `eq_triangle(b,c)->h -> orthocenter(o1,b,h)->i`
- 全演繹: 19157
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o1,o2,o1,t)`
  - `para(o1,o2,o2,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,o1)`
  - `cyclic(?A,?B,o1,o2)`
  - `cong(?A,?B,o1,o2)`
  - `para(o1,t,o2,t)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,o1)`
  - `cyclic(?A,?B,o1,t)`
  - `cong(?A,?B,o1,t)`
  - `midp(t,o1,o2)`

## 2015IranTSTp18

- 状態: `right_censored_timeout`
- 解釈: right_censored; no mathematical failure conclusion
- 探索候補: 28
- 経過秒: 7200.355345600001
- 入力: `7870e2656fc8900b965c159defe70ceda01324af374c2109c8590bcf9a4bce3a`

```text
point a 0.4126714639001544 0.5303261703377309
point b 0.9201678147586083 0.6639432475191882
point c 0.5467821565428718 1.2822640458094112
point h 0.8436828238080911 0.790601193857394
point o 0.5902098693008602 0.8865900764988245
point x 1.4006307792923711 1.3759793154597695
point y 0.7735881427221301 0.6253507584922208
point z 0.5624529092161507 1.3701275281312837
point h1 0.6232671474933891 1.1556060994712054
point m_bc 0.7334749856507401 0.9731036466642997
assume coll a b y
assume coll a c z
assume coll b c h
assume coll h h1 m_bc
assume cong b o a o
assume cong c o b o
assume cong h1 m_bc h m_bc
assume midp m_bc b c
assume perp a h b c
assume perp b o b x
assume perp c o c x
assume perp h1 x h1 y
assume perp h1 x h1 z
prove eqangle b x x y c x x z
```

### 観測上位 1

- 構成経路: `circle(b,c,o)->d -> intersection_tt(x,b,c,b,c,o)->e`
- 全演繹: 6229
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `eqangle(b,o,c,o,x,y,x,z)`
  - `eqangle(b,x,c,x,x,y,x,z)`
  - `eqangle(b,e,c,e,x,z,x,y)`

### 観測上位 2

- 構成経路: `circle(b,c,o)->d -> orthocenter(x,b,d)->e`
- 全演繹: 5087
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `eqangle(b,o,c,o,x,y,x,z)`
  - `eqangle(b,x,c,x,x,y,x,z)`
  - `eqangle(b,c,e,x,x,z,x,y)`

### 観測上位 3

- 構成経路: `circle(b,c,o)->d -> intersection_lp(x,b,c,b,o)->e`
- 全演繹: 4760
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `eqangle(b,o,c,o,x,y,x,z)`
  - `eqangle(b,x,c,x,x,y,x,z)`

## 2016CTSTp5

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 7.128963299999668
- 入力: `66a7bd8b0292e9316532bb1ca8c5eb8357e3253e20671afd251402f59d5d91b7`

```text
a b c = triangle a b c; d = on_circum d a b c; o = circumcenter o a b c; i = angle_bisector i d a b, angle_bisector i b c d; j = angle_bisector j a b c, angle_bisector j c d a; p = on_line p a b, on_line p i j; r = on_line r c d, on_line r i j; q = on_line q b c, on_line q i j; s = on_line s d a, on_line s i j; m = midpoint m p r; n = midpoint n q s ? perp m o n o
```

### 観測上位 1

- 構成経路: `between_bound(j,b)->e -> foot(o,j,e)->f`
- 全演繹: 5553
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `circle(i,m,o,n)`
  - `circle(j,m,o,n)`
  - `circle(p,m,o,n)`
  - `circle(?O,m,o,n)`
  - `coll(?O,m,n)`
  - `circle(q,m,o,n)`
  - `circle(r,m,o,n)`
  - `circle(s,m,o,n)`
  - `circle(?O,n,o,m)`
  - `circle(i,n,o,m)`
  - `circle(j,n,o,m)`
  - `circle(p,n,o,m)`

### 観測上位 2

- 構成経路: `nsquare(j,b)->e -> foot(o,j,e)->f`
- 全演繹: 5148
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `circle(i,m,o,n)`
  - `circle(j,m,o,n)`
  - `circle(p,m,o,n)`
  - `circle(?O,m,o,n)`
  - `coll(?O,m,n)`
  - `circle(q,m,o,n)`
  - `circle(r,m,o,n)`
  - `circle(s,m,o,n)`
  - `circle(?O,n,o,m)`
  - `circle(i,n,o,m)`
  - `circle(j,n,o,m)`
  - `circle(p,n,o,m)`

### 観測上位 3

- 構成経路: `psquare(j,b)->e -> foot(o,j,e)->f`
- 全演繹: 5148
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `circle(i,m,o,n)`
  - `circle(j,m,o,n)`
  - `circle(p,m,o,n)`
  - `circle(?O,m,o,n)`
  - `coll(?O,m,n)`
  - `circle(q,m,o,n)`
  - `circle(r,m,o,n)`
  - `circle(s,m,o,n)`
  - `circle(?O,n,o,m)`
  - `circle(i,n,o,m)`
  - `circle(j,n,o,m)`
  - `circle(p,n,o,m)`

## 2016USATSTSTp6

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 48.23859459999949
- 入力: `ffd6a2e36a473113e198abd0a21a913f268d19e363530dbdc36aeda3ad36a017`

```text
a b c = triangle a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; k = foot k d e f; o1 = circumcenter o1 a i b; c1 = on_circle c1 o1 a, on_circle c1 i d; c2 = on_circle c2 o1 a, on_circle c2 i d; o2 = circumcenter o2 a i c; b1 = on_circle b1 o2 a, on_circle b1 i d; b2 = on_circle b2 o2 a, on_circle b2 i d; o3 = circumcenter o3 b b1 b2; o4 = circumcenter o4 c c1 c2; p1 = on_circle p1 o3 b, on_circle p1 o4 c; p2 = on_circle p2 o3 b, on_circle p2 o4 c; m = midpoint m d k ? coll m p1 p2
```

### 観測上位 1

- 構成経路: `midpoint(m,d)->g -> foot(p1,m,g)->h`
- 全演繹: 15585
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(m,p1,m,p2)`
  - `para(m,p1,p1,p2)`
  - `midp(p2,?A,?B)`
  - `circle(p2,?A,?B,m)`
  - `cyclic(?A,?B,m,p1)`
  - `cong(?A,?B,m,p1)`
  - `para(m,p2,p1,p2)`
  - `midp(p1,?A,?B)`
  - `circle(p1,?A,?B,m)`
  - `cyclic(?A,?B,m,p2)`
  - `cong(?A,?B,m,p2)`
  - `midp(p2,m,p1)`

### 観測上位 2

- 構成経路: `mirror(m,d)->g -> foot(p1,m,g)->h`
- 全演繹: 15591
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(m,p1,m,p2)`
  - `para(m,p1,p1,p2)`
  - `midp(p2,?A,?B)`
  - `circle(p2,?A,?B,m)`
  - `cyclic(?A,?B,m,p1)`
  - `cong(?A,?B,m,p1)`
  - `para(m,p2,p1,p2)`
  - `midp(p1,?A,?B)`
  - `circle(p1,?A,?B,m)`
  - `cyclic(?A,?B,m,p2)`
  - `cong(?A,?B,m,p2)`
  - `midp(p2,m,p1)`

### 観測上位 3

- 構成経路: `between_bound(m,d)->g -> foot(p1,m,g)->h`
- 全演繹: 15531
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(m,p1,m,p2)`
  - `para(m,p1,p1,p2)`
  - `midp(p2,?A,?B)`
  - `circle(p2,?A,?B,m)`
  - `cyclic(?A,?B,m,p1)`
  - `cong(?A,?B,m,p1)`
  - `para(m,p2,p1,p2)`
  - `midp(p1,?A,?B)`
  - `circle(p1,?A,?B,m)`
  - `cyclic(?A,?B,m,p2)`
  - `cong(?A,?B,m,p2)`
  - `midp(p2,m,p1)`

## 2017G4

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 62.474026899999444
- 入力: `2488dd6a623c55498616fbb9a4d5adbff86c52fd04804d764df3e3b602f6e5ee`

```text
a b c = triangle a b c; i1 = excenter i1 a b c; d = foot d i1 b c; e = foot e i1 a c; f = foot f i1 a b; o1 = circumcenter o1 a e f; p = on_line p b c, on_circle p o1 a; q = on_line q b c, on_circle q o1 a; m = midpoint m a d; o2 = circumcenter o2 m p q; u = on_circle u o2 m, on_circle u i1 d ? coll i1 o2 u
```

### 観測上位 1

- 構成経路: `circumcenter(i1,b,c)->g -> intersection_lp(i1,o2,b,c,q)->h`
- 全演繹: 7836
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(i1,o2,i1,u)`
  - `para(i1,o2,o2,u)`
  - `midp(u,?A,?B)`
  - `circle(u,?A,?B,i1)`
  - `cyclic(?A,?B,i1,o2)`
  - `cong(?A,?B,i1,o2)`
  - `para(i1,u,o2,u)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,i1)`
  - `cyclic(?A,?B,i1,u)`
  - `cong(?A,?B,i1,u)`
  - `midp(u,i1,o2)`

### 観測上位 2

- 構成経路: `reflect(i1,b,c)->g -> circumcenter(i1,a,g)->h`
- 全演繹: 8218
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(i1,o2,i1,u)`
  - `para(i1,o2,o2,u)`
  - `midp(u,?A,?B)`
  - `circle(u,?A,?B,i1)`
  - `cyclic(?A,?B,i1,o2)`
  - `cong(?A,?B,i1,o2)`
  - `para(i1,u,o2,u)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,i1)`
  - `cyclic(?A,?B,i1,u)`
  - `cong(?A,?B,i1,u)`
  - `midp(u,i1,o2)`

### 観測上位 3

- 構成経路: `reflect(i1,b,c)->g -> circle(i1,a,g)->h`
- 全演繹: 8212
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(i1,o2,i1,u)`
  - `para(i1,o2,o2,u)`
  - `midp(u,?A,?B)`
  - `circle(u,?A,?B,i1)`
  - `cyclic(?A,?B,i1,o2)`
  - `cong(?A,?B,i1,o2)`
  - `para(i1,u,o2,u)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,i1)`
  - `cyclic(?A,?B,i1,u)`
  - `cong(?A,?B,i1,u)`
  - `midp(u,i1,o2)`

## 2017USAMOp3

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 50.73633619999964
- 入力: `d99e367d0583ee9a7fa035f7f7d50971f4311b6018876d958947c6a7fedc8572`

```text
a b c = triangle a b c; o = circumcenter o a b c; i = incenter i a b c; d = on_line d a i, on_line d b c; m = on_line m a i, on_circle m o a; k = on_dia k m d, on_circle k o a; s = on_line s m k, on_line s b c; n = midpoint n i s; o1 = circumcenter o1 k i d; o2 = circumcenter o2 m a n; l = on_circle l o1 k, on_circle l o2 m; p = midpoint p i l ? cyclic a b c p
```

### 観測上位 1

- 構成経路: `intersection_lt(b,a,m,b,c)->e -> orthocenter(b,o,e)->f`
- 全演繹: 7594
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,c,a,p,b,c,b,p)`
  - `ncoll(a,b,c,p)`
  - `eqangle(a,b,a,p,b,c,c,p)`
  - `eqangle(a,b,a,c,b,p,c,p)`

### 観測上位 2

- 構成経路: `intersection_lt(b,a,m,b,c)->e -> foot(b,o,e)->f`
- 全演繹: 8659
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,c,a,p,b,c,b,p)`
  - `ncoll(a,b,c,p)`
  - `eqangle(a,b,a,p,b,c,c,p)`
  - `eqangle(a,b,a,c,b,p,c,p)`

### 観測上位 3

- 構成経路: `midpoint(b,c)->e -> intersection_lt(b,a,m,b,c)->f`
- 全演繹: 8649
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,c,a,p,b,c,b,p)`
  - `ncoll(a,b,c,p)`
  - `eqangle(a,b,a,p,b,c,c,p)`
  - `eqangle(a,b,a,c,b,p,c,p)`

## 2019IranTSTp15

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 143.11296690000017
- 入力: `2706434d9e84d5d7b11ce3bbb2994d0e4242bdb2f00e6ddd2490b422a5301ad1`

```text
k b c = triangle k b c; b1 = mirror b1 b k; c1 = mirror c1 c k; a = on_line a b1 c1, angle_bisector a b k c; m = midpoint m b c; n = midpoint n c a; p = midpoint p a b; e = on_line e m n, on_line e b k; f = on_line f m p, on_line f c k; h = foot h a b c; o1 = circumcenter o1 a k h; o2 = circumcenter o2 h e f; l = on_circle l o1 a, on_circle l o2 h; x = on_line x m k, on_line x e f ? coll h l x
```

### 観測上位 1

- 構成経路: `circle(h,a,c1)->d -> incenter(h,k,a)->g`
- 全演繹: 21528
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(h,l,h,x)`
  - `para(h,l,l,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,h)`
  - `cyclic(?A,?B,h,l)`
  - `cong(?A,?B,h,l)`
  - `para(h,x,l,x)`
  - `midp(l,?A,?B)`
  - `circle(l,?A,?B,h)`
  - `cyclic(?A,?B,h,x)`
  - `cong(?A,?B,h,x)`
  - `midp(x,h,l)`

### 観測上位 2

- 構成経路: `circumcenter(h,a,c1)->d -> incenter(h,k,a)->g`
- 全演繹: 21528
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(h,l,h,x)`
  - `para(h,l,l,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,h)`
  - `cyclic(?A,?B,h,l)`
  - `cong(?A,?B,h,l)`
  - `para(h,x,l,x)`
  - `midp(l,?A,?B)`
  - `circle(l,?A,?B,h)`
  - `cyclic(?A,?B,h,x)`
  - `cong(?A,?B,h,x)`
  - `midp(x,h,l)`

### 観測上位 3

- 構成経路: `circle(h,a,c1)->d -> shift(h,b,c)->g`
- 全演繹: 21847
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(h,l,h,x)`
  - `para(h,l,l,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,h)`
  - `cyclic(?A,?B,h,l)`
  - `cong(?A,?B,h,l)`
  - `para(h,x,l,x)`
  - `midp(l,?A,?B)`
  - `circle(l,?A,?B,h)`
  - `cyclic(?A,?B,h,x)`
  - `cong(?A,?B,h,x)`
  - `midp(x,h,l)`

## 2020IranGOAp2

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 5.6551662999991095
- 入力: `85e48377a0b6e26ea36230f187df13f6af38e26cb8019a7ae9faa5adf95adeb7`

```text
a b c = triangle a b c; i = incenter i a b c; o = circumcenter o a b c; n = on_bline n b c, on_circle n o a; m = midpoint m b c; p = mirror p a m; q = mirror q a n; r = foot r a q i; o1 = circumcenter o1 p q r; t = foot t o1 a i ? cong o1 p o1 t
```

### 観測上位 1

- 構成経路: `intersection_ll(o1,t,a,r)->d -> shift(o1,i,d)->e`
- 全演繹: 4345
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `cyclic(p,q,r,t)`
  - `cong(d,n,o1,t)`
  - `circle(o1,p,t,?C)`
  - `cong(o1,q,o1,t)`
  - `cong(o1,r,o1,t)`
  - `circle(o1,t,p,?C)`
  - `circle(o1,?A,p,t)`
  - `circle(o1,?A,t,p)`
  - `perp(?C,t,p,t)`
  - `midp(o1,p,?C)`
  - `perp(?C,p,p,t)`
  - `midp(o1,t,?C)`

### 観測上位 2

- 構成経路: `mirror(a,o)->d -> foot(o1,n,d)->e`
- 全演繹: 4962
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `cyclic(p,q,r,t)`
  - `cong(o1,q,o1,t)`
  - `cong(o1,r,o1,t)`
  - `circle(o1,p,t,?C)`
  - `circle(o1,t,p,?C)`
  - `circle(o1,?A,p,t)`
  - `circle(o1,?A,t,p)`
  - `perp(?C,t,p,t)`
  - `midp(o1,p,?C)`
  - `perp(?C,p,p,t)`
  - `midp(o1,t,?C)`

### 観測上位 3

- 構成経路: `eq_triangle(b,c)->d -> eq_triangle(b,m)->e`
- 全演繹: 3973
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `cyclic(p,q,r,t)`
  - `cong(o1,q,o1,t)`
  - `cong(o1,r,o1,t)`
  - `circle(o1,p,t,?C)`
  - `circle(o1,t,p,?C)`
  - `circle(o1,?A,p,t)`
  - `circle(o1,?A,t,p)`
  - `perp(?C,t,p,t)`
  - `midp(o1,p,?C)`
  - `perp(?C,p,p,t)`
  - `midp(o1,t,?C)`

## 2020IranTSTp9

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 46.34325350000108
- 入力: `29a9fb61f57d5b7062fb44e81c7a8eec8f7a3ea6590f3ee0e66754d39fa75caa`

```text
a b c = triangle a b c; o = circumcenter o a b c; i = incenter i a b c; e = on_line e a c, angle_bisector e c b a; f = on_line f a b, angle_bisector f b c a; k = on_line k a i, on_line k e f; t = on_circle t o a, on_bline t b c; m = midpoint m b c; x = on_line x a m, on_circle x o a; o1 = circumcenter o1 a e f; s = on_circle s o1 a, on_circle s o a; s1 = reflect s1 s a i; o2 = circumcenter o2 a s1 k; j = on_line j a x, on_circle j o2 a ? cyclic i j t x
```

### 観測上位 1

- 構成経路: `intersection_lp(x,t,i,b,e)->d -> mirror(t,o)->g`
- 全演繹: 10972
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(i,t,i,x,j,t,j,x)`
  - `ncoll(i,j,t,x)`
  - `eqangle(i,j,i,x,j,t,t,x)`
  - `eqangle(i,j,i,t,j,x,t,x)`

### 観測上位 2

- 構成経路: `shift(x,a,j)->d -> mirror(t,o)->g`
- 全演繹: 10771
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(i,t,i,x,j,t,j,x)`
  - `ncoll(i,j,t,x)`
  - `eqangle(i,j,i,x,j,t,t,x)`
  - `eqangle(i,j,i,t,j,x,t,x)`

### 観測上位 3

- 構成経路: `intersection_lc(x,a,j)->d -> mirror(t,o)->g`
- 全演繹: 10751
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(i,t,i,x,j,t,j,x)`
  - `ncoll(i,j,t,x)`
  - `eqangle(i,j,i,x,j,t,t,x)`
  - `eqangle(i,j,i,t,j,x,t,x)`

## 2021ARMOg10p8

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 97.31613490000018
- 入力: `e9165479f04905dd253c1c4d1cfebf94fa6b9cdbe6890896c9967d6c6a332578`

```text
a b c = triangle a b c; d = on_circum d a b c; e = on_circum e a b c; o = circumcenter o a b c; x = on_line x c d, on_line x a b; y = on_line y c d, on_line y a e; p = on_line p e x, on_line p b y; q = on_line q e x, on_circle q o a; r = on_line r b y, on_circle r o a; a1 = reflect a1 a c d; o1 = circumcenter o1 p q r; o2 = circumcenter o2 a1 x y; m = on_circle m o1 p, on_circle m o2 x; n = on_circle n o1 p, on_circle n o2 x; z = on_line z c m, on_line z d n ? cyclic p q r z
```

### 観測上位 1

- 構成経路: `intersection_lc(p,b,x)->f -> intersection_cc(p,r,f)->g`
- 全演繹: 9978
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(p,r,p,z,q,r,q,z)`
  - `ncoll(p,q,r,z)`
  - `eqangle(p,q,p,z,q,r,r,z)`
  - `eqangle(p,q,p,r,q,z,r,z)`

### 観測上位 2

- 構成経路: `intersection_lp(p,r,q,b,x)->f -> intersection_lp(p,r,z,p,x)->g`
- 全演繹: 10960
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(p,r,p,z,q,r,q,z)`
  - `ncoll(p,q,r,z)`
  - `eqangle(p,q,p,z,q,r,r,z)`
  - `eqangle(p,q,p,r,q,z,r,z)`

### 観測上位 3

- 構成経路: `intersection_lp(p,r,q,b,x)->f -> intersection_lt(p,r,q,b,o)->g`
- 全演繹: 10849
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(p,r,p,z,q,r,q,z)`
  - `ncoll(p,q,r,z)`
  - `eqangle(p,q,p,z,q,r,r,z)`
  - `eqangle(p,q,p,r,q,z,r,z)`

## 2021GOWACAp5

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 157.46511620000092
- 入力: `a64b0589ec52852348fff41ae72c86319b073c2c9c517883044d833c208e5573`

```text
a b c = triangle a b c; d = foot d a b c; o = circumcenter o a b c; m m1 m2 g = centroid m m1 m2 g a b c; k = on_aline k a c b a g, on_aline k b a c b g; d1 = mirror d1 d m; d2 = on_line d2 b c, on_aline d2 a b c a d1; p = on_tline p k a o, on_line p a d2; x = on_line x b c, on_tline x k b o; y = on_line y b c, on_tline y k c o; i = incenter i p x y ? coll a d i
```

### 観測上位 1

- 構成経路: `angle_mirror(d,m,d1)->e -> intersection_cc(d,a,e)->f`
- 全演繹: 16386
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,d,a,i)`
  - `para(a,d,d,i)`
  - `para(a,i,d,i)`
  - `midp(i,a,d)`
  - `midp(d,a,i)`
  - `midp(i,d,a)`
  - `midp(d,i,a)`
  - `midp(a,d,i)`
  - `midp(a,i,d)`
  - `lequation(1/1,a,d,1/1,d,i,-1/1,a,i,0)`
  - `lequation(1/1,a,i,1/1,i,d,-1/1,a,d,0)`
  - `lequation(1/1,d,a,1/1,a,i,-1/1,d,i,0)`

### 観測上位 2

- 構成経路: `angle_mirror(d,m,d1)->e -> on_pline(d,b,e)->f`
- 全演繹: 16099
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,d,a,i)`
  - `para(a,d,d,i)`
  - `midp(i,?A,?B)`
  - `circle(i,?A,?B,a)`
  - `cyclic(?A,?B,a,d)`
  - `cong(?A,?B,a,d)`
  - `para(a,i,d,i)`
  - `midp(d,?A,?B)`
  - `circle(d,?A,?B,a)`
  - `cyclic(?A,?B,a,i)`
  - `cong(?A,?B,a,i)`
  - `midp(i,a,d)`

### 観測上位 3

- 構成経路: `angle_mirror(d,m,d1)->e -> angle_bisector(d,c,e)->f`
- 全演繹: 16096
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,d,a,i)`
  - `para(a,d,d,i)`
  - `midp(i,?A,?B)`
  - `circle(i,?A,?B,a)`
  - `cyclic(?A,?B,a,d)`
  - `cong(?A,?B,a,d)`
  - `para(a,i,d,i)`
  - `midp(d,?A,?B)`
  - `circle(d,?A,?B,a)`
  - `cyclic(?A,?B,a,i)`
  - `cong(?A,?B,a,i)`
  - `midp(i,a,d)`

## 2021IranTSTp6

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 18.594043100001727
- 入力: `260eda2ec771e54b489a68bf47f9b3083beb535fb95e9bcd80d243cb36aff10f`

```text
a b c = triangle a b c; o = circumcenter o a b c; h = orthocenter h a b c; d = on_line d o h; e = on_line e b d, on_line e a c; f = on_line f c d, on_line f a b; x = on_line x a d, eqangle3 x e f a b c; o1 = circumcenter o1 c x f; o2 = circumcenter o2 b x e; p = on_circle p o1 c, on_circle p o2 b; q = on_line q x p, on_line q e f ? coll a h q
```

### 観測上位 1

- 構成経路: `angle_bisector(a,b,f)->g -> shift(a,b,g)->i`
- 全演繹: 3425
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,h,a,q)`
  - `para(a,h,h,q)`
  - `para(a,q,h,q)`
  - `midp(q,a,h)`
  - `midp(h,a,q)`
  - `midp(q,h,a)`
  - `midp(h,q,a)`
  - `midp(a,h,q)`
  - `midp(a,q,h)`
  - `lequation(1/1,a,h,1/1,h,q,-1/1,a,q,0)`
  - `lequation(1/1,a,q,1/1,q,h,-1/1,a,h,0)`
  - `lequation(1/1,h,a,1/1,a,q,-1/1,h,q,0)`

### 観測上位 2

- 構成経路: `angle_mirror(a,b,f)->g -> shift(a,b,g)->i`
- 全演繹: 3425
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,h,a,q)`
  - `para(a,h,h,q)`
  - `para(a,q,h,q)`
  - `midp(q,a,h)`
  - `midp(h,a,q)`
  - `midp(q,h,a)`
  - `midp(h,q,a)`
  - `midp(a,h,q)`
  - `midp(a,q,h)`
  - `lequation(1/1,a,h,1/1,h,q,-1/1,a,q,0)`
  - `lequation(1/1,a,q,1/1,q,h,-1/1,a,h,0)`
  - `lequation(1/1,h,a,1/1,a,q,-1/1,h,q,0)`

### 観測上位 3

- 構成経路: `angle_bisector(a,b,f)->g -> angle_bisector(a,f,g)->i`
- 全演繹: 3349
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,h,a,q)`
  - `para(a,h,h,q)`
  - `para(a,q,h,q)`
  - `midp(q,a,h)`
  - `midp(h,a,q)`
  - `midp(q,h,a)`
  - `midp(h,q,a)`
  - `midp(a,h,q)`
  - `midp(a,q,h)`
  - `lequation(1/1,a,h,1/1,h,q,-1/1,a,q,0)`
  - `lequation(1/1,a,q,1/1,q,h,-1/1,a,h,0)`
  - `lequation(1/1,h,a,1/1,a,q,-1/1,h,q,0)`

## 2021IsraelOlympicRev

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 69.08909399999902
- 入力: `8c8691c3c5bdfc682b937068f36739e7d7aeb52aaee8d8b1c4713730e6c0e243`

```text
a b c = triangle a b c; p = eqangle3 p b c a c b; p1 = on_line p1 a p, on_line p1 b c; p2 = on_line p2 b p, on_line p2 a c; p3 = on_line p3 c p, on_line p3 a b; o = circumcenter o a b c; o2 = circumcenter o2 a p2 p3; x1 = on_circle x1 o a, on_circle x1 o2 a; o3 = circumcenter o3 b p3 p1; x2 = on_circle x2 o b, on_circle x2 o3 b; o4 = circumcenter o4 c p1 p2; x3 = on_circle x3 o c, on_circle x3 o4 c; b1 = on_line b1 a x1, on_line b1 c x3; c1 = on_line c1 a x1, on_line c1 b x2; k = on_line k b b1, on_line k c c1 ? cyclic a k p2 p3
```

### 観測上位 1

- 構成経路: `midpoint(a,x1)->d -> intersection_lc(a,b,d)->e`
- 全演繹: 9972
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,p2,a,p3,k,p2,k,p3)`
  - `ncoll(a,k,p2,p3)`
  - `eqangle(a,k,a,p3,k,p2,p2,p3)`
  - `eqangle(a,k,a,p2,k,p3,p2,p3)`

### 観測上位 2

- 構成経路: `midpoint(a,x1)->d -> intersection_lp(a,p3,p2,a,d)->e`
- 全演繹: 9779
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,p2,a,p3,k,p2,k,p3)`
  - `ncoll(a,k,p2,p3)`
  - `eqangle(a,k,a,p3,k,p2,p2,p3)`
  - `eqangle(a,k,a,p2,k,p3,p2,p3)`

### 観測上位 3

- 構成経路: `intersection_lt(a,p3,p2,a,b)->d -> midpoint(a,x1)->e`
- 全演繹: 9566
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,p2,a,p3,k,p2,k,p3)`
  - `ncoll(a,k,p2,p3)`
  - `eqangle(a,k,a,p3,k,p2,p2,p3)`
  - `eqangle(a,k,a,p2,k,p3,p2,p3)`

## 2022G5

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 44.257531299999755
- 入力: `2b6e8f44d3914a1b5335a76d4a130094f187c501bc0a9ec6a02d315d39230806`

```text
a b c = triangle a b c; x1 = on_line x1 b c; y1 = on_line y1 a c; z1 = on_line z1 a b, on_line z1 x1 y1; x2 = on_line x2 b c; y2 = on_line y2 a c, on_pline y2 x2 x1 y1; z2 = on_line z2 a b, on_pline z2 x2 x1 y1; u1 = on_tline u1 y1 a c, on_tline u1 z1 a b; v1 = on_tline v1 x1 b c, on_tline v1 z1 a b; w1 = on_tline w1 x1 b c, on_tline w1 y1 a c; u2 = on_tline u2 y2 a c, on_tline u2 z2 a b; v2 = on_tline v2 x2 b c, on_tline v2 z2 a b; w2 = on_tline w2 x2 b c, on_tline w2 y2 a c; o1 = circumcenter o1 u1 v1 w1; o2 = circumcenter o2 u2 v2 w2; t = on_circle t o1 u1, on_circle t o2 u2 ? coll o1 o2 t
```

### 観測上位 1

- 構成経路: `parallelogram(o2,o1,u1)->d -> intersection_lc(o2,t,d)->e`
- 全演繹: 12948
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o1,o2,o1,t)`
  - `para(o1,o2,o2,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,o1)`
  - `cyclic(?A,?B,o1,o2)`
  - `cong(?A,?B,o1,o2)`
  - `para(o1,t,o2,t)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,o1)`
  - `cyclic(?A,?B,o1,t)`
  - `cong(?A,?B,o1,t)`
  - `midp(t,o1,o2)`

### 観測上位 2

- 構成経路: `between_bound(o2,u2)->d -> parallelogram(o2,o1,u1)->e`
- 全演繹: 12919
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o1,o2,o1,t)`
  - `para(o1,o2,o2,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,o1)`
  - `cyclic(?A,?B,o1,o2)`
  - `cong(?A,?B,o1,o2)`
  - `para(o1,t,o2,t)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,o1)`
  - `cyclic(?A,?B,o1,t)`
  - `cong(?A,?B,o1,t)`
  - `midp(t,o1,o2)`

### 観測上位 3

- 構成経路: `on_pline(o2,o1,u1)->d -> intersection_lc(o2,t,d)->e`
- 全演繹: 12849
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o1,o2,o1,t)`
  - `para(o1,o2,o2,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,o1)`
  - `cyclic(?A,?B,o1,o2)`
  - `cong(?A,?B,o1,o2)`
  - `para(o1,t,o2,t)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,o1)`
  - `cyclic(?A,?B,o1,t)`
  - `cong(?A,?B,o1,t)`
  - `midp(t,o1,o2)`

## 2023IMOp6

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 57.8476828999992
- 入力: `9a1953e82a03c37a1ce5e991bb73441e0360ddb9ddfd65df776d718c544952f2`

```text
a b c = ieq_triangle a b c; o = circumcenter o a b c; a1 = on_bline a1 b c; b1 = on_bline b1 c a; c0 = on_aline c0 a b a1 c b1; c1 = on_bline c1 a b, on_aline c1 a b c0 a o; a2 = on_line a2 b c1, on_line a2 c b1; b2 = on_line b2 c a1, on_line b2 a c1; c2 = on_line c2 a b1, on_line c2 b a1; o1 = circumcenter o1 a a1 a2; o2 = circumcenter o2 b b1 b2; o3 = circumcenter o3 c c1 c2; x = on_circle x o1 a, on_circle x o2 b ? cyclic c c1 c2 x
```

### 観測上位 1

- 構成経路: `intersection_cc(c,a,o)->d -> reflect(c,a,d)->e`
- 全演繹: 9477
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(c,c2,c,x,c1,c2,c1,x)`
  - `ncoll(c,c1,c2,x)`
  - `eqangle(c,c1,c,x,c1,c2,c2,x)`
  - `eqangle(c,c1,c,c2,c1,x,c2,x)`

### 観測上位 2

- 構成経路: `circle(c,a,o)->d -> orthocenter(c,a,d)->e`
- 全演繹: 9475
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(c,c2,c,x,c1,c2,c1,x)`
  - `ncoll(c,c1,c2,x)`
  - `eqangle(c,c1,c,x,c1,c2,c2,x)`
  - `eqangle(c,c1,c,c2,c1,x,c2,x)`

### 観測上位 3

- 構成経路: `shift(c,a,o)->d -> orthocenter(c,a,d)->e`
- 全演繹: 9474
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(c,c2,c,x,c1,c2,c1,x)`
  - `ncoll(c,c1,c2,x)`
  - `eqangle(c,c1,c,x,c1,c2,c2,x)`
  - `eqangle(c,c1,c,c2,c1,x,c2,x)`

## 2023MOSTMockp2

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 31.75084269999934
- 入力: `800ac979a58bb45264241769d895925262c2cffde4f31ac66392f6d2a73591b8`

```text
a1 a3 a5 = triangle a1 a3 a5; a4 = free a4; a6 = free a6; a2 = on_aline a2 a4 a6 a5 a1 a3, on_aline a2 a6 a4 a5 a3 a1; x1 = on_line x1 a1 a3, on_line x1 a2 a6; x2 = on_line x2 a1 a3, on_line x2 a2 a4; x3 = on_line x3 a2 a4, on_line x3 a3 a5; x4 = on_line x4 a3 a5, on_line x4 a4 a6; x5 = on_line x5 a1 a5, on_line x5 a6 a4; x6 = on_line x6 a1 a5, on_line x6 a2 a6; o1 = circumcenter o1 a1 x1 a2; o2 = circumcenter o2 a2 x2 a3; o3 = circumcenter o3 a3 x3 a4; o4 = circumcenter o4 a4 x4 a5; o5 = circumcenter o5 a5 x5 a6; o6 = circumcenter o6 a6 x6 a1; k = on_line k o1 o4, on_line k o2 o5 ? coll k o3 o6
```

### 観測上位 1

- 構成経路: `midpoint(k,o1)->a -> intersection_lc(k,o3,a)->b`
- 全演繹: 9104
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k,o3,k,o6)`
  - `para(k,o3,o3,o6)`
  - `midp(o6,?A,?B)`
  - `circle(o6,?A,?B,k)`
  - `cyclic(?A,?B,k,o3)`
  - `cong(?A,?B,k,o3)`
  - `para(k,o6,o3,o6)`
  - `midp(o3,?A,?B)`
  - `circle(o3,?A,?B,k)`
  - `cyclic(?A,?B,k,o6)`
  - `cong(?A,?B,k,o6)`
  - `midp(o6,k,o3)`

### 観測上位 2

- 構成経路: `mirror(k,o1)->a -> intersection_lc(k,o3,a)->b`
- 全演繹: 9105
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k,o3,k,o6)`
  - `para(k,o3,o3,o6)`
  - `midp(o6,?A,?B)`
  - `circle(o6,?A,?B,k)`
  - `cyclic(?A,?B,k,o3)`
  - `cong(?A,?B,k,o3)`
  - `para(k,o6,o3,o6)`
  - `midp(o3,?A,?B)`
  - `circle(o3,?A,?B,k)`
  - `cyclic(?A,?B,k,o6)`
  - `cong(?A,?B,k,o6)`
  - `midp(o6,k,o3)`

### 観測上位 3

- 構成経路: `between_bound(k,o1)->a -> intersection_lc(k,o3,a)->b`
- 全演繹: 9079
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k,o3,k,o6)`
  - `para(k,o3,o3,o6)`
  - `midp(o6,?A,?B)`
  - `circle(o6,?A,?B,k)`
  - `cyclic(?A,?B,k,o3)`
  - `cong(?A,?B,k,o3)`
  - `para(k,o6,o3,o6)`
  - `midp(o3,?A,?B)`
  - `circle(o3,?A,?B,k)`
  - `cyclic(?A,?B,k,o6)`
  - `cong(?A,?B,k,o6)`
  - `midp(o6,k,o3)`

## 2023RMMSLG3

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 1178.808289200002
- 入力: `132bd01d41573a1de9e9045063407e77403e2eca2f43f7d60f80b6e1a4f891e4`

```text
a b c = triangle a b c; p = free p; o = circumcenter o a b c; o1 = circumcenter o1 a p b; o2 = circumcenter o2 b p c; o3 = circumcenter o3 c p a; o4 = circumcenter o4 o1 o2 o3; x = on_circle x o a, on_circle x o4 o1; y = on_circle y o a, on_circle y o4 o1; q = reflect q p x y ? eqangle a b a p a q a c
```

### 観測上位 1

- 構成経路: `intersection_cc(a,b,o)->d -> shift(a,o,d)->e`
- 全演繹: 3413
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 2
- 未充足前提:
  - `eqangle(a,c,a,q,o1,o2,b,o1)`
  - `eqangle(a,c,a,q,o1,p,o1,o2)`

### 観測上位 2

- 構成経路: `shift(a,b,o)->d -> shift(a,o,d)->e`
- 全演繹: 3412
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 2
- 未充足前提:
  - `eqangle(a,c,a,q,o1,o2,b,o1)`
  - `eqangle(a,c,a,q,o1,p,o1,o2)`

### 観測上位 3

- 構成経路: `intersection_cc(a,b,o)->d -> foot(a,o1,d)->e`
- 全演繹: 3275
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 2
- 未充足前提:
  - `eqangle(a,c,a,p,a,q,a,e)`
  - `eqangle(a,c,a,q,o1,o2,b,o1)`
  - `eqangle(a,c,a,q,o1,p,o1,o2)`

## 2023SAGFp8

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 118
- 経過秒: 147.53227979999792
- 入力: `0eec560fc44055a28a740419cbae2ff97e72a96debdfcdfa6bdd5daf21083f01`

```text
a b c = triangle a b c; o = circumcenter o a b c; d = on_bline d b c, on_circle d o a; e = on_bline e c a, on_circle e o a; f = on_bline f a b, on_circle f o a; r = mirror r d o; s = mirror s e o; t = mirror t f o; d1 = reflect d1 d b c; e1 = reflect e1 e c a; f1 = reflect f1 f a b; r1 = reflect r1 r b c; s1 = reflect s1 s c a; t1 = reflect t1 t a b; h1 = orthocenter h1 d1 e1 f1; o1 = circumcenter o1 r1 s1 t1; h = orthocenter h a b c ? para h1 o1 h o
```

### 観測上位 1

- 構成経路: `orthocenter(o,b,a)->g -> intersection_ll(o,g,h,h1)->i`
- 全演繹: 54398
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `eqratio(h,h1,h,i,o,o1,i,o)`
  - `coll(i,o,o1)`
  - `sameside(h,i,h1,o,i,o1)`
  - `sameside(o,i,o1,h,i,h1)`
  - `eqratio(h,h1,h1,i,o,o1,i,o1)`
  - `sameside(h1,i,h,o1,i,o)`
  - `midp(?M,h,h1)`
  - `midp(?M,o,o1)`
  - `sameside(o1,i,o,h1,i,h)`
  - `midp(?M,h,o1)`
  - `midp(?M,o,h1)`
  - `midp(?M,h1,h)`

### 観測上位 2

- 構成経路: `circle(o,b,a)->g -> intersection_ll(o,g,h,h1)->i`
- 全演繹: 53422
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 2
- 未充足前提:
  - `eqratio(h,h1,h,i,o,o1,i,o)`
  - `coll(i,o,o1)`
  - `sameside(h,i,h1,o,i,o1)`
  - `sameside(o,i,o1,h,i,h1)`
  - `eqratio(h,h1,h1,i,o,o1,i,o1)`
  - `sameside(h1,i,h,o1,i,o)`
  - `midp(?M,h,h1)`
  - `midp(?M,o,o1)`
  - `sameside(o1,i,o,h1,i,h)`
  - `midp(?M,h,o1)`
  - `midp(?M,o,h1)`
  - `midp(?M,h1,h)`

### 観測上位 3

- 構成経路: `circumcenter(o,b,a)->g -> intersection_ll(o,g,h,h1)->i`
- 全演繹: 53422
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 2
- 未充足前提:
  - `eqratio(h,h1,h,i,o,o1,i,o)`
  - `coll(i,o,o1)`
  - `sameside(h,i,h1,o,i,o1)`
  - `sameside(o,i,o1,h,i,h1)`
  - `eqratio(h,h1,h1,i,o,o1,i,o1)`
  - `sameside(h1,i,h,o1,i,o)`
  - `midp(?M,h,h1)`
  - `midp(?M,o,o1)`
  - `sameside(o1,i,o,h1,i,h)`
  - `midp(?M,h,o1)`
  - `midp(?M,o,h1)`
  - `midp(?M,h1,h)`

## 2023SerbiaMOp6

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 15.198339799999303
- 入力: `9e86fd5b43a6a8aea0fa7068d031595e0e9a880bcbe02c246a11dea538c6d2f0`

```text
a b c = triangle a b c; i = incenter i a b c; o = circumcenter o a b c; d = foot d i b c; e = on_line e a b, on_tline e i a i; f = on_line f a c, on_tline f i a i; o1 = circumcenter o1 a e f; g = on_circle g o1 a, on_circle g o a; h = on_circle h o1 a, on_line h a i; j = on_tline j g o g, on_line j b c; k = on_line k a j, on_circle k o a; o3 = circumcenter o3 d j k; o4 = circumcenter o4 g i h; t = on_circle t o4 i, on_circle t o3 d ? coll o3 o4 t
```

### 観測上位 1

- 構成経路: `nsquare(i,a)->l -> nsquare(i,l)->m`
- 全演繹: 10633
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o3,o4,o3,t)`
  - `para(o3,o4,o4,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,o3)`
  - `cyclic(?A,?B,o3,o4)`
  - `cong(?A,?B,o3,o4)`
  - `para(o3,t,o4,t)`
  - `midp(o4,?A,?B)`
  - `circle(o4,?A,?B,o3)`
  - `cyclic(?A,?B,o3,t)`
  - `cong(?A,?B,o3,t)`
  - `midp(t,o3,o4)`

### 観測上位 2

- 構成経路: `psquare(i,a)->l -> psquare(i,l)->m`
- 全演繹: 10633
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o3,o4,o3,t)`
  - `para(o3,o4,o4,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,o3)`
  - `cyclic(?A,?B,o3,o4)`
  - `cong(?A,?B,o3,o4)`
  - `para(o3,t,o4,t)`
  - `midp(o4,?A,?B)`
  - `circle(o4,?A,?B,o3)`
  - `cyclic(?A,?B,o3,t)`
  - `cong(?A,?B,o3,t)`
  - `midp(t,o3,o4)`

### 観測上位 3

- 構成経路: `nsquare(i,a)->l -> psquare(i,h)->m`
- 全演繹: 9079
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o3,o4,o3,t)`
  - `para(o3,o4,o4,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,o3)`
  - `cyclic(?A,?B,o3,o4)`
  - `cong(?A,?B,o3,o4)`
  - `para(o3,t,o4,t)`
  - `midp(o4,?A,?B)`
  - `circle(o4,?A,?B,o3)`
  - `cyclic(?A,?B,o3,t)`
  - `cong(?A,?B,o3,t)`
  - `midp(t,o3,o4)`

## 2023VietnamTSTp3

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 12.796110799999951
- 入力: `681603c371620e379a6f6a685ad88c54e9aa663f7bc151e235fdc6b02818b94e`

```text
a b c = triangle a b c; o = circumcenter o a b c; e = foot e b a c; f = foot f c a b; h = on_line h b e, on_line h c f; m = midpoint m a h; k = foot k h e f; p = on_circle p o a; q = on_circle q o a, on_pline q p b c; o1 = circumcenter o1 c q e; o2 = circumcenter o2 b p f; x = on_tline x e o1 e, on_tline x f o2 f ? coll k m x
```

### 観測上位 1

- 構成経路: `intersection_lt(k,m,a,e,h)->d -> nsquare(e,b)->g`
- 全演繹: 6246
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k,m,k,x)`
  - `para(k,m,m,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,k)`
  - `cyclic(?A,?B,k,m)`
  - `cong(?A,?B,k,m)`
  - `para(k,x,m,x)`
  - `midp(m,?A,?B)`
  - `circle(m,?A,?B,k)`
  - `cyclic(?A,?B,k,x)`
  - `cong(?A,?B,k,x)`
  - `midp(x,k,m)`

### 観測上位 2

- 構成経路: `intersection_lt(k,m,a,e,h)->d -> psquare(e,b)->g`
- 全演繹: 6246
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k,m,k,x)`
  - `para(k,m,m,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,k)`
  - `cyclic(?A,?B,k,m)`
  - `cong(?A,?B,k,m)`
  - `para(k,x,m,x)`
  - `midp(m,?A,?B)`
  - `circle(m,?A,?B,k)`
  - `cyclic(?A,?B,k,x)`
  - `cong(?A,?B,k,x)`
  - `midp(x,k,m)`

### 観測上位 3

- 構成経路: `intersection_lt(k,m,a,e,h)->d -> lc_tangent(e,b)->g`
- 全演繹: 6208
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(k,m,k,x)`
  - `para(k,m,m,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,k)`
  - `cyclic(?A,?B,k,m)`
  - `cong(?A,?B,k,m)`
  - `para(k,x,m,x)`
  - `midp(m,?A,?B)`
  - `circle(m,?A,?B,k)`
  - `cyclic(?A,?B,k,x)`
  - `cong(?A,?B,k,x)`
  - `midp(x,k,m)`

## 2024ELMOSLp1

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 11.582449900000938
- 入力: `5e361894f697e79af3d28ffe0a20d267d604b121ad68d89e8aefcc71401f0a09`

```text
a b c d = quadrangle a b c d; e = on_line e a c, on_line e b d; p = on_line p a b, on_circum p a d e; q = on_line q a b, on_circum q b c e; r = on_line r a d, on_circum r a c p; s = on_line s b c, on_circum s b d q ? cyclic a b r s
```

### 観測上位 1

- 構成経路: `circle(a,b,c)->f -> orthocenter(a,e,f)->g`
- 全演繹: 1774
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,r,a,s,b,r,b,s)`
  - `ncoll(a,b,r,s)`
  - `eqangle(a,b,a,s,b,r,r,s)`
  - `eqangle(a,b,a,r,b,s,r,s)`

### 観測上位 2

- 構成経路: `intersection_lp(a,b,c,a,r)->f -> intersection_lp(a,b,s,a,c)->g`
- 全演繹: 2638
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,r,a,s,b,r,b,s)`
  - `ncoll(a,b,r,s)`
  - `eqangle(a,b,a,s,b,r,r,s)`
  - `eqangle(a,b,a,r,b,s,r,s)`

### 観測上位 3

- 構成経路: `intersection_lp(a,b,c,a,r)->f -> intersection_lt(a,b,s,a,b)->g`
- 全演繹: 2473
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,r,a,s,b,r,b,s)`
  - `ncoll(a,b,r,s)`
  - `eqangle(a,b,a,s,b,r,r,s)`
  - `eqangle(a,b,a,r,b,s,r,s)`

## 2024KoMaLA877

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 6.170807099999365
- 入力: `e944080707f05db3976832384ff5c08303a881a3e72359175b8164661a999925`

```text
t1 t2 t3 = triangle t1 t2 t3; i = circumcenter i t1 t2 t3; t4 = on_circle t4 i t1; a = on_tline a t1 i t1, on_tline a t2 i t2; b = on_tline b t2 i t2, on_tline b t3 i t3; c = on_tline c t3 i t3, on_tline c t4 i t4; d = on_tline d t1 i t1, on_tline d t4 i t4; t5 = on_circle t5 i t1, on_tline t5 i a c; p = on_tline p t5 i t5, on_line p b d; t = reflect t t5 i p; o = circumcenter o a t c ? coll i o t
```

### 観測上位 1

- 構成経路: `nsquare(t1,i)->e -> intersection_cc(i,t1,e)->f`
- 全演繹: 4495
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(i,o,i,t)`
  - `para(i,o,o,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,i)`
  - `cyclic(?A,?B,i,o)`
  - `cong(?A,?B,i,o)`
  - `para(i,t,o,t)`
  - `midp(o,?A,?B)`
  - `circle(o,?A,?B,i)`
  - `cyclic(?A,?B,i,t)`
  - `cong(?A,?B,i,t)`
  - `midp(t,i,o)`

### 観測上位 2

- 構成経路: `nsquare(t1,i)->e -> nsquare(i,e)->f`
- 全演繹: 4495
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(i,o,i,t)`
  - `para(i,o,o,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,i)`
  - `cyclic(?A,?B,i,o)`
  - `cong(?A,?B,i,o)`
  - `para(i,t,o,t)`
  - `midp(o,?A,?B)`
  - `circle(o,?A,?B,i)`
  - `cyclic(?A,?B,i,t)`
  - `cong(?A,?B,i,t)`
  - `midp(t,i,o)`

### 観測上位 3

- 構成経路: `lc_tangent(t1,i)->e -> intersection_cc(i,t1,e)->f`
- 全演繹: 4321
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(i,o,i,t)`
  - `para(i,o,o,t)`
  - `midp(t,?A,?B)`
  - `circle(t,?A,?B,i)`
  - `cyclic(?A,?B,i,o)`
  - `cong(?A,?B,i,o)`
  - `para(i,t,o,t)`
  - `midp(o,?A,?B)`
  - `circle(o,?A,?B,i)`
  - `cyclic(?A,?B,i,t)`
  - `cong(?A,?B,i,t)`
  - `midp(t,i,o)`

## 2024PlanetCupp10

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 16.815844599999764
- 入力: `5ea9e4f1a8b2c50e63bc5ca93177f43097991a738a4846be8e6da6811955c718`

```text
a b c = triangle a b c; d = foot d a b c; e = foot e b a c; f = foot f c a b; d1 = foot d1 d e f; e1 = foot e1 e d f; f1 = foot f1 f d e; n1 = circumcenter n1 d e f; m = midpoint m b c; j = on_line j e1 f1, on_line j b c; k = on_line k d1 n1, on_line k b c; o = circumcenter o a j k; t = on_line t a m, on_circle t o a; p = on_line p a m, on_line p e f; q = on_line q t k, on_line q a j ? perp m o p q
```

### 観測上位 1

- 構成経路: `reflect(m,p,e)->g -> midpoint(m,g)->h`
- 全演繹: 16167
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `lequation(1/1,m,p,*,m,p,1/1,o,q,*,o,q,-1/1,m,q,*,m,q,-1/1,o,p,*,o,p,0)`
  - `lequation(1/1,m,q,*,m,q,1/1,o,p,*,o,p,-1/1,m,p,*,m,p,-1/1,o,q,*,o,q,0)`
  - `lequation(1/1,o,p,*,o,p,1/1,m,q,*,m,q,-1/1,o,q,*,o,q,-1/1,m,p,*,m,p,0)`
  - `perp(?C,?D,m,o)`
  - `para(?C,?D,p,q)`
  - `lequation(1/1,o,q,*,o,q,1/1,m,p,*,m,p,-1/1,o,p,*,o,p,-1/1,m,q,*,m,q,0)`
  - `lequation(1/1,p,m,*,p,m,1/1,q,o,*,q,o,-1/1,p,o,*,p,o,-1/1,q,m,*,q,m,0)`
  - `lequation(1/1,q,m,*,q,m,1/1,p,o,*,p,o,-1/1,q,o,*,q,o,-1/1,p,m,*,p,m,0)`
  - `lequation(1/1,p,o,*,p,o,1/1,q,m,*,q,m,-1/1,p,m,*,p,m,-1/1,q,o,*,q,o,0)`
  - `lequation(1/1,q,o,*,q,o,1/1,p,m,*,p,m,-1/1,q,m,*,q,m,-1/1,p,o,*,p,o,0)`
  - `perp(m,p,o,q)`
  - `perp(m,q,o,p)`

### 観測上位 2

- 構成経路: `foot(m,p,e)->g -> reflect(m,p,g)->h`
- 全演繹: 16182
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `lequation(1/1,m,p,*,m,p,1/1,o,q,*,o,q,-1/1,m,q,*,m,q,-1/1,o,p,*,o,p,0)`
  - `lequation(1/1,m,q,*,m,q,1/1,o,p,*,o,p,-1/1,m,p,*,m,p,-1/1,o,q,*,o,q,0)`
  - `lequation(1/1,o,p,*,o,p,1/1,m,q,*,m,q,-1/1,o,q,*,o,q,-1/1,m,p,*,m,p,0)`
  - `perp(?C,?D,m,o)`
  - `para(?C,?D,p,q)`
  - `lequation(1/1,o,q,*,o,q,1/1,m,p,*,m,p,-1/1,o,p,*,o,p,-1/1,m,q,*,m,q,0)`
  - `lequation(1/1,p,m,*,p,m,1/1,q,o,*,q,o,-1/1,p,o,*,p,o,-1/1,q,m,*,q,m,0)`
  - `lequation(1/1,q,m,*,q,m,1/1,p,o,*,p,o,-1/1,q,o,*,q,o,-1/1,p,m,*,p,m,0)`
  - `lequation(1/1,p,o,*,p,o,1/1,q,m,*,q,m,-1/1,p,m,*,p,m,-1/1,q,o,*,q,o,0)`
  - `lequation(1/1,q,o,*,q,o,1/1,p,m,*,p,m,-1/1,q,m,*,q,m,-1/1,p,o,*,p,o,0)`
  - `perp(m,p,o,q)`
  - `perp(m,q,o,p)`

### 観測上位 3

- 構成経路: `foot(m,p,e)->g -> on_tline(m,p,g)->h`
- 全演繹: 14449
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `lequation(1/1,m,p,*,m,p,1/1,o,q,*,o,q,-1/1,m,q,*,m,q,-1/1,o,p,*,o,p,0)`
  - `lequation(1/1,m,q,*,m,q,1/1,o,p,*,o,p,-1/1,m,p,*,m,p,-1/1,o,q,*,o,q,0)`
  - `lequation(1/1,o,p,*,o,p,1/1,m,q,*,m,q,-1/1,o,q,*,o,q,-1/1,m,p,*,m,p,0)`
  - `perp(?C,?D,m,o)`
  - `para(?C,?D,p,q)`
  - `lequation(1/1,o,q,*,o,q,1/1,m,p,*,m,p,-1/1,o,p,*,o,p,-1/1,m,q,*,m,q,0)`
  - `lequation(1/1,p,m,*,p,m,1/1,q,o,*,q,o,-1/1,p,o,*,p,o,-1/1,q,m,*,q,m,0)`
  - `lequation(1/1,q,m,*,q,m,1/1,p,o,*,p,o,-1/1,q,o,*,q,o,-1/1,p,m,*,p,m,0)`
  - `lequation(1/1,p,o,*,p,o,1/1,q,m,*,q,m,-1/1,p,m,*,p,m,-1/1,q,o,*,q,o,0)`
  - `lequation(1/1,q,o,*,q,o,1/1,p,m,*,p,m,-1/1,q,m,*,q,m,-1/1,p,o,*,p,o,0)`
  - `perp(m,p,o,q)`
  - `perp(m,q,o,p)`

## 2024VietnamTSTp5

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 911.9319239000033
- 入力: `914aa1e9f24f5c7657c27ede60356db8a1007b653d500cbffee18e2f0b4e715f`

```text
a b c = triangle a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; o = circumcenter o a b c; m = on_line m e f, on_circle m o a; s = on_tline s m o m, on_tline s a o a; t = on_tline t b o b, on_tline t c o c; j = on_line j t i, on_line j o a ? eqangle a s j s i s s t
```

### 観測上位 1

- 構成経路: `midpoint(f,e)->g -> between_bound(a,g)->h`
- 全演繹: 4186
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `simtri(a,s,i,j,s,t)`
  - `diff(a,i,s)`
  - `diff(j,s,t)`
  - `simtri(a,s,j,i,s,t)`
  - `diff(a,j,s)`
  - `diff(i,s,t)`
  - `simtri(i,s,a,t,s,j)`
  - `eqangle(?E,?F,?G,?H,a,s,i,s)`
  - `eqangle(?E,?F,?G,?H,j,s,s,t)`
  - `simtri(j,s,a,t,s,i)`
  - `simtri(i,s,t,a,s,j)`
  - `simtri(j,s,t,a,s,i)`

### 観測上位 2

- 構成経路: `midpoint(f,e)->g -> incenter(s,a,m)->h`
- 全演繹: 4152
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `simtri(a,s,i,j,s,t)`
  - `diff(a,i,s)`
  - `diff(j,s,t)`
  - `simtri(a,s,j,i,s,t)`
  - `diff(a,j,s)`
  - `diff(i,s,t)`
  - `simtri(i,s,a,t,s,j)`
  - `eqangle(?E,?F,?G,?H,a,s,i,s)`
  - `eqangle(?E,?F,?G,?H,j,s,s,t)`
  - `simtri(j,s,a,t,s,i)`
  - `simtri(i,s,t,a,s,j)`
  - `simtri(j,s,t,a,s,i)`

### 観測上位 3

- 構成経路: `midpoint(f,e)->g -> excenter(s,a,m)->h`
- 全演繹: 4151
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `simtri(a,s,i,j,s,t)`
  - `diff(a,i,s)`
  - `diff(j,s,t)`
  - `simtri(a,s,j,i,s,t)`
  - `diff(a,j,s)`
  - `diff(i,s,t)`
  - `simtri(i,s,a,t,s,j)`
  - `eqangle(?E,?F,?G,?H,a,s,i,s)`
  - `eqangle(?E,?F,?G,?H,j,s,s,t)`
  - `simtri(j,s,a,t,s,i)`
  - `simtri(i,s,t,a,s,j)`
  - `simtri(j,s,t,a,s,i)`

## 2025KoeraFinalRoundp3

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 100
- 経過秒: 3.0405056000017794
- 入力: `3b6f52e2a445e54c37b978012fa34dc1bca525f0acfdb924178e9ef024fd9b5a`

```text
a b c = triangle a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; p = on_line p a d, on_line p b e; o1 = circumcenter o1 d i p; o2 = circumcenter o2 e i p; o3 = circumcenter o3 f i p; q = on_tline q d o1 d, on_tline q e o2 e ? perp f o3 f q
```

### 観測上位 1

- 構成経路: `intersection_lt(f,o3,i,f,o3)->g -> intersection_lt(f,o3,a,f,o3)->h`
- 全演繹: 2804
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `perp(f,q,g,o3)`
  - `perp(f,q,h,o3)`
  - `circle(?O,o3,f,q)`
  - `coll(?O,o3,q)`
  - `circle(?O,q,f,o3)`
  - `perp(?C,?D,f,o3)`
  - `para(?C,?D,f,q)`
  - `lequation(1/1,f,q,*,f,q,1/1,o3,f,*,o3,f,-1/1,f,f,*,f,f,-1/1,o3,q,*,o3,q,0)`
  - `lequation(1/1,o3,q,*,o3,q,1/1,f,f,*,f,f,-1/1,o3,f,*,o3,f,-1/1,f,q,*,f,q,0)`

### 観測上位 2

- 構成経路: `intersection_lt(f,o3,i,f,o3)->g -> intersection_tt(f,o3,q,i,f,o3)->h`
- 全演繹: 2623
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `perp(f,q,g,o3)`
  - `circle(?O,o3,f,q)`
  - `coll(?O,o3,q)`
  - `circle(?O,q,f,o3)`
  - `lequation(1/1,f,q,*,f,q,1/1,o3,f,*,o3,f,-1/1,f,f,*,f,f,-1/1,o3,q,*,o3,q,0)`
  - `perp(?C,?D,f,o3)`
  - `para(?C,?D,f,q)`
  - `lequation(1/1,o3,q,*,o3,q,1/1,f,f,*,f,f,-1/1,o3,f,*,o3,f,-1/1,f,q,*,f,q,0)`
  - `lequation(1/1,f,o3,*,f,o3,1/1,q,f,*,q,f,-1/1,f,f,*,f,f,-1/1,q,o3,*,q,o3,0)`
  - `lequation(1/1,q,o3,*,q,o3,1/1,f,f,*,f,f,-1/1,q,f,*,q,f,-1/1,f,o3,*,f,o3,0)`
  - `para(f,q,g,h)`
  - `para(f,q,g,i)`

### 観測上位 3

- 構成経路: `angle_mirror(f,a,i)->g -> mirror(i,o3)->h`
- 全演繹: 3303
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `lequation(1/1,f,q,*,f,q,1/1,o3,f,*,o3,f,-1/1,f,f,*,f,f,-1/1,o3,q,*,o3,q,0)`
  - `lequation(1/1,o3,q,*,o3,q,1/1,f,f,*,f,f,-1/1,o3,f,*,o3,f,-1/1,f,q,*,f,q,0)`
  - `lequation(1/1,f,o3,*,f,o3,1/1,q,f,*,q,f,-1/1,f,f,*,f,f,-1/1,q,o3,*,q,o3,0)`
  - `circle(?O,o3,f,q)`
  - `coll(?O,o3,q)`
  - `lequation(1/1,q,o3,*,q,o3,1/1,f,f,*,f,f,-1/1,q,f,*,q,f,-1/1,f,o3,*,f,o3,0)`
  - `perp(f,o3,f,q)`
  - `perp(f,f,o3,q)`
  - `circle(?O,q,f,o3)`
  - `lequation(1/1,f,f,*,f,f,1/1,o3,q,*,o3,q,-1/1,f,q,*,f,q,-1/1,o3,f,*,o3,f,0)`
  - `ncoll(f,f,o3)`
  - `perp(?C,?D,f,o3)`

## ShuZhiMiGeo128

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 38.17040139999881
- 入力: `2fd54fc19563bb673aee445aab1fda0817d5ca35c97dc11d19d3c5c95a115331`

```text
a b c = triangle a b c; p = free p; d = on_line d a p, on_line d b c; e = on_line e b p, on_line e a c; f = on_line f c p, on_line f a b; o1 = circumcenter o1 a e f; o2 = circumcenter o2 b d f; q = on_circle q o1 a, on_circle q o2 b; r = on_line r p q; j = on_line j a r, on_circle j o1 a; k = on_line k b r, on_circle k o2 b; o3 = circumcenter o3 c d e; l = on_line l c r, on_circle l o3 c; o4 = circumcenter o4 a j d; o5 = circumcenter o5 b k e; t = on_circle t o4 a, on_circle t o5 b ? cyclic c f l t
```

### 観測上位 1

- 構成経路: `shift(c,a,e)->g -> intersection_lc(c,f,g)->h`
- 全演繹: 7912
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(c,l,c,t,f,l,f,t)`
  - `ncoll(c,f,l,t)`
  - `eqangle(c,f,c,t,f,l,l,t)`
  - `eqangle(c,f,c,l,f,t,l,t)`

### 観測上位 2

- 構成経路: `angle_mirror(c,a,e)->g -> intersection_lc(c,f,g)->h`
- 全演繹: 7895
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(c,l,c,t,f,l,f,t)`
  - `ncoll(c,f,l,t)`
  - `eqangle(c,f,c,t,f,l,l,t)`
  - `eqangle(c,f,c,l,f,t,l,t)`

### 観測上位 3

- 構成経路: `on_pline(c,a,e)->g -> intersection_lc(c,f,g)->h`
- 全演繹: 7895
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(c,l,c,t,f,l,f,t)`
  - `ncoll(c,f,l,t)`
  - `eqangle(c,f,c,t,f,l,l,t)`
  - `eqangle(c,f,c,l,f,t,l,t)`

## ShuZhiMiGeo309

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 124
- 経過秒: 178.04349640000146
- 入力: `b194a2552972b6d2ecd06aeecb16787300d1148a403dda03f54497cd2e87906e`

```text
a b c = triangle a b c; i = incenter i a b c; i1 = excenter i1 a b c; i2 = excenter i2 b c a; i3 = excenter i3 c a b; a1 = foot a1 i1 a b; a2 = foot a2 i1 a c; b1 = foot b1 i2 b c; b2 = foot b2 i2 b a; c1 = foot c1 i3 c a; c2 = foot c2 i3 c b; d = on_line d b1 b2, on_line d c1 c2; e = on_line e a1 a2, on_line e c1 c2; f = on_line f a1 a2, on_line f b1 b2; o1 = circumcenter o1 d e f; x1 = on_circle x1 o1 d, on_circle x1 i1 a1; x2 = on_circle x2 o1 d, on_circle x2 i1 a1; y1 = on_circle y1 o1 d, on_circle y1 i2 b1; y2 = on_circle y2 o1 d, on_circle y2 i2 b1; z1 = on_circle z1 o1 d, on_circle z1 i3 c1; z2 = on_circle z2 o1 d, on_circle z2 i3 c1; x = on_line x y1 y2, on_line x z1 z2; y = on_line y x1 x2, on_line y z1 z2; z = on_line z x1 x2, on_line z y1 y2; o2 = circumcenter o2 x y z ? coll i o1 o2
```

### 観測上位 1

- 構成経路: `foot(i,d,b2)->g -> intersection_lt(i,o1,d,i,b)->h`
- 全演繹: 50348
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(i,o1,i,o2)`
  - `para(i,o1,o1,o2)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,i)`
  - `cyclic(?A,?B,i,o1)`
  - `cong(?A,?B,i,o1)`
  - `para(i,o2,o1,o2)`
  - `midp(o1,?A,?B)`
  - `circle(o1,?A,?B,i)`
  - `cyclic(?A,?B,i,o2)`
  - `cong(?A,?B,i,o2)`
  - `midp(o2,i,o1)`

### 観測上位 2

- 構成経路: `foot(i,d,b2)->g -> foot(i,d,c1)->h`
- 全演繹: 53131
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(i,o1,i,o2)`
  - `para(i,o1,o1,o2)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,i)`
  - `cyclic(?A,?B,i,o1)`
  - `cong(?A,?B,i,o1)`
  - `para(i,o2,o1,o2)`
  - `midp(o1,?A,?B)`
  - `circle(o1,?A,?B,i)`
  - `cyclic(?A,?B,i,o2)`
  - `cong(?A,?B,i,o2)`
  - `midp(o2,i,o1)`

### 観測上位 3

- 構成経路: `foot(i,d,b2)->g -> intersection_lc(i,o1,g)->h`
- 全演繹: 49266
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(i,o1,i,o2)`
  - `para(i,o1,o1,o2)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,i)`
  - `cyclic(?A,?B,i,o1)`
  - `cong(?A,?B,i,o1)`
  - `para(i,o2,o1,o2)`
  - `midp(o1,?A,?B)`
  - `circle(o1,?A,?B,i)`
  - `cyclic(?A,?B,i,o2)`
  - `cong(?A,?B,i,o2)`
  - `midp(o2,i,o1)`

## ShuZhiMiGeo489

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 112
- 経過秒: 13.636455599998953
- 入力: `76df24bed86e7b0a603c7e07dc7748a876c2dab8b93d19c068a4b12d2d5fedae`

```text
a b c = triangle a b c; o = circumcenter o a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; h = reflect h d e f; m = on_line m o i, on_circle m o a; t = on_line t i o, on_line t b c; q = on_line q a t, on_circle q o a; o1 = circumcenter o1 q m h; y = on_line y m a, on_circle y o1 q; y1 = reflect y1 y e f ? coll b c y1
```

### 観測上位 1

- 構成経路: `reflect(b,c,i)->g -> angle_mirror(b,c,t)->j`
- 全演繹: 6656
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(b,c,b,y1)`
  - `para(b,c,c,y1)`
  - `midp(y1,?A,?B)`
  - `circle(y1,?A,?B,b)`
  - `cyclic(?A,?B,b,c)`
  - `cong(?A,?B,b,c)`
  - `para(b,y1,c,y1)`
  - `midp(c,?A,?B)`
  - `circle(c,?A,?B,b)`
  - `cyclic(?A,?B,b,y1)`
  - `cong(?A,?B,b,y1)`
  - `midp(y1,b,c)`

### 観測上位 2

- 構成経路: `angle_mirror(b,c,i)->g -> shift(b,c,t)->j`
- 全演繹: 6232
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(b,c,b,y1)`
  - `para(b,c,c,y1)`
  - `midp(y1,?A,?B)`
  - `circle(y1,?A,?B,b)`
  - `cyclic(?A,?B,b,c)`
  - `cong(?A,?B,b,c)`
  - `para(b,y1,c,y1)`
  - `midp(c,?A,?B)`
  - `circle(c,?A,?B,b)`
  - `cyclic(?A,?B,b,y1)`
  - `cong(?A,?B,b,y1)`
  - `midp(y1,b,c)`

### 観測上位 3

- 構成経路: `angle_mirror(b,c,i)->g -> angle_mirror(b,c,t)->j`
- 全演繹: 6086
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(b,c,b,y1)`
  - `para(b,c,c,y1)`
  - `midp(y1,?A,?B)`
  - `circle(y1,?A,?B,b)`
  - `cyclic(?A,?B,b,c)`
  - `cong(?A,?B,b,c)`
  - `para(b,y1,c,y1)`
  - `midp(c,?A,?B)`
  - `circle(c,?A,?B,b)`
  - `cyclic(?A,?B,b,y1)`
  - `cong(?A,?B,b,y1)`
  - `midp(y1,b,c)`

## ShuZhiMiGeo635

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 101
- 経過秒: 41.96892849999858
- 入力: `9c597dd3fb0859eb75c430355ada2c5ec39832d808b20837d078c25a6fe18315`

```text
a b c = triangle a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; k = on_line k a d, on_line k b e; o = circumcenter o a b c; x = on_line x a k, on_circle x o a; y = on_line y b k, on_circle y o a; z = on_line z c k, on_circle z o a; o1 = circumcenter o1 y k z; o2 = circumcenter o2 z k x; o3 = circumcenter o3 x k y; m1 m2 m3 g = centroid m1 m2 m3 g o1 o2 o3 ? coll g i k
```

### 観測上位 1

- 構成経路: `midpoint(k,x)->h -> shift(k,a,h)->j`
- 全演繹: 15497
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(g,i,g,k)`
  - `para(g,i,i,k)`
  - `midp(k,?A,?B)`
  - `circle(k,?A,?B,g)`
  - `cyclic(?A,?B,g,i)`
  - `cong(?A,?B,g,i)`
  - `para(g,k,i,k)`
  - `midp(i,?A,?B)`
  - `circle(i,?A,?B,g)`
  - `cyclic(?A,?B,g,k)`
  - `cong(?A,?B,g,k)`
  - `midp(k,g,i)`

### 観測上位 2

- 構成経路: `midpoint(k,x)->h -> angle_bisector(k,a,h)->j`
- 全演繹: 15458
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(g,i,g,k)`
  - `para(g,i,i,k)`
  - `midp(k,?A,?B)`
  - `circle(k,?A,?B,g)`
  - `cyclic(?A,?B,g,i)`
  - `cong(?A,?B,g,i)`
  - `para(g,k,i,k)`
  - `midp(i,?A,?B)`
  - `circle(i,?A,?B,g)`
  - `cyclic(?A,?B,g,k)`
  - `cong(?A,?B,g,k)`
  - `midp(k,g,i)`

### 観測上位 3

- 構成経路: `midpoint(k,x)->h -> angle_mirror(k,a,h)->j`
- 全演繹: 15458
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(g,i,g,k)`
  - `para(g,i,i,k)`
  - `midp(k,?A,?B)`
  - `circle(k,?A,?B,g)`
  - `cyclic(?A,?B,g,i)`
  - `cong(?A,?B,g,i)`
  - `para(g,k,i,k)`
  - `midp(i,?A,?B)`
  - `circle(i,?A,?B,g)`
  - `cyclic(?A,?B,g,k)`
  - `cong(?A,?B,g,k)`
  - `midp(k,g,i)`

