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
