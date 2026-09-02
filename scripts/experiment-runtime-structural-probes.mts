import { readFile, writeFile } from 'node:fs/promises'
import { resolve } from 'node:path'

import {
  problemStructureFingerprints,
  selectStructurallyDiverseProblems,
} from '../lib/mortra/problem-structure-normal-form.js'
import { problemTaskPrimitiveSet } from '../lib/mortra/problem-task-algebra.js'
import { hasCompleteParentProof } from '../worker/src/autonomous-synthesis.js'
import { capabilityOrigin } from '../worker/src/execution-certificate.js'
import type { ExecutableFusionCard } from '../worker/src/executable-fusion.js'
import type { DiscoveryParent } from '../worker/src/parent-conditioned-discovery.js'
import { runtimeGenerationEngines } from '../worker/src/runtime-generation-registry.js'

type ProbeRelation = 'baseline' | 'recompute' | 'alpha-equivalent'

type ProbeCase = {
  id: string
  relation: ProbeRelation
  comparesTo?: string
  renames?: Record<string, string>
  parents: DiscoveryParent[]
}

type ProbeBank = {
  schema: number
  purpose: string
  cases: ProbeCase[]
}

function argument(name: string): string | undefined {
  const index = process.argv.indexOf(name)
  return index >= 0 ? process.argv[index + 1] : undefined
}

function compact(value: string): string {
  return value.normalize('NFKC').replace(/\s+/g, '')
}

function renamed(value: string, renames: Record<string, string> | undefined): string {
  let result = value
  for (const [source, target] of Object.entries(renames ?? {}).sort((left, right) =>
    right[0].length - left[0].length
  )) {
    result = result.replace(new RegExp(`(?<![A-Za-z])${source}(?![A-Za-z])`, 'g'), target)
  }
  return compact(result)
}

const bankPath = resolve(argument('--bank') ?? 'data/mortra-generation-structural-probes-20260903.json')
const outputPath = resolve(argument('--out') ?? 'artifacts/benchmarks/runtime-structural-probes-20260903.json')
const requested = Number(argument('--requested') ?? '5')
if (!Number.isInteger(requested) || requested < 1) throw new Error('--requested must be a positive integer')

const bank = JSON.parse(await readFile(bankPath, 'utf8')) as ProbeBank
const engines = runtimeGenerationEngines({ includeExpression: false })
const allCards: ExecutableFusionCard[] = []
const cardCase = new Map<ExecutableFusionCard, string>()
const caseResults: Array<{
  id: string
  relation: ProbeRelation
  comparesTo?: string
  parentCount: number
  attempts: Array<{ engine: string; applicable: boolean; reason: string; generated: number }>
  cards: Array<{
    id: string
    engine: string
    family: string
    statement: string
    answer: string
    solution: string
    domain: string
    morphismChain: string[]
    structureBlueprint: ExecutableFusionCard['structure_blueprint']
    diagram?: unknown
    proofRoadmap?: unknown
    proofObligations?: unknown
    hasDiagram: boolean
    difficulty: number
    verificationMethod: string
    exactBackend: boolean
    independentCheck: boolean
    completeParentProof: boolean
    capabilityOrigin: string
    registeredCompositeUsed: boolean
    kernelFingerprint: string
    programFingerprint: string
    taskFingerprint: string
    taskAlgebraFingerprint: string
    taskAlgebra: ReturnType<typeof problemStructureFingerprints>['normalForm']['task']['algebra']
    taskAlgebraOrigin: ReturnType<typeof problemStructureFingerprints>['normalForm']['task']['algebraOrigin']
  }>
}> = []

