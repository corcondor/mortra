# MORTRA 多項式補題から型付き幾何関係への逆精緻化実験

## 目的

Wu法・Groebner消去・局所resultantが生成した多項式補題を、Newclid/GCLCが交換できる
`coll / para / perp / cong / cyclic / eqangle / eqratio / midp / lequation`
へ戻す。問題ID、数値、表層文型による分岐は使わない。

## 仮説

型付き関係 `r` の座標意味を `F(r)`、exact backendの補題を `f_i` とする。
逆変換を次の証明可能な場合だけ認める。

1. 単一補題: `f = c F(r)`、正則条件で除ける因子を除いたassociate、または同じsquare-free part。
2. 補題集合: `F(r) = sum h_i f_i` を有理多項式環上のMacaulay恒等式として再生できる。
3. 穴付き義務: 同じAND分岐内の型変数へ同じ点代入を使い、有限個のground関係だけを1または2で検査する。

これは多項式の文字列分類ではない。型付き候補を既存JGEX chartで順変換し、その像との代数的関係を証明するbidirectional elaborationである。

## 実装

- `worker/backend/polynomial_relation_reelaborator.py`
  - 関係候補の順変換、associate/radical照合、正則条件の再生成。
  - degree-bounded ideal membershipによる集合逆変換。
  - worker境界での証明書・hash・恒等式再生。
- `worker/backend/jgex_exact_constraint_bridge.py`
  - Newclid `lequation` のうち、各長さが偶数次数で現れる式をbranch-freeな距離二乗多項式へ変換。
  - Pythagoras、Apollonius、parallelogram lawを同じ表現で扱える。
- `scripts/experiment_hageo_passk.py`
  - open obligationと最終goalだけを需要駆動で逆変換。
  - `?C, ?D` はAND分岐ごとに一貫した有限代入でground化。
- `scripts/run_jgex_exact_specialist.py`
  - timeout前に完了した局所消去証明を`partial_certificate`へatomic保存。
- `worker/backend/bounded_macaulay_membership.py`
  - serialized ideal-membership certificateの独立再生。

## 方法

固定HAGeo問題に対し、Yuclidのnative factsとopen proof obligationsを取得する。exact backendの完了または途中checkpointから、replayed nodeの出力多項式だけを回収する。その後、以下を順に測る。

1. 単一補題とのexact照合。
2. open obligationからの需要駆動照合。
3. 型付き穴を有限ground化した照合。
4. degree 0、次にdegree 1のbounded ideal membership。
5. 回収関係が既知factか、新規factか、goalを閉じたかを分離。

## 結果

### 2024PlanetCupp10

- full exact artifact: 55多項式。
- open obligation: 24分岐。
- ground/hole候補: 267関係。
- 単一補題比較: 14,685組。
- 回収: 4 unique relations。
- 4件すべてYuclidの既知factと重複。
- 新規fact 0、追加正答 0。
- 需要駆動実行時間: 25.63秒。

回収した関係は `coll(d1,e,f)`、`perp(d,d1,e,f)`、`cong(d,n1,e,n1)`、`cong(e,n1,f,n1)`。

### 2016G6

- 70秒で意図的にright-censor。
- timeout前にlocal 9 node、separator 6 nodeを保存。
- replayed output: 24多項式。
- open obligation: 24分岐、18 demands。
- hole completion: 256候補。
- 単一補題比較: 6,336組。
- degree 0 ideal membership: 新規関係0。
- degree 1 ideal membership: 新規関係0、66.58秒。
- 追加正答0。

### 回帰

- 単一逆変換、pure power、異因子積の拒否、条件改ざん拒否。
- `lequation`とperpendicular relationの相互変換。
- bounded Macaulay証明書の再生と改ざん拒否。
- 型付き穴の有限ground化。
- timeout checkpointからの補題回収。

## 考察

接続不良は解消したが、固定2問では得点が増えなかった。原因は次のように分離できる。

1. 旧実装は多項式の座標変数所有点を関係引数へ必須化しており、構成点が祖先変数を共有する場合に誤って候補を落としていた。需要駆動経路では撤廃した。
2. Newclidのopen obligationsに`lequation`が多いのに未対応だった。偶数長さ次数の範囲は接続した。
3. timeout時に多項式本体を保存せず、件数だけ残していた。partial certificateへ変更した。
4. それらを修正しても追加0だったため、主要因は単なる配線ではない。現在の局所消去順序が、Newclidの未解決義務に対応する意味境界を生成していない。
5. hole completionを増やすだけでも追加0だった。次は候補数ではなく、open AND-DAGを閉じるseparatorを目的関数にした消去順序が必要である。

## 教科書の解法との位置付け

- 複素座標: Euclidean relationを複素共役・偏角・比へ写す別chart。円・角・相似で式次数を下げる候補になる。
- Cramer/線形代数: `lequation`やincidence制約の線形部分を行列rank、determinant、nullspaceとして解くbackendになる。
- 正弦・余弦定理、Heron: angle/ratio/area間の型付きviewであり、座標多項式を短い辺長制約へ変換する。
- Muirhead、重み付きAM-GM、Schur、Chebyshev、rearrangement、convexity、Holder: 幾何relationへ混ぜず、対称多項式・majorization・凸性の別theoryとして、同じ証明書交換規約へ接続する。

これらは問題別解法として登録せず、表現chartと可逆または証明付きviewとして追加する。

## 結論

多項式補題から型付き関係への経路、`lequation`、集合証明、穴の有限ground化、timeout checkpointは実装・再生できた。しかし固定未解決2問の追加正答は0であり、スコア改善を主張しない。

次の実験対象は、消去変数の局所次数ではなく「現在のopen obligationを閉じる型付きseparatorを生成できるか」で局所消去順序を選ぶobligation-conditioned eliminationである。対照群は現行min-fill、処置群は同じ計算予算でtyped obligationとのforward-image距離を目的関数に加える。

この後続実験は`MORTRA-OBLIGATION-CONDITIONED-ELIMINATION-EXPERIMENT-20260822.md`で実施した。接続と合成因果例は成功したが、固定未解決2問の追加正答は0だった。変数支持・単項式支持では実座標chart上の意味差を十分に分離できないことが判明した。

## 再現物

- `data/polynomial-relation-hole-ideal-exchange-2024planet-2026-08-22.json`
- `data/polynomial-relation-hole-exchange-2016g6-2026-08-22.json`
- `data/polynomial-relation-ideal-degree1-2016g6-2026-08-22.json`
- `data/polynomial-checkpoint-cohort-2016g6-runs/2016G6.json`
