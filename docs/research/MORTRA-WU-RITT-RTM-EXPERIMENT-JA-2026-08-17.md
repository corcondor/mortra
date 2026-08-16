# MORTRA Wu--Ritt 零点分解・RTM 局所義務実験

記録日: 2026-08-17

## 1. 実験の意味

座標幾何を一括して多項式消去すると、`on_aline` や `cc_tangent` のような
高次の構成で中間式が数千から数万項へ膨張する。前段の MORTRA は
擬除算恒等式を保存できたが、近似的な三角化と正則成分だけの証明を
Wu--Ritt の完全な characteristic set や零点分解と区別できていなかった。

本実験の目的は、次の三点を同時に満たす最小の実行系を作ることである。

1. characteristic set の完成条件を論文どおり `RS = empty` で判定する。
2. `initial != 0` の正則成分と `initial = 0` の退化成分を有限枝へ分ける。
3. 各中間式が元のどの仮定に依存するかを RTM の支持集合として追跡し、
   局所エージェントへ分割できる箇所を定量化する。

LLM、問題番号分岐、既知解答、データセットの補助構成節は使用しない。

## 2. 仮説

- **H1: 忠実な完成条件**
  BasicSet と set pseudo-remainder を反復すれば、近似三角集合より厳しい
  characteristic set 証明書を構成できる。
- **H2: 弱基本集合**
  weak ascending set は standard ascending set より中間項膨張を抑え、
  同じ上限内で証明到達性を上げる。
- **H3: 係数体局所化**
  構造マッチングで独立と判定した変数を `QQ(u)` の係数体へ移せば、
  消去変数と係数膨張が減る。
- **H4: goal cone**
  目標から構成依存を逆向きにたどれば、不要な方程式を安全に除去できる。
- **H5: 零点分解**
  子系を `P union CS union {init(p)}` とすれば、三角ランクが低下し、
  条件付き証明を有限の全域証明へ昇格できる。
- **H6: RTM 局所性**
  RTM の Boolean 支持射影は、全仮定より小さい局所証明義務を抽出する。

## 3. 原理

### 3.1 Characteristic set

有限多項式集合 `PS` に対し、各ラウンドで

```text
BS := BasicSet(PS')
RS := { prem(p, BS) | p in PS' - BS, prem(p, BS) != 0 }
PS' := PS union RS union BS
```

を実行し、`RS` が空になったときだけ完成とする。各擬除算は

```text
I(B)^k P = Q B + R
```

の multiplier、quotient、remainder を保存し、残差0を再生する。

### 3.2 Standard と weak

standard basic set は、候補多項式全体が既存の ascending set に対して
reduced であることを要求する。weak basic set は主変数の増加を保ちつつ、
候補の initial が reduced であることだけを要求する。本実装は公開 Lean 実装の
制御構造を別実装として再構成した。

### 3.3 零点分解

検証済み characteristic set `CS` に対し、零点集合を

```text
V(P) = regular(CS) union union_p V(P union CS union {init(p)})
```

へ分解する。全退化枝が証明または空集合として閉じるまで、親を全域証明へ
昇格しない。因数分解は必須ではないため、既定では論文どおり `init(p)` 自体を
子条件とし、巨大式の既約因数分解を任意の精密化へ分離した。

### 3.4 RTM 支持射影

完全 RTM は各中間多項式を元仮定の多項式係数ベクトルとして保持する。
今回はその非零位置の上界だけを集合 `S(P)` として伝播した。

```text
I(B)^k P = Q B + R なら S(R) subseteq S(P) union S(B)
```

これは係数相殺を除去しないため最小支持ではなく、安全な過大近似である。

## 4. 方法

### 4.1 実装

- `worker/backend/wu_ritt_characteristic.py`
  - standard / weak basic set
  - characteristic set 完成ループ
  - 擬除算 micro-step 単位の厳密 timeout
  - 目標の条件付き剰余0証明
