import { createHash } from 'node:crypto'

import {
  hasCompleteParentProof,
  type AutonomousSearchState,
} from './autonomous-synthesis'
import {
  capabilityOrigin,
  certificateParentSha256,
  certificateValueSha256,
  type CapabilityOrigin,
} from './execution-certificate'
import type { ExecutableFusionCard } from './executable-fusion'
import type { DiscoveryParent } from './parent-conditioned-discovery'
import { auditPublicationContent } from './publication-content-audit'

export type CardReplayEvidence = {
  schema: 'mortra.card-replay.v1'
  card_id: string
  status: 'accepted' | 'rejected'
  errors: string[]
  capability_origin: CapabilityOrigin | null
  parent_ids: string[]
  input_binding_sha256: string
  artifact_sha256: string
  proof_sha256: string
  execution_certificate_sha256: string
  generated_program_sha256: string | null
  replay_sha256: string
}

export type ResearchEvidenceEnvelope = {
  schema: 'mortra.research-evidence.v1'
  round: number
  status: 'certified' | 'certified_partial' | 'open' | 'rejected'
  previous_evidence_sha256: string | null
  input: {
    parent_ids: string[]
    certificate_parent_sha256: string
    parent_source_sha256: string
  }
  output: {
    requested_card_count: number
    attempted_card_count: number
    accepted_card_count: number
    rejected_card_count: number
    accepted_card_ids: string[]
    rejected_card_ids: string[]
    accepted_artifact_set_sha256: string
  }
  unresolved: {
    continuing: boolean
    frontier_count: number
    frontier_sha256: string
    execution_obligation_count: number
    execution_obligations_sha256: string
  }
  card_replays: CardReplayEvidence[]
  evidence_sha256: string
}

type SealResearchRoundInput = {
  parents: readonly DiscoveryParent[]
  cards: readonly ExecutableFusionCard[]
  requested: number
  state: AutonomousSearchState
  previousEvidenceSha256?: string | null
  now?: Date
}

export type SealedResearchRound = {
  cards: ExecutableFusionCard[]
  state: AutonomousSearchState
  evidence: ResearchEvidenceEnvelope
}

function canonicalize(value: unknown, arrayElement = false): unknown {
  if (value === undefined || typeof value === 'function' || typeof value === 'symbol') {
    return arrayElement ? null : undefined
  }
  if (value === null || typeof value === 'string' || typeof value === 'boolean') return value
  if (typeof value === 'number') return Number.isFinite(value) ? value : null
  if (typeof value === 'bigint') return { $bigint: value.toString() }
  if (Array.isArray(value)) return value.map(item => canonicalize(item, true))
  if (value instanceof Date) return value.toISOString()
  if (typeof value === 'object') {
    const output: Record<string, unknown> = {}
    for (const key of Object.keys(value as Record<string, unknown>).sort()) {
      const normalized = canonicalize((value as Record<string, unknown>)[key])
      if (normalized !== undefined) output[key] = normalized
    }
    return output
  }
  return String(value)
}

export function canonicalJson(value: unknown): string {
  return JSON.stringify(canonicalize(value)) ?? 'null'
}

export function canonicalSha256(value: unknown): string {
  return createHash('sha256').update(canonicalJson(value)).digest('hex')
}

function textSha256(value: string): string {
  return createHash('sha256').update(value).digest('hex')
}

function parentSourcePayload(parents: readonly DiscoveryParent[]) {
  return parents.map(parent => ({
    id: String(parent.id),
    statement: parent.statement ?? '',
    answer: parent.answer ?? null,
    solution: parent.solution ?? null,
    inspiration: parent.inspiration ?? null,
  }))
}

function artifactPayload(card: ExecutableFusionCard) {
  const {
    research_evidence: _researchEvidence,
    verification,
    ...artifact
  } = card
  return {
    ...artifact,
    verification: {
      method: verification.method,
      exact_backend: verification.exact_backend,
      independent_check: verification.independent_check,
      samples: verification.samples,
    },
  }
}

