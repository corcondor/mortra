# MORTRA HAGeo深さ・Pass@K再現実験

## 原理

HAGeoは、DDARが未証明の問題に対し、1試行内で補助構成を `N=6` round追加し、
独立した構成列を `K=2048/8192` 回試す。論文ではHAGeo-409に対して
Pass@2048で64.3%、Pass@8192で70.2%を報告している。

- 論文: https://arxiv.org/abs/2512.00097
- 公式リポジトリ: https://github.com/boduan1/HAGeo

2026-08-19時点の公式リポジトリはREADMEと図のみで、READMEにはfull codeが
Microsoftの審査後に公開予定と記載されている。従って本実験は公開コードの完全再現ではなく、
論文に明記された `N round × independent Pass@K × terminal DDAR` をMORTRAの
型付き構成語彙とnative Yuclid検証器で再実装したものである。

### 仮説

前実験の深さ2・beam 12は、各層で経路を少数へ潰すため、HAGeoの独立軌道探索と
同値ではない。同一KでNだけを2から6へ増やせば、2段では到達不能だった5点以上の
補助構成証明を発見できる可能性がある。

## 方法

### 固定条件

- 問題: HAGeo-409 frozen held-out `2002CTSTp25`
- dataset auxiliary clauses: 非表示
- 外部LLM: 不使用
- 問題ID・期待答による探索分岐: 不使用
- 候補: 既存の有限型付き構成語彙
- 候補順位: 数値incidence。該当候補がない場合は型検査済み候補からseed付き無作為選択
- 真理判定: native Yuclid証明のみ
- K: 64
- seed集合: 0から63に対応する同一の決定的attempt seed

### 比較

1. N=2、K=64
2. N=6、K=64
3. N=6、K=64を8プロセスへ同じseed集合のまま分割
4. 成功列の全dependency-closed部分列を検査し、最小補助構成数を測る
5. 成功列をゼロから二回再構築し、入力SHA・証明SHAが一致することを検査する

## 結果

| 条件 | 証明 | unique path | 壁時計 |
|---|---:|---:|---:|
| N=2, K=64, thread | 0/64 | 64 | 294.33秒 |
| N=6, K=64, thread | **1/64** | 64 | 1631.47秒 |
| N=6, K=64, 8 process | **1/64** | 64 | **701.40秒** |

プロセス分割は同じ48番軌道と同じ構成列を再発見し、壁時計を2.326倍高速化した。
スレッド版で生じた9件の数値構築競合は、プロセス分離版では0件だった。

### 発見された構成列

```text
intersection_pp(a,o,p,e,o,f)->g
mirror(a,g)->h
midpoint(o,p)->i
foot(b,e,f)->j
foot(d,o,e)->k
reflect(b,e,g)->l
```

成功はattempt 48で得られた。依存閉部分列39本を全検査した結果、`midpoint(o,p)->i`
だけは削除できたが、残る5構成より短い部分列は証明できなかった。

```text
intersection_pp(a,o,p,e,o,f)->g
mirror(a,g)->h
foot(b,e,f)->j
foot(d,o,e)->k
reflect(b,e,g)->l
```

従って、この成功は単に深い列の末尾で1点を偶然拾った結果ではない。発見された
証明は少なくともこのdependency-closed部分列内で5個の補助構成を必要とし、
深さ2探索では表現できない。

### 厳密再生

固定 `PYTHONHASHSEED=0` で成功列を二回ゼロから再構築した。

- replay solved: true / true
- input SHA一致: true
- proof SHA一致: true
- input SHA: `f1c01fa8324965b56071fd78bc88d2aee65818c63acb6b1f52aaf1e76225bd8b`
- proof SHA: `75eb8e293887219d488f3d403058be7e65268e54a08b479209253ff1f4e59c5a`

## 考察

### なぜ前回は探索量を増やしても解けなかったか

前回はHAGeo型の実験単位を再現していなかった。深さ2・branch 32・beam 12では、
第2層以降に残る親経路は12本に制限される。幅を増やしても、同じ少数prefixの近傍を
評価するだけで、8192本の独立した6段軌道にはならない。

今回、独立軌道へ変更するとN=6で実際に新しい証明が得られた。従って「探索量ではなく
補題の質だけが問題」という前判断は不完全だった。正しくは次の積である。

```text
成功確率 = 構成語彙の被覆 × 1軌道の深さ × 独立軌道の多様性
           × verifier能力 × 実行可能なK
```

### 深さを固定すべきか

固定N=6は論文再現のための実験条件であり、MORTRAの最終設計ではない。実運用では、
厳密証明完了、候補枯渇、証明残差の停滞、資源上限を停止条件とする適応深さが必要である。
微分可能回路またはSheaf-ADMMは、`continue / branch / verify / stop` の資源配分だけを
学習し、証明の真偽には関与させない。

### 深くすれば必ず解けるか

必ずではない。HAGeo論文自体もK=8192で70.2%であり、難易度[6,7]では2/22である。
深さは必要な変数だが、誤った構成語彙を深く合成すれば組合せ爆発する。未解決goalから
必要relationへ逆向きに制約しつつ、独立軌道を保持する必要がある。

## 結論

ユーザーの「深さを増やすべき」という指摘は、この問題では実験的に正しかった。
同一K・同一seedでN=2は失敗し、N=6はnative証明を発見した。発見証明は最小化後も
5補助構成を必要とした。前回の深さ2結果から深さの効果を否定した判断を撤回する。

次の実験は、Nを固定値ではなく適応変数にし、Kを64から256、2048へ段階的に増やす。
その際、独立軌道のプロセス分離、prefixキャッシュ、型付き後向き制約を併用し、
Pass@K曲線と計算量を同時に報告する。

## 再現成果物

- `scripts/experiment_hageo_passk.py`
- `scripts/benchmark_hageo_passk_sharded.py`
- `scripts/verify_hageo_passk_artifact.py`
- `scripts/minimize_hageo_passk_path.py`
- `data/hageo-passk-ablation-n2-k64-2002ctstp25-2026-08-19.json`
  - SHA-256 `9297e04bedb41f12fb0866b9b133585726faa45f9de7311fae8a1c81c49b7696`
- `data/hageo-passk-ablation-n6-k64-2002ctstp25-2026-08-19.json`
  - SHA-256 `2d9d815572c61e7129f50678a517c48aa8b43605724d34f596730b209dee8df2`
- `data/hageo-passk-sharded-n6-k64-2002ctstp25-2026-08-19.json`
  - SHA-256 `8a16a3c5e4871a5c3a110e5013ae124ddb741545050aa94618e02be80c58aa22`
- `data/hageo-passk-sharded-replay-n6-k64-2002ctstp25-2026-08-19.json`
  - SHA-256 `1c763fbf7462f0933c2193451c07c859621d8b2a3c5d7bddd83b0064789471dc`
- `data/hageo-passk-minimal-path-2002ctstp25-2026-08-19.json`
  - SHA-256 `0d8d3be93f1cf4a99a419bea8cf2823c47913fa588d4e91f01ea9b69c53facc0`
