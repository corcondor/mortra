import assert from 'node:assert/strict'
import test from 'node:test'

import {
  acceptedBinaryWords,
  buildForbiddenWordAutomaton,
  canonicalForbiddenWords,
  normalizeForbiddenWords,
} from './finite-word-grammar'

test('constructs the no-consecutive-R automaton from the forbidden word', () => {
  const automaton = buildForbiddenWordAutomaton(['RR'])
  assert.deepEqual(automaton.states, ['', 'R'])
  assert.deepEqual(automaton.transitions, [
    { from: 0, to: 0, symbol: 'L' },
    { from: 0, to: 1, symbol: 'R' },
    { from: 1, to: 0, symbol: 'L' },
  ])
  assert.deepEqual(acceptedBinaryWords(['RR'], 3), ['LLL', 'LLR', 'LRL', 'RLL', 'RLR'])
})

test('identifies mirror grammars and removes redundant longer words', () => {
  assert.deepEqual(canonicalForbiddenWords(['RR']), canonicalForbiddenWords(['LL']))
  assert.deepEqual(normalizeForbiddenWords(['RR', 'LRR', 'RR']), ['RR'])
})

test('builds a prefix automaton for a length-three constraint', () => {
  const automaton = buildForbiddenWordAutomaton(['LRL'])
  assert.deepEqual(automaton.states, ['', 'L', 'LR'])
  assert.equal(automaton.transitions.length, 5)
  assert.ok(acceptedBinaryWords(['LRL'], 5).every(word => !word.includes('LRL')))
})

test('rejects malformed forbidden words', () => {
  assert.throws(() => buildForbiddenWordAutomaton([]), /at least one/)
  assert.throws(() => buildForbiddenWordAutomaton(['L2']), /only L\/R/)
})
