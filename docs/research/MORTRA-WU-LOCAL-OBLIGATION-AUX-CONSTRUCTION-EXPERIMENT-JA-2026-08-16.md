# MORTRA Wu 局所証明義務・補助構成探索実験

記録日: 2026-08-16

## 1. 研究課題

前段の chordal Gröbner 実験では、局所証明書の健全な交換はできたが、
`on_aline` / `cc_tangent` を展開した多項式の項数爆発を止められなかった。
本実験は次の二つを分離して検証する。

1. 大きな座標証明義務を Wu 型の構成順三角化と擬除算へ移すと、
   厳密な証明DAGを保ったまま処理範囲が広がるか。
2. 単一消去器が止まる問題で、記号推論の証明ハイパーグラフから補助構成を
   探し、局所的な小さい証明義務へ問題を変形できるか。

外部LLM、問題番号分岐、既知解答、データセットの隠し補助点は使用しない。

## 2. 論文から採用した原理

### 2.1 Wu--Ritt

Wu--Ritt 法では、多項式集合を変数順序に沿う三角集合へ変換し、
擬除算恒等式

\[
  I(f)^k g = qf + r
\]

を反復する。ここで先頭係数 `I(f)` の非零性は隠してはいけない。
零点集合は、三角集合の零点と initials が零になる退化枝へ分解される。
MORTRA は今回、initial、擬除算、擬剰余、正則条件の記録までを実装した。
完全な zero decomposition / regular chain はまだ実装していない。

- https://arxiv.org/abs/2604.14912
- https://arxiv.org/abs/1108.1486
- https://arxiv.org/abs/1702.08664
- https://arxiv.org/abs/1907.13537

### 2.2 記号的 portfolio

Wu 法単独と、演繹データベース、角度・比・距離追跡との組合せは補完的である。
IMO-AG-30 について報告された値は Wu 単独15/30、古典記号法との組合せ21/30であり、
一つの大域CASへ全てを渡すより、関係型推論と代数消去を切り替える根拠になる。

- https://arxiv.org/abs/2404.06405

### 2.3 補助構成探索

AlphaGeometry2 は、形式言語の被覆拡張、探索改善、探索木間の知識共有を
別々の寄与として扱っている。本実験では学習モデルを再現せず、
Newclid が実際に導出した証明ハイパーグラフだけから、目標関係へ近い点と
構成族を順位付けする決定論的な探索へ置き換えた。

- https://arxiv.org/abs/2502.03544
- https://github.com/Newclid/Newclid
- https://github.com/janicicpredrag/gclc

## 3. 公開実装の監査

GCLC の現行 `Wu.cpp` / `Reduce.cpp` を読み、実装上の順序を確認した。
現在の GCLC は構成から得た座標順を用い、最大座標変数を含む多項式を選び、
線形 pivot なら他式を直接簡約し、非線形なら低次数の二式を擬除算する。
最終剰余は pivot を逆順に適用する。

したがって MORTRA でも、単なる min-fill 順だけでなく構成順を独立条件として
比較し、各擬除算を係数恒等式として保存する。公開コードを呼んだだけではなく、
停止条件、pivot 選択、最終剰余の順序をテスト可能な部品へ移した。

## 4. 実装

### 4.1 証明書付き疎 Wu 消去

- `worker/backend/certified_wu_characteristic.py`
- 擬除算の各段で multiplier、quotient、remainder を保持する。
- content / primitive-part 正規化も独立した恒等式として記録する。
- 消去中に消滅した変数を「pivot不足」と誤判定しない。
- 中間項数の上限を擬除算ループ内部で検査し、最後の状態を残して停止する。
- 各 micro-step で `L R_i - q_i G - C R_{i+1}=0` を再生可能にする。

### 4.2 正則条件の型付き照合

