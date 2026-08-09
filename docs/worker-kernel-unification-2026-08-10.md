# MathOS実行核の統一（2026-08-10）

> **訂正:** 「112射Atlas」は112個の型付き射契約を意味し、112個の実行器を意味しない。
> 型到達36.4%も正答率ではない。実行可能loweringと再測定値は
> `executable-lowering-and-benchmark-correction-2026-08-10.md` を正本とする。

## 結論

Web本番と公開ベンチの意味解析・射探索は、`worker/src/` の型付きWorker核を正本とする。
旧Python意味核は比較用の `legacy-python` として明示指定した場合だけ使用する。
Python側にはコーパス取得、固定分割、正答照合、厳密backendを残すが、独自の問題型判定で
Workerを迂回させない。

## 分裂していた原因

1. Obsidianは設計を共有していたが、実行コードを自動同期する仕組みではなかった。
2. Claude側で検証した整数・不等式・解析・数列・組合せ・確率の射が
   `probe-*.ts` に留まり、本体Atlasへ昇格していなかった。
3. Pythonの公開ベンチは旧 `LiftCertificate` 経路を直接呼び、本番Workerを通っていなかった。

## 統一後の経路

```text
問題文だけ
  -> mathematical-language（字句・構文・量化・定義）
  -> SemanticHypergraph（型付き対象・制約・問い）
  -> typed-term-enumerator（型で有限列挙）
  -> unified morphism atlas
  -> exact backend / verifier
  -> 正答照合（ベンチ側だけ）
```

問題ID、模範解答、解答文、コンテスト名はWorkerへ渡さない。族IDによる解法選択も行わない。

## 今回の修復

- Claudeのprobeで確認済みの射を `verified-domain-extensions.ts` へ集約した。
- 基本57射と検証済み55射を単一の112射Atlasとして公開した。
- probe内でだけ有効だった射は、親問題間を勝手に融合できないようにした。
- 演算子の単語だけで別親の対象を借りる「幽霊入力」を禁止した。
- 日本語・英語の問いを有限なquery kindへ落とし、Workerの目標型へ接続した。
- PythonベンチからWorkerを一括実行するbridgeを追加した。
- core/unifiedの同一問題A/B測定を可能にした。

## 観測値

MathNet development分割、先頭50行から該当44問、深さ6、最大1000状態:

| Atlas | 射 | 問い型を解決 | 型付き目標へ到達 |
|---|---:|---:|---:|
| core | 57 | 28/44 (63.6%) | 11/44 (25.0%) |
| unified | 112 | 28/44 (63.6%) | 16/44 (36.4%) |

統合射による到達増分は5問、+11.4ポイントだった。

この値は**正答率ではない**。型の上で目標へ到達しただけで、制約を実行し答えを照合していない。
したがって「16問解けた」とは報告しない。正答率はbackend実行と検証を接続した後に別測定する。

## 残る主要欠陥

1. 17言語コーパスに対し、問い認識は日本語・英語中心で、多言語16/44が未解決だった。
2. 組合せ配置、離散操作、一般多角形などは `OpaqueSort` に落ちる例が多い。
3. `Scalar` や `Proof` への型到達は、求める式そのものの導出をまだ保証しない。
4. exact backendへの実引数loweringと最終回答照合が次の測定対象である。

## 回帰確認

- Worker: 64 tests passed
- Worker TypeScript build: passed
- Python benchmark/core regression: 145 tests passed
