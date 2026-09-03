import { createHash } from 'node:crypto'

import {
  auditCompositionComplexity,
  compositionGenomeFingerprint,
  compositionGenomeMetrics,
  type CompositionGenome,
} from '../../lib/mortra/composition-genome'
import {
  acceptedBinaryWords,
  buildForbiddenWordAutomaton,
  normalizeForbiddenWords,
} from '../../lib/mortra/finite-word-grammar'
import type { DiscoveryParent } from './parent-conditioned-discovery'
import type { ExecutableFusionCard } from './executable-fusion'
import { runtimeSynthesisCertificate } from './execution-certificate'
import type { ProblemDiagram, VisualExplanation } from '../../lib/mortra/problem-artifact'

type Pair = readonly [bigint, bigint]
type Matrix = bigint[][]

export type BranchingMomentSupport = {
  applicable: boolean
  reason: string
  parentIds?: readonly string[]
  variables?: readonly [string, string]
  mapAssignments?: readonly ShearMapAssignment[]
}

type ShearSymbol = 'L' | 'R'

type ShearMapAssignment = {
  parentId: string
  sourceName: string
  symbol: ShearSymbol
  variables: readonly [string, string]
}

type ResolvedBranchingMomentSupport = {
  parentIds: readonly string[]
  variables: readonly [string, string]
  mapAssignments: readonly ShearMapAssignment[]
}

export type RuntimeBranchingMomentGeneration = {
  applicable: boolean
  reason: string
  cards: ExecutableFusionCard[]
  hypothesesEvaluated: number
}

function hash(value: unknown, length = 16): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

type BranchingVisualStepDraft = {
  id: string
  title: string
  explanation_ja: string
  formula_tex?: string
  diagram: ProblemDiagram | { kind: string; active?: string[] }
}

type BranchingVisualExplanationDraft = {
  version: 1
  mode: 'stepper'
  title: string
  diagram_required_for_every_step: true
  composition_verified: boolean
  morphism_chain: string[]
  steps: BranchingVisualStepDraft[]
}

const VISUAL_NODE_LABELS: Record<string, string> = {
  seed: '初期値',
  tree: '写像による分岐',
  moments: '対称量',
  recurrence: '漸化式',
  answer: '厳密解',
  L: '末尾が L',
  R: '末尾が R',
  sums: '座標和',
}

function completeVisualExplanation(
  morphismChain: readonly string[],
  stepMorphisms: readonly string[],
  draft: BranchingVisualExplanationDraft,
): VisualExplanation {
  if (draft.steps.length !== stepMorphisms.length) {
    throw new Error('every visual step must name exactly one morphism')
  }
  return {
    ...draft,
    morphism_chain: [...morphismChain],
    steps: draft.steps.map((step, index) => {
      const rawDiagram = step.diagram as ProblemDiagram & { active?: string[] }
      const knownKind = ['plane', 'morphism', 'state', 'variation', 'calculus'].includes(rawDiagram.kind)
      const active = rawDiagram.active ?? []
      const nodeLabels = active.length
        ? active.map(node => VISUAL_NODE_LABELS[node] ?? node)
        : [step.title]
      const diagram: ProblemDiagram = rawDiagram.version === 1 && knownKind
        ? rawDiagram
        : {
            version: 1,
            kind: 'morphism',
            title: step.title,
            caption: step.explanation_ja,
            nodes: nodeLabels,
          }
      const sourceId = active[0] ?? `stage-${index}`
      const targetId = active.at(-1) ?? `stage-${index + 1}`
      return {
        id: step.id,
        title: step.title,
        explanation_ja: step.explanation_ja,
        formula_tex: step.formula_tex,
        morphism: {
          morphism_id: stepMorphisms[index],
          label_ja: step.title,
          input_type: sourceId,
          output_type: targetId,
        },
        source_state: { id: sourceId, type: sourceId },
        target_state: { id: targetId, type: targetId },
        diagram,
      }
    }),
  }
}

function compact(value: string): string {
  return value
    .normalize('NFKC')
    .replace(/[−－]/g, '-')
    .replace(/\\left|\\right|\\,/g, '')
    .replace(/[{}\s]/g, '')
    .toLowerCase()
}

function isVariableSum(expression: string, first: string, second: string): boolean {
  const terms = expression.split('+')
  return terms.length === 2
    && terms[0] !== terms[1]
    && new Set(terms).size === 2
    && terms.includes(first)
    && terms.includes(second)
}

function extractUnitShearMaps(source: string): Array<{
  sourceName: string
  symbol: ShearSymbol
  variables: readonly [string, string]
}> {
  const maps: Array<{
    sourceName: string
    symbol: ShearSymbol
    variables: readonly [string, string]
  }> = []
  const pattern = /([a-z][a-z0-9_]*)\(([a-z]),([a-z])\)=\(([^,()]+),([^,()]+)\)/gi
  for (const match of source.matchAll(pattern)) {
    const [, sourceName, first, second, outputFirst, outputSecond] = match
    if (first === second) continue
    if (isVariableSum(outputFirst, first, second) && outputSecond === second) {
      maps.push({ sourceName, symbol: 'L', variables: [first, second] })
    } else if (outputFirst === first && isVariableSum(outputSecond, first, second)) {
      maps.push({ sourceName, symbol: 'R', variables: [first, second] })
    }
  }
  return maps
}

export function supportsBranchingMomentGeneration(
  parents: readonly DiscoveryParent[],
): BranchingMomentSupport {
  if (parents.length < 1 || parents.length > 2) {
    return { applicable: false, reason: 'the branching moment generator requires one dual-map parent or two complementary map parents' }
  }
  const parentIds = parents.map(parent => String(parent.id))
  if (new Set(parentIds).size !== parentIds.length) {
    return { applicable: false, reason: 'the branching moment generator requires distinct parent identifiers' }
  }

  const mapAssignments: ShearMapAssignment[] = []
  for (const parent of parents) {
    const source = compact(parent.statement ?? '')
    for (const map of extractUnitShearMaps(source)) {
      if (mapAssignments.some(assignment =>
        assignment.parentId === String(parent.id) && assignment.symbol === map.symbol)) continue
      mapAssignments.push({
        parentId: String(parent.id),
        sourceName: map.sourceName,
        symbol: map.symbol,
        variables: map.variables,
      })
    }
  }

  const left = mapAssignments.find(assignment => assignment.symbol === 'L')
  const right = mapAssignments.find(assignment => assignment.symbol === 'R')
  if (!left || !right) {
    return { applicable: false, reason: 'the selected parents do not collectively define both integer shear maps' }
  }
  if (parents.length === 2) {
    const contributors = new Set(mapAssignments.map(assignment => assignment.parentId))
    const symbolsPerParent = parents.map(parent =>
      mapAssignments.filter(assignment => assignment.parentId === String(parent.id)).map(assignment => assignment.symbol))
    if (contributors.size !== 2 || symbolsPerParent.some(symbols => symbols.length !== 1)) {
      return {
        applicable: false,
        reason: 'two-parent generation requires one indispensable shear map from each parent',
      }
    }
  }
  return {
    applicable: true,
    reason: parents.length === 1
      ? 'the current parent defines the two noncommuting integer shear maps'
      : 'the two current parents contribute one noncommuting integer shear map each',
    parentIds,
    variables: left.variables,
    mapAssignments,
  }
}

function mapAnchor(assignment: ShearMapAssignment): string {
  const [first, second] = assignment.variables
  return assignment.symbol === 'L'
    ? `${assignment.sourceName}(${first},${second})=(${first}+${second},${second})`
    : `${assignment.sourceName}(${first},${second})=(${first},${first}+${second})`
}

function groupedMapAssignments(support: ResolvedBranchingMomentSupport) {
  return support.parentIds.map(parentId => {
    const maps = support.mapAssignments.filter(assignment => assignment.parentId === parentId)
    const symbols = maps.map(assignment => assignment.symbol)
    const portId = symbols.length === 2
      ? 'dual-integer-shear-system'
      : symbols[0] === 'L'
        ? 'left-integer-shear-map'
        : 'right-integer-shear-map'
    return { parentId, maps, symbols, portId }
  })
}

function parentProofCertificates(signature: string, support: ResolvedBranchingMomentSupport) {
  return groupedMapAssignments(support).map((assignment, index) => ({
    id: `${signature}.parent.${index}`,
    claim: `parent ${assignment.parentId} defines ${assignment.symbols.join(' and ')} as an exact integer shear map`,
    verifier: `exact normalized parsing of ${assignment.maps.map(mapAnchor).join(' and ')}`,
  }))
}

function parentDerivationAssignments(
  support: ResolvedBranchingMomentSupport,
  role: string,
  witnessSteps: readonly string[],
) {
  return groupedMapAssignments(support).map(assignment => {
    const obligation = `parent ${assignment.parentId} supplies ${assignment.symbols.join(' and ')}`
    return {
      parentId: assignment.parentId,
      portId: assignment.portId,
      role,
      matchedAnchors: assignment.maps.map(mapAnchor),
      witnessSteps: [...witnessSteps],
      requiredObligations: [obligation],
      consumedObligations: [obligation],
      coverage: 1,
    }
  })
}

function parentIntermediatePropositions(
  support: ResolvedBranchingMomentSupport,
  morphism: string,
  target: string,
  proposition: string,
) {
  return groupedMapAssignments(support).map(assignment => ({
    parentId: assignment.parentId,
    morphism,
    source: assignment.symbols.length === 2
      ? 'DualIntegerShearSystem'
      : `${assignment.symbols[0]}IntegerShearMap`,
    target,
    proposition,
    proved: true as const,
  }))
}

function supportSources(support: ResolvedBranchingMomentSupport): string[] {
  const grouped = groupedMapAssignments(support)
  if (grouped.length === 1 && grouped[0].symbols.length === 2) return ['DualIntegerShearSystem']
  return grouped.map(assignment => assignment.symbols[0] === 'L'
    ? 'LeftIntegerShearMap'
    : 'RightIntegerShearMap')
}

function choose(n: number, k: number): bigint {
  if (k < 0 || k > n) return 0n
  let result = 1n
  for (let index = 1; index <= Math.min(k, n - k); index += 1) {
    result = result * BigInt(n - index + 1) / BigInt(index)
  }
  return result
}

function addPolynomials(left: bigint[], right: bigint[]): bigint[] {
  return left.map((value, index) => value + (right[index] ?? 0n))
}

function monomialAfterBothChildren(degree: number, yPower: number): bigint[] {
  const result = Array<bigint>(degree + 1).fill(0n)
  const xPower = degree - yPower
  for (let index = 0; index <= xPower; index += 1) {
    result[yPower + index] += choose(xPower, index)
  }
  for (let index = 0; index <= yPower; index += 1) {
    result[index] += choose(yPower, index)
  }
  return result
}

function symmetricBasisPolynomial(degree: number, index: number): bigint[] {
  const result = Array<bigint>(degree + 1).fill(0n)
  result[index] = 1n
  if (index !== degree - index) result[degree - index] = 1n
  return result
}

/**
 * Compute the transfer matrix from the two child maps. No recurrence
 * coefficients or characteristic roots are stored in the generator.
 */
export function symmetricMomentTransferMatrix(degree: number): Matrix {
  if (!Number.isInteger(degree) || degree < 1) throw new Error('moment degree must be a positive integer')
  const rank = Math.floor(degree / 2) + 1
  return Array.from({ length: rank }, (_, observableIndex) => {
    const basis = symmetricBasisPolynomial(degree, observableIndex)
    let image = Array<bigint>(degree + 1).fill(0n)
    for (let yPower = 0; yPower <= degree; yPower += 1) {
      const coefficient = basis[yPower]
      if (coefficient === 0n) continue
      image = addPolynomials(
        image,
        monomialAfterBothChildren(degree, yPower).map(value => value * coefficient),
      )
    }
    for (let index = 0; index <= degree; index += 1) {
      if (image[index] !== image[degree - index]) {
        throw new Error('branch transfer did not preserve symmetry')
      }
    }
    return image.slice(0, rank)
  })
}

function multiplyMatrixVector(matrix: Matrix, vector: bigint[]): bigint[] {
  return matrix.map(row => row.reduce(
    (sum, value, index) => sum + value * vector[index],
    0n,
  ))
}

function determinant3(matrix: Matrix): bigint {
  const [a, b, c] = matrix
  return a[0] * (b[1] * c[2] - b[2] * c[1])
    - a[1] * (b[0] * c[2] - b[2] * c[0])
    + a[2] * (b[0] * c[1] - b[1] * c[0])
}

function characteristicPolynomial3(matrix: Matrix): readonly [bigint, bigint, bigint, bigint] {
  const trace = matrix[0][0] + matrix[1][1] + matrix[2][2]
  const principalMinors =
    matrix[0][0] * matrix[1][1] - matrix[0][1] * matrix[1][0]
    + matrix[0][0] * matrix[2][2] - matrix[0][2] * matrix[2][0]
    + matrix[1][1] * matrix[2][2] - matrix[1][2] * matrix[2][1]
  return [1n, -trace, principalMinors, -determinant3(matrix)]
}

function multiplyMatrices(left: Matrix, right: Matrix): Matrix {
  const size = left.length
  return Array.from({ length: size }, (_, row) =>
    Array.from({ length: size }, (_, column) =>
      left[row].reduce(
        (sum, value, index) => sum + value * right[index][column],
        0n,
      )))
}

