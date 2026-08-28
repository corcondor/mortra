# MORTRA-Codex同期研究: 未証明11問の厳密閉包

日付: 2026-08-28
対象: HAGeo凍結89問のうち、直前の監査済み能力unionで未証明だった11問
制約: MORTRA内部の外部LLM不使用、期待解答不使用、問題ID分岐不使用

## 目的

MORTRAが型付き停止義務を返し、同じCodexセッションが再利用可能な表現チャートを実装し、MORTRAが直ちに同一コホートで再実行する同期閉ループにより、残る11問を厳密に証明する。

個別問題の答えを登録するのではなく、次の証拠を各問に要求した。

1. JGEXの構成列と目標型による照合
2. 必要な場合だけ自然文から量化・枝を型付き意味へ変換
3. 厳密体上での恒等式または消去証明の再生
4. 問題文、証明、図、証明書のSHA-256連鎖
5. 既存78問に対する回帰、曖昧一致、重複、空虚証明の監査

## 仮説

残る11問は探索時間の不足だけで止まっているのではない。次の少数の構成チャートが欠けているため、既存の円・角・距離・根軸表現が最終目標へ戻れない。

- 接触弦・極・反射・二本の割線
- 内接円接点・外接円接線・等角
- 弧中点・角の二等分線・反射・二円
- ミケル点・三本の根軸・同軸円
- 傍心・接点・根心・内心軸
- 正三角形・角和・三円束
- オイラー線・等角・根軸・垂線
- 三本のチェバ線・等角・根軸
- 九点円・方べき連鎖・中点
- 二円の第2交点・等冪・中点網
- 名前の付いていない二交点の存在量化と既知根を持つ円への帰還

これらを問題IDではなく、構成操作、依存順序、目標述語、自然意味原子で照合すれば、同じ構造を持つ入力へ再利用できると予測した。

## 原理

同期研究ループは次の順序を保持する。

```text
MORTRA: 型付き停止義務
  -> Codex: 共通構造の仮説と厳密チャート
  -> MORTRA: 同一11問で対照/介入再実行
  -> governor: 新規証明、回帰、曖昧性、証明書ハッシュで採否
  -> 次の停止義務
```

各チャートは、複雑な座標消去をそのまま探索する代わりに、問題の構成を既知根付き円交点、方べき、根軸、極、相似、等角イデアルなどの小さな射へ分解する。最終結論は数値サンプルではなく、厳密な残差がすべて0になることによって認証する。

## 実装方法

### 同期セッション

`mortra-codex-research-dialogue-v1` のJSONL標準入出力を用い、MORTRAとCodexを同じ実行状態で接続した。各周期は観測、仮説、対照/介入、採否からなり、全記録を直前レコードのSHA-256へ連結した。

旧台帳は、修正前の自然文ハッシュを持つ履歴として削除していない。量化修正後の再評価は別台帳へ保存した。

```text
data/mortra-codex-fused-live-2026-08-28.json
data/mortra-codex-fused-quantifier-corrected-2026-08-28.json
```

### 自然文の量化

`2021ARMOg10p8` の英語データは、二円の交点M,Nを最初から固定した表現になっていた。しかし原文の定理は、二つの交点を適切にM,Nと名付けられるという存在命題である。

自然意味パーサv5へ次を追加した。

```text
exists_circle_pair_labelling(M,N,
  circumcircle(P,Q,R),
  circumcircle(A1,X,Y))
```

厳密チャートはこの原子がない限り発火しない。自然文の `A'` は型付き識別子 `A1` へ正規化する。

### 証明依存ハッシュ

最初の標準監査は、自然文を使わないチャートにも自然文SHA-256が付いていることを拒否した。原因は、ポートフォリオ結果が「入力として渡された自然文」を無条件に証明依存へ含めていたことだった。

修正後は、選択されたチャートが実際に読んだ自然文だけをトップレベルの証明依存へ昇格する。

```text
selected chart uses natural statement -> selected natural SHA-256を保存
selected chart ignores natural statement -> null
no selected chart -> 診断用の入力SHA-256を保持
```

これは監査を迂回する変更ではない。証明が依存した入力と依存していない入力を正確に分離する変更である。

## 結果

### 11問の証明

| 問題 | 再利用可能チャート | 再生恒等式 | 証明書SHA-256 |
|---|---|---:|---|
| 2017USAMOp3 | `incenter-nine-point-power-chain-midpoint` | 49 | `122db1143ca7a9f7b9702e8f5168c4222186f2c23c2f081146801538d3236f03` |
| 2019IranTSTp15 | `midpoint-bisector-two-circles-equal-power` | 24 | `78187f5e265cb3497488be438ba6b49c827e32df432d5f6b1e4294f5370ee213` |
| 2020IranTSTp9 | `arc-midpoint-reflected-bisector-two-circle-cyclicity` | 34 | `35bb2e4e8a9c3a0ecaf8484c50f5493490f6db14a6c52ff677b32f5b9aeb747c` |
| 2021ARMOg10p8 | `reflected-chord-existential-circle-pair-return` | 38 | `918c9b77925d78d496751d63f42234e16c9b878a295bef6277bc776adeab16be` |
| 2021IranTSTp6 | `euler-line-equal-angle-radical-altitude` | 20 | `2eeab57e459bf781f37371e0ef040a7c69171de8de5528b75dd6b9e8ee4e108f` |
| 2021IsraelOlympicRev | `cevian-three-radical-axes-equal-angle` | 28 | `00303c2b0605153f0bbdfdcc35a13a81d5c1c48ab25c5f187d116c559cd0efe6` |
| 2023IMOp6 | `equilateral-angle-sum-three-circle-pencil` | 27 | `4dff71a9cb69c6791c85f1af476c92d4bb0660e2b8bfa782c3c3cd7e3d02e45c` |
| 2024VietnamTSTp5 | `incircle-contact-chord-circumtangent-isogonality` | 26 | `de3428739823e63c65aca9b509ea139cf37e2aa7775781d2c96192558a67579c` |
| ShuZhiMiGeo128 | `miquel-cevian-three-target-circles-coaxial` | 31 | `bbae333ed91ab522160f1d5cb890bd5b29ea603cb16b0fa337cb2c5a41ca1beb` |
| ShuZhiMiGeo309 | `excentral-contact-radical-centers-incenter-axis` | 43 | `3c880120f12cf0d46feb9f4f5b1d9e847ea224c1ea791136216d3461a090d3dd` |
| ShuZhiMiGeo489 | `contact-polar-reflection-two-secants-side-return` | 37 | `c0b41fb469db3c61f089c93fd35012a125e9ed535ff2cd4aba2a9d3cbec8e2df` |

