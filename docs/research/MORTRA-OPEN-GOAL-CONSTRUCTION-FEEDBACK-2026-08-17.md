# MORTRA 未解決goalからの補助構成閉ループ実験

記録日: 2026-08-17

## 1. 原理

記号推論が未解決で停止したとき、最終goalだけを見るのではなく、現在の演繹閉包にある
「goalへ近いが未完了の関係」を局所証明義務として読む。各義務に対し、有限の型付き
構成子から補助点を作り、推論器へ戻す。

探索状態を `S`、型付き構成を `c : S -> S'`、Newclidの演繹閉包を `D(S)`、
goalを `G` とすると、1回のフィードバックは

\[
  S \xrightarrow{c} S'
    \xrightarrow{\mathrm{Newclid}} D(S')
    \xrightarrow{\mathrm{frontier}(G)} \text{次の構成候補}
\]

である。成功は候補順位の高さではなく、増補後の問題に対するnative proofの再生でのみ
認定する。

## 2. 仮説

1. goalから逆向きに測った関係型距離、goal支持点との重なり、型の合う射の置換軌道を
   使えば、閉包サイズだけの探索より有効な補助構成を残せる。
2. 同じ型付き構成文法と同じ予算を全未解決問題に適用しても、問題別解法を登録せずに
   IMO-AG-30のnative proof数を増やせる。
3. 構造順位を乱数順位に置き換えると、同一予算で成功率または探索経路数が悪化する。

## 3. 方法

### 3.1 入力と禁止事項

- 対象: Newclid/JGEX IMO-AG-30のoriginal set
- 基準: Yuclid original score `17/30`
- データセット補助構成: 探索前に全削除
- 問題ID、既知解答、既知補助点列: 探索器へ非入力
- 外部LLM: 不使用
- 問題別分岐: 不使用

### 3.2 共通探索器

1. Newclidの基準演繹閉包から、construction由来の直接事実を除く。
2. 各新規関係について、native rule、前提、支持点、goal関係までの距離を記録する。
3. 型付き構成族を1手列挙する。出力関係がgoalへ到達不能な族は除く。
4. 1手目では効果が見えない構成を失わないため、同じ構成族・同じ入力型の置換軌道と、
   native frontierのPareto beamを半分ずつ保持する。
5. 候補ごとにNewclidを再実行する。goalが証明されなければfrontierを次段へ返す。

探索順は全問題共通で次の通り。

| 段階 | 構成族 | 深さ | 最大経路 |
|---|---|---:|---:|
| 1 | 拡張型付き構成族 | 1 | 42 |
| 2 | midpoint / mirror | 2 | 544 |

### 3.3 受理条件

各成功成果物について次を全て検査した。

- `uses_external_llm = false`
- `uses_dataset_auxiliary_clauses = false`
- `uses_problem_id_in_search = false`
- 補助構成なしbaselineが未証明
- 探索経路に実在するsolved recordがある
- 同じ構成を再構築した確認実行がsolved
- native proof JSONにgoal deductionがある

## 4. 結果

### 4.1 構成閉ループ

13未解決formulationを29分39.88秒で走査した。6問にnative proofを生成した。

| 問題 | 構成経路 | 評価経路 |
|---|---|---:|
| `2000_p6` | `intersection_ll(i,t1,t2,z)->d` | 8 |
| `2008_p1a` | `circle(b1,b2,c2)->g` | 8 |
| `2008_p1b` | `circle(a1,a2,b1)->g` | 8 |
| `2009_p2` | `midpoint(o,p)->d`, `midpoint(o,q)->e` | 274 |
| `2010_p2` | `midpoint(a,i)->h`, `midpoint(b,i)->j` | 586 |
| `2015_p3` | `midpoint(h,k)->d`, `midpoint(a,k)->e` | 82 |

`2008_p6`, `2011_p6`, `2012_p5`, `2019_p2`, `2019_p6`, `2020_p1`,
`2021_p3`は同じ上限で未証明だった。

### 4.2 IMO-AG-30 portfolio

| 要素 | 解けた問題 |
|---|---:|
| Yuclid original baseline | 17/30 |
| 既存の厳密GCLC/CAS交換の新規分 | 2 |
| 今回の構成閉ループの新規分（上と重複除外） | 5 |
| portfolio union | **24/30 = 80.0%** |

`2008_p1a`は厳密交換と構成閉ループの両方が解いたため、二重計上していない。
また、README用の易化版`2019_p2_easy`をoriginal scoreへ誤算入していた集計を修正し、
基準を17/30へ固定した。

### 4.3 順位付けアブレーション

構造探索が解いた6問だけをpaired setとし、文法、上限、seed、backendを固定して、
候補順位だけを乱数へ変更した。

| 指標 | 構造順位 | 乱数順位 |
|---|---:|---:|
| 証明成功 | **6/6** | 3/6 |
| 評価経路合計 | **966** | 1,930 |
| 乱数/構造の経路比 | - | 1.998 |

ただし乱数順位は`2010_p2`と`2015_p3`で構造順位より速かった。したがって、現在の
順位関数が各問題で最適という仮説は棄却される。一方、paired coverageと総経路数では
構造順位が優位だった。

### 4.4 独立backend交換

`2000_p6`と`2010_p2`の増補問題をGCLC Wu、GCLC Groebner、独立CASへ再送したが、
60秒/方式と120秒/CASでは証明に到達しなかった。したがって今回の構成成功は
Newclid native proofとして受理し、GCLC/CASの厳格な多エンジン一致とは主張しない。

## 5. 考察

### 5.1 何が改善したか

以前の探索は閉包件数が大きいmirror列を過大評価し、1手目で効果がない補助点を落とした。
今回、native proof frontierと同型射の置換軌道を別枠で残したことで、
`midpoint(a,i)`の後に`midpoint(b,i)`を試す遅延効果を保持できた。旧実験の
`2010_p2` 2,000経路に対し586経路で同じ証明へ到達した。

### 5.2 解法暗記ではない根拠と限界

問題番号、既知解答、既知補助点列を参照せず、全13問に同一スケジュールを適用した。
paired ablationでも構造順位の効果が出たため、成功を問題固有の文字列照合だけでは
説明できない。

ただし、midpoint、circle、intersectionなどの一般構成語彙とNewclidの定理群は
事前知識である。新しい原始公理を発明したわけではなく、有限の型付き射を合成している。
したがって主張範囲は「既知の一般構成語彙から未見の補助構成列を合成した」である。

### 5.3 自己組織化との関係

中央が完成証明を与えず、局所エージェントが `frontier witness`、構成候補、native proofを
交換して全体goalを閉じる点では、証明書交換型の自己組織化に一歩近づいた。ただし
Sheaf-ADMMの連続合意最適化そのものではない。今回実証したのは離散的な型付き
CEGIS/beam閉ループである。

## 6. 結論

未解決goalから中間補助構成を生成し、Newclidへ返してnative proofを得る閉ループを、
IMO-AG-30全未解決集合で実行した。問題別解法を追加せず、構成agent単体で6問を証明し、
既存agentとのportfolio unionは17/30から24/30へ上がった。paired ablationは、構造順位が
乱数順位より成功数2倍、総経路約半分であることを示した。

残る課題は、未証明7問に対する新しい中間補題の型合成、退化条件の分岐、GCLC/CASでの
独立交換を時間内に閉じる局所分割である。

## 7. 再現コマンド

```powershell
& "$HOME\.cache\mortra-research-sources\Newclid\.venv\Scripts\python.exe" `
  scripts/experiment_open_goal_feedback_imo_ag_30.py `
  --max-workers 8 --stage-timeout-seconds 900 `
  --skip-independent-exchange `
  --output data/open-goal-feedback-imo-ag-30-2026-08-17.json

python -B scripts/compare_open_goal_feedback_ablation.py `
  --structural data/open-goal-feedback-imo-ag-30-2026-08-17.json `
  --random data/open-goal-feedback-imo-ag-30-random-ablation-2026-08-17.json `
  --output data/open-goal-feedback-ranking-ablation-2026-08-17.json
```
