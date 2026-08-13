import { createHash } from 'node:crypto'
import { mkdir, readFile, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { performance } from 'node:perf_hooks'
import { fileURLToPath } from 'node:url'

import {
  compileFiniteStateArtifact,
  solveByDirectIteration,
  solveWithFiniteStateDiagram,
  transitionState,
  verifyFiniteStateDiagram,
  type FiniteRecurrenceSpec,
} from '../lib/mortra/diagram/finite-state-transition.js'

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DATASET_PATH = path.join(ROOT, 'data', 'finite-state-diagram-benchmark.json')
const raw = await readFile(DATASET_PATH, 'utf8')
const dataset = JSON.parse(raw) as { name: string; description: string; cases: FiniteRecurrenceSpec[] }
const digest = createHash('sha256').update(raw).digest('hex').slice(0, 16)
const STEP_BUDGET = 10_000
const MAX_STATES = 200_000

const key = (state: number[]) => state.join(',')

/** Independent oracle: Floyd cycle finding stores no graph and shares no index-reduction code. */
function oracle(spec: FiniteRecurrenceSpec): number {
  const initial = spec.initial.map(value => ((value % spec.modulus) + spec.modulus) % spec.modulus)
  const next = (state: number[]) => transitionState(spec, state)
  let tortoise = next(initial)
  let hare = next(next(initial))
  let guard = 0
  while (key(tortoise) !== key(hare)) {
    tortoise = next(tortoise)
    hare = next(next(hare))
    guard += 1
    if (guard > MAX_STATES) throw new Error(`${spec.id}: oracle cycle search exceeded MAX_STATES`)
  }
  let mu = BigInt(0)
  tortoise = initial
  while (key(tortoise) !== key(hare)) {
    tortoise = next(tortoise)
    hare = next(hare)
    mu += BigInt(1)
  }
  let period = BigInt(1)
  hare = next(tortoise)
  while (key(tortoise) !== key(hare)) {
    hare = next(hare)
    period += BigInt(1)
  }
  const target = BigInt(spec.targetIndex)
  const reduced = target < mu ? target : mu + ((target - mu) % period)
  let state = initial
  for (let index = BigInt(0); index < reduced; index += BigInt(1)) state = next(state)
  return state[0]
}

const rows = dataset.cases.map(spec => {
  const expected = oracle(spec)
  const baselineStart = performance.now()
  const baseline = solveByDirectIteration(spec, STEP_BUDGET)
  const baselineMs = performance.now() - baselineStart
  const diagramStart = performance.now()
  const diagram = solveWithFiniteStateDiagram(spec, { maxStates: MAX_STATES })
  const diagramMs = performance.now() - diagramStart
  const verified = diagram.diagram ? verifyFiniteStateDiagram(spec, diagram.diagram).certified : false
  return {
    id: spec.id,
    expected,
    baseline_status: baseline.status,
    baseline_answer: baseline.answer ?? null,
    baseline_correct: baseline.status === 'certified' && baseline.answer === expected,
    baseline_operations: baseline.operations,
    baseline_runtime_ms: Number(baselineMs.toFixed(3)),
    diagram_status: diagram.status,
    diagram_answer: diagram.answer ?? null,
    diagram_correct: diagram.status === 'certified' && diagram.answer === expected && verified,
    diagram_operations: diagram.operations,
    diagram_runtime_ms: Number(diagramMs.toFixed(3)),
    reachable_states: diagram.diagram?.carriers.length ?? null,
    preperiod: diagram.diagram?.structure.preperiod ?? null,
    period: diagram.diagram?.structure.period ?? null,
    reduced_index: diagram.reducedIndex ?? null,
  }
})

const tamperCases = dataset.cases.slice(0, 5).map(spec => {
  const solved = solveWithFiniteStateDiagram(spec)
  if (!solved.diagram) return false
  const tampered = structuredClone(solved.diagram)
  tampered.structure.transitions[0].emitted = (tampered.structure.transitions[0].emitted + 1) % spec.modulus
  return verifyFiniteStateDiagram(spec, tampered).certified
})

const coefficientMetamorphic = dataset.cases.slice(0, 8).map(spec => {
  const base = solveWithFiniteStateDiagram(spec)
  const transformed = solveWithFiniteStateDiagram({
    ...spec,
    id: `${spec.id}:coefficient-metamorphic`,
    initial: spec.initial.map((value, index) => value + spec.modulus * (index + 2)),
    update: {
      terms: spec.update.terms.map((term, index) => ({
        ...term,
        coefficient: term.coefficient + spec.modulus * (index + 1),
      })),
    },
  })
  return base.answer === transformed.answer
    && JSON.stringify(base.diagram?.carriers.map(state => state.values))
      === JSON.stringify(transformed.diagram?.carriers.map(state => state.values))
})

const baselineSolved = rows.filter(row => row.baseline_correct).length
const diagramSolved = rows.filter(row => row.diagram_correct).length
const baselineWrong = rows.filter(row => row.baseline_status === 'certified' && !row.baseline_correct).length
const diagramWrong = rows.filter(row => row.diagram_status === 'certified' && !row.diagram_correct).length
const proposedCycles = rows.filter(row => row.diagram_status === 'certified').length
const verifiedCycles = rows.filter(row => row.diagram_correct).length
const summary = {
  cases: rows.length,
  baseline_certified_solve_rate: baselineSolved / rows.length,
  diagram_certified_solve_rate: diagramSolved / rows.length,
  baseline_wrong: baselineWrong,
  diagram_wrong: diagramWrong,
  baseline_abstained: rows.filter(row => row.baseline_status === 'abstained').length,
  diagram_abstained: rows.filter(row => row.diagram_status === 'abstained').length,
  cycle_candidate_precision: verifiedCycles / Math.max(1, proposedCycles),
  newly_closed_proofs: rows.filter(row => row.diagram_correct && !row.baseline_correct).length,
  tampered_certificates_false_accepts: tamperCases.filter(Boolean).length,
  metamorphic_preservation_rate: coefficientMetamorphic.filter(Boolean).length / coefficientMetamorphic.length,
  baseline_operations: rows.reduce((sum, row) => sum + row.baseline_operations, 0),
  diagram_operations: rows.reduce((sum, row) => sum + row.diagram_operations, 0),
  baseline_runtime_ms: Number(rows.reduce((sum, row) => sum + row.baseline_runtime_ms, 0).toFixed(3)),
  diagram_runtime_ms: Number(rows.reduce((sum, row) => sum + row.diagram_runtime_ms, 0).toFixed(3)),
}

const artifact = {
  experiment: 'finite-state-recurrence-diagram-ab-v1',
  recorded_on: '2026-08-13',
  implementation_base_commit: '1926596fb943f481bb7cff05b51e019567b72f88',
  dataset: dataset.name,
  dataset_digest: digest,
  controls: {
    surface_parser: 'held constant; typed recurrence specifications are the common input',
    baseline: `direct recurrence execution with step budget ${STEP_BUDGET}`,
    intervention: 'reachable finite-state diagram plus certified cycle quotient',
    max_states: MAX_STATES,
    parallelism: 1,
    oracle: 'independent Floyd cycle finder without graph materialization',
  },
  summary,
  rows,
}

const demoSpec = dataset.cases.find(item => item.id === 'tokyo-nonlinear-mod-17-huge')!
const demoSolution = solveWithFiniteStateDiagram(demoSpec)
const demo = compileFiniteStateArtifact(demoSolution)

await mkdir(path.join(ROOT, 'data'), { recursive: true })
await writeFile(
  path.join(ROOT, 'data', 'finite-state-diagram-experiment.json'),
  `${JSON.stringify(artifact, null, 2)}\n`,
  'utf8',
)
await writeFile(
  path.join(ROOT, 'data', 'finite-state-diagram-demo.json'),
  `${JSON.stringify(demo, null, 2)}\n`,
  'utf8',
)

console.log(JSON.stringify({ dataset_digest: digest, ...summary }, null, 2))
if (diagramSolved !== rows.length || diagramWrong !== 0 || tamperCases.some(Boolean)
  || coefficientMetamorphic.some(value => !value)) process.exit(1)
