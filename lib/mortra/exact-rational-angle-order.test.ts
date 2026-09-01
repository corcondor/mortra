import assert from 'node:assert/strict'
import test from 'node:test'

import type { CertifiedFusionParent } from './certified-fusion'
import type { ParsedRationalAngle } from './certified-finite-state-trig-fusion'
import { synthesizeCertifiedThreeParentPowerThresholdFusion } from './certified-multi-parent-power-fusion'
import {
  certifyRationalAngleQuadraticComparisons,
  exactQ,
  verifyRationalAngleQuadraticCertificate,
} from './exact-rational-angle-order'

function angle(numerator: bigint, denominator: bigint): ParsedRationalAngle {
  return {
    parentId: `angle-${numerator}-${denominator}`,
    numerator,
    denominator,
    evidence: `${numerator} pi/${denominator}`,
    role: 'angle_condition',
  }
}

test('certifies exact rational quadratic angle values', () => {
  const result = certifyRationalAngleQuadraticComparisons(
    angle(1n, 6n),
    'sine_squared',
    exactQ(1n, 2027n),
    [exactQ(1n, 8n), exactQ(1n, 2n)],
  )
  assert.ok(result)
  assert.deepEqual(result.certificate.exactValue, exactQ(1n, 4n))
  assert.deepEqual(result.comparisons.map(item => item.relation), [
    'less_or_equal',
    'greater',
  ])
  assert.equal(verifyRationalAngleQuadraticCertificate(result.certificate), true)
})

test('certifies algebraic rational-angle comparisons without floating point', () => {
  const result = certifyRationalAngleQuadraticComparisons(
    angle(2n, 7n),
    'sine_squared',
    exactQ(1n, 2027n),
    [exactQ(1n, 2n), exactQ(1n)],
  )
  assert.ok(result)
  assert.equal(result.certificate.exactValue, null)
  assert.deepEqual(result.comparisons.map(item => item.relation), [
    'less_or_equal',
    'greater',
  ])
  assert.equal(verifyRationalAngleQuadraticCertificate(result.certificate), true)

  const altered = structuredClone(result.certificate)
  altered.threshold.lower = exactQ(0n)
  assert.equal(verifyRationalAngleQuadraticCertificate(altered), false)
})

test('one reusable three-parent chart handles rational and algebraic angle thresholds', () => {
  const recurrence: CertifiedFusionParent = {
    id: 'recurrence',
    statement: String.raw`F_1=F_2=1,\quad F_{n+2}=F_{n+1}+F_n`,
  }
  const power: CertifiedFusionParent = {
    id: 'power',
    statement: String.raw`\sin\theta+\cos\theta=\frac{1}{2027}. \sin^n\theta+\cos^n\theta>\frac{1}{2027} となる n を求めよ。`,
  }
  const angleParents: CertifiedFusionParent[] = [
    { id: 'angle-7', statement: String.raw`\cos\frac{2\pi}{7} を考える。` },
    { id: 'angle-11', statement: String.raw`\alpha=\frac{2\pi}{11} とする。` },
    { id: 'angle-2', statement: String.raw`角 \alpha=\frac{\pi}{2} とする。` },
  ]

  for (const angleParent of angleParents) {
    const cards = synthesizeCertifiedThreeParentPowerThresholdFusion([
      recurrence,
      power,
      angleParent,
    ])
    assert.equal(cards.length, 1, angleParent.id)
    assert.deepEqual(new Set(cards[0].parent_ids), new Set([
      recurrence.id,
      power.id,
      angleParent.id,
    ]))
    assert.match(cards[0].solution_tex, /Machin|厳密に/)
    assert.equal(cards[0].verification.exact_backend, true)
    assert.equal(cards[0].verification.independent_check, true)
  }
})
