# MORTRA 6論文統合実験（2026-08-22）

## 目的

C-RASP、OpenMath/MMT、Sheaf-ADMM、HAGeo、Hilbert-Geo、LEAPを、名前だけ接続するのではなく、MORTRAの実行経路へ落とし込む。導入前後を固定問題・固定予算で比較し、追加正答、通信量、型安全性、回帰の有無を測る。

## 仮説

1. OpenMath型の意味付き記号とMMT型のtheory viewを使えば、異なる証明器間で述語名が同じだけの誤交換を防げる。
2. Hilbert-Geoの2D/3D型分離を取り入れれば、点・直線・平面・円・球の混同を実行前に拒否できる。
3. LEAP型のAND/OR proof DAG、無進捗分解の拒否、verifier feedback順位付けは、同じ探索予算で未解決義務へ到達しやすくする。
4. Sheaf-ADMM型の局所通信は、各証明器の能力を変えずに証明書通信を減らせる。
5. C-RASP分解理論は有限語彙の数ではなく遷移合成の代数を調べる対照理論として有効だが、正規表現ではない一般証明探索へそのまま適用はできない。

## 調査対象と再現境界

| 対象 | 固定ソース | MORTRAでの扱い | 再現境界 |
|---|---|---|---|
| C-RASP | `903fba2` | 正規言語判定器を対照実装として監査 | 一般証明探索の正答器ではない |
| OpenMath CDs | `cbf6075` | 公開URIと私有CDを併用した型付き幾何語彙 | plangeoの実験的CDを全面採用しない |
| MMT | `fca5d7e` | theory view、symbol対応、push/pullを独立実装 | Scala MMTサーバー自体の埋込みではない |
| Sheaf-ADMM | `1e2b5d6` | restriction map、局所合意、残差診断を記号証明書へ適応 | NN encoder/decoderは使わない |
| HAGeo | `2217d81` | N-round/K-trajectoryと数値incidence gateの独立再構成 | 公式full code未公開のため完全再現ではない |
| Hilbert-Geo | `7a230d0` | 2D/3Dのsort/predicate設計を独立語彙へ適応 | theorem bankはコピーしない |
| LEAP | 公式コード未確認 | 論文由来のAND/OR DAGとfeedback reviewerを記号化 | 論文のLLM分解器の再現ではない |

ソース、commit、origin、証拠ファイルは `data/mortra-six-paper-source-integration-audit-2026-08-22.json` に機械可読形式で固定した。clone済みであることとruntime統合済みであることを別項目にした。

## 実装

### 1. OpenMath/MMT型付き交換

- `mortra_geometry_content_dictionary.py` に `Point2/Point3`、`Line2/Line3`、`Plane3`、`Circle2`、`Sphere3` と構成・関係signatureを定義した。
- 公開OpenMathの意味と一致する場合だけ標準URIを使い、Newclidの4点 `perp(A,B,C,D)` のように引数構造が違う関係は私有URIへ分離した。
- `mmt_exact_coordination.py` でsymbol URIだけでなく引数sort列を共有し、arity、点/実数/角、未束縛変数を検査する。
- `hageo_mmt_certificate_bridge.py` でHAGeo/Newclidのflat atomを型付き共有signatureへ持ち上げる。native verifierで閉じた証明書だけをpush/pullできる。

### 2. Hilbert-Geo型2D/3D語彙

- 3次元対象を2次元の点列へ潰さず、直線・平面・球を一級対象として保持する。
- 同じ綴りの述語でもsortが違えば交換不能とする。
- 外部theorem bankの暗記ではなく、MORTRA側の型検査とre-elaboration contractだけを実装した。

### 3. LEAP型proof DAG

- root goalをOR候補、各候補の前提をAND義務として保持する。
- 親と同一のfrontier、親の真の上位集合、既訪問frontierの深い再訪を拒否する。
- verifierが既に持つ述語集合から、各未解決述語までの楽観的AND距離を計算し、候補順位だけに使う。証明なしに真とはしない。

