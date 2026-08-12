# 167問の位置づけ — 汚染の明示

## 結論

**167問（北大138＋東大29）は、もはや未見テストではない。**

以後の正式名称：

```
167-problem development / regression set
```

## なぜ汚染されたか

この集合を使って、次を行った。

- 誤答の中身を一件ずつ確認した（`log(r) = (1<α ∧ …)`、`α = a_1`、`e = 0<t<∞`）
- その確認を元に guard を設計した（`is_trivial` / `restates_premise` / `usable_goal`）
- 目標選択の規則を改善した（`⟦式⟧` の位置から目標を決める）
- 条件抽出の規則を足した（`⟦式⟧ を自然数とする`）
- failure taxonomy を作った

**失敗を見て規則を足した時点で、この集合での成績は汎化性能ではない。**

## この集合で行ってよいこと

```
退行検査
failure taxonomy
ablation（A0〜A4 の相対比較）
parser の改善
```

## 行ってはいけないこと

```
汎化性能の主張
「未見問題で X%」という言い方
holdout との混同
```

## 汚染されていない集合

`data/holdout-manifest.json` で固定した。

```
dev/regression   167 問   digest 7adf7bf62c6a1c0f   北大 138 / 東大 29
holdout          522 問   digest 358eeae73d231854   東北大 425 / 札幌医科 41 / 岩手県立 56
```

holdout は **source holdout**（大学単位）。固定時点で本文も解答も読んでいない。

## holdout の規則

```
holdout の本文・解答を実装前に読まない
holdout で失敗した問題を見て規則を足さない
足した場合、その問題は dev へ移し holdout から外す
結果は dev と holdout を分けて報告する
```

`python scripts/freeze_holdout.py --verify` で digest を検査できる。
中身が変わっていれば不一致になる。

## 報告のしかた

```
dev/regression 167問   → 退行の有無と ablation の相対差だけを言う
holdout 522問          → 汎化性能はこちらだけで言う
```

**二つを足した数字を出さない。**
