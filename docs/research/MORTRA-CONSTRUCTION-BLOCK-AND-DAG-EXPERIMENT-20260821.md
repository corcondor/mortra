# MORTRA 構成ブロック局所消去・AND-DAG再合成実験

日付: 2026-08-21

## 目的

巨大な座標イデアルを一度に消去する代わりに、作図の各構成ブロックを局所因子として
扱い、境界上の中間補題だけをAND-DAGで上位へ渡せるかを検証する。問題ID、数値、
表層文型に依存する分岐は追加しない。

## 仮説

1. 作図依存グラフに沿った局所消去は、全体イデアルの変数数を厳密証明書付きで減らす。
2. 局所クリークが目標の全変数を含む場合、全体Gröbner基底を作らずrootを閉じられる。
3. separator幅を増やせば、より多くの局所補題が得られ、未見問題の正答が増える。

## 原理

各構成を多項式集合 `I_i` とし、共有変数をseparator `S_ij` とする。局所消去は
`I_i ∩ Q[S_ij]` の元だけを隣接ブロックへ送る。送信する各多項式には、元の局所生成元
まで遡れる係数恒等式を付ける。rootは受け取った補題のANDとし、ideal membershipが
0剰余で再生された場合だけ証明済みとする。

線形局所化 `a x + b = 0` は `a != 0` が既存の実行可能な非退化条件から導ける場合だけ
許可する。未知の非零性を仮定して正答を水増ししない。

## 実装

- `construction_block_proof_dag.py`: 構成、局所消去、separator、rootを型付きAND-DAG化。
- `local_polynomial_elimination.py`: 線形消去とresultantの証明書、非零条件の事前型検査。
- `chordal_buchberger_elimination.py`: 有界局所Buchberger、separator補題、局所root閉包。
- `run_jgex_exact_specialist.py`: 独立プロセスと原子的checkpoint。
- `experiment_construction_block_dag_cohort.py`: 外側の候補探索を除いた固定コホート測定。

局所root閉包は、目標変数が一つのクリークに含まれる場合だけ実行する。途中基底で目標が
0へ還元され、全DAG恒等式と最終membershipが再生できた時点で停止する。

## 方法

HAGeo-409の未解決3問に、同一コード・同一予算を適用した。各30秒で右打ち切りを許し、
打ち切り時も最後のcheckpointを回収した。その後 `2024PlanetCupp10` について、
separator幅12、幅16、前処理幅12/DAG幅16を比較した。

## 結果

### 未見3問、30秒

| 問題 | 初期変数 | 前処理後 | 完了クリーク | 補題 | 結果 |
|---|---:|---:|---:|---:|---|
| 2016G6 | 25 | 16 | 2 | 8 | timeout / 未証明 |
| 2024PlanetCupp10 | 31 | 25 | 4 | 16 | timeout / 未証明 |
| 2025KoeraFinalRoundp3 | 24 | 18 | 2 | 6 | timeout / 未証明 |

正答は **0/3**。局所root閉包はこの3問では発火しなかった。

非零条件を消去後でなく消去前に型検査する変更により、`2025KoeraFinalRoundp3` は
前処理開始直後の30秒timeoutから、6変数消去・2クリーク・6補題まで進んだ。
`2024PlanetCupp10` は前処理4段から6段へ増えた。

### separator幅の因果比較

| 前処理幅 | DAG幅 | 時間 | 前処理後変数 | クリーク | 補題 | 結果 |
|---:|---:|---:|---:|---:|---:|---|
| 12 | 12 | 43.04秒 | 25 | 4 | 16 | unproved |
| 16 | 16 | 120秒打切り | 19 | 2 | 8 | timeout |
| 12 | 16 | 49.16秒 | 25 | 8 | 32 | unproved |

全局所証明書とroot replayは成功したが、root membershipは未証明だった。前処理とDAGの
幅を分離すると局所補題数は16から32へ増えたが、正答は増えず、次の幅16超separatorで
停止した。

Artifacts:

- `data/construction-block-dag-prefilter-cohort3-2026-08-21.json`
- `data/construction-block-dag-prefilter-2024planet-120s-2026-08-21.json`
- `data/construction-block-dag-width16-2024planet-2026-08-21.json`
- `data/construction-block-dag-pre12-dag16-2024planet-2026-08-21.json`

## 考察

仮説1は支持された。異なる3問で同じ規則が変数を削減し、証明書を再生したため、一問の
解法暗記ではない。仮説2は小規模回帰例では成立したが、未見3問での追加正答はなく、
転移は未実証である。仮説3は否定された。幅を広げるだけでは補題が増えてもrootは閉じず、
前処理まで広げると多項式が密化して遅くなった。

現在のseparator出力は多項式文字列のままであり、`coll/perp/para/cyclic/cong/eqangle`
などの型付き幾何関係へ戻されていない。そのためNewclid/GCLCは32本の中間補題を利用
できず、Exact backend内に閉じている。これが次の因果的ボトルネックである。

## 結論

構成ブロック局所消去と証明書付きAND-DAGは動作し、計算の途中を検査可能にした。しかし
未見3問の正答は0/3で、スコア向上は主張できない。次の実験は、separator多項式を型付き
関係へ再elaborationし、Newclid/GCLCで再生できる補題だけを交換する処理である。成功条件は
補題数ではなく、固定未見集合における追加正答と、交換証明書の完全再生で判定する。