function proofPayload(card: ExecutableFusionCard) {
  return {
    morphism_chain: card.morphism_chain,
    fusion_derivation: card.fusion_derivation,
    blueprint_id: card.structure_blueprint.id,
    blueprint_kernel: card.structure_blueprint.kernel,
    blueprint_observable: card.structure_blueprint.observable,
    blueprint_morphism_chain: card.structure_blueprint.morphismChain,
    proof_certificate: card.structure_blueprint.proofCertificate,
    proof_obligations: card.proof_obligations ?? null,
  }
}

function replayDigestPayload(replay: Omit<CardReplayEvidence, 'replay_sha256'>) {
  return replay
}

export function replayCardEvidence(
  card: ExecutableFusionCard,
  parents: readonly DiscoveryParent[],
): CardReplayEvidence {
  const errors: string[] = []
  const certificate = card.execution_certificate
  const origin = capabilityOrigin(certificate)
  const expectedInputHash = certificateParentSha256(parents)

  if (!card.statement_tex.trim()) errors.push('generated statement is empty')
  if (!card.answer_tex.trim()) errors.push('exact answer is empty')
  if (!card.solution_tex.trim()) errors.push('worked solution is empty')
  errors.push(...auditPublicationContent(card).errors)
  if (card.unresolved !== false || card.discovery_status !== 'verified') {
    errors.push('card is not marked as a verified resolved artifact')
  }
  if (!hasCompleteParentProof(card, parents)) {
    errors.push('parent-to-goal proof coverage is incomplete')
  }
  if (!origin) errors.push('execution certificate has no recognized verified capability origin')
  if (origin === 'registered_parameterized_morphism' || certificate?.registered_composite_used === true) {
    errors.push('registered completed-route replay cannot certify autonomous generation')
  }

  let inputBindingFound = false
  if (certificate && typeof certificate.input_parent_sha256 === 'string') {
    inputBindingFound = true
    if (certificate.input_parent_sha256 !== expectedInputHash) {
      errors.push('execution certificate parent hash does not match the current input')
    }
  }
  if (certificate && typeof certificate.statement_sha256 === 'string') {
    inputBindingFound = true
    if (parents.length !== 1 ||
        certificate.statement_sha256 !== textSha256((parents[0].statement ?? '').trim())) {
      errors.push('execution certificate statement hash does not match the current input')
    }
  }
  if (!inputBindingFound) errors.push('execution certificate is not bound to the current input')

  let resultBindingFound = false
  let generatedProgramHash: string | null = null
  if (certificate && ('generated_program' in certificate || 'generated_program_sha256' in certificate)) {
    resultBindingFound = true
    if (typeof certificate.generated_program_sha256 !== 'string' ||
        !('generated_program' in certificate)) {
      errors.push('generated program and its hash must both be present')
    } else {
      generatedProgramHash = certificate.generated_program_sha256
      if (certificateValueSha256(certificate.generated_program) !== certificate.generated_program_sha256) {
        errors.push('generated program hash does not match the executable program')
      }
    }
  }
  if (certificate && typeof certificate.answer_tex_sha256 === 'string') {
    resultBindingFound = true
    if (certificate.answer_tex_sha256 !== textSha256(card.answer_tex)) {
      errors.push('execution certificate answer hash does not match the generated answer')
    }
  }
  if (!resultBindingFound) errors.push('execution certificate is not bound to a generated program or answer')

  if (certificate && Array.isArray(certificate.morphism_chain)) {
    if (!certificate.morphism_chain.every(item => typeof item === 'string') ||
        certificate.morphism_chain.join('\u0000') !== card.morphism_chain.join('\u0000')) {
      errors.push('execution certificate morphism chain does not match the proof artifact')
    }
  }
  if (card.structure_blueprint.proofCertificate.some(step =>
    !step.id.trim() || !step.claim.trim() || !step.verifier.trim())) {
    errors.push('proof certificate contains an incomplete verification step')
  }

  const withoutDigest: Omit<CardReplayEvidence, 'replay_sha256'> = {
    schema: 'mortra.card-replay.v1',
    card_id: card.id,
    status: errors.length ? 'rejected' : 'accepted',
    errors: [...new Set(errors)].sort(),
    capability_origin: origin,
    parent_ids: [...card.parent_ids],
    input_binding_sha256: expectedInputHash,
    artifact_sha256: canonicalSha256(artifactPayload(card)),
    proof_sha256: canonicalSha256(proofPayload(card)),
    execution_certificate_sha256: canonicalSha256(certificate ?? null),
    generated_program_sha256: generatedProgramHash,
  }
  return {
    ...withoutDigest,
    replay_sha256: canonicalSha256(replayDigestPayload(withoutDigest)),
  }
}

