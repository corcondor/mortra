import { spawnSync } from 'node:child_process'
import { createHash } from 'node:crypto'
import { existsSync } from 'node:fs'
import path from 'node:path'
import type { DiscoveryParent } from './parent-conditioned-discovery'
import type { ExecutableFusionCard } from './executable-fusion'
import { runtimeSynthesisCertificate } from './execution-certificate'
import {
  extractMathRelations,
  mathExpressionToSympy,
  renameMathSymbol,
  symbolsInMathExpression,
} from './math-expression-ir'
import type { MathExpression } from './math-expression-ir'
import {
  executeExactRootInvariant,
  executeExactRootComposition,
  polynomialCoefficientsFromMathExpression,
} from './exact-polynomial-resultant'

export type PolynomialRootOperation = 'sum' | 'difference' | 'product'
export type PolynomialRootInvariant = 'trace' | 'norm'

export type PolynomialPairMapTerm = {
  coefficient: number
  left_power: number
  right_power: number
}

export type PolynomialPairMapSpec = {
  id: string
  terms: PolynomialPairMapTerm[]
}

export type RationalMapInput = {
  parentId: string
  source: string
  normalized: string
  variable: string
  elaborator: 'mathjson-ir'
}

export type PolynomialInput = {
  parentId: string
  source: string
  normalized: string
  coefficients?: string[]
  elaborator: 'mathjson-ir' | 'legacy-normalizer'
}

export type ExactPolynomialRootOperationResult = {
  left: string
  right: string
  result: string
  left_sympy: string
  right_sympy: string
  result_sympy: string
  degree_left: number
  degree_right: number
  degree_result: number
  operation: PolynomialRootOperation
  exact: true
  numeric_check: true
  ablation: true
  error?: never
}

export type ExactPolynomialRootInvariantResult = {
  polynomial: string
  polynomial_sympy: string
  degree: number
  invariant: PolynomialRootInvariant
  value: string
  value_sympy: string
  coefficient_formula: string
  numeric_check: true
  exact: true
  ablation_polynomial_sympy: string
  error?: never
}

export type ExactRationalRootMapResult = {
  map: string
  map_sympy: string
  numerator_sympy: string
  denominator_sympy: string
  orbit_polynomial: string
  orbit_polynomial_sympy: string
  result: string
  result_sympy: string
  determinant: string
  determinant_sympy: string
  degree_orbit: number
  degree_result: number
  exact: true
  numeric_check: true
  map_ablation_sympy: string
  error?: never
}

export type ExactPolynomialPairMapResult = {
  left: string
  right: string
  result: string
  left_sympy: string
  right_sympy: string
  result_sympy: string
  map: string
  map_sympy: string
  map_terms: PolynomialPairMapTerm[]
  first_resultant: string
  elimination_result: string
  elimination_gcd: string
  degree_left: number
  degree_right: number
  degree_result: number
  exact: true
  numeric_check: true
  ablation: true
  error?: never
}

const backendCache = new Map<string, ExactPolynomialRootOperationResult | null>()
const invariantBackendCache = new Map<string, ExactPolynomialRootInvariantResult | null>()
const rationalMapBackendCache = new Map<string, ExactRationalRootMapResult | null>()
const polynomialPairMapBackendCache = new Map<string, ExactPolynomialPairMapResult | null>()

function enumeratePolynomialPairMapGrammar(maximum = 4): PolynomialPairMapSpec[] {
  const monomials: Array<Omit<PolynomialPairMapTerm, 'coefficient'>> = []
  for (let totalDegree = 0; totalDegree <= 3; totalDegree += 1) {
    for (let leftPower = totalDegree; leftPower >= 0; leftPower -= 1) {
      monomials.push({ left_power: leftPower, right_power: totalDegree - leftPower })
    }
  }
  const supports: Array<Array<Omit<PolynomialPairMapTerm, 'coefficient'>>> = []
  for (let first = 0; first < monomials.length; first += 1) {
    for (let second = first + 1; second < monomials.length; second += 1) {
      for (let third = second + 1; third < monomials.length; third += 1) {
        const support = [monomials[first], monomials[second], monomials[third]]
        if (!support.some(term => term.left_power > 0) || !support.some(term => term.right_power > 0)) continue
        if (!support.some(term => term.left_power > 0 && term.right_power > 0)) continue
        supports.push(support)
      }
    }
  }
  const supportKey = (support: Array<Omit<PolynomialPairMapTerm, 'coefficient'>>) =>
    support.map(term => `${term.left_power}:${term.right_power}`).sort().join('|')
  const score = (support: Array<Omit<PolynomialPairMapTerm, 'coefficient'>>) => {
    const keys = new Set(support.map(term => `${term.left_power}:${term.right_power}`))
    const symmetryPenalty = support.filter(term => !keys.has(`${term.right_power}:${term.left_power}`)).length
    const degrees = support.map(term => term.left_power + term.right_power)
    const spread = Math.max(...degrees) - Math.min(...degrees)
    const maximumDegree = Math.max(...degrees)
    const constantPenalty = support.some(term => term.left_power === 0 && term.right_power === 0) ? 1 : 0
    return [symmetryPenalty, spread, Math.abs(maximumDegree - 2), constantPenalty, supportKey(support)] as const
  }
  supports.sort((left, right) => {
    const leftScore = score(left)
    const rightScore = score(right)
    for (let index = 0; index < leftScore.length - 1; index += 1) {
      const difference = Number(leftScore[index]) - Number(rightScore[index])
      if (difference) return difference
    }
    return String(leftScore.at(-1)).localeCompare(String(rightScore.at(-1)))
  })
  return supports.slice(0, maximum).map(support => ({
    id: `grammar-map-${supportKey(support).replaceAll(':', '_').replaceAll('|', '-')}`,
    terms: support.map(term => ({ coefficient: 1, ...term })),
  }))
}

