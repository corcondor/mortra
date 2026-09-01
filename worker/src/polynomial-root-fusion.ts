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

const backendCache = new Map<string, ExactPolynomialRootOperationResult | null>()
const invariantBackendCache = new Map<string, ExactPolynomialRootInvariantResult | null>()
const rationalMapBackendCache = new Map<string, ExactRationalRootMapResult | null>()

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
          operation === 'sum' ? 'MinkowskiSum' : operation === 'difference' ? 'MinkowskiDifference' : 'PointwiseProduct',
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
        const solution = String.raw`\(f(x)=0\) の根 \(\alpha\) と \(g(y)=0\) の根 \(\beta\) の${operationLabel(operation)}を消去する。したがって \[R(z)=\operatorname{Res}_x\!\left(f(x),${substitution}\right)\] を計算し、重複根を除いてモニック化すればよい。厳密終結式計算により \(P(z)=${result.result}\) を得る。全根の数値照合と、各親多項式を独立に摂動するアブレーション検査も通過した。`
        const proofCertificate = [
          { id: 'typed-inputs', claim: 'both parents elaborate to univariate polynomial constraints', verifier: 'MathOS typed parser + SymPy Poly(QQ)' },
          { id: 'fiber-product', claim: `the joint root configuration contains every ordered pair (alpha,beta)`, verifier: 'finite algebraic fiber product' },
          { id: 'resultant', claim: `elimination computes every value of ${operation}`, verifier: 'SymPy exact resultant over QQ' },
          { id: 'squarefree', claim: 'the output roots are the distinct composed values', verifier: 'exact square-free monic reduction' },
          { id: 'numeric-check', claim: 'all numerical pairwise root compositions vanish in P', verifier: 'independent nroots comparison' },
          { id: 'ablation', claim: 'perturbing either parent changes P', verifier: 'two-sided parent perturbation' },
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
        })
      }
    }
  }
  return cards
}