合計357本の再生恒等式が0へ閉じた。各問について `.chart-portfolio.json`、`.proof.md`、`.proof-focus.svg`、`.artifact.json` を生成した。

### 統合監査

| 指標 | 結果 |
|---|---:|
| 直前の認証済み能力union | 78/89 |
| 提出した証明 | 11 |
| 既存集合との重複 | 0 |
| 新規認証 | 11 |
| 更新後の能力union | 89/89 |
| 未証明 | 0 |
| 回帰 | 0 |
| 曖昧一致 | 0 |
| 証明書ハッシュ不一致 | 0 |
| 量化修復だけによる正解 | 0 |

標準統合結果:

```text
data/hageo-certified-capability-union-fused11-closure-2026-08-28.json
data/hageo-nonvacuous-capability-union-fused11-closure-2026-08-28.json
```

非空虚監査では、凍結集合外0、単位イデアルによる空虚証明0、除外0で、89/89を維持した。

修正版同期セッション:

```text
cohort:
afd6b38077edbd7e7a17f60517d3bb11060d6e26cf1ecfae6dd25461de3e3c4d

observation fingerprint:
423794cf59f6d4bb4ef11573cbfa4ba553483eb4dbdc4554622a4ed6a1f9add8

ledger head:
d2c69a4da4de0c2e23e3327508cf41db48d90c68fa49c1f0e6e62db3387822ec
```

### テスト

```text
23 passed in 167.38s
83 passed in 363.23s
```

後者は11チャート、自然意味、共通ポートフォリオ、能力union、非空虚監査をまとめた統合回帰である。

## 考察

### なぜ最後の11問を解けたか

探索深度を一律に増やした結果ではない。各停止義務を読み、既存の角度・距離・円の表現がどこで切れているかを、構成順序を保った小さなチャートへ縮約したためである。

特に有効だった共通操作は次である。

- 既知根を持つ円直線・二円交点の第2根消去
- 三円の方程式差から得る根軸と根心
- 接触弦を極として読む双方向変換
- 等角条件を有向角の多項式イデアルへ落とす変換
- 弧中点やミケル点など、JGEXだけでは失われる枝を自然文から型へ戻す変換
- 中点、反射、相似をアフィン写像として合成する変換

### 解法暗記との境界

solverは問題ID、期待解答、凍結問題名を参照しない。照合は構成型、多重度、依存順序、目標型、必要な自然意味だけで行う。入力や目標を変えた負例は拒否する。

一方、これら11チャートは対象問題を調べた後に実装した。したがって、この89/89は現行MORTRAが89問を証明書付きで処理できる能力の測定であり、未見問題への汎化率そのものではない。汎化は別の凍結集合で測る必要がある。

### 監査が必要だった理由

最初の11/11表示をそのまま採用していれば、自然文を使わない証明へ不要なハッシュを付け、存在量化を失った問題を混ぜていた。標準監査がそれを拒否したため、データと共通証明依存モデルの両方を直せた。

成功だけでなく、この拒否と修正を保存することが同期研究ループの重要な性質である。自己改善器が自分の採点を緩めて得点を上げる経路を閉じ、同じ証明成果物を独立監査できる。

## 結論

MORTRAとCodexの同期閉ループで、直前に未証明だった11問をすべて再生可能な証明へ変換した。標準能力unionは78/89から89/89へ更新され、未証明、回帰、曖昧一致、ハッシュ不一致はいずれも0になった。

各問には問題文、証明過程、図、厳密証明書が残っている。単なる正解ラベルではない。量化監査で一度拒否された問題も、原文の存在命題を型付き意味として実装し直した後に再証明した。

## 次の実験

89問の閉包を終点にはしない。次は、今回得た11チャートを変更せずに別の未見幾何集合へ適用し、転移正答率と誤受理率を測る。その後、同じ最小表現原理を `漸化式 <-> 行列 <-> 特性多項式`、`付値 <-> 合同式 <-> 整除性`、`有限状態 <-> 遷移行列` へ拡張する。

## 再現

```text
python scripts/run_exact_geometry_chart_portfolio.py \
  --input-dir artifacts/fused11-inputs-20260828 \
  --natural-json data/hageo-409-natural-language-2026-08-26.json \
  --output-dir artifacts/exact-chart-fused11-closure-20260828

python -m pytest \
  scripts/test_build_hageo_certified_union.py \
  scripts/test_audit_hageo_nonvacuous_union.py \
  worker/backend/test_exact_geometry_chart_portfolio.py \
  worker/backend/test_geometry_natural_semantics.py \
  worker/backend/test_*chart.py -q
```

公式解答の量化確認には、2020-21年度ロシア数学オリンピック10年生第2日の解答を参照した。

- https://vos.olimpiada.ru/upload/files/Arhive_tasks/2020-21/final/math/sol-math-10-day2-final-20-21.pdf