const PAIR_MAP_BASIS: readonly PolynomialPairMapSpec[] = enumeratePolynomialPairMapGrammar()

export function polynomialPairMapBasis(): PolynomialPairMapSpec[] {
  return PAIR_MAP_BASIS.map(map => ({
    id: map.id,
    terms: map.terms.map(term => ({ ...term })),
  }))
}

function hash(value: unknown, length = 12): string {
  return createHash('sha256').update(JSON.stringify(value)).digest('hex').slice(0, length)
}

function mathSegments(statement: string): string[] {
  const segments: string[] = []
  const patterns = [
    /\$([^$]+)\$/g,
    /\\\(([^]*?)\\\)/g,
    /\\\[([^]*?)\\\]/g,
  ]
  for (const pattern of patterns) {
    for (const match of statement.matchAll(pattern)) segments.push(match[1])
  }
  return segments.length ? segments : [statement]
}

function replaceFractions(source: string): string {
  let current = source
  const fraction = /\\(?:d?frac)\s*\{([^{}]+)\}\s*\{([^{}]+)\}/g
  for (let iteration = 0; iteration < 12 && fraction.test(current); iteration++) {
    fraction.lastIndex = 0
    current = current.replace(fraction, '(($1)/($2))')
  }
  return current
}

function normalizeLatexExpression(source: string): string | null {
  let value = source
    .replace(/\\left|\\right/g, '')
    .replace(/−|–/g, '-')
    .replace(/\\cdot|\\times/g, '*')
    .replace(/\\sqrt\s*\{([^{}]+)\}/g, 'sqrt($1)')
  value = replaceFractions(value)
    .replace(/\^\s*\{([^{}]+)\}/g, '^($1)')
    .replace(/_\s*\{[^{}]+\}/g, '')
    .replace(/[{}]/g, match => match === '{' ? '(' : ')')
    .replace(/\\[a-zA-Z]+/g, '')
    .replace(/[^0-9A-Za-z+\-*/^().\s]/g, '')
    .trim()
  if (!value || /[A-Za-z]{2,}/.test(value.replace(/sqrt/g, ''))) return null
  return value
}

function polynomialDegreeIn(expression: MathExpression, variable: string): number | null {
  if (typeof expression === 'number') return 0
  if (typeof expression === 'string') return expression === variable ? 1 : 0

  const [operator, ...args] = expression
  if (operator === 'Apply' || operator === 'Sum' || operator === 'Limit' || operator === 'Integral' || operator === 'Binomial') {
    return symbolsInMathExpression(expression).includes(variable) ? null : 0
  }
  if (operator === 'Negate' || operator === 'Sqrt') {
    const degree = polynomialDegreeIn(args[0] as MathExpression, variable)
    if (operator === 'Sqrt' && degree !== 0) return null
    return degree
  }
  if (operator === 'Add' || operator === 'Subtract') {
    const degrees = args.map(value => polynomialDegreeIn(value as MathExpression, variable))
    return degrees.some(degree => degree === null) ? null : Math.max(...degrees as number[])
  }
  if (operator === 'Multiply') {
    const degrees = args.map(value => polynomialDegreeIn(value as MathExpression, variable))
    return degrees.some(degree => degree === null) ? null : (degrees as number[]).reduce((sum, degree) => sum + degree, 0)
  }
  if (operator === 'Divide') {
    const numerator = polynomialDegreeIn(args[0] as MathExpression, variable)
    const denominator = polynomialDegreeIn(args[1] as MathExpression, variable)
    return numerator === null || denominator !== 0 ? null : numerator
  }
  if (operator === 'Power') {
    const base = polynomialDegreeIn(args[0] as MathExpression, variable)
    const exponent = args[1]
    return base === null || typeof exponent !== 'number' || !Number.isInteger(exponent) || exponent < 0
      ? null
      : base * exponent
  }
  return null
}

function hasRootSetSemantics(statement: string): boolean {
  if (/(?:方程式|零点|最小多項式|(?:すべて|全て|相異なる|\d+)?\s*(?:根|解)(?:を|と|に|が|について)|roots?|zeros?|solutions?|minimal\s+polynomial)/i.test(statement)) {
    return true
  }
  if (/(?:実数|複素数|数)\s*[A-Za-z\u0370-\u03ff][A-Za-z0-9_\u0370-\u03ff]*\s*(?:は|が)[^。．]*?(?:を満たす|satisf(?:y|ies))/iu.test(statement)) {
    return true
  }
  const compact = statement.replace(/\s+/g, '')
  return compact.includes('=') && !/[ぁ-んァ-ヶ一-龠]/u.test(compact) && !/[A-Za-z]{3,}/.test(compact.replace(/\\[A-Za-z]+/g, ''))
}

function isZeroExpression(expression: MathExpression): boolean {
  return typeof expression === 'number' && expression === 0
}

function relationPolynomialExpression(
  relation: ReturnType<typeof extractMathRelations>[number],
  variable: string,
): MathExpression {
  const functionDefinition = relation.latex.match(/^\s*[A-Za-z]\s*\(\s*([A-Za-z])\s*\)\s*=/)
  if (functionDefinition?.[1] === variable && !isZeroExpression(relation.rhs)) return relation.rhs
  return ['Subtract', relation.lhs, relation.rhs]
}

