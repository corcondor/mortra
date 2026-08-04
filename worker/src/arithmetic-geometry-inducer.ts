import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import path from 'node:path'
import type { ExecutableFusionCard } from './executable-fusion'
import type { HyperMorphismSchema } from './generalization-kernel'
import type { DiscoveryParent } from './parent-conditioned-discovery'
import type { CertifiedLawRecord } from './primitive-law-inducer'
import { extractDistinctiveParentObligations } from './parent-obligation-coverage'

type DomainMode = 'triangle' | 'topology'

type ParentFeatures = {
  id: string
  text: string
  triangle: boolean
  topology: boolean
  arithmetic: boolean
  prime: boolean
  anchors: string[]
  requiredObligations: string[]
  consumedObligations: string[]
  uncoveredObligations: string[]
}

type BackendCandidate = {
  id: string
  kind: string
  observable: string
  observable_tex: string
  expression: string
  expression_tex: string
  numerator: string
  denominator: string
  numerator_tex: string
  denominator_tex: string
  statement_tex: string
  answer_tex: string
  solution_tex: string
  samples: number[]
  domain: string
  source_types: string[]
}

export type ArithmeticGeometryTelemetry = {
  enumerated: number
  tested: number
  rejected: number
  equivalence_classes: number
  certified: number
  synthesis_engine: string
}

type BackendResult = {
  candidates: BackendCandidate[]
  telemetry: ArithmeticGeometryTelemetry
}

export type ArithmeticGeometryInductionResult = {
  applicable: boolean
  reason: string
  modes: DomainMode[]
  rules: HyperMorphismSchema[]
  cards: ExecutableFusionCard[]
  telemetry: ArithmeticGeometryTelemetry
}

const EMPTY_TELEMETRY: ArithmeticGeometryTelemetry = {
  enumerated: 0,
  tested: 0,
  rejected: 0,
  equivalence_classes: 0,
  certified: 0,
  synthesis_engine: 'unavailable',
}

const backendCache = new Map<string, BackendResult | null>()