for (const probe of bank.cases) {
  const attempts: Array<{ engine: string; applicable: boolean; reason: string; generated: number }> = []
  const cards: (typeof caseResults)[number]['cards'] = []
  for (const engine of engines) {
    const result = engine.synthesize(probe.parents, requested)
    attempts.push({
      engine: engine.id,
      applicable: result.applicable,
      reason: result.reason,
      generated: result.cards.length,
    })
    for (const card of result.cards) {
      const fingerprints = problemStructureFingerprints(card)
      const origin = capabilityOrigin(card.execution_certificate)
      allCards.push(card)
      cardCase.set(card, probe.id)
      cards.push({
        id: card.id,
        engine: engine.id,
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
        completeParentProof: hasCompleteParentProof(card, probe.parents),
        capabilityOrigin: origin,
        registeredCompositeUsed: card.execution_certificate?.registered_composite_used === true,
        kernelFingerprint: fingerprints.kernel,
        programFingerprint: fingerprints.program,
        taskFingerprint: fingerprints.task,
        taskAlgebraFingerprint: fingerprints.algebra,
        taskAlgebra: fingerprints.normalForm.task.algebra,
        taskAlgebraOrigin: fingerprints.normalForm.task.algebraOrigin,
      })
    }
  }
  caseResults.push({
    id: probe.id,
    relation: probe.relation,
    comparesTo: probe.comparesTo,
    parentCount: probe.parents.length,
    attempts,
    cards,
  })
}

const resultById = new Map(caseResults.map(result => [result.id, result]))
const probeById = new Map(bank.cases.map(probe => [probe.id, probe]))
const relationAudits = caseResults
  .filter(result => result.comparesTo)
  .map(result => {
    const baseline = resultById.get(result.comparesTo as string)
    if (!baseline) throw new Error(`missing baseline ${result.comparesTo}`)
    const currentByEngine = new Map(result.cards.map(card => [`${card.engine}:${card.taskFingerprint}`, card]))
    const baselineByEngine = new Map(baseline.cards.map(card => [`${card.engine}:${card.taskFingerprint}`, card]))
    const sharedKeys = [...currentByEngine.keys()].filter(key => baselineByEngine.has(key))
    const comparisons = sharedKeys.map(key => {
      const current = currentByEngine.get(key) as (typeof result.cards)[number]
      const original = baselineByEngine.get(key) as (typeof result.cards)[number]
      return {
        key,
        sameKernel: current.kernelFingerprint === original.kernelFingerprint,
        sameProgram: current.programFingerprint === original.programFingerprint,
        sameTask: current.taskFingerprint === original.taskFingerprint,
        sameAnswer: compact(current.answer) === renamed(original.answer, probeById.get(result.id)?.renames),
      }
    })
    const passed = result.relation === 'recompute'
      ? comparisons.length > 0
        && comparisons.every(comparison => comparison.sameKernel && comparison.sameProgram && comparison.sameTask)
        && comparisons.some(comparison => !comparison.sameAnswer)
      : comparisons.length > 0
        && comparisons.every(comparison =>
          comparison.sameKernel && comparison.sameProgram && comparison.sameTask && comparison.sameAnswer)
    return {
      caseId: result.id,
      baselineId: baseline.id,
      relation: result.relation,
      sharedTaskCount: comparisons.length,
      changedAnswerCount: comparisons.filter(comparison => !comparison.sameAnswer).length,
      passed,
      comparisons,
    }
  })

