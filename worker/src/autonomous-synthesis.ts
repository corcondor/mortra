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
import { executableMorphismAtlas, generalizeParents, type GeneralizationCertificate } from './generalization-kernel'
import {
  inducePrimitiveLaws,
  type PrimitiveLawInductionResult,
  type CertifiedLawRecord,
} from './primitive-law-inducer'
import { enumerateTypedTerms, type TypedEnumerationResult } from './typed-term-enumerator'
import {
  supportsPolynomialRootFusion,
  synthesizePolynomialRootFusions,
} from './polynomial-root-fusion'
import {
  induceArithmeticGeometryLemmas,
  type ArithmeticGeometryInductionResult,
} from './arithmetic-geometry-inducer'

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
  local_expansions?: number
  states_explored?: number
  progress_delta?: number
  induction_enumerated?: number
  induction_tested?: number
  induction_rejected?: number
  induced_laws?: number
  induction_engine?: string
  synthesis_terms_examined?: number
  equivalence_classes?: number
  cvc5_checked?: number
  cvc5_available?: boolean
  egglog_available?: boolean
  synthesized_programs?: SynthesizedProgram[]
}

export type SynthesizedProgram = {
  id: string
  input_parent_ids: string[]
  output_sort: string
  morphism_chain: string[]
  backend_contracts: string[]
  verified: true
}

export type SynthesisContext = {
  parents: DiscoveryParent[]
  requested: number
  round: number
  depth: number
  generalization: GeneralizationCertificate
  enumeration: TypedEnumerationResult
  induction: PrimitiveLawInductionResult
  arithmeticGeometry: ArithmeticGeometryInductionResult
}

const ARITHMETIC_GEOMETRY_CEGIS: SynthesisStrategy = {
  id: 'arithmetic-geometry-relational-synthesis',
  version: 1,
  supports(context) {
    return {
      applicable: context.arithmeticGeometry.applicable,
      reason: context.arithmeticGeometry.reason,
    }
  },
  execute(context) {
    return context.arithmeticGeometry.cards.slice(0, context.requested)
  },
}

