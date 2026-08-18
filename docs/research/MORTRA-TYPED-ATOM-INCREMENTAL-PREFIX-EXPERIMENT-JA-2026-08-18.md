# MORTRA typed atom照合・増分作図 実験報告

日付: 2026-08-18

## 要旨

候補構成をopen proof obligationへ近づけるため、述語名だけでなく、量化変数、既知点、穴の位置、引数対称性を保つtyped atom照合を実装した。また、深さ2以降で共通する親問題を毎回再構築せず、prefixごとの型付き状態を再利用する増分作図を実装した。

typed atom照合は`2015_p3`で同じ証明経路を保ったが、評価枝が12本から27本へ増え、時間も21.67秒から28.31秒へ30.6%悪化した。候補と直接単一化した義務は0件だった。したがって「1段のopen obligationを平坦化した集合へtyped atom照合すれば順位が改善する」という仮説は棄却された。

増分作図は`2000_p6`で、Yuclidへ渡した入力、証明成否、構成経路、評価枝142本、エラー0を保持した。評価済み経路の作図遷移は267回から142回へ46.8%減り、壁時計時間は253.47秒から241.57秒へ4.7%短縮した。作図再構築の重複は除けたが、全体の支配項はYuclidの正確閉包である。

## 原理

```mermaid
flowchart LR
    G["最終goal"] --> O["後向き証明義務"]
    O --> A["typed atom照合"]
    A --> C["有限の構成候補"]
    C --> P["prefix状態"]
    P -->|"共有親を再利用"| N["子状態"]
    N --> Y["Yuclid exact closure"]
    Y --> R["native certificate"]
```

typed atom照合は、候補構成の形式定義から得た関係原子とopen premiseを比較する。例えば`perp(x,a,b,c)`では、穴`x`の束縛だけでなく、直線の端点交換に対する対称性も保存する。問題番号、問題文の語句、既知の補助点、答えは参照しない。

増分作図では、構成列`(c1,c2,...,cn)`の乱数をprefixから決定する。

```text
state(c1,...,cn) = extend(state(c1,...,c(n-1)), cn, hash(prefix))
```

したがって兄弟候補は同じ親状態を共有し、子候補によって親の座標標本が変わらない。キャッシュ状態は不変スナップショットとして保持し、検証器へ渡す際だけ複製する。

## 仮説

- H1: symmetry-aware typed atom照合は、問題固有規則なしで正しい候補を前方へ移す。
- H2: prefix状態の再利用は、Yuclidへ渡す数学的入力と証明結果を変えない。
- H3: prefix状態の再利用は、重複作図と壁時計時間を減らす。

## 方法

### typed atom照合

- 対象: `2015_p3`
- family set: extended
- branch limit: 64
- depth: 1
- workers: 8
- candidate gate: combined
- 対照: alignment off
- 処置: symmetry-aware typed atom alignment

構成関係はNewclidのJGEX形式定義から抽出し、問題文の正規表現では作っていない。引数を一様に改名しても順位特徴が変わらないことを単体試験した。

### 増分作図

- 対象: `2000_p6`
- branch limit: 24
- beam width: 8
- depth: 2
- workers: 8
- candidate gate: combined
- 対照: prefix-stable replay
- 処置: prefix-stable incremental cache

両方式で乱数規則を同一にした。比較した受理条件は、最終構成経路だけでなく、Yuclid入力SHA-256、成否、評価枝数、エラー数の一致である。Yuclidのraw JSONは巨大な推論集合の列挙順が実行ごとに変わるため、raw出力ハッシュの一致を受理条件にはしない。

## 結果

### typed atom照合

| 指標 | alignment off | typed atom | 差 |
|---|---:|---:|---:|
| solved | yes | yes | 保持 |
| 評価枝 | 12 | 27 | +15 |
| エラー | 0 | 0 | 0 |
| 時間 | 21.67 s | 28.31 s | +6.64 s (+30.6%) |
| direct atom match | - | 0 / 256 | - |

証明経路は両方とも次である。

```text
intersection_lc(a,f,h)->d
```

最終goalは`coll(k,o1,o2)`だが、1段後向き義務は`para`、`midp`、`lequation`など24個の代替候補になった。正しい構成が直接作る`coll(a,d,h)`と`cong(d,f,f,h)`は、この1段義務に現れない。代替義務を一つの集合として平坦化した結果、任意の一義務と局所的に重なる無関係な候補が先行した。

### 増分作図

| 指標 | prefix replay | incremental | 差 |
|---|---:|---:|---:|
| solved | yes | yes | 保持 |
| 評価枝 | 142 | 142 | 0 |
| エラー | 0 | 0 | 0 |
| 評価経路の作図遷移 | 267 | 142 | -125 (-46.8%) |
| 時間 | 253.47 s | 241.57 s | -11.90 s (-4.7%) |

証明経路:

```text
foot(i,z,x2)->d
reflect(t1,i,d)->e
```

Yuclid入力は両方式で完全一致した。

```text
f47ce96b7145fd4a46bf82c570b06f1c78f337e60bcab29a182e8caabc4b9172
```

## 考察

H1は棄却された。問題はtyped unification自体ではなく、照合対象となる後向き義務の深さと論理構造である。複数の代替証明義務をOR構造のまま保持せず平坦化すると、「どれか一つに近い」候補が過大評価される。また正しい補助構成が最終goalから複数推論離れている場合、1段照合だけでは観測できない。

H2は支持された。入力ハッシュ、探索結果、経路、評価本数は一致した。raw証明JSONのハッシュは異なったが、同一入力に対するYuclid内部列挙順の差であり、入力差ではないことを独立に確認した。

H3は部分的に支持された。重複作図遷移は半分近く減ったが、全体時間の短縮は4.7%だった。したがって増分作図は採用可能だが、それだけで探索全体は高速化しない。次の支配項は候補ごとのYuclid exact closureである。

## 結論

- symmetry-aware typed atom単一化の実装自体は、改名・対称性試験を通過した。
- ただし1段義務の平坦集合を順位付けに使う方式は採用しない。
- prefix-stable incremental constructionは、数学的入力を保持して重複遷移を46.8%除いたため採用候補とする。
- 次の本質的実験は、ORで分かれた後向き義務をproof DAGとして保持し、2段以上の中間goalを型付きで合成すること。ただし候補ごとの完全前向き飽和は2分以上停止したため使わず、有限深さ・有限beamの後向き展開として測る。

この結論は`2000_p6`と`2015_p3`の校正実験に限定される。IMO-AG全体の速度改善や正答率改善はまだ主張しない。

## 再現

```powershell
python -B -m pytest worker/backend/test_incremental_prefix_state.py worker/backend/test_typed_candidate_alignment.py -q
python -B scripts/experiment_incremental_prefix_ablation.py --python <newclid-python> --dataset <imo.txt> --yuclid-exe <yuclid> --runtime-path <boost-runtime> --problem 2000_p6 --output <summary.json> --run-dir <trace-dir>
python -B scripts/verify_incremental_prefix_ablation.py --artifact <summary.json>
```

主要実装:

- `worker/backend/geometry_proof_hypergraph.py`
- `worker/backend/typed_candidate_alignment.py`
- `worker/backend/incremental_prefix_state.py`
- `worker/backend/yuclid_native_verifier.py`
- `scripts/experiment_newclid_construction_stalk.py`
- `scripts/experiment_incremental_prefix_ablation.py`
- `scripts/verify_incremental_prefix_ablation.py`
