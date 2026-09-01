import { createHash } from 'node:crypto'

import type { DiscoveryParent } from './parent-conditioned-discovery'
import { extractMobiusMap, type ExecutableFusionCard } from './executable-fusion'
import { runtimeSynthesisCertificate } from './execution-certificate'
import { evaluateExactExpression } from './exact-expression-executor'
import {
  extractBoundMathExpression,
  isDirectBoundExpressionQuery,
  mathExpressionToLatex,
  type MathExpression,
} from './math-expression-ir'
import {
  executePolynomialRootInvariant,
  executePolynomialRootOperation,
  executeRationalMapOnRoots,
  extractPolynomial,
  extractRationalMap,
  type ExactPolynomialRootInvariantResult,
  type ExactPolynomialRootOperationResult,
  type ExactRationalRootMapResult,
  type PolynomialInput,
  type PolynomialRootInvariant,
  type PolynomialRootOperation,
  type RationalMapInput,
} from './polynomial-root-fusion'
import type { TypedProgramNode, TypedTerm } from './typed-term-enumerator'
import { extractSymbolicPowerRelation } from './symbolic-power-relation'
import { synthesizeExactSingleProblem } from './single-problem-exact'

type PolynomialValue = {
  kind: 'polynomial'
  polynomial: PolynomialInput
}

type OrbitValue = {
  kind: 'finite_algebraic_orbit'
  polynomial: PolynomialInput
}

type ScalarValue = {
  kind: 'scalar'
  latex: string
  sympy: string
}

type IntegerMatrix2 = readonly [bigint, bigint, bigint, bigint]

type Matrix2Value = {
  kind: 'matrix2'
  map: RationalMapInput
  matrix: IntegerMatrix2 | null
}

type RationalSelfMapValue = {
  kind: 'rational_self_map'
  map: RationalMapInput
  matrix: IntegerMatrix2 | null
}

type CyclicGroupValue = {
  kind: 'cyclic_group'
  parentId: string
  source: string
  variable: string
  degreeSymbol: string
  rhs: bigint
}

type SymbolicPowerOrbitValue = {
  kind: 'symbolic_power_orbit'
  parentId: string
  source: string
  variable: string
  degreeSymbol: string
  rhs: bigint
}

type FiniteFamilyValue = {
  kind: 'finite_family'
  polynomial: PolynomialInput
}

type RationalPowerOrbitFamilyValue = {
  kind: 'rational_power_orbit_family'
  map: RationalMapInput
  matrix: IntegerMatrix2
  orbit: SymbolicPowerOrbitValue
  parentIds: string[]
}

type RuntimeValue =
  | PolynomialValue
  | OrbitValue
  | ScalarValue
  | Matrix2Value
  | RationalSelfMapValue
  | CyclicGroupValue
  | SymbolicPowerOrbitValue
  | FiniteFamilyValue
  | RationalPowerOrbitFamilyValue

type RootOperationTrace = ExactPolynomialRootOperationResult & {
  kind: 'root-operation'
  morphism: string
  parent_ids: string[]
}

type InvariantTrace = ExactPolynomialRootInvariantResult & {
  kind: 'root-invariant'
  morphism: string
  parent_ids: string[]
}

type RationalMapOrbitTrace = ExactRationalRootMapResult & {
  kind: 'rational-map-orbit'
  morphism: string
  parent_ids: string[]
}

type SymbolicPowerOrbitTrace = {
  kind: 'symbolic-power-orbit'
  morphism: 'RootsOfUnity'
  parent_ids: string[]
  relation: string
  variable: string
  degree_symbol: string
  rhs: string
  exact: true
}

type PowerOrbitSummationTrace = {
  kind: 'power-orbit-summation'
  morphism: 'FiniteSummation'
  parent_ids: string[]
  map: string
  matrix: string[]
  orbit_relation: string
  degree_symbol: string
  rhs: string
  value: string
  value_sympy: string
  decomposition: string
  logarithmic_derivative: string
  pole_condition: string
  numeric_samples: number[]
  exact: true
  numeric_check: true
}

type RuntimeTrace =
  | RootOperationTrace
  | InvariantTrace
  | RationalMapOrbitTrace
  | SymbolicPowerOrbitTrace
  | PowerOrbitSummationTrace

type EvaluationContext = {
  inputs: Map<string, RuntimeValue>
  overrides: Map<string, RuntimeValue>
  trace: RuntimeTrace[]
}

export type TypedProgramExecutionSupport = {
  executable: boolean
  reason: string
  unsupported: string[]
}

export type TypedProgramExecutionResult = {
  cards: ExecutableFusionCard[]
  programsExamined: number
  unsupportedObligations: string[]
}

const ROOT_OPERATIONS: Readonly<Record<string, PolynomialRootOperation>> = {
  RootMinkowskiSum: 'sum',
  RootMinkowskiDifference: 'difference',
  RootPointwiseProduct: 'product',
}

const ROOT_INVARIANTS: Readonly<Record<string, PolynomialRootInvariant>> = {
  FieldTrace: 'trace',
  FieldNorm: 'norm',
}

const SUPPORTED_PARENT_SORTS = new Set([
  'Polynomial',
  'Matrix2',
  'CyclicGroup',
  'ExecutableExpression',
  'ExecutableConstraintIR',
])
const RATIONAL_MAP_REALIZATIONS = new Set(['MobiusMap', 'MobiusRealization'])

export function runtimePrimitiveHandlers(): string[] {
  return [
    'RootExtraction',
    'RootConfiguration',
    'RootsOfUnity',
    'EvaluateExpression',
    'SolveConstraintQuery',
    ...RATIONAL_MAP_REALIZATIONS,
    'MapOrbitEvaluation',
    'FiniteSummation',
    ...Object.keys(ROOT_OPERATIONS),
    ...Object.keys(ROOT_INVARIANTS),
  ].sort()
}

export function runtimeParentSorts(): string[] {
  return [...SUPPORTED_PARENT_SORTS].sort()
}

function hash(value: unknown, length = 14): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function unique<T>(values: readonly T[]): T[] {
  return [...new Set(values)]
}

function parentIdsOf(node: TypedProgramNode): string[] {
  if (node.kind === 'parent') return [node.parentId]
  return unique(node.args.flatMap(parentIdsOf)).sort()
}

function parentSortsOf(node: TypedProgramNode): Map<string, Set<string>> {
  const result = new Map<string, Set<string>>()
  const visit = (current: TypedProgramNode) => {
    if (current.kind === 'parent') {
      const sorts = result.get(current.parentId) ?? new Set<string>()
      sorts.add(current.sort)
      result.set(current.parentId, sorts)
      return
    }
    current.args.forEach(visit)
  }
  visit(node)
  return result
}

