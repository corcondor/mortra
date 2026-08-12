import assert from 'node:assert/strict'
import test from 'node:test'

import {
  closeWithVisualReasoning,
  compileScene,
  factKey,
  forwardChain,
  type Fact,
  type Pt,
} from '../lib/proof-scene.js'

const para: Fact = { pred: 'para', args: ['a', 'b', 'c', 'd'] }
const goalPerp: Fact = { pred: 'perp', args: ['a', 'b', 'e', 'f'] }
const hiddenPerp: Fact = { pred: 'perp', args: ['c', 'd', 'e', 'f'] }

const exactPoints: Record<string, Pt> = {
  a: { x: 0, y: 0 },
  b: { x: 2, y: 0 },
  c: { x: 0, y: 1 },
  d: { x: 2, y: 1 },
  e: { x: 0, y: 0 },
  f: { x: 0, y: 2 },
}

test('a certified visual intermediate is returned to the reasoner', () => {
  const baseline = forwardChain([para], goalPerp, exactPoints)
  assert.equal(baseline.proved, false)

  const result = closeWithVisualReasoning({
    premises: [para],
    goal: goalPerp,
    points: exactPoints,
    options: { coordinateProvenance: 'given_exact', allowDirectGoal: false },
  })
  assert.equal(result.closure.proved, true)
  const candidate = result.audit.candidates.find(item => factKey(item.fact) === factKey(hiddenPerp))
  assert.equal(candidate?.certificate.status, 'certified')
  assert.ok(result.closure.derivations.has(factKey(hiddenPerp)))
  assert.equal(result.closure.derivations.get(factKey(hiddenPerp))?.origin, 'visual-certified')
})

test('a constructed witness can suggest but cannot certify a theorem', () => {
  const result = closeWithVisualReasoning({
    premises: [para],
    goal: goalPerp,
    points: exactPoints,
    options: { coordinateProvenance: 'constructed_witness', allowDirectGoal: false },
  })
  assert.equal(result.closure.proved, false)
  assert.equal(result.audit.certified, 0)
  assert.ok(result.audit.conjectureOnly > 0)
})

test('an almost perpendicular visual relation is rejected by exact arithmetic', () => {
  const nearPoints = {
    ...exactPoints,
    d: { x: 2, y: 1.02 },
  }
  const goal: Fact = { pred: 'para', args: ['a', 'b', 'c', 'd'] }
  const premise: Fact = { pred: 'perp', args: ['a', 'b', 'e', 'f'] }
  const result = closeWithVisualReasoning({
    premises: [premise],
    goal,
    points: nearPoints,
    options: { coordinateProvenance: 'given_exact', allowDirectGoal: false },
  })
  const candidate = result.audit.candidates.find(item => factKey(item.fact) === factKey(hiddenPerp))
  assert.equal(candidate?.certificate.status, 'rejected')
  assert.equal(result.closure.proved, false)
})

test('translation, rotation, and scaling preserve the certified proof', () => {
  const transformed = Object.fromEntries(Object.entries(exactPoints).map(([name, point]) => [
    name,
    { x: -2 * point.y + 7, y: 2 * point.x - 3 },
  ]))
  const original = closeWithVisualReasoning({
    premises: [para], goal: goalPerp, points: exactPoints,
    options: { coordinateProvenance: 'given_exact', allowDirectGoal: false },
  })
  const moved = closeWithVisualReasoning({
    premises: [para], goal: goalPerp, points: transformed,
    options: { coordinateProvenance: 'given_exact', allowDirectGoal: false },
  })
  assert.equal(original.closure.proved, true)
  assert.equal(moved.closure.proved, true)
  const certifiedKeys = (value: typeof original) => value.audit.candidates
    .filter(candidate => candidate.certificate.status === 'certified')
    .map(candidate => factKey(candidate.fact))
    .sort()
  assert.deepEqual(certifiedKeys(moved), certifiedKeys(original))
})

test('a counterfactual coordinate change removes the missing lemma and proof', () => {
  const changed = { ...exactPoints, d: { x: 2, y: 2 }, f: { x: 1, y: 2 } }
  const result = closeWithVisualReasoning({
    premises: [para], goal: goalPerp, points: changed,
    options: { coordinateProvenance: 'given_exact', allowDirectGoal: false },
  })
  assert.equal(result.closure.proved, false)
  assert.equal(
    result.audit.candidates.some(item =>
      factKey(item.fact) === factKey(hiddenPerp) && item.certificate.status === 'certified'),
    false,
  )
})

test('Proof Scene records candidate provenance and exact certificate', () => {
  const scene = compileScene({
    title: 'visual feedback',
    statement: 'exact coordinate geometry',
    premises: [para],
    goal: goalPerp,
    points: exactPoints,
    visualReasoning: { coordinateProvenance: 'given_exact', allowDirectGoal: false },
  })
  assert.equal(scene.proved, true)
  assert.equal(scene.visualReasoning?.baselineProved, false)
  assert.equal(scene.visualReasoning?.augmentedProved, true)
  const visualBeat = scene.beats.find(beat => beat.origin === 'visual-certified')
  assert.ok(visualBeat)
  assert.equal(visualBeat?.certificate?.status, 'certified')
  assert.match(visualBeat?.says ?? '', /厳密座標/)
})