- `worker/backend/wu_ritt_zero_decomposition.py`
  - characteristic set を継承する退化枝
  - 三角ランク低下検査
  - 深さ・枝・項数上限時の棄却
- `worker/backend/wu_rtm_support.py`
  - exact trace からの Boolean RTM 支持伝播
  - 局所義務、支持密度、連結成分、目標支持の監査
- `scripts/verify_wu_ritt_artifacts.py`
  - 公開gzipの証明書内容ハッシュ、残差0、RTM参照、枝被覆の再監査

### 4.2 対象と統制

- 実問題: JGEX `2021_p3`
- 入力: setup clauses のみ。auxiliary clauses は除去。
- 入力規模: 15方程式、19変数。
- 語彙: `triangle`, `angle_bisector`, `on_aline`, `on_line`,
  `on_bline`, `circle`。
- standard / weak 比較: 180秒、最大20,000項、最大12ラウンド。
- 問題ID、目標値、既知補助点に基づく分岐は禁止。
- 実問題は固定4問中、前段で条件付き剰余0まで達した唯一の診断対象であり、
  frozen benchmark のスコアではない。

### 4.3 受理条件

1. 全擬除算恒等式の残差が0で、内容ハッシュを再計算できる。
2. characteristic set の入力再剰余がすべて0である。
3. 退化子は親の `P` と `CS` と対象 `init(p)` を継承する。
4. 未解決枝が一つでもあれば全域証明を宣言しない。
5. RTM 支持の参照がすべて元仮定まで解決する。

## 5. 結果

### 5.1 制御構造の合成テスト

characteristic set、零点分解、RTM支持、既存Wu stalkを含む局所テストは
すべて成功した。偽の非帰結は証明へ昇格せず、深さ・時間・項数上限は棄却になる。

### 5.2 standard / weak の公平比較

| 指標 | standard | weak |
|---|---:|---:|
| characteristic ラウンド | 5 | 4 |
| 擬除算段数 | 658 | 569 |
| 最大項数 | 22,884 | 9,774 |
| 証明計算時間 | 106.30秒 | 152.89秒 |
| 停止理由 | term budget | なし |
| characteristic set 検証 | 失敗 | 成功 |
| 目標剰余0 | 未到達 | 成功 |

weak は高速ではないが、最大項数を57.3%減らし、20,000項上限内で
検証済み characteristic set と条件付き目標証明へ到達した。

### 5.3 棄却された局所化

| 方式 | 結果 |
|---|---|
| 構造的係数体 `QQ(u)` | 外部240秒で timeout |
| backward goal cone | 15/15方程式、19/19変数が残り、削減0 |

この問題では全構成が目標へつながっており、単純な依存閉包では削れない。

### 5.4 零点分解

weak characteristic set の正則成分は証明された。重複と定数を除いた
`init(p)` から13退化枝を生成し、枝継承検査は成功した。しかし深さ0では
13枝が未解決なので、全域証明ではない。

最初の退化枝を実行すると、子の三角ランクは親より厳密に低下した。一方で
2ラウンド、159擬除算、最大23,813項となり term budget で停止した。
したがって有限降下の方向は観測できたが、全退化枝閉包は未達である。

### 5.5 RTM 支持

| 指標 | 結果 |
|---|---:|
| 元仮定 | 15 |
| 追跡した導出多項式 | 54 |
| 証明義務 | 69 |
| 全系より狭い義務 | 32 |
| 支持行列密度 | 0.7531 |
| 目標支持 | 15/15 |
| 仮定ハイパーグラフ連結成分 | 1 |
| 未解決参照 | 0 |
| 証明書再生失敗 | 0 |

最終目標の削減は最初に仮定14だけを参照し、第2段で仮定11を除く14本へ
拡大し、後段で15本すべてへ到達した。局所義務は存在するが、問題全体を
互いに独立な成分へ分割することはできなかった。

## 6. 考察

### 6.1 支持された仮説