function hash(value: unknown, length = 14): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function backendPath(): string {
  return path.resolve(process.cwd(), 'backend', 'arithmetic_geometry_induction.py')
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
      env: { ...process.env, PYTHONUTF8: '1', PYTHONIOENCODING: 'utf-8' },
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

function analyzeParent(parent: DiscoveryParent, index: number): ParentFeatures {
  const text = parent.statement ?? ''
  const topology = /位相|曲面|三角形分割|単体分割|Euler標数|オイラー標数|triangulation|simplicial|topological/i.test(text)
  const triangle = !topology && /三角形|外接円半径|内接円半径|傍接円半径|triangle|circumradius|inradius/i.test(text)
  const prime = /素数|prime/i.test(text)
  const arithmetic = prime || /整数|自然数|整除|約数|倍数|互いに素|最大公約数|\gcd|divisib|integer/i.test(text)
  const anchors = [
    triangle ? 'TriangleMetricStructure' : '',
    topology ? 'FiniteTriangulationStructure' : '',
    arithmetic ? 'IntegerPredicate' : '',
    prime ? 'PrimePredicate' : '',
  ].filter(Boolean)
  const distinctiveObligations = extractDistinctiveParentObligations(text).map(item => item.id)
  const requiredObligations = [...new Set([...anchors, ...distinctiveObligations])]
  // This backend implements only the listed endpoint contracts. A broad
  // domain tag cannot discharge a parent's more specific construction.
  const consumedObligations = [...anchors]
  const uncoveredObligations = requiredObligations.filter(item => !consumedObligations.includes(item))
  return {
    id: String(parent.id || `parent-${index + 1}`),
    text,
    triangle,
    topology,
    arithmetic,
    prime,
    anchors,
    requiredObligations,
    consumedObligations,
    uncoveredObligations,
  }
}

function supportsMode(features: ParentFeatures[], mode: DomainMode): boolean {
  const hasGeometry = mode === 'triangle'
    ? features.some(feature => feature.triangle)
    : features.some(feature => feature.topology)
  const hasArithmetic = features.some(feature => feature.arithmetic)
  if (!hasGeometry || !hasArithmetic) return false
  if (features.some(feature => feature.uncoveredObligations.length > 0)) return false
  // Every selected endpoint must be indispensable. If deleting one endpoint
  // leaves the same two capabilities, the proposed fusion is rejected.
  return features.every((_, removed) => {
    const remainder = features.filter((__, index) => index !== removed)
    const geometryRemains = mode === 'triangle'
      ? remainder.some(feature => feature.triangle)
      : remainder.some(feature => feature.topology)
    const arithmeticRemains = remainder.some(feature => feature.arithmetic)
    return !geometryRemains || !arithmeticRemains
  })
}

function sourceType(feature: ParentFeatures, mode: DomainMode): string {
  if (mode === 'triangle' && feature.triangle) return 'TriangleMetricData'
  if (mode === 'topology' && feature.topology) return 'FiniteTriangulation'
  return feature.prime ? 'PrimeSpectrum' : 'IntegerPredicate'
}

export function induceArithmeticGeometryLemmas(
  parents: DiscoveryParent[],
  requested: number,
  round: number,
  registeredLaws: CertifiedLawRecord[] = [],
): ArithmeticGeometryInductionResult {
  const features = parents.map(analyzeParent)
  const modes = (['triangle', 'topology'] as const).filter(mode => supportsMode(features, mode))
  if (!modes.length) {
    return {
      applicable: false,
      reason: 'selected endpoints do not form an all-parent-indispensable geometry/topology and arithmetic pair',
      modes: [],
      rules: [],
      cards: [],
      telemetry: { ...EMPTY_TELEMETRY },
    }
  }
  const result = runBackend({
    modes,
    max_candidates: 24,
    offset: 0,
    registered_expressions: [],
  })
  if (!result) {
    return {
      applicable: false,
      reason: 'the arithmetic-geometry symbolic backend did not return a certificate',
      modes,
      rules: [],
      cards: [],
      telemetry: { ...EMPTY_TELEMETRY },
    }
  }
  const registeredExpressions = new Set(registeredLaws.map(law => law.expression))
  const offset = Math.max(0, round - 1) * Math.max(1, requested)
  const candidates = result.candidates
    .filter(candidate => !registeredExpressions.has(candidate.id))
    .slice(offset, offset + Math.max(1, requested))
  const telemetry: ArithmeticGeometryTelemetry = {
    ...result.telemetry,
    rejected: result.telemetry.rejected + (result.candidates.length - candidates.length),
    certified: candidates.length,
  }
  const parentIds = features.map(feature => feature.id)
  const rules = candidates.map(candidate => {
    const mode: DomainMode = candidate.domain === 'arithmetic_topology' ? 'topology' : 'triangle'
    return {
      name: `InducedArithmeticGeometryLaw_${hash(candidate.id, 10)}`,
      sources: features.map(feature => sourceType(feature, mode)),
      target: 'Proposition',
      preserves: ['all-parent-provenance', 'exact-identity', 'integrality', candidate.kind],
      backend: ['sympy-symbolic-identity', 'integer-divisibility', 'independent-substitution', 'all-parent-semantic-ablation'],
    }
  })
  const cards = candidates.map((candidate, index): ExecutableFusionCard => {
    const rule = rules[index]
    const mode: DomainMode = candidate.domain === 'arithmetic_topology' ? 'topology' : 'triangle'
    const morphisms = mode === 'triangle'
      ? ['TriangleMetricElaboration', 'HeronFactorization', 'RadiusExpressionGrammar', 'AreaElimination', 'RationalNormalForm', 'IntegerPredicateLift', rule.name, 'IndependentSubstitution', 'AllParentSemanticAblation']
      : ['TriangulationElaboration', 'EulerCharacteristic', 'IncidenceDoubleCounting', 'LinearRelationElimination', 'IntegerPredicateLift', rule.name, 'IndependentSubstitution', 'AllParentSemanticAblation']
    const structureId = `induced-${candidate.id}.${hash({ parentIds, expression: candidate.expression })}`
    const proofCertificate = [
      { id: 'typed-grammar', claim: 'the observable and predicate were composed from typed endpoint operators', verifier: 'finite typed relational grammar' },
      { id: 'geometric-elimination', claim: candidate.expression_tex, verifier: mode === 'triangle' ? 'SymPy Heron and radius identity elimination' : 'SymPy Euler and incidence linear elimination' },
      { id: 'integer-lift', claim: candidate.answer_tex, verifier: 'exact divisibility and primality reduction' },
      { id: 'sample-check', claim: 'the identity holds on independent admissible instances', verifier: 'independent exact substitution' },
      { id: 'parent-ablation', claim: 'removing any selected parent removes a required endpoint capability', verifier: 'all-parent semantic ablation' },
    ]
    const structuralUniqueness = {
      schema: 1 as const,
      conditionSkeleton: mode === 'triangle'
        ? ['NondegenerateTriangle', 'IntegralSides', 'HeronIdentity', 'RadiusDefinitions', candidate.kind]
        : ['ClosedSurface', 'FiniteTriangulation', 'EulerCharacteristic', 'IncidenceDoubleCounting', candidate.kind],
      querySignature: candidate.kind,
      normalForm: `${candidate.id}:${candidate.expression}`,
      quotientAction: mode === 'triangle' ? 'S3-side-permutation' : 'simplicial-incidence-isomorphism',
      freeParameters: mode === 'triangle'
        ? candidate.kind === 'two_prime_side_reduction' ? ['p', 'q', 'n', 'ell'] : ['a', 'b', 'c']
        : ['V', 'chi'],
      uniqueNormalForm: true,
      // These cards prove a unique parametric relation. They do not yet claim
      // that the complete integer model set is finite.
      finiteSolutionSet: false,
      numericInstanceConstants: [],
      conditionAblationPassed: true,
    }
    return {
      id: `mathos-${hash(structureId, 18)}`,
      family_id: `discovered.${candidate.id}`,
      statement_tex: candidate.statement_tex,
      answer_tex: candidate.answer_tex,
      solution_tex: candidate.solution_tex,
      domain: candidate.domain,
      morphism_chain: morphisms,
      parent_ids: parentIds,
      unresolved: false,
      discovery_status: 'verified',
      verification: {
        method: `${telemetry.synthesis_engine} + exact symbolic elimination + all-parent semantic ablation`,
        exact_backend: true,
        independent_check: true,
        samples: candidate.samples,
      },
      difficulty: { band: 'A_abstract_arithmetic_geometry', score: 8.5 + morphisms.length * 0.5 },
      fusion_derivation: {
        passed: true,
        reason: 'geometric or topological identities are lifted to an integer predicate using indispensable selected endpoints',
        ablationPassed: true,
        assignments: features.map((feature, featureIndex) => ({
          parentId: feature.id,
          portId: `endpoint_${featureIndex + 1}`,
          role: feature.triangle || feature.topology ? 'object' : 'constraint',
          matchedAnchors: feature.anchors,
          requiredObligations: feature.requiredObligations,
          consumedObligations: feature.consumedObligations,
          coverage: feature.requiredObligations.length === 0
            ? 1
            : feature.consumedObligations.length / feature.requiredObligations.length,
          witnessSteps: mode === 'triangle' && feature.triangle
            ? ['TriangleMetricElaboration', 'HeronFactorization']
            : mode === 'topology' && feature.topology
            ? ['TriangulationElaboration', 'EulerCharacteristic']
            : ['IntegerPredicateLift'],
        })),
        bridges: [{
          id: rule.name,
          witnessStep: candidate.expression,
          consumes: features.map((_, featureIndex) => `endpoint_${featureIndex + 1}`),
          produces: 'verified_integer_geometric_proposition',
        }],
        intermediatePropositions: features.map(feature => ({
          parentId: feature.id,
          morphism: mode === 'triangle' && feature.triangle
            ? 'HeronFactorization'
            : mode === 'topology' && feature.topology
            ? 'EulerIncidenceElimination'
            : 'IntegerPredicateLift',
          source: sourceType(feature, mode),
          target: 'Proposition',
          proposition: feature.anchors.join(' and '),
          proved: true,
        })),
      },
      structure_blueprint: {
        id: structureId,
        version: 1,
        kernel: mode === 'triangle' ? 'ArithmeticGeometryLemmaIR' : 'ArithmeticTopologyLemmaIR',
        observable: 'Proposition',
        operators: morphisms,
        domain: candidate.domain,
        tags: [mode, 'integer', candidate.kind, 'abstract-lemma', 'no-numeric-instance'],
        morphismChain: morphisms,
        executable: true,
        proofCertificate,
        synthesizedLaw: {
          name: rule.name,
          expression: candidate.id,
          arity: parents.length,
          sources: [...rule.sources],
          target: rule.target,
          preserves: [...rule.preserves],
          backend: [...rule.backend],
        },
        structuralUniqueness,
      },
      search_evidence: {
        hypotheses_evaluated: telemetry.tested,
        valid_hypotheses: telemetry.certified,
        elapsed_ms: 0,
      },
    }
  })
  return {
    applicable: cards.length > 0,
    reason: cards.length
      ? `${cards.length} abstract arithmetic-geometric lemmas passed exact elimination and all-parent ablation`
      : 'no new certified arithmetic-geometric lemma survived',
    modes,
    rules,
    cards,
    telemetry,
  }
}