function inspectNode(node: TypedProgramNode): string[] {
  if (node.kind === 'parent') {
    return SUPPORTED_PARENT_SORTS.has(node.sort) ? [] : [`parent sort ${node.sort}`]
  }
  const childIssues = node.args.flatMap(inspectNode)
  if (node.morphism === 'RootExtraction' || node.morphism === 'RootConfiguration') {
    return node.args.length === 1
      ? childIssues
      : [...childIssues, `${node.morphism} arity ${node.args.length}`]
  }
  if (node.morphism === 'RootsOfUnity') {
    return node.args.length === 1
      ? childIssues
      : [...childIssues, `${node.morphism} arity ${node.args.length}`]
  }
  if (node.morphism === 'EvaluateExpression') {
    return node.args.length === 1
      ? childIssues
      : [...childIssues, `${node.morphism} arity ${node.args.length}`]
  }
  if (node.morphism === 'SolveConstraintQuery') {
    return node.args.length === 1
      ? childIssues
      : [...childIssues, `${node.morphism} arity ${node.args.length}`]
  }
  if (ROOT_OPERATIONS[node.morphism]) {
    return node.args.length === 2
      ? childIssues
      : [...childIssues, `${node.morphism} arity ${node.args.length}`]
  }
  if (ROOT_INVARIANTS[node.morphism]) {
    return node.args.length === 1
      ? childIssues
      : [...childIssues, `${node.morphism} arity ${node.args.length}`]
  }
  if (RATIONAL_MAP_REALIZATIONS.has(node.morphism)) {
    return node.args.length === 1
      ? childIssues
      : [...childIssues, `${node.morphism} arity ${node.args.length}`]
  }
  if (node.morphism === 'MapOrbitEvaluation') {
    return node.args.length === 2
      ? childIssues
      : [...childIssues, `${node.morphism} arity ${node.args.length}`]
  }
  if (node.morphism === 'FiniteSummation') {
    return node.args.length === 1
      ? childIssues
      : [...childIssues, `${node.morphism} arity ${node.args.length}`]
  }
  return [...childIssues, `missing primitive handler ${node.morphism}`]
}

export function inspectTypedProgramExecution(node: TypedProgramNode): TypedProgramExecutionSupport {
  const unsupported = unique(inspectNode(node))
  return {
    executable: unsupported.length === 0,
    reason: unsupported.length
      ? unsupported.join('; ')
      : 'the enumerated typed program is executable by cold primitive handlers',
    unsupported,
  }
}

function parseSymbolicPowerRelation(parent: DiscoveryParent): CyclicGroupValue | null {
  const relation = extractSymbolicPowerRelation(parent)
  return relation ? {
    kind: 'cyclic_group',
    ...relation,
  } : null
}

function rationalMapVariable(parent: DiscoveryParent): string {
  return (parent.statement ?? '').match(/[A-Za-z][A-Za-z0-9_]*\s*\(\s*([A-Za-z])\s*\)\s*=/)?.[1] ?? 'z'
}

function matrixDeterminant(matrix: IntegerMatrix2): bigint {
  return matrix[0] * matrix[3] - matrix[1] * matrix[2]
}

function linearExpression(coefficient: bigint, constant: bigint, variable: string): string {
  const variableTerm = coefficient === 0n
    ? ''
    : coefficient === 1n
      ? variable
      : coefficient === -1n
        ? `-${variable}`
        : `${coefficient}${variable}`
  if (constant === 0n) return variableTerm || '0'
  if (!variableTerm) return constant.toString()
  return `${variableTerm}${constant > 0n ? '+' : ''}${constant}`
}

function mapFromMatrix(parentId: string, matrix: IntegerMatrix2, variable = 'z'): RationalMapInput {
  const [a, b, c, d] = matrix
  return {
    parentId,
    source: `T(${variable})=\\frac{${linearExpression(a, b, variable)}}{${linearExpression(c, d, variable)}}`,
    normalized: `((${a}*x+${b})/(${c}*x+${d}))`,
    variable,
    elaborator: 'mathjson-ir',
  }
}

type NumericComplex = { re: number; im: number }

function numericMobius(matrix: IntegerMatrix2, z: NumericComplex): NumericComplex | null {
  const [a, b, c, d] = matrix.map(Number) as unknown as [number, number, number, number]
  const denominator = { re: c * z.re + d, im: c * z.im }
  const norm = denominator.re * denominator.re + denominator.im * denominator.im
  if (norm < 1e-18) return null
  const numerator = { re: a * z.re + b, im: a * z.im }
  return {
    re: (numerator.re * denominator.re + numerator.im * denominator.im) / norm,
    im: (numerator.im * denominator.re - numerator.re * denominator.im) / norm,
  }
}

function numericPowerOrbitFormula(matrix: IntegerMatrix2, rhs: bigint, degree: number): number | null {
  const [a, b, c, d] = matrix.map(Number) as unknown as [number, number, number, number]
  const q = Number(rhs)
  if (c === 0) return degree * b / d
  const denominator = Math.pow(-d, degree) - q * Math.pow(c, degree)
  if (Math.abs(denominator) < 1e-12) return null
  return degree * a / c - degree * (b * c - a * d) * Math.pow(-d, degree - 1) /
    (c * denominator)
}

function verifyPowerOrbitNumerically(matrix: IntegerMatrix2, rhs: bigint): number[] {
  const q = Number(rhs)
  if (!Number.isFinite(q) || q === 0) return []
  const verified: number[] = []
  for (const degree of [2, 3, 4, 5, 7, 9]) {
    const expected = numericPowerOrbitFormula(matrix, rhs, degree)
    if (expected === null || !Number.isFinite(expected)) continue
    const radius = Math.pow(Math.abs(q), 1 / degree)
    const argument = q < 0 ? Math.PI : 0
    let sum: NumericComplex = { re: 0, im: 0 }
    let valid = true
    for (let index = 0; index < degree; index++) {
      const angle = (argument + 2 * Math.PI * index) / degree
      const image = numericMobius(matrix, {
        re: radius * Math.cos(angle),
        im: radius * Math.sin(angle),
      })
      if (!image) {
        valid = false
        break
      }
      sum = { re: sum.re + image.re, im: sum.im + image.im }
    }
    if (!valid) continue
    const scale = Math.max(1, Math.abs(expected))
    if (Math.abs(sum.re - expected) <= 1e-8 * scale && Math.abs(sum.im) <= 1e-8 * scale) {
      verified.push(degree)
    }
  }
  return verified
}

function executePowerOrbitSummation(input: RationalPowerOrbitFamilyValue): PowerOrbitSummationTrace | null {
  const [a, b, c, d] = input.matrix
  if (matrixDeterminant(input.matrix) === 0n) return null
  const degree = input.orbit.degreeSymbol
  const q = input.orbit.rhs
  const numericSamples = verifyPowerOrbitNumerically(input.matrix, q)
  if (numericSamples.length < 3) return null

  let value: string
  let valueSympy: string
  let decomposition: string
  let logarithmicDerivative: string
  let poleCondition: string
  if (c === 0n) {
    value = `${degree}\\cdot\\frac{${b}}{${d}}`
    valueSympy = `${degree}*Rational(${b},${d})`
    decomposition = `T(z)=\\frac{${a}}{${d}}z+\\frac{${b}}{${d}}`
    logarithmicDerivative = `\\sum_{${input.orbit.variable}^${degree}=${q}}${input.orbit.variable}=0`
    poleCondition = `${d}\\ne0`
  } else {
    const delta = b * c - a * d
    const negativeD = -d
    value = `${degree}\\left(\\frac{${a}}{${c}}-\\frac{\\left(${delta}\\right)\\left(${negativeD}\\right)^{${degree}-1}}{${c}\\left(\\left(${negativeD}\\right)^{${degree}}-\\left(${q}\\right)\\left(${c}\\right)^{${degree}}\\right)}\\right)`
    valueSympy = `${degree}*(Rational(${a},${c})-(${delta})*(${negativeD})**(${degree}-1)/(${c}*((${negativeD})**${degree}-(${q})*(${c})**${degree})))`
    decomposition = `T(z)=\\frac{${a}}{${c}}+\\frac{${delta}}{${c}(${c}z+${d})}`
    logarithmicDerivative = `\\sum_{z^{${degree}}=${q}}\\frac{1}{${c}z+${d}}=-\\frac{${degree}\\left(${negativeD}\\right)^{${degree}-1}}{\\left(${negativeD}\\right)^{${degree}}-\\left(${q}\\right)\\left(${c}\\right)^{${degree}}}`
    poleCondition = `\\left(${negativeD}\\right)^{${degree}}\\ne\\left(${q}\\right)\\left(${c}\\right)^{${degree}}`
  }

  return {
    kind: 'power-orbit-summation',
    morphism: 'FiniteSummation',
    parent_ids: input.parentIds,
    map: input.map.source,
    matrix: input.matrix.map(String),
    orbit_relation: input.orbit.source,
    degree_symbol: degree,
    rhs: q.toString(),
    value,
    value_sympy: valueSympy,
    decomposition,
    logarithmic_derivative: logarithmicDerivative,
    pole_condition: poleCondition,
    numeric_samples: numericSamples,
    exact: true,
    numeric_check: true,
  }
}

