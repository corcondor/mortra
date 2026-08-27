import { createHash } from 'node:crypto'
import { readFileSync, writeFileSync } from 'node:fs'
import { homedir } from 'node:os'
import { resolve } from 'node:path'

import { compileDirectionalWord, verifyDirectionalWordCompilation } from '../lib/mortra/cross-domain/directional-word.js'
import { verifyDirectionalCssCertificate } from '../lib/mortra/cross-domain/directional-css-certificate.js'

type FrozenCase = {
  id: string
  word: string
  simple: boolean
  commutes: boolean
  displacementParity: boolean
}

type Manifest = {
  benchmarkId: string
  paperSource: {
    path: string
    sourceUrl: string
    pathOverrideEnvironment: string
    sha256: string
    definition: string
  }
  foundationalSource: {
    arxiv: string
    sourceUrl: string
    theorem: string
    deltaVector: string
    role: string
  }
  cases: FrozenCase[]
}

const root = resolve(import.meta.dirname, '..')
const manifestPath = resolve(root, 'data/directional-css-frozen-v1.json')
const outputPath = resolve(root, 'data/directional-css-certificate-experiment-2026-08-27.json')
const manifest = JSON.parse(readFileSync(manifestPath, 'utf8')) as Manifest

const sha256 = (content: Buffer | string) => createHash('sha256').update(content).digest('hex')
const configuredPaperSourcePath = process.env[manifest.paperSource.pathOverrideEnvironment]
  ?? manifest.paperSource.path
const paperSourcePath = configuredPaperSourcePath.startsWith('~/')
  ? resolve(homedir(), configuredPaperSourcePath.slice(2))
  : configuredPaperSourcePath
const paperBytes = readFileSync(paperSourcePath)
if (sha256(paperBytes) !== manifest.paperSource.sha256) throw new Error('directional-tile paper source hash changed')

type RawEdge = { orientation: 'horizontal' | 'vertical'; x: number; y: number }

type Direction = 'N' | 'E' | 'S' | 'W'

function independentlyExpandWord(word: string): Direction[] {
  const compact = word.replace(/\s+/g, '')
  const directions: Direction[] = []
  let consumed = ''
  for (const match of compact.matchAll(/([NESW])(?:\^(\d+))?/g)) {
    const token = match[0]
    const direction = match[1] as Direction
    const count = match[2] ? Number.parseInt(match[2], 10) : 1
    if (!Number.isSafeInteger(count) || count < 1) throw new Error(`invalid exponent in ${word}`)
    consumed += token
    directions.push(...Array.from({ length: count }, () => direction))
  }
  if (consumed !== compact || directions.length === 0) throw new Error(`invalid independent word: ${word}`)
  return directions
}

function independentEdges(directions: Direction[]): RawEdge[] {
  let x = 0
  let y = 0
  const edges: RawEdge[] = []
  for (const direction of directions) {
    const next = direction === 'N' ? { x, y: y + 1 }
      : direction === 'E' ? { x: x + 1, y }
        : direction === 'S' ? { x, y: y - 1 }
          : { x: x - 1, y }
    edges.push({
      orientation: y === next.y ? 'horizontal' : 'vertical',
      x: Math.min(x, next.x),
      y: Math.min(y, next.y),
    })
    x = next.x
    y = next.y
  }
  const minX = Math.min(...edges.map(edge => edge.x))
  const minY = Math.min(...edges.map(edge => edge.y))
  return edges.map(edge => ({ ...edge, x: edge.x - minX, y: edge.y - minY }))
}

