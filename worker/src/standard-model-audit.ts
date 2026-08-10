import { readFileSync, writeFileSync } from 'node:fs'
import {
  buildSemanticHypergraph,
  executableMorphismAtlas,
  type HyperMorphismSchema,
} from './generalization-kernel'
import {
  EXECUTION_SERVICES,
  JUDGMENT_KINDS,
  OBJECT_CONSTRUCTORS,
  STRUCTURAL_PRIMITIVES,
  distinctDeclaredContracts,
  lowerMorphismToKnowledgeCore,
  morphismDeclaredContractKey,
} from './kernel-calculus'

export type AuditProblem = { id: string; statement: string; benchmark?: string }

export type StandardModelAudit = {
  corpus: {
    total: number
    with_query: number
    without_query: number
    with_opaque_root: number
    kernel_ready: number
    kernel_ready_ids: string[]
    parse_truncated: number
    structural_signatures: number
    root_sort_counts: Record<string, number>
    query_sort_counts: Record<string, number>
    constraint_operator_counts: Record<string, number>
    detected_operator_counts: Record<string, number>
    structural_signature_counts: Record<string, number>
    by_benchmark: Record<string, {
      total: number
      with_query: number
      with_opaque_root: number
      kernel_ready: number
    }>
  }
  atlas: {
    named_morphisms: number
    declared_contracts: number
    contract_collisions: number
    sorts: number
    object_constructors: number
    structural_primitives: number
    judgment_kinds: number
    execution_services: number
    declaration_to_object_constructor_ratio: number
    law_signatures: number
    backend_signatures: number
    object_constructor_use: Record<string, number>
    contract_collision_groups: string[][]
  }
}

function increment(counts: Map<string, number>, key: string): void {
  counts.set(key, (counts.get(key) ?? 0) + 1)
}

function record(counts: Map<string, number>): Record<string, number> {
  return Object.fromEntries([...counts].sort((left, right) =>
    right[1] - left[1] || left[0].localeCompare(right[0]),
  ))
}

function topRecord(counts: Map<string, number>, limit = 40): Record<string, number> {
  return Object.fromEntries(Object.entries(record(counts)).slice(0, limit))
}

function normalizedRootSort(sort: string): string {
  return sort.startsWith('OpaqueSort[') ? 'OpaqueSort' : sort
}

function duplicateGroups(rules: readonly HyperMorphismSchema[]): string[][] {
  const groups = new Map<string, string[]>()
  for (const rule of rules) {
    const key = morphismDeclaredContractKey(rule)
    groups.set(key, [...(groups.get(key) ?? []), rule.name])
  }
  return [...groups.values()].filter(group => group.length > 1)
}

