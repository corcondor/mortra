/**
 * v2。v1の測り方が甘かったので締める。
 *
 * 甘かった点:
 *  (1) goalソートに届いただけでは解けたことにならない。
 *      P1 が IntegerInclusion 深さ1 で Real に届いたのは、確率を出したのではなく
 *      「積という整数を実数と見なした」だけ。両方の root を実際に使った項に限る。
 *  (2) frontier は「あと1ソートで撃てる射」しか報告しない。素のアトラスでは
 *      組合せ領域が完全に切れているので frontier がほぼ空になる。
 *      到達可能ソート集合そのものを出す。
 *  (3) 「1問でしか使われない＝暗記」は誤判定になる。その射の入力ソートが
 *      そもそも1問にしか現れないなら分母が1。分母付きで見る。
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

const FIX: HyperMorphismSchema[] = [
  { name: 'ScalarAsReal', sources: ['Scalar'], target: 'Real', preserves: ['value'], backend: ['identity'] },
  { name: 'RealAsScalar', sources: ['Real'], target: 'Scalar', preserves: ['value'], backend: ['identity'] },
  { name: 'IntegerInclusion', sources: ['Integer'], target: 'Real', preserves: ['value'], backend: ['identity'] },
]

const COMB: HyperMorphismSchema[] = [
  { name: 'ConfigurationDiscretization', sources: ['GeometricConfiguration'], target: 'FiniteSet', preserves: ['incidence', 'finite-support'], backend: ['incidence-enumeration'] },
  { name: 'OrbitAsFiniteSet', sources: ['FiniteAlgebraicOrbit'], target: 'FiniteSet', preserves: ['finite-support', 'multiplicity'], backend: ['identity'] },
  { name: 'CyclicGroupRealization', sources: ['CyclicGroup'], target: 'FiniteAlgebraicOrbit', preserves: ['cyclic-order'], backend: ['cyclotomic-polynomial'] },
  { name: 'SubsetFamilyConstruction', sources: ['FiniteSet'], target: 'FamilyOfSets', preserves: ['inclusion-order', 'finite-support'], backend: ['subset-enumeration'] },
  { name: 'ProductTrial', sources: ['FiniteSet', 'FiniteSet'], target: 'FiniteSet', preserves: ['both-parent-provenance', 'product-structure'], backend: ['cartesian-product'] },
  { name: 'FamilyUnderlyingSet', sources: ['FamilyOfSets'], target: 'FiniteSet', preserves: ['finite-support'], backend: ['identity'] },
  { name: 'SetIndexedFamily', sources: ['FiniteSet'], target: 'FiniteFamily', preserves: ['index-set'], backend: ['indexing'] },
  { name: 'InclusionExclusion', sources: ['FamilyOfSets'], target: 'Integer', preserves: ['cardinality', 'sieve-identity'], backend: ['inclusion-exclusion'] },
  { name: 'GeneratingFunctionEncoding', sources: ['FiniteFamily'], target: 'Polynomial', preserves: ['index-set', 'coefficient-sequence'], backend: ['generating-function'] },
  { name: 'CoefficientExtraction', sources: ['Polynomial'], target: 'FiniteFamily', preserves: ['coefficient-sequence'], backend: ['series-expansion'] },
  { name: 'UniformProbabilitySpace', sources: ['FiniteSet'], target: 'ProbabilitySpace', preserves: ['equal-likelihood', 'finite-support'], backend: ['uniform-measure'] },
  { name: 'EventExtraction', sources: ['ProbabilitySpace', 'Proposition'], target: 'Event', preserves: ['both-parent-provenance', 'measurability'], backend: ['predicate-selection'] },
  { name: 'EventFromFamily', sources: ['ProbabilitySpace', 'FamilyOfSets'], target: 'Event', preserves: ['both-parent-provenance', 'measurability'], backend: ['sigma-algebra'] },
  { name: 'ProbabilityMeasure', sources: ['ProbabilitySpace', 'Event'], target: 'Real', preserves: ['both-parent-provenance', 'measure-class', 'normalization'], backend: ['counting-measure', 'exact-rational'] },
  { name: 'RandomVariableFromFamily', sources: ['ProbabilitySpace', 'FiniteFamily'], target: 'RandomVariable', preserves: ['both-parent-provenance', 'measurability'], backend: ['pushforward'] },
  { name: 'LinearityOfExpectation', sources: ['RandomVariable'], target: 'Real', preserves: ['linearity', 'measure-class'], backend: ['exact-summation', 'indicator-decomposition'] },
  { name: 'TransitionRecurrence', sources: ['ProbabilitySpace', 'Sequence'], target: 'Sequence', preserves: ['both-parent-provenance', 'markov-transition'], backend: ['linear-recurrence'] },
  { name: 'SequenceEvaluation', sources: ['Sequence'], target: 'FiniteFamily', preserves: ['index-set'], backend: ['recurrence-engine'] },
  { name: 'CountingIdentityAssertion', sources: ['Integer', 'Integer'], target: 'Proposition', preserves: ['both-parent-provenance', 'cardinality'], backend: ['symbolic-identity', 'cvc5'] },
  { name: 'ProbabilityIdentityAssertion', sources: ['Real', 'Real'], target: 'Proposition', preserves: ['both-parent-provenance', 'measure-class'], backend: ['symbolic-identity', 'cvc5'] },
]

type Case = { id: string; roots: string[]; goals: string[] }
const CASES: Case[] = [
  { id: 'P1 京大1992', roots: ['FiniteSet', 'Integer'], goals: ['Real', 'Scalar', 'Quantity'] },
  { id: 'P2 正八角形', roots: ['CyclicGroup', 'FiniteSet'], goals: ['Real', 'Scalar'] },
  { id: 'P3 格子路', roots: ['GeometricConfiguration', 'Sequence'], goals: ['Integer', 'Scalar'] },
  { id: 'P4 東工大2019', roots: ['Sequence', 'FiniteSet'], goals: ['Real', 'Scalar'] },
  { id: 'P5 IMO1987-1', roots: ['FiniteSet', 'Function'], goals: ['Proposition', 'Proof', 'Integer'] },
  { id: 'P6 撹乱順列', roots: ['FiniteSet', 'FamilyOfSets'], goals: ['Integer', 'Scalar'] },
  { id: 'P7 Vandermonde', roots: ['FiniteFamily', 'Polynomial'], goals: ['Proposition', 'Proof', 'Integer'] },
  { id: 'P8 くじ引き', roots: ['FiniteSet', 'FiniteFamily'], goals: ['Real', 'Proposition', 'Proof'] },
]

/** 両方の root ソートを式の中で実際に消費している項だけを「到達」と数える。 */
function usesAllRoots(expression: string, roots: string[]): boolean {
  return roots.every(r => expression.includes(`,${JSON.stringify(r)})`))
}

