# MORTRA 現在地

最終更新 2026-08-13。この文書が唯一の正本。Codex の作業のあと、必ずここを直す。
書いてよいのは実行して得た数字だけ。見込みは書かない。

---

## 0. 2026-08-13 引き継ぎ監査スナップショット

### Source snapshot

- `sakumon-station` 監査開始時local HEAD: `57ae962`、remote: `a630fae`。
  本文談話IR、proof backend、判定集計修正とsplit監査を統合した実装基線は `7c91e32`。
- `mathos` 監査開始時HEAD: `92d7eb6`。CI依存契約修正 `3b06841`を経て、
  自律研究commitを含む現在のHEADは `476fcb0`。frozen 3,574問artifactは
  `artifacts/public_benchmark_3574_typed_cas_lowering_v3_20260811.json`。
- Obsidianはmirror。正本はこのファイルであり、Obsidianの古い数値を優先しない。

### Current runtime boundary

- **DeepSeek:** 現在のMORTRAでは使用しない。runtime依存、必須環境変数、生成route、
  worker経路はすべて除去した。
- **AlphaGeometry / AlphaGeometry2:** finite vocabulary、symbolic deduction、補助構成、
  tracebackを考えるための研究・設計上の参考に限る。公式runtime、DDAR、adapter、
  executor、CI checkout、`MATHOS_AG2_DIR`への依存はMORTRA coreに存在しない。
- **MORTRA reasoning:** MORTRA独自のtyped IR、semantic kernel、CAS/proof/inequality/
  geometry backends、certificate・verification infrastructureで実装する。

### REPRODUCED

- regression `19/19`、generalization `20/20`、discourse `42/42`、proof backend
  `19/19`、kernel integration `17/17`、identity `12/12`、lattice `93/93`、
  ornament mutation `71/71`、control character `237 files / 0`。
- Worker: 外部数学AIなしで `82/82 pass / 0 skip / 0 fail`。worker production build成功。
- MathML/discourse位置保存 `11/11`。Web production build成功（40 routes）。
- frozen split: dev `167`、holdout `522`はmanifest digest一致。後から追加された
  holdout-source `52`件は未割当であり、固定holdoutへ混ぜない。

### OBSERVED

- dev A5を167問全件再実行。`proved 37`、`verified_instance 3`、
  `numerically_supported 8`。certifiedは `40/167 = 24.0%`、certified wrong `0`。
- 同一コード・同一12秒上限・同一4並列で、旧flat MathML alignmentは
  `33/167 = 19.8%`。位置保存後は `40/167 = 24.0%`で、`+7問 / +4.2pt`。
  `goal_not_meaningful`は `29 -> 21`、timeoutは `20 -> 18`。
- dev 167問中136問で、従来は本文placeholder数と解析後expression数が不一致だった。
  2,817数式枠中511枠が未解析時に削除され、後続参照がずれていた。現在は未解析枠を
  `None`として保持し、談話照合用slotsとCAS用expressionsを分離する。
- このcorpusは解答本文を収録せず解答URLだけを持つ。ここでの`certified_correct`は
  「MORTRAが選択した目標に対する内部証明書」を意味し、公式解答との外部一致ではない。
  目標同定の誤りを測るには解答本文付き評価集合が別途必要。
- frozen holdout A5を、問題本文を検査せず522問全件で一度だけ実行した。
  `certified 112/522 = 21.5%`、`certified_wrong 1`、`numerically_supported 5`、
  `abstained 332`、`solver_failure 11`、`parse_failure 2`、`timeout 59`。
  abstained内訳は `not_reduced 135 / goal_not_meaningful 102 /
  unsupported_backend 79 / goal_is_relation 16`。実行前後のsource digestは
  `e9fc9963d8d8ee12`で一致した。上記の測定上の制約により、21.5%を公式正答率とは呼ばない。
- GitHub Actions: MathOS全8 test shard + aggregate (`31624676721`) 成功。
  自律研究 (`31624693493`) は13 tests成功後、型付き候補を1件追加して研究キューを
  `116`構造へ更新。旧MORTRA Worker runの外部runtime結果は現行architectureの根拠にしない。

