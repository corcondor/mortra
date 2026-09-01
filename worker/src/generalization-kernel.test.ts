import assert from 'node:assert/strict'
import test from 'node:test'
import { buildSemanticHypergraph, generalizeParents } from './generalization-kernel'

test('builds semantic operators and queries without using a problem id', () => {
  const graph = buildSemanticHypergraph({
    id: 'arbitrary-id',
    statement: '曲線 y=x^3-2x の接線の交点が描く軌跡の面積の最大値を求めよ。',
  })
  const canonical = graph.nodes.map(node => node.canonical)
  assert.ok(canonical.includes('Tangent'))
  assert.ok(canonical.includes('Locus'))
  assert.ok(canonical.includes('Measure'))
  assert.ok(canonical.includes('Extremum'))
})

test('surface and number perturbations preserve the anti-unified roadmap', () => {
  const left = generalizeParents([
    { statement: '曲線 y=x^3-2x の接線の交点の軌跡を求めよ。' },
    { statement: '座標平面上の図形を方程式で表し、面積を求めよ。' },
  ])
  const right = generalizeParents([
    { statement: '曲線 y=t^3-7t の接線の交点の軌跡を求めよ。' },
    { statement: '座標平面上の領域を方程式で表し、面積を求めよ。' },
  ])
  assert.equal(left.certificate.target_sort, right.certificate.target_sort)
  assert.deepEqual(
    left.certificate.roadmap.map(step => [step.source, step.target, step.morphism]),
    right.certificate.roadmap.map(step => [step.source, step.target, step.morphism]),
  )
})

test('does not fabricate a common target for disconnected opaque structures', () => {
  const result = generalizeParents([
    { statement: '未知対象 foo に操作 bar を施す。' },
    { statement: '別の未知対象 baz を考える。' },
  ])
  assert.equal(result.certificate.target_sort, null)
  assert.equal(result.certificate.roadmap.length, 0)
  assert.match(result.certificate.proof_obligations[0], /No joint executable construction/)
})

test('plans a genuine multi-input roadmap for a map acting on a finite orbit', () => {
  const result = generalizeParents([
    { id: 'map', statement: '一次分数変換 T(z)=\\frac{3z+2}{z+2} を考える。' },
    { id: 'orbit', statement: 'z_1,\\ldots,z_n を z^n=1 の全ての解とする。' },
  ], 4)
  assert.equal(result.certificate.target_sort, 'Scalar')
  assert.ok(result.certificate.typed_proof_obligations.length > 0)
  assert.ok(result.certificate.typed_proof_obligations.every(item => item.status === 'open'))
  assert.deepEqual(
    result.certificate.roadmap.map(step => step.morphism),
    ['MobiusRealization', 'RootsOfUnity', 'MapOrbitEvaluation', 'FiniteSummation'],
  )
  assert.deepEqual(result.certificate.roadmap[2].parent_ids.sort(), ['map', 'orbit'])
})

test('sharing only a scalar codomain is not accepted as a fusion', () => {
  const result = generalizeParents([
    { id: 'integral', statement: '関数 f の積分で定まる数列の極限を求めよ。' },
    { id: 'solid', statement: '四面体を平面で切断して得られる断面積の最大値を求めよ。' },
  ], 5)
  assert.equal(result.certificate.target_sort, null)
  assert.equal(result.certificate.roadmap.length, 0)
})

test('a detected operator from one parent may act on a compatible object from another parent', () => {
  const result = generalizeParents([
    { id: 'operator', statement: '関数 f を積分して値を求めよ。' },
    { id: 'object', statement: '関数 g(x) に対し方程式 g(x)=0 の根を考える。' },
  ], 4)
  const step = result.certificate.roadmap.find(item => item.morphism === 'Integral')
  assert.ok(step)
  assert.deepEqual(new Set(step.parent_ids), new Set(['operator', 'object']))
})

