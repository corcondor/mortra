import type { DiscoveryParent } from './parent-conditioned-discovery'
import type { ExecutableFusionCard } from './executable-fusion'
import {
  supportsPolynomialRootFusion,
  synthesizePolynomialRootFusions,
} from './polynomial-root-fusion'
import { synthesizeRuntimeExpressionProblems } from './runtime-expression-synthesizer'
import { synthesizeRuntimeLatticePickProblems } from './runtime-lattice-pick-generation'
import { synthesizeRuntimeLinearProblems } from './runtime-linear-problem-generation'
import { synthesizeRuntimePrimitiveRightTriangleProblems } from './runtime-primitive-right-triangle-generation'
import { synthesizeRuntimeQuadraticExpectationProblems } from './runtime-quadratic-expectation-generation'
import { synthesizeRuntimeRecurrenceCongruenceProblems } from './runtime-recurrence-congruence-generation'

export type RuntimeGenerationResult = {
  applicable: boolean
  reason: string
  cards: ExecutableFusionCard[]
  hypothesesEvaluated: number
}

export type RuntimeGenerationEngine = {
  id: string
  synthesize: (parents: DiscoveryParent[], requested: number) => RuntimeGenerationResult
}

const ENGINES: RuntimeGenerationEngine[] = [
  {
    id: 'runtime-polynomial-root-generation',
    synthesize: (parents, requested) => {
      const support = supportsPolynomialRootFusion(parents)
      const cards = support.applicable
        ? synthesizePolynomialRootFusions(parents, requested, 1)
        : []
      return {
        applicable: cards.length > 0,
        reason: cards.length ? `${cards.length} exact root-set problems synthesized` : support.reason,
        cards,
        hypothesesEvaluated: support.applicable ? 3 : 0,
      }
    },
  },
  { id: 'runtime-quadratic-expectation-generation', synthesize: synthesizeRuntimeQuadraticExpectationProblems },
  { id: 'runtime-recurrence-congruence-generation', synthesize: synthesizeRuntimeRecurrenceCongruenceProblems },
  { id: 'runtime-lattice-pick-generation', synthesize: synthesizeRuntimeLatticePickProblems },
  { id: 'runtime-primitive-right-triangle-generation', synthesize: synthesizeRuntimePrimitiveRightTriangleProblems },
  { id: 'runtime-linear-problem-generation', synthesize: synthesizeRuntimeLinearProblems },
]

const EXPRESSION_ENGINE: RuntimeGenerationEngine = {
  id: 'runtime-expression-grammar',
  synthesize: synthesizeRuntimeExpressionProblems,
}

/** One registry is shared by the product path and every generation experiment. */
export function runtimeGenerationEngines(options: { includeExpression?: boolean } = {}): RuntimeGenerationEngine[] {
  return options.includeExpression === false ? [...ENGINES] : [...ENGINES, EXPRESSION_ENGINE]
}
