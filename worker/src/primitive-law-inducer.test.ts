import assert from 'node:assert/strict'
import test from 'node:test'
import { inducePrimitiveLaws } from './primitive-law-inducer'

const parents = [
  { id: 'left', statement: '方程式 $u^2-2=0$ の根を考える。' },
  { id: 'right', statement: '方程式 $v^2-3=0$ の根を考える。' },
]

test('induces previously unregistered executable laws from a typed expression grammar', () => {
  const result = inducePrimitiveLaws(parents, 3, 1, 8)
  assert.equal(result.applicable, true)
  assert.ok(result.telemetry.enumerated > result.telemetry.certified)
  assert.ok(result.cards.length >= 2)
  assert.equal(result.rules.length, result.cards.length)
  assert.ok(result.rules.every(rule => rule.name.startsWith('InducedAlgebraicLaw_')))
  assert.ok(result.cards.every(card => card.verification.exact_backend && card.fusion_derivation.ablationPassed))
  assert.ok(result.cards.every(card => card.parent_ids.includes('left') && card.parent_ids.includes('right')))
  assert.equal(result.telemetry.synthesis_engine, 'cvc5-sygus-enum')
  assert.equal(result.telemetry.cvc5_available, true)
  assert.equal(result.telemetry.egglog_available, true)
  assert.match(result.cards[0].statement_tex, /f_\{2\}/)
  assert.ok(result.cards.every(card =>
    card.execution_certificate?.capability_origin === 'synthesized_proof_program'))
  assert.ok(result.cards.every(card =>
    card.execution_certificate?.registered_composite_used === false))
  assert.ok(result.cards.every(card =>
    card.execution_certificate?.composite_cache_role === 'not_consulted'))
})

test('uses every selected polynomial parent in one synthesized observable', () => {
  const result = inducePrimitiveLaws([
    ...parents,
    { id: 'third', statement: '方程式 $w^2-5=0$ の根を考える。' },
  ], 1, 1, 8)
  assert.equal(result.cards.length, 1)
  assert.deepEqual(result.cards[0].parent_ids, ['left', 'right', 'third'])
  assert.equal(result.rules[0].sources.length, 3)
  assert.equal(result.cards[0].fusion_derivation.assignments.length, 3)
  assert.equal(result.cards[0].fusion_derivation.bridges[0].consumes.length, 3)
  assert.match(result.cards[0].statement_tex, /f_\{3\}/)
})

test('coefficient perturbation recomputes answers while preserving induced law identity', () => {
  const first = inducePrimitiveLaws(parents, 1, 1, 8)
  const changed = inducePrimitiveLaws([
    { id: 'left-new', statement: '方程式 $a^2-5=0$ の根を考える。' },
    { id: 'right-new', statement: '方程式 $b^2-7=0$ の根を考える。' },
  ], 1, 1, 8)
  assert.equal(first.rules[0].name, changed.rules[0].name)
  assert.notEqual(first.cards[0].answer_tex, changed.cards[0].answer_tex)
})

test('later rounds explore different certified expression programs', () => {
  const first = inducePrimitiveLaws(parents, 2, 1, 8)
  const later = inducePrimitiveLaws(parents, 2, 2, 8)
  const firstExpressions = new Set(first.cards.map(card => card.fusion_derivation.bridges[0].witnessStep))
  const laterExpressions = new Set(later.cards.map(card => card.fusion_derivation.bridges[0].witnessStep))
  assert.ok(later.cards.length > 0)
  assert.ok(later.cards.some(card => !firstExpressions.has(card.fusion_derivation.bridges[0].witnessStep)))
  assert.ok(first.cards.some(card => !laterExpressions.has(card.fusion_derivation.bridges[0].witnessStep)))
})

test('uses the composite cache only to exclude duplicates and still synthesizes a new program', () => {
  const first = inducePrimitiveLaws(parents, 1, 1, 8)
  const firstLaw = first.cards[0].structure_blueprint.synthesizedLaw!
  const next = inducePrimitiveLaws(parents, 1, 1, 8, [firstLaw])
  assert.equal(next.cards.length, 1)
  assert.notEqual(
    next.cards[0].fusion_derivation.bridges[0].witnessStep,
    first.cards[0].fusion_derivation.bridges[0].witnessStep,
  )
  assert.equal(next.cards[0].execution_certificate?.registered_composite_used, false)
  assert.equal(next.cards[0].execution_certificate?.composite_cache_role, 'duplicate_exclusion_only')
})

test('does not fabricate a law when parent constraints cannot be executed', () => {
  const result = inducePrimitiveLaws([
    { id: 'a', statement: '未知対象 A に操作 F を施す。' },
    { id: 'b', statement: '未知対象 B に操作 G を施す。' },
  ], 2, 1, 8)
  assert.equal(result.applicable, false)
  assert.equal(result.rules.length, 0)
  assert.equal(result.cards.length, 0)
})

test('does not discard non-polynomial obligations from a rich parent', () => {
  const result = inducePrimitiveLaws([
    { id: 'root', statement: '方程式 $u^2-2=0$ の根を考える。' },
    { id: 'rich', statement: '行列 $A$ の n 乗から得る漸化式が素数で割り切れることを示せ。' },
  ], 2, 1, 8)
  assert.equal(result.applicable, false)
  assert.equal(result.cards.length, 0)
})