function unresolvedPayload(state: AutonomousSearchState) {
  const executionObligations = [...(state.execution_obligations ?? [])]
  return {
    continuing: state.continuing,
    frontier_count: state.frontier.length,
    frontier_sha256: canonicalSha256(state.frontier),
    execution_obligation_count: executionObligations.length,
    execution_obligations_sha256: canonicalSha256(executionObligations),
  }
}

function envelopeWithoutDigest(input: {
  parents: readonly DiscoveryParent[]
  requested: number
  state: AutonomousSearchState
  previousEvidenceSha256: string | null
  replays: CardReplayEvidence[]
}): Omit<ResearchEvidenceEnvelope, 'evidence_sha256'> {
  const accepted = input.replays.filter(replay => replay.status === 'accepted')
  const rejected = input.replays.filter(replay => replay.status === 'rejected')
  const status: ResearchEvidenceEnvelope['status'] = rejected.length > 0 && accepted.length === 0
    ? 'rejected'
    : accepted.length >= input.requested && !input.state.continuing && rejected.length === 0
      ? 'certified'
      : accepted.length > 0
        ? 'certified_partial'
        : 'open'
  return {
    schema: 'mortra.research-evidence.v1',
    round: input.state.round,
    status,
    previous_evidence_sha256: input.previousEvidenceSha256,
    input: {
      parent_ids: input.parents.map(parent => String(parent.id)),
      certificate_parent_sha256: certificateParentSha256(input.parents),
      parent_source_sha256: canonicalSha256(parentSourcePayload(input.parents)),
    },
    output: {
      requested_card_count: input.requested,
      attempted_card_count: input.replays.length,
      accepted_card_count: accepted.length,
      rejected_card_count: rejected.length,
      accepted_card_ids: accepted.map(replay => replay.card_id),
      rejected_card_ids: rejected.map(replay => replay.card_id),
      accepted_artifact_set_sha256: canonicalSha256(accepted.map(replay => replay.artifact_sha256)),
    },
    unresolved: unresolvedPayload(input.state),
    card_replays: input.replays,
  }
}

function appendRejectedEvidence(
  state: AutonomousSearchState,
  rejected: readonly CardReplayEvidence[],
  now: Date,
): AutonomousSearchState {
  if (!rejected.length) return state
  const diagnostics = rejected.map(replay =>
    `${replay.card_id}: ${replay.errors.join('; ')}`)
  const obligations = rejected.map(replay =>
    `certificate replay for ${replay.card_id}: ${replay.errors.join('; ')}`)
  return {
    ...state,
    continuing: true,
    next_attempt_at: new Date(now.getTime() + 60_000).toISOString(),
    counterexamples: [...new Set([...state.counterexamples, ...diagnostics])].slice(-200),
    execution_obligations: [
      ...new Set([...(state.execution_obligations ?? []), ...obligations]),
    ].slice(0, 200),
    frontier: [
      ...state.frontier,
      ...rejected.map(replay => ({
        source: replay.card_id,
        target: 'replayable certified artifact',
        obligation: replay.errors.join('; '),
      })),
    ].slice(0, 48),
  }
}

