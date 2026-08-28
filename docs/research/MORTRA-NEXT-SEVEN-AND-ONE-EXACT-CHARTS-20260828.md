# MORTRA: 次の未認証7問と既認証1問の厳密チャート反復

日付: 2026-08-28
対象: HAGeo 409問のうち既存認証89問の外側
制約: MORTRA内部の外部LLM不使用、期待解答不使用、問題ID分岐不使用

## 目的

既存の認証済み89問と直前に観察した14問を終点にせず、残る問題を実際に解く。停止問題を一問ずつ例外処理するのではなく、構成DAGを少数の正規形へ写し、問題名を変えても再生できる厳密チャートとして実装する。

同時に、次の三つを分けて測る。

1. 観察した対象問題を、問題文、証明、図、証明書付きで閉じたか
2. 同じチャートが内容を見ていない残余問題へ転移したか
3. 誤ゴール、量化の欠落、曖昧一致を正解としていないか

## 仮説

今回の停止問題群は、定理名の追加ではなく次の4表現で圧縮できる。

- 中点、反射、射影をアフィン写像として合成する
- 円と直線の第2交点を、既知根または方べきの積で消去する
- 内接円を単位円へ正規化し、三辺を接線として表す
- 等角・等長・直交を内積と外積の0恒等式へ落とす

この仮説が正しければ、各問題の固有数値を保存せず、改名された同型構造でも同じ証明書を再生できる。ただし、対象を見てから実装したチャートはposthocであり、未見転移とは別に数える。

## 原理

```text
型付きJGEX構成DAG
  -> 相似座標または単位内接円座標
  -> 中点・反射・垂足・既知根を有理射として合成
  -> 最終目標より強い低次元不変量を抽出
  -> 全構成条件と目標を小さい0恒等式へ分割
  -> CAS再生
  -> 問題文・証明・図・SHA-256証明書
```

第2交点の枝をJGEXだけで区別できない場合に限り、自然文から `distinct` 原子を要求する。自然文がその枝を指定しなければ、座標恒等式が0でも公開正解にはしない。

## 方法

各停止問題について、構成を最後まで直接読み、目標を含意する最小の強い不変量を先に求めた。その後に構成順序へ戻り、全中間条件を同じ座標体上で再生した。

各チャートには次の負例を含む。

- 点名を全面的に変更した同型問題
- 目標だけを別述語へ変えた問題
- 第2交点の自然意味を削除した問題
- 共通ポートフォリオ上での競合・曖昧一致

## 結果

### 解いた問題と強い不変量

| 問題 | チャート | 強い不変量 | 残差 | 証明書SHA-256 |
|---|---|---|---:|---|
| 2010AsiaPacificMOp1 | `circumcenter-secondary-circle-diameter-parallelogram` | `A+N=P+Q` | 14 | `6b2cece6cb1e424e5e296892f7672426bcfc07951518f33a66b97ced2a53922e` |
| 2010CTSTp19 | `isogonal-median-two-circumcenters-midpoint-on-euler-radius` | 2外心の中点が `AO` 上 | 14 | `a4269b95d84b741fc41af76f3a2ca90e08a7239ce6fff5c5393ba44d916186a4` |
| 2011ARMOg10p6 | `cross-altitudes-right-angle-pedal-on-diameter-circle` | 垂足 `F` が直径 `BC` の円上 | 10 | `7fec27627fabab2e140c84466bf63cd6a553e63b87108bae8185ce8bc03fbb82` |
| 2017CHNSouthEastMOg10p2 | `midpoint-feet-two-circumcenters-parallel-to-base` | 2外心の高さが一致 | 18 | `a3657eda8d707ece8cf3347b1344c8ebab9e3a426bc659a6961a9422ceab2ad0` |
| 2019GOTEEMp2 | `orthic-transversals-midpoint-right-angle` | `M dot T=0` | 14 | `fba33b43a53bd5352a6ea07609824f0882751533c28612c31578ff15b1eab9a5` |
| 2020AQGOp4 | `transversal-cross-midpoints-perpendicular-bisectors-translation` | `vector(MN)=vector(PQ)` | 13 | `dbca7315f6643a3083dd11136c4e724e6ba849ee934f766c5475715a67b3c349` |
| 2020POGCHAMPp1 | `cyclic-cevian-reflection-second-roots-parallel` | `Q=lambda(C-B)` | 22 | `b0dbc1e21ac1c92f64f727b3df7d0fec4cb63ed431fb4d8084bbbeadc89e058d` |
| 2022CGMOp3 | `unit-incircle-midline-perpendicular-antipode-equal-angle` | 内積・外積による有向角恒等式 | 8 | `b161ab2a4cbec50003699d3142ca48efbf844247cb8951ebadb229f32f5473b5` |

8チャートで113個の残差がすべて0へ還元された。`2017CHNSouthEastMOg10p2` は既存89問ですでに認証済みだったため、新規得点ではなく別形式の厳密証明と図の追加である。残る7問は、既存89問の外側から追加で閉じた。

### 構造監査

開発集合を更新する前に、既存89問と従来の開発14問だけを除外して306問を再評価した。

