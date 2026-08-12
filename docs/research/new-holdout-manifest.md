# 新 holdout の固定

`data/holdout-manifest.json` / `scripts/freeze_holdout.py`

## 固定した内容

```
dev/regression   167 問   digest 7adf7bf62c6a1c0f
                 北海道大学 138 / 東京大学 29

holdout          522 問   digest 358eeae73d231854
                 東北大学 425 / 札幌医科大学 41 / 岩手県立大学 56
```

## 種類

**source holdout**（大学単位）。dev に使った大学を丸ごと除く。

固定した時点で、holdout の**本文も解答も読んでいない**。
大学名と問題数だけを見て manifest を作った。

## 検証

```
python scripts/freeze_holdout.py --verify
```

id の集合を sha256 で封じている。中身が変われば不一致になる。

## 規則

```
holdout の本文・解答を実装前に読まない
holdout で失敗した問題を見て規則を足さない
足した場合、その問題は dev へ移し holdout から外す
結果は dev と holdout を分けて報告する
```

## まだ無いもの

```
temporal holdout    収集日時を問題に持たせていない。次に足す
structural holdout  構造 signature での分割。goal operator と
                    constraint skeleton で割れるようになったので次に足せる
human gold set      100問の人手確認。未着手
```

structural holdout は Discourse IR ができたので実装可能になった。
`(goal_operator, domain種別, interval有無, 対象sort)` を signature にして割る。
