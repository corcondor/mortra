import assert from 'node:assert/strict'
import test from 'node:test'

import { solveWithLinearRecurrenceMatrix } from '../lib/mortra/chart/linear-recurrence-matrix.js'
import {
  solveCongruenceByGeneratedAction,
  solveRecurrenceByGeneratedAction,
} from '../lib/mortra/cross-domain/generated-action-adapters.js'
import type { FiniteRecurrenceSpec } from '../lib/mortra/diagram/finite-state-transition.js'

const fibonacci: FiniteRecurrenceSpec = {
  id: 'generated-action-fibonacci',
  sourceSemanticIds: ['benchmark:recurrence'] as FiniteRecurrenceSpec['sourceSemanticIds'],
  modulus: 17,
  initial: [0, 1],
  update: { terms: [
    { coefficient: 1, powers: [1, 0] },
    { coefficient: 1, powers: [0, 1] },
  ] },
  targetIndex: '1000000000000000000',
}

test('the same finite generated-action kernel solves a modular recurrence orbit', () => {
  const generated = solveRecurrenceByGeneratedAction(fibonacci)
  const matrix = solveWithLinearRecurrenceMatrix(fibonacci)
  assert.equal(generated.status, 'certified')
  assert.equal(generated.answer, matrix.answer)
  assert.deepEqual(generated.errors, [])
  assert.ok((generated.orbit?.period ?? 0) > 0)
  assert.equal(generated.atlas?.generators[0].id, 'T')
})

test('affine recurrences retain the homogeneous coordinate under orbit reduction', () => {
  const spec: FiniteRecurrenceSpec = {
    ...fibonacci,
    id: 'generated-action-affine',
    modulus: 19,
    initial: [4, 7],
    update: { terms: [
      { coefficient: 2, powers: [1, 0] },
      { coefficient: 3, powers: [0, 1] },
      { coefficient: 4, powers: [0, 0] },
    ] },
    targetIndex: '1000000000000000007',
  }
  const generated = solveRecurrenceByGeneratedAction(spec)
  assert.equal(generated.status, 'certified')
  assert.equal(generated.answer, solveWithLinearRecurrenceMatrix(spec).answer)
  assert.ok(generated.atlas?.entries.every(entry => entry.state.at(-1) === 1))
})

test('linear congruence is the reachability problem for repeated addition', () => {
  const result = solveCongruenceByGeneratedAction({
    id: 'generated-action-congruence',
    sourceSemanticIds: ['benchmark:integer'],
    coefficient: '14',
    rhs: '30',
    modulus: '100',
  })
  assert.equal(result.status, 'certified')
  assert.equal(result.solvable, true)
  assert.equal(result.baseSolution, '45')
  assert.equal(result.solutionModulus, '50')
  assert.equal(result.atlas?.certificate.reachableStates, 50)
})

test('unreachable residue agrees with the valuation obstruction', () => {
  const result = solveCongruenceByGeneratedAction({
    id: 'generated-action-obstruction',
    sourceSemanticIds: ['benchmark:integer'],
    coefficient: '84',
    rhs: '30',
    modulus: '126',
  })
  assert.equal(result.status, 'certified')
  assert.equal(result.solvable, false)
  assert.equal(result.targetReachable, false)
  assert.equal(result.atlas?.certificate.reachableStates, 3)
})

test('bounded orbit enumeration abstains instead of hiding a state explosion', () => {
  const result = solveCongruenceByGeneratedAction({
    id: 'generated-action-cap',
    sourceSemanticIds: ['benchmark:integer'],
    coefficient: '1',
    rhs: '2',
    modulus: '10007',
  }, 1000)
  assert.equal(result.status, 'abstained')
  assert.match(result.errors.join(' '), /exceeded maxStates/)
})
