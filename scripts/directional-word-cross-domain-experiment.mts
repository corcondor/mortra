import { createHash } from 'node:crypto'
import { existsSync, readFileSync, renameSync, rmSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'

import {
  compileDirectionalWord,
  endpointNormalFormLosesSupport,
  type Direction,
  verifyDirectionalWordCompilation,
  verifyEndpointNormalFormCertificate,
} from '../lib/mortra/cross-domain/directional-word.js'
import {
  buildCanonicalNormalFormAtlas,
  normalizeGeneratorWord,
  verifyCanonicalNormalFormAtlas,
  verifyNormalizationWitness,
} from '../lib/mortra/kernel/canonical-generator-normal-form.js'

type Manifest = {
  benchmarkId: string
  frozenOn: string
  generatorAlphabet: Direction[]
  exhaustiveMaxLength: number
  namedExamples: { id: string; input: string; expectedWord: string; expectedWeight: number }[]
}

type Counters = {
  certified: number
  geometry: number
  stabilizer: number
  schedule: number
  matrix: number
  staleCertificateRejected: number
  endpointQuotientSupportLoss: number
  simpleEdgeSupportCandidates: number
  originalSteps: number
  endpointNormalSteps: number
  firstErrors: { id: string; errors: string[] }[]
}

type Checkpoint = {
  inputDigest: string
  nextIndex: number
  counters: Counters
}

const here = dirname(fileURLToPath(import.meta.url))
const root = resolve(here, '..')
const manifestPath = resolve(root, 'data/directional-word-cross-domain-frozen-v1.json')
const resultPath = resolve(root, 'data/directional-word-cross-domain-benchmark-2026-08-27.json')
const checkpointPath = `${resultPath}.progress.json`
const manifestText = readFileSync(manifestPath, 'utf8')
const manifest = JSON.parse(manifestText) as Manifest
const scriptText = readFileSync(fileURLToPath(import.meta.url), 'utf8')
const implementationText = [
  'lib/mortra/cross-domain/directional-word.ts',
  'lib/mortra/kernel/canonical-generator-normal-form.ts',
  'lib/mortra/kernel/semantic-kernel.ts',
].map(path => readFileSync(resolve(root, path), 'utf8')).join('\n')
const inputDigest = createHash('sha256')
  .update(scriptText).update('\n').update(implementationText).update('\n').update(manifestText)
  .digest('hex')

function enumerateWords(alphabet: Direction[], maxLength: number): string[] {
  const words: string[] = []
  let frontier = ['']
  for (let length = 1; length <= maxLength; length += 1) {
    const next: string[] = []
    for (const prefix of frontier) {
      for (const symbol of alphabet) next.push(`${prefix}${symbol}`)
    }
    words.push(...next)
    frontier = next
  }
  return words
}

function oracle(word: Direction[]) {
  const vector: Record<Direction, [number, number]> = {
    N: [0, 1], E: [1, 0], S: [0, -1], W: [-1, 0],
  }
  const opposite: Record<Direction, Direction> = { N: 'S', E: 'W', S: 'N', W: 'E' }
  let x = 0
  let y = 0
  const orderedEdges: string[] = []
  for (const symbol of word) {
    const [dx, dy] = vector[symbol]
    const nx = x + dx
    const ny = y + dy
    const left = `${x},${y}`
    const right = `${nx},${ny}`
    orderedEdges.push(left < right ? `${left}|${right}` : `${right}|${left}`)
    x = nx
    y = ny
  }
  return {
    endpoint: { x, y },
    orderedEdges,
    support: [...new Set(orderedEdges)].sort(),
    inverse: [...word].reverse().map(symbol => opposite[symbol]),
  }
}

function emptyCounters(): Counters {
  return {
    certified: 0,
    geometry: 0,
    stabilizer: 0,
    schedule: 0,
    matrix: 0,
    staleCertificateRejected: 0,
    endpointQuotientSupportLoss: 0,
    simpleEdgeSupportCandidates: 0,
    originalSteps: 0,
    endpointNormalSteps: 0,
    firstErrors: [],
  }
}

function writeJsonAtomic(path: string, value: unknown) {
  const temporary = `${path}.tmp`
  writeFileSync(temporary, `${JSON.stringify(value, null, 2)}\n`, 'utf8')
  renameSync(temporary, path)
}

const cases = [
  ...enumerateWords(manifest.generatorAlphabet, manifest.exhaustiveMaxLength)
    .map((input, index) => ({ id: `exhaustive-${index + 1}`, input, expectedWord: input })),
  ...manifest.namedExamples,
]

let checkpoint: Checkpoint = { inputDigest, nextIndex: 0, counters: emptyCounters() }
if (existsSync(checkpointPath)) {
  const saved = JSON.parse(readFileSync(checkpointPath, 'utf8')) as Checkpoint
  if (saved.inputDigest === inputDigest && saved.nextIndex <= cases.length) checkpoint = saved
}

for (let index = checkpoint.nextIndex; index < cases.length; index += 1) {
  const item = cases[index]
  const built = compileDirectionalWord(item.id, item.input)
  const errors = [...built.errors]
  if (!built.compilation) {
    errors.push('compiler returned no artifact')
  } else {
    const compilation = built.compilation
    const expected = item.expectedWord.split('') as Direction[]
    const independent = oracle(expected)
    const geometryOk = JSON.stringify(compilation.geometry.endpoint) === JSON.stringify(independent.endpoint)
      && compilation.geometry.edges.length === expected.length
      && compilation.geometry.vertices.length === expected.length + 1
    const stabilizerOk = JSON.stringify(compilation.stabilizer.orderedSupport) === JSON.stringify(independent.orderedEdges)
      && JSON.stringify(compilation.stabilizer.support) === JSON.stringify(independent.support)
    const scheduleOk = compilation.schedule.interactionDepth === expected.length
      && compilation.schedule.roundDepthWithPreparationAndMeasurement === expected.length + 2
      && compilation.schedule.inverseWord.join('') === independent.inverse.join('')
      && compilation.schedule.forwardInverseRestoresOrigin
    const matrixOk = compilation.translationMatrix[0][2] === independent.endpoint.x
      && compilation.translationMatrix[1][2] === independent.endpoint.y
    if (geometryOk) checkpoint.counters.geometry += 1
    else errors.push('independent geometry oracle mismatch')
    if (stabilizerOk) checkpoint.counters.stabilizer += 1
    else errors.push('independent stabilizer oracle mismatch')
    if (scheduleOk) checkpoint.counters.schedule += 1
    else errors.push('independent schedule oracle mismatch')
    if (matrixOk) checkpoint.counters.matrix += 1
    else errors.push('independent matrix oracle mismatch')

    errors.push(...verifyDirectionalWordCompilation(compilation))
    const named = manifest.namedExamples.find(example => example.id === item.id)
    if (named && compilation.stabilizer.weight !== named.expectedWeight) {
      errors.push(`paper weight mismatch: expected ${named.expectedWeight}, received ${compilation.stabilizer.weight}`)
    }
    if (!errors.length) checkpoint.counters.certified += 1

    const stale = structuredClone(compilation.endpointNormalForm)
    stale.originalMatrix[0][2] += 1
    if (verifyEndpointNormalFormCertificate(stale, compilation.steps).length > 0) {
      checkpoint.counters.staleCertificateRejected += 1
    }
    if (endpointNormalFormLosesSupport(compilation)) checkpoint.counters.endpointQuotientSupportLoss += 1
    if (compilation.stabilizer.codeAdmissibility.simpleEdgeSupport) {
      checkpoint.counters.simpleEdgeSupportCandidates += 1
    }
    checkpoint.counters.originalSteps += compilation.steps.length
    checkpoint.counters.endpointNormalSteps += compilation.endpointNormalForm.normalWord.length
  }
  if (errors.length && checkpoint.counters.firstErrors.length < 20) {
    checkpoint.counters.firstErrors.push({ id: item.id, errors: [...new Set(errors)] })
  }
  checkpoint.nextIndex = index + 1
  if ((index + 1) % 250 === 0 || index + 1 === cases.length) writeJsonAtomic(checkpointPath, checkpoint)
}

type TorusPoint = { x: number; y: number }
const modulus = 7
const mod = (value: number) => ((value % modulus) + modulus) % modulus
const key = (state: TorusPoint) => `${state.x},${state.y}`
const atlas = buildCanonicalNormalFormAtlas<TorusPoint>({
  initial: { x: 0, y: 0 },
  key,
  generators: [
    { id: 'E', apply: state => ({ x: mod(state.x + 1), y: state.y }) },
    { id: 'N', apply: state => ({ x: state.x, y: mod(state.y + 1) }) },
    { id: 'W', apply: state => ({ x: mod(state.x - 1), y: state.y }) },
    { id: 'S', apply: state => ({ x: state.x, y: mod(state.y - 1) }) },
  ],
})
const atlasErrors = verifyCanonicalNormalFormAtlas(atlas, key)
const normalization = normalizeGeneratorWord(atlas, key, [
  'E', 'E', 'E', 'E', 'E', 'E', 'E', 'E',
  'N', 'N', 'N', 'N', 'N', 'N', 'N',
])
const normalizationErrors = normalization.witness
  ? verifyNormalizationWitness(atlas, key, normalization.witness)
  : normalization.errors

const total = cases.length
const counters = checkpoint.counters
const result = {
  benchmarkId: manifest.benchmarkId,
  completedAt: new Date().toISOString(),
  inputDigest,
  method: {
    model: 'symbolic only; no external LLM',
    exhaustiveWords: total - manifest.namedExamples.length,
    namedPaperExamples: manifest.namedExamples.length,
    totalCases: total,
    generatorSymbols: manifest.generatorAlphabet.length,
    existingMathSortsReused: ['Sequence', 'VisualElement', 'Stabilizer', 'Matrix'],
    newMathSortDeclarations: 0,
    independentOracles: ['direct coordinate walk', 'undirected edge support', 'inverse schedule', 'homogeneous translation'],
    durableCheckpoint: 'input-digest guarded, atomic periodic checkpoint',
  },
  results: {
    certified: `${counters.certified}/${total}`,
    geometry: `${counters.geometry}/${total}`,
    stabilizer: `${counters.stabilizer}/${total}`,
    schedule: `${counters.schedule}/${total}`,
    matrix: `${counters.matrix}/${total}`,
    staleCertificateRejected: `${counters.staleCertificateRejected}/${total}`,
    falseAccepts: total - counters.staleCertificateRejected,
    endpointQuotientSupportLossCases: counters.endpointQuotientSupportLoss,
    simpleEdgeSupportCandidates: counters.simpleEdgeSupportCandidates,
    originalStepSymbols: counters.originalSteps,
    endpointNormalFormSymbols: counters.endpointNormalSteps,
    endpointActionCompressionPercent: Number((100 * (1 - counters.endpointNormalSteps / counters.originalSteps)).toFixed(3)),
    sharedParseStepCopies: counters.originalSteps,
    fourIndependentViewStepCopies: counters.originalSteps * 4,
    representationDuplicationAvoidedPercent: 75,
  },
  finiteGeneratedAction: {
    stateSpace: `Z/${modulus}Z x Z/${modulus}Z`,
    reachableStates: atlas.certificate.reachableStates,
    maximumCanonicalDistance: atlas.certificate.maxDistance,
    distanceHistogram: atlas.certificate.distanceHistogram,
    deterministicDigest: atlas.certificate.deterministicDigest,
    verificationErrors: atlasErrors,
    longWordLength: normalization.witness?.originalLength,
    canonicalLength: normalization.witness?.canonicalLength,
    normalizationErrors,
  },
  errors: counters.firstErrors,
  allClaimsPassed: counters.certified === total
    && counters.geometry === total
    && counters.stabilizer === total
    && counters.schedule === total
    && counters.matrix === total
    && counters.staleCertificateRejected === total
    && atlasErrors.length === 0
    && normalizationErrors.length === 0,
  limitations: [
    'This proves cross-representation compilation and canonical finite-action reduction, not quantum-code distance or fault tolerance.',
    'Mutual primal/dual commutation and the displacement-parity condition for a valid directional CSS code are not checked.',
    'Endpoint normal form is valid only in the translation-action quotient and must not replace support or schedule.',
    'The benchmark contains structural words, not competition-level problems.',
  ],
}

writeJsonAtomic(resultPath, result)
if (existsSync(checkpointPath)) rmSync(checkpointPath)
console.log(JSON.stringify(result, null, 2))
if (!result.allClaimsPassed) process.exitCode = 1
