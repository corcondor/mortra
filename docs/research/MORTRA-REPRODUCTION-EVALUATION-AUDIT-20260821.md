# MORTRA 再現性・協調効果・評価監査 2026-08-21

## 目的

外部論文の名前、clone、単体テスト、中間事実数を能力達成と混同せず、次を分離して測る。

1. 公式実装をnativeに実行しているか。
2. 論文から独立再構成した機構か。
3. 複数証明器の交換で、未解決の型付き証明義務が実際に閉じたか。
4. native証明書で正答が増えたか。
5. timeout、未観測、誤答、未証明を混同していないか。

## 原理

MORTRAの共有単位は文字列の解法名ではなく、型付き関係原子、構成射、未解決義務、native証明書である。
各証明器は固有表現を維持し、共有層へ渡す事実には元の証明書と再生契約を付ける。真偽はYuclid、
GCLC/Wu、Groebner等のnative検証で決め、MMT/Sheaf/微分可能な順位器は探索順だけを決める。

今回の進歩判定は次に固定した。

```text
parent open obligation p
  -> candidate construction c
  -> native verifier facts F_c
  -> progress iff canonical(p) is in F_c
```

未解決義務の件数が減ったこと、別の義務へ置換されたこと、無関係な事実が増えたことだけでは進歩としない。

## 仮説

- H1: goal-conditioned proof basisなら、旧lexical sliceより証明に必要な事実をMMTへ渡せる。
- H2: MMTで導出した事実数ではなく、親義務のnative閉鎖数を候補順位へ入れると誤った協調評価を防げる。
- H3: 高価な双方向proof DAGを全候補へ適用せず、有限の昇格候補へ段階的に適用すれば実行時間を抑えられる。
- H4: 上記だけで追加正答が出ない場合、原因は証明書輸送ではなく、新しい補助構成・中間補題の供給不足である。

## 方法

### 評価条件

- 外部LLM、期待解、問題ID分岐、dataset auxiliary clausesを不使用。
- HAGeo-409の固定未証明問題を使用。
- 正答はYuclid native certificate replayだけで判定。
- timeoutまたは手動停止はright-censoredであり、誤答にも正答にも数えない。
- 比較前に問題集合、seed、N、K、候補数を固定する。

### 実装

1. MMTへ渡す192 factsをlexical順ではなく、goalの後向きtheorem coneと型付きpremise matchから選ぶよう変更。
2. `closed_parent_demands`を、義務一覧の差ではなくnative verifierが直接受理した事実との共通部分として定義。
3. `introduced_relation_demands`を別計測し、閉鎖と新規負債を分離。
4. 候補順位を、閉じた親義務数、導入した新義務数、AR residual、既知rank、残義務数の順で比較。
5. 双方向proof DAGの入力を全304候補から昇格予算内へ制限。全候補は安価なMMT/incidence portfolioに残す。
6. 外部source 21件について、cloneとintegrationを分離する機械監査を追加。

## 結果

### MMT fact selection

`2011CTSTp16`, N=1, K=1:

- 旧lexical slice: derived facts 0。
- goal-conditioned proof basis: selected 192、derived 89、certificate 89。
- しかし初期open demands 24、終了時24、直接閉鎖0、追加正答0。

同一のN=4, K=1, feedback=4比較でも、旧版42.55秒、新proof basis 104.92秒で、ともに未証明だった。
中間事実を増やすことには成功したが、得点と速度は改善しなかった。

### 固定3問

`2015IranTSTp18`, `2024VietnamTSTp5`, `2020IranGOAp2`をN=1, K=1で固定した。

| problem | derived | initial -> open | direct closed | status | elapsed |
|---|---:|---:|---:|---|---:|
| 2015IranTSTp18 | 55 | 2 -> 2 | 0 | unsolved | 115.99 s |
| 2024VietnamTSTp5 | 46 | 24 -> 24 | 0 | unsolved | 95.80 s |
| 2020IranGOAp2 | 55 | 3 -> 4 | 0 | unsolved | 20.39 s |

