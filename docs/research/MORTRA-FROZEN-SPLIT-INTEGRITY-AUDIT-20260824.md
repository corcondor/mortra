# MORTRA 凍結split整合性再監査（2026-08-24）

## 目的

HAGeo固定89問の得点について、証明の非空性だけでなく、認証問題が本当に凍結splitへ属するかを
独立に検査する。過去の集合和を再計算し、問題名の母集団混入、空虚証明、重複除外を分離する。

## 原理

厳格得点集合を次で定義する。

```text
strict = (claimed_certified ∩ frozen_89) - vacuous_unit_ideal
```

得点分母と分子は同一の凍結名簿から導く。後続コホートの問題名が凍結集合外なら、集合和を作る
時点で失敗させる。SHA-256や余り0は証明artifactの再生可能性を示すが、母集団所属の代用には
ならない。

## 方法

- 凍結名簿: `data/hageo-409-heldout-native-baseline-2026-08-18.json`
- 監査対象: `data/hageo-certified-capability-union-stage-guided-v5-2026-08-23.json`
- 非空性除外: 単位Groebner基底`[1]`で独立した非空性証明がない8問
- 実装:
  - `scripts/hageo_frozen_split.py`
  - `scripts/build_hageo_certified_union.py`
  - `scripts/update_hageo_capability_union.py`
  - `scripts/audit_hageo_nonvacuous_union.py`

## 結果

| 項目 | 件数 |
|---|---:|
| 旧集合和の認証主張 | 67 |
| 凍結89問に属する主張 | 56 |
| 凍結split外 | 11 |
| 空虚な単位イデアル証明 | 8 |
| 二条件の重複をまとめた除外 | 12 |
| 厳格認証 | **55** |
| 未認証 | **34** |

現在の厳格下限は **`55/89 = 61.80%`** である。

凍結split外の11問:

```text
2005CTSTp19
2006G9
2016USATSTSTp2
2017CHNGaoLian
2018CzechAPSlovakp2-
2019ELMOSLp4
2021GOWACAp3
2022IranGOAp3
2023PlanetCupp9
2023USAMOp6
XinXingV28p2
```

空虚証明8問のうち7問は上の母集団外集合にも含まれる。凍結集合内で追加除外されたのは
`2023SerbiaMOp6`である。したがって除外の一意な総数は12となる。

未認証34問の正本は
`data/hageo-certified-capability-union-strict-split-audit-2026-08-24.json`の
`sets.unresolved_frozen_problems`に保存した。

## 原因

`hageo-certified-capability-union-exact-2026-08-22.json`までは認証54問がすべて凍結集合内だった。
その後のknown-root-circle系コホートがHAGeo409全体から問題を選び、集合和生成器が凍結名簿との
所属照合を行わないまま分子へ追加した。分母89だけが固定されていたため、母集団外問題が得点へ
混入した。

## 再発防止

集合和の作成・更新・再監査の全経路で凍結名簿を必須入力にした。基礎集合または追加集合に
凍結外の名前が1件でもあれば処理を拒否する。関連回帰試験は **8件すべて成功**した。

## 考察

2026-08-23の`67→59`訂正は非空性だけを監査し、母集団所属を監査していなかったため不十分だった。
この再訂正は数学能力の低下ではなく、以前の得点計算の誤りの除去である。一方、現在の能力主張は
55問分の凍結内・非空な証明artifactに限定されるため、以後の改善は未認証34問への追加証明だけで
測る。

## 結論

現在値は`55/89`である。`59/89`、`61/89`、`67/89`は当時の履歴として残すが、現在の
ベンチマーク値として引用しない。次の実験対象は固定した未認証34問であり、既存の停止段階、
証明DAG、図を直接読み、最終証明へ最も近い問題から継続する。
