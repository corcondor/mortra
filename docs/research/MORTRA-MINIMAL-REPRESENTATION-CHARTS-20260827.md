# MORTRA 最小表現チャートによる未証明問題の追加認証

## 目的

固定89問の未証明20問から、問題名・点名・期待結論を記憶せずに使える少数の表現チャートを抽出し、追加正答と誤判定を同時に測る。

今回の採用条件は次の通り。

1. JGEXの構成依存関係と目標だけで照合する。
2. 点名を全面変更しても適用できる。
3. 接続を1本だけ壊した近傍問題を受理しない。
4. 局所恒等式をCASで厳密再生する。
5. 別実装の有理数配置でも結論を再検算する。
6. 固定集合外・空虚イデアル・既認証との重複を加算しない。
7. 残り全問への誤一致と曖昧一致を測る。

外部LLMと期待解答は、証明器・照合器・採点器の経路で使用していない。

## 仮説

未証明問題の一部は規則不足ではなく、同じ幾何構成を高次の表現へ移す橋が不足している。構成をそのまま全展開する代わりに、円束・根軸・複素アフィン中心公式へ縮約すれば、少数の恒等式で証明できる。

## 方法

### 1. 二直径円・ペダル円・根軸

対象は `2011G3`。最初は4変数の垂足座標と二円の係数を一括展開したが、式膨張により3分以上完了しなかった。この経路は採用しなかった。

公式解答の構成を読み直し、次の4橋へ分解した。

```text
直径円上の点
-> 直角の分割
-> 3垂足円を第4射影で完成
-> 交差する割線による等べき
-> E+F=U+V というアフィン平行四辺形
-> EFの中点が根軸上
```

最後の橋は、2本の基準線を `AD: y=0`、`BC` の方向を `(cosine,sine)` とすると、交差射影点が

```text
U=(ex, fy+cosine*(fx-ex)/sine)
V=(fx, ey+cosine*(ex-fx)/sine)
```

となり、成分ごとに `U+V=E+F` で閉じる。巨大消去は不要になった。

### 2. 接触三角形・共通弦・円束

対象は `2016USATSTSTp6`。公式解答にはGergonne点、Cevian Nest、Desargues、調和束を使う解法がある。一方、MORTRAの共通核としてはさらに小さくできる。

内接円を単位円、接点 `D=(1,0)` とし、他の接点を2つの有理パラメータ `u,v` で表す。

```text
E=((1-u^2)/(1+u^2), 2u/(1+u^2))
F=((1-v^2)/(1+v^2), 2v/(1+v^2))
```

三角形の頂点は接線の交点だけで復元できる。

```text
A=((1-uv)/(1+uv), (u+v)/(1+uv))
B=(1,v)
C=(1,u)
```

二円の交点 `B1,B2` や `C1,C2` は個別に解かない。二円の方程式を引き、共通弦を一次式 `L=0` として得る。目的の円は

```text
incircle + lambda * L = 0
```

という円束で表す。`B` または `C` を代入して `lambda` を一意に決め、`M=(D+proj_EF(D))/2` における二つの冪を比較すると差が恒等的に0になる。

### 3. 円弧中点・辺鏡映・中心軸

対象は `2023SAGFp8`。外接円を単位円とし、頂点を半角複素数で

```text
A=x^2, B=y^2, C=z^2
```

と書く。三つの辺の垂直二等分線と円の交点は、独立な符号 `sd,se,sf` を用いて

```text
D=sd*yz, E=se*zx, F=sf*xy
```

となる。単位円上の `p,q` を通る直線に関する鏡映は

```text
w -> p+q-pq*conjugate(w)
```

である。鏡映後の2三角形について、外心は2本の等距離一次方程式、垂心は `H=P+Q+R-2O` で計算した。最終的に

```text
H1-O1 = real_scalar * (H-O)
```

と因数分解できる。符号については `sd^2=se^2=sf^2=1` で剰余を取り、8通りすべての枝で実数係数になることを1つの多項式義務として再生した。

### 4. 円に内接する四角形・対向二等分線・横断線

対象は `2016CTSTp5`。外接円上の4点を半角複素数で表し、対向する2組の角の二等分線を、それぞれ対蹠な弧中点を結ぶ直線へ変換した。横断線との4交点は同次座標の外積だけで構成できる。対辺上の交点対の中点を `M,N` とすると、目標の直交性はHermitian内積

```text
M0*N1 + M1*N0 = 0
```

へ縮約される。4つの独立な二等分線分岐すべてで恒等的に0となった。

### 5. 三外心円・根軸鏡映・等角共役

