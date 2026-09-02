import { createHash } from 'node:crypto'
import type { DiscoveryParent } from './parent-conditioned-discovery'
import { discoverParentStructures } from './parent-conditioned-discovery'
import {
  hasCompleteParentProof,
  runAutonomousSynthesis,
  type AutonomousSynthesisResult,
  type AutonomousSearchState,
  type StrategyAttempt,
} from './autonomous-synthesis'
import { generalizeParents } from './generalization-kernel'
import { capabilityOrigin } from './execution-certificate'
import type { ExecutableFusionCard } from './executable-fusion'
import { runtimeGenerationEngines } from './runtime-generation-registry'

function directRuntimeGeneration(
  parents: DiscoveryParent[],
  requested: number,
): AutonomousSynthesisResult | null {
  const attempts: StrategyAttempt[] = []
  const cards: ExecutableFusionCard[] = []
  for (const engine of runtimeGenerationEngines()) {
    if (cards.length >= requested) break
    const startedAt = Date.now()
    const result = engine.synthesize(parents, requested - cards.length)
    const generated = result.applicable
      ? result.cards.filter(card => hasCompleteParentProof(card, parents))
      : []
    cards.push(...generated.slice(0, requested - cards.length))
    attempts.push({
      strategy: engine.id,
      version: 1,
      round: 1,
      depth: 0,
      applicable: result.applicable,
      generated: generated.length,
      reason: generated.length
        ? 'current-input typed program and exact certificate closed without structural search'
        : result.reason,
      elapsed_ms: Date.now() - startedAt,
    })
  }

  // Partial direct output does not suppress the general search. It is returned
  // early only when the current-input kernels already satisfy the request.
  if (cards.length < requested) return null

  const discovery = discoverParentStructures(parents, requested)
  const generalized = generalizeParents(parents, 2, 512)
  const state: AutonomousSearchState = {
    schema: 1,
    parent_fingerprint: createHash('sha256').update(JSON.stringify(parents)).digest('hex').slice(0, 20),
    round: 1,
    depth: 0,
    hypotheses_evaluated: discovery.hypotheses.length,
    attempts,
    counterexamples: [],
    frontier: [],
    continuing: false,
    next_attempt_at: null,
    terms_enumerated: 0,
    executable_goals: cards.length,
    states_explored: generalized.certificate.search_evidence.states_explored,
    composite_cache_mode: 'not_consulted',
    reused_parameterized_morphisms: 0,
  }
  return {
    cards,
    discovery,
    state,
    attempts,
    generalization: generalized.certificate,
    enumeration: {
      terms: [],
      goals: [],
      frontier: [],
      statesExplored: generalized.certificate.search_evidence.states_explored,
      exhausted: generalized.certificate.search_evidence.exhausted,
    },
  }
}

/**
 * Product boundary for parent-conditioned generation.
 *
 * Persisted composites may be used elsewhere for replay/audit, but a product
 * request must be reachable from the current parents and primitive executors.
 */
export function runPublicRuntimeGeneration(
  parents: DiscoveryParent[],
  requested: number,
  previous?: AutonomousSearchState | null,
) {
  const result = directRuntimeGeneration(parents, requested)
    ?? runAutonomousSynthesis(parents, requested, previous)
  const forbidden = result.cards.filter(card =>
    capabilityOrigin(card.execution_certificate) === 'registered_parameterized_morphism' ||
    card.execution_certificate?.registered_composite_used === true,
  )
  if (forbidden.length) {
    throw new Error('public generation attempted to return a registered completed route')
  }
  return result
}
