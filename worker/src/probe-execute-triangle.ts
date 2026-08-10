/**
 * 実験2: 到達した経路を実際に走らせて値を出す。
 *
 * enumerateTypedTerms が返した goal.steps（射名と backend 名の列）を、
 * そのまま backend/triangle_metric_ideal.py に渡して実行する。
 * 経路は列挙器が見つけたものをそのまま使い、手で並べ替えない。
 *
 * AB=7, BC=5, CA=3 の三角形で cos A を求める。
 */
import { spawnSync } from 'node:child_process'
import path from 'node:path'
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

const ADDED: HyperMorphismSchema[] = [
  { name: 'ScalarAsReal', sources: ['Scalar'], target: 'Real', preserves: ['value'], backend: ['identity'] },
  { name: 'RealAsScalar', sources: ['Real'], target: 'Scalar', preserves: ['value'], backend: ['identity'] },
  { name: 'MetricRelationIdeal', sources: ['TriangleMetricData'], target: 'PolynomialSystem', preserves: ['metric'], backend: ['sympy.groebner'] },
  { name: 'DesignatedRootEvaluation', sources: ['AlgebraicSet'], target: 'Real', preserves: ['exactness'], backend: ['sympy.solve'] },
  { name: 'IntegerInclusion', sources: ['Integer'], target: 'Real', preserves: ['value'], backend: ['identity'] },
  { name: 'RealFieldCombination', sources: ['Real', 'Real'], target: 'Real', preserves: ['exactness'], backend: ['sympy.simplify'] },
  { name: 'OrderComparison', sources: ['Real', 'Real'], target: 'Proposition', preserves: ['order'], backend: ['cvc5'] },
  { name: 'TriangleAsConfiguration', sources: ['Triangle'], target: 'GeometricConfiguration', preserves: ['incidence'], backend: ['identity'] },
]

const rules = [...executableMorphismAtlas(), ...ADDED]
const enumeration = enumerateTypedTerms(
  [graph('余弦定理', ['Triangle', 'TriangleMetricData'], ['Real', 'Scalar', 'Quantity'])],
  { maxDepth: 6, maxStates: 40_000, goalSorts: ['Real', 'Scalar', 'Quantity'], rules },
)

const goal = enumeration.goals.find(term =>
  term.steps.some(step => step.morphism === 'MetricRelationIdeal') &&
  term.steps.some(step => step.morphism === 'DesignatedRootEvaluation'))

if (!goal) {
  console.log('MetricRelationIdeal を通る経路が到達しなかった')
  process.exit(1)
}

console.log('=== 列挙器が返した経路（手で書いていない） ===')
console.log(goal.expression)
console.log(goal.steps.map(s => `${s.morphism}[${s.backend.join(',')}]`).join(' → '))

// AB=7, BC=5, CA=3。標準記法では a=BC, b=CA, c=AB
const request = {
  steps: goal.steps.map(s => ({ morphism: s.morphism, backend: s.backend })),
  data: { vertex: 'A', sides: { a: 5, b: 3, c: 7 } },
}

const script = path.resolve(__dirname, '..', 'backend', 'triangle_metric_ideal.py')
const proc = spawnSync('python', [script], {
  input: JSON.stringify(request), encoding: 'utf8', timeout: 120_000, maxBuffer: 8 * 1024 * 1024,
})
if (proc.stderr) console.error(proc.stderr)
const out = JSON.parse(proc.stdout) as {
  error?: string
  trace: Array<{ morphism: string; backend: string[]; status: string; output_sort?: string; output?: Record<string, unknown> }>
  result?: Record<string, unknown>
}

console.log('\n=== 各射の実行結果 ===')
for (const step of out.trace) {
  console.log(`\n[${step.status}] ${step.morphism}  backend=${JSON.stringify(step.backend)} -> ${step.output_sort ?? '-'}`)
  const o = step.output as Record<string, string[] | string> | undefined
  if (!o) continue
  if (o.generators_str) console.log('  生成元:', (o.generators_str as string[]).join('  |  '))
  if (o.eliminated_generators_str) console.log('  x,y 消去後:', (o.eliminated_generators_str as string[]).join('  |  '))
  if (o.substituted_relations) console.log('  辺長代入後:', (o.substituted_relations as string[]).join('  |  '))
  if (o.all_roots) console.log('  実根 (-1,1):', (o.all_roots as string[]).join(', '))
}

console.log('\n=== 出た値 ===')
const value = out.result?.value as string | null | undefined
console.log('cos A =', value ?? '(値が出なかった)')
console.log('数値  =', out.result?.value_float)
console.log('11/14 =', 11 / 14)
console.log('一致  :', value === '11/14' ? 'yes' : 'no')
