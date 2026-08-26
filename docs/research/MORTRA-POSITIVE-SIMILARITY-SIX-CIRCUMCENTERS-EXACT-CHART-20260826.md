# MORTRA 正相似六外心・共点の厳密チャート実験

## 目的

固定89問の未認証24問に、平面幾何だけでは閉じない中間能力が必要かを調べる。対象は `2023MOSTMockp2` とし、問題名・期待解答・標本座標に依存しない共通チャートで厳密証明を再生できるかを検証した。

問題の構造は次のとおりである。正相似な二つの三角形 `A1A3A5` と `A4A6A2` を取り、添字を6を法として、`Xi` を直線 `AiAi+2` と `Ai+1Ai-1` の交点、`Oi` を三角形 `AiXiAi+1` の外心とする。このとき `O1O4`、`O2O5`、`O3O6` の共点を示す。

## 仮説

目標自体は平面幾何だが、局所的な円周角・接線規則の反復だけでは、六つの外心を一度に拘束する全体構造を捉えにくい。正相似を線形変換、交点と共点を同次座標の外積と行列式へ移すことで、探索を増やさず一つの恒等式として閉じられると予想した。

## 原理

一つの正相似変換で

```text
A1=(0,0), A3=(1,0), A5=(u,v)
```

と正規化する。第二の三角形は、複素数の乗法に対応する実2次行列を用いて

```text
S(x,y)=(r+p*x-q*y, t+q*x+p*y)
A4=S(A1), A6=S(A3), A2=S(A5)
```

と表せる。点を同次座標で持ち、直線と交点を

```text
line(P,Q) = P cross Q
meet(PQ,RS) = (P cross Q) cross (R cross S)
```

で構成する。3点を通る円の係数 `(alpha,beta,gamma,delta)` は、各点の行

```text
(x^2+y^2, xz, yz, z^2)
```

から得る符号付き3次小行列式で求め、その外心を同次座標 `(-beta,-gamma,2*alpha)` として復元する。最後に三直線 `O1O4`、`O2O5`、`O3O6` の係数ベクトルを `L1,L2,L3` とすれば、目標は

```text
L1 dot (L2 cross L3) = 0
```

である。六つの自由パラメータを残したままこの式を厳密簡約し、恒等的に0となることを再生した。

## 実装方法

1. `triangle`、2本の `on_aline`、6個の線分交点、6個の `circumcenter`、最後の `coll` を依存関係として照合した。
2. 点名や問題IDを使わず、正相似な二三角形と六外心の役割を構造から復元した。
3. 正相似を一つの線形変換、交点を外積、外心を円係数の小行列式へ変換した。
4. 正相似6本、交点の所属12本、円から外心への一般橋1本、円係数3本、最終共点1本の計23恒等式を再生した。
5. JGEXに混在していた `x = on_line a b` と `x = on_line x a b` を同じ意味へ正規化した。複数出力の `a b c = triangle a b c` も同じ境界で処理した。
6. 同じ証明書から可読証明とSVGの構成図を生成し、入力・証明書・適用成果物のSHA-256を保存した。

## 対照実験

| 入力 | 結果 |
|---|---:|
| 点名をすべて変更した同型構成 | 証明成功 |
| 目標を無関係な垂直条件へ変更 | 不採用 |
| 正相似を定める角条件を1本削除 | 不採用 |
| 六交点のうち1本の担体直線を変更 | 不採用 |
| 当時の未認証24問を一括照合 | 対象1問だけ採用、他23問は不採用 |

問題名や答えを記憶した分岐ではなく、必要な型付き構成が揃ったときだけ発火する。

## 結果

```text
status                         proved
ambiguous                      false
undischarged conditions        0
replayed identities            23/23
concurrency expression ops     2676
problem-id dispatch            none
expected answer                unused
external LLM                   unused
other unresolved false accepts 0/23
chart regression               70 passed
union/audit regression         6 passed
```

監査済み固定89問の能力和は次のように更新された。

```text
65/89 = 73.03%
66/89 = 74.16%
増分   = 1問、約+1.12 percentage points
未認証 = 24問から23問
母集団外の加算 = 0
空虚証明の加算 = 0
```

## 考察

「幾何以外の能力が必要」という見方は半分正しい。問題の対象と結論は平面幾何のままである。一方、証明を探索・実行する内部表現には、複素数型の線形変換、射影・同次座標、行列式、多項式恒等式が必要だった。別分野を不自然に問題文へ混ぜたのではなく、同じ幾何構造を別の表現チャートから観測したことが効いた。

今回の因果は探索量の増加ではない。正相似、六交点、六外心を一つの大域的座標チャートへ移し、局所規則では長くなる関係を一つの共点行列式へ縮約したことにある。したがって、残り23問も「幾何の語彙を無制限に増やす」のではなく、停止した証明義務がどの表現なら短く閉じるかを監査し、問題非依存の変換として追加するべきである。

ただし、このチャートは対象問題を確認した後に実装した post-hoc 能力追加である。66/89は現在コードが証明できる固定集合上の監査済み能力和であり、未見問題への汎化率ではない。汎化は、同型名変更・条件欠落・誤目標・他23問への反例検査では支持されたが、独立した未見集合で別途測る必要がある。

## 結論

不足していたのは新しい幾何述語そのものではなく、正相似を線形変換へ、円と外心を小行列式へ、共点を行列式へ移す大域的な表現チャートだった。この共通変換を厳密証明器として実装し、`2023MOSTMockp2` を追加認証した。監査済み能力和は66/89、残りは23問となった。

## 再現資料

- `worker/backend/positive_similarity_six_circumcenters_chart.py`
- `worker/backend/test_positive_similarity_six_circumcenters_chart.py`
- `worker/backend/jgex_chart_parser.py`
- `data/fixtures/2023MOSTMockp2.jgex.txt`
- `data/hageo-exact-chart-2023mostmockp2-runs-2026-08-26/`
- `data/hageo-positive-similarity-chart-counterfactual-audit-2026-08-26.json`
- `data/hageo-certified-capability-union-plus-2023mostmockp2-chart-2026-08-26.json`
- `data/hageo-certified-capability-union-plus-2023mostmockp2-chart-nonvacuous-audit-2026-08-26.json`
