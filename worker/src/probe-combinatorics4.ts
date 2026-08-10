/**
 * v3。ホールドアウト検証。
 *
 * 語彙か暗記かの本当の判定は「設計に使わなかった問題に効くか」。
 * COMB の20射は P1..P8 を見ながら設計した。H1..H5 は設計後に選んだ別問題で、
 * root ソートの組み合わせも P1..P8 に無いものを使う。
 */
import { enumerateTypedTerms } from './typed-term-enumerator.ts'
import { executableMorphismAtlas } from './generalization-kernel.ts'
import type { HyperMorphismSchema, SemanticHypergraph } from './generalization-kernel.ts'

function graph(id: string, rootSorts: string[], querySorts: string[]): SemanticHypergraph {
  return {
    parent_id: id,
    nodes: rootSorts.map((sort, i) => ({ id: `${id}:n${i}`, sort, label: sort } as never)),
    edges: [], root_sorts: rootSorts, query_sorts: querySorts,
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

/**
 * 第2ラウンド。ホールドアウトで露出した3つのシンクを埋める。
 *  - OrderedFamily は出次数0。順序（最大・最小・第k位）の段が丸ごと無い。
 *  - Matrix2 は出次数0。線形反復の段が無い（入る射だけあって出る射が無い）。
 *  - IntegerPair は数論側（gcd/lcm）にしか出口が無く、数え上げの添字にならない。
 * どれも1問の都合ではなく、ソートグラフの穴として観測されたもの。
 */
const COMB2: HyperMorphismSchema[] = [
  { name: 'OrderFiltration', sources: ['OrderedFamily'], target: 'FamilyOfSets', preserves: ['order', 'monotone-filtration'], backend: ['threshold-decomposition'] },
  { name: 'OrderStatisticSelection', sources: ['OrderedFamily', 'FiniteSet'], target: 'FiniteFamily', preserves: ['both-parent-provenance', 'order', 'index-set'], backend: ['order-statistics'] },
  { name: 'LinearIterationOrbit', sources: ['Matrix2'], target: 'Orbit', preserves: ['iteration', 'initial-state'], backend: ['matrix-power'] },
  { name: 'ParameterPairIndexing', sources: ['IntegerPair'], target: 'FiniteFamily', preserves: ['index-set', 'integrality'], backend: ['indexing'] },
]

const HOLDOUT = [
  { id: 'H1 京大2007', problem: 'サイコロをn回投げるとき出た目の最大値がkである確率', roots: ['OrderedFamily', 'FiniteSet'], goals: ['Real', 'Scalar'] },
  { id: 'H2 球と箱', problem: 'n個の区別できる球をm個の箱に入れ空箱を作らない場合の数', roots: ['FiniteSet', 'IntegerPair'], goals: ['Integer', 'Scalar'] },
  { id: 'H3 マルコフ', problem: '2状態の推移行列で表される試行のn回後の状態確率', roots: ['Matrix2', 'FiniteSet'], goals: ['Real', 'Scalar'] },
  { id: 'H4 グラフ彩色', problem: 'グラフをk色で塗り分ける方法の数（彩色多項式）', roots: ['GeometricConfiguration', 'FamilyOfSets'], goals: ['Integer', 'Proposition'] },
  { id: 'H5 コイン期待値', problem: 'n枚のコインを投げたときの表の枚数の期待値を求めよ', roots: ['FiniteSet', 'Polynomial'], goals: ['Real', 'Scalar'] },
]

function usesAllRoots(expression: string, roots: string[]): boolean {
  return roots.every(r => expression.includes(`,${JSON.stringify(r)})`))
}

function run(rules: readonly HyperMorphismSchema[]) {
  return HOLDOUT.map(c => {
    const r = enumerateTypedTerms([graph(c.id, c.roots, c.goals)], {
      maxDepth: 7, maxStates: 60_000, goalSorts: c.goals, rules,
    })
    const strict = r.goals.filter(g => usesAllRoots(g.expression, c.roots))
    const used = new Set<string>()
    for (const g of strict) for (const s of g.steps) used.add(s.morphism)
    return {
      id: c.id, loose: r.goals.length, strict: strict.length, terms: r.terms.length,
      reachable: [...new Set(r.terms.map(t => t.sort))].sort(),
      best: strict[0] ? { sort: strict[0].sort, depth: strict[0].depth, path: strict[0].steps.map(s => s.morphism) } : undefined,
      used: [...used].sort(),
      missing: [...new Set(r.frontier.flatMap(f => f.missing))].sort(),
    }
  })
}

// 設計セット P1..P8 も同じ規則で走らせて、第2ラウンドが回帰を起こさないか見る
const DESIGN = [
  { id: 'P1 京大1992', problem: '', roots: ['FiniteSet', 'Integer'], goals: ['Real', 'Scalar', 'Quantity'] },
  { id: 'P2 正八角形', problem: '', roots: ['CyclicGroup', 'FiniteSet'], goals: ['Real', 'Scalar'] },
  { id: 'P3 格子路', problem: '', roots: ['GeometricConfiguration', 'Sequence'], goals: ['Integer', 'Scalar'] },
  { id: 'P4 東工大2019', problem: '', roots: ['Sequence', 'FiniteSet'], goals: ['Real', 'Scalar'] },
  { id: 'P5 IMO1987-1', problem: '', roots: ['FiniteSet', 'Function'], goals: ['Proposition', 'Proof', 'Integer'] },
  { id: 'P6 撹乱順列', problem: '', roots: ['FiniteSet', 'FamilyOfSets'], goals: ['Integer', 'Scalar'] },
  { id: 'P7 Vandermonde', problem: '', roots: ['FiniteFamily', 'Polynomial'], goals: ['Proposition', 'Proof', 'Integer'] },
  { id: 'P8 くじ引き', problem: '', roots: ['FiniteSet', 'FiniteFamily'], goals: ['Real', 'Proposition', 'Proof'] },
]

function runOn(cases: typeof HOLDOUT, rules: readonly HyperMorphismSchema[]) {
  return cases.map(c => {
    const r = enumerateTypedTerms([graph(c.id, c.roots, c.goals)], {
      maxDepth: 7, maxStates: 60_000, goalSorts: c.goals, rules,
    })
    const strict = r.goals.filter(g => usesAllRoots(g.expression, c.roots))
    const used = new Set<string>()
    for (const g of strict) for (const s of g.steps) used.add(s.morphism)
    return {
      id: c.id, loose: r.goals.length, strict: strict.length, terms: r.terms.length,
      reachable: [...new Set(r.terms.map(t => t.sort))].sort(),
      best: strict[0] ? { sort: strict[0].sort, depth: strict[0].depth, path: strict[0].steps.map(s => s.morphism) } : undefined,
      used: [...used].sort(),
    }
  })
}

const base = executableMorphismAtlas()
const r1 = [...base, ...FIX, ...COMB]
const r2 = [...base, ...FIX, ...COMB, ...COMB2]

const hB = runOn(HOLDOUT, base)
const h1 = runOn(HOLDOUT, r1)
const h2 = runOn(HOLDOUT, r2)
const dB = runOn(DESIGN, base)
const d1 = runOn(DESIGN, r1)
const d2 = runOn(DESIGN, r2)

const tot = (x: { strict: number }[]) => x.reduce((a, r) => a + r.strict, 0)
const cnt = (x: { strict: number }[]) => x.filter(r => r.strict > 0).length

console.log('=== ホールドアウト5問 厳格(緩い)/探索項 ===')
console.log('問題                素             +COMB          +COMB2')
for (let i = 0; i < HOLDOUT.length; i++) {
  const f = (r: typeof hB[0]) => `${String(r.strict).padStart(3)}(${String(r.loose).padStart(3)})/${String(r.terms).padStart(4)}`
  console.log(`${HOLDOUT[i].id.padEnd(16)} ${f(hB[i])}   ${f(h1[i])}   ${f(h2[i])}`)
}
console.log(`\nホールドアウト到達問題数: 素 ${cnt(hB)}/5 → 第1ラウンド ${cnt(h1)}/5 → 第2ラウンド ${cnt(h2)}/5`)
console.log(`ホールドアウト厳格到達項: 素 ${tot(hB)} → ${tot(h1)} → ${tot(h2)}`)

console.log('\n=== 設計セット P1..P8（回帰チェック） ===')
console.log('問題                素             +COMB          +COMB2')
for (let i = 0; i < DESIGN.length; i++) {
  const f = (r: typeof dB[0]) => `${String(r.strict).padStart(3)}(${String(r.loose).padStart(3)})/${String(r.terms).padStart(4)}`
  console.log(`${DESIGN[i].id.padEnd(16)} ${f(dB[i])}   ${f(d1[i])}   ${f(d2[i])}`)
}
console.log(`\n設計セット到達問題数: 素 ${cnt(dB)}/8 → ${cnt(d1)}/8 → ${cnt(d2)}/8`)
console.log(`設計セット厳格到達項: 素 ${tot(dB)} → ${tot(d1)} → ${tot(d2)}`)

console.log('\n=== 第2ラウンド後のホールドアウト最短経路 ===')
for (const r of h2) {
  if (r.best) console.log(`${r.id.padEnd(16)} ${r.best.sort} 深さ${r.best.depth}\n    ${r.best.path.join(' → ')}`)
  else console.log(`${r.id.padEnd(16)} 未到達 / 到達ソート: ${r.reachable.join(', ')}`)
}

console.log('\n=== 第2ラウンドの4射: 足した理由の問題以外でも使われたか ===')
console.log('射名                            足した理由  ホールドアウト使用   設計セット使用')
const reason: Record<string, string> = {
  OrderFiltration: 'H1', OrderStatisticSelection: 'H1',
  LinearIterationOrbit: 'H3', ParameterPairIndexing: 'H2',
}
for (const m of COMB2) {
  const hu = h2.filter(r => r.used.includes(m.name)).map(r => r.id.split(' ')[0])
  const du = d2.filter(r => r.used.includes(m.name)).map(r => r.id.split(' ')[0])
  console.log(`${m.name.padEnd(30)} ${reason[m.name].padEnd(10)} ${(hu.join(',') || '—').padEnd(18)} ${du.join(',') || '—'}`)
}

console.log('\n=== 第1ラウンド20射: 設計セット/ホールドアウト 両方での使用 ===')
for (const m of COMB) {
  const hu = h2.filter(r => r.used.includes(m.name)).map(r => r.id.split(' ')[0])
  const du = d2.filter(r => r.used.includes(m.name)).map(r => r.id.split(' ')[0])
  const verdict = hu.length > 0 && du.length > 0 ? '語彙' : hu.length + du.length <= 1 ? '★暗記の疑い' : '設計セット内のみ'
  console.log(`${m.name.padEnd(30)} ${verdict.padEnd(16)} 設計[${du.join(',') || '—'}] HO[${hu.join(',') || '—'}]`)
}
