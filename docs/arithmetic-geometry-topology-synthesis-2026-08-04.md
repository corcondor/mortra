# 整数・図形・位相の抽象補題合成（2026-08-04）

## 目的

整数論と図形・位相を、互いに無関係な完成問題の連結として扱わない。幾何量や位相的不変量を整数関係へ
写す実行可能な射を合成し、具体的な数値を持たない一般補題を生成する。

## 三角形から整数関係への射

型付き原子は外接円半径、内接円半径、傍接円半径である。

```text
R   = abc/(4 Delta)       area degree -1
r   = Delta/s             area degree +1
r_a = Delta/(s-a)         area degree +1
r_b = Delta/(s-b)         area degree +1
r_c = Delta/(s-c)         area degree +1
```

生成器は原子の積を文法列挙し、面積次数が偶数のものだけをHeron恒等式

```text
Delta^2 = s(s-a)(s-b)(s-c),  s=(a+b+c)/2
```

で消去する。得られた有理式を既約な `N/D` とし、次の述語射を適用する。

```text
N/D is integral  <=>  D divides N
N/D is prime     <=>  exists prime p, N=pD
```

これは特定の係数や問題文を保存する規則ではなく、任意の正の整数辺三角形へ適用する関係変換である。

### 自動生成例

```text
Rr = abc / (2(a+b+c))
Rr in Z  <=>  2(a+b+c) divides abc
Rr is prime  <=>  exists prime l, abc=2l(a+b+c)
```

さらに式が三辺の置換に不変な場合だけ、二辺を任意の素数 `p,q` とする補題を自動派生する。

```text
Rr is prime
<=> exists prime l, npq=2l(n+p+q)
```

これは「二辺が素数で、`Rr` も素数となる整数三角形を分類する」問題の探索空間を、幾何から
Diophantine方程式へ正確に移す補題である。現時点では全解の分類までは自動証明していない。

## 位相から整数関係への射

閉曲面の有限三角形分割について、頂点数、辺数、面数を `V,E,F`、Euler標数を `chi` とする。
接続対の二重計数とEuler関係を線形消去する。

```text
3F=2E
V-E+F=chi
=> E=3(V-chi), F=2(V-chi)
```

この整数ベクトルの係数 `(3,2)` が原始的であることから、次を生成する。

```text
gcd(E,F)=V-chi
E prime => E=3 and V-chi=1
F prime => F=2 and V-chi=1
E:F=3:2
```

分割の具体例や曲面の種数を固定せず、位相的不変量と整数条件の関係を補題として出力する。

## 受理条件

1. 選択親の一方が図形または位相構造、他方が整数述語を供給する。
2. 親を一つ除いても同じ能力が残る場合は、冗長な融合として棄却する。
3. 型付き量の文法から候補を列挙する。
4. 辺の置換で同型な式を正規化して除外する。
5. SymPyで恒等式・線形消去を厳密検証する。
6. 独立な整数三角形または接続データへ代入して反例を探す。
7. 認証した関係だけを動的Atlasへ保存する。
8. 次回は保存済み関係IDを除外し、別の補題へ進む。

## 構造的一意性証明書

数値を変えただけの問題を新問と数えないため、各カードへ `StructuralUniquenessCertificate` を付ける。

```text
conditionSkeleton       型付き条件の骨格
querySignature          問われる述語
normalForm              条件から得た一意な関係正規形
quotientAction          S3辺置換または単体接続同型
freeParameters          残る抽象変数
uniqueNormalForm        関係式が一意に正規化されたか
finiteSolutionSet       全整数解の有限性を証明したか
numericInstanceConstants 問題固有の数値
conditionAblationPassed 条件・親の不可欠性
```

今回の抽象補題は `uniqueNormalForm=true`, `numericInstanceConstants=[]` だが、一般の整数解集合を
分類していないため `finiteSolutionSet=false` と明記する。将来の「全て求めよ」型カードは、合同式ふるいと
完全性証明によって `finiteSolutionSet=true` になった場合だけ公開する。

## UI

生成画面は次を表示する。

- 合成器 `sympy-relational-grammar`
- 候補式列挙数
- 同値類数
- 認証射数
- `SymPy relational ACTIVE`
- 問題文、答え、証明の射列、親割当、ablation結果

## 検証

- worker全51テスト成功。
- 三角形・整数の二親から3補題を一回で生成する統合テスト成功。
- 位相・整数の二親からEuler接続補題を生成するテスト成功。
- 冗長親と無関係親を棄却するテスト成功。
- 認証済み補題を再度返さず、次候補へ進むテスト成功。
- worker TypeScript build成功。

三角形文法は15個の積を列挙し、辺置換で7同値類へ圧縮する。整数性、素数性、置換不変式に対する
二素数辺還元を合わせて17候補を生成する。位相文法は4候補を生成する。

## 限界と次の検証

現在は抽象補題の生成と厳密な関係還元までである。Diophantine方程式の全解分類、一般の高次元単体複体、
ホモロジー群のtorsionと素数条件までは未実装。次は生成した `npq=2l(n+p+q)` をZ3/cvc5の合同式探索、
SymPyの因数分解、素数ふるいへ渡し、有限候補化または不存在証明へ進める。また位相側は境界付き曲面、
多角形分割、鎖複体のSmith標準形を同じ整数関係IRへ追加する。
