# Newclid型付きstalk補助構成実験

## 目的

Newclid/YuclidのIMO-AG-30未解決証明義務へ、LLMを使わずに補助構成を提案し、
native verifierが受理する証明を増やせるかを測る。問題ID、正解、データセット付属の
補助構成は探索順位へ使わない。

この段階で検証する仮説は限定的である。

> 型付き幾何グラフとgoal supportから定まる有限順位だけでも、少なくとも一部の
> 未解決義務について、証明を可能にする補助構成をランダム探索より早く発見できる。

## 入力経路の修復

旧JGEX入力には、出力点を左辺と右辺の両方へ書く方言、右辺だけへ書く方言、
左辺を省く方言が混在していた。旧builderは5問を構文エラーにしており、探索以前に
公式Newclidと異なる入力集合を実行していた。

`jgex_legacy_normalizer.py`は、個別問題名を参照せず、各definitionの型付き
`output_points`と左辺の点列を照合して正規形へ変換する。この修復だけで次を得た。

| 経路 | 正答 | 入力エラー |
|---|---:|---:|
| 旧JGEX heuristic経路 | 14/30 | 5 |
| 型付き正規化 + ratio-only | 16/30 | 0 |
| 型付き正規化 + all-AR | **17/30** | **0** |

したがって、公式Newclidのall-AR `17/30`を同じ30問で復元できた。ここは探索性能の
改善ではなく、比較可能な入力契約の回復である。

## 型付きstalk探索

最初の構成族を次の射に固定した。

```text
midpoint : Point x Point -> Point
```

各問題を有限の型付きincidence graphへ写し、goalに現れる点をsupportとする。
候補`midpoint(p,q)`は、`p,q`からgoal supportまでのグラフ距離と、goal引数としての
出現多重度だけで順位付けする。問題ID、模範解答、付属auxiliary clauseは使わない。

各候補を追加するたびにYuclid all-ARを実行し、導出閉包の増分を反例・進捗信号として
次のbeamへ返す。採用条件はスコアではなく、Yuclidがgoalを証明しnative proof JSONを
出力できることである。これは無制限グラフ探索ではなく、型が一致する有限項のCEGISである。

## 結果

校正問題`2000_p6`では、付属auxiliary clauseを隠した状態から5番目の候補
`midpoint(b,i)`を発見し、native proofを得た。座標seed 0, 1, 2でも同じ構造を選び、
**3/3**で証明を再生した。

候補予算を5に固定した比較では、構造順位は`1/1`、ランダム順位10試行は`0/10`だった。
ただし校正問題1問上の比較なので、一般的優位の統計的証明ではない。

設計後に固定した残り12問へ同じ`midpoint`族、同じ順位、候補上限8を適用した結果は
**0/12**だった。従って現時点の数値は次のように読む。

| 指標 | 結果 | 解釈 |
|---|---:|---|
| 正規化後の再現baseline | 17/30 | 公式all-AR経路の復元 |
| 校正問題を含む探索後 | 18/30 | post-design calibration |
| 固定残り12問での追加 | 0/12 | 未見一般化は未確認 |
| 付属補助構成を与えたoracle上限 | 25/30 | verifierはさらに8問を証明可能 |

oracle `25/30`は探索スコアではない。中点だけの段階では「正しい補助構成が得られれば、
現在のverifierで少なくともあと7問分の余地がある」ことを分離して示す診断値だった。
多族探索で2問目を加えた開発値`19/30`との差は6問である。

## 何が確立し、何が未確立か

確立したこと:

- JGEX方言を型情報で正規化し、問題別分岐なしに公式`17/30`を復元した。
- 未解決義務から有限の補助構成候補を作り、exact verifier feedbackで1件のnative proofを得た。
- 同一候補予算では、校正例上で構造順位がランダム順位より先に証明へ到達した。
- 外部LLM、問題ID分岐、答え参照は使用していない。

## 動的な多族探索

中点実験後、構成文法を次の7射へ拡張した。

```text
midpoint        : Point x Point -> Point
mirror          : Point x Point -> Point
foot            : Point x Point x Point -> Point
circle          : Point x Point x Point -> Point
orthocenter     : Point x Point x Point -> Point
reflect         : Point x Point x Point -> Point
intersection_ll : Point^4 -> Point
```

各射は入力役割の対称性を宣言し、生成した点を次段の入力へ戻せる。族ごとの候補枠を
round-robin配分し、低arityの射だけがbeamを占有しないようにした。