export function sealResearchRound(input: SealResearchRoundInput): SealedResearchRound {
  const replays = input.cards.map(card => replayCardEvidence(card, input.parents))
  const rejected = replays.filter(replay => replay.status === 'rejected')
  const state = appendRejectedEvidence(input.state, rejected, input.now ?? new Date())
  const withoutDigest = envelopeWithoutDigest({
    parents: input.parents,
    requested: input.requested,
    state,
    previousEvidenceSha256: input.previousEvidenceSha256 ?? null,
    replays,
  })
  const evidence: ResearchEvidenceEnvelope = {
    ...withoutDigest,
    evidence_sha256: canonicalSha256(withoutDigest),
  }
  const cards = input.cards.flatMap((card, index) => {
    const replay = replays[index]
    if (replay.status !== 'accepted') return []
    return [{
      ...card,
      verification: {
        ...card.verification,
        certificate_sha256: replay.replay_sha256,
      },
      research_evidence: {
        schema: 'mortra.card-replay.v1' as const,
        envelope_sha256: evidence.evidence_sha256,
        previous_evidence_sha256: evidence.previous_evidence_sha256,
        replay_sha256: replay.replay_sha256,
        artifact_sha256: replay.artifact_sha256,
        proof_sha256: replay.proof_sha256,
        execution_certificate_sha256: replay.execution_certificate_sha256,
      },
    }]
  })
  return { cards, state, evidence }
}

export function verifyResearchEvidenceEnvelope(input: {
  evidence: ResearchEvidenceEnvelope
  parents: readonly DiscoveryParent[]
  acceptedCards: readonly ExecutableFusionCard[]
  state: AutonomousSearchState
}): string[] {
  const errors: string[] = []
  const { evidence_sha256: recordedDigest, ...withoutDigest } = input.evidence
  if (canonicalSha256(withoutDigest) !== recordedDigest) {
    errors.push('research evidence envelope hash mismatch')
  }
  if (input.evidence.input.certificate_parent_sha256 !== certificateParentSha256(input.parents)) {
    errors.push('research evidence input certificate hash mismatch')
  }
  if (input.evidence.input.parent_source_sha256 !== canonicalSha256(parentSourcePayload(input.parents))) {
    errors.push('research evidence full parent-source hash mismatch')
  }
  if (canonicalJson(input.evidence.input.parent_ids) !==
      canonicalJson(input.parents.map(parent => String(parent.id)))) {
    errors.push('research evidence parent identifiers mismatch')
  }
  if (canonicalJson(input.evidence.unresolved) !== canonicalJson(unresolvedPayload(input.state))) {
    errors.push('research evidence unresolved-obligation state mismatch')
  }

  const acceptedEvidence = input.evidence.card_replays.filter(replay => replay.status === 'accepted')
  for (const replay of input.evidence.card_replays) {
    const { replay_sha256: replayDigest, ...replayWithoutDigest } = replay
    if (canonicalSha256(replayWithoutDigest) !== replayDigest) {
      errors.push(`${replay.card_id}: stored card replay digest mismatch`)
    }
  }
  if (acceptedEvidence.length !== input.acceptedCards.length) {
    errors.push('research evidence accepted-card count mismatch')
  }
  for (const card of input.acceptedCards) {
    const expected = acceptedEvidence.find(replay => replay.card_id === card.id)
    if (!expected) {
      errors.push(`research evidence has no accepted replay for ${card.id}`)
      continue
    }
    const replayed = replayCardEvidence(card, input.parents)
    if (replayed.status !== 'accepted') {
      errors.push(...replayed.errors.map(error => `${card.id}: ${error}`))
    }
    if (replayed.artifact_sha256 !== expected.artifact_sha256) {
      errors.push(`${card.id}: artifact hash mismatch`)
    }
    if (replayed.proof_sha256 !== expected.proof_sha256) {
      errors.push(`${card.id}: proof hash mismatch`)
    }
    if (replayed.execution_certificate_sha256 !== expected.execution_certificate_sha256) {
      errors.push(`${card.id}: execution certificate hash mismatch`)
    }
    if (canonicalJson(replayed) !== canonicalJson(expected)) {
      errors.push(`${card.id}: independently replayed evidence differs from the stored replay`)
    }
  }
  return [...new Set(errors)]
}
