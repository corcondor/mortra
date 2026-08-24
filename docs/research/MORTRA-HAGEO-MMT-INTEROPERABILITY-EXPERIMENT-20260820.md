# MORTRA HAGeo / MMT相互運用実験 2026-08-20

## 原理

MORTRAの幾何探索は、一つの巨大な証明器へ全表現を潰すのではなく、各証明器の
固有表現を保存したまま中間命題と補助構成を交換する。共有層はOpenMath/MMT型の
記号URI・項・理論射であり、真偽は各native証明書の再生だけで決める。

この構成で検証する仮説は三つである。

1. HAGeo/Newclidで公開された一般的な補助構成語彙を有限文法へ追加すると、問題名や
   既知解を使わず、固定held-outのnative証明数が増える。
2. MMT theory viewを通すことで、Newclid DD/AR、GCLC/Wu、数値incidence、型付き構成器が
   固有の形式言語を失わずに候補と証明書を交換できる。
3. 単位selectorからなるSheaf-ADMMは密行列を作らず疎なchannel更新へ変換でき、
   数値結果を保ったまま大規模候補集合を実行可能にできる。

## 方法

### 一次実装の扱い

- Newclid/Yuclidは公式リポジトリ `ac6550732a950564cf7614d605b5bf1eadd29701` を
  そのまま実行し、native proof JSONを真偽判定に使った。
- HAGeo公式リポジトリ `2217d813960cd689cf21c25520f6af664dc2da6e` は、READMEに
  full codeが未公開と明記されている。従ってHAGeo部分は論文のN-round、K-trajectory、
  numerical incidence gateを独立再構成したもので、公式コードの完全再現ではない。
- MMTは公式サーバ全体ではなく、今回必要なinterface theory、symbol assignment、
  push/pull、certificate envelope、replayを実装した部分実装である。

### 実装

- `MMTTheoryView`: native predicateと共有symbol URIの可逆な引数対応。
- `MMTExactCoordinator`: 各agentのnative証明書を検査してから共有理論へpushし、
  他agentへpullする。共有層だけで新しい真理を生成しない。
- `HAGeoMMTCertificateBridge`: Yuclidのnative deductionをDD/ARのstalkへ分け、共有URIへ
  push/pullし、再生済み事実・未閉鎖義務・証明書SHA-256をHAGeo Pass@Kへ返す。
  fact slice 192件、1 round最大256証明書、最大8 roundの有限予算を持つ。
- 証明書交換は全候補の順位付けには使わない。まずnative residualで候補を一つ選び、
  選択候補にだけ遅延起動する。新しい共有事実を導出できなかった交換結果は、
  Newclidのnative residualを上書きしない。
- HAGeo/Newclid構成family: `eqangle2`, `lc_tangent`, `on_aline`, `eqangle3`,
  `iso_triangle_vertex`, `iso_triangle_vertex_angle`。
- Sparse Sheaf-ADMM: selector行列を生成せず、共有channelごとの局所値・双対変数を更新。
- 証明書監査器: cohort -> problem -> shard -> native proofを辿り、入力hash、proof hash、
  proof file SHA-256、goal deduction列を検査。

### 評価規約

- 外部LLM、問題ID分岐、期待解、dataset auxiliary clausesを不使用。
- HAGeo-409 frozen held-out 89問の既存primary certified unionを起点とする。
- timeoutは誤答にせずright-censoredとする。
- native proofとhash監査を通った問題だけを集合和へ追加する。

## 結果

### 正答率

既存の監査済みprimary unionは `47/89 = 52.81%` だった。そこに、以前の探索集合とは
独立に残っていた52問を同一の `N=6, K=64` random incidence policyで全件実行した。

- 完走: `52/52` 問、`3328/3328` 軌道
- timeout: `0`
- execution error: `0`
- cohort内native証明: `6/52`
- 過去primary unionと重複: `2`
- 新規primary証明: `4`
- 更新後: **`51/89 = 57.30%`**（`+4問`, `+4.49 pt`）

新規4問は `2005CTSTp11b`, `2011ARMOg11p8`, `2019USATSTSTp5`,
`2024ARMOg9p4`。6件のsolved claimは全て、native proof status、goal deduction列、
入力/proof対応、proof file SHA-256を監査済みである。

