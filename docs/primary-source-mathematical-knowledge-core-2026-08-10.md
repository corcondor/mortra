# 数学を共通表現へ縮約する一次資料調査（2026-08-10）

> External inspiration / primary-source survey. 記載された外部システムは研究上の参考であり、
> 現在のMORTRA runtime backendではない。

## 調査目的

MathOS の「数学の標準模型」を、独自用語だけで設計しない。既存の形式数学、
数理知識管理、プログラム合成、等式飽和、圏論的計算、定理証明の一次資料から、
実際の最小構文、判断、理論間写像、実行方法を抽出する。

## 結論

最も近い既存設計は、単一の巨大な意味グラフでも、全数学を数個の動詞へ潰す
方式でもない。次の四層である。

1. **対象項の小さい構文**: 記号参照、変数、リテラル、適用、束縛。
2. **little theories の理論グラフ**: 小さい理論、型付き宣言、理論射、代入。
3. **判断**: 型付け、定義的等式、証明可能性。保存則は文字列でなく判断にする。
4. **複数の解釈器**: 正規化、閉包、SMT/CAS、合成、証明検査。解釈器名は
   数学的意味そのものではない。

有限なのは項の構成子と、各時点で宣言済みの理論語彙である。項は再帰と束縛に
より無限に作れる。したがって「有限語彙だから有限状態」という主張は成立しない。
組合せ爆発を抑える根拠は、型、理論境界、正規形、依存関係、証明済みの射である。

## 一次資料から得た具体的な表現

### 1. OpenMath / Content MathML: 数式対象の交換形式

OpenMath の中核オブジェクトは次の形である。

| 記号 | 意味 |
|---|---|
| `OMS` | content dictionary と名前を持つ記号 |
| `OMV` | 変数 |
| `OMI`, `OMF`, `OMSTR`, `OMB` | 整数、浮動小数、文字列、バイト列 |
| `OMA` | 関数適用 |
| `OMBIND`, `OMBVAR` | 束縛と束縛変数 |
| `OMATTR` | 意味属性 |
| `OME` | エラー |

MMT はこれをさらに `OMID / OMV / OMA / OMBIND / OMLIT` に整理する。
Content MathML 4 の Strict 構文も同型で、`cn / ci / csymbol / apply /
bind / bvar / semantics` を使う。重要なのは `+` や「三角形」を核構文にせず、
参照される記号として content dictionary / theory 側に置く点である。

一次資料:

- https://openmath.org/standard/om20-2019-07-01/omstd20.html
- https://www.w3.org/TR/mathml4/#contm
- https://uniformal.github.io/doc/language/objects

### 2. OMDoc/MMT: 数学全体を little theories と射で組織する

MMT の簡約文法は次である。

```text
Doc := (Thy | Mor)*
Thy := c [: o] = { Dec* }
Mor := c : o -> o = { Ass* }
Dec := c [: o] [= o]
Ass := c = o
o   := c | x | c((x [: o])* ; o*) | c(STRING)
```

知識を `Document / Module / Symbol / Object` の4段階に分ける。理論は宣言の
名前付き集合、理論射は view・継承・翻訳・実装・モデルを統一的に表す。
複合射は合成でき、暗黙射は薄い部分圏をなす。これは MathOS のアトラスに最も
近いが、現在の `sources/target/preserves/backend` だけでは assignment と
可換性の証明が欠けている。

一次資料:

- https://uniformal.github.io/doc/philosophy/articles/mmt.pdf
- https://uniformal.github.io/doc/language/index
- https://uniformal.github.io/doc/api/syntax/
- https://uniformal.github.io/doc/language/modules

### 3. Lean / Isabelle / Metamath: 小さい信頼核

Lean は依存型付きラムダ計算を核にし、`Sort u`、依存関数型
`(x : α) -> β x`、`fun x => t`、適用、`let`、定数、帰納型から項と証明を
作る。戦術は証明そのものではなく、最終的に小さい核が検査する項を生成する。

Isabelle/Pure は、項依存 `⇒`、全称量化 `⋀`、含意 `⟹`、メタ等式 `≡` と
判断 `A1, ..., An ⊢ B` を核にする。対象論理は Pure の上の theory として置く。

Metamath はさらに小さく、`$c $v $f $e $d $a $p` と置換、スタック検査だけで
任意の形式体系を検証する。ただし、意味検索や理論の再利用は別層で必要になる。

一次資料:

- https://lean-lang.org/theorem_proving_in_lean4/Dependent-Type-Theory/
- https://lean-lang.org/doc/reference/latest/The-Type-System/
- https://isabelle.in.tum.de/website-Isabelle2025/dist/library/Doc/Implementation/Logic.html
- https://us.metamath.org/downloads/metamath.pdf

### 4. SMT-LIB / SyGuS: 制約実行と中間射合成

SMT-LIB は多ソート論理を使い、例えば
`(declare-fun f (tau1 ... taun) tau)`、`assert`、`forall`、`check-sat`、
`get-model` で実行する。型の合わない項は solver 前に拒否される。

SyGuS は「未知の関数」を、型・候補文法・意味制約から合成する。

```text
(synth-fun f ((x Int)) Int
  ((I Int (0 1 x (+ I I) (- I I)))))
(constraint (= ...))
(check-synth)
```

これは MathOS の中間射探索に直接対応する。ただし grammar に存在しない
原始操作は生成できない。未知構造へ対応するには、既存の型付き構成子から
新しい合成項を見つけ、証明後に定義として theory へ昇格する必要がある。

一次資料:

- https://smt-lib.org/papers/smt-lib-reference-v2.7-r2025-07-07.pdf
- https://sygus-org.github.io/assets/pdf/SyGuS-IF_2.1.pdf

