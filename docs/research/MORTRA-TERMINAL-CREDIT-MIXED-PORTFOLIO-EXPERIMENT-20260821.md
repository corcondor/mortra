# MORTRA terminal-credit mixed portfolio experiment

実施日: 2026-08-21

## 目的

終端証明から逆向きに与えた信用だけで候補集合を占有すると、未見問題で探索多様性を失う。そこで、各 round の4候補を「凍結済み信用候補1本 + 現在の証明残差から選ぶ候補3本」とし、同一予算の残差候補4本と比較した。

検証仮説は次の通りである。

1. 信用候補を1枠に制限すれば、過去の成功軌跡を利用しながら残差探索を維持できる。
2. native verifier が4候補を同時に比較すれば、信用と局所証明進捗が一致した候補だけを採用できる。
3. その結果、未見問題で追加正答または未解決証明義務の減少が生じる。

## 方法

### 実装

- `residual-portfolio`: incidence hard gateを開き、型付き残差ランキングの上位4候補をYuclidで並列検証する対照方策。
- `terminal-credit-mixed`: 正の終端信用を持つ候補を最大1本だけ入れ、残り3枠を対照方策と同じ残差候補で埋める処置方策。
- traceへ各候補の `selection_channel` を保存し、信用枠と残差枠のどちらが最終採用されたかを監査可能にした。
- 信用台帳は開発3問のnative certificateだけから作成し、評価中は凍結した。問題ID、期待解、座標値は信用signatureに含めない。

### 固定条件

- 評価集合: 開発・以前の転送評価に使っていないHAGeo未解決10問。
- `N=1`, `K=1`, seed `31`。
- 候補上限32、incidence preselect 48、各roundのYuclid検証4本、worker 4。
- 対照と処置で問題、seed、探索予算、検証数を一致させた。
- native Yuclid certificateだけを正答とした。時間切れと実行失敗を不正解へ混ぜず、別に数えた。

## 結果

| 指標 | 残差4本 | 信用1本 + 残差3本 |
|---|---:|---:|
| 完全観測 | 10/10 | 10/10 |
| 正答 | 0/10 | 0/10 |
| 時間切れ | 0 | 0 |
| 実行失敗 | 0 | 0 |
| Yuclid候補検証 | 40 | 40 |
| 未解決relation demands合計 | 202 | 202 |
| ar_known_rank合計 | 466 | 468 |
| cohort wall time | 97.458秒 | 112.945秒 |

処置群では10問すべてで正確に「信用1本 + 残差3本」が形成された。最終採用は信用枠2問、残差枠8問だった。対照群から経路が変わったのは1/10問で、`2005CTSTp11b` が `parallelogram(a,b,c)->d` から `foot(a,c,b)->d` に変わった。この変更は既知関係を118から120へ増やしたが、未解決relation demandsは24のままで、終端証明には到達しなかった。

凍結台帳の最上位の文脈非依存creditは `foot(given,given,given)` だった。全10問の候補集合に `foot` が存在したため、信用枠は全問で `foot` に占有された。これは多様な成功軌跡の転送ではなく、抽象化の粗い階層creditが単一morphismへ崩壊した結果である。

## 考察

仮説1の機構的部分は成立した。信用枠を1本に制限し、残り3本の残差探索を維持できた。仮説2も機構として成立し、verifierは8/10問で信用候補を退けた。しかし、仮説3の追加正答・証明残差減少は観測されなかった。

したがって「正の終端信用を増やせば未見問題で改善する」という説明は支持されない。現在のhierarchical forgettingは、点名や問題IDを忘れるだけでなく、どの未解決義務を閉じた信用かまで忘れている。morphism familyだけのcreditは `foot` の頻度priorになり、局所的な証明有用性を表していない。

処置群はcohort wall timeで15.9%、問題単位平均で18.9%遅かった。追加検証数は同じなので、主因は信用signature生成・照合と、選ばれた候補による証明計算差である。正答が増えていないため、このコストは現状では正当化できない。

## 結論

「信用1本 + 残差複数本」という混合制御は実装・監査できたが、この固定10問・固定予算では追加正答0、残差減少0であった。負の結果として仮説を棄却する。

次の実験で必要なのは信用値の増量ではない。終端証明の各構成が具体的に閉じたtyped obligationを記録し、未解決goalとのunificationが成立した場合だけ信用枠へ昇格させる必要がある。比較対象は同じ残差portfolioとし、以下を事前受理条件にする。

1. 文脈非依存morphism creditだけでは候補を昇格させない。
2. 候補のpostconditionと現在のopen obligationが型付き単一化できる。
3. 1-step verifierで親の未解決義務を少なくとも1つ閉じる、またはbackward obligationを厳密に減らす。
4. 凍結未見集合で追加正答または残差減少を示す。

## 再現物

- cohort: `data/terminal-credit-mixed-frozen-probe10-2026-08-21.txt`
- frozen ledger: `data/terminal-credit-development-ledger-3problems-hierarchical-2026-08-21.json`
- control: `data/terminal-credit-mixed-probe10-control-n1-k1-f4-2026-08-21.json`
- treatment: `data/terminal-credit-mixed-probe10-treatment-n1-k1-f4-2026-08-21.json`
- machine-readable audit: `data/terminal-credit-mixed-portfolio-audit-2026-08-21.json`
