# HAGeo current rerun: unresolved dossiers

## 判定規約

- `completed_unsolved` は不正解ではなく、今回の有限探索で証明書が閉じなかったことだけを表す。
- `right_censored_timeout` は時間打切りであり、数学的な失敗判定には使わない。
- 原因名は推測せず、実際の補助構成、証明DAG、未充足前提だけを記録する。

## 集計

- 未証明 dossier: 53問
- 探索完了・証明書なし: 52問
- 時間打切り: 1問

## 2000USATSTp2

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 112.21900259999529
- 入力: `af5e6aaa1da49c9eee9b2f337683fe0059ff8dc52731796a66ed9b6524fe2c19`

```text
a b c = triangle a b c; d = on_circum d a b c; p = on_line p a c, on_line p b d; e = foot e p a b; f = foot f p c d; m = midpoint m a d; n = midpoint n b c ? perp e f m n
```

### 観測上位 1

- 構成経路: `intersection_cc(e,a,p)->g`
- 全演繹: 1442
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `lequation(1/1,e,m,*,e,m,1/1,f,n,*,f,n,-1/1,e,n,*,e,n,-1/1,f,m,*,f,m,0)`
  - `lequation(1/1,e,n,*,e,n,1/1,f,m,*,f,m,-1/1,e,m,*,e,m,-1/1,f,n,*,f,n,0)`
  - `lequation(1/1,f,m,*,f,m,1/1,e,n,*,e,n,-1/1,f,n,*,f,n,-1/1,e,m,*,e,m,0)`
  - `perp(?C,?D,e,f)`
  - `para(?C,?D,m,n)`
  - `lequation(1/1,f,n,*,f,n,1/1,e,m,*,e,m,-1/1,f,m,*,f,m,-1/1,e,n,*,e,n,0)`
  - `lequation(1/1,m,e,*,m,e,1/1,n,f,*,n,f,-1/1,m,f,*,m,f,-1/1,n,e,*,n,e,0)`
  - `lequation(1/1,n,e,*,n,e,1/1,m,f,*,m,f,-1/1,n,f,*,n,f,-1/1,m,e,*,m,e,0)`
  - `lequation(1/1,m,f,*,m,f,1/1,n,e,*,n,e,-1/1,m,e,*,m,e,-1/1,n,f,*,n,f,0)`
  - `lequation(1/1,n,f,*,n,f,1/1,m,e,*,m,e,-1/1,n,e,*,n,e,-1/1,m,f,*,m,f,0)`
  - `perp(e,m,f,n)`
  - `perp(e,n,f,m)`

### 観測上位 2

- 構成経路: `shift(e,a,b)->g`
- 全演繹: 1325
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `lequation(1/1,e,m,*,e,m,1/1,f,n,*,f,n,-1/1,e,n,*,e,n,-1/1,f,m,*,f,m,0)`
  - `lequation(1/1,e,n,*,e,n,1/1,f,m,*,f,m,-1/1,e,m,*,e,m,-1/1,f,n,*,f,n,0)`
  - `lequation(1/1,f,m,*,f,m,1/1,e,n,*,e,n,-1/1,f,n,*,f,n,-1/1,e,m,*,e,m,0)`
  - `perp(?C,?D,e,f)`
  - `para(?C,?D,m,n)`
  - `lequation(1/1,f,n,*,f,n,1/1,e,m,*,e,m,-1/1,f,m,*,f,m,-1/1,e,n,*,e,n,0)`
  - `lequation(1/1,m,e,*,m,e,1/1,n,f,*,n,f,-1/1,m,f,*,m,f,-1/1,n,e,*,n,e,0)`
  - `lequation(1/1,n,e,*,n,e,1/1,m,f,*,m,f,-1/1,n,f,*,n,f,-1/1,m,e,*,m,e,0)`
  - `lequation(1/1,m,f,*,m,f,1/1,n,e,*,n,e,-1/1,m,e,*,m,e,-1/1,n,f,*,n,f,0)`
  - `lequation(1/1,n,f,*,n,f,1/1,m,e,*,m,e,-1/1,n,e,*,n,e,-1/1,m,f,*,m,f,0)`
  - `perp(e,m,f,n)`
  - `perp(e,n,f,m)`

### 観測上位 3

- 構成経路: `angle_mirror(e,a,b)->g`
- 全演繹: 1304
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `lequation(1/1,e,m,*,e,m,1/1,f,n,*,f,n,-1/1,e,n,*,e,n,-1/1,f,m,*,f,m,0)`
  - `lequation(1/1,e,n,*,e,n,1/1,f,m,*,f,m,-1/1,e,m,*,e,m,-1/1,f,n,*,f,n,0)`
  - `lequation(1/1,f,m,*,f,m,1/1,e,n,*,e,n,-1/1,f,n,*,f,n,-1/1,e,m,*,e,m,0)`
  - `perp(?C,?D,e,f)`
  - `para(?C,?D,m,n)`
  - `lequation(1/1,f,n,*,f,n,1/1,e,m,*,e,m,-1/1,f,m,*,f,m,-1/1,e,n,*,e,n,0)`
  - `lequation(1/1,m,e,*,m,e,1/1,n,f,*,n,f,-1/1,m,f,*,m,f,-1/1,n,e,*,n,e,0)`
  - `lequation(1/1,n,e,*,n,e,1/1,m,f,*,m,f,-1/1,n,f,*,n,f,-1/1,m,e,*,m,e,0)`
  - `lequation(1/1,m,f,*,m,f,1/1,n,e,*,n,e,-1/1,m,e,*,m,e,-1/1,n,f,*,n,f,0)`
  - `lequation(1/1,n,f,*,n,f,1/1,m,e,*,m,e,-1/1,n,e,*,n,e,-1/1,m,f,*,m,f,0)`
  - `perp(e,m,f,n)`
  - `perp(e,n,f,m)`

## 2002CTSTp25

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 271.9963839000002
- 入力: `43c4cf0fa5ae166a8cdc389c7aac2c646b23dcfaab5fe6cfd63be9d56cbcf2b6`

```text
a b c d = quadrangle a b c d; e = on_line e a b, on_line e c d; f = on_line f a d, on_line f b c; p = on_line p a c, on_line p b d; o = foot o p e f ? eqangle a o d o b o c o
```

### 観測上位 1

- 構成経路: `intersection_pp(o,a,b,a,d,f)->g`
- 全演繹: 860
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `simtri(a,o,b,d,o,c)`
  - `diff(a,b,o)`
  - `diff(c,d,o)`
  - `simtri(a,o,d,b,o,c)`
  - `diff(a,d,o)`
  - `diff(b,c,o)`
  - `simtri(b,o,a,c,o,d)`
  - `eqangle(?E,?F,?G,?H,a,o,b,o)`
  - `eqangle(?E,?F,?G,?H,d,o,c,o)`
  - `simtri(d,o,a,c,o,b)`
  - `simtri(b,o,c,a,o,d)`
  - `simtri(d,o,c,a,o,b)`

### 観測上位 2

- 構成経路: `intersection_lc(a,b,d)->g`
- 全演繹: 824
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `simtri(a,o,b,d,o,c)`
  - `diff(a,b,o)`
  - `diff(c,d,o)`
  - `simtri(a,o,d,b,o,c)`
  - `diff(a,d,o)`
  - `diff(b,c,o)`
  - `simtri(b,o,a,c,o,d)`
  - `eqangle(?E,?F,?G,?H,a,o,b,o)`
  - `eqangle(?E,?F,?G,?H,d,o,c,o)`
  - `simtri(d,o,a,c,o,b)`
  - `simtri(b,o,c,a,o,d)`
  - `simtri(d,o,c,a,o,b)`

### 観測上位 3

- 構成経路: `angle_bisector(a,b,e)->g`
- 全演繹: 780
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `simtri(a,o,b,d,o,c)`
  - `diff(a,b,o)`
  - `diff(c,d,o)`
  - `simtri(a,o,d,b,o,c)`
  - `diff(a,d,o)`
  - `diff(b,c,o)`
  - `simtri(b,o,a,c,o,d)`
  - `eqangle(?E,?F,?G,?H,a,o,b,o)`
  - `eqangle(?E,?F,?G,?H,d,o,c,o)`
  - `simtri(d,o,a,c,o,b)`
  - `simtri(b,o,c,a,o,d)`
  - `simtri(d,o,c,a,o,b)`

## 2004CTSTp1

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 293.01813939999556
- 入力: `ffc3ab7d19c6bc80bed164731e4bd5c74cbfa33ca2d303e1f5e6e8a4af3b9815`

```text
a b c = triangle a b c; o1 = midpoint o1 a b; o2 = midpoint o2 a c; h = foot h a b c; d = on_line d b c; e = on_circle e o1 a, on_pline e d a c; f = on_circle f o2 a, on_pline f d a b ? cyclic d e f h
```

### 観測上位 1

- 構成経路: `excenter(h,c,o2)->g`
- 全演繹: 2228
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(d,f,d,h,e,f,e,h)`
  - `ncoll(d,e,f,h)`
  - `eqangle(d,e,d,h,e,f,f,h)`
  - `eqangle(d,e,d,f,e,h,f,h)`

### 観測上位 2

- 構成経路: `intersection_cc(h,a,b)->g`
- 全演繹: 2228
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(d,f,d,h,e,f,e,h)`
  - `ncoll(d,e,f,h)`
  - `eqangle(d,e,d,h,e,f,f,h)`
  - `eqangle(d,e,d,f,e,h,f,h)`

### 観測上位 3

- 構成経路: `midpoint(h,a)->g`
- 全演繹: 2110
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(d,f,d,h,e,f,e,h)`
  - `ncoll(d,e,f,h)`
  - `eqangle(d,e,d,h,e,f,f,h)`
  - `eqangle(d,e,d,f,e,h,f,h)`

## 2005CTSTp11b

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 412.84223550000024
- 入力: `c815acaf3c1984b10d69bd4bbd42f4200c335945aee435cd6d4bfa4c3580e4af`

```text
a b c = triangle a b c; o = circumcenter o a b c; p = on_tline p b o b, on_tline p c o c; q = on_tline q a o a, on_tline q c o c; r = on_tline r b o b, on_tline r a o a; d1 = on_line d1 a p, on_line d1 b c; e1 = on_line e1 a c, on_pline e1 d1 a b; f1 = on_line f1 a b, on_pline f1 d1 a c; d2 = on_line d2 b q, on_line d2 a c; e2 = on_line e2 b a, on_pline e2 d2 b c; f2 = on_line f2 b c, on_pline f2 d2 b a; d3 = on_line d3 c r, on_line d3 b a; e3 = on_line e3 c b, on_pline e3 d3 c a; f3 = on_line f3 c a, on_pline f3 d3 c b; a1 = circumcenter a1 f1 b c; b1 = circumcenter b1 f2 a c; c1 = circumcenter c1 f3 a b; x = on_line x a a1, on_line x b b1 ? coll c c1 x
```

### 観測上位 1

- 構成経路: `midpoint(c,b)->d`
- 全演繹: 34530
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(c,c1,c,x)`
  - `para(c,c1,c1,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,c)`
  - `cyclic(?A,?B,c,c1)`
  - `cong(?A,?B,c,c1)`
  - `para(c,x,c1,x)`
  - `midp(c1,?A,?B)`
  - `circle(c1,?A,?B,c)`
  - `cyclic(?A,?B,c,x)`
  - `cong(?A,?B,c,x)`
  - `midp(x,c,c1)`

