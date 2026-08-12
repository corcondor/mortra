# 証明義務と条件依存グラフの検証（2026-08-10）

> Historical experiment. AlphaGeometry2に関する測定は当時の比較記録であり、
> 現在のMORTRA core architectureまたはruntime依存を表さない。

## 結論

`preserves: string[]` と `backend: string[]` は、数学的証明でも実行器でもなかった。
射の定義可能性・保存則・実装実現性を型付き証明義務へ変換し、バックエンド名だけでは
証明済みにしないようにした。

問題解答側では、候補式が同じ条件依存成分の前提を黙って捨てていないかを検査する
ゲートを追加した。同じソース・同じ3,574問での対照実験は次の通り。

| 指標 | ゲートOFF | ゲートON | 差 |
|---|---:|---:|---:|
| 正答 | 850 | 851 | +1 |
| 誤答 | 358 | 267 | -91 |
| 回答数 | 1,208 | 1,118 | -90 |
| exact rate | 23.7829% | 23.8109% | +0.0280 pt |
| 回答精度 | 70.3642% | 76.1181% | +5.7539 pt |

held-out部分でも正答は590から591、誤答は262から192になった。ただし同じ固定集合を
開発中に参照しているため、これは回帰実験であり、新規held-outに対する不偏推定ではない。

## 実装した原理

1. 各射から `definedness`、各保存則、`implementation-realization` を型付き命題として生成する。
2. SymPy、Lean、Wolfram等の名前は実装候補に留め、証明書が義務IDを明示して初めて discharge する。
3. 量を頂点、同じ型付き対象と局所的な文法的付着を辺とする条件依存グラフを作る。
4. 候補式と接続している未使用前提が残る場合は、答えを公開しない。
5. 上限制約、係数1、共通基底の相殺、型の異なる枝への射影は、一般法則として義務を消去する。

数値・問題ID・期待解による分岐は追加していない。

## 汎用アトラスの監査

- 名前付き射: 112
- 型付き証明義務: 417
- 明示証明なしで開いている義務: 417
- 明示証明済みの汎用射: 0

従って、汎用アトラスは現時点では「探索候補の宣言」であり、解答器そのものではない。
以前の `executableMorphismAtlas` という名前は互換性のため残るが、公開判定には
`certifiedExecutableMorphismAtlas` を使う。

## AlphaGeometry 2 非回帰

AlphaGeometry 2は汎用アトラスとは別の専用実行経路である。公式DDAR suiteは26/26、
公式checkoutを有効にしたWorker全テストは100/100で通過した。定式化、補助構成探索、
DDAR証明、偽目標拒否は維持されており、今回の核整理で破壊されていない。

## 残るボトルネック

ゲートONでもmorphism-to-backend gapは2,258件、generic CAS partialは1,985件ある。
証明義務ゲートは誤答を減らすが、未実装の実行射を作らない。次の正答率向上には、
型付き意味IRからCAS制約への lowering と、各義務に証明書を返す実バックエンドが必要である。

## 再現物

- `math_os_prototype/artifacts/public_benchmark_3574_dependency_gate_control_20260810.json`
- `math_os_prototype/artifacts/public_benchmark_3574_dependency_gate_v3_20260810.json`
- `math_os_prototype/artifacts/proof_gate_ablation_3574_20260810.json`
- `math-web/worker/artifacts/standard-model-audit-3574.json`
