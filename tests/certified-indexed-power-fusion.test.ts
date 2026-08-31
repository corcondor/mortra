import assert from 'node:assert/strict'
import test from 'node:test'

import {
  parsePositiveSecondOrderRecurrence,
  parseTrigonometricPowerSum,
  synthesizeCertifiedIndexedPowerSumFusion,
} from '../lib/mortra/certified-indexed-power-fusion.js'
import { synthesizeCertifiedFusions } from '../lib/mortra/certified-fusion-registry.js'

const recurrenceParent = {
  id: 'full-problems-recurrence-holdout',
  statement: String.raw`n\in\mathbb N,\ F_1=F_2=1,\ F_{n+2}=F_{n+1}+F_n で定まる数列を考える。`,
}

const powerParent = {
  id: 'full-problems-power-holdout',
  statement: String.raw`実数 \theta が
  \[\sin\theta+\cos\theta=\frac{1}{2027}\]
  を満たすとする。\[\sin^n\theta+\cos^n\theta>\frac{1}{2027}\]
  となる正の整数 n をすべて求めよ。`,
}

test('unseen corpus endpoints produce a new exact indexed power-sum problem', () => {
  const cards = synthesizeCertifiedIndexedPowerSumFusion([recurrenceParent, powerParent])
  assert.equal(cards.length, 1)
  const card = cards[0]
  assert.equal(card.answer_tex, String.raw`\(k\in\{3,4,5,6\}\)`)
  assert.equal(card.verification.exact_backend, true)
  assert.equal(card.verification.independent_check, true)
  assert.equal(card.fusion_derivation.ablationPassed, true)
  assert.deepEqual(new Set(card.parent_ids), new Set([recurrenceParent.id, powerParent.id]))
  assert.match(card.solution_tex, /Newton和/)
  assert.match(card.solution_tex, /伴行列/)
  assert.equal(card.diagram.kind, 'state')
})

test('generated TeX preserves commands and contains no control characters', () => {
  const card = synthesizeCertifiedIndexedPowerSumFusion([recurrenceParent, powerParent])[0]
  assert.ok(card)
  const rendered = `${card.statement_tex}\n${card.solution_tex}`
  assert.doesNotMatch(rendered, /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/)
  assert.match(card.statement_tex, /\\theta/)
  assert.match(card.statement_tex, /\\sin/)
  assert.match(card.solution_tex, /\\beta/)
})

test('surface renaming preserves the normalized result without problem ids', () => {
  const renamedRecurrence = {
    id: 'arbitrary-a',
    statement: String.raw`G_1=G_2=1,\qquad G_{r+2}=G_{r+1}+G_r.`,
  }
  const renamedPower = {
    id: 'arbitrary-b',
    statement: String.raw`\sin\varphi+\cos\varphi=\dfrac{1}{2027}.
      \sin^m\varphi+\cos^m\varphi>\dfrac{1}{2027} となる m を求めよ。`,
  }
  const original = synthesizeCertifiedIndexedPowerSumFusion([recurrenceParent, powerParent])[0]
  const renamed = synthesizeCertifiedIndexedPowerSumFusion([renamedPower, renamedRecurrence])[0]
  assert.ok(original)
  assert.ok(renamed)
  assert.equal(renamed.answer_tex, original.answer_tex)
  assert.equal(renamed.structure_blueprint.id, original.structure_blueprint.id)
})

test('mutating recurrence data recomputes the answer rather than replaying a template', () => {
  const mutation = {
    id: 'mutated-recurrence',
    statement: String.raw`A_1=1,\ A_2=2,\ A_{j+2}=A_{j+1}+A_j.`,
  }
  const base = synthesizeCertifiedIndexedPowerSumFusion([recurrenceParent, powerParent])[0]
  const changed = synthesizeCertifiedIndexedPowerSumFusion([mutation, powerParent])[0]
  assert.ok(base)
  assert.ok(changed)
  assert.notEqual(changed.answer_tex, base.answer_tex)
  assert.equal(changed.answer_tex, String.raw`\(k\in\{2,3,4,5\}\)`)
  assert.notEqual(changed.structure_blueprint.id, base.structure_blueprint.id)
})

test('both typed parents are indispensable', () => {
  assert.deepEqual(synthesizeCertifiedIndexedPowerSumFusion([recurrenceParent]), [])
  assert.deepEqual(synthesizeCertifiedIndexedPowerSumFusion([powerParent]), [])
  assert.deepEqual(synthesizeCertifiedIndexedPowerSumFusion([recurrenceParent, {
    id: 'unrelated', statement: '三角形の面積を求めよ。',
  }]), [])
})

test('parsers read mathematical structure rather than labels', () => {
  const recurrence = parsePositiveSecondOrderRecurrence(recurrenceParent)
  const power = parseTrigonometricPowerSum(powerParent)
  assert.deepEqual(recurrence?.initial, [1n, 1n])
  assert.deepEqual(recurrence?.coefficients, [1n, 1n])
  assert.equal(power?.sum.n, 1n)
  assert.equal(power?.sum.d, 2027n)
})

test('the public certified registry dispatches the new cross-domain engine', () => {
  const cards = synthesizeCertifiedFusions([recurrenceParent, powerParent], 1)
  assert.equal(cards[0]?.family_id, 'certified.recurrence_indexed_power_sum')
})
