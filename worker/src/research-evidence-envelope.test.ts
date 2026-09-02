import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import test from 'node:test'

import {
  runAutonomousSynthesis,
  type AutonomousSearchState,
} from './autonomous-synthesis'
import {
  canonicalSha256,
  sealResearchRound,
  verifyResearchEvidenceEnvelope,
} from './research-evidence-envelope'

const parents = [{
  id: 'unseen-evidence-linear',
  statement: '実数 $x,y$ は $x+y=19$, $y=4$ を満たす。$x$ を求めよ。',
}]

function solvedRound() {
  const result = runAutonomousSynthesis(
    parents,
    1,
    null,
    undefined,
    new Date('2026-09-03T00:00:00.000Z'),
  )
  assert.equal(result.cards.length, 1)
  return result
}

function sha256Text(value: string): string {
  return createHash('sha256').update(value).digest('hex')
}

test('canonical evidence hashing is independent of object key insertion order', () => {
  assert.equal(
    canonicalSha256({ beta: [3, 2, 1], alpha: { y: 2, x: 1 } }),
    canonicalSha256({ alpha: { x: 1, y: 2 }, beta: [3, 2, 1] }),
  )
})

test('seals a cold typed result and independently replays every binding', () => {
  const result = solvedRound()
  const sealed = sealResearchRound({
    parents,
    cards: result.cards,
    requested: 1,
    state: result.state,
    now: new Date('2026-09-03T00:01:00.000Z'),
  })

  assert.equal(sealed.cards.length, 1)
  assert.equal(sealed.evidence.status, 'certified')
  assert.equal(sealed.evidence.output.accepted_card_count, 1)
  assert.equal(sealed.evidence.output.rejected_card_count, 0)
  assert.match(sealed.evidence.evidence_sha256, /^[0-9a-f]{64}$/)
  assert.equal(
    sealed.cards[0].verification.certificate_sha256,
    sealed.evidence.card_replays[0].replay_sha256,
  )
  assert.equal(
    sealed.cards[0].research_evidence?.envelope_sha256,
    sealed.evidence.evidence_sha256,
  )
  assert.deepEqual(verifyResearchEvidenceEnvelope({
    evidence: sealed.evidence,
    parents,
    acceptedCards: sealed.cards,
    state: sealed.state,
  }), [])
})

test('accepts a cross-runtime certificate only when statement, answer, and morphism hashes bind', () => {
  const result = solvedRound()
  const card = structuredClone(result.cards[0])
  card.execution_certificate = {
    verified: true,
    capability_origin: 'verified_backend_execution',
    registered_composite_used: false,
    statement_sha256: sha256Text(parents[0].statement),
    answer_tex_sha256: sha256Text(card.answer_tex),
    morphism_chain: [...card.morphism_chain],
  }
  const sealed = sealResearchRound({
    parents,
    cards: [card],
    requested: 1,
    state: result.state,
  })

  assert.equal(sealed.cards.length, 1)
  assert.equal(sealed.evidence.status, 'certified')
  assert.equal(sealed.evidence.card_replays[0].capability_origin, 'verified_backend_execution')
})

test('seals the actual binder-aware Python certificate used by the persistent worker', () => {
  const expressionParents = [{
    id: 'unseen-evidence-integral',
    statement: '$\\int_0^1 t^2\\,dt$ を求めよ。',
  }]
  const result = runAutonomousSynthesis(expressionParents, 1)
  const sealed = sealResearchRound({
    parents: expressionParents,
    cards: result.cards,
    requested: 1,
    state: result.state,
  })

  assert.equal(result.cards[0].answer_tex, '\\(\\frac{1}{3}\\)')
  assert.equal(sealed.cards.length, 1)
  assert.equal(sealed.evidence.status, 'certified')
  assert.equal(sealed.evidence.card_replays[0].capability_origin, 'synthesized_expression_program')
})

test('rejects a generated program whose certificate hash no longer matches', () => {
  const result = solvedRound()
  const card = structuredClone(result.cards[0])
  assert.ok(card.execution_certificate)
  card.execution_certificate.generated_program = {
    tampered: true,
    original: card.execution_certificate.generated_program,
  }
  const sealed = sealResearchRound({
    parents,
    cards: [card],
    requested: 1,
    state: result.state,
    now: new Date('2026-09-03T00:02:00.000Z'),
  })

  assert.equal(sealed.cards.length, 0)
  assert.equal(sealed.evidence.status, 'rejected')
  assert.equal(sealed.evidence.output.rejected_card_count, 1)
  assert.equal(sealed.state.continuing, true)
  assert.ok(sealed.state.execution_obligations?.some(obligation =>
    obligation.includes('generated program hash does not match')))
})

test('detects changes to a sealed solution and to full parent provenance', () => {
  const result = solvedRound()
  const sealed = sealResearchRound({
    parents,
    cards: result.cards,
    requested: 1,
    state: result.state,
  })
  const changedCard = structuredClone(sealed.cards[0])
  changedCard.solution_tex += ' 改変'
  const changedParents = [{ ...parents[0], answer: 'preloaded answer' }]

  const cardErrors = verifyResearchEvidenceEnvelope({
    evidence: sealed.evidence,
    parents,
    acceptedCards: [changedCard],
    state: sealed.state,
  })
  assert.ok(cardErrors.some(error => error.includes('artifact hash mismatch')))

  const parentErrors = verifyResearchEvidenceEnvelope({
    evidence: sealed.evidence,
    parents: changedParents,
    acceptedCards: sealed.cards,
    state: sealed.state,
  })
  assert.ok(parentErrors.some(error => error.includes('full parent-source hash mismatch')))
})

test('chains unresolved rounds without claiming a certified result', () => {
  const firstState: AutonomousSearchState = {
    schema: 1,
    parent_fingerprint: 'unresolved-parent',
    round: 3,
    depth: 5,
    hypotheses_evaluated: 120,
    attempts: [],
    counterexamples: [],
    frontier: [{
      source: 'QuadraticConstraint',
      target: 'CertifiedExtremum',
      obligation: 'prove boundedness before maximizing',
    }],
    continuing: true,
    next_attempt_at: '2026-09-03T00:05:00.000Z',
    execution_obligations: ['exact bounded-domain elimination'],
  }
  const first = sealResearchRound({
    parents,
    cards: [],
    requested: 1,
    state: firstState,
  })
  const second = sealResearchRound({
    parents,
    cards: [],
    requested: 1,
    state: { ...firstState, round: 4, depth: 6 },
    previousEvidenceSha256: first.evidence.evidence_sha256,
  })

  assert.equal(first.evidence.status, 'open')
  assert.equal(second.evidence.status, 'open')
  assert.equal(second.evidence.previous_evidence_sha256, first.evidence.evidence_sha256)
  assert.notEqual(second.evidence.evidence_sha256, first.evidence.evidence_sha256)
  assert.deepEqual(verifyResearchEvidenceEnvelope({
    evidence: second.evidence,
    parents,
    acceptedCards: [],
    state: second.state,
  }), [])
})