export function auditStandardModel(problems: readonly AuditProblem[]): StandardModelAudit {
  const rules = executableMorphismAtlas()
  const contractRepresentatives = distinctDeclaredContracts(rules)
  const constructors = new Map<string, number>()
  const sorts = new Set<string>()
  const lawSignatures = new Set<string>()
  const backendSignatures = new Set<string>()
  for (const rule of contractRepresentatives) {
    rule.sources.forEach(sort => sorts.add(sort))
    sorts.add(rule.target)
    const lowering = lowerMorphismToKnowledgeCore(rule)
    increment(constructors, lowering.application.constructor)
    increment(constructors, lowering.application.operator.constructor)
    lowering.declaration.parameters.forEach(() => increment(constructors, 'variable-reference'))
    lowering.declaration.parameters.forEach(parameter => increment(constructors, parameter.type.constructor))
    increment(constructors, lowering.declaration.result.constructor)
    lawSignatures.add(JSON.stringify(lowering.preservation_obligations))
    backendSignatures.add(JSON.stringify(lowering.implementation_hints))
  }

  const rootSorts = new Map<string, number>()
  const querySorts = new Map<string, number>()
  const constraints = new Map<string, number>()
  const operators = new Map<string, number>()
  const signatures = new Map<string, number>()
  const byBenchmark = new Map<string, { total: number; with_query: number; with_opaque_root: number; kernel_ready: number }>()
  let withQuery = 0
  let opaque = 0
  let kernelReady = 0
  const kernelReadyIds: string[] = []
  let truncated = 0

  for (const problem of problems) {
    const graph = buildSemanticHypergraph({ id: problem.id, statement: problem.statement })
    const hasQuery = graph.query_sorts.length > 0
    const hasOpaqueRoot = graph.root_sorts.some(sort => sort.startsWith('OpaqueSort['))
    const ready = hasQuery && !hasOpaqueRoot
    if (hasQuery) withQuery++
    if (hasOpaqueRoot) opaque++
    if (ready) {
      kernelReady++
      kernelReadyIds.push(problem.id)
    }
    if (graph.language_analysis.parse_truncated) truncated++
    graph.root_sorts.forEach(sort => increment(rootSorts, normalizedRootSort(sort)))
    graph.query_sorts.forEach(sort => increment(querySorts, sort))
    graph.language_analysis.constraints.forEach(item => increment(constraints, item.operator))
    graph.nodes.filter(node => node.role === 'operator').forEach(node => increment(operators, node.canonical))
    const signature = JSON.stringify({
      roots: [...new Set(graph.root_sorts.map(normalizedRootSort))].sort(),
      queries: [...new Set(graph.query_sorts)].sort(),
      relations: graph.language_analysis.constraints.map(item => item.operator).sort(),
      operators: graph.nodes.filter(node => node.role === 'operator').map(node => node.canonical).sort(),
    })
    increment(signatures, signature)
    const benchmark = problem.benchmark ?? 'unknown'
    const benchmarkRow = byBenchmark.get(benchmark) ?? { total: 0, with_query: 0, with_opaque_root: 0, kernel_ready: 0 }
    benchmarkRow.total++
    if (hasQuery) benchmarkRow.with_query++
    if (hasOpaqueRoot) benchmarkRow.with_opaque_root++
    if (ready) benchmarkRow.kernel_ready++
    byBenchmark.set(benchmark, benchmarkRow)
  }

  return {
    corpus: {
      total: problems.length,
      with_query: withQuery,
      without_query: problems.length - withQuery,
      with_opaque_root: opaque,
      kernel_ready: kernelReady,
      kernel_ready_ids: kernelReadyIds,
      parse_truncated: truncated,
      structural_signatures: signatures.size,
      root_sort_counts: record(rootSorts),
      query_sort_counts: record(querySorts),
      constraint_operator_counts: record(constraints),
      detected_operator_counts: record(operators),
      structural_signature_counts: topRecord(signatures),
      by_benchmark: Object.fromEntries([...byBenchmark].sort(([left], [right]) => left.localeCompare(right))),
    },
    atlas: {
      named_morphisms: rules.length,
      declared_contracts: contractRepresentatives.length,
      contract_collisions: rules.length - contractRepresentatives.length,
      sorts: sorts.size,
      object_constructors: OBJECT_CONSTRUCTORS.length,
      structural_primitives: STRUCTURAL_PRIMITIVES.length,
      judgment_kinds: JUDGMENT_KINDS.length,
      execution_services: EXECUTION_SERVICES.length,
      declaration_to_object_constructor_ratio: Number((rules.length / OBJECT_CONSTRUCTORS.length).toFixed(3)),
      law_signatures: lawSignatures.size,
      backend_signatures: backendSignatures.size,
      object_constructor_use: record(constructors),
      contract_collision_groups: duplicateGroups(rules),
    },
  }
}

function main(): void {
  const input = process.argv[2]
  if (!input) throw new Error('usage: standard-model-audit <problems.jsonl> [output.json]')
  const problems = readFileSync(input, 'utf8').split(/\r?\n/).filter(Boolean).map(line => JSON.parse(line) as AuditProblem)
  const result = auditStandardModel(problems)
  const rendered = `${JSON.stringify(result, null, 2)}\n`
  if (process.argv[3]) writeFileSync(process.argv[3], rendered, 'utf8')
  else process.stdout.write(rendered)
}

if (process.argv[1]?.replaceAll('\\', '/').endsWith('/standard-model-audit.ts')) main()
