import { readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

import { certifiedFusionKind } from '../lib/mortra/certified-fusion-kind.js'
import { synthesizeCertifiedFusions } from '../lib/mortra/certified-fusion-registry.js'
import { elaborateCertifiedFusionParent } from '../lib/mortra/certified-fusion-planner.js'

type CatalogEntry = {
  id: string
  ordinal: number
  label: string
  statement: string
}

type Candidate = {
  cardId: string
  family: string
  observable: string
  querySignature: string
  parents: Array<{ id: string; label: string; ordinal: number }>
  endpointKinds: string[]
  statement: string
  answer: string
  solution: string
  declaredDifficulty: { band: string; score: number }
  proofStepCount: number
  representationCount: number
  answerOperationCount: number
  solutionSentenceCount: number
  maximumParentSurfaceJaccard: number
  maximumCorpusSurfaceJaccard: number
  corpusSurfaceNovelty: number
  exactBackend: boolean
  independentCheck: boolean
  allParentDependence: boolean
  crossParentComposition: boolean
  premiseMinimality: boolean
  reversePlaybackOnly: boolean
  unusedPremiseCount: number
}

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}

function canonical(text: string): string {
  return text
    .toLowerCase()
    .replace(/\\(left|right|displaystyle|textstyle)/g, '')
    .replace(/\\[dt]frac/g, '\\frac')
    .replace(/\s+/g, '')
}

function ngrams(text: string, size = 3): Set<string> {
  const normalized = canonical(text)
  const result = new Set<string>()
  if (normalized.length <= size) {
    if (normalized) result.add(normalized)
    return result
  }
  for (let index = 0; index + size <= normalized.length; index += 1) {
    result.add(normalized.slice(index, index + size))
  }
  return result
}

function jaccard(left: Set<string>, right: Set<string>): number {
  if (!left.size && !right.size) return 1
  let intersection = 0
  for (const item of left) if (right.has(item)) intersection += 1
  const union = left.size + right.size - intersection
  return union ? intersection / union : 0
}

function rounded(value: number): number {
  return Number(value.toFixed(6))
}

function answerOperationCount(answer: string): number {
  return Array.from(answer.matchAll(
    /(?:[+\-*/^=<>]|\\(?:frac|sqrt|sin|cos|tan|log|sum|prod|lim|bmod|pmod))/g,
  )).length
}

function solutionSentenceCount(solution: string): number {
  return solution
    .split(/[。.!?]+/)
    .map(item => item.trim())
    .filter(Boolean)
    .length
}

function dominates(left: Candidate, right: Candidate): boolean {
  const leftValues = [
    left.proofStepCount,
    left.representationCount,
    left.answerOperationCount,
    left.corpusSurfaceNovelty,
  ]
  const rightValues = [
    right.proofStepCount,
    right.representationCount,
    right.answerOperationCount,
    right.corpusSurfaceNovelty,
  ]
  return leftValues.every((value, index) => value >= rightValues[index])
    && leftValues.some((value, index) => value > rightValues[index])
}

const catalogPath = resolve(argument('--catalog') ?? 'artifacts/benchmarks/fullproblem-certified-catalog-20260831.json')
const outputPath = resolve(argument('--out') ?? 'artifacts/benchmarks/certified-difficult-problem-generation-20260901.json')
const perPairLimit = Number(argument('--per-pair-limit') ?? '64')
if (!Number.isInteger(perPairLimit) || perPairLimit < 1) {
  throw new Error('--per-pair-limit must be a positive integer')
}
const catalog = JSON.parse(await readFile(catalogPath, 'utf8')) as { entries: CatalogEntry[] }
const entries = catalog.entries
const corpusGrams = entries.map(entry => ({ entry, grams: ngrams(entry.statement) }))
const candidates: Candidate[] = []
const seenCards = new Set<string>()

