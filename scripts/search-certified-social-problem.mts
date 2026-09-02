import { readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

import {
  problemStructureFingerprints,
} from '../lib/mortra/problem-structure-normal-form.js'
import { hasCompleteParentProof } from '../worker/src/autonomous-synthesis.js'
import { capabilityOrigin } from '../worker/src/execution-certificate.js'
import type { ExecutableFusionCard } from '../worker/src/executable-fusion.js'
import type { DiscoveryParent } from '../worker/src/parent-conditioned-discovery.js'
import { synthesizePolynomialRootFusions } from '../worker/src/polynomial-root-fusion.js'

type Cubic = { linear: number; constant: number }

type SearchCandidate = {
  card: ExecutableFusionCard
  parents: DiscoveryParent[]
  resultDegree: number
  termCount: number
  maximumCoefficient: number
  answerLength: number
  corpusSurfaceNovelty: number
  taskFingerprint: string
  taskAlgebraFingerprint: string
}

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
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
  const values = new Set<string>()
  for (let index = 0; index + size <= normalized.length; index += 1) {
    values.add(normalized.slice(index, index + size))
  }
  return values
}

function jaccard(left: Set<string>, right: Set<string>): number {
  if (!left.size && !right.size) return 1
  let intersection = 0
  for (const value of left) if (right.has(value)) intersection += 1
  const union = left.size + right.size - intersection
  return union ? intersection / union : 0
}

function integerTerm(coefficient: number, variable: string): string {
  if (coefficient === 0) return ''
  const sign = coefficient > 0 ? '+' : '-'
  const magnitude = Math.abs(coefficient)
  return `${sign}${magnitude === 1 ? '' : magnitude}${variable}`
}

function cubicTex(cubic: Cubic): string {
  const constant = cubic.constant > 0 ? `+${cubic.constant}` : String(cubic.constant)
  return `x^3${integerTerm(cubic.linear, 'x')}${constant}`
}

function hasIntegerRoot(cubic: Cubic): boolean {
  const bound = Math.abs(cubic.constant)
  for (let root = -bound; root <= bound; root += 1) {
    if (root !== 0 && cubic.constant % root === 0) {
      if (root ** 3 + cubic.linear * root + cubic.constant === 0) return true
    }
  }
  return false
}

function isEligibleCubic(cubic: Cubic): boolean {
  const discriminant = -4 * cubic.linear ** 3 - 27 * cubic.constant ** 2
  return cubic.constant !== 0 && discriminant !== 0 && !hasIntegerRoot(cubic)
}

function polynomialStatistics(answer: string): { termCount: number; maximumCoefficient: number } {
  const expression = answer.replace(/^P\(z\)=/, '').replace(/\s+/g, '')
  const terms = expression.replace(/-/g, '+-').split('+').filter(Boolean)
  const coefficients = terms.flatMap(term => {
    const coefficient = term.match(/^[+-]?(\d+)/)?.[0]
    return coefficient ? [Math.abs(Number(coefficient))] : [1]
  })
  return {
    termCount: terms.length,
    maximumCoefficient: Math.max(...coefficients, 0),
  }
}

function cardSummary(candidate: SearchCandidate) {
  const card = candidate.card
  return {
    id: card.id,
    engine: 'runtime-polynomial-root-generation',
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
    taskAlgebraOrigin: problemStructureFingerprints(card).normalForm.task.algebraOrigin,
    resultDegree: candidate.resultDegree,
    termCount: candidate.termCount,
    maximumCoefficient: candidate.maximumCoefficient,
    corpusSurfaceNovelty: candidate.corpusSurfaceNovelty,
    parents: candidate.parents,
  }
}

const outputPath = resolve(argument('--out') ?? 'artifacts/benchmarks/certified-social-problem-search-20260903.json')
const catalogPath = resolve(argument('--catalog') ?? 'artifacts/benchmarks/fullproblem-certified-catalog-20260831.json')
const catalog = JSON.parse(await readFile(catalogPath, 'utf8')) as { entries: Array<{ statement: string }> }
const corpusGrams = catalog.entries.map(entry => ngrams(entry.statement))
const catalogStatements = new Set(catalog.entries.map(entry => canonical(entry.statement)))

const cubics: Cubic[] = []
for (let linear = -6; linear <= 2; linear += 1) {
  for (let constant = -5; constant <= 5; constant += 1) {
    const cubic = { linear, constant }
    if (isEligibleCubic(cubic)) cubics.push(cubic)
  }
}

const candidates: SearchCandidate[] = []
const seenAnswers = new Set<string>()
for (let leftIndex = 0; leftIndex < cubics.length; leftIndex += 1) {
  for (let rightIndex = leftIndex + 1; rightIndex < cubics.length; rightIndex += 1) {
    const selected = [cubics[leftIndex], cubics[rightIndex]]
    const parents: DiscoveryParent[] = selected.map((cubic, index) => ({
      id: `bounded-cubic-${leftIndex}-${rightIndex}-${index}`,
      statement: `方程式 \\(${cubicTex(cubic)}=0\\) のすべての複素数解を考える。`,
    }))
    for (const card of synthesizePolynomialRootFusions(parents, 3)) {
      if (seenAnswers.has(canonical(card.answer_tex))) continue
      const origin = capabilityOrigin(card.execution_certificate)
      if (!card.verification.exact_backend || !card.verification.independent_check) continue
      if (!hasCompleteParentProof(card, parents) || origin !== 'synthesized_proof_program') continue
      if (card.execution_certificate?.registered_composite_used === true) continue
      const resultDegree = Number(card.verification.samples?.[2] ?? 0)
      const statistics = polynomialStatistics(card.answer_tex)
      const cardGrams = ngrams(card.statement_tex)
      const maximumSimilarity = Math.max(...corpusGrams.map(grams => jaccard(cardGrams, grams)))
      const fingerprints = problemStructureFingerprints(card)
      seenAnswers.add(canonical(card.answer_tex))
      candidates.push({
        card,
        parents,
        resultDegree,
        ...statistics,
        answerLength: card.answer_tex.length,
        corpusSurfaceNovelty: Number((1 - maximumSimilarity).toFixed(6)),
        taskFingerprint: fingerprints.task,
        taskAlgebraFingerprint: fingerprints.algebra,
      })
    }
  }
}

