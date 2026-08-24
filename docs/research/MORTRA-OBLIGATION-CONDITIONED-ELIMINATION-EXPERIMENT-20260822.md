# MORTRA 型付き義務条件付き消去実験

## 目的

多項式補題から型付き幾何関係への逆精緻化が接続できても、局所消去が
Newclidの未解決義務と無関係な補題だけを生成すれば得点には寄与しない。
そこで、open typed obligationを座標多項式へ順精緻化し、同じ代数予算内で
意味的に近いseparatorを優先する消去順序を検証する。

## 原理と仮説

型付き義務 `r` の座標像を `F(r)`、消去候補の代数コストを `C`、意味整合度を
`S` とする。処置群は問題ID、数値、表層文型を使わず、次のepsilon制約を使う。

1. 最小次数の候補だけを残す。
2. fill-inとseparator幅が最小値+1以内の候補だけを残す。
3. その集合内で、separatorと`F(r)`の単項式支持および変数支持の近さを最適化する。
4. 正しさは探索スコアで決めず、既存の恒等式証明書とNewclid再生で決める。

仮説は、`C`をほぼ固定した候補間で`S`を使えば、処理量を落とさずopen obligationを
閉じる多項式補題が増える、である。

## 実装

- `local_polynomial_elimination.py`: `obligation_conditioned`順序、epsilon制約、候補separatorの単項式支持評価。
- `chordal_buchberger_elimination.py`: 同じ制御をclique選択へ接続。
- `construction_block_proof_dag.py`: 型付き関係をJGEX chartで順変換し、仮定には加えず探索順位だけへ渡す。
- `run_jgex_exact_specialist.py`: process境界で`--guidance-relations`を受け取り、checkpointへ順序と証明ノードを保存。
- `polynomial_obligation_alignment.py`: 係数に依存しない単項式支持比較。証明器ではなく探索ヒューリスティックである。
- `experiment_obligation_conditioned_elimination.py`: control/treatmentを同一マシン上で逐次実行する。

## 方法

HAGeo-409の固定未解決問題について、Yuclidからopen AND-branchesを取得する。
ground化できる`lequation/perp/...`だけを順変換し、controlは`min_fill`、treatmentは
上記epsilon制約を使う。各armの時間・代数予算は同一で、timeoutはright-censorとして
完了済みの再生可能証明ノードを比較する。

評価量は追加正答、回収した新規open relation、局所node数、separator node数、
replayed polynomial数、選択変数列、cost/alignment rankである。

## 結果

### 合成因果テスト

同一1-step予算・同一代数コストの2候補では、controlが無関係な枝を選ぶ一方、
treatmentだけが目標separator `y-b=0` を生成した。したがって配線とepsilon制御は
機能している。

### 2016G6、逐次45秒/arm

| 指標 | control | treatment |
|---|---:|---:|
| solved | 0 | 0 |
| local nodes | 9 | 9 |
| separator nodes | 2 | 2 |
| replayed polynomials | 20 | 20 |
| recovered open relations | 0 | 0 |

選択変数列も一致した。すべての保存済み局所証明書はreplayした。

### 2024PlanetCupp10、逐次45秒/arm

| 指標 | control | treatment |
|---|---:|---:|
| solved | 0 | 0 |
| local nodes | 6 | 6 |
| separator nodes | 4 | 4 |
| replayed polynomials | 51 | 51 |
| recovered open relations | 0 | 0 |

変数支持スコアは候補を区別したが、epsilon制約内の選択変数列は一致した。

### 単項式支持追加、2024PlanetCupp10、逐次30秒/arm

単項式支持を加えても選択列、6 local nodes、4 separator nodes、51 polynomials、
追加正答0が一致した。

初期の「意味距離を代数コストより優先」する版は、並列70秒実験でtreatmentの
保存node数を12から8へ減らした。ただし並列CPU競合を含むため主結果には使わない。
この観測を受け、逐次実行とepsilon制約へ修正した。

## 考察

実装上の接続不良ではない。型付き義務はprocess境界を通り、座標多項式へ変換され、
順序制御に入り、全証明書が再生された。しかし固定実問題では追加正答0だったため、
支持集合の近さだけで有用な中間補題を予測できるという仮説は支持されない。

主因は、実際の座標chartでは多くの構成点が祖先パラメータを共有し、異なる幾何関係の
多項式像が同じ変数・類似単項式を持つことである。次の目的関数には、支持ではなく
`F(r)`を候補separator idealで簡約したnormal-form residual、または別chartで次数を
下げた残差が必要である。

## 教科書的表現との接続

- 複素座標は円、角、相似の関係を複素共役・偏角・比へ写し、実座標chartで区別不能な関係を低次数化する候補である。
- Cramer、rank、determinant、nullspaceはincidenceと`lequation`の線形部分を直接扱う。
- 正弦・余弦定理、三角恒等式、Heronは辺長・角・面積の型付きviewを与える。
- Muirhead、重み付きAM-GM、Schur、Chebyshev、並べ替え、凸性、Holderは対称多項式・majorization・凸性の別theoryとし、同じ証明書交換規約へ接続する。

これらは解法テンプレートとして覚えず、型付き対象間の証明付きviewとして実装する。

## 結論

義務条件付き消去は実装・再生でき、合成因果例では同一予算で目的補題を生成した。
一方、固定未解決2問では追加正答0であり、実問題への有効性はまだ示されていない。
次の本質的実験は、候補separatorによるtyped obligation polynomialのbounded normal-form
residualを比較し、実座標・複素座標・辺長/角・線形代数chartのどれが残差を最も下げるかを
同一予算で選ぶrepresentation atlasである。

## 再現物

- `data/obligation-conditioned-elimination-sequential-2016g6-2026-08-22.json`
- `data/obligation-conditioned-elimination-sequential-2024planet-2026-08-22.json`
- `data/obligation-conditioned-elimination-monomial-2024planet-2026-08-22.json`
