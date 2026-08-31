import assert from 'node:assert/strict'
import test from 'node:test'

import {
  parseCertifiedExactScalar,
  synthesizeCertifiedAnswerRecurrenceFusion,
} from '../lib/mortra/certified-answer-recurrence-fusion'
import type { CertifiedFusionParent } from '../lib/mortra/certified-fusion'

function parent(id: string, answer: string): CertifiedFusionParent {
  return {
    id,
    statement: `${id} の厳密値を求めよ。`,
    answer,
    solution: `${id} の保存済み厳密証明。`,
    certificate: { verified: true, id: `proof-${id}`, method: 'exact replay' },
  }
}

const parents = [
  parent('left', String.raw`\(-\frac{\sqrt{3}}{8}\)`),
  parent('right', String.raw`\(\frac{8\sqrt{102}}{85}\)`),
]

test('accepts certified exact scalar expressions without using problem ids', () => {
  const parsed = parseCertifiedExactScalar(parents[0])
  assert.equal(parsed?.tex, String.raw`-\frac{\sqrt{3}}{8}`)
  assert.equal(parseCertifiedExactScalar({ ...parents[0], certificate: null }), null)
  assert.equal(parseCertifiedExactScalar(parent('tuple', String.raw`\((1,2)\)`)), null)
  assert.equal(parseCertifiedExactScalar(parent('decimal', String.raw`\(0.125\)`)), null)
})

test('composes two parent proof certificates into a solved recurrence problem', () => {
  const card = synthesizeCertifiedAnswerRecurrenceFusion(parents, 1)[0]
  assert.ok(card)
  assert.equal(card.family_id, 'certified.answer_pair_companion_recurrence')
  assert.deepEqual(card.parent_ids, ['left', 'right'])
  assert.match(card.answer_tex, /u_n=\\alpha\^n\+\\beta\^n/)
  assert.match(card.solution_tex, /特性多項式/)
  assert.equal(card.diagram.kind, 'state')
  assert.equal(card.verification.independent_check, true)
  assert.equal(card.fusion_derivation.ablationPassed, true)
})

test('renaming parent ids does not change the mathematical normal form', () => {
  const original = synthesizeCertifiedAnswerRecurrenceFusion(parents, 1)[0]
  const renamed = synthesizeCertifiedAnswerRecurrenceFusion([
    { ...parents[0], id: 'unknown-a', certificate: { ...parents[0].certificate!, id: 'new-proof-a' } },
    { ...parents[1], id: 'unknown-b', certificate: { ...parents[1].certificate!, id: 'new-proof-b' } },
  ], 1)[0]
  assert.equal(renamed.structure_blueprint.id, original.structure_blueprint.id)
  assert.equal(renamed.answer_tex, original.answer_tex)
})

test('swapping parents preserves the symmetric construction', () => {
  const original = synthesizeCertifiedAnswerRecurrenceFusion(parents, 1)[0]
  const swapped = synthesizeCertifiedAnswerRecurrenceFusion([...parents].reverse(), 1)[0]
  assert.equal(swapped.structure_blueprint.id, original.structure_blueprint.id)
  assert.equal(
    swapped.structure_blueprint.structuralUniqueness.normalForm,
    original.structure_blueprint.structuralUniqueness.normalForm,
  )
})

test('changing exact values recomputes the generated answer', () => {
  const original = synthesizeCertifiedAnswerRecurrenceFusion(parents, 1)[0]
  const changed = synthesizeCertifiedAnswerRecurrenceFusion([
    parent('a', String.raw`\(2\)`),
    parent('b', String.raw`\(3\)`),
  ], 1)[0]
  assert.notEqual(changed.answer_tex, original.answer_tex)
  assert.notEqual(changed.structure_blueprint.id, original.structure_blueprint.id)
})

test('removing either parent makes the composition abstain', () => {
  assert.deepEqual(synthesizeCertifiedAnswerRecurrenceFusion([parents[0]], 1), [])
  assert.deepEqual(synthesizeCertifiedAnswerRecurrenceFusion([parents[1]], 1), [])
})
