# MORTRA HAGeo深さ探索とFPGA高速化実験

## 原理

前実験では、HAGeo型の独立軌道探索を `N=6, K=64` で実行し、
`2002CTSTp25` に対して1本の厳密証明を得た。しかし壁時計は701.40秒であり、
`K=2048/8192` へ拡大するには探索核の高速化が必要である。

本実験の仮説は二つである。

1. 未解決の一部は探索深さ不足であり、同一seed集合でも `N` を増やすと証明可能になる。
2. 探索時間の大半は終端証明ではなく候補列挙・数値退化判定にあり、ここはFPGAの
   ストリーミング回路へ写せる。

真偽判定はFPGAへ移さない。FPGAは候補の提案と明白な退化候補の除外だけを行い、
最終受理には従来どおりYuclidの証明書再生を要求する。

## 方法

### CPUプロファイル

固定問題 `2002CTSTp25` の成功軌道48を `N=6` で再生し、Pythonの関数単位で
実行時間を測った。問題ID、参照補助構成、期待解は探索器へ渡していない。

### 意味保存CPU最適化

Pass@Kの `ranking=random` では、候補のseed付きshuffleとrole-balanced prefixは
familyと入力tupleしか参照しない。それにもかかわらず旧実装は、prefixで捨てる候補を
含む全候補について19成分の構造順位を計算していた。

そこで次の順序へ変えた。

```text
旧: 全候補の構造順位計算 -> shuffle -> prefix
新: family/inputだけ生成 -> shuffle -> prefix -> 採用候補だけ構造順位計算
```

shuffle順、採用候補、採用後の構造順位は変えない。小規模全列挙との一致テストと、
成功軌道の入力SHA・証明SHA一致で意味保存を検査した。

### 深さsweep

同じ64個のattempt seed、同じ候補語彙、8プロセス分離を用い、
`N in {2,4,6}` を測った。各軌道は終端でのみnative Yuclid DDARへ渡した。

### FPGA回路

Amaranth 0.5.9で18-bit符号付き固定小数点の1-stage回路を実装した。
現在のCPU前処理と同じ次の有限演算を行う。

- 2点の相異判定: 距離二乗
- 3点の非共線判定: 符号付き面積
- 2直線の非平行判定: 方向ベクトルの外積
- その他のfamily: fail-open

1候補/clockを受理できるインターフェースとし、10,000個のseed付き入力でPython参照実装と
比較した。その後YoWASP Yosys 0.68でXilinx 7-series primitiveへ論理合成した。

## 結果

### CPUボトルネック

旧成功軌道は86.19秒で、そのうち候補列挙が69.83秒、候補の数値構築・incidence評価が
11.72秒だった。6 roundで841,964候補を退化判定し、選択前の構造順位計算だけで
約500万回のgenerator評価が発生していた。

意味保存最適化後は次の結果になった。

| 指標 | 旧 | 新 | 改善 |
|---|---:|---:|---:|
| 成功軌道48 | 86.19秒 | 20.62秒 | **4.18倍** |
| 候補列挙 | 69.83秒 | 7.01秒 | **9.96倍** |
| 構造順位計算数 | 841,964 | 3,072 | **274倍削減** |

成功attemptは48のままであり、構成列、入力SHA、証明SHAも完全一致した。

### 深さsweep

| 深さN | K | 結果 | unique path | 壁時計 |
|---:|---:|---:|---:|---:|
| 2 | 64 | 0/64 | 64 | 54.27秒 |
| 4 | 64 | 0/64 | 64 | 153.85秒 |
| 6 | 64 | **1/64** | 64 | 254.70秒 |

`N=6` の成功は旧実装と同じattempt 48で、証明SHAは
`75eb8e293887219d488f3d403058be7e65268e54a08b479209253ff1f4e59c5a` で一致した。
旧8-process実行701.40秒に対し、新実装は254.70秒で **2.754倍** 高速だった。

### FPGA同値性・合成

| 項目 | 結果 |
|---|---:|
| 比較ベクトル | 10,000 |
| CPU参照との不一致 | **0** |
| pipeline initiation interval | 1 cycle |
| pipeline latency | 1 cycle |
| Xilinx 7-series cells | 532 |
| DSP48E1 | 12 |
| LUT2/3/5/6合計 | 295 |
| CARRY4 | 70 |

論理上1候補/clockなので、841,964候補の回路通過時間は100 MHzで8.42 ms、
200 MHzで4.21 msである。ただしこれはplace-and-route前のthroughput modelであり、
実機転送、BRAMアクセス、タイミング閉包を含む測定値ではない。

## 考察

### 深さ不足だったか

この問題については、明確に深さ不足だった。同一64軌道で `N=2,4` は失敗し、
`N=6` だけが証明を発見した。既存のdependency-closed最小化では成功列から不要な
midpointを除いた5構成が必要だったため、浅い探索では表現できない。

