# Vision → Reasoning の還流

## 現状：一方向しかできていない

```
Reasoning → Vision    実装済み（proof-scene.ts が証明の段から図の段を作る）
Vision → Reasoning    NOT_IMPLEMENTED
```

Vision で見つけた候補を証明探索へ返す経路は**まだ無い**。

## ただし design が kernel の欠陥を出した実例がある

意匠生成は次を要求するので、reasoning kernel の検査になった。

```
closure / orbit completeness / boundary consistency
quotient correctness / fundamental domain / symmetry validation
```

**実際に出た欠陥**

1. 生成元を手で 8 個並べて「位数 8」と書いたら、群として閉じていなかった。
   p4m と p6m が対称性検証に落ちて発覚。閉包を計算する形に直した
2. 壁紙群を有限群として扱っていた。G は無限で、数えていたのは点群 G/T だった
3. 検証が点群しか見ておらず、並進の周期性を確かめていなかった

**Vision/design が reasoning kernel のテストになる**という仮説は、この 3 件で支持された。

## 次に作るもの（A6）

```
Visual Observation → Candidate Proposition → Perturbation Test
→ Counterexample Search → Formal Proposition → Proof Search
```

状態は分ける。

```
observed / stable_under_perturbation / conjectured / proved / disproved
```

`KnowledgeStatus` に `stable_under_perturbation` と `conjectured` は既に入れてある。
使う側がまだ無い。