対象は `2023RMMSLG3`。`ABC` を単位円に置き、自由点 `P` の共役だけを独立変数として保持した。`APB`,`BPC`,`CPA` の3外心を6本の等距離一次式で解き、その3点円と単位円の差から根軸を直接得た。根軸に関する `P` の鏡映を `Q` とすると、

```text
(P-A)(Q-A) / ((B-A)(C-A))
```

が共役と一致するため、`AP` と `AQ` は角 `BAC` で等角共役になる。

### 6. 接触三角形・ジェルゴンヌ点・三外心重心

対象は `ShuZhiMiGeo635`。内接円を単位円、接点を `D=(1,0),E(u),F(v)` とした。3辺は接線なので `ABC`、ジェルゴンヌ点 `K`、チェバ線と外接円の第2交点 `X,Y,Z` は2変数 `u,v` の有理式になる。`YKZ`,`ZKX`,`XKY` の外心を線形に解いて平均すると、内心を原点として

```text
G = ((u^2 v^2 + u^2 + 2uv + v^2 + 3) / (6(uv+1))) K
```

と因数分解できる。したがって `G,I,K` は共線である。接触円チャートと三外心チャートを同じ2変数座標で合成した例である。

### 7. 垂足枠・平行弦・二外心接線

対象は `2023VietnamTSTp3`。`A=(0,0),B=(1,0),C=(u,v)` とし、円上の可動点 `P` を直線 `AP` の傾き `t` で有理パラメータ化した。`P` を既知根として割ることで、`PQ || BC` を満たす第2交点 `Q` を得る。垂足 `E,F`、垂心 `H`、中点 `M`、射影 `K`、2外心、2接線はすべて一次式で解ける。接線交点 `X` について

```text
det(X-M, K-M) = 0
```

が3変数 `u,v,t` の恒等式として消去された。

## 実装

| チャート | 問題 | 局所恒等式 | 独立配置 |
|---|---|---:|---:|
| two-diameter-circles-pedal-radical-axis | `2011G3` | 15/15 | 有理8配置 |
| incircle-contact-circle-pencil-midpoint-radical-axis | `2016USATSTSTp6` | 22/22 | 有理8配置 |
| arc-midpoint-antipode-reflection-center-axis | `2023SAGFp8` | 22/22 | 有理4配置 x 8枝 |
| cyclic-opposite-bisectors-transversal-midpoints | `2016CTSTp5` | 20/20 | 有理4配置 x 4枝 |
| three-circumcenters-radical-reflection | `2023RMMSLG3` | 18/18 | 有理8配置 |
| incircle-gergonne-three-circumcenters | `ShuZhiMiGeo635` | 30/30 | 有理8配置 |
| orthic-parallel-chord-two-tangents | `2023VietnamTSTp3` | 23/23 | 有理8配置 |

各チャートは証明Markdown、SVG、構造適用記録、証明書SHA-256を生成する。ポートフォリオには問題IDによる分岐を追加していない。

## 結果

### 認証済み能力和

```text
開始時                     69/89 = 77.53%
2011G3                     +1
2016USATSTSTp6             +1
2023SAGFp8                 +1
2016CTSTp5                 +1
2023RMMSLG3                +1
ShuZhiMiGeo635             +1
2023VietnamTSTp3           +1
現在                       76/89 = 85.39%
未証明                     13問
母集団外加算                0
空虚単位イデアル加算        0
既認証との重複              0
```

### 証明書

| 問題 | 証明書SHA-256 |
|---|---|
| `2011G3` | `66c2da925fdea8c2482bbb8ad3aab86eec6d77f6fce00e312d8bcfdef754865c` |
| `2016USATSTSTp6` | `9af628159cba1714545645950dc531cb26fdbe3e87cf228bca3798cc15d8773c` |
| `2023SAGFp8` | `714f18e864507c514c5366c4bb63d30f86709b21a6ee8d81d127b1436717c5c3` |
| `2016CTSTp5` | `49f3179997618d5c6d84833435ded44c4446109bfba09a72a3a58cfd3d5fd6b9` |
| `2023RMMSLG3` | `cb3a76184864f6f644a48258b1208e052b21e2cc9b183215b7d181f80ae8cd37` |
| `ShuZhiMiGeo635` | `7a0a41039baac848422e6458e90f1fc7c24ff6ee24a6167db315b634a61b287d` |
| `2023VietnamTSTp3` | `fde31ec4d2f576dfb59f1d5543edf9b2e625fbc482ff131b3df27602650d217e` |

### 回帰と誤判定

| 検査 | 結果 |
|---|---:|
| 7チャートの全点名変更 | 7/7 採用 |
| 近傍接続破壊 | 36/36 不採用 |
| 独立有理配置・分岐 | 88/88 成功 |
| 全厳密チャート・能力和監査回帰 | 168/168 成功 |
| 能力和・非空虚監査回帰 | 4/4 成功 |
| 残り13問への再照合 | 採用0、曖昧0 |

