# 図を「実行可能な数学表現」にする

実施日: 2026-08-13<br>
実装基線: `1926596fb943f481bb7cff05b51e019567b72f88`<br>
実験: `finite-state-recurrence-diagram-ab-v1`<br>
データdigest: `3f5f5dd2dedef69a`

## 結論

MORTRAでいう図は、対象を見せる画像ではない。**数学的構造の一部を明示し、
その表現上で許される操作、保存される量、失われる情報、逆像の曖昧性を宣言した
実行可能な表現**である。

したがって、図を共通のnode/edge形式へ潰すことはしない。共通化するのは次の契約だけで、
carrier、関係、書換え、証明義務は分野別の型として残す。

```text
source semantic IDs
  + diagram kind
  + encoded / forgotten structure
  + typed carriers and domain structure
  + legal rewrites / preserved invariants
  + inverse ambiguities
  + certificates / provenance / parameters / timeline
```

この契約を満たす図だけがReasonerへ候補を返せる。レイアウト、色、カメラ、アニメーションは
同じ状態から作れるが、`DESIGN HEURISTIC`であって証明には使わない。

## Diagram Atlas

| 図式族 | 明示する構造 | 主な合法操作 | 忘れるもの / 逆像の曖昧性 |
|---|---|---|---|
| 可換図式、string diagram、proof net、ZX | 合成、型、依存、等式 | 局所書換え、cut elimination、spider fusion | 具体座標、構文順序、同じ射を表す複数描画 |
| Hasse、Young、Bratteli | 半順序、包含、分岐、重複度 | 被覆関係の閉包、分岐の合成 | 非被覆関係、要素の内部表現 |
| quiver、Dynkin、Coxeter | 向き付き作用、根、生成関係 | reflection、mutation、word reduction | 表現の具体的実現、同型なラベル替え |
| tensor/Penrose、circuit、factor/Bayesian/computation graph | 添字縮約、依存、局所因子 | contraction、message passing、局所消去 | 計算順序または正規化定数、潜在変数の同定 |
| Cayley、Schreier、Bass-Serre、building、fundamental domain | 群作用、軌道、剰余、安定化群 | generator walk、orbit quotient、folding | 元の命名、基本領域の選択 |
| Voronoi、Delaunay、power、arrangement、visibility | 最近傍、双対、分割、可視性 | dualization、cell refinement、flip | 元点の絶対配置、退化時の非一意性 |
| knot、braid、simplicial/cell、Reeb、Morse-Smale、persistence | 接続、貼合せ、臨界点、filtration | Reidemeister move、collapse、persistence pairing | 埋込みの計量、同じ位相型の多数の表示 |
| phase/bifurcation/state transition | 軌道、安定性、分岐、到達性 | orbit quotient、cycle compression、basin split | 時間の絶対尺度、観測されない状態 |
| configuration/free space、roadmap、PRM/RRT、reachability | 衝突制約、可到達性、運動経路 | configuration lift、path search、refinement | 物体の外観、近似roadmapの欠落経路 |
| polytope、Schlegel、展開図、断面、投影 | incidence、境界、可視面、断面 | projection、section、unfold/fold | 奥行き、自己遮蔽、投影の多義性 |
| perspective、illusion、anamorphosis、moire、Gestalt | 観測写像、局所整合、知覚群化 | viewpoint change、inverse reconstruction | 一意な3D原像。局所整合でも大域非整合になり得る |

同じ「線と点」に見えても意味は異なる。例えばCayley図の辺は生成元の作用、factor graphの辺は
変数と因子の接続、string diagramの線は型付きwireである。この差を消すと、合法でない書換えを
別分野へ持ち込むため、汎用graphだけを核にはしない。

## Diagrammatic Representation Invariant

図式コンパイラ `D : SemanticState -> Diagram` が推論に利用可能である条件を、次で固定する。

1. `D`は元のsemantic IDを保持する。
2. `D`が保存する構造と忘れる構造を両方宣言する。
3. 各rewrite `r`は型付きpreconditionと保存不変量を持つ。
4. Reasonerへ戻す命題は、`D`上の見た目ではなく元の意味へ戻した証明義務で検証する。
5. `D(x)=D(y)`でも`x=y`とは限らない。逆像の曖昧性を型として残す。
6. レイアウト変更は意味輸送と別の層であり、証明状態を変えない。

図上の錯視はこの契約の例外ではなく、次のいずれかとして扱える。

- 観測写像の非単射性: 複数の3D対象が同じ2D像を持つ。
- 局所/大域不整合: 各部分は整合するが全体の原像が存在しない。
- 逆問題の事前分布依存: 補助条件なしに一意復元できない。

したがって、錯視を入力失敗として捨てず、`ambiguities`と追加観測の必要条件へ落とす。

## 図が推論へ効く因果経路

```text
型付き意味状態
  -> 構造を保存する図式化
  -> 合法な商・双対化・局所書換え
  -> 探索空間の縮約
  -> 候補不変量 / 中間命題
  -> 元の意味で独立検証
  -> 認証済み解答・証明・作問状態
```

