/**
 * MORTRA 公開ページの言語辞書。
 *
 * 方針
 * - スローガン `Finite primitives. Infinite mathematics.` は両言語で英語のまま置く。
 *   ブランドの一行なので翻訳しない。
 * - 数字は両言語で同一。ここが唯一の出典になるので、更新はこのファイルだけを直す。
 * - 公開ページには検証済みの成果だけを書く。限界と失敗は研究記録で扱う。
 */

export type Lang = 'en' | 'ja'

export const LANGS: Lang[] = ['en', 'ja']

/** 公開する検証値。研究記録の正本から転記する。ここ以外に数字を書かない。 */
export const FIGURES = {
  /**
   * 固定89問の監査済み能力和。
   * 正本 docs/research/MORTRA-CODEX-FUSED-REMAINING11-CLOSURE-20260828.md
   */
  hageo: { mortra: 89, total: 89, pct: '100%' },
  replayedIdentities: { closed: 357, total: 357 },
  fpgaEquivalence: { matched: '2,000,000', total: '2,000,000' },
} as const

export type Copy = {
  htmlLang: string
  meta: { title: string; description: string }
  nav: { results: string; architecture: string; research: string; try: string }
  langToggle: { label: string; to: string; href: string }
  hero: {
    slogan: string
    standardModel: string
    lead: string
    tryCta: string
    resultsCta: string
  }
  try: { index: string; title: string; titleBreak: string; copy: string }
  why: { index: string; title: string; copy: string; more: string }
  results: {
    index: string
    title: string
    copy: string
    metrics: { value: string; label: string; body: string; tone: 'orange' | 'rose' | 'green' | 'blue' }[]
    cross: { heading: string; copy: string; domains: string[]; note: string }
  }
  architecture: {
    index: string
    title: string
    copy: string
    items: { title: string; body: string }[]
  }
  research: {
    index: string
    timeline: { date: string; title: string; body: string }[]
  }
  vision: { title: string; copy: string; chips: string[] }
  footer: { left: string; right: string }
}

