# MORTRA 生成作用幾何・Directional CSS 厳密実験（2026-08-27）

## 目的

一つの有限生成作用から複数表現を作るMORTRAの方針が、既存の幾何作図探索にも再利用できるかを検証する。同時に、前回は候補支持としてしか扱っていなかったDirectional Tile Codesについて、CSS相互可換条件と変位偶奇条件を一次資料どおりに実装し、証明書を独立再生する。

評価する問いは次の二つである。

1. 型付き幾何作図列を、生成点の名前や独立な作図順序に依存しない記号的生成作用へ写すと、固定探索予算で未証明問題の探索範囲または追加正答が改善するか。
2. 方向語から作るprimal/dual支持が静的CSS可換条件を満たし、順序付き支持の変位偶奇条件を満たすかを、論文の定義と別形式の計算で検証できるか。

## 原理と仮説

### H1: 幾何作図列の記号的商

各作図を型付き項として表す。

```text
family(input_1, ..., input_n) -> generated_point
```

次の三種類だけを同一視する。

- 生成点のalpha-renaming。
- 作図族が宣言した入力対称性。
- 同じ依存DAGにある独立作図の順序交換。

これにより、同じ記号的作図状態を繰り返し検証せず、同じ経路上限の中で後続候補を検証できる可能性がある。

ただし、これは幾何配置全体の同値ではない。次は同一視しないし、証明書も保証しない。

- 乱数で選ばれる数値分岐の同値。
- 生成点座標の一致。
- 数値分岐を含む探索完全性。
- native verifierの証明結果の同値。

したがって、記号的商は候補選択の処置としてだけ使う。正答は処置の判定ではなく、Yuclidによるnative証明と独立した再生証明書が一致した場合だけ数える。

### H2: Directional CSSの有限検証

論文のmutual conditionでは、`B x B` grid上のX tileの辺を次のZ tileの辺へ写す。

```text
H(a,b) -> V(B-1-a, B-1-b)
V(a,b) -> H(B-1-a, B-1-b)
```

有限支持の全相対平行移動についてX/Z支持の重なりを数え、すべて偶数ならCSS stabilizerは可換である。

変位条件は、順序付き方向列 `d_1,...,d_w` の `i<j` に対して元論文の定理1が与える

```text
Delta(i,j) = d_i + 2 * sum(d_p, i<p<j) + d_j
```

を使う。垂直成分が奇数の同一ベクトルは、すべて偶数回現れなければならない。実装本体は辺の中心を2倍した整数座標で計算し、独立oracleは上式を方向列から直接計算する。両者が一致すれば、同じコードを二度呼んだだけの自己一致ではない。

## 一次資料