## 考察

### 何が正答を増やしたか

探索深度や変換規則数を増やした効果ではない。7問とも、長い構成を別の表現へ移して次元を下げたことが直接の要因である。

```text
多数の垂足       -> 4つの局所橋と1つのアフィン恒等式
4つの円交点      -> 2本の共通弦と2つの円束係数
12回の中心・鏡映 -> 半角複素数と実スカラー因数分解
4本の角二等分線 -> 対蹠弧中点と同次外積
3外心円と鏡映   -> Hermitian円差と実交比
接触三角形と3外心 -> 2変数有理座標と重心のスカラー倍
平行弦と2接線   -> 既知根除去と一次接線交点
```

この方法は「規則を増やさない」こと自体を目的にしていない。必要な数学構造を、より少数の生成子と合成則で再表現する。追加した7チャートは既存規則を列挙したものではなく、各構成族を一括して扱う座標変換である。

### 汎化について言えること

点名、三角形頂点の順序、円交点の順序、円弧中点の8枝には依存しない。近傍接続を壊すと受理しない。したがって同型構造への汎化は実証した。

ただし7問はいずれも問題を確認した後のpost-hoc追加である。76/89は現在のコードが固定集合上で再生できる監査済み能力和であり、独立未見集合での正答率ではない。未見集合での追加正答が出るまで、任意の幾何問題を解けるとは主張しない。

### 量化・分岐の監査

`2020IranGOAp2` は自然文で点 `N` を大弧 `BAC` 上に固定するが、凍結JGEXは垂直二等分線と外接円の2交点を一出力で選択している。独立数値検査では大弧側だけが成立し、他方の枝は成立しなかった。`2017USAMOp3` も自然文は2交点の少なくとも一方に関する存在命題だが、JGEXは一方だけを無指定で選ぶ。したがって両問は、量化修復なしに得点へ加えていない。これは探索不足ではなく、入力意味論の不一致である。

### 残る不足

残り13問には少なくとも次が残る。

1. 角の二等分線が作る射影・極・調和束の共通チャート。
2. 接線、方べき、円周角を双方向に移す円チャート。
3. 反転・相似中心・複数円交点を同じアフィン/複素表現へ移すチャート。
4. 3次元または順序条件を含む構成の型付き非退化処理。

次の問題は名前順ではなく、停止した証明義務をこれらのチャート候補へクラスタリングし、1チャートが複数問へ発火する候補を優先する。

## 結論

未証明7問を、7つの問題名非依存チャートで追加認証した。巨大な一括消去を採用せず、円束・根軸・複素中心軸・接触円座標・既知根除去へ縮約した結果、固定89問の監査済み能力和は69から76へ増え、85%を超えた。全168回帰、非空虚監査、残り13問の誤一致監査を通過した。

## 再現資料

- `worker/backend/two_diameter_pedal_radical_axis_chart.py`
- `worker/backend/incircle_contact_pencil_midpoint_chart.py`
- `worker/backend/arc_midpoint_reflection_center_axis_chart.py`
- `worker/backend/cyclic_bisector_transversal_midpoints_chart.py`
- `worker/backend/three_circumcenters_radical_reflection_chart.py`
- `worker/backend/incircle_gergonne_three_circumcenters_chart.py`
- `worker/backend/orthic_parallel_chord_two_tangents_chart.py`
- `worker/backend/exact_geometry_chart_portfolio.py`
- `data/hageo-exact-chart-two-diameter-pedal-runs-2026-08-26/`
- `data/hageo-exact-chart-incircle-pencil-runs-2026-08-26/`
- `data/hageo-exact-chart-arc-reflection-axis-runs-2026-08-27/`
- `data/hageo-exact-chart-cyclic-bisector-runs-2026-08-27/`
- `data/hageo-exact-chart-three-circumcenters-runs-2026-08-27/`
- `data/hageo-exact-chart-incircle-gergonne-three-centers-runs-2026-08-27/`
- `data/hageo-exact-chart-orthic-parallel-chord-two-tangents-runs-2026-08-27/`
- `data/hageo-certified-capability-union-plus-orthic-parallel-chord-two-tangents-chart-2026-08-27.json`
- `data/hageo-certified-capability-union-plus-orthic-parallel-chord-two-tangents-chart-nonvacuous-audit-2026-08-27.json`
- `data/exact-chart-remaining13-runtime-audit-2026-08-27.json`

## 参考

- IMO 2011 Shortlist G3 official solution: `https://www.imo-official.org/problems/IMO2011SL.pdf`
- USA TSTST 2016/6 solutions: `https://web.evanchen.cc/exams/sols-TSTST-2016.pdf`
