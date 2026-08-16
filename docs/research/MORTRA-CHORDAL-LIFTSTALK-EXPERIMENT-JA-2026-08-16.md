# MORTRA 証明DAG付き Chordal 消去・liftstd 実験

記録日: 2026-08-16

## 1. 原理

対象は、`on_aline` / `cc_tangent` を座標展開したときに数千項規模へ成長する
多項式証明義務である。単一の大域 Gröbner 基底を作る代わりに、変数と多項式の
主グラフを chordal completion し、局所 clique で得た消去イデアルだけを
separator へ送る。

局所メッセージ `h=0` は必ず次の証明DAG辺を持つ。

\[
 h=\sum_i q_i f_i.
\]

受信側は文字列やCASの成否を信用せず、この恒等式を有理係数多項式環で再計算する。
未完備の局所基底は消去イデアルと同一視せず、元生成元を保持する。

論文に合わせて、各 clique は主変数 `x` に関する先頭係数も公開する。
先頭係数が単元でない場合は `lc_x(f) != 0` を別の証明義務とし、局所化の仮定を
隠さない。これは係数イデアル／domination 条件を今後実装するための境界である。

## 2. 一次資料から採用した部分

### Chordal elimination

Cifuentes--Parrilo の chordal elimination は、局所イデアルの Gröbner 基底から
消去変数を含まない生成元を次の clique へ送る。計算環の変数数は treewidth で
決まる。ただし線形計算量の主張は制限されたイデアル族に対するもので、任意の
幾何イデアルが高速になるとは主張していない。

- https://arxiv.org/abs/1411.1745
- https://arxiv.org/abs/1604.02618

### Buchberger / F5B

SymPy 1.14 の改善 Buchberger 実装を読み、初期生成元の自己簡約、積規準、
LCM による critical-pair 削減を移植した。F5B も同一入力で比較した。

- https://docs.sympy.org/latest/modules/polys/reference.html

### Singular liftstd

Singular の `liftstd(I,T)` は `G=I*T` を満たす標準基底と変換行列を返す。
さらに `lift(G,target)` を合成し、`target=I*(T*U)` を得る。この係数恒等式を
MORTRA側のSymPyで再生する。したがってSingularは判定oracleではなく、検査可能な
証明書生成backendとしてだけ使う。

- https://www.singular.uni-kl.de/ftp/pub/Math/Singular/doc/tutor.pdf

## 3. 実装

### 証明DAG付き Buchberger

- `worker/backend/certified_buchberger.py`
- 中間基底を元生成元まで毎回平坦化せず、直前の基底への局所恒等式として保存。
- 完全基底になる前でも、目標の余りが0になれば `target_membership` で停止。
- 完備していない場合は `groebner_complete=false` を維持する。

### Chordal separator 輸送

- `worker/backend/chordal_buchberger_elimination.py`
- min-fill 順で局所 clique を選択。
- 完備した局所基底だけを消去としてcommit。
- 未完備の場合は元生成元を残し、目標変数へのグラフ距離、scope、項数、
  先頭単項式の非冗長性で少数の健全な帰結だけを輸送。
- 先頭係数と非零義務を証明書へ記録。

### 型付きstalk交換

- `worker/backend/chordal_polynomial_stalk.py`
- 各多項式恒等式を独立に再計算してから `ExactSheafCoordinator` へ渡す。
- 証明DAGの前提が未導出ならそのメッセージを採用しない。

### 公開CASとの証明書付き接続

- `worker/backend/singular_lift_backend.py`
- WSL内の隔離Singularへ一般の多項式環を送る。
- 元の変数名を `x1,...,xn` へ写し、表層名依存を除く。
- `liftstd + lift` の係数を受け取り、元式との残差が厳密に0の場合のみ証明とする。

## 4. 実験条件

- 固定問題: `2008_p6`, `2010_p2`, `2020_p1`, `2021_p3`。
- 問題の補助節: 非表示。
- LLM: 不使用。
- 問題番号、既知解答、固有数値によるsolver分岐: 不使用。
- 成功条件: 全中間証明書と最終目標証明書が再生できること。
- 時間切れ: 誤りではなく棄却。正答には含めない。

## 5. 結果

### 5.1 非線形 Resultant 先行

`2020_p1` は第一段で12変数・5多項式まで縮約し、5/5の局所証明書を再生した。
しかし7変数separatorのcliqueで16組を処理するのに73.18秒かかり、基底は未完備。
12個の帰結を全送信すると次cliqueが15入力へ膨張し、300秒で時間切れになった。