function evaluate(node: TypedProgramNode, context: EvaluationContext): RuntimeValue {
  if (node.kind === 'parent') {
    if (!SUPPORTED_PARENT_SORTS.has(node.sort)) throw new Error(`unsupported parent sort: ${node.sort}`)
    const value = context.overrides.get(node.parentId) ?? context.inputs.get(node.parentId)
    if (!value) throw new Error(`no ${node.sort} elaboration for parent ${node.parentId}`)
    if (node.sort === 'Polynomial' && value.kind !== 'polynomial') {
      throw new Error(`parent ${node.parentId} did not elaborate as Polynomial`)
    }
    if (node.sort === 'Matrix2' && value.kind !== 'matrix2') {
      throw new Error(`parent ${node.parentId} did not elaborate as Matrix2`)
    }
    if (node.sort === 'CyclicGroup' && value.kind !== 'cyclic_group') {
      throw new Error(`parent ${node.parentId} did not elaborate as CyclicGroup`)
    }
    return value
  }

  if (node.morphism === 'RootExtraction' || node.morphism === 'RootConfiguration') {
    if (node.args.length !== 1) throw new Error(`${node.morphism} requires one argument`)
    const input = evaluate(node.args[0], context)
    if (input.kind !== 'polynomial') throw new Error(`${node.morphism} requires a polynomial`)
    return { kind: 'finite_algebraic_orbit', polynomial: input.polynomial }
  }

  if (node.morphism === 'RootsOfUnity') {
    if (node.args.length !== 1) throw new Error(`${node.morphism} requires one argument`)
    const input = evaluate(node.args[0], context)
    if (input.kind !== 'cyclic_group') throw new Error(`${node.morphism} requires a cyclic power relation`)
    const orbit: SymbolicPowerOrbitValue = {
      kind: 'symbolic_power_orbit',
      parentId: input.parentId,
      source: input.source,
      variable: input.variable,
      degreeSymbol: input.degreeSymbol,
      rhs: input.rhs,
    }
    context.trace.push({
      kind: 'symbolic-power-orbit',
      morphism: 'RootsOfUnity',
      parent_ids: [input.parentId],
      relation: input.source,
      variable: input.variable,
      degree_symbol: input.degreeSymbol,
      rhs: input.rhs.toString(),
      exact: true,
    })
    return orbit
  }

  if (RATIONAL_MAP_REALIZATIONS.has(node.morphism)) {
    if (node.args.length !== 1) throw new Error(`${node.morphism} requires one argument`)
    const input = evaluate(node.args[0], context)
    if (input.kind !== 'matrix2') throw new Error(`${node.morphism} requires a Matrix2 realization`)
    return { kind: 'rational_self_map', map: input.map, matrix: input.matrix }
  }

  if (node.morphism === 'MapOrbitEvaluation') {
    if (node.args.length !== 2) throw new Error(`${node.morphism} requires two arguments`)
    const map = evaluate(node.args[0], context)
    const orbit = evaluate(node.args[1], context)
    if (map.kind !== 'rational_self_map') {
      throw new Error(`${node.morphism} requires a rational self-map`)
    }
    if (orbit.kind === 'symbolic_power_orbit') {
      if (!map.matrix) throw new Error(`${node.morphism} requires exact integer Mobius coefficients`)
      return {
        kind: 'rational_power_orbit_family',
        map: map.map,
        matrix: map.matrix,
        orbit,
        parentIds: unique([...parentIdsOf(node.args[0]), ...parentIdsOf(node.args[1])]).sort(),
      }
    }
    if (orbit.kind !== 'finite_algebraic_orbit') {
      throw new Error(`${node.morphism} requires a finite algebraic orbit`)
    }
    const result = executeRationalMapOnRoots(map.map, orbit.polynomial)
    if (!result) throw new Error(`${node.morphism} failed exact rational-map elimination`)
    const parentIds = unique([...parentIdsOf(node.args[0]), ...parentIdsOf(node.args[1])]).sort()
    context.trace.push({
      ...result,
      kind: 'rational-map-orbit',
      morphism: node.morphism,
      parent_ids: parentIds,
    })
    return {
      kind: 'finite_family',
      polynomial: {
        parentId: parentIds.join('+'),
        source: result.result,
        normalized: result.result_sympy,
        elaborator: 'mathjson-ir',
      },
    }
  }

  if (node.morphism === 'FiniteSummation') {
    if (node.args.length !== 1) throw new Error(`${node.morphism} requires one argument`)
    const input = evaluate(node.args[0], context)
    if (input.kind === 'rational_power_orbit_family') {
      const result = executePowerOrbitSummation(input)
      if (!result) throw new Error(`${node.morphism} failed the exact power-orbit identity`)
      context.trace.push(result)
      return { kind: 'scalar', latex: result.value, sympy: result.value_sympy }
    }
    if (input.kind !== 'finite_family') throw new Error(`${node.morphism} requires one finite family`)
    const result = executePolynomialRootInvariant(input.polynomial, 'trace')
    if (!result) throw new Error(`${node.morphism} failed exact coefficient verification`)
    const parentIds = parentIdsOf(node.args[0])
    context.trace.push({
      ...result,
      kind: 'root-invariant',
      morphism: node.morphism,
      parent_ids: parentIds,
    })
    return { kind: 'scalar', latex: result.value, sympy: result.value_sympy }
  }

  const invariant = ROOT_INVARIANTS[node.morphism]
  if (invariant) {
    if (node.args.length !== 1) throw new Error(`${node.morphism} requires one argument`)
    const input = evaluate(node.args[0], context)
    if (input.kind !== 'finite_algebraic_orbit') {
      throw new Error(`${node.morphism} requires one finite algebraic orbit`)
    }
    const result = executePolynomialRootInvariant(input.polynomial, invariant)
    if (!result) throw new Error(`${node.morphism} failed exact coefficient verification`)
    const parentIds = parentIdsOf(node.args[0])
    context.trace.push({
      ...result,
      kind: 'root-invariant',
      morphism: node.morphism,
      parent_ids: parentIds,
    })
    return { kind: 'scalar', latex: result.value, sympy: result.value_sympy }
  }

  const operation = ROOT_OPERATIONS[node.morphism]
  if (!operation) throw new Error(`missing primitive handler: ${node.morphism}`)
  if (node.args.length !== 2) throw new Error(`${node.morphism} requires two arguments`)
  const left = evaluate(node.args[0], context)
  const right = evaluate(node.args[1], context)
  if (left.kind !== 'finite_algebraic_orbit' || right.kind !== 'finite_algebraic_orbit') {
    throw new Error(`${node.morphism} requires two finite algebraic orbits`)
  }
  const result = executePolynomialRootOperation(left.polynomial, right.polynomial, operation)
  if (!result) throw new Error(`${node.morphism} failed exact resultant verification`)
  const parentIds = unique([...parentIdsOf(node.args[0]), ...parentIdsOf(node.args[1])]).sort()
  context.trace.push({
    ...result,
    kind: 'root-operation',
    morphism: node.morphism,
    parent_ids: parentIds,
  })
  return {
    kind: 'finite_algebraic_orbit',
    polynomial: {
      parentId: parentIds.join('+'),
      source: result.result,
      normalized: result.result_sympy,
      elaborator: 'mathjson-ir',
    },
  }
}

