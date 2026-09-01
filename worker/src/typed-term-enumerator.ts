import { createHash } from 'node:crypto'
import {
  primitiveMorphismBasis,
  type HyperMorphismSchema,
  type SemanticBinding,
  type SemanticHypergraph,
} from './generalization-kernel'

export type TypedTermStep = {
  morphism: string
  sources: string[]
  target: string
  backend: string[]
  preserves: string[]
}

export type TypedProgramNode =
  | {
      kind: 'parent'
      parentId: string
      sort: string
      bindingId?: string
      canonical?: string
      surface?: string
      semanticRole?: 'object' | 'assumption' | 'goal'
      propositionCanonical?: string
      certificateHash?: string
    }
  | {
      kind: 'apply'
      morphism: string
      sources: string[]
      target: string
      backend: string[]
      preserves: string[]
      args: TypedProgramNode[]
    }

export type TypedTerm = {
  id: string
  sort: string
  expression: string
  parentMask: number
  parentIds: string[]
  depth: number
  steps: TypedTermStep[]
  constraints: string[]
  propositionCanonical?: string
  certificateHash?: string
  program: TypedProgramNode
}

export type TypedEnumerationResult = {
  terms: TypedTerm[]
  goals: TypedTerm[]
  frontier: Array<{
    morphism: string
    sources: string[]
    target: string
    missing: string[]
    availableParentMask: number
  }>
  statesExplored: number
  exhausted: boolean
}

export type TypedEnumerationOptions = {
  maxDepth?: number
  maxStates?: number
  goalSorts?: string[]
  rules?: readonly HyperMorphismSchema[]
  /**
   * A value with the requested sort is not necessarily an answer to the
   * requested operation. For example, a triangle inequality invariant and a
   * maximum area are both Scalars. Keep the terminal operation explicit so a
   * type-correct but semantically unrelated route cannot count as coverage.
   */
  terminalMorphismsBySort?: Readonly<Record<string, readonly string[]>>
}

function hash(value: unknown, length = 14): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function combinations<T>(sets: T[][], limit: number): T[][] {
  let rows: T[][] = [[]]
  for (const set of sets) {
    const next: T[][] = []
    for (const row of rows) {
      for (const value of set) {
        next.push([...row, value])
        if (next.length >= limit) break
      }
      if (next.length >= limit) break
    }
    rows = next
    if (!rows.length) break
  }
  return rows
}

function rootTerms(graphs: SemanticHypergraph[]): TypedTerm[] {
  return graphs.flatMap((graph, graphIndex) => {
    const constraints = graph.language_analysis.constraints
      .filter(item => item.role !== 'goal')
      .map(item => item.canonical)
    const bindings: SemanticBinding[] = graph.root_bindings?.length
      ? graph.root_bindings
      : graph.root_sorts.map((sort, sortIndex) => ({
        id: `${graph.parent_id}:legacy-root:${sortIndex}`,
        role: 'object' as const,
        canonical: `LegacyRoot[${sortIndex}]`,
        sort,
        surface: sort,
        parent_id: graph.parent_id,
      }))
    return bindings.map(binding => ({
      id: `root.${hash([graph.parent_id, binding.id, binding.sort])}`,
      sort: binding.sort,
      expression: `ParentObject(${JSON.stringify(graph.parent_id)},${JSON.stringify(binding.sort)},${JSON.stringify(binding.id)})`,
      parentMask: graphs.length < 31 ? 1 << graphIndex : 0,
      parentIds: [graph.parent_id],
      depth: 0,
      steps: [],
      constraints,
      propositionCanonical: binding.proposition_canonical,
      certificateHash: binding.certificate_hash,
      program: {
        kind: 'parent' as const,
        parentId: graph.parent_id,
        sort: binding.sort,
        bindingId: binding.id,
        canonical: binding.canonical,
        surface: binding.surface,
        semanticRole: binding.role,
        propositionCanonical: binding.proposition_canonical,
        certificateHash: binding.certificate_hash,
      },
    }))
  })
}

function graphRules(graphs: SemanticHypergraph[]): HyperMorphismSchema[] {
  return graphs.flatMap(graph => graph.edges
    .filter(edge => edge.backend.length > 0)
    .map(edge => ({
      name: edge.morphism,
      sources: [edge.source],
      target: edge.target,
      preserves: edge.preserves,
      backend: edge.backend,
      allows_cross_parent_fusion: edge.proved,
    })))
}

