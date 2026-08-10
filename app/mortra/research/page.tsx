import Link from 'next/link'
import ScrollSolid from '@/components/ScrollSolid'

export const metadata = {
  title: 'Research — MORTRA',
  description: '数学の構造を見つけ、表現のあいだを移す研究。',
}

/*
 * 記事は「分野」で束ねる。記事の種類（測定・失敗・調査）では分けない。
 *
 * 題は成果の断定形にする。「何を測った」ではなく「何が言えるか」。
 * 現時点でできるかどうかは、来月には変わる。だから原理を書く。
 * 能力の点数表は記事の主題にしない。
 *
 * 限界を書くのは、それが原理的な境界であるときだけ。
 * 「加法と乗法を同時に線形にする座標は存在しない」は原理なので書く。
 * 「今は7問中1問しか解けない」は状態なので書かない。
 */

type Article = {
  slug: string
  title: string
  tag: string
  date: string
  minutes: number
  lead?: string
}

type Area = {
  id: string
  name: string
  description: string
  articles: Article[]
}

const AREAS: Area[] = [
  {
    id: 'vocabulary',
    name: '語彙と構造',
    description:
      '数学の知識が増えても、原始的な語彙は増えなくてよい。'
      + '増えるのは構造・射・合成である。この原則がどこまで成り立つのかを調べています。',
    articles: [
      {
        slug: 'finite-vocabulary',
        title: '有限の語彙で、幾何は書ける',
        tag: '語彙',
        date: '2026年8月8日',
        minutes: 9,
        lead:
          'Tarski の初等幾何は「間にある」と「合同」の2つの述語だけで書けて、しかも決定可能である。'
          + '語彙を足すことと、知識が増えることは同じではない。',
      },
      {
        slug: 'atlas-audit',
        title: '構造の欠陥を埋めると、無関係な分野が同時に開く',
        tag: '構造',
        date: '2026年8月8日',
        minutes: 7,
        lead:
          '型付き射のアトラスで、ある型を作る射が1本も無かった。'
          + '包含を1本引いただけで、幾何・複素数・整数・漸化式・解析が同時に到達可能になった。',
      },
      {
        slug: 'not-memorization',
        title: '射を足すことは、解法を覚えることではない',
        tag: '汎化',
        date: '2026年8月8日',
        minutes: 11,
        lead:
          'n本の射は深さ d で組合せ的に到達範囲を広げる。n個の暗記は n個しか解かない。'
          + 'その差を、足した動機と違う問題に効いたかで測る。',
      },
    ],
  },
  {
    id: 'representation',
    name: '表現の移動',
    description:
      '同じ構造が、式にも図にも行列にも漸化式にも領域にもなる。'
      + '意味を保ったまま、その間を移す仕組みを作っています。',
    articles: [
      {
        slug: 'log-linearization',
        title: '対数を座標に取ると、分野が消える',
        tag: '線形化',
        date: '2026年8月8日',
        minutes: 12,
        lead:
          '幾何の長さ、複素数の絶対値、整数の素因数、漸化式の特性根。'
          + 'どれも対数を取れば加法になり、同じ線形代数に乗る。境界は加法と乗法の同時線形化にある。',
      },
      {
        slug: 'representation-routing',
        title: '表現のあいだを移すことは、既に数学の概念である',
        tag: '基礎',
        date: '2026年8月8日',
        minutes: 10,
        lead:
          '理論間の解釈、institution、函手的意味論。'
          + '「別の姿で見る」は既に厳密に定式化されている。MORTRA はそれを実装している。',
      },
    ],
  },
  {
    id: 'verification',
    name: '検証',
    description:
      '生成した対象が正しいことを、生成した経路とは独立に確かめます。'
      + '記号計算と数値走査とSMTを併用し、一致しないものは出口に到達させません。',
    articles: [
      {
        slug: 'exact-backends',
        title: '余弦定理を書かずに、余弦定理を出す',
        tag: '検証',
        date: '2026年8月8日',
        minutes: 6,
        lead:
          '三角形を座標に置き、内積で角を定義する。それだけから消去が cos A を返す。'
          + '定理を射として持たないので、同じ経路が三角形の任意の計量量に効く。',
      },
    ],
  },
  {
    id: 'geometry-motion',
    name: '幾何と運動',
    description:
      '図は説明の飾りではなく、同じ対象の別の姿です。'
      + '証明された境界を6軸アームの軌道に変換し、物理的に描かせています。',
    articles: [
      {
        slug: 'proof-to-motion',
        title: '証明された境界を、なぞらずに描く',
        tag: '運動',
        date: '2026年8月8日',
        minutes: 8,
        lead:
          'ペン先の位置と姿勢から逆運動学を閉形式で解き、関節角を最小ジャーク軌道で繋ぐ。'
          + '画面の線は、あらかじめ用意した図ではなく、腕が通った跡そのもの。',
      },
    ],
  },
]

