import assert from 'node:assert/strict'
import test from 'node:test'
import {
  parseMonicIntegerPolynomial,
  synthesizeCertifiedPolynomialFusions,
} from '../lib/mortra/certified-fusion'

const parents = [
  { id: 'left', statement: '方程式 $x^2-2=0$ の根を考える。' },
  { id: 'right', statement: '方程式 $y^2-3=0$ の根を考える。' },
]

test('parses unseen monic integer polynomial constraints without problem ids', () => {
  const parsed = parseMonicIntegerPolynomial({ id: 'p', statement: '三次方程式 $t^3-2t+7=0$ を考える。' })
  assert.deepEqual(parsed?.coefficients, [7n, -2n, 0n, 1n])
})

test('ignores prose wrapped in LaTeX text commands while elaborating the equation', () => {
  const parsed = parseMonicIntegerPolynomial({
    id: 'p',
    statement: String.raw`\text{方程式 }x^3-6x^2+11x-6=0\text{ の根を考える。}`,
  })
  assert.deepEqual(parsed?.coefficients, [-6n, 11n, -6n, 1n])
})

test('rejects linear endpoints whose root operation can erase one parent contribution', () => {
  const linear = parseMonicIntegerPolynomial({ id: 'p', statement: '方程式 $x-1=0$ の根を考える。' })
  assert.equal(linear, null)
})

test('generates three exact fusion problems through two independent algebraic routes', () => {
  const cards = synthesizeCertifiedPolynomialFusions(parents, 3)
  assert.equal(cards.length, 3)
  assert.match(cards[0].answer_tex.replace(/\s/g, ''), /z\^\{4\}-10z\^\{2\}\+1/)
  assert.equal(cards[0].verification.exact_backend, true)
  assert.equal(cards[0].verification.independent_check, true)
  assert.equal(cards[0].fusion_derivation.ablationPassed, true)
  assert.deepEqual(cards[0].parent_ids, ['left', 'right'])
  assert.match(cards[0].statement_tex, /\\prod_\{i=1\}/)
  assert.match(cards[0].statement_tex, /\\alpha_i\+\\beta_j/)
})

test('renaming variables preserves the certificate and answer', () => {
  const renamed = [
    { id: 'a', statement: '方程式 $u^2-2=0$ の根を考える。' },
    { id: 'b', statement: '方程式 $v^2-3=0$ の根を考える。' },
  ]
  const original = synthesizeCertifiedPolynomialFusions(parents, 1)[0]
  const transformed = synthesizeCertifiedPolynomialFusions(renamed, 1)[0]
  assert.equal(transformed.answer_tex, original.answer_tex)
  assert.deepEqual(transformed.morphism_chain, original.morphism_chain)
})

test('coefficient mutation recomputes the result instead of replaying an answer', () => {
  const changed = [
    { id: 'left', statement: '方程式 $x^2-5=0$ の根を考える。' },
    { id: 'right', statement: '方程式 $y^2-7=0$ の根を考える。' },
  ]
  const original = synthesizeCertifiedPolynomialFusions(parents, 1)[0]
  const transformed = synthesizeCertifiedPolynomialFusions(changed, 1)[0]
  assert.notEqual(transformed.answer_tex, original.answer_tex)
  assert.deepEqual(transformed.morphism_chain, original.morphism_chain)
})

test('abstains when either endpoint cannot elaborate to the supported executable IR', () => {
  const unsupported = [
    parents[0],
    { id: 'geometry', statement: '三角形の内心と外心の関係を証明せよ。' },
  ]
  assert.deepEqual(synthesizeCertifiedPolynomialFusions(unsupported, 1), [])
})