function operationSymbol(morphism: string): string {
  if (morphism === 'RootMinkowskiSum') return '+'
  if (morphism === 'RootMinkowskiDifference') return '-'
  if (morphism === 'RootPointwiseProduct') return '\\cdot '
  return '?'
}

function renderRootExpression(
  node: TypedProgramNode,
  parentIndexes: ReadonlyMap<string, number>,
  parentSorts: ReadonlyMap<string, string>,
  occurrences: Map<string, number>,
): string {
  if (node.kind === 'parent') {
    const occurrence = (occurrences.get(node.parentId) ?? 0) + 1
    occurrences.set(node.parentId, occurrence)
    const parentIndex = parentIndexes.get(node.parentId) ?? 0
    if (parentSorts.get(node.parentId) === 'Matrix2') return `T_${parentIndex}`
    if (parentSorts.get(node.parentId) === 'CyclicGroup') return `\\zeta_{${parentIndex},${occurrence}}`
    return `\\alpha_{${parentIndex},${occurrence}}`
  }
  if (node.morphism === 'RootExtraction' || node.morphism === 'RootConfiguration') {
    return renderRootExpression(node.args[0], parentIndexes, parentSorts, occurrences)
  }
  if (node.morphism === 'RootsOfUnity') {
    return renderRootExpression(node.args[0], parentIndexes, parentSorts, occurrences)
  }
  if (RATIONAL_MAP_REALIZATIONS.has(node.morphism)) {
    return renderRootExpression(node.args[0], parentIndexes, parentSorts, occurrences)
  }
  if (node.morphism === 'MapOrbitEvaluation' && node.args.length === 2) {
    const map = renderRootExpression(node.args[0], parentIndexes, parentSorts, occurrences)
    const argument = renderRootExpression(node.args[1], parentIndexes, parentSorts, occurrences)
    return `${map}\\!\\left(${argument}\\right)`
  }
  if (ROOT_OPERATIONS[node.morphism] && node.args.length === 2) {
    const left = renderRootExpression(node.args[0], parentIndexes, parentSorts, occurrences)
    const right = renderRootExpression(node.args[1], parentIndexes, parentSorts, occurrences)
    return `\\left(${left}${operationSymbol(node.morphism)}${right}\\right)`
  }
  return `\\operatorname{${node.morphism}}\\left(${node.args.map(arg => renderRootExpression(arg, parentIndexes, parentSorts, occurrences)).join(',')}\\right)`
}

function postorderMorphisms(node: TypedProgramNode): string[] {
  if (node.kind === 'parent') return []
  return [...node.args.flatMap(postorderMorphisms), node.morphism]
}

function parentWitnesses(node: TypedProgramNode): Map<string, string[]> {
  const result = new Map<string, string[]>()
  const walk = (current: TypedProgramNode, ancestors: string[]) => {
    if (current.kind === 'parent') {
      const existing = result.get(current.parentId) ?? []
      result.set(current.parentId, unique([...existing, ...ancestors.slice().reverse()]))
      return
    }
    for (const argument of current.args) walk(argument, [...ancestors, current.morphism])
  }
  walk(node, [])
  return result
}

function resultantFormula(trace: RootOperationTrace, index: number): string {
  const left = `F_${index}`
  const right = `G_${index}`
  if (trace.operation === 'sum') {
    return `\\operatorname{Res}_x\\!\\left(${left}(x),${right}(z-x)\\right)`
  }
  if (trace.operation === 'difference') {
    return `\\operatorname{Res}_x\\!\\left(${left}(x),${right}(x-z)\\right)`
  }
  return `\\operatorname{Res}_x\\!\\left(${left}(x),x^{${trace.degree_right}}${right}(z/x)\\right)`
}

function buildSolution(trace: readonly RuntimeTrace[]): string {
  const rows = trace.map((step, index) => {
    if (step.kind === 'symbolic-power-orbit') {
      return `${index + 1}. 親問題から \\(${step.relation}\\) を抽出し、その解全体を多項式 \\(P_${step.degree_symbol}(z)=z^{${step.degree_symbol}}-${step.rhs}\\) の重複度付き根集合として扱う。`
    }
    if (step.kind === 'power-orbit-summation') {
      if (step.matrix[2] === '0') {
        return `${index + 1}. \\(${step.decomposition}\\) と分解する。\\(P_${step.degree_symbol}(z)=z^{${step.degree_symbol}}-${step.rhs}\\) の \\(z^{${step.degree_symbol}-1}\\) の係数は0なので、Vietaの公式から \\(${step.logarithmic_derivative}\\) である。したがって像の総和は \\(${step.value}\\) である。`
      }
      return `${index + 1}. \\(${step.decomposition}\\) と分解する。\\(P_${step.degree_symbol}(z)=z^{${step.degree_symbol}}-${step.rhs}\\) に対する対数微分 \\(P'_${step.degree_symbol}(x)/P_${step.degree_symbol}(x)=\\sum_{P_${step.degree_symbol}(\\zeta)=0}(x-\\zeta)^{-1}\\) を \\(x=-d/c\\) で用いると、\\(${step.logarithmic_derivative}\\) を得る。したがって、\\(${step.pole_condition}\\) のもとで像の総和は \\(${step.value}\\) である。`
    }
    if (step.kind === 'rational-map-orbit') {
      return `${index + 1}. 一次分数変換を \\(T(x)=${step.map}\\)、根集合を定める多項式を \\(F(x)=${step.orbit_polynomial}\\) とする。\\(T\\) の分子・分母を \\(N(x),D(x)\\) と書けば、像 \\(z=T(x)\\) は \\(D(x)z-N(x)=0\\) を満たす。したがって \\(\\operatorname{Res}_x(F(x),D(x)z-N(x))\\) を平方因子除去・モニック化し、像全体を根にもつ \\(P(z)=${step.result}\\) を得る。行列式は \\(${step.determinant}\\neq0\\) であり、分母は根集合上で零にならない。`
    }
    if (step.kind === 'root-invariant') {
      const label = step.invariant === 'trace' ? '根の総和' : '根の総積'
      const formula = step.invariant === 'trace' ? '-a_{d-1}/a_d' : '(-1)^d a_0/a_d'
      return `${index + 1}. \\(P(z)=${step.polynomial}\\) の次数を \\(d=${step.degree}\\) とする。Vieta の公式より${label}は \\(${formula}=${step.value}\\) である。`
    }
    const label = step.operation === 'sum' ? '和' : step.operation === 'difference' ? '差' : '積'
    const stepNumber = index + 1
    return `${stepNumber}. \\(F_${stepNumber}(x)=${step.left}\\), \\(G_${stepNumber}(x)=${step.right}\\) とおく。二つの根集合の${label}を取る消去式は \\(${resultantFormula(step, stepNumber)}\\) である。平方因子を除いてモニック化すると \\(P_${stepNumber}(z)=${step.result}\\) を得る。`
  })
  const verification = trace.some(step => step.kind === 'power-orbit-summation')
    ? '部分分数分解と対数微分恒等式は記号のまま導出し、複数の次数で直接求めた根の和とも独立に照合した。'
    : '終結式と係数計算は有理数体上で厳密に行い、数値根による独立照合も行った。'
  return `親問題から一次分数変換または一変数多項式を読み取り、写像と根集合を型付き対象として扱う。${rows.join('')}${verification}また、各親入力を一つずつ摂動して型付きプログラム全体を再実行し、最終結果が変わることを確かめた。`
}

