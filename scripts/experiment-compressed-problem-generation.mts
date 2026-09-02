import { readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

import type { CertifiedFusionCard } from '../lib/mortra/certified-fusion.js'
import { certifiedFusionKind } from '../lib/mortra/certified-fusion-kind.js'
import { synthesizeCertifiedFusions } from '../lib/mortra/certified-fusion-registry.js'
import {
  problemStructureFingerprints,
  selectStructurallyDiverseProblems,
  type StructuralProblemCard,
} from '../lib/mortra/problem-structure-normal-form.js'
import { problemTaskPrimitiveSet } from '../lib/mortra/problem-task-algebra.js'
import { hasCompleteParentProof } from '../worker/src/autonomous-synthesis.js'
import { capabilityOrigin } from '../worker/src/execution-certificate.js'
import type { ExecutableFusionCard } from '../worker/src/executable-fusion.js'
import type { DiscoveryParent } from '../worker/src/parent-conditioned-discovery.js'
import {
  runtimeGenerationEngines,
  type RuntimeGenerationEngine,
} from '../worker/src/runtime-generation-registry.js'

type CatalogEntry = {
  id: string
  ordinal: number
  label: string
  statement: string
  answerTex?: string | null
  solutionTex?: string | null
  certificate?: { verified: true; id: string; method?: string } | null
}

type GeneratedCard = CertifiedFusionCard | ExecutableFusionCard

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}

function hasFlag(name: string): boolean {
  return process.argv.includes(name)
}

function canonical(text: string): string {
  return text
    .normalize('NFKC')
    .toLowerCase()
    .replace(/\\(?:left|right|displaystyle|textstyle)/g, '')
    .replace(/\\[dt]frac/g, '\\frac')
    .replace(/\s+/g, '')
}

function ngrams(text: string, size = 3): Set<string> {
  const normalized = canonical(text)
  const result = new Set<string>()
  for (let index = 0; index + size <= normalized.length; index += 1) {
    result.add(normalized.slice(index, index + size))
  }
  return result
}

function jaccard(left: Set<string>, right: Set<string>): number {
  if (!left.size && !right.size) return 1
  let intersection = 0
  for (const value of left) if (right.has(value)) intersection += 1
  const union = left.size + right.size - intersection
  return union ? intersection / union : 0
}

function rounded(value: number): number {
  return Number(value.toFixed(6))
}

const catalogPath = resolve(argument('--catalog') ?? 'artifacts/benchmarks/fullproblem-certified-catalog-20260831.json')
const outputPath = resolve(argument('--out') ?? 'artifacts/benchmarks/compressed-problem-generation-20260902.json')
const perEngineLimit = Number(argument('--per-engine-limit') ?? '8')
const selectedLimit = Number(argument('--selected-limit') ?? '24')
const maximumPairs = Number(argument('--max-pairs') ?? Number.MAX_SAFE_INTEGER)
if (![perEngineLimit, selectedLimit, maximumPairs].every(value => Number.isInteger(value) && value > 0)) {
  throw new Error('limits must be positive integers')
}

const catalog = JSON.parse(await readFile(catalogPath, 'utf8')) as { entries: CatalogEntry[] }
const entries = catalog.entries
const corpusGrams = entries.map(entry => ngrams(entry.statement))
const engines: RuntimeGenerationEngine[] = runtimeGenerationEngines({
  includeExpression: hasFlag('--include-expression'),
})
const cards: GeneratedCard[] = []
const sourceByCardId = new Map<string, string>()
const failures: Array<{ engine: string; parents: string[]; message: string }> = []
const engineAttempts = new Map<string, number>()
const engineAccepted = new Map<string, number>()
let pairsVisited = 0

function accept(card: GeneratedCard, source: string): void {
  if (sourceByCardId.has(card.id)) return
  sourceByCardId.set(card.id, source)
  cards.push(card)
  engineAccepted.set(source, (engineAccepted.get(source) ?? 0) + 1)
}

outer:
for (let leftIndex = 0; leftIndex < entries.length; leftIndex += 1) {
  for (let rightIndex = leftIndex + 1; rightIndex < entries.length; rightIndex += 1) {
    if (pairsVisited >= maximumPairs) break outer
    pairsVisited += 1
    const selectedEntries = [entries[leftIndex], entries[rightIndex]]
    const parents: DiscoveryParent[] = selectedEntries.map(entry => ({
      id: entry.id,
      statement: entry.statement,
      answer: entry.answerTex,
      solution: entry.solutionTex,
    }))

    engineAttempts.set('certified-fusion-planner', (engineAttempts.get('certified-fusion-planner') ?? 0) + 1)
    for (const card of synthesizeCertifiedFusions(parents.map(parent => ({
      id: String(parent.id),
      statement: String(parent.statement),
      answer: parent.answer,
      solution: parent.solution,
      certificate: selectedEntries.find(entry => entry.id === parent.id)?.certificate ?? null,
    })), perEngineLimit)) {
      if (certifiedFusionKind(card.family_id) === 'structural' && card.generation_audit?.passed) {
        accept(card, 'certified-fusion-planner')
      }
    }

    for (const engine of engines) {
      engineAttempts.set(engine.id, (engineAttempts.get(engine.id) ?? 0) + 1)
      try {
        const result = engine.synthesize(parents, perEngineLimit)
        for (const card of result.cards) {
          const origin = capabilityOrigin(card.execution_certificate)
          if (!hasCompleteParentProof(card, parents)) continue
          if (origin === 'registered_parameterized_morphism' || card.execution_certificate?.registered_composite_used === true) continue
          accept(card, engine.id)
        }
      } catch (error) {
        failures.push({
          engine: engine.id,
          parents: selectedEntries.map(entry => entry.id),
          message: error instanceof Error ? error.message : String(error),
        })
      }
    }
  }
}

