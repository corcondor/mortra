import { createHash } from 'node:crypto'
import type { DiscoveryParent } from './parent-conditioned-discovery'

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
}

export type SemanticHypergraph = {
  parent_id: string
  nodes: SemanticNode[]
  edges: SemanticEdge[]
  root_sorts: string[]
  query_sorts: string[]
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
  method: 'typed-hypergraph-anti-unification'
  parent_ids: string[]
  common_operators: string[]
  common_sorts: string[]
  bindings: Array<{ parent_id: string; surface: string; canonical: string; sort: string }>
  target_sort: string | null
  roadmap: RoadmapStep[]
  proof_obligations: string[]
  negative_transfer_checks: string[]
  executable_backends: string[]
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
  { canonical: 'Integral', patterns: [/\\int\b/i, /積分/], input: 'Function', output: 'Scalar', preserves: ['linearity'], backend: ['symbolic-integration', 'numeric-quadrature'] },
  { canonical: 'Derivative', patterns: [/\\frac\s*\{d|f\s*['′]|微分|導関数/], input: 'DifferentiableFunction', output: 'Function', preserves: ['local-contact'], backend: ['symbolic-differentiation'] },
  { canonical: 'Limit', patterns: [/\\lim\b/i, /極限/], input: 'FilteredObject', output: 'Scalar', preserves: ['asymptotic-class'], backend: ['limit-engine', 'interval-bound'] },
  { canonical: 'Sum', patterns: [/\\sum\b/i, /総和|和を求め/], input: 'FiniteFamily', output: 'Scalar', preserves: ['index-set', 'multiplicity'], backend: ['exact-summation'] },
  { canonical: 'Product', patterns: [/\\prod\b/i, /総積|積を求め/], input: 'FiniteFamily', output: 'Scalar', preserves: ['index-set', 'multiplicity'], backend: ['resultant', 'exact-product'] },
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
  { canonical: 'Proof', patterns: [/示せ|証明|prove/i], input: 'Proposition', output: 'Proof', role: 'query', preserves: ['truth'], backend: ['lean', 'smt', 'symbolic-identity'] },
]

type MorphismSchema = {
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
]

function hash(value: unknown, length = 12): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function textOf(parent: DiscoveryParent): string {
  return [parent.statement, parent.solution, parent.inspiration].filter(Boolean).join('\n')
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

export function buildSemanticHypergraph(parent: DiscoveryParent): SemanticHypergraph {
  const id = parentId(parent)
  const text = textOf(parent)
  const nodes = identifierNodes(text, id)
  const edges: SemanticEdge[] = []
  const rootSorts = new Set<string>()
  const querySorts = new Set<string>()

  for (const schema of OPERATOR_SCHEMAS) {
    const match = schema.patterns.map(pattern => text.match(pattern)).find(Boolean)
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
    rootSorts.add(schema.input)
    rootSorts.add(schema.output)
    if (schema.role === 'query') querySorts.add(schema.output)
    edges.push({
      source: schema.input,
      target: schema.output,
      morphism: schema.canonical,
      preserves: schema.preserves,
      backend: schema.backend,
      proved: false,
    })
  }
  if (!rootSorts.size) rootSorts.add(`OpaqueSort[${hash(text || id, 10)}]`)
  return {
    parent_id: id,
    nodes,
    edges,
    root_sorts: [...rootSorts],
    query_sorts: [...querySorts],
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
  }).sort((left, right) =>
    Number(right.executable) - Number(left.executable) || left.totalCost - right.totalCost,
  )
  return ranked[0] ?? null
}

export function generalizeParents(
  parents: DiscoveryParent[],
  maxDepth = 6,
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
  const join = bestCommonTarget(graphs, maxDepth)
  const roadmap: RoadmapStep[] = []
  if (join) {
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
  if (!join) proofObligations.push('No common executable codomain was found; expand the typed atlas without inventing a scalar bridge')
  return {
    graphs,
    certificate: {
      id: `generalization.${hash({ parents: graphs.map(graph => graph.parent_id), commonOperators, commonSorts, roadmap })}`,
      method: 'typed-hypergraph-anti-unification',
      parent_ids: graphs.map(graph => graph.parent_id),
      common_operators: commonOperators,
      common_sorts: commonSorts,
      bindings,
      target_sort: join?.target ?? null,
      roadmap,
      proof_obligations: proofObligations,
      negative_transfer_checks: [
        'remove each parent and require the resulting construction to change',
        'rename variables and perturb numeric parameters without changing the certificate',
        'reject non-adjacent morphology jumps and bare-scalar bridges',
        'reject any roadmap edge without an executable backend contract',
      ],
      executable_backends: executableBackends,
    },
  }
}
