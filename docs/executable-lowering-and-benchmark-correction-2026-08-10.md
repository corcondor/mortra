# 実行可能loweringとベンチ指標の訂正（2026-08-10）

## 結論

MathOSの評価単位を次の5段階に固定する。

1. `formalized`: 問題文から型付き対象・制約・queryを得た。
2. `lowered`: 制約をbackendが受理する具体的な引数へ変換した。
3. `executed`: backendが停止し、結果または証明書を返した。
4. `verified`: 独立な検査が結果を承認した。
5. `exact`: frozen正答と一致した。

Atlasのbackend欄に名前があるだけでは `lowered` でも `executed` でもない。
従来の「112射」は型付き射契約の数であり、112個の実行器が存在するという意味ではない。

## 誤比較の訂正

MathNet 44問に対する36.4%は、型グラフ上でquery sortへ到達した割合であり、正答率ではない。
AlphaGeometry 2の42/50 = 84%は、形式化済み幾何問題に対する証明成功率である。両者は比較できない。

同日に再実行した固定公開135問の実測は次の通り。

| 指標 | 値 |
|---|---:|
| exact | 110/135 = 81.48% |
| answered | 114/135 = 84.44% |
| precision | 110/114 = 96.49% |
| wrong | 4 |
| abstain | 21 |
| timeout | 0 |

これは小規模固定監査であり、AlphaGeometry 2と同じ問題集合ではない。さらにfrozen 3,574問では
672/3,574 = 18.80%、回答精度53.59%である。135問の81.5%をMathOS全体の正答率とは呼ばない。

## 今回追加した実行経路

```text
TeX relation AST
  -> affine form (coefficient map + exact rational constant)
  -> LinearInvariantProgram
  -> exact rational Gaussian elimination
  -> provenance-carrying certificate
```

同じlowering関数と同じ消去器を、次の座標で共有する。

- additive: 一次方程式、状態変化、アフィン量
- log_multiplicative: 積・比・素因数指数を加法化した座標
- angle: 有向角を加法化した座標

問題族ID、問題番号、固定数値、模範解答を経路選択に使わない。非線形積は線形backendへ誤投入せず、
`nonlinear` として次の多項式イデアルbackendへ送る。

## 実証したこと

- 日本語を含む文からTeX関係式とquery式を抽出し、`x+y=10, y=3` から `x+2=9` を厳密計算した。
- additive、valuation/log、angleの3領域が同一lowering・同一消去器を通った。
- 変数名と係数を変更しても同じ実行契約を維持し、答えは再計算された。
- `x*y=6` は線形問題として偽装せず棄却した。

Worker全68テストとTypeScript buildは成功した。ただしこの68は公開問題の正答数ではない。

## 残るボトルネック

frozen 3,574問の最初の失敗層は、morphism-to-backend 2,096、semantic/strategy 578、
elaboration 108、backend execution 89である。最大の問題は語彙数より、型付き意味IRを実行可能な
制約へloweringする実装が未接続なことにある。

次の優先順位は、問題型を追加することではなく、共通述語代数ごとに実行loweringを完成させること。

1. additive / log / angle linear（今回の実装）
2. polynomial ideal / Groebner / resultant
3. order / inequality / optimization
4. finite incidence / counting
5. auxiliary-term synthesisと証明探索

この分解は幾何専用ではない。整数、代数、解析、数列、確率でも、同じ標準座標と消去器へ
loweringできる部分を共有し、共有できない非線形部分だけ別backendへ送る。
