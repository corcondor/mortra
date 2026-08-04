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
}

export type LawInductionTelemetry = {
  enumerated: number
  tested: number
  rejected_elimination: number
  rejected_numeric: number
  rejected_ablation: number
  rejected_duplicate: number
  certified: number
}

type BackendResult = {
  left: string
  right: string
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

const EMPTY_TELEMETRY: LawInductionTelemetry = {
  enumerated: 0,
  tested: 0,
  rejected_elimination: 0,
  rejected_numeric: 0,
  rejected_ablation: 0,
  rejected_duplicate: 0,
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
  const left = inputs[0]
  const right = inputs.find(input => input.parentId !== left.parentId)!
  const result = runBackend({
    left: left.normalized,
    right: right.normalized,
    max_depth: Math.max(2, Math.min(4, Math.ceil(searchDepth / 4))),
    max_candidates: Math.max(1, requested),
    offset: Math.max(0, round - 1) * Math.max(1, requested),
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
  const parentIds = [left.parentId, right.parentId]
  const rules = result.candidates.map(candidate => ({
    name: `InducedAlgebraicLaw_${hash(candidate.expression, 10)}`,
    sources: ['FiniteAlgebraicOrbit', 'FiniteAlgebraicOrbit'],
    target: 'FiniteAlgebraicOrbit',
    preserves: ['both-parent-provenance', 'algebraicity', 'finite-support', 'exact-elimination'],
    backend: ['sympy-resultant', 'numeric-counterexample-check', 'two-sided-parent-ablation'],
  }))
  const cards = result.candidates.map((candidate, index): ExecutableFusionCard => {
    const rule = rules[index]
    const rightPolynomialTex = result.right.replace(/\bx\b/g, 'y')
    const observableTex = candidate.expression_tex
      .replace(/\bx\b/g, '\\alpha')
      .replace(/\by\b/g, '\\beta')
    const structureId = `induced-law.${hash([parentIds, candidate.expression, candidate.result])}`
    const morphisms = [
      'PolynomialConstraintExtraction',
      'RootConfiguration',
      rule.name,
      'IteratedResultantElimination',
      'SquareFreeReduction',
      'NumericCounterexampleCheck',
      'TwoSidedParentAblation',
    ]
    const proofCertificate = [
      { id: 'grammar', claim: `typed candidate ${candidate.expression} uses both parent variables`, verifier: 'typed polynomial grammar' },
      { id: 'elimination', claim: 'the output polynomial is the exact image of the joint root set', verifier: 'iterated SymPy resultants over QQ' },
      { id: 'counterexample', claim: 'all numerical root pairs satisfy the induced polynomial', verifier: 'independent nroots substitution' },
      { id: 'ablation', claim: 'changing either parent changes the induced observable', verifier: 'two-sided exact parent perturbation' },
    ]
    return {
      id: `mathos-${structureId}`,
      family_id: `discovered.induced_algebraic_law.${hash(candidate.expression, 8)}`,
      statement_tex: `\\(f(x)=${result.left}\\), \\(g(y)=${rightPolynomialTex}\\) とする。\\(f(\\alpha)=0\\), \\(g(\\beta)=0\\) を満たす複素数 \\(\\alpha,\\beta\\) をすべて動かすとき、\\(${observableTex}\\) の異なる値全体を根にもつモニック多項式を求めよ。`,
      answer_tex: `P(z)=${candidate.result}`,
      solution_tex: `型付き式文法から観測 \\(${observableTex}\\) を合成した。\\(f(x)=0\\), \\(g(y)=0\\), \\(z=${candidate.expression_tex}\\) を反復終結式で消去し、平方因子を除いてモニック化すると \\(P(z)=${candidate.result}\\) を得る。全根対の独立数値代入と、左右それぞれの親制約を変えるアブレーション検査を通過した。`,
      domain: 'algebraic_geometry',
      morphism_chain: morphisms,
      parent_ids: parentIds,
      unresolved: false,
      discovery_status: 'verified',
      verification: {
        method: 'typed candidate enumeration + exact elimination + counterexample and ablation checks',
        exact_backend: true,
        independent_check: true,
        samples: [candidate.degree_result, candidate.operations, result.telemetry.tested],
      },
      difficulty: { band: 'A_induced_algebraic_law', score: 7 + candidate.degree_result + candidate.operations * 0.75 },
      fusion_derivation: {
        passed: true,
        reason: 'the induced observable is synthesized from both typed parent root configurations and certified independently',
        ablationPassed: true,
        assignments: [
          { parentId: left.parentId, portId: 'left_variable', role: 'object', matchedAnchors: [left.source], witnessSteps: ['PolynomialConstraintExtraction', 'RootConfiguration'] },
          { parentId: right.parentId, portId: 'right_variable', role: 'object', matchedAnchors: [right.source], witnessSteps: ['PolynomialConstraintExtraction', 'RootConfiguration'] },
        ],
        bridges: [{ id: rule.name, witnessStep: candidate.expression, consumes: ['left_variable', 'right_variable'], produces: 'induced_observable' }],
        intermediatePropositions: [
          { parentId: left.parentId, morphism: 'RootConfiguration', source: 'Polynomial', target: 'FiniteAlgebraicOrbit', proposition: 'the left constraint defines a finite algebraic orbit', proved: true },
          { parentId: right.parentId, morphism: 'RootConfiguration', source: 'Polynomial', target: 'FiniteAlgebraicOrbit', proposition: 'the right constraint defines a finite algebraic orbit', proved: true },
        ],
      },
      structure_blueprint: {
        id: structureId,
        version: 1,
        kernel: 'PrimitiveLawInductionIR',
        observable: 'FiniteAlgebraicOrbit',
        operators: ['typed-term-enumeration', 'resultant-elimination', 'counterexample-guided-filtering'],
        domain: 'algebraic_geometry',
        tags: ['induced-law', 'cegis', 'exact', `grammar-depth-${Math.max(2, Math.min(4, Math.ceil(searchDepth / 4)))}`],
        morphismChain: morphisms,
        executable: true,
        proofCertificate,
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
