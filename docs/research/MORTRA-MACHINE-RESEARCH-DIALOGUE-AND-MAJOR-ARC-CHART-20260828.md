# MORTRA: 機械研究対話と大弧・相似拡大・接円チャート実験

日付: 2026-08-28
対象: HAGeo凍結89問、直前の厳密能力union 77/89
方針: 外部LLM不使用、期待解答不使用、問題ID分岐不使用

## 目的

未証明問題が出るたびに人間へ自然文で判断を求めるのではなく、次の閉ループを再開可能な形で実装する。

```text
MORTRA: 型付き停止義務と十分統計量
  -> Codex: 問題固有でない最小理論チャート
  -> MORTRA: 同一凍結集合で対照/介入実験
  -> governor: 証明書・回帰・曖昧性だけで採否
  -> 次の停止義務
```

同時に、研究記録で次対象とされていた大弧中点を含む構成を、相似拡大・二つの方べき・接円の一意性へ縮約し、追加正答へ因果的に寄与するかを測る。

## 仮説

### H0

JGEXの `on_bline(B,C) + on_circle(O,A)` だけでは交点が二つあり、自然文が指定する「弧BACの中点」を選べない。この枝情報を復元しない限り、厳密チャートは受理してはならない。

### H1

次の射列は問題名に依存しない再利用可能なチャートになる。

```text
弧を通る中点
  -> 反対側の弧中点
  -> A中心・比1/2の相似拡大
  -> 直角三角形の相似による方べき
  -> 弧中点による第2の方べき
  -> 接点と通過点を共有する円の一意性
  -> 逆相似拡大
```

### H2

MORTRAとCodexの内部交換に自然文は不要である。型、射、残差、証明書ハッシュ、反例、採否だけで十分であり、自然文は人間への説明と入力意味の取得に限定できる。

## 原理

単位円上で

```text
A=(cos 2alpha, sin 2alpha)
B=(cos 2beta,  sin 2beta)
C=(cos 2beta, -sin 2beta)
N=(-1,0)
D=(1,0)
```

とする。領域

```text
0 < beta < pi/4 < alpha < pi/2
alpha + beta > pi/2
```

は三角形ABCが鋭角であることと、NがBからCへAを通る弧の中点であることを固定する。DはNの反対側の弧中点で、AI上にある。

SをAIの中点とする。Aを中心とする比1/2の相似拡大は

```text
P -> M
Q -> N
R -> U
I -> S
```

と写す。RがAからQIへの垂足なので、UはAからSNへの垂足になる。

直角三角形ASNとUSAの相似から

```text
SU * SN = SA^2 = SI^2
```

であり、AIは円IUNにIで接する。一方、弧中点Dについて

```text
DM * DN = DB^2 = DI^2
```

なのでAIは円IMNにもIで接する。IとNを通りAIにIで接する円は一意だから、I,M,N,Uは共円である。比2の逆写像により、AIはPQRの外接円に接する。

## 実装方法

### 1. 自然意味の枝を保存

`geometry_natural_semantics.py` をv2へ更新し、次の型付き原子を追加した。

```text
arc_midpoint_through(N,B,A,C)
```

`\overarc{BAC}` を正規化し、点Nが端点B,Cの間でAを通る側の弧を二等分することを証明書ハッシュへ含める。自然文なし、鋭角条件なし、または別の通過点ではチャートは発火しない。

### 2. 厳密チャート

`major-arc-homothety-right-circle-tangent` を実装した。照合条件は構成グラフと型付き自然意味だけであり、問題名を参照しない。

42本の残差を

```text
sin(alpha)^2 + cos(alpha)^2 = 1
sin(beta)^2  + cos(beta)^2  = 1
```

で生成される厳密な商環で0へ正規化した。数値近似や期待解答の代入は使っていない。

### 3. 対照/介入

同じ未証明12問に対して、

```text
control:   新チャートだけを無効化
treatment: 新チャートを有効化
```

を実行した。既存チャート、入力、自然文、採点条件は同一である。

### 4. 機械研究対話

`mortra-codex-research-dialogue-v1` を実装した。1周期は次の4レコードからなる。

1. `mortra/cohort_observation`
2. `codex/typed_hypothesis`
3. `mortra/controlled_experiment`
4. `governor/decision`

各レコードは直前のSHA-256を含む。途中で停止しても、存在する段階を再利用して次段から再開する。同一fingerprintの完了周期は二重実行しない。改ざんしたpayloadは再読込時に拒否する。

停止義務には次を保存する。

- JGEX source SHA-256
- 自然文SHA-256と型付き原子
- 構成操作の多重集合
- 目標述語と引数
- 有効だったchart attempt
- 登録済みチャートとの不足操作数
- 対照/介入結果
- 証明書SHA-256
- 回帰、曖昧一致、量化修復の有無

## 結果

| 指標 | 結果 |
|---|---:|
| 対象 | 12問 |
| 新規厳密解決 | 1問 |
| 回帰 | 0問 |
| 曖昧一致 | 0問 |
| 証明書ハッシュ不一致 | 0問 |
| 再生恒等式 | 42/42 |
| 直前union | 77/89 = 86.52% |
| 更新union | 78/89 = 87.64% |
| 改善 | +1問、+1.12ポイント |
| 非空虚監査による除外 | 0問 |
| 残り | 11問 |

