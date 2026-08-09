import {
  extractLatexSegments,
  parseLatexExpression,
  parseLatexRelation,
  type MathExpression,
  type MathRelationIR,
} from './math-expression-ir'
import {
  executeLinearInvariant,
  type LinearCoordinate,
  type LinearInvariantCertificate,
  type LinearInvariantProgram,
  type LinearSideCondition,
} from './exact-linear-invariant'

type Q = { n: bigint; d: bigint }
type AffineForm = { terms: Map<string, Q>; constant: Q }

export type LinearPredicateDocument = {
  coordinate: LinearCoordinate
  relations: string[]
  goal: string
  sideConditions?: LinearSideCondition[]
  expected?: string | number | bigint
}

export type LinearPredicateLowering =
  | { status: 'lowered'; program: LinearInvariantProgram; certificate: LinearInvariantCertificate }
  | { status: 'parse_error' | 'non_equality' | 'nonlinear' | 'missing_goal'; detail: string }

const ZERO: Q = { n: 0n, d: 1n }
const ONE: Q = { n: 1n, d: 1n }

function gcd(left: bigint, right: bigint): bigint {
  let a = left < 0n ? -left : left
  let b = right < 0n ? -right : right
  while (b !== 0n) [a, b] = [b, a % b]
  return a || 1n
}

function q(n: bigint, d = 1n): Q {
  if (d === 0n) throw new Error('division by zero')
  if (d < 0n) return q(-n, -d)
  const divisor = gcd(n, d)
  return { n: n / divisor, d: d / divisor }
}

function rationalNumber(value: number): Q | null {
  if (!Number.isFinite(value)) return null
  if (Number.isSafeInteger(value)) return q(BigInt(value))
  const source = value.toString().toLowerCase()
  const match = source.match(/^([+-]?)(\d+)(?:\.(\d+))?(?:e([+-]?\d+))?$/)
  if (!match) return null
  const sign = match[1] === '-' ? -1n : 1n
  const fractional = match[3] ?? ''
  const exponent = Number(match[4] ?? 0) - fractional.length
  const digits = BigInt(`${match[2]}${fractional}`)
  return exponent >= 0
    ? q(sign * digits * (10n ** BigInt(exponent)))
    : q(sign * digits, 10n ** BigInt(-exponent))
}

function addQ(left: Q, right: Q): Q { return q(left.n * right.d + right.n * left.d, left.d * right.d) }
function negateQ(value: Q): Q { return { n: -value.n, d: value.d } }
function subtractQ(left: Q, right: Q): Q { return addQ(left, negateQ(right)) }
function multiplyQ(left: Q, right: Q): Q { return q(left.n * right.n, left.d * right.d) }
function divideQ(left: Q, right: Q): Q | null { return right.n === 0n ? null : q(left.n * right.d, left.d * right.n) }
function isZero(value: Q): boolean { return value.n === 0n }
function formatQ(value: Q): string { return value.d === 1n ? String(value.n) : `${value.n}/${value.d}` }

function constant(value: Q): AffineForm { return { terms: new Map(), constant: value } }

function scaled(form: AffineForm, factor: Q): AffineForm {
  return {
    terms: new Map([...form.terms].map(([name, coefficient]) => [name, multiplyQ(coefficient, factor)])),
    constant: multiplyQ(form.constant, factor),
  }
}

function combined(left: AffineForm, right: AffineForm, sign: 1 | -1): AffineForm {
  const terms = new Map(left.terms)
  for (const [name, coefficient] of right.terms) {
    const next = addQ(terms.get(name) ?? ZERO, sign === 1 ? coefficient : negateQ(coefficient))
    if (isZero(next)) terms.delete(name)
    else terms.set(name, next)
  }
  return {
    terms,
    constant: sign === 1 ? addQ(left.constant, right.constant) : subtractQ(left.constant, right.constant),
  }
}

