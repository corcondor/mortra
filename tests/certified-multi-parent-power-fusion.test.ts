import assert from 'node:assert/strict'
import test from 'node:test'

import { parseRationalAngles } from '../lib/mortra/certified-finite-state-trig-fusion.js'
import { planCertifiedFusions } from '../lib/mortra/certified-fusion-planner.js'
import { synthesizeCertifiedFusions } from '../lib/mortra/certified-fusion-registry.js'
import {
  exactRationalCosineOfDoubleAngle,
  synthesizeCertifiedThreeParentPowerThresholdFusion,
} from '../lib/mortra/certified-multi-parent-power-fusion.js'

const recurrenceParent = {
  id: 'recurrence-parent',
  statement: String.raw`F_1=F_2=1,\qquad F_{n+2}=F_{n+1}+F_n`,
}

const powerParent = {
  id: 'power-parent',
  statement: String.raw`\sin\theta+\cos\theta=\frac{1}{2027}.
    \sin^m\theta+\cos^m\theta>\frac{1}{2027} となる m を求めよ。`,
}

const angleParent = {
  id: 'angle-parent',
  statement: String.raw`二直線のなす角は \frac{\pi}{6} である。`,
}

test('the rational-angle threshold is derived exactly and abstains outside the rational cases', () => {
  const sixth = parseRationalAngles(angleParent)[0]
  const seventh = parseRationalAngles({
    id: 'seventh',
    statement: String.raw`二直線のなす角は \frac{\pi}{7} である。`,
  })[0]
  assert.deepEqual(exactRationalCosineOfDoubleAngle(sixth), { n: 1n, d: 2n })
  assert.equal(exactRationalCosineOfDoubleAngle(seventh), null)
})

test('three typed parents produce one concise exact problem and proof', () => {
  const cards = synthesizeCertifiedThreeParentPowerThresholdFusion([
    angleParent,
    powerParent,
    recurrenceParent,
  ], 64)
  assert.equal(cards.length, 1)
  const card = cards[0]
  assert.equal(card.answer_tex, String.raw`\(k\in\{3\}\)`)
  assert.equal(card.family_id, 'certified.three_parent_recurrence_power_angle')
  assert.equal(card.structure_blueprint.kernel, 'ReversibleGeneratedIndexPowerSumIR')
  assert.equal(card.statement_tex.length < 500, true)
  assert.deepEqual(
    new Set(card.parent_ids),
    new Set([recurrenceParent.id, powerParent.id, angleParent.id]),
  )
  assert.deepEqual(card.fusion_derivation.bridges[0].consumes, [
    'exponent_orbit',
    'power_sum_transition',
    'rational_angle_threshold',
  ])
  assert.equal(card.fusion_derivation.ablationPassed, true)
  assert.equal(card.verification.exact_backend, true)
  assert.equal(card.verification.independent_check, true)
  assert.match(card.solution_tex, /倍角/)
  assert.match(card.solution_tex, /伴行列/)
  assert.doesNotMatch(
    card.statement_tex + card.solution_tex,
    /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/,
  )
})

test('parent order and surface ids do not change the mathematical result', () => {
  const original = synthesizeCertifiedThreeParentPowerThresholdFusion([
    recurrenceParent,
    powerParent,
    angleParent,
  ])[0]
  const renamed = synthesizeCertifiedThreeParentPowerThresholdFusion([
    { ...powerParent, id: 'renamed-power' },
    { ...angleParent, id: 'renamed-angle' },
    { ...recurrenceParent, id: 'renamed-recurrence' },
  ])[0]
  assert.ok(original)
  assert.ok(renamed)
  assert.equal(renamed.answer_tex, original.answer_tex)
  assert.equal(renamed.structure_blueprint.id, original.structure_blueprint.id)
})

test('all three parents are indispensable', () => {
  assert.deepEqual(
    synthesizeCertifiedThreeParentPowerThresholdFusion([recurrenceParent, powerParent]),
    [],
  )
  assert.deepEqual(
    synthesizeCertifiedThreeParentPowerThresholdFusion([recurrenceParent, angleParent]),
    [],
  )
  assert.deepEqual(
    synthesizeCertifiedThreeParentPowerThresholdFusion([powerParent, angleParent]),
    [],
  )
})

test('the variable-arity planner prefers the all-parent chart when all three ports exist', () => {
  const plan = planCertifiedFusions([powerParent, recurrenceParent, angleParent], 1)
  assert.equal(plan.cards.length, 1)
  assert.equal(plan.cards[0].family_id, 'certified.three_parent_recurrence_power_angle')
  assert.equal(plan.attempts[0]?.chartId, 'three-parent-recurrence-power-angle')
  assert.equal(plan.attempts[0]?.parentIds.length, 3)
  assert.equal(plan.attempts[0]?.inputKinds.length, 3)
})

test('the public registry preserves the three-parent proof composition', () => {
  const cards = synthesizeCertifiedFusions([powerParent, angleParent, recurrenceParent], 64)
  assert.equal(cards.length, 1)
  assert.equal(cards[0].family_id, 'certified.three_parent_recurrence_power_angle')
  assert.equal(cards[0].parent_ids.length, 3)
  assert.equal(cards[0].fusion_derivation.ablationPassed, true)
})