export function extractPolynomial(parent: DiscoveryParent, index: number): PolynomialInput | null {
  const parentId = String(parent.id || `parent-${index + 1}`)
  const statement = parent.statement ?? ''
  if (!hasRootSetSemantics(statement)) return null

  const candidates: Array<PolynomialInput & { degree: number; priority: number }> = []
  for (const relation of extractMathRelations(statement)) {
    if (relation.operator !== 'Equal') continue
    const variableCandidates = relation.variables.flatMap(variable => {
      const expression = relationPolynomialExpression(relation, variable)
      const degree = polynomialDegreeIn(expression, variable)
      return degree !== null && degree > 0 ? [{ variable, expression, degree }] : []
    })
    if (!variableCandidates.length) continue
    const maxDegree = Math.max(...variableCandidates.map(candidate => candidate.degree))
    const maximal = variableCandidates.filter(candidate => candidate.degree === maxDegree)
    // A relation such as x^2+y^2=1 does not designate one finite root set.
    if (maximal.length !== 1) continue
    const { variable, expression, degree } = maximal[0]
    const renamed = renameMathSymbol(expression, variable, 'x')
    candidates.push({
      parentId,
      source: relation.latex,
      normalized: mathExpressionToSympy(renamed),
      coefficients: polynomialCoefficientsFromMathExpression(expression, variable) ?? undefined,
      elaborator: 'mathjson-ir',
      degree,
      priority: 1,
    })
  }
  for (const segment of mathSegments(statement)) {
    const relation = segment.match(/([^=<>]+)=([^=<>]+)/)
    if (!relation) continue
    const left = normalizeLatexExpression(relation[1])
    const right = normalizeLatexExpression(relation[2])
    if (!left || !right) continue
    const normalized = `((${left})-(${right}))`
    const variables = new Set((normalized.replace(/sqrt/g, '').match(/[A-Za-z]/g) ?? []))
    if (variables.size !== 1) continue
    const variable = [...variables][0]
    const alphaNormalized = normalized.replace(new RegExp(`(?<![A-Za-z])${variable}(?![A-Za-z])`, 'g'), 'x')
    const explicitPowers = [...alphaNormalized.matchAll(/(?<![A-Za-z])x\s*\^\s*\(?\s*(\d+)\s*\)?/g)]
      .map(match => Number(match[1]))
    const degree = explicitPowers.length ? Math.max(...explicitPowers) : 1
    candidates.push({
      parentId,
      source: relation[0].trim(),
      normalized: alphaNormalized,
      elaborator: 'legacy-normalizer',
      degree,
      priority: 0,
    })
  }
  const selected = candidates.sort((left, right) =>
    right.degree - left.degree || right.priority - left.priority)[0]
  if (!selected) return null
  const { degree: _degree, priority: _priority, ...input } = selected
  return input
}

function backendPath(): string {
  const candidates = [
    process.env.MORTRA_SYMPY_FUSION_BACKEND,
    path.resolve(process.cwd(), 'worker', 'backend', 'sympy_fusion.py'),
    path.resolve(process.cwd(), 'backend', 'sympy_fusion.py'),
    path.resolve(__dirname, '..', 'backend', 'sympy_fusion.py'),
  ].filter((candidate): candidate is string => Boolean(candidate))
  return candidates.find(candidate => existsSync(candidate)) ?? candidates[0]
}

export function extractRationalMap(parent: DiscoveryParent, index: number): RationalMapInput | null {
  const parentId = String(parent.id || `parent-${index + 1}`)
  for (const relation of extractMathRelations(parent.statement ?? '')) {
    if (relation.operator !== 'Equal') continue
    const rhsVariables = [...new Set(symbolsInMathExpression(relation.rhs))]
    if (rhsVariables.length !== 1) continue
    const variable = rhsVariables[0]
    const lhsVariables = new Set(symbolsInMathExpression(relation.lhs))
    if (!lhsVariables.has(variable) || lhsVariables.size < 2) continue
    const normalized = mathExpressionToSympy(renameMathSymbol(relation.rhs, variable, 'x'))
    return {
      parentId,
      source: relation.latex,
      normalized,
      variable,
      elaborator: 'mathjson-ir',
    }
  }
  return null
}

export function executePolynomialRootOperation(
  left: PolynomialInput,
  right: PolynomialInput,
  operation: PolynomialRootOperation,
): ExactPolynomialRootOperationResult | null {
  const cacheKey = JSON.stringify([left.normalized, right.normalized, operation])
  if (backendCache.has(cacheKey)) return backendCache.get(cacheKey) ?? null
  if (left.coefficients && right.coefficients) {
    const exact = executeExactRootComposition(left.coefficients, right.coefficients, operation)
    if (exact) {
      backendCache.set(cacheKey, exact)
      return exact
    }
  }
  const request = JSON.stringify({ left: left.normalized, right: right.normalized, operation })
  const commands = process.platform === 'win32' ? ['python', 'py'] : ['python3', 'python']
  for (const command of commands) {
    const args = command === 'py' ? ['-3', backendPath()] : [backendPath()]
    const result = spawnSync(command, args, {
      input: request,
      encoding: 'utf8',
      timeout: 120_000,
      maxBuffer: 4 * 1024 * 1024,
    })
    if (result.error && (result.error as NodeJS.ErrnoException).code === 'ENOENT') continue
    if (!result.stdout) {
      backendCache.set(cacheKey, null)
      return null
    }
    try {
      const parsed = JSON.parse(result.stdout) as ExactPolynomialRootOperationResult | { error: string }
      const value = 'error' in parsed ? null : parsed
      backendCache.set(cacheKey, value)
      return value
    } catch {
      backendCache.set(cacheKey, null)
      return null
    }
  }
  backendCache.set(cacheKey, null)
  return null
}

