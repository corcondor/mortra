# どのコードがどの数学構造に効くのか — 実測による対応表

すべて環境変数 `MORTRA_RESEARCH_SOURCES` が指す研究ソース群の実コードから抽出した。
論文の要約ではなく、規則ファイルと述語定義を数えた結果である。

---

## 1. 幾何の演繹エンジン — 述語体系と「演繹で作れる/作れない」の境界

### Newclid（MORTRA が実際に使っている）

`all_rules.py` で宣言されている規則は **87**、`DEFAULT_RULES` で通常実行に
入る規則は **58**。規則IDが `r00` から `r92` まであることと、93本が宣言・
実行されることは同じではない。以下は有効58規則についての境界である。

```
有効DD規則の結論に現れる
  coll cong perp para midp cyclic circle eqangle eqratio
  simtri simtrir contri contrir lequation aequation rconst

有効DD規則では前提にだけ現れる
  ncoll(27規則が要求)  diff(35)  sameclock(17)  sameside(4)
  npara(3)  nperp(3)  obtuse_angle(1)  nsameside(1)
```

これは **DD規則チャネルだけ** の境界であり、Newclid全体の到達可能性ではない。
`cong` や `eqangle` はARも生成する。`ncoll`、`sameclock`、`obtuse_angle` は
構成・数値guardから供給され、DD規則の正当な前提になる。`equation_class` はARの
証明状態であって残骸ではない。これらを除外した集計を全エンジンの到達不能性と
解釈してはいけない。

### AlphaGeometry v1

規則 **43**（Newclid の r00–r42 に対応）。

```
到達しうる  coll cong perp para midp cyclic eqangle eqratio simtri contri
作れない    ncoll npara sameside circle
```

**v1 では `circle` が作れない。** Newclid はここを拡張して `circle` を結論に持つ規則を2本足している。

### AlphaGeometry2 の DDAR（`ddar.py` / `elimination.py`、Apache-2.0）

これは規則表ではない。**表現ごとの代数と、その間の移送関数**として書かれている。

```python
class DDAR:
    pred_to_angle           述語 → 角度の表現
    pred_to_dist_add        述語 → 距離の加法表現
    pred_to_dist_mul        述語 → 距離の乗法表現
    transfer_dist_add_mul   加法 ⇄ 乗法 の移送
    transfer_dist_arc_mul   弧 ⇄ 乗法 の移送
    deduction_closure
    search_similar / search_concyclic / search_circles
    force_similar / force_collinear / force_concyclic
    merge_points
class FormalLine, FormalCircle
```

`elimination.py` は明記どおり "Elimination of variables, without proof"。
`ElimVar/ElimLHS/ElimRHS`、有理数、`prime_decomposition`。

`transfer_dist_add_mul` は、既存制約で同じ正規形になった距離について加法表現と
乗法表現を同期する。`transfer_dist_arc_mul` は、同一円上の等しい有向弧と等しい
弦を対応させる。いずれも数値配置をassertionのsanity checkに使い、証明履歴は
生成しない。したがってMORTRAでは候補生成に使えても、そのまま最終証明書にはできない。

またNewclidにも `cyclic` / `eqangle` / `cong` を結ぶDD規則群と、ARから
`cong`を列挙する経路がある。よって「Newclidに弧・弦移送が全く無い」は誤り。
比較すべき差は、AG2が持つ独立した加法距離表 `elim_dist_add` と、Newclidの
有効DD+ARで同じ定理義務を閉じられるかである。

### TongGeometry

述語ごとに規則ファイルを分けている。

```
cong contri eqangle eqcircle eqline eqratio midp para perp simtri
```

`eqcircle` `eqline` が独立した述語として立っている点が Newclid と違う。
Newclid は円と直線を点の関係へ潰すが、TongGeometry は**対象として持つ**。

### FormalGeo（GDL）

関係 **29**、属性 **12**、定理 **52**。設計思想が根本的に違う。

```
関係   FreePoint FreeLine FreeCircle SamePoint SameLine SameCircle
       PointOnLine PointOnCircle PointLeftSegment
       ParallelBetweenLine PerpendicularBetweenLine
       EqualDistancePointToPoint EqualDistancePointToLine EqualAngle
       AngleBisector MidpointOfArc Triangle IsoscelesTriangle
       CongruentTriangle MirrorCongruentTriangle IntersectBetweenCircle
       CenterOfCircle CircumcenterOfTriangle OrthocenterOfTriangle
       IncenterOfTriangle CircumcircleOfTriangle
       TangentBetweenLineAndCircle PerpendicularBisector ConcyclicBetweenPoints

属性   XOfPoint YOfPoint KOfLine BOfLine UOfCircle VOfCircle ROfCircle
       DistancePowBetweenPointAndPoint DistancePowBetweenPointAndLine
       DistanceBetweenPointAndCircle MeasureOfAngle RadiusOfCircle
```

**直線・円が第一級の対象で、座標属性（`XOfPoint`、`KOfLine`、`ROfCircle`）を持つ。**
Newclid は点だけを対象にして関係で表すので、`TangentBetweenLineAndCircle` のような
述語が存在しない。接線条件は Newclid では点の関係へ展開するしかない。