type Row = {
  id: string
  loose: number
  strict: number
  terms: number
  reachable: string[]
  best?: { sort: string; depth: number; path: string[] }
  used: Set<string>
}

function run(rules: readonly HyperMorphismSchema[]): Row[] {
  return CASES.map(c => {
    const r = enumerateTypedTerms([graph(c.id, c.roots, c.goals)], {
      maxDepth: 7, maxStates: 60_000, goalSorts: c.goals, rules,
    })
    const strictGoals = r.goals.filter(g => usesAllRoots(g.expression, c.roots))
    const used = new Set<string>()
    for (const g of strictGoals) for (const s of g.steps) used.add(s.morphism)
    const best = strictGoals[0]
    return {
      id: c.id,
      loose: r.goals.length,
      strict: strictGoals.length,
      terms: r.terms.length,
      reachable: [...new Set(r.terms.map(t => t.sort))].sort(),
      best: best ? { sort: best.sort, depth: best.depth, path: best.steps.map(s => s.morphism) } : undefined,
      used,
    }
  })
}

const base = executableMorphismAtlas()
const withFix = [...base, ...FIX]
const withComb = [...base, ...FIX, ...COMB]

const rBase = run(base), rFix = run(withFix), rComb = run(withComb)

console.log('=== 厳格到達（両方の root を実際に使った項のみ） / 緩い到達 / 探索項 ===')
console.log('問題                 素            +FIX          +COMB')
for (let i = 0; i < CASES.length; i++) {
  const f = (r: Row) => `${String(r.strict).padStart(3)}(${String(r.loose).padStart(3)})/${String(r.terms).padStart(4)}`
  console.log(`${CASES[i].id.padEnd(16)} ${f(rBase[i])}  ${f(rFix[i])}  ${f(rComb[i])}`)
}
const S = (rows: Row[]) => rows.reduce((a, r) => a + r.strict, 0)
const N = (rows: Row[]) => rows.filter(r => r.strict > 0).length
console.log(`\n厳格到達 合計: 素 ${S(rBase)} / +FIX ${S(rFix)} / +COMB ${S(rComb)}`)
console.log(`厳格に解けた問題数: 素 ${N(rBase)}/8 / +FIX ${N(rFix)}/8 / +COMB ${N(rComb)}/8`)