test('a query word alone does not count as a parent contribution', () => {
  const result = generalizeParents([
    { id: 'equation', statement: '関数 f に対し I_n=\\int_0^1 x^n f(x)dx と定める。' },
    { id: 'proof-query', statement: '素数 p と整数 a に対し、条件を示せ。' },
  ], 5)
  assert.equal(result.certificate.target_sort, null)
})

test('gcd and lcm are typed operators joined by a reusable product law', () => {
  const first = generalizeParents([
    { id: 'gcd-parent', statement: '正整数 m,n の最大公約数 gcd(m,n) を考える。' },
    { id: 'lcm-parent', statement: '正整数 a,b の最小公倍数 lcm(a,b) を考える。' },
  ], 6)
  const perturbed = generalizeParents([
    { id: 'gcd-parent-2', statement: '整数 x,y に対して \\gcd(x,y)=14 とする。' },
    { id: 'lcm-parent-2', statement: '整数 u,v に対して \\operatorname{lcm}(u,v)=630 とする。' },
  ], 6)
  const chain = first.certificate.roadmap.map(step => step.morphism)
  assert.ok(chain.includes('GCDLCMProductLaw'))
  assert.equal(first.certificate.target_sort, 'Integer')
  assert.equal(perturbed.certificate.target_sort, 'Integer')
  assert.ok(perturbed.certificate.roadmap.some(step => step.morphism === 'GCDLCMProductLaw'))
})

test('rounding and percent syntax lift to typed backend contracts', () => {
  const ceiling = buildSemanticHypergraph({ statement: '実数 x に対し \\lceil x \\rceil+x=23/7 とする。' })
  const percent = buildSemanticHypergraph({ statement: '量 A の 35% を求める。' })
  assert.ok(ceiling.edges.some(edge =>
    edge.morphism === 'CeilingProjection' && edge.source === 'Real' && edge.target === 'Integer' &&
    edge.backend.includes('exact-rounding'),
  ))
  assert.ok(percent.edges.some(edge =>
    edge.morphism === 'PercentScalarAction' && edge.source === 'RateQuantityPair' &&
    edge.backend.includes('rational-arithmetic'),
  ))
})

test('the language query is wired into a typed Worker goal', () => {
  const algebra = buildSemanticHypergraph({ statement: '実数 x,y が x+y=5 を満たすとき x^2+y^2 を求めよ。' })
  const proof = buildSemanticHypergraph({ statement: 'For every integer n, prove that n(n+1) is even.' })
  assert.deepEqual(algebra.query_sorts, ['Scalar'])
  assert.deepEqual(proof.query_sorts, ['Proof'])
})

test('grounds an executable constraint IR only after exact query-directed lowering succeeds', () => {
  const solvable = buildSemanticHypergraph({
    id: 'fresh-linear-ir',
    statement: String.raw`方程式 \(7x-5=30\) を解け。`,
  })
  const nonlinear = buildSemanticHypergraph({
    id: 'nonlinear-open-ir',
    statement: String.raw`方程式 \(x^2+x+1=0\) の解を求めよ。`,
  })
  assert.ok(solvable.root_bindings?.some(binding =>
    binding.sort === 'ExecutableConstraintIR' && binding.canonical.startsWith('ConstraintIR[')))
  assert.equal(nonlinear.root_bindings?.some(binding =>
    binding.sort === 'ExecutableConstraintIR'), false)
})

test('separates proof assumptions, quantified context, and the demanded proposition', () => {
  const graph = buildSemanticHypergraph({
    id: 'proof-separation',
    statement: '整数 n に対し、n>0 ならば n^2>0 を示せ。',
  })
  assert.ok(graph.root_sorts.includes('AssumptionProposition'))
  assert.ok(!graph.root_sorts.includes('GoalProposition'))
  assert.ok(!graph.root_sorts.includes('Proposition'))
  assert.ok(!graph.root_sorts.includes('QuantifierContext'))
  assert.deepEqual(
    graph.root_bindings?.filter(binding => binding.role === 'assumption').map(binding => binding.canonical),
    ['Relation[>,v0,0]'],
  )
  assert.deepEqual(
    graph.query_bindings?.map(binding => [binding.sort, binding.canonical]),
    [['GoalProposition', 'Relation[>,v0^2,0]']],
  )
  assert.deepEqual(
    graph.language_analysis.constraints.map(constraint => constraint.role),
    ['assumption', 'goal'],
  )
})