const PRIMITIVE_LAW_CEGIS: SynthesisStrategy = {
  id: 'primitive-law-cegis',
  version: 1,
  supports(context) {
    return {
      applicable: context.induction.applicable,
      reason: context.induction.reason,
    }
  },
  execute(context) {
    return context.induction.cards.slice(0, context.requested)
  },
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

const TYPED_COMPOSITE_PROGRAM_SYNTHESIS: SynthesisStrategy = {
  id: 'typed-composite-program-synthesis',
  version: 1,
  supports(context) {
    const fullPrograms = context.enumeration.goals.filter(goal =>
      goal.parentIds.length === context.parents.length && goal.steps.every(step => step.backend.length > 0),
    )
    return {
      applicable: fullPrograms.length > 0,
      reason: fullPrograms.length
        ? `${fullPrograms.length} full-provenance typed programs are executable by primitive contracts`
        : 'no full-provenance typed program reaches an executable observable',
    }
  },
  execute(context) {
    const programs = context.enumeration.goals.map(goal => new Set(goal.steps.map(step => step.morphism)))
    const hasRootSetProgram = programs.some(chain =>
      chain.has('RootMinkowskiSum') || chain.has('RootMinkowskiDifference') || chain.has('RootPointwiseProduct'),
    )
    if (hasRootSetProgram && supportsPolynomialRootFusion(context.parents).applicable) {
      return synthesizePolynomialRootFusions(context.parents, context.requested, context.round)
    }
    const hasFiniteOrbitProgram = programs.some(chain => chain.has('MapOrbitEvaluation'))
    if (hasFiniteOrbitProgram && extractMobiusMap(context.parents)) {
      const minIteration = 2 + Math.max(0, context.round - 1) * 4
      return synthesizeExecutableFusions(context.parents, context.requested, {
        minIteration,
        maxIteration: minIteration + Math.max(3, context.depth),
      })
    }
    return []
  },
}

export const DEFAULT_SYNTHESIS_STRATEGIES: readonly SynthesisStrategy[] = [
  ARITHMETIC_GEOMETRY_CEGIS,
  PRIMITIVE_LAW_CEGIS,
  TYPED_COMPOSITE_PROGRAM_SYNTHESIS,
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
  certifiedLaws: CertifiedLawRecord[] = [],
): AutonomousSynthesisResult {
  const state = compatibleState(parents, previous)
  state.round += 1
  state.depth = Math.max(2, state.depth + (state.round > 1 ? 1 : 0))
  state.state_budget = Math.max(10_000, 10_000 * state.round)
  const discovery = discoverParentStructures(parents, requested)
  const priorTerms = state.terms_enumerated ?? 0
  const priorGoals = state.executable_goals ?? 0
  const expansionStarted = Date.now()
  let generalized = generalizeParents(parents, state.depth, state.state_budget)
  const induction = inducePrimitiveLaws(parents, requested, state.round, state.depth, certifiedLaws)
  const arithmeticGeometry = induceArithmeticGeometryLemmas(parents, requested, state.round, certifiedLaws)
  state.induction_enumerated = induction.telemetry.enumerated + arithmeticGeometry.telemetry.enumerated
  state.induction_tested = induction.telemetry.tested + arithmeticGeometry.telemetry.tested
  state.induction_rejected = induction.telemetry.rejected_elimination +
    induction.telemetry.rejected_numeric + induction.telemetry.rejected_ablation +
    induction.telemetry.rejected_duplicate + arithmeticGeometry.telemetry.rejected
  state.induced_laws = induction.rules.length + arithmeticGeometry.rules.length
  state.induction_engine = [induction.telemetry.synthesis_engine, arithmeticGeometry.telemetry.synthesis_engine]
    .filter(engine => engine !== 'unavailable')
    .join(' + ') || 'unavailable'
  state.synthesis_terms_examined = induction.telemetry.synthesis_terms_examined + arithmeticGeometry.telemetry.enumerated
  state.equivalence_classes = induction.telemetry.equivalence_classes + arithmeticGeometry.telemetry.equivalence_classes
  state.cvc5_checked = induction.telemetry.cvc5_checked
  state.cvc5_available = induction.telemetry.cvc5_available
  state.egglog_available = induction.telemetry.egglog_available
  const learnedRules = certifiedLaws.map(law => ({
    name: law.name,
    sources: law.sources,
    target: law.target,
    preserves: law.preserves,
    backend: law.backend,
  }))
  const executableRules = induction.rules.length || arithmeticGeometry.rules.length || learnedRules.length
    ? [...executableMorphismAtlas(), ...learnedRules, ...induction.rules, ...arithmeticGeometry.rules]
    : undefined
  let enumeration = enumerateTypedTerms(generalized.graphs, {
    maxDepth: Math.max(6, state.depth),
    maxStates: state.state_budget,
    rules: executableRules,
  })
  let selectedScore = enumeration.goals.length * 1_000_000 + enumeration.terms.length
  let localExpansions = 1
  let deepestExplored = state.depth
  // A worker invocation should perform meaningful search, not merely add one
  // depth and sleep. Widen locally while bounded by wall time and state budget.
  for (let expansion = 1; expansion < 3 && Date.now() - expansionStarted < 20_000; expansion++) {
    const candidateDepth = state.depth + expansion * 2
    const candidateBudget = Math.min(250_000, state.state_budget * (expansion + 1))
    const candidateGeneralization = generalizeParents(parents, candidateDepth, candidateBudget)
    const candidateEnumeration = enumerateTypedTerms(candidateGeneralization.graphs, {
      maxDepth: Math.max(6, candidateDepth),
      maxStates: candidateBudget,
      rules: executableRules,
    })
    localExpansions++
    deepestExplored = candidateDepth
    const candidateScore = candidateEnumeration.goals.length * 1_000_000 + candidateEnumeration.terms.length
    if (candidateScore >= selectedScore) {
      generalized = candidateGeneralization
      enumeration = candidateEnumeration
      selectedScore = candidateScore
    }
    if (candidateEnumeration.goals.length >= requested) break
  }
  state.depth = deepestExplored
  state.terms_enumerated = enumeration.terms.length
  state.executable_goals = enumeration.goals.length
  state.local_expansions = localExpansions
  state.states_explored = enumeration.statesExplored
  state.progress_delta = Math.max(0, enumeration.terms.length - priorTerms) +
    Math.max(0, enumeration.goals.length - priorGoals) * 1000
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
    induction,
    arithmeticGeometry,
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
  state.synthesized_programs = cards.map(card => ({
    id: `program.${createHash('sha256').update(JSON.stringify({
      parents: card.parent_ids,
      chain: card.morphism_chain,
      observable: card.structure_blueprint.observable,
    })).digest('hex').slice(0, 16)}`,
    input_parent_ids: [...card.parent_ids],
    output_sort: card.structure_blueprint.observable,
    morphism_chain: [...card.morphism_chain],
    backend_contracts: [...new Set(card.structure_blueprint.proofCertificate.map(step => step.verifier))],
    verified: true,
  }))
  state.continuing = cards.length < requested
  const retryDelayMs = state.progress_delta > 0
    ? 60_000
    : (state.stagnant_rounds ?? 0) < 3
    ? 2 * 60_000
    : 5 * 60_000
  state.next_attempt_at = state.continuing ? new Date(now.getTime() + retryDelayMs).toISOString() : null
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