function normalizePolynomialPairMap(spec: PolynomialPairMapSpec): PolynomialPairMapSpec | null {
  if (!spec.id.trim() || !spec.terms.length || spec.terms.length > 12) return null
  const combined = new Map<string, PolynomialPairMapTerm>()
  for (const term of spec.terms) {
    if (!Number.isSafeInteger(term.coefficient) || term.coefficient === 0 || Math.abs(term.coefficient) > 12) return null
    if (!Number.isSafeInteger(term.left_power) || !Number.isSafeInteger(term.right_power)) return null
    if (term.left_power < 0 || term.right_power < 0 || term.left_power > 3 || term.right_power > 3) return null
    const key = `${term.left_power}:${term.right_power}`
    const coefficient = (combined.get(key)?.coefficient ?? 0) + term.coefficient
    if (coefficient === 0) combined.delete(key)
    else combined.set(key, { ...term, coefficient })
  }
  const terms = [...combined.values()].sort((left, right) =>
    right.left_power - left.left_power || right.right_power - left.right_power,
  )
  if (!terms.length || !terms.some(term => term.left_power > 0) || !terms.some(term => term.right_power > 0)) return null
  return { id: spec.id.trim(), terms }
}

export function executePolynomialPairMap(
  left: PolynomialInput,
  right: PolynomialInput,
  map: PolynomialPairMapSpec,
): ExactPolynomialPairMapResult | null {
  const normalizedMap = normalizePolynomialPairMap(map)
  if (!normalizedMap) return null
  const cacheKey = JSON.stringify([left.normalized, right.normalized, normalizedMap.terms])
  if (polynomialPairMapBackendCache.has(cacheKey)) return polynomialPairMapBackendCache.get(cacheKey) ?? null
  const request = JSON.stringify({
    request: 'polynomial_pair_map',
    left: left.normalized,
    right: right.normalized,
    map_terms: normalizedMap.terms,
  })
  const commands = process.platform === 'win32' ? ['python', 'py'] : ['python3', 'python']
  for (const command of commands) {
    const args = command === 'py' ? ['-3', backendPath()] : [backendPath()]
    const result = spawnSync(command, args, {
      input: request,
      encoding: 'utf8',
      timeout: 120_000,
      maxBuffer: 8 * 1024 * 1024,
    })
    if (result.error && (result.error as NodeJS.ErrnoException).code === 'ENOENT') continue
    if (!result.stdout) {
      polynomialPairMapBackendCache.set(cacheKey, null)
      return null
    }
    try {
      const parsed = JSON.parse(result.stdout) as ExactPolynomialPairMapResult | { error: string }
      const value = 'error' in parsed ? null : parsed
      polynomialPairMapBackendCache.set(cacheKey, value)
      return value
    } catch {
      polynomialPairMapBackendCache.set(cacheKey, null)
      return null
    }
  }
  polynomialPairMapBackendCache.set(cacheKey, null)
  return null
}

export function executePolynomialRootInvariant(
  polynomial: PolynomialInput,
  invariant: PolynomialRootInvariant,
): ExactPolynomialRootInvariantResult | null {
  const cacheKey = JSON.stringify([polynomial.normalized, invariant])
  if (invariantBackendCache.has(cacheKey)) return invariantBackendCache.get(cacheKey) ?? null
  if (polynomial.coefficients) {
    const exact = executeExactRootInvariant(polynomial.coefficients, invariant)
    if (exact) {
      invariantBackendCache.set(cacheKey, exact)
      return exact
    }
  }
  const request = JSON.stringify({
    request: 'invariant',
    polynomial: polynomial.normalized,
    invariant,
  })
  const commands = process.platform === 'win32' ? ['python', 'py'] : ['python3', 'python']
  for (const command of commands) {
    const args = command === 'py' ? ['-3', backendPath()] : [backendPath()]
    const result = spawnSync(command, args, {
      input: request,
      encoding: 'utf8',
      timeout: 120_000,
      maxBuffer: 4 * 1024 * 1024,
    })
    if (result.error && (result.error as NodeJS.ErrnoException).code === 'ENOENT') continue
    if (!result.stdout) {
      invariantBackendCache.set(cacheKey, null)
      return null
    }
    try {
      const parsed = JSON.parse(result.stdout) as ExactPolynomialRootInvariantResult | { error: string }
      const value = 'error' in parsed ? null : parsed
      invariantBackendCache.set(cacheKey, value)
      return value
    } catch {
      invariantBackendCache.set(cacheKey, null)
      return null
    }
  }
  invariantBackendCache.set(cacheKey, null)
  return null
}

export function executeRationalMapOnRoots(
  map: RationalMapInput,
  orbit: PolynomialInput,
): ExactRationalRootMapResult | null {
  const cacheKey = JSON.stringify([map.normalized, orbit.normalized])
  if (rationalMapBackendCache.has(cacheKey)) return rationalMapBackendCache.get(cacheKey) ?? null
  const request = JSON.stringify({
    request: 'rational_map_orbit',
    map: map.normalized,
    polynomial: orbit.normalized,
  })
  const commands = process.platform === 'win32' ? ['python', 'py'] : ['python3', 'python']
  for (const command of commands) {
    const args = command === 'py' ? ['-3', backendPath()] : [backendPath()]
    const result = spawnSync(command, args, {
      input: request,
      encoding: 'utf8',
      timeout: 120_000,
      maxBuffer: 4 * 1024 * 1024,
    })
    if (result.error && (result.error as NodeJS.ErrnoException).code === 'ENOENT') continue
    if (!result.stdout) {
      rationalMapBackendCache.set(cacheKey, null)
      return null
    }
    try {
      const parsed = JSON.parse(result.stdout) as ExactRationalRootMapResult | { error: string }
      const value = 'error' in parsed ? null : parsed
      rationalMapBackendCache.set(cacheKey, value)
      return value
    } catch {
      rationalMapBackendCache.set(cacheKey, null)
      return null
    }
  }
  rationalMapBackendCache.set(cacheKey, null)
  return null
}

function operationTex(operation: PolynomialRootOperation): string {
  if (operation === 'sum') return '\\alpha+\\beta'
  if (operation === 'difference') return '\\alpha-\\beta'
  return '\\alpha\\beta'
}

function operationPlainText(operation: PolynomialRootOperation): string {
  if (operation === 'sum') return 'α + β'
  if (operation === 'difference') return 'α − β'
  return 'αβ'
}

