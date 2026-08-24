# MORTRA 記号証明器ポートフォリオ接続実験

日付: 2026-08-21

## 目的

HAGeo-409の固定held-out 89問について、既存の証明済み集合を壊さず、未解決38問を
GCLCのArea法・Wu法へ接続すると、MORTRA全体の証明済み集合が増えるかを測る。
問題ID、期待解、公開データの補助構成を探索へ渡さず、保存した証明書だけを正答とする。

## 原理

同じ幾何問題でも、推論器ごとに自然な表現が異なる。

- Newclid/Yuclid: incidence、角、比などの有限述語と演繹規則
- GCLC/Wu: 構成から得た座標多項式の擬除算
- GCLC/Area: 面積法の幾何不変量
- MORTRA typed contract: 未解決述語から補助構成のpostconditionへの逆単一化

仮説は「探索器を一つに統一する」ではなく、型付き構成グラフを各専門表現へ写し、
どれかが返した証明書を共通の真理面へ戻すと、単体の能力集合の和を超えられる、である。
証明器の投票数は正しさに使わず、1本の再生可能な証明で十分とする。

この設計は、記号推論と補助構成を分ける
[AlphaGeometry](https://deepmind.google/blog/alphageometry-an-olympiad-level-ai-system-for-geometry/)、
前向き・後向き推論を形式化する
[FormalGeo](https://github.com/FormalGeo/FormalGeo)、証明依存グラフを公開する
[GenesisGeo](https://github.com/ZJUVAI/GenesisGeo)を参照した。

## 方法

1. 既存の証明書集合和51/89から未解決38問を固定した。
2. データセット由来の補助構成を削除し、自然なJGEX構成だけをGCLCへ変換した。
3. まずWu法を各問60秒、問題全体150秒、2問題並列で実行した。
4. 証明時はGCLCのTeX証明を保存し、SHA-256一致を確認した。
5. 問題名による集合和で既存正答との重複を除いた。
6. 相補性の対照としてArea法を各問10秒、問題全体90秒で同じ38問へ適用した。
7. 翻訳未対応語彙は問題別分岐でなく、原始構成への一般展開として追加し、固定8問を再実行した。

## 実装

### GCLCの直接実行

当初は問題ごとに補助Pythonを起動していたため、Newclid経由でMatplotlibを重複ロードし、
6並列時に `MemoryError` が発生した。翻訳を親プロセスで一度行い、独立一時ディレクトリ内の
GCLC実行だけを並列化するよう変更した。これにより、単独では証明できた2007CMOp4が
並列時だけ失敗する非決定性を解消した。

### 循環的な見かけの進捗の除去

`OI perpendicular MN` に対して `AG parallel OI` を作り、残差を
`AG perpendicular MN` とする候補は、元目標と残差が相互に導けるだけで進捗ではない。
候補postconditionと残差から元目標が導け、候補postconditionと元目標から残差も導ける場合を
reversible goal transportとして棄却した。

### 構成語彙の一般展開

- `free`, `quadrangle`: 自由点
- `on_circum`: 2本の垂直二等分線から中心を構成した円
- `centroid`: 3中点と2中線の交点
- `excenter`: 内角二等分線と、それに直交する外角二等分線の交点
- `eqangle`: 方向ベクトルを平行移動し、外積と内積の多項式恒等式へ変換

数値、問題番号、解答文型は分岐条件に含めていない。

## 結果

### Wu法、固定未解決38問

成果物: `data/mortra-gclc-wu-direct-remaining38-2026-08-21.json`

| 観測 | 件数 |
|---|---:|
| 証明書取得 | 2 |
| 予算内で未証明 | 21 |
| 問題全体の時間打切り | 15 |
| 実行エラー | 0 |

証明できた問題:

- `2007CMOp4`: Wu法 0.11秒（最終ポートフォリオ再生時）
- `2021CGMOp7`: Wu法 4.99秒

`2007CMOp4`は既に単独実験で能力集合へ加えていたため、38問実験による新規差分は
`2021CGMOp7`の1問である。

### 証明済み能力集合

成果物: `data/hageo-certified-capability-union-gclc-2026-08-21.json`

| 段階 | 証明済み | スコア |
|---|---:|---:|
| 実験開始時 | 51/89 | 57.30% |
| 2007CMOp4接続後 | 52/89 | 58.43% |
| 2021CGMOp7接続後 | **53/89** | **59.55%** |

開始時からは2問、+2.25ポイント。直前の52/89からは1問、+1.12ポイントである。

### Area法の相補性

成果物: `data/mortra-gclc-area-remaining38-2026-08-21.json`

- 追加正答: 0/38
- 時間打切り: 17/38
- 予算内未証明: 21/38

この固定集合ではArea法の追加正答は観測されなかった。したがってArea法を既定の先頭に
置く根拠は得られず、Wu法を既定とし、Area法は選択可能な対照に残す。

### 語彙拡張

初回観測で `quadrangle / on_circum / excenter / centroid / free / eqangle` により
翻訳不能だった8問は、一般展開後すべてGCLC入力へ変換できた。固定8問の再実行では
追加正答0、時間打切り4、予算内未証明4だった。

## 考察

支持された仮説:

1. 専門証明器の未接続は実際の失点原因だった。Wu法の接続だけで2問の証明を回収した。
2. 表現変換と証明器実行を分離すると、証明器を交換して相補性を測定できる。
3. 証明ファイルのハッシュと問題名の集合和により、重複や見かけの正答を排除できる。

支持されなかった仮説:

1. 翻訳語彙を増やすだけでは正答は増えなかった。
2. Area法はこの38問ではWu法を補完しなかった。
3. 現在の候補集合で探索深さだけを増やしても、先の実験では終端正答が増えなかった。

残る本質的ボトルネックは、Wu法で数万から16万項へ膨張する消去を、現在の地上残差に
対応する小さな中間補題へ分割する機構である。これは問題別解法の追加ではなく、
`typed obligation -> admissible lemma schema -> specialist certificate -> parent proof DAG`
という同一規則で実装する必要がある。

## 結論

GCLC/WuをMORTRA全体の真理面へ接続し、固定held-out 89問の証明済み集合を
**51/89から53/89へ増加**させた。これは証明書の実体とハッシュを伴う差分であり、
期待解や問題IDによる暗記ではない。一方、38問中36問は新規に閉じておらず、任意の幾何問題を
解ける段階ではない。次の実験は、巨大な一括消去を型付き中間補題へ分解し、各補題を
Newclid/GCLC間で交換したときの追加正答と計算時間を測ることである。

## 再現成果物

- `scripts/experiment_hageo_passk.py`
- `scripts/benchmark_hageo_passk_cohort.py`
- `scripts/benchmark_hageo_passk_sharded.py`
- `worker/backend/jgex_gclc_translator.py`
- `scripts/update_hageo_capability_union.py`
- `data/mortra-gclc-wu-direct-remaining38-2026-08-21.json`
- `data/mortra-gclc-area-remaining38-2026-08-21.json`
- `data/hageo-certified-capability-union-gclc-2026-08-21.json`
