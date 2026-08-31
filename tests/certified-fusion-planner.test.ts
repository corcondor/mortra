import assert from 'node:assert/strict'
import test from 'node:test'

import {
  elaborateCertifiedFusionParent,
  planCertifiedFusions,
} from '../lib/mortra/certified-fusion-planner.js'
import { synthesizeCertifiedFusions } from '../lib/mortra/certified-fusion-registry.js'

const recurrenceParent = {
  id: 'source-sequence',
  statement: String.raw`U_1=2,\ U_2=5,\qquad U_{j+2}=3U_{j+1}-U_j`,
}

const angleParent = {
  id: 'source-angle',
  statement: String.raw`二直線のなす角は \frac{\pi}{7} である。`,
}

test('elaboration exposes mathematical interfaces instead of problem labels', () => {
  const recurrenceKinds = elaborateCertifiedFusionParent(recurrenceParent).map(item => item.kind)
  const angleKinds = elaborateCertifiedFusionParent(angleParent).map(item => item.kind)
  assert.ok(recurrenceKinds.includes('sequence.integer_second_order'))
  assert.ok(angleKinds.includes('angle.rational_phase'))
})

test('the planner selects a chart by typed ports from more than two parents', () => {
  const unrelated = { id: 'unrelated', statement: '三角形の面積を求めよ。' }
  const plan = planCertifiedFusions([unrelated, angleParent, recurrenceParent], 1)
  assert.equal(plan.cards.length, 1)
  assert.equal(plan.cards[0].family_id, 'certified.recurrence_rational_angle_orbit')
  assert.deepEqual(new Set(plan.cards[0].parent_ids), new Set([recurrenceParent.id, angleParent.id]))
  assert.equal(plan.attempts.at(-1)?.chartId, 'finite-state-rational-angle-orbit')
  assert.equal(plan.attempts.at(-1)?.produced, 1)
})

test('the public registry now uses typed chart planning', () => {
  const card = synthesizeCertifiedFusions([angleParent, recurrenceParent], 1)[0]
  assert.ok(card)
  assert.equal(card.family_id, 'certified.recurrence_rational_angle_orbit')
})

test('an unmatched endpoint set abstains and records no fabricated attempt', () => {
  const parents = [
    { id: 'geometry-a', statement: '三角形ABCの面積を求めよ。' },
    { id: 'geometry-b', statement: '四面体の体積を求めよ。' },
  ]
  const plan = planCertifiedFusions(parents, 1)
  assert.deepEqual(plan.cards, [])
  assert.deepEqual(plan.attempts, [])
})

test('the public registry never drops a selected parent to manufacture a result', () => {
  const unrelated = { id: 'required-unrelated', statement: '三角形ABCの面積を求めよ。' }
  assert.deepEqual(
    synthesizeCertifiedFusions([unrelated, angleParent, recurrenceParent], 64),
    [],
  )
})