- `worker/backend/jgex_exact_constraint_bridge.py`
- 座標正規化の分母非零条件と、構成由来の非退化条件を抽出する。
- `worker/backend/wu_polynomial_stalk.py`
- 条件文字列を直接比較せず、有理係数多項式の因子集合として比較する。
- 非零条件は定数倍、冪、因子順の違いを同一視する。
- 入力条件で閉じない regularity は `open` のまま残す。

### 4.3 局所証明書交換

小さな擬除算は micro-step へ分解し、各恒等式を独立に再生する。
実問題で micro-step 自体が上限を超える場合は、証明書本体を生成元エージェント内に
保持し、調停層には SHA-256 の規則名と型付き前提だけを送る。

これは通信量の制御であって、多項式計算の局所分解ではない。
したがって `content_addressed_fallback` を成功した分割数と混同しない。

### 4.4 証明ハイパーグラフからの補助構成

- `worker/backend/typed_geometry_stalk.py`
- Newclid/Yuclid の導出に現れた `point_deps` を支持集合として読む。
- 目標点との重なりを支持集合サイズで正規化し、点の関連度を求める。
- 候補は目標関係の発生数、支持重み、関係遷移距離で順位付けする。
- beam 内で同じ構成族や同じ親だけが占有しないよう、
  `親 x 構成族` の strata を round-robin する。
- `scripts/experiment_newclid_construction_stalk.py`
- 探索前に問題ファイルの補助構成節を除去する。
- 問題番号と既知解答を探索器へ渡さない。
- midpoint / mirror は型付き構成子として列挙し、Newclidで各候補を再実行する。

## 5. 実験A: 固定4問の Wu 消去

### 5.1 条件

- 問題: `2008_p6`, `2010_p2`, `2020_p1`, `2021_p3`
- 表現: relational coordinate constraints
- 変数順: construction order
- 上限: 180秒/問、2並列
- 隠し補助構成: 除去
- 成功条件: 最終剰余だけでなく全恒等式を厳密再生すること

### 5.2 結果

| 指標 | 結果 |
|---|---:|
| 計測完了 | 4/4 |
| 構造変換完了 | 4/4 |
| 三角化完了 | 2/4 |
| 条件付き目標証明 | 1/4 |
| 入力条件だけで閉じた証明 | 0/4 |
| 無条件証明 | 0/4 |
| 擬除算段数 | 61 |
| 正規化証明義務 | 14 |
| 再生成功 | 4/4 |
| 入力条件で閉じた正則条件 | 11 |
| 未閉鎖の正則条件 | 25 |
| oversized 証明書 | 6 |
| micro-step へ分割できた oversized | 0 |
| content-address fallback | 6 |
| 壁時計時間合計 | 174.89秒 |

`2021_p3` だけは最終剰余0まで到達したが、11件の正則条件が未閉鎖なので
条件付き証明である。無条件の正答としては数えない。

### 5.3 GCLC native 比較

同じ `2010_p2` を GCLC の現行 Wu / Gröbner backendへ渡した。

| backend | prover時間 | 最大項数 | 結果 |
|---|---:|---:|---|
| GCLC Wu | 124.766秒 | 9,676 | timeout / 未証明 |
| GCLC Gröbner | 121.188秒 | 179,346 | timeout / 未証明 |

この比較により、MORTRAのPythonコードだけが遅いという説明は棄却される。
座標化後の高次数・退化枝を含む大域義務そのものが重い。

## 6. 実験B: 未解決問題の補助構成探索

### 6.1 対照条件

対象は `2010_p2`。補助構成を除いた Newclid baseline は未証明で、
全導出1,230件、目標導出0件だった。

最初の実験では上位候補をそのまま beam に残した。1,000経路を評価し、
30経路が退化または実行不能、証明0件だった。繰返し mirror が beam を占有し、
構成族の多様性が失われていた。

### 6.2 層別 beam

同じ候補生成・同じ検証器のまま、`親 x 構成族` の strata から均等に候補を残した。