完走3/3、execution error 0、追加正答0/3だった。`2020IranGOAp2`では義務が1件増えたため、
単なる導出数を協調成功と呼べないことがさらに明確になった。

### direct-demand候補順位

`2020IranGOAp2`, N=1, K=1, feedback candidates=4で、4候補をnative verifierへ渡した。

- 4候補すべてdirect closed=0。
- AR known rankが最大の`circle(i,b,c)->d`が選択された。
- 15.27秒、未証明、追加正答0。

評価コードは親義務の直接閉鎖を扱えるようになったが、この問題の既存候補集合には閉鎖できる候補がなかった。

### proof DAG実行量

- 旧完全DAG: 304候補を展開し、5分30秒で1 round未完了のためright-censored。
- family代表+昇格52候補: 3分で1 round未完了のためright-censored。
- 16候補: 3分で1 round未完了のためright-censored。
- 昇格8候補も3分で1 round未完了のためright-censored。
- stage 1を深さ1・64 states/task・昇格4候補へ修正すると27.07秒で完走した。
  proof DAG本体は10.12秒、5 tasks、189 states、truncated=falseだった。
- stage 1の追加正答は0、direct closed demandsも0だった。

right-censored実行は正解数の分母へ入れない。これは精度実験ではなく、専門家起動量の計算量診断である。

### source integration監査

`data/mortra-source-integration-audit-2026-08-21.json`の結果:

- source checkout: 21件。
- native/library runtimeのコード証拠あり: 4件。
- reference-only: 12件。
- complete reverse engineering claim: false。

主要区分:

| source | 現状 | 実際の意味 |
|---|---|---|
| Newclid/Yuclid | native-runtime | 公式実行系を証明判定に直接使用 |
| GCLC | native-runtime-bridge | executable、Wu/Groebner、Newclid bridgeを実行 |
| HAGeo | independent-reconstruction | N-round/K-trajectory/incidenceを独立再構成。full code未公開 |
| Sheaf-ADMM | partial-independent-adaptation | CPU疎協調のみ。公式JAX/Flax学習再現ではない |
| AlphaGeometry/AlphaGeometry2 | reference-only | 原理・形式・比較対象。MORTRA採点経路で公式solverを直接実行していない |
| FormalGeo/AutoGPS/Euclean/FGPS等 | reference-only | cloneや設計参照はあるが、追加得点を持つnative agentではない |
| Seed-Prover | unusable-checkout | ローカルcheckoutが大幅dirtyで、再現証拠として使えない |

従って「公開コードを全部リバースエンジニアリングして統合済み」とは言えない。

## 不正・不誠実な評価の監査

### 修正した問題

1. derived factsが1件でもあれば`mmt_residual_applied=true`としていた。
   現在は親義務をnative factとして直接閉じた場合だけtrueになる。
2. open demandの件数だけで進歩を判断していた。
   現在はcanonical relation identityとnative proof factsを照合する。
3. clone、文書、単体テストの存在をintegrationと混同できた。
   現在はsource auditで区分する。

### 数字の扱い

- IMO-AG-30の25/30は、複数の監査済みnative証明集合のportfolio unionである。
  単一agentの25/30ではなく、開発中に繰り返し観測した集合なので、未見汎化値としては扱わない。
- HAGeo固定held-outの51/89はnative certificate/hash監査を通したprimary値である。
  ただしHAGeo公式のK=2048/8192と同一計算量・同一実装ではないので、公式70.2%との直接比較はしない。
- `全問題.tex`の54/85は内部検証portfolioで、公式解答との完全照合値ではない。
- timeoutは誤答にしない一方、正答にも加えない。完走率とright-censor率を併記する。

## 考察

MMT bridgeは以前の「共有事実0」から「共有事実46〜89」へ改善した。しかし追加正答は0だった。
原因は、現在の二つのMMT agentが同じHorn theorem closureを分割しているだけで、open demandに必要な
新しい点や構成を供給していないことにある。証明書の輸送は、証明書が存在しない原始構成を発明しない。