### REPORTED_NOT_REPRODUCED / STALE

- `data/holdout-results.json` の旧A5 `139 correct / 11 wrong / 354 abstain` は、
  判定bucket修正前のartifactであり公開値にしない。
- 2026-08-11節の幾何 `7/7` は当時の限定corpusでは有効だが、一般入試性能ではない。
- GitHub `Resume MathOS Research` の成功runはテスト後に `No autonomous research job is due`
  で終了しており、研究が進行した証拠ではない。

### Current failure distribution (dev 167)

`certified 40 / numerically_supported 8 / abstained 97 / solver_error 4 / timeout 18`。
abstainedの内訳は `not_reduced 43 / unsupported_backend 31 /
goal_not_meaningful 21 / goal_is_relation 2`。not_reducedは `cas 36 / proof 5 /
inequality 2`。unsupportedは `probability 13 / solution_set 8 /
geometry_region 7 / optimization 2 / counting 1`。

### Current top 3 experiments

1. `not_reduced` 43件を小問scope・goal operator・束縛変数・型付き制約の共通loweringで
   閉じる。特にCAS 36件を、問題IDや表層文型なしで分類する。
2. 511個の未解析MathML slotのうち、括弧depth、vector/angle、集合・数列groupingを
   typed objectへelaborateし、位置保存を維持したまま実行可能式を増やす。
3. probability / geometry region / solution set / optimization / countingを、既存の
   `ProblemIR -> backend contract`へ個別solverではなく型付き観測として接続する。

### Claims not ready for publication

- 東大・京大数学が解ける、AlphaGeometry2相当、一般proofから3D/robot trajectoryまで
  自動compileできる、という主張。現行の中核推論・作問経路は外部LLMを使用しないが、
  その事実だけで一般数学性能を主張してはならない。

---

## 1. North Star

MORTRA は解答器ではない。**一つの数学的構造を、意味を失わずに別の姿へ移す装置**である。

```
問題文 → 型付き構造 → 表現の選択 → 厳密な証明 or 計算
                                → 図 / 3D
                                → 人が読む説明
                                → 物理的な運動
```

公開時の一文は `One structure. Many representations.`

**UX の中心原理**：文章・式・図・3D・運動は別々の出力ではない。
**同じ証明状態の、同期した眺め**である。図は説明の挿絵ではない。

---

## 2. 実測で確かめたこと（2026-08-11）

すべてこの日に実行した。推定値は含まない。

### 幾何の自然文形式化

| | 前 | 後 |
|---|---|---|
| 入試の言い回し6問の形式化 | **0/6** | **5/6** |
| コーパス7問（合成2問を追加） | — | **7/7** |

原因は数学ではなく日本語だった。形式化器は主題形（`M は BC の中点`）しか
読めず、入試がほぼ必ず使う措定形（`BC の中点を M とする`）を一つも持っていなかった。
足したもの：

- 措定形「〜を X とする / とおく / と呼ぶ」と、列挙「〜を M、〜を N とする」
- 語で書かれた関係（`垂直` `平行` `等しい`）。記号 `⊥ ∥ =` しか読めなかった
- 従属節の切り出し（`…とするとき、` を前提側へ送る）。
  「。」だけで切ると結論の述語が3本になって落ちていた
- 中点の別名衝突の解消。重心の展開が `g_mid_bc` を新規に作り、
  問題文の `M` と同一点が二名になって数値作図が退化していた

### 証明

**7/7 証明済み**。うち2問は3手の合成。

```
中点連結と垂心   M は AB の中点 / N は AC の中点  ⇒ MN ∥ BC      midline
                AH ⊥ BC / A,D,H は同一直線上     ⇒ AD ⊥ BC      perp-along-line
                                                ∴ MN ⊥ AD      para-perp
```

規則が効いた問題数（1問専用なら暗記、複数なら語彙）：

```
midline           4問
perp-along-line   2問
perp-bisector     2問
para-perp         2問
```

**1問専用の規則はゼロ**。これが「解法暗記ではない」ことの、この規模での証拠。

### 図の読みやすさ

