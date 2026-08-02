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
  assert.match(result.certificate.proof_obligations[0], /No common executable codomain/)
})