function runtimeSignature(value: RuntimeValue): string {
  if (value.kind === 'scalar') return `scalar:${value.sympy}`
  if (value.kind === 'polynomial' || value.kind === 'finite_algebraic_orbit' || value.kind === 'finite_family') {
    return `${value.kind}:${value.polynomial.normalized}`
  }
  if (value.kind === 'matrix2' || value.kind === 'rational_self_map') {
    return `${value.kind}:${value.map.normalized}`
  }
  if (value.kind === 'cyclic_group' || value.kind === 'symbolic_power_orbit') {
    return `${value.kind}:${value.variable}^${value.degreeSymbol}=${value.rhs}`
  }
  return `${value.kind}:${value.map.normalized}:${value.orbit.variable}^${value.orbit.degreeSymbol}=${value.orbit.rhs}`
}

function rootObservableNode(node: TypedProgramNode): {
  node: TypedProgramNode
  invariant: PolynomialRootInvariant | null
} {
  if (node.kind === 'apply' && ROOT_INVARIANTS[node.morphism] && node.args.length === 1) {
    return { node: node.args[0], invariant: ROOT_INVARIANTS[node.morphism] }
  }
  if (node.kind === 'apply' && node.morphism === 'FiniteSummation' && node.args.length === 1) {
    return { node: node.args[0], invariant: 'trace' }
  }
  return { node, invariant: null }
}

function traceDegree(trace: readonly RuntimeTrace[]): number {
  const final = trace[trace.length - 1]
  if (!final) return 0
  if (final.kind === 'root-operation' || final.kind === 'rational-map-orbit') return final.degree_result
  if (final.kind === 'power-orbit-summation') return final.numeric_samples.length
  if (final.kind === 'symbolic-power-orbit') return 0
  return final.degree
}

function elaborateRuntimeParent(
  parent: DiscoveryParent,
  sort: string,
  index: number,
): RuntimeValue | null {
  if (sort === 'Polynomial') {
    const polynomial = extractPolynomial(parent, index)
    return polynomial ? { kind: 'polynomial', polynomial } : null
  }
  if (sort === 'Matrix2') {
    const mobius = extractMobiusMap([parent])
    const map = extractRationalMap(parent, index) ?? (mobius
      ? mapFromMatrix(String(parent.id), mobius.matrix, rationalMapVariable(parent))
      : null)
    if (!map) return null
    return { kind: 'matrix2', map, matrix: mobius?.matrix ?? null }
  }
  if (sort === 'CyclicGroup') {
    return parseSymbolicPowerRelation(parent)
  }
  return null
}

function runtimeInputSource(input: RuntimeValue): string {
  if (input.kind === 'polynomial' || input.kind === 'finite_algebraic_orbit' || input.kind === 'finite_family') {
    return input.polynomial.source
  }
  if (input.kind === 'matrix2' || input.kind === 'rational_self_map') return input.map.source
  if (input.kind === 'cyclic_group' || input.kind === 'symbolic_power_orbit') return input.source
  if (input.kind === 'rational_power_orbit_family') return `${input.map.source}; ${input.orbit.source}`
  return input.latex
}

function incrementExactRational(source: string): string | null {
  const value = source.trim()
  const fraction = value.match(/^([+-]?\d+)\/([+-]?\d+)$/)
  if (fraction) {
    const numerator = BigInt(fraction[1])
    const denominator = BigInt(fraction[2])
    if (denominator === 0n) return null
    const nextNumerator = numerator + denominator
    return denominator === 1n ? String(nextNumerator) : `${nextNumerator}/${denominator}`
  }
  if (!/^[+-]?\d+$/.test(value)) return null
  return String(BigInt(value) + 1n)
}

function polynomialSympyFromCoefficients(coefficients: readonly string[]): string {
  return coefficients
    .map((coefficient, degree) => degree === 0
      ? `(${coefficient})`
      : `(${coefficient})*x**${degree}`)
    .join('+')
}

function runtimeInputPerturbations(input: RuntimeValue): RuntimeValue[] {
  if (input.kind === 'polynomial') {
    const exactPerturbations = (input.polynomial.coefficients ?? []).flatMap((_, index, coefficients) => {
      const degree = coefficients.length - 1
      if (index !== 0 && index !== Math.max(0, degree - 1)) return []
      const incremented = incrementExactRational(coefficients[index])
      if (incremented === null) return []
      const changed = [...coefficients]
      changed[index] = incremented
      return [{
        kind: 'polynomial' as const,
        polynomial: {
          ...input.polynomial,
          normalized: polynomialSympyFromCoefficients(changed),
          coefficients: changed,
        },
      }]
    })
    if (exactPerturbations.length) return exactPerturbations

    const traceInvariant = executePolynomialRootInvariant(input.polynomial, 'trace')
    return unique([
      `((${input.polynomial.normalized})+1)`,
      traceInvariant?.ablation_polynomial_sympy ?? '',
    ].filter(Boolean)).map(normalized => ({
      kind: 'polynomial' as const,
      polynomial: { ...input.polynomial, normalized, coefficients: undefined },
    }))
  }
  if (input.kind === 'matrix2') {
    if (!input.matrix) {
      return [{
        kind: 'matrix2',
        map: {
          ...input.map,
          normalized: `((${input.map.normalized})+1)`,
        },
        matrix: null,
      }]
    }
    const [a, b, c, d] = input.matrix
    const candidates: IntegerMatrix2[] = [
      [a + 1n, b, c, d],
      [a, b + 1n, c, d],
      [a, b, c + 1n, d],
      [a, b, c, d + 1n],
    ]
    return candidates
      .filter(matrix => matrixDeterminant(matrix) !== 0n)
      .map(matrix => ({
        kind: 'matrix2' as const,
        map: mapFromMatrix(input.map.parentId, matrix, input.map.variable),
        matrix,
      }))
  }
  if (input.kind === 'cyclic_group') {
    return [1n, -1n, 2n]
      .map(delta => input.rhs + delta)
      .filter(rhs => rhs !== 0n)
      .map(rhs => ({
        ...input,
        rhs,
        source: `${input.variable}^{${input.degreeSymbol}}=${rhs}`,
      }))
  }
  return []
}