function independentCssOracle(word: string) {
  const directions = independentlyExpandWord(word)
  const ordered = independentEdges(directions)
  const edgeKey = (edge: RawEdge) => `${edge.orientation}:${edge.x},${edge.y}`
  const unique = [...new Map(ordered.map(edge => [edgeKey(edge), edge])).values()]
  const gridSize = Math.max(...unique.flatMap(edge => [edge.x, edge.y])) + 2
  const dual = unique.map(edge => ({
    orientation: edge.orientation === 'horizontal' ? 'vertical' as const : 'horizontal' as const,
    x: gridSize - 1 - edge.x,
    y: gridSize - 1 - edge.y,
  }))
  const correlations = new Map<string, number>()
  for (const xEdge of unique) {
    for (const zEdge of dual) {
      if (xEdge.orientation !== zEdge.orientation) continue
      const key = `${xEdge.x - zEdge.x},${xEdge.y - zEdge.y}`
      correlations.set(key, (correlations.get(key) ?? 0) + 1)
    }
  }
  const displacementCounts = new Map<string, number>()
  const vector = (direction: Direction) => direction === 'N' ? { x: 0, y: 1 }
    : direction === 'E' ? { x: 1, y: 0 }
      : direction === 'S' ? { x: 0, y: -1 }
        : { x: -1, y: 0 }
  for (let earlier = 0; earlier < directions.length; earlier += 1) {
    for (let later = earlier + 1; later < directions.length; later += 1) {
      const first = vector(directions[earlier])
      const last = vector(directions[later])
      let dx2 = first.x + last.x
      let dy2 = first.y + last.y
      for (let between = earlier + 1; between < later; between += 1) {
        const step = vector(directions[between])
        dx2 += 2 * step.x
        dy2 += 2 * step.y
      }
      if (Math.abs(dy2) % 2 === 1) {
        const key = `${dx2},${dy2}`
        displacementCounts.set(key, (displacementCounts.get(key) ?? 0) + 1)
      }
    }
  }
  return {
    simple: unique.length === ordered.length,
    commutes: [...correlations.values()].every(count => count % 2 === 0),
    displacementParity: [...displacementCounts.values()].every(count => count % 2 === 0),
  }
}

function enumerateWords(maxLength: number): string[] {
  const alphabet = ['N', 'E', 'S', 'W']
  let layer = ['']
  const words: string[] = []
  for (let length = 1; length <= maxLength; length += 1) {
    layer = layer.flatMap(prefix => alphabet.map(letter => prefix + letter))
    words.push(...layer)
  }
  return words
}

const cases = manifest.cases.map(item => {
  const built = compileDirectionalWord(item.id, item.word)
  if (!built.compilation) throw new Error(`${item.id}: ${built.errors.join('; ')}`)
  const compilation = built.compilation
  const certificate = compilation.stabilizer.cssCertificate
  const replayErrors = verifyDirectionalWordCompilation(compilation)
  const observed = {
    simple: compilation.stabilizer.codeAdmissibility.simpleEdgeSupport,
    commutes: compilation.stabilizer.codeAdmissibility.mutualPrimalDualCommutation,
    displacementParity: compilation.stabilizer.codeAdmissibility.displacementParityCondition,
  }
  const expected = {
    simple: item.simple,
    commutes: item.commutes,
    displacementParity: item.displacementParity,
  }
  const independent = independentCssOracle(item.word)
  return {
    id: item.id,
    word: item.word,
    expected,
    observed,
    expectationMatched: JSON.stringify(expected) === JSON.stringify(observed),
    independentOracleMatched: JSON.stringify(independent) === JSON.stringify(observed),
    certificateReplayAccepted: replayErrors.length === 0,
    certificateReplayErrors: replayErrors,
    distinctSupportEdges: compilation.stabilizer.weight,
    gridSize: certificate.gridSize,
    checkedMutualEdges: certificate.mutualCondition.checkedEdges,
    checkedRelativeTranslations: certificate.staticCssCommutation.checkedRelativeTranslations,
    maximumStaticOverlap: certificate.staticCssCommutation.maximumOverlap,
    checkedOrderedPairs: certificate.displacementParity.checkedOrderedPairs,
    oddVerticalVectorKinds: certificate.displacementParity.oddVerticalVectors.length,
    parityViolationKinds: certificate.displacementParity.oddMultiplicityViolations.length,
  }
})

const mutationSource = compileDirectionalWord('mutation-control', 'NESEN').compilation!
const mutated = structuredClone(mutationSource)
mutated.stabilizer.cssCertificate.staticCssCommutation.witnesses[0].overlap += 1
const mutationRejected = verifyDirectionalWordCompilation(mutated).some(error =>
  error.includes('CSS certificate replay mismatch'))