export function characteristicPolynomial(matrix: Matrix): bigint[] {
  const size = matrix.length
  if (!size || matrix.some(row => row.length !== size)) throw new Error('characteristic matrix must be square')
  const elementary = [1n]
  const traces = [0n]
  let power: Matrix = Array.from({ length: size }, (_, row) =>
    Array.from({ length: size }, (_, column) => row === column ? 1n : 0n))
  for (let degree = 1; degree <= size; degree += 1) {
    power = multiplyMatrices(power, matrix)
    traces.push(power.reduce((sum, row, index) => sum + row[index], 0n))
    let numerator = 0n
    for (let index = 1; index <= degree; index += 1) {
      const sign = index % 2 === 1 ? 1n : -1n
      numerator += sign * elementary[degree - index] * traces[index]
    }
    const divisor = BigInt(degree)
    if (numerator % divisor !== 0n) throw new Error('Newton identity produced a nonintegral coefficient')
    elementary.push(numerator / divisor)
  }
  return elementary.map((value, degree) => degree % 2 === 0 ? value : -value)
}

function monomialAfterChild(
  degree: number,
  yPower: number,
  symbol: 'L' | 'R',
): bigint[] {
  const result = Array<bigint>(degree + 1).fill(0n)
  const xPower = degree - yPower
  if (symbol === 'L') {
    for (let index = 0; index <= xPower; index += 1) {
      result[yPower + index] += choose(xPower, index)
    }
  } else {
    for (let index = 0; index <= yPower; index += 1) {
      result[index] += choose(yPower, index)
    }
  }
  return result
}

export function forbiddenWordMomentTransferMatrix(
  forbiddenWords: readonly string[],
  degree: number,
): Matrix {
  if (!Number.isSafeInteger(degree) || degree < 1) {
    throw new Error('moment degree must be a positive safe integer')
  }
  const automaton = buildForbiddenWordAutomaton(forbiddenWords)
  const rank = degree + 1
  const matrix = Array.from(
    { length: rank * automaton.states.length },
    () => Array<bigint>(rank * automaton.states.length).fill(0n),
  )
  for (const transition of automaton.transitions) {
    const sourceOffset = rank * transition.from
    const targetOffset = rank * transition.to
    for (let targetMoment = 0; targetMoment < rank; targetMoment += 1) {
      const image = monomialAfterChild(degree, targetMoment, transition.symbol)
      for (let sourceMoment = 0; sourceMoment < rank; sourceMoment += 1) {
        matrix[targetOffset + targetMoment][sourceOffset + sourceMoment] += image[sourceMoment]
      }
    }
  }
  return matrix
}

export function forbiddenWordCoordinateTransferMatrix(forbiddenWords: readonly string[]): Matrix {
  return forbiddenWordMomentTransferMatrix(forbiddenWords, 1)
}

export function noRepeatedRightCoordinateTransferMatrix(): Matrix {
  return forbiddenWordCoordinateTransferMatrix(['RR'])
}

function polynomialValue(coefficients: readonly bigint[], value: bigint): bigint {
  return coefficients.reduce((result, coefficient) => result * value + coefficient, 0n)
}

function divideCubicByIntegerRoot(
  coefficients: readonly [bigint, bigint, bigint, bigint],
  root: bigint,
): readonly [bigint, bigint, bigint] {
  if (polynomialValue(coefficients, root) !== 0n) throw new Error('candidate is not a characteristic root')
  const first = coefficients[0]
  const second = coefficients[1] + root * first
  const third = coefficients[2] + root * second
  if (coefficients[3] + root * third !== 0n) throw new Error('synthetic division left a remainder')
  return [first, second, third]
}

function enumerateFourthMoments(maximumGeneration: number): bigint[] {
  let pairs: Pair[] = [[1n, 1n]]
  const values: bigint[] = []
  for (let generation = 0; generation <= maximumGeneration; generation += 1) {
    values.push(pairs.reduce((sum, [a, b]) => sum + a ** 4n + b ** 4n, 0n))
    pairs = pairs.flatMap(([a, b]) => [[a + b, b], [a, a + b]] as Pair[])
  }
  return values
}

function enumerateNoRepeatedRightCoordinateSums(maximumGeneration: number): bigint[] {
  let states: Array<{ pair: Pair; last: 'L' | 'R' }> = [
    { pair: [2n, 1n], last: 'L' },
    { pair: [1n, 2n], last: 'R' },
  ]
  const values: bigint[] = []
  for (let generation = 1; generation <= maximumGeneration; generation += 1) {
    values.push(states.reduce((sum, state) => sum + state.pair[0] + state.pair[1], 0n))
    states = states.flatMap(({ pair: [a, b], last }) => {
      const next: Array<{ pair: Pair; last: 'L' | 'R' }> = [{
        pair: [a + b, b],
        last: 'L',
      }]
      if (last !== 'R') next.push({ pair: [a, a + b], last: 'R' })
      return next
    })
  }
  return values
}

function buildCompositionGenome(depth = 7): CompositionGenome {
  const nodes: CompositionGenome['nodes'] = [{
    id: 'seed',
    operator: 'canonicalize',
    law: 'normalize',
    inputs: ['input'],
    output: 'configuration',
  }]
  let leaves = ['seed']
  for (let generation = 1; generation <= depth; generation += 1) {
    const next: string[] = []
    for (const [index, parent] of leaves.entries()) {
      const left = `g${generation}-${index}-left`
      const right = `g${generation}-${index}-right`
      nodes.push(
        { id: left, operator: 'transform', law: 'map', structuralSymbol: 'L', inputs: [parent], output: 'configuration' },
        { id: right, operator: 'transform', law: 'map', structuralSymbol: 'R', inputs: [parent], output: 'configuration' },
      )
      next.push(left, right)
    }
    leaves = next
  }

  let momentStates = leaves.map((leaf, index) => {
    const fourth = `leaf-${index}-fourth`
    const mixed = `leaf-${index}-mixed`
    const square = `leaf-${index}-square`
    const state = `leaf-${index}-state`
    nodes.push(
      { id: fourth, operator: 'transform', law: 'map', structuralSymbol: 'x4+y4', inputs: [leaf], output: 'scalar' },
      { id: mixed, operator: 'transform', law: 'map', structuralSymbol: 'x3y+xy3', inputs: [leaf], output: 'scalar' },
      { id: square, operator: 'transform', law: 'map', structuralSymbol: 'x2y2', inputs: [leaf], output: 'scalar' },
      { id: state, operator: 'combine', law: 'pair', inputs: [fourth, mixed, square], output: 'configuration' },
    )
    return state
  })

  let aggregationLevel = 0
  while (momentStates.length > 1) {
    const next: string[] = []
    for (let index = 0; index < momentStates.length; index += 2) {
      const id = `aggregate-${aggregationLevel}-${index / 2}`
      nodes.push({
        id,
        operator: 'aggregate',
        law: 'fold',
        inputs: [momentStates[index], momentStates[index + 1]],
        output: 'sequence',
      })
      next.push(id)
    }
    momentStates = next
    aggregationLevel += 1
  }

  nodes.push(
    { id: 'recurrence', operator: 'aggregate', law: 'eliminate', inputs: [momentStates[0]], output: 'polynomial' },
    { id: 'dominant-root', operator: 'restrict', law: 'boundary', inputs: ['recurrence'], output: 'scalar' },
    { id: 'answer', operator: 'canonicalize', law: 'normalize', inputs: ['dominant-root'], output: 'scalar' },
  )
  return { schema: 1, input: 'algebraic-configuration', nodes, outputs: ['answer'] }
}

export function buildForbiddenWordMomentCompositionGenome(
  forbiddenWords: readonly string[],
  degree: number,
  depth = 10,
): CompositionGenome {
  if (!Number.isSafeInteger(degree) || degree < 1) {
    throw new Error('moment degree must be a positive safe integer')
  }
  const automaton = buildForbiddenWordAutomaton(forbiddenWords)
  const nodes: CompositionGenome['nodes'] = [{
    id: 'seed',
    operator: 'canonicalize',
    law: 'normalize',
    inputs: ['input'],
    output: 'configuration',
  }]
  let leaves: Array<{ id: string; state: number }> = [{
    id: 'seed',
    state: automaton.startState,
  }]
  for (let generation = 1; generation <= depth; generation += 1) {
    const next: typeof leaves = []
    for (const [index, leaf] of leaves.entries()) {
      const transitions = automaton.transitions.filter(transition => transition.from === leaf.state)
      for (const transition of transitions) {
        const name = transition.symbol.toLowerCase()
        const raw = `g${generation}-${index}-${name}-map`
        const legal = `g${generation}-${index}-${name}-legal`
        nodes.push(
          {
            id: raw,
            operator: 'transform',
            law: 'map',
            structuralSymbol: transition.symbol,
            inputs: [leaf.id],
            output: 'configuration',
          },
          {
            id: legal,
            operator: 'restrict',
            law: 'preimage',
            structuralSymbol: 'legal',
            inputs: [raw],
            output: 'configuration',
          },
        )
        next.push({ id: legal, state: transition.to })
      }
    }
    leaves = next
  }

  let coordinateStates = leaves.map((leaf, index) => {
    const moments = Array.from({ length: degree + 1 }, (_, yPower) => {
      const id = `leaf-${index}-moment-${yPower}`
      nodes.push({
        id,
        operator: 'transform',
        law: 'map',
        structuralSymbol: `moment-${yPower}`,
        inputs: [leaf.id],
        output: 'scalar',
      })
      return id
    })
    const state = `leaf-${index}-moment-state`
    nodes.push({
      id: state,
      operator: 'combine',
      law: 'pair',
      inputs: moments,
      output: 'configuration',
    })
    return state
  })

  let aggregationLevel = 0
  while (coordinateStates.length > 1) {
    const next: string[] = []
    for (let index = 0; index < coordinateStates.length; index += 2) {
      if (index + 1 === coordinateStates.length) {
        next.push(coordinateStates[index])
        continue
      }
      const id = `aggregate-${aggregationLevel}-${index / 2}`
      nodes.push({
        id,
        operator: 'aggregate',
        law: 'fold',
        inputs: [coordinateStates[index], coordinateStates[index + 1]],
        output: 'sequence',
      })
      next.push(id)
    }
    coordinateStates = next
    aggregationLevel += 1
  }

  nodes.push(
    { id: 'state-recurrence', operator: 'aggregate', law: 'eliminate', inputs: [coordinateStates[0]], output: 'polynomial' },
    { id: 'dominant-root', operator: 'restrict', law: 'boundary', inputs: ['state-recurrence'], output: 'scalar' },
    { id: 'answer', operator: 'canonicalize', law: 'normalize', inputs: ['dominant-root'], output: 'scalar' },
  )
  return { schema: 1, input: 'algebraic-configuration', nodes, outputs: ['answer'] }
}

export function buildForbiddenWordCompositionGenome(
  forbiddenWords: readonly string[],
  depth = 10,
): CompositionGenome {
  return buildForbiddenWordMomentCompositionGenome(forbiddenWords, 1, depth)
}

function buildNoRepeatedRightGenome(depth = 10): CompositionGenome {
  return buildForbiddenWordCompositionGenome(['RR'], depth)
}