### MMT/協調層

- MMT theory viewのpush/pull、native certificate交換、改ざん拒否を単体テストで確認。
- `HAGeoMMTCertificateBridge`をHAGeo Pass@Kの実採点経路へ接続した。真偽判定は従来通り
  Yuclid native certificateだけで、MMTは中間証明書と未閉鎖義務の交換に限定した。
- 疎Sheaf-ADMMは小規模入力で旧密行列版と数値一致し、2048候補 x 5 agentの回帰を
  5秒未満で通すテストを追加した。
- 実問題 `2011CTSTp16`, N=6, K=64では、random policyは108.72秒、疎
  `mmt-hageo-lite`は651.08秒で、両方とも証明に成功した。
- 従って疎化で「実行不能」は解消したが、現時点ではMMT協調による追加正答はなく、
  同問題ではrandomより約5.99倍遅い。
- full `mmt-hageo`の旧実行は4 shard全てが900秒でright-censored、完走attempt 0。
  これは不正解ではなく未観測である。

### exact bridgeの固定比較

`2011CTSTp16`, N=4, K=1, feedback=4, seed=19を同一条件で比較した。

- `residual-static`: native証明に成功、6.76秒、1 round、検証4回。
- 全候補でexact交換する旧`mmt-hageo-lite`: 未証明、42.71秒、4 round、検証13回。
- 選択候補だけでexact交換する遅延版: 未証明、42.55秒、4 round、検証13回。
- 遅延版のexact交換は新しい共有事実0件で、native residualを上書きしなかった。

遅延化だけでは時間を短縮できなかった。時間差の主因は証明書push/pullそのものではなく、
MMT theory-view policyがnative baselineと異なる4段の構成経路を選び、13回のYuclid検証を
必要としたことである。従ってMMTをbaselineの代替policyにしてはいけない。

既存能力を壊さないため、native証明書監査を通ったpolicyの集合和を作るportfolioを実装した。
この固定例では`residual-static`の1証明を保持し、MMTの追加証明は0、既存能力保持はtrueだった。

さらにnative baselineで未証明かつ完走済みの5問を固定し、`mmt-hageo-lite`, N=3, K=1,
feedback=1を各300秒で測った。5/5がright-censored、完走attempt 0、追加証明0だった。
これは誤答5ではないが、現在のMMT policyが追加得点を観測できる計算量にないことを示す。

exact交換を選択候補だけに遅延させた同条件の再実験も固定5問すべてを実行した。
5/5がright-censored、完走attempt 0、追加証明0、execution error 0、wall time 901.31秒だった。
したがって、全候補交換を止めただけでは未解決5問の実行可能性も得点も改善しない。

### 未証明問題への深さ追加

既存primary unionで未証明のまま残った5問を事前に固定し、random incidence policyを
`N=8, K=128`へ拡張した。各問題を2 shardに分け、途中結果をatomic progress snapshotへ
保存し、既完了shardを再利用できるようにした。

- 対象: `2015IranTSTp18`, `2024VietnamTSTp5`, `2020IranGOAp2`,
  `2025KoeraFinalRoundp3`, `2016G6`
- 完走: `5/5`問、`640/640`軌道
- timeout: `0`
- execution error: `0`
- 新規native証明: **`0/5`**
- 更新後primary union: **`51/89 = 57.30%`**（変化なし）

この結果は「残る問題は探索深さだけが不足している」という仮説を支持しない。5問だけの
診断実験なので一般的な不可能性は示さないが、同じ構成文法の反復より、open proof residualから
新しい補助構成familyを作ること、未接続の関係語彙をloweringすること、必要なagentだけを
遅延起動することを次に優先すべきである。

## 考察

### 2026-08-21訂正: exact交換の実効性監査

上の「遅延版のexact交換は新しい共有事実0件」という値は、旧lexical fact sliceに対する結果である。
goal-conditioned theorem coneと型付きpremise matchで192 factsを選ぶよう修正すると、
`2011CTSTp16`で89 facts、固定未証明3問で46〜55 factsを導出できた。しかし各問で親の
open demandをnative factとして直接閉じた件数は0、追加正答も0だった。従って訂正後の結論は、
「証明書交換が動かなかった」ではなく「証明書交換は動いたが、目標へ進む構成・補題を供給しなかった」
である。