function executeExpressionGoal(
  parents: readonly DiscoveryParent[],
  goal: TypedTerm,
  cacheRole: 'not_consulted' | 'duplicate_exclusion_only',
  hypothesesExamined: number,
): ExecutableFusionCard | null {
  if (goal.program.kind !== 'apply' || goal.program.morphism !== 'EvaluateExpression' ||
      goal.program.args.length !== 1) return null
  const argument = goal.program.args[0]
  if (argument.kind !== 'parent' || argument.sort !== 'ExecutableExpression') return null
  const parentIds = parents.map(parent => String(parent.id))
  const goalParentIds = parentIdsOf(goal.program)
  if (goalParentIds.length !== parentIds.length || parentIds.some(id => !goalParentIds.includes(id))) return null
  const parent = parents.find(item => String(item.id) === argument.parentId)
  if (!parent) return null
  if (!isDirectBoundExpressionQuery(parent.statement ?? '')) return null
  const parsed = extractBoundMathExpression(parent.statement ?? '')
  if (!parsed) return null
  const evaluation = evaluateExactExpression(parsed.expression)
  if (!evaluation.ok || !evaluation.result_tex || !evaluation.result_srepr) return null
  const perturbedExpression: MathExpression = ['Add', parsed.expression, 1]
  const perturbed = evaluateExactExpression(perturbedExpression)
  if (!perturbed.ok || !perturbed.result_srepr || perturbed.result_srepr === evaluation.result_srepr) return null

  const expressionTex = mathExpressionToLatex(parsed.expression)
  const programId = hash({ program: goal.program, ast: parsed.expression, result: evaluation.result_srepr })
  const morphismChain = postorderMorphisms(goal.program)
  const obligations = [
    'the complete expression occurs in the current parent statement',
    'all binder scopes are preserved by the expression IR',
    'exact evaluation and independent AST reconstruction agree',
    'perturbing the current expression changes the final result',
  ]
  const proofCertificate = [
    {
      id: `${programId}.parse`,
      claim: 'the executable AST was parsed from the current statement without an Atlas route',
      verifier: 'binder-aware expression parser',
    },
    {
      id: `${programId}.exact`,
      claim: 'the expression evaluates to the displayed exact result',
      verifier: 'whitelisted SymPy AST evaluation and reconstruction replay',
    },
    {
      id: `${programId}.ablation`,
      claim: 'a structural perturbation changes the exact result',
      verifier: 'whole-expression counterfactual replay',
    },
  ]
  const generatedProgram = {
    schema: 'mortra.typed-expression-program.v1',
    ast: parsed.expression,
    ast_sha256: evaluation.certificate?.ast_sha256,
    result: evaluation.result_srepr,
    result_sha256: evaluation.certificate?.result_sha256,
    replay: evaluation.certificate,
    perturbation: perturbedExpression,
    perturbation_result: perturbed.result_srepr,
  }
  const parentId = String(parent.id)

  return {
    id: `mathos-runtime-expression-${programId}`,
    family_id: 'runtime.typed_expression_program',
    statement_tex: `次の値を厳密に求めよ。\\[${expressionTex}\\]`,
    answer_tex: `\\(${evaluation.result_tex}\\)`,
    solution_tex: `問題文に書かれた式を、和・極限・積分の束縛変数と範囲を保った式木として読む。` +
      `その式木は \\(${expressionTex}\\) である。内側の束縛演算から順に厳密計算すると ` +
      `\\[${expressionTex}=${evaluation.result_tex}\\]` +
      `を得る。さらに同じ式木を再構成して再計算し、結果が一致することを確かめた。`,
    domain: 'runtime_exact_expression',
    morphism_chain: morphismChain,
    parent_ids: parentIds,
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: 'binder-aware expression IR + exact evaluation + AST reconstruction replay + counterfactual perturbation',
      exact_backend: true,
      independent_check: true,
      samples: [hypothesesExamined, evaluation.operators?.length ?? 0, 1],
    },
    difficulty: {
      band: 'runtime_exact_expression',
      score: 2 + (evaluation.operators?.length ?? 0),
    },
    fusion_derivation: {
      passed: true,
      reason: 'the current statement supplied the complete expression AST and the cold executor replayed it exactly',
      ablationPassed: true,
      assignments: [{
        parentId,
        portId: `input:${parentId}`,
        role: 'current executable expression',
        matchedAnchors: [parsed.surface],
        witnessSteps: morphismChain,
        requiredObligations: obligations,
        consumedObligations: obligations,
        coverage: 1,
      }],
      bridges: [{
        id: `typed-expression:${programId}`,
        witnessStep: 'EvaluateExpression',
        consumes: [`input:${parentId}`],
        produces: goal.sort,
      }],
      intermediatePropositions: [{
        parentId,
        morphism: 'EvaluateExpression',
        source: 'ExecutableExpression',
        target: 'Scalar',
        proposition: `the current expression equals ${evaluation.result_tex}`,
        proved: true,
      }],
    },
    structure_blueprint: {
      id: `runtime.typed-expression.${programId}`,
      version: 1,
      kernel: 'runtime_typed_expression_interpreter',
      observable: 'exact_value_of_current_expression',
      operators: morphismChain,
      domain: 'current_input_expression_ir',
      tags: ['runtime-synthesis', 'atlas-free', 'expression-ir'],
      morphismChain,
      executable: true,
      proofCertificate,
    },
    search_evidence: {
      hypotheses_evaluated: hypothesesExamined,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
    execution_certificate: runtimeSynthesisCertificate({
      origin: 'synthesized_expression_program',
      parents,
      generatedProgram,
      checks: proofCertificate.map(step => `${step.id}: ${step.verifier}`),
      cacheRole,
    }),
  }
}