test('does not invent an operator input merely because the operation is mentioned', () => {
  const graph = buildSemanticHypergraph({
    id: 'ungrounded-limit',
    statement: '未知の数列の極限を求めよ。',
  })
  assert.equal(graph.root_sorts.includes('FilteredObject'), false)
  assert.equal(graph.root_sorts.includes('FiniteFamily'), false)
  assert.equal(graph.root_bindings?.some(binding =>
    binding.canonical.startsWith('InferredInput[')), false)
})

test('grounds a nested query from the current expression AST rather than an Atlas route', () => {
  const graph = buildSemanticHypergraph({
    id: 'fresh-limit-sum',
    statement: String.raw`\[\lim_{r\to\infty}\{\sum_{j=0}^{r}j-r^2\}\]を求めよ。`,
  })
  assert.deepEqual(graph.query_expression_ir, [
    'Limit',
    'r',
    'Infinity',
    ['Subtract', ['Sum', 'j', 0, 'r', 'j'], ['Power', 'r', 2]],
  ])
  assert.ok(graph.root_bindings?.some(binding =>
    binding.sort === 'ExecutableExpression' && binding.canonical.startsWith('ExpressionIR[')))
  assert.ok(graph.edges.some(edge =>
    edge.morphism === 'EvaluateExpression' && edge.source === 'ExecutableExpression'))
})

test('query operators are taken from the demanded clause, not background wording', () => {
  const minimalPolynomial = buildSemanticHypergraph({
    statement: String.raw`\(\alpha\) の最小多項式を \(f(x)\) とする。
      \(g(S)=C_0+C_1/S\) の定数項 \(C_0\) を求めよ。`,
  })
  const finalSeries = buildSemanticHypergraph({
    statement: String.raw`立体の体積を \(V_n\) とする。(1) \(V_n\) を求めよ。
      (2) \(\sum_{k=1}^{\infty}1/k^2\) を求めよ。`,
  })
  assert.equal(minimalPolynomial.nodes.some(node => node.canonical === 'Extremum'), false)
  assert.equal(finalSeries.nodes.some(node => node.canonical === 'Measure'), false)
})

test('a query may recover an observable through an exact named reference', () => {
  const graph = buildSemanticHypergraph({
    statement: String.raw`双曲線の弧と線分に囲まれる面積を \(S_k\) とする。\(S_k\) を求めよ。`,
  })
  assert.ok(graph.nodes.some(node => node.canonical === 'Measure'))
})

test('direct measure and extremum requests remain attached to the final query', () => {
  const graph = buildSemanticHypergraph({
    statement: String.raw`曲線上の三点を A,B,C とする。三角形 ABC の面積の最小値を求めよ。`,
  })
  assert.ok(graph.nodes.some(node => node.canonical === 'Measure'))
  assert.ok(graph.nodes.some(node => node.canonical === 'Extremum'))
})

test('keeps intermediate observables out of the final proof demand', () => {
  const graph = buildSemanticHypergraph({
    statement: String.raw`三角形の面積の最大値は \(5\) 未満であることを示せ。`,
  })
  assert.ok(graph.nodes.some(node => node.canonical === 'Measure'))
  assert.ok(graph.nodes.some(node => node.canonical === 'Extremum'))
  assert.deepEqual(graph.query_sorts, ['Proof'])
})

test('uses the cardinality codomain for an explicit counting query', () => {
  const graph = buildSemanticHypergraph({
    statement: String.raw`条件を満たす整数の個数を求めよ。`,
  })
  assert.deepEqual(graph.query_sorts, ['Integer'])
})
