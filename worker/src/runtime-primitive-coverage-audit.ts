import { readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'

import { generalizeParents } from './generalization-kernel'
import {
  enumerateTypedTerms,
  semanticQueryTerminalMorphisms,
  type TypedProgramNode,
} from './typed-term-enumerator'
import {
  inspectTypedProgramExecution,
  runtimeParentSorts,
  runtimePrimitiveHandlers,
} from './typed-program-executor'

type CatalogEntry = {
  id: string
  ordinal: number
  label: string
  statement: string
}

type Catalog = {
  sourceLabel: string
  sourceSha256: string
  entries: CatalogEntry[]
}

const root = path.resolve(__dirname, '..', '..')
const inputPath = path.resolve(
  root,
  process.argv[2] ?? 'artifacts/benchmarks/fullproblem-certified-catalog-20260831.json',
)
const outputPath = path.resolve(
  root,
  process.argv[3] ?? 'artifacts/benchmarks/runtime-primitive-coverage-20260901.json',
)
const catalog = JSON.parse(readFileSync(inputPath, 'utf8')) as Catalog
const problemOrdinals = new Map<string, number[]>()
const minimumDepth = new Map<string, number>()
const frontierProblemOrdinals = new Map<string, number[]>()
const forcedMinimalGapDemands = new Map<string, Array<{ ordinal: number; sort: string }>>()
const optionalMinimalGapDemands = new Map<string, Array<{ ordinal: number; sort: string }>>()
let totalGoals = 0
let executableGoals = 0
let preInvariantExecutableGoals = 0
let postInvariantExecutableGoals = 0
let postMapOrbitExecutableGoals = 0
let concreteRootBindings = 0
let assumptionBindings = 0
let proofQueryProblems = 0
let proofGoalBindings = 0
let typedProofGoals = 0
let executableProofGoals = 0
let querySortDemands = 0
let typedReachableQuerySortDemands = 0
let executableQuerySortDemands = 0
let parsedQueryProblems = 0
let unparsedQueryProblems = 0
let problemsWithTypedQueryProgram = 0
let problemsWithExecutableQueryProgram = 0
let fullyExecutableQueryProblems = 0
const unparsedQueryOrdinals: number[] = []
const unreachableQueryDemands: Array<{ ordinal: number; sort: string }> = []
const queryDemandDiagnostics: Array<{
  ordinal: number
  sort: string
  typed_candidate_count: number
  minimum_unsupported_count: number | null
  minimum_depth: number | null
  forced_minimal_gaps: string[]
  alternative_minimal_gap_sets: string[][]
}> = []
const invariantNewProblems = new Set<number>()
const mapOrbitNewProblems = new Set<number>()
const expressionIrNewProblems = new Set<number>()
const currentHandlers = new Set(runtimePrimitiveHandlers())
const currentParentSorts = new Set(runtimeParentSorts())
const expressionIrHandlers = new Set(['EvaluateExpression'])
const mapOrbitHandlers = new Set(['MobiusMap', 'MobiusRealization', 'MapOrbitEvaluation', 'FiniteSummation'])
const postMapOrbitHandlers = new Set([...currentHandlers].filter(handler => !expressionIrHandlers.has(handler)))
const postInvariantHandlers = new Set([...postMapOrbitHandlers].filter(handler => !mapOrbitHandlers.has(handler)))
const preInvariantHandlers = new Set([...postInvariantHandlers].filter(handler =>
  handler !== 'FieldTrace' && handler !== 'FieldNorm'))
const polynomialParentOnly = new Set(['Polynomial'])

function executableWith(
  node: TypedProgramNode,
  handlers: ReadonlySet<string>,
  parentSorts: ReadonlySet<string>,
): boolean {
  if (node.kind === 'parent') return parentSorts.has(node.sort)
  return handlers.has(node.morphism) && node.args.every(argument =>
    executableWith(argument, handlers, parentSorts))
}

for (const entry of catalog.entries) {
  const parent = { id: entry.id, statement: entry.statement, answer: null, solution: null }
  const generalized = generalizeParents([parent], 4, 5_000)
  const graph = generalized.graphs[0]
  concreteRootBindings += graph.root_bindings?.length ?? graph.root_sorts.length
  assumptionBindings += graph.root_bindings?.filter(binding => binding.role === 'assumption').length ?? 0
  if (graph.query_sorts.includes('Proof')) {
    proofQueryProblems++
    proofGoalBindings += graph.query_bindings?.filter(binding => binding.sort === 'GoalProposition').length ?? 0
  }
  const requestedGoalSorts = [...new Set(graph.query_sorts)]
  if (!requestedGoalSorts.length) {
    unparsedQueryProblems++
    unparsedQueryOrdinals.push(entry.ordinal)
    continue
  }
  parsedQueryProblems++
  querySortDemands += requestedGoalSorts.length
  const terminalMorphismsBySort = Object.fromEntries(requestedGoalSorts.flatMap(sort => {
    const terminals = semanticQueryTerminalMorphisms(generalized.graphs, sort)
    return terminals.length ? [[sort, terminals] as const] : []
  }))
  const enumeration = enumerateTypedTerms(generalized.graphs, {
    maxDepth: 4,
    maxStates: 5_000,
    goalSorts: requestedGoalSorts,
    terminalMorphismsBySort,
  })
  let problemHasTypedQueryProgram = false
  let problemHasExecutableQueryProgram = false
  let executableSortsInProblem = 0
  const obligationsInProblem = new Set<string>()
  for (const requestedSort of requestedGoalSorts) {
    const candidates = enumeration.goals.filter(goal => goal.sort === requestedSort)
    if (!candidates.length) {
      unreachableQueryDemands.push({ ordinal: entry.ordinal, sort: requestedSort })
      const hasGoalBinding = graph.query_bindings?.some(binding =>
        binding.role === 'goal' && binding.sort === 'GoalProposition') ?? false
      const requestedTerminals = terminalMorphismsBySort[requestedSort] ?? []
      for (const frontier of enumeration.frontier.filter(item =>
        item.target === requestedSort &&
        (!requestedTerminals.length || requestedTerminals.includes(item.morphism)))) {
        const missing = frontier.missing.filter(sort => !(sort === 'GoalProposition' && hasGoalBinding))
        for (const sort of missing) {
          const obligation = `${frontier.morphism} requires ${sort}`
          const ordinals = frontierProblemOrdinals.get(obligation) ?? []
          if (!ordinals.includes(entry.ordinal)) ordinals.push(entry.ordinal)
          frontierProblemOrdinals.set(obligation, ordinals)
        }
      }
      queryDemandDiagnostics.push({
        ordinal: entry.ordinal,
        sort: requestedSort,
        typed_candidate_count: 0,
        minimum_unsupported_count: null,
        minimum_depth: null,
        forced_minimal_gaps: [],
        alternative_minimal_gap_sets: [],
      })
      continue
    }
    const candidateSupports = candidates.map(candidate => ({
      candidate,
      unsupported: inspectTypedProgramExecution(candidate.program).unsupported,
    }))
    const minimumUnsupportedCount = Math.min(...candidateSupports.map(item => item.unsupported.length))
    const minimumCandidates = candidateSupports.filter(item =>
      item.unsupported.length === minimumUnsupportedCount)
    const distinctGapSets = [...new Map(minimumCandidates.map(item => {
      const gapSet = [...item.unsupported].sort()
      return [JSON.stringify(gapSet), gapSet] as const
    })).values()]
    const forcedGaps = distinctGapSets.length
      ? distinctGapSets.slice(1).reduce(
          (shared, gapSet) => shared.filter(item => gapSet.includes(item)),
          [...distinctGapSets[0]],
        )
      : []
    const optionalGaps = [...new Set(distinctGapSets.flat())].sort()
    const minimumDepth = Math.min(...minimumCandidates.map(item => item.candidate.depth))
    const demand = { ordinal: entry.ordinal, sort: requestedSort }
    for (const gap of forcedGaps) {
      const demands = forcedMinimalGapDemands.get(gap) ?? []
      demands.push(demand)
      forcedMinimalGapDemands.set(gap, demands)
    }
    for (const gap of optionalGaps) {
      const demands = optionalMinimalGapDemands.get(gap) ?? []
      demands.push(demand)
      optionalMinimalGapDemands.set(gap, demands)
    }
    queryDemandDiagnostics.push({
      ordinal: entry.ordinal,
      sort: requestedSort,
      typed_candidate_count: candidates.length,
      minimum_unsupported_count: minimumUnsupportedCount,
      minimum_depth: minimumDepth,
      forced_minimal_gaps: forcedGaps,
      alternative_minimal_gap_sets: distinctGapSets.slice(0, 16),
    })
    typedReachableQuerySortDemands++
    problemHasTypedQueryProgram = true
    if (candidates.some(goal => inspectTypedProgramExecution(goal.program).executable)) {
      executableQuerySortDemands++
      executableSortsInProblem++
      problemHasExecutableQueryProgram = true
    }
  }
  if (problemHasTypedQueryProgram) problemsWithTypedQueryProgram++
  if (problemHasExecutableQueryProgram) problemsWithExecutableQueryProgram++
  if (executableSortsInProblem === requestedGoalSorts.length) fullyExecutableQueryProblems++
  for (const goal of enumeration.goals) {
    totalGoals++
    const support = inspectTypedProgramExecution(goal.program)
    if (goal.sort === 'Proof') typedProofGoals++
    if (support.executable) executableGoals++
    if (goal.sort === 'Proof' && support.executable) executableProofGoals++
    const preInvariantExecutable = executableWith(goal.program, preInvariantHandlers, polynomialParentOnly)
    const postInvariantExecutable = executableWith(goal.program, postInvariantHandlers, polynomialParentOnly)
    const postMapOrbitExecutable = executableWith(goal.program, postMapOrbitHandlers, currentParentSorts)
    const currentExecutable = executableWith(goal.program, currentHandlers, currentParentSorts)
    if (preInvariantExecutable) preInvariantExecutableGoals++
    if (postInvariantExecutable) postInvariantExecutableGoals++
    if (postMapOrbitExecutable) postMapOrbitExecutableGoals++
    if (!preInvariantExecutable && postInvariantExecutable) invariantNewProblems.add(entry.ordinal)
    if (!postInvariantExecutable && postMapOrbitExecutable) mapOrbitNewProblems.add(entry.ordinal)
    if (!postMapOrbitExecutable && currentExecutable) expressionIrNewProblems.add(entry.ordinal)
    if (support.executable !== currentExecutable) {
      throw new Error(`coverage audit disagrees with runtime inspection for problem ${entry.ordinal}`)
    }
    for (const obligation of support.unsupported) {
      obligationsInProblem.add(obligation)
      const priorDepth = minimumDepth.get(obligation)
      if (priorDepth === undefined || goal.depth < priorDepth) minimumDepth.set(obligation, goal.depth)
    }
  }
  for (const obligation of obligationsInProblem) {
    const ordinals = problemOrdinals.get(obligation) ?? []
    ordinals.push(entry.ordinal)
    problemOrdinals.set(obligation, ordinals)
  }
}

const obligations = [...problemOrdinals.entries()]
  .map(([obligation, ordinals]) => ({
    obligation,
    problem_count: ordinals.length,
    minimum_goal_depth: minimumDepth.get(obligation) ?? null,
    example_ordinals: ordinals.slice(0, 12),
  }))
  .sort((left, right) =>
    right.problem_count - left.problem_count || left.obligation.localeCompare(right.obligation))

const typedFrontierObligations = [...frontierProblemOrdinals.entries()]
  .map(([obligation, ordinals]) => ({
    obligation,
    problem_count: ordinals.length,
    example_ordinals: ordinals.slice(0, 12),
  }))
  .sort((left, right) =>
    right.problem_count - left.problem_count || left.obligation.localeCompare(right.obligation))

function summarizeGapDemands(
  source: ReadonlyMap<string, Array<{ ordinal: number; sort: string }>>,
) {
  return [...source.entries()].map(([obligation, demands]) => ({
    obligation,
    query_demand_count: demands.length,
    problem_count: new Set(demands.map(demand => demand.ordinal)).size,
    examples: demands.slice(0, 12),
  })).sort((left, right) =>
    right.query_demand_count - left.query_demand_count || left.obligation.localeCompare(right.obligation))
}

const forcedMinimalGaps = summarizeGapDemands(forcedMinimalGapDemands)
const optionalMinimalGaps = summarizeGapDemands(optionalMinimalGapDemands)

const report = {
  schema: 'mortra.runtime-primitive-coverage.v5',
  created_at: new Date().toISOString(),
  source: {
    label: catalog.sourceLabel,
    sha256: catalog.sourceSha256,
    problem_count: catalog.entries.length,
  },
  protocol: {
    expected_answers_supplied: false,
    solutions_supplied: false,
    problem_id_branching: false,
    max_depth: 4,
    max_states_per_problem: 5_000,
    aggregation: 'each obligation receives at most one vote per problem',
    goal_selection: 'graph.query_sorts plus the explicit terminal query operation; no default goal-sort or same-codomain fallback',
    proposition_roles_separated: true,
    query_bindings_are_input_terms: false,
    proof_requires_matching_goal_and_certificate_identity: true,
  },
  implemented_handlers: runtimePrimitiveHandlers(),
  implemented_parent_sorts: runtimeParentSorts(),
  summary: {
    total_typed_goals: totalGoals,
    executable_typed_goals: executableGoals,
    executable_goal_rate: totalGoals ? executableGoals / totalGoals : 0,
    concrete_root_bindings: concreteRootBindings,
    assumption_proposition_bindings: assumptionBindings,
    proof_query_problems: proofQueryProblems,
    proof_goal_bindings: proofGoalBindings,
    typed_proof_goals: typedProofGoals,
    executable_proof_goals: executableProofGoals,
    parsed_query_problems: parsedQueryProblems,
    unparsed_query_problems: unparsedQueryProblems,
    unparsed_query_ordinals: unparsedQueryOrdinals,
    query_sort_demands: querySortDemands,
    typed_reachable_query_sort_demands: typedReachableQuerySortDemands,
    executable_query_sort_demands: executableQuerySortDemands,
    problems_with_typed_query_program: problemsWithTypedQueryProgram,
    problems_with_executable_query_program: problemsWithExecutableQueryProgram,
    fully_executable_query_problems: fullyExecutableQueryProblems,
    unreachable_query_sort_demands: unreachableQueryDemands.length,
    baseline_executable_goals_before_trace_norm: preInvariantExecutableGoals,
    executable_goals_after_trace_norm_before_map_orbit: postInvariantExecutableGoals,
    executable_goals_after_map_orbit_before_expression_ir: postMapOrbitExecutableGoals,
    newly_executable_goals_from_trace_norm: postInvariantExecutableGoals - preInvariantExecutableGoals,
    newly_executable_goals_from_map_orbit: postMapOrbitExecutableGoals - postInvariantExecutableGoals,
    newly_executable_goals_from_expression_ir: executableGoals - postMapOrbitExecutableGoals,
    problems_newly_covered_by_trace_norm: invariantNewProblems.size,
    trace_norm_new_problem_ordinals: [...invariantNewProblems].sort((left, right) => left - right),
    problems_newly_covered_by_map_orbit: mapOrbitNewProblems.size,
    map_orbit_new_problem_ordinals: [...mapOrbitNewProblems].sort((left, right) => left - right),
    problems_newly_covered_by_expression_ir: expressionIrNewProblems.size,
    expression_ir_new_problem_ordinals: [...expressionIrNewProblems].sort((left, right) => left - right),
    distinct_open_obligations: obligations.length,
    distinct_typed_frontier_obligations: typedFrontierObligations.length,
    distinct_forced_minimal_gap_obligations: forcedMinimalGaps.length,
    distinct_optional_minimal_gap_obligations: optionalMinimalGaps.length,
  },
  obligations,
  typed_frontier_obligations: typedFrontierObligations,
  forced_minimal_gap_obligations: forcedMinimalGaps,
  optional_minimal_gap_obligations: optionalMinimalGaps,
  query_demand_diagnostics: queryDemandDiagnostics,
  unreachable_query_demands: unreachableQueryDemands,
}

writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
process.stdout.write(`${JSON.stringify({
  outputPath,
  summary: report.summary,
  top_runtime_obligations: obligations.slice(0, 12),
  top_typed_frontier_obligations: typedFrontierObligations.slice(0, 12),
  top_forced_minimal_gap_obligations: forcedMinimalGaps.slice(0, 12),
  top_optional_minimal_gap_obligations: optionalMinimalGaps.slice(0, 12),
}, null, 2)}\n`)
