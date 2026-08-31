import { readFile, writeFile } from 'node:fs/promises'
import { basename, resolve } from 'node:path'

import { certifiedFusionKind } from '../lib/mortra/certified-fusion-kind.js'
import { synthesizeCertifiedFusions } from '../lib/mortra/certified-fusion-registry.js'
import { parseCertifiedExactScalar } from '../lib/mortra/certified-answer-recurrence-fusion.js'
import {
  elaborateCertifiedFusionParent,
  type CertifiedFusionEndpointKind,
} from '../lib/mortra/certified-fusion-planner.js'

type CorpusProblem = {
  id: string
  label: string
  statement: string
  answer?: string | null
  solution?: string | null
  certificate?: { verified: true; id: string; method?: string } | null
}

function extractItemboxProblems(source: string): CorpusProblem[] {
  const answerBoundary = source.indexOf('\\fbox{解答編}')
  const problemSection = answerBoundary >= 0 ? source.slice(0, answerBoundary) : source
  return Array.from(problemSection.matchAll(
    /\\begin\{itembox\}\[l\]\{([^{}]+)\}([\s\S]*?)\\end\{itembox\}/g,
  )).map((match, index) => ({
    id: `corpus-${String(index + 1).padStart(3, '0')}`,
    label: match[1].trim(),
    statement: match[2].trim(),
  }))
}

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}

const texPath = argument('--tex')
if (!texPath) throw new Error('usage: benchmark-certified-fusion-corpus.mts --tex <全問題.tex> [--out report.json]')

const startedAt = Date.now()
const source = await readFile(resolve(texPath), 'utf8')
let problems = extractItemboxProblems(source)
const catalogPath = argument('--catalog')
if (catalogPath) {
  const catalog = JSON.parse(await readFile(resolve(catalogPath), 'utf8')) as {
    entries: Array<{
      id: string
      ordinal: number
      label: string
      statement: string
      answerTex: string | null
      solutionTex: string | null
      certificate: { verified: true; id: string; method?: string } | null
    }>
  }
  const byOrdinal = new Map(catalog.entries.map(entry => [entry.ordinal, entry]))
  problems = problems.map((problem, index) => {
    const entry = byOrdinal.get(index + 1)
    return entry ? {
      id: entry.id,
      label: entry.label,
      statement: entry.statement,
      answer: entry.answerTex,
      solution: entry.solutionTex,
      certificate: entry.certificate,
    } : problem
  })
}
const typedEndpoints = problems.flatMap(problem => {
  const types = [...new Set(elaborateCertifiedFusionParent(problem).map(item => item.kind))]
  return types.length ? [{ id: problem.id, label: problem.label, types }] : []
})
const endpointKinds = [...new Set(typedEndpoints.flatMap(endpoint => endpoint.types))]
  .sort() as CertifiedFusionEndpointKind[]
const endpointTypeCounts = Object.fromEntries(endpointKinds.map(kind => [
  kind,
  typedEndpoints.filter(endpoint => endpoint.types.includes(kind)).length,
]))
const successes: Array<{
  left: { id: string; label: string }
  right: { id: string; label: string }
  family: string
  kind: 'structural' | 'proof_composition'
  cardId: string
  answer: string
  exactBackend: boolean
  independentCheck: boolean
  ablationPassed: boolean
  generationAuditPassed: boolean
  reversePlaybackOnly: boolean
  premiseMinimalityPassed: boolean
  unusedPremiseCount: number
  proofStepCount: number
}> = []
const familyCounts: Record<string, number> = {}
let directCertifiedPairCount = 0
let certificateCompositionPairCount = 0

for (let left = 0; left < problems.length; left += 1) {
  for (let right = left + 1; right < problems.length; right += 1) {
    const parents = [problems[left], problems[right]]
    const directParents = parents.map(parent => ({ id: parent.id, statement: parent.statement }))
    const directCard = synthesizeCertifiedFusions(directParents, 1)[0]
    if (directCard && certifiedFusionKind(directCard.family_id) === 'structural') {
      directCertifiedPairCount += 1
    }
    const cards = synthesizeCertifiedFusions(parents, 1)
    for (const card of cards) {
      const kind = certifiedFusionKind(card.family_id)
      if (!kind) continue
      if (kind === 'proof_composition') certificateCompositionPairCount += 1
      familyCounts[card.family_id] = (familyCounts[card.family_id] ?? 0) + 1
      successes.push({
        left: { id: parents[0].id, label: parents[0].label },
        right: { id: parents[1].id, label: parents[1].label },
        family: card.family_id,
        kind,
        cardId: card.id,
        answer: card.answer_tex,
        exactBackend: card.verification.exact_backend,
        independentCheck: card.verification.independent_check,
        ablationPassed: card.fusion_derivation.ablationPassed,
        generationAuditPassed: card.generation_audit?.passed === true,
        reversePlaybackOnly: card.generation_audit?.reversePlaybackOnly ?? true,
        premiseMinimalityPassed: card.generation_audit?.checks.premiseMinimality === true,
        unusedPremiseCount: card.generation_audit?.unusedPremiseIds.length ?? -1,
        proofStepCount: card.generation_audit?.proofStepCount ?? 0,
      })
    }
  }
}

const pairCount = problems.length * (problems.length - 1) / 2
const report = {
  schema: 6,
  source: basename(resolve(texPath)),
  measuredAt: new Date().toISOString(),
  problemCount: problems.length,
  pairCount,
  typedEndpointCount: typedEndpoints.length,
  certifiedExactScalarEndpointCount: problems.filter(problem => parseCertifiedExactScalar(problem) !== null).length,
  endpointTypeCounts,
  typedEndpoints,
  certifiedPairCount: successes.length,
  certifiedPairRate: pairCount ? successes.length / pairCount : 0,
  structuralFusionPairCount: directCertifiedPairCount,
  structuralFusionPairRate: pairCount ? directCertifiedPairCount / pairCount : 0,
  proofCompositionPairCount: certificateCompositionPairCount,
  proofCompositionPairRate: pairCount ? certificateCompositionPairCount / pairCount : 0,
  directCertifiedPairCount,
  certificateCompositionPairCount,
  familyCounts,
  allCertificatesComplete: successes.every(item =>
    item.exactBackend
      && item.independentCheck
      && item.ablationPassed
      && item.generationAuditPassed
      && !item.reversePlaybackOnly
      && item.premiseMinimalityPassed
      && item.unusedPremiseCount === 0,
  ),
  elapsedMs: Date.now() - startedAt,
  successes,
}

const output = `${JSON.stringify(report, null, 2)}\n`
const outPath = argument('--out')
if (outPath) await writeFile(resolve(outPath), output, 'utf8')
process.stdout.write(output)
