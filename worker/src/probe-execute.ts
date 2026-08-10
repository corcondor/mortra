/**
 * 実験1: 到達した型付き経路を「実際に実行」しようとする。
 *
 * probe-user-problems.ts は goal.steps に morphism 名と backend 名を積むが、
 * その backend 名を受け取って計算を走らせる側が存在するかを、読まずに実行で確かめる。
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

const MODULES = [
  './generalization-kernel.ts', './typed-term-enumerator.ts', './executable-fusion.ts',
  './primitive-law-inducer.ts', './arithmetic-geometry-inducer.ts', './polynomial-root-fusion.ts',
  './autonomous-synthesis.ts', './parent-conditioned-discovery.ts', './mathematical-language.ts',
  './math-expression-ir.ts', './parent-obligation-coverage.ts',
]

async function main() {
  const rules = [...executableMorphismAtlas(), ...ADDED]
  const result = enumerateTypedTerms(
    [graph('余弦定理', ['Triangle', 'TriangleMetricData'], ['Real', 'Scalar', 'Quantity'])],
    { maxDepth: 6, maxStates: 40_000, goalSorts: ['Real', 'Scalar', 'Quantity'], rules },
  )
  const goal = result.goals[0]

  console.log('=== (a) 到達した goal term ===')
  console.log('sort      :', goal.sort)
  console.log('depth     :', goal.depth)
  console.log('expression:', goal.expression)
  for (const s of goal.steps) {
    console.log(`  ${s.morphism.padEnd(26)} ${s.sources.join('×')} -> ${s.target}   backend=[${s.backend.join(', ')}]`)
  }

  console.log('\n=== (b) worker/src 全 export を集める ===')
  const scope: Record<string, unknown> = {}
  for (const m of MODULES) {
    const mod = await import(m)
    for (const [k, v] of Object.entries(mod)) scope[k] = v
  }
  console.log(`export 総数: ${Object.keys(scope).length}`)

  console.log('\n=== (c) 経路に現れる射名が実体を持つか ===')
  for (const name of [...new Set(goal.steps.map(s => s.morphism))]) {
    const v = scope[name]
    console.log(`  ${name.padEnd(26)} -> ${v === undefined ? '未定義（実装が無い）' : typeof v}`)
  }

  console.log('\n=== (d) expression を実際に評価してみる ===')
  scope.ParentObject = (parentId: string, sort: string) => ({ parentId, sort })
  try {
    const names = Object.keys(scope)
    const fn = new Function(...names, `return (${goal.expression})`)
    console.log('評価成功:', fn(...names.map(n => scope[n])))
  } catch (error) {
    console.log('評価失敗:', (error as Error).message)
  }

  console.log('\n=== (e) backend 名を実行に振り分ける表を探す ===')
  for (const b of [...new Set(goal.steps.flatMap(s => s.backend))]) {
    const hit = Object.entries(scope).filter(([, v]) => typeof v === 'function' && String(v).includes(b))
    console.log(`  backend '${b}' を文字列として持つ関数: ${hit.length ? hit.map(([k]) => k).join(', ') : 'なし'}`)
  }
}

void main()
