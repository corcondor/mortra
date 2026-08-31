import assert from 'node:assert/strict'
import test from 'node:test'

import {
  parseMobiusRootTransport,
  synthesizeCertifiedMobiusPolynomialFusion,
} from './certified-mobius-polynomial-fusion'

const cubic = {
  id: 'cubic-parent',
  statement: String.raw`\[x^3-2026x^2-2029x-1=0\] を解け。`,
}

const transport = {
  id: 'transport-parent',
  statement: String.raw`変換 \[S=\frac{1}{1-x}\] により根を移し、\(S=g(S)\) の不動点として表す。`,
}

test('parses a nonsingular affine fractional transformation', () => {
  const parsed = parseMobiusRootTransport(transport)
  assert.ok(parsed)
  assert.deepEqual(parsed.matrix, [0n, 1n, -1n, 1n])
})

test('fuses an unseen cubic root configuration and Mobius transport without stored answers', () => {
  const card = synthesizeCertifiedMobiusPolynomialFusion([cubic, transport])[0]
  assert.ok(card)
  assert.equal(card.family_id, 'certified.mobius_polynomial_fixed_point_transport')
  assert.deepEqual(card.parent_ids, ['cubic-parent', 'transport-parent'])
  assert.equal(card.verification.exact_backend, true)
  assert.equal(card.verification.independent_check, true)
  assert.equal(card.fusion_derivation.ablationPassed, true)
  assert.match(card.answer_tex, /P\(S\)=/)
  assert.match(card.answer_tex, /g\(S\)=/)
  if (card.diagram.kind !== 'morphism') assert.fail('expected a morphism diagram')
  assert.ok(card.diagram.nodes.includes('逆変換で照合'))
})

test('renaming parent ids and swapping input order preserve the mathematical result', () => {
  const original = synthesizeCertifiedMobiusPolynomialFusion([cubic, transport])[0]
  const swapped = synthesizeCertifiedMobiusPolynomialFusion([
    { ...transport, id: 'renamed-transform' },
    { ...cubic, id: 'renamed-cubic' },
  ])[0]
  assert.ok(original)
  assert.ok(swapped)
  assert.equal(swapped.answer_tex, original.answer_tex)
  assert.deepEqual(swapped.morphism_chain, original.morphism_chain)
})

test('changing the polynomial coefficients recomputes the fixed-point equation', () => {
  const original = synthesizeCertifiedMobiusPolynomialFusion([cubic, transport])[0]
  const changed = synthesizeCertifiedMobiusPolynomialFusion([
    { id: 'changed', statement: String.raw`\[x^3-5x+1=0\] を解け。` },
    transport,
  ])[0]
  assert.ok(original)
  assert.ok(changed)
  assert.notEqual(changed.answer_tex, original.answer_tex)
  assert.deepEqual(changed.morphism_chain, original.morphism_chain)
})

test('keeps generic source and target symbols in the generated problem and proof', () => {
  const card = synthesizeCertifiedMobiusPolynomialFusion([
    { id: 'quartic', statement: String.raw`\[t^4+2t^3-3t^2+5t+1=0\] の根を考える。` },
    { id: 'generic-map', statement: String.raw`\[Y=\frac{2z+3}{z+2}\]` },
  ])[0]
  assert.ok(card)
  assert.match(card.statement_tex, /f\(t\)=/)
  assert.match(card.statement_tex, /T\(t\)=/)
  assert.match(card.statement_tex, /P\(Y\)/)
  assert.match(card.solution_tex, /Y=T\(t\)/)
  assert.doesNotMatch(card.solution_tex, /\(cx\+d\)/)
})

test('abstains when either typed endpoint is absent or the map is singular', () => {
  assert.deepEqual(synthesizeCertifiedMobiusPolynomialFusion([cubic, { id: 'plain', statement: '整数 n を求めよ。' }]), [])
  assert.equal(parseMobiusRootTransport({
    id: 'singular',
    statement: String.raw`\[S=\frac{2x+2}{x+1}\]`,
  }), null)
})
