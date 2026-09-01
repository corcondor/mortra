import type { ParsedRationalAngle } from './certified-finite-state-trig-fusion'
import type { Q } from './certified-indexed-power-fusion'

export type RationalAngleQuadraticProjection = 'sine_squared' | 'cosine_squared'

export type RationalInterval = {
  lower: Q
  upper: Q
}

export type RationalAngleQuadraticCertificate = {
  schema: 1
  projection: RationalAngleQuadraticProjection
  angle: {
    numerator: bigint
    denominator: bigint
  }
  exactValue: Q | null
  cosineOfDoubleAngle: RationalInterval
  threshold: RationalInterval
  cosineTaylorTerms: number
  machinTerms: {
    arctanOneFifth: number
    arctanOneTwoHundredThirtyNinth: number
  }
}

export type CertifiedQuadraticThresholdComparison = {
  certificate: RationalAngleQuadraticCertificate
  comparisons: Array<{
    value: Q
    relation: 'greater' | 'less_or_equal'
  }>
}

const MACHIN_TERMS = {
  arctanOneFifth: 32,
  arctanOneTwoHundredThirtyNinth: 10,
} as const

function gcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left
  let b = right < 0n ? -right : right
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

export function exactQ(numerator: bigint, denominator = 1n): Q {
  if (denominator === 0n) throw new Error('zero denominator')
  const sign = denominator < 0n ? -1n : 1n
  const divisor = gcd(numerator, denominator)
  return {
    n: sign * numerator / divisor,
    d: sign * denominator / divisor,
  }
}

function add(left: Q, right: Q): Q {
  return exactQ(left.n * right.d + right.n * left.d, left.d * right.d)
}

function subtract(left: Q, right: Q): Q {
  return exactQ(left.n * right.d - right.n * left.d, left.d * right.d)
}

function multiply(left: Q, right: Q): Q {
  return exactQ(left.n * right.n, left.d * right.d)
}

function scale(value: Q, numerator: bigint, denominator = 1n): Q {
  return exactQ(value.n * numerator, value.d * denominator)
}

export function compareExactQ(left: Q, right: Q): number {
  const difference = left.n * right.d - right.n * left.d
  return difference < 0n ? -1 : difference > 0n ? 1 : 0
}

function equal(left: Q, right: Q): boolean {
  return left.n === right.n && left.d === right.d
}

function positiveMod(value: bigint, modulus: bigint): bigint {
  const residue = value % modulus
  return residue < 0n ? residue + modulus : residue
}

/** Exact rational cases for cos(2 phi), with phi a rational multiple of pi. */
export function exactRationalCosineOfDoubleAngle(angle: ParsedRationalAngle): Q | null {
  const denominator = angle.denominator
  const residue = positiveMod(2n * angle.numerator, 2n * denominator)
  if (residue === 0n) return exactQ(1n)
  if (residue === denominator) return exactQ(-1n)
  if (2n * residue === denominator || 2n * residue === 3n * denominator) return exactQ(0n)
  if (3n * residue === denominator || 3n * residue === 5n * denominator) return exactQ(1n, 2n)
  if (3n * residue === 2n * denominator || 3n * residue === 4n * denominator) return exactQ(-1n, 2n)
  return null
}

function arctangentUnitFractionInterval(inverse: bigint, terms: number): RationalInterval {
  if (inverse <= 1n || terms < 1) throw new Error('invalid arctangent interval parameters')
  const inverseSquared = inverse * inverse
  let power = inverse
  let sum = exactQ(0n)
  for (let index = 0; index < terms; index += 1) {
    const term = exactQ(1n, BigInt(2 * index + 1) * power)
    sum = index % 2 === 0 ? add(sum, term) : subtract(sum, term)
    power *= inverseSquared
  }
  const next = exactQ(1n, BigInt(2 * terms + 1) * power)
  return terms % 2 === 0
    ? { lower: sum, upper: add(sum, next) }
    : { lower: subtract(sum, next), upper: sum }
}

function certifiedPiInterval(): RationalInterval {
  const arctanOneFifth = arctangentUnitFractionInterval(
    5n,
    MACHIN_TERMS.arctanOneFifth,
  )
  const arctanOneTwoHundredThirtyNinth = arctangentUnitFractionInterval(
    239n,
    MACHIN_TERMS.arctanOneTwoHundredThirtyNinth,
  )
  // Machin's identity: pi = 16 atan(1/5) - 4 atan(1/239).
  return {
    lower: subtract(
      scale(arctanOneFifth.lower, 16n),
      scale(arctanOneTwoHundredThirtyNinth.upper, 4n),
    ),
    upper: subtract(
      scale(arctanOneFifth.upper, 16n),
      scale(arctanOneTwoHundredThirtyNinth.lower, 4n),
    ),
  }
}

function cosineAtRationalInterval(value: Q, terms: number): RationalInterval {
  if (value.n < 0n || terms < 2) throw new Error('invalid cosine interval parameters')
  const square = multiply(value, value)
  let term = exactQ(1n)
  let sum = term
  for (let index = 1; index <= terms; index += 1) {
    term = scale(
      multiply(term, square),
      1n,
      BigInt(2 * index - 1) * BigInt(2 * index),
    )
    sum = index % 2 === 0 ? add(sum, term) : subtract(sum, term)
  }
  const nextIndex = terms + 1
  const next = scale(
    multiply(term, square),
    1n,
    BigInt(2 * nextIndex - 1) * BigInt(2 * nextIndex),
  )
  return nextIndex % 2 === 0
    ? { lower: sum, upper: add(sum, next) }
    : { lower: subtract(sum, next), upper: sum }
}

