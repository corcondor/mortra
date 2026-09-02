import { mkdir, readFile, writeFile } from 'node:fs/promises'
import { dirname, resolve } from 'node:path'

import { problemStructureFingerprints } from '../lib/mortra/problem-structure-normal-form.js'
import { hasCompleteParentProof } from '../worker/src/autonomous-synthesis.js'
import { capabilityOrigin } from '../worker/src/execution-certificate.js'
import type { ExecutableFusionCard } from '../worker/src/executable-fusion.js'
import type { DiscoveryParent } from '../worker/src/parent-conditioned-discovery.js'
import { synthesizePolynomialPairMapFusions } from '../worker/src/polynomial-root-fusion.js'
import { auditPublicationContent } from '../worker/src/publication-content-audit.js'
import { replayCardEvidence, type CardReplayEvidence } from '../worker/src/research-evidence-envelope.js'

type Cubic = { linear: number; constant: number }

type Candidate = {
  card: ExecutableFusionCard
  parents: DiscoveryParent[]
  replay: CardReplayEvidence
  mapId: string
  resultDegree: number
  termCount: number
  maximumCoefficient: number
  answerLength: number
  corpusSurfaceNovelty: number
  taskFingerprint: string
  taskAlgebraFingerprint: string
  coreAlgebraFingerprint: string
}

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}

function canonical(source: string): string {
  return source.normalize('NFKC').toLowerCase().replace(/\s+/g, '')
}

function ngrams(source: string, size = 3): Set<string> {
  const value = canonical(source)
  const result = new Set<string>()
  for (let index = 0; index + size <= value.length; index += 1) {
    result.add(value.slice(index, index + size))
  }
  return result
}

function jaccard(left: Set<string>, right: Set<string>): number {
  let overlap = 0
  for (const value of left) if (right.has(value)) overlap += 1
  const union = left.size + right.size - overlap
  return union ? overlap / union : 0
}

function variableTerm(coefficient: number): string {
  if (!coefficient) return ''
  const sign = coefficient > 0 ? '+' : '-'
  const magnitude = Math.abs(coefficient)
  return `${sign}${magnitude === 1 ? '' : magnitude}x`
}

function cubicTex(cubic: Cubic): string {
  const constant = cubic.constant > 0 ? `+${cubic.constant}` : String(cubic.constant)
  return `x^3${variableTerm(cubic.linear)}${constant}`
}

function hasIntegerRoot(cubic: Cubic): boolean {
  const bound = Math.abs(cubic.constant)
  for (let root = -bound; root <= bound; root += 1) {
    if (root && cubic.constant % root === 0 && root ** 3 + cubic.linear * root + cubic.constant === 0) {
      return true
    }
  }
  return false
}

function eligibleCubic(cubic: Cubic): boolean {
  const discriminant = -4 * cubic.linear ** 3 - 27 * cubic.constant ** 2
  return cubic.constant !== 0 && discriminant !== 0 && !hasIntegerRoot(cubic)
}

function polynomialStatistics(answer: string) {
  const expression = answer.replace(/^P\(z\)=/, '').replace(/\s+/g, '')
  const terms = expression.replace(/-/g, '+-').split('+').filter(Boolean)
  const coefficients = terms.map(term => {
    const coefficient = term.match(/^[+-]?(\d+)/)?.[0]
    return coefficient ? Math.abs(Number(coefficient)) : 1
  })
  return {
    termCount: terms.length,
    maximumCoefficient: Math.max(...coefficients, 0),
  }
}

function generatedProgram(card: ExecutableFusionCard): Record<string, unknown> {
  const value = card.execution_certificate && 'generated_program' in card.execution_certificate
    ? card.execution_certificate.generated_program
    : null
  return value && typeof value === 'object' && !Array.isArray(value)
    ? value as Record<string, unknown>
    : {}
}

function summary(candidate: Candidate) {
  const card = candidate.card
  return {
    id: card.id,
    engine: 'runtime-polynomial-pair-map-generation',
    family: card.family_id,
    statement: card.statement_tex,
    answer: card.answer_tex,
    solution: card.solution_tex,
    domain: card.domain,
    morphismChain: card.morphism_chain,
    structureBlueprint: card.structure_blueprint,
    diagram: card.diagram,
    proofRoadmap: card.proof_roadmap,
    proofObligations: card.proof_obligations,
    hasDiagram: card.diagram !== undefined,
    difficulty: card.difficulty.score,
    verificationMethod: card.verification.method,
    exactBackend: card.verification.exact_backend,
    independentCheck: card.verification.independent_check,
    completeParentProof: hasCompleteParentProof(card, candidate.parents),
    capabilityOrigin: capabilityOrigin(card.execution_certificate),
    registeredCompositeUsed: card.execution_certificate?.registered_composite_used === true,
    taskFingerprint: candidate.taskFingerprint,
    taskAlgebraFingerprint: candidate.taskAlgebraFingerprint,
    coreAlgebraFingerprint: candidate.coreAlgebraFingerprint,
    taskAlgebraOrigin: problemStructureFingerprints(card).normalForm.task.algebraOrigin,
    mapId: candidate.mapId,
    resultDegree: candidate.resultDegree,
    termCount: candidate.termCount,
    maximumCoefficient: candidate.maximumCoefficient,
    corpusSurfaceNovelty: candidate.corpusSurfaceNovelty,
    replayEvidence: candidate.replay,
    parents: candidate.parents,
  }
}