function affine(expression: MathExpression): AffineForm | null {
  if (typeof expression === 'number') {
    const value = rationalNumber(expression)
    return value === null ? null : constant(value)
  }
  if (typeof expression === 'string') return { terms: new Map([[expression, ONE]]), constant: ZERO }
  const [operator, ...rawArguments] = expression
  const operands = rawArguments as MathExpression[]
  if (operator === 'Add') {
    return operands.reduce<AffineForm | null>((result, item) => {
      const next = affine(item)
      return result !== null && next !== null ? combined(result, next, 1) : null
    }, constant(ZERO))
  }
  if (operator === 'Subtract') {
    const left = affine(operands[0])
    const right = affine(operands[1])
    return left !== null && right !== null ? combined(left, right, -1) : null
  }
  if (operator === 'Negate') {
    const value = affine(operands[0])
    return value === null ? null : scaled(value, q(-1n))
  }
  if (operator === 'Multiply') {
    let result = constant(ONE)
    for (const item of operands) {
      const next = affine(item)
      if (next === null) return null
      const resultHasVariables = result.terms.size > 0
      const nextHasVariables = next.terms.size > 0
      if (resultHasVariables && nextHasVariables) return null
      result = resultHasVariables
        ? scaled(result, next.constant)
        : nextHasVariables
          ? scaled(next, result.constant)
          : constant(multiplyQ(result.constant, next.constant))
    }
    return result
  }
  if (operator === 'Divide') {
    const numerator = affine(operands[0])
    const denominator = affine(operands[1])
    if (numerator === null || denominator === null || denominator.terms.size > 0) return null
    const reciprocal = divideQ(ONE, denominator.constant)
    return reciprocal === null ? null : scaled(numerator, reciprocal)
  }
  if (operator === 'Power') {
    const exponent = affine(operands[1])
    if (exponent === null || exponent.terms.size > 0 || exponent.constant.d !== 1n) return null
    if (exponent.constant.n === 0n) return constant(ONE)
    return exponent.constant.n === 1n ? affine(operands[0]) : null
  }
  return null
}

function record(form: AffineForm): Record<string, string> {
  return Object.fromEntries([...form.terms].sort(([left], [right]) => left.localeCompare(right)).map(
    ([name, coefficient]) => [name, formatQ(coefficient)],
  ))
}

function equation(relation: MathRelationIR, index: number): LinearInvariantProgram['equations'][number] | null {
  if (relation.operator !== 'Equal') return null
  const lhs = affine(relation.lhs)
  const rhs = affine(relation.rhs)
  if (lhs === null || rhs === null) return null
  const difference = combined(lhs, rhs, -1)
  return {
    terms: record(difference),
    rhs: formatQ(negateQ(difference.constant)),
    provenance: [`relation:${index + 1}:${relation.latex}`],
  }
}

export function lowerLinearPredicateDocument(document: LinearPredicateDocument): LinearPredicateLowering {
  if (!document.goal.trim()) return { status: 'missing_goal', detail: 'goal expression is empty' }
  const parsedRelations = document.relations.map(parseLatexRelation)
  if (parsedRelations.some(relation => relation === null)) {
    return { status: 'parse_error', detail: 'at least one relation could not be parsed' }
  }
  if (parsedRelations.some(relation => relation!.operator !== 'Equal')) {
    return { status: 'non_equality', detail: 'linear invariant backend currently accepts equalities only' }
  }
  const equations = parsedRelations.map((relation, index) => equation(relation!, index))
  if (equations.some(value => value === null)) {
    return { status: 'nonlinear', detail: 'a relation is not affine in the selected coordinate system' }
  }
  const parsedGoal = parseLatexExpression(document.goal)
  if (parsedGoal === null) return { status: 'parse_error', detail: 'goal expression could not be parsed' }
  const goal = affine(parsedGoal)
  if (goal === null) return { status: 'nonlinear', detail: 'goal is not affine in the selected coordinate system' }
  const program: LinearInvariantProgram = {
    coordinate: document.coordinate,
    equations: equations as LinearInvariantProgram['equations'],
    sideConditions: document.sideConditions,
    goal: {
      terms: record(goal),
      constant: formatQ(goal.constant),
      expected: document.expected,
    },
  }
  return { status: 'lowered', program, certificate: executeLinearInvariant(program) }
}

export function lowerLinearPredicateStatement(
  statement: string,
  coordinate: LinearCoordinate = 'additive',
): LinearPredicateLowering {
  const segments = extractLatexSegments(statement)
  const relations = segments.filter(segment => parseLatexRelation(segment) !== null)
  const expressions = segments.filter(segment => parseLatexRelation(segment) === null && parseLatexExpression(segment) !== null)
  if (!expressions.length) return { status: 'missing_goal', detail: 'no standalone TeX goal expression was found' }
  return lowerLinearPredicateDocument({ coordinate, relations, goal: expressions.at(-1)! })
}