### 観測上位 2

- 構成経路: `angle_bisector(c,b,e3)->d`
- 全演繹: 32471
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(c,c1,c,x)`
  - `para(c,c1,c1,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,c)`
  - `cyclic(?A,?B,c,c1)`
  - `cong(?A,?B,c,c1)`
  - `para(c,x,c1,x)`
  - `midp(c1,?A,?B)`
  - `circle(c1,?A,?B,c)`
  - `cyclic(?A,?B,c,x)`
  - `cong(?A,?B,c,x)`
  - `midp(x,c,c1)`

### 観測上位 3

- 構成経路: `angle_mirror(c,b,e3)->d`
- 全演繹: 32471
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(c,c1,c,x)`
  - `para(c,c1,c1,x)`
  - `midp(x,?A,?B)`
  - `circle(x,?A,?B,c)`
  - `cyclic(?A,?B,c,c1)`
  - `cong(?A,?B,c,c1)`
  - `para(c,x,c1,x)`
  - `midp(c1,?A,?B)`
  - `circle(c1,?A,?B,c)`
  - `cyclic(?A,?B,c,x)`
  - `cong(?A,?B,c,x)`
  - `midp(x,c,c1)`

## 2007CMOp4

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 67.7110937000034
- 入力: `b1055c07f732fbd60397b2e3ecb855e5fc9c53409c31dcb772977a99927688b9`

```text
a b c = triangle a b c; o = circumcenter o a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; p = on_line p f d, on_line p a c; q = on_line q e d, on_line q a b; m = midpoint m p e; n = midpoint n q f ? perp i o m n
```

### 観測上位 1

- 構成経路: `angle_mirror(i,f,a)->g`
- 全演繹: 4168
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `lequation(1/1,i,m,*,i,m,1/1,o,n,*,o,n,-1/1,i,n,*,i,n,-1/1,o,m,*,o,m,0)`
  - `lequation(1/1,i,n,*,i,n,1/1,o,m,*,o,m,-1/1,i,m,*,i,m,-1/1,o,n,*,o,n,0)`
  - `lequation(1/1,o,m,*,o,m,1/1,i,n,*,i,n,-1/1,o,n,*,o,n,-1/1,i,m,*,i,m,0)`
  - `perp(?C,?D,i,o)`
  - `para(?C,?D,m,n)`
  - `lequation(1/1,o,n,*,o,n,1/1,i,m,*,i,m,-1/1,o,m,*,o,m,-1/1,i,n,*,i,n,0)`
  - `lequation(1/1,m,i,*,m,i,1/1,n,o,*,n,o,-1/1,m,o,*,m,o,-1/1,n,i,*,n,i,0)`
  - `lequation(1/1,n,i,*,n,i,1/1,m,o,*,m,o,-1/1,n,o,*,n,o,-1/1,m,i,*,m,i,0)`
  - `lequation(1/1,m,o,*,m,o,1/1,n,i,*,n,i,-1/1,m,i,*,m,i,-1/1,n,o,*,n,o,0)`
  - `lequation(1/1,n,o,*,n,o,1/1,m,i,*,m,i,-1/1,n,i,*,n,i,-1/1,m,o,*,m,o,0)`
  - `perp(i,m,n,o)`
  - `perp(i,n,m,o)`

### 観測上位 2

- 構成経路: `reflect(i,a,b)->g`
- 全演繹: 4964
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `lequation(1/1,i,m,*,i,m,1/1,o,n,*,o,n,-1/1,i,n,*,i,n,-1/1,o,m,*,o,m,0)`
  - `lequation(1/1,i,n,*,i,n,1/1,o,m,*,o,m,-1/1,i,m,*,i,m,-1/1,o,n,*,o,n,0)`
  - `lequation(1/1,o,m,*,o,m,1/1,i,n,*,i,n,-1/1,o,n,*,o,n,-1/1,i,m,*,i,m,0)`
  - `perp(?C,?D,i,o)`
  - `para(?C,?D,m,n)`
  - `lequation(1/1,o,n,*,o,n,1/1,i,m,*,i,m,-1/1,o,m,*,o,m,-1/1,i,n,*,i,n,0)`
  - `lequation(1/1,m,i,*,m,i,1/1,n,o,*,n,o,-1/1,m,o,*,m,o,-1/1,n,i,*,n,i,0)`
  - `lequation(1/1,n,i,*,n,i,1/1,m,o,*,m,o,-1/1,n,o,*,n,o,-1/1,m,i,*,m,i,0)`
  - `lequation(1/1,m,o,*,m,o,1/1,n,i,*,n,i,-1/1,m,i,*,m,i,-1/1,n,o,*,n,o,0)`
  - `lequation(1/1,n,o,*,n,o,1/1,m,i,*,m,i,-1/1,n,i,*,n,i,-1/1,m,o,*,m,o,0)`
  - `perp(i,m,n,o)`
  - `perp(i,n,m,o)`

### 観測上位 3

- 構成経路: `on_tline(i,a,b)->g`
- 全演繹: 4166
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `lequation(1/1,i,m,*,i,m,1/1,o,n,*,o,n,-1/1,i,n,*,i,n,-1/1,o,m,*,o,m,0)`
  - `lequation(1/1,i,n,*,i,n,1/1,o,m,*,o,m,-1/1,i,m,*,i,m,-1/1,o,n,*,o,n,0)`
  - `lequation(1/1,o,m,*,o,m,1/1,i,n,*,i,n,-1/1,o,n,*,o,n,-1/1,i,m,*,i,m,0)`
  - `perp(?C,?D,i,o)`
  - `para(?C,?D,m,n)`
  - `lequation(1/1,o,n,*,o,n,1/1,i,m,*,i,m,-1/1,o,m,*,o,m,-1/1,i,n,*,i,n,0)`
  - `lequation(1/1,m,i,*,m,i,1/1,n,o,*,n,o,-1/1,m,o,*,m,o,-1/1,n,i,*,n,i,0)`
  - `lequation(1/1,n,i,*,n,i,1/1,m,o,*,m,o,-1/1,n,o,*,n,o,-1/1,m,i,*,m,i,0)`
  - `lequation(1/1,m,o,*,m,o,1/1,n,i,*,n,i,-1/1,m,i,*,m,i,-1/1,n,o,*,n,o,0)`
  - `lequation(1/1,n,o,*,n,o,1/1,m,i,*,m,i,-1/1,n,i,*,n,i,-1/1,m,o,*,m,o,0)`
  - `perp(i,m,n,o)`
  - `perp(i,n,m,o)`

## 2008CTSTp4

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 49.14984430000186
- 入力: `d686ea7386d3183c7ca025fb89fa810be26e061bd7cc87390233168e7fd4a60c`

```text
a b c = triangle a b c; d = on_line d b c; e = on_line e a c; f = on_line f a b, on_line f d e; o1 = circumcenter o1 a e f; o2 = circumcenter o2 b f d; o3 = circumcenter o3 c d e; h = orthocenter h o1 o2 o3 ? coll d e h
```

### 観測上位 1

- 構成経路: `shift(e,d,f)->g`
- 全演繹: 1330
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(d,e,d,h)`
  - `para(d,e,e,h)`
  - `midp(h,?A,?B)`
  - `circle(h,?A,?B,d)`
  - `cyclic(?A,?B,d,e)`
  - `cong(?A,?B,d,e)`
  - `para(d,h,e,h)`
  - `midp(e,?A,?B)`
  - `circle(e,?A,?B,d)`
  - `cyclic(?A,?B,d,h)`
  - `cong(?A,?B,d,h)`
  - `midp(h,d,e)`

### 観測上位 2

- 構成経路: `angle_bisector(e,f,d)->g`
- 全演繹: 1268
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(d,e,d,h)`
  - `para(d,e,e,h)`
  - `midp(h,?A,?B)`
  - `circle(h,?A,?B,d)`
  - `cyclic(?A,?B,d,e)`
  - `cong(?A,?B,d,e)`
  - `para(d,h,e,h)`
  - `midp(e,?A,?B)`
  - `circle(e,?A,?B,d)`
  - `cyclic(?A,?B,d,h)`
  - `cong(?A,?B,d,h)`
  - `midp(h,d,e)`

### 観測上位 3

- 構成経路: `angle_mirror(e,d,f)->g`
- 全演繹: 1268
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(d,e,d,h)`
  - `para(d,e,e,h)`
  - `midp(h,?A,?B)`
  - `circle(h,?A,?B,d)`
  - `cyclic(?A,?B,d,e)`
  - `cong(?A,?B,d,e)`
  - `para(d,h,e,h)`
  - `midp(e,?A,?B)`
  - `circle(e,?A,?B,d)`
  - `cyclic(?A,?B,d,h)`
  - `cong(?A,?B,d,h)`
  - `midp(h,d,e)`

## 2011ARMOg11p8

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 154.53757170000608
- 入力: `6fc2cedc14dccab20ecaedf84f66af2ee6cb483433439a5d0e1ef62b1bf3936f`

```text
a b c = triangle a b c; o = circumcenter o a b c; n = on_circle n o a, on_bline n a c; m = midpoint m a c; i1 = incenter i1 a b m; i2 = incenter i2 c b m ? cyclic b i1 i2 n
```

### 観測上位 1

- 構成経路: `circle(i1,a,m)->d`
- 全演繹: 930
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(b,i2,b,n,i1,i2,i1,n)`
  - `ncoll(b,i1,i2,n)`
  - `eqangle(b,i1,b,n,i1,i2,i2,n)`
  - `eqangle(b,i1,b,i2,i1,n,i2,n)`

### 観測上位 2

- 構成経路: `circumcenter(i1,a,m)->d`
- 全演繹: 930
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(b,i2,b,n,i1,i2,i1,n)`
  - `ncoll(b,i1,i2,n)`
  - `eqangle(b,i1,b,n,i1,i2,i2,n)`
  - `eqangle(b,i1,b,i2,i1,n,i2,n)`

### 観測上位 3

- 構成経路: `intersection_cc(b,i1,a)->d`
- 全演繹: 917
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(b,i2,b,n,i1,i2,i1,n)`
  - `ncoll(b,i1,i2,n)`
  - `eqangle(b,i1,b,n,i1,i2,i2,n)`
  - `eqangle(b,i1,b,i2,i1,n,i2,n)`

## 2011CHNSouthEastMOp4

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 493.91187309999987
- 入力: `1d966dba38350e3735d94e5c0abfb1fe6fef9e28af278af96b5af05b1c073c74`

```text
a b c = triangle a b c; o = circumcenter o a b c; m = on_line m a b; n = on_line n a c, on_line n o m; e = midpoint e n b; f = midpoint f m c ? eqangle a b a c e o f o
```