const en: Copy = {
  htmlLang: 'en',
  meta: {
    title: 'MORTRA — Finite primitives. Infinite mathematics.',
    description:
      'MORTRA turns mathematical statements into typed structures, composes verifiable morphisms, and returns proofs, figures and certificates from the same execution.',
  },
  nav: { results: 'Results', architecture: 'Architecture', research: 'Research', try: 'Try MORTRA' },
  langToggle: { label: 'EN', to: '日本語', href: '/ja' },
  hero: {
    slogan: 'Finite primitives. Infinite mathematics.',
    standardModel: 'Executable mathematics, from statement to certificate.',
    lead:
      'A mathematical operating system that turns a statement into typed structure, composes morphisms, and returns the proof, figure and certificate from one execution.',
    tryCta: 'Try MORTRA',
    resultsCta: 'See results',
  },
  try: {
    index: '01 / TRY MORTRA',
    title: 'Solve one.',
    titleBreak: 'Fuse two.',
    copy:
      'Enter one problem for a worked solution, or two compatible problems for a new fused problem. The result keeps the statement, figure, derivation route, worked solution and certificate together.',
  },
  why: {
    index: '02 / WHY FIGURES',
    title: 'The figure is part of the proof.',
    copy: 'In geometry, probability and calculus, drawing is a mathematical operation. MORTRA builds the figure from the same typed state used by the proof.',
    more: 'More on this research',
  },
  results: {
    index: '03 / RESULTS',
    title: 'A result you can replay.',
    copy:
      'The public path is symbolic. Every accepted conclusion carries its derivation route and a replayable certificate.',
    metrics: [
      { value: `${FIGURES.hageo.mortra} / ${FIGURES.hageo.total}`, label: 'Audited geometry cohort', body: 'All 89 problems close with replayable proof artifacts.', tone: 'orange' },
      { value: `${FIGURES.replayedIdentities.closed} / ${FIGURES.replayedIdentities.total}`, label: 'Replayed identities', body: 'Every exact identity in the final eleven geometry proofs reduced to zero.', tone: 'rose' },
      { value: 'SHA-256', label: 'Proof identity', body: 'Statement, figure, derivation and execution are bound to one certificate.', tone: 'green' },
      { value: `${FIGURES.fpgaEquivalence.matched} / ${FIGURES.fpgaEquivalence.total}`, label: 'Circuit equivalence', body: 'Software and synthesized candidate-filter logic agreed on every simulated input.', tone: 'blue' },
    ],
    cross: {
      heading: 'Not a geometry engine',
      copy:
        'The same typed-object and morphism kernel also executes algebraic, discrete and analytic charts.',
      domains: [
        'Swept regions and loci',
        'Circles and triangles',
        'Typed fusion of geometry with algebra and number theory',
        'Complex transformations',
        'Recurrences and congruences',
        'Integral recurrences and limits',
      ],
      note:
        'Try MORTRA returns the executed route, not only the final expression.',
    },
  },
  architecture: {
    index: '04 / ARCHITECTURE',
    title: 'Many reasoners. One proof.',
    copy:
      'Deduction, coordinates, Wu and Groebner elimination retain their own mathematics, exchange certified intermediate facts, and close one proof graph.',
    items: [
      {
        title: 'Different methods, kept different',
        body: 'Deduction, coordinates, Wu characteristic sets and Groebner elimination are not forced into one method.',
      },
      {
        title: 'Intermediate results are shared',
        body: 'A fact proved by one method is converted into a form another method can consume, and the search continues.',
      },
      {
        title: 'Truth is decided by proof',
        body: 'Which paths to explore is decided cooperatively. Whether a conclusion holds is decided by a certificate, never by a vote.',
      },
      {
        title: 'The filter, put on silicon',
        body: 'A dedicated candidate-check circuit runs one per cycle, matched the software implementation across 2,000,000 simulated inputs, and passed Xilinx 7-series logic synthesis.',
      },
    ],
  },
  research: {
    index: '05 / RESEARCH',
    timeline: [
      {
        date: 'COORDINATION',
        title: 'Connecting different proof methods',
        body: 'Deduction, coordinates, Wu and Groebner elimination each reason their own way and consume each other’s intermediate results.',
      },
      {
        date: 'SELF-ORGANIZATION',
        title: 'From local decisions to a global solution',
        body: 'Rather than concentrating judgement in one large model, several reasoners exchange only what they need and advance toward the answer.',
      },
      {
        date: 'ADAPTIVE SEARCH',
        title: 'Depth only where it is needed',
        body: 'Start shallow, spend more only on the problems that resist. Avoid searching every candidate to the same depth.',
      },
      {
        date: 'HARDWARE',
        title: 'Candidate filtering, lowered to a circuit',
        body: 'A dedicated circuit processes one candidate per cycle, matched the software across 2,000,000 simulated inputs, and passed synthesis for Xilinx 7-series.',
      },
    ],
  },
  vision: {
    title: 'Building a standard model for mathematical structure.',
    copy:
      'An expression, a figure and a motion are the same structure seen from different sides. The solid below is not decoration — the cross-section polygon is computed every frame.',
    chips: [
      'One structure, as expression, figure or motion',
      'Experiments with a fixed fingerprint',
      'Derivation chains with named rules',
    ],
  },
  footer: { left: 'MORTRA / Model 1', right: 'Finite primitives. Infinite mathematics.' },
}

