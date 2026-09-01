import type { MathExpression } from './math-expression-ir'

type Rational = { numerator: bigint; denominator: bigint }
type Polynomial = Rational[]
type Complex = { re: number; im: number }

export type ExactRootComposition = {
  left: string
  right: string
  result: string
  left_sympy: string
  right_sympy: string
  result_sympy: string
  degree_left: number
  degree_right: number
  degree_result: number
  operation: 'sum' | 'difference' | 'product'
  exact: true
  numeric_check: true
  ablation: true
}

export type ExactRootInvariant = {
  polynomial: string
  polynomial_sympy: string
  degree: number
  invariant: 'trace' | 'norm'
  value: string
  value_sympy: string
  coefficient_formula: string
  numeric_check: true
  exact: true
  ablation_polynomial_sympy: string
}

const ZERO: Rational = { numerator: 0n, denominator: 1n }
const ONE: Rational = { numerator: 1n, denominator: 1n }

function absBigInt(value: bigint): bigint {
  return value < 0n ? -value : value
}

function gcdBigInt(left: bigint, right: bigint): bigint {
  let a = absBigInt(left)
  let b = absBigInt(right)
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

function rational(numerator: bigint, denominator = 1n): Rational {
  if (denominator === 0n) throw new Error('zero rational denominator')
  if (numerator === 0n) return ZERO
  const sign = denominator < 0n ? -1n : 1n
  const divisor = gcdBigInt(numerator, denominator)
  return {
    numerator: sign * numerator / divisor,
    denominator: absBigInt(denominator) / divisor,
  }
}

function rationalFromString(source: string): Rational | null {
  const value = source.trim()
  const fraction = value.match(/^([+-]?\d+)\/([+-]?\d+)$/)
  if (fraction) return rational(BigInt(fraction[1]), BigInt(fraction[2]))
  if (/^[+-]?\d+$/.test(value)) return rational(BigInt(value))
  const decimal = value.match(/^([+-]?)(\d*)\.(\d+)(?:e([+-]?\d+))?$/i)
  if (!decimal) return null
  const sign = decimal[1] === '-' ? -1n : 1n
  const digits = `${decimal[2] || '0'}${decimal[3]}`
  const exponent = Number(decimal[4] ?? 0) - decimal[3].length
  return exponent >= 0
    ? rational(sign * BigInt(digits) * (10n ** BigInt(exponent)))
    : rational(sign * BigInt(digits), 10n ** BigInt(-exponent))
}

function rationalFromNumber(value: number): Rational | null {
  if (!Number.isFinite(value)) return null
  return rationalFromString(String(value))
}

function isZero(value: Rational): boolean {
  return value.numerator === 0n
}

function equal(left: Rational, right: Rational): boolean {
  return left.numerator === right.numerator && left.denominator === right.denominator
}

function add(left: Rational, right: Rational): Rational {
  return rational(
    left.numerator * right.denominator + right.numerator * left.denominator,
    left.denominator * right.denominator,
  )
}

function negate(value: Rational): Rational {
  return rational(-value.numerator, value.denominator)
}

function subtract(left: Rational, right: Rational): Rational {
  return add(left, negate(right))
}

function multiply(left: Rational, right: Rational): Rational {
  return rational(left.numerator * right.numerator, left.denominator * right.denominator)
}

function divide(left: Rational, right: Rational): Rational {
  if (isZero(right)) throw new Error('division by zero')
  return rational(left.numerator * right.denominator, left.denominator * right.numerator)
}

function trim(polynomial: Polynomial): Polynomial {
  const result = polynomial.length ? polynomial.slice() : [ZERO]
  while (result.length > 1 && isZero(result[result.length - 1])) result.pop()
  return result
}

function degree(polynomial: Polynomial): number {
  return trim(polynomial).length - 1
}

function polynomialEqual(left: Polynomial, right: Polynomial): boolean {
  const a = trim(left)
  const b = trim(right)
  return a.length === b.length && a.every((value, index) => equal(value, b[index]))
}

function polynomialAdd(left: Polynomial, right: Polynomial): Polynomial {
  const length = Math.max(left.length, right.length)
  return trim(Array.from({ length }, (_, index) => add(left[index] ?? ZERO, right[index] ?? ZERO)))
}

function polynomialNegate(polynomial: Polynomial): Polynomial {
  return trim(polynomial.map(negate))
}

function polynomialSubtract(left: Polynomial, right: Polynomial): Polynomial {
  return polynomialAdd(left, polynomialNegate(right))
}

function polynomialScale(polynomial: Polynomial, scalar: Rational): Polynomial {
  return trim(polynomial.map(value => multiply(value, scalar)))
}

function polynomialMultiply(left: Polynomial, right: Polynomial): Polynomial {
  const result = Array.from({ length: left.length + right.length - 1 }, () => ZERO)
  for (let i = 0; i < left.length; i++) {
    for (let j = 0; j < right.length; j++) {
      result[i + j] = add(result[i + j], multiply(left[i], right[j]))
    }
  }
  return trim(result)
}

function polynomialPower(base: Polynomial, exponent: number): Polynomial {
  let result: Polynomial = [ONE]
  let factor = trim(base)
  let power = exponent
  while (power > 0) {
    if (power % 2 === 1) result = polynomialMultiply(result, factor)
    power = Math.floor(power / 2)
    if (power) factor = polynomialMultiply(factor, factor)
  }
  return result
}

function polynomialMonic(polynomial: Polynomial): Polynomial {
  const value = trim(polynomial)
  if (value.length === 1 && isZero(value[0])) return value
  return polynomialScale(value, divide(ONE, value[value.length - 1]))
}

function polynomialDerivative(polynomial: Polynomial): Polynomial {
  if (polynomial.length <= 1) return [ZERO]
  return trim(polynomial.slice(1).map((value, index) => multiply(value, rational(BigInt(index + 1)))))
}

function polynomialDivmod(dividend: Polynomial, divisor: Polynomial): [Polynomial, Polynomial] {
  const denominator = trim(divisor)
  if (denominator.length === 1 && isZero(denominator[0])) throw new Error('polynomial division by zero')
  let remainder = trim(dividend)
  const quotient = Array.from({ length: Math.max(1, degree(remainder) - degree(denominator) + 1) }, () => ZERO)
  while (!(remainder.length === 1 && isZero(remainder[0])) && degree(remainder) >= degree(denominator)) {
    const shift = degree(remainder) - degree(denominator)
    const coefficient = divide(remainder[remainder.length - 1], denominator[denominator.length - 1])
    quotient[shift] = add(quotient[shift], coefficient)
    const term = Array.from({ length: shift }, () => ZERO).concat(polynomialScale(denominator, coefficient))
    remainder = polynomialSubtract(remainder, term)
  }
  return [trim(quotient), trim(remainder)]
}

function polynomialGcd(left: Polynomial, right: Polynomial): Polynomial {
  let a = trim(left)
  let b = trim(right)
  while (!(b.length === 1 && isZero(b[0]))) {
    const [, remainder] = polynomialDivmod(a, b)
    a = b
    b = remainder
  }
  return polynomialMonic(a)
}

function polynomialSquarefreeMonic(polynomial: Polynomial): Polynomial {
  const monic = polynomialMonic(polynomial)
  const derivative = polynomialDerivative(monic)
  if (derivative.length === 1 && isZero(derivative[0])) return monic
  const divisor = polynomialGcd(monic, derivative)
  const [quotient, remainder] = polynomialDivmod(monic, divisor)
  if (!(remainder.length === 1 && isZero(remainder[0]))) throw new Error('non-exact squarefree division')
  return polynomialMonic(quotient)
}

function binomial(n: number, k: number): bigint {
  const index = Math.min(k, n - k)
  let value = 1n
  for (let i = 1; i <= index; i++) value = value * BigInt(n - index + i) / BigInt(i)
  return value
}

function addBivariateTerm(
  coefficients: Polynomial[],
  xDegree: number,
  zDegree: number,
  coefficient: Rational,
): void {
  while (coefficients.length <= xDegree) coefficients.push([ZERO])
  const term = Array.from({ length: zDegree + 1 }, (_, index) => index === zDegree ? coefficient : ZERO)
  coefficients[xDegree] = polynomialAdd(coefficients[xDegree], term)
}

function transformedRight(right: Polynomial, operation: 'sum' | 'difference' | 'product'): Polynomial[] {
  const coefficients: Polynomial[] = []
  const rightDegree = degree(right)
  for (let power = 0; power <= rightDegree; power++) {
    const baseCoefficient = right[power] ?? ZERO
    if (isZero(baseCoefficient)) continue
    if (operation === 'product') {
      addBivariateTerm(coefficients, rightDegree - power, power, baseCoefficient)
      continue
    }
    for (let xDegree = 0; xDegree <= power; xDegree++) {
      const zDegree = power - xDegree
      const parity = operation === 'sum' ? xDegree : zDegree
      const signed = parity % 2 ? negate(baseCoefficient) : baseCoefficient
      addBivariateTerm(
        coefficients,
        xDegree,
        zDegree,
        multiply(signed, rational(binomial(power, xDegree))),
      )
    }
  }
  while (coefficients.length > 1) {
    const leading = trim(coefficients[coefficients.length - 1])
    if (!(leading.length === 1 && isZero(leading[0]))) break
    coefficients.pop()
  }
  return coefficients.length ? coefficients : [[ZERO]]
}

function determinant(matrix: Polynomial[][]): Polynomial {
  const size = matrix.length
  if (!size || matrix.some(row => row.length !== size)) throw new Error('resultant matrix must be square')
  let states = new Map<number, Polynomial>([[0, [ONE]]])
  for (let row = 0; row < size; row++) {
    const next = new Map<number, Polynomial>()
    for (const [mask, accumulated] of states) {
      for (let column = 0; column < size; column++) {
        if (mask & (1 << column)) continue
        let inversions = 0
        for (let used = column + 1; used < size; used++) if (mask & (1 << used)) inversions++
        const product = polynomialMultiply(accumulated, matrix[row][column])
        const signed = inversions % 2 ? polynomialNegate(product) : product
        const nextMask = mask | (1 << column)
        next.set(nextMask, polynomialAdd(next.get(nextMask) ?? [ZERO], signed))
      }
    }
    states = next
  }
  return trim(states.get((1 << size) - 1) ?? [ZERO])
}

function rootComposition(
  leftInput: Polynomial,
  rightInput: Polynomial,
  operation: 'sum' | 'difference' | 'product',
): Polynomial {
  const left = trim(leftInput)
  const transformed = transformedRight(trim(rightInput), operation)
  const leftDegree = degree(left)
  const rightDegree = transformed.length - 1
  const size = leftDegree + rightDegree
  if (size > 20) throw new Error('exact resultant matrix exceeds the bounded runtime kernel')
  const leftDescending = left.slice().reverse().map(value => [value] as Polynomial)
  const rightDescending = transformed.slice().reverse()
  const matrix: Polynomial[][] = []
  for (let row = 0; row < rightDegree; row++) {
    const values = Array.from({ length: size }, () => [ZERO] as Polynomial)
    for (let index = 0; index < leftDescending.length; index++) values[row + index] = leftDescending[index]
    matrix.push(values)
  }
  for (let row = 0; row < leftDegree; row++) {
    const values = Array.from({ length: size }, () => [ZERO] as Polynomial)
    for (let index = 0; index < rightDescending.length; index++) values[row + index] = rightDescending[index]
    matrix.push(values)
  }
  return polynomialSquarefreeMonic(determinant(matrix))
}

function complexSubtract(left: Complex, right: Complex): Complex {
  return { re: left.re - right.re, im: left.im - right.im }
}

function complexMultiply(left: Complex, right: Complex): Complex {
  return { re: left.re * right.re - left.im * right.im, im: left.re * right.im + left.im * right.re }
}

function complexDivide(left: Complex, right: Complex): Complex {
  const denominator = right.re * right.re + right.im * right.im
  return {
    re: (left.re * right.re + left.im * right.im) / denominator,
    im: (left.im * right.re - left.re * right.im) / denominator,
  }
}

function complexAbs(value: Complex): number {
  return Math.hypot(value.re, value.im)
}

function evaluateComplex(polynomial: number[], value: Complex): Complex {
  let result: Complex = { re: 0, im: 0 }
  for (let index = polynomial.length - 1; index >= 0; index--) {
    result = complexMultiply(result, value)
    result.re += polynomial[index]
  }
  return result
}

function approximateRoots(polynomialInput: Polynomial): Complex[] | null {
  const polynomial = polynomialSquarefreeMonic(polynomialInput)
  const count = degree(polynomial)
  if (count < 1) return []
  const coefficients = polynomial.map(value => Number(value.numerator) / Number(value.denominator))
  if (coefficients.some(value => !Number.isFinite(value))) return null
  if (count === 1) return [{ re: -coefficients[0], im: 0 }]
  const radius = 1 + Math.max(...coefficients.slice(0, -1).map(Math.abs))
  let roots = Array.from({ length: count }, (_, index) => {
    const angle = 2 * Math.PI * (index + 0.37) / count
    return { re: radius * Math.cos(angle), im: radius * Math.sin(angle) }
  })
  for (let iteration = 0; iteration < 600; iteration++) {
    let maximumDelta = 0
    const next = roots.map((root, index) => {
      let denominator: Complex = { re: 1, im: 0 }
      for (let other = 0; other < roots.length; other++) {
        if (other !== index) denominator = complexMultiply(denominator, complexSubtract(root, roots[other]))
      }
      if (complexAbs(denominator) < 1e-24) denominator = { re: denominator.re + 1e-12, im: denominator.im + 1e-12 }
      const delta = complexDivide(evaluateComplex(coefficients, root), denominator)
      maximumDelta = Math.max(maximumDelta, complexAbs(delta))
      return complexSubtract(root, delta)
    })
    roots = next
    if (maximumDelta < 1e-12) break
  }
  const residual = Math.max(...roots.map(root => complexAbs(evaluateComplex(coefficients, root))))
  return Number.isFinite(residual) && residual < 1e-6 ? roots : null
}

function numericRootCheck(
  left: Polynomial,
  right: Polynomial,
  result: Polynomial,
  operation: 'sum' | 'difference' | 'product',
): boolean {
  const leftRoots = approximateRoots(left)
  const rightRoots = approximateRoots(right)
  const resultRoots = approximateRoots(result)
  if (!leftRoots || !rightRoots || !resultRoots) return false
  const expected = leftRoots.flatMap(leftRoot => rightRoots.map(rightRoot => {
    if (operation === 'sum') return { re: leftRoot.re + rightRoot.re, im: leftRoot.im + rightRoot.im }
    if (operation === 'difference') return { re: leftRoot.re - rightRoot.re, im: leftRoot.im - rightRoot.im }
    return complexMultiply(leftRoot, rightRoot)
  }))
  const close = (leftValue: Complex, rightValue: Complex) => {
    const scale = Math.max(1, complexAbs(leftValue), complexAbs(rightValue))
    return complexAbs(complexSubtract(leftValue, rightValue)) <= 2e-5 * scale
  }
  return expected.every(value => resultRoots.some(root => close(value, root))) &&
    resultRoots.every(root => expected.some(value => close(root, value)))
}

function rationalToString(value: Rational): string {
  return value.denominator === 1n
    ? String(value.numerator)
    : `${value.numerator}/${value.denominator}`
}

function polynomialToText(polynomialInput: Polynomial, variable: string, latex: boolean): string {
  const polynomial = trim(polynomialInput)
  const terms: Array<{ negative: boolean; body: string }> = []
  for (let power = polynomial.length - 1; power >= 0; power--) {
    const coefficient = polynomial[power]
    if (isZero(coefficient)) continue
    const negative = coefficient.numerator < 0n
    const absolute = rational(absBigInt(coefficient.numerator), coefficient.denominator)
    const coefficientText = latex && absolute.denominator !== 1n
      ? `\\frac{${absolute.numerator}}{${absolute.denominator}}`
      : rationalToString(absolute)
    const variableText = power === 0
      ? ''
      : power === 1
        ? variable
        : latex
          ? `${variable}^{${power}}`
          : `${variable}**${power}`
    const omitUnit = power > 0 && equal(absolute, ONE)
    const body = `${omitUnit ? '' : coefficientText}${omitUnit || !variableText ? '' : latex ? ' ' : '*'}${variableText}`
    terms.push({ negative, body })
  }
  if (!terms.length) return '0'
  return terms.map((term, index) => {
    if (index === 0) return `${term.negative ? '-' : ''}${term.body}`
    return `${term.negative ? ' - ' : ' + '}${term.body}`
  }).join('')
}

function parseCoefficientStrings(values: string[]): Polynomial | null {
  const parsed = values.map(rationalFromString)
  return parsed.some(value => value === null) ? null : trim(parsed as Polynomial)
}

function rationalToLatex(value: Rational): string {
  if (value.denominator === 1n) return String(value.numerator)
  return value.numerator < 0n
    ? `-\\frac{${absBigInt(value.numerator)}}{${value.denominator}}`
    : `\\frac{${value.numerator}}{${value.denominator}}`
}

export function polynomialCoefficientsFromMathExpression(
  expression: MathExpression,
  variable: string,
): string[] | null {
  const convert = (value: MathExpression): Polynomial | null => {
    if (typeof value === 'number') {
      const coefficient = rationalFromNumber(value)
      return coefficient ? [coefficient] : null
    }
    if (typeof value === 'string') return value === variable ? [ZERO, ONE] : null
    const [operator, ...args] = value
    if (operator === 'Negate') {
      const child = convert(args[0] as MathExpression)
      return child ? polynomialNegate(child) : null
    }
    if (operator === 'Add' || operator === 'Multiply') {
      let result: Polynomial = operator === 'Add' ? [ZERO] : [ONE]
      for (const argument of args) {
        const child = convert(argument as MathExpression)
        if (!child) return null
        result = operator === 'Add' ? polynomialAdd(result, child) : polynomialMultiply(result, child)
      }
      return result
    }
    if (operator === 'Subtract') {
      const left = convert(args[0] as MathExpression)
      const right = convert(args[1] as MathExpression)
      return left && right ? polynomialSubtract(left, right) : null
    }
    if (operator === 'Divide') {
      const numerator = convert(args[0] as MathExpression)
      const denominator = convert(args[1] as MathExpression)
      if (!numerator || !denominator || degree(denominator) !== 0 || isZero(denominator[0])) return null
      return polynomialScale(numerator, divide(ONE, denominator[0]))
    }
    if (operator === 'Power') {
      const base = convert(args[0] as MathExpression)
      const exponent = args[1]
      return base && typeof exponent === 'number' && Number.isInteger(exponent) && exponent >= 0
        ? polynomialPower(base, exponent)
        : null
    }
    return null
  }
  const polynomial = convert(expression)
  return polynomial ? trim(polynomial).map(rationalToString) : null
}

export function executeExactRootComposition(
  leftCoefficients: string[],
  rightCoefficients: string[],
  operation: 'sum' | 'difference' | 'product',
): ExactRootComposition | null {
  try {
    const leftRaw = parseCoefficientStrings(leftCoefficients)
    const rightRaw = parseCoefficientStrings(rightCoefficients)
    if (!leftRaw || !rightRaw || degree(leftRaw) < 1 || degree(rightRaw) < 1) return null
    const left = polynomialMonic(leftRaw)
    const right = polynomialMonic(rightRaw)
    const result = rootComposition(left, right, operation)
    if (!numericRootCheck(left, right, result, operation)) return null

    const leftPerturbed = leftRaw.slice()
    leftPerturbed[0] = add(leftPerturbed[0] ?? ZERO, ONE)
    const rightPerturbed = rightRaw.slice()
    rightPerturbed[0] = add(rightPerturbed[0] ?? ZERO, ONE)
    const ablation = !polynomialEqual(rootComposition(leftPerturbed, rightRaw, operation), result) &&
      !polynomialEqual(rootComposition(leftRaw, rightPerturbed, operation), result)
    if (!ablation) return null

    return {
      left: polynomialToText(left, 'x', true),
      right: polynomialToText(right, 'x', true),
      result: polynomialToText(result, 'z', true),
      left_sympy: polynomialToText(left, 'x', false),
      right_sympy: polynomialToText(right, 'x', false),
      result_sympy: polynomialToText(result, 'z', false),
      degree_left: degree(left),
      degree_right: degree(right),
      degree_result: degree(result),
      operation,
      exact: true,
      numeric_check: true,
      ablation: true,
    }
  } catch {
    return null
  }
}

export function executeExactRootInvariant(
  coefficients: string[],
  invariant: 'trace' | 'norm',
): ExactRootInvariant | null {
  try {
    const raw = parseCoefficientStrings(coefficients)
    if (!raw || degree(raw) < 1) return null
    const polynomial = polynomialMonic(raw)
    const polynomialDegree = degree(polynomial)
    const value = invariant === 'trace'
      ? negate(polynomial[polynomialDegree - 1] ?? ZERO)
      : polynomialDegree % 2
        ? negate(polynomial[0])
        : polynomial[0]
    const roots = approximateRoots(polynomial)
    if (!roots) return null
    const observed = invariant === 'trace'
      ? roots.reduce((sum, root) => ({ re: sum.re + root.re, im: sum.im + root.im }), { re: 0, im: 0 })
      : roots.reduce(complexMultiply, { re: 1, im: 0 })
    const expected = Number(value.numerator) / Number(value.denominator)
    const tolerance = 2e-6 * Math.max(1, Math.abs(expected))
    if (Math.hypot(observed.re - expected, observed.im) > tolerance) return null

    const perturbation = polynomial.slice()
    const perturbationDegree = invariant === 'trace' ? polynomialDegree - 1 : 0
    perturbation[perturbationDegree] = add(perturbation[perturbationDegree] ?? ZERO, ONE)
    return {
      polynomial: polynomialToText(polynomial, 'x', true),
      polynomial_sympy: polynomialToText(polynomial, 'x', false),
      degree: polynomialDegree,
      invariant,
      value: rationalToLatex(value),
      value_sympy: rationalToString(value),
      coefficient_formula: invariant === 'trace' ? '-a_(n-1)/a_n' : '(-1)^n*a_0/a_n',
      numeric_check: true,
      exact: true,
      ablation_polynomial_sympy: polynomialToText(perturbation, 'x', false),
    }
  } catch {
    return null
  }
}
