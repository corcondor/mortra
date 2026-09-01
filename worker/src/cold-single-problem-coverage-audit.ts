import { readFileSync, writeFileSync } from 'node:fs'
import path from 'node:path'

import { synthesizeExactCasSingleProblemBatch } from './single-problem-cas'

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

function increment(counts: Map<string, number>, value: unknown): void {
  const key = typeof value === 'string' && value ? value : 'none'
  counts.set(key, (counts.get(key) ?? 0) + 1)
}

const root = path.resolve(__dirname, '..', '..')
const inputPath = path.resolve(
  root,
  process.argv[2] ?? 'artifacts/benchmarks/fullproblem-certified-catalog-20260831.json',
)
const outputPath = path.resolve(
  root,
  process.argv[3] ?? 'artifacts/benchmarks/cold-single-problem-coverage-20260901.json',
)
const catalog = JSON.parse(readFileSync(inputPath, 'utf8')) as Catalog
const parents = catalog.entries.map(entry => ({
  id: entry.id,
  statement: entry.statement,
  answer: null,
  solution: null,
}))

const startedAt = Date.now()
const results = synthesizeExactCasSingleProblemBatch(parents)
const originCounts = new Map<string, number>()
const familyCounts = new Map<string, number>()
const failureCodeCounts = new Map<string, number>()
const failureDomainCounts = new Map<string, number>()
const operationKindCounts = new Map<string, number>()
const attemptedToolCounts = new Map<string, number>()
const toolErrorCounts = new Map<string, number>()
let certified = 0
let registryIndependent = 0
let registeredCompositeReuse = 0

const rows = results.map((result, index) => {
  const entry = catalog.entries[index]
  const card = result.cards[0]
  const certificate = card?.execution_certificate ?? {}
  const origin = certificate.capability_origin
  const registered = certificate.registered_composite_used === true ||
    origin === 'registered_parameterized_morphism'
  const diagnostics = result.diagnostics ?? null
  if (card) {
    certified++
    increment(originCounts, origin)
    increment(familyCounts, card.family_id)
    if (registered) registeredCompositeReuse++
    else registryIndependent++
  } else if (diagnostics) {
    increment(failureCodeCounts, diagnostics.failure_code)
    increment(failureDomainCounts, diagnostics.domain)
    const operations = Array.isArray(diagnostics.operations) ? diagnostics.operations : []
    const operationKinds = new Set(
      operations
        .map(item => item && typeof item === 'object' ? (item as Record<string, unknown>).kind : null)
        .filter((item): item is string => typeof item === 'string' && item.length > 0),
    )
    for (const kind of operationKinds) increment(operationKindCounts, kind)
    const toolAttempts = Array.isArray(diagnostics.tool_attempts) ? diagnostics.tool_attempts : []
    for (const item of toolAttempts) {
      if (!item || typeof item !== 'object') continue
      const attempt = item as Record<string, unknown>
      increment(attemptedToolCounts, attempt.name)
      const error = attempt.error || attempt.result_error
      if (typeof error === 'string' && error) increment(toolErrorCounts, error)
    }
  }
  return {
    ordinal: entry.ordinal,
    id: entry.id,
    label: entry.label,
    certified: Boolean(card),
    registry_independent: Boolean(card) && !registered,
    capability_origin: typeof origin === 'string' ? origin : null,
    registered_composite_used: registered,
    family_id: card?.family_id ?? null,
    domain: card?.domain ?? null,
    answer_tex: card?.answer_tex ?? null,
    morphism_chain: card?.morphism_chain ?? [],
    certificate_sha256: typeof certificate.answer_tex_sha256 === 'string'
      ? certificate.answer_tex_sha256
      : null,
    reason: result.reason,
    diagnostics,
  }
})

const report = {
  schema: 'mortra.cold-single-problem-coverage.v2',
  created_at: new Date().toISOString(),
  source: {
    label: catalog.sourceLabel,
    sha256: catalog.sourceSha256,
    problem_count: catalog.entries.length,
  },
  protocol: {
    expected_answers_supplied: false,
    solutions_supplied: false,
    external_llm_used: false,
    theorem_kernels_allowed: false,
    registered_composite_reuse_counted_as_cold_synthesis: false,
    success_requires_exact_backend: true,
    success_requires_independent_replay: true,
    success_requires_statement_and_answer_hashes: true,
  },
  summary: {
    certified_problems: certified,
    registry_independent_certified_problems: registryIndependent,
    registered_composite_reuse_problems: registeredCompositeReuse,
    unresolved_problems: catalog.entries.length - certified,
    registry_independent_rate: catalog.entries.length
      ? registryIndependent / catalog.entries.length
      : 0,
    elapsed_ms: Date.now() - startedAt,
    capability_origin_counts: Object.fromEntries([...originCounts].sort()),
    family_counts: Object.fromEntries([...familyCounts].sort()),
    failure_code_counts: Object.fromEntries([...failureCodeCounts].sort()),
    failure_domain_counts: Object.fromEntries([...failureDomainCounts].sort()),
    unresolved_operation_kind_counts: Object.fromEntries([...operationKindCounts].sort()),
    attempted_tool_counts: Object.fromEntries([...attemptedToolCounts].sort()),
    tool_error_counts: Object.fromEntries([...toolErrorCounts].sort()),
  },
  rows,
}

writeFileSync(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
process.stdout.write(`${JSON.stringify({ outputPath, summary: report.summary }, null, 2)}\n`)
