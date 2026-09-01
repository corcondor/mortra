import assert from 'node:assert/strict'
import test from 'node:test'

import { hasCompleteParentProof, runAutonomousSynthesis } from './autonomous-synthesis'
import {
  clearExactCasSynthesisCache,
  synthesizeExactCasSingleProblem,
  synthesizeExactCasSingleProblemBatch,
} from './single-problem-cas'

test('solves an unregistered cubic in cold mode and replays its cross-runtime certificate', () => {
  clearExactCasSynthesisCache()
  const parents = [{ id: 'unseen-cubic', statement: '方程式 $x^3-7x+3=0$ を解け。' }]
  const result = synthesizeExactCasSingleProblem(parents)
  assert.equal(result.applicable, true)
  assert.equal(result.cards.length, 1)
  assert.match(result.cards[0].answer_tex, /\\arccos/)
  assert.doesNotMatch(result.cards[0].solution_tex, /\\sqrt\{--/)
  assert.equal(result.cards[0].structure_blueprint.domain, 'unregistered_typed_problem')
  assert.equal(hasCompleteParentProof(result.cards[0], parents), true)
})

test('routes an unregistered definite integral through the persistent worker strategy', () => {
  clearExactCasSynthesisCache()
  const parents = [{ id: 'unseen-integral', statement: '$\\int_0^1 t^2\\,dt$ を求めよ。' }]
  const result = runAutonomousSynthesis(parents, 1)
  assert.equal(result.cards.length, 1)
  assert.equal(result.cards[0].answer_tex, '\\(\\frac{1}{3}\\)')
  assert.equal(result.attempts[0].strategy, 'exact-single-problem-proof-synthesis')
  assert.equal(result.attempts[0].applicable, false)
  assert.equal(result.attempts[1].strategy, 'exact-cas-single-problem-proof-synthesis')
  assert.equal(result.attempts[1].generated, 1)
  assert.equal(hasCompleteParentProof(result.cards[0], parents), true)
  assert.equal(result.cards[0].family_id, 'solve.runtime.exact_expression_ir')
  assert.equal(result.cards[0].execution_certificate?.registered_composite_used, false)
})

test('evaluates a fresh nested sum-limit directly from its binder AST', () => {
  clearExactCasSynthesisCache()
  const parents = [{
    id: 'fresh-sum-limit',
    statement: String.raw`\[\lim_{r\to\infty}\frac{\sum_{j=1}^{r}j}{r^2}\]を求めよ。`,
  }]
  const result = synthesizeExactCasSingleProblem(parents)
  assert.equal(result.applicable, true)
  assert.equal(result.cards[0].answer_tex, String.raw`\(\frac{1}{2}\)`)
  assert.equal(result.cards[0].family_id, 'solve.runtime.exact_expression_ir')
  assert.equal(result.cards[0].execution_certificate?.registered_composite_used, false)
  assert.ok(Array.isArray(result.cards[0].execution_certificate?.morphism_chain))
  assert.equal(hasCompleteParentProof(result.cards[0], parents), true)
})

test('evaluates a fresh finite sum without a registered sequence family', () => {
  clearExactCasSynthesisCache()
  const result = synthesizeExactCasSingleProblem([{
    id: 'fresh-finite-sum',
    statement: String.raw`\[\sum_{j=1}^{7}j^2\]を求めよ。`,
  }])
  assert.equal(result.applicable, true)
  assert.equal(result.cards[0].answer_tex, String.raw`\(140\)`)
  assert.equal(result.cards[0].execution_certificate?.registered_composite_used, false)
})

test('keeps binder AST execution enabled in the batch benchmark path', () => {
  clearExactCasSynthesisCache()
  const results = synthesizeExactCasSingleProblemBatch([
    { id: 'batch-integral', statement: String.raw`\[\int_0^1 x^3\,dx\]を求めよ。` },
    { id: 'batch-sum', statement: String.raw`\[\sum_{k=1}^{9}k\]を求めよ。` },
  ])

  assert.deepEqual(results.map(result => result.cards[0]?.answer_tex), [
    String.raw`\(\frac{1}{4}\)`,
    String.raw`\(45\)`,
  ])
  assert.ok(results.every(result =>
    result.cards[0]?.execution_certificate?.capability_origin === 'synthesized_expression_program'))
  assert.ok(results.every(result =>
    result.cards[0]?.execution_certificate?.registered_composite_used === false))
})

test('recomputes a renamed limit instead of matching a stored problem', () => {
  clearExactCasSynthesisCache()
  const first = runAutonomousSynthesis([
    { id: 'limit-u', statement: '$\\lim_{u\\to0}\\frac{\\sin(5u)}{u}$ を求めよ。' },
  ], 1)
  const second = runAutonomousSynthesis([
    { id: 'limit-z', statement: '$\\lim_{z\\to0}\\frac{\\sin(7z)}{z}$ を求めよ。' },
  ], 1)
  assert.equal(first.cards[0].answer_tex, '\\(5\\)')
  assert.equal(second.cards[0].answer_tex, '\\(7\\)')
  assert.notEqual(first.cards[0].execution_certificate?.statement_sha256, second.cards[0].execution_certificate?.statement_sha256)
})

test('accepts a parameterized recurrence morphism only with a cross-runtime replay certificate', () => {
  clearExactCasSynthesisCache()
  const statement = (
    '実数 $\\alpha$ が $\\sin\\alpha+\\cos\\alpha=\\frac{1}{37}$ を満たしているとする。' +
    '$\\sin^n\\alpha+\\cos^n\\alpha>\\frac{1}{37}$ となる正の整数 $n$ をすべて求めよ。'
  )
  const result = synthesizeExactCasSingleProblem([{ id: 'renamed-threshold', statement }])

  assert.equal(result.applicable, true)
  assert.equal(result.cards.length, 1)
  assert.equal(
    result.cards[0].family_id,
    'solve.structural_theorem.structural_theorem_trigonometric_power_sum_threshold',
  )
  const certificate = result.cards[0].execution_certificate
  assert.ok(certificate)
  const contract = certificate.cold_generalization_contract as Record<string, unknown> | undefined
  assert.deepEqual(
    contract?.required_object_keys,
    ['sum_numerator', 'sum_denominator'],
  )
})

test('retains machine-readable failure diagnostics for an unresolved cold problem', () => {
  clearExactCasSynthesisCache()
  const statement = '$\\lim_{n\\to\\infty}f(n)$ を求めよ。'
  const result = synthesizeExactCasSingleProblem([{ id: 'unseen-correlation', statement }])

  assert.equal(result.applicable, false)
  assert.ok(result.diagnostics)
  assert.equal(result.diagnostics.schema, 'mortra.single-problem-failure.v1')
  assert.equal(typeof result.diagnostics.failure_code, 'string')
  assert.ok(Array.isArray(result.diagnostics.operations))
})
