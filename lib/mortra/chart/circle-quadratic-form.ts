export type RationalInput = string | number | bigint
type Q = { n: bigint; d: bigint }

export type CircleQuadraticSpec = {
  id: string
  sourceSemanticIds: string[]
  quadraticCoefficient: RationalInput
  linearX: RationalInput
  linearY: RationalInput
  constant: RationalInput
}

export type CircleQuadraticFormChart = {
  kind: 'affine-quadratic-form-circle'
  sourceId: string
  sourceSemanticIds: string[]
  normalizedEquation: { linearX: string; linearY: string; constant: string }
  center: { x: string; y: string }
  radiusSquared: string
  homogeneousQuadraticMatrix: string[][]
  certificates: Array<{ claim: string; method: string; status: 'certified' }>
  forgotten: string[]
}

const ZERO: Q = { n: 0n, d: 1n }
const ONE: Q = { n: 1n, d: 1n }

function gcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left
  let b = right < 0n ? -right : right
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

function q(n: bigint, d = 1n): Q {
  if (d === 0n) throw new Error('zero rational denominator')
  if (d < 0n) return q(-n, -d)
  const divisor = gcd(n, d)
  return { n: n / divisor, d: d / divisor }
}

function parse(value: RationalInput): Q | null {
  if (typeof value === 'bigint') return q(value)
  const source = String(value).trim()
  const match = source.match(/^([+-]?\d+)(?:\/([+-]?\d+))?$/)
  if (!match) return null
  return q(BigInt(match[1]), BigInt(match[2] ?? '1'))
}

function add(left: Q, right: Q): Q { return q(left.n * right.d + right.n * left.d, left.d * right.d) }
function subtract(left: Q, right: Q): Q { return add(left, { n: -right.n, d: right.d }) }
function multiply(left: Q, right: Q): Q { return q(left.n * right.n, left.d * right.d) }
function divide(left: Q, right: Q): Q { return q(left.n * right.d, left.d * right.n) }
function negate(value: Q): Q { return { n: -value.n, d: value.d } }
function equal(left: Q, right: Q): boolean { return left.n === right.n && left.d === right.d }
function format(value: Q): string { return value.d === 1n ? value.n.toString() : `${value.n}/${value.d}` }

export function buildCircleQuadraticFormChart(
  spec: CircleQuadraticSpec,
): { chart?: CircleQuadraticFormChart; errors: string[] } {
  const quadratic = parse(spec.quadraticCoefficient)
  const linearX = parse(spec.linearX)
  const linearY = parse(spec.linearY)
  const constant = parse(spec.constant)
  const errors: string[] = []
  if (!spec.id.trim()) errors.push('id is required')
  if (!spec.sourceSemanticIds.length) errors.push('sourceSemanticIds must not be empty')
  if (!quadratic || quadratic.n === 0n) errors.push('quadratic coefficient must be a nonzero rational')
  if (!linearX || !linearY || !constant) errors.push('circle coefficients must be rational')
  if (errors.length || !quadratic || !linearX || !linearY || !constant || quadratic.n === 0n) {
    return { errors }
  }
  const d = divide(linearX, quadratic)
  const e = divide(linearY, quadratic)
  const f = divide(constant, quadratic)
  const centerX = divide(negate(d), q(2n))
  const centerY = divide(negate(e), q(2n))
  const radiusSquared = subtract(add(multiply(centerX, centerX), multiply(centerY, centerY)), f)
  if (radiusSquared.n <= 0n) return { errors: ['the real locus is not a nondegenerate circle'] }
  const halfD = divide(d, q(2n))
  const halfE = divide(e, q(2n))
  const chart: CircleQuadraticFormChart = {
    kind: 'affine-quadratic-form-circle',
    sourceId: spec.id,
    sourceSemanticIds: spec.sourceSemanticIds,
    normalizedEquation: { linearX: format(d), linearY: format(e), constant: format(f) },
    center: { x: format(centerX), y: format(centerY) },
    radiusSquared: format(radiusSquared),
    homogeneousQuadraticMatrix: [
      ['1', '0', format(halfD)],
      ['0', '1', format(halfE)],
      [format(halfD), format(halfE), format(f)],
    ],
    certificates: [
      {
        claim: 'the affine quadratic equation and center-radius equation have identical coefficients',
        method: 'exact rational completion of squares',
        status: 'certified',
      },
      {
        claim: 'the homogeneous symmetric matrix evaluates to the normalized circle polynomial',
        method: 'exact coefficient replay of [x y 1]Q[x y 1]^T',
        status: 'certified',
      },
      {
        claim: 'matrix decoding reconstructs the normalized circle equation',
        method: 'forward/inverse quadratic-form round trip',
        status: 'certified',
      },
    ],
    forgotten: [
      'a common nonzero scalar multiple of the original equation',
      'Euclidean coordinates before the selected affine chart',
      'general conics whose quadratic part is not a scalar identity',
    ],
  }
  const verification = verifyCircleQuadraticFormChart(chart)
  return verification.certified ? { chart, errors: [] } : { errors: verification.errors }
}

export function verifyCircleQuadraticFormChart(
  chart: CircleQuadraticFormChart,
): { certified: boolean; errors: string[] } {
  const errors: string[] = []
  if (chart.kind !== 'affine-quadratic-form-circle') errors.push('wrong chart kind')
  if (!chart.sourceSemanticIds.length) errors.push('sourceSemanticIds must not be empty')
  const matrix = chart.homogeneousQuadraticMatrix.map(row => row.map(parse))
  if (matrix.length !== 3 || matrix.some(row => row.length !== 3 || row.some(value => value === null))) {
    return { certified: false, errors: [...errors, 'quadratic matrix must be 3 by 3 over Q'] }
  }
  const values = matrix as Q[][]
  if (!equal(values[0][0], ONE) || !equal(values[1][1], ONE) || !equal(values[0][1], ZERO)
    || !equal(values[1][0], ZERO)) errors.push('quadratic part is not the normalized Euclidean circle form')
  if (!equal(values[0][2], values[2][0]) || !equal(values[1][2], values[2][1])) {
    errors.push('quadratic matrix is not symmetric')
  }
  const d = parse(chart.normalizedEquation.linearX)!
  const e = parse(chart.normalizedEquation.linearY)!
  const f = parse(chart.normalizedEquation.constant)!
  if (!equal(multiply(q(2n), values[0][2]), d)
    || !equal(multiply(q(2n), values[1][2]), e)
    || !equal(values[2][2], f)) errors.push('matrix does not encode the normalized equation')
  const centerX = divide(negate(d), q(2n))
  const centerY = divide(negate(e), q(2n))
  const radiusSquared = subtract(add(multiply(centerX, centerX), multiply(centerY, centerY)), f)
  if (format(centerX) !== chart.center.x || format(centerY) !== chart.center.y) errors.push('center is inconsistent')
  if (format(radiusSquared) !== chart.radiusSquared || radiusSquared.n <= 0n) errors.push('radius squared is inconsistent')
  return { certified: errors.length === 0, errors }
}

export function evaluateCirclePower(
  chart: CircleQuadraticFormChart,
  point: { x: RationalInput; y: RationalInput },
): string {
  const x = parse(point.x)
  const y = parse(point.y)
  if (!x || !y) throw new Error('point coordinates must be rational')
  const d = parse(chart.normalizedEquation.linearX)!
  const e = parse(chart.normalizedEquation.linearY)!
  const f = parse(chart.normalizedEquation.constant)!
  return format(add(add(add(multiply(x, x), multiply(y, y)), multiply(d, x)), add(multiply(e, y), f)))
}
