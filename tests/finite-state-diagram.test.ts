import assert from 'node:assert/strict'
import test from 'node:test'

import { semanticId } from '../lib/mortra/world/world-types.js'
import {
  buildFiniteStateDiagram,
  compileFiniteStateArtifact,
  solveWithFiniteStateDiagram,
  verifyFiniteStateDiagram,
  type FiniteRecurrenceSpec,
} from '../lib/mortra/diagram/finite-state-transition.js'

const fibonacci: FiniteRecurrenceSpec = {
  id: 'fib-mod-10',
  sourceSemanticIds: [semanticId('sequence:fibonacci'), semanticId('ring:zmod10')],
  modulus: 10,
  initial: [0, 1],
  update: { terms: [
    { coefficient: 1, powers: [1, 0] },
    { coefficient: 1, powers: [0, 1] },
  ] },
  targetIndex: '1000000000000',
}

test('a finite-state diagram certifies and compresses a huge recurrence index', () => {
  const result = solveWithFiniteStateDiagram(fibonacci)
  assert.equal(result.status, 'certified')
  assert.equal(result.answer, 5)
  assert.equal(result.diagram?.structure.preperiod, 0)
  assert.equal(result.diagram?.structure.period, 60)
  assert.ok((result.reducedIndex ?? 1_000_000) < 60)
})
test('the Tokyo parity recurrence is solved from the typed recurrence, not a problem id', () => {
  const spec: FiniteRecurrenceSpec = {
    id: 'arbitrary-renamed-source',
    sourceSemanticIds: [semanticId('sequence:a'), semanticId('ring:zmod2')],
    modulus: 2,
    initial: [1, 3],
    update: { terms: [
      { coefficient: -7, powers: [1, 0] },
      { coefficient: 3, powers: [0, 1] },
    ] },
    targetIndex: '1000001',
  }
  const result = solveWithFiniteStateDiagram(spec)
  assert.equal(result.status, 'certified')
  assert.equal(result.answer, 0)
  assert.equal(result.diagram?.structure.period, 3)
})

test('a nonlinear polynomial transition over a finite ring is executable', () => {
  const result = solveWithFiniteStateDiagram({
    id: 'nonlinear',
    sourceSemanticIds: [semanticId('sequence:b'), semanticId('ring:zmod17')],
    modulus: 17,
    initial: [2, 3],
    update: { terms: [
      { coefficient: 1, powers: [1, 1] },
      { coefficient: 1, powers: [0, 1] },
    ] },
    targetIndex: '1000000000000000033',
  })
  assert.equal(result.status, 'certified')
  assert.ok(result.diagram && result.diagram.carriers.length <= 17 ** 2)
})

test('adding multiples of the modulus does not change the residue diagram', () => {
  const original = solveWithFiniteStateDiagram(fibonacci)
  const transformed = solveWithFiniteStateDiagram({
    ...fibonacci,
    id: 'fib-mod-10-metamorphic',
    initial: [20, -19],
    update: { terms: [
      { coefficient: 11, powers: [1, 0] },
      { coefficient: -9, powers: [0, 1] },
    ] },
  })
  assert.equal(transformed.answer, original.answer)
  assert.deepEqual(
    transformed.diagram?.carriers.map(state => state.values),
    original.diagram?.carriers.map(state => state.values),
  )
})

test('the verifier rejects a visually plausible but false transition', () => {
  const built = buildFiniteStateDiagram(fibonacci)
  assert.ok(built.diagram)
  const diagram = structuredClone(built.diagram!)
  diagram.structure.transitions[0].emitted = (diagram.structure.transitions[0].emitted + 1) % 10
  const verification = verifyFiniteStateDiagram(fibonacci, diagram)
  assert.equal(verification.certified, false)
  assert.ok(verification.errors.some(error => error.includes('false emitted value')))
})

test('a diagram without semantic sources is rejected before construction', () => {
  const result = solveWithFiniteStateDiagram({ ...fibonacci, sourceSemanticIds: [] })
  assert.equal(result.status, 'invalid')
  assert.match(result.errors.join(' '), /sourceSemanticIds/)
})

test('the interactive artifact separates proof transport from layout heuristic', () => {
  const result = solveWithFiniteStateDiagram(fibonacci)
  const artifact = compileFiniteStateArtifact(result)
  assert.equal(artifact.semanticTransport.status, 'certified')
  assert.equal(artifact.designHeuristic.status, 'heuristic')
  assert.equal(artifact.states.length, 60)
  assert.ok(artifact.references.includes(semanticId('sequence:fibonacci')))
})
