import assert from 'node:assert/strict'
import test from 'node:test'
import { executableMorphismAtlas } from './generalization-kernel'
import {
  JUDGMENT_KINDS,
  OBJECT_CONSTRUCTORS,
  STRUCTURAL_PRIMITIVES,
  dischargeProofObligations,
  distinctDeclaredContracts,
  hasOpenProofObligations,
  lowerMorphismToKnowledgeCore,
} from './kernel-calculus'
import { auditStandardModel } from './standard-model-audit'

test('every named map becomes a typed declaration and application', () => {
  for (const rule of executableMorphismAtlas()) {
    const lowering = lowerMorphismToKnowledgeCore(rule)
    assert.equal(lowering.declaration.primitive, 'constant-declaration')
    assert.equal(lowering.application.constructor, 'application')
    assert.equal(lowering.judgments[0].kind, 'has-type')
    assert.equal(lowering.declaration.parameters.length, rule.sources.length)
    assert.equal(lowering.proof_obligations[0].kind, 'definedness')
    assert.equal(lowering.proof_obligations.at(-1)?.kind, 'implementation-realization')
    assert.ok(lowering.proof_obligations.every(item => item.status === 'open'))
    assert.ok(!JSON.stringify(lowering).match(/dataset|benchmark|expected_answer/i))
  }
})

test('backend labels do not discharge preservation obligations', () => {
  const lowering = lowerMorphismToKnowledgeCore({
    name: 'ExampleMap',
    sources: ['A'],
    target: 'B',
    preserves: ['order'],
    backend: ['lean', 'sympy'],
  })
  assert.equal(hasOpenProofObligations(lowering), true)
  assert.ok(lowering.proof_obligations.every(item => item.evidence === null))
})

test('an explicit certificate discharges only the addressed obligation', () => {
  const lowering = lowerMorphismToKnowledgeCore({
    name: 'CertifiedMap',
    sources: ['A'],
    target: 'B',
    preserves: ['value'],
    backend: ['exact'],
  })
  const target = lowering.proof_obligations.find(item => item.kind === 'preservation')
  assert.ok(target)
  if (!target) return
  const discharged = dischargeProofObligations(lowering, {
    [target.id]: {
      verifier: 'unit-test',
      certificate: { constructor: 'literal', value: 'checked' },
    },
  })
  assert.equal(discharged.proof_obligations.filter(item => item.status === 'discharged').length, 1)
  assert.equal(hasOpenProofObligations(discharged), true)
})

test('declared-contract collisions are visible but are not equality proofs', () => {
  const duplicate = [
    { name: 'FirstName', sources: ['A'], target: 'B', preserves: ['x'], backend: ['exact'] },
    { name: 'SecondName', sources: ['A'], target: 'B', preserves: ['x'], backend: ['exact'] },
  ]
  assert.equal(distinctDeclaredContracts(duplicate).length, 1)
  assert.notEqual(duplicate[0].name, duplicate[1].name)
})

test('audit separates object syntax, module structure and judgments', () => {
  const audit = auditStandardModel([
    { id: 'a', statement: '実数 x が $x+3=11$ を満たすとき x を求めよ。' },
    { id: 'b', statement: '三角形 ABC の面積を求めよ。' },
  ])
  assert.equal(audit.corpus.total, 2)
  assert.equal(audit.atlas.object_constructors, OBJECT_CONSTRUCTORS.length)
  assert.equal(audit.atlas.structural_primitives, STRUCTURAL_PRIMITIVES.length)
  assert.equal(audit.atlas.judgment_kinds, JUDGMENT_KINDS.length)
  assert.ok(audit.atlas.proof_obligations > 0)
  assert.equal(audit.atlas.proof_obligations, audit.atlas.open_proof_obligations)
  assert.equal(audit.atlas.certified_executable_morphisms, 0)
  assert.ok(audit.atlas.named_morphisms > audit.atlas.object_constructors)
})
