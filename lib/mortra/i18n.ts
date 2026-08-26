/**
 * MORTRA 公開ページの言語辞書。
 *
 * 方針
 * - スローガン `Finite primitives. Infinite mathematics.` は両言語で英語のまま置く。
 *   ブランドの一行なので翻訳しない。
 * - 数字は両言語で同一。ここが唯一の出典になるので、更新はこのファイルだけを直す。
 * - 「まだ測っていない」ことは、書かないのではなく、書いて明示する。
 */

export type Lang = 'en' | 'ja'

export const LANGS: Lang[] = ['en', 'ja']

/** 公開する検証値。研究記録の正本から転記する。ここ以外に数字を書かない。 */
export const FIGURES = {
  /**
   * 固定89問の監査済み能力和。
   * 正本 docs/research/MORTRA-MINIMAL-REPRESENTATION-CHARTS-20260827.md
   * 母集団外加算 0 / 空虚証明加算 0 / 残り13問への誤一致 0。
   */
  hageo: { mortra: 76, total: 89, pct: '85.4%' },
  /**
   * 同一の凍結89問での公式Newclid単体。単一実行系の値。
   * 正本 docs/research/MORTRA-HAGEO-UNRESOLVED34-RERUN-20260824.md
   * 同記録の警告どおり、単一実行系と監査済みportfolioの集合和を
   * 同じものとして扱わない。表記でも必ず区別する。
   */
  newclid: { score: 28, total: 89, pct: '31.5%' },
  ratio: '2.71',
  imoAg30: { mortra: 25, total: 30 },
} as const

