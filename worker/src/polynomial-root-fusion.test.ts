import assert from 'node:assert/strict'
import test from 'node:test'
import {
  supportsPolynomialRootFusion,
  synthesizePolynomialRootFusions,
} from './polynomial-root-fusion'

const parents = [
  { id: 'left', statement: '方程式 $x^2-2=0$ の根について考える。' },
  { id: 'right', statement: '方程式 $y^2-3=0$ の根について考える。' },
]

test('constructs a new root-set problem by exact elimination', () => {
  const cards = synthesizePolynomialRootFusions(parents, 3, 1)
  assert.equal(cards.length, 3)
  assert.match(cards[0].answer_tex.replace(/\s/g, ''), /z\^\{4\}-10z\^\{2\}\+1/)
  assert.ok(cards.every(card => card.verification.exact_backend))
  assert.ok(cards.every(card => card.verification.independent_check))
  assert.ok(cards.every(card => card.fusion_derivation.ablationPassed))
  assert.ok(cards.every(card => card.parent_ids.join(',') === 'left,right'))
})

test('renaming variables keeps the same morphism certificate', () => {
  const renamed = [
    { id: 'a', statement: '方程式 $u^2-2=0$ の根について考える。' },
    { id: 'b', statement: '方程式 $v^2-3=0$ の根について考える。' },
  ]
  const original = synthesizePolynomialRootFusions(parents, 1, 1)[0]
  const transformed = synthesizePolynomialRootFusions(renamed, 1, 1)[0]
  assert.ok(original)
  assert.ok(transformed)
  assert.equal(transformed.answer_tex, original.answer_tex)
  assert.deepEqual(transformed.morphism_chain, original.morphism_chain)
})

test('coefficient changes are computed instead of returning a memorized answer', () => {
  const changed = [
    { id: 'left', statement: '方程式 $x^2-5=0$ の根について考える。' },
    { id: 'right', statement: '方程式 $y^2-7=0$ の根について考える。' },
  ]
  const original = synthesizePolynomialRootFusions(parents, 1, 1)[0]
  const transformed = synthesizePolynomialRootFusions(changed, 1, 1)[0]
  assert.ok(original)
  assert.ok(transformed)
  assert.notEqual(transformed.answer_tex, original.answer_tex)
  assert.deepEqual(transformed.morphism_chain, original.morphism_chain)
})

test('abstains unless two distinct parents provide executable polynomial inputs', () => {
  const unsupported = [
    { id: 'left', statement: '方程式 $x^2-2=0$ の根について考える。' },
    { id: 'right', statement: '関数 $f(x)$ の積分を求めよ。' },
  ]
  assert.equal(supportsPolynomialRootFusion(unsupported).applicable, false)
  assert.deepEqual(synthesizePolynomialRootFusions(unsupported, 1), [])
})