function termKey(term: Pick<TypedTerm, 'sort' | 'expression' | 'parentIds'>): string {
  return `${term.sort}\u0000${term.parentIds.join(',')}\u0000${term.expression}`
}

function mergeSteps(terms: TypedTerm[], next: TypedTermStep): TypedTermStep[] {
  const seen = new Set<string>()
  const result: TypedTermStep[] = []
  for (const step of [...terms.flatMap(term => term.steps), next]) {
    const key = JSON.stringify([step.morphism, step.sources, step.target, step.backend])
    if (seen.has(key)) continue
    seen.add(key)
    result.push(step)
  }
  return result
}

export function enumerateTypedTerms(
  graphs: SemanticHypergraph[],
  options: TypedEnumerationOptions = {},
): TypedEnumerationResult {
  const maxDepth = Math.max(1, options.maxDepth ?? 6)
  const maxStates = Math.max(1, options.maxStates ?? 10_000)
  const goalSorts = new Set(options.goalSorts ?? ['Scalar', 'Integer', 'Proof', 'FiniteAlgebraicOrbit'])
  const rules = [...(options.rules ?? primitiveMorphismBasis()), ...graphRules(graphs)]
    .filter(rule => rule.backend.length > 0)
  const terms = rootTerms(graphs)
  const seen = new Set(terms.map(termKey))
  const beamCounts = new Map<string, number>()
  let statesExplored = terms.length
  let changed = true

  while (changed && statesExplored < maxStates) {
    changed = false
    const bySort = new Map<string, TypedTerm[]>()
    for (const term of terms) {
      const rows = bySort.get(term.sort) ?? []
      rows.push(term)
      bySort.set(term.sort, rows)
    }
    for (const rule of rules) {
      const inputs = rule.sources.map(source => bySort.get(source) ?? [])
      if (inputs.some(rows => rows.length === 0)) continue
      for (const args of combinations(inputs, 256)) {
        const depth = Math.max(...args.map(arg => arg.depth)) + 1
        if (depth > maxDepth) continue
        const parentMask = args.reduce((mask, arg) => mask | arg.parentMask, 0)
        const introducesCrossParentFusion = args.length > 1 &&
          args.every(arg => arg.parentMask !== parentMask)
        if (rule.allows_cross_parent_fusion === false && introducesCrossParentFusion) continue
        let propositionCanonical: string | undefined
        let certificateHash: string | undefined
        if (rule.name === 'PropositionCertification') {
          const goal = args.find(argument => argument.sort === 'GoalProposition')
          const certified = args.find(argument => argument.sort === 'CertifiedProposition')
          if (!goal?.propositionCanonical || !certified?.propositionCanonical) continue
          if (goal.propositionCanonical !== certified.propositionCanonical) continue
          if (!certified.certificateHash) continue
        } else if (rule.name === 'AssumptionConjunction') {
          if (args.some(argument => !argument.propositionCanonical)) continue
          propositionCanonical = `And[${args.map(argument => argument.propositionCanonical).sort().join(',')}]`
        } else if (rule.name === 'CertifiedConjunction') {
          if (args.some(argument => !argument.propositionCanonical || !argument.certificateHash)) continue
          propositionCanonical = `And[${args.map(argument => argument.propositionCanonical).sort().join(',')}]`
          certificateHash = hash(args.map(argument => argument.certificateHash).sort(), 64)
        }
        const expression = `${rule.name}(${args.map(arg => arg.expression).join(',')})`
        if (expression.length > 4096) continue
        const parentIds = [...new Set(args.flatMap(arg => arg.parentIds))].sort()
        const beamKey = `${rule.target}\u0000${parentIds.join(',')}\u0000${depth}\u0000${rule.name}`
        if ((beamCounts.get(beamKey) ?? 0) >= 4) continue
        const nextStep = {
          morphism: rule.name,
          sources: rule.sources,
          target: rule.target,
          backend: rule.backend,
          preserves: rule.preserves,
        }
        const term: TypedTerm = {
          id: `term.${hash([rule.name, expression, parentMask])}`,
          sort: rule.target,
          expression,
          parentMask,
          parentIds,
          depth,
          steps: mergeSteps(args, nextStep),
          constraints: [...new Set(args.flatMap(arg => arg.constraints))],
          propositionCanonical,
          certificateHash,
          program: {
            kind: 'apply',
            morphism: rule.name,
            sources: [...rule.sources],
            target: rule.target,
            backend: [...rule.backend],
            preserves: [...rule.preserves],
            args: args.map(arg => arg.program),
          },
        }
        const key = termKey(term)
        if (seen.has(key)) continue
        seen.add(key)
        beamCounts.set(beamKey, (beamCounts.get(beamKey) ?? 0) + 1)
        terms.push(term)
        statesExplored++
        changed = true
        if (statesExplored >= maxStates) break
      }
      if (statesExplored >= maxStates) break
    }
  }

  const goals = terms
    .filter(term => {
      if (term.parentIds.length !== graphs.length || !goalSorts.has(term.sort) || term.depth === 0) return false
      const requiredTerminals = options.terminalMorphismsBySort?.[term.sort] ?? []
      if (!requiredTerminals.length) return true
      return term.program.kind === 'apply' && requiredTerminals.includes(term.program.morphism)
    })
    .sort((left, right) => left.depth - right.depth || left.expression.localeCompare(right.expression))
  const availableSorts = new Map<string, number>()
  for (const term of terms) {
    availableSorts.set(term.sort, (availableSorts.get(term.sort) ?? 0) | term.parentMask)
  }
  const demandedSorts = new Set(graphs.flatMap(graph => graph.query_sorts))
  const frontier = rules.flatMap(rule => {
    const missing = rule.sources.filter(source => !availableSorts.has(source))
    if (!missing.length) return []
    const availableParentMask = rule.sources.reduce(
      (mask, source) => mask | (availableSorts.get(source) ?? 0),
      0,
    )
    // Keep a completely missing path when it is the direct producer of the
    // requested result. Otherwise proof goals with no certificate disappear
    // from the audit instead of remaining explicit obligations.
    if (!availableParentMask && !demandedSorts.has(rule.target)) return []
    return [{
      morphism: rule.name,
      sources: rule.sources,
      target: rule.target,
      missing,
      availableParentMask,
    }]
  })

  return {
    terms,
    goals,
    frontier,
    statesExplored,
    exhausted: !changed,
  }
}

