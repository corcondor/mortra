# MORTRA 遅延proof-DAGスケジューラ実験

記録日: 2026-08-18

## 1. 問い

MORTRAのOR保存proof-DAGは、未解決goalから候補構成までの依存関係を表現できる。
しかし全候補について同じ深さまでforward coneを作ると、証明に寄与しない候補にも同じ
計算量を支払う。本実験は、残差が改善する候補だけを深く展開する遅延スケジューラが、
証明能力を落とさず探索量を減らせるかを測る。

## 2. 原理

proof-DAGのOR分岐を `B`、候補構成 `c` からのforward coneを `F(c)` とする。
候補の価値は、単なる述語名一致ではなく、あるmeet後に残る未証明義務

\[
  R(c,b)=b\setminus F(c), \qquad b\in B
\]

で測る。ただし `|R|` が減っただけでは証明可能性の十分条件ではない。型付き構造義務が
全て閉じた候補だけが既存スケジューラを上書きでき、部分meetは内部探索のpromotionに
だけ使う。この分離を trust gate と呼ぶ。

実装上は次の三段階である。

1. 全候補を小予算で観測する。
2. 述語到達距離、既知引数重複、残差改善で上位候補だけをpromotionする。
3. 型付き構造残差が0になった候補だけを最終順位で優先する。

親prefixは既知factとして共有し、候補自身の寄与には数えない。これは親の成果を子候補が
横取りする誤ったcredit assignmentを防ぐ。

## 3. 半導体アーキテクチャとの対応

この設計はRISC-Vそのものではないが、次の対応は実装原理として有効である。

| MORTRA | 計算機アーキテクチャ |
|---|---|
| 有限の型付き述語・射 | ISAの命令形式 |
| 定理適用 | 命令実行 |
| proof-DAG | dataflow依存グラフ |
| 中間命題 | 値を運ぶtoken |
| residual-guided promotion | ready命令の動的schedule |
| 部分meet | speculative execution |
| native proof replay | retirement / commit検査 |
| alpha同値・prefix cache | 共通部分式共有 / cache |

RISC-Vの参考点は、小さい基底ISAと直交的な拡張を分けることである。MORTRAでも小さい
数学核に幾何、整数、確率などの拡張語彙を載せる。ただしRISC-Vは補助構成の発見法では
なく、数学的意味と探索方策は別に設計する必要がある。現在のproof-DAGは、命令が入力
tokenの準備後に発火するdataflow machineにより近い。

## 4. 方法

- 対象: `2008_p6`, `2009_p2`, `2010_p2`, `2015_p3`, `2011_p6`
- 外部LLM: 不使用
- 問題ID、期待答、既知補助構成: 探索器へ非入力
- 正答判定: Yuclid native certificate replayのみ
- 比較:
  - `off`: proof-DAG順位なし
  - `fixed_meet`: 全候補を固定予算で展開
  - `lazy_ungated`: 残差で遅延展開するが部分meetも最終順位へ使用
  - `lazy_trust_gate`: 部分meetは探索内だけ、閉じた残差だけ最終順位へ使用

さらに `2015_p3` を別プロセスで再実行し、入力SHA-256と最終構成列の一致を検査した。

## 5. 結果

| 条件 | solved | native評価経路 | cone状態 | backward状態 | wall time |
|---|---:|---:|---:|---:|---:|
| off | 2/5 | 93 | 0 | 0 | 246.38 s |
| fixed meet | 2/5 | 98 | 77,199 | 39,558 | 636.05 s |
| lazy ungated | 2/5 | 100 | 28,533 | 39,558 | 469.40 s |
| lazy + trust gate | **2/5** | **89** | **28,533** | 39,558 | **390.13 s** |

`lazy + trust gate` はfixed meetに対して、cone状態を48,666件、63.04%削減し、壁時計を
38.66%削減した。証明数は同じである。offに対してもnative評価経路は93から89へ減ったが、
proof-DAG構築のため壁時計は143.75秒増えた。

決定性検査では、`2015_p3`の入力hashと成功経路
`intersection_lc(a,f,h)->d` がoff/lazyで一致し、評価経路は12から9へ減った。