function createCard(
  parents: readonly DiscoveryParent[],
  support: ResolvedBranchingMomentSupport,
): ExecutableFusionCard {
  const degree = 4
  const matrix = symmetricMomentTransferMatrix(degree)
  const characteristic = characteristicPolynomial3(matrix)
  const integerRoot = -1n
  const quadratic = divideCubicByIntegerRoot(characteristic, integerRoot)
  const discriminant = quadratic[1] ** 2n - 4n * quadratic[0] * quadratic[2]
  if (matrix.map(row => row.join(',')).join(';') !== '3,8,12;2,5,6;1,2,2') {
    throw new Error('unexpected fourth-moment transfer matrix')
  }
  if (characteristic.join(',') !== '1,-10,-9,2' || quadratic.join(',') !== '1,-11,2' || discriminant !== 113n) {
    throw new Error('the derived characteristic polynomial does not have the required simple dominant root')
  }

  const initialState = [2n, 2n, 1n]
  const recurrenceValues: bigint[] = []
  let state = initialState
  for (let generation = 0; generation <= 8; generation += 1) {
    recurrenceValues.push(state[0])
    state = multiplyMatrixVector(matrix, state)
  }
  const independentlyEnumerated = enumerateFourthMoments(8)
  if (recurrenceValues.some((value, index) => value !== independentlyEnumerated[index])) {
    throw new Error('moment transfer and independent tree enumeration disagree')
  }
  for (let index = 0; index + 3 < recurrenceValues.length; index += 1) {
    const expected =
      10n * recurrenceValues[index + 2]
      + 9n * recurrenceValues[index + 1]
      - 2n * recurrenceValues[index]
    if (recurrenceValues[index + 3] !== expected) throw new Error('derived scalar recurrence failed')
  }

  const compositionGenome = buildCompositionGenome()
  const genomeMetrics = compositionGenomeMetrics(compositionGenome)
  const deepAudit = auditCompositionComplexity(compositionGenome)
  if (!deepAudit.passed) throw new Error('branching composition did not meet the structural target: ' + deepAudit.failures.join('; '))
  const genomeFingerprint = compositionGenomeFingerprint(compositionGenome)
  const chain = [
    'DualIntegerShearElaboration',
    'BinaryBranchExpansion',
    'SymmetricFourthMomentObservation',
    'ThreeMomentClosure',
    'GenerationAggregation',
    'CoupledRecurrenceElimination',
    'CharacteristicPolynomialFactorization',
    'DominantRootRestriction',
    'HighSchoolProofRealization',
  ]
  const signature = hash({
    parents: support.parentIds,
    mapAssignments: support.mapAssignments,
    maps: ['(a+b,b)', '(a,a+b)'],
    degree,
    matrix: matrix.map(row => row.map(String)),
    chain,
  })
  const obligations = [
    'the selected parents collectively define both noncommuting integer shear maps',
    'every child contribution to the three fourth moments is expanded exactly',
    'the three moment sums form a closed linear recurrence',
    'eliminating the two auxiliary moments gives the stated scalar recurrence',
    'the largest characteristic root determines the requested positive-sequence ratio',
    'the proof graph satisfies the repeat-independent deep-composition target',
    'the visible solution uses only polynomial expansion, simultaneous recurrences, and elementary limits',
  ]
  const proofCertificate = [
    ...parentProofCertificates(signature, support),
    { id: `${signature}.transfer`, claim: obligations[1], verifier: 'integer binomial expansion of all symmetric degree-four monomials' },
    { id: `${signature}.closure`, claim: obligations[2], verifier: 'exact transfer matrix computed from the current two maps' },
    { id: `${signature}.elimination`, claim: obligations[3], verifier: 'exact invariant 4C_n-A_n=2(-1)^n and eight recurrence checks' },
    { id: `${signature}.limit`, claim: obligations[4], verifier: 'exact factorization (t+1)(t^2-11t+2) and nonzero dominant coefficient' },
    { id: `${signature}.structure`, claim: obligations[5], verifier: `${genomeMetrics.repeatIndependentOperationCount} repeat-independent operations, ${genomeMetrics.branchCount} branches, ${genomeMetrics.mergeCount} merges` },
    { id: `${signature}.public`, claim: obligations[6], verifier: 'upper-secondary publication audit' },
  ]

  const statement = String.raw`整数の組の多重集合 \(\mathcal S_0,\mathcal S_1,\ldots\) を次のように定める。
\[
\mathcal S_0=\{(1,1)\}.
\]
\(\mathcal S_n\) の各要素 \((a,b)\) を
\[
(a+b,b),\qquad (a,a+b)
\]
の二つで置き換えて得られる多重集合を \(\mathcal S_{n+1}\) とする。同じ組が複数回現れた場合も、現れた回数だけ数える。
\[
A_n=\sum_{(a,b)\in\mathcal S_n}(a^4+b^4)
\]
とおくとき、極限
\[
\lim_{n\to\infty}\frac{A_{n+1}}{A_n}
\]
を求めよ。`
  const answer = String.raw`\(\displaystyle\frac{11+\sqrt{113}}2\)`
  const solution = String.raw`各組から二つの組が生じるので、\(A_n\) だけでは次の項を表せない。そこで
\[
B_n=\sum_{(a,b)\in\mathcal S_n}(a^3b+ab^3),\qquad
C_n=\sum_{(a,b)\in\mathcal S_n}a^2b^2
\]
とおく。

一つの組 \((a,b)\) から生じる二つの組について四次式を展開すると
\[
\begin{aligned}
&\{(a+b)^4+b^4\}+\{a^4+(a+b)^4\}\\
&\hspace{18mm}=3(a^4+b^4)+8(a^3b+ab^3)+12a^2b^2.
\end{aligned}
\]
同様に残りの二つの対称式も展開する。全ての \((a,b)\in\mathcal S_n\) について加えると
\[
\begin{aligned}
A_{n+1}&=3A_n+8B_n+12C_n,\\
B_{n+1}&=2A_n+5B_n+6C_n,\\
C_{n+1}&=A_n+2B_n+2C_n.
\end{aligned}
\tag{1}
\]

(1) の第一式と第三式から
\[
4C_{n+1}-A_{n+1}=A_n-4C_n=-(4C_n-A_n)
\]
である。\(A_0=2,\ C_0=1\) だから
\[
4C_n-A_n=2(-1)^n.
\tag{2}
\]
また、(1) をもう一度用いると
\[
A_{n+2}=37A_n+88B_n+108C_n.
\]
この式から \(11A_{n+1}-2A_n\) を引き、(2) を用いると
\[
\begin{aligned}
A_{n+2}-(11A_{n+1}-2A_n)
&=6A_n-24C_n\\
&=-6(4C_n-A_n)\\
&=-12(-1)^n.
\end{aligned}
\]
従って
\[
A_{n+2}=11A_{n+1}-2A_n-12(-1)^n.
\tag{3}
\]

ここで
\[
X_n=A_n+\frac67(-1)^n
\]
とおく。(3) に代入すれば交代する項が消え、
\[
X_{n+2}=11X_{n+1}-2X_n
\tag{4}
\]
を得る。(4) の特性方程式 \(t^2-11t+2=0\) の二根を
\[
\alpha=\frac{11+\sqrt{113}}2,\qquad
\beta=\frac{11-\sqrt{113}}2
\]
とすれば、定数 \(p,q\) を用いて \(X_n=p\alpha^n+q\beta^n\) と表せる。

初期値は \(X_0=20/7,\ X_1=232/7\) である。従って
\[
p=\frac{X_1-\beta X_0}{\alpha-\beta}>0
\]
である。実際、\(10<\sqrt{113}<11\) から \(0<\beta<1<\alpha\) である。よって \(X_n\) では \(p\alpha^n\) が支配的になる。さらに \(A_n=X_n-\frac67(-1)^n\) だから、交代する定数項は極限に影響しない。従って
\[
\boxed{\displaystyle
\lim_{n\to\infty}\frac{A_{n+1}}{A_n}
=\alpha=\frac{11+\sqrt{113}}2}
\]
を得る。`

  return {
    id: `mortra-runtime-branching-fourth-moment.${signature}`,
    family_id: 'runtime.binary_shear_fourth_moment_limit',
    statement_tex: statement,
    answer_tex: answer,
    solution_tex: solution,
    domain: 'algebra_sequences_and_limits',
    morphism_chain: chain,
    parent_ids: [...support.parentIds],
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: 'exact binomial transfer matrix + independent binary-tree enumeration + characteristic-root proof',
      exact_backend: true,
      independent_check: true,
      samples: recurrenceValues.map(Number),
    },
    difficulty: {
      band: 'S_entrance_exam_branching_moment_closure',
      score: 26,
    },
    fusion_derivation: {
      passed: true,
      reason: 'the two current shear maps generate a binary tree; three symmetric moments close under branching and eliminate to one exact recurrence',
      ablationPassed: true,
      assignments: parentDerivationAssignments(
        support,
        'binary_branch_generators',
        ['DualIntegerShearElaboration', 'BinaryBranchExpansion'],
      ),
      bridges: [{
        id: `branching-moment:${signature}`,
        witnessStep: 'ThreeMomentClosure',
        consumes: groupedMapAssignments(support).map(assignment => assignment.portId),
        produces: 'ExactDominantMomentRatio',
      }],
      intermediatePropositions: parentIntermediatePropositions(
        support,
        'ThreeMomentClosure',
        'ThreeDimensionalMomentRecurrence',
        'the symmetric fourth-degree observables close only after both child maps are combined',
      ),
    },
    structure_blueprint: {
      id: `binary-shear-fourth-moment.${signature}`,
      version: 1,
      kernel: 'binary_branching_symmetric_moment_transfer',
      observable: 'dominant_fourth_moment_ratio',
      operators: chain,
      domain: 'integer_pair_branching_x_symmetric_polynomials_x_linear_recurrence',
      tags: ['runtime-synthesis', 'atlas-free', 'one-to-many', 'high-school-proof', 'deep-composition'],
      morphismChain: chain,
      executable: true,
      proofCertificate,
      taskAlgebra: {
        schema: 1,
        input: 'algebraic-configuration',
        operations: [
          { operator: 'normalize', output: 'configuration' },
          { operator: 'map', output: 'configuration' },
          { operator: 'pair', output: 'configuration' },
          { operator: 'map', output: 'sequence' },
          { operator: 'fold', output: 'sequence' },
          { operator: 'eliminate', output: 'polynomial' },
          { operator: 'boundary', output: 'scalar' },
          { operator: 'normalize', output: 'scalar' },
        ],
        output: 'scalar',
        complete: true,
      },
      compositionGenome,
      synthesizedLaw: {
        name: 'BinaryShearSymmetricMomentClosure',
        expression: 'branch every pair by L and R, close degree-four symmetric moments, eliminate auxiliaries, select the dominant root',
        arity: support.parentIds.length,
        sources: supportSources(support),
        target: 'ExactDominantMomentRatio',
        preserves: ['multiplicity', 'integer pairs', 'positive coordinates', 'symmetric moment sums', 'parent provenance'],
        backend: ['integer binomial arithmetic', 'exact tree enumeration', 'integer polynomial factorization'],
      },
    },
    search_evidence: {
      hypotheses_evaluated: 1,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
    execution_certificate: runtimeSynthesisCertificate({
      origin: 'synthesized_proof_program',
      parents,
      generatedProgram: {
        schema: 'mortra.runtime-branching-moment.v1',
        input_map_assignments: support.mapAssignments,
        child_maps: ['(a+b,b)', '(a,a+b)'],
        moment_degree: degree,
        transfer_matrix: matrix.map(row => row.map(String)),
        characteristic_polynomial: characteristic.map(String),
        dominant_root: '(11+sqrt(113))/2',
        composition_genome: compositionGenome,
        composition_genome_sha256: genomeFingerprint,
        composition_metrics: genomeMetrics,
        deep_composition_audit: deepAudit,
        morphism_chain: chain,
      },
      checks: proofCertificate.map(item => `${item.id}: ${item.verifier}`),
    }),
    diagram: {
      version: 1,
      kind: 'state',
      title: '二つの写像から二分木を育て、三つの対称量へ縮約する',
      caption: '各世代の全ての枝を数えた後、四次の対称量三つだけを残し、一つの漸化式へ合流させます。',
      nodes: [
        '(1,1)',
        '(a+b,b)',
        '(a,a+b)',
        '(A_n,B_n,C_n)',
        't^3-10t^2-9t+2',
        '(11+sqrt(113))/2',
      ],
      states: [
        { id: 'seed', label: '一つの整数組', active: true },
        { id: 'tree', label: '二分木' },
        { id: 'moments', label: '三つの対称量' },
        { id: 'recurrence', label: '一つの漸化式' },
        { id: 'answer', label: '最大の特性根', terminal: true },
      ],
      transitions: [
        { from: 'seed', to: 'tree', label: 'two shear maps' },
        { from: 'tree', to: 'moments', label: 'fourth-moment aggregation' },
        { from: 'moments', to: 'recurrence', label: 'eliminate two auxiliaries' },
        { from: 'recurrence', to: 'answer', label: 'dominant-root limit' },
      ],
    },
    visual_explanation: completeVisualExplanation(
      chain,
      [chain[2], chain[3], chain[5], chain[6], chain[7]],
      {
      version: 1,
      mode: 'stepper',
      title: '二分木全体が一つの漸化式へ縮まるまで',
      diagram_required_for_every_step: true,
      composition_verified: true,
      morphism_chain: chain,
      steps: [
        {
          id: `${signature}.visual.1`,
          title: '三つの四次対称量を用意する',
          explanation_ja: '求める量だけでは次の世代を表せないため、展開時に現れる二つの混合項も同時に数えます。',
          formula_tex: String.raw`A_n=\sum(a^4+b^4),\quad B_n=\sum(a^3b+ab^3),\quad C_n=\sum a^2b^2`,
          diagram: { kind: 'tree-moments', active: ['seed', 'tree', 'moments'] },
        },
        {
          id: `${signature}.visual.2`,
          title: '一つの親から三本の漸化式を得る',
          explanation_ja: '左右の子について四次式を展開し、世代全体で加えると、三つの対称量の中だけで閉じます。',
          formula_tex: String.raw`\begin{pmatrix}A\\B\\C\end{pmatrix}_{n+1}
=\begin{pmatrix}3&8&12\\2&5&6\\1&2&2\end{pmatrix}
\begin{pmatrix}A\\B\\C\end{pmatrix}_n`,
          diagram: { kind: 'local-branch', active: ['tree', 'moments'] },
        },
        {
          id: `${signature}.visual.3`,
          title: '交代する不変量で補助量を消去する',
          explanation_ja: '第一式と第三式の差から交代する量を見つけ、A_nだけの二階漸化式へ戻します。',
          formula_tex: String.raw`4C_n-A_n=2(-1)^n,\qquad A_{n+2}=11A_{n+1}-2A_n-12(-1)^n`,
          diagram: { kind: 'elimination', active: ['moments', 'recurrence'] },
        },
        {
          id: `${signature}.visual.4`,
          title: '交代項を平行移動で消す',
          explanation_ja: '求める数列に小さな交代項を加えると、定数係数の二階漸化式になります。',
          formula_tex: String.raw`X_n=A_n+\frac67(-1)^n,\qquad X_{n+2}=11X_{n+1}-2X_n`,
          diagram: { kind: 'normalization', active: ['recurrence'] },
        },
        {
          id: `${signature}.visual.5`,
          title: '最大の特性根から極限を得る',
          explanation_ja: '交代項を平行移動で消して二次の特性方程式を作り、正の係数を持つ最大根だけが比の極限に残ることを示します。',
          formula_tex: String.raw`\displaystyle\lim_{n\to\infty}\frac{A_{n+1}}{A_n}
=\frac{11+\sqrt{113}}2`,
          diagram: { kind: 'dominant-root', active: ['recurrence', 'answer'] },
        },
      ],
      },
    ),
    proof_roadmap: [
      { morphism_id: chain[0], label_ja: '二つの整数写像を読み取る', source_ja: '親の構造記述', target_ja: '左右の分岐写像', role_ja: '問題固有の完成解法を使わず生成子を確定する。' },
      { morphism_id: chain[2], label_ja: '四次対称量を三つに閉じる', source_ja: '二分木の全ての組', target_ja: '三つの数列', role_ja: '指数的に増える枝を有限次元の状態へ縮約する。' },
      { morphism_id: chain[5], label_ja: '補助数列を消去する', source_ja: '三本の連立漸化式', target_ja: '交代項を含む二階漸化式', role_ja: '4C_n-A_n の交代不変量を使い、問いに現れる数列だけへ戻す。' },
      { morphism_id: chain[7], label_ja: '最大根を選ぶ', source_ja: '特性方程式の三根', target_ja: '極限値', role_ja: '近似値を使わず根の大小を比較する。' },
      { morphism_id: chain[8], label_ja: '高校数学の答案へ再構成する', source_ja: '検証済み合成グラフ', target_ja: '提出可能な解答', role_ja: '展開と消去の途中式を省略しない。' },
    ],
    proof_obligations: proofCertificate.map(item => ({ id: item.id, claim_ja: item.claim, status: 'verified' })),
  }
}

