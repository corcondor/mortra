import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildValuationCongruenceDivisibilityChart,
  verifyValuationCongruenceDivisibilityChart,
} from '../lib/mortra/chart/valuation-congruence-divisibility.js'
import {
  buildCircleQuadraticFormChart,
  evaluateCirclePower,
  verifyCircleQuadraticFormChart,
} from '../lib/mortra/chart/circle-quadratic-form.js'

test('one exact chart connects a linear congruence, divisibility, and prime valuations', () => {
  const built = buildValuationCongruenceDivisibilityChart({
    id: 'unseen-linear-congruence',
    sourceSemanticIds: ['benchmark:integer'],
    coefficient: '84',
    rhs: '30',
    modulus: '126',
  })
  assert.ok(built.chart)
  assert.equal(built.chart.solvable, false)
  assert.equal(built.chart.normalized.gcd, '42')
  assert.equal(built.chart.valuationWitnesses.find(item => item.prime === '7')?.satisfied, false)
})

test('the congruence chart returns and verifies the complete residue class', () => {
  const built = buildValuationCongruenceDivisibilityChart({
    id: 'solvable-linear-congruence',
    sourceSemanticIds: ['benchmark:integer'],
    coefficient: '14',
    rhs: '30',
    modulus: '100',
  })
  assert.ok(built.chart)
  assert.equal(built.chart.solvable, true)
  assert.equal(built.chart.baseSolution, '45')
  assert.equal(built.chart.solutionModulus, '50')
  assert.equal(verifyValuationCongruenceDivisibilityChart(built.chart).certified, true)
})

test('a false congruence witness is rejected', () => {
  const built = buildValuationCongruenceDivisibilityChart({
    id: 'mutation', sourceSemanticIds: ['benchmark:integer'],
    coefficient: '14', rhs: '30', modulus: '100',
  })
  assert.ok(built.chart)
  const mutation = structuredClone(built.chart)
  mutation.baseSolution = '44'
  assert.equal(verifyValuationCongruenceDivisibilityChart(mutation).certified, false)
})

test('circle equation, quadratic form, and center-radius form round trip exactly', () => {
  const built = buildCircleQuadraticFormChart({
    id: 'unseen-circle',
    sourceSemanticIds: ['benchmark:circle'],
    quadraticCoefficient: 2,
    linearX: -12,
    linearY: 8,
    constant: -6,
  })
  assert.ok(built.chart)
  assert.deepEqual(built.chart.center, { x: '3', y: '-2' })
  assert.equal(built.chart.radiusSquared, '16')
  assert.equal(evaluateCirclePower(built.chart, { x: 7, y: -2 }), '0')
  assert.equal(verifyCircleQuadraticFormChart(built.chart).certified, true)
})

test('the circle chart preserves exact rational centers', () => {
  const built = buildCircleQuadraticFormChart({
    id: 'rational-circle', sourceSemanticIds: ['benchmark:circle'],
    quadraticCoefficient: 2, linearX: 3, linearY: -5, constant: -7,
  })
  assert.ok(built.chart)
  assert.deepEqual(built.chart.center, { x: '-3/4', y: '5/4' })
  assert.equal(built.chart.radiusSquared, '45/8')
})

test('a matrix mutation cannot retain a circle certificate', () => {
  const built = buildCircleQuadraticFormChart({
    id: 'circle-mutation', sourceSemanticIds: ['benchmark:circle'],
    quadraticCoefficient: 1, linearX: -6, linearY: 4, constant: -3,
  })
  assert.ok(built.chart)
  const mutation = structuredClone(built.chart)
  mutation.homogeneousQuadraticMatrix[0][2] = '-2'
  assert.equal(verifyCircleQuadraticFormChart(mutation).certified, false)
})

test('non-circles are rejected instead of being forced into the chart', () => {
  const degenerate = buildCircleQuadraticFormChart({
    id: 'empty-real-locus', sourceSemanticIds: ['benchmark:conic'],
    quadraticCoefficient: 1, linearX: 0, linearY: 0, constant: 1,
  })
  assert.equal(degenerate.chart, undefined)
  assert.match(degenerate.errors.join(' '), /not a nondegenerate circle/)
})
