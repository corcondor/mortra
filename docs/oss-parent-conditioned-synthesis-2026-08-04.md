# 公開実装を接続した複数親・構造帰納（2026-08-04）

## 目的

選択された2問以上を固定端点とし、保存済み問題文や解法テンプレートを選ぶのではなく、端点から抽出した
型付き制約を同時に使う新しい観測式を列挙する。検証できた式だけを動的Atlasへ登録し、同じ実行内で
問題文、答え、証明書、UIの進捗表示まで返す。

## 公開実装の採用範囲

| 公開実装・規格 | MathOSでの使用 | 状態 |
|---|---|---|
| [cvc5](https://github.com/cvc5/cvc5) | SyGuS文法による型付き式列挙、QF_NIAによる全親変数依存の存在証人探索 | 実行接続済み |
| [egglog](https://github.com/egraphs-good/egglog) | 可換・結合・定数計算をe-graphで飽和し、同値候補をe-classへ圧縮 | 実行接続済み |
| [SymPy](https://github.com/sympy/sympy) | 反復resultant、平方因子除去、モニック化、数値根による反例検査 | 実行接続済み |
| [MathJSON / Cortex Compute Engine](https://github.com/cortex-js/compute-engine) | 数式を関数適用木として表す設計 | 同じ原則の軽量IRをローカル実装 |
| [QuickSpec](https://github.com/nick8325/quickspec) | 意味シグネチャによる候補列挙・重複除外 | cvc5不在時の決定的fallback設計 |
| [Rosette](https://github.com/emina/rosette) | solver-aided synthesisと反例修正の設計 | 設計参照。runtime未接続 |
| [Lean mathlib](https://github.com/leanprover-community/mathlib4) / [Aesop](https://github.com/leanprover-community/aesop) | 形式証明と証明探索 | 次の独立検証adapter。現時点では未接続 |
| [GiNZA](https://github.com/megagonlabs/ginza) / [MMT](https://github.com/UniFormal/MMT) / [OpenMath](https://openmath.org/) | 日本語依存構造、理論グラフ、意味オブジェクト設計 | 設計参照。重いruntime依存は未追加 |

「参考にした」と「実際に実行している」を分ける。現在の生成経路で実行される外部エンジンは
cvc5、egglog、SymPyである。

## 実行経路

```text
複数の親問題
-> MathJSON型の字句・構文解析
-> 一変数代数制約の型付きIR
-> cvc5 SyGuSで全親変数を含む観測式を列挙
-> egglogで等価な式を同一e-classへ圧縮
-> cvc5で各親変数への意味依存を検査
-> SymPyで全親変数を反復resultant消去
-> 全根直積の数値代入で反例探索
-> 親制約を一つずつ摂動する全親ablation
-> 認証済みHyperMorphismを動的Atlasへ登録
-> 問題文・答え・証明書を生成してDB/UIへ返す
```

親が `n` 個なら候補式は `x0,...,x(n-1)` をすべて含まなければならない。cvc5の依存検査は
自由整数上の意味依存を確認するが、それだけでは親制約上の本質性を証明しない。このため各親多項式を
独立に摂動し、消去結果が変化することを追加の受理条件にしている。

## 暗記との違い

DBへ保存するのは問題文や答えではなく、認証された射の次の契約である。

```text
name, expression program, arity, source types, target type,
preserved properties, executable backends
```

次回の探索では同じ認証式を候補から除外し、別の式プログラムを探索する。係数や変数名を変更した場合も
答えは再計算される。親問題ID、正答、表層文型による分岐は候補文法に含めない。

## 実測結果

### 2親

入力制約 `x^2-2=0`, `x^2-3=0` に対し、cvc5が207項を調べ、egglogが116 e-classへ圧縮した。
認証観測 `x0^2*x1` に対して `P(z)=z^2-12` を得た。全根代入、cvc5依存検査、2親それぞれの
摂動検査を通過した。

同じ認証射をAtlasから再読込した再実行では、それを再利用して同じ問題を返さず、別の観測
`x0*x1+x0` を生成した。

### 3親

入力制約 `x^2-2=0`, `x^2-3=0`, `x^2-5=0` に対し、cvc5が492項を調べ、egglogが108 e-classへ
圧縮した。全3親を使う観測 `x0-x1+x2` を認証し、次を厳密計算した。

```text
P(z)=z^8-40z^6+352z^4-960z^2+576
```

3親すべての独立ablationを通過している。

## 検証

- worker: 46テスト中46件成功。
- 3親が同じ観測式に使われることを検査。
- 認証Atlasを再読込すると既存式が除外され、別プログラムへ進むことを検査。
- worker build成功。
- Next.js production build成功、34ページを生成。

## 保証範囲と次段階

現在E2Eで保証できる対象は、複数の一変数代数方程式が定める有限根配置である。任意の積分、整数、確率、
幾何が同じ完成度で自動生成できるという結果ではない。拡張単位は完成問題テンプレートではなく、各型に対する
合法な項文法、等価性、実行backend、反例生成器である。次は整数関係、定積分作用素、座標幾何構成について
同じ `synthesize -> collapse -> verify -> ablate -> promote` 契約を実装し、frozen親集合で測る。

## 本番E2E

コミット `c6a4447` を本番workerへ反映し、答えを与えない三親 `u^2-2=0`, `v^2-3=0`,
`w^2-5=0` をAPIへ送った。job `9c95e21d-0c14-4cc9-9537-8707a670bb46` は次を完了した。

- GitHub Actions run `30901039860` 成功。Python依存導入、46テスト、worker build、job処理が全て成功。
- cvc5/egglogはいずれもACTIVE。SyGuS 495項、108 e-class、型付き項526件を処理。
- 全親provenanceを持つ実行候補76件から観測 `x0-x1+x2` を認証。
- 問題文、答え、解説、全親割当、証明書を生成し問題DBへ保存。
- 厳密答え `P(z)=z^8-40z^6+352z^4-960z^2+576`。
- runtimeはjob開始から保存まで約2.5秒。LLM API呼び出しなし。