const outputPath = resolve(argument('--out') ?? 'artifacts/benchmarks/certified-polynomial-map-search-20260903.json')
const catalogPath = resolve(argument('--catalog') ?? 'artifacts/benchmarks/fullproblem-certified-catalog-20260831.json')
const maximumPairs = Math.max(1, Number.parseInt(argument('--max-pairs') ?? '12', 10))
const catalog = JSON.parse(await readFile(catalogPath, 'utf8')) as { entries: Array<{ statement: string }> }
const corpusGrams = catalog.entries.map(entry => ngrams(entry.statement))
const catalogStatements = new Set(catalog.entries.map(entry => canonical(entry.statement)))

const cubics: Cubic[] = []
for (let linear = -4; linear <= 4; linear += 1) {
  for (let constant = -3; constant <= 3; constant += 1) {
    const cubic = { linear, constant }
    if (eligibleCubic(cubic)) cubics.push(cubic)
  }
}
cubics.sort((left, right) =>
  Math.abs(left.linear) + Math.abs(left.constant) - Math.abs(right.linear) - Math.abs(right.constant)
  || left.linear - right.linear
  || left.constant - right.constant)

const pairs: Array<[Cubic, Cubic]> = []
for (let left = 0; left < cubics.length; left += 1) {
  for (let right = left + 1; right < cubics.length; right += 1) {
    pairs.push([cubics[left], cubics[right]])
  }
}
pairs.sort((left, right) => {
  const leftMaximum = Math.max(...left.map(cubic => Math.abs(cubic.linear) + Math.abs(cubic.constant)))
  const rightMaximum = Math.max(...right.map(cubic => Math.abs(cubic.linear) + Math.abs(cubic.constant)))
  const leftTotal = left.reduce((sum, cubic) => sum + Math.abs(cubic.linear) + Math.abs(cubic.constant), 0)
  const rightTotal = right.reduce((sum, cubic) => sum + Math.abs(cubic.linear) + Math.abs(cubic.constant), 0)
  return leftMaximum - rightMaximum || leftTotal - rightTotal
})

const startedAt = Date.now()
const candidates: Candidate[] = []
const rejectionCounts: Record<string, number> = {}
const seenAnswers = new Set<string>()
for (const [pairIndex, selected] of pairs.slice(0, maximumPairs).entries()) {
  const parents: DiscoveryParent[] = selected.map((cubic, parentIndex) => ({
    id: `pair-${pairIndex + 1}-parent-${parentIndex + 1}`,
    statement: `方程式 \\(${cubicTex(cubic)}=0\\) のすべての複素数解を考える。`,
  }))
  for (const card of synthesizePolynomialPairMapFusions(parents, 4, pairIndex + 1)) {
    const reject = (reason: string) => {
      rejectionCounts[reason] = (rejectionCounts[reason] ?? 0) + 1
    }
    const audit = auditPublicationContent(card)
    const replay = replayCardEvidence(card, parents)
    if (!audit.passed) { reject('publication-content-audit'); continue }
    if (replay.status !== 'accepted') { reject('replay-evidence'); continue }
    if (!hasCompleteParentProof(card, parents)) { reject('parent-proof'); continue }
    if (capabilityOrigin(card.execution_certificate) !== 'synthesized_proof_program') {
      reject('non-synthesized-origin'); continue
    }
    if (card.execution_certificate?.registered_composite_used === true) {
      reject('registered-composite'); continue
    }
    const answerKey = canonical(card.answer_tex)
    if (seenAnswers.has(answerKey)) { reject('duplicate-answer'); continue }
    seenAnswers.add(answerKey)
    const fingerprints = problemStructureFingerprints(card)
    const statistics = polynomialStatistics(card.answer_tex)
    const maximumSimilarity = Math.max(0, ...corpusGrams.map(grams => jaccard(ngrams(card.statement_tex), grams)))
    const program = generatedProgram(card)
    candidates.push({
      card,
      parents,
      replay,
      mapId: typeof program.map_id === 'string' ? program.map_id : 'unknown',
      resultDegree: Number(card.verification.samples?.[2] ?? 0),
      ...statistics,
      answerLength: card.answer_tex.length,
      corpusSurfaceNovelty: Number((1 - maximumSimilarity).toFixed(6)),
      taskFingerprint: fingerprints.task,
      taskAlgebraFingerprint: fingerprints.algebra,
      coreAlgebraFingerprint: fingerprints.coreAlgebra,
    })
  }
}