これは「局所帰結はすべて送ればよい」という仮説を反証した。健全な帰結でも、
通信幅を制御しなければ計算グラフを密化する。

### 5.2 separator メッセージを2件へ制限

同じ `2020_p1` で、局所候補5件・8件から各2件だけを輸送できた。
一方、`_free_y_15` の初期自己簡約だけで206.39秒を要し、全体は300秒で時間切れ。
伝送幅は抑制できたが、局所演算そのものの項増加は残った。

### 5.3 線形消去だけを先行

非線形Resultantを遅延し、疎な二次式を保持した。`2020_p1` は16変数・9式となり、
最初の三つの長さ変数を合計0.07秒未満で完全消去した。次の `_free_x_14` は
16組・8.77秒で候補10件を作り、2件だけを輸送した。

非線形Resultant先行時の対応する重い局所計算より明確に軽くなったが、その次の
5入力cliqueは300秒内に完了しなかった。よって「疎性保持は必要」だが十分ではない。

### 5.4 Singular liftstd 固定4問

線形局所消去後の残差を、Singular `liftstd + lift` へ180秒/問で渡した。

| 問題 | 初期 変数/式 | 線形前処理後 変数/式 | 第一段再生 | 最終結果 |
|---|---:|---:|---:|---:|
| 2008_p6 | 32/28 | 32/28 | 成功 | timeout |
| 2010_p2 | 20/16 | 16/12 | 成功 | timeout |
| 2020_p1 | 28/19 | 16/9 | 成功 | timeout |
| 2021_p3 | 19/15 | 17/13 | 成功 | timeout |

集計は、完了0/4、時間切れ4/4、最終証明0/4、誤受理0である。壁時計時間は
392.71秒（2並列）。SymPy F5BとSingular `slimgb` も `2020_p1` の同じ疎な
16変数・9式をそれぞれ100秒超・180秒で完了できなかった。

したがってボトルネックは独自Python実装だけではない。現在の座標多項式化が
生む正次元・高次数・退化枝を含むイデアルを、標準基底一括計算へ渡すこと自体が重い。

## 6. 科学的結論

### 残った正の結果

1. 局所証明DAGは20テストで恒等式を再生した。Singularのlive `liftstd` 小例も含む。
2. 未完備基底を消去済みと誤認する経路を除去した。
3. 目標が部分基底で閉じた場合、完全基底を待たずに証明できる。
4. separator候補12件を2件へ抑える一般的な通信規則が動いた。
5. 局所化に必要な先頭係数の非零条件を明示的な証明義務にした。
6. 非線形Resultantの前倒しが疎性を壊すことを定量的に確認した。

### 反証された仮説

1. chordal分割だけで重い幾何イデアルが180秒内に解ける、は偽だった。
2. 最適化済みCASへ置換すれば固定4問が閉じる、もこの条件では偽だった。
3. 健全な局所帰結をすべて交換すれば協調が強くなる、も偽だった。

### 次の本質的実験

次は大域標準基底を再試行するのではなく、構成順の三角鎖と擬除算へ移る。

1. `on_aline` は等角という関係型のままDD/ARへ渡し、座標式へ展開しない。
2. `cc_tangent` は4接点を隠し、外相似中心、中心の共線、半径比を境界命題とする。
3. 残る座標義務だけを構成の逆順に擬除算し、各段で
   `lc(f)^k g = qf + r` を証明DAGとして交換する。
4. 非零先頭係数をNewclid/GCLCの非退化条件へ照合する。
5. 同じ固定4問で、標準基底、三角鎖、両者のportfolioを比較する。

これはWu法の完全再現へ向かう具体的な差分である。現在はまだ三角鎖生成と
非退化条件の閉包が未実装なので、固定4問を解いたとは主張しない。

## 7. 再現物

- `data/hybrid-polynomial-stalk-smoke-2020-p1-2026-08-16.json`
- `data/hybrid-polynomial-stalk-goal-directed-smoke-2020-p1-2026-08-16.json`
- `data/hybrid-polynomial-stalk-linear-first-smoke-2020-p1-2026-08-16.json`
- `data/singular-lift-fixed4-2026-08-16.json`
- `scripts/experiment_hybrid_polynomial_stalk_fixed4.py`
- `scripts/experiment_singular_lift_fixed4.py`
- `worker/backend/test_certified_buchberger.py`
- `worker/backend/test_chordal_buchberger_elimination.py`
- `worker/backend/test_chordal_polynomial_stalk.py`
- `worker/backend/test_singular_lift_backend.py`
