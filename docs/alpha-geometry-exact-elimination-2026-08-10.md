# AlphaGeometry型の厳密消去核をMathOS Workerへ移植

> Historical design reference only. 現在のMORTRAは外部AlphaGeometry runtimeへ依存せず、
> 本文中の実装はMORTRA独自の消去核として保守する。

## 実装

`worker/src/exact-linear-invariant.ts` に、有理数係数の厳密Gauss消去を追加した。

同じ実行核が次の3座標を扱う。

- `additive`: 状態保存、加法的不変量、アフィン結合
- `log_multiplicative`: 比、積、素因数評価などを加法化した座標
- `angle`: 有向角の線形関係

各入力式はprovenanceを持ち、結果は `proved / underdetermined / inconsistent / blocked` のいずれかになる。副条件が未証明なら実行しない。

## AlphaGeometryから採用した原理

AlphaGeometry 2は距離の加法、距離の乗法、角度を別の消去系として実装する。MathOSでは消去アルゴリズムを共有し、座標の意味と副条件だけを分離した。

これは「9述語をそのままコピー」したものではない。少数のbackend正規形へloweringし、exact closureとprovenanceを共通化する設計を採用した。

## 検証

Worker全体60テストが成功した。追加テストは以下を確認する。

1. 加法状態、対数乗法、角度を同一核で証明する。
2. 変数名を変更しても証明値とprovenanceが不変である。
3. 情報不足を`underdetermined`として棄却する。
4. 副条件未証明を`blocked`として棄却する。

## 未完了

現在、Worker Atlasのbackend名と実行核は完全統合されていない。型付き項から `LinearInvariantProgram` を生成するlowererと、UIへ証明証跡を返す接続が次の実装対象である。単にbackend名を宣言するだけでは実行済みと数えない。