### 観測上位 1

- 構成経路: `shift(a,b,m)->d`
- 全演繹: 819
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,b,a,n,e,o,f,o)`
  - `eqangle(a,c,a,d,f,o,e,o)`
  - `eqangle(a,c,a,m,f,o,e,o)`

### 観測上位 2

- 構成経路: `intersection_lp(a,o,b,a,c)->d`
- 全演繹: 733
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,b,a,n,e,o,f,o)`
  - `eqangle(a,b,b,d,e,o,f,o)`
  - `eqangle(a,c,a,m,f,o,e,o)`

### 観測上位 3

- 構成経路: `angle_bisector(a,b,m)->d`
- 全演繹: 733
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,b,a,n,e,o,f,o)`
  - `eqangle(a,c,a,d,f,o,e,o)`
  - `eqangle(a,c,a,m,f,o,e,o)`

## 2011CTSTp16

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 60.77574110000569
- 入力: `cf65011e6ea5c17ae051a178ba2488032a75908c707425034dce1ad56177cf66`

```text
a b c = triangle a b c; h = orthocenter h a b c; o = circumcenter o a b c; p = on_circle p o a; m = on_line m p h, on_circle m o a; p1 = foot p1 p b c; p2 = foot p2 p c a; k = on_circle k o a, on_pline k m p1 p2; q = on_circle q o a, on_pline q p b c; j = on_line j b c, on_line j k q ? cong j k j m
```

### 観測上位 1

- 構成経路: `mirror(a,o)->d`
- 全演繹: 6518
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `circle(j,k,a,b)`
  - `circle(j,k,a,c)`
  - `circle(j,k,a,d)`
  - `circle(j,k,a,p)`
  - `circle(j,k,a,q)`
  - `circle(j,k,b,a)`
  - `circle(j,k,b,c)`
  - `circle(j,k,b,d)`
  - `circle(j,k,b,p)`
  - `circle(j,k,b,q)`
  - `circle(j,k,c,a)`
  - `circle(j,k,c,b)`

### 観測上位 2

- 構成経路: `intersection_cc(j,o,b)->d`
- 全演繹: 5420
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `circle(j,k,a,b)`
  - `circle(j,k,a,c)`
  - `circle(j,k,a,d)`
  - `circle(j,k,a,p)`
  - `circle(j,k,a,q)`
  - `circle(j,k,b,a)`
  - `circle(j,k,b,c)`
  - `circle(j,k,b,d)`
  - `circle(j,k,b,p)`
  - `circle(j,k,b,q)`
  - `circle(j,k,c,a)`
  - `circle(j,k,c,b)`

### 観測上位 3

- 構成経路: `circle(m,k,o)->d`
- 全演繹: 4302
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `circle(j,k,a,b)`
  - `circle(j,k,a,c)`
  - `circle(j,k,a,p)`
  - `circle(j,k,m,?C)`
  - `circle(j,k,a,q)`
  - `circle(j,k,b,a)`
  - `circle(j,k,b,c)`
  - `circle(j,m,k,?C)`
  - `circle(j,k,b,p)`
  - `circle(j,k,b,q)`
  - `circle(j,k,c,a)`
  - `circle(j,?A,k,m)`

## 2011G3

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 221.48564669999905
- 入力: `352a7df3ad0cde902c198780b52f69bb8f82f0a72265b61c14223a932fc11f2b`

```text
a b c d = quadrangle a b c d; m1 = midpoint m1 a b; m2 = midpoint m2 c d; e = on_circle e m1 a, on_circle e m2 c; f = on_circle f m1 a, on_circle f m2 c; e1 = foot e1 e a b; e2 = foot e2 e b c; e3 = foot e3 e c d; o_e = circumcenter o_e e1 e2 e3; f1 = foot f1 f c d; f2 = foot f2 f d a; f3 = foot f3 f a b; o_f = circumcenter o_f f1 f2 f3; k1 = on_circle k1 o_e e1, on_circle k1 o_f f1; k2 = on_circle k2 o_e e1, on_circle k2 o_f f1; m = midpoint m e f ? coll k1 k2 m
```

### 観測上位 1

- 構成経路: `intersection_cc(m,e,m1)->g`
- 全演繹: 9806
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

- 構成経路: `psquare(m,e)->g`
- 全演繹: 9541
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

- 構成経路: `nsquare(m,e)->g`
- 全演繹: 9540
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
- 探索候補: 16
- 経過秒: 136.8947113000031
- 入力: `7f5a70aa73dedd5c517c7105806e303e36ed71ddc040d336949486401145533f`

```text
a b c = triangle a b c; i = incenter i a b c; o = circumcenter o a b c; d = on_line d a i, on_circle d o a; e = on_line e b i, on_circle e o b; f = on_line f d e, on_line f a c; g = on_line g d e, on_line g b c; p = on_pline p f a d, on_pline p g b e; k = on_tline k a o a, on_tline k b o b; x = on_line x a e, on_line x b d ? coll k p x
```

### 観測上位 1

- 構成経路: `midpoint(a,c)->h`
- 全演繹: 7698
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

- 構成経路: `incenter(k,a,b)->h`
- 全演繹: 10078
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

- 構成経路: `between_bound(a,x)->h`
- 全演繹: 7061
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
- 探索候補: 16
- 経過秒: 133.48088260000077
- 入力: `6c5de38d6fcf4cf26d85a2212f71f976ade226e254fd38685209903f4c92e7ca`

```text
a b c = triangle a b c; o = circumcenter o a b c; d = on_tline d b o b, on_circle d b c; e = on_tline e c o c, on_circle e c b; f = on_line f a b, on_line f d e; g = on_line g a c, on_line g d e; m = on_line m c f, on_line m b d; n = on_line n c e, on_line n b g ? cong a m a n
```

### 観測上位 1

- 構成経路: `intersection_cc(a,b,o)->h`
- 全演繹: 2592
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

- 構成経路: `reflect(n,a,b)->h`
- 全演繹: 2448
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `cong(a,h,a,m)`
  - `circle(a,m,n,?C)`
  - `circle(a,n,m,?C)`
  - `circle(a,?A,m,n)`
  - `circle(a,?A,n,m)`
  - `perp(?C,n,m,n)`
  - `midp(a,m,?C)`
  - `perp(?C,m,m,n)`
  - `midp(a,n,?C)`
  - `cyclic(?B,h,m,n)`
  - `cong(?B,a,a,m)`
  - `npara(?B,m,h,n)`

### 観測上位 3

- 構成経路: `circumcenter(a,n,b)->h`
- 全演繹: 2430
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `cong(a,m,a,n)`
  - `circle(a,m,n,?C)`
  - `circle(a,n,m,?C)`
  - `circle(a,?A,m,n)`
  - `circle(a,?A,n,m)`
  - `perp(?C,n,m,n)`
  - `midp(a,m,?C)`
  - `perp(?C,m,m,n)`
  - `midp(a,n,?C)`
  - `cyclic(?B,m,n,n)`
  - `cong(?B,a,a,m)`
  - `npara(?B,m,n,n)`

## 2015CTSTp9

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 152.47931480000034
- 入力: `18ec1e5a166809f7b113b976d1ace02431e8e8f716c75b6a72e056bed8cbb5d1`

```text
a b c = triangle a b c; o = circumcenter o a b c; d d1 d2 g = centroid d d1 d2 g a b c; e = on_circle e d b, on_tline e a b c; f = on_line f e g, on_line f o d; k = on_line k b c, on_pline k f o b; l = on_line l b c, on_pline l f o c; m = on_line m a b, on_tline m k b c; n = on_line n a c, on_tline n l b c; o1 = on_bline o1 b c, on_tline o1 b o b; o2 = circumcenter o2 a m n; t = on_circle t o1 b, on_circle t o2 a ? coll o1 o2 t
```

### 観測上位 1

- 構成経路: `intersection_lp(o1,o2,b,c,l)->h`
- 全演繹: 15311
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

- 構成経路: `orthocenter(o1,b,c)->h`
- 全演繹: 17310
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

- 構成経路: `circumcenter(o1,b,c)->h`
- 全演繹: 15737
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
- 探索候補: 14
- 経過秒: 900.2156760999997
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

- 構成経路: `intersection_tt(x,b,c,b,c,o)->d`
- 全演繹: 4217
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `eqangle(b,o,c,o,x,y,x,z)`
  - `eqangle(b,x,c,x,x,y,x,z)`
  - `eqangle(b,d,c,d,x,z,x,y)`

### 観測上位 2

- 構成経路: `orthocenter(b,c,o)->d`
- 全演繹: 4213
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `eqangle(b,o,c,o,x,y,x,z)`
  - `eqangle(b,x,c,x,x,y,x,z)`
  - `eqangle(b,d,c,d,x,z,x,y)`

### 観測上位 3

- 構成経路: `circumcenter(b,c,o)->d`
- 全演繹: 3341
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `eqangle(b,o,c,o,x,y,x,z)`
  - `eqangle(b,x,c,x,x,y,x,z)`

## 2016CGMOp7

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 169.8994187999997
- 入力: `8842d22c252d0002054f8102bebff3304f096dc3925a35904a2378687221933f`

```text
a b c = triangle a b c; i = incenter i a b c; d = foot d i b c; h = foot h a b c; p = on_line p a h, on_line p b i; q = on_line q a h, on_line q c i; o = circumcenter o i p q; l = on_line l a o, on_line l b c; n = on_line n b c, on_circum n a i l ? eqratio b d b n c d c n
```

### 観測上位 1

- 構成経路: `intersection_cc(b,c,i)->e`
- 全演繹: 4626
- ゴール演繹: 0
- 進展DAG枝: 15
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `coll(b,c,d,n)`

### 観測上位 2

- 構成経路: `reflect(c,b,p)->e`
- 全演繹: 3814
- ゴール演繹: 0
- 進展DAG枝: 15
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `coll(b,c,d,n)`

### 観測上位 3

- 構成経路: `orthocenter(b,c,i)->e`
- 全演繹: 4089
- ゴール演繹: 0
- 進展DAG枝: 15
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `coll(b,c,d,n)`

## 2016CTSTp5

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 57.65022200000385
- 入力: `66a7bd8b0292e9316532bb1ca8c5eb8357e3253e20671afd251402f59d5d91b7`

```text
a b c = triangle a b c; d = on_circum d a b c; o = circumcenter o a b c; i = angle_bisector i d a b, angle_bisector i b c d; j = angle_bisector j a b c, angle_bisector j c d a; p = on_line p a b, on_line p i j; r = on_line r c d, on_line r i j; q = on_line q b c, on_line q i j; s = on_line s d a, on_line s i j; m = midpoint m p r; n = midpoint n q s ? perp m o n o
```

### 観測上位 1

- 構成経路: `nsquare(j,b)->e`
- 全演繹: 4298
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

- 構成経路: `psquare(j,b)->e`
- 全演繹: 4298
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

- 構成経路: `lc_tangent(j,b)->e`
- 全演繹: 4281
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

## 2016G5

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 15
- 経過秒: 100.22308579999662
- 入力: `f52cf7a435f95325c601f94330db969aab24502c262a0873d667c76ba3ccd5d1`

```text
a b c = triangle a b c; o = circumcenter o a b c; h = orthocenter h a b c; d = foot d a o h; s = on_bline s a d; x = on_circle x s a, on_line x a b; y = on_circle y s a, on_line y a c; p = foot p a b c; m = midpoint m b c; o1 = circumcenter o1 x s y ? cong o1 p m o1
```

### 観測上位 1

- 構成経路: `eq_triangle(o1,x)->e`
- 全演繹: 2565
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `midp(o1,m,a)`
  - `midp(o1,m,h)`
  - `midp(o1,p,o)`
  - `circle(o1,m,p,?C)`
  - `circle(o1,p,m,?C)`
  - `circle(o1,?A,m,p)`
  - `circle(o1,?A,p,m)`
  - `perp(?C,p,m,p)`
  - `midp(o1,m,?C)`
  - `perp(?C,m,m,p)`
  - `midp(o1,p,?C)`
  - `contri(m,o1,?C,o1,p,?R)`

### 観測上位 2

- 構成経路: `on_circle(o1,x)->e`
- 全演繹: 2513
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `midp(o1,m,a)`
  - `midp(o1,m,h)`
  - `midp(o1,p,o)`
  - `circle(o1,m,p,?C)`
  - `circle(o1,p,m,?C)`
  - `circle(o1,?A,m,p)`
  - `circle(o1,?A,p,m)`
  - `perp(?C,p,m,p)`
  - `midp(o1,m,?C)`
  - `perp(?C,m,m,p)`
  - `midp(o1,p,?C)`
  - `contri(m,o1,?C,o1,p,?R)`

### 観測上位 3

- 構成経路: `shift(o1,c,m)->e`
- 全演繹: 2593
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `midp(o1,m,a)`
  - `midp(o1,m,h)`
  - `midp(o1,p,o)`
  - `circle(o1,m,p,?C)`
  - `cong(c,e,o1,p)`
  - `circle(o1,p,m,?C)`
  - `circle(o1,?A,m,p)`
  - `circle(o1,?A,p,m)`
  - `perp(?C,p,m,p)`
  - `midp(o1,m,?C)`
  - `perp(?C,m,m,p)`
  - `midp(o1,p,?C)`

## 2016USATSTSTp6

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 188.47194459999446
- 入力: `ffd6a2e36a473113e198abd0a21a913f268d19e363530dbdc36aeda3ad36a017`

```text
a b c = triangle a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; k = foot k d e f; o1 = circumcenter o1 a i b; c1 = on_circle c1 o1 a, on_circle c1 i d; c2 = on_circle c2 o1 a, on_circle c2 i d; o2 = circumcenter o2 a i c; b1 = on_circle b1 o2 a, on_circle b1 i d; b2 = on_circle b2 o2 a, on_circle b2 i d; o3 = circumcenter o3 b b1 b2; o4 = circumcenter o4 c c1 c2; p1 = on_circle p1 o3 b, on_circle p1 o4 c; p2 = on_circle p2 o3 b, on_circle p2 o4 c; m = midpoint m d k ? coll m p1 p2
```

### 観測上位 1

- 構成経路: `midpoint(m,d)->g`
- 全演繹: 14018
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

- 構成経路: `mirror(m,d)->g`
- 全演繹: 14025
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

- 構成経路: `between_bound(m,d)->g`
- 全演繹: 13965
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

## 2017CHNSouthEastMOg10p2

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 15
- 経過秒: 80.17758160000085
- 入力: `2f95654e0cfce86e04fddbd92c34c8a3383d59da1ed7fa5f8eca0c2b8121dbf9`

```text
a b c = triangle a b c; d = midpoint d b c; k = midpoint k a d; e = foot e d a b; f = foot f d a c; m = on_line m b c, on_line m k e; n = on_line n b c, on_line n k f; o1 = circumcenter o1 d e m; o2 = circumcenter o2 d f n ? para o1 o2 b c
```

### 観測上位 1

- 構成経路: `circle(c,d,f)->g`
- 全演繹: 5172
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 2
- 未充足前提:
  - `para(b,d,o1,o2)`
  - `para(b,g,o1,o2)`
  - `para(b,m,o1,o2)`
  - `para(b,n,o1,o2)`
  - `para(c,d,o1,o2)`
  - `para(c,g,o1,o2)`
  - `para(c,m,o1,o2)`
  - `para(c,n,o1,o2)`

### 観測上位 2

- 構成経路: `circumcenter(c,d,f)->g`
- 全演繹: 5172
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 2
- 未充足前提:
  - `para(b,d,o1,o2)`
  - `para(b,g,o1,o2)`
  - `para(b,m,o1,o2)`
  - `para(b,n,o1,o2)`
  - `para(c,d,o1,o2)`
  - `para(c,g,o1,o2)`
  - `para(c,m,o1,o2)`
  - `para(c,n,o1,o2)`

### 観測上位 3

- 構成経路: `midpoint(c,d)->g`
- 全演繹: 5172
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 2
- 未充足前提:
  - `para(b,d,o1,o2)`
  - `para(b,g,o1,o2)`
  - `para(b,m,o1,o2)`
  - `para(b,n,o1,o2)`
  - `para(c,d,o1,o2)`
  - `para(c,g,o1,o2)`
  - `para(c,m,o1,o2)`
  - `para(c,n,o1,o2)`

## 2017G3

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 74.86425639999652
- 入力: `f1c772983279f06291edbbcf8115efd293a11688f133f1e4cc630ef8151a6360`

```text
a b c = triangle a b c; o = circumcenter o a b c; h = orthocenter h a b c; p = on_line p o a, on_line p b h; q = on_line q o a, on_line q c h; k = circumcenter k p q h; m = midpoint m b c ? coll a k m
```

### 観測上位 1

- 構成経路: `mirror(a,o)->d`
- 全演繹: 2713
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,k,a,m)`
  - `para(a,k,k,m)`
  - `para(a,m,k,m)`
  - `midp(m,a,k)`
  - `midp(k,a,m)`
  - `midp(m,k,a)`
  - `midp(k,m,a)`
  - `midp(a,k,m)`
  - `midp(a,m,k)`
  - `lequation(1/1,a,k,1/1,k,m,-1/1,a,m,0)`
  - `lequation(1/1,a,m,1/1,m,k,-1/1,a,k,0)`
  - `lequation(1/1,k,a,1/1,a,m,-1/1,k,m,0)`

