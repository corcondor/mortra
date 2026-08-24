# MORTRA 全問題.tex Portfolio / Executor Ablation 2026-08-20

## 原理

MORTRAの能力を一つの数字へ混ぜず、次の二条件で測る。

- **portfolio**: 実装済みの型付き定理executorを含む、現在のMORTRAシステム全体を測る。
- **executor ablation（旧cold）**: 定理executorだけを外し、その寄与量を測る対照条件。

portfolioは製品として現在解ける問題数であり、水増しではない。executor ablationは汎化性能ではなく、
型付き数学知識を除いたときに失われる能力を測る。汎化性能は、論文由来の型・射・補助構成・証明器を
すべて有効にしたfrozen portfolioを、未見問題で評価して測る。

## 方法

入力は `全問題.tex` から抽出した85問。各問題を独立プロセスで実行し、失敗や時間超過が後続問題を
止めないようにした。検証済みの場合は、同じ実行結果から次を生成した。

1. 問題文
2. 答え
3. 解答
4. 実行した射のTikZ図
5. 検証記録
6. 独立したupLaTeX文書とPDF

portfolioでは `allow_curated_theorem_kernels=true`、
`allow_legacy_surface_specialists=false` とした。型付き定理executorと旧表層ヒューリスティックを
別フラグに分離し、旧ルータがより厳密なexecutorを隠さないようにした。

## 結果

| 条件 | 検証済み | 未解決 | 時間超過 | 実行エラー | PDF成功 |
|---|---:|---:|---:|---:|---:|
| portfolio | **54 / 85 (63.53%)** | 31 | 0 | 0 | **54 / 54** |
| executor ablation（旧cold） | **11 / 85 (12.94%)** | 73 | 1 | 0 | **11 / 11** |

portfolioの54件は次の内訳だった。

- 型付き定理executor: 43件
- 汎用・分野backend: 11件
- 旧表層ヒューリスティック: 0件

固定結果:

- `artifacts/fullproblems/mortra-autonomous-portfolio-final-20260820/summary.json`
- `artifacts/fullproblems/mortra-autonomous-cold-e2e-20260820/summary.json`

## 実装修正

- 未評価の極限式を答えとして認証しないようにした。
- 型付き定理executorと旧表層ヒューリスティックの有効化を分離した。
- TeX抽出後に空の `enumerate` / `itemize` を残さないようにした。
- `^`、`~`、`_` と原文独自マクロを独立解答TeXで安全に扱うようにした。
- 公開カードへ解答TeXのダウンロードを追加した。
- ローカル開発時もNext.jsとVercel用Python解答APIを同時起動し、UIから実動確認できるようにした。

## 考察

54/85は再実行で一致し、全54件がPDFまで生成できたため、現行portfolioの再現可能な能力である。
ただし、内部証明書による合格と公式解答との外部照合は別の評価である。ablationとの差43件は、
型付き定理executorがMORTRAの数学知識として実際に寄与していることを示す。この差を
「汎化不足」とは解釈しない。

次の汎化実験ではAtlasとexecutorを凍結したまま、数値変更、記号変更、表層言い換え、条件の反転、
未見の射の合成、分野横断合成をheld-outで測る。これにより「型付き構造を再利用・再合成した」のか
「文面だけを認識した」のかを分離する。

## 結論

`54/85`はMORTRA portfolioの正当な再現値である。`11/85`はexecutor除外ablationであり、
汎化スコアではない。今後は製品能力、frozen portfolio汎化、executor寄与ablation、外部正答照合を
別々に更新する。
