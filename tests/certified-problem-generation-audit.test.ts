import assert from 'node:assert/strict'
import test from 'node:test'

import {
  attachCertifiedGenerationAudit,
  auditCertifiedGeneratedProblem,
} from '../lib/mortra/certified-problem-generation-audit.js'
import { planCertifiedFusions } from '../lib/mortra/certified-fusion-planner.js'

const parents = [
  {
    id: 'recurrence-parent',
    statement: String.raw`U_1=2,\ U_2=5,\qquad U_{j+2}=3U_{j+1}-U_j`,
  },
  {
    id: 'angle-parent',
    statement: String.raw`二直線のなす角は \frac{\pi}{7} である。`,
  },
]

function generatedCard() {
  const card = planCertifiedFusions(parents, 1).cards[0]
  assert.ok(card)
  return card
}

test('traceback certifies a genuinely cross-parent generated problem', () => {
  const audit = auditCertifiedGeneratedProblem(generatedCard(), parents)
  assert.equal(audit.passed, true)
  assert.equal(audit.reversePlaybackOnly, false)
  assert.deepEqual(new Set(audit.tracedParentIds), new Set(parents.map(parent => parent.id)))
  assert.equal(audit.checks.crossParentComposition, true)
  assert.equal(audit.checks.clauseCompleteness, true)
  assert.equal(audit.checks.premiseMinimality, true)
  assert.equal(audit.unusedPremiseIds.length, 0)
  assert.ok(audit.trace.some(node => node.kind === 'bridge' && node.parentIds.length === 2))
})

test('a missing cross-parent bridge is rejected as reverse playback', () => {
  const card = generatedCard()
  const audit = auditCertifiedGeneratedProblem({
    ...card,
    fusion_derivation: {
      ...card.fusion_derivation,
      bridges: [],
    },
  }, parents)
  assert.equal(audit.passed, false)
  assert.equal(audit.reversePlaybackOnly, true)
  assert.ok(audit.failures.includes('crossParentComposition'))
})

test('an unused parent clause is rejected', () => {
  const card = generatedCard()
  const audit = auditCertifiedGeneratedProblem({
    ...card,
    fusion_derivation: {
      ...card.fusion_derivation,
      assignments: card.fusion_derivation.assignments.slice(0, 1),
    },
  }, parents)
  assert.equal(audit.passed, false)
  assert.equal(audit.checks.clauseCompleteness, false)
  assert.equal(audit.checks.allParentDependence, false)
})

test('a declared premise outside the goal traceback is rejected', () => {
  const card = generatedCard()
  const audit = auditCertifiedGeneratedProblem({
    ...card,
    fusion_derivation: {
      ...card.fusion_derivation,
      assignments: [
        ...card.fusion_derivation.assignments,
        {
          parentId: parents[0].id,
          portId: 'unused_recurrence_annotation',
          role: 'unused',
          matchedAnchors: ['unused condition'],
          witnessSteps: ['UnusedElaboration'],
        },
      ],
    },
  }, parents)
  assert.equal(audit.passed, false)
  assert.equal(audit.checks.premiseMinimality, false)
  assert.deepEqual(audit.unusedPremiseIds, [
    `premise:${parents[0].id}:unused_recurrence_annotation`,
  ])
})

test('the public audit is attached without changing the proof card', () => {
  const card = generatedCard()
  const attached = attachCertifiedGenerationAudit(card, parents)
  assert.equal(attached.id, card.id)
  assert.equal(attached.generation_audit?.passed, true)
  assert.equal(attached.generation_audit?.proofStepCount, card.proof_roadmap?.length)
})