### 観測上位 2

- 構成経路: `shift(a,o,q)->d`
- 全演繹: 1908
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,k,a,m)`
  - `para(a,k,k,m)`
  - `para(a,m,k,m)`
  - `midp(m,a,k)`
  - `midp(k,a,m)`
  - `midp(m,k,a)`
  - `midp(k,m,a)`
  - `midp(a,k,m)`
  - `midp(a,m,k)`
  - `lequation(1/1,a,k,1/1,k,m,-1/1,a,m,0)`
  - `lequation(1/1,a,m,1/1,m,k,-1/1,a,k,0)`
  - `lequation(1/1,k,a,1/1,a,m,-1/1,k,m,0)`

### 観測上位 3

- 構成経路: `angle_bisector(a,q,o)->d`
- 全演繹: 1892
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,k,a,m)`
  - `para(a,k,k,m)`
  - `para(a,m,k,m)`
  - `midp(m,a,k)`
  - `midp(k,a,m)`
  - `midp(m,k,a)`
  - `midp(k,m,a)`
  - `midp(a,k,m)`
  - `midp(a,m,k)`
  - `lequation(1/1,a,k,1/1,k,m,-1/1,a,m,0)`
  - `lequation(1/1,a,m,1/1,m,k,-1/1,a,k,0)`
  - `lequation(1/1,k,a,1/1,a,m,-1/1,k,m,0)`

## 2017G4

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 137.41504929999792
- 入力: `2488dd6a623c55498616fbb9a4d5adbff86c52fd04804d764df3e3b602f6e5ee`

```text
a b c = triangle a b c; i1 = excenter i1 a b c; d = foot d i1 b c; e = foot e i1 a c; f = foot f i1 a b; o1 = circumcenter o1 a e f; p = on_line p b c, on_circle p o1 a; q = on_line q b c, on_circle q o1 a; m = midpoint m a d; o2 = circumcenter o2 m p q; u = on_circle u o2 m, on_circle u i1 d ? coll i1 o2 u
```

### 観測上位 1

- 構成経路: `midpoint(b,c)->g`
- 全演繹: 5823
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

- 構成経路: `circle(i1,b,c)->g`
- 全演繹: 6352
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

- 構成経路: `circumcenter(i1,b,c)->g`
- 全演繹: 6351
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
- 探索候補: 16
- 経過秒: 265.9250166000056
- 入力: `d99e367d0583ee9a7fa035f7f7d50971f4311b6018876d958947c6a7fedc8572`

```text
a b c = triangle a b c; o = circumcenter o a b c; i = incenter i a b c; d = on_line d a i, on_line d b c; m = on_line m a i, on_circle m o a; k = on_dia k m d, on_circle k o a; s = on_line s m k, on_line s b c; n = midpoint n i s; o1 = circumcenter o1 k i d; o2 = circumcenter o2 m a n; l = on_circle l o1 k, on_circle l o2 m; p = midpoint p i l ? cyclic a b c p
```

### 観測上位 1

- 構成経路: `midpoint(b,c)->e`
- 全演繹: 6903
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

- 構成経路: `intersection_lt(b,a,m,b,c)->e`
- 全演繹: 5828
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

- 構成経路: `on_pline(b,c,d)->e`
- 全演繹: 5715
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,c,a,p,b,c,b,p)`
  - `ncoll(a,b,c,p)`
  - `eqangle(a,b,a,p,b,c,c,p)`
  - `eqangle(a,b,a,c,b,p,c,p)`

## 2018ARMOg11p4

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 57.71033400000306
- 入力: `1af3fb0486b2531b4415ad5c9a1eda8b428d3205868993d4dc7685cd359e3cff`

```text
a b c = triangle a b c; p = on_line p a b; q = on_line q a c, on_pline q p b c; o = on_line o b q, on_line o c p; a1 = reflect a1 a b c; o1 = circumcenter o1 a p q; s = on_line s a1 o, on_circle s o1 a; o2 = circumcenter o2 b c s ? coll o1 o2 s
```

### 観測上位 1

- 構成経路: `shift(s,a1,o)->d`
- 全演繹: 1401
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o1,o2,o1,s)`
  - `para(o1,o2,o2,s)`
  - `midp(s,?A,?B)`
  - `circle(s,?A,?B,o1)`
  - `cyclic(?A,?B,o1,o2)`
  - `cong(?A,?B,o1,o2)`
  - `para(o1,s,o2,s)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,o1)`
  - `cyclic(?A,?B,o1,s)`
  - `cong(?A,?B,o1,s)`
  - `midp(s,o1,o2)`

### 観測上位 2