/**
 * Recover the operation requested by the statement, not merely its codomain.
 * The semantic graph already records explicit query operators such as
 * Extremum and Measure. We expand each to the equivalent primitive-basis name
 * used by the cold planner.
 */
export function semanticQueryTerminalMorphisms(
  graphs: readonly SemanticHypergraph[],
  requestedSort: string,
): string[] {
  const terminals = new Set<string>()
  const queryNodes = graphs.flatMap(graph => graph.nodes.filter(node => node.role === 'query'))
  const queryKinds = queryNodes.flatMap(node => {
    const match = node.canonical.match(/^Query\[([^\]]+)]$/)
    return match ? [match[1]] : []
  })
  if (requestedSort === 'Proof' || queryKinds.includes('prove')) {
    if (requestedSort === 'Proof') terminals.add('PropositionCertification')
    return [...terminals]
  }

  const explicit = new Set(queryNodes
    .filter(node => node.sort === requestedSort && !/^Query\[/.test(node.canonical) && node.sort !== 'GoalProposition')
    .map(node => node.canonical))
  // A composite request is governed by its outermost observation. Computing an
  // area is not yet an answer to "find the maximum area"; the extremum must be
  // the terminal operation. The same precedence keeps counting and measure
  // queries from being accepted through a weaker same-codomain operation.
  if (explicit.has('Extremum')) {
    terminals.add('Extremum')
    terminals.add('ExtremalObservation')
  } else if (explicit.has('Cardinality')) {
    terminals.add('Cardinality')
    terminals.add('Counting')
  } else if (explicit.has('Measure')) {
    terminals.add('Measure')
    terminals.add('MeasureObservation')
  } else if (explicit.has('EvaluateExpression')) {
    terminals.add('EvaluateExpression')
  }

  for (const graph of graphs) {
    // A generic "compute this observable" query is not licensed to accept an
    // arbitrary value of the same codomain. It must pass through a constraint
    // program synthesized from this statement. When that IR cannot be built,
    // keeping this terminal requirement makes the obligation remain open.
    if (!terminals.size && requestedSort === 'Scalar' &&
        queryKinds.some(kind => kind === 'compute' || kind === 'observe')) {
      terminals.add('SolveConstraintQuery')
    }
    if (!terminals.size && requestedSort === 'FiniteSet' && queryKinds.includes('classify')) {
      terminals.add('EnumerateConstraintSolutions')
    }
  }
  return [...terminals].sort()
}
