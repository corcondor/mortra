# MORTRA 未証明問題の全件再実行と証明書監査（2026-08-24）

## 目的

凍結HAGeo 89問について、厳格集合和で未証明だった34問を省略せず再実行し、
MORTRAが保存した証明結果を直接読み、独立再生できた問題だけを認証集合へ加える。
時間打切りは不正解にせず、証明DAG・未充足前提・候補経路を保存する。

## 原理

- 候補生成と真偽判定を分離する。補助構成候補は型付き探索で作るが、正解判定はnative Yuclid証明書だけで行う。
- 問題ID、期待解答、外部LLMは探索・判定に使わない。
- `solved`だけでは採用せず、入力・証明SHA-256と二度の決定的再生を一致させる。
- 証明の全deductionを読み、前提の生成元が欠けた証明や曖昧な等式参照を拒否する。
- 数値guardはnative証明書の一部として明示するが、完全に形式化されたguard-free証明とは呼ばない。

## 方法

1. 現行native基準を89問で再実行した（`data/hageo-409-current-native-certified-rerun-2026-08-24.json`）。
2. 旧厳格集合和55問との差集合34問を固定し、各問で深さ2、最大112経路を探索した。
3. 経路、証明DAG、未充足前提、列挙済み候補を問題別checkpointへ保存した。
4. 得られた全証明を別プロセスで二度再生し、全deduction traceを監査した。
5. 凍結89問の外側を拒否する集合和で、重複を除いて再集計した。
6. 元のJGEX式または認証済み補助構成込み式から図を生成し、証明済みは監査済み全deduction、未証明は状態文を出力した。

## 結果

### 現行native基準

- native solved: **28/89**
- 二重再生受理: **28/28**
- trace整合: **28/28**
- 読み取ったdeduction: **3,757**
- 数値guard: **948**
- 表現chart間bridge: **37**
- 未接続前提: **0**、曖昧な等式参照: **0**

### 厳格未証明34問の再実行

- 証明: **2**
- 探索完了・未証明: **31**
- 時間打切り: **1**
- 実行エラー: **0**
- 独立再生受理: **2/2**

| 問題 | 補助構成経路 | deduction | 数値guard | 終端命題 |
|---|---|---:|---:|---|
| `2014BulgariaMOp6` | `['excenter(b,a,c)->g']` | 186 | 50 | `cyclic(a,b,c,p)` |
| `2016G6` | `['parallelogram(a,b,c)->g']` | 420 | 93 | `perp(a,c,p,q)` |

### 凍結集合和

- 再実行前: **55/89**
- 新規の一意な認証: **2問**
- 再実行後: **57/89 = 64.04%**
- native 28/89と厳格集合和を混同しない。前者は単一実行系、後者は監査済みportfolioの集合和である。

### 図・解答成果物

- 要求: **34問**
- 図生成: **34問**
- 成果物出力: **34問**
- 認証済み証明本文: **2/2問**
- 図が描けたこと自体は証明成功として数えていない。

## 考察

以前の再実行が全件にならなかった直接原因は、既定上限10問、native未証明61問と厳格未証明34問の混同、
証明ファイルの未保存、診断用progressを真の再開状態として扱ったこと、Windows上の非原子的な進捗更新だった。
今回、明示的34問名簿、既定全件、証明保存、列挙済み候補を含むcheckpoint、原子的更新へ修正した。
また、3問だけの再試行が同じ集計先を上書きする欠陥を検出した。個別成果物33件と右打切り記録1件から34問集計を再構成し、
今後は問題集合が異なる既存レポートへの上書きを実行前に拒否する。

未証明は『誤答』ではない。有限探索で証明書が閉じなかったという観測であり、
原因の推測ではなく、各問題の実際の構成経路、証明DAG、未充足前提をdossierに残した。
dossierは **32問**を含む。

## 結論

MORTRAの結果は読める。今回、証明済み問題では全deductionと依存関係を直接読み、二度の再生で照合した。
未証明問題も全件を再実行し、停止状態を問題別に保存した。認証集合へ加えたのは再生監査を通った問題だけである。

## 成果物

- native再実行: `data/hageo-409-current-native-certified-rerun-2026-08-24.json`
- native再生監査: `data/hageo-409-current-native-certified-rerun-2026-08-24-audit.json`
- native trace監査: `data/hageo-409-current-native-certified-rerun-2026-08-24-trace-audit.json`
- 未証明34問再実行: `data/hageo-409-strict-unresolved34-depth2-rerun-2026-08-24.json`
- 補助構成証明監査: `data/hageo-409-strict-unresolved34-depth2-rerun-2026-08-24-audit.json`
- 厳格集合和: `data/hageo-certified-capability-union-current-rerun-2026-08-24.json`
- 未証明dossier: `data/hageo-409-strict-unresolved34-depth2-dossiers-2026-08-24.json`
- 図・解答manifest: `data/hageo-strict-unresolved34-solution-artifacts-2026-08-24.json`

### 時間打切り問題

`2015IranTSTp18`