開発問題`2020_p1`では、データセット付属の`intersection_ll -> reflect`を隠した状態から、
探索器が次の別構成を発見した。

```text
reflect(b,c,o)
reflect(a,d,o)
```

この2点を追加するとYuclidがgoalを証明した。付属補助構成とは異なるため、模範補助点の
文字列復元ではない。座標seed 0, 1, 2で**3/3**再現し、変更後の退化候補filterでも
41経路・error 0で再証明した。同一の候補数、beam幅、深さによるランダム順位は**0/2**だった。

従って開発集合上では`17/30 -> 19/30`となった。ただし`2000_p6`と`2020_p1`は設計と診断に
使ったため、これはheld-out scoreではない。

7族を固定して未見`2011_p6`へ適用した結果は`0/1`だった。224経路中124経路が退化構成で
失敗したため、definitionの`diff / ncoll / npara`を数値proposal filterへloweringした。
数値は候補除去だけに使い、証明採否には使っていない。再実行では無効経路が
`124 -> 42`へ減ったが、正答は増えなかった。

未確立のこと:

- `midpoint`一族だけでは固定12問を1問も改善できず、広い幾何一般化は示していない。
- NewclidとGCLCの途中証明義務を相互にrestrictionする実行時協調は未接続である。
- `19/30`をAlphaGeometry系の論文スコアやIMO全体性能として主張できない。

## 次の反証可能な実験

次は問題ごとのheuristicではなく、構成の論理前提とgoal predicateをstalkのrelation channelへ追加する。

```text
carrier channel  : Point / Line / Circle
relation channel : coll / perp / para / cyclic / cong / eqangle
requirement      : diff / ncoll / npara
restriction      : local derived predicates -> shared goal support
```

各族は同じ`source type -> target type`契約とnative proof gateを保つが、閉包総数ではなく
goalと同型の述語channelへ届いた導出を優先する。devでrestrictionと探索予算を固定した後、
現在の問題を再び変更用に使わず、別のfrozen集合で
Newclid単体、GCLC単体、単純和集合、stalk協調を同一timeoutで比較する。

受理条件は、追加正答がnative certificateで再生でき、ランダム順位を同一予算で上回り、
異なる問題でも同じ型付き射が発火することである。満たさなければ協調仮説を棄却する。

## 再現物

- 集約: `data/imo-ag-30-newclid-typed-stalk-comparison-2026-08-15.json`
- 正規化baseline: `data/newclid-jgex-normalized-all-ar-imo-ag-30-2026-08-15.json`
- oracle: `data/newclid-jgex-oracle-aux-unresolved13-2026-08-15.json`
- 校正seed: `data/newclid-midpoint-stalk-2000-p6-seed{0,1,2}-2026-08-15.json`
- 固定12問: `data/newclid-midpoint-stalk-heldout-*-2026-08-15.json`
- ランダムablation: `data/newclid-midpoint-random-ablation-seed*-2026-08-15.json`
- 多族の別解発見: `data/newclid-dynamic-stalk-2020-p1-*-2026-08-15.json`
- 多族ランダムablation: `data/newclid-dynamic-stalk-2020-p1-random-seed*-2026-08-15.json`
- 未見probe: `data/newclid-dynamic-stalk-heldout-2011-p6*-2026-08-15.json`

native proof本体は各数十MBのためGit管理せず、compact report内のcommandとhashから再生成する。

## Relation channel実験

### 科学的仮説

閉包の総数だけを最大化すると、目標証明と無関係な導出が多い枝も高く評価される。
一方、`coll / perp / para / cyclic / cong / eqangle`を独立channelとして保持すれば、
目標へ必要な局所情報を失わずに探索枝を比較できる可能性がある。

ただし「目標と同じchannelの事実数」だけでも不十分である。Newclidのnative rule表では、
例えば次のように異なる関係型を経由して証明が進む。

```text
perp -> para -> coll -> eqangle -> cyclic -> cong
```

そこで`DEFAULT_RULES`のpremise/conclusionから、目標channelへの逆向き距離を問題非依存に
計算した。各候補では、親問題で既知のassertionと`By construction`直後の自明なassertionを
除外し、逆向き到達可能な新規assertionだけを距離減衰付きで数える。採否は従来どおり
Yuclid native verifierだけが行う。

### Ablation

`2020_p1`で候補文法、候補数、beam幅、深さ、seedを固定した。

