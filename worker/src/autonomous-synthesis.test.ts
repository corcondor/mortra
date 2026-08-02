import assert from 'node:assert/strict'
import test from 'node:test'
import {
  isAutonomousResearchDue,
  runAutonomousSynthesis,
  type SynthesisStrategy,
} from './autonomous-synthesis'

const parents = [
  { id: 'map', solution: 'T(z)=\\frac{3z+2}{z+2}' },
  { id: 'orbit', statement: 'z_1,\\ldots,z_n を z^n=1 の全ての解とする。' },
]

test('runs a typed strategy registry and returns verified cards', () => {
  const result = runAutonomousSynthesis(parents, 3)
  assert.equal(result.cards.length, 3)
  assert.equal(result.state.continuing, false)
  assert.equal(result.attempts[0].strategy, 'rational-map-finite-algebraic-orbit')
  assert.equal(result.attempts[0].generated, 3)
})

test('continuation becomes due only after its persisted wake time', () => {
  const state = { continuing: true, next_attempt_at: '2026-08-03T00:15:00.000Z' }
  assert.equal(isAutonomousResearchDue(state, new Date('2026-08-03T00:14:59.000Z')), false)
  assert.equal(isAutonomousResearchDue(state, new Date('2026-08-03T00:15:00.000Z')), true)
  assert.equal(isAutonomousResearchDue({ ...state, continuing: false }, new Date('2026-08-04T00:00:00Z')), false)
})

test('persists and expands the search frontier without claiming success', () => {
  const unknown = [
    { id: 'a', statement: '関数 f の積分で定まる数列を考える。' },
    { id: 'b', statement: '三角形の接線と重心を考える。' },
  ]
  const first = runAutonomousSynthesis(unknown, 2, null, [], new Date('2026-08-03T00:00:00Z'))
  const second = runAutonomousSynthesis(unknown, 2, first.state, [], new Date('2026-08-03T00:15:00Z'))
  assert.equal(first.cards.length, 0)
  assert.equal(first.state.continuing, true)
  assert.equal(second.state.round, 2)
  assert.ok(second.state.depth > first.state.depth)
  assert.ok(second.state.hypotheses_evaluated > first.state.hypotheses_evaluated)
  assert.ok(second.state.frontier.length > 0)
})

test('strategies are selected by their typed support contract, not problem ids', () => {
  const seen: string[] = []
  const strategies: SynthesisStrategy[] = [
    {
      id: 'not-applicable', version: 1,
      supports: () => ({ applicable: false, reason: 'wrong input sorts' }),
      execute: () => { throw new Error('must not run') },
    },
    {
      id: 'applicable', version: 1,
      supports: context => ({ applicable: context.parents.length === 2, reason: 'two typed inputs' }),
      execute: context => { seen.push(...context.parents.map(parent => String(parent.id))); return [] },
    },
  ]
  const result = runAutonomousSynthesis(parents, 1, null, strategies)
  assert.deepEqual(seen, ['map', 'orbit'])
  assert.deepEqual(result.attempts.map(attempt => attempt.applicable), [false, true])
})