- 構成経路: `angle_bisector(s,a1,o)->d`
- 全演繹: 1384
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o1,o2,o1,s)`
  - `para(o1,o2,o2,s)`
  - `midp(s,?A,?B)`
  - `circle(s,?A,?B,o1)`
  - `cyclic(?A,?B,o1,o2)`
  - `cong(?A,?B,o1,o2)`
  - `para(o1,s,o2,s)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,o1)`
  - `cyclic(?A,?B,o1,s)`
  - `cong(?A,?B,o1,s)`
  - `midp(s,o1,o2)`

### 観測上位 3

- 構成経路: `angle_mirror(s,a1,o)->d`
- 全演繹: 1384
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(o1,o2,o1,s)`
  - `para(o1,o2,o2,s)`
  - `midp(s,?A,?B)`
  - `circle(s,?A,?B,o1)`
  - `cyclic(?A,?B,o1,o2)`
  - `cong(?A,?B,o1,o2)`
  - `para(o1,s,o2,s)`
  - `midp(o2,?A,?B)`
  - `circle(o2,?A,?B,o1)`
  - `cyclic(?A,?B,o1,s)`
  - `cong(?A,?B,o1,s)`
  - `midp(s,o1,o2)`

## 2019IranTSTp15

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 280.59836399999995
- 入力: `2706434d9e84d5d7b11ce3bbb2994d0e4242bdb2f00e6ddd2490b422a5301ad1`

```text
k b c = triangle k b c; b1 = mirror b1 b k; c1 = mirror c1 c k; a = on_line a b1 c1, angle_bisector a b k c; m = midpoint m b c; n = midpoint n c a; p = midpoint p a b; e = on_line e m n, on_line e b k; f = on_line f m p, on_line f c k; h = foot h a b c; o1 = circumcenter o1 a k h; o2 = circumcenter o2 h e f; l = on_circle l o1 a, on_circle l o2 h; x = on_line x m k, on_line x e f ? coll h l x
```

### 観測上位 1

- 構成経路: `circle(h,a,c1)->d`
- 全演繹: 17900
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

- 構成経路: `circumcenter(h,a,c1)->d`
- 全演繹: 17900
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

- 構成経路: `shift(h,b,c)->d`
- 全演繹: 17383
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

## 2019USATSTSTp5

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 153.2153057999967
- 入力: `7d0126fbec5dd59e66b7921c543429b300f25ce53de850d578c97016b9ec2adf`

```text
a b c = triangle a b c; h = orthocenter h a b c; o = circumcenter o a b c; e = on_line e a b; f = on_line f a c, on_line f e h; k = circumcenter k a e f; d = on_line d a k, on_circum d a b c; p = on_line p h k, on_tline p d b c ? cyclic a b c p
```

### 観測上位 1

- 構成経路: `intersection_cc(a,e,f)->g`
- 全演繹: 2271
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

- 構成経路: `reflect(b,a,c)->g`
- 全演繹: 2189
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

- 構成経路: `intersection_lt(a,b,c,a,b)->g`
- 全演繹: 2233
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,c,a,p,b,c,b,p)`
  - `ncoll(a,b,c,p)`
  - `eqangle(a,b,a,p,b,c,c,p)`
  - `eqangle(a,b,a,c,b,p,c,p)`

## 2020IranGOAp2

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 260.2552642999999
- 入力: `85e48377a0b6e26ea36230f187df13f6af38e26cb8019a7ae9faa5adf95adeb7`

```text
a b c = triangle a b c; i = incenter i a b c; o = circumcenter o a b c; n = on_bline n b c, on_circle n o a; m = midpoint m b c; p = mirror p a m; q = mirror q a n; r = foot r a q i; o1 = circumcenter o1 p q r; t = foot t o1 a i ? cong o1 p o1 t
```

### 観測上位 1

- 構成経路: `intersection_ll(o1,t,a,r)->d`
- 全演繹: 3212
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

- 構成経路: `mirror(a,o)->d`
- 全演繹: 3603
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

- 構成経路: `eq_triangle(b,c)->d`
- 全演繹: 2941
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
- 探索候補: 16
- 経過秒: 242.64418109999997
- 入力: `29a9fb61f57d5b7062fb44e81c7a8eec8f7a3ea6590f3ee0e66754d39fa75caa`

```text
a b c = triangle a b c; o = circumcenter o a b c; i = incenter i a b c; e = on_line e a c, angle_bisector e c b a; f = on_line f a b, angle_bisector f b c a; k = on_line k a i, on_line k e f; t = on_circle t o a, on_bline t b c; m = midpoint m b c; x = on_line x a m, on_circle x o a; o1 = circumcenter o1 a e f; s = on_circle s o1 a, on_circle s o a; s1 = reflect s1 s a i; o2 = circumcenter o2 a s1 k; j = on_line j a x, on_circle j o2 a ? cyclic i j t x
```

### 観測上位 1

- 構成経路: `intersection_lp(x,t,i,b,e)->d`
- 全演繹: 6628
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

- 構成経路: `shift(x,a,j)->d`
- 全演繹: 6541
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

- 構成経路: `intersection_lc(x,a,j)->d`
- 全演繹: 6504
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
- 探索候補: 16
- 経過秒: 346.3428607999999
- 入力: `e9165479f04905dd253c1c4d1cfebf94fa6b9cdbe6890896c9967d6c6a332578`

```text
a b c = triangle a b c; d = on_circum d a b c; e = on_circum e a b c; o = circumcenter o a b c; x = on_line x c d, on_line x a b; y = on_line y c d, on_line y a e; p = on_line p e x, on_line p b y; q = on_line q e x, on_circle q o a; r = on_line r b y, on_circle r o a; a1 = reflect a1 a c d; o1 = circumcenter o1 p q r; o2 = circumcenter o2 a1 x y; m = on_circle m o1 p, on_circle m o2 x; n = on_circle n o1 p, on_circle n o2 x; z = on_line z c m, on_line z d n ? cyclic p q r z
```

### 観測上位 1

- 構成経路: `intersection_lp(p,r,q,b,x)->f`
- 全演繹: 8941
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

- 構成経路: `intersection_lc(p,b,x)->f`
- 全演繹: 8803
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

- 構成経路: `intersection_lt(p,r,q,p,b)->f`
- 全演繹: 8788
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(p,r,p,z,q,r,q,z)`
  - `ncoll(p,q,r,z)`
  - `eqangle(p,q,p,z,q,r,r,z)`
  - `eqangle(p,q,p,r,q,z,r,z)`

## 2021CGMOp2

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 270.0024020999999
- 入力: `bfeb1fa9b559507690476ffd5016b1143f1fb15da5e7256425a3c763f351f273`

```text
a b c = triangle a b c; i = incenter i a b c; j = excenter j a b c; o = circumcenter o a b c; m1 = midpoint m1 a i; x = on_circle x o a, on_circle x m1 a; m2 = midpoint m2 a j; y = on_circle y o a, on_circle y m2 a; k = on_line k b c, on_bline k i j; m = midpoint m x y ? coll a k m
```

### 観測上位 1

- 構成経路: `angle_bisector(a,j,m2)->d`
- 全演繹: 3250
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,k,a,m)`
  - `para(a,k,k,m)`
  - `para(a,m,k,m)`
  - `midp(m,a,k)`
  - `midp(k,a,m)`
  - `midp(m,k,a)`
  - `midp(k,m,a)`
  - `midp(a,k,m)`
  - `midp(a,m,k)`
  - `lequation(1/1,a,k,1/1,k,m,-1/1,a,m,0)`
  - `lequation(1/1,a,m,1/1,m,k,-1/1,a,k,0)`
  - `lequation(1/1,k,a,1/1,a,m,-1/1,k,m,0)`

### 観測上位 2

- 構成経路: `angle_mirror(a,j,m2)->d`
- 全演繹: 3250
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,k,a,m)`
  - `para(a,k,k,m)`
  - `para(a,m,k,m)`
  - `midp(m,a,k)`
  - `midp(k,a,m)`
  - `midp(m,k,a)`
  - `midp(k,m,a)`
  - `midp(a,k,m)`
  - `midp(a,m,k)`
  - `lequation(1/1,a,k,1/1,k,m,-1/1,a,m,0)`
  - `lequation(1/1,a,m,1/1,m,k,-1/1,a,k,0)`
  - `lequation(1/1,k,a,1/1,a,m,-1/1,k,m,0)`

### 観測上位 3

- 構成経路: `on_pline(a,j,m2)->d`
- 全演繹: 3250
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,k,a,m)`
  - `para(a,k,k,m)`
  - `para(a,m,k,m)`
  - `midp(m,a,k)`
  - `midp(k,a,m)`
  - `midp(m,k,a)`
  - `midp(k,m,a)`
  - `midp(a,k,m)`
  - `midp(a,m,k)`
  - `lequation(1/1,a,k,1/1,k,m,-1/1,a,m,0)`
  - `lequation(1/1,a,m,1/1,m,k,-1/1,a,k,0)`
  - `lequation(1/1,k,a,1/1,a,m,-1/1,k,m,0)`

## 2021CGMOp7

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 276.6321286000001
- 入力: `e0c29d8832fabe011d7216dde2a4230163973ff91c3c00a7049044dac6884f8d`

```text
a b c = triangle a b c; o = circumcenter o a b c; k = reflect k b a c; l = reflect l c a b; x = on_tline x a b c, on_bline x k l; y = on_line y b k, on_tline y x c k; z = on_line z c l, on_tline z x b l ? cyclic b c o y
```

### 観測上位 1

- 構成経路: `intersection_ll(b,k,c,l)->d`
- 全演繹: 2011
- ゴール演繹: 0
- 進展DAG枝: 1
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(b,y,o,y,o,y,c,y)`
  - `ncoll(b,c,o,y)`
  - `eqangle(b,o,b,y,c,o,c,y)`
  - `eqangle(b,c,b,y,c,o,o,y)`
  - `eqangle(b,c,b,o,c,y,o,y)`

### 観測上位 2

- 構成経路: `orthocenter(b,c,a)->d`
- 全演繹: 2011
- ゴール演繹: 0
- 進展DAG枝: 1
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(b,y,o,y,o,y,c,y)`
  - `ncoll(b,c,o,y)`
  - `eqangle(b,o,b,y,c,o,c,y)`
  - `eqangle(b,c,b,y,c,o,o,y)`
  - `eqangle(b,c,b,o,c,y,o,y)`

### 観測上位 3

- 構成経路: `circumcenter(b,a,k)->d`
- 全演繹: 1536
- ゴール演繹: 0
- 進展DAG枝: 1
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(b,y,o,y,o,y,c,y)`
  - `ncoll(b,c,o,y)`
  - `eqangle(b,o,b,y,c,o,c,y)`
  - `eqangle(b,c,b,y,c,o,o,y)`
  - `eqangle(b,c,b,o,c,y,o,y)`

## 2021GOWACAp5

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 181.4437498999996
- 入力: `a64b0589ec52852348fff41ae72c86319b073c2c9c517883044d833c208e5573`