したがって次の本質は、open relation demandを構成の出力仕様へ変換し、候補構成がその義務を閉じるかを
native verifierで反例駆動評価することにある。これは問題別の解法登録ではなく、
`relation obligation -> typed construction contract -> native certificate`という一般射である。

proof DAGの旧実装は、候補文法を広げるほど全候補へ高価な専門家を適用するため、組合せ爆発を起こした。
段階制は候補を消さず、安価な局所評価、昇格、native検証の順に資源を配る。HAGeoの独立trajectoryと
Sheaf-ADMMの局所viewを活かすには、この実行制御が必要である。

## 結論

今回完了したのは、MMT/HAGeo配線の実在確認、偽の進歩判定の除去、親義務の直接閉鎖に基づく候補順位、
proof DAGの段階起動、source integrationの機械監査である。追加正答はまだ0であり、自己組織化による
得点向上、Sheaf-ADMM完全再現、HAGeo完全再現、任意問題の自律補助構成発明は未完了である。

次の実装優先順位は次の通り。

1. open demandから、そのrelationを出力できるtyped construction contractを逆生成する。
2. NewclidとGCLCが同じHorn closureを重複実行するのではなく、異なるnative証明書を交換する。
3. staged proof DAGを固定未証明群でlite/full ablationし、時間と追加正答を同時に測る。
4. 成功した`obligation -> construction -> certificate`部分グラフだけを未知二親融合へ再利用する。
5. frozen cohortで追加正答を確認できるまで、協調・微分可能回路・自己組織化を得点向上済みと表示しない。

## 再現成果物

- `worker/backend/hageo_mmt_certificate_bridge.py`
- `worker/backend/hageo_search_control.py`
- `worker/backend/geometry_proof_hypergraph.py`
- `scripts/experiment_hageo_passk.py`
- `scripts/experiment_newclid_construction_stalk.py`
- `scripts/audit_research_integrations.py`
- `data/mmt-proof-basis-audited-2011ctstp16-n1-k1-2026-08-20.json`
- `data/mmt-proof-basis-audited-frozen3-n1-k1-2026-08-20.json`
- `data/demand-closure-ranking-2020irangoap2-n1-k1-f4-2026-08-20.json`
- `data/demand-closure-stage1-proofdag-v2-2020irangoap2-n1-k1-f4-2026-08-21.json`
- `data/mortra-source-integration-audit-2026-08-21.json`

## 一次資料

- AlphaGeometry: https://github.com/google-deepmind/alphageometry
- AlphaGeometry2: https://github.com/google-deepmind/alphageometry2
- HAGeo: https://github.com/boduan1/HAGeo
- Newclid/Yuclid: https://github.com/Newclid/Newclid
- Sheaf-ADMM: https://github.com/SakanaAI/sheaf-admm
- FormalGeo: https://github.com/FormalGeo/FormalGeo

## 2026-08-21 失敗台帳: 仮説と実装を分離する

### できると考えた根拠

根拠は万能性ではなく、次の条件付き半決定性である。

1. 必要な対象、関係、補助構成、中間補題が有限の型付き言語で表せる。
2. 候補列挙が公平で、有限長の正しい証明経路をいつか訪れる。
3. native verifierが候補証明を正しく受理・棄却できる。
4. 探索深さ、候補数、時間を正しい証明より手前で切らない。

この4条件の下では、型付き構成列挙と証明検証の組は、言語内に存在する証明を発見できる。
Newclid/DDAR、HAGeo型の補助構成探索、Wu/Groebner消去は、この限定された根拠を支持する。
しかし、これは任意の高校数学、未知の原始法則、言語外の補題を自動発明できるという証明ではない。
現在のMORTRAは4条件すべてを満たしていないため、任意問題への成功を主張しない。

### 今回確認した実装失敗

