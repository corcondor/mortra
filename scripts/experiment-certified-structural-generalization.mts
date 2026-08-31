import { readFile, writeFile } from 'node:fs/promises'
import { performance } from 'node:perf_hooks'
import { relative, resolve } from 'node:path'

import { certifiedFusionKind } from '../lib/mortra/certified-fusion-kind.js'
import {
  elaborateCertifiedFusionParent,
  listCertifiedFusionChartSignatures,
  planCertifiedFusions,
} from '../lib/mortra/certified-fusion-planner.js'
import { attachCertifiedGenerationAudit } from '../lib/mortra/certified-problem-generation-audit.js'
import type { CertifiedFusionCard, CertifiedFusionParent } from '../lib/mortra/certified-fusion.js'

type CatalogEntry = {
  id: string
  ordinal: number
  label: string
  statement: string
  answerTex?: string | null
  solutionTex?: string | null
  certificate?: CertifiedFusionParent['certificate']
}

type EligibleGroup = {
  key: string
  parentIds: string[]
  chartIds: Set<string>
}

type AuditedInstance = {
  configurationKey: string
  card: CertifiedFusionCard
}

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}

function sortedKey(values: string[]): string {
  return [...values].sort().join('\u0000')
}

function countBy(values: string[]): Record<string, number> {
  const counts = new Map<string, number>()
  for (const value of values) counts.set(value, (counts.get(value) ?? 0) + 1)
  return Object.fromEntries([...counts].sort(([left], [right]) => left.localeCompare(right)))
}

function repositoryPath(filePath: string): string {
  const path = relative(process.cwd(), filePath)
  return (path && !path.startsWith('..') ? path : filePath).replaceAll('\\', '/')
}

function asParent(entry: CatalogEntry): CertifiedFusionParent {
  return {
    id: entry.id,
    statement: entry.statement,
    answer: entry.answerTex,
    solution: entry.solutionTex,
    certificate: entry.certificate ?? null,
  }
}

function sameParentSet(card: CertifiedFusionCard, parentIds: string[]): boolean {
  return sortedKey(card.parent_ids) === sortedKey(parentIds)
}

function enumerateEligibleGroups(
  entries: CatalogEntry[],
): Map<string, EligibleGroup> {
  const endpointsByKind = new Map<string, Set<string>>()
  for (const entry of entries) {
    for (const endpoint of elaborateCertifiedFusionParent(asParent(entry))) {
      const ids = endpointsByKind.get(endpoint.kind) ?? new Set<string>()
      ids.add(entry.id)
      endpointsByKind.set(endpoint.kind, ids)
    }
  }

  const groups = new Map<string, EligibleGroup>()
  for (const chart of listCertifiedFusionChartSignatures().filter(chart => chart.outputKind === 'structural')) {
    const candidates = chart.inputKinds.map(kind => [...(endpointsByKind.get(kind) ?? [])])
    if (candidates.some(values => values.length === 0)) continue

    const visit = (position: number, selected: string[]) => {
      if (position === candidates.length) {
        const parentIds = [...selected].sort()
        const key = sortedKey(parentIds)
        const existing = groups.get(key) ?? { key, parentIds, chartIds: new Set<string>() }
        existing.chartIds.add(chart.id)
        groups.set(key, existing)
        return
      }
      for (const parentId of candidates[position]) {
        if (selected.includes(parentId)) continue
        selected.push(parentId)
        visit(position + 1, selected)
        selected.pop()
      }
    }
    visit(0, [])
  }
  return groups
}