```text
a b c = triangle a b c; d = foot d a b c; o = circumcenter o a b c; m m1 m2 g = centroid m m1 m2 g a b c; k = on_aline k a c b a g, on_aline k b a c b g; d1 = mirror d1 d m; d2 = on_line d2 b c, on_aline d2 a b c a d1; p = on_tline p k a o, on_line p a d2; x = on_line x b c, on_tline x k b o; y = on_line y b c, on_tline y k c o; i = incenter i p x y ? coll a d i
```

### 観測上位 1

- 構成経路: `on_pline(d,b,c)->e`
- 全演繹: 12850
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

### 観測上位 2

- 構成経路: `angle_mirror(d,m,d1)->e`
- 全演繹: 12848
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

- 構成経路: `between_bound(d,m)->e`
- 全演繹: 12849
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
- 探索候補: 16
- 経過秒: 119.28537920000008
- 入力: `260eda2ec771e54b489a68bf47f9b3083beb535fb95e9bcd80d243cb36aff10f`

```text
a b c = triangle a b c; o = circumcenter o a b c; h = orthocenter h a b c; d = on_line d o h; e = on_line e b d, on_line e a c; f = on_line f c d, on_line f a b; x = on_line x a d, eqangle3 x e f a b c; o1 = circumcenter o1 c x f; o2 = circumcenter o2 b x e; p = on_circle p o1 c, on_circle p o2 b; q = on_line q x p, on_line q e f ? coll a h q
```

### 観測上位 1

- 構成経路: `shift(a,b,f)->g`
- 全演繹: 2589
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,h,a,q)`
  - `para(a,h,h,q)`
  - `midp(q,?A,?B)`
  - `circle(q,?A,?B,a)`
  - `cyclic(?A,?B,a,h)`
  - `cong(?A,?B,a,h)`
  - `para(a,q,h,q)`
  - `midp(h,?A,?B)`
  - `circle(h,?A,?B,a)`
  - `cyclic(?A,?B,a,q)`
  - `cong(?A,?B,a,q)`
  - `midp(q,a,h)`

### 観測上位 2

- 構成経路: `angle_bisector(a,b,f)->g`
- 全演繹: 2527
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,h,a,q)`
  - `para(a,h,h,q)`
  - `midp(q,?A,?B)`
  - `circle(q,?A,?B,a)`
  - `cyclic(?A,?B,a,h)`
  - `cong(?A,?B,a,h)`
  - `para(a,q,h,q)`
  - `midp(h,?A,?B)`
  - `circle(h,?A,?B,a)`
  - `cyclic(?A,?B,a,q)`
  - `cong(?A,?B,a,q)`
  - `midp(q,a,h)`

### 観測上位 3

- 構成経路: `angle_mirror(a,b,f)->g`
- 全演繹: 2527
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(a,h,a,q)`
  - `para(a,h,h,q)`
  - `midp(q,?A,?B)`
  - `circle(q,?A,?B,a)`
  - `cyclic(?A,?B,a,h)`
  - `cong(?A,?B,a,h)`
  - `para(a,q,h,q)`
  - `midp(h,?A,?B)`
  - `circle(h,?A,?B,a)`
  - `cyclic(?A,?B,a,q)`
  - `cong(?A,?B,a,q)`
  - `midp(q,a,h)`

## 2021IsraelOlympicRev

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 218.4674573000002
- 入力: `8c8691c3c5bdfc682b937068f36739e7d7aeb52aaee8d8b1c4713730e6c0e243`

```text
a b c = triangle a b c; p = eqangle3 p b c a c b; p1 = on_line p1 a p, on_line p1 b c; p2 = on_line p2 b p, on_line p2 a c; p3 = on_line p3 c p, on_line p3 a b; o = circumcenter o a b c; o2 = circumcenter o2 a p2 p3; x1 = on_circle x1 o a, on_circle x1 o2 a; o3 = circumcenter o3 b p3 p1; x2 = on_circle x2 o b, on_circle x2 o3 b; o4 = circumcenter o4 c p1 p2; x3 = on_circle x3 o c, on_circle x3 o4 c; b1 = on_line b1 a x1, on_line b1 c x3; c1 = on_line c1 a x1, on_line c1 b x2; k = on_line k b b1, on_line k c c1 ? cyclic a k p2 p3
```

### 観測上位 1

- 構成経路: `midpoint(a,x1)->d`
- 全演繹: 8163
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

- 構成経路: `shift(a,b,p3)->d`
- 全演繹: 7786
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

- 構成経路: `intersection_lt(a,p3,p2,a,b)->d`
- 全演繹: 7776
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,p2,a,p3,k,p2,k,p3)`
  - `ncoll(a,k,p2,p3)`
  - `eqangle(a,k,a,p3,k,p2,p2,p3)`
  - `eqangle(a,k,a,p2,k,p3,p2,p3)`

## 2021SilkRoadp3

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 85.78302129999997
- 入力: `bb5cf3623becf6040231fd257b9aafd04475e57382d4bbd4ad3aa084dbad7eb2`

```text
a b c = triangle a b c; m = midpoint m a b; b1 = on_line b1 a c, eqdistance b1 c c b; o = circumcenter o a b c; o1 = circumcenter o1 b m b1; k = on_circle k o a, on_circle k o1 b; q = on_bline q a b, on_circle q o a; e = on_line e b1 q, on_line e b c; m1 = midpoint m1 b1 e ? coll c k m1
```

### 観測上位 1

- 構成経路: `eq_triangle(b,a)->d`
- 全演繹: 2856
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(c,k,c,m1)`
  - `para(c,k,k,m1)`
  - `midp(m1,?A,?B)`
  - `circle(m1,?A,?B,c)`
  - `cyclic(?A,?B,c,k)`
  - `cong(?A,?B,c,k)`
  - `para(c,m1,k,m1)`
  - `midp(k,?A,?B)`
  - `circle(k,?A,?B,c)`
  - `cyclic(?A,?B,c,m1)`
  - `cong(?A,?B,c,m1)`
  - `midp(m1,c,k)`

### 観測上位 2

- 構成経路: `iso_triangle_vertex(b,a)->d`
- 全演繹: 2780
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(c,k,c,m1)`
  - `para(c,k,k,m1)`
  - `midp(m1,?A,?B)`
  - `circle(m1,?A,?B,c)`
  - `cyclic(?A,?B,c,k)`
  - `cong(?A,?B,c,k)`
  - `para(c,m1,k,m1)`
  - `midp(k,?A,?B)`
  - `circle(k,?A,?B,c)`
  - `cyclic(?A,?B,c,m1)`
  - `cong(?A,?B,c,m1)`
  - `midp(m1,c,k)`

### 観測上位 3

- 構成経路: `iso_triangle_vertex_angle(b,a)->d`
- 全演繹: 2778
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(c,k,c,m1)`
  - `para(c,k,k,m1)`
  - `midp(m1,?A,?B)`
  - `circle(m1,?A,?B,c)`
  - `cyclic(?A,?B,c,k)`
  - `cong(?A,?B,c,k)`
  - `para(c,m1,k,m1)`
  - `midp(k,?A,?B)`
  - `circle(k,?A,?B,c)`
  - `cyclic(?A,?B,c,m1)`
  - `cong(?A,?B,c,m1)`
  - `midp(m1,c,k)`

## 2022CHNSouthEastMOg11p6

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 109.66833919999999
- 入力: `0d40890008e875c5c14e6dc328d9f13c58b39c894cd145e62400f74eb50746aa`

```text
a b c = triangle a b c; o = circumcenter o a b c; p = on_bline p a o, on_pline p o b c; d = on_aline d b a b a c, on_aline d c a c a b; q = midpoint q a d; k = on_circle k p a, on_circle k q a ? cyclic b c d k
```

### 観測上位 1

- 構成経路: `parallelogram(d,b,a)->e`
- 全演繹: 716
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(b,d,b,k,c,d,c,k)`
  - `ncoll(b,c,d,k)`
  - `eqangle(b,c,b,k,c,d,d,k)`
  - `eqangle(b,c,b,d,c,k,d,k)`

### 観測上位 2

- 構成経路: `intersection_cc(k,a,q)->e`
- 全演繹: 910
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(b,d,b,k,c,d,c,k)`
  - `ncoll(b,c,d,k)`
  - `eqangle(b,c,b,k,c,d,d,k)`
  - `eqangle(b,c,b,d,c,k,d,k)`

### 観測上位 3

- 構成経路: `midpoint(k,a)->e`
- 全演繹: 778
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(b,d,b,k,c,d,c,k)`
  - `ncoll(b,c,d,k)`
  - `eqangle(b,c,b,k,c,d,d,k)`
  - `eqangle(b,c,b,d,c,k,d,k)`

## 2022G5

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 210.89023930000008
- 入力: `2b6e8f44d3914a1b5335a76d4a130094f187c501bc0a9ec6a02d315d39230806`

```text
a b c = triangle a b c; x1 = on_line x1 b c; y1 = on_line y1 a c; z1 = on_line z1 a b, on_line z1 x1 y1; x2 = on_line x2 b c; y2 = on_line y2 a c, on_pline y2 x2 x1 y1; z2 = on_line z2 a b, on_pline z2 x2 x1 y1; u1 = on_tline u1 y1 a c, on_tline u1 z1 a b; v1 = on_tline v1 x1 b c, on_tline v1 z1 a b; w1 = on_tline w1 x1 b c, on_tline w1 y1 a c; u2 = on_tline u2 y2 a c, on_tline u2 z2 a b; v2 = on_tline v2 x2 b c, on_tline v2 z2 a b; w2 = on_tline w2 x2 b c, on_tline w2 y2 a c; o1 = circumcenter o1 u1 v1 w1; o2 = circumcenter o2 u2 v2 w2; t = on_circle t o1 u1, on_circle t o2 u2 ? coll o1 o2 t
```

### 観測上位 1

- 構成経路: `on_aline(o2,o1,b,c,x1)->d`
- 全演繹: 11523
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

- 構成経路: `parallelogram(o2,o1,u1)->d`
- 全演繹: 11766
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

- 構成経路: `midpoint(o2,u2)->d`
- 全演繹: 11705
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

## 2022KoMaLA805

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 178.66775389999998
- 入力: `c91fac32adeb0336aff0c5117054251d66a03fa011cfe6c70a7726ce701a1a0e`

```text
a b c = triangle a b c; a1 = foot a1 a b c; b1 = foot b1 b a c; c1 = foot c1 c a b; o = circumcenter o a b c; o1 = circumcenter o1 a b1 c1; p = on_circle p o a, on_circle p o1 a; o2 = circumcenter o2 b c1 a1; q = on_circle q o b, on_circle q o2 b; h = orthocenter h a b c; r = on_line r a q, on_line r b p ? coll h o r
```

### 観測上位 1

