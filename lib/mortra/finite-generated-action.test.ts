import assert from 'node:assert/strict'
import test from 'node:test'

import {
  enumerateFiniteOrbit,
  minimalDivisorPeriod,
  minimalPeriodicStart,
} from './finite-generated-action'

test('enumerates a finite action without knowing its mathematical domain', () => {
  const orbit = enumerateFiniteOrbit<readonly [number, number]>({
    initial: [1, 1] as const,
    next: ([left, right]) => [right, (left + right) % 5] as const,
    key: state => state.join(','),
    maxStates: 25,
  })

  assert.ok(orbit)
  assert.equal(orbit.cycleStart, 0)
  assert.equal(orbit.period, 20)
  assert.deepEqual(orbit.states[0], [1, 1])
  assert.equal(orbit.transitionsEvaluated, orbit.states.length)
})

test('minimizes an observable period independently of the state representation', () => {
  assert.equal(minimalDivisorPeriod([0, 1, 0, 1]), 2)
  assert.equal(minimalDivisorPeriod(['a', 'b', 'c']), 3)
})

test('extends a periodic observation through a transient prefix when valid', () => {
  const values = ['x', 'a', 'b', 'a', 'b', 'a', 'b']
  assert.equal(minimalPeriodicStart({
    stateCycleStart: 3,
    observablePeriod: 2,
    valueAt: index => values[index],
  }), 1)
})
