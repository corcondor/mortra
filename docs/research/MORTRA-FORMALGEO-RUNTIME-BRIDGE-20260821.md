# FormalGeo公式runtime bridge実験

日付: 2026-08-21

## 目的

参照止まりだったFormalGeoの公式GDLと後向きAND/OR goal decompositionを、
MORTRAのNewclid/JGEX問題から実行し、未解決義務をNewclid/GCLCへ戻せるか検証する。
得点の増加ではなく、まず公式runtimeが実際の採点候補経路へ入ることを対象とする。

## 原理

FormalGeoの定理は `premises -> conclusion` の型付き論理木である。未解決atomを
定理のconclusionへ単一化し、定理の全parameterが決まる場合は具体化済みinstanceだけを
後向き適用する。結論から決まらない隠れparameterがある場合に限り、同じ結論述語を持つ
定理の制約joinへ退避する。単なる引数置換だけの定理は、同じ義務を往復させるため除外する。

この順序は、問題番号、期待解、既知の証明列を使わない。型、述語、現在の未解決goalだけを使う。

## 方法

1. `jgex_formalgeo_translator.py` がNewclid/JGEXの構成DAGをFormalGeo GCLへ変換する。
2. GPL-3.0の公式FormalGeo 2.2.2は別processで実行し、JSONだけを交換する。
3. 公式 `construct`、`set_goal`、`decompose` を呼び、AND/OR treeを保存する。
4. 分解済みatomを子goalへ展開し、現在のleaf frontierだけをDNFの型付き義務へ戻す。
5. `Eq` は文字列照合せず、SymPy ASTから距離合同 `cong` と等角 `eqangle` へlowerする。
6. 各roundのfrontierを原子的にcheckpointし、timeout後も最後の型付き義務を保持する。
7. FormalGeo単体の成功はMORTRA正答に数えず、Exact/GCLCの証明書replayを必須とする。

対応した構成はfree point、triangle、circle/circumcircle/circumcenter、incenter、
angle bisector、midpoint、mirror、line/circle incidence、parallel/perpendicular/
equal-angle line、line-line intersectionである。

## 結果

### 小さな公式runtime試験

`AB || CD`、`CD || EF`から`AB || EF`を示す問題で、公式
`parallel_property_transitivity_parallel`が発火し、二つのpremiseを持つAND goalを生成して
rootを閉じた。

### IMO 2010 Problem 2

- JGEX setup: 8 clauses。
- FormalGeo construction: 19 statements、51 facts。
- 数値branch: seed offset 0はgoal gateを棄却、offset 100は受理。
- 未解決goal: `EqualDistancePointToPoint(A,J,I,J)`。
- 適用候補: 52定理全走査ではなく、具体化済み1定理。
- 生成frontier: `AJ.dpp - IJ.dpp = 0`。
- AST lower後: 元の型付き目標 `cong(a,o,k,o)`。
- wall time: 60.9秒のtimeoutから6.97秒完了へ短縮。
- Exact: 15秒および300秒の双方でright-censored timeout。
- GCLC Area: 0.05秒でunproved。Wu/Gröbner: 各125秒でtimeout。
- MORTRA正答: false。

artifact: `data/formalgeo-runtime-bridge-smoke-2010-p2-2026-08-21.json`

replay artifacts:

- `data/formalgeo-obligation-replay-2010-p2-2026-08-21.json`
- `data/formalgeo-gclc-replay-2010-p2-2026-08-21.json`
- `data/formalgeo-exact300-replay-2010-p2-2026-08-21.json`

### HAGeo 2007CMOp4

- 新規語彙 `circumcenter` を問題固有分岐ではなく型付き構成射として追加。
- FormalGeoは15秒でtimeoutしたが、`goal_initialized` checkpointから
  `perp(i,o,m,n)` を回収。
- GCLC Wu法が同じroot obligationを証明。
- 証明SHA-256: `5cf8a1123f6e2af367565d9bc46041637dbbbeb873c5867d93923c893ea64853`。
- MORTRA正答: true。wall time 16.07秒。

artifact: `data/formalgeo-checkpoint-gclc-replay-2007cmop4-2026-08-21.json`

### HAGeo 2016CTSTp5

- 新規語彙 `angle_bisector` をFormalGeo `AngleBisector`へ接続。
- 数値branchの複素値例外をseed局所棄却へ変更し、二等分線の左右順序を有限列挙。
- 5秒以内に有効なFormalGeo数値branchを得られなくても、元の型付きroot
  `perp(m,o,n,o)` を保持して全backendへ配送。
- Exact: 30秒timeout。Wu: 65秒timeout。Gröbner: 内部62.56秒timeout。
- Gröbner最大多項式: 101,540 terms。
- MORTRA正答: false。未接続ではなく多項式爆発によるright-censoring。

artifact: `data/formalgeo-root-preserved-portfolio-replay-2016ctstp5-2026-08-21.json`

関連回帰試験は20件が通過した。

## 考察

公式GDLの後向き分解、代数ASTの型付きlower、checkpoint、Exact/GCLC replayまで
一つの因果経路として動作した。2007CMOp4ではこの経路が追加正答を生んだため、接続は
参照表示ではなく採点経路として機能している。

一方、2010_p2と2016CTSTp5ではrootを単一の巨大な多項式義務として渡しており、時間を
15秒から300秒へ増やしても閉じなかった。後者の101,540項という観測から、次の改善対象は
探索時間の単純延長ではなく、構成block境界での局所消去と中間補題への分割である。

総当たりtimeoutの原因は定理数そのものではなく、parameter-free modeが対象entityの
直積を先に列挙する順序だった。goal単一化を先に行うことで、問題固有ルールを加えずに解消した。

## 結論

FormalGeoは「参照のみ」から「型付き義務をExact/GCLCへ交換し、証明書を採点へ戻すruntime
bridge」へ進んだ。小規模2問probeでは1問追加正答、1問right-censoredであり、ベンチマーク
全体の改善率はまだ主張しない。次の実装対象は、101,540項規模のroot義務を構成blockごとの
局所消去・separator lemmaへ分割し、各証明書をAND-DAGとして再合成する層である。

この後続層は
`docs/research/MORTRA-CONSTRUCTION-BLOCK-AND-DAG-EXPERIMENT-20260821.md`
で実装・検証した。未見3問で変数縮約と証明書付き補題生成は再現したが正答は0/3であり、
次の未接続部分はseparator多項式から型付き幾何関係への再elaborationである。

## 一次資料

- FormalGeo paper: https://arxiv.org/abs/2310.18021
- FormalGeo code: https://github.com/FormalGeo/FormalGeo
- Newclid code: https://github.com/Newclid/Newclid
- GCLC code: https://github.com/janicicpredrag/gclc
