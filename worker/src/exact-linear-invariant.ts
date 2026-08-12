/**
 * Exact provenance-carrying linear elimination.
 *
 * Finite symbolic elimination succeeds because
 * predicates are lowered to a small number of linear coordinate systems. This
 * module provides the same reusable kernel for MathOS. Geometry, affine state
 * equations, prime valuations, and directed angles differ only by coordinate
 * interpretation; elimination and provenance are shared.
 */

export type LinearCoordinate = 'additive' | 'log_multiplicative' | 'angle'

export type RationalInput = bigint | number | string

export type LinearEquation = {
  terms: Record<string, RationalInput>
  rhs: RationalInput
  provenance: string[]
}

export type LinearSideCondition = {
  id: string
  predicate: string
  proved: boolean
}

export type LinearInvariantProgram = {
  coordinate: LinearCoordinate
  equations: LinearEquation[]
  sideConditions?: LinearSideCondition[]
  goal: {
    terms: Record<string, RationalInput>
    constant?: RationalInput
    expected?: RationalInput
  }
}

export type LinearInvariantCertificate = {
  status: 'proved' | 'underdetermined' | 'inconsistent' | 'blocked'
  coordinate: LinearCoordinate
  value: string | null
  expectedMatches: boolean | null
  usedProvenance: string[]
  rank: number
  variables: string[]
  residual: Record<string, string>
  blockedSideConditions: string[]
}

type Q = { n: bigint; d: bigint }
type Row = { values: Q[]; provenance: Set<string> }

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

function parse(value: RationalInput): Q {
  if (typeof value === 'bigint') return q(value)
  if (typeof value === 'number') {
    if (!Number.isSafeInteger(value)) throw new Error('linear invariant coefficients must be exact integers or rational strings')
    return q(BigInt(value))
  }
  const source = value.trim()
  const match = source.match(/^([+-]?\d+)(?:\/([+-]?\d+))?$/)
  if (!match) throw new Error(`invalid rational coefficient: ${value}`)
  return q(BigInt(match[1]), BigInt(match[2] ?? '1'))
}

function add(a: Q, b: Q): Q { return q(a.n * b.d + b.n * a.d, a.d * b.d) }
function neg(a: Q): Q { return { n: -a.n, d: a.d } }
function sub(a: Q, b: Q): Q { return add(a, neg(b)) }
function mul(a: Q, b: Q): Q { return q(a.n * b.n, a.d * b.d) }
function div(a: Q, b: Q): Q {
  if (b.n === 0n) throw new Error('division by zero in exact elimination')
  return q(a.n * b.d, a.d * b.n)
}
function isZero(a: Q): boolean { return a.n === 0n }
function equal(a: Q, b: Q): boolean { return a.n === b.n && a.d === b.d }
function format(a: Q): string { return a.d === 1n ? String(a.n) : `${a.n}/${a.d}` }

function scaled(row: Row, factor: Q): Row {
  return { values: row.values.map(value => mul(value, factor)), provenance: new Set(row.provenance) }
}

function subtractRows(left: Row, right: Row, factor: Q): Row {
  return {
    values: left.values.map((value, index) => sub(value, mul(right.values[index], factor))),
    provenance: new Set([...left.provenance, ...right.provenance]),
  }
}

function rref(rows: Row[], variableCount: number): { rows: Row[]; pivots: number[] } {
  const matrix = rows.map(row => ({ values: [...row.values], provenance: new Set(row.provenance) }))
  const pivots: number[] = []
  let pivotRow = 0
  for (let column = 0; column < variableCount && pivotRow < matrix.length; column++) {
    const found = matrix.findIndex((row, index) => index >= pivotRow && !isZero(row.values[column]))
    if (found < 0) continue
    ;[matrix[pivotRow], matrix[found]] = [matrix[found], matrix[pivotRow]]
    matrix[pivotRow] = scaled(matrix[pivotRow], div(ONE, matrix[pivotRow].values[column]))
    for (let index = 0; index < matrix.length; index++) {
      if (index === pivotRow || isZero(matrix[index].values[column])) continue
      matrix[index] = subtractRows(matrix[index], matrix[pivotRow], matrix[index].values[column])
    }
    pivots.push(column)
    pivotRow++
  }
  return { rows: matrix, pivots }
}

export function executeLinearInvariant(program: LinearInvariantProgram): LinearInvariantCertificate {
  const blocked = (program.sideConditions ?? []).filter(condition => !condition.proved).map(condition => condition.id)
  const variables = [...new Set([
    ...program.equations.flatMap(equation => Object.keys(equation.terms)),
    ...Object.keys(program.goal.terms),
  ])].sort()
  if (blocked.length) {
    return {
      status: 'blocked', coordinate: program.coordinate, value: null, expectedMatches: null,
      usedProvenance: [], rank: 0, variables, residual: {}, blockedSideConditions: blocked,
    }
  }

  const rows: Row[] = program.equations.map(equation => ({
    values: [...variables.map(variable => parse(equation.terms[variable] ?? 0)), parse(equation.rhs)],
    provenance: new Set(equation.provenance),
  }))
  const reduced = rref(rows, variables.length)
  const contradiction = reduced.rows.find(row =>
    row.values.slice(0, variables.length).every(isZero) && !isZero(row.values[variables.length]),
  )
  if (contradiction) {
    return {
      status: 'inconsistent', coordinate: program.coordinate, value: null, expectedMatches: null,
      usedProvenance: [...contradiction.provenance].sort(), rank: reduced.pivots.length,
      variables, residual: {}, blockedSideConditions: [],
    }
  }

  let goal: Row = {
    // For g(x) = sum(a_i x_i) + c, store sum(a_i x_i) - value = -c.
    values: [
      ...variables.map(variable => parse(program.goal.terms[variable] ?? 0)),
      neg(parse(program.goal.constant ?? 0)),
    ],
    provenance: new Set(),
  }
  reduced.pivots.forEach((column, rowIndex) => {
    const coefficient = goal.values[column]
    if (!isZero(coefficient)) goal = subtractRows(goal, reduced.rows[rowIndex], coefficient)
  })
  const residualEntries = variables
    .map((variable, index) => [variable, goal.values[index]] as const)
    .filter(([, coefficient]) => !isZero(coefficient))
  const residual = Object.fromEntries(residualEntries.map(([variable, coefficient]) => [variable, format(coefficient)]))
  if (residualEntries.length) {
    return {
      status: 'underdetermined', coordinate: program.coordinate, value: null, expectedMatches: null,
      usedProvenance: [...goal.provenance].sort(), rank: reduced.pivots.length,
      variables, residual, blockedSideConditions: [],
    }
  }
  // Elimination computes goal_terms - value = 0, hence value is -constant.
  const value = neg(goal.values[variables.length])
  const expected = program.goal.expected === undefined ? null : parse(program.goal.expected)
  return {
    status: 'proved', coordinate: program.coordinate, value: format(value),
    expectedMatches: expected === null ? null : equal(value, expected),
    usedProvenance: [...goal.provenance].sort(), rank: reduced.pivots.length,
    variables, residual: {}, blockedSideConditions: [],
  }
}
