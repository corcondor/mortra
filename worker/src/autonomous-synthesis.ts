import { createHash } from 'node:crypto'
import {
  discoverParentStructures,
  liftParent,
  type DiscoveryParent,
} from './parent-conditioned-discovery'
import {
  extractMobiusMap,
  synthesizeExecutableFusions,
  type ExecutableFusionCard,
} from './executable-fusion'
import { generalizeParents, type GeneralizationCertificate } from './generalization-kernel'
import { enumerateTypedTerms, type TypedEnumerationResult } from './typed-term-enumerator'
import {
  supportsPolynomialRootFusion,
  synthesizePolynomialRootFusions,
} from './polynomial-root-fusion'

export type StrategyAttempt = {
  strategy: string
  version: number
  round: number
  depth: number
  applicable: boolean
  generated: number
  reason: string
  elapsed_ms: number
}

export type AutonomousSearchState = {
  schema: 1
  parent_fingerprint: string
  round: number
  depth: number
  hypotheses_evaluated: number
  attempts: StrategyAttempt[]
  counterexamples: string[]
  frontier: Array<{ source: string; target: string; obligation: string }>
  continuing: boolean
  next_attempt_at: string | null
  state_budget?: number
  frontier_fingerprint?: string
  stagnant_rounds?: number
  last_progress_at?: string
  terms_enumerated?: number
  executable_goals?: number
}

export type SynthesisContext = {
  parents: DiscoveryParent[]
  requested: number
  round: number
  depth: number
  generalization: GeneralizationCertificate
  enumeration: TypedEnumerationResult
}

export type SynthesisStrategy = {
  id: string
  version: number
  supports: (context: SynthesisContext) => { applicable: boolean; reason: string }
  execute: (context: SynthesisContext) => ExecutableFusionCard[]
}

export type AutonomousSynthesisResult = {
  cards: ExecutableFusionCard[]
  discovery: ReturnType<typeof discoverParentStructures>
  state: AutonomousSearchState
  attempts: StrategyAttempt[]
  generalization: GeneralizationCertificate
  enumeration: TypedEnumerationResult
}

function fingerprint(parents: DiscoveryParent[]): string {
  return createHash('sha256').update(JSON.stringify(parents.map(parent => ({
    id: parent.id,
    statement: parent.statement,
    answer: parent.answer,
    solution: parent.solution,
  })))).digest('hex').slice(0, 20)
}

const RATIONAL_MAP_FINITE_ORBIT: SynthesisStrategy = {
  id: 'rational-map-finite-algebraic-orbit',
  version: 1,
  supports(context) {
    const operators = new Set(context.generalization.bindings.map(binding => binding.canonical))
    const hasRationalMap = operators.has('MobiusMap') || extractMobiusMap(context.parents) !== null
    const hasFiniteOrbit = operators.has('RootsOfUnity') || context.parents.some(parent =>
      /z\s*\^\s*\{?n\}?\s*=\s*1|1\s*の\s*n\s*乗根|1の冪根|roots? of unity/i.test(
        [parent.statement, parent.solution, parent.inspiration].filter(Boolean).join('\n'),
      ),
    )
    return {
      applicable: hasRationalMap && hasFiniteOrbit,
      reason: hasRationalMap && hasFiniteOrbit
        ? 'rational self-map and finite algebraic orbit are both present'
        : `missing ${!hasRationalMap ? 'rational-map' : 'finite-orbit'} input`,
    }
  },
  execute(context) {
    const minIteration = 2 + Math.max(0, context.round - 1) * 4
    return synthesizeExecutableFusions(context.parents, context.requested, {
      minIteration,
      maxIteration: minIteration + Math.max(3, context.depth),
    })
  },
}

const POLYNOMIAL_ROOT_COMPOSITION: SynthesisStrategy = {
  id: 'polynomial-root-set-composition',
  version: 1,
  supports(context) {
    const support = supportsPolynomialRootFusion(context.parents)
    return { applicable: support.applicable, reason: support.reason }
  },
  execute(context) {
    return synthesizePolynomialRootFusions(context.parents, context.requested, context.round)
  },
}

export const DEFAULT_SYNTHESIS_STRATEGIES: readonly SynthesisStrategy[] = [
  RATIONAL_MAP_FINITE_ORBIT,
  POLYNOMIAL_ROOT_COMPOSITION,
]

function initialState(parents: DiscoveryParent[]): AutonomousSearchState {
  return {
    schema: 1,
    parent_fingerprint: fingerprint(parents),
    round: 0,
    depth: 2,
    hypotheses_evaluated: 0,
    attempts: [],
    counterexamples: [],
    frontier: [],
    continuing: true,
    next_attempt_at: null,
    stagnant_rounds: 0,
  }
}