- 構成経路: `angle_mirror(h,a,o1)->d`
- 全演繹: 10042
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(h,o,h,r)`
  - `para(h,o,o,r)`
  - `para(h,r,o,r)`
  - `midp(r,h,o)`
  - `midp(o,h,r)`
  - `midp(r,o,h)`
  - `midp(o,r,h)`
  - `midp(h,o,r)`
  - `midp(h,r,o)`
  - `lequation(1/1,h,o,1/1,o,r,-1/1,h,r,0)`
  - `lequation(1/1,h,r,1/1,r,o,-1/1,h,o,0)`
  - `lequation(1/1,o,h,1/1,h,r,-1/1,o,r,0)`

### 観測上位 2

- 構成経路: `on_pline(h,a,o1)->d`
- 全演繹: 10042
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(h,o,h,r)`
  - `para(h,o,o,r)`
  - `para(h,r,o,r)`
  - `midp(r,h,o)`
  - `midp(o,h,r)`
  - `midp(r,o,h)`
  - `midp(o,r,h)`
  - `midp(h,o,r)`
  - `midp(h,r,o)`
  - `lequation(1/1,h,o,1/1,o,r,-1/1,h,r,0)`
  - `lequation(1/1,h,r,1/1,r,o,-1/1,h,o,0)`
  - `lequation(1/1,o,h,1/1,h,r,-1/1,o,r,0)`

### 観測上位 3

- 構成経路: `angle_bisector(h,a,o1)->d`
- 全演繹: 10039
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `para(h,o,h,r)`
  - `para(h,o,o,r)`
  - `para(h,r,o,r)`
  - `midp(r,h,o)`
  - `midp(o,h,r)`
  - `midp(r,o,h)`
  - `midp(o,r,h)`
  - `midp(h,o,r)`
  - `midp(h,r,o)`
  - `lequation(1/1,h,o,1/1,o,r,-1/1,h,r,0)`
  - `lequation(1/1,h,r,1/1,r,o,-1/1,h,o,0)`
  - `lequation(1/1,o,h,1/1,h,r,-1/1,o,r,0)`

## 2023IMOp6

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 268.1290338000001
- 入力: `9a1953e82a03c37a1ce5e991bb73441e0360ddb9ddfd65df776d718c544952f2`

```text
a b c = ieq_triangle a b c; o = circumcenter o a b c; a1 = on_bline a1 b c; b1 = on_bline b1 c a; c0 = on_aline c0 a b a1 c b1; c1 = on_bline c1 a b, on_aline c1 a b c0 a o; a2 = on_line a2 b c1, on_line a2 c b1; b2 = on_line b2 c a1, on_line b2 a c1; c2 = on_line c2 a b1, on_line c2 b a1; o1 = circumcenter o1 a a1 a2; o2 = circumcenter o2 b b1 b2; o3 = circumcenter o3 c c1 c2; x = on_circle x o1 a, on_circle x o2 b ? cyclic c c1 c2 x
```

### 観測上位 1

- 構成経路: `intersection_cc(c,a,o)->d`
- 全演繹: 6135
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

- 構成経路: `circle(c,a,o)->d`
- 全演繹: 6134
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

- 構成経路: `shift(c,a,o)->d`
- 全演繹: 6134
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
- 探索候補: 16
- 経過秒: 205.99733820000006
- 入力: `800ac979a58bb45264241769d895925262c2cffde4f31ac66392f6d2a73591b8`

```text
a1 a3 a5 = triangle a1 a3 a5; a4 = free a4; a6 = free a6; a2 = on_aline a2 a4 a6 a5 a1 a3, on_aline a2 a6 a4 a5 a3 a1; x1 = on_line x1 a1 a3, on_line x1 a2 a6; x2 = on_line x2 a1 a3, on_line x2 a2 a4; x3 = on_line x3 a2 a4, on_line x3 a3 a5; x4 = on_line x4 a3 a5, on_line x4 a4 a6; x5 = on_line x5 a1 a5, on_line x5 a6 a4; x6 = on_line x6 a1 a5, on_line x6 a2 a6; o1 = circumcenter o1 a1 x1 a2; o2 = circumcenter o2 a2 x2 a3; o3 = circumcenter o3 a3 x3 a4; o4 = circumcenter o4 a4 x4 a5; o5 = circumcenter o5 a5 x5 a6; o6 = circumcenter o6 a6 x6 a1; k = on_line k o1 o4, on_line k o2 o5 ? coll k o3 o6
```

### 観測上位 1

- 構成経路: `midpoint(k,o1)->a`
- 全演繹: 7732
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

- 構成経路: `mirror(k,o1)->a`
- 全演繹: 7733
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

- 構成経路: `between_bound(k,o1)->a`
- 全演繹: 7708
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
- 探索候補: 16
- 経過秒: 653.0486695999998
- 入力: `132bd01d41573a1de9e9045063407e77403e2eca2f43f7d60f80b6e1a4f891e4`

```text
a b c = triangle a b c; p = free p; o = circumcenter o a b c; o1 = circumcenter o1 a p b; o2 = circumcenter o2 b p c; o3 = circumcenter o3 c p a; o_g = circumcenter o_g o1 o2 o3; x = on_circle x o a, on_circle x o_g o1; y = on_circle y o a, on_circle y o_g o1; q = reflect q p x y ? eqangle a b a p a q a c
```

### 観測上位 1

- 構成経路: `intersection_cc(a,b,o)->d`
- 全演繹: 2351
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,c,a,q,o1,o2,b,o1)`
  - `eqangle(a,c,a,q,o1,p,o1,o2)`

### 観測上位 2

- 構成経路: `parallelogram(a,o,b)->d`
- 全演繹: 2351
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,c,a,q,o1,o2,b,o1)`
  - `eqangle(a,c,a,q,o1,p,o1,o2)`

### 観測上位 3

- 構成経路: `shift(a,b,o)->d`
- 全演繹: 2351
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `eqangle(a,c,a,q,o1,o2,b,o1)`
  - `eqangle(a,c,a,q,o1,p,o1,o2)`

## 2023SAGFp8

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 17
- 経過秒: 127.38603779999994
- 入力: `0eec560fc44055a28a740419cbae2ff97e72a96debdfcdfa6bdd5daf21083f01`

```text
a b c = triangle a b c; o = circumcenter o a b c; d = on_bline d b c, on_circle d o a; e = on_bline e c a, on_circle e o a; f = on_bline f a b, on_circle f o a; r = mirror r d o; s = mirror s e o; t = mirror t f o; d1 = reflect d1 d b c; e1 = reflect e1 e c a; f1 = reflect f1 f a b; r1 = reflect r1 r b c; s1 = reflect s1 s c a; t1 = reflect t1 t a b; h1 = orthocenter h1 d1 e1 f1; o1 = circumcenter o1 r1 s1 t1; h = orthocenter h a b c ? para h1 o1 h o
```

### 観測上位 1

- 構成経路: `parallelogram(o,h,b)->g`
- 全演繹: 47978
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 2
- 未充足前提:
  - `para(b,g,h1,o1)`
  - `midp(?M,h,h1)`
  - `midp(?M,o,o1)`
  - `midp(?M,h,o1)`
  - `midp(?M,o,h1)`
  - `midp(?M,h1,h)`
  - `midp(?M,o1,o)`
  - `midp(?M,o1,h)`
  - `midp(?M,h1,o)`
  - `coll(g,h,h1)`
  - `coll(b,o,o1)`
  - `eqratio(b,o1,g,h1,o,o1,h,h1)`

### 観測上位 2

- 構成経路: `orthocenter(o,b,a)->g`
- 全演繹: 49014
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `midp(?M,h,h1)`
  - `midp(?M,o,o1)`
  - `midp(?M,h,o1)`
  - `midp(?M,o,h1)`
  - `midp(?M,h1,h)`
  - `midp(?M,o1,o)`
  - `midp(?M,o1,h)`
  - `midp(?M,h1,o)`
  - `eqratio(?O,h,?O,o,h,h1,o,o1)`
  - `coll(?O,h,h1)`
  - `coll(?O,o,o1)`
  - `sameside(h,?O,h1,o,?O,o1)`

### 観測上位 3

- 構成経路: `circumcenter(o,b,a)->g`
- 全演繹: 48111
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: -1
- 未充足前提:
  - `midp(?M,h,h1)`
  - `midp(?M,o,o1)`
  - `midp(?M,h,o1)`
  - `midp(?M,o,h1)`
  - `midp(?M,h1,h)`
  - `midp(?M,o1,o)`
  - `midp(?M,o1,h)`
  - `midp(?M,h1,o)`
  - `eqratio(?O,h,?O,o,h,h1,o,o1)`
  - `coll(?O,h,h1)`
  - `coll(?O,o,o1)`
  - `sameside(h,?O,h1,o,?O,o1)`

## 2023SerbiaMOp6

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 122.79518310000003
- 入力: `9e86fd5b43a6a8aea0fa7068d031595e0e9a880bcbe02c246a11dea538c6d2f0`

```text
a b c = triangle a b c; i = incenter i a b c; o = circumcenter o a b c; d = foot d i b c; e = on_line e a b, on_tline e i a i; f = on_line f a c, on_tline f i a i; o1 = circumcenter o1 a e f; g = on_circle g o1 a, on_circle g o a; h = on_circle h o1 a, on_line h a i; j = on_tline j g o g, on_line j b c; k = on_line k a j, on_circle k o a; o3 = circumcenter o3 d j k; o4 = circumcenter o4 g i h; t = on_circle t o4 i, on_circle t o3 d ? coll o3 o4 t
```

### 観測上位 1

- 構成経路: `nsquare(i,a)->l`
- 全演繹: 7364
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

- 構成経路: `psquare(i,a)->l`
- 全演繹: 7364
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

- 構成経路: `lc_tangent(i,a)->l`
- 全演繹: 7323
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
- 探索候補: 16
- 経過秒: 91.90870130000008
- 入力: `681603c371620e379a6f6a685ad88c54e9aa663f7bc151e235fdc6b02818b94e`

```text
a b c = triangle a b c; o = circumcenter o a b c; e = foot e b a c; f = foot f c a b; h = on_line h b e, on_line h c f; m = midpoint m a h; k = foot k h e f; p = on_circle p o a; q = on_circle q o a, on_pline q p b c; o1 = circumcenter o1 c q e; o2 = circumcenter o2 b p f; x = on_tline x e o1 e, on_tline x f o2 f ? coll k m x
```

### 観測上位 1

- 構成経路: `circumcenter(k,e,h)->d`
- 全演繹: 5257
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

- 構成経路: `circle(k,e,h)->d`
- 全演繹: 5253
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

- 構成経路: `intersection_lt(k,m,a,e,h)->d`
- 全演繹: 4960
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

## 2024ARMOg9p4

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 14
- 経過秒: 60.011224800000036
- 入力: `fda9a12bc29958db5353e1321e440a20e7573c144651d59832cc3e09ca1eb2f8`

```text
a b c = triangle a b c; d = on_circum d a b c, on_tline d c a b; e = on_line e a c, on_line e b d; z = on_line z a c, eqdistance z a c e; t = on_line t d b, eqdistance t d b e; x = on_line x a b, on_line x z t; y = on_line y c d, on_line y z t; o1 = circumcenter o1 e z t; e1 = mirror e1 e o1 ? cong x y e e1
```

### 観測上位 1

