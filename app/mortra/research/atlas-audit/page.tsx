import Link from 'next/link'
import ScrollSolid from '@/components/ScrollSolid'

export const metadata = {
  title: 'アトラスに足りなかったのは数学ではなかった — MORTRA Research',
  description:
    '型付き射のアトラスを監査したところ、32ソート中18個が構造的に壊れていた。埋めたのは包含と標準的な構成の書き忘れだった。',
}

/** 記事本文の共通スタイル。背景の立体が透けるので、文字側は不透明の帯に載せない */
const P = 'mt-6 text-[14px] leading-8 text-zinc-300'
const H = 'mt-16 text-[19px] font-semibold text-zinc-100'
const CODE =
  'mt-6 overflow-x-auto rounded-sm border border-zinc-800 bg-black/70 p-5 text-[12px] leading-6 text-zinc-400 backdrop-blur'

export default function Article() {
  return (
    <>
      <ScrollSolid />
      <main className="relative min-h-[100dvh] text-zinc-100">
        <div className="mx-auto max-w-3xl px-6 py-28">
          <Link
            href="/mortra/research"
            className="text-[11px] tracking-[0.28em] text-zinc-600 hover:text-zinc-300"
          >
            ← RESEARCH
          </Link>

          <div className="mt-10 flex items-center gap-4 text-[10px] tracking-[0.2em] text-zinc-600">
            <span>2026-08-08</span>
            <span className="text-zinc-700">/</span>
            <span>測定</span>
            <span className="text-zinc-700">/</span>
            <span>実装・測定済み</span>
          </div>

          <h1 className="mt-6 text-[clamp(1.9rem,4.6vw,2.8rem)] font-semibold leading-tight">
            アトラスに足りなかったのは数学ではなかった
          </h1>

          <p className="mt-8 text-[15px] leading-8 text-zinc-400">
            型付き射のアトラスを監査したところ、32のソートのうち18個が構造的に壊れていた。
            埋めたのは新しい数学ではなく、包含と標準的な構成の書き忘れだった。
          </p>

          <h2 className={H}>仮説</h2>
          <p className={P}>
            MathOS は三角形の3辺から cos A を出せなかった。
            最初は「余弦定理の射が無いからだ」と考えた。だとすれば、
            足りない定理を1本ずつ射として足していけばよい。
          </p>
          <p className={P}>
            この仮説は間違っていた。そして間違い方が、設計の問題を露出させた。
          </p>

          <h2 className={H}>測ったこと</h2>
          <p className={P}>
            アトラスの各ソートについて、入次数（それを作る射の本数）と
            出次数（そこから出る射の本数）を数えた。
          </p>
          <div className={CODE}>
            <pre>{`射 37 / ソート 32

入次数0（誰も作れない）        12個
  Real, Triangle, Polynomial, Sequence,
  GeometricConfiguration, RationalSelfMap, …

出次数0（作った瞬間に行き止まり） 6個
  Scalar, Proposition, Matrix2, Quantity, …

健全                          14個`}</pre>
          </div>
          <p className={P}>
            <strong className="text-zinc-100">アトラス全体に、Real を作る射が1本も無かった。</strong>
            数を要求しているのに、この空間は数を生成できない。
            余弦定理が通らないのは当然で、原因は射の不足ではなく出口の欠落だった。
          </p>
          <p className={P}>
            さらに Scalar は入次数6・出次数0。6本の射が作るのに、誰も消費しない。
            アトラスはグラフではなく漏斗の形をしていた。
          </p>

          <h2 className={H}>埋めたもの</h2>
          <p className={P}>穴は2種類しかなかった。どちらも新しい数学ではない。</p>
          <div className={CODE}>
            <pre>{`(1) 包含の書き忘れ
    Scalar     ⊂ Real
    Quantity   ⊂ Real
    Polynomial ⊂ DifferentiableFunction   多項式は微分可能
    Triangle   ⊂ GeometricConfiguration

(2) 標準的な構成の書き忘れ
    Matrix2    → Polynomial        特性多項式
    Matrix2    → RationalSelfMap   Möbius変換
    Integer    → PrimeSpectrum     素因数分解`}</pre>
          </div>
          <p className={P}>
            包含を1本引くと、出次数0のソートと入次数0のソートが同時に埋まる。
            だから効率が良い。
          </p>

          <h2 className={H}>結果</h2>
          <div className={CODE}>
            <pre>{`             射    欠陥        到達
素        37    18/32 (56%)   2/16
修復後    57     0/32  (0%)  16/16`}</pre>
          </div>
          <p className={P}>
            幾何を狙って直したのに、複素数・整数・漸化式・不等式・解析・領域・組合せが開いた。
            経路を見ると、使われていた射の多くは<strong className="text-zinc-100">元からアトラスにあったもの</strong>だった。
            出口が無かったせいで眠っていただけで、橋を架けた途端に生き返った。
          </p>

          <h2 className={H}>暗記ではないことの確認</h2>
          <p className={P}>
            射を足して解ける問題が増えても、それが「その問題専用の射を足しただけ」なら暗記である。
            そこで leave-one-out で測った。射を1本抜き、
            その射を足す動機になった問題<em>以外</em>が落ちるかを見る。
          </p>
          <div className={CODE}>
            <pre>{`ScalarAsReal          落ちる4問  うち動機以外 4  → 語彙
OrderComparison       落ちる1問  うち動機以外 0  → 単機能
MobiusRealization     落ちる1問  うち動機以外 0  → 単機能
他7本                 落ちる0問                  → 冗長`}</pre>
          </div>
          <p className={P}>
            この測定は、先に書いた「8本の射で8分野が開いた」という主張を否定した。
            実際には <code className="text-zinc-100">ScalarAsReal</code> 1本がほぼ全部を開けている。
            そしてそれは射の追加ではなく、ソート設計の誤りの是正だった。
          </p>

          <h2 className={H}>限界</h2>
          <p className={P}>
            <strong className="text-zinc-100">到達は難易度と無関係である。</strong>
            型の上で Triangle から Real への経路があることと、問題が解けることは別。
          </p>
          <p className={P}>
            実際に経路を実行して答えが合ったのは、導出が座標3行で書ける水準のものだけだった
            （6例で一致、余弦定理は一行も書かずに 11/14 を出した）。
            着想を要する問題は、型が到達しても導出が出てこない。
          </p>

          <h2 className={H}>次の実験</h2>
          <p className={P}>
            自作問題集82問を形式化し、導出の性質を三段階に分ける。
            機械的（計算だけで出る）／定型の着想（既知の手筋）／非定型の着想（その問題固有のひらめき）。
            現在できるのは一段目だけなので、二段目がどれだけ射の語彙で届くかが次の測定対象になる。
          </p>

          <div className="mt-24 border-t border-zinc-900 pt-8 text-[12px] leading-7 text-zinc-600">
            この記事に出てくる数字はすべて実行して得たもの。
            推定値や見込みは含めていない。
          </div>
        </div>
      </main>
    </>
  )
}