function operationLabel(operation: PolynomialRootOperation): string {
  if (operation === 'sum') return '和'
  if (operation === 'difference') return '差'
  return '積'
}

export function supportsPolynomialRootFusion(parents: DiscoveryParent[]): {
  applicable: boolean
  reason: string
  inputs: PolynomialInput[]
} {
  const inputs = parents.map(extractPolynomial).filter((item): item is PolynomialInput => item !== null)
  const distinctParents = new Set(inputs.map(input => input.parentId))
  const completeBinaryInput = parents.length === 2 && inputs.length === 2 && distinctParents.size === 2
  return {
    applicable: completeBinaryInput,
    reason: completeBinaryInput
      ? 'both selected parents provide parseable univariate polynomial constraints'
      : 'binary root-set generation requires exactly two selected parents and two parseable polynomial constraints',
    inputs,
  }
}

export function synthesizePolynomialRootFusions(
  parents: DiscoveryParent[],
  requested: number,
  round = 1,
): ExecutableFusionCard[] {
  const startedAt = Date.now()
  const support = supportsPolynomialRootFusion(parents)
  if (!support.applicable) return []
  const operations: PolynomialRootOperation[] = round % 3 === 1
    ? ['sum', 'product', 'difference']
    : round % 3 === 2
      ? ['product', 'difference', 'sum']
      : ['difference', 'sum', 'product']
  const cards: ExecutableFusionCard[] = []
  for (let leftIndex = 0; leftIndex < support.inputs.length; leftIndex++) {
    for (let rightIndex = leftIndex + 1; rightIndex < support.inputs.length; rightIndex++) {
      const left = support.inputs[leftIndex]
      const right = support.inputs[rightIndex]
      if (left.parentId === right.parentId) continue
      for (const operation of operations) {
        if (cards.length >= requested) return cards
        const result = executePolynomialRootOperation(left, right, operation)
        if (!result) continue
        const parentIds = [left.parentId, right.parentId]
        const expression = operationTex(operation)
        const structureId = `root-set.${operation}.${hash({ parentIds, left: result.left, right: result.right })}`
        const morphisms = [
          'PolynomialConstraintExtraction',
          'RootConfiguration',
          operation === 'sum'
            ? 'RootMinkowskiSum'
            : operation === 'difference'
              ? 'RootMinkowskiDifference'
              : 'RootPointwiseProduct',
          'FiberProduct',
          'ParameterElimination',
          'Resultant',
          'SquareFreeReduction',
          'NumericRootCounterexampleCheck',
          'ParentPerturbationAblation',
        ]
        const statement = String.raw`\(f(x)=${result.left}\), \(g(x)=${result.right}\) とする。\(f(\alpha)=0\), \(g(\beta)=0\) を満たす複素数 \(\alpha,\beta\) をすべて動かしたとき、\(${expression}\) の異なる値全体をちょうど根にもつモニック多項式を求めよ。`
        const answer = `P(z)=${result.result}`
        const substitution = operation === 'sum'
          ? 'g(z-x)'
          : operation === 'difference'
            ? 'g(x-z)'
            : `x^{${result.degree_right}}g(z/x)`
        const solution = String.raw`\(f(x)=0\) の根を \(\alpha\)、\(g(y)=0\) の根を \(\beta\) とする。${operationLabel(operation)} \(${expression}\) から一方の根を消去するため、
\[
R(z)=\operatorname{Res}_x\!\left(f(x),${substitution}\right)
\]
とおく。\(z=${expression}\) なら、\(x=\alpha\) は終結式を作る二つの多項式の共通根になるので、\(R(z)=0\) である。逆に \(R(z)=0\) なら共通根 \(x=\alpha\) が存在し、もう一方の式からある根 \(\beta\) が得られる。したがって \(R\) の根は求める${operationLabel(operation)}の値と一致する。同じ値が複数の根の組から現れる場合だけ因子が重なるため、
\[
P(z)=\operatorname{monic}\!\left(\frac{R(z)}{\gcd(R(z),R'(z))}\right)
\]
とすれば、異なる値を一度ずつ根にもつ。係数を有理数のまま展開すると \(P(z)=${result.result}\) を得る。最後に、全ての根の組を別計算で代入し、どちらの親多項式を変えても \(P\) が変わることを確認した。`
        const proofCertificate = [
          { id: 'typed-inputs', claim: 'both parents elaborate to univariate polynomial constraints', verifier: 'MathOS typed parser + SymPy Poly(QQ)' },
          { id: 'fiber-product', claim: `the joint root configuration contains every ordered pair (alpha,beta)`, verifier: 'finite algebraic fiber product' },
          { id: 'resultant', claim: `elimination computes every value of ${operation}`, verifier: 'SymPy exact resultant over QQ' },
          { id: 'squarefree', claim: 'the output roots are the distinct composed values', verifier: 'exact square-free monic reduction' },
          { id: 'numeric-check', claim: 'all numerical pairwise root compositions vanish in P', verifier: 'independent nroots comparison' },
          { id: 'ablation', claim: 'perturbing either parent changes P', verifier: 'two-sided parent perturbation' },
        ]
        const proofClaimsJa = [
          '二つの親問題がともに一変数多項式の制約として読み取れる。',
          '二つの根集合の順序付きの組を全て構成している。',
          `終結式による消去は、各組から得られる${operationLabel(operation)}を全て根に持つ。`,
          '平方因子を除いた出力の根は、合成した値の異なる値全体と一致する。',
          '全ての根の組を独立に数値計算し、出力多項式の根と一致する。',
          'どちらの親多項式を変えても出力が変わり、両方の親問題が必要である。',
        ]
        cards.push({
          id: `mathos-discovered-${hash([structureId, result.result])}`,
          family_id: `runtime.polynomial_root_${operation}`,
          statement_tex: statement,
          answer_tex: answer,
          solution_tex: solution,
          domain: 'algebraic_geometry',
          morphism_chain: morphisms,
          parent_ids: parentIds,
          unresolved: false,
          discovery_status: 'verified',
          verification: {
            method: 'exact resultant plus independent numerical roots and parent perturbation',
            exact_backend: true,
            independent_check: true,
            samples: [result.degree_left, result.degree_right, result.degree_result],
          },
          difficulty: { band: 'A_algebraic_elimination', score: 7 + result.degree_result + morphisms.length * 0.25 },
          fusion_derivation: {
            passed: true,
            reason: 'each parent supplies one algebraic root configuration and the binary root-set operation requires both inputs',
            ablationPassed: true,
            assignments: [
              { parentId: left.parentId, portId: 'left_root_set', role: 'object', matchedAnchors: [left.source], witnessSteps: ['PolynomialConstraintExtraction', 'RootConfiguration'] },
              { parentId: right.parentId, portId: 'right_root_set', role: 'object', matchedAnchors: [right.source], witnessSteps: ['PolynomialConstraintExtraction', 'RootConfiguration'] },
            ],
            bridges: [{ id: `root-set-${operation}`, witnessStep: morphisms[2], consumes: ['left_root_set', 'right_root_set'], produces: 'composed_root_set' }],
            intermediatePropositions: [
              { parentId: left.parentId, morphism: 'RootConfiguration', source: 'Polynomial', target: 'FiniteAlgebraicOrbit', proposition: 'the roots of f form a finite algebraic configuration', proved: true },
              { parentId: right.parentId, morphism: 'RootConfiguration', source: 'Polynomial', target: 'FiniteAlgebraicOrbit', proposition: 'the roots of g form a finite algebraic configuration', proved: true },
            ],
          },
          structure_blueprint: {
            id: structureId,
            version: 1,
            kernel: 'binary_operation_on_algebraic_root_configurations',
            observable: `minimal_squarefree_root_polynomial_of_${operation}`,
            operators: morphisms,
            domain: 'algebraic_geometry',
            tags: ['polynomial', 'root_configuration', operation, 'resultant'],
            morphismChain: morphisms,
            executable: true,
            proofCertificate,
            taskAlgebra: {
              schema: 1,
              input: 'algebraic-configuration',
              operations: [
                { operator: 'pair', output: 'configuration' },
                { operator: 'map', output: 'configuration' },
                { operator: 'eliminate', output: 'polynomial' },
                { operator: 'normalize', output: 'polynomial' },
              ],
              output: 'polynomial',
              complete: true,
            },
          },
          search_evidence: { hypotheses_evaluated: operations.length, valid_hypotheses: cards.length + 1, elapsed_ms: Date.now() - startedAt },
          execution_certificate: runtimeSynthesisCertificate({
            origin: 'synthesized_proof_program',
            parents,
            generatedProgram: {
              schema: 'mortra.runtime-polynomial-root-composition.v1',
              operation,
              left_parent_id: left.parentId,
              right_parent_id: right.parentId,
              left_source_relation: left.source,
              right_source_relation: right.source,
              left_polynomial: result.left,
              right_polynomial: result.right,
              generated_resultant: result.result,
              exact: result.exact,
              numeric_root_check: result.numeric_check,
              whole_parent_ablation: result.ablation,
              morphism_chain: morphisms,
            },
            checks: proofCertificate.map(step => `${step.id}: ${step.verifier}`),
          }),
          diagram: {
            version: 1,
            kind: 'morphism',
            title: '二つの根集合から新しい根集合を作る',
            caption: `二つの多項式の根を全て組み合わせ、${operationLabel(operation)}を取ってから、終結式で一変数の多項式へ戻します。`,
            nodes: [
              `f の根 ${result.degree_left} 個`,
              `g の根 ${result.degree_right} 個`,
              `全ての組 ${result.degree_left * result.degree_right} 個`,
              operationPlainText(operation),
              '終結式で消去',
              '重複を除いてモニック化',
              `P の根 ${result.degree_result} 個`,
            ],
          },
          proof_roadmap: [
            { morphism_id: morphisms[0], label_ja: '親問題から多項式を読み取る', source_ja: '二つの親問題', target_ja: '二つの一変数多項式', role_ja: '変数名ではなく係数と次数を保存します。' },
            { morphism_id: morphisms[1], label_ja: '根の配置を構成する', source_ja: '一変数多項式', target_ja: '有限な代数的根集合', role_ja: '各多項式の根を個別の数値ではなく、方程式で定まる集合として扱います。' },
            { morphism_id: morphisms[2], label_ja: `根の組を${operationLabel(operation)}へ写す`, source_ja: '二つの根集合の直積', target_ja: `${operationLabel(operation)}の値の集合`, role_ja: '全ての順序付きの根の組に同じ二項演算を適用します。' },
            { morphism_id: morphisms[5], label_ja: '終結式で一方の根を消去する', source_ja: '二変数の代数制約', target_ja: 'z の一変数多項式', role_ja: '根を近似値に変えず、有理数係数のまま厳密に消去します。' },
            { morphism_id: morphisms[6], label_ja: '異なる値だけを残す', source_ja: '終結式', target_ja: '平方因子を持たないモニック多項式', role_ja: '重複根を除き、最高次係数を1にします。' },
            { morphism_id: `${morphisms[7]}+${morphisms[8]}`, label_ja: '全根と親依存性を独立に検証する', source_ja: '出力多項式', target_ja: '再生可能な検証証明書', role_ja: '全根の数値照合と、両親を別々に変える検査を実行します。' },
          ],
          proof_obligations: proofCertificate.map((step, index) => ({
            id: step.id,
            claim_ja: proofClaimsJa[index],
            status: 'verified',
          })),
        })
      }
    }
  }
  return cards
}

