import type { Lang } from './i18n'

export type ResearchCommit = {
  sha: string
  message: string
  url: string
  date: string
  author: string
}

export const RESEARCH_REPOSITORY = {
  owner: 'corcondor',
  repo: 'mortra',
  branch: 'release/mortra-1-beta',
  url: 'https://github.com/corcondor/mortra',
} as const

export const FALLBACK_COMMITS: ResearchCommit[] = [
  {
    sha: '15193f9',
    message: 'design: refine MORTRA interface and rerun IMO benchmark',
    url: 'https://github.com/corcondor/mortra/commit/15193f9',
    date: '2026-08-30T16:22:56.000Z',
    author: 'MORTRA',
  },
  {
    sha: 'd4d4239',
    message: 'Wire theorem kernels through public solve pipeline',
    url: 'https://github.com/corcondor/mortra/commit/d4d4239',
    date: '2026-08-29T22:23:48.000Z',
    author: 'MORTRA',
  },
  {
    sha: '6dff757',
    message: 'Certify remaining HAGeo geometry cohort',
    url: 'https://github.com/corcondor/mortra/commit/6dff757',
    date: '2026-08-28T07:51:44.000Z',
    author: 'MORTRA',
  },
]

export const CERTIFIED_PROOF_REPLAY = {
  artifact: '2024VietnamTSTp5',
  theorem: 'incircle-contact-chord-circumtangents-isogonal-trace',
  chart: 'incircle-contact-chord-circumtangent-isogonality',
  goal: 'eqangle A S J S I S S T',
  identityCount: 26,
  certificate: 'de3428739823e63c65aca9b509ea139cf37e2aa7775781d2c96192558a67579c',
  figure: '/research/proof-2024-vietnam-tst.svg',
  steps: [
    {
      id: 'construct',
      engine: 'CONSTRUCTION',
      ja: '内心 I を辺 CA, AB へ射影し、接点 E, F を構成',
      en: 'Project the incenter I to CA and AB, constructing E and F',
      detail: 'foot(I, CA), foot(I, AB)',
    },
    {
      id: 'polar',
      engine: 'DEDUCTION',
      ja: '垂直条件から E, F が A の接触弦、すなわち極線上にあると証明',
      en: 'Use the perpendicular conditions to identify EF as the contact polar of A',
      detail: 'IE ⟂ CA ∧ IF ⟂ AB → polar(A) = EF',
    },
    {
      id: 'normalize',
      engine: 'COORDINATE',
      ja: '外接円を単位円へ正規化し、M の条件を極線の式へ変換',
      en: 'Normalize the circumcircle to the unit circle and translate M to polar incidence',
      detail: 'O = (0,0), R = 1, M ∈ EF ∩ Γ',
    },
    {
      id: 'intersections',
      engine: 'LINEAR',
      ja: '4本の接線から S, T を、直線 TI と OA から J を厳密構成',
      en: 'Solve the four tangent equations for S,T and intersect TI with OA to obtain J',
      detail: 'X · Y = 1 → S,T; J = TI ∩ OA',
    },
    {
      id: 'translate',
      engine: 'TYPED IR',
      ja: '目標角 ASJ = IST を有向角の外積・内積式へ変換',
      en: 'Translate the target angle ASJ = IST into a directed cross-dot identity',
      detail: 'eqangle → cross-dot polynomial',
    },
    {
      id: 'factor',
      engine: 'SYMPY',
      ja: '目標式の分子を極線への incidence 因子で因数分解',
      en: 'Factor the goal numerator through the polar-incidence numerator',
      detail: 'goal numerator = polar(M, A) × quotient',
    },
    {
      id: 'verify',
      engine: 'CERTIFICATE',
      ja: '26本の恒等式を再生し、未消去条件0で証明書を確定',
      en: 'Replay 26 exact identities and seal the certificate with zero open obligations',
      detail: '26 / 26 residuals = 0; obligations = 0',
    },
  ],
  residuals: [
    'E_on_CA = 0',
    'IE_perpendicular_CA = 0',
    'F_on_AB = 0',
    'IF_perpendicular_AB = 0',
    'EF_line_equals_contact_polar = 0',
    'S_on_tangent_at_M = 0',
    'J_on_TI = 0',
    'directed_angle_numerator_factors_through_EF = 0',
  ],
} as const

export const RESEARCH_METRICS = [
  {
    value: '17 / 30',
    ja: 'IMO-AG-30 native再実行',
    en: 'IMO-AG-30 native rerun',
    noteJa: '同一DDAR・外部LLMなし。証明JSON 31/31を保存・照合。',
    noteEn: 'One DDAR configuration, no external LLM. All 31 proof JSON files saved and checked.',
    tone: 'cyan',
  },
  {
    value: '89 / 89',
    ja: '監査済み幾何ポートフォリオ',
    en: 'Audited geometry portfolio',
    noteJa: '問題文、図、証明過程、証明書を再生可能な成果物として保存。',
    noteEn: 'Statements, figures, derivations and certificates remain replayable artifacts.',
    tone: 'amber',
  },
  {
    value: '100 / 100',
    ja: '既存射だけで生成した意味図形',
    en: 'Semantic figures from existing morphisms',
    noteJa: '新規幾何射0。640候補から異なる100図を固定。',
    noteEn: 'Zero new geometry morphisms; 100 distinct figures selected from 640 candidates.',
    tone: 'rose',
  },
  {
    value: '2,000,000',
    ja: '回路とソフトの一致入力数',
    en: 'Circuit/software matching inputs',
    noteJa: '候補検査回路のRTLシミュレーションと論理合成を通過。',
    noteEn: 'Candidate-filter RTL passed equivalence simulation and logic synthesis.',
    tone: 'green',
  },
] as const