ただし全未解決問題が深さ不足とは限らない。必要な構成family、関係述語、退化条件処理、
verifier規則が欠ける場合、深さを増やしても1軌道成功確率は0のままである。従って今後は
各未解決問題を `depth-limited / grammar-limited / verifier-limited / parser-limited` に分類する。

### FPGAでどこまで速くなるか

現在のFPGA回路が置換できるのは候補tuple・退化判定・構造特徴側だけである。
CPU最適化後の20.62秒から候補列挙7.01秒を完全に消しても、Amdahl上限は1.515倍である。
次の支配項は3,072回の数値構築・incidence評価11.72秒なので、実用上のFPGA化には
次も必要になる。

1. 点座標とincidence bitsetをBRAMへ常駐させる。
2. family別の点構成をDSP pipelineで計算する。
3. line/circle incidence profileとtop-kをdevice内で完結させる。
4. CPUへは採用候補だけを返し、PCIe転送量を候補総数に比例させない。

一方、Yuclid/Wu/Gröbner全体をFPGAへ移すのは現段階では不適切である。規則集合と
多項式サイズが動的で、開発コストが高い。まず規則的で大量反復する提案面だけを
FPGA化し、真理面をCPUの厳密検証器に残す構成が妥当である。

### 微分可能回路との関係

FPGA回路は微分可能制御器の代替ではない。微分可能/Sheaf-ADMM制御器は
`continue / branch / verify / stop` と候補順位を決め、FPGAは選ばれた演算を高速に実行する。
学習済み重みは小さな固定小数点係数として回路へ載せられるが、証明受理には使わない。

## 結論

この問題では、解けなかった主要因の一つが探索深さだった。`N=2,4` では失敗し、
`N=6` で厳密証明を再現した。同時に、候補順位の遅延評価だけでPass@64の壁時計を
701.40秒から254.70秒へ短縮した。

FPGA化については、10,000入力のbit-exact同値試験とXilinx 7-series論理合成まで成立した。
ただし実機高速化を実証した段階ではない。現在の回路だけのend-to-end上限は約1.515倍であり、
大幅な高速化にはfamily別数値構築とincidence top-kまでdevice側へ拡張する必要がある。

## 再現成果物

- `worker/backend/typed_geometry_stalk.py`
- `worker/backend/test_typed_geometry_stalk.py`
- `research/fpga/mortra_geometry_prefilter.py`
- `research/fpga/generated/mortra_geometry_prefilter.v`
- `research/fpga/generated/mortra_geometry_prefilter-xc7-stat.json`
- `scripts/experiment_fpga_geometry_prefilter.py`
- `scripts/summarize_hageo_cpu_profile.py`
- `scripts/requirements-fpga.txt`
- `data/hageo-passk-cpu-profile-summary-2026-08-19.json`
- `data/mortra-fpga-geometry-prefilter-2026-08-19.json`
- `data/hageo-passk-sharded-lazy-n2-k64-2002ctstp25-2026-08-19.json`
- `data/hageo-passk-sharded-lazy-n4-k64-2002ctstp25-2026-08-19.json`
- `data/hageo-passk-sharded-lazy-n6-k64-2002ctstp25-2026-08-19.json`
- `data/hageo-passk-sharded-lazy-replay-n6-k64-2002ctstp25-2026-08-19.json`

主要SHA-256:

| 成果物 | SHA-256 |
|---|---|
| CPU profile summary | `4dd68eeb0cfa085551aa9a8f722d170d6b785341ecf1fd1d3d52f467eeb59890` |
| FPGA experiment | `c7b7b571fc10a480628117e8c0bb845985a93d9dbc6d515dfbd9a31a1dfcac91` |
| N=2, K=64 | `0b48b191b6edd85fd728e5d198023b4b7ae63da66df6d7a8d517d6285224b698` |
| N=4, K=64 | `18ae28ab706251943b635f39b73da75f783dc798943fb9aa8832d30a2d0d971e` |
| N=6, K=64 | `8445a52d96d3f53a1c48a6538db8abb8f551da6e4fda845bc107e4bb906aace4` |
| N=6 replay | `8c9b0e77b53a9d900e4faa6a30d91e79b5dc858ce9d11c5ae5e7a71ce879917e` |
| generated Verilog | `2fa8ae459f3ef6bc111607a4c444b70f4f04b6eb62db8d2915bfac0d87084f6f` |
| Xilinx synthesis stat | `70be442fd7a1b29941a50de766159fb83d808e281900f4300ee76ff1208f90e8` |

参考:

- HAGeo: https://arxiv.org/abs/2512.00097
- Amaranth HDL: https://github.com/amaranth-lang/amaranth
- Yosys `stat`: https://yosyshq.readthedocs.io/projects/yosys/en/0.40/cmd/stat.html
