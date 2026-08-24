# MORTRA 表現・初見探索・複数agent接続監査 2026-08-20

## 問い

1. 初見問題を、既知の型付き構造と射の未見合成として探索できるか。
2. 分野別表現が、agentに依存しない共通数学表現へ昇華されているか。
3. 異なる形式言語を持つ複数agentが、証明義務と証明書を交換できるか。
4. その協調経路が公開の任意問題入力まで接続されているか。

## コード監査結果

| 層 | 現在の実装 | 判定 |
|---|---|---|
| 理論Atlas | `TheoryNode`, `MorphismSchema`, `LiftCertificate` が存在する | 部品あり |
| 共通意味表現 | `TypedSemanticGraph = objects + morphisms + constraints + query` が存在する | 記述層として存在 |
| 初見の射探索 | TypeScript側の `generalization-kernel.ts` が型付きAtlas上の経路を探索する | 既知射の未見合成に限定して存在 |
| agent共通境界 | 幾何研究系に `SymbolicAgentAdapter`, `LocalCertificate`, `ExactSheafCoordinator` が存在する | 幾何・多項式系で成立 |
| 厳密協調 | typed logic circuit, Wu, Groebner, Newclid/GCLC系adapterが証明書をreplayする | 研究経路で成立 |
| 公開解答経路 | `run_reasoning_pipeline` は単一 `MathIR` を選び、toolを実行してから意味グラフを作る | 共通agent協調へ未接続 |
| 定理executor | `structural_theorem_query` が大きな問題構造を表層条件から選ぶ | 一部が粗粒度で、共通射へ未分解 |

## 結論

MORTRAは必要な部品を持つが、全体として一本化されていない。特に次の三表現が分かれている。

1. Python解答系の `TypedSemanticGraph` / `MathIR`
2. Python幾何研究系の `Atom` / `TypedVocabulary` / `LocalCertificate`
3. TypeScript作問系の `SemanticHypergraph` / `TypedProofObligation`

したがって現状は、既知のparserまたは粗粒度executorにliftできた初見問題は解けるが、任意の初見問題を
複数agentが共通表現上で分担して解く構造には未到達である。幾何研究で成立した協調は、公開APIと
他分野へまだ一般接続されていない。

## 必要な共通核

共通交換形式を次で固定する。

```text
TypedProblem
  sorts
  terms
  predicates
  constraints
  goal
  morphisms
  open_obligations

ProofCertificate
  agent_id
  consumed_obligations
  produced_facts
  native_payload
  replay_contract
```

各agentは次の同じ契約を実装する。

```text
lower(TypedProblem) -> NativeProblem | NotApplicable
propose(NativeProblem, OpenObligations) -> CandidateCertificates
lift(NativeCertificate) -> ProofCertificate
replay(ProofCertificate) -> verified | rejected
```

## 実装受理条件

1. 公開APIが意味グラフをtool実行後ではなく、agent探索前に構成する。
2. theorem/CAS/Newclid/GCLC/Wu/Groebnerの全経路が同じgoal identifierを受け取る。
3. agent固有の結果は共通証明書へliftされ、別agentが生成した事実を型検査後に利用できる。
4. 粗粒度の定理executorは共通の型・述語・射・補題へ段階的に分解する。
5. Atlasを凍結したheld-outで、単体agent、単純union、証明義務交換ありの三条件を比較する。
6. 初見問題で既知射の未見合成が成功し、問題ID・全文・期待解を参照しないことをtraceで示す。

この接続が完了するまで、新しいexecutor数だけを増やしてもMORTRA全体の合成汎化とは数えない。