| 指標 | 結果 |
|---|---:|
| 評価経路 | 2,000 |
| 退化/実行不能 | 13 |
| 証明経路 | 4 |
| 選択経路 | `midpoint(a,i)->h`, `midpoint(b,i)->j` |
| 確認時の全導出 | 3,090 |
| 確認時の目標導出 | 216 |
| proof SHA-256 | `55d9d28f8cc466cfa4cc7e9feb5f3495057125b4b8513c4e93f0b0f372523fda` |

データセットに元から記録されていた補助構成は
`mirror(e,o)`, `midpoint(a,i)`, `midpoint(b,i)` の3段だった。
探索器は隠し節を見ず、二つの midpoint だけの別経路を発見した。
したがって既知補助点列の文字列再生ではない。

## 7. 仮説判定

### 支持された仮説

1. 関係型を保持してから必要部分だけ座標化すると、固定4問すべてを消去入力まで運べる。
2. 構成順 Wu 消去は、前段の一括 Gröbner より途中証明義務を細かく記録できる。
3. 証明ハイパーグラフの目標近接度と層別多様性を併用すると、
   単純 beam が落とした有効な補助構成を保持できる。
4. Newclid の推論器は、探索器が新しく提案した2段構成を独立に証明できる。

### 棄却または未支持の仮説

1. 擬除算を micro-step にすれば実問題の巨大証明書を必ず小さく分割できる、は偽。
   途中 remainder 自体が巨大なら一段の恒等式も巨大なままである。
2. SHA-256参照にすれば計算量も減る、は偽。減るのは調停層の通信量だけである。
3. Wu 三角化だけで固定4問が無条件に閉じる、はこの実験では支持されない。
4. 1問の補助構成成功から IMO-AG-30 全体のスコア向上を主張することはできない。

## 8. 科学的結論

今回の前進は「大きな式を別のCASへ投げた」ことではない。
関係型推論、補助構成探索、構成順擬除算、正則条件、厳密証明書を、
検査可能な境界で接続したことである。

最も強い実測結果は、従来未解決だった `2010_p2` に対し、隠し補助点なし・
LLMなし・問題IDなしで、Newclidが検証できる新しい2段補助構成を発見したことだ。
同時に、固定4問の無条件 Wu 証明が0/4だった事実も残す。

## 9. 次の反証可能な実験

1. Wu--Ritt の zero decomposition を実装し、25件の open regularity を
   `initial = 0` と `initial != 0` の有限枝へ分ける。
2. 分岐ごとに Newclid の非退化事実と照合し、閉じない枝は誤答でなく棄却する。
3. 残る IMO-AG-30 未解決集合へ同じ補助構成探索を固定設定で一度だけ適用する。
4. midpoint / mirror 以外の構成族を、問題名でなく型契約から追加する。
5. 単純beam、層別beam、ランダムbeamを同一予算で比較し、
   solved rate、誤構成率、探索時間、証明長を報告する。

受理条件は、未見問題で証明数が増え、全証明書が再生でき、
誤受理が増えず、問題ID・既知解答・隠し補助点に依存しないことである。

## 10. 再現物

- `data/certified-wu-relational-construction-fixed4-micro-2026-08-16.json`
- `data/gclc-native-wu-2010-p2-2026-08-16.json`
- `data/newclid-proof-hypergraph-aux-search-2010-p2-2026-08-16.json`
- `data/newclid-proof-hypergraph-balanced-aux-search-2010-p2-2026-08-16.json`
- `data/newclid-proof-hypergraph-balanced-aux-search-2010-p2-2026-08-16.proof.json`
- `scripts/experiment_certified_wu_fixed4.py`
- `scripts/experiment_newclid_construction_stalk.py`
- `scripts/verify_certified_wu_artifact.py`
- `scripts/verify_newclid_construction_stalk_artifact.py`

検証コマンドは GitHub Actions の
`.github/workflows/reversible-symbolic-geometry.yml` に固定した。