function compatibleState(
  parents: DiscoveryParent[],
  previous?: AutonomousSearchState | null,
): AutonomousSearchState {
  if (!previous || previous.schema !== 1 || previous.parent_fingerprint !== fingerprint(parents)) {
    return initialState(parents)
  }
  return {
    ...previous,
    attempts: [...previous.attempts],
    counterexamples: [...previous.counterexamples],
    frontier: [...previous.frontier],
  }
}

export function runAutonomousSynthesis(
  parents: DiscoveryParent[],
  requested: number,
  previous?: AutonomousSearchState | null,
  strategies: readonly SynthesisStrategy[] = DEFAULT_SYNTHESIS_STRATEGIES,
  now = new Date(),
): AutonomousSynthesisResult {
  const state = compatibleState(parents, previous)
  state.round += 1
  state.depth = Math.max(2, state.depth + (state.round > 1 ? 1 : 0))
  state.state_budget = Math.max(10_000, 10_000 * state.round)
  const discovery = discoverParentStructures(parents, requested)
  const generalized = generalizeParents(parents, state.depth, state.state_budget)
  const enumeration = enumerateTypedTerms(generalized.graphs, {
    maxDepth: state.depth,
    maxStates: state.state_budget,
  })
  state.terms_enumerated = enumeration.terms.length
  state.executable_goals = enumeration.goals.length
  state.hypotheses_evaluated += discovery.hypotheses.length
  state.frontier = enumeration.frontier.length
    ? enumeration.frontier.slice(0, 48).map(item => ({
        source: item.sources.join(' × '),
        target: item.target,
        obligation: `${item.morphism} requires ${item.missing.join(', ')}`,
      }))
    : generalized.certificate.roadmap.length
    ? generalized.certificate.roadmap.slice(0, 48).map(step => ({
        source: step.source,
        target: step.target,
        obligation: `${step.morphism} preserves ${step.preserves.join(', ')}`,
      }))
    : discovery.hypotheses.slice(0, 24).flatMap(hypothesis =>
        hypothesis.paths.map(path => ({
          source: path.start_sort,
          target: hypothesis.target_sort,
          obligation: hypothesis.proof_obligations[1],
        })),
      )

  const frontierFingerprint = createHash('sha256').update(JSON.stringify({
    frontier: state.frontier,
    target: generalized.certificate.target_sort,
    bindings: generalized.certificate.bindings,
    exhausted: generalized.certificate.search_evidence.exhausted,
  })).digest('hex').slice(0, 16)
  if (state.frontier_fingerprint === frontierFingerprint) {
    state.stagnant_rounds = (state.stagnant_rounds ?? 0) + 1
  } else {
    state.stagnant_rounds = 0
    state.last_progress_at = now.toISOString()
  }
  state.frontier_fingerprint = frontierFingerprint

  const context: SynthesisContext = {
    parents,
    requested,
    round: state.round,
    depth: state.depth,
    generalization: generalized.certificate,
    enumeration,
  }
  const roundAttempts: StrategyAttempt[] = []
  const cards: ExecutableFusionCard[] = []

  for (const strategy of strategies) {
    const started = Date.now()
    const support = strategy.supports(context)
    let generated: ExecutableFusionCard[] = []
    let reason = support.reason
    if (support.applicable) {
      try {
        generated = strategy.execute(context)
        reason = generated.length
          ? 'typed construction, exact backend, and independent verification succeeded'
          : 'applicable types found but verification produced no surviving construction'
      } catch (error) {
        reason = `strategy error: ${error instanceof Error ? error.message : String(error)}`
      }
    }
    const attempt: StrategyAttempt = {
      strategy: strategy.id,
      version: strategy.version,
      round: state.round,
      depth: state.depth,
      applicable: support.applicable,
      generated: generated.length,
      reason,
      elapsed_ms: Date.now() - started,
    }
    roundAttempts.push(attempt)
    state.attempts.push(attempt)
    cards.push(...generated.slice(0, Math.max(0, requested - cards.length)))
    if (cards.length >= requested) break
  }

  state.attempts = state.attempts.slice(-200)
  state.continuing = cards.length < requested
  state.next_attempt_at = state.continuing
    ? new Date(now.getTime() + 15 * 60 * 1000).toISOString()
    : null
  return { cards, discovery, state, attempts: roundAttempts, generalization: generalized.certificate, enumeration }
}

export function summarizeLift(parents: DiscoveryParent[]) {
  return parents.map(liftParent)
}

export function isAutonomousResearchDue(
  state: Partial<Pick<AutonomousSearchState, 'continuing' | 'next_attempt_at'>> | null | undefined,
  now = new Date(),
): boolean {
  if (!state?.continuing) return false
  return !state.next_attempt_at || Date.parse(state.next_attempt_at) <= now.getTime()
}
