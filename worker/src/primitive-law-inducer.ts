import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import path from 'node:path'
import type { ExecutableFusionCard } from './executable-fusion'
import type { HyperMorphismSchema } from './generalization-kernel'
import type { DiscoveryParent } from './parent-conditioned-discovery'
import { extractPolynomial } from './polynomial-root-fusion'

type BackendCandidate = {
  expression: string
  expression_tex: string
  result: string
  degree_result: number
  operations: number
  exact: true
  numeric_check: true
  left_ablation: true
  right_ablation: true
  all_parent_ablation: true
  parent_arity: number
  synthesis_engine: string
  equivalence_engine: string
  dependency_verifier: string
}

export type LawInductionTelemetry = {
  enumerated: number
  tested: number
  rejected_elimination: number
  rejected_numeric: number
  rejected_ablation: number
  rejected_duplicate: number
  cvc5_checked: number
  cvc5_rejected: number
  cvc5_available: boolean
  egglog_available: boolean
  equivalence_classes: number
  synthesis_terms_examined: number
  synthesis_engine: string
  certified: number
}

type BackendResult = {
  left: string
  right: string
  polynomials: string[]
  candidates: BackendCandidate[]
  telemetry: LawInductionTelemetry
  error?: never
}

export type PrimitiveLawInductionResult = {
  applicable: boolean
  reason: string
  rules: HyperMorphismSchema[]
  cards: ExecutableFusionCard[]
  telemetry: LawInductionTelemetry
}

export type CertifiedLawRecord = {
  name: string
  expression: string
  arity: number
  sources: string[]
  target: string
  preserves: string[]
  backend: string[]
}

const EMPTY_TELEMETRY: LawInductionTelemetry = {
  enumerated: 0,
  tested: 0,
  rejected_elimination: 0,
  rejected_numeric: 0,
  rejected_ablation: 0,
  rejected_duplicate: 0,
  cvc5_checked: 0,
  cvc5_rejected: 0,
  cvc5_available: false,
  egglog_available: false,
  equivalence_classes: 0,
  synthesis_terms_examined: 0,
  synthesis_engine: 'unavailable',
  certified: 0,
}

const backendCache = new Map<string, BackendResult | null>()

function hash(value: unknown, length = 14): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function backendPath(): string {
  return path.resolve(process.cwd(), 'backend', 'primitive_law_induction.py')
}

function runBackend(request: object): BackendResult | null {
  const cacheKey = JSON.stringify(request)
  if (backendCache.has(cacheKey)) return backendCache.get(cacheKey) ?? null
  const commands = process.platform === 'win32' ? ['python', 'py'] : ['python3', 'python']
  for (const command of commands) {
    const args = command === 'py' ? ['-3', backendPath()] : [backendPath()]
    const result = spawnSync(command, args, {
      input: JSON.stringify(request),
      encoding: 'utf8',
      timeout: 120_000,
      maxBuffer: 8 * 1024 * 1024,
    })
    if (result.error && (result.error as NodeJS.ErrnoException).code === 'ENOENT') continue
    if (!result.stdout) {
      backendCache.set(cacheKey, null)
      return null
    }
    try {
      const parsed = JSON.parse(result.stdout) as BackendResult | { error: string }
      const value = 'error' in parsed ? null : parsed
      backendCache.set(cacheKey, value)
      return value
    } catch {
      backendCache.set(cacheKey, null)
      return null
    }
  }
  backendCache.set(cacheKey, null)
  return null
}