function executeOne(
  parents: readonly DiscoveryParent[],
  goal: TypedTerm,
  cacheRole: 'not_consulted' | 'duplicate_exclusion_only',
  hypothesesExamined: number,
): ExecutableFusionCard | null {
  const support = inspectTypedProgramExecution(goal.program)
  if (!support.executable) return null
  if (goal.program.kind === 'apply' && goal.program.morphism === 'EvaluateExpression') {
    return executeExpressionGoal(parents, goal, cacheRole, hypothesesExamined)
  }
  if (goal.program.kind === 'apply' && goal.program.morphism === 'SolveConstraintQuery') {
    if (goal.program.args.length !== 1) return null
    const argument = goal.program.args[0]
    if (argument.kind !== 'parent' || argument.sort !== 'ExecutableConstraintIR') return null
    if (parents.length !== 1 || String(parents[0].id) !== argument.parentId) return null
    return synthesizeExactSingleProblem(parents)[0] ?? null
  }
  const parentIds = parents.map(parent => String(parent.id))
  const goalParents = parentIdsOf(goal.program)
  if (goalParents.length !== parentIds.length || parentIds.some(id => !goalParents.includes(id))) return null

  const sortSets = parentSortsOf(goal.program)
  const parentSorts = new Map<string, string>()
  for (const parentId of parentIds) {
    const sorts = [...(sortSets.get(parentId) ?? [])]
    if (sorts.length !== 1) return null
    parentSorts.set(parentId, sorts[0])
  }
  const inputs = new Map<string, RuntimeValue>()
  parents.forEach((parent, index) => {
    const parentId = String(parent.id)
    const input = elaborateRuntimeParent(parent, parentSorts.get(parentId) ?? '', index)
    if (input) inputs.set(String(parent.id), input)
  })
  if (inputs.size !== parents.length) return null

  const trace: RuntimeTrace[] = []
  const value = evaluate(goal.program, { inputs, overrides: new Map(), trace })
  if ((value.kind !== 'scalar' && value.kind !== 'finite_algebraic_orbit') || trace.length === 0) return null
  const finalResult = runtimeSignature(value)
  const ablationOutputs: Record<string, string> = {}
  for (const parentId of parentIds) {
    const input = inputs.get(parentId)!
    let changedOutput: string | null = null
    for (const perturbation of runtimeInputPerturbations(input)) {
      try {
        const perturbedTrace: RuntimeTrace[] = []
        const perturbedValue = evaluate(goal.program, {
          inputs,
          overrides: new Map([[parentId, perturbation]]),
          trace: perturbedTrace,
        })
        const signature = runtimeSignature(perturbedValue)
        if (signature !== finalResult) {
          changedOutput = signature
          break
        }
      } catch {
        // Try the next exact coefficient perturbation.
      }
    }
    if (!changedOutput) return null
    ablationOutputs[parentId] = changedOutput
  }

  const parentIndexes = new Map(parentIds.map((parentId, index) => [parentId, index + 1]))
  const occurrences = new Map<string, number>()
  const observable = rootObservableNode(goal.program)
  const rootExpression = renderRootExpression(observable.node, parentIndexes, parentSorts, occurrences)
  const inputClauses = parentIds.map((parentId, index) => {
    const input = inputs.get(parentId)!
    if (input.kind === 'matrix2') {
      return `親問題${index + 1}の関係式 \\(${input.map.source}\\) が定める一次分数変換を \\(T_${index + 1}\\) とする。`
    }
    if (input.kind === 'cyclic_group') {
      return `親問題${index + 1}から \\(${input.source}\\) を抽出し、その解全体を \\(\\mathcal R_${index + 1}\\) とする。ただし \\(${input.degreeSymbol}\\ge2\\) とする。`
    }
    if (input.kind !== 'polynomial') return ''
    const count = occurrences.get(parentId) ?? 1
    const symbols = Array.from({ length: count }, (_, occurrence) =>
      `\\alpha_{${index + 1},${occurrence + 1}}`)
    const movement = count > 1
      ? `\\(${symbols.join(',')}\\) は \\(\\mathcal R_${index + 1}\\) 内を互いに独立に動く`
      : `\\(${symbols[0]}\\) は \\(\\mathcal R_${index + 1}\\) 全体を動く`
    return `親問題${index + 1}から抽出した方程式 \\(${input.polynomial.source}\\) の根全体を \\(\\mathcal R_${index + 1}\\) とする。${movement}。`
  })
  const finalTrace = trace[trace.length - 1]
  const poleClause = finalTrace.kind === 'power-orbit-summation'
    ? `また、\\(${finalTrace.pole_condition}\\) を満たすものとする。`
    : ''
  const setDefinition = `\\(\\mathcal S=\\{${rootExpression}\\}\\) を、各根変数が指定された根集合を動くときの異なる値全体とする。`
  const statement = value.kind === 'finite_algebraic_orbit'
    ? `${inputClauses.join('')}${poleClause}${setDefinition} \\(\\mathcal S\\) をちょうど根にもつモニック多項式を求めよ。`
    : observable.invariant === 'trace'
      ? `${inputClauses.join('')}${poleClause}${setDefinition} \\(\\displaystyle\\sum_{\\gamma\\in\\mathcal S}\\gamma\\) を求めよ。`
      : observable.invariant === 'norm'
        ? `${inputClauses.join('')}${poleClause}${setDefinition} \\(\\displaystyle\\prod_{\\gamma\\in\\mathcal S}\\gamma\\) を求めよ。`
        : null
  if (!statement) return null
  const answer = value.kind === 'finite_algebraic_orbit'
    ? `P(z)=${value.polynomial.source}`
    : value.latex
  const observableName = value.kind === 'finite_algebraic_orbit'
    ? 'minimal_squarefree_polynomial_of_composed_root_set'
    : trace.some(step => step.kind === 'rational-map-orbit' || step.kind === 'power-orbit-summation')
      ? 'exact_sum_of_fractional_linear_image_of_algebraic_orbit'
    : observable.invariant === 'trace'
      ? 'field_trace_of_composed_root_set'
      : 'field_norm_of_composed_root_set'
  const morphismChain = postorderMorphisms(goal.program)
  const witnesses = parentWitnesses(goal.program)
  const inputPorts = parentIds.map(parentId => `input:${parentId}`)
  const proofCertificate = [
    {
      id: 'typed-program',
      claim: 'the program was enumerated from parent sorts and primitive morphism signatures',
      verifier: 'typed-program-enumerator',
    },
    ...trace.map((step, index) => {
      if (step.kind === 'root-operation') {
        return {
          id: `exact-operation-${index + 1}`,
          claim: `${step.morphism} eliminates both finite root sets exactly`,
          verifier: 'SymPy resultant over QQ + square-free monic reduction',
        }
      }
      if (step.kind === 'rational-map-orbit') {
        return {
          id: `exact-map-orbit-${index + 1}`,
          claim: `${step.morphism} eliminates the orbit parameter under a nonsingular fractional-linear map`,
          verifier: 'SymPy resultant over QQ + pole exclusion + square-free monic reduction',
        }
      }
      if (step.kind === 'symbolic-power-orbit') {
        return {
          id: `exact-power-orbit-${index + 1}`,
          claim: `${step.morphism} elaborates the current power relation without a registered problem route`,
          verifier: 'typed symbolic relation parser + monic power-polynomial identity',
        }
      }
      if (step.kind === 'power-orbit-summation') {
        return {
          id: `exact-power-sum-${index + 1}`,
          claim: `${step.morphism} composes the current Mobius coefficients with the current power orbit`,
          verifier: 'exact partial-fraction decomposition + polynomial logarithmic derivative + pole exclusion',
        }
      }
      return {
        id: `exact-invariant-${index + 1}`,
        claim: `${step.morphism} is computed from the exact monic coefficients`,
        verifier: 'Vieta coefficient identity over QQ',
      }
    }),
    {
      id: 'independent-root-check',
      claim: 'the exact root-set operation or invariant agrees with independent numerical roots',
      verifier: 'independent SymPy nroots comparison',
    },
    {
      id: 'whole-program-ablation',
      claim: 'perturbing each parent separately changes the final output',
      verifier: 'full typed-program replay under one-parent perturbations',
    },
  ]
  const programId = hash(goal.program)
  const structureId = `runtime.typed-program.${programId}`
  const generatedProgram = {
    schema: 'mortra.typed-program.v1',
    ast: goal.program,
    input_parent_ids: parentIds,
    output_sort: goal.sort,
    exact_trace: trace.map(step => {
      if (step.kind === 'root-operation') {
        return {
          kind: step.kind,
          morphism: step.morphism,
          operation: step.operation,
          parents: step.parent_ids,
          left: step.left_sympy,
          right: step.right_sympy,
          result: step.result_sympy,
        }
      }
      if (step.kind === 'rational-map-orbit') {
        return {
          kind: step.kind,
          morphism: step.morphism,
          parents: step.parent_ids,
          map: step.map_sympy,
          orbit: step.orbit_polynomial_sympy,
          result: step.result_sympy,
          determinant: step.determinant_sympy,
        }
      }
      if (step.kind === 'symbolic-power-orbit') {
        return {
          kind: step.kind,
          morphism: step.morphism,
          parents: step.parent_ids,
          relation: step.relation,
          variable: step.variable,
          degree_symbol: step.degree_symbol,
          rhs: step.rhs,
        }
      }
      if (step.kind === 'power-orbit-summation') {
        return {
          kind: step.kind,
          morphism: step.morphism,
          parents: step.parent_ids,
          map: step.map,
          matrix: step.matrix,
          orbit: step.orbit_relation,
          value: step.value_sympy,
          decomposition: step.decomposition,
          logarithmic_derivative: step.logarithmic_derivative,
          pole_condition: step.pole_condition,
          numeric_samples: step.numeric_samples,
        }
      }
      return {
        kind: step.kind,
        morphism: step.morphism,
        invariant: step.invariant,
        parents: step.parent_ids,
        polynomial: step.polynomial_sympy,
        value: step.value_sympy,
        formula: step.coefficient_formula,
      }
    }),
    parent_ablation_outputs: ablationOutputs,
  }

  return {
    id: `mathos-runtime-${hash([programId, finalResult])}`,
    family_id: 'runtime.typed_program',
    statement_tex: statement,
    answer_tex: answer,
    solution_tex: buildSolution(trace),
    domain: 'algebraic_geometry',
    morphism_chain: morphismChain,
    parent_ids: parentIds,
    unresolved: false,
    discovery_status: 'verified',
    verification: {
      method: 'runtime typed-program interpretation with exact resultants, independent root checks, and whole-program parent ablation',
      exact_backend: true,
      independent_check: true,
      samples: [parents.length, trace.length, traceDegree(trace)],
    },
    difficulty: {
      band: 'A_runtime_algebraic_composition',
      score: 6 + goal.depth + trace.length * 1.5 + traceDegree(trace),
    },
    fusion_derivation: {
      passed: true,
      reason: 'the cold typed AST consumes every selected parent and is replayed only through primitive exact handlers',
      ablationPassed: true,
      assignments: parentIds.map(parentId => {
        const input = inputs.get(parentId)!
        const isMap = input.kind === 'matrix2'
        const isPowerOrbit = input.kind === 'cyclic_group'
        const obligations = isMap
          ? ['fractional-linear elaboration', 'nonsingular matrix provenance']
          : isPowerOrbit
            ? ['symbolic power-relation elaboration', 'finite orbit provenance']
            : ['polynomial elaboration', 'root-set provenance']
        return {
          parentId,
          portId: `input:${parentId}`,
          role: isMap
            ? 'typed fractional-linear map input'
            : isPowerOrbit
              ? 'typed symbolic power-orbit input'
              : 'typed polynomial input',
          matchedAnchors: [runtimeInputSource(input)],
          witnessSteps: witnesses.get(parentId) ?? [isMap ? 'MobiusMap' : isPowerOrbit ? 'RootsOfUnity' : 'RootExtraction'],
          requiredObligations: obligations,
          consumedObligations: obligations,
          coverage: 1,
        }
      }),
      bridges: [{
        id: `typed-program:${programId}`,
        witnessStep: finalTrace.morphism,
        consumes: inputPorts,
        produces: goal.sort,
      }],
      intermediatePropositions: parentIds.map(parentId => {
        const input = inputs.get(parentId)!
        const isMap = input.kind === 'matrix2'
        const isPowerOrbit = input.kind === 'cyclic_group'
        return {
          parentId,
          morphism: isMap ? 'MobiusMap' : isPowerOrbit ? 'RootsOfUnity' : 'RootExtraction',
          source: isMap ? 'Matrix2' : isPowerOrbit ? 'CyclicGroup' : 'Polynomial',
          target: isMap ? 'RationalSelfMap' : 'FiniteAlgebraicOrbit',
          proposition: isMap
            ? 'the elaborated nonsingular matrix determines a fractional-linear self-map'
            : isPowerOrbit
              ? 'the elaborated symbolic power relation determines a finite algebraic orbit for every admissible degree'
              : 'the elaborated polynomial determines a finite algebraic root configuration',
          proved: true as const,
        }
      }),
    },
    structure_blueprint: {
      id: structureId,
      version: 1,
      kernel: 'runtime_typed_program_interpreter',
      observable: observableName,
      operators: morphismChain,
      domain: 'algebraic_geometry',
      tags: [
        'runtime-synthesis',
        'typed-program',
        'root-set',
        trace.some(step => step.kind === 'power-orbit-summation')
          ? 'symbolic-power-orbit'
          : trace.some(step => step.kind === 'rational-map-orbit')
            ? 'rational-map-orbit'
            : observable.invariant ?? 'resultant',
      ],
      morphismChain,
      executable: true,
      proofCertificate,
    },
    search_evidence: {
      hypotheses_evaluated: hypothesesExamined,
      valid_hypotheses: 1,
      elapsed_ms: 0,
    },
    execution_certificate: runtimeSynthesisCertificate({
      origin: 'synthesized_proof_program',
      parents,
      generatedProgram,
      checks: proofCertificate.map(step => `${step.id}: ${step.verifier}`),
      cacheRole,
    }),
  }
}

