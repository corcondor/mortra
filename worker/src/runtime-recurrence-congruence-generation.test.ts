import assert from 'node:assert/strict'
import test from 'node:test'

import { hasCompleteParentProof } from './autonomous-synthesis'
import { capabilityOrigin } from './execution-certificate'
import { runPublicRuntimeGeneration } from './public-runtime-generation'
import { synthesizeRuntimeRecurrenceCongruenceProblems } from './runtime-recurrence-congruence-generation'

const parents = [
  {
    id: 'unseen-recurrence',
    statement: '整数列 {a_n} を a_0=1, a_1=4, a_{n+2}=a_{n+1}+a_n で定める。',
  },
  {
    id: 'unseen-congruence',
    statement: '整数 x について、5x≡1 (mod 13) を満たす剰余類を求めよ。',
  },
]

test('pulls a current congruence back through a complete current recurrence orbit', () => {
  const result = synthesizeRuntimeRecurrenceCongruenceProblems(parents, 1)
  assert.equal(result.applicable, true)
  assert.equal(result.cards.length, 1)
  const card = result.cards[0]
  assert.equal(card.family_id, 'runtime.recurrence_congruence_orbit')
  assert.match(card.answer_tex, /7\+28k/)
  assert.equal(hasCompleteParentProof(card, parents), true)
  assert.equal(capabilityOrigin(card.execution_certificate), 'synthesized_proof_program')
  assert.equal(card.execution_certificate?.registered_composite_used, false)
  assert.equal(card.diagram && (card.diagram as { kind?: string }).kind, 'state')
})

test('generates several shifted observations without changing the primitive vocabulary', () => {
  const result = synthesizeRuntimeRecurrenceCongruenceProblems(parents, 5)
  assert.equal(result.cards.length, 5)
  assert.equal(new Set(result.cards.map(card => card.statement_tex)).size, 5)
  assert.ok(result.cards.every(card => hasCompleteParentProof(card, parents)))
  assert.ok(result.cards.every(card => card.verification.exact_backend && card.verification.independent_check))
})

test('accepts the parents in either order and supports an affine recurrence', () => {
  const reversed = [
    { id: 'mod-condition', statement: '3z≡2 (mod 11) を満たす整数 z を考える。' },
    { id: 'affine-recurrence', statement: '数列 b_n を b_0=2, b_1=3, b_{n+2}=2b_{n+1}-b_n+1 で定める。' },
  ]
  const result = synthesizeRuntimeRecurrenceCongruenceProblems(reversed, 2)
  assert.equal(result.cards.length, 2)
  assert.ok(result.cards.every(card => hasCompleteParentProof(card, reversed)))
  assert.match(result.cards[0].statement_tex, /b_\{n\+2\}=2b_\{n\+1\}-b_n\+1/)
  assert.doesNotMatch(result.cards[0].statement_tex, /b_n\+\\\)/)
})

test('changing either current parent changes the generated certified result', () => {
  const baseline = synthesizeRuntimeRecurrenceCongruenceProblems(parents, 1).cards[0]
  const changedRecurrence = synthesizeRuntimeRecurrenceCongruenceProblems([
    { ...parents[0], statement: '整数列 {a_n} を a_0=2, a_1=4, a_{n+2}=a_{n+1}+a_n で定める。' },
    parents[1],
  ], 1).cards[0]
  const changedCongruence = synthesizeRuntimeRecurrenceCongruenceProblems([
    parents[0],
    { ...parents[1], statement: '整数 x について、5x≡2 (mod 13) を満たす剰余類を求めよ。' },
  ], 1).cards[0]
  assert.ok(baseline && changedRecurrence && changedCongruence)
  assert.notEqual(changedRecurrence.answer_tex, baseline.answer_tex)
  assert.notEqual(changedCongruence.answer_tex, baseline.answer_tex)
})

test('public generation resolves the recurrence-congruence pair immediately', () => {
  const result = runPublicRuntimeGeneration(parents, 3)
  assert.equal(result.cards.length, 3)
  assert.ok(result.cards.every(card => card.family_id === 'runtime.recurrence_congruence_orbit'))
  assert.ok(result.cards.every(card => card.execution_certificate?.registered_composite_used === false))
})

test('abstains instead of inventing missing initial values', () => {
  const result = synthesizeRuntimeRecurrenceCongruenceProblems([
    { id: 'missing-initial', statement: '数列 a_n を a_{n+2}=a_{n+1}+a_n で定める。' },
    parents[1],
  ], 1)
  assert.equal(result.cards.length, 0)
  assert.equal(result.applicable, false)
})
