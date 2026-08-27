import {
  validateFiniteRecurrence,
  type FiniteRecurrenceSpec,
  type PolynomialTerm,
} from '../diagram/finite-state-transition'

export type ModularMatrix = number[][]

export type AffineRecurrenceNormalForm = {
  modulus: number
  order: number
  coefficients: number[]
  constant: number
  initial: number[]
  targetIndex: string
}

export type LinearRecurrenceMatrixChart = {
  kind: 'linear-recurrence-matrix-characteristic-polynomial'
  sourceId: string
  sourceSemanticIds: string[]
  normalForm: AffineRecurrenceNormalForm
  stateConvention: string
  transitionMatrix: ModularMatrix
  recurrenceCharacteristicPolynomial: number[]
  augmentedCharacteristicPolynomial: number[]
  reversibleWith: string[]
  forgotten: string[]
  certificates: Array<{
    claim: string
    method: string
    status: 'certified'
  }>
}

export type MatrixRecurrenceSolution = {
  status: 'certified' | 'abstained' | 'invalid'
  answer?: number
  errors: string[]
  chart?: LinearRecurrenceMatrixChart
  matrixMultiplications: number
}

function canonical(value: number, modulus: number): number {
  return ((value % modulus) + modulus) % modulus
}

function addMod(left: number, right: number, modulus: number): number {
  return Number((BigInt(left) + BigInt(right)) % BigInt(modulus))
}

function multiplyMod(left: number, right: number, modulus: number): number {
  return Number((BigInt(left) * BigInt(right)) % BigInt(modulus))
}

function zeroMatrix(size: number): ModularMatrix {
  return Array.from({ length: size }, () => Array<number>(size).fill(0))
}

function identityMatrix(size: number): ModularMatrix {
  const result = zeroMatrix(size)
  for (let index = 0; index < size; index += 1) result[index][index] = 1
  return result
}

function matrixEquals(left: ModularMatrix, right: ModularMatrix): boolean {
  return left.length === right.length
    && left.every((row, rowIndex) => row.length === right[rowIndex]?.length
      && row.every((value, columnIndex) => value === right[rowIndex][columnIndex]))
}

function multiplyMatrices(
  left: ModularMatrix,
  right: ModularMatrix,
  modulus: number,
): ModularMatrix {
  const size = left.length
  const result = zeroMatrix(size)
  for (let row = 0; row < size; row += 1) {
    for (let pivot = 0; pivot < size; pivot += 1) {
      if (left[row][pivot] === 0) continue
      for (let column = 0; column < size; column += 1) {
        result[row][column] = addMod(
          result[row][column],
          multiplyMod(left[row][pivot], right[pivot][column], modulus),
          modulus,
        )
      }
    }
  }
  return result
}

function multiplyMatrixVector(matrix: ModularMatrix, vector: number[], modulus: number): number[] {
  return matrix.map(row => row.reduce(
    (sum, value, index) => addMod(sum, multiplyMod(value, vector[index], modulus), modulus),
    0,
  ))
}

function multiplyPolynomials(left: number[], right: number[], modulus: number): number[] {
  const result = Array<number>(left.length + right.length - 1).fill(0)
  for (let i = 0; i < left.length; i += 1) {
    for (let j = 0; j < right.length; j += 1) {
      result[i + j] = addMod(result[i + j], multiplyMod(left[i], right[j], modulus), modulus)
    }
  }
  return result
}

function polynomialAtMatrix(coefficients: number[], matrix: ModularMatrix, modulus: number): ModularMatrix {
  const size = matrix.length
  let result = zeroMatrix(size)
  let power = identityMatrix(size)
  for (const coefficient of coefficients) {
    for (let row = 0; row < size; row += 1) {
      for (let column = 0; column < size; column += 1) {
        result[row][column] = addMod(
          result[row][column],
          multiplyMod(coefficient, power[row][column], modulus),
          modulus,
        )
      }
    }
    power = multiplyMatrices(power, matrix, modulus)
  }
  return result
}

function matrixPower(
  matrix: ModularMatrix,
  exponent: bigint,
  modulus: number,
): { matrix: ModularMatrix; multiplications: number } {
  let result = identityMatrix(matrix.length)
  let factor = matrix
  let remaining = exponent
  let multiplications = 0
  while (remaining > 0n) {
    if (remaining % 2n === 1n) {
      result = multiplyMatrices(result, factor, modulus)
      multiplications += 1
    }
    remaining /= 2n
    if (remaining > 0n) {
      factor = multiplyMatrices(factor, factor, modulus)
      multiplications += 1
    }
  }
  return { matrix: result, multiplications }
}

