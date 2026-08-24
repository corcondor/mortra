# MORTRA 型付き中間補題・Wolfram証明書交換実験

日付: 2026-08-21

## 目的

Newclid/Yuclidが残した型付き証明義務をGCLC/WuとWolframへ渡し、外部LLM、問題ID、
期待解、データセット付属の補助構成を使わずに、固定未見集合の追加証明を得られるかを測る。
同時に、時間切れを「未証明」と誤記録せず、証明書をMORTRA側で再生できる場合だけ
正答へ昇格する評価系を作る。

## 原理

各証明器の表現を同一文字列へ潰さず、型付き証明義務だけを交換する。

1. Yuclidは有限述語による前向き演繹を行う。
2. 未解決のground atomを、問題番号に依存しないGCLC関係語彙へloweringする。
3. GCLC/Wuが返した証明、またはWolframが返した多項式cofactorを検査する。
4. Wolframの結果は `goal * multiplier = sum(q_i * f_i) + remainder` をSymPyで再生する。
5. `remainder = 0`、前処理証明書の再生成功、使用した非退化条件の記録が揃った場合だけ
   中間補題をtyped proof DAGへ戻す。

Wolframの `PolynomialReduce` は商と剰余を返す。
[公式仕様](https://reference.wolfram.com/language/ref/PolynomialReduction.html)を用い、
基底から元仮定への変換には
[ExtendedGroebnerBasis](https://resources.wolframcloud.com/FunctionRepository/resources/ExtendedGroebnerBasis/)
の変換行列を利用できるようにした。Wolfram自体を真理面にはしていない。

## 仮説

- H1: 型付き中間補題交換により、固定5問の証明済み数が対照条件より増える。
- H2: 数値incidence gateは偽候補を実行前に除き、正答を失わず実行時間を減らす。
- H3: GCLCで時間切れになる義務の一部を、Wolframの再生可能cofactorが閉じる。
- H4: 通常のideal membershipで残る剰余の一部は、既存elaboratorが持つ非退化条件による
  saturationで0になる。

## 方法

固定集合:

- `2007CMOp4`
- `2016CTSTp5`
- `2016G6`
- `2024PlanetCupp10`
- `2025KoeraFinalRoundp3`

共通条件は `N=1, K=1, contract-portfolio, feedback=2`。GCLC/Wuは1義務5秒、
中間補題上限2。候補は型付きopen obligationから作り、問題名や数値による分岐を置かない。

比較条件:

1. control: 中間補題交換なし。
2. ungated: GCLC中間補題交換、数値gateなし。
3. gated: 1回の独立数値incidence gate後にGCLCを実行。
4. Wolfram direct: GCLC後に元仮定への `PolynomialReduce` を4種の変数順序で実行。
5. saturation single/cumulative: 型付きelaborator由来の非零因子を単独または累積でgoalへ掛ける。

証明器の内部時間切れ、プロセス時間切れ、実行エラー、予算内未証明を別状態として保存した。

## 実装

- `scripts/experiment_hageo_passk.py`
  - GCLC/Wolframのtyped lemma exchange
  - 内部時間切れの右打切り伝播
  - 証明書・前処理・実行ファイルのfingerprint
- `worker/backend/wolfram_polynomial_certificate.py`
  - direct / extended Groebnerの選択
  - SymPyによるcofactor再生
  - 非退化条件によるsingle/cumulative saturation
  - 局所消去証明書の再生を採用条件へ追加
- cohort/sharded/adaptive runner
  - Wolfram条件をCLI、再開互換性、成果物protocolへ伝播
  - 打切りがある場合は主 `pass_at_k` をnullとし、証明済み下限を別記

## 結果

### 固定5問

| 条件 | 証明済み | 右打切り | 完全観測 | 経過秒 |
|---|---:|---:|---:|---:|
| control | 1/5 | 0 | 5/5 | 77.53 |
| ungated | 1/5 | 1 | 4/5 | 141.04 |
| gated、旧集計 | 1/5 | 0と誤記録 | 5/5と誤記録 | 105.82 |
| gated、修正後 | 1/5 | 4 | 1/5 | 105.57 |

修正後の主 `pass_at_k` は、4問が未確定なのでnull。証明済み下限は `1/5 = 20%`。
完全観測1問だけを分母にした100%は主スコアに用いない。

H1は支持されなかった。H2も、この小集合では正答増加・実時間短縮の証拠を得られなかった。

### 2016G6の局所義務

数値gateを通った候補は `perp(a,e,p,q)` と `perp(a,f,p,q)`。

- GCLC/Wu: 両方とも内部時間切れ。最大多項式はそれぞれ8,881項、8,729項。
- Wolfram direct: 7.13秒、8.88秒。両方とも返却恒等式はSymPyで完全再生したが、剰余は非零。
- 式規模: 初期21式・25変数・105項。局所消去後は候補ごとに17式/21変数/181項、
  15式/19変数/177項。局所消去は変数を減らしたが項数を増やした。
- single saturation: 10個の型付き非零因子を試し7.32秒、追加証明0。
- cumulative saturation: 60秒内部予算で打切り、実経過117.78秒、追加証明0。

H3とH4はこの問題では支持されなかった。誤証明は0。

### 回帰

- backend pytest: 58件成功
- runner/unittest: 30件成功
- 合計: **88件成功**

## 考察

追加正答が出なかった主因は、証明深さだけではなく表現幅である。`2016G6`では
`eqangle3`と長さ変数が多くの構成節を同一成分へ結び、goal coneで全10構成節が残った。
局所線形消去は変数数を減らしても項数を105から181へ増やした。非退化因子の累積積は
さらに式を肥大化した。このため「探索を深くする」「非退化条件を全部掛ける」だけでは改善しない。

一方、次の点は前進した。

1. GCLC内部時間切れを予算内未証明と誤分類していた評価バグを除去した。
2. CASの出力を答えとして信頼せず、元式へのcofactor再生を必須化した。
3. 陰性結果でも非零剰余、式規模、前処理証明書、実行ファイルhashを保存できる。
4. 非退化条件は新規暗記ではなく、既存の型付き構成意味論から取得している。

## 結論

今回の実験では証明済み集合は増えず、HAGeo固定89問の証明済み能力集合は
**53/89 = 59.55%のまま**である。したがって得点改善を主張しない。

ただし、型付き義務をGCLC/Wolframへ渡し、再生可能な証明だけをproof DAGへ戻す経路と、
右打切りを正しく扱う評価系は完成した。次の実験は巨大な多項式を平坦化せず、
構成blockごとの小さなseparator義務として交換することを目的とする。

## 次の実験

名称: Typed Separator Certificate Exchange

目的: `eqangle3`・距離変数が作る幅広い多項式系を構成blockへ分割し、境界変数上の
中間補題だけをNewclid/GCLC/Wolfram間で交換したとき、最大同時変数数と追加正答が改善するか測る。

受理条件:

1. 問題ID・期待解・問題別補題を使わない。
2. 各separator補題は元の構成式へ再生できる。
3. 固定未見集合で追加証明が1問以上、または右打切り時間が有意に減る。
4. 既存53証明をすべて再生できる。

## 成果物

- `data/gclc-lemma-ablation-control-frozen5-2026-08-21.json`
- `data/gclc-lemma-ablation-treatment-frozen5-2026-08-21.json`
- `data/gclc-lemma-ablation-gated-censored-frozen5-2026-08-21.json`
- `data/wolfram-direct-gclc-exchange-v2-2016g6-2026-08-21.json`
- `data/wolfram-saturation-single-2016g6-ae-2026-08-21.json`
- `data/wolfram-saturation-cumulative-2016g6-ae-2026-08-21.json`
