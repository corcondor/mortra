/**
 * 組合せ・確率を形式空間に入れて、どこまで到達するかを測る。
 *
 * 3構成で比較する:
 *   base  素のアトラス
 *   +FIX  ソート設計の是正のみ（Scalar/Real/Integer の同一視）。前回の実験の流用。
 *   +COMB 組合せ・確率の語彙を追加
 *
 * FIX を分離するのは、伸びが「新語彙のおかげ」なのか
 * 「単なるソート同一視のおかげ」なのかを切り分けるため。
 */
import { enumerateTypedTerms } from './typed-term-enumerator.ts'
import { executableMorphismAtlas } from './generalization-kernel.ts'
import type { HyperMorphismSchema, SemanticHypergraph } from './generalization-kernel.ts'

function graph(id: string, rootSorts: string[], querySorts: string[]): SemanticHypergraph {
  return {
    parent_id: id,
    nodes: rootSorts.map((sort, i) => ({ id: `${id}:n${i}`, sort, label: sort } as never)),
    edges: [],
    root_sorts: rootSorts,
    query_sorts: querySorts,
    language_analysis: {
      token_count: 0, parse_count: 1, parse_truncated: false, clause_count: 1,
      quantifier_prefix: [], definitions: [], declarations: [],
      constraints: [], unresolved_references: [], diagnostics: ['手で形式化'],
    },
  }
}

/** ソート設計の是正。数学的に同じ対象がアトラス上で分断されている分だけ。 */
const FIX: HyperMorphismSchema[] = [
  { name: 'ScalarAsReal', sources: ['Scalar'], target: 'Real', preserves: ['value'], backend: ['identity'] },
  { name: 'RealAsScalar', sources: ['Real'], target: 'Scalar', preserves: ['value'], backend: ['identity'] },
  { name: 'IntegerInclusion', sources: ['Integer'], target: 'Real', preserves: ['value'], backend: ['identity'] },
]

/**
 * 組合せ・確率の語彙。
 *
 * 規律: 1問専用の射は入れない。「サイコロの積」「カタラン数」のような
 * 個別の答えを出す射は暗記なので禁止。代わりに、その分野の問題が
 * 共通して踏む構造の段を置く。
 */