const publishable = candidates
  .filter(candidate => candidate.resultDegree >= 9)
  .filter(candidate => candidate.termCount >= 5 && candidate.termCount <= 9)
  .filter(candidate => candidate.maximumCoefficient <= 500)
  .filter(candidate => candidate.answerLength <= 220)
  .sort((left, right) =>
    left.termCount - right.termCount
    || left.maximumCoefficient - right.maximumCoefficient
    || right.corpusSurfaceNovelty - left.corpusSurfaceNovelty
    || left.card.id.localeCompare(right.card.id))

const selected = publishable[0]
if (!selected) throw new Error('no replay-certified readable degree-nine problem was found')
const mutation = candidates.find(candidate =>
  candidate.mapId === selected.mapId
  && candidate.parents.some(parent => selected.parents.some(original => parent.statement === original.statement))
  && candidate.card.answer_tex !== selected.card.answer_tex)
if (!mutation) throw new Error('selected map has no one-parent mutation in the measured search')

const mutationAudit = {
  sameTaskProgram: mutation.taskFingerprint === selected.taskFingerprint,
  sameTaskAlgebra: mutation.taskAlgebraFingerprint === selected.taskAlgebraFingerprint,
  sameCoreAlgebra: mutation.coreAlgebraFingerprint === selected.coreAlgebraFingerprint,
  changedAnswer: mutation.card.answer_tex !== selected.card.answer_tex,
}
const measured = pairs.slice(0, maximumPairs)
const report = {
  schema: 2,
  measuredAt: new Date().toISOString(),
  purpose: '一つの汎用二変数多項式写像プログラムから、問題固有規則なしで難問を生成し、公開可能性まで再生検証する',
  method: {
    parentSpace: '有界係数の既約・重根なし三次多項式を複雑さ順に組み合わせる',
    mapSpace: '次数3以下、整数係数の二変数多項式写像という共通文法',
    proofProgram: '直積 → 多項式写像 → 二段終結式 → 平方因子除去 → 全根相互被覆 → 両親摂動',
    publicationGate: '文章監査、親依存証明、実行証明書、独立検算、再生SHA-256を全て要求',
    expectedAnswersStored: false,
    externalLlmUsed: false,
  },
  elapsedMs: Date.now() - startedAt,
  cubicCount: cubics.length,
  availablePairCount: pairs.length,
  measuredPairCount: measured.length,
  generatedCardCount: candidates.length,
  publishableCardCount: publishable.length,
  rejectionCounts,
  distinctAnswerCount: new Set(candidates.map(candidate => canonical(candidate.card.answer_tex))).size,
  distinctMapCount: new Set(candidates.map(candidate => candidate.mapId)).size,
  distinctTaskProgramCount: new Set(candidates.map(candidate => candidate.taskFingerprint)).size,
  distinctTaskAlgebraCount: new Set(candidates.map(candidate => candidate.taskAlgebraFingerprint)).size,
  distinctCoreAlgebraCount: new Set(candidates.map(candidate => candidate.coreAlgebraFingerprint)).size,
  allGeneratedCardsReplayCertified: candidates.every(candidate => candidate.replay.status === 'accepted'),
  selectedParentsAbsentFromCatalog: selected.parents.every(parent => !catalogStatements.has(canonical(parent.statement ?? ''))),
  mutationAudit: { ...mutationAudit, passed: Object.values(mutationAudit).every(Boolean) },
  selectedCardId: selected.card.id,
  cases: [{
    id: 'fresh-certified-polynomial-map',
    relation: 'bounded-generic-map-search-selection',
    parentCount: selected.parents.length,
    cards: [summary(selected)],
  }],
  topCandidates: publishable.slice(0, 20).map(summary),
}

await mkdir(dirname(outputPath), { recursive: true })
await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
process.stdout.write(`${JSON.stringify({
  outputPath,
  elapsedMs: report.elapsedMs,
  measuredPairCount: report.measuredPairCount,
  generatedCardCount: report.generatedCardCount,
  publishableCardCount: report.publishableCardCount,
  distinctAnswerCount: report.distinctAnswerCount,
  distinctMapCount: report.distinctMapCount,
  distinctTaskProgramCount: report.distinctTaskProgramCount,
  distinctTaskAlgebraCount: report.distinctTaskAlgebraCount,
  distinctCoreAlgebraCount: report.distinctCoreAlgebraCount,
  mutationAudit: report.mutationAudit,
  selected: summary(selected),
}, null, 2)}\n`)