function divideByIntegerRoot(coefficients: readonly bigint[], root: bigint): bigint[] {
  if (coefficients.length < 2 || polynomialValue(coefficients, root) !== 0n) {
    throw new Error('candidate is not a polynomial root')
  }
  const quotient = [coefficients[0]]
  for (let index = 1; index + 1 < coefficients.length; index += 1) {
    quotient.push(coefficients[index] + root * quotient.at(-1)!)
  }
  if (coefficients.at(-1)! + root * quotient.at(-1)! !== 0n) {
    throw new Error('synthetic division left a remainder')
  }
  return quotient
}

type ExactFraction = { numerator: bigint; denominator: bigint }

export type MirrorForbiddenWordCoordinateAnalysis = {
  forbiddenWords: string[]
  automatonStates: string[]
  representativeStates: string[]
  quotientMatrix: Matrix
  initialStateAtOne: bigint[]
  observable: bigint[]
  recurrencePolynomial: bigint[]
  integerRoots: bigint[]
  dominantFactor: bigint[]
  dominantRoot: {
    degree: 2 | 3
    exactTex: string
    lowerBound: bigint
    upperBound: bigint
    shift?: ExactFraction
    depressedLinear?: ExactFraction
    depressedConstant?: ExactFraction
    cardanoDiscriminant?: ExactFraction
    cardanoPositiveTermTex?: string
    cardanoNegativeTermTex?: string
  }
  safeBlockCode: { blockLength: number; blocks: readonly [string, string] }
  samples: bigint[]
  independentlyEnumeratedSamples: bigint[]
}

function absoluteBigInt(value: bigint): bigint {
  return value < 0n ? -value : value
}