export function executeTypedPrograms(
  parents: readonly DiscoveryParent[],
  goals: readonly TypedTerm[],
  requested: number,
  cacheRole: 'not_consulted' | 'duplicate_exclusion_only' = 'not_consulted',
): TypedProgramExecutionResult {
  const shallowFirst = [...goals].sort((left, right) =>
    left.depth - right.depth || left.expression.localeCompare(right.expression))
  const primaryMorphisms = [
    'RootMinkowskiSum',
    'RootPointwiseProduct',
    'RootMinkowskiDifference',
    'FieldTrace',
    'FieldNorm',
    'FiniteSummation',
  ]
  const primary = primaryMorphisms.flatMap(morphism => {
    const goal = shallowFirst.find(candidate =>
      candidate.parentIds.length === parents.length &&
      parents.every(parent => candidate.parentIds.includes(String(parent.id))) &&
      candidate.program.kind === 'apply' &&
      candidate.program.morphism === morphism &&
      inspectTypedProgramExecution(candidate.program).executable)
    return goal ? [goal] : []
  })
  const primaryIds = new Set(primary.map(goal => goal.id))
  const ordered = [...primary, ...shallowFirst.filter(goal => !primaryIds.has(goal.id))]
  const cards: ExecutableFusionCard[] = []
  const seen = new Set<string>()
  const unsupported = new Set<string>()
  let programsExamined = 0
  for (const goal of ordered) {
    const support = inspectTypedProgramExecution(goal.program)
    if (!support.executable) {
      support.unsupported.forEach(item => unsupported.add(item))
      continue
    }
    programsExamined++
    try {
      const card = executeOne(parents, goal, cacheRole, programsExamined)
      if (!card) continue
      const key = `${goal.program.kind === 'apply' ? goal.program.morphism : 'parent'}\u0000${card.answer_tex}`
      if (seen.has(key)) continue
      seen.add(key)
      cards.push(card)
      if (cards.length >= requested) break
    } catch (error) {
      unsupported.add(error instanceof Error ? error.message : String(error))
    }
  }
  return {
    cards,
    programsExamined,
    unsupportedObligations: [...unsupported].sort(),
  }
}