| 失敗 | 観測 | 修正 | 修正後の結果 |
|---|---|---|---|
| MMTが導出した事実を次roundへ渡していない | 証明書は生成されるが探索状態から消失 | exact proof stateと、探索へ渡す有限proof basisを分離 | 状態輸送は動作、追加正答0 |
| 全proof stateを探索へ投入 | 2,000〜4,000事実でCPU/メモリが急増 | goal-conditioned proof basisだけをcarry | 完走可能になったが追加正答0 |
| proof DAGが最終goalだけを追う | native verifierの残余義務と探索対象が不一致 | 現在のopen relation demandsをDAG goalに使用 | 残余3義務のbackward task生成を確認 |
| 固定された族登録順 | relevance score後も先頭4族だけを選択 | relevance順から族順を再構成 | 関連族へ移動したが追加正答0 |
| 需要述語の被覆なし | `cyclic`需要があるのにcongruence系4候補が枠を占有 | 各open predicateの最良候補を最低1件確保 | `on_circum`の実行を確認、追加正答0 |
| 再実行時のDLL場所誤指定 | Yuclid終了コード`0xC0000135`、3/3 execution error | Boost 1.88 DLLディレクトリを単体検証して再実行 | 実行エラー0 |

`NameError: candidate_demands`、全状態carryによる膨張、DLL誤指定は研究上の負結果ではなく
実装・実験運用上の失敗として分離した。削除せず、再発防止テストとartifactを残す。

### 修正後の固定診断

対象は既存の固定難例`2020IranGOAp2`、N=1、K=1、候補4、外部LLMなし。

- 修正前のproof DAG族: 登録順由来の`circle/mirror/midpoint/foot`。
- relevance順修正後: `shift/eq_triangle/reflect/parallelogram`。完走206秒、未証明。
- 需要述語被覆後: `eq_triangle/reflect/on_circum/parallelogram`。
- 需要述語被覆後は66.86秒で完走、未証明、親義務の直接閉鎖0。
- 回帰テスト: 44/44成功。

artifact:

- `data/relevance-scheduler-v6-frozen3-n1-k1-f4-2026-08-21.json`
- `data/demand-predicate-coverage-v7-2020irangoap2-n1-k1-f4-2026-08-21.json`

### 理論的に残った原因

`cyclic(p,q,r,t)`は、既存4点について共円を**証明する義務**である。一方、
`on_circum(p,a,m)->d`は、新しい点`d`を既知3点の円周上へ**構成する射**である。
述語名が`cyclic`で一致しても、出力穴の位置、既知点、引数対応が一致しないので、前者を閉じない。
今回の実験は、述語一致だけの候補選択が不十分であることを反証した。

次に必要なのは問題別解法ではなく、次の一般条件である。

1. relation demandを`既存対象の証明義務`と`構成穴を含む合成義務`へ型分けする。
2. 構成射は出力穴と引数対応がunifyする場合だけ直接候補とする。
3. 穴のない証明義務は、backward theoremで中間義務へ分解する。
4. forward construction coneとbackward obligation coneが型付きatomで一致した場合だけnative検証へ昇格する。

現時点の正確な結論は、MORTRAは多数の既存問題を解いている一方、この固定難例群に対する
MMT/証明DAG改良の追加得点は0である、というもの。既存実績`51/89`とportfolio `25/30`を否定せず、
今回の追加効果も水増ししない。

## 2026-08-21 型付き補題CEGIS追試

### 原理

未知問題の状態を`Gamma |- goal`とし、backward proof DAGが作る開いたatomを型付き穴として扱う。
有限の項・構成文法から局所補題候補を列挙し、反例が見つかった候補を除外し、Yuclid/Wu/Groebner等が
再生可能な証明書を返した候補だけを`Gamma`へ戻す。これは局所補題のCEGISであり、問題文テンプレや
問題番号を登録する処理ではない。証明器が閉じなかった候補は偽とはせず`unknown`に残す。

### 実装修正

- ground命題`cyclic(p,q,r,t)`と、新点を作る`cyclic(d,...)`を同一候補として扱わない
  `TypedObligationSignature`を追加。
- 深さ1から順に予算を増やす反復深化を追加。
- 幅1層目が全予算を消費しないよう、各深さへ状態予算を公平配分。
- 状態上限ちょうどで生成された有効なopen proof branchを捨てる境界バグを修正。
- frontierの型付き穴を可視対象だけで具体化する`typed_lemma_cegis`を追加。
- Yuclidのgoalを局所補題へ差し替え、native certificateがある場合だけ採用する
  `yuclid_local_lemma_oracle`を追加。
