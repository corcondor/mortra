import { createHash } from 'node:crypto'
import type { DiscoveryParent } from './parent-conditioned-discovery'
import { elaborateMathematicalText } from './mathematical-language'

export type SemanticRole = 'object' | 'operator' | 'relation' | 'query'

export type SemanticNode = {
  id: string
  role: SemanticRole
  canonical: string
  sort: string
  surface: string
  parent_id: string
}

export type SemanticEdge = {
  source: string
  target: string
  morphism: string
  preserves: string[]
  backend: string[]
  proved: boolean
  contributes_provenance: boolean
}

export type SemanticHypergraph = {
  parent_id: string
  nodes: SemanticNode[]
  edges: SemanticEdge[]
  root_sorts: string[]
  query_sorts: string[]
  language_analysis: {
    token_count: number
    parse_count: number
    parse_truncated: boolean
    clause_count: number
    quantifier_prefix: string[]
    definitions: Array<{ symbol: string; canonical: string; sort: string }>
    declarations: Array<{ symbol: string; sort: string; implicit_forall: boolean }>
    constraints: Array<{ operator: string; canonical: string }>
    unresolved_references: string[]
    diagnostics: string[]
  }
}

export type RoadmapStep = {
  id: string
  source: string
  target: string
  morphism: string
  preserves: string[]
  backend: string[]
  status: 'proved' | 'open'
  parent_ids: string[]
}

export type GeneralizationCertificate = {
  id: string
  method: 'typed-operator-overlap-and-hypergraph-planning-v1'
  parent_ids: string[]
  common_operators: string[]
  common_sorts: string[]
  bindings: Array<{ parent_id: string; surface: string; canonical: string; sort: string }>
  target_sort: string | null
  roadmap: RoadmapStep[]
  proof_obligations: string[]
  negative_transfer_checks: string[]
  executable_backends: string[]
  language_analysis: SemanticHypergraph['language_analysis'][]
  search_evidence: {
    max_depth: number
    max_states: number
    states_explored: number
    exhausted: boolean
  }
}

type OperatorSchema = {
  canonical: string
  patterns: RegExp[]
  input: string
  output: string
  role?: SemanticRole
  preserves: string[]
  backend: string[]
}