function classifyLinearTerm(term: PolynomialTerm): { variable?: number; constant: boolean } | null {
  const active = term.powers
    .map((power, index) => ({ power, index }))
    .filter(item => item.power !== 0)
  if (!active.length) return { constant: true }
  if (active.length === 1 && active[0].power === 1) {
    return { variable: active[0].index, constant: false }
  }
  return null
}

export function elaborateAffineRecurrence(
  spec: FiniteRecurrenceSpec,
): { normalForm?: AffineRecurrenceNormalForm; errors: string[] } {
  const errors = validateFiniteRecurrence(spec)
  if (errors.length) return { errors }
  const coefficients = Array<number>(spec.initial.length).fill(0)
  let constant = 0
  for (const term of spec.update.terms) {
    const shape = classifyLinearTerm(term)
    if (!shape) {
      return { errors: ['update is nonlinear; the linear recurrence chart abstains'] }
    }
    if (shape.constant) constant = addMod(constant, canonical(term.coefficient, spec.modulus), spec.modulus)
    else if (shape.variable !== undefined) {
      coefficients[shape.variable] = addMod(
        coefficients[shape.variable],
        canonical(term.coefficient, spec.modulus),
        spec.modulus,
      )
    }
  }
  return {
    normalForm: {
      modulus: spec.modulus,
      order: spec.initial.length,
      coefficients,
      constant,
      initial: spec.initial.map(value => canonical(value, spec.modulus)),
      targetIndex: spec.targetIndex,
    },
    errors: [],
  }
}

function transitionMatrix(normalForm: AffineRecurrenceNormalForm): ModularMatrix {
  const size = normalForm.order + 1
  const matrix = zeroMatrix(size)
  for (let row = 0; row < normalForm.order - 1; row += 1) matrix[row][row + 1] = 1
  for (let column = 0; column < normalForm.order; column += 1) {
    matrix[normalForm.order - 1][column] = normalForm.coefficients[column]
  }
  matrix[normalForm.order - 1][normalForm.order] = normalForm.constant
  matrix[normalForm.order][normalForm.order] = 1
  return matrix
}

function characteristicPolynomial(normalForm: AffineRecurrenceNormalForm): number[] {
  return [
    ...normalForm.coefficients.map(value => canonical(-value, normalForm.modulus)),
    1,
  ]
}

export function buildLinearRecurrenceMatrixChart(
  spec: FiniteRecurrenceSpec,
): { chart?: LinearRecurrenceMatrixChart; errors: string[] } {
  const elaborated = elaborateAffineRecurrence(spec)
  if (!elaborated.normalForm) return { errors: elaborated.errors }
  const normalForm = elaborated.normalForm
  const recurrencePolynomial = characteristicPolynomial(normalForm)
  const augmentedPolynomial = multiplyPolynomials(
    recurrencePolynomial,
    [canonical(-1, normalForm.modulus), 1],
    normalForm.modulus,
  )
  const chart: LinearRecurrenceMatrixChart = {
    kind: 'linear-recurrence-matrix-characteristic-polynomial',
    sourceId: spec.id,
    sourceSemanticIds: spec.sourceSemanticIds,
    normalForm,
    stateConvention: '(a_n, a_{n+1}, ..., a_{n+k-1}, 1)^T',
    transitionMatrix: transitionMatrix(normalForm),
    recurrenceCharacteristicPolynomial: recurrencePolynomial,
    augmentedCharacteristicPolynomial: augmentedPolynomial,
    reversibleWith: [
      'the canonical companion basis',
      'the affine homogeneous coordinate',
      'the modulus and initial state',
    ],
    forgotten: [
      'integer coefficients that differ by a multiple of the modulus',
      'nonlinear recurrence structure',
      'a change of basis outside canonical companion form',
    ],
    certificates: [
      {
        claim: 'the recurrence and augmented companion matrix define the same state transition',
        method: 'exact coefficient extraction over Z/mZ',
        status: 'certified',
      },
      {
        claim: 'the augmented characteristic polynomial annihilates the transition matrix',
        method: 'exact modular Cayley-Hamilton replay',
        status: 'certified',
      },
      {
        claim: 'canonical matrix decoding reconstructs the normalized recurrence',
        method: 'forward/inverse chart round trip',
        status: 'certified',
      },
    ],
  }
  const verification = verifyLinearRecurrenceMatrixChart(chart)
  return verification.certified ? { chart, errors: [] } : { errors: verification.errors }
}