function summarizeCard(card: CertifiedFusionCard, configurationKeys: string[]) {
  return {
    cardId: card.id,
    family: card.family_id,
    domain: card.domain,
    kernel: card.structure_blueprint.kernel,
    observable: card.structure_blueprint.observable,
    querySignature: card.structure_blueprint.structuralUniqueness.querySignature,
    parentIds: card.parent_ids,
    parentCount: card.parent_ids.length,
    sourceConfigurationKeys: configurationKeys,
    statement: card.statement_tex,
    answer: card.answer_tex,
    solution: card.solution_tex,
    morphismChain: card.morphism_chain,
    exactBackend: card.verification.exact_backend,
    independentCheck: card.verification.independent_check,
    auditPassed: card.generation_audit?.passed === true,
    auditFailures: card.generation_audit?.failures ?? [],
    proofStepCount: card.generation_audit?.proofStepCount ?? card.morphism_chain.length,
  }
}

const startedAt = performance.now()
const catalogPath = resolve(
  argument('--catalog') ?? 'artifacts/benchmarks/fullproblem-certified-catalog-20260831.json',
)
const baselinePath = resolve(
  argument('--baseline') ?? 'artifacts/benchmarks/certified-difficult-problem-generation-20260901.json',
)
const outputPath = resolve(
  argument('--out') ?? 'artifacts/benchmarks/certified-structural-generalization-20260901.json',
)
const perConfigurationLimit = Number(argument('--per-configuration-limit') ?? '256')
if (!Number.isInteger(perConfigurationLimit) || perConfigurationLimit < 1) {
  throw new Error('--per-configuration-limit must be a positive integer')
}

const catalog = JSON.parse(await readFile(catalogPath, 'utf8')) as { entries: CatalogEntry[] }
const baseline = JSON.parse(await readFile(baselinePath, 'utf8')) as {
  candidateCount: number
  distinctStatementCount: number
  distinctQuestionFormCount: number
  familyCounts: Record<string, number>
  candidates: Array<{ parents: Array<{ id: string }> }>
}
const entries = catalog.entries
const entryById = new Map(entries.map(entry => [entry.id, entry]))
const eligibleGroups = enumerateEligibleGroups(entries)
const rawInstances: AuditedInstance[] = []
const passedInstances: AuditedInstance[] = []
const groupReports: Array<{
  key: string
  parentIds: string[]
  parentLabels: string[]
  parentCount: number
  eligibleChartIds: string[]
  plannerAttemptCount: number
  plannerAttempts: Array<{ chartId: string; produced: number }>
  rawCardCount: number
  passedCardCount: number
  rejectedCardCount: number
}> = []

for (const group of eligibleGroups.values()) {
  const parents = group.parentIds
    .map(parentId => entryById.get(parentId))
    .filter((entry): entry is CatalogEntry => Boolean(entry))
    .map(asParent)
  const plan = planCertifiedFusions(parents, perConfigurationLimit)
  const rawCards = plan.cards
    .filter(card => sameParentSet(card, group.parentIds))
    .filter(card => certifiedFusionKind(card.family_id) === 'structural')
    .map(card => attachCertifiedGenerationAudit(card, parents))
  const passedCards = rawCards.filter(card => card.generation_audit?.passed)
  const relevantAttempts = plan.attempts.filter(attempt => sortedKey(attempt.parentIds) === group.key)
  rawInstances.push(...rawCards.map(card => ({ configurationKey: group.key, card })))
  passedInstances.push(...passedCards.map(card => ({ configurationKey: group.key, card })))
  groupReports.push({
    key: group.key,
    parentIds: group.parentIds,
    parentLabels: group.parentIds.map(parentId => entryById.get(parentId)?.label ?? parentId),
    parentCount: group.parentIds.length,
    eligibleChartIds: [...group.chartIds].sort(),
    plannerAttemptCount: relevantAttempts.length,
    plannerAttempts: relevantAttempts.map(attempt => ({
      chartId: attempt.chartId,
      produced: attempt.produced,
    })),
    rawCardCount: rawCards.length,
    passedCardCount: passedCards.length,
    rejectedCardCount: rawCards.length - passedCards.length,
  })
}

