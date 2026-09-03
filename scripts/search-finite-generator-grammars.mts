import { mkdirSync, writeFileSync } from 'node:fs'
import { dirname, resolve } from 'node:path'

import {
  auditCompositionComplexity,
  compositionGenomeFingerprint,
} from '../lib/mortra/composition-genome'
import {
  acceptedBinaryWords,
  buildForbiddenWordAutomaton,
  canonicalForbiddenWords,
} from '../lib/mortra/finite-word-grammar'
import {
  buildForbiddenWordMomentCompositionGenome,
  characteristicPolynomial,
  forbiddenWordMomentTransferMatrix,
} from '../worker/src/runtime-branching-moment-generation'

type Matrix = bigint[][]

type Factor = {
  coefficients: bigint[]
  multiplicity: number
}

type Rational = {
  numerator: bigint
  denominator: bigint
}

function absolute(value: bigint): bigint {
  return value < 0n ? -value : value
}

function gcd(left: bigint, right: bigint): bigint {
  let a = absolute(left)
  let b = absolute(right)
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

function rational(numerator: bigint, denominator = 1n): Rational {
  if (denominator === 0n) throw new Error('zero rational denominator')
  const sign = denominator < 0n ? -1n : 1n
  const divisor = gcd(numerator, denominator)
  return {
    numerator: sign * numerator / divisor,
    denominator: sign * denominator / divisor,
  }
}

function subtractRational(left: Rational, right: Rational): Rational {
  return rational(
    left.numerator * right.denominator - right.numerator * left.denominator,
    left.denominator * right.denominator,
  )
}

function multiplyRational(left: Rational, right: Rational): Rational {
  return rational(left.numerator * right.numerator, left.denominator * right.denominator)
}

function divideRational(left: Rational, right: Rational): Rational {
  return rational(left.numerator * right.denominator, left.denominator * right.numerator)
}

function findMinimalRecurrence(sequence: bigint[], maximumOrder: number): Rational[] {
  for (let order = 1; order <= maximumOrder; order += 1) {
    const rows = sequence.slice(order).map((value, offset) => [
      ...Array.from({ length: order }, (_, index) => rational(sequence[offset + order - index - 1])),
      rational(value),
    ])
    let pivotRow = 0
    const pivotColumns: number[] = []
    for (let column = 0; column < order && pivotRow < rows.length; column += 1) {
      const candidate = rows.findIndex((row, index) =>
        index >= pivotRow && row[column].numerator !== 0n)
      if (candidate < 0) continue
      ;[rows[pivotRow], rows[candidate]] = [rows[candidate], rows[pivotRow]]
      const pivot = rows[pivotRow][column]
      rows[pivotRow] = rows[pivotRow].map(value => divideRational(value, pivot))
      for (let row = 0; row < rows.length; row += 1) {
        if (row === pivotRow || rows[row][column].numerator === 0n) continue
        const factor = rows[row][column]
        rows[row] = rows[row].map((value, index) =>
          subtractRational(value, multiplyRational(factor, rows[pivotRow][index])))
      }
      pivotColumns.push(column)
      pivotRow += 1
    }
    const inconsistent = rows.some(row =>
      row.slice(0, order).every(value => value.numerator === 0n)
      && row[order].numerator !== 0n)
    if (inconsistent || pivotColumns.length !== order) continue
    const solution = Array.from({ length: order }, () => rational(0n))
    for (let row = 0; row < pivotColumns.length; row += 1) {
      solution[pivotColumns[row]] = rows[row][order]
    }
    const verified = sequence.slice(order).every((value, offset) => {
      const prediction = solution.reduce(
        (sum, coefficient, index) => subtractRational(
          sum,
          multiplyRational(coefficient, rational(-sequence[offset + order - index - 1])),
        ),
        rational(0n),
      )
      return prediction.denominator === 1n && prediction.numerator === value
    })
    if (verified) return solution
  }
  throw new Error('no scalar recurrence found within the transfer dimension')
}

function allWords(length: number): string[] {
  let words = ['']
  for (let index = 0; index < length; index += 1) {
    words = words.flatMap(word => [word + 'L', word + 'R'])
  }
  return words
}

function candidateGrammars(): string[][] {
  const shortWords = [...allWords(2), ...allWords(3)]
  const raw: string[][] = [
    ...[2, 3, 4].flatMap(length => allWords(length).map(word => [word])),
  ]
  for (let left = 0; left < shortWords.length; left += 1) {
    for (let right = left + 1; right < shortWords.length; right += 1) {
      raw.push([shortWords[left], shortWords[right]])
    }
  }
  const unique = new Map<string, string[]>()
  for (const candidate of raw) {
    const canonical = canonicalForbiddenWords(candidate)
    unique.set(canonical.join(','), canonical)
  }
  return [...unique.values()]
}

function multiplyMatrixVector(matrix: Matrix, vector: bigint[]): bigint[] {
  return matrix.map(row => row.reduce(
    (sum, coefficient, index) => sum + coefficient * vector[index],
    0n,
  ))
}

function endpointMomentSequence(
  matrix: Matrix,
  stateCount: number,
  degree: number,
  length: number,
): bigint[] {
  const rank = degree + 1
  let vector = Array<bigint>(rank * stateCount).fill(0n)
  for (let moment = 0; moment < rank; moment += 1) vector[moment] = 1n
  const sequence: bigint[] = []
  for (let index = 0; index < length; index += 1) {
    sequence.push(Array.from({ length: stateCount }, (_, state) =>
      vector[state * rank] + vector[state * rank + degree])
      .reduce((sum, value) => sum + value, 0n))
    vector = multiplyMatrixVector(matrix, vector)
  }
  return sequence
}

function dividePolynomial(dividend: bigint[], divisor: bigint[]): bigint[] | undefined {
  const quotient = Array<bigint>(dividend.length - divisor.length + 1).fill(0n)
  const remainder = [...dividend]
  for (let index = 0; index < quotient.length; index += 1) {
    if (remainder[index] % divisor[0] !== 0n) return undefined
    const coefficient = remainder[index] / divisor[0]
    quotient[index] = coefficient
    for (let offset = 0; offset < divisor.length; offset += 1) {
      remainder[index + offset] -= coefficient * divisor[offset]
    }
  }
  return remainder.slice(quotient.length).every(value => value === 0n)
    ? quotient
    : undefined
}

function factorPolynomial(coefficients: bigint[]): Factor[] {
  let remainder = [...coefficients]
  const factors: Factor[] = []
  const append = (factor: bigint[]) => {
    const key = factor.join(',')
    const existing = factors.find(item => item.coefficients.join(',') === key)
    if (existing) existing.multiplicity += 1
    else factors.push({ coefficients: factor, multiplicity: 1 })
  }
  let changed = true
  while (changed && remainder.length > 1) {
    changed = false
    for (let root = -16; root <= 16; root += 1) {
      const quotient = dividePolynomial(remainder, [1n, -BigInt(root)])
      if (!quotient) continue
      append([1n, -BigInt(root)])
      remainder = quotient
      changed = true
      break
    }
  }
  changed = true
  while (changed && remainder.length > 2) {
    changed = false
    outer: for (let linear = -16; linear <= 16; linear += 1) {
      for (let constant = -16; constant <= 16; constant += 1) {
        const factor = [1n, BigInt(linear), BigInt(constant)]
        const quotient = dividePolynomial(remainder, factor)
        if (!quotient) continue
        append(factor)
        remainder = quotient
        changed = true
        break outer
      }
    }
  }
  if (remainder.length > 1) append(remainder)
  return factors
}

function verifyCharacteristicRecurrence(sequence: bigint[], polynomial: bigint[]): boolean {
  const degree = polynomial.length - 1
  for (let start = 0; start + degree < sequence.length; start += 1) {
    const residual = polynomial.reduce(
      (sum, coefficient, index) => sum + coefficient * sequence[start + degree - index],
      0n,
    )
    if (residual !== 0n) return false
  }
  return true
}

function approximateRatio(sequence: bigint[]): number {
  const last = sequence.at(-1) ?? 0n
  const previous = sequence.at(-2) ?? 1n
  const scale = 1_000_000_000n
  return Number(last * scale / previous) / Number(scale)
}

function polynomialText(coefficients: bigint[]): string {
  const degree = coefficients.length - 1
  const terms: string[] = []
  for (const [index, coefficient] of coefficients.entries()) {
    if (coefficient === 0n) continue
    const power = degree - index
    const sign = coefficient < 0n ? '-' : '+'
    const absolute = coefficient < 0n ? -coefficient : coefficient
    const body = power === 0
      ? String(absolute)
      : (absolute === 1n ? '' : String(absolute)) + (power === 1 ? 't' : 't^' + power)
    terms.push((terms.length === 0 && sign === '+' ? '' : sign) + body)
  }
  return terms.join('') || '0'
}

function main(): void {
  const outputArgument = process.argv.find(argument => argument.startsWith('--out='))
  const outputPath = resolve(
    outputArgument?.slice('--out='.length)
      ?? 'artifacts/benchmarks/finite-generator-grammar-search-20260904.json',
  )
  const candidates = []
  for (const forbiddenWords of candidateGrammars()) {
    const legalAtDepth = acceptedBinaryWords(forbiddenWords, 10)
    if (legalAtDepth.length === 0) continue
    const automaton = buildForbiddenWordAutomaton(forbiddenWords)
    for (let degree = 1; degree <= 4; degree += 1) {
      const matrix = forbiddenWordMomentTransferMatrix(forbiddenWords, degree)
      const polynomial = characteristicPolynomial(matrix)
      const sequence = endpointMomentSequence(matrix, automaton.states.length, degree, 80)
      const recurrence = findMinimalRecurrence(sequence, matrix.length)
      const recurrenceIsIntegral = recurrence.every(coefficient => coefficient.denominator === 1n)
      const minimalPolynomial = recurrenceIsIntegral
        ? [1n, ...recurrence.map(coefficient => -coefficient.numerator)]
        : undefined
      const genome = buildForbiddenWordMomentCompositionGenome(forbiddenWords, degree, 10)
      const audit = auditCompositionComplexity(genome)
      const factors = factorPolynomial(polynomial)
      const minimalFactors = minimalPolynomial ? factorPolynomial(minimalPolynomial) : []
      const maximumMinimalFactorDegree = minimalFactors.length
        ? Math.max(...minimalFactors.map(factor => factor.coefficients.length - 1))
        : null
      const hasOnlyLinearOrQuadraticFactors = minimalFactors.length > 0
        && minimalFactors.every(factor => factor.coefficients.length <= 3)
      const exactResidualWindow = minimalPolynomial
        ? sequence.slice(0, matrix.length + minimalPolynomial.length - 1)
        : []
      const cayleyHamiltonCertificatePassed = minimalPolynomial
        ? verifyCharacteristicRecurrence(exactResidualWindow, minimalPolynomial)
        : false
      candidates.push({
        forbiddenWords,
        momentDegree: degree,
        statementSymbolCount: forbiddenWords.reduce((sum, word) => sum + word.length, 0),
        automatonStateCount: automaton.states.length,
        legalWordCountAtDepth10: legalAtDepth.length,
        characteristicPolynomial: polynomialText(polynomial),
        characteristicPolynomialCoefficients: polynomial.map(String),
        factors: factors.map(factor => ({
          polynomial: polynomialText(factor.coefficients),
          coefficients: factor.coefficients.map(String),
          multiplicity: factor.multiplicity,
        })),
        recurrenceVerified: verifyCharacteristicRecurrence(sequence, polynomial),
        minimalRecurrenceOrder: recurrence.length,
        minimalRecurrenceCoefficients: recurrence.map(coefficient => ({
          numerator: String(coefficient.numerator),
          denominator: String(coefficient.denominator),
        })),
        minimalPolynomial: minimalPolynomial ? polynomialText(minimalPolynomial) : null,
        minimalFactors: minimalFactors.map(factor => ({
          polynomial: polynomialText(factor.coefficients),
          coefficients: factor.coefficients.map(String),
          multiplicity: factor.multiplicity,
        })),
        minimalRecurrenceVerified: minimalPolynomial
          ? verifyCharacteristicRecurrence(sequence, minimalPolynomial)
          : true,
        hasOnlyLinearOrQuadraticMinimalFactors: hasOnlyLinearOrQuadraticFactors,
        maximumMinimalFactorDegree,
        cayleyHamiltonScalarRecurrenceCertificate: {
          passed: cayleyHamiltonCertificatePassed,
          exactResidualWindowLength: matrix.length,
          transferDimension: matrix.length,
          reason: 'The exact residual is zero for one full transfer dimension; Cayley-Hamilton propagates it to every later index.',
        },
        firstTerms: sequence.slice(0, 12).map(String),
        ratioAfter79Steps: approximateRatio(sequence),
        compositionFingerprint: compositionGenomeFingerprint(genome),
        deepStructuralTargetPassed: audit.passed,
        structuralMetrics: audit.metrics,
        structuralCompressionRatio:
          audit.metrics.structuralQuotientNodeCount / recurrence.length,
        structuralFailures: audit.failures,
      })
    }
  }
  const canonicalGrammars = new Set(candidates.map(candidate => candidate.forbiddenWords.join(',')))
  const structurallyDistinct = new Set(candidates.map(candidate => candidate.compositionFingerprint))
  const deep = candidates.filter(candidate => candidate.deepStructuralTargetPassed)
  const deepWithShortExactOutput = deep.filter(candidate =>
    candidate.hasOnlyLinearOrQuadraticMinimalFactors
    && candidate.minimalRecurrenceOrder <= 8)
  const deepWithAtMostCubicOutput = deep.filter(candidate =>
    candidate.maximumMinimalFactorDegree !== null
    && candidate.maximumMinimalFactorDegree <= 3
    && candidate.minimalRecurrenceOrder <= 8)
  const report = {
    schema: 'mortra.finite-generator-grammar-search.v1',
    generatedAt: new Date().toISOString(),
    generatorAlphabet: ['L', 'R'],
    mapDefinitions: ['L(a,b)=(a+b,b)', 'R(a,b)=(a,a+b)'],
    searchSpace: {
      singleForbiddenWords: 'all binary words of length 2, 3, or 4',
      pairedForbiddenWords: 'all unordered pairs of binary words of length 2 or 3',
      momentDegrees: [1, 2, 3, 4],
      equivalencesRemoved: ['L/R renaming', 'duplicate words', 'words made redundant by a shorter forbidden substring'],
      numericParameterMutation: false,
    },
    summary: {
      canonicalGrammarCount: canonicalGrammars.size,
      grammarMomentCaseCount: candidates.length,
      structurallyDistinctCompositionCount: structurallyDistinct.size,
      deepStructuralTargetPassedCount: deep.length,
      deepWithShortExactOutputCount: deepWithShortExactOutput.length,
      deepWithAtMostCubicOutputCount: deepWithAtMostCubicOutput.length,
      allCharacteristicRecurrencesVerified: candidates.every(candidate => candidate.recurrenceVerified),
      allMinimalRecurrencesVerified: candidates.every(candidate => candidate.minimalRecurrenceVerified),
      allCayleyHamiltonCertificatesPassed: candidates.every(candidate =>
        candidate.cayleyHamiltonScalarRecurrenceCertificate.passed),
    },
    candidates,
  }
  mkdirSync(dirname(outputPath), { recursive: true })
  writeFileSync(outputPath, JSON.stringify(report, null, 2) + '\n')
  console.log(JSON.stringify({
    outputPath,
    ...report.summary,
    deepest: [...candidates]
      .sort((left, right) =>
        right.structuralMetrics.structuralQuotientNodeCount
        - left.structuralMetrics.structuralQuotientNodeCount)
      .slice(0, 5)
      .map(candidate => ({
        forbiddenWords: candidate.forbiddenWords,
        momentDegree: candidate.momentDegree,
        quotientNodes: candidate.structuralMetrics.structuralQuotientNodeCount,
        localContexts: candidate.structuralMetrics.distinctCompositionContextCount,
        characteristicPolynomial: candidate.characteristicPolynomial,
      })),
  }, null, 2))
}

main()