export function reconstructFiniteRecurrence(
  chart: LinearRecurrenceMatrixChart,
): FiniteRecurrenceSpec {
  const { normalForm } = chart
  const terms: PolynomialTerm[] = normalForm.coefficients
    .map((coefficient, variable) => ({ coefficient, variable }))
    .filter(item => item.coefficient !== 0)
    .map(item => ({
      coefficient: item.coefficient,
      powers: Array.from({ length: normalForm.order }, (_, index) => index === item.variable ? 1 : 0),
    }))
  if (normalForm.constant !== 0) {
    terms.push({ coefficient: normalForm.constant, powers: Array<number>(normalForm.order).fill(0) })
  }
  if (!terms.length) terms.push({ coefficient: 0, powers: Array<number>(normalForm.order).fill(0) })
  return {
    id: `${chart.sourceId}:reconstructed`,
    sourceSemanticIds: chart.sourceSemanticIds as FiniteRecurrenceSpec['sourceSemanticIds'],
    modulus: normalForm.modulus,
    initial: normalForm.initial,
    update: { terms },
    targetIndex: normalForm.targetIndex,
    source: 'inverse of MORTRA linear recurrence matrix chart',
  }
}

export function verifyLinearRecurrenceMatrixChart(
  chart: LinearRecurrenceMatrixChart,
): { certified: boolean; errors: string[] } {
  const errors: string[] = []
  const { normalForm, transitionMatrix: matrix } = chart
  const expectedSize = normalForm.order + 1
  if (chart.kind !== 'linear-recurrence-matrix-characteristic-polynomial') errors.push('wrong chart kind')
  if (!chart.sourceSemanticIds.length) errors.push('sourceSemanticIds must not be empty')
  if (matrix.length !== expectedSize || matrix.some(row => row.length !== expectedSize)) {
    errors.push('transition matrix has the wrong dimensions')
    return { certified: false, errors }
  }
  if (!matrixEquals(matrix, transitionMatrix(normalForm))) errors.push('matrix is not the canonical affine companion matrix')
  const expectedRecurrencePolynomial = characteristicPolynomial(normalForm)
  if (JSON.stringify(chart.recurrenceCharacteristicPolynomial) !== JSON.stringify(expectedRecurrencePolynomial)) {
    errors.push('recurrence characteristic polynomial is inconsistent')
  }
  const expectedAugmentedPolynomial = multiplyPolynomials(
    expectedRecurrencePolynomial,
    [canonical(-1, normalForm.modulus), 1],
    normalForm.modulus,
  )
  if (JSON.stringify(chart.augmentedCharacteristicPolynomial) !== JSON.stringify(expectedAugmentedPolynomial)) {
    errors.push('augmented characteristic polynomial is inconsistent')
  }
  const annihilator = polynomialAtMatrix(
    chart.augmentedCharacteristicPolynomial,
    matrix,
    normalForm.modulus,
  )
  if (!matrixEquals(annihilator, zeroMatrix(expectedSize))) {
    errors.push('Cayley-Hamilton certificate failed')
  }
  const roundTrip = elaborateAffineRecurrence(reconstructFiniteRecurrence(chart)).normalForm
  if (!roundTrip || JSON.stringify(roundTrip) !== JSON.stringify(normalForm)) {
    errors.push('recurrence round trip failed')
  }
  return { certified: errors.length === 0, errors }
}

export function solveWithLinearRecurrenceMatrix(
  spec: FiniteRecurrenceSpec,
): MatrixRecurrenceSolution {
  const built = buildLinearRecurrenceMatrixChart(spec)
  if (!built.chart) {
    return {
      status: built.errors.some(error => error.includes('nonlinear')) ? 'abstained' : 'invalid',
      errors: built.errors,
      matrixMultiplications: 0,
    }
  }
  const chart = built.chart
  let target: bigint
  try {
    target = BigInt(spec.targetIndex)
  } catch {
    return { status: 'invalid', errors: ['targetIndex must be an integer string'], matrixMultiplications: 0 }
  }
  const powered = matrixPower(chart.transitionMatrix, target, spec.modulus)
  const initial = [...chart.normalForm.initial, 1]
  const state = multiplyMatrixVector(powered.matrix, initial, spec.modulus)
  return {
    status: 'certified',
    answer: state[0],
    errors: [],
    chart,
    matrixMultiplications: powered.multiplications,
  }
}
