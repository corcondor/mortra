import { createHash } from 'node:crypto'
import {
  executableMorphismAtlas,
  type HyperMorphismSchema,
  type SemanticHypergraph,
} from './generalization-kernel'

export type TypedTermStep = {
  morphism: string
  sources: string[]
  target: string
  backend: string[]
  preserves: string[]
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
    const constraints = graph.language_analysis.constraints.map(item => item.canonical)
    return graph.root_sorts.map((sort, sortIndex) => ({
      id: `root.${hash([graph.parent_id, sort, sortIndex])}`,
      sort,
      expression: `ParentObject(${JSON.stringify(graph.parent_id)},${JSON.stringify(sort)})`,
      parentMask: graphs.length < 31 ? 1 << graphIndex : 0,
      parentIds: [graph.parent_id],
      depth: 0,
      steps: [],
      constraints,
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
  options: { maxDepth?: number; maxStates?: number; goalSorts?: string[]; rules?: readonly HyperMorphismSchema[] } = {},
): TypedEnumerationResult {
  const maxDepth = Math.max(1, options.maxDepth ?? 6)
  const maxStates = Math.max(1, options.maxStates ?? 10_000)
  const goalSorts = new Set(options.goalSorts ?? ['Scalar', 'Integer', 'Proof', 'FiniteAlgebraicOrbit'])
  const rules = [...(options.rules ?? executableMorphismAtlas()), ...graphRules(graphs)]
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
    .filter(term => term.parentIds.length === graphs.length && goalSorts.has(term.sort) && term.depth > 0)
    .sort((left, right) => left.depth - right.depth || left.expression.localeCompare(right.expression))
  const availableSorts = new Map<string, number>()
  for (const term of terms) {
    availableSorts.set(term.sort, (availableSorts.get(term.sort) ?? 0) | term.parentMask)
  }
  const frontier = rules.flatMap(rule => {
    const missing = rule.sources.filter(source => !availableSorts.has(source))
    if (!missing.length) return []
    const availableParentMask = rule.sources.reduce(
      (mask, source) => mask | (availableSorts.get(source) ?? 0),
      0,
    )
    if (!availableParentMask) return []
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