for (let leftIndex = 0; leftIndex < entries.length; leftIndex += 1) {
  for (let rightIndex = leftIndex + 1; rightIndex < entries.length; rightIndex += 1) {
    const left = entries[leftIndex]
    const right = entries[rightIndex]
    const parents = [left, right].map(parent => ({ id: parent.id, statement: parent.statement }))
    const cards = synthesizeCertifiedFusions(parents, perPairLimit)
      .filter(card => certifiedFusionKind(card.family_id) === 'structural')
    for (const card of cards) {
      if (seenCards.has(card.id)) continue
      seenCards.add(card.id)
      const cardGrams = ngrams(card.statement_tex)
      const parentSimilarities = [left, right].map(parent => jaccard(cardGrams, ngrams(parent.statement)))
      const corpusSimilarities = corpusGrams.map(item => jaccard(cardGrams, item.grams))
      const audit = card.generation_audit
      candidates.push({
        cardId: card.id,
        family: card.family_id,
        observable: card.structure_blueprint.observable,
        querySignature: card.structure_blueprint.structuralUniqueness.querySignature,
        parents: [left, right].map(parent => ({
          id: parent.id,
          label: parent.label,
          ordinal: parent.ordinal,
        })),
        endpointKinds: [...new Set(parents.flatMap(parent =>
          elaborateCertifiedFusionParent(parent).map(endpoint => endpoint.kind),
        ))].sort(),
        statement: card.statement_tex,
        answer: card.answer_tex,
        solution: card.solution_tex,
        declaredDifficulty: card.difficulty,
        proofStepCount: audit?.proofStepCount ?? 0,
        representationCount: new Set(card.morphism_chain).size,
        answerOperationCount: answerOperationCount(card.answer_tex),
        solutionSentenceCount: solutionSentenceCount(card.solution_tex),
        maximumParentSurfaceJaccard: rounded(Math.max(...parentSimilarities)),
        maximumCorpusSurfaceJaccard: rounded(Math.max(...corpusSimilarities)),
        corpusSurfaceNovelty: rounded(1 - Math.max(...corpusSimilarities)),
        exactBackend: card.verification.exact_backend,
        independentCheck: card.verification.independent_check,
        allParentDependence: audit?.checks.allParentDependence === true,
        crossParentComposition: audit?.checks.crossParentComposition === true,
        premiseMinimality: audit?.checks.premiseMinimality === true,
        reversePlaybackOnly: audit?.reversePlaybackOnly ?? true,
        unusedPremiseCount: audit?.unusedPremiseIds.length ?? -1,
      })
    }
  }
}

const familyCounts = Object.fromEntries(
  [...new Set(candidates.map(candidate => candidate.family))]
    .sort()
    .map(family => [family, candidates.filter(candidate => candidate.family === family).length]),
)
const observableCounts = Object.fromEntries(
  [...new Set(candidates.map(candidate => candidate.observable))]
    .sort()
    .map(observable => [observable, candidates.filter(candidate => candidate.observable === observable).length]),
)
const paretoFront = candidates.filter(candidate =>
  !candidates.some(other => other.cardId !== candidate.cardId && dominates(other, candidate)),
)
const byProofDepth = [...candidates].sort((left, right) =>
  right.proofStepCount - left.proofStepCount
  || right.representationCount - left.representationCount
  || right.answerOperationCount - left.answerOperationCount
  || right.corpusSurfaceNovelty - left.corpusSurfaceNovelty,
)

const report = {
  schema: 1,
  measuredAt: new Date().toISOString(),
  purpose: '直接構造融合が、単なる逆再生ではない検証済み難問候補を生成できるかを測る',
  method: {
    population: `${entries.length}問の全組合せ`,
    pairCount: entries.length * (entries.length - 1) / 2,
    perPairLimit,
    selection: '証明深度・表現数・答えの演算数・90問に対する表層新規性を別々に測り、単一の恣意的総合点へ潰さない',
    proofRequirement: '厳密計算、独立検算、両親依存、交差合成、条件最小性、逆再生拒否のすべて',
  },
  candidateCount: candidates.length,
  familyCounts,
  observableCounts,
  distinctCardIdCount: new Set(candidates.map(candidate => candidate.cardId)).size,
  distinctStatementCount: new Set(candidates.map(candidate => canonical(candidate.statement))).size,
  distinctQuestionFormCount: new Set(candidates.map(candidate => candidate.querySignature)).size,
  allAuditsPassed: candidates.every(candidate =>
    candidate.exactBackend
    && candidate.independentCheck
    && candidate.allParentDependence
    && candidate.crossParentComposition
    && candidate.premiseMinimality
    && !candidate.reversePlaybackOnly
    && candidate.unusedPremiseCount === 0,
  ),
  paretoFrontCardIds: paretoFront.map(candidate => candidate.cardId),
  proofDepthRanking: byProofDepth.map(candidate => candidate.cardId),
  candidates,
}

await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
process.stdout.write(`${JSON.stringify({
  outputPath,
  candidateCount: candidates.length,
  familyCounts,
  observableCounts,
  allAuditsPassed: report.allAuditsPassed,
  paretoFront: paretoFront.map(candidate => ({
    cardId: candidate.cardId,
    parents: candidate.parents.map(parent => parent.label),
    family: candidate.family,
    proofStepCount: candidate.proofStepCount,
    representationCount: candidate.representationCount,
    answerOperationCount: candidate.answerOperationCount,
    corpusSurfaceNovelty: candidate.corpusSurfaceNovelty,
  })),
  topByProofDepth: byProofDepth.slice(0, 5).map(candidate => ({
    cardId: candidate.cardId,
    parents: candidate.parents.map(parent => parent.label),
    family: candidate.family,
    proofStepCount: candidate.proofStepCount,
    representationCount: candidate.representationCount,
    answerOperationCount: candidate.answerOperationCount,
    corpusSurfaceNovelty: candidate.corpusSurfaceNovelty,
  })),
}, null, 2)}\n`)
