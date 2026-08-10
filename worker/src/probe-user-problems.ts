/** 本体に入れた後の最終確認。外から射を渡さず、素の executableMorphismAtlas() だけを使う */
import { enumerateTypedTerms } from './typed-term-enumerator.ts'
import { executableMorphismAtlas } from './generalization-kernel.ts'
import type { SemanticHypergraph } from './generalization-kernel.ts'

const g = (id: string, roots: string[], goals: string[]): SemanticHypergraph => ({
  parent_id: id,
  nodes: roots.map((sort, i) => ({ id: `${id}:n${i}`, sort, label: sort } as never)),
  edges: [], root_sorts: roots, query_sorts: goals,
  language_analysis: {
    token_count: 0, parse_count: 1, parse_truncated: false, clause_count: 1,
    quantifier_prefix: [], definitions: [], declarations: [],
    constraints: [], unresolved_references: [], diagnostics: [],
  },
})

const atlas = executableMorphismAtlas()

// 次数の監査
const inD = new Map<string, number>(), outD = new Map<string, number>(), sorts = new Set<string>()
for (const r of atlas) {
  for (const x of r.sources) { sorts.add(x); outD.set(x, (outD.get(x) ?? 0) + 1) }
  sorts.add(r.target); inD.set(r.target, (inD.get(r.target) ?? 0) + 1)
}
const bad = [...sorts].filter(s => (inD.get(s) ?? 0) === 0 || (outD.get(s) ?? 0) === 0)
console.log(`本体のアトラス: 射 ${atlas.length} / ソート ${sorts.size} / 欠陥 ${bad.length}`)
if (bad.length) console.log(`  残: ${bad.join(', ')}`)

const CASES = [
  ['幾何', '余弦定理', ['Triangle', 'TriangleMetricData'], ['Real']],
  ['幾何', '通過領域', ['GeometricConfiguration', 'Sequence'], ['Real']],
  ['複素数', '1のn乗根', ['FiniteAlgebraicOrbit', 'Polynomial'], ['Real']],
  ['複素数', 'Mobius反復', ['RationalSelfMap', 'Orbit'], ['Real']],
  ['整数', 'gcd/lcm', ['Integer', 'GCDValue'], ['Integer', 'Real']],
  ['整数', '整数判定', ['Polynomial', 'Integer'], ['IntegerPredicate']],
  ['漸化式', '線形漸化式', ['Matrix2', 'Sequence'], ['Real']],
  ['漸化式', '確率漸化式', ['Sequence', 'FiniteSet'], ['Real']],
  ['不等式', '大小比較', ['Real', 'Real'], ['Proposition']],
  ['解析', '関数の極値', ['DifferentiableFunction'], ['Real']],
  ['領域', '半代数集合', ['SemialgebraicSet', 'Polynomial'], ['Real', 'Proposition']],
  ['組合せ', '数え上げ', ['FiniteFamily', 'FiniteSet'], ['Integer']],
  ['漸化式', '特性根から一般項', ['Matrix2'], ['Real']],
  ['解析', '多項式の極値', ['Polynomial'], ['Real']],
  ['幾何', '整数三角形', ['IntegralTriangle'], ['Real']],
  ['証明', '不等式の連言', ['Real', 'Real'], ['Proposition']],
] as const

console.log('\n分野      問題                 到達')
let ok = 0
for (const [d, id, roots, goals] of CASES) {
  const n = enumerateTypedTerms([g(id, [...roots], [...goals])], {
    maxDepth: 6, maxStates: 40_000, goalSorts: [...goals],
  }).goals.length
  if (n > 0) ok++
  console.log(`${d.padEnd(7)} ${id.padEnd(18)} ${String(n).padStart(4)}  ${n > 0 ? '' : '未到達'}`)
}
console.log(`\n到達 ${ok} / ${CASES.length}`)