function cosineDoubleAngleInterval(
  angle: ParsedRationalAngle,
  cosineTaylorTerms: number,
): RationalInterval {
  const exact = exactRationalCosineOfDoubleAngle(angle)
  if (exact) return { lower: exact, upper: exact }

  const denominator = angle.denominator
  const residue = positiveMod(angle.numerator, denominator)
  const reflected = residue * 2n <= denominator ? residue : denominator - residue
  const pi = certifiedPiInterval()
  const lowerAngle = scale(pi.lower, 2n * reflected, denominator)
  const upperAngle = scale(pi.upper, 2n * reflected, denominator)
  const cosineAtUpperAngle = cosineAtRationalInterval(upperAngle, cosineTaylorTerms)
  const cosineAtLowerAngle = cosineAtRationalInterval(lowerAngle, cosineTaylorTerms)
  return {
    lower: cosineAtUpperAngle.lower,
    upper: cosineAtLowerAngle.upper,
  }
}

function projectCosineInterval(
  cosine: RationalInterval,
  projection: RationalAngleQuadraticProjection,
): RationalInterval {
  const one = exactQ(1n)
  return projection === 'sine_squared'
    ? {
        lower: scale(subtract(one, cosine.upper), 1n, 2n),
        upper: scale(subtract(one, cosine.lower), 1n, 2n),
      }
    : {
        lower: scale(add(one, cosine.lower), 1n, 2n),
        upper: scale(add(one, cosine.upper), 1n, 2n),
      }
}

function certificateAtTerms(
  angle: ParsedRationalAngle,
  projection: RationalAngleQuadraticProjection,
  cosineTaylorTerms: number,
): RationalAngleQuadraticCertificate {
  const exactCosine = exactRationalCosineOfDoubleAngle(angle)
  const cosineOfDoubleAngle = cosineDoubleAngleInterval(angle, cosineTaylorTerms)
  const threshold = projectCosineInterval(cosineOfDoubleAngle, projection)
  return {
    schema: 1,
    projection,
    angle: {
      numerator: angle.numerator,
      denominator: angle.denominator,
    },
    exactValue: exactCosine ? threshold.lower : null,
    cosineOfDoubleAngle,
    threshold,
    cosineTaylorTerms: exactCosine ? 0 : cosineTaylorTerms,
    machinTerms: { ...MACHIN_TERMS },
  }
}

function classify(value: Q, interval: RationalInterval): 'greater' | 'less_or_equal' | null {
  if (compareExactQ(value, interval.upper) > 0) return 'greater'
  if (compareExactQ(value, interval.lower) <= 0) return 'less_or_equal'
  return null
}

export function certifyRationalAngleQuadraticComparisons(
  angle: ParsedRationalAngle,
  projection: RationalAngleQuadraticProjection,
  tailReference: Q,
  values: Q[],
): CertifiedQuadraticThresholdComparison | null {
  const exactCosine = exactRationalCosineOfDoubleAngle(angle)
  const termCounts = exactCosine ? [0] : Array.from({ length: 17 }, (_, index) => 8 + 4 * index)
  for (const cosineTaylorTerms of termCounts) {
    const certificate = certificateAtTerms(angle, projection, cosineTaylorTerms)
    if (compareExactQ(tailReference, certificate.threshold.lower) >= 0) continue
    const comparisons = values.map(value => ({
      value,
      relation: classify(value, certificate.threshold),
    }))
    if (comparisons.some(item => item.relation === null)) continue
    return {
      certificate,
      comparisons: comparisons as CertifiedQuadraticThresholdComparison['comparisons'],
    }
  }
  return null
}

export function selectCertifiedRationalAngleQuadraticComparisons(
  angle: ParsedRationalAngle,
  tailReference: Q,
  values: Q[],
): CertifiedQuadraticThresholdComparison | null {
  return certifyRationalAngleQuadraticComparisons(
    angle,
    'sine_squared',
    tailReference,
    values,
  ) ?? certifyRationalAngleQuadraticComparisons(
    angle,
    'cosine_squared',
    tailReference,
    values,
  )
}

export function verifyRationalAngleQuadraticCertificate(
  certificate: RationalAngleQuadraticCertificate,
): boolean {
  if (certificate.schema !== 1) return false
  if (certificate.machinTerms.arctanOneFifth !== MACHIN_TERMS.arctanOneFifth) return false
  if (
    certificate.machinTerms.arctanOneTwoHundredThirtyNinth
    !== MACHIN_TERMS.arctanOneTwoHundredThirtyNinth
  ) return false
  const angle: ParsedRationalAngle = {
    parentId: 'certificate-replay',
    numerator: certificate.angle.numerator,
    denominator: certificate.angle.denominator,
    evidence: 'certificate replay',
    role: 'angle_condition',
  }
  const replayed = certificateAtTerms(
    angle,
    certificate.projection,
    certificate.cosineTaylorTerms,
  )
  const intervalsMatch = (
    equal(replayed.cosineOfDoubleAngle.lower, certificate.cosineOfDoubleAngle.lower)
    && equal(replayed.cosineOfDoubleAngle.upper, certificate.cosineOfDoubleAngle.upper)
    && equal(replayed.threshold.lower, certificate.threshold.lower)
    && equal(replayed.threshold.upper, certificate.threshold.upper)
  )
  const exactValuesMatch = replayed.exactValue === null
    ? certificate.exactValue === null
    : certificate.exactValue !== null && equal(replayed.exactValue, certificate.exactValue)
  return intervalsMatch && exactValuesMatch
}
