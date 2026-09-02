import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'

type JsonRecord = Record<string, unknown>

type Candidate = JsonRecord & {
  id: string
  caseId: string
  sourceReport: string
  statement: string
  answer: string
  solution: string
  difficulty: number
  corpusSurfaceNovelty: number
  taskAlgebraFingerprint: string
  taskAlgebraOrigin: string
}

function records(value: unknown): JsonRecord[] {
  return Array.isArray(value)
    ? value.filter((item): item is JsonRecord => Boolean(item) && typeof item === 'object' && !Array.isArray(item))
    : []
}

function text(value: unknown): string {
  return typeof value === 'string' ? value.trim() : ''
}

function number(value: unknown): number {
  return typeof value === 'number' && Number.isFinite(value) ? value : 0
}

function flagValues(name: string): string[] {
  const values: string[] = []
  for (let index = 0; index < process.argv.length; index += 1) {
    if (process.argv[index] === name && process.argv[index + 1]) values.push(process.argv[index + 1])
  }
  return values
}

function flagValue(name: string): string | undefined {
  return flagValues(name).at(-1)
}

function candidatesFrom(report: JsonRecord, sourceReport: string): Candidate[] {
  const result: Candidate[] = []
  const seen = new Set<string>()
  const append = (card: JsonRecord, caseId: string) => {
    const id = text(card.id)
    if (!id || seen.has(id)) return
    seen.add(id)
    result.push({
      ...card,
      id,
      caseId,
      sourceReport,
      statement: text(card.statement),
      answer: text(card.answer),
      solution: text(card.solution),
      difficulty: number(card.difficulty),
      corpusSurfaceNovelty: number(card.corpusSurfaceNovelty),
      taskAlgebraFingerprint: text(card.taskAlgebraFingerprint),
      taskAlgebraOrigin: text(card.taskAlgebraOrigin),
    })
  }

  for (const probe of records(report.cases)) {
    const caseId = text(probe.id) || 'unlabelled-case'
    for (const card of records(probe.cards)) append(card, caseId)
  }

  if (report.selected && typeof report.selected === 'object' && !Array.isArray(report.selected)) {
    append(report.selected as JsonRecord, text(report.selectedCardId) || 'selected-card')
  }
  return result
}

function taskPrimitives(candidate: Candidate): string[] {
  const blueprint = candidate.structureBlueprint
  if (!blueprint || typeof blueprint !== 'object' || Array.isArray(blueprint)) return []
  const taskAlgebra = (blueprint as JsonRecord).taskAlgebra
  if (!taskAlgebra || typeof taskAlgebra !== 'object' || Array.isArray(taskAlgebra)) return []
  return records((taskAlgebra as JsonRecord).operations)
    .map(operation => text(operation.operator))
    .filter(Boolean)
}

function rejectionReasons(candidate: Candidate, minimumDifficulty: number): string[] {
  const reasons: string[] = []
  if (candidate.taskAlgebraOrigin !== 'emitted') reasons.push('task-program-not-emitted')
  if (!candidate.taskAlgebraFingerprint) reasons.push('missing-task-program-fingerprint')
  if (candidate.exactBackend !== true) reasons.push('missing-exact-backend')
  if (candidate.independentCheck !== true) reasons.push('missing-independent-check')
  if (candidate.completeParentProof !== true) reasons.push('missing-parent-dependence-proof')
  if (candidate.registeredCompositeUsed !== false) reasons.push('registered-composite-used-or-unknown')
  if (candidate.hasDiagram !== true) reasons.push('missing-diagram')
  if (!candidate.statement || !candidate.answer || !candidate.solution) reasons.push('incomplete-publication-content')
  if (candidate.difficulty < minimumDifficulty) reasons.push('below-minimum-difficulty')
  return reasons
}

const defaultReports = [
  'artifacts/benchmarks/certified-social-problem-search-20260903.json',
  'artifacts/benchmarks/runtime-structural-probes-20260903-task-algebra.json',
]
const reportPaths = (flagValues('--report').length ? flagValues('--report') : defaultReports)
  .map(value => resolve(value))
const outputPath = resolve(flagValue('--out') ?? 'artifacts/social/mortra-certified-social-queue-20260903.json')
const maximum = Math.max(1, Number.parseInt(flagValue('--max') ?? '6', 10))
const minimumDifficulty = Math.max(0, Number.parseFloat(flagValue('--min-difficulty') ?? '8'))

const allCandidates: Candidate[] = []
for (const reportPath of reportPaths) {
  const report = JSON.parse(await readFile(reportPath, 'utf8')) as JsonRecord
  allCandidates.push(...candidatesFrom(report, reportPath))
}

const rejectedCounts: Record<string, number> = {}
const eligible = allCandidates.filter(candidate => {
  const reasons = rejectionReasons(candidate, minimumDifficulty)
  for (const reason of reasons) rejectedCounts[reason] = (rejectedCounts[reason] ?? 0) + 1
  return reasons.length === 0
})

eligible.sort((left, right) =>
  right.difficulty - left.difficulty
  || right.corpusSurfaceNovelty - left.corpusSurfaceNovelty
  || left.id.localeCompare(right.id),
)

// One representative per typed question program. Numeric mutations and wording
// variants cannot occupy multiple publication slots.
const selected: Candidate[] = []
const selectedPrograms = new Set<string>()
for (const candidate of eligible) {
  if (selectedPrograms.has(candidate.taskAlgebraFingerprint)) continue
  selectedPrograms.add(candidate.taskAlgebraFingerprint)
  selected.push(candidate)
  if (selected.length >= maximum) break
}

if (!selected.length) throw new Error('no directly emitted, independently verified publication candidate was found')

const primitives = [...new Set(selected.flatMap(taskPrimitives))].sort()
const report = {
  schema: 1,
  measuredAt: new Date().toISOString(),
  purpose: 'Select structurally distinct MORTRA-generated problems for public release.',
  method: {
    unit: 'typed task program',
    deduplication: 'one card per taskAlgebraFingerprint',
    minimumDifficulty,
    maximum,
    required: [
      'engine-emitted typed task program',
      'exact backend certificate',
      'independent answer check',
      'two-parent dependence proof when applicable',
      'generated diagram and complete solution',
      'no registered composite template',
    ],
  },
  inputReports: reportPaths,
  candidateCount: allCandidates.length,
  eligibleCount: eligible.length,
  rejectedCounts,
  selectedCount: selected.length,
  selectedTaskAlgebraCount: selectedPrograms.size,
  taskPrimitiveCount: primitives.length,
  taskPrimitives: primitives,
  cases: selected.map((candidate, index) => ({
    id: `publication-${String(index + 1).padStart(2, '0')}`,
    sourceReport: candidate.sourceReport,
    sourceCaseId: candidate.caseId,
    cards: [{
      ...candidate,
      publicationRank: index + 1,
      publicationState: 'awaiting-action-time-confirmation',
    }],
  })),
}

await mkdir(dirname(outputPath), { recursive: true })
await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
console.log(JSON.stringify({
  outputPath,
  candidateCount: report.candidateCount,
  eligibleCount: report.eligibleCount,
  selectedCount: report.selectedCount,
  selectedTaskAlgebraCount: report.selectedTaskAlgebraCount,
  taskPrimitiveCount: report.taskPrimitiveCount,
  selected: selected.map(candidate => ({
    id: candidate.id,
    family: candidate.family,
    domain: candidate.domain,
    difficulty: candidate.difficulty,
    taskAlgebraFingerprint: candidate.taskAlgebraFingerprint,
  })),
}, null, 2))