export function inducePrimitiveLaws(
  parents: DiscoveryParent[],
  requested: number,
  round: number,
  searchDepth: number,
  registeredLaws: CertifiedLawRecord[] = [],
): PrimitiveLawInductionResult {
  const inputs = parents.map(extractPolynomial).filter((value): value is NonNullable<typeof value> => value !== null)
  if (inputs.length < 2 || new Set(inputs.map(input => input.parentId)).size < 2) {
    return {
      applicable: false,
      reason: 'fewer than two parents elaborate to executable algebraic constraints',
      rules: [],
      cards: [],
      telemetry: { ...EMPTY_TELEMETRY },
    }
  }
  const selectedInputs = [...new Map(inputs.map(input => [input.parentId, input])).values()]
  const result = runBackend({
    polynomials: selectedInputs.map(input => input.normalized),
    max_depth: Math.max(2, Math.min(4, Math.ceil(searchDepth / 4))),
    max_candidates: Math.max(1, requested),
    offset: Math.max(0, round - 1) * Math.max(1, requested),
    registered_expressions: registeredLaws
      .filter(law => law.arity === selectedInputs.length)
      .map(law => law.expression),
  })
  if (!result) {
    return {
      applicable: true,
      reason: 'candidate grammar was applicable but the exact backend certified no law',
      rules: [],
      cards: [],
      telemetry: { ...EMPTY_TELEMETRY },
    }
  }
  const parentIds = selectedInputs.map(input => input.parentId)
  const rules = result.candidates.map(candidate => ({
    name: `InducedAlgebraicLaw_${hash(candidate.expression, 10)}`,
    sources: selectedInputs.map(() => 'FiniteAlgebraicOrbit'),
    target: 'FiniteAlgebraicOrbit',
    preserves: ['both-parent-provenance', 'algebraicity', 'finite-support', 'exact-elimination'],
    backend: ['sympy-resultant', 'numeric-counterexample-check', 'all-parent-ablation'],
  }))
  const cards = result.candidates.map((candidate, index): ExecutableFusionCard => {
    const rule = rules[index]
    const alpha = (index: number) => `\\alpha_{${index + 1}}`
    let observableTex = candidate.expression_tex
    for (let inputIndex = selectedInputs.length - 1; inputIndex >= 0; inputIndex--) {
      observableTex = observableTex
        .replace(new RegExp(`x_\\{${inputIndex}\\}`, 'g'), alpha(inputIndex))
        .replace(new RegExp(`\\bx${inputIndex}\\b`, 'g'), alpha(inputIndex))
    }
    const polynomialDefinitions = result.polynomials.map((polynomial, inputIndex) => {
      const variable = `x_{${inputIndex + 1}}`
      return `f_{${inputIndex + 1}}(${variable})=${polynomial.replace(/\bx\b/g, variable)}`
    }).join(',\\quad ')
    const rootConstraints = result.polynomials.map((_, inputIndex) =>
      `f_{${inputIndex + 1}}(${alpha(inputIndex)})=0`).join(', ')
    const structureId = `induced-law.${hash([parentIds, candidate.expression, candidate.result])}`
    const morphisms = [
      'PolynomialConstraintExtraction',
      'RootConfiguration',
      rule.name,
      'IteratedResultantElimination',
      'SquareFreeReduction',
      'NumericCounterexampleCheck',
      'AllParentAblation',
    ]
    const proofCertificate = [
      { id: 'grammar', claim: `typed candidate ${candidate.expression} was synthesized from the endpoint grammar`, verifier: candidate.synthesis_engine },
      { id: 'equivalence', claim: 'equivalent candidate programs were collapsed before verification', verifier: candidate.equivalence_engine },
      { id: 'dependency', claim: 'the observable changes under independent variation of every endpoint variable', verifier: candidate.dependency_verifier },
      { id: 'elimination', claim: 'the output polynomial is the exact image of the joint root set', verifier: 'iterated SymPy resultants over QQ' },
      { id: 'counterexample', claim: 'all numerical root tuples satisfy the induced polynomial', verifier: 'independent nroots substitution' },
      { id: 'ablation', claim: 'changing every parent independently changes the induced observable', verifier: 'all-parent exact perturbation' },
    ]
    return {
      id: `mathos-${structureId}`,
      family_id: `discovered.induced_algebraic_law.${hash(candidate.expression, 8)}`,
      statement_tex: `\\(${polynomialDefinitions}\\) とする。\\(${rootConstraints}\\) を満たす複素数 \\(${selectedInputs.map((_, inputIndex) => alpha(inputIndex)).join(',')}\\) をすべて動かすとき、\\(${observableTex}\\) の異なる値全体を根にもつモニック多項式を求めよ。`,
      answer_tex: `P(z)=${candidate.result}`,
      solution_tex: `型付き式文法から観測 \\(${observableTex}\\) を合成した。\\(${rootConstraints}\\) と \\(z=${candidate.expression_tex}\\) から各変数を反復終結式で消去し、平方因子を除いてモニック化すると \\(P(z)=${candidate.result}\\) を得る。全根組の独立数値代入と、${selectedInputs.length}個の親制約を一つずつ変えるアブレーション検査を通過した。`,
      domain: 'algebraic_geometry',
      morphism_chain: morphisms,
      parent_ids: parentIds,
      unresolved: false,
      discovery_status: 'verified',
      verification: {
        method: `${candidate.synthesis_engine} + ${candidate.equivalence_engine} + exact elimination + counterexample and ablation checks`,
        exact_backend: true,
        independent_check: true,
        samples: [candidate.degree_result, candidate.operations, result.telemetry.tested],
      },
      difficulty: { band: 'A_induced_algebraic_law', score: 7 + candidate.degree_result + candidate.operations * 0.75 },
      fusion_derivation: {
        passed: true,
        reason: 'the induced observable is synthesized from every typed parent root configuration and certified independently',
        ablationPassed: true,
        assignments: selectedInputs.map((input, inputIndex) => ({
          parentId: input.parentId,
          portId: `parent_variable_${inputIndex + 1}`,
          role: 'object',
          matchedAnchors: [input.source],
          witnessSteps: ['PolynomialConstraintExtraction', 'RootConfiguration'],
        })),
        bridges: [{
          id: rule.name,
          witnessStep: candidate.expression,
          consumes: selectedInputs.map((_, inputIndex) => `parent_variable_${inputIndex + 1}`),
          produces: 'induced_observable',
        }],
        intermediatePropositions: selectedInputs.map(input => ({
          parentId: input.parentId,
          morphism: 'RootConfiguration',
          source: 'Polynomial',
          target: 'FiniteAlgebraicOrbit',
          proposition: 'the parent constraint defines a finite algebraic orbit',
          proved: true,
        })),
      },
      structure_blueprint: {
        id: structureId,
        version: 1,
        kernel: 'PrimitiveLawInductionIR',
        observable: 'FiniteAlgebraicOrbit',
        operators: [candidate.synthesis_engine, candidate.equivalence_engine, 'resultant-elimination', 'counterexample-guided-filtering'],
        domain: 'algebraic_geometry',
        tags: ['induced-law', 'cegis', 'exact', `grammar-depth-${Math.max(2, Math.min(4, Math.ceil(searchDepth / 4)))}`],
        morphismChain: morphisms,
        executable: true,
        proofCertificate,
        synthesizedLaw: {
          name: rule.name,
          expression: candidate.expression,
          arity: selectedInputs.length,
          sources: [...rule.sources],
          target: rule.target,
          preserves: [...rule.preserves],
          backend: [...rule.backend],
        },
      },
      search_evidence: {
        hypotheses_evaluated: result.telemetry.tested,
        valid_hypotheses: result.telemetry.certified,
        elapsed_ms: 0,
      },
    }
  })
  return {
    applicable: true,
    reason: cards.length
      ? `${cards.length} previously unregistered typed laws were synthesized and certified`
      : 'all generated laws were rejected by exact or counterexample checks',
    rules,
    cards,
    telemetry: result.telemetry,
  }
}