- **H1**: 合成例と実問題で、完成条件・入力再剰余・証明書再生を実行できた。
- **H2**: 同じ180秒・20,000項条件で weak のみが目標へ到達した。
- **H5の一部**: 親 `CS` を継承した最初の退化子で三角ランクが低下した。
- **H6の弱い形**: 69義務中32義務に厳密な局所支持上界が得られた。

### 6.2 棄却または未支持の仮説

- **H3**: SymPy の有理関数係数演算はこの問題で高速化を生まなかった。
- **H4**: goal cone は連結した構成鎖を切れなかった。
- **H5の強い形**: 13退化枝を閉じる全域証明は得られていない。
- **H6の強い形**: 目標支持は15/15であり、独立成分分割は不可能だった。

### 6.3 科学的な解釈

本実験の前進はスコア上昇ではなく、失敗位置を次の三層へ分離したことである。

1. **集合選択**: weak basic set により正則成分の証明到達性は改善した。
2. **退化成分**: zero decomposition は正しい枝を作れるが、子で再び項膨張する。
3. **局所性**: 初期の義務は疎だが、目標直前で支持がほぼ全系へ合流する。

したがって次の課題は語彙追加や問題別補題ではない。RTM支持を消去後の説明に
使うだけでなく、消去前に局所 characteristic set を構成するスケジューラへ
変換し、重なり部分だけを stalk 間で交換する必要がある。

## 7. 結論

公開 Lean 実装に対応する standard / weak basic set、characteristic set 完成、
Wu--Ritt 零点分解の枝継承を、MORTRA の証明書付きPython核へ接続した。
`2021_p3` の正則成分では weak basic set が条件付き証明へ到達したが、
13退化枝は閉じておらず、定理全体を証明したとは言えない。

次の反証可能な実験は次のとおりである。

1. RTMの直接支持が急拡大する境界を separator として抽出する。
2. separator の両側で characteristic set を独立計算する。
3. 共有式だけを局所 stalk 証明書として交換する。
4. 一括 weak Wu と、局所RTMスケジューラを同じ時間・項数予算で比較する。
5. `on_aline` と `cc_tangent` を含む未見集合で、証明率、最大項数、誤受理0、
   全域枝閉包率を測る。

受理条件は、一括方式より最大項数または証明時間が下がり、未見問題の証明数が
増え、全証明書が再生でき、未解決枝を証明へ昇格しないことである。

## 8. 一次資料

- [Formalizing Wu--Ritt Method in Lean 4](https://arxiv.org/abs/2604.14912)
- [WuProver/lean_characteristic_set](https://github.com/WuProver/lean_characteristic_set)
- [A Structured Reconstruction of Identity Proofs in Wu's Method](https://www.mdpi.com/2227-7390/14/13/2442)
- [A New Algorithmic Scheme for Computing Characteristic Sets](https://arxiv.org/abs/1108.1486)
- [On the Connection Between Ritt Characteristic Sets and Buchberger--Groebner Bases](https://arxiv.org/abs/1506.08994)
- [Wu's Method Can Boost Symbolic AI](https://arxiv.org/abs/2404.06405)

## 9. 再現物

- `data/wu-ritt-standard-strict180-2021-p3-2026-08-17.json.gz`
- `data/wu-ritt-weak-strict180-2021-p3-2026-08-17.json.gz`
- `data/wu-ritt-parameter-field-2021-p3-2026-08-17.json`
- `data/wu-ritt-goal-cone-2021-p3-2026-08-17.json.gz`
- `data/wu-ritt-weak-zero-decomposition-2021-p3-one-child-2026-08-17.json`
- `data/wu-rtm-support-2021-p3-2026-08-17.json`
- `scripts/experiment_wu_ritt_parameter_field.py`
- `scripts/experiment_wu_ritt_characteristic_decomposition.py`
- `scripts/audit_wu_rtm_support_artifact.py`
- `scripts/verify_wu_ritt_artifacts.py`

注意: 本結果は Lean kernel による定理証明ではない。Lean 論文の制御構造を
再構成し、Python 上で疎多項式恒等式と枝継承を独立再生した段階である。