const exhaustiveWords = enumerateWords(6)
const exhaustive = exhaustiveWords.map((word, index) => {
  const built = compileDirectionalWord(`exhaustive-${index}`, word)
  if (!built.compilation) throw new Error(`${word}: ${built.errors.join('; ')}`)
  const compilation = built.compilation
  const expected = independentCssOracle(word)
  const observed = {
    simple: compilation.stabilizer.codeAdmissibility.simpleEdgeSupport,
    commutes: compilation.stabilizer.codeAdmissibility.mutualPrimalDualCommutation,
    displacementParity: compilation.stabilizer.codeAdmissibility.displacementParityCondition,
  }
  const replayAccepted = verifyDirectionalCssCertificate(
    compilation.geometry,
    compilation.stabilizer.cssCertificate,
  ).length === 0
  const stale = structuredClone(compilation.stabilizer.cssCertificate)
  stale.gridSize += 1
  const mutationRejected = verifyDirectionalCssCertificate(
    compilation.geometry,
    stale,
  ).some(error => error.includes('CSS certificate replay mismatch'))
  return {
    word,
    expected,
    observed,
    oracleMatched: JSON.stringify(expected) === JSON.stringify(observed),
    replayAccepted,
    mutationRejected,
  }
})

const exhaustiveSummary = {
  maxLength: 6,
  total: exhaustive.length,
  orderedResultSha256: sha256(JSON.stringify(exhaustive)),
  independentOracleMatches: exhaustive.filter(item => item.oracleMatched).length,
  certificateReplaysAccepted: exhaustive.filter(item => item.replayAccepted).length,
  staleCertificatesRejected: exhaustive.filter(item => item.mutationRejected).length,
  simpleSupports: exhaustive.filter(item => item.observed.simple).length,
  staticCommutationAccepted: exhaustive.filter(item => item.observed.commutes).length,
  displacementParityAccepted: exhaustive.filter(item => item.observed.displacementParity).length,
  fullyDirectional: exhaustive.filter(item =>
    item.observed.simple && item.observed.commutes && item.observed.displacementParity).length,
}

const accepted = cases.filter(item =>
  item.expectationMatched && item.independentOracleMatched && item.certificateReplayAccepted).length
const result = {
  experiment: 'directional_css_exact_mutual_commutation_and_displacement_parity',
  benchmarkId: manifest.benchmarkId,
  principle: {
    mutualCondition: 'H(a,b) maps to V(B-1-a,B-1-b), and V maps to H',
    commutation: 'finite X/Z support cross-correlation enumerates every relative anchor translation with nonzero overlap; CSS commutation requires even overlap',
    displacementParity: 'edge centres are represented in doubled integer coordinates; every ordered vector with odd dy2 must have even multiplicity',
  },
  provenance: {
    manifest: 'data/directional-css-frozen-v1.json',
    manifestSha256: sha256(readFileSync(manifestPath)),
    paperSource: {
      ...manifest.paperSource,
      observedPath: configuredPaperSourcePath,
    },
    foundationalSource: manifest.foundationalSource,
    implementation: 'lib/mortra/cross-domain/directional-css-certificate.ts',
    implementationSha256: sha256(readFileSync(resolve(root, 'lib/mortra/cross-domain/directional-css-certificate.ts'))),
    usesExternalLlm: false,
  },
  summary: {
    total: cases.length,
    accepted,
    expectationAccuracy: accepted / cases.length,
    independentOracleMatches: cases.filter(item => item.independentOracleMatched).length,
    certificateReplayRate: cases.filter(item => item.certificateReplayAccepted).length / cases.length,
    falseAccepts: cases.filter(item => !item.expectationMatched && item.observed.simple && item.observed.commutes && item.observed.displacementParity).length,
    mutationRejected,
    paperPositiveCases: cases.filter(item => item.id.startsWith('paper-')).length,
    paperPositiveCasesCertified: cases.filter(item =>
      item.id.startsWith('paper-')
      && item.expectationMatched
      && item.independentOracleMatched
      && item.certificateReplayAccepted).length,
    checkedRelativeTranslations: cases.reduce((sum, item) => sum + item.checkedRelativeTranslations, 0),
    checkedOrderedPairs: cases.reduce((sum, item) => sum + item.checkedOrderedPairs, 0),
  },
  exhaustiveSummary,
  cases,
  conclusion: accepted === cases.length
    && mutationRejected
    && exhaustiveSummary.independentOracleMatches === exhaustiveSummary.total
    && exhaustiveSummary.certificateReplaysAccepted === exhaustiveSummary.total
    && exhaustiveSummary.staleCertificatesRejected === exhaustiveSummary.total
    ? 'The frozen cases and all words through length six agree with an independent oracle; every certificate replays and every stale certificate is rejected.'
    : 'The directional CSS implementation did not meet the frozen acceptance criterion.',
}

writeFileSync(outputPath, `${JSON.stringify(result, null, 2)}\n`)
console.log(JSON.stringify(result.summary, null, 2))