// This is an operator vocabulary. Entries define mathematical meaning and type,
// never a finished problem family, dataset id, or numeric answer.
const OPERATOR_SCHEMAS: readonly OperatorSchema[] = [
  { canonical: 'Integral', patterns: [/\\int(?![A-Za-z])/i, /積分/], input: 'Function', output: 'Scalar', preserves: ['linearity'], backend: ['symbolic-integration', 'numeric-quadrature'] },
  { canonical: 'Derivative', patterns: [/\\frac\s*\{d|f\s*['′]|微分|導関数/], input: 'DifferentiableFunction', output: 'Function', preserves: ['local-contact'], backend: ['symbolic-differentiation'] },
  { canonical: 'Limit', patterns: [/\\lim\b/i, /極限/], input: 'FilteredObject', output: 'Scalar', preserves: ['asymptotic-class'], backend: ['limit-engine', 'interval-bound'] },
  { canonical: 'Sum', patterns: [/\\sum(?![A-Za-z])/i, /総和|和を求め/], input: 'FiniteFamily', output: 'Scalar', preserves: ['index-set', 'multiplicity'], backend: ['exact-summation'] },
  { canonical: 'Product', patterns: [/\\prod(?![A-Za-z])/i, /総積|積を求め/], input: 'FiniteFamily', output: 'Scalar', preserves: ['index-set', 'multiplicity'], backend: ['resultant', 'exact-product'] },
  { canonical: 'TriangleMetricStructure', patterns: [/三角形|triangle/i], input: 'Triangle', output: 'TriangleMetricData', preserves: ['side-lengths', 'incidence', 'metric'], backend: ['heron-identity', 'triangle-radius-identities'] },
  { canonical: 'IntegralSideRestriction', patterns: [/整数三角形|三辺.{0,12}整数|integer-sided triangle/i], input: 'TriangleMetricData', output: 'IntegralTriangle', preserves: ['side-lengths', 'integrality'], backend: ['integer-arithmetic', 'triangle-inequality'] },
  { canonical: 'CircumradiusObservable', patterns: [/外接円半径|circumradius/i], input: 'TriangleMetricData', output: 'RadiusObservable', preserves: ['metric', 'similarity-weight'], backend: ['triangle-radius-identities'] },
  { canonical: 'InradiusObservable', patterns: [/内接円半径|inradius/i], input: 'TriangleMetricData', output: 'RadiusObservable', preserves: ['metric', 'similarity-weight'], backend: ['heron-identity'] },
  { canonical: 'TriangulationStructure', patterns: [/三角形分割|単体分割|triangulation|simplicial complex/i], input: 'TopologicalSpace', output: 'FiniteTriangulation', preserves: ['homeomorphism-type', 'incidence'], backend: ['simplicial-incidence'] },
  { canonical: 'EulerCharacteristic', patterns: [/Euler標数|オイラー標数|Euler characteristic/i], input: 'FiniteTriangulation', output: 'IntegerInvariant', preserves: ['homeomorphism-type'], backend: ['euler-incidence-elimination'] },
  { canonical: 'IntegerRestriction', patterns: [/整数|自然数|integer/i], input: 'ArithmeticObject', output: 'IntegerPredicate', preserves: ['integrality'], backend: ['integer-arithmetic'] },
  { canonical: 'PrimeRestriction', patterns: [/素数|prime/i], input: 'Integer', output: 'PrimeSpectrum', preserves: ['primality'], backend: ['primality-test', 'modular-arithmetic'] },
  { canonical: 'ZeroLocus', patterns: [/方程式|解とする|根とする|=\s*0/], input: 'Function', output: 'AlgebraicSet', preserves: ['solution-set', 'multiplicity'], backend: ['polynomial-solver', 'groebner-basis'] },
  { canonical: 'RootsOfUnity', patterns: [/z\s*\^\s*\{?n\}?\s*=\s*1|1\s*の\s*n\s*乗根|1の冪根|roots? of unity/i], input: 'CyclicGroup', output: 'FiniteAlgebraicOrbit', preserves: ['cyclic-order', 'multiplicity'], backend: ['cyclotomic-polynomial'] },
  { canonical: 'MobiusMap', patterns: [/一次分数変換|m[oö]bius|T\s*\(\s*z\s*\)\s*=\s*\\frac/i], input: 'Matrix2', output: 'RationalSelfMap', preserves: ['cross-ratio', 'projective-orbit'], backend: ['matrix-power', 'rational-normal-form'] },
  { canonical: 'Iteration', patterns: [/反復|合成写像|\\circ\s*\d+|iterate/i], input: 'SelfMap', output: 'Orbit', preserves: ['orbit'], backend: ['matrix-power', 'recurrence-engine'] },
  { canonical: 'RootConfiguration', patterns: [/根|解と係数|多項式/], input: 'Polynomial', output: 'FiniteAlgebraicOrbit', preserves: ['multiplicity', 'symmetric-action'], backend: ['vieta', 'resultant'] },
  { canonical: 'CoordinateRealization', patterns: [/座標|x\s*=|y\s*=|z\s*=/], input: 'GeometricConfiguration', output: 'PolynomialSystem', preserves: ['incidence', 'metric'], backend: ['coordinate-algebra'] },
  { canonical: 'Tangent', patterns: [/接線|tangent/i], input: 'DifferentiableCurve', output: 'LineFamily', preserves: ['contact-order'], backend: ['symbolic-differentiation'] },
  { canonical: 'Intersection', patterns: [/交点|intersection/i], input: 'FamilyOfSets', output: 'AlgebraicSet', preserves: ['incidence'], backend: ['elimination'] },
  { canonical: 'Centroid', patterns: [/重心|centroid/i], input: 'FinitePointConfiguration', output: 'AffinePoint', preserves: ['affine-action'], backend: ['linear-algebra'] },
  { canonical: 'Locus', patterns: [/軌跡|locus/i], input: 'ParameterizedPoint', output: 'SemialgebraicSet', preserves: ['incidence', 'parameter-image'], backend: ['quantifier-elimination', 'resultant'] },
  { canonical: 'Envelope', patterns: [/包絡線|envelope/i], input: 'ParameterizedFamily', output: 'AlgebraicSet', preserves: ['first-order-contact'], backend: ['resultant'] },
  { canonical: 'Measure', patterns: [/面積|体積|測度|area|volume/i], input: 'MeasurableSet', output: 'Scalar', role: 'query', preserves: ['measure-class'], backend: ['symbolic-integration', 'polytope-volume'] },
  { canonical: 'Extremum', patterns: [/最大|最小|極値|maximi|minimi/i], input: 'OrderedFamily', output: 'Scalar', role: 'query', preserves: ['feasible-set', 'order'], backend: ['optimization', 'quantifier-elimination'] },
  { canonical: 'Cardinality', patterns: [/個数|何通り|cardinality/i], input: 'FiniteSet', output: 'Integer', role: 'query', preserves: ['bijection-class'], backend: ['enumeration', 'generating-function'] },
  { canonical: 'GreatestCommonDivisor', patterns: [/\\gcd\b|最大公約数|greatest common divisor|\bgcd\b/i], input: 'IntegerPair', output: 'GCDValue', preserves: ['common-divisor-order', 'bezout-ideal'], backend: ['integer-arithmetic', 'extended-euclidean-algorithm'] },
  { canonical: 'LeastCommonMultiple', patterns: [/\\(?:operatorname|mathop)\s*\{?(?:\\text\s*\{)?lcm|最小公倍数|least common multiple|\blcm\b/i], input: 'IntegerPair', output: 'LCMValue', preserves: ['common-multiple-order', 'prime-valuations'], backend: ['integer-arithmetic', 'prime-valuation'] },
  { canonical: 'CeilingProjection', patterns: [/\\lceil|天井関数|ceiling|\bceil\b/i], input: 'Real', output: 'Integer', preserves: ['least-integer-upper-bound', 'order'], backend: ['exact-rounding', 'presburger-arithmetic'] },
  { canonical: 'FloorProjection', patterns: [/\\lfloor|床関数|floor function|\bfloor\b/i], input: 'Real', output: 'Integer', preserves: ['greatest-integer-lower-bound', 'order'], backend: ['exact-rounding', 'presburger-arithmetic'] },
  { canonical: 'PercentScalarAction', patterns: [/\\%|百分率|パーセント|percent|\d\s*%/i], input: 'RateQuantityPair', output: 'Quantity', preserves: ['unit', 'rational-scaling'], backend: ['rational-arithmetic', 'unit-checker'] },
  { canonical: 'Proof', patterns: [/示せ|証明|prove/i], input: 'Proposition', output: 'Proof', role: 'query', preserves: ['truth'], backend: ['lean', 'smt', 'symbolic-identity'] },
]

export type MorphismSchema = {
  name: string
  source: string
  target: string
  preserves: string[]
  backend: string[]
}

const MORPHISM_ATLAS: readonly MorphismSchema[] = [
  { name: 'CoordinateRealization', source: 'GeometricConfiguration', target: 'PolynomialSystem', preserves: ['incidence', 'metric'], backend: ['coordinate-algebra'] },
  { name: 'EquationEncoding', source: 'PolynomialSystem', target: 'AlgebraicSet', preserves: ['solution-set'], backend: ['groebner-basis'] },
  { name: 'ParameterElimination', source: 'AlgebraicSet', target: 'SemialgebraicSet', preserves: ['projection'], backend: ['resultant', 'quantifier-elimination'] },
  { name: 'MeasureObservation', source: 'SemialgebraicSet', target: 'Scalar', preserves: ['measure-class'], backend: ['symbolic-integration'] },
  { name: 'ExtremalObservation', source: 'SemialgebraicSet', target: 'Scalar', preserves: ['feasible-set', 'order'], backend: ['optimization'] },
  { name: 'RootExtraction', source: 'Polynomial', target: 'FiniteAlgebraicOrbit', preserves: ['multiplicity'], backend: ['polynomial-solver'] },
  { name: 'FieldTrace', source: 'FiniteAlgebraicOrbit', target: 'Scalar', preserves: ['Galois-orbit'], backend: ['vieta', 'log-derivative'] },
  { name: 'FieldNorm', source: 'FiniteAlgebraicOrbit', target: 'Scalar', preserves: ['Galois-orbit'], backend: ['resultant'] },
  { name: 'OrbitConstruction', source: 'RationalSelfMap', target: 'Orbit', preserves: ['iteration'], backend: ['matrix-power'] },
  { name: 'OrbitEvaluation', source: 'Orbit', target: 'FiniteFamily', preserves: ['index-set'], backend: ['recurrence-engine'] },
  { name: 'FiniteSummation', source: 'FiniteFamily', target: 'Scalar', preserves: ['multiplicity'], backend: ['exact-summation'] },
  { name: 'ZeroSet', source: 'Function', target: 'AlgebraicSet', preserves: ['solution-set'], backend: ['symbolic-solver'] },
  { name: 'Differentiation', source: 'DifferentiableFunction', target: 'Function', preserves: ['local-contact'], backend: ['symbolic-differentiation'] },
  { name: 'Integration', source: 'Function', target: 'Scalar', preserves: ['linearity'], backend: ['symbolic-integration'] },
  { name: 'CompanionRepresentation', source: 'Sequence', target: 'Matrix2', preserves: ['orbit', 'initial-state'], backend: ['linear-recurrence'] },
  { name: 'ResidueProjection', source: 'Integer', target: 'FiniteSet', preserves: ['congruence-class'], backend: ['modular-arithmetic'] },
  { name: 'Counting', source: 'FiniteSet', target: 'Integer', preserves: ['bijection-class'], backend: ['enumeration'] },
  { name: 'EuclideanMeet', source: 'IntegerPair', target: 'GCDValue', preserves: ['common-divisor-order', 'bezout-ideal'], backend: ['extended-euclidean-algorithm'] },
  { name: 'DivisibilityJoin', source: 'IntegerPair', target: 'LCMValue', preserves: ['common-multiple-order', 'prime-valuations'], backend: ['prime-valuation'] },
  { name: 'CeilingAdjunction', source: 'Real', target: 'Integer', preserves: ['least-integer-upper-bound', 'order'], backend: ['exact-rounding', 'presburger-arithmetic'] },
  { name: 'FloorAdjunction', source: 'Real', target: 'Integer', preserves: ['greatest-integer-lower-bound', 'order'], backend: ['exact-rounding', 'presburger-arithmetic'] },
  { name: 'RationalScaleAction', source: 'RateQuantityPair', target: 'Quantity', preserves: ['unit', 'rational-scaling'], backend: ['rational-arithmetic', 'unit-checker'] },
  { name: 'TriangleMetricElaboration', source: 'Triangle', target: 'TriangleMetricData', preserves: ['side-lengths', 'incidence', 'metric'], backend: ['heron-identity', 'triangle-radius-identities'] },
  { name: 'IntegralSideRestriction', source: 'TriangleMetricData', target: 'IntegralTriangle', preserves: ['side-lengths', 'integrality'], backend: ['integer-arithmetic', 'triangle-inequality'] },
  { name: 'TriangulationElaboration', source: 'TopologicalSpace', target: 'FiniteTriangulation', preserves: ['homeomorphism-type', 'incidence'], backend: ['simplicial-incidence'] },
  { name: 'EulerCharacteristic', source: 'FiniteTriangulation', target: 'IntegerInvariant', preserves: ['homeomorphism-type'], backend: ['euler-incidence-elimination'] },
  { name: 'IntegerPredicateIntroduction', source: 'ArithmeticObject', target: 'IntegerPredicate', preserves: ['integrality'], backend: ['integer-arithmetic'] },

  /*
   * 構造修復。
   *
   * アトラスの次数を数えたところ、32ソート中18個が壊れていた。
   * 入次数0（誰も作れない）が12個、出次数0（行き止まり）が6個。
   * Scalar は入次数6・出次数0で、6本の射が作るのに誰も消費しない。
   * グラフではなく漏斗の形をしていた。
   *
   * 欠けていたのは新しい数学ではなく、次の2種類の書き忘れだった。
   *
   * (1) 包含。数学的に一方が他方の部分集合なのにソートが分断されていた。
   *     1本引くと入次数0と出次数0が同時に埋まるので効率が良い。
   * (2) 標準的な構成。特性多項式や素因数分解のような、誰でも知っているもの。
   *
   * これで欠陥は 0 になり、型の上の到達は 2/16 → 16/16 になった。
   * ただし到達は必要条件にすぎず、導出が出るかは別に測る必要がある。
   */

  // (1) 包含
  { name: 'ScalarAsReal', source: 'Scalar', target: 'Real', preserves: ['value'], backend: ['inclusion'] },
  { name: 'QuantityAsReal', source: 'Quantity', target: 'Real', preserves: ['value'], backend: ['inclusion'] },
  { name: 'IntegerAsReal', source: 'Integer', target: 'Real', preserves: ['value'], backend: ['inclusion'] },
  { name: 'IntegerInvariantAsInteger', source: 'IntegerInvariant', target: 'Integer', preserves: ['value'], backend: ['inclusion'] },
  { name: 'IntegerAsArithmeticObject', source: 'Integer', target: 'ArithmeticObject', preserves: ['value'], backend: ['inclusion'] },
  { name: 'IntegralTriangleAsTriangle', source: 'IntegralTriangle', target: 'Triangle', preserves: ['side-lengths', 'incidence'], backend: ['inclusion'] },
  { name: 'TriangleAsConfiguration', source: 'Triangle', target: 'GeometricConfiguration', preserves: ['incidence'], backend: ['inclusion'] },
  // 多項式は微分可能。これが無いせいで Polynomial から微分に入れなかった
  { name: 'PolynomialAsSmooth', source: 'Polynomial', target: 'DifferentiableFunction', preserves: ['value', 'derivative'], backend: ['inclusion'] },
  { name: 'SemialgebraicUnderlyingSpace', source: 'SemialgebraicSet', target: 'TopologicalSpace', preserves: ['topology'], backend: ['subspace-topology'] },

  // (2) 標準的な構成
  { name: 'CharacteristicPolynomial', source: 'Matrix2', target: 'Polynomial', preserves: ['spectrum'], backend: ['charpoly'] },
  { name: 'MobiusRealization', source: 'Matrix2', target: 'RationalSelfMap', preserves: ['projective-action'], backend: ['rational-normal-form'] },
  { name: 'CoefficientSequence', source: 'Polynomial', target: 'Sequence', preserves: ['coefficients'], backend: ['polynomial-coefficients'] },
  { name: 'PrimeFactorization', source: 'Integer', target: 'PrimeSpectrum', preserves: ['valuation'], backend: ['integer-factorization'] },
  // 三角形の計量量が満たす関係式のイデアル。余弦定理はここから落ちる帰結であって、
  // 余弦定理そのものを射にすると1問専用になる（暗記）
  { name: 'MetricRelationIdeal', source: 'TriangleMetricData', target: 'PolynomialSystem', preserves: ['metric'], backend: ['groebner-basis', 'coordinate-algebra'] },
  { name: 'DesignatedRootEvaluation', source: 'AlgebraicSet', target: 'Real', preserves: ['exactness'], backend: ['polynomial-solver'] },
]

export type HyperMorphismSchema = {
  name: string
  sources: string[]
  target: string
  preserves: string[]
  backend: string[]
  // Some operations are valid inside an existing proof but are too weak to
  // establish that independent parent problems share one mathematical object.
  allows_cross_parent_fusion?: boolean
}

const HYPER_MORPHISM_ATLAS: readonly HyperMorphismSchema[] = [
  ...MORPHISM_ATLAS.map(edge => ({ ...edge, sources: [edge.source] })),

  /*
   * 複数の親が1本の射で出会う手段が、数値層に一つも無かった。
   * 融合は「全親が別々の入力ポートを占める」ことを要求するので、
   * これが無いと数値を扱う問題どうしは融合できない。
   */
  {
    name: 'RealFieldCombination',
    sources: ['Real', 'Real'],
    target: 'Real',
    preserves: ['exactness'],
    backend: ['field-arithmetic', 'exact-linear-invariant'],
    allows_cross_parent_fusion: false,
  },
  {
    // 不等式。sympy の ask は判定できず None を返す。SMT に投げる
    name: 'OrderComparison',
    sources: ['Real', 'Real'],
    target: 'Proposition',
    preserves: ['order'],
    backend: ['smt-nonlinear-real'],
    allows_cross_parent_fusion: false,
  },
  {
    // Proposition が出次数0だったので、証明を連鎖できなかった
    name: 'PropositionConjunction',
    sources: ['Proposition', 'Proposition'],
    target: 'Proposition',
    preserves: ['truth'],
    backend: ['smt-nonlinear-real'],
    allows_cross_parent_fusion: false,
  },
  {
    name: 'IntegerPairing',
    sources: ['Integer', 'Integer'],
    target: 'IntegerPair',
    preserves: ['components'],
    backend: ['integer-arithmetic'],
    allows_cross_parent_fusion: false,
  },
  {
    name: 'RatePairing',
    sources: ['Quantity', 'Quantity'],
    target: 'RateQuantityPair',
    preserves: ['unit', 'ratio'],
    backend: ['unit-checker'],
    allows_cross_parent_fusion: false,
  },
  {
    name: 'MapOrbitEvaluation',
    sources: ['RationalSelfMap', 'FiniteAlgebraicOrbit'],
    target: 'FiniteFamily',
    preserves: ['map-action', 'orbit-index', 'multiplicity'],
    backend: ['rational-normal-form', 'cyclotomic-polynomial'],
  },
  {
    name: 'ConstraintPullback',
    sources: ['PolynomialSystem', 'AlgebraicSet'],
    target: 'SemialgebraicSet',
    preserves: ['joint-solution-set', 'projection'],
    backend: ['groebner-basis', 'quantifier-elimination'],
  },
  {
    name: 'RootMinkowskiSum',
    sources: ['FiniteAlgebraicOrbit', 'FiniteAlgebraicOrbit'],
    target: 'FiniteAlgebraicOrbit',
    preserves: ['both-parent-provenance', 'algebraicity', 'finite-support'],
    backend: ['resultant', 'square-free-reduction'],
  },
  {
    name: 'RootMinkowskiDifference',
    sources: ['FiniteAlgebraicOrbit', 'FiniteAlgebraicOrbit'],
    target: 'FiniteAlgebraicOrbit',
    preserves: ['both-parent-provenance', 'algebraicity', 'finite-support'],
    backend: ['resultant', 'square-free-reduction'],
  },
  {
    name: 'RootPointwiseProduct',
    sources: ['FiniteAlgebraicOrbit', 'FiniteAlgebraicOrbit'],
    target: 'FiniteAlgebraicOrbit',
    preserves: ['both-parent-provenance', 'algebraicity', 'finite-support'],
    backend: ['resultant', 'square-free-reduction'],
  },
  {
    name: 'GCDLCMProductLaw',
    sources: ['GCDValue', 'LCMValue'],
    target: 'Integer',
    preserves: ['both-parent-provenance', 'prime-valuations', 'gcd-times-lcm-equals-product'],
    backend: ['integer-arithmetic', 'prime-valuation'],
  },
  {
    name: 'ArithmeticGeometryPredicateLift',
    sources: ['TriangleMetricData', 'IntegerPredicate'],
    target: 'Proposition',
    preserves: ['both-parent-provenance', 'metric-identity', 'integrality'],
    backend: ['arithmetic-geometry-induction', 'sympy-symbolic-identity'],
  },
  {
    name: 'PrimeGeometryPredicateLift',
    sources: ['TriangleMetricData', 'PrimeSpectrum'],
    target: 'Proposition',
    preserves: ['both-parent-provenance', 'metric-identity', 'primality'],
    backend: ['arithmetic-geometry-induction', 'primality-test'],
  },
  {
    name: 'ArithmeticTopologyPredicateLift',
    sources: ['FiniteTriangulation', 'IntegerPredicate'],
    target: 'Proposition',
    preserves: ['both-parent-provenance', 'homeomorphism-type', 'integrality'],
    backend: ['arithmetic-geometry-induction', 'euler-incidence-elimination'],
  },
  {
    name: 'PrimeTopologyPredicateLift',
    sources: ['FiniteTriangulation', 'PrimeSpectrum'],
    target: 'Proposition',
    preserves: ['both-parent-provenance', 'homeomorphism-type', 'primality'],
    backend: ['arithmetic-geometry-induction', 'primality-test'],
  },
]

export function executableMorphismAtlas(): readonly HyperMorphismSchema[] {
  return HYPER_MORPHISM_ATLAS
}

function hash(value: unknown, length = 12): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function textOf(parent: DiscoveryParent): string {
  // The statement defines the mathematical objects and constraints. A proposed
  // solution is tactic evidence and must not be allowed to redefine the input.
  return parent.statement ?? ''
}

function parentId(parent: DiscoveryParent): string {
  return String(parent.id || `parent-${hash(parent, 8)}`)
}

function identifierNodes(text: string, id: string): SemanticNode[] {
  const identifiers = [...new Set(text.match(/(?<!\\)[A-Za-zα-ωΑ-Ω](?:_\{?[A-Za-z0-9]+\}?)?/g) ?? [])]
  return identifiers.slice(0, 32).map((surface, index) => ({
    id: `${id}:symbol:${index}`,
    role: 'object',
    canonical: `Symbol_${index}`,
    sort: 'Unknown',
    surface,
    parent_id: id,
  }))
}

function inferredSort(text: string): string {
  for (const schema of OPERATOR_SCHEMAS) {
    if (schema.patterns.some(pattern => pattern.test(text))) return schema.output
  }
  return `OpaqueSort[${hash(text, 10)}]`
}

export function buildSemanticHypergraph(parent: DiscoveryParent): SemanticHypergraph {
  const id = parentId(parent)
  const text = textOf(parent)
  const language = elaborateMathematicalText(text, inferredSort)
  const nodes = identifierNodes(text, id)
  const edges: SemanticEdge[] = []
  const rootSorts = new Set<string>()
  const querySorts = new Set<string>()

  const clauses = language.forest.analyses[language.ir.selected_analysis]?.clauses ?? []
  for (const schema of OPERATOR_SCHEMAS) {
    const match = clauses.flatMap(clause => schema.patterns.map(pattern => clause.raw.match(pattern))).find(Boolean)
    if (!match) continue
    const nodeId = `${id}:op:${schema.canonical}`
    nodes.push({
      id: nodeId,
      role: schema.role ?? 'operator',
      canonical: schema.canonical,
      sort: schema.output,
      surface: match[0],
      parent_id: id,
    })
    // The input object exists in the parent. The output is only available after
    // the detected operator has actually been applied by the planner.
    rootSorts.add(schema.input)
    if (schema.role === 'query') querySorts.add(schema.output)
    edges.push({
      source: schema.input,
      target: schema.output,
      morphism: schema.canonical,
      preserves: schema.preserves,
      backend: schema.backend,
      proved: false,
      contributes_provenance: schema.role !== 'query',
    })
  }
  for (const definition of language.ir.definitions) {
    nodes.push({
      id: `${id}:${definition.id}`,
      role: 'object',
      canonical: definition.canonical,
      sort: definition.inferred_sort,
      surface: definition.symbol,
      parent_id: id,
    })
    rootSorts.add(definition.inferred_sort)
  }
  for (const declaration of language.ir.declarations) {
    nodes.push({
      id: `${id}:declaration:${declaration.symbol}`,
      role: 'object',
      canonical: `Declared[${declaration.sort}]`,
      sort: declaration.sort,
      surface: declaration.symbol,
      parent_id: id,
    })
    rootSorts.add(declaration.sort)
  }
  for (const constraint of language.ir.constraints) {
    nodes.push({
      id: `${id}:constraint:${hash(constraint.canonical, 8)}`,
      role: 'relation',
      canonical: constraint.canonical,
      sort: 'Proposition',
      surface: `${constraint.lhs} ${constraint.operator} ${constraint.rhs}`,
      parent_id: id,
    })
    rootSorts.add('Proposition')
  }
  language.ir.quantifiers.forEach((quantifier, index) => {
    nodes.push({
      id: `${id}:quantifier:${index}`,
      role: 'relation',
      canonical: `${quantifier.kind === 'forall' ? 'Forall' : 'Exists'}[${index}]`,
      sort: 'Proposition',
      surface: `${quantifier.kind}:${quantifier.variable ?? '?'}`,
      parent_id: id,
    })
    rootSorts.add('Proposition')
  })
  if (!rootSorts.size) rootSorts.add(`OpaqueSort[${hash(text || id, 10)}]`)
  return {
    parent_id: id,
    nodes,
    edges,
    root_sorts: [...rootSorts],
    query_sorts: [...querySorts],
    language_analysis: {
      token_count: language.forest.tokens.length,
      parse_count: language.forest.analyses.length,
      parse_truncated: language.forest.truncated,
      clause_count: clauses.length,
      quantifier_prefix: language.ir.quantifier_prefix,
      definitions: language.ir.definitions.map(definition => ({
        symbol: definition.symbol,
        canonical: definition.canonical,
        sort: definition.inferred_sort,
      })),
      declarations: language.ir.declarations.map(declaration => ({
        symbol: declaration.symbol,
        sort: declaration.sort,
        implicit_forall: declaration.implicit_forall,
      })),
      constraints: language.ir.constraints.map(constraint => ({
        operator: constraint.operator,
        canonical: constraint.canonical,
      })),
      unresolved_references: language.ir.unresolved_references,
      diagnostics: language.ir.diagnostics,
    },
  }
}

function pathsFrom(source: string, maxDepth: number): Array<{ target: string; edges: MorphismSchema[] }> {
  const queue: Array<{ sort: string; edges: MorphismSchema[] }> = [{ sort: source, edges: [] }]
  const seen = new Map<string, number>([[source, 0]])
  const paths: Array<{ target: string; edges: MorphismSchema[] }> = [{ target: source, edges: [] }]
  while (queue.length) {
    const current = queue.shift()!
    if (current.edges.length >= maxDepth) continue
    for (const edge of MORPHISM_ATLAS) {
      if (edge.source !== current.sort) continue
      const next = [...current.edges, edge]
      const prior = seen.get(edge.target)
      if (prior !== undefined && prior <= next.length) continue
      seen.set(edge.target, next.length)
      paths.push({ target: edge.target, edges: next })
      queue.push({ sort: edge.target, edges: next })
    }
  }
  return paths
}

function bestCommonTarget(graphs: SemanticHypergraph[], maxDepth: number) {
  const perParent = graphs.map(graph => graph.root_sorts.flatMap(sort =>
    pathsFrom(sort, maxDepth).map(path => ({ ...path, start: sort })),
  ))
  const targets = perParent.reduce<Set<string>>((common, paths, index) => {
    const current = new Set(paths.map(path => path.target))
    return index === 0 ? current : new Set([...common].filter(target => current.has(target)))
  }, new Set())
  const ranked = [...targets].map(target => {
    const paths = perParent.map(options => options
      .filter(option => option.target === target)
      .sort((left, right) => left.edges.length - right.edges.length)[0])
    const totalCost = paths.reduce((sum, path) => sum + path.edges.length, 0)
    const executable = paths.flatMap(path => path.edges).every(edge => edge.backend.length > 0)
    return { target, paths, totalCost, executable }
  }).filter(candidate => candidate.paths.every(path => path.edges.length > 0))
    .sort((left, right) =>
    Number(right.executable) - Number(left.executable) || left.totalCost - right.totalCost,
  )
  return ranked[0] ?? null
}

function parentIdsFromMask(graphs: SemanticHypergraph[], mask: number): string[] {
  return graphs.filter((_, index) => (mask & (1 << index)) !== 0).map(graph => graph.parent_id)
}

function planJointHypergraph(graphs: SemanticHypergraph[], maxDepth: number, maxStates: number) {
  if (!graphs.length || graphs.length > 30) return { plan: null, statesExplored: 0, exhausted: true }
  const fullMask = (1 << graphs.length) - 1
  type Provenance = { mask: number; fused: boolean }
  const initial = new Map<string, Provenance[]>()
  graphs.forEach((graph, index) => {
    const mask = 1 << index
    for (const sort of graph.root_sorts) {
      const alternatives = initial.get(sort) ?? []
      if (!alternatives.some(item => item.mask === mask && !item.fused)) {
        alternatives.push({ mask, fused: false })
      }
      initial.set(sort, alternatives)
    }
  })
  type State = { known: Map<string, Provenance[]>; steps: RoadmapStep[] }
  const queue: State[] = [{ known: initial, steps: [] }]
  const seen = new Set<string>()
  const preferredTargets = new Set(['Scalar', 'Integer', 'Proof'])
  const keyOf = (known: Map<string, Provenance[]>) => [...known.entries()]
    .sort(([left], [right]) => left.localeCompare(right))
    .map(([sort, alternatives]) => `${sort}:${alternatives
      .map(provenance => `${provenance.mask}.${Number(provenance.fused)}`)
      .sort()
      .join(',')}`)
    .join('|')
  seen.add(keyOf(initial))
  const planningEdges = [
    ...HYPER_MORPHISM_ATLAS.map(edge => ({ ...edge, originMask: 0 })),
    ...graphs.flatMap((graph, graphIndex) => graph.edges.map(edge => ({
      name: edge.morphism,
      sources: [edge.source],
      target: edge.target,
      preserves: edge.preserves,
      backend: edge.backend,
      allows_cross_parent_fusion: true,
      originMask: edge.contributes_provenance ? 1 << graphIndex : 0,
    }))),
  ]

  let statesExplored = 0
  for (let cursor = 0; cursor < queue.length && cursor < maxStates; cursor++) {
    statesExplored++
    const state = queue[cursor]
    const completed = [...state.known.entries()]
      .filter(([sort, alternatives]) => alternatives.some(provenance =>
        provenance.mask === fullMask && provenance.fused,
      ) && preferredTargets.has(sort))
      .sort(([left], [right]) => Number(right === 'Scalar') - Number(left === 'Scalar'))[0]
    if (completed && state.steps.length > 0) return {
      plan: { target: completed[0], roadmap: state.steps },
      statesExplored,
      exhausted: false,
    }
    if (state.steps.length >= maxDepth) continue

    for (const edge of planningEdges) {
      const alternatives = edge.sources.map(source => state.known.get(source) ?? [])
      if (alternatives.some(options => options.length === 0)) continue
      const combinations: Provenance[][] = [[]]
      for (const options of alternatives) {
        const prior = combinations.splice(0)
        for (const combination of prior) {
          for (const option of options) combinations.push([...combination, option])
        }
      }
      for (const provenances of combinations) {
        const inputMask = provenances.reduce((mask, input) => mask | input.mask, 0)
        const combinedMask = inputMask | edge.originMask
        const contributorMasks = [...provenances.map(input => input.mask), edge.originMask].filter(Boolean)
        const hasDistinctContributors = new Set(contributorMasks).size > 1
        const mayIntroduceFusion = edge.allows_cross_parent_fusion !== false
        const combinedFused = provenances.some(input => input.fused) ||
          (mayIntroduceFusion && hasDistinctContributors && combinedMask === fullMask)
        const previous = state.known.get(edge.target) ?? []
        const dominated = previous.some(item =>
          item.mask === combinedMask && (item.fused || !combinedFused),
        )
        if (dominated) continue
        const nextAlternatives = previous
          .filter(item => item.mask !== combinedMask || combinedFused || !item.fused)
          .concat({ mask: combinedMask, fused: combinedFused })
        const known = new Map(state.known)
        known.set(edge.target, nextAlternatives)
        const key = keyOf(known)
        if (seen.has(key)) continue
        seen.add(key)
        const step: RoadmapStep = {
          id: `joint-${state.steps.length + 1}-${edge.name}`,
          source: edge.sources.join(' × '),
          target: edge.target,
          morphism: edge.name,
          preserves: edge.preserves,
          backend: edge.backend,
          status: 'open',
          parent_ids: parentIdsFromMask(graphs, combinedMask),
        }
        queue.push({ known, steps: [...state.steps, step] })
      }
    }
  }
  return { plan: null, statesExplored, exhausted: queue.length <= statesExplored }
}

export function generalizeParents(
  parents: DiscoveryParent[],
  maxDepth = 6,
  maxStates = 10_000,
): { graphs: SemanticHypergraph[]; certificate: GeneralizationCertificate } {
  const graphs = parents.map(buildSemanticHypergraph)
  const operatorSets = graphs.map(graph => new Set(graph.nodes
    .filter(node => node.role === 'operator')
    .map(node => node.canonical)))
  const sortSets = graphs.map(graph => new Set(graph.root_sorts))
  const intersect = (sets: Set<string>[]) => sets.length
    ? [...sets[0]].filter(value => sets.every(set => set.has(value)))
    : []
  const commonOperators = intersect(operatorSets)
  const commonSorts = intersect(sortSets)
  const jointSearch = planJointHypergraph(graphs, maxDepth, maxStates)
  const jointPlan = jointSearch.plan
  // Multiple parents must meet in one provenance-carrying construction. Merely
  // mapping them separately into a common codomain is not a fusion.
  const join = jointPlan || parents.length > 1 ? null : bestCommonTarget(graphs, maxDepth)
  const roadmap: RoadmapStep[] = []
  if (jointPlan) {
    roadmap.push(...jointPlan.roadmap)
  } else if (join) {
    join.paths.forEach((path, parentIndex) => {
      path.edges.forEach((edge, edgeIndex) => roadmap.push({
        id: `r${parentIndex + 1}-${edgeIndex + 1}-${edge.name}`,
        source: edge.source,
        target: edge.target,
        morphism: edge.name,
        preserves: edge.preserves,
        backend: edge.backend,
        status: 'open',
        parent_ids: [graphs[parentIndex].parent_id],
      }))
    })
  }
  const bindings = graphs.flatMap(graph => graph.nodes
    .filter(node => node.role === 'operator' || node.role === 'query')
    .map(node => ({
      parent_id: graph.parent_id,
      surface: node.surface,
      canonical: node.canonical,
      sort: node.sort,
    })))
  const executableBackends = [...new Set(roadmap.flatMap(step => step.backend))]
  const proofObligations = roadmap.flatMap(step => [
    `${step.morphism}: ${step.source} -> ${step.target} is defined under the parent constraints`,
    `${step.morphism} preserves ${step.preserves.join(', ') || 'the required observable'}`,
  ])
  if (!jointPlan && !join) proofObligations.push('No joint executable construction was found; synthesize typed intermediate morphisms without inventing a scalar bridge')
  return {
    graphs,
    certificate: {
      id: `generalization.${hash({ parents: graphs.map(graph => graph.parent_id), commonOperators, commonSorts, roadmap })}`,
      method: 'typed-operator-overlap-and-hypergraph-planning-v1',
      parent_ids: graphs.map(graph => graph.parent_id),
      common_operators: commonOperators,
      common_sorts: commonSorts,
      bindings,
      target_sort: jointPlan?.target ?? join?.target ?? null,
      roadmap,
      proof_obligations: proofObligations,
      negative_transfer_checks: [
        'remove each parent and require the resulting construction to change',
        'rename variables and perturb numeric parameters without changing the certificate',
        'reject non-adjacent morphology jumps and bare-scalar bridges',
        'reject any roadmap edge without an executable backend contract',
      ],
      executable_backends: executableBackends,
      language_analysis: graphs.map(graph => graph.language_analysis),
      search_evidence: {
        max_depth: maxDepth,
        max_states: maxStates,
        states_explored: jointSearch.statesExplored,
        exhausted: jointSearch.exhausted,
      },
    },
  }
}