| 指標 | 結果 |
|---|---:|
| 評価問題 | 306 |
| 厳密一致 | 7 |
| 量化修復のみ | 0 |
| 曖昧一致 | 0 |
| 狙った7問以外の一致 | 0 |

一致した7問は、今回内容を読んだ未認証7問と完全に一致した。

次に今回観察した8問を開発集合へ追加した。既存89問との重複1問を除くと、残る完全未見集合は299問である。

| 指標 | 結果 |
|---|---:|
| 完全未見問題 | 299 |
| 厳密転移 | 0 |
| 量化修復のみ | 0 |
| 曖昧一致 | 0 |
| near attempt | 9 |

したがって、今回の結果は未認証7問の追加厳密解であり、未見転移得点の上昇ではない。

### 証明書と図

新規7問について各4ファイル、合計28ファイルを生成した。

```text
*.chart-portfolio.json
*.artifact.json
*.proof.md
*.proof-focus.svg
```

独立監査は7/7を受理し、95個の再生残差、入力ハッシュ、証明書ハッシュ、問題名、目標、量化枝を照合した。拒否は0だった。

### 回帰

8チャートの正例、改名、誤ゴール、自然意味、SVG生成をまとめた重点回帰は34/34成功した。全チャート、転移監査、成果物生成、同期セッションを含む回帰は287/287成功した（541.69秒）。

同じプロセスで待機していたMORTRAへ、問題名を含まない型付き射列を返して凍結11問を再評価した。11問は介入前から11/11証明済みだったため `rejected_no_strict_gain` となったが、回帰0、曖昧一致0、証明書欠損0を維持した。decision entryは `06ed223e604d58622762cae96ba0e68749e0740b7b21261b9337870d3a605af3`、次観測後のledger headは `38d5e5b6f0ad0c29ddbaedb271ec83db6f5554d68384ce9986f1cffc57968f3d` である。

## 考察

### 何が得点を増やしたか

探索深度を増やしたことではない。各問題で複雑に見えた構成を、最後に残る1個の不変量へ縮約したことが直接要因である。

- 2外心の座標全体ではなく、共有する高さだけを比較する
- 円の中心を毎回求めず、既知根と方べきの積を使う
- 内心の公式を根号付きで持たず、単位円への3接線で表す
- 平行・直交・等角を、最終的に1個の外積または内外積恒等式へ落とす

この縮約により、問題文の点名と固有数値をsolverから除外できた。

### 何がまだ足りないか

完全未見299問で追加転移0だったため、チャート照合の被覆はまだ狭い。数学表現は共有されていても、現状は構成DAG全体がほぼ同型でないと発火しない。

次の改善対象は規則の無差別追加ではない。near attempt 9問について、現在の強い不変量へ至る前のどの射が欠けたかを比較し、1本の双方向変換で複数問の停止義務を閉じる場合だけ共通核へ昇格する。

### 解法暗記との境界

問題ID、期待解答、問題固有の数値による分岐はない。改名構造でも再生し、誤ゴールは拒否する。しかし対象問題を見た後に実装したため、7問の成功はposthoc closureである。

厳密に解けた事実と未見汎化を分けたことで、解けた7問を不正解へ落とさず、同時に未見得点を水増ししない評価になっている。

## 結論

処理を継続し、既存89問の外側から7問を追加で厳密閉包した。既認証1問にも別の厳密証明を追加し、8チャート113残差をすべて再生した。新規7問の証明、図、証明書28ファイルは7/7受理、重点回帰34/34、全体回帰287/287、誤ゴール・曖昧一致・量化修復による誤受理は0だった。

完全未見299問への転移は0である。したがって次の目標は、今回の正規形を保ったまま、near attempt 9問の構成差分から複数問へ効く最小射を抽出することである。

## 再現

```text
python scripts/audit_exact_chart_transfer.py \
  --excluded-union data/hageo-certified-capability-union-fused11-closure-2026-08-28.json \
  --dataset data/hageo-409-jgex-2026-08-18.txt \
  --natural-dataset data/hageo-409-natural-language-2026-08-26.json \
  --development-problems data/exact-chart-observed-development-problems-2026-08-28.txt \
  --output data/hageo-409-exact-chart-source-excluded-eight-more-2026-08-28.json

python scripts/run_exact_geometry_chart_portfolio.py \
  --dataset data/hageo-409-jgex-2026-08-18.txt \
  --natural-json data/hageo-409-natural-language-2026-08-26.json \
  --problem-report data/hageo-409-exact-chart-plus-eight-more-development-audit-2026-08-28.json \
  --output-dir artifacts/exact-chart-complement-next-seven-20260828

python scripts/audit_exact_chart_transfer_artifacts.py \
  --transfer-report data/hageo-409-exact-chart-plus-eight-more-development-audit-2026-08-28.json \
  --artifact-dir artifacts/exact-chart-complement-next-seven-20260828 \
  --output data/hageo-409-exact-chart-complement-next-seven-artifact-audit-2026-08-28.json
```

## 成果物

```text
data/hageo-409-exact-chart-plus-eight-more-development-audit-2026-08-28.json
data/hageo-409-exact-chart-source-excluded-eight-more-2026-08-28.json
data/hageo-409-exact-chart-complement-next-seven-artifact-audit-2026-08-28.json
artifacts/exact-chart-complement-next-seven-20260828/
```