追加された問題は `2020IranGOAp2` である。対照では新チャートが `disabled_by_experiment` のため未証明、介入では同チャートだけが一意に一致して `proved` となった。

証明書:

```text
chart certificate:
14fce866da10724217a145f52c199e0e50c860400d1559d0d5321f6c71a24045

corrected dialogue cycle:
85c257a3fe89ba13a3414ec502e679c194d4b5e69946f0adf69595bf23c034ee

dialogue head:
6e84616e82fed6e8bdec560d3f1e58b3a577eba32cf279ae4203d3ff8379327f
```

## 集計誤りと訂正

最初の対話周期は `2019IranTSTp15` を通常解決として数え、残りを10問とした。これは誤りだった。同問は自然定理を証明できるが、凍結JGEXが「第2交点」を保持せず、量化修復後のみの証明である。

修正として、内部結果を

```text
raw_chart_solved
proved_after_quantifier_repair_only
solved
```

に分離した。誤った周期は削除せずハッシュ連鎖に残し、修正版コードをfingerprintへ含めた新周期を実行した。修正版は残り11問を返す。量化修復を通常得点に混ぜない回帰テストも追加した。

この訂正は、対話ledgerを持つ意味を示す。MORTRAとCodexが十分統計量を交換しても、採点意味論が誤っていれば自己強化は誤方向へ進む。したがって、自己修正は履歴を消すのではなく、反証と修正を新しい証明可能な周期として積む必要がある。

## 考察

### 効果が出た理由

探索深度を増やしたからではない。JGEXから失われた弧の枝を型として戻し、公式解答の複数の補助点を一つの相似拡大へ圧縮したことで、停止していた構成と目標の間に実行可能な射列が生まれた。

### 解法暗記との違い

追加したmatcherは、問題ID、期待解答、固定数値を使わない。必要なのは構成操作の型、多重度、依存関係、目標型、自然意味原子である。ただし本チャートは対象問題を見た後に実装したため、未見汎化の証拠ではなく、post-inspection capabilityとして扱う。

### 自然言語は不要か

MORTRAとCodexの内部通信には不要である。ただし二つの用途には残る。

1. JGEXが落とした定義域・量化・枝条件を取得する入力層
2. 人間が原理、証明、失敗を監査する説明層

内部表現を自然文にすると曖昧になるが、自然文を完全に捨てると今回の弧の枝を失う。したがって「自然文を型付きIRへ一度だけelaborateし、その後は型付き記録で対話する」が適切である。

### 自律性の境界

MORTRAが自分の規則と採点器を同時に変更して成功宣言する設計にはしない。探索器、理論修正器、凍結評価器を分離し、証明書を交換する。この分離は融合を弱めるためではなく、誤った自己強化を防ぐために必要である。

## 結論

大弧中点の枝情報と、相似拡大・二つの方べき・接円一意性を一つの可逆チャートとして実装した。未証明12問の対照/介入で追加正答1、回帰0を得て、非空虚な能力unionは78/89となった。

また、MORTRAとCodexが自然文を介さず、停止義務、仮説、実験、採否をハッシュ連鎖で交換する再開可能な研究ループを実装した。これは「会話を続ければ賢くなる」という主張だけではなく、誤集計を履歴付きで検出・訂正できる工学的な閉ループである。

## 次の課題

残り11問は、目標型で `cyclic: 6`、`coll: 4`、`eqangle: 1` に分かれる。次周期では、問題ごとの規則を足す前に、機械記録のnearest-chart residualを集約する。

1. 6問のcyclic目標について、円・円周角・接線・方べきの双方向変換の共通欠落を抽出する。
2. `2020IranTSTp9` では再利用可能になった `arc_midpoint_through(T,B,A,C)` を入力意味として利用する。
3. `2019IranTSTp15` は第2交点量化をJGEX本体で表現できるまで通常得点へ入れない。
4. 幾何以外へ進む際も、同じledgerで `漸化式 <-> 行列 <-> 特性多項式` を最初の凍結対照/介入実験にする。

## 再現

```text
python -m pytest   worker/backend/test_major_arc_homothety_tangent_chart.py   worker/backend/test_mortra_research_dialogue.py   scripts/test_experiment_mortra_codex_research_dialogue.py -q

python scripts/experiment_mortra_codex_research_dialogue.py   --union data/hageo-certified-capability-union-plus-second-lemoine-chart-2026-08-28.json   --dataset data/hageo-409-jgex-2026-08-18.txt   --natural-dataset data/hageo-409-natural-language-2026-08-26.json   --output data/mortra-codex-research-dialogue-major-arc-homothety-2026-08-28.json
```

主要成果物:

- `artifacts/exact-chart-runtime-v25/2020IranGOAp2.chart-portfolio.json`
- `artifacts/exact-chart-runtime-v25/2020IranGOAp2.proof.md`
- `artifacts/exact-chart-runtime-v25/2020IranGOAp2.proof-focus.svg`
- `data/mortra-codex-research-dialogue-major-arc-homothety-2026-08-28.json`
- `data/hageo-certified-capability-union-plus-major-arc-homothety-chart-2026-08-28.json`
- `data/hageo-nonvacuous-capability-union-plus-major-arc-homothety-2026-08-28.json`
- `data/exact-chart-remaining11-natural-runtime-audit-2026-08-28.json`
