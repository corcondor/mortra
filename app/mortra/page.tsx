/**
 * MORTRA 公開サイト。
 *
 * Sakumon とは役割が違うので、UI も分ける。
 *
 *   MORTRA   静か / 余白 / 研究所 / 黒 / ログイン不要 / 一画面に一つの主張
 *   Sakumon  密度 / 速度 / キーボード / 業務 / ログインの内側
 *
 * Adobe の本体サイトと Photoshop の UI が同じでないのと同じ理由。
 *
 * ここに置く主張は一つだけ。
 *   同じ構造が、式にも図にも行列にも漸化式にも領域にも運動にもなる。
 *   MORTRA はその間を移動する。
 *
 * 「Try MORTRA」は Sakumon の管理画面へ直行させない。
 * まず技術を体験させ、そのあとで「これで問題を作りたいなら Sakumon へ」と分ける。
 */
import Link from 'next/link'

export const metadata = {
  title: 'MORTRA — One structure. Many representations.',
  description:
    '数学の同じ構造を、式・図・行列・漸化式・領域・運動のあいだで移動させる研究基盤です。',
}

/** 一つの構造が取りうる姿。ここが MORTRA の主張そのもの */
const SECTIONS = [
  {
    href: '/mortra/research',
    kicker: 'Research',
    title: '見つけたこと、作ったこと',
    body: '仮説・実装・ベンチマーク・限界・次の実験を分けて書きます。',
  },
  {
    href: '/mortra/vision',
    kicker: 'Vision',
    title: '数学は文章に閉じ込められている',
    body:
      '人は figure を描き、座標を変え、模型を替えて考えます。'
      + '推論の一部は、表現のあいだを移動することだという仮説。',
  },
  {
    href: '/robot',
    kicker: 'Demos',
    title: '6軸アームが定理を描く',
    body:
      '証明された境界を、なぞらずに描きます。'
      + 'ペン先の位置と姿勢から逆運動学を閉形式で解いています。',
  },
  {
    href: '/mortra/try',
    kicker: 'Try',
    title: '構造 → 表現の経路 → 証明 → 図',
    body: '問題を一つ入れて、MORTRA が何をするのかを見てください。',
  },
]

export default function MortraPage() {
  return (
    <main className="min-h-[100dvh] bg-black text-zinc-100">
      {/* 主張は一画面に一つ。上半分で「使える物だ」と伝える */}
      <section className="mx-auto flex min-h-[78dvh] max-w-5xl flex-col justify-center px-6 py-24">
        <p className="text-[11px] tracking-[0.34em] text-zinc-600">MORTRA</p>
        <h1 className="mt-8 text-[clamp(2.2rem,7vw,4.6rem)] font-semibold leading-[1.06] tracking-tight">
          One structure.
          <br />
          <span className="text-zinc-500">Many representations.</span>
        </h1>
        <p className="mt-10 max-w-xl text-[15px] leading-8 text-zinc-400">
          同じ数学的構造が、式にも、図にも、行列にも、漸化式にも、領域にも、
          そして物理的な運動にもなります。MORTRA はその構造を見つけ、
          意味を保ったまま、有用な表現へ移します。
        </p>

        <div className="mt-16 flex flex-wrap items-center gap-4">
          <Link
            href="/mortra/try"
            className="rounded-sm border border-zinc-100 px-7 py-3 text-[13px] tracking-wide text-zinc-100 transition hover:bg-zinc-100 hover:text-black"
          >
            Try MORTRA
          </Link>
          <Link
            href="/mortra/research"
            className="rounded-sm border border-zinc-800 px-7 py-3 text-[13px] tracking-wide text-zinc-400 transition hover:border-zinc-600 hover:text-zinc-100"
          >
            Explore research
          </Link>
        </div>
      </section>

      <div className="mx-auto max-w-5xl px-6">
        <div className="h-px bg-zinc-900" />
      </div>

      <section className="mx-auto max-w-5xl px-6 py-24">
        <div className="grid gap-x-12 gap-y-16 md:grid-cols-2">
          {SECTIONS.map((s) => (
            <Link key={s.href} href={s.href} className="group block">
              <p className="text-[10px] tracking-[0.28em] text-zinc-600">
                {s.kicker.toUpperCase()}
              </p>
              <h2 className="mt-4 text-[22px] font-medium leading-snug text-zinc-100 transition group-hover:text-white">
                {s.title}
              </h2>
              <p className="mt-3 text-[13px] leading-7 text-zinc-500">{s.body}</p>
            </Link>
          ))}
        </div>
      </section>

      {/* 製品への導線。技術を見せてから、仕事の道具へ渡す */}
      <section className="border-t border-zinc-900">
        <div className="mx-auto max-w-5xl px-6 py-24">
          <p className="text-[10px] tracking-[0.28em] text-zinc-600">PRODUCTS</p>
          <h2 className="mt-6 text-[clamp(1.6rem,4vw,2.4rem)] font-medium leading-tight">
            これで問題を作りたいなら
          </h2>
          <div className="mt-10 flex flex-col gap-6 border border-zinc-900 p-8 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="text-[19px] font-semibold">
                Sakumon <span className="text-[12px] font-normal tracking-[0.14em] text-zinc-500">by MORTRA</span>
              </p>
              <p className="mt-2 max-w-md text-[13px] leading-7 text-zinc-500">
                塾講師・教員・作問者のための作業場。種を選び、生成し、検証し、
                比べ、直し、図にし、書き出すまで。
              </p>
            </div>
            <Link
              href="/"
              className="shrink-0 rounded-sm border border-zinc-700 px-6 py-3 text-[13px] text-zinc-200 transition hover:border-zinc-400"
            >
              Open Sakumon →
            </Link>
          </div>
        </div>
      </section>

      <footer className="border-t border-zinc-900">
        <div className="mx-auto flex max-w-5xl flex-wrap items-center justify-between gap-4 px-6 py-10 text-[11px] text-zinc-600">
          <span className="tracking-[0.24em]">MORTRA</span>
          <span>morphism + semantic transport</span>
        </div>
      </footer>
    </main>
  )
}
