import assert from 'node:assert/strict'
import test from 'node:test'
import { capabilityOrigin } from './execution-certificate'
import { runPublicRuntimeGeneration } from './public-runtime-generation'

test('public gateway derives an unseen fusion without a registered completed route', () => {
  const result = runPublicRuntimeGeneration([
    { id: 'cold-polynomial-a', statement: 'x^2-2=0 のすべての実数解を考える。' },
    { id: 'cold-polynomial-b', statement: 'y^2-3=0 のすべての実数解を考える。' },
  ], 1)

  assert.equal(result.cards.length, 1)
  const card = result.cards[0]
  assert.deepEqual(new Set(card.parent_ids), new Set(['cold-polynomial-a', 'cold-polynomial-b']))
  assert.match(capabilityOrigin(card.execution_certificate) ?? '', /^synthesized_/)
  assert.equal(card.execution_certificate?.registered_composite_used, false)
  assert.equal(result.cards.some(candidate =>
    capabilityOrigin(candidate.execution_certificate) === 'registered_parameterized_morphism' ||
    candidate.execution_certificate?.registered_composite_used === true,
  ), false)
})

test('public gateway re-synthesizes inputs shaped like an old registered case', () => {
  const result = runPublicRuntimeGeneration([
    { id: 'known-shape-cubic', statement: 'u^3-7u+3=0 の根を考える。' },
    { id: 'known-shape-quadratic', statement: 'v^2+v-5=0 の根を考える。' },
  ], 2)

  assert.equal(result.cards.length, 2)
  for (const card of result.cards) {
    assert.deepEqual(new Set(card.parent_ids), new Set(['known-shape-cubic', 'known-shape-quadratic']))
    assert.match(capabilityOrigin(card.execution_certificate) ?? '', /^synthesized_/)
    assert.equal(card.execution_certificate?.registered_composite_used, false)
  }
})

test('public gateway fuses the two shear maps when users submit them as separate parents', () => {
  const parents = [
    {
      id: 'public-left-shear',
      statement: String.raw`整数の組に対する写像 \(L(x,y)=(x+y,y)\) を考える。`,
    },
    {
      id: 'public-right-shear',
      statement: String.raw`整数の組に対する写像 \(R(u,v)=(u,u+v)\) を考える。`,
    },
  ]
  const result = runPublicRuntimeGeneration(parents, 2)

  assert.equal(result.cards.length, 2)
  for (const card of result.cards) {
    assert.deepEqual(card.parent_ids, ['public-left-shear', 'public-right-shear'])
    assert.deepEqual(
      card.fusion_derivation.assignments.map(item => item.parentId),
      ['public-left-shear', 'public-right-shear'],
    )
    assert.equal(card.structure_blueprint.synthesizedLaw?.arity, 2)
    assert.equal(capabilityOrigin(card.execution_certificate), 'synthesized_proof_program')
    assert.equal(card.execution_certificate?.registered_composite_used, false)
    assert.equal(card.unresolved, false)
  }
})