const selectedCards = selectStructurallyDiverseProblems(cards, selectedLimit)
const summaries = cards.map(card => {
  const fingerprints = problemStructureFingerprints(card)
  const cardGrams = ngrams(card.statement_tex)
  return {
    cardId: card.id,
    source: sourceByCardId.get(card.id),
    family: card.family_id,
    domain: card.domain,
    parents: card.parent_ids,
    kernel: card.structure_blueprint.kernel,
    observable: card.structure_blueprint.observable,
    kernelFingerprint: fingerprints.kernel,
    programFingerprint: fingerprints.program,
    taskFingerprint: fingerprints.task,
    taskAlgebraFingerprint: fingerprints.algebra,
    taskAlgebra: fingerprints.normalForm.task.algebra,
    taskAlgebraOrigin: fingerprints.normalForm.task.algebraOrigin,
    difficulty: card.difficulty.score,
    proofStepCount: card.generation_audit?.proofStepCount ?? card.morphism_chain.length,
    morphismCount: new Set(card.morphism_chain).size,
    corpusSurfaceNovelty: rounded(1 - Math.max(...corpusGrams.map(grams => jaccard(cardGrams, grams)))),
    hasDiagram: card.diagram !== undefined,
    statement: card.statement_tex,
    answer: card.answer_tex,
    solution: card.solution_tex,
  }
})
const summaryById = new Map(summaries.map(summary => [summary.cardId, summary]))
const kernelCount = new Set(summaries.map(summary => summary.kernelFingerprint)).size
const programCount = new Set(summaries.map(summary => summary.programFingerprint)).size
const taskCount = new Set(summaries.map(summary => summary.taskFingerprint)).size
const taskAlgebraCount = new Set(summaries.map(summary => summary.taskAlgebraFingerprint)).size
const surfaceQuestionCount = new Set(summaries.map(summary => summary.observable)).size
const taskAlgebras = [...new Map(summaries.map(summary => [
  summary.taskAlgebraFingerprint,
  summary.taskAlgebra,
])).values()]
const taskPrimitives = problemTaskPrimitiveSet(taskAlgebras)
const incompleteTaskAlgebraCount = summaries.filter(summary => !summary.taskAlgebra.complete).length
const emittedTaskAlgebraCount = summaries.filter(summary => summary.taskAlgebraOrigin === 'emitted').length
const inferredTaskAlgebraCount = summaries.filter(summary => summary.taskAlgebraOrigin === 'inferred').length
const report = {
  schema: 2,
  measuredAt: new Date().toISOString(),
  purpose: '問題固有の文面や数値を記憶せず、少数の型付き作問核から構造の異なる難問を生成できるか測る',
  method: {
    catalog: catalogPath,
    problemCount: entries.length,
    totalPossiblePairs: entries.length * (entries.length - 1) / 2,
    pairsVisited,
    perEngineLimit,
    engines: ['certified-fusion-planner', ...engines.map(engine => engine.id)],
    selection: '親ID・記号・数値・答えを除き、実行核、型付き入力形成、型付き問い代数を分離して重複を除く',
  },
  rawCardCount: cards.length,
  distinctKernelCount: kernelCount,
  distinctProgramCount: programCount,
  distinctTaskCount: taskCount,
  distinctSurfaceQuestionCount: surfaceQuestionCount,
  distinctTaskAlgebraCount: taskAlgebraCount,
  surfaceQuestionsPerTaskAlgebra: rounded(surfaceQuestionCount / Math.max(1, taskAlgebraCount)),
  taskPrimitiveCount: taskPrimitives.length,
  taskPrimitives,
  incompleteTaskAlgebraCount,
  emittedTaskAlgebraCount,
  inferredTaskAlgebraCount,
  rawCardsPerKernel: rounded(cards.length / Math.max(1, kernelCount)),
  engineAttempts: Object.fromEntries([...engineAttempts].sort()),
  engineAccepted: Object.fromEntries([...engineAccepted].sort()),
  failureCount: failures.length,
  failures: failures.slice(0, 100),
  selectedCardIds: selectedCards.map(card => card.id),
  selected: selectedCards.map(card => summaryById.get(card.id)),
  candidates: summaries,
}

await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
process.stdout.write(`${JSON.stringify({
  outputPath,
  pairsVisited,
  rawCardCount: cards.length,
  distinctKernelCount: kernelCount,
  distinctProgramCount: programCount,
  distinctTaskCount: taskCount,
  distinctSurfaceQuestionCount: surfaceQuestionCount,
  distinctTaskAlgebraCount: taskAlgebraCount,
  surfaceQuestionsPerTaskAlgebra: report.surfaceQuestionsPerTaskAlgebra,
  taskPrimitiveCount: taskPrimitives.length,
  taskPrimitives,
  incompleteTaskAlgebraCount,
  emittedTaskAlgebraCount,
  inferredTaskAlgebraCount,
  rawCardsPerKernel: report.rawCardsPerKernel,
  engineAccepted: report.engineAccepted,
  failureCount: failures.length,
  selected: report.selected.map(card => card && ({
    cardId: card.cardId,
    source: card.source,
    family: card.family,
    kernel: card.kernel,
    observable: card.observable,
    difficulty: card.difficulty,
    proofStepCount: card.proofStepCount,
    corpusSurfaceNovelty: card.corpusSurfaceNovelty,
    hasDiagram: card.hasDiagram,
  })),
}, null, 2)}\n`)