const COMB: HyperMorphismSchema[] = [
  // (A) 離散対象を作る入口。素のアトラスでは FiniteSet の生成源が
  //     ResidueProjection(Integer) の1本しかなかった。
  { name: 'ConfigurationDiscretization', sources: ['GeometricConfiguration'], target: 'FiniteSet', preserves: ['incidence', 'finite-support'], backend: ['incidence-enumeration'] },
  { name: 'OrbitAsFiniteSet', sources: ['FiniteAlgebraicOrbit'], target: 'FiniteSet', preserves: ['finite-support', 'multiplicity'], backend: ['identity'] },
  { name: 'CyclicGroupRealization', sources: ['CyclicGroup'], target: 'FiniteAlgebraicOrbit', preserves: ['cyclic-order'], backend: ['cyclotomic-polynomial'] },

  // (B) 有限集合の作り方。選ぶ・並べる・直積を取る。
  { name: 'SubsetFamilyConstruction', sources: ['FiniteSet'], target: 'FamilyOfSets', preserves: ['inclusion-order', 'finite-support'], backend: ['subset-enumeration'] },
  { name: 'ProductTrial', sources: ['FiniteSet', 'FiniteSet'], target: 'FiniteSet', preserves: ['both-parent-provenance', 'product-structure'], backend: ['cartesian-product'] },
  { name: 'FamilyUnderlyingSet', sources: ['FamilyOfSets'], target: 'FiniteSet', preserves: ['finite-support'], backend: ['identity'] },
  { name: 'SetIndexedFamily', sources: ['FiniteSet'], target: 'FiniteFamily', preserves: ['index-set'], backend: ['indexing'] },

  // (C) 数え上げの二大道具。包除と母関数。
  { name: 'InclusionExclusion', sources: ['FamilyOfSets'], target: 'Integer', preserves: ['cardinality', 'sieve-identity'], backend: ['inclusion-exclusion'] },
  { name: 'GeneratingFunctionEncoding', sources: ['FiniteFamily'], target: 'Polynomial', preserves: ['index-set', 'coefficient-sequence'], backend: ['generating-function'] },
  { name: 'CoefficientExtraction', sources: ['Polynomial'], target: 'FiniteFamily', preserves: ['coefficient-sequence'], backend: ['series-expansion'] },

  // (D) 確率の段。素のアトラスには確率のソートが1つも無かった。
  { name: 'UniformProbabilitySpace', sources: ['FiniteSet'], target: 'ProbabilitySpace', preserves: ['equal-likelihood', 'finite-support'], backend: ['uniform-measure'] },
  { name: 'EventExtraction', sources: ['ProbabilitySpace', 'Proposition'], target: 'Event', preserves: ['both-parent-provenance', 'measurability'], backend: ['predicate-selection'] },
  { name: 'EventFromFamily', sources: ['ProbabilitySpace', 'FamilyOfSets'], target: 'Event', preserves: ['both-parent-provenance', 'measurability'], backend: ['sigma-algebra'] },
  { name: 'ProbabilityMeasure', sources: ['ProbabilitySpace', 'Event'], target: 'Real', preserves: ['both-parent-provenance', 'measure-class', 'normalization'], backend: ['counting-measure', 'exact-rational'] },
  { name: 'RandomVariableFromFamily', sources: ['ProbabilitySpace', 'FiniteFamily'], target: 'RandomVariable', preserves: ['both-parent-provenance', 'measurability'], backend: ['pushforward'] },
  { name: 'LinearityOfExpectation', sources: ['RandomVariable'], target: 'Real', preserves: ['linearity', 'measure-class'], backend: ['exact-summation', 'indicator-decomposition'] },

  // (E) 状態空間上の漸化式。確率漸化式・ランダムウォーク・遷移の全般。
  { name: 'TransitionRecurrence', sources: ['ProbabilitySpace', 'Sequence'], target: 'Sequence', preserves: ['both-parent-provenance', 'markov-transition'], backend: ['linear-recurrence'] },
  { name: 'SequenceEvaluation', sources: ['Sequence'], target: 'FiniteFamily', preserves: ['index-set'], backend: ['recurrence-engine'] },

  // (F) 恒等式を主張に持ち上げる段。組合せ的恒等式の証明問題はここを通る。
  { name: 'CountingIdentityAssertion', sources: ['Integer', 'Integer'], target: 'Proposition', preserves: ['both-parent-provenance', 'cardinality'], backend: ['symbolic-identity', 'cvc5'] },
  { name: 'ProbabilityIdentityAssertion', sources: ['Real', 'Real'], target: 'Proposition', preserves: ['both-parent-provenance', 'measure-class'], backend: ['symbolic-identity', 'cvc5'] },
]

type Case = { id: string; problem: string; roots: string[]; goals: string[] }

const CASES: Case[] = [
  {
    id: 'P1 京大1992',
    problem: 'n個のサイコロを同時に投げるとき、出る目の積が4で割り切れる確率を求めよ',
    roots: ['FiniteSet', 'Integer'],
    goals: ['Real', 'Scalar', 'Quantity'],
  },
  {
    id: 'P2 正八角形',
    problem: '正八角形の頂点（1の8乗根）から4点を選ぶとき、その積が1になる確率を求めよ',
    roots: ['CyclicGroup', 'FiniteSet'],
    goals: ['Real', 'Scalar'],
  },
  {
    id: 'P3 格子路',
    problem: '(0,0)から(n,n)への格子路で y=x を越えないものの個数を求めよ（カタラン数）',
    roots: ['GeometricConfiguration', 'Sequence'],
    goals: ['Integer', 'Scalar'],
  },
  {
    id: 'P4 東工大2019',
    problem: '正四面体の頂点を毎回等確率で移動する。n回後に元の頂点にいる確率を求めよ',
    roots: ['Sequence', 'FiniteSet'],
    goals: ['Real', 'Scalar'],
  },
  {
    id: 'P5 IMO1987-1',
    problem: 'n元集合の置換σの不動点数を p(σ) とするとき Σ_σ p(σ) = n! を示せ',
    roots: ['FiniteSet', 'Function'],
    goals: ['Proposition', 'Proof', 'Integer'],
  },
  {
    id: 'P6 撹乱順列',
    problem: 'n人が自分以外の帽子を取る場合の数 D_n を求めよ（完全順列・包除原理）',
    roots: ['FiniteSet', 'FamilyOfSets'],
    goals: ['Integer', 'Scalar'],
  },
  {
    id: 'P7 Vandermonde',
    problem: 'Σ_{k=0}^{n} C(n,k)^2 = C(2n,n) を示せ（母関数・二重数え上げ）',
    roots: ['FiniteFamily', 'Polynomial'],
    goals: ['Proposition', 'Proof', 'Integer'],
  },
  {
    id: 'P8 くじ引き',
    problem: 'n本中k本が当たりのくじを順に引くとき、何番目に引いても当たる確率が等しいことを示せ',
    roots: ['FiniteSet', 'FiniteFamily'],
    goals: ['Real', 'Proposition', 'Proof'],
  },
]

