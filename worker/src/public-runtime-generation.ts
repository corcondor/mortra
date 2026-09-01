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
import {
  supportsPolynomialRootFusion,
  synthesizePolynomialRootFusions,
} from './polynomial-root-fusion'
import { synthesizeRuntimeExpressionProblems } from './runtime-expression-synthesizer'
import { synthesizeRuntimeLatticePickProblems } from './runtime-lattice-pick-generation'
import { synthesizeRuntimeLinearProblems } from './runtime-linear-problem-generation'
import { synthesizeRuntimeQuadraticExpectationProblems } from './runtime-quadratic-expectation-generation'
import { synthesizeRuntimeRecurrenceCongruenceProblems } from './runtime-recurrence-congruence-generation'
import { synthesizeRuntimePrimitiveRightTriangleProblems } from './runtime-primitive-right-triangle-generation'

function directRuntimeGeneration(
  parents: DiscoveryParent[],
  requested: number,
): AutonomousSynthesisResult | null {
  const attempts: StrategyAttempt[] = []
  const cards: ExecutableFusionCard[] = []
  const record = (
    strategy: string,
    applicable: boolean,
    reason: string,
    execute: () => ReturnType<typeof synthesizePolynomialRootFusions>,
  ) => {
    if (cards.length >= requested) return
    const startedAt = Date.now()
    const generated = applicable
      ? execute().filter(card => hasCompleteParentProof(card, parents))
      : []
    cards.push(...generated.slice(0, requested - cards.length))
    attempts.push({
      strategy,
      version: 1,
      round: 1,
      depth: 0,
      applicable,
      generated: generated.length,
      reason: generated.length
        ? 'current-input typed program and exact certificate closed without structural search'
        : reason,
      elapsed_ms: Date.now() - startedAt,
    })
  }

  const polynomial = supportsPolynomialRootFusion(parents)
  record(
    'runtime-polynomial-root-generation',
    polynomial.applicable,
    polynomial.reason,
    () => synthesizePolynomialRootFusions(parents, requested - cards.length, 1),
  )

  if (cards.length < requested) {
    const quadraticExpectation = synthesizeRuntimeQuadraticExpectationProblems(parents, requested - cards.length)
    record(
      'runtime-quadratic-expectation-generation',
      quadraticExpectation.applicable,
      quadraticExpectation.reason,
      () => quadraticExpectation.cards,
    )
  }

  if (cards.length < requested) {
    const recurrenceCongruence = synthesizeRuntimeRecurrenceCongruenceProblems(parents, requested - cards.length)
    record(
      'runtime-recurrence-congruence-generation',
      recurrenceCongruence.applicable,
      recurrenceCongruence.reason,
      () => recurrenceCongruence.cards,
    )
  }

  if (cards.length < requested) {
    const latticePick = synthesizeRuntimeLatticePickProblems(parents, requested - cards.length)
    record(
      'runtime-lattice-pick-generation',
      latticePick.applicable,
      latticePick.reason,
      () => latticePick.cards,
    )
  }

  if (cards.length < requested) {
    const primitiveRightTriangle = synthesizeRuntimePrimitiveRightTriangleProblems(parents, requested - cards.length)
    record(
      'runtime-primitive-right-triangle-generation',
      primitiveRightTriangle.applicable,
      primitiveRightTriangle.reason,
      () => primitiveRightTriangle.cards,
    )
  }

  if (cards.length < requested) {
    const linear = synthesizeRuntimeLinearProblems(parents, requested - cards.length)
    record(
      'runtime-linear-problem-generation',
      linear.applicable,
      linear.reason,
      () => linear.cards,
    )
  }

  if (cards.length < requested) {
    const expression = synthesizeRuntimeExpressionProblems(parents, requested - cards.length)
    record(
      'runtime-expression-grammar',
      expression.applicable,
      expression.reason,
      () => expression.cards,
    )
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
