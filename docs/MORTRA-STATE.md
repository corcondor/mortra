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
- frozen holdout A5を、問題本文を検査せず522問全件で実行した。
  同じdigest `e9fc9963d8d8ee12` で、1問の制限時間だけを変えて2回測った。

  ```
  制限時間 12s   certified 112/522 = 21.5%   timeout 59
  制限時間 60s   certified 138/522 = 26.4%   timeout  7
  ```

  差の26問は計算の中身ではなく制限時間である。12秒には Python 起動と
  sympy の import が含まれ、4並列だとさらに削られる。timeoutは
  「解けなかった」ではなく「測っていない」ので、分母に入れると
  数学ではなくCPUの混雑を測ることになる。**採用する値は 60s 側の
  `138/522 = 26.4%`**。誤答1、numerically_supported 9、abstained 351、
  solver_failure 14、parse_failure 2。abstained内訳は
  `not_reduced 142 / goal_not_meaningful 106 / unsupported_backend 86 /
  goal_is_relation 17`。
  同条件のdev A5は `46/167 = 27.5%`、誤答0、timeout 1。
  holdoutがdevを下回らない（26.4% vs 27.5%）ので、devへの過適合は無い。
  これは「MORTRAが選択した目標に対する内部証明書」であり、
  公式解答との外部一致ではない。
- `scripts/run_holdout.py` は制限時間・並列数・無効backendを実行時に出力し、
  timeoutが2%を超えたらその場で警告する。設定を書かずに記録された率は
  比較に使えない。
- semantic geometry feedback loop v1を8ケースで実行した。厳密座標を与えた正例6件は
  baseline `0/6`からvisual candidate + exact verifierで`6/6`へ改善。期待した中間命題の
  recall `6/6`、候補の厳密検証後precision `92.6%`、証明を開く候補8件から6件を選択し、
  selected seed precision `100%`。constructed witnessと近似関係の負例2件はfalse acceptance `0`。
  これは座標が数学的入力として厳密に与えられた限定実験であり、一般幾何証明率ではない。
- executable finite-state diagram実験を、commit `1926596`を基線、dataset digest
  `3f5f5dd2dedef69a`、1並列、直接反復上限10,000、到達状態上限200,000で18ケース実行した。
  parserを固定したA/Bで、baselineは`3/18 = 16.7%`、有限状態遷移図は
  `18/18 = 100%`を内部認証し、両者とも誤答0。15件を新たに閉じた。
  cycle候補precision `18/18`、改ざん辺false acceptance `0/5`、法の倍数を加える
  metamorphic test `8/8`、操作数はbaseline `150,147`、diagram `707`。
  これは型付き剰余漸化式に限定した機構実験であり、自然言語parseや一般数学ベンチの改善ではない。
  同じ認証済み状態を`/research/diagram`へcompileし、意味輸送と表示layoutを分離した。
- GitHub Actions: MathOS全8 test shard + aggregate (`31624676721`) 成功。
  自律研究 (`31624693493`) は13 tests成功後、型付き候補を1件追加して研究キューを
  `116`構造へ更新。cleanup後のMORTRA Worker (`31637500154`) も、外部runtime
  再混入検査、82 tests、TypeScript buildを含め成功。旧MORTRA Worker runの
  外部runtime結果は現行architectureの根拠にしない。
- semantic geometry feedback loopのCI (`31642888799`) は、worker 82 tests、visual loop 6 tests、
  実験artifact完全一致、外部backend不変条件、Worker buildをLinux上で完走した。

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

### Current four-axis status

- **Reasoning / REPRODUCED:** dev `46/167 = 27.5%`、frozen holdout内部認証
  `138/522 = 26.4%`（1問60s・4並列、digest `e9fc9963d8d8ee12`、誤答1）。
  visual feedback限定実験は正例`0/6 -> 6/6`、負例誤受理`0/2`。
  finite-state diagram限定実験は`3/18 -> 18/18`、誤答0、改ざん誤受理`0/5`。
- **Discovery / PROTOTYPE:** semantic geometryから関係候補を観測し、厳密有理座標の
  多項式恒等式、証明寄与アブレーションを通した候補だけReasonerへ戻せる。
  witness図からの一般定理発見、円・接線・補助構成の探索は未実装。
- **Generation / PROTOTYPE:** 型付き自律合成と親条件付き探索は存在する。今回の
  visual candidateを定理化し、条件tracebackから作問へ戻す経路は未接続。
- **Experience / PROTOTYPE:** proof DAGから図・式・説明を同一Beatとして再生でき、
  今回のvisual certificateもBeatへ記録される。一般scrubber、分岐、理解度実験は未実装。
- **Business / VISION:** advanced learning、作問、interactive textbook、research visualization
  は仮説。利用、理解、継続、支払意思の実測はまだない。

### Current top 3 experiments

1. visual feedbackを厳密座標から、記号的な構成証明書、円・接線・共円、補助点へ拡張し、
   未見幾何でbaselineとのproof-rate差を測る。witness図は引き続き証明へ昇格させない。
2. `not_reduced` 43件を小問scope・goal operator・束縛変数・型付き制約の共通loweringで
   閉じ、ReasoningだけでなくGeneration/Visualが共有できるsemantic stateを増やす。
3. visual candidateから条件traceback→問題→独立解法へ一本通し、作問validity、条件必要性、
   solution depth、人間選好を測る。同時にProof Scene scrubberで理解度比較を準備する。

### Claims not ready for publication

- 東大・京大数学が解ける、AlphaGeometry2相当、一般proofから3D/robot trajectoryまで
  自動compileできる、という主張。現行の中核推論・作問経路は外部LLMを使用しないが、
  その事実だけで一般数学性能を主張してはならない。

---

## 1. North Star

### VISION

MORTRA は解答器ではない。**一つの数学的構造を、意味を失わずに別の姿へ移し、
各表現から得た候補を検証して数学状態へ戻す装置**である。目的関数はcertified solve rate
単独ではなく、Reasoning・Discovery・Generation・Mathematical Experienceを同一semantic
state上で相互強化し、その統合能力をproductへ接続すること。

```
                         Reasoning
                             ↕
                  Semantic Mathematical State
                    ↙          ↓          ↘
              Discovery   Generation   Experience
                    ↘          ↑          ↙
                         Verification
                             ↓
                          Reasoning
```

公開時の一文は `One structure. Many representations.`

**UX の中心原理**：文章・式・図・3D・運動は別々の出力ではない。
**同じ証明状態の、同期した眺め**である。図は説明の挿絵ではない。
Visual/Geometry/Designはpresentation layerではなく、候補命題生成、数学的発見、作問、
人間理解、product experienceの一部である。ただし候補はcertificateなしにReasonerへ入れない。

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
