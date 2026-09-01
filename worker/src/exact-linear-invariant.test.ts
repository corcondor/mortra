import assert from 'node:assert/strict'
import test from 'node:test'
import {
  executeLinearInvariant,
  verifyLinearInvariantCertificate,
  type LinearInvariantProgram,
} from './exact-linear-invariant'

test('one exact elimination kernel proves additive, logarithmic, and angle invariants', () => {
  const programs: LinearInvariantProgram[] = [
    {
      coordinate: 'additive',
      equations: [
        { terms: { initial: 1, gain: 1, final: -1 }, rhs: 0, provenance: ['state-law'] },
        { terms: { gain: 1 }, rhs: 3, provenance: ['gain-observation'] },
        { terms: { final: 1 }, rhs: 11, provenance: ['final-observation'] },
      ],
      goal: { terms: { initial: 1 }, expected: 8 },
    },
    {
      coordinate: 'log_multiplicative',
      equations: [
        { terms: { logAB: 1, logCD: -1 }, rhs: 0, provenance: ['eqratio-1'] },
        { terms: { logCD: 1, logEF: -1 }, rhs: 0, provenance: ['eqratio-2'] },
      ],
      goal: { terms: { logAB: 1, logEF: -1 }, expected: 0 },
    },
    {
      coordinate: 'angle',
      equations: [
        { terms: { dirAB: 1, dirCD: -1 }, rhs: '1/2', provenance: ['perpendicular'] },
        { terms: { dirCD: 1, dirEF: -1 }, rhs: 0, provenance: ['parallel'] },
      ],
      goal: { terms: { dirAB: 1, dirEF: -1 }, expected: '1/2' },
    },
  ]
  for (const program of programs) {
    const result = executeLinearInvariant(program)
    assert.equal(result.status, 'proved')
    assert.equal(result.expectedMatches, true)
    assert.ok(result.usedProvenance.length >= 2)
    assert.equal(verifyLinearInvariantCertificate(program, result), true)
  }
})

test('proof-combination replay rejects a modified answer', () => {
  const program: LinearInvariantProgram = {
    coordinate: 'additive',
    equations: [
      { terms: { x: 1, y: 1 }, rhs: 19, provenance: ['sum'] },
      { terms: { y: 1 }, rhs: 4, provenance: ['observation'] },
    ],
    goal: { terms: { x: 1 } },
  }
  const certificate = executeLinearInvariant(program)
  assert.equal(certificate.value, '15')
  assert.equal(verifyLinearInvariantCertificate(program, certificate), true)
  assert.equal(verifyLinearInvariantCertificate(program, { ...certificate, value: '16' }), false)
})

test('alpha-renaming preserves the exact elimination certificate', () => {
  const left = executeLinearInvariant({
    coordinate: 'additive',
    equations: [
      { terms: { x: 1, y: 1 }, rhs: 10, provenance: ['sum'] },
      { terms: { y: 1 }, rhs: 3, provenance: ['observation'] },
    ],
    goal: { terms: { x: 1 } },
  })
  const right = executeLinearInvariant({
    coordinate: 'additive',
    equations: [
      { terms: { u: 1, v: 1 }, rhs: 10, provenance: ['sum'] },
      { terms: { v: 1 }, rhs: 3, provenance: ['observation'] },
    ],
    goal: { terms: { u: 1 } },
  })
  assert.equal(left.value, '7')
  assert.equal(right.value, left.value)
  assert.deepEqual(right.usedProvenance, left.usedProvenance)
})

test('does not execute when information is missing or a side condition is open', () => {
  const underdetermined = executeLinearInvariant({
    coordinate: 'additive',
    equations: [{ terms: { x: 1, y: 1 }, rhs: 1, provenance: ['sum'] }],
    goal: { terms: { x: 1 } },
  })
  assert.equal(underdetermined.status, 'underdetermined')

  const blocked = executeLinearInvariant({
    coordinate: 'log_multiplicative',
    equations: [{ terms: { logAB: 1, logCD: -1 }, rhs: 0, provenance: ['ratio'] }],
    sideConditions: [{ id: 'nonzero-lengths', predicate: 'AB != 0 and CD != 0', proved: false }],
    goal: { terms: { logAB: 1, logCD: -1 } },
  })
  assert.equal(blocked.status, 'blocked')
  assert.deepEqual(blocked.blockedSideConditions, ['nonzero-lengths'])
})