### 4. Sheaf-ADMM型協調

- 各agentのprivate state、共有restriction、consensus、dual disagreementを分離した。
- 学習入力はagent role、前提述語multiset、結論述語、再生済み証明書dataflowに限定した。
- 問題文、問題ID、点名、数値答えは禁止し、解法暗記を避けた。
- 優先順位は変えても、最終受理はnative certificate replayに限定した。

### 5. 既定経路から外したもの

- Sheaf協調は実問題での追加正答が未実証なので、既定採点を変更しない。
- LEAP型feedback routingは凍結5問で追加正答がなかったため、診断機構に留める。
- C-RASPはMORTRAの射列を正規言語へ符号化する健全な写像が未定義なので、探索rankingへ直結させない。

## 方法

1. 変更前に関連回帰65件を固定した。
2. 型、証明書交換、proof DAG、Sheaf、統合manifestを個別テストした。
3. LEAP型変更は未解決5問、同一深さ・同一branch数・同一state予算でcontrol/treatment比較した。
4. Sheafは幾何・整数・集合の各20件、合計60件をfrozen testとし、entity名と数値をtrain/devから分離した。
5. HAGeo系のスコアは、証明artifactとhashが一致する89問unionだけを参照した。

## 結果

> **後続監査**: 本文は6資料由来の独立適応実験であり、6論文の公式方式を
> 同一条件で再現したものではない。理解・再現・接続・因果効果の境界と、
> 到達可能性分析の訂正は
> `MORTRA-SIX-PAPER-COMPREHENSION-AUDIT-20260822.md`を参照する。
> 最新の認証済み能力集合は後続artifactで`53/89 = 59.55%`となったが、
> 本実験の導入機構による追加正答は0のままである。

### 回帰

- 統合関連テスト: **99/99 pass**。
- Sheaf関連テスト: **27/27 pass**。
- 型付きMMT/CD集中テスト: **20/20 pass**。

### C-RASP公式判定器

公式READMEの3例を隔離環境で再生し、`(cab+c)*`はC-RASP外、`(ab+ba)*`と`(aabb)*`はC-RASP内と判定された。上流`requirements.txt`の`automata==0.1.4`と実際の`automata-lib`名前空間に不整合があるため、互換`automata-lib 9.2.0`を使った。生出力と環境差は `data/crasp-upstream-decider-reproduction-2026-08-22.json` に記録した。

### 型安全性

- flat 4点垂直関係をOpenMathの2直線関係と誤同一視しない。
- point slotへの数値、angle slotへの点名、未束縛変数、arity不一致を交換前に拒否する。
- 2D/3D sort不一致をtheory viewの境界で拒否する。
- `coll`、`cyclic`、`diff`、`lequation`などの可変長述語は、arity別のshared symbol familyとして交換し、pull時に元のnative述語へ戻す。

### HAGeo/MMT実経路smoke

最初の実行では、可変長述語を1述語1arityと仮定していたため、`coll=[3,4]`、`cyclic=[4,6]`、`diff=[2,3]`、`lequation=[10,25]`、`ncoll=[3,4]`で開始前に停止した。これをarity overloadとして実装し直した。

修正後、公式Newclid環境の`2007_p4`を`candidate_policy=mmt-hageo`で実行し、**solved=true、replayed=true**。4,685 native factから192 factの証明基底を選び、MMT交換した8証明書をすべて受理・再生して、open demand 1件を閉じた。経過は19.635秒。既にbaselineで解ける問題なので追加正答には数えず、実配線と意味保存のsmokeとして扱う。artifactは `data/six-paper-mmt-hageo-runtime-smoke-2007p4-2026-08-22.json`。

### LEAP型探索制御