const uniqueCards = [...new Map(allCards.map(card => [card.id, card])).values()]
const selected = selectStructurallyDiverseProblems(uniqueCards, 24)
const engineAccepted = Object.fromEntries(engines.map(engine => [
  engine.id,
  caseResults.reduce(
    (total, result) => total + result.cards.filter(card => card.engine === engine.id).length,
    0,
  ),
]))
const kernelCount = new Set(caseResults.flatMap(result => result.cards.map(card => card.kernelFingerprint))).size
const programCount = new Set(caseResults.flatMap(result => result.cards.map(card => card.programFingerprint))).size
const taskCount = new Set(caseResults.flatMap(result => result.cards.map(card => card.taskFingerprint))).size
const taskAlgebraCount = new Set(caseResults.flatMap(result => result.cards.map(card => card.taskAlgebraFingerprint))).size
const certifiedCards = caseResults.flatMap(result => result.cards)
const taskAlgebras = [...new Map(certifiedCards.map(card => [
  card.taskAlgebraFingerprint,
  card.taskAlgebra,
])).values()]
const taskPrimitives = problemTaskPrimitiveSet(taskAlgebras)
const report = {
  schema: 2,
  measuredAt: new Date().toISOString(),
  purpose: bank.purpose,
  method: {
    probeBank: bankPath,
    expectedAnswersStored: false,
    requestedPerEngine: requested,
    engines: engines.map(engine => engine.id),
    acceptance: 'exact backend, independent replay, complete current-parent proof, and no registered completed route',
    mutationTest: 'coefficient changes must preserve kernel/program/task fingerprints and change at least one exact answer; alpha-renaming must preserve all four',
  },
  caseCount: caseResults.length,
  rawCardCount: certifiedCards.length,
  distinctCardCount: uniqueCards.length,
  distinctKernelCount: kernelCount,
  distinctProgramCount: programCount,
  distinctTaskCount: taskCount,
  distinctTaskAlgebraCount: taskAlgebraCount,
  taskPrimitiveCount: taskPrimitives.length,
  taskPrimitives,
  incompleteTaskAlgebraCount: certifiedCards.filter(card => !card.taskAlgebra.complete).length,
  emittedTaskAlgebraCount: certifiedCards.filter(card => card.taskAlgebraOrigin === 'emitted').length,
  inferredTaskAlgebraCount: certifiedCards.filter(card => card.taskAlgebraOrigin === 'inferred').length,
  engineAccepted,
  allCardsCertified: certifiedCards.length > 0 && certifiedCards.every(card =>
    card.exactBackend
    && card.independentCheck
    && card.completeParentProof
    && !card.registeredCompositeUsed
    && card.capabilityOrigin !== 'registered_parameterized_morphism'
  ),
  allRelationAuditsPassed: relationAudits.length > 0 && relationAudits.every(audit => audit.passed),
  relationAudits,
  selected: selected.map(card => {
    const fingerprints = problemStructureFingerprints(card)
    return {
      caseId: cardCase.get(card),
      id: card.id,
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
      difficulty: card.difficulty.score,
      verificationMethod: card.verification.method,
      hasDiagram: card.diagram !== undefined,
      kernelFingerprint: fingerprints.kernel,
      programFingerprint: fingerprints.program,
      taskFingerprint: fingerprints.task,
      taskAlgebraFingerprint: fingerprints.algebra,
      taskAlgebra: fingerprints.normalForm.task.algebra,
      taskAlgebraOrigin: fingerprints.normalForm.task.algebraOrigin,
    }
  }),
  cases: caseResults,
}

await writeFile(outputPath, `${JSON.stringify(report, null, 2)}\n`, 'utf8')
process.stdout.write(`${JSON.stringify({
  outputPath,
  caseCount: report.caseCount,
  rawCardCount: report.rawCardCount,
  distinctCardCount: report.distinctCardCount,
  distinctKernelCount: report.distinctKernelCount,
  distinctProgramCount: report.distinctProgramCount,
  distinctTaskCount: report.distinctTaskCount,
  distinctTaskAlgebraCount: report.distinctTaskAlgebraCount,
  taskPrimitiveCount: report.taskPrimitiveCount,
  taskPrimitives: report.taskPrimitives,
  incompleteTaskAlgebraCount: report.incompleteTaskAlgebraCount,
  emittedTaskAlgebraCount: report.emittedTaskAlgebraCount,
  inferredTaskAlgebraCount: report.inferredTaskAlgebraCount,
  engineAccepted: report.engineAccepted,
  allCardsCertified: report.allCardsCertified,
  allRelationAuditsPassed: report.allRelationAuditsPassed,
  relationAudits: report.relationAudits.map(audit => ({
    caseId: audit.caseId,
    relation: audit.relation,
    sharedTaskCount: audit.sharedTaskCount,
    changedAnswerCount: audit.changedAnswerCount,
    passed: audit.passed,
  })),
  selected: report.selected.map(card => ({
    caseId: card.caseId,
    family: card.family,
    difficulty: card.difficulty,
    hasDiagram: card.hasDiagram,
    answer: card.answer,
  })),
}, null, 2)}\n`)
