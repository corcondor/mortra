# ベンチマーク手順（MORTRA）

## 分割（§9）

**5,369問（8大学の .tex アーカイブ）** — 既に開発判断に使ったので **development / regression set** として扱う。ここでの数字を能力の主張に使わない。

**mathexamtest.jp 収集分（51大学・3,530問、解答リンクつき）** — 見る前に分割を固定する。

| 分割 | 定義 |
|---|---|
| Development | 実装時に見てよい |
| Structural Holdout | 制約・証明・射の構造で分ける。ランダム分割では不十分 |
| Source Holdout | 大学単位で分ける |
| Temporal Holdout | 指定日時以降に追加された問題 |
| Gold Set | 100〜300問。人間が監査する |

## 指標

```
formalization_rate            問題文を型付き述語と座標に落とせた割合
goal_reachability             型の上で結論に至る経路がある割合
execution_lowering_rate       実際に計算へ下りた割合
certified_solve_rate          独立な検証を通った答えが出た割合
precision_when_attempted      答えを出したもののうち正しかった割合
coverage                      棄権しなかった割合
abstention_rate               棄権した割合
correct_rejection_rate        偽の主張を正しく拒否した割合
false_proof_rate              偽を証明したと言った割合（0 でなければならない）
metamorphic_consistency       意味保存変換での一致率
counterfactual_sensitivity    意味変更での変化率
structural_holdout_score
source_holdout_score
temporal_holdout_score
proof_diagram_sync_rate       証明の段と図の段が対応した割合
cross_representation_consistency  表現をまたいで同じ意味を追えた割合
```

## 判定の言葉（§8）

「具体例で数値が合った」と「一般式として証明した」を同じ言葉で呼ばない。

```
proved                 記号的に導出し、恒等式として確かめた
verified_instance      具体値を入れた場合に一致した。一般には未証明
numerically_supported  数値では合うが記号的な確認が無い
unverified             答えは出たが独立な確認が取れていない
rejected               確認して、合わないと分かった
```

実装は `worker/backend/cas_solver.py` の `classify()` と `symbolic_identity()`。

## 検証の手段（§6.6）

LLM の自己申告を正答判定に使わない。使うのは次。

```
CAS の結果        → 元の式へ厳密に代入
多項式            → 記号的な恒等式の確認 / グレブナー基底での剰余
幾何              → 前向き推論 + 座標での数値検証
不等式            → 符号・区間・境界の確認
積分              → 微分と境界での確認
格子              → 性質テスト（基底変換で不変、群として閉じる、等）
証明              → 依存関係と証明書
```

## 棄権（§6.7）

次を区別する。混ぜると数字が嘘になる。

```
unsupported     扱える範囲の外
ambiguous       問題文が一意でない
unformalized    形式化できていない
unverifiable    答えは出たが確かめる手段が無い
```

**照合不能を分母から外さない。** 外した瞬間に率は意味を失う。
