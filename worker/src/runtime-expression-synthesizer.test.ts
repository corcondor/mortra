import assert from 'node:assert/strict'
import test from 'node:test'

import { hasCompleteParentProof, runAutonomousSynthesis } from './autonomous-synthesis'
import {
  clearRuntimeExpressionSynthesisCache,
  synthesizeRuntimeExpressionProblems,
} from './runtime-expression-synthesizer'

const unseenParents = [
  {
    id: 'fresh-integral-parent',
    statement: String.raw`\[\int_0^1 x^2\,dx\]を求めよ。`,
  },
  {
    id: 'fresh-sum-limit-parent',
    statement: String.raw`\[\lim_{r\to\infty}\frac{\sum_{j=1}^{r}j}{r^2}\]を求めよ。`,
  },
]

test('enumerates a fresh multi-parent program from current expression ASTs only', () => {
  clearRuntimeExpressionSynthesisCache()
  const result = synthesizeRuntimeExpressionProblems(unseenParents, 3)

  assert.equal(result.applicable, true)
  assert.equal(result.cards.length, 3)
  assert.ok(result.hypothesesEvaluated > result.cards.length)
  for (const card of result.cards) {
    assert.deepEqual(new Set(card.parent_ids), new Set(unseenParents.map(parent => parent.id)))
    assert.equal(card.family_id, 'runtime.expression_grammar')
    assert.equal(card.execution_certificate?.capability_origin, 'synthesized_expression_program')
    assert.equal(card.execution_certificate?.registered_composite_used, false)
    assert.equal(card.execution_certificate?.composite_cache_role, 'not_consulted')
    assert.equal(hasCompleteParentProof(card, unseenParents), true)
    const program = card.execution_certificate?.generated_program as Record<string, unknown>
    assert.ok(Array.isArray(program.generated_ast))
    assert.deepEqual(
      Object.keys(program.parent_ablation_results as Record<string, unknown>).sort(),
      unseenParents.map(parent => parent.id).sort(),
    )
  }
})

test('uses the runtime expression grammar in the autonomous strategy chain', () => {
  clearRuntimeExpressionSynthesisCache()
  const result = runAutonomousSynthesis(unseenParents, 2)

  assert.equal(result.cards.length, 2)
  const attempt = result.attempts.find(item => item.strategy === 'runtime-expression-grammar')
  assert.ok(attempt)
  assert.equal(attempt.applicable, true)
  assert.equal(attempt.generated, 2)
  assert.ok(result.cards.every(card =>
    card.execution_certificate?.capability_origin === 'synthesized_expression_program'))
})

test('changed current input changes the synthesized program instead of replaying a card', () => {
  clearRuntimeExpressionSynthesisCache()
  const first = synthesizeRuntimeExpressionProblems(unseenParents, 1).cards[0]
  const changedParents = [
    unseenParents[0],
    {
      id: 'fresh-renamed-sum-limit-parent',
      statement: String.raw`\[\lim_{s\to\infty}\frac{\sum_{k=1}^{s}k^2}{s^3}\]を求めよ。`,
    },
  ]
  const second = synthesizeRuntimeExpressionProblems(changedParents, 1).cards[0]

  assert.ok(first)
  assert.ok(second)
  assert.notEqual(first.id, second.id)
  assert.notDeepEqual(
    first.execution_certificate?.generated_program,
    second.execution_certificate?.generated_program,
  )
})

test('does not fabricate an expression when a parent supplies only a topic label', () => {
  clearRuntimeExpressionSynthesisCache()
  const result = synthesizeRuntimeExpressionProblems([
    unseenParents[0],
    { id: 'opaque-parent', statement: '数列と極限について考える。' },
  ], 1)

  assert.equal(result.applicable, false)
  assert.equal(result.cards.length, 0)
  assert.match(result.reason, /lacks a concrete binder-aware expression/)
})