export const GEOMETRY_FIGURES = [
  { src: '/research/geometry/figure-001.png', code: '001', ja: '円の交差列', en: 'Circle intersections' },
  { src: '/research/geometry/figure-002.png', code: '002', ja: '回転と弦', en: 'Rotation and chords' },
  { src: '/research/geometry/figure-011.png', code: '011', ja: '直交格子', en: 'Orthogonal lattice' },
  { src: '/research/geometry/figure-037.png', code: '037', ja: '多重軌道', en: 'Nested orbits' },
  { src: '/research/geometry/figure-046.png', code: '046', ja: '交差星形', en: 'Intersecting star' },
  { src: '/research/geometry/figure-065.png', code: '065', ja: '反射格子', en: 'Reflected grid' },
] as const

export const REPRESENTATION_PATHS = [
  { ja: '製図', en: 'Drafting', detail: 'Line / circle / intersection' },
  { ja: '建築', en: 'Architecture', detail: 'Parallel / perpendicular / subdivision' },
  { ja: '手稿', en: 'Manuscript', detail: 'Proof step / focus / annotation' },
  { ja: 'ノート', en: 'Notebook', detail: 'Derivation / state / branch' },
  { ja: 'プロダクト', en: 'Product', detail: 'Symmetry / constraint / variant' },
  { ja: '生成アート', en: 'Generative art', detail: 'Orbit / reflection / composition' },
] as const

export const RESEARCH_RECORDS = [
  {
    date: '2026-08-30',
    ja: '既存幾何基底による複雑図形生成',
    en: 'Complex figure generation from the existing geometry basis',
    href: 'https://github.com/corcondor/mortra/blob/release/mortra-1-beta/docs/research/MORTRA-GENERATIVE-GEOMETRY-BASIS-20260830.md',
    tag: 'GENERATIVE GEOMETRY',
  },
  {
    date: '2026-08-30',
    ja: 'IMO-AG-30 native再実行',
    en: 'IMO-AG-30 native rerun',
    href: 'https://github.com/corcondor/mortra/blob/release/mortra-1-beta/docs/research/MORTRA-IMO-AG-30-NATIVE-RERUN-20260830.md',
    tag: 'BENCHMARK',
  },
  {
    date: '2026-08-28',
    ja: '未証明11問の厳密閉包',
    en: 'Exact closure of eleven previously uncertified problems',
    href: 'https://github.com/corcondor/mortra/blob/release/mortra-1-beta/docs/research/MORTRA-CODEX-FUSED-REMAINING11-CLOSURE-20260828.md',
    tag: 'PROOF SYSTEM',
  },
  {
    date: '2026-08-27',
    ja: '可逆な分野横断チャートと円幾何の融合',
    en: 'Reversible cross-domain charts and circle fusion',
    href: 'https://github.com/corcondor/mortra/commit/e6b9e6b',
    tag: 'REPRESENTATION',
  },
] as const

export function researchText(lang: Lang) {
  const ja = lang === 'ja'
  return {
    lang,
    eyebrow: 'MORTRA / OPEN RESEARCH SYSTEM',
    title: ja ? '証明が動くところまで、公開する。' : 'Publish the proof while it moves.',
    lead: ja
      ? '保存済みの証明を再生し、型付きの射がどの推論器を渡り、図・解答・証明書へ変わるかを追えます。研究記録とGitHubの更新も同じ画面で同期します。'
      : 'Replay a certified proof and follow typed morphisms across reasoners into a figure, solution and certificate. Research records and repository activity stay in the same surface.',
    traceTitle: ja ? '証明再生' : 'Proof replay',
    traceNote: ja ? '保存済み証明書を再生中。架空のライブ推論ではありません。' : 'Replaying a stored certificate, not simulating a live solve.',
    activityTitle: ja ? '研究ストリーム' : 'Research stream',
    systemTitle: ja ? '数学構造は、推論器の間を移動する。' : 'Mathematical structure moves between reasoners.',
    systemCopy: ja
      ? 'ノードは実装済みの表現または検証器、線は受け渡せる型付き関係です。触れると、その射が何を保存するかを確認できます。'
      : 'Nodes are implemented representations or verifiers; edges are typed relations they can exchange. Inspect a node to see what each morphism preserves.',
    geometryTitle: ja ? '証明用の幾何が、表現の基底になる。' : 'Proof geometry becomes a basis for expression.',
    geometryCopy: ja
      ? '点・線・円・交点・回転・中点・鏡映・平行・垂直だけを合成し、図案専用の命令を追加せず100種類を生成しました。同じ意味図形を製図、手稿、建築、プロダクト、生成アートへ描き分けます。'
      : 'Points, lines, circles, intersections, rotation, midpoint, reflection, parallel and perpendicular constructions generated 100 distinct figures without motif-specific commands. One semantic figure can be rendered for drafting, manuscript, architecture, product and generative art.',
    evidenceTitle: ja ? '数字は、再生できる成果物と一緒に置く。' : 'Numbers stay beside replayable artifacts.',
    recordsTitle: ja ? '研究記録' : 'Research records',
    developerTitle: ja ? '開発者向けの入口' : 'Developer surface',
    developerCopy: ja
      ? '公開リポジトリ、証明書、研究記録、活動APIを同じ境界から追跡できます。'
      : 'Trace the public repository, certificates, research records and activity API from one boundary.',
  }
}