- [Nearest-neighbour gates are all you need: High-rate quantum low-density parity-check codes on a planar grid](https://arxiv.org/abs/2606.19482)
  - mutual condition: source `main.tex` line 360。
  - odd vertical displacement condition: line 373、定義: line 377。
- [Directional Codes: a new family of quantum LDPC codes on hexagonal- and square-grid connectivity hardware](https://arxiv.org/abs/2507.19430v3)
  - 定理1のdelta vector: equation (4)。
  - odd multiplicity set: equation (5)。

一次資料のローカルsourceはSHA-256で固定し、別sourceへ差し替わった場合は実験を停止する。

## 方法

### 幾何A/B実験

母集団は監査済み89問である。実験開始時の厳密な能力和は76/89で、未証明13問を凍結した。既証明7問は正答率の水増しには使わず、証明書再生系が既知の証明を壊していないかを見る正の対照とした。

対照群と処置群は同じ問題、seed、作図深さ、native path上限、candidate幅、1問内のcandidate worker数、各種timeoutを使う。機械全体では対照4問、処置1問を並列実行したため、総native worker上限とwall-clockは同一ではない。処置群だけ次を有効にする。

```text
generated_action_quotient = true
generated_action_oversample_factor = 4
```

oversampleはnative検証本数を増やすためではない。記号的重複を除いた後も、各親状態から対照群と同じ最大16本を供給するために候補列挙だけを広げる。各問題のnative検証上限は両群とも112経路である。

主要評価値は次である。

- 独立再生済みの追加正答。
- native検証経路数。
- 記号的重複として除いた候補数。
- right-censored timeout数。
- 証明書再生率と誤受理数。

wall-clock時間は記録するが、専有machine上の速度試験ではないため高速化の主張には使わない。timeoutは不正解ではなく未確定として扱う。

### Directional CSS実験

凍結集合は論文掲載の正例5語と、条件を一つずつ壊す負例2語である。

- 正例: `NESEN`、重み7、9、11、13の掲載語。
- 変位偶奇の負例: `NE`。
- 同じ辺を二度通る負例: `NS`。

さらに `N/E/S/W` の長さ1から6までの全5,460語について、次を検証する。

1. 実装結果と独立代数oracleの一致。
2. 生成した証明書の再生。
3. grid sizeを改変した古い証明書の拒否。

外部LLM、期待解答、問題ID固有分岐は使用しない。

## 結果

### Directional CSS

- 凍結7例: 期待値一致7/7、独立oracle一致7/7、証明書再生7/7、誤受理0。
- 論文掲載の正例: 5/5を認証。
- 長さ1から6までの全5,460語:
  - 独立oracle一致5,460/5,460。
  - 証明書再生5,460/5,460。
  - grid sizeを改変した古い証明書の拒否5,460/5,460。
  - 単純支持1,392語、静的可換5,460語、変位偶奇1,404語、三条件すべてを満たす語104語。
- 順序付き全結果のSHA-256は`ef952c9d9125bc838953fe1008ee5d55418f01ba3739ab475494f81f0ca88841`で、再実行後も不変だった。

### 幾何生成作用

- 実験前の厳密能力和: 76/89、正答率85.393%。
- 既証明7問の独立再生: 7/7、入力・証明ハッシュ不一致0。
- 過去に検証した1,505作図列を正規化すると1,487状態となり、18列、1.196%を同じ記号的生成状態として除けた。
- 正規化エラー0、生成作用証明書の再生失敗0、同じ同値類内のnative proof outcome不一致0。
- 因果比較できる完走10問では、対照・処置とも1,120経路をnative検証した。
- 処置群は1,134候補を正規化し、14候補、1.235%を同値として除き、次順位を補充して対照と同じ1,120経路を検証した。
- 処置群の無効候補0、生成作用証明書再生失敗0。
- 完走10問の追加正答は対照0、処置0。正答率は76/89、85.393%のままである。
- 残る3問は対照または処置が時間上限に達したため、因果効果から除外した。右打ち切りは不正解として数えていない。
- 全13問の終了状態は、対照が未証明10・右打ち切り3・実行エラー0、処置が未証明11・右打ち切り2・実行エラー0である。
- `ShuZhiMiGeo309`の処置実行は累積96経路をcheckpointへ保存したが、最終artifactの書き込み前に1時間上限へ達したため、完走へ読み替えず右打ち切りのまま固定した。
- 問題worker数が対照4、処置1で異なるため、wall-clockの高速化・低速化は主張しない。

### 実行系

長時間再開中に、Windowsの仮想環境launcherだけを止めると実体Pythonが残りうる経路を検出した。探索を独立process groupで起動し、時間切れ時はprocess tree全体を終了するようにした。また、証明事実の位置索引を`Atom`集合の複製から整数posting listへ変更し、大きな証明DAGの常駐複製を削減した。これらは実行安定性の修正であり、数学正答の増加としては数えていない。

## 考察

H1は限定的に成立した。生成点名、宣言済み入力対称性、独立作図順序を商にしてもnative outcomeの不整合は起きず、同じ検証本数のまま重複を後続候補へ置換できた。一方、重複率は過去列・前向き実験とも約1.2%で、13問の追加正答は0だった。したがって現在のボトルネックは同じ作図列の再検証ではなく、既存の作図族にない中間構成・表現間変換である。

凍結13問の表層語彙には、外心13問、円上12問、内心7問、垂足6問、中点4問が現れる。これは次の実装範囲を定める在庫であって、失敗原因の因果証明ではない。次の実験では、停止したtyped obligationを直接読み、複数問を同時に閉じる最小チャートだけを追加する。

H2は検証した有限範囲で成立した。mutual condition、全相対平行移動でのCSS可換性、順序付き変位偶奇を別形式で再計算し、全5,460語で一致した。ただし、これは無限長の完全証明、量子符号の距離・率、境界条件、論理演算、物理processor性能を示さない。

次の研究順序は次のとおりである。

1. 角の二等分線、射影、極、調和束。
2. 接線、方べき、円周角の双方向変換。
3. 複数外心、反転、相似中心のアフィン・複素表現。
4. 3次元・順序・非退化条件の型付き処理と自然文elaboration。
5. 幾何・整数・確率・微積の可逆作問チャート。
6. 問題文・図・証明を公開作問へ接続する経路。
7. 幾何以外の凍結ベンチマーク。
8. 長時間探索を安全に再開する永続worker。

分野横断の少数生成チャートとして、`漸化式 <-> 行列 <-> 特性多項式`、`付値 <-> 合同式 <-> 整除性`、`アフィン・二次形式 <-> 円幾何`、`有限状態 <-> 遷移行列`を同じ凍結A/B手順で測る。

## 結論

既存の幾何作図列は、証明書付き有限生成作用へ安全に写せた。記号的重複の除去と証明再生は成功したが、現在の未証明13問に対する追加正答は0であり、数オリ正答率の上昇は示されなかった。次に正答を増やすには商を広げるのではなく、停止義務から再利用可能な中間構成チャートを追加し、同じ凍結集合で再測定する必要がある。

Directional CSSについては、以前未検証だった相互可換条件と変位偶奇条件を一次資料から実装し、凍結例と長さ6までの全語で独立照合・証明書再生・改変拒否を完了した。主張範囲はこの有限検証に限定する。

## 再現

```powershell
# Directional CSS
node worker/node_modules/tsx/dist/cli.mjs --test tests/directional-word-cross-domain.test.ts
node worker/node_modules/tsx/dist/cli.mjs scripts/directional-css-certificate-experiment.mts

# 生成作用の単体検証
python -m pytest worker/backend/test_generated_construction_action.py -q

# 最終集計。compact cohort reportだけで再集計できる。
python scripts/experiment_geometry_generated_actions.py `
  --manifest data/geometry-generated-action-frozen-v1.json `
  --output data/geometry-generated-action-experiment-2026-08-27.json `
  --fresh-replay-dir data/geometry-generated-action-fresh-replays-2026-08-27 `
  --control-report data/geometry-generated-action-control-remaining13-2026-08-27.json `
  --treatment-report data/geometry-generated-action-treatment-remaining13-2026-08-27.json
```

生のrun directoryがある環境では`--control-run-dir`と`--treatment-run-dir`も指定すると、compact reportへ埋め込んだartifact SHA-256を再照合する。

凍結入力と結果:

- `data/geometry-generated-action-frozen-v1.json`
- `data/geometry-generated-action-unresolved13-frozen-v1.txt`
- `data/geometry-generated-action-experiment-2026-08-27.json`
- `data/directional-css-frozen-v1.json`
- `data/directional-css-certificate-experiment-2026-08-27.json`