- GCLC翻訳で欠けていた`circumcenter -> perpendicular bisectors`の一般語彙射を追加。

### 固定実験の結果

`2020IranGOAp2`, N=1, K=1, 外部LLMなし:

| 実験 | 実深さ backward/forward | 診断 | 正答 |
|---|---:|---|---:|
| v8 | 1/1 | 予算を幅1層で消費 | 0 |
| v9 | 3/0 | 境界枝を捨てたため偽の語彙gap | 0 |
| v10 | 3/3 | 予算切れなし、現理論内のtyped meetなし | 0 |

v10は71.80秒で完走し、3つのopen relation demandは閉じなかった。探索を深くしただけでは解けない。
一方、一般の外心構成から生成した別目標`cong(o,a,o,b)`は、Yuclidがgoal deduction 1件、
all deductions 51件、証明SHA-256
`d643957895a8e1d3f3d095282d491307679aba65caf336e4b7b32d5d6e5fb4c8`で閉じた。
したがって局所補題の生成、差し替え、厳密採用という最小閉ループは実動した。

GCLCは`circumcenter`修正後に対象問題を受理したが、Wu法は外部315.107秒でtimeout、Groebner法は
302.125秒で内部timeoutとなり、中間式は最大233,469項だった。巨大一括消去ではなく、局所補題への
分解が必要という仮説を支持する。ただし固定難例の追加正答は依然0なので、成功とは扱わない。

### 結論と次の反証可能な仮説

任意の数学問題を必ず解く保証は、停止性不能・不完全性のため与えられない。工学的に主張できるのは、
必要な補題・補助構成が型付き候補言語に存在し、列挙が公平で、検証器が閉じられる有限断片における
半決定性である。次の仮説は、単一構成の即時得点ではなく、数値incidenceが中立な構成も残す
多段trajectoryと、各段で証明済み局所補題を再投入すれば、v10のtyped meetが生じる、である。

再現artifact: `data/typed-lemma-cegis-audit-2026-08-21.json`。

## 2026-08-21 総合能力と機構差分の分離

### 原理

ある新しい探索機構が固定probeで追加正答を出さなかったことは、その問題をMORTRA全体が
解けないことを意味しない。MORTRAの総合能力は、全agentが返した監査済みnative証明書の
集合和で測る。新機構の因果効果は、その集合和に新しく加えた証明数として別に測る。

### 実装

`build_hageo_policy_portfolio.py`に監査済みbaseline unionの継承を追加した。局所実験が0問でも
既存証明を削除せず、`baseline / overlap / additions / MORTRA overall`を別々に出力する。
未監査の回答集合をbaselineとして渡した場合は拒否する。HAGeo探索成果物には、今後の
seed再実行を監査できるよう、Python、データセット、Yuclid実行ファイル、主要探索コードの
SHA-256を自動記録する。

### 結果

直近のobligation-conditioned credit固定10問は追加`0/10`だったが、認証済みbaselineと
合成した総合スコアは **`51/89 = 57.30%`** のまま保持された。

過去に新規正答を出した`2002CTSTp25`の48番軌道を現在のYuclidで二回再生した結果、両方とも
`solved`となり、再生間の入力SHAと証明SHAも一致した。一方、変更後の候補列挙器で同じseedから
48番軌道を再探索すると同じ経路は選ばれなかった。従って、証明能力は再生可能だが、古い探索器の
seed-to-path写像は現在のコードだけでは再現できない。以後は実行時source fingerprintを保存する。

### 結論

`51/89`はMORTRA全体の認証済み能力下限として有効である。信用制御の追加効果が0だったことは
この値を取り消さず、信用制御がまだ集合和を増やしていないことだけを意味する。

再現artifact:

- `data/mortra-overall-obligation-credit-probe10-2026-08-21.json`
- `data/reproduction-replay-2002ctstp25-attempt48-2026-08-21.json`