固定5問でcontrol **0/5**、treatment **0/5**。追加正答は0。treatmentは無進捗658枝、既訪問193枝を拒否したが、control/treatmentとも50,000 stateを使い切った。枝の衛生化は確認できたが、正答改善の因果効果は確認できなかった。

### Sheaf型協調

合成frozen 60件で、strict全送信、learned global blackboard、static sheaf、learned sheafはいずれも60/60を再生証明書で閉じた。送信数はstrict 2,461件、learned sheaf 276件で、**88.785%削減**。learned global blackboardは282件であり、sheaf固有の差は6件、paired bootstrap 95% CIは `[-0.233, 0.0]`。したがって「型付き学習で通信を減らす」効果は強いが、「sheafでなければ得られない正答増」は未実証である。故障注入では無効証明書59件を拒否し、false acceptは0だった。

### HAGeo系の現在値

証明artifact付きのcapability unionは **52/89 = 58.43%**。これはHAGeo論文の公式benchmark値の再現ではなく、MORTRA内の監査済み89問集合での値である。今回の型/CD/探索変更による追加正答はまだ0で、スコアを上げたとは主張しない。

## 考察

今回、最も確実に改善したのは証明器間の意味保存である。これまでは同じ述語名とarityだけで交換でき、`perp`のようなflat relationとstructured OpenMath termを混同し得た。型付きContent DictionaryとMMT viewにより、この誤接続を実行前に排除できた。

一方、LEAP型の枝除外と述語距離だけでは追加正答が出なかった。未解決問題では、既存定理への最短距離を並べ替える以前に、現在の語彙にない補助構成または中間関係を生成する必要がある。HAGeoの数値incidence proposal、FormalGeoのGDL、Newclid/GCLCのnative certificateを同じ型付き義務へ戻す経路が次の実験対象になる。

C-RASPから得られる主要な示唆は、有限語彙であること自体は長さ一般化を保証せず、遷移作用の合成代数を調べる必要がある点である。MORTRAでは、証明軌跡を問題文token列ではなく、型付き射とobligation stateの遷移系として監査する必要がある。ただし現時点で一般proof DAGをC-RASP判定可能な正規言語へ落とす定理はない。

## 結論

- OpenMath/MMT/Hilbert-Geo由来の型付き交換はruntimeへ接続し、誤交換を防ぐテストまで通した。
- Sheaf型協調は合成未見問題で通信を88.785%削減したが、実ベンチの追加正答は未実証なので既定化しない。
- LEAP型review/rankingは枝を減らしたが、固定5問の追加正答は0。得点改善としては不採用。
- HAGeoの次の不足は探索量ではなく、数値提案を型付き中間義務へre-elaborateし、native verifierへ返す補助構成閉ループである。
- 今回は問題ID、数値答え、表層文型による分岐を追加していない。

## 再実行

```powershell
python -B -m pytest worker/backend/test_geometry_representation_atlas.py worker/backend/test_typed_construction_contracts.py worker/backend/test_typed_construction_cegis.py worker/backend/test_typed_open_proof_dag.py worker/backend/test_mmt_exact_coordination.py worker/backend/test_hageo_mmt_certificate_bridge.py worker/backend/test_mortra_geometry_content_dictionary.py worker/backend/test_symbolic_sheaf_coordination.py worker/backend/test_native_formal_obligation_sheaf.py worker/backend/test_mortra_unified_architecture.py scripts/test_audit_research_integrations.py -q
python -B scripts/experiment_proof_dag_progress_ablation.py --depth 6 --branches 256 --states 10000 --output data/proof-dag-feedback-routing-ablation-frozen5-2026-08-22.json
python -B scripts/experiment_symbolic_sheaf_learning.py --train-per-domain 10 --dev-per-domain 5 --test-per-domain 20 --output data/six-paper-sheaf-ablation-2026-08-22.json
python -B scripts/audit_research_integrations.py --source-root research_sources/2026-08-22 --output data/mortra-six-paper-source-integration-audit-2026-08-22.json
```
