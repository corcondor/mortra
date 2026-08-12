# AlphaGeometryから参照したものと、参照していないもの

## Status

AlphaGeometryおよびAlphaGeometry2は、MORTRAの依存関係・runtime・proof backendではない。

## 参考にした設計上の考え方

- 小さい構築語彙から複雑な図形関係を表すこと
- 記号推論と補助構成探索を分離すること
- 候補生成と厳密検証を分離すること
- 問題別の答え暗記ではなく、再利用可能な規則を評価すること

これらは論文・公開設計から得た一般的な着想であり、MORTRAでは独自の型、IR、推論器、検証器として実装する。

## 使用していないもの

- AlphaGeometry / AlphaGeometry2のコード
- DDAR engine
- 公式repositoryのcheckout
- 公式test suiteをMORTRAの性能値として扱うこと
- AlphaGeometry互換または同等性能という主張

将来、外部backendとの比較実験を行う場合でも、隔離されたbenchmark adapterとして設計し、MORTRAのcore architectureやproduction runtimeとは明確に分離する。
