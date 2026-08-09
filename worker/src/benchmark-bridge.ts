import { readFileSync } from 'node:fs'
import {
  buildSemanticHypergraph,
  coreExecutableMorphismAtlas,
  executableMorphismAtlas,
} from './generalization-kernel'
import { enumerateTypedTerms } from './typed-term-enumerator'

type Request = {
  id?: string
  statement: string
  max_depth?: number
  max_states?: number
  atlas?: 'core' | 'unified'
  compact?: boolean
}

function evaluate(request: Request) {
  const graph = buildSemanticHypergraph({ id: request.id, statement: request.statement })
  const rules = request.atlas === 'core' ? coreExecutableMorphismAtlas() : executableMorphismAtlas()
  const goalSorts = graph.query_sorts
  if (!goalSorts.length) {
    const unresolved = {
      id: request.id ?? null,
      status: 'query_unresolved',
      atlas: request.atlas ?? 'unified',
      atlas_size: rules.length,
      states_explored: 0,
      root_sorts: graph.root_sorts,
      query_sorts: graph.query_sorts,
      morphisms: graph.edges.map(edge => edge.morphism),
      language_analysis: graph.language_analysis,
      goal_count: 0,
    }
    return request.compact ? unresolved : { ...unresolved, graph, goals: [], frontier: [] }
  }
  const enumeration = enumerateTypedTerms([graph], {
    maxDepth: request.max_depth ?? 7,
    maxStates: request.max_states ?? 10_000,
    goalSorts,
    rules,
  })
  const result = {
    id: request.id ?? null,
    status: enumeration.goals.length ? 'goal_reached' : 'goal_unreached',
    atlas: request.atlas ?? 'unified',
    atlas_size: rules.length,
    states_explored: enumeration.statesExplored,
    exhausted: enumeration.exhausted,
    root_sorts: graph.root_sorts,
    query_sorts: graph.query_sorts,
    morphisms: graph.edges.map(edge => edge.morphism),
    language_analysis: graph.language_analysis,
    goal_count: enumeration.goals.length,
    first_goal: enumeration.goals[0] ?? null,
  }
  return request.compact
    ? result
    : { ...result, graph, goals: enumeration.goals.slice(0, 8), frontier: enumeration.frontier.slice(0, 30) }
}

const input = JSON.parse(readFileSync(0, 'utf8')) as Request | Request[]
const output = Array.isArray(input) ? input.map(evaluate) : evaluate(input)
process.stdout.write(JSON.stringify(output))
