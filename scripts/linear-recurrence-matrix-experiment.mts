import { createHash } from 'node:crypto'
import { mkdir, readFile, rename, writeFile } from 'node:fs/promises'
import path from 'node:path'
import { performance } from 'node:perf_hooks'
import { fileURLToPath } from 'node:url'

import {
  buildLinearRecurrenceMatrixChart,
  reconstructFiniteRecurrence,
  solveWithLinearRecurrenceMatrix,
  verifyLinearRecurrenceMatrixChart,
} from '../lib/mortra/chart/linear-recurrence-matrix.js'
import {
  solveWithFiniteStateDiagram,
  verifyFiniteStateDiagram,
  type FiniteRecurrenceSpec,
} from '../lib/mortra/diagram/finite-state-transition.js'

type BenchmarkRow = {
  id: string
  expected: number | null
  eligible: boolean
  matrixStatus: string
  matrixAnswer: number | null
  matrixCorrect: boolean
  matrixRuntimeMs: number
  matrixMultiplications: number
  finiteStateRuntimeMs: number
  finiteStateReachableStates: number | null
  roundTripCorrect: boolean
  mutationRejected: boolean | null
  errors: string[]
}

type Progress = {
  experiment: string
  datasetDigest: string
  completed: boolean
  rows: BenchmarkRow[]
}

const ROOT = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..')
const DATASET_PATH = path.join(ROOT, 'data', 'finite-state-diagram-benchmark.json')
const PROGRESS_PATH = path.join(ROOT, 'data', 'linear-recurrence-matrix-benchmark.progress.json')
const OUTPUT_PATH = path.join(ROOT, 'data', 'linear-recurrence-matrix-benchmark-2026-08-27.json')
const raw = await readFile(DATASET_PATH, 'utf8')
const dataset = JSON.parse(raw) as { name: string; description: string; cases: FiniteRecurrenceSpec[] }
const datasetDigest = createHash('sha256').update(raw).digest('hex')
const restart = process.argv.includes('--restart')

async function saveProgress(progress: Progress): Promise<void> {
  await mkdir(path.dirname(PROGRESS_PATH), { recursive: true })
  const temporary = `${PROGRESS_PATH}.tmp`
  await writeFile(temporary, `${JSON.stringify(progress, null, 2)}\n`, 'utf8')
  await rename(temporary, PROGRESS_PATH)
}

async function loadProgress(): Promise<Progress> {
  if (restart) {
    return { experiment: 'linear-recurrence-matrix-chart-v1', datasetDigest, completed: false, rows: [] }
  }
  try {
    const stored = JSON.parse(await readFile(PROGRESS_PATH, 'utf8')) as Progress
    if (stored.datasetDigest === datasetDigest && stored.experiment === 'linear-recurrence-matrix-chart-v1') {
      return stored
    }
  } catch {
    // A missing or stale checkpoint starts a fresh frozen-dataset run.
  }
  return { experiment: 'linear-recurrence-matrix-chart-v1', datasetDigest, completed: false, rows: [] }
}

const progress = await loadProgress()
const completedIds = new Set(progress.rows.map(row => row.id))

