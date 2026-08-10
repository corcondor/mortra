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

const base = executableMorphismAtlas()
const b = run(base)
const c = run([...base, ...FIX, ...COMB])

console.log('=== ホールドアウト（設計に使っていない5問） 厳格(緩い)/探索項 ===')
console.log('問題                素            +COMB')
for (let i = 0; i < HOLDOUT.length; i++) {
  console.log(`${HOLDOUT[i].id.padEnd(16)} ${String(b[i].strict).padStart(3)}(${String(b[i].loose).padStart(3)})/${String(b[i].terms).padStart(4)}   ${String(c[i].strict).padStart(3)}(${String(c[i].loose).padStart(3)})/${String(c[i].terms).padStart(4)}`)
}
console.log(`\n厳格に到達した問題数: 素 ${b.filter(r => r.strict > 0).length}/5 → +COMB ${c.filter(r => r.strict > 0).length}/5`)
console.log(`厳格到達項の合計:     素 ${b.reduce((a, r) => a + r.strict, 0)} → +COMB ${c.reduce((a, r) => a + r.strict, 0)}`)

console.log('\n=== +COMB でのホールドアウト最短経路 ===')
for (const r of c) {
  if (r.best) console.log(`${r.id.padEnd(16)} ${r.best.sort} 深さ${r.best.depth}\n    ${r.best.path.join(' → ')}`)
  else console.log(`${r.id.padEnd(16)} 未到達 / 到達ソート: ${r.reachable.join(', ')}`)
}

console.log('\n=== ホールドアウトで実際に使われた追加射 ===')
for (const m of COMB) {
  const users = c.filter(r => r.used.includes(m.name)).map(r => r.id.split(' ')[0])
  console.log(`${m.name.padEnd(30)} ${users.length ? users.join(',') : '—'}`)
}