### 5. egglog: 同値な表現をまとめる

egglog は Datalog の固定点計算と e-graph の equality saturation を統合する。
`datatype` で項言語、`rewrite` で証明済み等式、`run` で飽和、`check` で同値、
`extract` でコスト最小の代表を得る。

egglog は未知の等式の真偽を発明しない。誤った rewrite を与えると誤った商を
作る。したがって `RootMinkowskiSum / Difference / Product` を同じ型・backend
だけで統合してはいけない。等式証明または明示的な理論射が必要である。

一次資料:

- https://arxiv.org/abs/2304.04332
- https://egraphs-good.github.io/egglog-tutorial/01-basics.html

### 6. Catlab / generalized algebraic theories: 図式を実行可能にする

Catlab の GAT は型構成子、項構成子、等式公理で理論を定義する。圏なら

```text
Ob : TYPE
Hom(A, B) : TYPE
id(A) : Hom(A, A)
compose(f : Hom(A,B), g : Hom(B,C)) : Hom(A,C)
```

となる。合成可能性を `cod(f)=dom(g)` という後置検査ではなく、依存型
`Hom(A,B)` で構文的に制限する。`@instance` は型を実データ型へ、項構成子を
実関数へ解釈する functorial semantics である。wiring diagram は対称モノイド
圏の射を箱・型付きport・wireで表す。

ただし Catlab 自身は証明書を出す定理証明器ではない。MathOS では図式探索
と可視化に使い、Lean 等で certificate を検査する位置づけになる。

一次資料:

- https://algebraicjulia.github.io/Catlab.jl/v0.12/
- https://algebraicjulia.github.io/Catlab.jl/v0.8/apis/core/
- https://algebraicjulia.github.io/Catlab.jl/latest/generated/wiring_diagrams/wd_cset/

### 7. AlphaGeometry 2: 少数述語、閉包、正規形、探索

AG1 の基礎述語は9個だった。

```text
cong, perp, para, coll, cyclic, eqangle, eqratio, aconst, rconst
```

AG2 は計算 query `acompute, rcompute`、線形関係
`distmeq, distseq, angeq`、軌跡11型、`sameclock, noverlap, lessthan,
overlap, cyclic_with_center` 等を追加した。Arithmetic Reasoning は角度、距離、
対数距離の線形関係を正規形へ落とし、DDAR は固定規則の演繹閉包を作る。

公開実装も確認した。低水準表現は `AGPredicate(name, points, constants)` と
`AGProblem(points, preds, goal)` であり、点は名前と数値座標を持つ。つまり、
AG2は汎用の「数学意味グラフ」を直接解くのではなく、自然文を有限の幾何述語へ
formalizeし、数値図と述語閉包を併用している。

結果は「述語数を減らしたから84%」ではない。言語被覆率を66%から88%へ
増やし、線形正規形、索引、C++ Gaussian elimination、探索木間共有、より複雑な
ランダム図生成を組み合わせて84%を得た。未被覆12%は3D、非線形方程式、
不等式、任意個の点などである。公開コードは主に formalized input 上の DDAR で、
完全な自然言語変換・Gemini探索の全実装ではない。

一次資料:

- https://www.jmlr.org/papers/volume26/25-1654/25-1654.pdf
- https://github.com/google-deepmind/alphageometry2
- https://github.com/google-deepmind/alphageometry2/blob/main/parse.py
- https://github.com/google-deepmind/alphageometry

## MathOS に採用する構造

```text
日本語 / TeX / 図
  -> 表層 chart と参照解決
  -> OpenMath型 Object (ref, var, literal, apply, bind)
  -> MMT型 Theory Graph (theory, declaration, view, assignment)
  -> Judgment (hasType, defEq, provable)
  -> egglog: 証明済み等式だけを飽和
  -> SyGuS: 型付き文法と制約から中間項を合成
  -> SMT / CAS / DDAR: theory別の実行解釈
  -> Lean / Isabelle / Metamath: 証明書検査
```

「幾何も整数も全部同じ」は、同じ名前へ潰すことではない。例えば整数三角形は、
EuclideanMetric theory と OrderedSemiring/Integer theory の間に
`sideLength : Segment -> Real`、`integral : Real -> Prop` などの解釈を置き、
可換条件を証明することで接続する。接続できなければ同一構造とは認めない。

## 現コードへの反映

旧暫定核 `coerce/tensor/map/action/relation/quantify/observe/certify` は、項構文、
数学操作、判断、実行サービスを混同していたため撤回した。実装を次へ分離した。

- object constructors: `symbol-reference / variable-reference / literal /
  application / binding`
- structural primitives: `theory / constant-declaration / theory-morphism /
  assignment`
- judgments: `has-type / definitionally-equal / provable`
- execution services: `normalize / saturate / solve / synthesize / certify`

既存112射は `constant-declaration` と `application` へ再表現できる。しかし
`preserves` と `backend` はまだ文字列注釈であり、意味保存の証明ではない。
ここを実行可能な式と certificate に変えるまで、標準模型が完成したとは言わない。

## 次の反証可能な実験

1. 既存射を little theory ごとに分割し、各宣言へ型または定義を必須化する。
2. `preserves` 文字列を `provable(commutes(...))` の proof obligation へ変換する。
3. 同一演算の別表現は egglog で統合するが、証明のない同型候補は統合しない。
4. 3,574問について `surface -> Object -> Theory -> Judgment -> Interpreter` の
   最初の失敗位置を記録する。
5. 指標は exact だけでなく、言語被覆率、型付け率、実行可能率、証明率、誤統合率を
   分離する。
6. 語彙追加なしで、既存構成子の新しい合成により未見構造が増えるかを測る。
