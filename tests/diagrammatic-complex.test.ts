import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildDynkinA,
  buildTorusCellulation,
  verifyCellComplex,
} from '../lib/mortra/construction/diagrammatic-complex'

test('a Dynkin diagram is represented as a labelled 1-complex', () => {
  const result = verifyCellComplex(buildDynkinA(8))
  assert.equal(result.passed, true)
  assert.deepEqual(result.counts, { 0: 8, 1: 7, 2: 0, 3: 0 })
  assert.equal(result.eulerCharacteristic, 1)
})

test('a periodic cellulation verifies torus topology without using circles', () => {
  const result = verifyCellComplex(buildTorusCellulation(12, 9))
  assert.equal(result.passed, true)
  assert.deepEqual(result.counts, { 0: 108, 1: 216, 2: 108, 3: 0 })
  assert.equal(result.eulerCharacteristic, 0)
  assert.equal(result.boundarySquaredResiduals, 0)
})

test('boundary-of-boundary rejects a locally plausible but broken face', () => {
  const complex = buildTorusCellulation(4, 3)
  const face = complex.cells.find(cell => cell.dimension === 2)
  assert.ok(face)
  face.boundary = face.boundary.slice(0, 3)
  const result = verifyCellComplex(complex)
  assert.equal(result.passed, false)
  assert.ok(result.boundarySquaredResiduals > 0)
})

test('sparse verification scales to thousands of cells', () => {
  const complex = buildTorusCellulation(40, 30)
  const result = verifyCellComplex(complex)
  assert.equal(complex.cells.length, 4_800)
  assert.equal(result.passed, true)
  assert.equal(result.eulerCharacteristic, 0)
})
