import assert from 'node:assert/strict'
import test from 'node:test'

import { hasCompleteParentProof } from './autonomous-synthesis'
import { capabilityOrigin } from './execution-certificate'
import { runPublicRuntimeGeneration } from './public-runtime-generation'
import { synthesizeRuntimePrimitiveRightTriangleProblems } from './runtime-primitive-right-triangle-generation'

const parents = [
  {
    id: 'primitive-right-triangle',
    statement: '直角三角形の3辺の長さを互いに素な自然数とする。',
  },
  {
    id: 'prime-radius-product',
    statement: '三角形の内接円半径と外接円半径の積が素数となる条件を考える。',
  },
]

test('classifies the primitive right triangle with prime radius product', () => {
  const result = synthesizeRuntimePrimitiveRightTriangleProblems(parents, 1)
  assert.equal(result.applicable, true)
  assert.equal(result.hypothesesEvaluated, 2)
  assert.equal(result.cards.length, 1)
  const card = result.cards[0]
  assert.match(card.answer_tex, /5,12,13/)
  assert.match(card.answer_tex, /13/)
  assert.equal(card.family_id, 'runtime.primitive_right_triangle_prime_radii')
  assert.equal(hasCompleteParentProof(card, parents), true)
  assert.equal(capabilityOrigin(card.execution_certificate), 'synthesized_proof_program')
  assert.equal(card.execution_certificate?.registered_composite_used, false)
  assert.equal((card.diagram as { kind?: string }).kind, 'plane')
  assert.equal((card.visual_explanation as { steps?: unknown[] }).steps?.length, 4)
})

test('generates several distinct questions from the same proved structure', () => {
  const result = synthesizeRuntimePrimitiveRightTriangleProblems(parents, 4)
  assert.equal(result.cards.length, 4)
  assert.equal(new Set(result.cards.map(card => card.statement_tex)).size, 4)
  assert.ok(result.cards.every(card => hasCompleteParentProof(card, parents)))
  assert.ok(result.cards.every(card => card.verification.exact_backend && card.verification.independent_check))
})

test('accepts equivalent English inputs in either parent order', () => {
  const reversed = [
    {
      id: 'radius-condition',
      statement: 'The product of the inradius and circumradius of a triangle is prime.',
    },
    {
      id: 'triangle-condition',
      statement: 'A primitive right triangle has pairwise coprime integer sides.',
    },
  ]
  const result = synthesizeRuntimePrimitiveRightTriangleProblems(reversed, 1)
  assert.equal(result.cards.length, 1)
  assert.match(result.cards[0].answer_tex, /5,12,13/)
  assert.equal(hasCompleteParentProof(result.cards[0], reversed), true)
})

test('public generation returns three proved questions without a queued search', () => {
  const result = runPublicRuntimeGeneration(parents, 3)
  assert.equal(result.cards.length, 3)
  assert.ok(result.cards.every(card => card.family_id === 'runtime.primitive_right_triangle_prime_radii'))
  assert.ok(result.cards.every(card => card.execution_certificate?.registered_composite_used === false))
})

test('does not claim the chart when a required semantic role is missing', () => {
  const result = synthesizeRuntimePrimitiveRightTriangleProblems([
    parents[0],
    { id: 'radii-only', statement: '三角形の内接円半径と外接円半径を考える。' },
  ], 1)
  assert.equal(result.applicable, false)
  assert.equal(result.cards.length, 0)
})