| 第2段順位 | 結果 | 評価経路 | 解釈 |
|---|---:|---:|---|
| closure総数 | solved | 41 | 既存成功baseline |
| 目標channelのみ | unsolved | 150 | 自明な合同関係を過大評価 |
| native rule遷移 | solved | 41 | 正しい2構成をbeamへ回復 |

遷移版の第1層上位は`reflect(b,c,o)`、`reflect(a,d,o)`で、最終証明に必要な2構成と一致した。
これは問題別解法を登録した結果ではなく、全問題共通のnative rule表から計算した順位である。

一方、固定未解決問題`2011_p6`ではclosure版も遷移版も`0/224`、無効候補はどちらも42だった。
従ってrelation遷移は悪い順位を修正したが、現行7構成族・深さ2の表現力不足を解消していない。
開発値は`19/30`のままであり、held-out改善は0である。

## Newclid / GCLC typed boundary監査

GCLC公式8例の複数行`prove`構文を解析し、証明済みgoalを共通relation channelへloweringした。
Newclid側は利用可能なIMO-AG 29形式化（sourceに`2000_p1`が欠落）についてgoalと
native rule逆向き閉包を集計した。

| 指標 | 結果 |
|---|---:|
| Newclid goal channel | 7 |
| GCLC proved channel | 5 |
| goal同士の共通channel | 4 |
| 共通channel | `coll`, `eqratio`, `para`, `perp` |
| channel-level委譲候補 | 203 pairs |
| cross-engine certificate replay | 未接続 |

203は「GCLCの証明済み型がNewclidの逆向き証明閉包に現れる問題・例の組数」であり、
追加正答数ではない。GCLCの多項式証明をNewclidの具体的な点、仮定、非退化条件へ戻す
certificate loweringがないため、ここで正答率改善は主張しない。

### 次の実装境界

次はrelation名だけでなく、具体的な型付きobligationを交換する。

```text
Newclid open predicate(points, assumptions)
  -> GCLC construction + conjecture
  -> Wu/Groebner certificate
  -> predicate(points, assumptions, nondegeneracy)へ再lowering
  -> Newclidでreplay
```

受理条件は、同一timeoutでNewclid単体より追加正答が得られ、GCLC証明書をnative仮定から
再生できることである。channel一致だけ、閉包増加だけでは成功と数えない。

追加再現物:

- target-only反証: `data/newclid-relation-stalk-2020-p1-delta-2026-08-15.json`
- rule遷移成功: `data/newclid-relation-transition-stalk-2020-p1-2026-08-15.json`
- 未見未改善: `data/newclid-relation-transition-stalk-heldout-2011-p6-2026-08-15.json`
- GCLC境界監査: `data/newclid-gclc-relation-exchange-audit-2026-08-15.json`

## Concrete certificate roundtrip

Relation名だけの監査から、具体的な点・構成式・NDG・結論多項式を交換するbridgeへ進めた。
GCLC公式5例ではWu法`5/5`、Gröbner法`3/5`、独立exact replay`5/5`だった。
Pappus 2例はGröbnerの上限を60秒から120秒へ延ばしても時間切れだったが、Wu法の提案を
構成順有理消去で独立再生できた。両native方式必須なら`3/5`、少なくとも1方式と独立再生を
要求するportfolio条件なら`5/5`である。

同じ設計をJGEXの`r_triangle / foot / on_line / on_circle`へ拡張すると、baselineで未解決の
`2012_p5`を補助構成なしでexact remainder 0として検証した。従ってNewclid-native値は
`17/30`のままだが、記号portfolioは`18/30`になった。問題名分岐はなく、点名変更で再生し、
結論改変では拒否する回帰試験を固定した。

詳細: `docs/research/GCLC-NEWCLID-CERTIFICATE-BRIDGE-2026-08-15.md`

### 固定未解決13題への継続

決定的射`triangle / midpoint / orthocenter / circumcenter`と、同一直線・同一円上の異なる
2交点に対する一般差分商を追加し、1題ごと120秒で固定13題を再実行した。

```text
proved 2 / unsupported 10 / timeout 1 / unproved 0
```

追加証明は`2008_p1a`と`2012_p5`で、記号portfolioは`17/30 -> 19/30`になった。
`2008_p1a`では3組の交点が異なるというNDGを明示し、37項のGroebner quotient certificateを
剰余0まで再生した。6点共円の`2008_p1b`は120秒timeoutであり、成功に数えていない。
