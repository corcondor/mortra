# MORTRA HAGeo 型付き適応Portfolio実験

## 原理

目的は、HAGeo型の補助構成探索を単なる探索量の増加から、次の5段へ分解することである。

1. 候補構成familyの被覆を測る。
2. 型付き関係、数値incidence、証明DAGを独立した順位器として保持する。
3. 証明残差に応じて候補検証幅、深さN、独立試行Kを有限に増やす。
4. Newclid/Yuclid/GCLC-Wu系の局所表現を、真偽判定と分離して協調させる。
5. 候補評価と協調計算を高速化し、厳密証明へ使える予算を増やす。

真偽はYuclid native証明書の再生だけで決める。順位器は問題ID、期待解、datasetの
補助構成、外部LLMを参照しない。したがって、成功は有限の型付き射と証明義務の合成、
失敗は候補被覆・順位・深さ・証明規則のいずれかとして観測できる。

## 実装方法

### 1. 候補被覆

証明済みdev経路の各射について、grammarへの符号化、有限予算内の列挙、実構築の3段を
別々に監査した。数値incidenceは提案専用とし、typed policyではhard gateにしない。

### 2. 型付き順位回路

次の順位を別々に保存した。

- typed construction grammar
- Newclid relation obligation
- GCLC/Wu polynomial channel
- HAGeo numerical incidence
- 双方向Newclid proof DAG
- typed relation + incidence proposal

ADMM合意は既存4エージェントの能力を保つ。新しいproof-DAG専門家は合意値を上書きせず、
各構成familyの最良候補を確保するportfolioとして合流する。これにより専門家追加による
catastrophic forgettingを防ぐ。

### 3. 適応予算

`SearchStage` を `(depth, attempts, feedback_candidates)` に拡張した。候補検証幅を
16から48へ増やし、その後に型付き証明残差が改善すれば深さを増やす。停滞すれば独立軌道を
増やす。時間超過は正解ではなくright-censoredとして記録する。

### 4. 証明器協調

基準事実、目標、定理を文字列ではなく `Atom` としてPass@Kから双方向proof-DAGへ渡す。
各候補はYuclidへ実投入し、goal closure、代数残差、既知ランク、未解決義務の順で比較する。
候補の採択と数学的真偽を分離した。

### 5. 高速化

Sheaf-ADMMの共有channelを密行列全体ではなく独立blockとして解いた。proof-DAGの初期探索
予算を、旧成功実験と同じ1候補32状態へ戻した。候補評価は並列Yuclid workerで実行する。

## 結果

### 候補被覆

小規模dev 3経路4射では、各family 32候補で3/4、64候補で4/4を列挙できた。
これは必要条件の監査であり、4射だけなので汎化精度とは解釈しない。

### 能力保存回帰

`2011CTSTp16` では、既存成功射 `reflect(k,b,c)` が新順位器で334位まで落ちていた。
proof-DAGのfamily frontierを復元すると9位になり、Yuclid証明書を再取得した。

回帰3問はすべて再成功した。

| 問題 | 経路 | 時間 |
|---|---|---:|
| 2011CTSTp16 | `reflect(k,b,c)` | 46.27秒 |
| 2012G4 | `intersection_lt(d,a,o,b,c)` | 16.00秒 |
| 2017G3 | 2段構成 | 29.61秒 |

### 未見開発問題

`2020_p1` は各family 16候補では必要射が列挙されず失敗した。64候補・検証幅48では、
既知経路とは異なる次の2段経路で解けた。

```
intersection_ll(a,y,b,u)
reflect(p,o,d)
```

直接実行は45.00秒、Yuclid呼出し96回だった。適応実行は検証幅16で失敗後、48へ自動拡張し、
2段階91.26秒で同じ証明経路へ到達した。

### 固定3問

実装前に固定した `2015IranTSTp18`, `2024VietnamTSTp5`, `2023IMOp6` は0/3のままだった。

- 2015: 代数残差L1が6から4へ改善したが未証明。
- 2024: 既知ランクが64から65へ増えたが未証明。
- 2023: 残差は停滞した。
- 2015を深さ4へ増やしても未証明。L1=4、既知ランク83だった。

従って、今回の固定集合では正答率向上を確認できていない。

### 速度

- Sheaf consensus microbenchmark: 52.17秒から24.57秒、2.12倍。
- 2011回帰: proof-DAG予算修正前65.32秒から46.27秒、29.2%短縮。
- 2020直接実行45.00秒に対し、再計算を含む適応実行は91.26秒。

最後の差は、適応段階間で候補順位と最初の16検証を再利用していないためである。

## 考察

### 解法暗記か

問題名・既知射・期待解の分岐は追加していない。2020では過去の成功経路とは異なる構成を
発見したため、少なくともこの成功は経路文字列の再生ではない。一方、dev被覆監査は4射と
小さく、広い汎化の証拠にはならない。

### なぜ固定3問は解けなかったか

候補幅の増加で残差が改善した問題はあるが、goal closureは全て0だった。深さ4でも閉じない
ため、残る支配要因は単純なN/K不足だけではない。必要な中間補題または補助構成が候補familyに
ない、あるいはNewclid/Yuclid規則がその中間関係を閉じられない可能性が高い。

### 自己組織化の意味

今回成立したのは、局所エージェントの順位を保持しながら有限portfolioへ合流する構造である。
完全なend-to-end Sheaf-ADMM自己組織化ではない。ADMM合意へ専門家を無条件に加えると2020の
順位が落ちたため、「合意すれば常に良い」は反証された。局所能力保存を制約にする必要がある。

## 結論

1から5の実装経路は接続された。候補被覆、型付き順位、適応予算、証明器feedback、高速化は
同じPass@K実験器で動作し、旧能力3/3と開発問題の新経路をnative証明で確認した。

ただし固定3問は0/3で、認証済みHAGeoスコアの増加はまだない。次の本質的課題は、残差から
新しい中間補題・補助構成を合成し、各証明器へ返す閉ループである。同時に、適応段階間の候補・
証明キャッシュを実装し、91.26秒を直接実行45.00秒へ近づける必要がある。

## 再現成果物

- `worker/backend/native_formal_obligation_sheaf.py`
- `worker/backend/hageo_search_control.py`
- `worker/backend/adaptive_search_budget.py`
- `scripts/experiment_hageo_passk.py`
- `scripts/experiment_hageo_adaptive_passk.py`
- `data/hageo-typed-adaptive-portfolio-summary-2026-08-19.json`
