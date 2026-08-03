import assert from 'node:assert/strict'
import test from 'node:test'
import { generalizeParents } from './generalization-kernel'
import { enumerateTypedTerms } from './typed-term-enumerator'

test('enumerates a full-provenance term by type, not by a remembered family id', () => {
  const parents = [
    { id: 'map-parent', statement: '一次分数変換 \\(T(z)=\\frac{2z+1}{z+1}\\) を反復する。' },
    { id: 'orbit-parent', statement: '\\(z^n=1\\) のすべての根を考える。' },
  ]
  const generalized = generalizeParents(parents, 6, 10_000)
  const result = enumerateTypedTerms(generalized.graphs, { maxDepth: 6, maxStates: 10_000 })
  const goal = result.goals.find(term => term.sort === 'Scalar')
  assert.ok(goal)
  assert.deepEqual(goal.parentIds, ['map-parent', 'orbit-parent'])
  assert.ok(goal.steps.some(step => step.morphism === 'MapOrbitEvaluation'))
  assert.ok(goal.steps.every(step => step.backend.length > 0))
})

test('does not manufacture a full-provenance goal when no typed bridge exists', () => {
  const parents = [
    { id: 'prime-parent', statement: '素数 p に対して命題を示せ。' },
    { id: 'curve-parent', statement: '曲線 C の接線を求めよ。' },
  ]
  const generalized = generalizeParents(parents, 5, 2_000)
  const result = enumerateTypedTerms(generalized.graphs, { maxDepth: 5, maxStates: 2_000 })
  assert.equal(result.goals.length, 0)
  assert.ok(result.terms.every(term => term.parentIds.length === 1))
})
