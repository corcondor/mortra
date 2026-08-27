import assert from 'node:assert/strict'
import test from 'node:test'

import { semanticId } from '../lib/mortra/world/world-types.js'
import {
  buildLinearRecurrenceMatrixChart,
  reconstructFiniteRecurrence,
  solveWithLinearRecurrenceMatrix,
  verifyLinearRecurrenceMatrixChart,
} from '../lib/mortra/chart/linear-recurrence-matrix.js'
import {
  solveWithFiniteStateDiagram,
  type FiniteRecurrenceSpec,
} from '../lib/mortra/diagram/finite-state-transition.js'

const fibonacci: FiniteRecurrenceSpec = {
  id: 'unseen-fibonacci-renamed',
  sourceSemanticIds: [semanticId('benchmark:recurrence'), semanticId('ring:zmod17')],
  modulus: 17,
  initial: [0, 1],
  update: { terms: [
    { coefficient: 1, powers: [1, 0] },
    { coefficient: 1, powers: [0, 1] },
  ] },
  targetIndex: '1000000000000000000',
}

test('recurrence, companion matrix, and characteristic polynomial round trip exactly', () => {
  const built = buildLinearRecurrenceMatrixChart(fibonacci)
  assert.deepEqual(built.errors, [])
  assert.ok(built.chart)
  assert.deepEqual(built.chart.recurrenceCharacteristicPolynomial, [16, 16, 1])
  assert.deepEqual(built.chart.transitionMatrix, [
    [0, 1, 0],
    [1, 1, 0],
    [0, 0, 1],
  ])
  assert.equal(verifyLinearRecurrenceMatrixChart(built.chart).certified, true)
  const reconstructed = reconstructFiniteRecurrence(built.chart)
  const originalAnswer = solveWithFiniteStateDiagram(fibonacci).answer
  assert.equal(solveWithFiniteStateDiagram(reconstructed).answer, originalAnswer)
})

test('matrix exponentiation and finite-state cycle quotient agree on a huge index', () => {
  const matrix = solveWithLinearRecurrenceMatrix(fibonacci)
  const finiteState = solveWithFiniteStateDiagram(fibonacci)
  assert.equal(matrix.status, 'certified')
  assert.equal(matrix.answer, finiteState.answer)
  assert.ok(matrix.matrixMultiplications < 200)
})

test('inhomogeneous recurrences use an exact affine homogeneous coordinate', () => {
  const spec: FiniteRecurrenceSpec = {
    ...fibonacci,
    id: 'affine-order-two',
    modulus: 19,
    initial: [4, 7],
    update: { terms: [
      { coefficient: 2, powers: [1, 0] },
      { coefficient: 3, powers: [0, 1] },
      { coefficient: 4, powers: [0, 0] },
    ] },
    targetIndex: '1000000000000000007',
  }
  const matrix = solveWithLinearRecurrenceMatrix(spec)
  const finiteState = solveWithFiniteStateDiagram(spec)
  assert.equal(matrix.status, 'certified')
  assert.equal(matrix.answer, finiteState.answer)
  assert.equal(matrix.chart?.transitionMatrix[1][2], 4)
})

test('the chart abstains on nonlinear transitions instead of falsely linearizing them', () => {
  const result = solveWithLinearRecurrenceMatrix({
    ...fibonacci,
    update: { terms: [{ coefficient: 1, powers: [1, 1] }] },
  })
  assert.equal(result.status, 'abstained')
  assert.match(result.errors.join(' '), /nonlinear/)
})

test('mutation of the matrix or characteristic polynomial invalidates the certificate', () => {
  const built = buildLinearRecurrenceMatrixChart(fibonacci)
  assert.ok(built.chart)
  const matrixMutation = structuredClone(built.chart)
  matrixMutation.transitionMatrix[1][0] = 2
  assert.equal(verifyLinearRecurrenceMatrixChart(matrixMutation).certified, false)
  const polynomialMutation = structuredClone(built.chart)
  polynomialMutation.recurrenceCharacteristicPolynomial[0] = 15
  assert.equal(verifyLinearRecurrenceMatrixChart(polynomialMutation).certified, false)
})

test('coefficient representatives modulo m do not change the normalized chart', () => {
  const base = buildLinearRecurrenceMatrixChart(fibonacci).chart
  const transformed = buildLinearRecurrenceMatrixChart({
    ...fibonacci,
    id: 'different-surface-coefficients',
    initial: [34, -33],
    update: { terms: [
      { coefficient: 18, powers: [1, 0] },
      { coefficient: -16, powers: [0, 1] },
    ] },
  }).chart
  assert.deepEqual(transformed?.normalForm, base?.normalForm)
  assert.deepEqual(transformed?.transitionMatrix, base?.transitionMatrix)
})
