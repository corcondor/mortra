import assert from 'node:assert/strict'
import test from 'node:test'

import {
  synthesizeCertifiedPolynomialFusions,
  type CertifiedFusionParent,
} from './certified-fusion'
import { synthesizeCertifiedFusions } from './certified-fusion-registry'

const unseenParents: CertifiedFusionParent[] = [
  {
    id: 'free-text-cubic',
    statement: String.raw`方程式 \(u^3-7u+3=0\) の根を考える。`,
  },
  {
    id: 'free-text-quadratic',
    statement: String.raw`方程式 \(v^2+v-5=0\) の根を考える。`,
  },
]

test('one unseen pair yields seven exact questions from reusable root observables', () => {
  const cards = synthesizeCertifiedPolynomialFusions(unseenParents, 7)

  assert.equal(cards.length, 7)
  assert.equal(new Set(cards.map(card => card.id)).size, 7)
  assert.deepEqual(cards.map(card => card.family_id), [
    'certified.polynomial_root_sum',
    'certified.polynomial_root_product',
    'certified.polynomial_root_difference',
    'certified.polynomial_root_sum_trace_norm',
    'certified.polynomial_root_product_trace_norm',
    'certified.polynomial_root_difference_trace_norm',
    'certified.polynomial_root_sum_power_sums',
  ])
  assert.match(cards[3].answer_tex, /T=-3/)
  assert.match(cards[3].answer_tex, /N=51/)
  assert.match(cards[6].answer_tex, /s_1=-3/)
  assert.match(cards[6].answer_tex, /s_2=61/)
  assert.match(cards[6].answer_tex, /s_3=-108/)
  assert.match(cards[6].answer_tex, /\\quad/)
  assert.match(cards[6].statement_tex, /\\qquad/)
  assert.doesNotMatch(cards[3].statement_tex, /f\(x\)=\\\)/)
  assert.ok(cards.every(card => card.solution_tex.length > 0))
  assert.ok(cards.every(card => card.diagram.kind === 'morphism'))
})

test('all seven unseen questions pass the public all-parent generation audit', () => {
  const cards = synthesizeCertifiedFusions(unseenParents, 7)

  assert.equal(cards.length, 7)
  for (const card of cards) {
    assert.deepEqual(new Set(card.parent_ids), new Set(unseenParents.map(parent => parent.id)))
    assert.equal(card.verification.exact_backend, true)
    assert.equal(card.verification.independent_check, true)
    assert.equal(card.generation_audit?.passed, true, card.generation_audit?.failures.join(','))
    assert.equal(card.generation_audit?.checks.allParentDependence, true)
    assert.equal(card.generation_audit?.checks.crossParentComposition, true)
  }
})

test('renaming parent ids does not change the mathematics', () => {
  const original = synthesizeCertifiedPolynomialFusions(unseenParents, 7)
  const renamed = synthesizeCertifiedPolynomialFusions([
    { ...unseenParents[0], id: 'renamed-a' },
    { ...unseenParents[1], id: 'renamed-b' },
  ], 7)

  assert.deepEqual(
    renamed.map(card => card.answer_tex),
    original.map(card => card.answer_tex),
  )
})

test('changing a coefficient recomputes projected invariants', () => {
  const original = synthesizeCertifiedPolynomialFusions(unseenParents, 7)
  const changed = synthesizeCertifiedPolynomialFusions([
    {
      id: 'changed-cubic',
      statement: String.raw`方程式 \(u^3-u^2-7u+3=0\) の根を考える。`,
    },
    unseenParents[1],
  ], 7)
  const originalTrace = original.find(card => card.family_id === 'certified.polynomial_root_sum_trace_norm')
  const changedTrace = changed.find(card => card.family_id === 'certified.polynomial_root_sum_trace_norm')

  assert.ok(originalTrace)
  assert.ok(changedTrace)
  assert.notEqual(changedTrace.answer_tex, originalTrace.answer_tex)
  assert.deepEqual(changedTrace.morphism_chain, originalTrace.morphism_chain)
})
