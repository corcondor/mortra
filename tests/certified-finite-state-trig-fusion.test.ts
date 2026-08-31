import assert from 'node:assert/strict'
import test from 'node:test'

import {
  parseIntegerSecondOrderRecurrence,
  parseRationalAngles,
  synthesizeCertifiedFiniteStateTrigFusion,
} from '../lib/mortra/certified-finite-state-trig-fusion.js'

const recurrenceParent = {
  id: 'recurrence-parent',
  statement: String.raw`F_1=F_2=1,\qquad F_{n+2}=F_{n+1}+F_n`,
}

const angleParent = {
  id: 'angle-parent',
  statement: String.raw`\sin\frac{\pi}{6}=\frac12 を用いて値を求めよ。`,
}

test('the recurrence parser extracts coefficients and consecutive initial values', () => {
  const parsed = parseIntegerSecondOrderRecurrence(recurrenceParent)
  assert.ok(parsed)
  assert.deepEqual(parsed.initial, [1n, 1n])
  assert.deepEqual(parsed.coefficients, [1n, 1n])
  assert.equal(parsed.startIndex, 1)
})

test('the rational-angle parser extracts a trigonometric argument', () => {
  const parsed = parseRationalAngles(angleParent)
  assert.equal(parsed.length, 1)
  assert.equal(parsed[0].numerator, 1n)
  assert.equal(parsed[0].denominator, 6n)
  assert.equal(parsed[0].role, 'trigonometric_argument')
})

test('an integration endpoint is not treated as a rational-angle parent', () => {
  const integral = {
    id: 'integral-parent',
    statement: String.raw`\int_0^{\frac{\pi}{2}}(\cos x+\sin x)\,dx を求めよ。`,
  }
  assert.deepEqual(parseRationalAngles(integral), [])
})

test('a recurrence and a rational angle synthesize an exact finite-state problem', () => {
  const card = synthesizeCertifiedFiniteStateTrigFusion([recurrenceParent, angleParent], 1)[0]
  assert.ok(card)
  assert.equal(card.family_id, 'certified.recurrence_rational_angle_orbit')
  assert.match(card.answer_tex, /\(N_0,T\)=\(1,24\)/)
  assert.match(card.answer_tex, /1周期/)
  assert.equal(card.verification.exact_backend, true)
  assert.equal(card.verification.independent_check, true)
  assert.equal(card.fusion_derivation.ablationPassed, true)
  assert.equal(card.proof_obligations?.length, 4)
  assert.ok(card.proof_obligations?.every(obligation => obligation.status === 'verified'))
  assert.equal(card.diagram.kind, 'morphism')
  assert.ok(card.search_evidence.hypotheses_evaluated > 0)
  assert.ok(card.search_evidence.hypotheses_evaluated <= card.verification.samples[0] ** 2)
})

test('one typed parent pair supports several distinct exact questions', () => {
  const cards = synthesizeCertifiedFiniteStateTrigFusion([recurrenceParent, angleParent], 64)
  assert.equal(cards.length, 7)
  assert.equal(new Set(cards.map(card => card.structure_blueprint.id)).size, cards.length)
  assert.deepEqual(
    new Set(cards.map(card => card.structure_blueprint.observable)),
    new Set([
      'eventual_minimal_trigonometric_period',
      'eventual_minimal_sine_period',
      'eventual_minimal_unit_circle_point_period',
      'sine_zero_index_set',
      'cosine_zero_index_set',
      'initial_unit_circle_point_return_set',
      'eventual_cosine_sign_profile',
    ]),
  )
  assert.ok(cards.every(card => card.verification.exact_backend && card.verification.independent_check))
})

test('zero sets, return times, and sign counts agree with the Fibonacci orbit modulo 12', () => {
  const cards = synthesizeCertifiedFiniteStateTrigFusion([recurrenceParent, angleParent], 64)
  const byObservable = new Map(cards.map(card => [card.structure_blueprint.observable, card]))

  assert.match(byObservable.get('sine_zero_index_set')?.answer_tex ?? '', /n\\bmod 12\\in\\\{0\\\}/)
  assert.match(byObservable.get('cosine_zero_index_set')?.answer_tex ?? '', /n\\bmod 12\\in\\\{4,8\\\}/)
  assert.match(
    byObservable.get('initial_unit_circle_point_return_set')?.answer_tex ?? '',
    /n\\bmod 24\\in\\\{1,2,7,17,23\\\}/,
  )
  assert.ok((byObservable.get('eventual_cosine_sign_profile')?.answer_tex ?? '').includes('(12,4,8)'))
})

test('input order and problem identifiers do not affect the normalized structure', () => {
  const base = synthesizeCertifiedFiniteStateTrigFusion([recurrenceParent, angleParent], 1)[0]
  const renamedRecurrence = { ...recurrenceParent, id: 'renamed-recurrence' }
  const renamedAngle = { ...angleParent, id: 'renamed-angle' }
  const changed = synthesizeCertifiedFiniteStateTrigFusion([renamedAngle, renamedRecurrence], 1)[0]
  assert.ok(base)
  assert.ok(changed)
  assert.equal(changed.structure_blueprint.id, base.structure_blueprint.id)
  assert.equal(changed.answer_tex, base.answer_tex)
})

test('coefficient and angle mutations are recomputed rather than replayed', () => {
  const changedRecurrence = {
    id: 'lucas-parent',
    statement: String.raw`L_1=1,\ L_2=3,\qquad L_{n+2}=2L_{n+1}+L_n`,
  }
  const changedAngle = {
    id: 'fifth-angle-parent',
    statement: String.raw`\cos\frac{\pi}{5} を考える。`,
  }
  const base = synthesizeCertifiedFiniteStateTrigFusion([recurrenceParent, angleParent], 1)[0]
  const coefficientMutation = synthesizeCertifiedFiniteStateTrigFusion([changedRecurrence, angleParent], 1)[0]
  const angleMutation = synthesizeCertifiedFiniteStateTrigFusion([recurrenceParent, changedAngle], 1)[0]
  assert.ok(base)
  assert.ok(coefficientMutation)
  assert.ok(angleMutation)
  assert.notEqual(coefficientMutation.structure_blueprint.id, base.structure_blueprint.id)
  assert.notEqual(coefficientMutation.answer_tex, base.answer_tex)
  assert.notEqual(angleMutation.structure_blueprint.id, base.structure_blueprint.id)
  assert.notEqual(angleMutation.answer_tex, base.answer_tex)
})

test('both typed parents are indispensable', () => {
  assert.deepEqual(synthesizeCertifiedFiniteStateTrigFusion([recurrenceParent], 1), [])
  assert.deepEqual(synthesizeCertifiedFiniteStateTrigFusion([angleParent], 1), [])
  assert.deepEqual(synthesizeCertifiedFiniteStateTrigFusion([
    recurrenceParent,
    { id: 'unrelated', statement: '三角形の面積を求めよ。' },
  ], 1), [])
})
