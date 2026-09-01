import { createHash } from 'node:crypto'
import {
  discoverParentStructures,
  liftParent,
  type DiscoveryParent,
} from './parent-conditioned-discovery'
import type { ExecutableFusionCard } from './executable-fusion'
import { primitiveMorphismBasis, generalizeParents, type GeneralizationCertificate } from './generalization-kernel'
import {
  inducePrimitiveLaws,
  type PrimitiveLawInductionResult,
  type CertifiedLawRecord,
} from './primitive-law-inducer'
import { enumerateTypedTerms, type TypedEnumerationResult } from './typed-term-enumerator'
import {
  executeTypedPrograms,
  inspectTypedProgramExecution,
} from './typed-program-executor'
import {
  induceArithmeticGeometryLemmas,
  type ArithmeticGeometryInductionResult,
} from './arithmetic-geometry-inducer'
import {
  exactSingleProblemSupport,
  synthesizeExactSingleProblem,
} from './single-problem-exact'
import { synthesizeExactCasSingleProblem } from './single-problem-cas'
import { synthesizeRuntimeExpressionProblems } from './runtime-expression-synthesizer'
import { synthesizeRuntimeLinearProblems } from './runtime-linear-problem-generation'
import { synthesizeRuntimeQuadraticExpectationProblems } from './runtime-quadratic-expectation-generation'
import { synthesizeRuntimeRecurrenceCongruenceProblems } from './runtime-recurrence-congruence-generation'
import { synthesizeRuntimePrimitiveRightTriangleProblems } from './runtime-primitive-right-triangle-generation'
import {
  supportsPolynomialRootFusion,
  synthesizePolynomialRootFusions,
} from './polynomial-root-fusion'
import {
  capabilityOrigin,
  isRuntimeSynthesisCertificate,
} from './execution-certificate'

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
  reused_parameterized_morphisms?: number
  primitive_executions?: number
  composite_cache_entries?: number
  composite_cache_mode?: 'not_consulted' | 'duplicate_exclusion_only'
  execution_obligations?: string[]
}

export type SynthesizedProgram = {
  id: string
  input_parent_ids: string[]
  output_sort: string
  morphism_chain: string[]
  backend_contracts: string[]
  origin: string
  verified: true
}

