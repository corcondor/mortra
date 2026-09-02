import assert from 'node:assert/strict'
import test from 'node:test'

import { hasCompleteParentProof } from './autonomous-synthesis'
import { capabilityOrigin } from './execution-certificate'
import { runPublicRuntimeGeneration } from './public-runtime-generation'
import { synthesizeRuntimeQuadraticExpectationProblems } from './runtime-quadratic-expectation-generation'

const parents = [
  {
    id: 'unseen-quadratic-form',
    statement: '二次形式 q(x,y)=2x^2+3xy+5y^2 を考える。',
  },
  {
    id: 'unseen-second-moments',
    statement: '確率変数 X,Y は独立で E[X]=1, E[Y]=-2, Var(X)=3, Var(Y)=4 とする。',
  },
]

test('connects a current quadratic form and current moments by an exact trace identity', () => {
  const result = synthesizeRuntimeQuadraticExpectationProblems(parents, 1)
  assert.equal(result.applicable, true)
  assert.equal(result.cards.length, 1)
  const card = result.cards[0]
  assert.equal(card.answer_tex, '42')
  assert.equal(card.family_id, 'runtime.quadratic_form_expectation')
  assert.equal(hasCompleteParentProof(card, parents), true)
  assert.equal(capabilityOrigin(card.execution_certificate), 'synthesized_proof_program')
  assert.equal(card.execution_certificate?.registered_composite_used, false)
  assert.equal(card.diagram && (card.diagram as { kind?: string }).kind, 'morphism')
})

test('separates a Japanese instruction suffix from the quadratic expression', () => {
  const result = synthesizeRuntimeQuadraticExpectationProblems([
    {
      id: 'ui-quadratic-form',
      statement: '二次形式 $q(x,y)=2x^2+3xy+5y^2$ を対称行列で表せ。',
    },
    {
      id: 'ui-second-moments',
      statement: '確率変数 $X,Y$ が $E[X]=1, E[Y]=-2, Var(X)=3, Var(Y)=4, Cov(X,Y)=0$ を満たすとき、二次モーメント行列を求めよ。',
    },
  ], 1)

  assert.equal(result.cards.length, 1)
  assert.equal(result.cards[0].answer_tex, '42')
})

test('synthesizes several fresh questions through invertible coordinate charts', () => {
  const result = synthesizeRuntimeQuadraticExpectationProblems(parents, 5)
  assert.equal(result.cards.length, 5)
  assert.equal(new Set(result.cards.map(card => card.statement_tex)).size, 5)
  assert.ok(result.cards.every(card => hasCompleteParentProof(card, parents)))
  assert.ok(result.cards.every(card => card.verification.exact_backend && card.verification.independent_check))
})

test('writes negative coefficients and unit shears as ordinary mathematics', () => {
  const result = synthesizeRuntimeQuadraticExpectationProblems(parents, 3)
  assert.equal(result.cards.length, 3)
  assert.ok(result.cards[1].solution_tex.includes('座標変換 \\((x+y,y)\\)'))
  assert.match(result.cards[2].solution_tex, /-7\\mathbb E\[XY\]/)
  assert.ok(result.cards[2].solution_tex.includes('座標変換 \\((x,y-x)\\)'))
  assert.equal(result.cards[2].solution_tex.includes('+-7'), false)
  assert.equal(result.cards[2].solution_tex.includes('-1x'), false)
})

test('accepts direct second moments and either parent order', () => {
  const reversed = [
    {
      id: 'direct-moments',
      statement: '確率変数 U,V は E[U^2]=5, E[UV]=-1, E[V^2]=2 を満たす。',
    },
    {
      id: 'another-form',
      statement: '二次形式 F(s,t)=3s^2-4st+2t^2 とする。',
    },
  ]
  const result = synthesizeRuntimeQuadraticExpectationProblems(reversed, 1)
  assert.equal(result.cards.length, 1)
  assert.equal(result.cards[0].answer_tex, '23')
  assert.equal(hasCompleteParentProof(result.cards[0], reversed), true)
})

test('preserves current variable names throughout the generated statement and solution', () => {
  const result = synthesizeRuntimeQuadraticExpectationProblems([
    { id: 'form-renamed', statement: '二次形式 h(u,v)=7u^2-4uv+3v^2 を考える。' },
    { id: 'moments-renamed', statement: '確率変数 U,V は E[U]=2, E[V]=-1, Var(U)=5, Var(V)=2, Cov(U,V)=1 を満たす。' },
  ], 1)
  assert.equal(result.cards.length, 1)
  const card = result.cards[0]
  assert.match(card.statement_tex, /q\(u,v\)/)
  assert.ok(card.statement_tex.includes('確率変数 \\(U,V\\)'))
  assert.match(card.statement_tex, /q\(U,V\)/)
  assert.equal(card.statement_tex.includes('確率変数 \\(X,Y\\)'), false)
  assert.match(card.solution_tex, /\\binom\{U\}\{V\}/)
  assert.match(card.solution_tex, /\\mathbb E\[UV\]/)
})

test('mutating coefficients or moments changes the generated certified value', () => {
  const changedForm = synthesizeRuntimeQuadraticExpectationProblems([
    { ...parents[0], statement: '二次形式 q(x,y)=4x^2+3xy+5y^2 を考える。' },
    parents[1],
  ], 1)
  const changedMoments = synthesizeRuntimeQuadraticExpectationProblems([
    parents[0],
    { ...parents[1], statement: '確率変数 X,Y は独立で E[X]=1, E[Y]=-2, Var(X)=5, Var(Y)=4 とする。' },
  ], 1)
  assert.equal(changedForm.cards.length, 1)
  assert.equal(changedMoments.cards.length, 1)
  assert.notEqual(changedForm.cards[0].answer_tex, '42')
  assert.notEqual(changedMoments.cards[0].answer_tex, '42')
})

test('public generation returns the current-input quadratic expectation without a queued search', () => {
  const result = runPublicRuntimeGeneration(parents, 3)
  assert.equal(result.cards.length, 3)
  assert.ok(result.cards.every(card => card.family_id === 'runtime.quadratic_form_expectation'))
  assert.ok(result.cards.every(card => card.execution_certificate?.registered_composite_used === false))
})

test('abstains when covariance information is insufficient', () => {
  const result = synthesizeRuntimeQuadraticExpectationProblems([
    parents[0],
    {
      id: 'missing-cross-moment',
      statement: '確率変数 X,Y は E[X]=1, E[Y]=2, Var(X)=3, Var(Y)=4 を満たす。',
    },
  ], 1)
  assert.equal(result.cards.length, 0)
  assert.equal(result.applicable, false)
})
