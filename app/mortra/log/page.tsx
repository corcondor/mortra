import Link from 'next/link'

/*
 * 研究ログ。
 *
 * 「いつ何をやったか」を5分で読める長さで書く。
 * これ1本が、そのまま note にも X にも Instagram にも流用できる形にする。
 * 媒体ごとに書き分けない。切り出す長さが違うだけ。
 *
 * Taste Skill の規則に従う:
 *   Inter を既定にしない / h-screen を使わない（min-h-[100dvh]）
 *   中央寄せヒーロー＋暗いメッシュを避ける
 *   等分の3カードを避ける
 *   flex の割合計算ではなく CSS Grid
 */

export const metadata = {
  title: 'Research log — MORTRA',
  description: '何を測り、何が壊れていて、何を直したか。日付順の記録。',
}

type Entry = {
  date: string
  title: string
  /** 5分で読める要約。ここだけで意味が通るように書く */
  summary: string[]
  numbers: Array<{ label: string; before?: string; after: string }>
  /** 媒体へ切り出すときの一行目 */
  hook: string
  media?: string
}

const LOG: Entry[] = [
  {
    date: '2026-08-10',
    title: '型の穴を埋めたら、狙っていない分野が開いた',
    hook: '37 morphisms. 18 of 32 types were structurally broken.',
    summary: [
      '型付き射のアトラスで、各ソートの入次数と出次数を数えた。'
      + '32個のうち18個が壊れていた。誰も作れないソートが12個、'
      + '作った瞬間に行き止まりになるソートが6個。',
      'とくに Real は入次数0だった。つまりアトラス全体に、数を生成する射が1本も無い。'
      + '三角形の3辺から cos A を出せなかったのは、余弦定理が無いからではなく、'
      + '数そのものを作れなかったからだった。',
      '埋めたのは新しい数学ではない。Scalar ⊂ Real、Polynomial ⊂ DifferentiableFunction、'
      + 'Matrix2 → 特性多項式、Integer → 素因数分解。'
      + 'どれも書き忘れであって、発明ではない。',
      '包含を1本引くと、出次数0のソートと入次数0のソートが同時に埋まる。'
      + '幾何を狙って直したのに、複素数・整数・漸化式・不等式・解析・領域・組合せが開いた。'
      + '使われた射の多くは元からあったもので、出口が無くて眠っていただけだった。',
      'ただし leave-one-out で測ると、実際に効いていたのは ScalarAsReal 1本だった。'
      + '残りは冗長か単機能。「8本で8分野が開いた」という最初の主張は誇大だった。',
    ],
    numbers: [
      { label: '射', before: '37', after: '57' },
      { label: '構造的欠陥', before: '18 / 32', after: '0 / 32' },
      { label: '型の上の到達', before: '2 / 16', after: '16 / 16' },
      { label: 'cos A の実行一致', after: '5 / 5' },
    ],
  },
  {
    date: '2026-08-10',
    title: '余弦定理を書かずに、余弦定理を出す',
    hook: 'The law of cosines, without writing the law of cosines.',
    summary: [
      '与えたのは3つだけ。三角形を座標に置くこと、ノルムの定義、内積による角の定義。'
      + '定理は一行も書いていない。',
      '消去を走らせると cos A が返る。AB=7, BC=5, CA=3 で 11/14。'
      + '同じ経路が cos B も cos C も返し、別の三角形でも通る。5例すべて一致。',
      '定理を射として持たせると、その1問専用になる。'
      + '代わりに「三角形の計量量が満たす関係式のイデアル」を射にした。'
      + '余弦定理はそこから落ちてくる帰結になる。',
    ],
    numbers: [
      { label: '一致', after: '5 / 5' },
      { label: '書いた定理', after: '0' },
    ],
  },
  {
    date: '2026-08-10',
    title: '9つの述語は幾何専用ではなかった',
    hook: 'AlphaGeometry の座標は、実装のコメントに書いてある。',
    summary: [
      'AlphaGeometry の ar.py には RatioTable = "Coefficient matrix A for log(distance)" とある。'
      + '長さは対数で線形化されている。推測ではなく実装がそう言っている。',
      '同じ仕掛けは幾何に固有ではない。複素数は log|z| と arg z、'
      + '整数は p進付値、漸化式は特性根の対数。どれも乗法構造を加法に落とすと線形になる。',
      '境界も理論から出る。加法と乗法を同時に線形にする座標は存在しない。'
      + '存在すれば Hilbert の第10問題が決定可能になってしまう。',
      '実測でも漏れている。AlphaGeometry 単独 25/30 に対し、'
      + '非線形消去（Wu の方法）を足すと 27/30。線形枠だけでは届かない問題がある。',
    ],
    numbers: [
      { label: 'AG の言語カバー率', before: '66%', after: '88%' },
      { label: 'AG の解答率', before: '54%', after: '84%' },
    ],
  },
]