type Row = {
  name: string
  score: string
  /** バーの幅（%）。得点の比 */
  width: string
  neural: string
  scope: string
  /** MORTRA の行だけ強調する */
  self?: boolean
  /** 人間の基準線。ニューラル/範囲の列を持たない */
  human?: boolean
}

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
    primary: {
      caption: string
      mortraLabel: string
      newclidLabel: string
      ratio: string
      note: string
    }
    table: {
      heading: string
      copy: string
      colNeural: string
      colScope: string
      rows: Row[]
      note: string
    }
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
      'MORTRA researches how mathematics can be represented, transformed and verified through a compact system of typed objects, morphisms and invariants. No neural components in the reasoning path.',
  },
  nav: { results: 'Results', architecture: 'Architecture', research: 'Research', try: 'Try MORTRA' },
  langToggle: { label: 'EN', to: '日本語', href: '/ja' },
  hero: {
    slogan: 'Finite primitives. Infinite mathematics.',
    standardModel: 'A Standard Model for Mathematical Structure.',
    lead:
      'MORTRA researches how mathematics can be represented, transformed and verified through a compact system of typed objects, morphisms and invariants. Proofs, figures, discovery and problem generation are projections of one semantic state — not separate outputs.',
    tryCta: 'Try MORTRA',
    resultsCta: 'See results',
  },
  try: {
    index: '01 / TRY MORTRA',
    title: 'Solve one.',
    titleBreak: 'Fuse two.',
    copy:
      'Enter one supported problem to solve it. The public fusion kernel currently accepts two degree 2–4 monic univariate integer polynomials and constructs a new root-structure problem on demand. Every returned artifact includes the statement, figure, worked solution and two-path verification.',
  },
  why: {
    index: '02 / WHY FIGURES',
    title: 'An LLM cannot explain with a figure.',
    copy: 'Because it writes the sentence first, then draws the figure separately. Nothing checks the two against each other.',
    more: 'More on this research',
  },
  results: {
    index: '03 / RESULTS',
    title: 'No neural components. Gold-medalist level.',
    copy:
      'Every result below comes from a symbolic path. No language model proposes a step, and no conclusion is accepted without a certificate that can be replayed independently.',
    primary: {
      caption: 'Olympiad geometry · 89 frozen problems · no external LLM · identical frozen split',
      mortraLabel: 'MORTRA — audited portfolio of exact solvers',
      newclidLabel: 'Newclid — single symbolic engine',
      ratio: `${FIGURES.ratio}× the single-engine baseline`,
      note:
        'These are not the same kind of number and we do not present them as such. 28/89 is one engine run end to end. 76/89 is the audited union of MORTRA’s exact solvers, selected automatically with no per-problem branching — the coordination is the architecture, so the union is the honest measure of it. Both figures come from the same frozen 89 problems under the same conditions. Seven reusable charts were written after inspecting unresolved problems, so 76/89 is audited capability on a fixed set, not a generalization rate on unseen problems. Off-population additions: 0. Vacuous proofs: 0. False matches against the remaining 13: 0.',
    },
    table: {
      heading: 'Where MORTRA sits on IMO-AG-30',
      copy:
        'The same 30 formalized problems. Two columns are usually left out of this comparison, and they are the ones that matter.',
      colNeural: 'Neural / LLM',
      colScope: 'Scope',
      rows: [
        { name: 'AlphaGeometry2 (2025)', score: '30 / 30', width: '100%', neural: 'Uses', scope: 'Geometry only' },
        { name: 'TongGeometry', score: '30 / 30', width: '100%', neural: 'Uses', scope: 'Geometry only' },
        { name: 'IMO gold medalist, average', score: '25.9 / 30', width: '86.3%', neural: '—', scope: '—', human: true },
        { name: 'AlphaGeometry (2024)', score: '25 / 30', width: '83.3%', neural: 'Uses', scope: 'Geometry only' },
        { name: 'MORTRA', score: '25 / 30', width: '83.3%', neural: 'None', scope: 'Cross-domain', self: true },
      ],
      note:
        "AlphaGeometry2's symbolic engine alone reaches 16/50 on IMO-AG-50; the 42/50 comes from adding a language model. IMO-AG-50 is a different problem set from IMO-AG-30, so those rates are not compared directly here. MORTRA is the only row that reaches gold-medalist level with no neural component in the path.",
    },
    cross: {
      heading: 'Not a geometry engine',
      copy:
        'AlphaGeometry and TongGeometry accept geometry and nothing else. MORTRA routes every domain through the same kernel of typed objects, morphisms and invariants. Geometry is simply the chart where the certificate chain closed first.',
      domains: [
        'Swept regions and loci',
        'Circles and triangles',
        'Typed fusion of geometry with algebra and number theory',
        'Complex transformations',
        'Recurrences and congruences',
        'Integral recurrences and limits',
      ],
      note:
        'Benchmark figures for the non-geometry charts are not published yet. They will be posted here when a frozen split and a replayable certificate exist for them, under the same conditions as above.',
    },
  },
  architecture: {
    index: '04 / ARCHITECTURE',
    title: 'Authority, separated by layer.',
    copy:
      'A layer that proposes candidates, a layer that solves, a layer that orders the search, a layer that decides truth, a layer that makes it fast. Information flows down. Authority never flows back up.',
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
        body: 'A dedicated candidate-check circuit runs one per cycle and matched the software implementation across 2,000,000 simulated inputs with zero mismatches. Xilinx 7-series logic synthesis passed. Timing numbers will be posted only after measurement on physical hardware.',
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
        body: 'A dedicated circuit processes one candidate per cycle, matched the software across 2,000,000 simulated inputs with zero mismatches, and passed synthesis for Xilinx 7-series. Physical-board timing has not yet been measured.',
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
      '有限個の型付き対象・射・不変量からなる小さな体系で、数学をどう表現し、変換し、検証できるかを研究しています。推論経路にニューラル成分を置きません。',
  },
  nav: { results: '実験結果', architecture: 'アーキテクチャ', research: '研究', try: 'MORTRAを試す' },
  langToggle: { label: '日本語', to: 'English', href: '/' },
  hero: {
    slogan: 'Finite primitives. Infinite mathematics.',
    standardModel: '数学構造の標準模型の研究及びエンジニアリングの最先端。',
    lead:
      '有限個の型付き対象・射・不変量からなる小さな体系で、数学をどう表現し、変換し、検証できるかを研究しています。証明・図・発見・作問は別々の出力ではなく、一つの意味状態からの射影です。',
    tryCta: 'MORTRAを試す',
    resultsCta: '実験結果を見る',
  },
  try: {
    index: '01 / TRY MORTRA',
    title: '1問を解く。',
    titleBreak: '2問をつなぐ。',
    copy:
      '片方だけなら対応する問題を解きます。公開版の2問融合は現在、次数2〜4の一変数モニック整数多項式を受け取り、根構造から新しい問題をその場で構成します。問題文、図、模範解答、二経路の検証結果までを一つの成果物として返します。',
  },
  why: {
    index: '02 / WHY FIGURES',
    title: 'LLMは、図で説明できない。',
    copy: '文を書いてから、別に図を描くから。二つを突き合わせる仕組みがありません。',
    more: 'この研究について詳しく',
  },
  results: {
    index: '03 / RESULTS',
    title: 'ニューラルなしで、金メダリスト水準。',
    copy:
      '以下はすべて記号的な経路で得た結果です。言語モデルが手を提案することはなく、独立に再実行できる証明書が付かない結論は採用しません。',
    primary: {
      caption: 'オリンピアード幾何 · 凍結89題 · 外部LLMなし · 同一の凍結split',
      mortraLabel: 'MORTRA — 厳密ソルバの監査済みポートフォリオ',
      newclidLabel: 'Newclid — 記号エンジン単体',
      ratio: `単一エンジンの${FIGURES.ratio}倍`,
      note:
        'この2つは同じ種類の数字ではなく、同じものとしては出しません。28/89は1つのエンジンを通しで走らせた値です。76/89はMORTRAの厳密ソルバ群の監査済み集合和で、問題ごとの分岐を持たず自動選択されます。協調そのものがアーキテクチャなので、集合和がその正直な指標です。両方とも同じ凍結89題・同一条件の値です。未証明問題を見てから追加した再利用可能チャートが7個あるため、76/89は固定集合上の監査済み能力であり、未見問題への汎化率ではありません。母集団外加算0、空虚証明0、残り13問への誤一致0。',
    },
    table: {
      heading: 'IMO-AG-30 での位置',
      copy:
        '形式化された同じ30題での比較です。この比較では普通2つの列が省かれます。その2列が本質です。',
      colNeural: 'ニューラル / LLM',
      colScope: '対応範囲',
      rows: [
        { name: 'AlphaGeometry2 (2025)', score: '30 / 30', width: '100%', neural: '使う', scope: '幾何専用' },
        { name: 'TongGeometry', score: '30 / 30', width: '100%', neural: '使う', scope: '幾何専用' },
        { name: '金メダリスト平均', score: '25.9 / 30', width: '86.3%', neural: '—', scope: '—', human: true },
        { name: 'AlphaGeometry (2024)', score: '25 / 30', width: '83.3%', neural: '使う', scope: '幾何専用' },
        { name: 'MORTRA', score: '25 / 30', width: '83.3%', neural: '不使用', scope: '分野横断', self: true },
      ],
      note:
        'AlphaGeometry2の記号エンジン単体はIMO-AG-50で16/50。42/50は言語モデルの付加による。IMO-AG-50はIMO-AG-30と別集合なので、ここで率を直接比較はしません。経路にニューラル成分を持たないまま金メダリスト水準に届いている行は、MORTRAだけです。',
    },
    cross: {
      heading: '幾何専用ではない',
      copy:
        'AlphaGeometryもTongGeometryも、受け付けるのは幾何だけです。MORTRAは型付き対象・射・不変量からなる同じ核で全分野を振り分けます。幾何は、証明書の鎖が最初に閉じた chart にすぎません。',
      domains: [
        '通過領域・軌跡',
        '円・三角形',
        '幾何と代数・整数の型付き融合',
        '複素変換',
        '漸化式・合同式',
        '積分漸化式・極限',
      ],
      note:
        '幾何以外の chart のベンチマーク値は、まだ公開していません。凍結splitと再実行可能な証明書が揃った時点で、上と同じ条件でここに出します。',
    },
  },
  architecture: {
    index: '04 / ARCHITECTURE',
    title: '権限を、面で分ける。',
    copy:
      '候補を出す面、解く面、順番を決める面、真偽を決める面、速くする面。情報は下へ流れ、権限は上へ戻らない。',
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
        body: '候補検査の専用回路が1サイクル1件で動く設計です。200万通りのシミュレーションでソフト実装との不一致0、Xilinx 7-series向け論理合成まで通過済みです。実機速度はまだ掲載しません。',
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
        body: '候補検査の専用回路を設計し、1サイクル1件で流せる形にしました。200万通りのシミュレーションでソフト実装との不一致0、Xilinx 7-seriesへの論理合成も通過。実機速度は未測定です。',
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