単に図を描いて正答率が上がっても因果は示せない。今回の実験では自然言語parseと型付き入力を
A/Bで固定し、介入を「有限状態図による到達部分への制限と周期商」だけにした。

## 実験: finite-state recurrence diagram

### Hypothesis

有限環上の有限次数多項式漸化式は、直近`k`項を状態にすれば有限決定性力学系になる。
到達状態だけを構成して同じ完全状態の再出現を認証すれば、大きな添字を周期で縮約できる。

### Baseline

同一の型付き漸化式を、周期表現を作らず順に実行する。上限は10,000遷移。
上限を超えた場合は推測せず棄却する。

### Diagram

```text
carrier: (Z/mZ)^k のうち、初期状態から到達する状態
edge:    recurrence(state) による一意遷移
rewrite: reachable-subgraph -> first-repeat cycle quotient -> index reduction
invariant: recurrence edge / canonical residue / determinism / periodicity
forgotten: 元の整数の大きさ、閉形式、未到達状態
```

### Intervention

完全な状態が初めて再出現するまで到達軌道を作り、preperiod `mu`、period `lambda`を得る。
`n >= mu`を`mu + ((n-mu) mod lambda)`へ書き換える。値だけの一致ではなく、次数`k`の状態全体の
一致を要求する。

### Verifier

全状態を標準剰余へ正規化し、全辺を漸化式から再計算する。各状態の出次数が1であること、
最終辺が宣言された周期始点へ戻ること、preperiodとperiodがcarrier数と整合することを検査する。
正解値はグラフを保存しないFloyd法の独立oracleと照合した。

### Negative / Metamorphic

- 先頭5ケースの辺の出力値を1だけ改ざんし、検証器が拒否するか測定。
- 先頭8ケースの初期値と係数へ法の倍数を加え、同一の剰余図と答えになるか測定。
- source semantic IDを空にした入力を構築前に拒否。

### Benchmark

- 18ケース。線形、非斉次、高階、非線形多項式を含む。
- 公開過去問由来の型付き構造3件と、構造変形control 15件。
- parserはA/Bで固定。これは自然言語理解の実験ではない。
- dataset digest `3f5f5dd2dedef69a`、1並列、最大到達状態200,000。

### Result

| 指標 | 直接反復 | 有限状態図 |
|---|---:|---:|
| certified solve | 3/18 = 16.7% | 18/18 = 100.0% |
| wrong | 0 | 0 |
| abstention | 15 | 0 |
| newly closed | - | 15 |

追加指標:

- cycle candidate precision: `18/18 = 100%`
- 改ざんcertificateのfalse acceptance: `0/5`
- metamorphic preservation: `8/8 = 100%`
- 実行操作数: baseline `150,147`、diagram `707`

runtimeは同一PCの単一runではartifactに記録するが、Windows上の他プロセス負荷に影響されるため、
solve rateの根拠にはしない。

### Interpretation

この18ケースでは、図は説明ではなく探索の商を実行した。大きな添字を直接たどる代わりに、
最大253の到達状態で問題を閉じた。問題IDや答えの分岐はなく、線形・非線形を同じ
`state + transition + quotient`で処理している。

ただし、これは高校数学全体や自然言語ベンチの改善ではない。入力は型付き漸化式であり、
実数上の収束、単調性、閉形式、非有限状態の力学系はこの図式の対象外である。

## 同じ状態からのExperience

`/research/diagram`は認証済み図と同じJSONから生成する。

- 推論に使うもの: state、transition、period、index reduction、certificate。
- 表示だけに使うもの: tail-then-cycle配置、色、線幅、余白。

スライダーで時間を進めてもsemantic IDは変わらない。将来Web、3D、ロボット運動へ出す場合も、
同じcontractを参照し、表現固有の配置を証明へ逆流させない。

## 一次資料から採用した原則

- Selingerのgraphical language survey: 図式言語は型と意味論を持ち、分野ごとのcaveatがある。
  [A survey of graphical languages for monoidal categories](https://arxiv.org/abs/0908.3347)
- Bonchiら: 図式書換えを代数的意味論とsound/completeに対応させ得る。
  [Interacting Hopf Algebras](https://arxiv.org/abs/1403.7048),
  [Diagrammatic Polyhedral Algebra](https://arxiv.org/abs/2105.10946)
- Kschischangら: factor graphは局所因子分解を明示し、同じsum-product操作を多領域へ適用する。
  [Factor Graphs and the Sum-Product Algorithm](https://doi.org/10.1109/18.910572)
- LaValle: configuration spaceへのliftは、物体運動を経路探索へ変える。
  [Planning Algorithms](https://lavalle.pl/planning/)
- Edelsbrunnerら: filtrationの履歴がfeatureのbirth/deathを表し、静止画より多くの構造を保持する。
  [Topological Persistence and Simplification](https://doi.org/10.1007/s00454-002-2885-2)

IUT/anabelian geometryからは「異なる表現世界を無証明で同一視せず、輸送を明示する」という
研究上の規律だけを参考にする。今回のfinite-state実装へIUTの定理や用語を直接導入する
数学的根拠はないため、アルゴリズムとしての採用は棄却した。