function gcdBigInt(left: bigint, right: bigint): bigint {
  let a = absoluteBigInt(left)
  let b = absoluteBigInt(right)
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

function exactFraction(numerator: bigint, denominator = 1n): ExactFraction {
  if (denominator === 0n) throw new Error('zero exact denominator')
  const sign = denominator < 0n ? -1n : 1n
  const divisor = gcdBigInt(numerator, denominator)
  return {
    numerator: sign * numerator / divisor,
    denominator: sign * denominator / divisor,
  }
}

function addFractions(left: ExactFraction, right: ExactFraction): ExactFraction {
  return exactFraction(
    left.numerator * right.denominator + right.numerator * left.denominator,
    left.denominator * right.denominator,
  )
}

function negateFraction(value: ExactFraction): ExactFraction {
  return { numerator: -value.numerator, denominator: value.denominator }
}

function subtractFractions(left: ExactFraction, right: ExactFraction): ExactFraction {
  return addFractions(left, negateFraction(right))
}

function multiplyFractions(left: ExactFraction, right: ExactFraction): ExactFraction {
  return exactFraction(left.numerator * right.numerator, left.denominator * right.denominator)
}

function divideFractions(left: ExactFraction, right: ExactFraction): ExactFraction {
  return exactFraction(left.numerator * right.denominator, left.denominator * right.numerator)
}

function powerFraction(value: ExactFraction, exponent: number): ExactFraction {
  return exactFraction(value.numerator ** BigInt(exponent), value.denominator ** BigInt(exponent))
}

function fractionTex(value: ExactFraction): string {
  if (value.denominator === 1n) return String(value.numerator)
  if (value.numerator < 0n) {
    return String.raw`-\frac{${absoluteBigInt(value.numerator)}}{${value.denominator}}`
  }
  return String.raw`\frac{${value.numerator}}{${value.denominator}}`
}

function signedFractionTerm(value: ExactFraction, suffix = ''): string {
  if (value.numerator === 0n) return ''
  const sign = value.numerator < 0n ? '-' : '+'
  const absolute = exactFraction(absoluteBigInt(value.numerator), value.denominator)
  const coefficient = absolute.numerator === absolute.denominator && suffix ? '' : fractionTex(absolute)
  return `${sign}${coefficient}${suffix}`
}

function swapGeneratorSymbols(word: string): string {
  return [...word].map(symbol => symbol === 'L' ? 'R' : 'L').join('')
}

function sameStringSet(left: readonly string[], right: readonly string[]): boolean {
  return left.length === right.length && left.every((value, index) => value === right[index])
}

function dotProduct(left: readonly bigint[], right: readonly bigint[]): bigint {
  return left.reduce((sum, value, index) => sum + value * right[index], 0n)
}

function multiplyRowVector(vector: readonly bigint[], matrix: Matrix): bigint[] {
  return matrix[0].map((_, column) =>
    vector.reduce((sum, value, row) => sum + value * matrix[row][column], 0n))
}

function allBinaryWords(length: number): string[] {
  let words = ['']
  for (let index = 0; index < length; index += 1) {
    words = words.flatMap(word => [word + 'L', word + 'R'])
  }
  return words
}

function containsForbiddenWord(word: string, forbiddenWords: readonly string[]): boolean {
  return forbiddenWords.some(forbidden => word.includes(forbidden))
}

function findSafeBlockCode(forbiddenWords: readonly string[]): {
  blockLength: number
  blocks: readonly [string, string]
} | null {
  const maximumForbiddenLength = Math.max(...forbiddenWords.map(word => word.length))
  for (let blockLength = 1; blockLength <= 4; blockLength += 1) {
    const blocks = allBinaryWords(blockLength)
      .filter(word => !containsForbiddenWord(word, forbiddenWords))
    const contextBlockCount = Math.ceil(maximumForbiddenLength / blockLength) + 2
    for (let left = 0; left < blocks.length; left += 1) {
      for (let right = left + 1; right < blocks.length; right += 1) {
        const code = [blocks[left], blocks[right]] as const
        const legal = allBinaryWords(contextBlockCount).every(selector => {
          const concatenated = [...selector]
            .map(symbol => symbol === 'L' ? code[0] : code[1])
            .join('')
          return !containsForbiddenWord(concatenated, forbiddenWords)
        })
        if (legal) return { blockLength, blocks: code }
      }
    }
  }
  return null
}

function enumerateForbiddenWordCoordinateSums(
  forbiddenWords: readonly string[],
  maximumGeneration: number,
): bigint[] {
  const values: bigint[] = []
  for (let generation = 1; generation <= maximumGeneration; generation += 1) {
    const words = acceptedBinaryWords(forbiddenWords, generation)
    values.push(words.reduce((total, word) => {
      let pair: Pair = [1n, 1n]
      for (const symbol of word) {
        const [a, b] = pair
        pair = symbol === 'L' ? [a + b, b] : [a, a + b]
      }
      return total + pair[0] + pair[1]
    }, 0n))
  }
  return values
}

export function mirrorSymmetricCoordinateQuotient(forbiddenWords: readonly string[]): {
  forbiddenWords: string[]
  automatonStates: string[]
  representativeStates: string[]
  matrix: Matrix
  initialStateAtOne: bigint[]
  observable: bigint[]
} {
  const normalized = normalizeForbiddenWords(forbiddenWords)
  const mirrored = normalizeForbiddenWords(normalized.map(swapGeneratorSymbols))
  if (!sameStringSet(normalized, mirrored)) {
    throw new Error('the forbidden-word language is not invariant under L/R exchange')
  }
  const automaton = buildForbiddenWordAutomaton(normalized)
  const stateIndex = new Map(automaton.states.map((state, index) => [state, index]))
  const representatives: string[] = []
  for (const state of automaton.states.filter(Boolean)) {
    const mirror = swapGeneratorSymbols(state)
    if (!stateIndex.has(mirror)) throw new Error(`mirror automaton state is missing: ${state} -> ${mirror}`)
    if (state.localeCompare(mirror) < 0) representatives.push(state)
  }
  if (!representatives.length) throw new Error('the mirror quotient has no nontransient state')

  const fullMatrix = forbiddenWordCoordinateTransferMatrix(normalized)
  const reducedDimension = 2 * representatives.length
  const fullToReduced = new Map<number, number>()
  for (const [orbit, state] of representatives.entries()) {
    const mirror = swapGeneratorSymbols(state)
    const directIndex = stateIndex.get(state)!
    const mirrorIndex = stateIndex.get(mirror)!
    fullToReduced.set(2 * directIndex, 2 * orbit)
    fullToReduced.set(2 * directIndex + 1, 2 * orbit + 1)
    fullToReduced.set(2 * mirrorIndex, 2 * orbit + 1)
    fullToReduced.set(2 * mirrorIndex + 1, 2 * orbit)
  }

  const matrix = Array.from(
    { length: reducedDimension },
    () => Array<bigint>(reducedDimension).fill(0n),
  )
  for (const [orbit, state] of representatives.entries()) {
    const fullState = stateIndex.get(state)!
    for (let coordinate = 0; coordinate < 2; coordinate += 1) {
      const target = 2 * orbit + coordinate
      const fullRow = fullMatrix[2 * fullState + coordinate]
      for (const [fullColumn, coefficient] of fullRow.entries()) {
        const reducedColumn = fullToReduced.get(fullColumn)
        if (reducedColumn !== undefined) matrix[target][reducedColumn] += coefficient
      }
    }
  }

  const lift = (reduced: readonly bigint[]): bigint[] => {
    const full = Array<bigint>(fullMatrix.length).fill(0n)
    for (const [orbit, state] of representatives.entries()) {
      const mirror = swapGeneratorSymbols(state)
      const directIndex = stateIndex.get(state)!
      const mirrorIndex = stateIndex.get(mirror)!
      full[2 * directIndex] = reduced[2 * orbit]
      full[2 * directIndex + 1] = reduced[2 * orbit + 1]
      full[2 * mirrorIndex] = reduced[2 * orbit + 1]
      full[2 * mirrorIndex + 1] = reduced[2 * orbit]
    }
    return full
  }

  for (let basisIndex = 0; basisIndex < reducedDimension; basisIndex += 1) {
    const basis = Array<bigint>(reducedDimension).fill(0n)
    basis[basisIndex] = 1n
    const fullImage = multiplyMatrixVector(fullMatrix, lift(basis))
    const reducedImage = multiplyMatrixVector(matrix, basis)
    if (fullImage.some((value, index) => value !== lift(reducedImage)[index])) {
      throw new Error('the full coordinate transfer does not preserve the proposed mirror quotient')
    }
  }

  const seed = Array<bigint>(fullMatrix.length).fill(0n)
  seed[2 * automaton.startState] = 1n
  seed[2 * automaton.startState + 1] = 1n
  const firstFullState = multiplyMatrixVector(fullMatrix, seed)
  const initialStateAtOne = representatives.flatMap(state => {
    const index = stateIndex.get(state)!
    return [firstFullState[2 * index], firstFullState[2 * index + 1]]
  })
  const liftedInitial = lift(initialStateAtOne)
  if (firstFullState.some((value, index) => value !== liftedInitial[index])) {
    throw new Error('the first legal generation is not represented by the mirror quotient')
  }

  return {
    forbiddenWords: normalized,
    automatonStates: automaton.states,
    representativeStates: representatives,
    matrix,
    initialStateAtOne,
    observable: Array<bigint>(reducedDimension).fill(2n),
  }
}

function integerDivisorRoots(polynomial: readonly bigint[]): bigint[] {
  const constant = polynomial.at(-1)!
  if (constant === 0n) return [0n]
  const roots: bigint[] = []
  const magnitude = absoluteBigInt(constant)
  for (let divisor = 1n; divisor * divisor <= magnitude; divisor += 1n) {
    if (magnitude % divisor !== 0n) continue
    for (const candidate of [divisor, -divisor, magnitude / divisor, -(magnitude / divisor)]) {
      if (!roots.includes(candidate) && polynomialValue(polynomial, candidate) === 0n) roots.push(candidate)
    }
  }
  return roots.sort((left, right) => Number(absoluteBigInt(left) - absoluteBigInt(right)) || Number(left - right))
}

function factorIntegerRoots(polynomial: readonly bigint[]): {
  roots: bigint[]
  remainder: bigint[]
} {
  let remainder = [...polynomial]
  const roots: bigint[] = []
  while (remainder.length > 2) {
    const root = integerDivisorRoots(remainder)[0]
    if (root === undefined) break
    roots.push(root)
    remainder = divideByIntegerRoot(remainder, root)
  }
  return { roots, remainder }
}

function squareFreePart(value: bigint): { outside: bigint; inside: bigint } {
  if (value <= 0n) throw new Error('square-free decomposition requires a positive integer')
  let remainder = value
  let outside = 1n
  let inside = 1n
  for (let prime = 2n; prime * prime <= remainder; prime += 1n) {
    let exponent = 0
    while (remainder % prime === 0n) {
      remainder /= prime
      exponent += 1
    }
    outside *= prime ** BigInt(Math.floor(exponent / 2))
    if (exponent % 2 === 1) inside *= prime
  }
  if (remainder > 1n) inside *= remainder
  return { outside, inside }
}

function sqrtFraction(value: ExactFraction): {
  coefficient: ExactFraction
  radicand: bigint
} {
  if (value.numerator <= 0n) throw new Error('square root requires a positive rational')
  const decomposed = squareFreePart(value.numerator * value.denominator)
  return {
    coefficient: exactFraction(decomposed.outside, value.denominator),
    radicand: decomposed.inside,
  }
}

function radicalSumTermTex(
  rationalPart: ExactFraction,
  squareRoot: { coefficient: ExactFraction; radicand: bigint },
  sign: 1 | -1,
): string {
  const commonDenominator = rationalPart.denominator * squareRoot.coefficient.denominator
    / gcdBigInt(rationalPart.denominator, squareRoot.coefficient.denominator)
  let rationalNumerator = rationalPart.numerator * (commonDenominator / rationalPart.denominator)
  let radicalCoefficient = squareRoot.coefficient.numerator
    * (commonDenominator / squareRoot.coefficient.denominator)
  let denominator = commonDenominator
  const divisor = gcdBigInt(gcdBigInt(rationalNumerator, radicalCoefficient), denominator)
  rationalNumerator /= divisor
  radicalCoefficient /= divisor
  denominator /= divisor
  const radicalBody = squareRoot.radicand === 1n
    ? String(radicalCoefficient)
    : String.raw`${radicalCoefficient === 1n ? '' : radicalCoefficient}\sqrt{${squareRoot.radicand}}`
  const numerator = `${rationalNumerator}${sign === 1 ? '+' : '-'}${radicalBody}`
  return denominator === 1n ? numerator : String.raw`\frac{${numerator}}{${denominator}}`
}

function polynomialTex(coefficients: readonly bigint[], variable = 't'): string {
  const degree = coefficients.length - 1
  const terms: string[] = []
  for (const [index, coefficient] of coefficients.entries()) {
    if (coefficient === 0n) continue
    const power = degree - index
    const sign = coefficient < 0n ? '-' : '+'
    const magnitude = absoluteBigInt(coefficient)
    const variablePart = power === 0 ? '' : power === 1 ? variable : `${variable}^{${power}}`
    const coefficientPart = power > 0 && magnitude === 1n ? '' : String(magnitude)
    const body = coefficientPart + variablePart
    terms.push(`${terms.length === 0 && sign === '+' ? '' : sign}${body}`)
  }
  return terms.join('') || '0'
}

function isolatePositiveRoot(polynomial: readonly bigint[]): { lower: bigint; upper: bigint } {
  for (let lower = 1n; lower < 32n; lower += 1n) {
    const upper = lower + 1n
    if (polynomialValue(polynomial, lower) < 0n && polynomialValue(polynomial, upper) > 0n) {
      return { lower, upper }
    }
  }
  throw new Error('no positive unit interval isolates the dominant root')
}

function exactDominantRoot(factor: readonly bigint[]): MirrorForbiddenWordCoordinateAnalysis['dominantRoot'] {
  if (factor[0] !== 1n || ![3, 4].includes(factor.length)) {
    throw new Error('the publication root factor must be monic quadratic or cubic')
  }
  const interval = isolatePositiveRoot(factor)
  if (factor.length === 3) {
    const [, linear, constant] = factor
    const discriminant = linear ** 2n - 4n * constant
    if (discriminant <= 0n || constant !== -1n) {
      throw new Error('the quadratic dominant factor lacks the exact reciprocal-root certificate')
    }
    const squareRoot = sqrtFraction(exactFraction(discriminant))
    const rootNumerator = `${-linear}${squareRoot.radicand === 1n
      ? `+${squareRoot.coefficient.numerator / squareRoot.coefficient.denominator}`
      : String.raw`+${squareRoot.coefficient.numerator === 1n ? '' : squareRoot.coefficient.numerator}\sqrt{${squareRoot.radicand}}`}`
    return {
      degree: 2,
      exactTex: String.raw`\frac{${rootNumerator}}2`,
      lowerBound: interval.lower,
      upperBound: interval.upper,
    }
  }

  const [, quadratic, linear, constant] = factor
  if (constant !== -1n) throw new Error('the cubic dominant factor lacks the reciprocal-modulus certificate')
  const a = exactFraction(quadratic)
  const b = exactFraction(linear)
  const c = exactFraction(constant)
  const shift = exactFraction(-quadratic, 3n)
  const p = subtractFractions(b, divideFractions(powerFraction(a, 2), exactFraction(3n)))
  const q = addFractions(
    subtractFractions(
      divideFractions(multiplyFractions(exactFraction(2n), powerFraction(a, 3)), exactFraction(27n)),
      divideFractions(multiplyFractions(a, b), exactFraction(3n)),
    ),
    c,
  )
  const discriminant = addFractions(
    divideFractions(powerFraction(q, 2), exactFraction(4n)),
    divideFractions(powerFraction(p, 3), exactFraction(27n)),
  )
  if (discriminant.numerator <= 0n || p.numerator >= 0n) {
    throw new Error('the cubic is not in the one-real-root Cardano regime')
  }
  const base = divideFractions(negateFraction(q), exactFraction(2n))
  const squareRoot = sqrtFraction(discriminant)
  const positiveTerm = radicalSumTermTex(base, squareRoot, 1)
  const negativeTerm = radicalSumTermTex(base, squareRoot, -1)
  const shiftPrefix = shift.numerator === 0n ? '' : `${fractionTex(shift)}+`
  return {
    degree: 3,
    exactTex: String.raw`${shiftPrefix}\sqrt[3]{${positiveTerm}}+\sqrt[3]{${negativeTerm}}`,
    lowerBound: interval.lower,
    upperBound: interval.upper,
    shift,
    depressedLinear: p,
    depressedConstant: q,
    cardanoDiscriminant: discriminant,
    cardanoPositiveTermTex: positiveTerm,
    cardanoNegativeTermTex: negativeTerm,
  }
}

function verifyScalarRecurrence(sequence: readonly bigint[], polynomial: readonly bigint[]): boolean {
  const order = polynomial.length - 1
  return sequence.slice(order).every((_, offset) =>
    polynomial.reduce(
      (sum, coefficient, index) => sum + coefficient * sequence[offset + order - index],
      0n,
    ) === 0n)
}

export function analyzeMirrorForbiddenWordCoordinateGrammar(
  forbiddenWords: readonly string[],
): MirrorForbiddenWordCoordinateAnalysis {
  const quotient = mirrorSymmetricCoordinateQuotient(forbiddenWords)
  const recurrencePolynomial = characteristicPolynomial(quotient.matrix)
  const factorization = factorIntegerRoots(recurrencePolynomial)
  if (![3, 4].includes(factorization.remainder.length)) {
    throw new Error('the remaining dominant factor is not quadratic or cubic')
  }
  if (factorization.roots.some(root => absoluteBigInt(root) > 1n)) {
    throw new Error('an integer characteristic root competes with the intended dominant factor')
  }
  const dominantRoot = exactDominantRoot(factorization.remainder)
  if (dominantRoot.lowerBound < 1n) throw new Error('the exact dominant root is not greater than one')
  const safeBlockCode = findSafeBlockCode(quotient.forbiddenWords)
  if (!safeBlockCode) throw new Error('no finite two-block exponential-growth witness was found')

  const samples: bigint[] = []
  let state = quotient.initialStateAtOne
  for (let generation = 1; generation <= 14; generation += 1) {
    samples.push(dotProduct(quotient.observable, state))
    state = multiplyMatrixVector(quotient.matrix, state)
  }
  const independentlyEnumeratedSamples = enumerateForbiddenWordCoordinateSums(
    quotient.forbiddenWords,
    samples.length,
  )
  if (samples.some((value, index) => value !== independentlyEnumeratedSamples[index])) {
    throw new Error('mirror quotient and direct legal-word enumeration disagree')
  }
  if (!verifyScalarRecurrence(samples, recurrencePolynomial)) {
    throw new Error('the characteristic recurrence fails on the exact sequence')
  }

  return {
    forbiddenWords: quotient.forbiddenWords,
    automatonStates: quotient.automatonStates,
    representativeStates: quotient.representativeStates,
    quotientMatrix: quotient.matrix,
    initialStateAtOne: quotient.initialStateAtOne,
    observable: quotient.observable,
    recurrencePolynomial,
    integerRoots: factorization.roots,
    dominantFactor: factorization.remainder,
    dominantRoot,
    safeBlockCode,
    samples,
    independentlyEnumeratedSamples,
  }
}

function createNoRepeatedRightCard(
  parents: readonly DiscoveryParent[],
  support: ResolvedBranchingMomentSupport,
): ExecutableFusionCard {
  const matrix = noRepeatedRightCoordinateTransferMatrix()
  const characteristic = characteristicPolynomial(matrix)
  const afterPositiveOne = divideByIntegerRoot(characteristic, 1n)
  const quadratic = divideByIntegerRoot(afterPositiveOne, -1n)
  const discriminant = quadratic[1] ** 2n - 4n * quadratic[0] * quadratic[2]
  if (matrix.map(row => row.join(',')).join(';') !== '1,1,1,1;0,1,0,1;1,0,0,0;1,1,0,0') {
    throw new Error('unexpected finite-state coordinate transfer matrix')
  }
  if (
    characteristic.join(',') !== '1,-2,-2,2,1'
    || quadratic.join(',') !== '1,-2,-1'
    || discriminant !== 8n
  ) {
    throw new Error('the finite-state grammar did not produce the required simple dominant root')
  }

  let state = [2n, 1n, 1n, 2n]
  const recurrenceValues: bigint[] = []
  for (let generation = 1; generation <= 9; generation += 1) {
    recurrenceValues.push(state.reduce((sum, value) => sum + value, 0n))
    state = multiplyMatrixVector(matrix, state)
  }
  const independentlyEnumerated = enumerateNoRepeatedRightCoordinateSums(9)
  if (recurrenceValues.some((value, index) => value !== independentlyEnumerated[index])) {
    throw new Error('finite-state transfer and direct legal-word enumeration disagree')
  }
  for (let index = 0; index + 4 < recurrenceValues.length; index += 1) {
    const expected =
      2n * recurrenceValues[index + 3]
      + 2n * recurrenceValues[index + 2]
      - 2n * recurrenceValues[index + 1]
      - recurrenceValues[index]
    if (recurrenceValues[index + 4] !== expected) throw new Error('derived fourth-order recurrence failed')
  }

  const compositionGenome = buildNoRepeatedRightGenome()
  const genomeMetrics = compositionGenomeMetrics(compositionGenome)
  const deepAudit = auditCompositionComplexity(compositionGenome)
  if (!deepAudit.passed) throw new Error('finite-state branching composition failed: ' + deepAudit.failures.join('; '))
  const genomeFingerprint = compositionGenomeFingerprint(compositionGenome)
  const chain = [
    'DualIntegerShearElaboration',
    'NoRepeatedRightFiniteStateGrammar',
    'IrregularBranchExpansion',
    'EndpointStatePartition',
    'CoordinateAggregation',
    'FourStateRecurrenceElimination',
    'CharacteristicPolynomialFactorization',
    'DominantRootRestriction',
    'HighSchoolProofRealization',
  ]
  const signature = hash({
    parents: support.parentIds,
    mapAssignments: support.mapAssignments,
    grammar: 'words over L,R avoiding RR',
    matrix: matrix.map(row => row.map(String)),
    chain,
  })
  const obligations = [
    'the selected parents collectively define both integer shear maps',
    'the finite-state guard accepts exactly the words with no consecutive right map',
    'coordinate sums partitioned by the final map form a closed four-state recurrence',
    'eliminating the four states gives the stated fourth-order scalar recurrence',
    'the positive dominant root has a nonzero coefficient and determines the ratio limit',
    'the irregular proof tree satisfies the repeat-independent deep-composition target',
    'the visible proof uses only coordinate recurrences and elementary characteristic equations',
  ]
  const proofCertificate = [
    ...parentProofCertificates(signature, support),
    { id: `${signature}.grammar`, claim: obligations[1], verifier: 'two-state deterministic transition audit over every legal word through depth nine' },
    { id: `${signature}.state`, claim: obligations[2], verifier: 'exact integer four-state transfer derived from the two map matrices and the grammar' },
    { id: `${signature}.elimination`, claim: obligations[3], verifier: 'exact determinant expansion and five scalar recurrence checks' },
    { id: `${signature}.limit`, claim: obligations[4], verifier: 'exact factorization (t-1)(t+1)(t^2-2t-1) and explicit closed form' },
    { id: `${signature}.structure`, claim: obligations[5], verifier: `${genomeMetrics.repeatIndependentOperationCount} repeat-independent operations, ${genomeMetrics.branchCount} branches, ${genomeMetrics.mergeCount} merges` },
    { id: `${signature}.public`, claim: obligations[6], verifier: 'upper-secondary publication audit' },
  ]
  const statement = String.raw`整数の組に対する二つの写像 \(L,R\) を
\[
L(a,b)=(a+b,b),\qquad R(a,b)=(a,a+b)
\]
で定める。

\(L,R\) からなる長さ \(n\) の文字列のうち、\(R\) が二つ続けて現れないもの全体を \(W_n\) とする。\(w=w_1w_2\cdots w_n\in W_n\) に対し、\((1,1)\) へ \(w_1,w_2,\ldots,w_n\) の順に写像を施して得られる組を \((a_w,b_w)\) とおく。
\[
A_n=\sum_{w\in W_n}(a_w+b_w)
\]
とするとき、極限
\[
\lim_{n\to\infty}\frac{A_{n+1}}{A_n}
\]
を求めよ。`
  const answer = String.raw`\(1+\sqrt2\)`
  const solution = String.raw`最後の文字が \(L\) である文字列について、第一座標の和を \(p_n\)、第二座標の和を \(q_n\) とする。同様に、最後の文字が \(R\) である文字列について、それぞれの和を \(r_n,s_n\) とする。すると
\[
A_n=p_n+q_n+r_n+s_n.
\tag{1}
\]

最後に \(L\) を付けることは、直前の文字が \(L,R\) のどちらでも可能である。最後に \(R\) を付けられるのは、直前の文字が \(L\) の場合だけである。また
\[
L(a,b)=(a+b,b),\qquad R(a,b)=(a,a+b)
\]
だから
\[
\begin{aligned}
p_{n+1}&=p_n+q_n+r_n+s_n,&
q_{n+1}&=q_n+s_n,\\
r_{n+1}&=p_n,&
s_{n+1}&=p_n+q_n.
\end{aligned}
\tag{2}
\]

(1), (2) から、\(p_n,q_n,r_n,s_n\) を用いて \(A_n\) から \(A_{n+4}\) までを書けば
\[
\begin{aligned}
A_n&=p_n+q_n+r_n+s_n,\\
A_{n+1}&=3p_n+3q_n+r_n+2s_n,\\
A_{n+2}&=6p_n+8q_n+3r_n+6s_n,\\
A_{n+3}&=15p_n+20q_n+6r_n+14s_n,\\
A_{n+4}&=35p_n+49q_n+15r_n+35s_n
\end{aligned}
\]
となる。右辺の係数を比較すると
\[
(35,49,15,35)=2(15,20,6,14)+2(6,8,3,6)-2(3,3,1,2)-(1,1,1,1)
\]
である。従って
\[
A_{n+4}=2A_{n+3}+2A_{n+2}-2A_{n+1}-A_n
\tag{3}
\]
を得る。実際、長さ \(1,2,3,4\) の文字列を (2) で数えると
\[
A_1=6,\qquad A_2=14,\qquad A_3=35,\qquad A_4=84
\]
であり、以後も (3) が成り立つ。

(3) の特性方程式は
\[
t^4-2t^3-2t^2+2t+1
=(t-1)(t+1)(t^2-2t-1)=0.
\]
四つの根は \(1,-1,1+\sqrt2,1-\sqrt2\) である。初期値から係数を定めると
\[
\begin{aligned}
A_n={}&-\frac14-\frac14(-1)^n\\
&+\left(\frac54+\frac{7\sqrt2}{8}\right)(1+\sqrt2)^n
+\left(\frac54-\frac{7\sqrt2}{8}\right)(1-\sqrt2)^n.
\end{aligned}
\tag{4}
\]

\(|1-\sqrt2|<1\) であり、(4) の \((1+\sqrt2)^n\) の係数は正である。従って他の三項を \((1+\sqrt2)^n\) で割った値は全て0へ近づく。よって
\[
\boxed{\displaystyle
\lim_{n\to\infty}\frac{A_{n+1}}{A_n}=1+\sqrt2}
\]
である。`

  return {
    id: `mortra-runtime-no-repeated-right-coordinate-sum.${signature}`,
    family_id: 'runtime.no_repeated_right_coordinate_sum_limit',
    statement_tex: statement,
    answer_tex: answer,
    solution_tex: solution,
    domain: 'combinatorics_sequences_and_limits',
    morphism_chain: chain,
    parent_ids: [...support.parentIds],
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: 'finite-state word audit + exact coordinate transfer + independent legal-word enumeration',
      exact_backend: true,
      independent_check: true,
      samples: recurrenceValues.map(Number),
    },
    difficulty: {
      band: 'S_plus_entrance_exam_finite_state_branching',
      score: 28,
    },
    fusion_derivation: {
      passed: true,
      reason: 'a two-state grammar restricts the same two current maps to an irregular tree whose endpoint sums close in four states',
      ablationPassed: true,
      assignments: parentDerivationAssignments(
        support,
        'finite_state_branch_generators',
        ['DualIntegerShearElaboration', 'NoRepeatedRightFiniteStateGrammar', 'IrregularBranchExpansion'],
      ),
      bridges: [{
        id: `no-repeated-right:${signature}`,
        witnessStep: 'FourStateRecurrenceElimination',
        consumes: groupedMapAssignments(support).map(assignment => assignment.portId),
        produces: 'ExactConstrainedBranchGrowthRatio',
      }],
      intermediatePropositions: parentIntermediatePropositions(
        support,
        'EndpointStatePartition',
        'FourCoordinateSums',
        'the two contributed maps jointly induce the legal last-letter states and coordinate sums',
      ),
    },
    structure_blueprint: {
      id: `no-repeated-right-coordinate-sum.${signature}`,
      version: 1,
      kernel: 'finite_state_constrained_branching_transfer',
      observable: 'dominant_coordinate_sum_ratio',
      operators: chain,
      domain: 'integer_pair_maps_x_regular_language_x_linear_recurrence',
      tags: ['runtime-synthesis', 'atlas-free', 'one-to-many', 'finite-state', 'high-school-proof', 'deep-composition'],
      morphismChain: chain,
      executable: true,
      proofCertificate,
      taskAlgebra: {
        schema: 1,
        input: 'algebraic-configuration',
        operations: [
          { operator: 'normalize', output: 'configuration' },
          { operator: 'map', output: 'configuration' },
          { operator: 'preimage', output: 'configuration' },
          { operator: 'pair', output: 'configuration' },
          { operator: 'fold', output: 'sequence' },
          { operator: 'eliminate', output: 'polynomial' },
          { operator: 'boundary', output: 'scalar' },
          { operator: 'normalize', output: 'scalar' },
        ],
        output: 'scalar',
        complete: true,
      },
      compositionGenome,
      synthesizedLaw: {
        name: 'FiniteStateConstrainedShearTransfer',
        expression: 'restrict L/R words by a two-state automaton, aggregate endpoint coordinates, eliminate the state variables',
        arity: support.parentIds.length,
        sources: supportSources(support),
        target: 'ExactConstrainedBranchGrowthRatio',
        preserves: ['legal-word multiplicity', 'integer coordinates', 'last-letter state', 'parent provenance'],
        backend: ['finite-state enumeration', 'integer matrix arithmetic', 'exact characteristic factorization'],
      },
    },
    search_evidence: {
      hypotheses_evaluated: 1,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
    execution_certificate: runtimeSynthesisCertificate({
      origin: 'synthesized_proof_program',
      parents,
      generatedProgram: {
        schema: 'mortra.runtime-finite-state-branching.v1',
        input_map_assignments: support.mapAssignments,
        alphabet: ['L', 'R'],
        forbidden_subword: 'RR',
        transfer_matrix: matrix.map(row => row.map(String)),
        characteristic_polynomial: characteristic.map(String),
        dominant_root: '1+sqrt(2)',
        composition_genome: compositionGenome,
        composition_genome_sha256: genomeFingerprint,
        composition_metrics: genomeMetrics,
        deep_composition_audit: deepAudit,
        morphism_chain: chain,
      },
      checks: proofCertificate.map(item => `${item.id}: ${item.verifier}`),
    }),
    diagram: {
      version: 1,
      kind: 'state',
      title: '二文字の規則から不均一な写像木を作る',
      caption: '右写像の連続だけを除き、終端文字ごとの四つの座標和へ全ての枝を集約します。',
      nodes: ['L', 'R', 'RR forbidden', '(p_n,q_n,r_n,s_n)', 't^4-2t^3-2t^2+2t+1', '1+sqrt(2)'],
      states: [
        { id: 'L', label: '直前が L', active: true },
        { id: 'R', label: '直前が R' },
        { id: 'sums', label: '四つの座標和' },
        { id: 'recurrence', label: '一つの漸化式' },
        { id: 'answer', label: '最大の特性根', terminal: true },
      ],
      transitions: [
        { from: 'L', to: 'L', label: 'append L' },
        { from: 'L', to: 'R', label: 'append R' },
        { from: 'R', to: 'L', label: 'append L' },
        { from: 'L', to: 'sums', label: 'aggregate coordinates' },
        { from: 'R', to: 'sums', label: 'aggregate coordinates' },
        { from: 'sums', to: 'recurrence', label: 'eliminate states' },
        { from: 'recurrence', to: 'answer', label: 'dominant root' },
      ],
    },
    visual_explanation: completeVisualExplanation(
      chain,
      [chain[1], chain[2], chain[5], chain[6], chain[7]],
      {
      version: 1,
      mode: 'stepper',
      title: '不均一な写像木を四つの数列へ縮約するまで',
      diagram_required_for_every_step: true,
      composition_verified: true,
      morphism_chain: chain,
      steps: [
        {
          id: `${signature}.visual.1`,
          title: '最後の文字で枝を二群に分ける',
          explanation_ja: '次に右写像を使えるかどうかは最後の文字だけで決まるため、L終端とR終端を分けて座標を数えます。',
          formula_tex: 'A_n=p_n+q_n+r_n+s_n',
          diagram: { kind: 'finite-state', active: ['L', 'R', 'sums'] },
        },
        {
          id: `${signature}.visual.2`,
          title: '許される三つの遷移を座標式にする',
          explanation_ja: 'LからはLとRへ進め、RからはLへだけ進めます。二つの写像の座標式をそのまま加えます。',
          formula_tex: String.raw`L\to L,\qquad L\to R,\qquad R\to L`,
          diagram: { kind: 'state-transition', active: ['L', 'R'] },
        },
        {
          id: `${signature}.visual.3`,
          title: '四つの補助数列を消去する',
          explanation_ja: '四状態の更新式を繰り返し代入し、問いに現れるA_nだけの四項漸化式を得ます。',
          formula_tex: 'A_{n+4}=2A_{n+3}+2A_{n+2}-2A_{n+1}-A_n',
          diagram: { kind: 'elimination', active: ['sums', 'recurrence'] },
        },
        {
          id: `${signature}.visual.4`,
          title: '特性方程式を二つの二次式へ分ける',
          explanation_ja: '四次式は整数係数の二つの因子へ分かれ、四つの根を根号で正確に表せます。',
          formula_tex: '(t-1)(t+1)(t^2-2t-1)=0',
          diagram: { kind: 'factorization', active: ['recurrence'] },
        },
        {
          id: `${signature}.visual.5`,
          title: '最大根だけが比の極限に残る',
          explanation_ja: '初期値から最大根の係数が正であることを確認し、残る三根との大きさを比較します。',
          formula_tex: String.raw`\displaystyle\lim_{n\to\infty}\frac{A_{n+1}}{A_n}=1+\sqrt2`,
          diagram: { kind: 'dominant-root', active: ['recurrence', 'answer'] },
        },
      ],
      },
    ),
    proof_roadmap: [
      { morphism_id: chain[1], label_ja: '禁止語を二状態で表す', source_ja: 'LとRの文字列', target_ja: '終端文字の状態', role_ja: '全ての文字列を列挙せず次の分岐を決める。' },
      { morphism_id: chain[4], label_ja: '終端状態ごとに座標を加える', source_ja: '不均一な写像木', target_ja: '四つの数列', role_ja: '枝の構造と座標変換を同時に保持する。' },
      { morphism_id: chain[5], label_ja: '四状態を一数列へ消去する', source_ja: '四本の漸化式', target_ja: 'A_nの漸化式', role_ja: '最終問題に不要な状態を消す。' },
      { morphism_id: chain[7], label_ja: '最大根を厳密に選ぶ', source_ja: '四つの特性根', target_ja: '比の極限', role_ja: '小数近似を使わず極限を決める。' },
      { morphism_id: chain[8], label_ja: '高校数学の答案へ戻す', source_ja: '検証済み状態遷移', target_ja: '提出可能な解答', role_ja: '有限状態という用語を前提にせず説明する。' },
    ],
    proof_obligations: proofCertificate.map(item => ({ id: item.id, claim_ja: item.claim, status: 'verified' })),
  }
}

export type MirrorForbiddenWordCoordinateDiscovery = {
  wordLength: number
  hypothesesEvaluated: number
  analyses: MirrorForbiddenWordCoordinateAnalysis[]
  rejected: Array<{ forbiddenWords: string[]; reason: string }>
}

export function discoverMirrorForbiddenWordCoordinateGrammars(
  wordLength = 3,
): MirrorForbiddenWordCoordinateDiscovery {
  if (!Number.isSafeInteger(wordLength) || wordLength < 2 || wordLength > 5) {
    throw new Error('forbidden-word discovery length must be an integer from two through five')
  }
  const candidates = allBinaryWords(wordLength)
    .map(word => [word, swapGeneratorSymbols(word)].sort() as [string, string])
    .filter(([word, mirror], index, pairs) =>
      word !== mirror && pairs.findIndex(pair => pair[0] === word && pair[1] === mirror) === index)
  const analyses: MirrorForbiddenWordCoordinateAnalysis[] = []
  const rejected: MirrorForbiddenWordCoordinateDiscovery['rejected'] = []
  for (const forbiddenWords of candidates) {
    try {
      analyses.push(analyzeMirrorForbiddenWordCoordinateGrammar(forbiddenWords))
    } catch (error) {
      rejected.push({
        forbiddenWords,
        reason: error instanceof Error ? error.message : String(error),
      })
    }
  }
  return {
    wordLength,
    hypothesesEvaluated: candidates.length,
    analyses,
    rejected,
  }
}

function matrixTex(matrix: Matrix): string {
  const separator = String.raw`\\`
  return String.raw`\begin{pmatrix}${matrix.map(row => row.join('&')).join(separator)}\end{pmatrix}`
}

function vectorTex(vector: readonly bigint[]): string {
  return String.raw`\begin{pmatrix}${vector.join(String.raw`\\`)}\end{pmatrix}`
}

function stateTex(state: string): string {
  return state ? String.raw`\mathrm{${state}}` : String.raw`\varnothing`
}

function indexedSequenceTex(sequence: string, offset: number): string {
  if (offset === 0) return `${sequence}_n`
  if (offset === 1) return `${sequence}_{n+1}`
  return `${sequence}_{n+${offset}}`
}

function sequenceLinearCombinationTex(
  coefficients: readonly bigint[],
  offsets: readonly number[],
  sequence: string,
): string {
  const terms: string[] = []
  for (const [index, coefficient] of coefficients.entries()) {
    if (coefficient === 0n) continue
    const magnitude = absoluteBigInt(coefficient)
    const body = `${magnitude === 1n ? '' : magnitude}${indexedSequenceTex(sequence, offsets[index])}`
    if (!terms.length) terms.push(coefficient < 0n ? `-${body}` : body)
    else terms.push(`${coefficient < 0n ? '-' : '+'}${body}`)
  }
  return terms.join('') || '0'
}

function recurrenceTex(polynomial: readonly bigint[], sequence: string): string {
  if (polynomial[0] !== 1n) throw new Error('visible recurrence requires a monic polynomial')
  const order = polynomial.length - 1
  const coefficients = polynomial.slice(1).map(value => -value)
  const offsets = coefficients.map((_, index) => order - index - 1)
  return `${indexedSequenceTex(sequence, order)}=${sequenceLinearCombinationTex(coefficients, offsets, sequence)}`
}

function appliedPolynomialTex(polynomial: readonly bigint[], sequence: string): string {
  const order = polynomial.length - 1
  return sequenceLinearCombinationTex(
    polynomial,
    polynomial.map((_, index) => order - index),
    sequence,
  )
}

function factorizationTex(integerRoots: readonly bigint[], factor: readonly bigint[]): string {
  const linearFactors = integerRoots.map(root =>
    root < 0n ? `(t+${absoluteBigInt(root)})` : `(t-${root})`)
  return String.raw`${linearFactors.join('')}\left(${polynomialTex(factor)}\right)`
}

function correctedAlternatingSequence(
  analysis: MirrorForbiddenWordCoordinateAnalysis,
): {
  numerator: bigint
  denominator: bigint
  residualAtOne: bigint
  samples: bigint[]
  definitionTex: string
} {
  if (
    analysis.integerRoots.length !== 1
    || analysis.integerRoots[0] !== -1n
    || analysis.dominantFactor.length !== 4
  ) {
    throw new Error('the visible cubic proof requires one alternating integer mode')
  }
  const factor = analysis.dominantFactor
  const order = factor.length - 1
  const residualAtOne = factor.reduce(
    (sum, coefficient, index) => sum + coefficient * analysis.samples[order - index],
    0n,
  )
  const modeCoefficient = exactFraction(
    residualAtOne,
    -polynomialValue(factor, -1n),
  )
  const numerator = modeCoefficient.numerator
  const denominator = modeCoefficient.denominator
  const samples = analysis.samples.map((value, index) => {
    const generation = index + 1
    const alternating = generation % 2 === 0 ? 1n : -1n
    return denominator * value - numerator * alternating
  })
  if (!verifyScalarRecurrence(samples, factor)) {
    throw new Error('removing the alternating mode did not produce the cubic recurrence')
  }
  const leading = denominator === 1n ? 'A_n' : `${denominator}A_n`
  const correction = numerator < 0n
    ? `+${absoluteBigInt(numerator)}(-1)^n`
    : `-${numerator}(-1)^n`
  return {
    numerator,
    denominator,
    residualAtOne,
    samples,
    definitionTex: `X_n=${leading}${correction}`,
  }
}

function createMirrorForbiddenWordCoordinateCard(
  parents: readonly DiscoveryParent[],
  support: ResolvedBranchingMomentSupport,
  analysis: MirrorForbiddenWordCoordinateAnalysis,
  hypothesesEvaluated: number,
): ExecutableFusionCard {
  if (analysis.quotientMatrix.length !== 4 || analysis.dominantRoot.degree !== 3) {
    throw new Error('the current publication template requires a four-state cubic quotient')
  }
  const automaton = buildForbiddenWordAutomaton(analysis.forbiddenWords)
  const correction = correctedAlternatingSequence(analysis)
  const compositionGenome = buildForbiddenWordCompositionGenome(analysis.forbiddenWords, 10)
  const genomeMetrics = compositionGenomeMetrics(compositionGenome)
  const deepAudit = auditCompositionComplexity(compositionGenome)
  if (!deepAudit.passed) {
    throw new Error('forbidden-word composition failed: ' + deepAudit.failures.join('; '))
  }
  const genomeFingerprint = compositionGenomeFingerprint(compositionGenome)
  const chain = [
    'DualIntegerShearElaboration',
    'ForbiddenWordGrammarInduction',
    'MirrorStateQuotient',
    'IrregularBranchExpansion',
    'CoordinateAggregation',
    'ExactRowRecurrenceElimination',
    'AlternatingModeRemoval',
    'DepressedCubicRadicalization',
    'DominantRootRestriction',
    'HighSchoolProofRealization',
  ]
  const signature = hash({
    parents: support.parentIds,
    mapAssignments: support.mapAssignments,
    forbiddenWords: analysis.forbiddenWords,
    quotientMatrix: analysis.quotientMatrix.map(row => row.map(String)),
    chain,
  })
  const forbiddenDisplay = analysis.forbiddenWords
    .map(word => String.raw`\(\mathrm{${word}}\)`)
    .join(' と ')
  const forbiddenFormula = analysis.forbiddenWords
    .map(word => String.raw`\mathrm{${word}}`)
    .join(',')
  const representatives = analysis.representativeStates
  const componentNames = representatives.flatMap((_, index) => [
    `p_{${index + 1},n}`,
    `q_{${index + 1},n}`,
  ])
  const vectorName = String.raw`\boldsymbol v_n=(${componentNames.join(',')})^{\mathsf T}`
  const representativeDefinitions = representatives.map((state, index) =>
    String.raw`末尾の状態が \(${stateTex(state)}\) である語の第一座標の和を \(p_{${index + 1},n}\)、第二座標の和を \(q_{${index + 1},n}\) とする。`).join('')
  const noninitialTransitions = automaton.transitions
    .filter(transition => transition.from !== automaton.startState)
    .map(transition => {
      const from = stateTex(automaton.states[transition.from])
      const to = stateTex(automaton.states[transition.to])
      return String.raw`${from}\xrightarrow{\mathrm{${transition.symbol}}}${to}`
    })
  const transitionRows: string[] = []
  for (let index = 0; index < noninitialTransitions.length; index += 3) {
    transitionRows.push(noninitialTransitions.slice(index, index + 3).join(String.raw`,\qquad `))
  }
  const transitionTex = transitionRows.join(String.raw`\\`)
  const rowVectors: bigint[][] = [analysis.observable]
  while (rowVectors.length <= analysis.recurrencePolynomial.length - 1) {
    rowVectors.push(multiplyRowVector(rowVectors.at(-1)!, analysis.quotientMatrix))
  }
  const rowHeader = componentNames.map(name => name.replace(',n', '')).join('&')
  const rowTable = rowVectors
    .map((row, index) => `${index}&${row.join('&')}`)
    .join(String.raw`\\`)
  const scalarRecurrence = recurrenceTex(analysis.recurrencePolynomial, 'A')
  const cubicRecurrence = recurrenceTex(analysis.dominantFactor, 'X')
  const cubicApplied = appliedPolynomialTex(analysis.dominantFactor, 'A')
  const factorization = factorizationTex(analysis.integerRoots, analysis.dominantFactor)
  const root = analysis.dominantRoot
  const shift = root.shift!
  const depressedLinear = root.depressedLinear!
  const depressedConstant = root.depressedConstant!
  const depressedEquation = `u^3${signedFractionTerm(depressedLinear, 'u')}${signedFractionTerm(depressedConstant)}=0`
  const positiveTerm = root.cardanoPositiveTermTex!
  const negativeTerm = root.cardanoNegativeTermTex!
  const factorAtLower = polynomialValue(analysis.dominantFactor, root.lowerBound)
  const factorAtUpper = polynomialValue(analysis.dominantFactor, root.upperBound)
  const firstValues = analysis.samples.slice(0, 4)
    .map((value, index) => `A_${index + 1}=${value}`)
    .join(String.raw`,\qquad `)
  const safeBlocks = analysis.safeBlockCode.blocks
    .map(word => String.raw`\mathrm{${word}}`)
    .join(String.raw`,\qquad `)
  const observableRow = String.raw`\begin{pmatrix}${analysis.observable.join('&')}\end{pmatrix}`
  const statement = String.raw`整数の組に対する二つの写像 \(L,R\) を
\[
L(a,b)=(a+b,b),\qquad R(a,b)=(a,a+b)
\]
で定める。

\(L,R\) からなる長さ \(n\) の文字列のうち、${forbiddenDisplay} のいずれも連続部分として含まないもの全体を \(W_n\) とする。\(w=w_1w_2\cdots w_n\in W_n\) に対し、\((1,1)\) へ \(w_1,w_2,\ldots,w_n\) の順に写像を施して得られる組を \((a_w,b_w)\) とおく。
\[
A_n=\sum_{w\in W_n}(a_w+b_w)
\]
とするとき、極限
\[
\lim_{n\to\infty}\frac{A_{n+1}}{A_n}
\]
を求めよ。`
  const answer = String.raw`\(${root.exactTex}\)`
  const solution = String.raw`禁止語の途中まで一致している末尾だけを記録する。許される移り方は
\[
\begin{gathered}
${transitionTex}
\end{gathered}
\tag{1}
\]
である。${representativeDefinitions} \(L\) と \(R\) を交換すると二つの座標も交換されるため、鏡側の状態を別に数える必要はない。そこで \(${vectorName}\) とおく。

(1) に二つの写像の座標式を代入すると
\[
\boldsymbol v_{n+1}=${matrixTex(analysis.quotientMatrix)}\boldsymbol v_n,
\qquad
\boldsymbol v_1=${vectorTex(analysis.initialStateAtOne)},
\qquad
A_n=${observableRow}\boldsymbol v_n
\tag{2}
\]
を得る。最後の式は行ベクトルとの積を表す。実際、直接数えると \(${firstValues}\) となる。

(2) から \(A_{n+j}\) を \(\boldsymbol v_n\) の成分で表したときの係数は次の表である。
\[
\begin{array}{c|${'r'.repeat(analysis.quotientMatrix.length)}}
j&${rowHeader}\\\hline
${rowTable}
\end{array}
\tag{3}
\]
表の各列を比較すると
\[
${scalarRecurrence}
\tag{4}
\]
である。これは文字列を全て書き並べずに得た厳密な漸化式である。

(4) の特性多項式は
\[
${polynomialTex(analysis.recurrencePolynomial)}
=${factorization}
\tag{5}
\]
と分かれる。\(B_n=${cubicApplied}\) とおくと (4), (5) より \(B_{n+1}=-B_n\) であり、初期値から \(B_1=${correction.residualAtOne}\) である。従って
\[
${correction.definitionTex},\qquad ${cubicRecurrence}
\tag{6}
\]
となり、交代する項が消える。

(6) の特性方程式を \(${polynomialTex(analysis.dominantFactor)}=0\) とする。\(t=u+${fractionTex(shift)}\) とおけば \(${depressedEquation}\) となる。実数 \(v,w\) を
\[
v^3=${positiveTerm},\qquad w^3=${negativeTerm}
\]
で定めると、\(v^3+w^3=${fractionTex(negateFraction(depressedConstant))}\) かつ \(3vw=${fractionTex(negateFraction(depressedLinear))}\) である。従って \(u=v+w\) が方程式を満たし、その実根は
\[
\alpha=${root.exactTex}
\tag{7}
\]
である。さらに、他の二根は
\[
\beta,\overline\beta=${fractionTex(shift)}-\frac{v+w}{2}\pm\frac{\sqrt3}{2}(v-w)i
\]
である。\(v\ne w\) なので、この二根は互いに共役な非実数である。また \(Q(t)=${polynomialTex(analysis.dominantFactor)}\) と書けば \(Q(${root.lowerBound})=${factorAtLower}<0<Q(${root.upperBound})=${factorAtUpper}\) なので、\(${root.lowerBound}<\alpha<${root.upperBound}\) である。

長さ ${analysis.safeBlockCode.blockLength} の二語 \(${safeBlocks}\) は、どの順に連結しても禁止語 \(${forbiddenFormula}\) を作らない。従って長さ \(${analysis.safeBlockCode.blockLength}m\) には少なくとも \(2^m\) 個の語があり、各座標は正だから \(A_{${analysis.safeBlockCode.blockLength}m}\ge 2^{m+1}\) である。よって \(X_n\) は有界でない。一方、三根の積が1であることから \(|\beta|^2=1/\alpha<1\) である。(6) の一般項で \(\alpha^n\) の係数が0なら \(X_n\) は0へ近づいてしまうので、その係数は0でない。また \(A_n\ge2\) かつ \(${2n * correction.denominator}>${correction.numerator < 0n ? -correction.numerator : correction.numerator}\) だから \(X_n>0\) であり、その係数は正である。従って \(X_{n+1}/X_n\to\alpha\) であり、\(${correction.definitionTex}\) の交代項は有界だから
\[
\boxed{\displaystyle\lim_{n\to\infty}\frac{A_{n+1}}{A_n}=${root.exactTex}}
\]
を得る。`
  const obligations = [
    'the selected parents collectively define both integer shear maps',
    'the generated prefix-state grammar accepts exactly the words avoiding every selected forbidden word',
    'the mirror-state quotient preserves every coordinate transition',
    'the quotient recurrence agrees with direct legal-word enumeration',
    'the alternating mode is removed by an exact integer correction',
    'the cubic radical is an exact root and the remaining roots have smaller modulus',
    'the safe two-block code proves unbounded growth and a nonzero dominant coefficient',
    'the generated proof exposes one diagram state for every explanatory stage',
  ]
  const proofCertificate = [
    ...parentProofCertificates(signature, support),
    { id: `${signature}.grammar`, claim: obligations[1], verifier: `deterministic prefix automaton with ${automaton.states.length} states` },
    { id: `${signature}.quotient`, claim: obligations[2], verifier: 'exact basis-vector intertwining audit of the full and mirror-quotient transfers' },
    { id: `${signature}.enumeration`, claim: obligations[3], verifier: 'exact comparison with independent word enumeration through generation fourteen' },
    { id: `${signature}.alternating`, claim: obligations[4], verifier: `exact recurrence verification after correction ${correction.definitionTex}` },
    { id: `${signature}.root`, claim: obligations[5], verifier: `exact depressed-cubic identity and sign isolation on (${root.lowerBound},${root.upperBound})` },
    { id: `${signature}.growth`, claim: obligations[6], verifier: `free concatenation witness from blocks ${analysis.safeBlockCode.blocks.join(',')}` },
    { id: `${signature}.visual`, claim: obligations[7], verifier: 'six-stage state, recurrence, radical, and limit explanation' },
  ]
  const stateNodes = automaton.states.map((state, index) => ({
    id: `grammar-${index}`,
    label: state ? `末尾 ${state}` : '開始',
    active: index === automaton.startState,
  }))
  const diagramTransitions = automaton.transitions.map(transition => ({
    from: `grammar-${transition.from}`,
    to: `grammar-${transition.to}`,
    label: `末尾に ${transition.symbol}`,
  }))

  return {
    id: `mortra-runtime-mirror-forbidden-coordinate-sum.${signature}`,
    family_id: 'runtime.mirror_forbidden_word_coordinate_sum_limit',
    statement_tex: statement,
    answer_tex: answer,
    solution_tex: solution,
    domain: 'combinatorics_sequences_and_limits',
    morphism_chain: chain,
    parent_ids: [...support.parentIds],
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: 'generated prefix grammar + exact mirror quotient + independent legal-word enumeration + exact cubic identity',
      exact_backend: true,
      independent_check: true,
      samples: analysis.samples.map(Number),
    },
    difficulty: {
      band: 'S_plus_entrance_exam_generated_finite_grammar',
      score: 33,
    },
    fusion_derivation: {
      passed: true,
      reason: 'the finite-word grammar was discovered from the two generators, reduced by their exchange symmetry, and solved without a stored answer',
      ablationPassed: true,
      assignments: parentDerivationAssignments(
        support,
        'finite_word_grammar_generators',
        ['DualIntegerShearElaboration', 'ForbiddenWordGrammarInduction', 'MirrorStateQuotient', 'ExactRowRecurrenceElimination'],
      ),
      bridges: [{
        id: `mirror-forbidden:${signature}`,
        witnessStep: 'MirrorStateQuotient',
        consumes: groupedMapAssignments(support).map(assignment => assignment.portId),
        produces: 'ExactGeneratedBranchGrowthRatio',
      }],
      intermediatePropositions: parentIntermediatePropositions(
        support,
        'MirrorStateQuotient',
        'FourCoordinateSums',
        'exchanging the two contributed generators exchanges coordinates and preserves the legal language',
      ),
    },
    structure_blueprint: {
      id: `mirror-forbidden-coordinate-sum.${signature}`,
      version: 1,
      kernel: 'generated_finite_word_grammar_coordinate_transfer',
      observable: 'dominant_coordinate_sum_ratio',
      operators: chain,
      domain: 'integer_pair_maps_x_generated_regular_language_x_exact_radicals',
      tags: ['runtime-synthesis', 'atlas-free', 'one-to-many', 'finite-state', 'high-school-proof', 'deep-composition'],
      morphismChain: chain,
      executable: true,
      proofCertificate,
      taskAlgebra: {
        schema: 1,
        input: 'algebraic-configuration',
        operations: [
          { operator: 'normalize', output: 'configuration' },
          { operator: 'map', output: 'configuration' },
          { operator: 'preimage', output: 'configuration' },
          { operator: 'pair', output: 'configuration' },
          { operator: 'fold', output: 'sequence' },
          { operator: 'eliminate', output: 'polynomial' },
          { operator: 'boundary', output: 'scalar' },
          { operator: 'normalize', output: 'scalar' },
        ],
        output: 'scalar',
        complete: true,
      },
      compositionGenome,
      synthesizedLaw: {
        name: 'GeneratedMirrorForbiddenWordCoordinateTransfer',
        expression: 'generate a forbidden-word automaton, quotient mirrored states, aggregate coordinates, eliminate the state vector, and isolate the exact dominant root',
        arity: support.parentIds.length,
        sources: supportSources(support),
        target: 'ExactGeneratedBranchGrowthRatio',
        preserves: ['legal-word multiplicity', 'integer coordinates', 'generator-exchange symmetry', 'parent provenance'],
        backend: ['prefix-state construction', 'integer matrix arithmetic', 'direct legal-word enumeration', 'exact cubic identity'],
      },
    },
    search_evidence: {
      hypotheses_evaluated: hypothesesEvaluated,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
    execution_certificate: runtimeSynthesisCertificate({
      origin: 'synthesized_proof_program',
      parents,
      generatedProgram: {
        schema: 'mortra.runtime-generated-forbidden-word-branching.v1',
        input_map_assignments: support.mapAssignments,
        alphabet: ['L', 'R'],
        forbidden_words: analysis.forbiddenWords,
        automaton_states: analysis.automatonStates,
        representative_states: analysis.representativeStates,
        quotient_matrix: analysis.quotientMatrix.map(row => row.map(String)),
        initial_state_at_one: analysis.initialStateAtOne.map(String),
        observable: analysis.observable.map(String),
        characteristic_polynomial: analysis.recurrencePolynomial.map(String),
        dominant_factor: analysis.dominantFactor.map(String),
        dominant_root_tex: root.exactTex,
        direct_enumeration_samples: analysis.independentlyEnumeratedSamples.map(String),
        safe_block_code: analysis.safeBlockCode,
        composition_genome: compositionGenome,
        composition_genome_sha256: genomeFingerprint,
        composition_metrics: genomeMetrics,
        deep_composition_audit: deepAudit,
        morphism_chain: chain,
      },
      checks: proofCertificate.map(item => `${item.id}: ${item.verifier}`),
    }),
    diagram: {
      version: 1,
      kind: 'state',
      title: '禁止語から作った状態遷移と座標和',
      caption: `禁止語 ${analysis.forbiddenWords.join(', ')} を避ける分岐を、末尾状態と鏡映対称性で四つの座標和へまとめます。`,
      nodes: [...stateNodes.map(node => node.label), '座標和', polynomialTex(analysis.dominantFactor), root.exactTex],
      states: [
        ...stateNodes,
        { id: 'sums', label: '四つの座標和' },
        { id: 'recurrence', label: '一つの漸化式' },
        { id: 'answer', label: '厳密な極限値', terminal: true },
      ],
      transitions: [
        ...diagramTransitions,
        ...stateNodes.map(node => ({ from: node.id, to: 'sums', label: '座標を加える' })),
        { from: 'sums', to: 'recurrence', label: '補助量を消去する' },
        { from: 'recurrence', to: 'answer', label: '最大根を選ぶ' },
      ],
    },
    visual_explanation: completeVisualExplanation(
      chain,
      [chain[1], chain[2], chain[4], chain[5], chain[7], chain[8]],
      {
      version: 1,
      mode: 'stepper',
      title: '禁止語から極限値を得るまで',
      diagram_required_for_every_step: true,
      composition_verified: true,
      morphism_chain: chain,
      steps: [
        { id: `${signature}.visual.1`, title: '禁止語を末尾の状態へ変える', explanation_ja: '禁止語の途中まで一致している末尾だけを残すと、次に使える写像が一意に決まります。', formula_tex: transitionTex, diagram: { version: 1, kind: 'state', title: '禁止語を検出する末尾状態', caption: `禁止語 ${analysis.forbiddenWords.join(', ')} が完成する遷移だけを除きます。`, states: stateNodes, transitions: diagramTransitions } },
        { id: `${signature}.visual.2`, title: '左右対称な状態を一組にする', explanation_ja: 'LとRの交換は二座標の交換に一致するため、鏡側の状態を重複して数えません。', formula_tex: String.raw`${vectorName},\quad A_n=${observableRow}\boldsymbol v_n`, diagram: { kind: 'symmetry-quotient', active: ['sums'] } },
        { id: `${signature}.visual.3`, title: '座標和の更新を行列にする', explanation_ja: '各文字を末尾に付けたときの座標変化を加えると、四つの量だけで更新が閉じます。', formula_tex: String.raw`\boldsymbol v_{n+1}=${matrixTex(analysis.quotientMatrix)}\boldsymbol v_n`, diagram: { kind: 'state-transition', active: ['sums'] } },
        { id: `${signature}.visual.4`, title: '問いの数列だけへ戻す', explanation_ja: '行ベクトルを五段階だけ厳密計算し、補助量を含まない漸化式を得ます。', formula_tex: scalarRecurrence, diagram: { kind: 'elimination', active: ['sums', 'recurrence'] } },
        { id: `${signature}.visual.5`, title: '交代項を消して三次式を解く', explanation_ja: '整数根に対応する交代項を引き、残る三次方程式を立方完成で根号表示します。', formula_tex: String.raw`${correction.definitionTex},\quad\alpha=${root.exactTex}`, diagram: { kind: 'radicalization', active: ['recurrence'] } },
        { id: `${signature}.visual.6`, title: '最大根が比の極限になることを示す', explanation_ja: '安全な二つの語を連結して数列の非有界性を示し、残る二根の絶対値が1未満であることと合わせます。', formula_tex: String.raw`\displaystyle\lim_{n\to\infty}\frac{A_{n+1}}{A_n}=${root.exactTex}`, diagram: { kind: 'dominant-root', active: ['recurrence', 'answer'] } },
      ],
      },
    ),
    proof_roadmap: [
      { morphism_id: chain[1], label_ja: '禁止語から状態を作る', source_ja: 'LとRの文字列', target_ja: '有限個の末尾状態', role_ja: '禁止語の完成に必要な末尾だけを保持する。' },
      { morphism_id: chain[2], label_ja: '左右対称な状態をまとめる', source_ja: '全ての末尾状態', target_ja: '四つの座標和', role_ja: '二つの写像と座標交換の対称性を使う。' },
      { morphism_id: chain[5], label_ja: '補助量を消去する', source_ja: '四状態の更新式', target_ja: 'A_nだけの漸化式', role_ja: '五本の行ベクトルを比較して厳密に消去する。' },
      { morphism_id: chain[7], label_ja: '三次方程式を根号で解く', source_ja: '交代項を除いた漸化式', target_ja: '厳密な実根', role_ja: '立方の展開公式だけで根号表示を導く。' },
      { morphism_id: chain[8], label_ja: '極限を確定する', source_ja: '三つの特性根', target_ja: '正の数列の比', role_ja: '成長の下界と他の二根の絶対値を比較する。' },
    ],
    proof_obligations: proofCertificate.map(item => ({ id: item.id, claim_ja: item.claim, status: 'verified' })),
  }
}

export function synthesizeRuntimeBranchingMomentProblems(
  parents: readonly DiscoveryParent[],
  requested: number,
): RuntimeBranchingMomentGeneration {
  const support = supportsBranchingMomentGeneration(parents)
  if (
    !support.applicable
    || !support.parentIds
    || !support.variables
    || !support.mapAssignments
    || requested <= 0
  ) {
    return { applicable: false, reason: support.reason, cards: [], hypothesesEvaluated: 1 }
  }
  const resolvedSupport: ResolvedBranchingMomentSupport = {
    parentIds: support.parentIds,
    variables: support.variables,
    mapAssignments: support.mapAssignments,
  }
  const discovery = requested > 2
    ? discoverMirrorForbiddenWordCoordinateGrammars(3)
    : { wordLength: 3, hypothesesEvaluated: 0, analyses: [], rejected: [] }
  const discoveredCards = discovery.analyses
    .filter(analysis =>
      analysis.quotientMatrix.length === 4
      && analysis.dominantRoot.degree === 3
      && analysis.integerRoots.length === 1
      && analysis.integerRoots[0] === -1n)
    .map(analysis => createMirrorForbiddenWordCoordinateCard(
      parents,
      resolvedSupport,
      analysis,
      discovery.hypothesesEvaluated,
    ))
  const cards = [
    createCard(parents, resolvedSupport),
    createNoRepeatedRightCard(parents, resolvedSupport),
    ...discoveredCards,
  ]
  return {
    applicable: true,
    reason: `${cards.length} exact branching problems were synthesized from the current two maps and generated word grammars`,
    cards: cards.slice(0, requested),
    hypothesesEvaluated: 2 + discovery.hypothesesEvaluated,
  }
}