type Row = {
  id: string
  goals: number
  terms: number
  best?: { sort: string; depth: number; path: string[] }
  usedMorphisms: string[]
  missing: string[]
}

function run(rules: readonly HyperMorphismSchema[]): Row[] {
  return CASES.map(c => {
    const r = enumerateTypedTerms([graph(c.id, c.roots, c.goals)], {
      maxDepth: 7, maxStates: 60_000, goalSorts: c.goals, rules,
    })
    const best = r.goals[0]
    const used = new Set<string>()
    for (const g of r.goals) for (const s of g.steps) used.add(s.morphism)
    const missing = new Set<string>()
    for (const f of r.frontier) for (const m of f.missing) missing.add(m)
    return {
      id: c.id,
      goals: r.goals.length,
      terms: r.terms.length,
      best: best ? { sort: best.sort, depth: best.depth, path: best.steps.map(s => s.morphism) } : undefined,
      usedMorphisms: [...used].sort(),
      missing: [...missing].sort(),
    }
  })
}

const base = executableMorphismAtlas()
const withFix = [...base, ...FIX]
const withComb = [...base, ...FIX, ...COMB]

console.log(`素のアトラス: 射 ${base.length}本 / +FIX ${withFix.length}本 / +COMB ${withComb.length}本\n`)

const rBase = run(base)
const rFix = run(withFix)
const rComb = run(withComb)

console.log('=== 到達数（goalソートに届いた項の数 / 探索した項の総数） ===')
console.log('問題              素            +FIX          +COMB')
for (let i = 0; i < CASES.length; i++) {
  const b = rBase[i], f = rFix[i], c = rComb[i]
  const mark = c.goals > f.goals ? '  ← 語彙で変化' : (f.goals > b.goals ? '  ← FIXで変化' : '')
  console.log(
    `${b.id.padEnd(16)}${String(b.goals).padStart(4)}/${String(b.terms).padStart(5)}  `
    + `${String(f.goals).padStart(4)}/${String(f.terms).padStart(5)}  `
    + `${String(c.goals).padStart(4)}/${String(c.terms).padStart(5)}${mark}`,
  )
}
const sum = (rows: Row[]) => rows.reduce((a, r) => a + r.goals, 0)
const solved = (rows: Row[]) => rows.filter(r => r.goals > 0).length
console.log(`\n合計到達項: 素 ${sum(rBase)} / +FIX ${sum(rFix)} / +COMB ${sum(rComb)}`)
console.log(`到達した問題数: 素 ${solved(rBase)}/${CASES.length} / +FIX ${solved(rFix)}/${CASES.length} / +COMB ${solved(rComb)}/${CASES.length}`)

console.log('\n=== 素の状態で未到達だった問題の frontier 不足ソート集計 ===')
const missCount = new Map<string, number>()
for (const r of rBase) {
  if (r.goals > 0) continue
  for (const m of r.missing) missCount.set(m, (missCount.get(m) ?? 0) + 1)
}
for (const [sort, n] of [...missCount].sort((a, b) => b[1] - a[1])) {
  console.log(`  ${String(n).padStart(2)}問  ${sort}`)
}

console.log('\n=== +COMB での最短到達経路 ===')
for (const r of rComb) {
  if (r.best) console.log(`${r.id}: ${r.best.sort} 深さ${r.best.depth}\n    ${r.best.path.join(' → ')}`)
  else console.log(`${r.id}: 到達せず（不足: ${r.missing.slice(0, 6).join(', ')}）`)
}

console.log('\n=== 追加した射が、足した理由の問題以外でも使われたか ===')
const addedNames = COMB.map(m => m.name)
for (const name of addedNames) {
  const users = rComb.filter(r => r.usedMorphisms.includes(name)).map(r => r.id)
  const verdict = users.length === 0 ? '未使用' : users.length === 1 ? '1問のみ＝暗記の疑い' : `${users.length}問＝語彙`
  console.log(`${name.padEnd(30)} ${verdict.padEnd(18)} ${users.join(' , ')}`)
}
