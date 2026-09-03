# MORTRA 折り配列実験

日付: 2026-09-04

実装: `math_os_prototype/origami_fold_dna.py`
生成器: `scripts/generate_origami_fold_dna_studies.py`

## 結論

折り紙は、MORTRAへ模様ごとの新しい幾何射を追加せずに扱える。必要なのは、既存の点・線・面・鏡映・三次元回転を、紙のどの面へどの順番で作用させるかを記した型付き配列である。

ただし「折線の図」と「実際の折り運動」は別の対象である。折線を再帰生成するだけでは、面が伸びないこと、折線の両側が離れないこと、閉路が閉じること、紙が互いに突き抜けないことは保証されない。そこでMORTRAの折り配列は、命令列と検証条件を一体として持つ。

## 先行研究との対応

### 折線を作る規則

Huzita-Justinの公理は、一回の折りで点と線をどのように一致させ、新しい折線を構成できるかを列挙する。Ghourabiらは、この公理を一階述語論理の制約として書き、多項式の等式・不等式へ変換して、折線の記号計算、可視化、正しさの自動証明へ接続した。

- Robert J. Lang, [Huzita-Justin Axioms](https://langorigami.com/article/huzita-justin-axioms/)
- Ghourabi et al., [Logical and algebraic view of Huzita's origami axioms](https://doi.org/10.1145/1244002.1244173)

MORTRAでは、これらを新しい描画プリミティブではなく、`Point2`、`Line2`、`Intersection`、`reflect` などへ展開される構成チャートとして扱える。

### 折線パターンを再帰生成する規則

Yuらのshape grammarは、始図形の一部を見つけ、線と曲線の書換え規則を再帰的に適用して折り紙パターンを生成する。これは、短い規則列から世代ごとに複雑な形を作るという意味で、今回の「DNA」に最も近い先行例である。

- Yu, Hong, Economou, Paulino, [Rethinking Origami: A Generative Specification of Origami Patterns with Shape Grammars](https://paulino.princeton.edu/journal_papers/2021/CAD_21_RethinkingOrigami.pdf)

MORTRAとの差は、書換え後の図を得るだけで終わらず、その図が折れるかを別の検証層で確かめる点にある。

### 三次元の折り運動

Tachiの剛体折りモデルでは、各面を変形しない剛体、折線を回転軸、折角を状態変数として扱う。経路が横切る折線の単一折りを \(R_1,R_2,\ldots,R_n\) とすると、相対的な折り運動は

\[
 F(\gamma)=R_1R_2\cdots R_n
\]

という回転の積で表される。

- Tomohiro Tachi, [Rigid Folding of Periodic Triangulated Origami Tessellations](https://origami.c.u-tokyo.ac.jp/~tachi/cg/rigid-origami-tessellation.pdf)
- Tomohiro Tachi, [Simulation of Rigid Origami](https://tsg.ne.jp/TT/cg/SimulationOfRigidOrigami_tachi_4OSME.pdf)

これはMORTRAの射の合成と直接一致する。一つの折り記号を、折線上の軸を中心とする既存 `Rotate3` へコンパイルすればよい。

## 折りDNAの型

今回の一記号は

\[
 g=(\text{hinge},\text{M/V},\rho)
\]

である。`hinge` は折線、`M/V` は山折り・谷折り、\(\rho\) は折角を表す。実行時には、その折線より先に接続された面集合を求め、各頂点を同じ軸のまわりに \(\rho\) だけ回転する。

例えば

```text
M57@a0.d3.hinge V57@a1.d3.hinge ...
```

は、外側の折線から順に、山折りと谷折りを交互に作用させる配列である。`fold` という新しい幾何射は作っていない。各記号は既存 `Rotate3` の有限列へ展開される。

## 実験

一つの平面展開図を用意した。

- 面: 25
- 折線: 24
- 接続グラフ: 木
- 一配列の長さ: 24記号

この同じ展開図へ、次の3配列を作用させた。

1. 外側から内側へ山谷を交互に折る配列
2. 腕ごとに内側から外側へ折る配列
3. 折りが周方向へ進む配列

一つの配列は240個の頂点回転へ展開された。三つの最終状態は意味ハッシュ、画像ハッシュともに相異なった。

さらに、同じ「外側の辺へ次の台形面を接続する」という一つの書換え規則を1回から4回まで反復し、4世代の相異なる展開図を生成した。世代のための図形命令は増やしていない。

## 検証結果

各折りの直後に、すべての面と折線を検査した。

| 検査 | 最大残差 |
|---|---:|
| 面内の全頂点間距離 | \(5.6\times10^{-16}\) |
| 四角形面の平面性 | \(5.6\times10^{-16}\) 以下 |
| 折線の両側の端点一致 | \(1.1\times10^{-16}\) |

全75途中状態で検査を通過した。追加した幾何射は0件である。

## 次の一般化

現在は接続グラフが木なので、一つの折線より先にある面集合が一意に決まる。次は、論文の条件を同じ型へ追加して、切れ目のない周期格子を扱う。

1. 一頂点の角度列にKawasaki条件と山谷割当て条件を適用する
2. 閉路に沿う回転の積が恒等変換になることを確かめる
3. 折り途中の面同士の衝突と、平坦状態の上下順を確かめる
4. shape grammarで生成した候補を、上の三検査に通ったものだけ残す

この順序なら、登録済みの折り紙だけを再生する仕組みにはならない。短い書換え配列を生成し、折れるかを厳密に判定し、失敗した局所配列を修正する閉ループになる。

## 生成物

- 比較画像: `brand/studies/origami-fold-dna-20260904/origami-fold-dna-review.png`
- 折り途中: `brand/studies/origami-fold-dna-20260904/origami-fold-dna-step-strip.png`
- 反復世代: `brand/studies/origami-fold-dna-20260904/origami-fold-dna-generations.png`
- 動画: `brand/studies/origami-fold-dna-20260904/origami-fold-dna-sequence.gif`
- 数値記録: `brand/studies/origami-fold-dna-20260904/manifest.json`

剛体折りの周期格子、単一頂点の剛体折り条件、曲率を指定した逆設計は、それぞれ次の研究と接続する。

- Abel et al., [Rigid Origami Vertices: Conditions and Forcing Sets](https://erikdemaine.org/papers/RigidOrigami_JoCG/paper.pdf)
- Dudte et al., [Programming Curvature using Origami Tessellations](https://arxiv.org/abs/1812.08922)