同時に、`derived_facts > 0`を`mmt_residual_applied`の条件にしていた評価を廃止した。現在は
親の型付き義務そのものがnative verifierの受理事実に含まれる場合だけ進歩とする。詳細は
`MORTRA-REPRODUCTION-EVALUATION-AUDIT-20260821.md`に記録した。

正答率を上げた直接要因は、MMTやADMMではなく、有限の一般構成語彙と独立軌道を
未実行問題へ広げたことである。同一文法が複数の問題へ移り、問題名・既知補助点・
期待解を使っていないため、今回の4問は問題別解法の登録ではない。ただし、これだけで
高校数学全体への汎化や、新しい原始定理の自動発明を示したことにはならない。

MMT候補順位層は表現間交換を型安全にし、exact certificate coordinatorも実採点経路へ
接続できた。しかし固定比較では追加共有事実も追加正答も0で、MMT policyはnative baselineと
違う低効率な軌道を選んだ。自己組織化した証明交換の実得点はまだ0である。
深さ追加した固定5問も`0/5`だった。次に必要なのは、全agentを毎候補で走らせたり同じ文法を
さらに反復したりすることではなく、native proof residualに応じて新しい中間補題・補助構成を
型付き合成し、必要なstalkだけを起動する遅延スケジューリングである。

疎ADMMはCPU実装であり、FPGA bitstream、RTL、実機測定は存在しない。FPGA化できるのは
selector更新、bitset閉包、bounded polynomial kernelなどの実行面であり、証明の正しさを
置き換えない。

## 結論

HAGeo/Newclidの一般補助構成探索を固定held-out全残件へ展開し、監査済みprimary scoreを
`47/89`から`51/89`へ改善した。MMT exact certificate bridgeは実採点経路へ接続したが、
固定比較と未証明5問で追加正答は0だった。従って「自己組織化で得点が上がった」
「FPGA化済み」とはまだ言えない。製品経路ではnative baselineを先に実行し、MMTは
未閉鎖義務が残った場合の追加specialistとしてのみ起動し、監査済み集合和で能力を保持する。

## 再現成果物

- `worker/backend/mmt_exact_coordination.py`
- `worker/backend/hageo_mmt_certificate_bridge.py`
- `worker/backend/native_formal_obligation_sheaf.py`
- `worker/backend/typed_geometry_stalk.py`
- `scripts/audit_hageo_cohort_certificates.py`
- `scripts/build_hageo_certified_union.py`
- `data/hageo-heldout-remaining52-n6-k64-2026-08-20.json`
- `data/hageo-heldout-remaining52-n6-k64-certificate-audit-2026-08-20.json`
- `data/hageo-certified-capability-union-2026-08-20.json`
- `data/hageo-heldout-residual-cohort5-n8-k128-s2-2026-08-20.json`
- `data/hageo-heldout-residual-cohort5-n8-k128-s2-certificate-audit-2026-08-20.json`
- `data/hageo-certified-capability-union-deep-2026-08-20.json`
- `data/mmt-hageo-lite-sparse-regression-k64-s4-2011ctstp16-2026-08-20.json`
- `data/mmt-exact-scoring-2011ctstp16-n4-k1-f4-2026-08-20.json`
- `data/mmt-exact-lazy-2011ctstp16-n4-k1-f4-2026-08-20.json`
- `data/mmt-hageo-exact-unsolved5-n3-k1-f1-2026-08-20.json`
- `data/mmt-hageo-exact-lazy-unsolved5-n3-k1-f1-2026-08-20.json`
- `data/hageo-mmt-exact-capability-portfolio-2011ctstp16-2026-08-20.json`

## 一次資料

- HAGeo: https://arxiv.org/abs/2512.00097
- HAGeo code/benchmark: https://github.com/boduan1/HAGeo
- Newclid: https://arxiv.org/abs/2411.11938
- Newclid code: https://github.com/Newclid/Newclid
- GenesisGeo: https://arxiv.org/abs/2509.21896
- MitM/MMT: https://research-repository.st-andrews.ac.uk/handle/10023/12491