const publishable = candidates
  .filter(candidate => candidate.resultDegree >= 9)
  .filter(candidate => candidate.termCount >= 5 && candidate.termCount <= 10)
  .filter(candidate => candidate.maximumCoefficient <= 1000)
  .filter(candidate => candidate.answerLength <= 180)
  .sort((left, right) =>
    right.resultDegree - left.resultDegree
    || right.termCount - left.termCount
    || left.maximumCoefficient - right.maximumCoefficient
    || right.corpusSurfaceNovelty - left.corpusSurfaceNovelty
    || left.card.id.localeCompare(right.card.id)
  )

const selected = publishable[0]
if (!selected) throw new Error('bounded search found no publishable certified problem')
const mutation = publishable.find(candidate =>
  candidate.card.family_id === selected.card.family_id
  && candidate.card.id !== selected.card.id
  && candidate.parents.some(parent => selected.parents.some(original => parent.statement === original.statement))
  && canonical(candidate.card.answer_tex) !== canonical(selected.card.answer_tex)
)
if (!mutation) throw new Error('no one-parent mutation was available for the selected problem')

const selectedFingerprints = problemStructureFingerprints(selected.card)
const mutationFingerprints = problemStructureFingerprints(mutation.card)
const mutationAudit = {
  sameTaskProgram: selectedFingerprints.task === mutationFingerprints.task,
  sameTaskAlgebra: selectedFingerprints.algebra === mutationFingerprints.algebra,
  changedAnswer: canonical(selected.card.answer_tex) !== canonical(mutation.card.answer_tex),
}
const parentsAbsentFromCatalog = selected.parents.every(parent => !catalogStatements.has(canonical(parent.statement ?? '')))
const report = {
  schema: 1,
  measuredAt: new Date().toISOString(),
  purpose: '問題固有の表現や期待解答を保存せず、共通の型付き問い代数から公開可能な難問を探索する',
  method: {
    searchSpace: '既約かつ重根を持たない x^3+px+q の有界係数集合から相異なる二式を選ぶ',
    expectedAnswersStored: false,
    externalLlmUsed: false,
    generation: '二つの有限根配置に同じ二項写像を適用し、終結式、重複因子除去、独立な全根照合で検証する',
    publicationFilter: '結果次数9以上、5項以上10項以下、最大係数1000以下、答え180文字以下',
  },
  cubicCount: cubics.length,
  pairCount: cubics.length * (cubics.length - 1) / 2,
  generatedCardCount: candidates.length,
  publishableCardCount: publishable.length,
  distinctTaskAlgebraCount: new Set(candidates.map(candidate => candidate.taskAlgebraFingerprint)).size,
  emittedTaskAlgebraCount: candidates.filter(candidate =>
    problemStructureFingerprints(candidate.card).normalForm.task.algebraOrigin === 'emitted'
  ).length,
  inferredTaskAlgebraCount: candidates.filter(candidate =>
    problemStructureFingerprints(candidate.card).normalForm.task.algebraOrigin === 'inferred'
  ).length,
  allGeneratedCardsCertified: candidates.every(candidate =>
    candidate.card.verification.exact_backend
    && candidate.card.verification.independent_check
    && hasCompleteParentProof(candidate.card, candidate.parents)
  ),
  parentsAbsentFromCatalog,
  mutationAudit: {
    ...mutationAudit,
    passed: Object.values(mutationAudit).every(Boolean),
    selectedAnswer: selected.card.answer_tex,
    mutatedAnswer: mutation.card.answer_tex,
  },
  selectedCardId: selected.card.id,
  cases: [{
    id: 'fresh-certified-algebraic-composition',
    relation: 'bounded-search-selection',
    parentCount: selected.parents.length,
    cards: [cardSummary(selected)],
  }],
  topCandidates: publishable.slice(0, 20).map(cardSummary),
}

await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
process.stdout.write(`${JSON.stringify({
  outputPath,
  cubicCount: report.cubicCount,
  pairCount: report.pairCount,
  generatedCardCount: report.generatedCardCount,
  publishableCardCount: report.publishableCardCount,
  distinctTaskAlgebraCount: report.distinctTaskAlgebraCount,
  emittedTaskAlgebraCount: report.emittedTaskAlgebraCount,
  inferredTaskAlgebraCount: report.inferredTaskAlgebraCount,
  allGeneratedCardsCertified: report.allGeneratedCardsCertified,
  parentsAbsentFromCatalog: report.parentsAbsentFromCatalog,
  mutationAudit: report.mutationAudit,
  selected: cardSummary(selected),
}, null, 2)}\n`)