export default function LogPage() {
  return (
    <main className="min-h-[100dvh] bg-[#08090a] text-zinc-100 antialiased">
      {/* 中央寄せの巨大ヒーローを避け、左揃えの帯にする */}
      <header className="border-b border-white/[0.06]">
        <div className="mx-auto grid max-w-6xl grid-cols-1 gap-8 px-6 py-20 md:grid-cols-[1.4fr_1fr] md:py-28">
          <div>
            <Link href="/mortra" className="text-[11px] tracking-[0.3em] text-zinc-600 transition hover:text-zinc-300">
              MORTRA
            </Link>
            <h1 className="mt-8 text-4xl font-medium leading-none tracking-tighter md:text-6xl">
              Research log
            </h1>
            <p className="mt-8 max-w-[52ch] text-[15px] leading-relaxed text-zinc-400">
              何を測り、何が壊れていて、何を直したか。日付順に置いています。
              数字はすべて実行して得たもので、見込みは含みません。
            </p>
          </div>
          <div className="flex items-end">
            <p className="text-[13px] leading-relaxed text-zinc-600">
              うまくいかなかった実験も同じ場所に載せます。
              自分の主張が測定に否定された記録も残します。
            </p>
          </div>
        </div>
      </header>

      {LOG.map((e, i) => (
        <article key={i} className="border-b border-white/[0.06]">
          <div className="mx-auto grid max-w-6xl grid-cols-1 gap-10 px-6 py-16 md:grid-cols-[1fr_2fr] md:py-24">
            {/* 左に日付と数字。右に本文。等分にしない */}
            <div>
              <p className="text-[11px] tracking-[0.24em] text-zinc-600">{e.date}</p>
              <dl className="mt-8 space-y-5">
                {e.numbers.map((n) => (
                  <div key={n.label}>
                    <dt className="text-[11px] tracking-wider text-zinc-600">{n.label}</dt>
                    <dd className="mt-1 font-mono text-[15px] text-zinc-200">
                      {n.before && (
                        <>
                          <span className="text-zinc-600 line-through decoration-zinc-700">{n.before}</span>
                          <span className="mx-2 text-zinc-700">→</span>
                        </>
                      )}
                      {n.after}
                    </dd>
                  </div>
                ))}
              </dl>
            </div>

            <div>
              <h2 className="text-2xl font-medium leading-tight tracking-tight md:text-3xl">
                {e.title}
              </h2>
              <div className="mt-8 space-y-5">
                {e.summary.map((p, j) => (
                  <p key={j} className="max-w-[62ch] text-[15px] leading-[1.9] text-zinc-300">
                    {p}
                  </p>
                ))}
              </div>
              {/* 媒体へ切り出すときの一行目。同じ内容を X にも note にも流す */}
              <p className="mt-10 border-l-2 border-zinc-700 pl-4 font-mono text-[12px] leading-relaxed text-zinc-500">
                {e.hook}
              </p>
            </div>
          </div>
        </article>
      ))}

      <footer className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-4 px-6 py-16 text-[11px] text-zinc-600">
        <span className="tracking-[0.24em]">MORTRA</span>
        <Link href="/" className="transition hover:text-zinc-300">Sakumon →</Link>
      </footer>
    </main>
  )
}