定理名が `..._property_algebraic` / `..._determination_algebraic` と分かれており、
**性質（前向き）と決定（後ろ向き）が別定理として明示されている。**

---

## 2. 代数の証明系

### GCLC（`source/AlgebraicMethods/`）

```
Wu.cpp        Wu の特性集合法
Groebner.cpp  Gröbner 基底
Reduce.cpp    簡約
```

述語を持たない。**多項式イデアルへの帰着**。Newclid の述語で書けない条件でも、
座標多項式にできれば扱える。逆に、証明が多項式の等式で出るので、
**幾何述語へ戻す経路が別に要る。**

### cvc5

SMT。理論が分かれている（`arith` `arrays` `bv` `datatypes` `bags` `booleans` …）。
**非線形実数算術**が使える。幾何の述語体系は持たない。

---

## 3. 書き換え・等式飽和

### egglog / ruler-oopsla21

**e-graph と等式飽和。** ruler は「規則そのものを推論する」枠組み
（Rewrite Rule Inference Using Equality Saturation）。

幾何の述語は持たない。だが **MORTRA の不足前提が「規則が足りない」だと確定した場合、
規則を人が書くのではなく推論させる**道具になりうる。現時点では前提が確定していない。

---

## 4. 学習系（MORTRA の非LLM条件では使えない）

```
GenesisGeo   HAGeo-409 で 278/409。ただし 2B モデルを使う
HyperGNet    ハイパーグラフ NN
AutoGPS      multimodal_formalizer + symbolic_reasoner の二段
difflogic    微分可能論理ゲート網
LNN          論理ニューラルネット
scallop      Datalog + 確率
```

**GenesisGeo の 278/409 は MORTRA の 53/89 と直接比較できない。** 条件が違う。

---

## 5. 形式化・入出力

```
Euclean          幾何問題を Lean へ形式化し統一検証（ICML 2026）
GeoParser        図と文から形式化（FGeo-Parser）
GeoModelBuilder  作図の生成
FGPS             FormalGeo の求解器
```

**Euclean は miniF2F 系のベンチに出るための橋になりうる。** 現時点で MORTRA は sympy 証明で、
Lean へ書き出す層が無い。

---

## 6. 協調・理論

```
sheaf-admm            局所合意。数学構造を持たない。優先順位のみ
state-tracking-crasp  分解理論。文字列言語と構文モノイド。幾何ではない
```

---

## 7. この地図から言えること

### 7.1 本日の誤診の原因

DD規則、AR、構成事実、数値guardをすべて `all_deductions` という一群で集計し、
述語名と点の重なりから因果を推測したことが誤りだった。逆にDD結論だけを残しても、
ARで解けた問題の根拠を落とす。今後は各assertionに producer channel と証明根拠を
付け、チャネル間の変換をコード位置と定理で監査する。

### 7.2 不足前提の述語と、それを埋められる系の対応

survey で出た未解決側の不足前提の分布は次のとおり。

```
midp 63  circle 42  para 18  lequation 18  contri 16
cong 14  cyclic 13  contrir 13  perp 6  eqangle 3
```

これを上の地図に当てると:

| 不足前提 | Newclid で作れるか | 他の系での扱い |
|---|---|---|
| `midp` | active DD結論に2回 | FormalGeo は `MidpointOfArc` を持つ |
| `circle` | active DD結論に1回 | FormalGeo は `CircumcircleOfTriangle` を第一級で持つ / TongGeometry は `eqcircle` |
| `lequation` | ○ 結論に4回 | AG2 は `pred_to_dist_add` で加法表現へ / GCLC は多項式へ |
| `cyclic` | active DD結論に2回 | AG2 は `search_concyclic` / `force_concyclic` を持つ |
| `contri/contrir` | ○ 結論に4回ずつ | AG2 は `force_similar` |

ただしこの不足前提集計は、OR枝を平坦化しproducer channelを失った旧診断である。
`circle` の件数だけから円規則不足を結論しない。

### 7.3 まだ言えないこと

- 上の対応は「述語名の一致」による対応であり、**意味の一致は確認していない。**
  `SinOrDist` で一度踏んだので、中身を見るまで同一視しない。
- 不足前提の分布は 6問対10問の比較で、条件も揃っていない（解けた側を補助構成なしで測った）。
  **この分布を根拠に実装を決めない。**
- AG2 の `transfer_*` は証明履歴を出さず、Newclid規則と機能重複もある。
  移植するなら、新規候補をnative verifierが再証明できることが必須である。

---

## 8. 次の一手（推測ではなく検証として）

1. 各assertionを DD / AR / construction / numerical guard / registry merge に分類する。
2. AG2の各transferを、前提・結論・非退化条件・証明履歴の有無まで定理単位で写す。
3. 同じ定理がNewclidのactive DD+ARで閉じるかを、合成例ではなく固定未解決問題の
   ground obligationで比較する。
4. 重複しない定理だけ候補生成器として実装し、NewclidまたはGCLCで再証明する。
5. 追加正答、誤受理、時間をcontrol/treatmentで測り、0なら既定経路へ入れない。