const configurationsByCard = new Map<string, Set<string>>()
const representativeByCard = new Map<string, CertifiedFusionCard>()
for (const instance of passedInstances) {
  const configurations = configurationsByCard.get(instance.card.id) ?? new Set<string>()
  configurations.add(instance.configurationKey)
  configurationsByCard.set(instance.card.id, configurations)
  representativeByCard.set(instance.card.id, instance.card)
}

const observablesByKernelInstance = new Map<string, Set<string>>()
for (const instance of passedInstances) {
  const key = `${instance.configurationKey}\u0001${instance.card.structure_blueprint.kernel}`
  const observables = observablesByKernelInstance.get(key) ?? new Set<string>()
  observables.add(instance.card.structure_blueprint.observable)
  observablesByKernelInstance.set(key, observables)
}
const kernelInstances = [...observablesByKernelInstance].map(([key, observables]) => ({
  key,
  observableCount: observables.size,
  observables: [...observables].sort(),
}))
const oneToManyKernelInstances = kernelInstances.filter(item => item.observableCount >= 2)
const uniqueCards = [...representativeByCard.values()]
const productiveGroups = groupReports.filter(group => group.passedCardCount > 0)
const rejectedInstances = rawInstances.filter(instance => !instance.card.generation_audit?.passed)
const baselineParentConfigurationCount = new Set(
  baseline.candidates.map(candidate => sortedKey(candidate.parents.map(parent => parent.id))),
).size
const morphismVocabulary = [...new Set(uniqueCards.flatMap(card => card.morphism_chain))].sort()
const chartResults = listCertifiedFusionChartSignatures()
  .filter(chart => chart.outputKind === 'structural')
  .map(chart => {
    const eligible = groupReports.filter(group => group.eligibleChartIds.includes(chart.id))
    const attempts = groupReports.flatMap(group =>
      group.plannerAttempts.filter(attempt => attempt.chartId === chart.id),
    )
    return {
      chartId: chart.id,
      parentCardinality: chart.inputKinds.length,
      eligibleParentConfigurationCount: eligible.length,
      productiveParentConfigurationCount: attempts.filter(attempt => attempt.produced > 0).length,
      producedCardCountBeforeAudit: attempts.reduce((sum, attempt) => sum + attempt.produced, 0),
    }
  })

const controlledCircleParents: CertifiedFusionParent[] = [
  { id: 'fixture-circle-a', statement: '円 $x^2+y^2-6x+4y-3=0$ を考える。' },
  { id: 'fixture-circle-b', statement: '円 $2x^2+2y^2+4x-8y-10=0$ を考える。' },
]
const controlledCircleCards = planCertifiedFusions(controlledCircleParents, perConfigurationLimit).cards
  .filter(card => sameParentSet(card, controlledCircleParents.map(parent => parent.id)))
  .map(card => attachCertifiedGenerationAudit(card, controlledCircleParents))
const controlledFixtures = [{
  id: 'affine-circle-pair-one-to-many',
  reason: '全問題90問には、二つのアフィン円方程式を同時に含む親配置がないため、円幾何の同一核・複数問だけを固定入力で検証した',
  parentCount: controlledCircleParents.length,
  generatedCardCount: controlledCircleCards.length,
  passedCardCount: controlledCircleCards.filter(card => card.generation_audit?.passed).length,
  kernels: [...new Set(controlledCircleCards.map(card => card.structure_blueprint.kernel))],
  observables: [...new Set(controlledCircleCards.map(card => card.structure_blueprint.observable))],
  cards: controlledCircleCards.map(card => summarizeCard(card, ['controlled:affine-circle-pair'])),
}]