for (const spec of dataset.cases) {
  if (completedIds.has(spec.id)) continue

  const finiteStateStarted = performance.now()
  const finiteState = solveWithFiniteStateDiagram(spec)
  const finiteStateRuntimeMs = performance.now() - finiteStateStarted
  const finiteStateVerified = finiteState.diagram
    ? verifyFiniteStateDiagram(spec, finiteState.diagram).certified
    : false
  const expected = finiteState.status === 'certified' && finiteStateVerified
    ? finiteState.answer ?? null
    : null

  const matrixStarted = performance.now()
  const matrix = solveWithLinearRecurrenceMatrix(spec)
  const matrixRuntimeMs = performance.now() - matrixStarted
  const eligible = matrix.status === 'certified'
  let roundTripCorrect = false
  let mutationRejected: boolean | null = null

  if (matrix.chart && expected !== null) {
    const reconstructed = reconstructFiniteRecurrence(matrix.chart)
    const roundTrip = solveWithFiniteStateDiagram(reconstructed)
    roundTripCorrect = roundTrip.status === 'certified' && roundTrip.answer === expected

    const mutation = structuredClone(matrix.chart)
    const recurrenceRow = mutation.normalForm.order - 1
    mutation.transitionMatrix[recurrenceRow][0] = (
      mutation.transitionMatrix[recurrenceRow][0] + 1
    ) % mutation.normalForm.modulus
    mutationRejected = !verifyLinearRecurrenceMatrixChart(mutation).certified
  }

  progress.rows.push({
    id: spec.id,
    expected,
    eligible,
    matrixStatus: matrix.status,
    matrixAnswer: matrix.answer ?? null,
    matrixCorrect: eligible && expected !== null && matrix.answer === expected,
    matrixRuntimeMs: Number(matrixRuntimeMs.toFixed(3)),
    matrixMultiplications: matrix.matrixMultiplications,
    finiteStateRuntimeMs: Number(finiteStateRuntimeMs.toFixed(3)),
    finiteStateReachableStates: finiteState.diagram?.carriers.length ?? null,
    roundTripCorrect,
    mutationRejected,
    errors: matrix.errors,
  })
  await saveProgress(progress)
  console.log(`[${progress.rows.length}/${dataset.cases.length}] ${spec.id}: ${matrix.status}`)
}

progress.completed = progress.rows.length === dataset.cases.length
await saveProgress(progress)

const eligibleRows = progress.rows.filter(row => row.eligible)
const abstainedRows = progress.rows.filter(row => row.matrixStatus === 'abstained')
const summary = {
  cases: progress.rows.length,
  eligibleLinearOrAffine: eligibleRows.length,
  certifiedCorrect: eligibleRows.filter(row => row.matrixCorrect).length,
  certifiedWrong: eligibleRows.filter(row => !row.matrixCorrect).length,
  nonlinearAbstentions: abstainedRows.length,
  invalid: progress.rows.filter(row => row.matrixStatus === 'invalid').length,
  roundTripCertified: eligibleRows.filter(row => row.roundTripCorrect).length,
  mutationFalseAccepts: eligibleRows.filter(row => row.mutationRejected === false).length,
  matrixMultiplications: eligibleRows.reduce((sum, row) => sum + row.matrixMultiplications, 0),
  finiteStateReachableStates: eligibleRows.reduce(
    (sum, row) => sum + (row.finiteStateReachableStates ?? 0),
    0,
  ),
  matrixRuntimeMs: Number(eligibleRows.reduce((sum, row) => sum + row.matrixRuntimeMs, 0).toFixed(3)),
  finiteStateRuntimeMs: Number(eligibleRows.reduce((sum, row) => sum + row.finiteStateRuntimeMs, 0).toFixed(3)),
}

const artifact = {
  experiment: progress.experiment,
  recordedOn: '2026-08-27',
  frozenDataset: dataset.name,
  frozenDatasetDigestSha256: datasetDigest,
  frozenBeforeImplementation: true,
  hypothesis: 'one canonical affine-companion chart can preserve answers across recurrence, matrix, characteristic-polynomial, and finite-state representations without problem-specific rules',
  intervention: {
    acceptedLanguage: 'arbitrary-order affine-linear recurrence over Z/mZ',
    forward: 'normalized recurrence -> augmented companion matrix -> characteristic polynomial',
    inverse: 'canonical companion matrix -> normalized recurrence',
    independentChecks: [
      'exact modular Cayley-Hamilton replay',
      'matrix exponentiation versus independently certified reachable-state cycle quotient',
      'forward/inverse round trip',
      'matrix mutation rejection',
    ],
    nonlinearPolicy: 'abstain and retain the general finite-state polynomial-transition solver',
    persistence: 'atomic per-case checkpoint with dataset-digest validation and resume',
  },
  summary,
  rows: progress.rows,
}

await writeFile(OUTPUT_PATH, `${JSON.stringify(artifact, null, 2)}\n`, 'utf8')
console.log(JSON.stringify(summary, null, 2))

if (!progress.completed
  || summary.certifiedWrong !== 0
  || summary.roundTripCertified !== summary.eligibleLinearOrAffine
  || summary.mutationFalseAccepts !== 0
  || summary.invalid !== 0) process.exit(1)