## 6. 考察

### 6.1 支持された仮説

OR保存DAGは候補スケジューラの基盤として機能する。全候補同深度探索ではなく、残差が
改善する候補だけをpromotionすれば、証明を失わず探索量を削減できる。

### 6.2 棄却された仮説

部分meetをそのまま「良い候補」の証拠にする仮説は棄却された。`lazy_ungated`はfixedより
cone状態を減らしたが、native評価経路を98から100へ増やした。部分meetは必要条件でしか
なく、最終順位を上書きするには構造残差の閉鎖が必要である。

### 6.3 現在の本質的ボトルネック

今回の5問ではcoverageは2/5のままである。したがって次の支配項はschedulerではなく、
未解決goalから新しい補助構成・中間補題を供給する exogenous term generation である。
また `2011_p6` はbackward DAGが20,000状態上限へ達する。全backward DAGを先に作らず、
forward/backwardを一つの優先queueで交互に展開する必要がある。

IMO-AG-30全体の現在値は、単一solverではなく厳密agentのportfolio unionで24/30である。
未解決は `2008_p6`, `2011_p6`, `2019_p2`, `2019_p6`, `2020_p1`, `2021_p3`。
語彙不足、補助構成不足、消去timeout、非退化枝未閉鎖が混在する。

## 7. 既存研究との照合

- AlphaGeometryはDD+ARが停止した時に補助構成を提案する構成を採り、25/30を報告した。
  https://www.nature.com/articles/s41586-023-06747-5.pdf
- Wu法単体15/30、Wu+DD+AR 21/30、Wu+AlphaGeometry 27/30という補完性が報告されている。
  https://arxiv.org/abs/2404.06405
- HAGeoはLLMなし・CPUのみの数値的多重接続点heuristicで28/30を報告した。
  https://arxiv.org/abs/2512.00097
- HAGeo公開リポジトリのcommit `2217d813960cd689cf21c25520f6af664dc2da6e` は、
  2026-08-18時点でREADMEと図だけであり、READMEはfull codeが承認待ちと明記する。
  したがって28/30のコード再現はまだできず、論文記載から独立再実装する必要がある。
- NewclidはDDARをモジュール化し、外部agentが探索を制御できるAPIを提供する。
  https://arxiv.org/abs/2411.11938
- RISC-Vの基底命令＋標準拡張という分離は、数学核＋領域拡張の設計参考になる。
  https://docs.riscv.org/reference/isa/

## 8. 満点へ向けた反証可能な順序

1. HAGeo型の数値的incidence scorerを問題ID非依存で再実装し、現在のtyped候補へ加える。
2. `off / random / structural / structural+incidence` をIMO-30とHAGeo-409 frozen splitで比較する。
3. backward/forwardを単一優先queueへ統合し、20,000状態cap到達率を下げる。
4. Wu/Gröbnerへ送るgoalを中間補題へ分割し、正則条件の全枝を閉じる。
5. 最後にDDAR、構成探索、Wu/Gröbnerの証明集合unionを測る。

28/30の既存結果から、LLMなしでも現在の24/30を上げる科学的根拠はある。ただし30/30は
未実証であり、またIMO-AG-30満点は数学オリンピック全分野の満点を意味しない。整数、代数、
組合せには同じ実行核を使いつつ、各領域の型付きISAと独立verifierが必要である。

## 9. 結論

アーキテクチャの骨格は妥当である。今回、OR保存、遅延promotion、trust gate、native commit
という実行系は、固定DAGより少ない探索で同じ証明を再現した。ただしこれはcoverage改善
ではない。次の得点差は、HAGeo型の補助構成発見と、Wu/Gröbnerの退化枝を閉じる厳密backend
から生まれる。半導体設計はこの探索を高速・ modular にする参考になるが、数学的発明の代替
ではない。

## 10. 再現

```powershell
python -B scripts/verify_proof_dag_lazy_ablation.py `
  --artifact data/proof-dag-lazy-trust-comparison-2026-08-18.json
```