- 構成経路: `reflect(e1,e,b)->f`
- 全演繹: 3470
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `cong(e,f,x,y)`
  - `contri(e,e1,?C,x,y,?R)`
  - `contri(e,e1,?C,y,x,?R)`
  - `contri(e1,e,?C,x,y,?R)`
  - `contri(e1,e,?C,y,x,?R)`
  - `contri(x,y,?C,e,e1,?R)`
  - `contri(y,x,?C,e,e1,?R)`
  - `contri(x,y,?C,e1,e,?R)`
  - `contri(y,x,?C,e1,e,?R)`

### 観測上位 2

- 構成経路: `eq_triangle(e,e1)->f`
- 全演繹: 3002
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `cong(e,e1,x,y)`
  - `contri(e,e1,?C,x,y,?R)`
  - `contri(e,e1,?C,y,x,?R)`
  - `contri(e1,e,?C,x,y,?R)`
  - `contri(e1,e,?C,y,x,?R)`
  - `contri(x,y,?C,e,e1,?R)`
  - `cong(e,f,x,y)`
  - `cong(e1,f,x,y)`
  - `contri(y,x,?C,e,e1,?R)`

### 観測上位 3

- 構成経路: `shift(e,o1,e1)->f`
- 全演繹: 3252
- ゴール演繹: 0
- 進展DAG枝: 0
- 構造的に閉じた枝: 0
- 最小残余前提数: 1
- 未充足前提:
  - `cong(f,o1,x,y)`
  - `contri(e,e1,?C,x,y,?R)`
  - `contri(e,e1,?C,y,x,?R)`
  - `contri(e1,e,?C,x,y,?R)`
  - `contri(e1,e,?C,y,x,?R)`
  - `contri(x,y,?C,e,e1,?R)`
  - `contri(y,x,?C,e,e1,?R)`
  - `contri(x,y,?C,e1,e,?R)`
  - `contri(y,x,?C,e1,e,?R)`

## 2024ELMOSLp1

- 状態: `unsolved`
- 解釈: search completed without a native solved certificate
- 探索候補: 16
- 経過秒: 164.1648186
- 入力: `5e361894f697e79af3d28ffe0a20d267d604b121ad68d89e8aefcc71401f0a09`

```text
a b c d = quadrangle a b c d; e = on_line e a c, on_line e b d; p = on_line p a b, on_circum p a d e; q = on_line q a b, on_circum q b c e; r = on_line r a d, on_circum r a c p; s = on_line s b c, on_circum s b d q ? cyclic a b r s
```

### 観測上位 1

- 構成経路: `intersection_lp(a,b,c,a,r)->f`
- 全演繹: 1718
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

- 構成経路: `intersection_lt(a,b,c,a,b)->f`
- 全演繹: 1597
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

- 構成経路: `shift(a,b,p)->f`
- 全演繹: 1587
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
- 探索候補: 16
- 経過秒: 73.50071599999978
- 入力: `e944080707f05db3976832384ff5c08303a881a3e72359175b8164661a999925`

```text
t1 t2 t3 = triangle t1 t2 t3; i = circumcenter i t1 t2 t3; t4 = on_circle t4 i t1; a = on_tline a t1 i t1, on_tline a t2 i t2; b = on_tline b t2 i t2, on_tline b t3 i t3; c = on_tline c t3 i t3, on_tline c t4 i t4; d = on_tline d t1 i t1, on_tline d t4 i t4; t5 = on_circle t5 i t1, on_tline t5 i a c; p = on_tline p t5 i t5, on_line p b d; t = reflect t t5 i p; o = circumcenter o a t c ? coll i o t
```

### 観測上位 1

- 構成経路: `nsquare(t1,i)->e`
- 全演繹: 3456
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

- 構成経路: `psquare(t1,i)->e`
- 全演繹: 3456
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

- 構成経路: `lc_tangent(t1,i)->e`
- 全演繹: 3420
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
- 探索候補: 16
- 経過秒: 124.20218049999994
- 入力: `5ea9e4f1a8b2c50e63bc5ca93177f43097991a738a4846be8e6da6811955c718`

```text
a b c = triangle a b c; d = foot d a b c; e = foot e b a c; f = foot f c a b; d1 = foot d1 d e f; e1 = foot e1 e d f; f1 = foot f1 f d e; n1 = circumcenter n1 d e f; m = midpoint m b c; j = on_line j e1 f1, on_line j b c; k = on_line k d1 n1, on_line k b c; o = circumcenter o a j k; t = on_line t a m, on_circle t o a; p = on_line p a m, on_line p e f; q = on_line q t k, on_line q a j ? perp m o p q
```

### 観測上位 1

- 構成経路: `foot(m,p,e)->g`
- 全演繹: 12833
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

- 構成経路: `circle(m,a,d)->g`
- 全演繹: 11558
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

- 構成経路: `reflect(m,p,e)->g`
- 全演繹: 11899
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
- 探索候補: 16
- 経過秒: 451.80476069999986
- 入力: `914aa1e9f24f5c7657c27ede60356db8a1007b653d500cbffee18e2f0b4e715f`

```text
a b c = triangle a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; o = circumcenter o a b c; m = on_line m e f, on_circle m o a; s = on_tline s m o m, on_tline s a o a; t = on_tline t b o b, on_tline t c o c; j = on_line j t i, on_line j o a ? eqangle a s j s i s s t
```

### 観測上位 1

- 構成経路: `midpoint(f,e)->g`
- 全演繹: 3296
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

- 構成経路: `orthocenter(a,i,b)->g`
- 全演繹: 2986
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

- 構成経路: `eq_triangle(f,e)->g`
- 全演繹: 2827
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
- 探索候補: 15
- 経過秒: 48.21956299999988
- 入力: `3b6f52e2a445e54c37b978012fa34dc1bca525f0acfdb924178e9ef024fd9b5a`

```text
a b c = triangle a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; p = on_line p a d, on_line p b e; o1 = circumcenter o1 d i p; o2 = circumcenter o2 e i p; o3 = circumcenter o3 f i p; q = on_tline q d o1 d, on_tline q e o2 e ? perp f o3 f q
```

### 観測上位 1

- 構成経路: `intersection_cc(f,a,i)->g`
- 全演繹: 2525
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

### 観測上位 2

- 構成経路: `circumcenter(f,i,a)->g`
- 全演繹: 2948
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

### 観測上位 3

- 構成経路: `circle(f,i,a)->g`
- 全演繹: 2947
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
- 探索候補: 16
- 経過秒: 242.2656410999998
- 入力: `2fd54fc19563bb673aee445aab1fda0817d5ca35c97dc11d19d3c5c95a115331`

```text
a b c = triangle a b c; p = free p; d = on_line d a p, on_line d b c; e = on_line e b p, on_line e a c; f = on_line f c p, on_line f a b; o1 = circumcenter o1 a e f; o2 = circumcenter o2 b d f; q = on_circle q o1 a, on_circle q o2 b; r = on_line r p q; j = on_line j a r, on_circle j o1 a; k = on_line k b r, on_circle k o2 b; o3 = circumcenter o3 c d e; l = on_line l c r, on_circle l o3 c; oa = circumcenter oa a j d; ob = circumcenter ob b k e; t = on_circle t oa a, on_circle t ob b ? cyclic c f l t
```

### 観測上位 1

- 構成経路: `shift(c,a,e)->g`
- 全演繹: 6526
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

- 構成経路: `angle_mirror(c,a,e)->g`
- 全演繹: 6509
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

- 構成経路: `on_pline(c,a,e)->g`
- 全演繹: 6509
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
- 探索候補: 16
- 経過秒: 219.19397389999995
- 入力: `b194a2552972b6d2ecd06aeecb16787300d1148a403dda03f54497cd2e87906e`

```text
a b c = triangle a b c; i = incenter i a b c; i1 = excenter i1 a b c; i2 = excenter i2 b c a; i3 = excenter i3 c a b; a1 = foot a1 i1 a b; a2 = foot a2 i1 a c; b1 = foot b1 i2 b c; b2 = foot b2 i2 b a; c1 = foot c1 i3 c a; c2 = foot c2 i3 c b; d = on_line d b1 b2, on_line d c1 c2; e = on_line e a1 a2, on_line e c1 c2; f = on_line f a1 a2, on_line f b1 b2; o1 = circumcenter o1 d e f; x1 = on_circle x1 o1 d, on_circle x1 i1 a1; x2 = on_circle x2 o1 d, on_circle x2 i1 a1; y1 = on_circle y1 o1 d, on_circle y1 i2 b1; y2 = on_circle y2 o1 d, on_circle y2 i2 b1; z1 = on_circle z1 o1 d, on_circle z1 i3 c1; z2 = on_circle z2 o1 d, on_circle z2 i3 c1; x = on_line x y1 y2, on_line x z1 z2; y = on_line y x1 x2, on_line y z1 z2; z = on_line z x1 x2, on_line z y1 y2; o2 = circumcenter o2 x y z ? coll i o1 o2
```

### 観測上位 1

- 構成経路: `foot(i,d,b2)->g`
- 全演繹: 44852
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

- 構成経路: `intersection_lt(i,o1,d,i,b)->g`
- 全演繹: 42046
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

- 構成経路: `mirror(i,a)->g`
- 全演繹: 43487
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
- 探索候補: 16
- 経過秒: 115.07152159999987
- 入力: `76df24bed86e7b0a603c7e07dc7748a876c2dab8b93d19c068a4b12d2d5fedae`

```text
a b c = triangle a b c; o = circumcenter o a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; h = reflect h d e f; m = on_line m o i, on_circle m o a; t = on_line t i o, on_line t b c; q = on_line q a t, on_circle q o a; o1 = circumcenter o1 q m h; y = on_line y m a, on_circle y o1 q; y1 = reflect y1 y e f ? coll b c y1
```

### 観測上位 1

- 構成経路: `shift(b,c,t)->g`
- 全演繹: 5248
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

- 構成経路: `on_pline(b,c,t)->g`
- 全演繹: 5101
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

- 構成経路: `intersection_lp(b,c,a,b,i)->g`
- 全演繹: 5317
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
- 探索候補: 16
- 経過秒: 194.02092300000004
- 入力: `9c597dd3fb0859eb75c430355ada2c5ec39832d808b20837d078c25a6fe18315`

```text
a b c = triangle a b c; i = incenter i a b c; d = foot d i b c; e = foot e i a c; f = foot f i a b; k = on_line k a d, on_line k b e; o = circumcenter o a b c; x = on_line x a k, on_circle x o a; y = on_line y b k, on_circle y o a; z = on_line z c k, on_circle z o a; oa = circumcenter oa y k z; ob = circumcenter ob z k x; oc = circumcenter oc x k y; m1 m2 m3 g = centroid m1 m2 m3 g oa ob oc ? coll g i k
```

### 観測上位 1

- 構成経路: `midpoint(k,x)->h`
- 全演繹: 13118
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

- 構成経路: `orthocenter(k,a,ob)->h`
- 全演繹: 12854
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

- 構成経路: `shift(k,a,x)->h`
- 全演繹: 12067
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
