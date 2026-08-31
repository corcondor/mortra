import assert from 'node:assert/strict'
import test from 'node:test'

import {
  parsePellOrbit,
  synthesizeCertifiedPellIndexedPowerSumFusion,
  synthesizeCertifiedPellRecurrenceFusion,
} from '../lib/mortra/certified-pell-recurrence-fusion.js'
import { synthesizeCertifiedFusions } from '../lib/mortra/certified-fusion-registry.js'

const pellParent = {
  id: 'full-problems-pell-holdout',
  statement: [
    '正の整数 m のうち',
    '\\[m^2-3\\left\\lfloor m/\\sqrt3\\right\\rfloor^2=1\\]',
    'を満たすものを並べる。双曲線',
    '\\[x^2-3y^2=1\\quad(y\\ge0)\\]',
    'を考える。',
  ].join('\n'),
}

const recurrenceParent = {
  id: 'full-problems-recurrence-holdout',
  statement: 'n\\in\\mathbb N,\\ F_1=F_2=1,\\ F_{n+2}=F_{n+1}+F_n で定まる数列を考える。',
}

const powerParent = {
  id: 'full-problems-power-holdout',
  statement: [
    '実数 \\theta が \\sin\\theta+\\cos\\theta=\\frac{1}{2027} を満たす。',
    '\\sin^n\\theta+\\cos^n\\theta>\\frac{1}{2027} となる n を求めよ。',
  ].join('\n'),
}

test('unseen Pell and recurrence endpoints produce a certified product-orbit problem', () => {
  const cards = synthesizeCertifiedPellRecurrenceFusion([pellParent, recurrenceParent])
  assert.equal(cards.length, 1)
  const card = cards[0]
  assert.equal(card.answer_tex, '\\(n\\ge1,\\quad n\\bmod 8\\in\\{2,3,5\\}\\)')
  assert.equal(card.verification.exact_backend, true)
  assert.equal(card.verification.independent_check, true)
  assert.equal(card.fusion_derivation.ablationPassed, true)
  assert.equal(card.diagram.kind, 'state')
  assert.match(card.solution_tex, /完全状態が 24 段後/)
  assert.match(card.solution_tex, /最小周期は 8/)
})

test('coordinate and sequence renaming preserve the normalized structure', () => {
  const renamedPell = { id: 'renamed-pell', statement: 'u^{2}-3v^{2}=1' }
  const renamedRecurrence = {
    id: 'renamed-recurrence',
    statement: 'A_1=A_2=1,\\ A_{j+2}=A_{j+1}+A_j',
  }
  const original = synthesizeCertifiedPellRecurrenceFusion([pellParent, recurrenceParent])[0]
  const renamed = synthesizeCertifiedPellRecurrenceFusion([renamedRecurrence, renamedPell])[0]
  assert.ok(original)
  assert.ok(renamed)
  assert.equal(renamed.answer_tex, original.answer_tex)
  assert.equal(renamed.structure_blueprint.id, original.structure_blueprint.id)
})

test('changing the Pell discriminant recomputes the period and answer', () => {
  const mutation = { id: 'pell-two', statement: 'u^2-2v^2=1' }
  const base = synthesizeCertifiedPellRecurrenceFusion([pellParent, recurrenceParent])[0]
  const changed = synthesizeCertifiedPellRecurrenceFusion([mutation, recurrenceParent])[0]
  assert.ok(base)
  assert.ok(changed)
  assert.notEqual(changed.answer_tex, base.answer_tex)
  assert.equal(changed.answer_tex, '\\(n\\ge1,\\quad n\\bmod 3\\in\\{1,2\\}\\)')
  assert.notEqual(changed.structure_blueprint.id, base.structure_blueprint.id)
})

test('both parents are required and unrelated inputs abstain', () => {
  assert.deepEqual(synthesizeCertifiedPellRecurrenceFusion([pellParent]), [])
  assert.deepEqual(synthesizeCertifiedPellRecurrenceFusion([recurrenceParent]), [])
  assert.deepEqual(synthesizeCertifiedPellRecurrenceFusion([
    pellParent,
    { id: 'unrelated', statement: '三角形の面積を求めよ。' },
  ]), [])
})

test('the Pell parser derives the fundamental unit from the equation', () => {
  const parsed = parsePellOrbit(pellParent)
  assert.equal(parsed?.discriminant, 3n)
  assert.deepEqual(parsed?.fundamental, [2n, 1n])
})

test('generated TeX has no control characters', () => {
  const card = synthesizeCertifiedPellRecurrenceFusion([pellParent, recurrenceParent])[0]
  assert.ok(card)
  const rendered = card.statement_tex + '\n' + card.solution_tex
  assert.doesNotMatch(rendered, /[\u0000-\u0008\u000b\u000c\u000e-\u001f]/)
  assert.match(rendered, /\\sqrt/)
  assert.match(rendered, /\\pmod/)
})

test('the public registry dispatches the product-orbit engine', () => {
  const cards = synthesizeCertifiedFusions([pellParent, recurrenceParent], 1)
  assert.equal(cards[0]?.family_id, 'certified.pell_recurrence_state_product')
})

test('the same Pell orbit acts as an exponent generator for the shared power-sum kernel', () => {
  const cards = synthesizeCertifiedPellIndexedPowerSumFusion([pellParent, powerParent])
  assert.equal(cards.length, 1)
  const card = cards[0]
  assert.equal(card.answer_tex, '\\(k\\in\\{1\\}\\)')
  assert.match(card.statement_tex, /\\sin\^\{x_k\}/)
  assert.match(card.solution_tex, /x_k&2/)
  assert.match(card.solution_tex, /2026/)
  assert.doesNotMatch(card.solution_tex, /x_k&2&7/)
  assert.ok(card.solution_tex.includes(String.raw`奇数なら \(x_k\ge7\)`))
  assert.doesNotMatch(card.solution_tex, /Newton和|Pell単数/)
  assert.equal(card.verification.independent_check, true)
  assert.equal(card.fusion_derivation.ablationPassed, true)
})

test('mutating the Pell discriminant recomputes the indexed power-sum answer', () => {
  const mutation = { id: 'pell-five', statement: 'u^2-5v^2=1' }
  const base = synthesizeCertifiedPellIndexedPowerSumFusion([pellParent, powerParent])[0]
  const changed = synthesizeCertifiedPellIndexedPowerSumFusion([mutation, powerParent])[0]
  assert.ok(base)
  assert.ok(changed)
  assert.notEqual(changed.answer_tex, base.answer_tex)
  assert.equal(changed.answer_tex, '\\(k\\in\\varnothing\\)')
  assert.notEqual(changed.structure_blueprint.id, base.structure_blueprint.id)
})

test('the registry dispatches the Pell-indexed power-sum engine', () => {
  const cards = synthesizeCertifiedFusions([pellParent, powerParent], 1)
  assert.equal(cards[0]?.family_id, 'certified.pell_indexed_power_sum')
})