console.log('\n=== 素のアトラスで各問題から到達できたソート ===')
for (let i = 0; i < CASES.length; i++) {
  console.log(`${CASES[i].id.padEnd(16)} ${rBase[i].reachable.join(', ')}`)
}

console.log('\n=== 素の状態で欠けていたもの（goalに必要なのに到達不能なソート） ===')
const need = new Map<string, string[]>()
for (let i = 0; i < CASES.length; i++) {
  const have = new Set(rBase[i].reachable)
  for (const g of CASES[i].goals) if (!have.has(g)) {
    need.set(g, [...(need.get(g) ?? []), CASES[i].id])
  }
}
for (const [sort, ids] of [...need].sort((a, b) => b[1].length - a[1].length)) {
  console.log(`  ${String(ids.length).padStart(2)}問  ${sort.padEnd(14)} ${ids.join(' , ')}`)
}

console.log('\n=== +COMB 厳格到達の最短経路 ===')
for (const r of rComb) {
  if (r.best) console.log(`${r.id.padEnd(16)} ${r.best.sort} 深さ${r.best.depth}\n    ${r.best.path.join(' → ')}`)
  else console.log(`${r.id.padEnd(16)} 厳格には未到達`)
}

// ---- ablation: 各射を1本抜いて厳格到達の落ち幅を測る ----
console.log('\n=== アブレーション（1本抜いたときの厳格到達の落ち幅） ===')
console.log('射名                            適用可能  実使用  抜くと落ちる問題')
const full = S(rComb)
for (const m of COMB) {
  const ablated = run(withComb.filter(x => x.name !== m.name))
  const dropped = CASES.map((c, i) => ({ c, before: rComb[i].strict, after: ablated[i].strict }))
    .filter(x => x.after < x.before)
  const usedIn = rComb.filter(r => r.used.has(m.name)).map(r => r.id)
  // 分母: その射の入力ソートが到達可能だった問題数
  const applicable = rComb.filter(r => m.sources.every(s => r.reachable.includes(s))).length
  const total = S(ablated)
  const verdict = dropped.length === 0 ? '冗長' : dropped.length === 1 ? '★1問限定' : `${dropped.length}問に効く`
  console.log(
    `${m.name.padEnd(30)} ${String(applicable).padStart(4)}問  ${String(usedIn.length).padStart(4)}問  `
    + `${verdict.padEnd(12)} 合計 ${full}→${total}  [${dropped.map(d => d.c.id.split(' ')[0]).join(',')}]`,
  )
}
