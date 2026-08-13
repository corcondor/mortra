import assert from 'node:assert/strict'
import test from 'node:test'

import {
  buildDynkinA,
  buildTorusCellulation,
  verifyCellComplex,
} from '../lib/mortra/construction/diagrammatic-complex'
import { evaluateDiagramSemantics } from '../lib/mortra/construction/diagram-semantic-evaluation'

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
  assert.deepEqual(result.bettiNumbers, { 0: 1, 1: 2, 2: 1, 3: 0 })
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

test('semantic scoring is invariant to cell identifiers', () => {
  const reference = buildTorusCellulation(5, 4)
  const idMap = new Map(reference.cells.map((cell, index) => [cell.id, `renamed_${index}`]))
  const renamed = {
    ...reference,
    cells: reference.cells.map(cell => ({
      ...cell,
      id: idMap.get(cell.id)!,
      boundary: cell.boundary.map(term => ({ ...term, cellId: idMap.get(term.cellId)! })),
    })),
  }
  const score = evaluateDiagramSemantics(reference, renamed)
  assert.equal(score.strictPass, true)
})

test('semantic scoring catches a topology error hidden by primitive counts', () => {
  const reference = buildTorusCellulation(5, 4)
  const broken = structuredClone(reference)
  const face = broken.cells.find(cell => cell.dimension === 2)!
  face.boundary[0] = face.boundary[1]
  const score = evaluateDiagramSemantics(reference, broken)
  assert.equal(score.strictPass, false)
  assert.equal(score.cellTypeF1, 1)
  assert.ok(score.incidenceF1 < 1 || !score.valid)
})

test('semantic scoring detects label omission independently of topology', () => {
  const reference = buildDynkinA(8)
  const unlabeled = structuredClone(reference)
  for (const cell of unlabeled.cells) delete cell.label
  const score = evaluateDiagramSemantics(reference, unlabeled)
  assert.equal(score.valid, true)
  assert.equal(score.cellTypeF1, 1)
  assert.equal(score.topologyF1, 1)
  assert.equal(score.labelF1, 0)
  assert.equal(score.strictPass, false)
})
