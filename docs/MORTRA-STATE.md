# MORTRA 現在地

最終更新: 2026-08-13

この文書は、所有者が確認した境界と現在の実装優先順位を記録する。コードや過去のAI生成文書に矛盾がある場合、まずこの境界を守り、その後に現在commitでテストを再実行する。

## 1. Owner-confirmed facts

- DeepSeekは使用しない。契約・課金・API key・成功したAPI呼び出しを、現在のMORTRAの前提にしてはならない。
- AlphaGeometry / AlphaGeometry2はruntime、solver、proof backendとして使用しない。論文と設計思想を参考にしただけである。
- MORTRAの主要経路は、独自のDiscourse IR / Problem IR / Semantic Kernel / CAS / proof backend / geometry reasoningで構成する。
- ファイル、test、CI設定が存在するだけでは、production usageやowner approvalの証拠にならない。
- AIが追加した実験コードや説明文は、所有者の承認なしにcanonical architectureへ昇格させない。

## 2. North Star

MORTRAは、一つの数学的構造を意味を保ったまま複数表現へ移す。

```text
問題文
  -> 型付き意味構造
  -> 適切な表現とbackendの選択
  -> 証明・計算・反例探索
  -> certificate
  -> 式・図・説明・時間軸
```

公開上の短い表現は `One structure. Many representations.`

## 3. 現在の最優先目標

新しい外部統合や大規模なデザイン作業ではなく、次を反復する。

```text
実装
-> regression / negative control
-> development benchmark
-> false-positive audit
-> 改善が一般規則によるか確認
-> fixed holdoutを節目で一度だけ測定
```

評価の中心は以下。

- certified solve rate
- wrong / false-proof count
- abstention reason
- formalization rate
- execution lowering rate
- held-out generalization

## 4. 次の技術課題

1. `not_reduced`を、問題IDや大学名ではなくgoal operator・束縛変数・型付き制約の共通loweringで減らす。
2. probability、geometry region、solution set、optimization、countingを既存の`Problem IR -> backend contract`へ接続する。
3. `proved`、`verified_instance`、`numerically_supported`、`unsupported`を混同しない。
4. 一つの修正が複数問題へ効いたかを測り、一問専用規則を拒否する。
5. Proof Scene / Visual IRは、推論スコアと証明同期性を壊さない範囲で進める。

## 5. 明示的に対象外

所有者の追加承認がない限り、次を再導入しない。

- DeepSeek API経路
- AlphaGeometry / AlphaGeometry2 / DDAR integration
- 外部モデルの自己申告を正解判定にする経路
- benchmarkを見ながらtest setへ問題別patchを追加すること
- 実装・テスト・スコア改善と無関係な監査作業の長期化

## 6. 記録規則

数値を書く場合は、必ずcommit SHA、artifact、実行コマンドを添える。再実行していない値は`OBSERVED_FROM_ARTIFACT`または`REPORTED_NOT_REPRODUCED`と記載し、`REPRODUCED`と呼ばない。