制約を満たす図は一つではない。最初に見つかった解を返していたので、
条件は満たすが人には読めない図（つぶれた三角形）が出ていた。

| | 前 | 後 |
|---|---|---|
| 三角形の最小角（最悪値） | **3.1°** | **24.8°** |
| 鋭角三角形 | — | **6/7** |
| 形式化率 | 7/7 | **7/7**（落ちていない） |

やったこと：残差に `sin(角) ≥ 0.42`（25°）を入れて潰れた図を実現不可能にし、
厳密解を最大24個集めてから最小角・点間距離・縦横比・鋭角性で選ぶ。
美しさを学習する前に、決定的に測れるものを測る。

### 動かない条件

- 円と接線（`外接円`, `接する`）は未対応。6問中これだけが形式化できなかった。
- 外部AlphaGeometry runtimeは実行対象に含めない。上の7/7はMORTRA独自の
  前向き推論器の限定corpus結果である。

---

## 3. 今日入った新しい部品

| ファイル | 役割 |
|---|---|
| `lib/proof-scene.ts` | 証明 DAG → Beat 列。**証明1段 = 図1段 = 文1段** |
| `app/proof/page.tsx` | Beat を再生。時間軸は手書きしていない |
| `app/api/frame/route.ts` | canvas → PNG をディスクへ。動画化の配管 |
| `scripts/formalize_corpus.py` | 日本語 → 述語 + 座標 → JSON |
| `scripts/prove-corpus.mts` | 証明の通過本数と、規則ごとの効き方を測る |
| `app/brand/page.tsx` | 印の候補（可換図式から作る） |

`/solve` は時間軸が手書きだった。`/proof` はそれを置き換える。

---

## 4. まだ本物でないもの

1. 円・接線・比・角度定数の語彙。幾何の言い回しの被覆はまだ狭い
2. 未見の入試問題での測定がない。形式化率／証明率／誤証明率を分けて測っていない
3. 別証明の提示。証明 DAG は持てているが、複数経路を保存して並べていない
4. 3D と運動が Proof Scene から出ていない（`/robot` は別系統のまま）
5. ラベル配置は重心から逃がすだけ。衝突を測っていない

---

## 5. 次にやること（この順）

1. **幾何語彙の拡張** — 円、接線、円周角、比、角度定数。
   1本足すごとに、それが何問に効いたかを測る（暗記かどうかの判定）
2. **未見入試ベンチマーク** — LLM OFF / 外部 API OFF を固定。
   形式化率・証明率・誤証明率・図の生成率を別々に出す
3. **Proof Scene を 3D と運動へ** — 同じ Beat から立体断面と6軸軌道を出す
4. **視覚評価器** — ラベル衝突、不要な交差、可読最小文字サイズを機械で数える
5. **公開** — 上が出てから。数字が出る前に優位は主張しない

---

## 6. 公開してよい主張 / まだ駄目な主張

**言ってよい**（実行して得た）
- 入試の言い回しから、LLM を使わずに図を構成し、証明を閉じ、その証明に同期した図を描ける
- 使った規則は4本で、どれも複数の問題に効いている
- 図の座標は問題の制約を満たしている（後付けの挿絵ではない）

**まだ言ってはいけない**
- 「東大数学が解ける」— 未見問題で測っていない
- 「AlphaGeometry より解ける」— エンジンが手元に無く、比較していない
- 「OpenAI / DeepMind より進んでいる」— 会社名で比べない。評価軸で比べる

競争の原則：**会社名ではなく評価軸で勝つ。**
狙うべき軸は `厳密な非LLM推論 + 意味に同期した図 + 人が読める説明` の同時達成。

---

## 7. 決めたことと、その理由

- **図を単独で描く機能は作らない。** 図が説明から切り離されていることが、
  これまでの不自然さの原因だった。図は必ず証明の段から出す
- **エージェントに LLM を使わない。** 数学 OS を作っている以上、
  その判断を外部モデルに投げると全体が意味を失う
- **記事は原理を書く。** 能力の点数表は来月には変わる。原理は変わらない
- **ロボットは主役にしない。** 数学構造が物理世界にまで出てきた、
  という最後の表現として置く
