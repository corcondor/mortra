# MORTRA能力監査 2026-08-20

この文書は、画面・設計文書・単体テストの存在を数学能力の達成と混同しないための現状表である。
数値は再実行可能な成果物からのみ採用する。

## 実証済み

| 能力 | 現在の証拠 | 適用範囲 |
|---|---|---|
| 1問の解答 | `/api/solve`、公開Try UI、関連回帰36件成功 | 実行可能な型・CAS制約へloweringできる問題 |
| 2問の融合生成 | 親ごとの必須port、親除去ablation、厳密計算と独立再計算を通した固定実験1件 | 登録済みの型付き射で両親を接続できる場合 |
| 解答成果物 | 問題文、答え、解答、検証状態、TeX、図を同じ`ProblemArtifact`から生成 | plane/state/variation/calculus/morphism図にloweringできる場合 |
| 全問題.tex portfolio | 54/85内部検証、54/54 PDF生成 | 公式解答との外部照合は未完了 |
| IMO-AG-30幾何portfolio | 25/30、native replayまたは完全なWu/Groebner cover | 単一solverではなく厳密solver集合の和 |
| HAGeo frozen held-out | 51/89 = 57.30%、native証明書とhashを監査 | HAGeo-409中の固定held-out 89問 |
| Newclid連携 | 公式Yuclid実行系をnative proof判定に利用 | Newclid形式へ変換できる幾何問題 |
| 長時間ベンチ | shard再開、attempt進捗、timeoutのright-censor、証明書監査 | HAGeo Pass@K実験 |

## 部分実装

| 機構 | できていること | 未接続部分 |
|---|---|---|
| HAGeo型探索 | N-round/K-trajectoryとnumerical incidence gateの独立再構成 | 公式full codeは未公開で完全再現ではない |
| MMT | symbol assignment、theory view、push/pull、exact certificate coordinatorをHAGeo Pass@Kへ接続 | 固定3問で46〜55 factsを導出したが親義務の直接閉鎖0、追加正答0 |
| Sheaf-ADMM | CPU上の疎channel更新、密行列版との小規模数値一致 | 実問題で追加正答なし。固定例ではrandomより5.99倍遅い |
| 作図 | 平面図、状態遷移図、増減表、関数概形、射列を成果物へ表示 | 任意問題から必要な補助図を自律発見する一般作図器ではない |
| 自律作問 | 実行可能な既知射の合成、親依存性・新規性・検証gate | 未知の原始射を任意の親問題から必ず発明する完全性はない |

## 未実装・未実証

- 高校数学全体または任意の未知問題に対する完全な解答能力。
- 任意の二親から、必ず自然で非自明な融合問題を返す能力。
- `MMTExactCoordinator`を使ったagent間証明交換によるベンチマーク改善。配線はあるが改善は未実証。
- Sheaf-ADMMまたは微分可能回路による自己組織化の得点向上。
- FPGAのRTL、bitstream、実機実行、実測速度向上。
- HAGeo論文の公式full codeと同一条件での完全再現。
- `全問題.tex`全85問の公式解答との外部照合。

## 直近の反証結果

未証明5問を`N=8, K=128`へ深くして640軌道を完走したが、新規証明は`0/5`だった。
従って、現在の残差を単に探索深さだけで説明する根拠はない。次の改善対象は、open proof residualから
新しい中間補題・補助構成を型付き合成する閉ループと、その証明書を必要なagentへだけ渡す実行配線である。

## 主張してよい数字

- IMO-AG-30厳密portfolio: `25/30 = 83.33%`。
- HAGeo固定held-out: `51/89 = 57.30%`。
- `全問題.tex`内部検証portfolio: `54/85 = 63.53%`、ただし公式解答照合ではない。

上記以外の「全数学への汎化」「自己組織化で向上」「FPGA化済み」は現時点では主張しない。