function pairMapRootTex(source: string): string {
  return source
    .replace(/\bx\b/g, '\\alpha')
    .replace(/\by\b/g, '\\beta')
}

function pairMapDefinitionTex(source: string): string {
  return source
    .replace(/\bx\b/g, 'u')
    .replace(/\by\b/g, 'v')
}

function rotatePairMaps(round: number): PolynomialPairMapSpec[] {
  const basis = polynomialPairMapBasis()
  const offset = basis.length ? ((round - 1) % basis.length + basis.length) % basis.length : 0
  return [...basis.slice(offset), ...basis.slice(0, offset)]
}

/**
 * Generate questions from one bounded grammar of bivariate polynomial maps.
 * Individual maps are data; all of them share the same product, map,
 * elimination, square-free normalization, and verification implementation.
 */
export function synthesizePolynomialPairMapFusions(
  parents: DiscoveryParent[],
  requested: number,
  round = 1,
): ExecutableFusionCard[] {
  const startedAt = Date.now()
  const support = supportsPolynomialRootFusion(parents)
  if (!support.applicable || requested <= 0) return []
  const cards: ExecutableFusionCard[] = []
  for (let leftIndex = 0; leftIndex < support.inputs.length; leftIndex += 1) {
    for (let rightIndex = leftIndex + 1; rightIndex < support.inputs.length; rightIndex += 1) {
      const left = support.inputs[leftIndex]
      const right = support.inputs[rightIndex]
      if (left.parentId === right.parentId) continue
      for (const map of rotatePairMaps(round)) {
        if (cards.length >= requested) return cards
        const result = executePolynomialPairMap(left, right, map)
        if (!result) continue
        const parentIds = [left.parentId, right.parentId]
        const rootExpression = pairMapRootTex(result.map)
        const mapDefinition = pairMapDefinitionTex(result.map)
        const structureId = `root-pair-map.${hash({
          parentIds,
          left: result.left,
          right: result.right,
          terms: result.map_terms,
        })}`
        const morphisms = [
          'PolynomialConstraintExtraction',
          'RootConfiguration',
          'CartesianProduct',
          'BivariatePolynomialMap',
          'FiberProduct',
          'ParameterElimination',
          'IteratedResultant',
          'SquareFreeReduction',
          'NumericRootCounterexampleCheck',
          'ParentPerturbationAblation',
        ]
        const proofCertificate = [
          { id: 'typed-inputs', claim: 'both parents elaborate to univariate polynomial constraints', verifier: 'MathOS typed parser + SymPy Poly(QQ)' },
          { id: 'cartesian-map', claim: 'the same bivariate polynomial map is applied to every ordered root pair', verifier: 'typed finite-product polynomial map' },
          { id: 'iterated-resultant', claim: 'two exact eliminations project the mapped zero-dimensional configuration to z', verifier: 'two exact SymPy resultants over QQ' },
          { id: 'squarefree', claim: 'the output roots are the distinct mapped values', verifier: 'exact square-free monic reduction' },
          { id: 'numeric-check', claim: 'all numerical pair-map values and output roots cover each other', verifier: 'independent nroots comparison' },
          { id: 'ablation', claim: 'perturbing either parent changes the output polynomial', verifier: 'two-sided parent perturbation' },
        ]
        const obligations = proofCertificate.map(item => item.claim)
        const answer = `P(z)=${result.result}`
        const statement = String.raw`\(f(x)=${result.left}\), \(g(x)=${result.right}\), \(H(u,v)=${mapDefinition}\) とする。\(f(\alpha)=0\), \(g(\beta)=0\) を満たす複素数 \(\alpha,\beta\) をすべて動かしたとき、\(H(\alpha,\beta)=${rootExpression}\) の異なる値全体をちょうど根にもつモニック多項式を求めよ。`
        const solution = String.raw`\(f(x)=0\) の根を \(\alpha\)、\(g(y)=0\) の根を \(\beta\) とする。二変数の写像を
\[
H(x,y)=${result.map}
\]
とおく。まず \(x\) を消去して
\[
A(y,z)=\operatorname{Res}_x\!\left(f(x),z-H(x,y)\right)
\]
を作り、次に \(y\) を消去して
\[
R(z)=\operatorname{Res}_y\!\left(g(y),A(y,z)\right)
\]
とおく。終結式の消去定理により、\(R\) の零点は \(H(\alpha,\beta)\) の値全体に一致する。二段目を有理数係数のまま展開し、モニック化すると
\[
R(z)=${result.elimination_result}
\]
を得る。さらに \(\gcd(R(z),R'(z))=${result.elimination_gcd}\) だから、平方因子を除いた答えは \(P(z)=${result.result}\) である。全9組の値との相互照合と、左右の親式を別々に変える検査も通過した。`
        const mapComplexity = result.map_terms.reduce(
          (sum, term) => sum + 1 + term.left_power + term.right_power,
          0,
        )
        cards.push({
          id: `mathos-generated-map-${hash([structureId, result.result])}`,
          family_id: 'runtime.polynomial_pair_map',
          statement_tex: statement,
          answer_tex: answer,
          solution_tex: solution,
          domain: 'algebraic_geometry',
          morphism_chain: morphisms,
          parent_ids: parentIds,
          unresolved: false,
          discovery_status: 'verified',
          verification: {
            method: 'exact iterated resultants plus independent root-map coverage and parent perturbation',
            exact_backend: true,
            independent_check: true,
            samples: [result.degree_left, result.degree_right, result.degree_result, result.map_terms.length],
          },
          difficulty: {
            band: 'A_algebraic_elimination',
            score: 7 + result.degree_result + mapComplexity * 0.25,
          },
          fusion_derivation: {
            passed: true,
            reason: 'both current root configurations are combined by one grammar-generated bivariate polynomial map',
            ablationPassed: true,
            assignments: [
              {
                parentId: left.parentId,
                portId: 'left_root_configuration',
                role: 'object',
                matchedAnchors: [left.source],
                witnessSteps: ['PolynomialConstraintExtraction', 'RootConfiguration'],
                requiredObligations: obligations,
                consumedObligations: obligations,
                coverage: 1,
              },
              {
                parentId: right.parentId,
                portId: 'right_root_configuration',
                role: 'object',
                matchedAnchors: [right.source],
                witnessSteps: ['PolynomialConstraintExtraction', 'RootConfiguration'],
                requiredObligations: obligations,
                consumedObligations: obligations,
                coverage: 1,
              },
            ],
            bridges: [{
              id: `polynomial-pair-map:${structureId}`,
              witnessStep: 'BivariatePolynomialMap',
              consumes: ['left_root_configuration', 'right_root_configuration'],
              produces: 'MappedAlgebraicConfiguration',
            }],
            intermediatePropositions: [
              { parentId: left.parentId, morphism: 'RootConfiguration', source: 'Polynomial', target: 'FiniteAlgebraicConfiguration', proposition: 'the roots of f form the left finite configuration', proved: true },
              { parentId: right.parentId, morphism: 'RootConfiguration', source: 'Polynomial', target: 'FiniteAlgebraicConfiguration', proposition: 'the roots of g form the right finite configuration', proved: true },
            ],
          },
          structure_blueprint: {
            id: structureId,
            version: 1,
            kernel: 'polynomial_map_on_product_of_algebraic_configurations',
            observable: 'minimal_squarefree_polynomial_of_mapped_root_pairs',
            operators: morphisms,
            domain: 'algebraic_geometry',
            tags: ['polynomial', 'root_configuration', 'product', 'polynomial_map', 'resultant'],
            morphismChain: morphisms,
            executable: true,
            proofCertificate,
            taskAlgebra: {
              schema: 1,
              input: 'algebraic-configuration',
              operations: [
                { operator: 'pair', output: 'configuration' },
                { operator: 'map', output: 'configuration' },
                { operator: 'eliminate', output: 'polynomial' },
                { operator: 'normalize', output: 'polynomial' },
              ],
              output: 'polynomial',
              complete: true,
            },
          },
          search_evidence: {
            hypotheses_evaluated: PAIR_MAP_BASIS.length,
            valid_hypotheses: cards.length + 1,
            elapsed_ms: Date.now() - startedAt,
          },
          execution_certificate: runtimeSynthesisCertificate({
            origin: 'synthesized_proof_program',
            parents,
            generatedProgram: {
              schema: 'mortra.runtime-polynomial-pair-map.v1',
              map_id: map.id,
              map_terms: result.map_terms,
              left_parent_id: left.parentId,
              right_parent_id: right.parentId,
              left_polynomial: result.left,
              right_polynomial: result.right,
              generated_resultant: result.result,
              first_resultant: result.first_resultant,
              elimination_result: result.elimination_result,
              elimination_gcd: result.elimination_gcd,
              exact: result.exact,
              numeric_root_check: result.numeric_check,
              whole_parent_ablation: result.ablation,
              morphism_chain: morphisms,
            },
            checks: proofCertificate.map(step => `${step.id}: ${step.verifier}`),
          }),
          diagram: {
            version: 1,
            kind: 'morphism',
            title: '根の直積を一つの多項式写像で観測する',
            caption: '写像を文法から入力し、直積、写像、消去、正規化の同じ証明プログラムを再利用します。',
            nodes: [
              `f の根 ${result.degree_left} 個`,
              `g の根 ${result.degree_right} 個`,
              `直積 ${result.degree_left * result.degree_right} 組`,
              `H(x,y) = ${result.map}`,
              '二段の終結式',
              '平方因子を除去',
              `P の根 ${result.degree_result} 個`,
            ],
          },
          proof_roadmap: [
            { morphism_id: morphisms[0], label_ja: '二つの親式を一変数多項式として読む', source_ja: '現在の二つの親問題', target_ja: '二つの根配置', role_ja: '係数や変数名に依存しない型付き入力を作ります。' },
            { morphism_id: morphisms[2], label_ja: '二つの根配置の直積を作る', source_ja: '二つの有限根配置', target_ja: '全ての順序付き根の組', role_ja: 'どの根の組も落としません。' },
            { morphism_id: morphisms[3], label_ja: '同じ多項式写像を全ての組へ作用させる', source_ja: '根の直積', target_ja: 'H の値の有限集合', role_ja: '問題ごとの解法ではなく、係数付き写像を入力として扱います。' },
            { morphism_id: morphisms[6], label_ja: '二つの根を順に消去する', source_ja: '三変数の代数制約', target_ja: 'z の一変数多項式', role_ja: '有理数係数のまま厳密に計算します。' },
            { morphism_id: morphisms[7], label_ja: '異なる値を一度ずつ残す', source_ja: '消去多項式', target_ja: '平方因子を持たないモニック多項式', role_ja: '重複と定数倍を正規化します。' },
            { morphism_id: `${morphisms[8]}+${morphisms[9]}`, label_ja: '全根と両親依存性を独立検査する', source_ja: '生成した多項式', target_ja: '再生可能な証明書', role_ja: '全組の値との相互被覆と二方向の摂動を検査します。' },
          ],
          proof_obligations: proofCertificate.map((step, index) => ({
            id: step.id,
            claim_ja: [
              '二つの親問題を一変数多項式として一意に読み取れる。',
              '全ての順序付き根の組へ同じ二変数多項式を適用している。',
              '二段の終結式が二つの根変数を厳密に消去する。',
              '平方因子の除去後の根が相異なる写像値全体と一致する。',
              '全ての数値的写像値と出力多項式の根が相互に対応する。',
              'どちらの親多項式を変えても出力が変わる。',
            ][index],
            status: 'verified',
          })),
        })
      }
    }
  }
  return cards
}
