# MathOS 標準模型核の全件監査（2026-08-10）

## 結論

正答率停滞の主因は backend の個数ではない。Python の問題型別実行経路と、
Worker の型付き項探索が分離している。Worker は理論上の射を探索できるが、
公開 3,574 問の大半を値付き数学対象へ elaborate できていない。

## 全 3,574 問の観測

正解・解答は Worker に渡さず、問題文だけを一括で意味グラフ化した。

| 観測 | 件数 | 割合 |
|---|---:|---:|
| query を認識 | 506 | 14.2% |
| 問題固有の `OpaqueSort` に落下 | 2,906 | 81.3% |
| 非 opaque root と query の両方を取得 | 248 | 6.9% |
| 構造署名 | 158 | - |

最大クラスタは `OpaqueSort + queryなし + relationなし + operatorなし` の
2,648問だった。これは問題が多様だからではなく、elaboration が意味を捨て、
各問題本文のハッシュを別ソートとしているためである。

分野別の kernel-ready 件数:

| benchmark | ready / total |
|---|---:|
| MATH | 217 / 700 |
| GSM8K | 20 / 1,319 |
| AQuA-RAT | 10 / 254 |
| ASDiv | 1 / 301 |
| SVAMP | 0 / 300 |
| MultiArith | 0 / 180 |
| MAWPS | 0 / 520 |

## Python 正答との交差監査

直前の固定回帰（850/3,574）と case ID で照合した。

| Worker状態 | 問題数 | Python正解 | Python回答 |
|---|---:|---:|---:|
| kernel-ready | 248 | 48 | 75 |
| kernelに入らない | 3,326 | 802 | 1,134 |

したがって、850正解を統一核の性能と呼ぶことはできない。Python の
`arithmetic_nl`、`quantity_reasoner`、個別 synthesis 群が回答している。

## 核・理論・表層を分離

最初の監査では、実行核を次の固定8生成子として仮置きした。

```text
coerce / tensor / map / action / relation / quantify / observe / certify
```

しかし一次資料との比較で、これは項構文、数学操作、判断、実行サービスを混同
していると判明したため撤回した。現在は OpenMath/MMT 型の5項構成子、4構造
宣言、3判断、5実行サービスへ分離している。既存112個の名前付き射は核命令では
なく、型付き定数宣言と適用項として保持する。

これは「112を5に圧縮して数学を解いた」という意味ではない。5個は数学の演算
ではなく、任意の対象項を書くための構文である。94の法則内容を実行可能な判断と
証明義務として持つ必要がある。現状は法則の多くが文字列ラベルまたは backend 名
であり、ここが未完成である。設計根拠と一次資料は
`primary-source-mathematical-knowledge-core-2026-08-10.md` に記録した。

## 実装した変更

1. 全ての理論射を型付き宣言・適用項・型判断へ lower する `kernel-calculus` を追加。
2. 型・保存則・backend契約が衝突する射を監査する。現状では
   `RootMinkowskiSum / Difference / Product` が同じ契約へ潰れるため、法則IRなしの
   自動商は不健全として禁止した。
3. 公開問題を問題文だけで一括監査する `standard-model-audit` を追加。
4. 直前に追加した別系統 `IncidenceGraph` solver は、4問改善しても核を
   肥大化させるため棄却し、Python回答経路から削除した。

## 次の受理条件

次の改善は solver 関数を増やしてはならない。

1. 値、対象、単位、添字、時点を持つ型付き項を Worker 正本へ保持する。
2. 自然文・TeXの関係を、文字列でなく実行可能な項・論理式へ lowering する。
3. 同じ制約核を線形代数、有限モデル、半代数、整数の解釈器へ渡す。
4. `OpaqueSort` を減らし、frozen 3,574問で kernel-ready と exact の両方を測る。
5. 新しい問題型名や benchmark ID を追加した変更は不合格にする。

監査出力: `worker/artifacts/standard-model-audit-3574-20260810.json`