export function hasCompleteParentProof(
  card: ExecutableFusionCard,
  parents: readonly DiscoveryParent[],
): boolean {
  const expectedParents = new Set(parents.map(parent => String(parent.id)))
  const cardParents = new Set(card.parent_ids.map(String))
  if (cardParents.size !== expectedParents.size || [...expectedParents].some(id => !cardParents.has(id))) {
    return false
  }

  const assignments = card.fusion_derivation.assignments
  const assignedParents = new Set(assignments.map(assignment => String(assignment.parentId)))
  if (assignedParents.size !== expectedParents.size || [...expectedParents].some(id => !assignedParents.has(id))) {
    return false
  }

  for (const assignment of assignments) {
    if (!assignment.portId || assignment.witnessSteps.length === 0 || assignment.matchedAnchors.length === 0) {
      return false
    }
    const required = assignment.requiredObligations ?? []
    const consumed = new Set(assignment.consumedObligations ?? [])
    if (required.some(obligation => !consumed.has(obligation))) return false
    if (typeof assignment.coverage === 'number' && assignment.coverage !== 1) return false
  }

  const consumedPorts = new Set(card.fusion_derivation.bridges.flatMap(bridge => bridge.consumes))
  if (assignments.some(assignment => !consumedPorts.has(assignment.portId))) return false
  if (card.morphism_chain.length === 0 || card.structure_blueprint.proofCertificate.length === 0) return false
  if (card.morphism_chain.join('\u0000') !== card.structure_blueprint.morphismChain.join('\u0000')) return false
  if (!capabilityOrigin(card.execution_certificate)) return false
  return card.verification.exact_backend && card.verification.independent_check
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
  compositeCacheRole: 'not_consulted' | 'duplicate_exclusion_only'
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

const EXACT_SINGLE_PROBLEM: SynthesisStrategy = {
  id: 'exact-single-problem-proof-synthesis',
  version: 1,
  supports(context) {
    return exactSingleProblemSupport(context.parents)
  },
  execute(context) {
    return synthesizeExactSingleProblem(context.parents).slice(0, context.requested)
  },
}

const EXACT_CAS_SINGLE_PROBLEM: SynthesisStrategy = {
  id: 'exact-cas-single-problem-proof-synthesis',
  version: 1,
  supports(context) {
    const result = synthesizeExactCasSingleProblem(context.parents)
    return { applicable: result.applicable, reason: result.reason }
  },
  execute(context) {
    return synthesizeExactCasSingleProblem(context.parents).cards.slice(0, context.requested)
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

const RUNTIME_TYPED_PROGRAM_EXECUTION: SynthesisStrategy = {
  id: 'runtime-typed-program-execution',
  version: 1,
  supports(context) {
    const fullPrograms = context.enumeration.goals.filter(goal =>
      goal.parentIds.length === context.parents.length &&
      goal.steps.every(step => step.backend.length > 0) &&
      inspectTypedProgramExecution(goal.program).executable,
    )
    return {
      applicable: fullPrograms.length > 0,
      reason: fullPrograms.length
        ? `${fullPrograms.length} cold typed ASTs are executable by primitive handlers`
        : 'no full-provenance typed AST reaches a currently implemented primitive handler',
    }
  },
  execute(context) {
    return executeTypedPrograms(
      context.parents,
      context.enumeration.goals,
      context.requested,
      context.compositeCacheRole,
    ).cards
  },
}

const RUNTIME_EXPRESSION_GRAMMAR: SynthesisStrategy = {
  id: 'runtime-expression-grammar',
  version: 1,
  supports(context) {
    const result = synthesizeRuntimeExpressionProblems(context.parents, context.requested)
    return { applicable: result.applicable, reason: result.reason }
  },
  execute(context) {
    return synthesizeRuntimeExpressionProblems(context.parents, context.requested).cards
  },
}

const RUNTIME_POLYNOMIAL_ROOT_GENERATION: SynthesisStrategy = {
  id: 'runtime-polynomial-root-generation',
  version: 1,
  supports(context) {
    if (context.parents.length !== 2) {
      return { applicable: false, reason: 'binary root-set composition currently requires exactly two selected parents' }
    }
    const support = supportsPolynomialRootFusion(context.parents)
    return { applicable: support.applicable, reason: support.reason }
  },
  execute(context) {
    return synthesizePolynomialRootFusions(context.parents, context.requested, context.round)
  },
}

const RUNTIME_LINEAR_PROBLEM_GENERATION: SynthesisStrategy = {
  id: 'runtime-linear-problem-generation',
  version: 1,
  supports(context) {
    const result = synthesizeRuntimeLinearProblems(context.parents, context.requested)
    return { applicable: result.applicable, reason: result.reason }
  },
  execute(context) {
    return synthesizeRuntimeLinearProblems(context.parents, context.requested).cards
  },
}

const RUNTIME_QUADRATIC_EXPECTATION_GENERATION: SynthesisStrategy = {
  id: 'runtime-quadratic-expectation-generation',
  version: 1,
  supports(context) {
    const result = synthesizeRuntimeQuadraticExpectationProblems(context.parents, context.requested)
    return { applicable: result.applicable, reason: result.reason }
  },
  execute(context) {
    return synthesizeRuntimeQuadraticExpectationProblems(context.parents, context.requested).cards
  },
}

const RUNTIME_RECURRENCE_CONGRUENCE_GENERATION: SynthesisStrategy = {
  id: 'runtime-recurrence-congruence-generation',
  version: 1,
  supports(context) {
    const result = synthesizeRuntimeRecurrenceCongruenceProblems(context.parents, context.requested)
    return { applicable: result.applicable, reason: result.reason }
  },
  execute(context) {
    return synthesizeRuntimeRecurrenceCongruenceProblems(context.parents, context.requested).cards
  },
}

const RUNTIME_PRIMITIVE_RIGHT_TRIANGLE_GENERATION: SynthesisStrategy = {
  id: 'runtime-primitive-right-triangle-generation',
  version: 1,
  supports(context) {
    const result = synthesizeRuntimePrimitiveRightTriangleProblems(context.parents, context.requested)
    return { applicable: result.applicable, reason: result.reason }
  },
  execute(context) {
    return synthesizeRuntimePrimitiveRightTriangleProblems(context.parents, context.requested).cards
  },
}

export const DEFAULT_SYNTHESIS_STRATEGIES: readonly SynthesisStrategy[] = [
  ARITHMETIC_GEOMETRY_CEGIS,
  RUNTIME_POLYNOMIAL_ROOT_GENERATION,
  RUNTIME_QUADRATIC_EXPECTATION_GENERATION,
  RUNTIME_RECURRENCE_CONGRUENCE_GENERATION,
  RUNTIME_PRIMITIVE_RIGHT_TRIANGLE_GENERATION,
  RUNTIME_TYPED_PROGRAM_EXECUTION,
  RUNTIME_LINEAR_PROBLEM_GENERATION,
  RUNTIME_EXPRESSION_GRAMMAR,
  PRIMITIVE_LAW_CEGIS,
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
  state.composite_cache_entries = certifiedLaws.length
  state.composite_cache_mode = certifiedLaws.length ? 'duplicate_exclusion_only' : 'not_consulted'
  // Persisted composites may prevent duplicate publication, but they never add
  // reachability to the cold synthesis graph. Fresh success must be derivable
  // from the primitive basis and laws induced from the current parents.
  const executableRules = induction.rules.length || arithmeticGeometry.rules.length
    ? [...primitiveMorphismBasis(), ...induction.rules, ...arithmeticGeometry.rules]
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
  state.execution_obligations = [...new Set(enumeration.goals
    .filter(goal => goal.parentIds.length === parents.length)
    .flatMap(goal => inspectTypedProgramExecution(goal.program).unsupported))]
    .slice(0, 64)
  const structuralFrontier = enumeration.frontier.length
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
  state.frontier = [
    ...state.execution_obligations.map(obligation => ({
      source: 'typed program',
      target: 'primitive executor',
      obligation,
    })),
    ...structuralFrontier,
  ].slice(0, 48)

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
    compositeCacheRole: state.composite_cache_mode ?? 'not_consulted',
  }
  const roundAttempts: StrategyAttempt[] = []
  const cards: ExecutableFusionCard[] = []

  const activeStrategies = parents.length === 1 && strategies === DEFAULT_SYNTHESIS_STRATEGIES
    ? [EXACT_SINGLE_PROBLEM, EXACT_CAS_SINGLE_PROBLEM, ...strategies]
    : strategies
  for (const strategy of activeStrategies) {
    const remaining = Math.max(0, requested - cards.length)
    if (remaining === 0) break
    const strategyContext = remaining === context.requested
      ? context
      : { ...context, requested: remaining }
    const started = Date.now()
    const support = strategy.supports(strategyContext)
    let generated: ExecutableFusionCard[] = []
    let reason = support.reason
    if (support.applicable) {
      try {
        const verified = strategy.execute(strategyContext).filter(card => hasCompleteParentProof(card, parents))
        const rejectedRegistered = verified.filter(card =>
          capabilityOrigin(card.execution_certificate) === 'registered_parameterized_morphism' ||
          card.execution_certificate?.registered_composite_used === true)
        generated = verified.filter(card => !rejectedRegistered.includes(card))
        reason = generated.length
          ? 'typed construction, exact backend, and independent verification succeeded'
          : rejectedRegistered.length
            ? 'registered completed routes are replay artifacts and cannot count as autonomous generation'
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
  const cardOrigin = (card: ExecutableFusionCard) => capabilityOrigin(card.execution_certificate)
  const synthesizedCards = cards.filter(card => isRuntimeSynthesisCertificate(card.execution_certificate))
  state.synthesized_programs = synthesizedCards.map(card => ({
    id: `program.${createHash('sha256').update(JSON.stringify({
      parents: card.parent_ids,
      chain: card.morphism_chain,
      observable: card.structure_blueprint.observable,
    })).digest('hex').slice(0, 16)}`,
    input_parent_ids: [...card.parent_ids],
    output_sort: card.structure_blueprint.observable,
    morphism_chain: [...card.morphism_chain],
    backend_contracts: [...new Set(card.structure_blueprint.proofCertificate.map(step => step.verifier))],
    origin: cardOrigin(card)!,
    verified: true,
  }))
  state.reused_parameterized_morphisms = cards.filter(
    card => cardOrigin(card) === 'registered_parameterized_morphism',
  ).length
  state.primitive_executions = cards.filter(
    card => cardOrigin(card) === 'primitive_exact_operation' || cardOrigin(card) === 'verified_backend_execution',
  ).length
  const registeredFallbackIsStillRequired = cards.some(
    card => cardOrigin(card) === 'registered_parameterized_morphism',
  ) && synthesizedCards.length < requested && (state.execution_obligations?.length ?? 0) > 0
  state.continuing = cards.length < requested || registeredFallbackIsStillRequired
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
