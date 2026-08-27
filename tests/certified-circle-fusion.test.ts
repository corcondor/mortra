import assert from 'node:assert/strict'
import test from 'node:test'

import {
  parseAffineCircleParent,
  synthesizeCertifiedCircleRadicalAxisFusion,
} from '../lib/mortra/certified-circle-fusion.js'

const parents = [
  { id: 'left', statement: '円 $x^2+y^2-6x+4y-3=0$ を考える。' },
  { id: 'right', statement: '円 $2x^2+2y^2+4x-8y-10=0$ を考える。' },
]

test('parses scaled affine circle equations without problem ids', () => {
  const parsed = parseAffineCircleParent(parents[1])
  assert.ok(parsed)
  assert.deepEqual(parsed.chart.center, { x: '-1', y: '2' })
  assert.equal(parsed.chart.radiusSquared, '10')
})

test('generates a proof-and-diagram radical-axis problem from two circle parents', () => {
  const cards = synthesizeCertifiedCircleRadicalAxisFusion(parents)
  assert.equal(cards.length, 1)
  assert.equal(cards[0].family_id, 'certified.circle_radical_axis')
  assert.deepEqual(cards[0].parent_ids, ['left', 'right'])
  assert.match(cards[0].answer_tex.replace(/\s/g, ''), /-8x\+8y\+2=0/)
  assert.match(cards[0].statement_tex, /C_2:x\^\{2\}\+y\^\{2\}\+2x-4y-5=0/)
  assert.match(cards[0].statement_tex, /\$P\(x,y\)\$/)
  assert.match(cards[0].solution_tex, /方べき/)
  assert.equal(cards[0].diagram.kind, 'morphism')
  assert.equal(cards[0].verification.independent_check, true)
  assert.equal(cards[0].fusion_derivation.ablationPassed, true)
})

test('common scaling of either equation preserves the generated result', () => {
  const scaled = [
    { id: 'left-scaled', statement: '円 $3x^2+3y^2-18x+12y-9=0$ を考える。' },
    parents[1],
  ]
  const original = synthesizeCertifiedCircleRadicalAxisFusion(parents)[0]
  const transformed = synthesizeCertifiedCircleRadicalAxisFusion(scaled)[0]
  assert.equal(transformed.answer_tex, original.answer_tex)
})

test('changing a parent circle changes the radical axis instead of replaying an answer', () => {
  const changed = [
    parents[0],
    { id: 'changed', statement: '円 $x^2+y^2+2x-4y-1=0$ を考える。' },
  ]
  const original = synthesizeCertifiedCircleRadicalAxisFusion(parents)[0]
  const transformed = synthesizeCertifiedCircleRadicalAxisFusion(changed)[0]
  assert.notEqual(transformed.answer_tex, original.answer_tex)
})

test('rejects a non-circle endpoint and concentric pairs', () => {
  assert.deepEqual(synthesizeCertifiedCircleRadicalAxisFusion([
    parents[0],
    { id: 'line', statement: '直線 $x+y=0$ を考える。' },
  ]), [])
  assert.deepEqual(synthesizeCertifiedCircleRadicalAxisFusion([
    { id: 'c1', statement: '円 $x^2+y^2-1=0$ を考える。' },
    { id: 'c2', statement: '円 $x^2+y^2-4=0$ を考える。' },
  ]), [])
})
