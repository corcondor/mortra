# 微積の解答図を実行可能な成果物にする

## 目的

増減表は二次関数専用の図ではない。一般の関数について、定義域を端点、臨界点、
特異点で分割し、各開区間の導関数の符号と各分割点での値・片側極限を対応させる。
MORTRAでは、問題文の表示器が係数から図を推測するのではなく、計算核が次の成果物を
一括生成する。

1. 問題文
2. 型付き意味IR
3. 増減表
4. 関数の概形
5. 模範解答
6. 検証証明書

公開単位はこの6項目をまとめた `ProblemArtifact` とする。途中の表だけ、答えだけを
完成品として公開しない。

## 共通核

```text
Function + Domain
  -> derivative
  -> critical/singular set
  -> ordered domain partition
  -> sign on each open interval
  -> values and one-sided limits
  -> monotonicity/extrema
  -> table + plot + explanation
```

この経路は関数名や問題文の文型ではなく、順序付き定義域上の微分可能部分という型に
依存する。多項式、有理関数、指数・対数、三角関数、媒介表示は、臨界集合と特異集合を
計算できれば同じIRへ下ろせる。

## 実装境界

- `CertifiedCalculusAnalysis` は分割点、区間符号、関数の振る舞い、表示標本点、証明書を持つ。
- UIはIRに含まれない臨界点や極値を推測しない。
- グラフの標本点は説明用であり、極値の根拠には使わない。
- 検証済みの符号分割が根拠で、数値プロットは独立した観測である。
- 現在のライブ核は、導関数を厳密に因数分解できる三次多項式を端から端まで実行する。
- 不連続点を含む有理関数が同じIRで表現できることを回帰テストで確認する。

## 参考研究

- SymPy Calculus: 定義域、特異点、極限、臨界点、値域を記号計算する。
  https://docs.sympy.org/latest/modules/calculus/index.html
- SymPy Plotting: 2D/3D、媒介、陰関数と適応的標本化。
  https://docs.sympy.org/dev/modules/plotting.html
- Math-Vision Diagrams: 数学的意味と空間配置を同時に満たす図生成の評価。
  https://arxiv.org/abs/2608.08964
- VeriGeo: 問題文、制約、図、解答を同じ実行列から作り、整合性を検査する。
  https://arxiv.org/abs/2606.14176
- DiagramAgent: plan/code/checkの分離と編集可能な構造化図。
  https://arxiv.org/abs/2411.11916
- GF-Reasoner: 自然言語推論と実行可能な形式コードを交互に使う。
  https://arxiv.org/abs/2508.09099
- Newclid: 作図、証明グラフ、証明図を同じ幾何証明から出力する。
  https://github.com/LMCRC/Newclid

## 次の実験

1. 有理関数の極・片側極限を実計算へ接続する。
2. 代数的臨界点は区間隔離証明書で順序を確定する。
3. 指数・対数・三角関数は周期と定義域を先に有限区間へ制限する。
4. 表だけ、グラフだけ、両方の三条件で解答正答率と説明理解度を比較する。
5. 表と概形が同じ証明書から再生成できることを保存後にも検査する。