/** 公開済みの記事だけリンクにする。器だけのものは灰色のまま置く */
const PUBLISHED = new Set(['atlas-audit'])

export default function ResearchIndex() {
  return (
    <>
      <ScrollSolid />
      <main className="relative min-h-screen text-zinc-100">
        {/* 使命を一段落。分野の見出しはその下 */}
        <section className="mx-auto max-w-3xl px-6 pb-16 pt-28">
          <Link
            href="/mortra"
            className="text-[11px] tracking-[0.28em] text-zinc-600 hover:text-zinc-300"
          >
            MORTRA
          </Link>
          <h1 className="mt-10 text-[clamp(2.2rem,5.5vw,3.4rem)] font-semibold leading-tight">
            Research
          </h1>
          <p className="mt-8 text-[17px] leading-9 text-zinc-300">
            数学の構造を見つけ、表現のあいだを移す
          </p>
          <p className="mt-6 max-w-xl text-[14px] leading-8 text-zinc-500">
            同じ構造が、式にも、図にも、行列にも、漸化式にも、領域にも、運動にもなります。
            私たちは、その構造を形式的に取り出し、意味を保ったまま有用な表現へ移す仕組みを作っています。
          </p>
        </section>

        {AREAS.map((area) => (
          <section key={area.id} className="border-t border-zinc-900">
            <div className="mx-auto max-w-3xl px-6 py-16">
              <h2 className="text-[22px] font-semibold text-zinc-100">{area.name}</h2>
              <p className="mt-4 max-w-xl text-[13px] leading-8 text-zinc-500">
                {area.description}
              </p>

              <div className="mt-12 space-y-12">
                {area.articles.map((a) => {
                  const live = PUBLISHED.has(a.slug)
                  const inner = (
                    <>
                      <h3
                        className={
                          'text-[20px] font-medium leading-snug '
                          + (live ? 'text-zinc-100 transition group-hover:text-white' : 'text-zinc-400')
                        }
                      >
                        {a.title}
                      </h3>
                      {a.lead && (
                        <p className="mt-3 text-[13px] leading-7 text-zinc-500">{a.lead}</p>
                      )}
                      <div className="mt-4 flex flex-wrap items-center gap-3 text-[11px] text-zinc-600">
                        <span>{a.tag}</span>
                        <span className="text-zinc-800">·</span>
                        <span>{a.date}</span>
                        <span className="text-zinc-800">·</span>
                        <span>読了時間：{a.minutes}分</span>
                        {!live && (
                          <>
                            <span className="text-zinc-800">·</span>
                            <span className="text-zinc-700">準備中</span>
                          </>
                        )}
                      </div>
                    </>
                  )
                  return live ? (
                    <Link key={a.slug} href={`/mortra/research/${a.slug}`} className="group block">
                      {inner}
                    </Link>
                  ) : (
                    <div key={a.slug}>{inner}</div>
                  )
                })}
              </div>
            </div>
          </section>
        ))}

        <section className="border-t border-zinc-900">
          <div className="mx-auto max-w-3xl px-6 py-20">
            <p className="text-[10px] tracking-[0.28em] text-zinc-600">PRODUCTS</p>
            <h2 className="mt-6 text-[22px] font-medium">
              この研究は、作る道具になっています
            </h2>
            <Link
              href="/"
              className="mt-8 inline-block rounded-sm border border-zinc-700 px-6 py-3 text-[13px] text-zinc-200 transition hover:border-zinc-400"
            >
              Sakumon by MORTRA →
            </Link>
          </div>
        </section>
      </main>
    </>
  )
}