const ja: Copy = {
  htmlLang: 'ja',
  meta: {
    title: 'MORTRA — Finite primitives. Infinite mathematics.',
    description:
      'MORTRAは問題文を型付き数学構造へ変換し、証明経路・図・解答・再実行可能な証明書を一つの実行から生成する数学OSです。',
  },
  nav: { results: '実験結果', architecture: 'アーキテクチャ', research: '研究', try: 'MORTRAを試す' },
  langToggle: { label: '日本語', to: 'English', href: '/' },
  hero: {
    slogan: 'Finite primitives. Infinite mathematics.',
    standardModel: '問題文から証明書まで、数学を実行可能に。',
    lead:
      '問題を型付き構造へ変換し、複数の推論器が中間結果を交換する。答えだけでなく、使った射、途中式、図、証明書まで返します。',
    tryCta: 'MORTRAを試す',
    resultsCta: '実験結果を見る',
  },
  try: {
    index: '01 / TRY MORTRA',
    title: '1問を解く。',
    titleBreak: '2問をつなぐ。',
    copy:
      '1問なら解答を生成し、2問なら共通構造を抽出して融合問題を構成します。問題文、図、途中式、証明経路、証明書を一つの成果物として返します。',
  },
  why: {
    index: '02 / WHY FIGURES',
    title: '図も、証明の一部にする。',
    copy: '幾何、確率、微積では、図を描くこと自体が推論です。MORTRAは証明と同じ型付き状態から図を構成します。',
    more: 'この研究について詳しく',
  },
  results: {
    index: '03 / RESULTS',
    title: '解いた証拠まで、残す。',
    copy:
      '受理した結論には、証明経路と再実行可能な証明書が付属します。問題文、図、導出、実行結果をSHA-256で一つに結びます。',
    metrics: [
      { value: `${FIGURES.hageo.mortra} / ${FIGURES.hageo.total}`, label: '監査済み幾何', body: '89題すべてを再生可能な証明成果物で閉じました。', tone: 'orange' },
      { value: `${FIGURES.replayedIdentities.closed} / ${FIGURES.replayedIdentities.total}`, label: '再生恒等式', body: '最後の幾何11題に含まれる357本の厳密恒等式がすべて0へ閉じました。', tone: 'rose' },
      { value: 'SHA-256', label: '証明の同一性', body: '問題文、図、導出経路、実行結果を一つの証明書に固定します。', tone: 'green' },
      { value: `${FIGURES.fpgaEquivalence.matched} / ${FIGURES.fpgaEquivalence.total}`, label: '回路等価性', body: '候補検査回路とソフト実装が200万入力すべてで一致しました。', tone: 'blue' },
    ],
    cross: {
      heading: '幾何から、分野横断へ。',
      copy:
        '型付き対象・射・不変量からなる同じ核で、幾何、代数、整数、解析を接続します。',
      domains: [
        '通過領域・軌跡',
        '円・三角形',
        '幾何と代数・整数の型付き融合',
        '複素変換',
        '漸化式・合同式',
        '積分漸化式・極限',
      ],
      note:
        'MORTRAを試すと、最終結果だけでなく実行された射列も表示されます。',
    },
  },
  architecture: {
    index: '04 / ARCHITECTURE',
    title: '異なる証明器を、ひとつの証明へ。',
    copy:
      '演繹、座標、Wu法、Groebner消去が固有の数学を保ったまま、検証済みの中間結果を交換して一つの証明グラフを閉じます。',
    items: [
      {
        title: '別々の方法で考える',
        body: '図形の演繹、座標計算、Wu法、Groebner消去を、無理に一つの方法へ統一しません。',
      },
      {
        title: '途中結果を共有する',
        body: '一つの方法で証明できた事実を、別の方法でも使える形へ変換して先へ進みます。',
      },
      {
        title: '正しさは証明で決める',
        body: 'どの経路を調べるかは協調して決めますが、結論の正しさは多数決ではなく証明書で確認します。',
      },
      {
        title: '絞り込みを回路へ',
        body: '候補検査の専用回路を設計し、200万通りの入力でソフト実装との完全一致を確認。Xilinx 7-series向け論理合成まで通過しています。',
      },
    ],
  },
  research: {
    index: '05 / RESEARCH',
    timeline: [
      {
        date: 'COORDINATION',
        title: '異なる証明法をつなぐ',
        body: '演繹、座標、Wu法、Groebner消去が、それぞれの得意な方法で考え、途中結果を相互に利用します。',
      },
      {
        date: 'SELF-ORGANIZATION',
        title: '局所の判断から全体解へ',
        body: '一つの大きなモデルに判断を集中させず、複数の推論器が必要な情報だけを交換して答えへ進む方法を研究しています。',
      },
      {
        date: 'ADAPTIVE SEARCH',
        title: '必要な経路だけを深く探す',
        body: '簡単な探索から始め、解けない問題だけ計算を増やします。すべての候補を同じ深さまで調べる無駄を減らします。',
      },
      {
        date: 'HARDWARE',
        title: '探索の絞り込みを、回路に落とした',
        body: '候補検査の専用回路を設計し、200万通りの入力でソフト実装との完全一致を確認。Xilinx 7-seriesへの論理合成も通過しました。',
      },
    ],
  },
  vision: {
    title: '数学構造の標準模型をつくる。',
    copy:
      '式・図・運動を、一つの構造の別の見え方として持つ。下の立方体は飾りではありません。断面の多角形を毎フレーム計算しています。',
    chips: ['同じ構造を、式でも図でも運動でも', '指紋を固定した実験', '規則名つきの導出列'],
  },
  footer: { left: 'MORTRA / Model 1', right: 'Finite primitives. Infinite mathematics.' },
}

const DICT: Record<Lang, Copy> = { en, ja }

export function getCopy(lang: Lang): Copy {
  return DICT[lang]
}