const report = {
  schema: 1,
  measuredAt: new Date().toISOString(),
  purpose: '少数の再利用可能な射が、一つの証明核から複数の問いと三親以上の問題を厳密に生成できるかを測る',
  definitions: {
    parentConfiguration: '生成に同時使用した相異なる親問題の集合',
    proofKernel: '数値や問い方が変わっても共有される実行可能な中間表現と証明手続き',
    observable: '同じ検証済み証明核から問題として読み出す量または命題',
    card: '問題文、厳密解、解説、証明書を一体にした一つの出力',
  },
  method: {
    catalogPath: repositoryPath(catalogPath),
    baselinePath: repositoryPath(baselinePath),
    catalogProblemCount: entries.length,
    untypedPairPopulationCount: entries.length * (entries.length - 1) / 2,
    eligibleGroupSelection: '型付き入力端点が既存の生成チャートを満たす親問題集合だけを列挙した',
    perConfigurationLimit,
    acceptance: '厳密計算、独立検算、全親依存、親をまたぐ合成、前提最小性、逆再生拒否をすべて監査した',
    aggregateScoreUsed: false,
  },
  baseline: {
    cardCount: baseline.candidateCount,
    distinctStatementCount: baseline.distinctStatementCount,
    distinctQuestionFormCount: baseline.distinctQuestionFormCount,
    familyIdCount: Object.keys(baseline.familyCounts).length,
    parentConfigurationCount: baselineParentConfigurationCount,
  },
  result: {
    eligibleParentConfigurationCount: groupReports.length,
    eligibleParentConfigurationCountsByCardinality: countBy(groupReports.map(group => String(group.parentCount))),
    productiveParentConfigurationCount: productiveGroups.length,
    productiveParentConfigurationCountsByCardinality: countBy(productiveGroups.map(group => String(group.parentCount))),
    abstainedParentConfigurationCount: groupReports.length - productiveGroups.length,
    rawCardInstanceCount: rawInstances.length,
    passedCardInstanceCount: passedInstances.length,
    rejectedCardInstanceCount: rejectedInstances.length,
    allProducedCardsPassedAudit: rejectedInstances.length === 0,
    uniqueCardCount: uniqueCards.length,
    uniqueStatementCount: new Set(uniqueCards.map(card => card.statement_tex)).size,
    proofKernelCount: new Set(uniqueCards.map(card => card.structure_blueprint.kernel)).size,
    observableCount: new Set(uniqueCards.map(card => card.structure_blueprint.observable)).size,
    familyIdCount: new Set(uniqueCards.map(card => card.family_id)).size,
    morphismVocabularyCount: morphismVocabulary.length,
    proofKernelInstanceCount: kernelInstances.length,
    oneToManyProofKernelInstanceCount: oneToManyKernelInstances.length,
    maximumObservablesFromOneProofKernelInstance: Math.max(0, ...kernelInstances.map(item => item.observableCount)),
    cardInstanceCountsByParentCardinality: countBy(passedInstances.map(instance => String(instance.card.parent_ids.length))),
    familyCounts: countBy(passedInstances.map(instance => instance.card.family_id)),
    kernelCounts: countBy(passedInstances.map(instance => instance.card.structure_blueprint.kernel)),
    observableCounts: countBy(passedInstances.map(instance => instance.card.structure_blueprint.observable)),
  },
  morphismVocabulary,
  chartResults,
  controlledFixtures,
  oneToManyProofKernelInstances: oneToManyKernelInstances
    .sort((left, right) => right.observableCount - left.observableCount || left.key.localeCompare(right.key)),
  rejectedCards: rejectedInstances.map(instance => ({
    configurationKey: instance.configurationKey,
    cardId: instance.card.id,
    failures: instance.card.generation_audit?.failures ?? [],
  })),
  parentConfigurations: groupReports,
  cards: uniqueCards.map(card => summarizeCard(
    card,
    [...(configurationsByCard.get(card.id) ?? [])].sort(),
  )),
  elapsedMs: Math.round(performance.now() - startedAt),
}

await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
process.stdout.write(`${JSON.stringify({ outputPath, ...report.result, elapsedMs: report.elapsedMs }, null, 2)}\n`)
