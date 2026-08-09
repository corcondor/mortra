import assert from 'node:assert/strict'
import test from 'node:test'
import {
  EQUALITY_TRANSITIVITY_RULE,
  executeTypedFactClosure,
  type TypedClosureProgram,
} from './typed-fact-closure'

function equalityProgram(sort: string, ids: string[]): TypedClosureProgram {
  return {
    terms: ids.map(id => ({ id, sort })),
    schemas: [{ name: 'Equal', argumentSorts: [sort, sort], symmetric: true }],
    facts: [
      { predicate: 'Equal', args: [ids[0], ids[1]], provenance: ['premise-1'] },
      { predicate: 'Equal', args: [ids[1], ids[2]], provenance: ['premise-2'] },
    ],
    rules: [EQUALITY_TRANSITIVITY_RULE],
    goal: { predicate: 'Equal', args: [ids[0], ids[2]] },
  }
}

test('one typed closure engine proves geometric and number-theoretic facts', () => {
  const programs = [
    equalityProgram('DirectedLength', ['AB', 'CD', 'EF']),
    equalityProgram('PrimeValuation', ['vp_n', 'vp_m', 'vp_k']),
  ]
  for (const program of programs) {
    const result = executeTypedFactClosure(program)
    assert.equal(result.status, 'proved')
    assert.equal(result.proof.at(-1)?.rule, 'equality-transitivity')
    assert.deepEqual(result.proof.at(-1)?.fact.provenance, ['equality-transitivity', 'premise-1', 'premise-2'])
  }
})

test('surface renaming does not change the proof shape', () => {
  const left = executeTypedFactClosure(equalityProgram('Scalar', ['a', 'b', 'c']))
  const right = executeTypedFactClosure(equalityProgram('Scalar', ['u', 'v', 'w']))
  assert.equal(left.status, 'proved')
  assert.equal(right.status, 'proved')
  assert.deepEqual(left.proof.map(step => step.rule), right.proof.map(step => step.rule))
  assert.deepEqual(left.proof.map(step => step.round), right.proof.map(step => step.round))
})

test('symmetric predicates do not depend on lexical argument order', () => {
  const result = executeTypedFactClosure(equalityProgram('Scalar', ['z', 'a', 'm']))
  assert.equal(result.status, 'proved')
})

test('type mismatch is rejected before search', () => {
  const program = equalityProgram('Integer', ['a', 'b', 'c'])
  program.terms[2] = { id: 'c', sort: 'Point' }
  const result = executeTypedFactClosure(program)
  assert.equal(result.status, 'invalid')
  assert.ok(result.diagnostics.some(message => message.includes('term c has sort Point')))
})

test('unproved goals remain explicit and do not become guessed answers', () => {
  const program = equalityProgram('Scalar', ['a', 'b', 'c'])
  program.facts = program.facts.slice(0, 1)
  const result = executeTypedFactClosure(program)
  assert.equal(result.status, 'unproved')
  assert.equal(result.proof.length, 0)
})
